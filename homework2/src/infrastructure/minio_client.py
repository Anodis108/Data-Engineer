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
    
    def list_buckets(self) -> list[str]:
        """List all available buckets."""
        if not self.is_connected:
            return []
        
        try:
            buckets = self._client.list_buckets()
            return [b.name for b in buckets]
        except S3Error as e:
            logger.error(f"Failed to list buckets: {e}")
            return []
    
    def list_objects(
        self,
        prefix: str = "",
        bucket: Optional[str] = None,
        max_keys: int = 100
    ) -> list[dict]:
        """
        List objects in bucket with given prefix.
        
        Args:
            prefix: Object key prefix to filter
            bucket: Bucket name (default: configured bucket)
            max_keys: Maximum number of objects to return
            
        Returns:
            List of object metadata dicts
        """
        if not self.is_connected:
            return []
        
        bucket = bucket or self.bucket
        
        try:
            objects = []
            count = 0
            
            for obj in self._client.list_objects(bucket, prefix=prefix, recursive=False):
                if count >= max_keys:
                    break
                
                objects.append({
                    "name": obj.object_name,
                    "size": obj.size or 0,
                    "last_modified": obj.last_modified,
                    "is_dir": obj.is_dir,
                    "etag": obj.etag
                })
                count += 1
            
            return objects
            
        except S3Error as e:
            logger.error(f"Failed to list objects: {e}")
            return []
    
    def get_object_content(
        self,
        object_name: str,
        bucket: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Get raw content of an object.
        
        Args:
            object_name: Object key
            bucket: Bucket name (default: configured bucket)
            
        Returns:
            Object content as bytes, or None if failed
        """
        if not self.is_connected:
            return None
        
        bucket = bucket or self.bucket
        
        try:
            response = self._client.get_object(bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.error(f"Failed to get object: {e}")
            return None
    
    def preview_parquet(
        self,
        object_name: str,
        bucket: Optional[str] = None,
        max_rows: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Preview content of a Parquet file.
        
        Args:
            object_name: Object key (must be .parquet file)
            bucket: Bucket name (default: configured bucket)
            max_rows: Maximum rows to return
            
        Returns:
            DataFrame with preview, or None if failed
        """
        if not self.is_connected:
            return None
        
        content = self.get_object_content(object_name, bucket)
        if content is None:
            return None
        
        try:
            buffer = io.BytesIO(content)
            table = pq.read_table(buffer)
            df = table.to_pandas()
            return df.head(max_rows)
        except Exception as e:
            logger.error(f"Failed to read Parquet: {e}")
            return None
    
    def get_object_url(
        self,
        object_name: str,
        bucket: Optional[str] = None,
        expires_hours: int = 1
    ) -> Optional[str]:
        """
        Generate presigned URL for object download.
        
        Args:
            object_name: Object key
            bucket: Bucket name (default: configured bucket)
            expires_hours: URL expiration time in hours
            
        Returns:
            Presigned URL, or None if failed
        """
        if not self.is_connected:
            return None
        
        bucket = bucket or self.bucket
        
        try:
            from datetime import timedelta
            url = self._client.presigned_get_object(
                bucket,
                object_name,
                expires=timedelta(hours=expires_hours)
            )
            return url
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
    
    def get_bucket_stats(self, bucket: Optional[str] = None) -> dict:
        """
        Get statistics about bucket contents.
        
        Args:
            bucket: Bucket name (default: configured bucket)
            
        Returns:
            Dict with object count and total size
        """
        if not self.is_connected:
            return {"object_count": 0, "total_size": 0}
        
        bucket = bucket or self.bucket
        
        try:
            total_size = 0
            object_count = 0
            
            for obj in self._client.list_objects(bucket, recursive=True):
                object_count += 1
                total_size += obj.size or 0
            
            return {
                "object_count": object_count,
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
        except S3Error as e:
            logger.error(f"Failed to get bucket stats: {e}")
            return {"object_count": 0, "total_size": 0}
