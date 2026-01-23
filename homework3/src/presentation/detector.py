"""Person detector with YOLO and polygon zone checking."""
import logging
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO

from src.domain.entities import Detection


logger = logging.getLogger(__name__)


class PersonDetector:
    """YOLO-based person detector with polygon zone checking."""
    
    def __init__(
        self,
        model_path: str = "yolo11s.pt",
        conf_threshold: float = 0.35,
        polygon: Optional[list[list[int]]] = None,
        imgsz: int = 640
    ):
        """
        Initialize person detector.
        
        Args:
            model_path: Path to YOLO model weights
            conf_threshold: Confidence threshold for detection
            polygon: Polygon defining the forbidden zone [[x1,y1], [x2,y2], ...]
            imgsz: Input image size for YOLO
        """
        self.conf_threshold = conf_threshold
        self.polygon = polygon or []
        self.imgsz = imgsz
        
        # Load YOLO model
        logger.info(f"Loading YOLO model: {model_path}")
        self.model = YOLO(model_path)
        logger.info("YOLO model loaded")
    
    def set_polygon(self, polygon: list[list[int]]) -> None:
        """Update the forbidden zone polygon."""
        self.polygon = polygon
        logger.debug(f"Polygon updated: {len(polygon)} points")
    
    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Detect persons in frame.
        
        Args:
            frame: BGR frame from camera
        
        Returns:
            List of Detection objects
        """
        # Run YOLO inference (class 0 = person)
        results = self.model(
            frame,
            classes=[0],
            conf=self.conf_threshold,
            verbose=False,
            imgsz=self.imgsz
        )
        
        detections = []
        
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            xyxy = boxes.xyxy.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy()
            
            for i, box in enumerate(xyxy):
                x1, y1, x2, y2 = box
                confidence = float(confs[i])
                
                # Check if center is inside polygon
                center = ((x1 + x2) / 2, (y1 + y2) / 2)
                is_inside = self._point_in_polygon(center)
                
                detections.append(Detection(
                    bbox=(x1, y1, x2, y2),
                    confidence=confidence,
                    is_inside_zone=is_inside
                ))
        
        return detections
    
    def _point_in_polygon(self, point: tuple[float, float]) -> bool:
        """Check if a point is inside the polygon."""
        if len(self.polygon) < 3:
            return False
        
        poly_np = np.array(self.polygon, np.int32)
        result = cv2.pointPolygonTest(poly_np, point, False)
        return result >= 0
    
    def draw_detections(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        draw_polygon: bool = True
    ) -> np.ndarray:
        """
        Draw detections and polygon on frame.
        
        Args:
            frame: BGR frame
            detections: List of detections to draw
            draw_polygon: Whether to draw the polygon
        
        Returns:
            Frame with drawings
        """
        output = frame.copy()
        
        # Draw polygon
        if draw_polygon and len(self.polygon) > 2:
            poly_np = np.array(self.polygon, np.int32)
            cv2.polylines(output, [poly_np], True, (255, 255, 0), 2)
        
        # Draw detections
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = (0, 0, 255) if det.is_inside_zone else (0, 255, 0)
            
            # Draw bbox
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"Person {det.confidence:.2f}"
            if det.is_inside_zone:
                label += " [INSIDE]"
            
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(output, (x1, y1 - h - 5), (x1 + w, y1), color, -1)
            cv2.putText(output, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return output
