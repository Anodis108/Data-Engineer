"""Các value objects cho pipeline sự kiện thị giác - cấu trúc dữ liệu bất biến (immutable)."""
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class AlertPayload:
    """
    Payload bất biến cho các tin nhắn cảnh báo RabbitMQ.
    
    Các loại sự kiện (Event types):
    - person.present: Người được phát hiện trong vùng cấm.
    - person.still_present: Người vẫn đang ở trong vùng (heartbeat).
    - person.left: Người đã rời khỏi vùng.
    """
    event_id: str
    camera_id: str
    ts: int  # Unix timestamp tính bằng milliseconds
    event_type: str
    person_count: int
    note: str = ""
    
    def to_json(self) -> str:
        """Serialize sang chuỗi JSON."""
        return json.dumps({
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "ts": self.ts,
            "type": self.event_type,
            "person_count": self.person_count,
            "note": self.note
        })
    
    def to_bytes(self) -> bytes:
        """Serialize sang bytes để gửi tin nhắn."""
        return self.to_json().encode("utf-8")

    @staticmethod
    def from_json(json_str: str) -> 'AlertPayload':
        """Deserialize từ chuỗi JSON."""
        data = json.loads(json_str)
        return AlertPayload(
            event_id=data["event_id"],
            camera_id=data["camera_id"],
            ts=data["ts"],
            event_type=data.get("type", data.get("event_type")),
            person_count=data["person_count"],
            note=data.get("note", "")
        )
