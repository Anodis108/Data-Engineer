"""Vòng lặp ứng dụng chính cho luồng xử lý sự kiện vision."""
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
    """Ứng dụng chính cho luồng xử lý sự kiện vision."""
    
    WINDOW_NAME = "Vision Event Pipeline"
    
    def __init__(self, config: AppConfig):
        """Khởi tạo ứng dụng vision và các thành phần của nó."""
        self.config = config
        
        self.detector = PersonDetector(
            model_path=config.model_path,
            conf_threshold=config.conf_threshold,
            polygon=config.polygon
        )
        
        self.minio_repo = MinioRepository(
            endpoint=config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            bucket=config.minio_bucket,
            secure=config.minio_secure
        )
        
        self.rabbitmq_pub = RabbitMQPublisher(
            host=config.rabbit_host,
            port=config.rabbit_port,
            user=config.rabbit_user,
            password=config.rabbit_pass,
            exchange=config.rabbit_exchange
        )
        
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
        
        self._temp_polygon: list[list[int]] = []
        self._polygon: list[list[int]] = config.polygon.copy()
    
    
    def _run_pipeline(self, frame: np.ndarray) -> list:
        """
        Thực thi luồng xử lý vision cốt lõi.
        
        Các bước:
        1. Phát hiện người và kiểm tra vùng polygon
        2. Tổng hợp kết quả thành các sự kiện (cửa sổ 5s)
        3. Xử lý sự kiện (Lưu trữ + Cảnh báo)
        """
        # 1. Phát hiện
        detections = self.detector.detect(frame)
        
        # 2. Tổng hợp
        event = self.aggregator.update(detections, frame)
        
        # 3. Thực thi (Tác dụng phụ)
        if event:
            snapshot = self.aggregator.get_snapshot_frame()
            self.use_case.execute(event, snapshot)
            
        return detections
    
    def run(self) -> None:
        """Chạy vòng lặp phát hiện chính."""
        logger.info(f"Đang khởi động Vision App: camera={self.config.camera_id}")
        
        cap = cv2.VideoCapture(self.config.camera_index)
        if not cap.isOpened():
            logger.error(f"Không thể mở camera: {self.config.camera_index}")
            return
        
        cv2.namedWindow(self.WINDOW_NAME)
        cv2.setMouseCallback(self.WINDOW_NAME, self._on_mouse)
        
        frame_count = 0
        target_fps = 15
        
        try:
            while cap.isOpened():
                t0 = time.time()
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Không thể đọc frame")
                    break
                
                frame_count += 1
                
                # Chạy pipeline (tùy chọn bỏ qua frame)
                if frame_count % self.config.infer_every_n == 0:
                    detections = self._run_pipeline(frame)
                else:
                    detections = []
                
                display_frame = self.detector.draw_detections(frame, detections)
                
                if self._temp_polygon:
                    pts = np.array(self._temp_polygon, np.int32)
                    cv2.polylines(display_frame, [pts], False, (0, 0, 255), 2)
                
                self._draw_status(display_frame)
                cv2.imshow(self.WINDOW_NAME, display_frame)
                
                elapsed = time.time() - t0
                wait_ms = max(1, int(1000 / target_fps - elapsed * 1000))
                
                key = cv2.waitKey(wait_ms) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('c'):
                    self._temp_polygon = []
                    self._polygon = []
                    self.detector.set_polygon([])
                    logger.info("Đã xóa polygon")
        
        finally:
            logger.info("Đang tắt ứng dụng...")
            final_event = self.aggregator.force_end_session()
            if final_event:
                snapshot = self.aggregator.get_snapshot_frame()
                self.use_case.execute(final_event, snapshot)
            
            self.use_case.flush()
            if self.rabbitmq_pub:
                self.rabbitmq_pub.close()
            cap.release()
            cv2.destroyAllWindows()
            logger.info("Vision App đã dừng")
    
    def _on_mouse(self, event: int, x: int, y: int, flags: int, param) -> None:
        """Callback chuột để vẽ polygon tương tác."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self._temp_polygon.append([x, y])
        
        elif event == cv2.EVENT_RBUTTONDOWN:
            if len(self._temp_polygon) > 2:
                self._polygon = list(self._temp_polygon)
                self._temp_polygon = []
                self.detector.set_polygon(self._polygon)
                save_polygon(self._polygon)
                logger.info(f"Đã lưu polygon: {len(self._polygon)} điểm")
    
    
    def _draw_status(self, frame: np.ndarray) -> None:
        """Vẽ trạng thái lên frame."""
        h, w = frame.shape[:2]
        state = self.aggregator.state.value
        minio_status = "[OK]" if self.minio_repo and self.minio_repo.is_connected else "[TAT]"
        rabbit_status = "[OK]" if self.rabbitmq_pub and self.rabbitmq_pub.is_connected else "[TAT]"
        
        lines = [
            f"Trang thai: {state}",
            f"MinIO: {minio_status}  RabbitMQ: {rabbit_status}",
            f"Polygon: {len(self._polygon)} diem | Nhan 'q' de thoat, 'c' de xoa"
        ]
        
        y_start = h - 80
        cv2.rectangle(frame, (0, y_start), (w, h), (0, 0, 0), -1)
        
        for i, line in enumerate(lines):
            y = y_start + 20 + i * 22
            cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
