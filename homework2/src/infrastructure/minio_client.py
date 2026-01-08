"""MinIO S3 repository for storing vision events and frames."""
import io
import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import cv2
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

from src.domain.entities import VisionEvent


logger = logging.getLogger(__name__)


class MinioRepository:
    """Repository for storing vision data in MinIO S3."""
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False
    ):
        """
        Initialize MinIO client.
        
        Args:
            endpoint: MinIO endpoint (host:port)
            access_key: Access key
            secret_key: Secret key
            bucket: Default bucket name
            secure: Use HTTPS if True
        """
        self.bucket = bucket
        self._client: Optional[Minio] = None
        self._connected = False
        
        try:
            self._client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            # Check bucket exists
            if self._client.bucket_exists(bucket):
                self._connected = True
                logger.info(f"MinIO connected: endpoint={endpoint}, bucket={bucket}")
            else:
                logger.error(f"MinIO bucket '{bucket}' NOT FOUND at {endpoint}. Storage disabled. Please create it first.")
        except Exception as e:
            logger.error(f"MinIO connection failed at {endpoint}: {e}. Storage disabled. Check if service is running.")
    
    @property
    def is_connected(self) -> bool:
        """Check if MinIO is connected and ready."""
        return self._connected and self._client is not None
    
    def upload_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        timestamp: datetime,
        prefix: str,
        jpeg_quality: int = 85
    ) -> Optional[str]:
        """
        Upload frame as JPEG to MinIO.
        
        Args:
            frame: OpenCV BGR frame
            camera_id: Camera identifier
            timestamp: Frame timestamp
            prefix: S3 prefix (e.g., 'raw/vision/person_snapshots')
            jpeg_quality: JPEG compression quality (0-100)
        
        Returns:
            S3 URI of uploaded file, or None if failed
        """
        if not self.is_connected:
            return None
        
        try:
            # Encode frame as JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
            _, buffer = cv2.imencode(".jpg", frame, encode_params)
            data = io.BytesIO(buffer.tobytes())
            
            # Build key with partitioning
            date_str = timestamp.strftime("%Y-%m-%d")
            hour_str = timestamp.strftime("%H")
            ts_ms = int(timestamp.timestamp() * 1000)
            
            key = f"{prefix}/camera_id={camera_id}/date={date_str}/hour={hour_str}/{ts_ms}.jpg"
            
            self._client.put_object(
                self.bucket,
                key,
                data,
                length=data.getbuffer().nbytes,
                content_type="image/jpeg"
            )
            
            uri = f"s3://{self.bucket}/{key}"
            logger.debug(f"Uploaded frame: {uri}")
            return uri
            
        except S3Error as e:
            logger.error(f"Failed to upload frame: {e}")
            return None
    
    def upload_events_parquet(
        self,
        events: list[VisionEvent],
        camera_id: str,
        timestamp: datetime,
        prefix: str
    ) -> Optional[str]:
        """
        Upload events as Parquet file to MinIO.
        
        Args:
            events: List of VisionEvent to upload
            camera_id: Camera identifier
            timestamp: Batch timestamp
            prefix: S3 prefix (e.g., 'raw/events/person_detection')
        
        Returns:
            S3 URI of uploaded file, or None if failed
        """
        if not self.is_connected or not events:
            return None
        
        try:
            # Convert events to DataFrame
            rows = []
            for event in events:
                rows.append({
                    "event_id": event.event_id,
                    "camera_id": event.camera_id,
                    "ts_start": event.ts_start,
                    "ts_end": event.ts_end,
                    "person_count": event.person_count,
                    "conf_avg": event.conf_avg,
                    "conf_max": event.conf_max,
                    "frame_uri": event.frame_uri,
                    "event_type": event.event_type
                })
            
            df = pd.DataFrame(rows)
            
            # Convert to Parquet
            table = pa.Table.from_pandas(df)
            buf = io.BytesIO()
            pq.write_table(table, buf, compression="snappy")
            buf.seek(0)
            
            # Build key with partitioning
            date_str = timestamp.strftime("%Y-%m-%d")
            hour_str = timestamp.strftime("%H")
            ts_ms = int(timestamp.timestamp() * 1000)
            
            key = f"{prefix}/camera_id={camera_id}/date={date_str}/hour={hour_str}/events_{ts_ms}.parquet"
            
            self._client.put_object(
                self.bucket,
                key,
                buf,
                length=buf.getbuffer().nbytes,
                content_type="application/octet-stream"
            )
            
            uri = f"s3://{self.bucket}/{key}"
            logger.info(f"Uploaded {len(events)} events: {uri}")
            return uri
            
        except S3Error as e:
            logger.error(f"Failed to upload events: {e}")
            return None
