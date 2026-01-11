"""Main application loop for vision event pipeline."""
import logging
import time
from typing import Optional

import cv2
import numpy as np

from src.infrastructure.config import AppConfig, save_polygon
from src.infrastructure.minio_client import MinioRepository
from src.infrastructure.rabbitmq_client import RabbitMQPublisher
from src.application.event_aggregator import EventAggregator
from src.application.use_cases import HandleVisionEventUseCase
from src.presentation.detector import PersonDetector


logger = logging.getLogger(__name__)


class VisionApp:
    """
    Main application for vision event pipeline.
    
    Features:
    - Camera capture with YOLO person detection
    - Interactive polygon drawing for forbidden zone
    - Event aggregation with 5-second windows
    - MinIO storage (frames + events)
    - RabbitMQ alerting
    """
    
    WINDOW_NAME = "Vision Event Pipeline"
    
    def __init__(self, config: AppConfig):
        """
        Initialize vision application.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Initialize detector
        self.detector = PersonDetector(
            model_path=config.model_path,
            conf_threshold=config.conf_threshold,
            polygon=config.polygon
        )
        
        # Initialize infrastructure (with graceful degradation)
        self.minio_repo: Optional[MinioRepository] = None
        self.rabbitmq_pub: Optional[RabbitMQPublisher] = None
        
        try:
            self.minio_repo = MinioRepository(
                endpoint=config.minio_endpoint,
                access_key=config.minio_access_key,
                secret_key=config.minio_secret_key,
                bucket=config.minio_bucket,
                secure=config.minio_secure
            )
        except Exception as e:
            logger.warning(f"MinIO initialization failed: {e}")
        
        try:
            self.rabbitmq_pub = RabbitMQPublisher(
                host=config.rabbit_host,
                port=config.rabbit_port,
                user=config.rabbit_user,
                password=config.rabbit_pass,
                exchange=config.rabbit_exchange
            )
        except Exception as e:
            logger.warning(f"RabbitMQ initialization failed: {e}")
        
        # Initialize aggregator and use case
        self.aggregator = EventAggregator(
            camera_id=config.camera_id,
            window_sec=config.emit_every_sec,
            gap_sec=config.session_gap_sec
        )
        
        self.use_case = HandleVisionEventUseCase(
            minio_repo=self.minio_repo,
            rabbitmq_pub=self.rabbitmq_pub,
            snapshot_prefix=config.s3_prefix_snapshots,
            events_prefix=config.s3_prefix_events,
            jpeg_quality=config.snapshot_jpeg_quality
        )
        
        # Polygon drawing state
        self._temp_polygon: list[list[int]] = []
        self._polygon: list[list[int]] = config.polygon.copy()
    
    def _on_mouse(self, event: int, x: int, y: int, flags: int, param) -> None:
        """Mouse callback for polygon drawing."""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Add point to temporary polygon
            self._temp_polygon.append([x, y])
        
        elif event == cv2.EVENT_RBUTTONDOWN:
            # Finalize polygon
            if len(self._temp_polygon) > 2:
                self._polygon = list(self._temp_polygon)
                self._temp_polygon = []
                
                # Update detector and save
                self.detector.set_polygon(self._polygon)
                save_polygon(self._polygon)
                logger.info(f"Polygon saved: {len(self._polygon)} points")
    
    def run(self) -> None:
        """Run the main detection loop."""
        logger.info(f"Starting Vision App: camera={self.config.camera_id}")
        
        # Open camera
        cap = cv2.VideoCapture(self.config.camera_index)
        if not cap.isOpened():
            logger.error(f"Cannot open camera: {self.config.camera_index}")
            return
        
        # Setup window
        cv2.namedWindow(self.WINDOW_NAME)
        cv2.setMouseCallback(self.WINDOW_NAME, self._on_mouse)
        
        frame_count = 0
        target_fps = 15
        
        try:
            while cap.isOpened():
                t0 = time.time()
                
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame")
                    break
                
                frame_count += 1
                
                # Run detection (optionally skip frames)
                if frame_count % self.config.infer_every_n == 0:
                    detections = self.detector.detect(frame)
                    
                    # Update aggregator
                    event = self.aggregator.update(detections, frame)
                    
                    # Handle event if emitted
                    if event:
                        snapshot = self.aggregator.get_snapshot_frame()
                        self.use_case.execute(event, snapshot)
                else:
                    detections = []
                
                # Draw visualization
                display_frame = self.detector.draw_detections(frame, detections)
                
                # Draw temporary polygon (being drawn)
                if self._temp_polygon:
                    pts = np.array(self._temp_polygon, np.int32)
                    cv2.polylines(display_frame, [pts], False, (0, 0, 255), 2)
                
                # Draw status
                self._draw_status(display_frame)
                
                # Show frame
                cv2.imshow(self.WINDOW_NAME, display_frame)
                
                # FPS limiting
                elapsed = time.time() - t0
                wait_ms = max(1, int(1000 / target_fps - elapsed * 1000))
                
                key = cv2.waitKey(wait_ms) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('c'):
                    # Clear polygon
                    self._temp_polygon = []
                    self._polygon = []
                    self.detector.set_polygon([])
                    logger.info("Polygon cleared")
        
        finally:
            # Cleanup
            logger.info("Shutting down...")
            
            # Force end any active session
            final_event = self.aggregator.force_end_session()
            if final_event:
                snapshot = self.aggregator.get_snapshot_frame()
                self.use_case.execute(final_event, snapshot)
            
            self.use_case.flush()
            
            if self.rabbitmq_pub:
                self.rabbitmq_pub.close()
            
            cap.release()
            cv2.destroyAllWindows()
            
            logger.info("Vision App stopped")
    
    def _draw_status(self, frame: np.ndarray) -> None:
        """Draw status overlay on frame."""
        h, w = frame.shape[:2]
        
        # Status text
        state = self.aggregator.state.value
        minio_status = "[OK]" if self.minio_repo and self.minio_repo.is_connected else "[OFF]"
        rabbit_status = "[OK]" if self.rabbitmq_pub and self.rabbitmq_pub.is_connected else "[OFF]"
        
        lines = [
            f"State: {state}",
            f"MinIO: {minio_status}  RabbitMQ: {rabbit_status}",
            f"Polygon: {len(self._polygon)} pts | Press 'q' to quit, 'c' to clear"
        ]
        
        # Draw background
        y_start = h - 80
        cv2.rectangle(frame, (0, y_start), (w, h), (0, 0, 0), -1)
        
        # Draw text
        for i, line in enumerate(lines):
            y = y_start + 20 + i * 22
            cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
