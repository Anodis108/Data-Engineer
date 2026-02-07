"""Các thực thể (Entities) của domain cho luồng xử lý sự kiện thị giác máy tính."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Detection:
    """Đại diện cho một phát hiện người từ mô hình YOLO."""
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    is_inside_zone: bool
    
    @property
    def center(self) -> tuple[float, float]:
        """Lấy điểm trung tâm của bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)


@dataclass
class VisionEvent:
    """
    Đại diện cho một sự kiện thị giác được tổng hợp qua một cửa sổ thời gian.
    
    Các loại sự kiện (Event types):
    - person_present_start: Phát hiện người đầu tiên trong vùng cấm.
    - person_still_present: Heartbeat mỗi N giây khi người vẫn còn trong vùng.
    - person_left: Người đã rời khỏi vùng sau khoảng thời gian gap_sec không phát hiện.
    """
    event_id: str
    camera_id: str
    ts_start: datetime
    ts_end: datetime
    person_count: int
    conf_avg: float
    conf_max: float
    frame_uri: str
    event_type: str  # person_present_start, person_still_present, person_left
    
    @classmethod
    def create(
        cls,
        camera_id: str,
        ts_start: datetime,
        ts_end: datetime,
        person_count: int,
        conf_avg: float,
        conf_max: float,
        event_type: str,
        frame_uri: str = ""
    ) -> "VisionEvent":
        """Phương thức Factory để tạo một VisionEvent mới với ID tự động sinh."""
        return cls(
            event_id=str(uuid.uuid4()),
            camera_id=camera_id,
            ts_start=ts_start,
            ts_end=ts_end,
            person_count=person_count,
            conf_avg=conf_avg,
            conf_max=conf_max,
            frame_uri=frame_uri,
            event_type=event_type
        )
    
    def to_dict(self) -> dict:
        """Chuyển đổi sang dictionary để serialization."""
        return {
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "ts_start": self.ts_start.isoformat(),
            "ts_end": self.ts_end.isoformat(),
            "person_count": self.person_count,
            "conf_avg": self.conf_avg,
            "conf_max": self.conf_max,
            "frame_uri": self.frame_uri,
            "event_type": self.event_type
        }
