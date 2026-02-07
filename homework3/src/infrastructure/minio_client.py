"""MinIO S3 repository để lưu trữ sự kiện thị giác và khung hình."""
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
    """Repository để lưu trữ dữ liệu thị giác trong MinIO S3."""
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False
    ):
        """
        Khởi tạo MinIO client.
        
        Args:
            endpoint: MinIO endpoint (host:port)
            access_key: Access key
            secret_key: Secret key
            bucket: Tên bucket mặc định
            secure: Sử dụng HTTPS nếu True
        """
        self.bucket = bucket
        self._client: Optional[Minio] = None
        self._connected = False
        
        # Kết nối tới MinIO
        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        # Kiểm tra bucket tồn tại
        if self._client.bucket_exists(bucket):
            self._connected = True
            logger.info(f"MinIO connected: endpoint={endpoint}, bucket={bucket}")
        else:
            logger.error(f"MinIO bucket '{bucket}' NOT FOUND at {endpoint}. Storage disabled. Please create it first.")
    
    @property
    def is_connected(self) -> bool:
        """Kiểm tra xem MinIO đã kết nối và sẵn sàng chưa."""
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
        Upload khung hình dưới dạng JPEG lên MinIO.
        
        Args:
            frame: Khung hình OpenCV BGR
            camera_id: Định danh camera
            timestamp: Thời gian của khung hình
            prefix: Tiền tố S3 (ví dụ: 'raw/vision/person_snapshots')
            jpeg_quality: Chất lượng nén JPEG (0-100)
        
        Returns:
            S3 URI of uploaded file, or None if failed
        """
        if not self.is_connected:
            return None
        
        # Encode khung hình sang JPEG
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        _, buffer = cv2.imencode(".jpg", frame, encode_params)
        data = io.BytesIO(buffer.tobytes())
        
        # Xây dựng key với phân vùng (partitioning)
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
    
    def upload_events_parquet(
        self,
        events: list[VisionEvent],
        camera_id: str,
        timestamp: datetime,
        prefix: str
    ) -> Optional[str]:
        """
        Upload các sự kiện dưới dạng file Parquet lên MinIO.
        
        Args:
            events: Danh sách VisionEvent cần upload
            camera_id: Định danh camera
            timestamp: Thời gian của lô (batch)
            prefix: Tiền tố S3 (ví dụ: 'raw/events/person_detection')
        
        Returns:
            S3 URI của file đã upload, hoặc None nếu thất bại
        """
        if not self.is_connected or not events:
            return None
        
        # Chuyển đổi events sang DataFrame
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
        
        # Chuyển đổi sang Parquet
        table = pa.Table.from_pandas(df)
        buf = io.BytesIO()
        pq.write_table(table, buf, compression="snappy")
        buf.seek(0)
        
        # Xây dựng key với phân vùng
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
    
    def list_buckets(self) -> list[str]:
        """Liệt kê tất cả các buckets có sẵn."""
        if not self.is_connected:
            return []
        
        # Liệt kê tất cả buckets
        buckets = self._client.list_buckets()
        return [b.name for b in buckets]
    
    def list_objects(
        self,
        prefix: str = "",
        bucket: Optional[str] = None,
        max_keys: int = 100
    ) -> list[dict]:
        """
        Liệt kê các objects trong bucket với prefix cho trước.
        
        Args:
            prefix: Object key prefix để lọc
            bucket: Tên bucket (mặc định: bucket đã cấu hình)
            max_keys: Số lượng tối đa objects trả về
            
        Returns:
            Danh sách các dictionary metadata của object
        """
        if not self.is_connected:
            return []
        
        bucket = bucket or self.bucket
        
        # Liệt kê objects với prefix
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
    
    def get_object_content(
        self,
        object_name: str,
        bucket: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Lấy nội dung thô (raw content) của một object.
        
        Args:
            object_name: Object key
            bucket: Tên bucket (mặc định: bucket đã cấu hình)
            
        Returns:
            Nội dung object dưới dạng bytes, hoặc None nếu thất bại
        """
        if not self.is_connected:
            return None
        
        bucket = bucket or self.bucket
        
        # Lấy nội dung object
        response = self._client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    
    def preview_parquet(
        self,
        object_name: str,
        bucket: Optional[str] = None,
        max_rows: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Xem trước nội dung của một file Parquet.
        
        Args:
            object_name: Object key (phải là file .parquet)
            bucket: Tên bucket (mặc định: bucket đã cấu hình)
            max_rows: Số dòng tối đa trả về
            
        Returns:
            DataFrame chứa bản xem trước, hoặc None nếu thất bại
        """
        if not self.is_connected:
            return None
        
        content = self.get_object_content(object_name, bucket)
        if content is None:
            return None
        
        # Đọc parquet từ bytes
        buffer = io.BytesIO(content)
        table = pq.read_table(buffer)
        df = table.to_pandas()
        return df.head(max_rows)
    
    def get_object_url(
        self,
        object_name: str,
        bucket: Optional[str] = None,
        expires_hours: int = 1
    ) -> Optional[str]:
        """
        Tạo presigned URL để tải object.
        
        Args:
            object_name: Object key
            bucket: Tên bucket (mặc định: bucket đã cấu hình)
            expires_hours: Thời gian hết hạn URL tính bằng giờ
            
        Returns:
            Presigned URL, hoặc None nếu thất bại
        """
        if not self.is_connected:
            return None
        
        bucket = bucket or self.bucket
        
        # Tạo presigned URL
        from datetime import timedelta
        url = self._client.presigned_get_object(
            bucket,
            object_name,
            expires=timedelta(hours=expires_hours)
        )
        return url
    
    def get_bucket_stats(self, bucket: Optional[str] = None) -> dict:
        """
        Lấy thống kê về nội dung của bucket.
        
        Args:
            bucket: Tên bucket (mặc định: bucket đã cấu hình)
            
        Returns:
            Dict với số lượng object và tổng kích thước
        """
        if not self.is_connected:
            return {"object_count": 0, "total_size": 0}
        
        bucket = bucket or self.bucket
        
        # Tính toán thống kê bucket
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
