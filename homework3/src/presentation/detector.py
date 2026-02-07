"""Module phát hiện người sử dụng YOLO và kiểm tra vùng polygon."""
import logging
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO

from src.domain.entities import Detection

logger = logging.getLogger(__name__)


class PersonDetector:
    """Bộ phát hiện người dựa trên YOLO với tính năng kiểm tra vùng polygon."""
    
    def __init__(
        self,
        model_path: str = "yolo11s.pt",
        conf_threshold: float = 0.35,
        polygon: Optional[list[list[int]]] = None,
        imgsz: int = 640
    ):
        """Khởi tạo bộ phát hiện người với model, ngưỡng và vùng polygon tùy chọn."""
        self.conf_threshold = conf_threshold
        self.polygon = polygon or []
        self.imgsz = imgsz
        
        logger.info(f"Đang tải model YOLO: {model_path}")
        self.model = YOLO(model_path)
        logger.info("Đã tải model YOLO")
    
    def set_polygon(self, polygon: list[list[int]]) -> None:
        """Cập nhật vùng polygon cấm."""
        self.polygon = polygon
        logger.debug(f"Đã cập nhật polygon: {len(polygon)} điểm")
    
    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Phát hiện người trong khung hình và kiểm tra xem họ có nằm trong vùng polygon không."""
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
                center = ((x1 + x2) / 2, (y1 + y2) / 2)
                is_inside = self._point_in_polygon(center)
                
                detections.append(Detection(
                    bbox=(x1, y1, x2, y2),
                    confidence=confidence,
                    is_inside_zone=is_inside
                ))
        
        return detections
    
    def _point_in_polygon(self, point: tuple[float, float]) -> bool:
        """Kiểm tra xem một điểm có nằm trong polygon không."""
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
        """Vẽ các phát hiện và polygon lên khung hình."""
        output = frame.copy()
        
        if draw_polygon and len(self.polygon) > 2:
            poly_np = np.array(self.polygon, np.int32)
            cv2.polylines(output, [poly_np], True, (255, 255, 0), 2)
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = (0, 0, 255) if det.is_inside_zone else (0, 255, 0)
            
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            
            label = f"Nguoi {det.confidence:.2f}"
            if det.is_inside_zone:
                label += " [TRONG VUNG CAM]"
            
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(output, (x1, y1 - h - 5), (x1 + w, y1), color, -1)
            cv2.putText(output, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return output
