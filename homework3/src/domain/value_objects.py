"""Value objects for vision event pipeline - immutable data structures."""
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class AlertPayload:
    """
    Immutable payload for RabbitMQ alert messages.
    
    Event types:
    - person.present: Person detected in forbidden zone
    - person.still_present: Person still in zone (heartbeat)
    - person.left: Person left the zone
    """
    event_id: str
    camera_id: str
    ts: int  # Unix timestamp in milliseconds
    event_type: str
    person_count: int
    note: str = ""
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps({
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "ts": self.ts,
            "type": self.event_type,
            "person_count": self.person_count,
            "note": self.note
        })
    
    def to_bytes(self) -> bytes:
        """Serialize to bytes for messaging."""
        return self.to_json().encode("utf-8")

    @staticmethod
    def from_json(json_str: str) -> 'AlertPayload':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return AlertPayload(
            event_id=data["event_id"],
            camera_id=data["camera_id"],
            ts=data["ts"],
            event_type=data.get("type", data.get("event_type")),
            person_count=data["person_count"],
            note=data.get("note", "")
        )
