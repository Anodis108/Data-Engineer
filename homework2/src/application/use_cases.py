"""Use cases for vision event handling."""
import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from src.domain.entities import VisionEvent
from src.domain.value_objects import AlertPayload
from src.infrastructure.minio_client import MinioRepository
from src.infrastructure.rabbitmq_client import RabbitMQPublisher


logger = logging.getLogger(__name__)


class HandleVisionEventUseCase:
    """
    Use case: Handle a vision event by storing and alerting.
    
    Actions:
    1. Upload frame snapshot to MinIO (optional)
    2. Store event data to MinIO (Parquet)
    3. Publish alert to RabbitMQ
    """
    
    def __init__(
        self,
        minio_repo: Optional[MinioRepository],
        rabbitmq_pub: Optional[RabbitMQPublisher],
        snapshot_prefix: str = "raw/vision/person_snapshots",
        events_prefix: str = "raw/events/person_detection",
        jpeg_quality: int = 85
    ):
        """
        Initialize use case.
        
        Args:
            minio_repo: MinIO repository (optional, can be None)
            rabbitmq_pub: RabbitMQ publisher (optional, can be None)
            snapshot_prefix: S3 prefix for snapshots
            events_prefix: S3 prefix for events
            jpeg_quality: JPEG quality for snapshots
        """
        self.minio_repo = minio_repo
        self.rabbitmq_pub = rabbitmq_pub
        self.snapshot_prefix = snapshot_prefix
        self.events_prefix = events_prefix
        self.jpeg_quality = jpeg_quality
        
        # Buffer for batch event upload
        self._event_buffer: list[VisionEvent] = []
    
    def execute(
        self,
        event: VisionEvent,
        frame: Optional[np.ndarray] = None
    ) -> None:
        """
        Execute the use case.
        
        Args:
            event: Vision event to handle
            frame: Optional frame for snapshot
        """
        logger.info(f"Handling event: {event.event_type} | count={event.person_count} | conf={event.conf_avg:.2f}")
        
        now = datetime.now(timezone.utc)
        
        # 1. Upload frame snapshot
        frame_uri = ""
        if frame is not None and self.minio_repo and self.minio_repo.is_connected:
            frame_uri = self.minio_repo.upload_frame(
                frame=frame,
                camera_id=event.camera_id,
                timestamp=now,
                prefix=self.snapshot_prefix,
                jpeg_quality=self.jpeg_quality
            ) or ""
        
        # Update event with frame URI
        event.frame_uri = frame_uri
        
        # 2. Store event (add to buffer and upload)
        self._event_buffer.append(event)
        
        if self.minio_repo and self.minio_repo.is_connected:
            self.minio_repo.upload_events_parquet(
                events=self._event_buffer,
                camera_id=event.camera_id,
                timestamp=now,
                prefix=self.events_prefix
            )
            self._event_buffer.clear()
        
        # 3. Publish alert to RabbitMQ
        if self.rabbitmq_pub and self.rabbitmq_pub.is_connected:
            routing_key = self._get_routing_key(event.event_type)
            
            payload = AlertPayload(
                event_id=event.event_id,
                camera_id=event.camera_id,
                ts=int(now.timestamp() * 1000),
                event_type=event.event_type,
                person_count=event.person_count,
                note=f"conf_avg={event.conf_avg:.2f}"
            )
            
            self.rabbitmq_pub.publish_alert(payload, routing_key)
    
    def _get_routing_key(self, event_type: str) -> str:
        """Map event type to RabbitMQ routing key."""
        mapping = {
            "person_present_start": "person.present",
            "person_still_present": "person.still_present",
            "person_left": "person.left"
        }
        return mapping.get(event_type, "person.present")
    
    def flush(self) -> None:
        """Flush any buffered events."""
        if self._event_buffer and self.minio_repo and self.minio_repo.is_connected:
            now = datetime.now(timezone.utc)
            if self._event_buffer:
                self.minio_repo.upload_events_parquet(
                    events=self._event_buffer,
                    camera_id=self._event_buffer[0].camera_id,
                    timestamp=now,
                    prefix=self.events_prefix
                )
                self._event_buffer.clear()
