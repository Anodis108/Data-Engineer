"""Các Use Cases cho việc xử lý sự kiện thị giác."""
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
    Use case: Xử lý một sự kiện thị giác bằng cách lưu trữ và cảnh báo.
    
    Các hành động (Actions):
    1. Upload snapshot khung hình lên MinIO (tùy chọn)
    2. Lưu dữ liệu sự kiện lên MinIO (Parquet)
    3. Gửi cảnh báo tới RabbitMQ
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
        Khởi tạo use case.
        
        Args:
            minio_repo: Repository MinIO (tùy chọn, có thể là None)
            rabbitmq_pub: Publisher RabbitMQ (tùy chọn, có thể là None)
            snapshot_prefix: Tiền tố S3 cho snapshots
            events_prefix: Tiền tố S3 cho các sự kiện
            jpeg_quality: Chất lượng JPEG cho snapshots
        """
        self.minio_repo = minio_repo
        self.rabbitmq_pub = rabbitmq_pub
        self.snapshot_prefix = snapshot_prefix
        self.events_prefix = events_prefix
        self.jpeg_quality = jpeg_quality
        
        # Buffer để upload sự kiện theo lô (batch)
        self._event_buffer: list[VisionEvent] = []
    
    def execute(
        self,
        event: VisionEvent,
        frame: Optional[np.ndarray] = None
    ) -> None:
        """
        Thực thi use case.
        
        Args:
            event: Sự kiện thị giác cần xử lý
            frame: Khung hình tùy chọn để làm snapshot
        """
        logger.info(f"Handling event: {event.event_type} | count={event.person_count} | conf={event.conf_avg:.2f}")
        
        # Thực thi các bước xử lý sự kiện
        now = datetime.now(timezone.utc)
        
        # 1. Upload snapshot khung hình
        frame_uri = ""
        if frame is not None and self.minio_repo and self.minio_repo.is_connected:
            frame_uri = self.minio_repo.upload_frame(
                frame=frame,
                camera_id=event.camera_id,
                timestamp=now,
                prefix=self.snapshot_prefix,
                jpeg_quality=self.jpeg_quality
            ) or ""
        
        # Cập nhật sự kiện với URI của khung hình
        event.frame_uri = frame_uri
        
        # 2. Lưu sự kiện (thêm vào buffer và upload)
        self._event_buffer.append(event)
        
        if self.minio_repo and self.minio_repo.is_connected:
            self.minio_repo.upload_events_parquet(
                events=self._event_buffer,
                camera_id=event.camera_id,
                timestamp=now,
                prefix=self.events_prefix
            )
            self._event_buffer.clear()
        
        # 3. Gửi cảnh báo tới RabbitMQ
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
        """Ánh xạ loại sự kiện sang routing key của RabbitMQ."""
        mapping = {
            "person_present_start": "person.present",
            "person_still_present": "person.still_present",
            "person_left": "person.left"
        }
        return mapping.get(event_type, "person.present")
    
    def flush(self) -> None:
        """Đẩy (Flush) bất kỳ sự kiện nào còn trong buffer."""
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
