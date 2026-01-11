"""Domain entities for vision event pipeline."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Detection:
    """Represents a single person detection from YOLO."""
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    is_inside_zone: bool
    
    @property
    def center(self) -> tuple[float, float]:
        """Get center point of bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)


@dataclass
class VisionEvent:
    """
    Represents an aggregated vision event over a time window.
    
    Event types:
    - person_present_start: First detection of person in zone
    - person_still_present: Heartbeat every N seconds while person present
    - person_left: Person left the zone after gap_sec of no detection
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
        """Factory method to create a new VisionEvent with auto-generated ID."""
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
        """Convert to dictionary for serialization."""
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
