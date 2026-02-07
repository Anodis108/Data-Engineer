"""Module tải cấu hình cho pipeline sự kiện thị giác."""
import os
import json
import os
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Cấu hình ứng dụng được tải từ file .env và các file config."""
    
    # Cài đặt MinIO
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    
    # Cài đặt RabbitMQ
    rabbit_host: str
    rabbit_port: int
    rabbit_user: str
    rabbit_pass: str
    rabbit_exchange: str
    
    # Cài đặt Camera
    camera_index: int
    camera_id: str
    
    # Cài đặt Phát hiện (Detection)
    conf_threshold: float
    infer_every_n: int
    
    # Cài đặt Tổng hợp sự kiện
    emit_every_sec: int
    session_gap_sec: int
    
    # Các tiền tố lưu trữ (Prefixes)
    s3_prefix_snapshots: str
    s3_prefix_events: str
    s3_prefix_sessions: str
    
    # Cài đặt Snapshot
    snapshot_jpeg_quality: int
    
    # Vùng cấm (Polygon)
    polygon: list[list[int]]
    
    # Đường dẫn mô hình YOLO
    model_path: str


def load_polygon(config_path: Optional[str] = None) -> list[list[int]]:
    """Tải polygon từ file cấu hình JSON."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "resource" / "config" / "polygon.json"
    
    with open(config_path, "r") as f:
        data = json.load(f)
        return data.get("active_area", [])


def save_polygon(polygon: list[list[int]], config_path: Optional[str] = None) -> None:
    """Lưu polygon vào file cấu hình JSON một cách nguyên tử (atomic)."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "resource" / "config" / "polygon.json"
    
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Saving polygon to: {config_path.absolute()}")
    
    # Ghi nguyên tử: ghi vào file tạm sau đó đổi tên
    with tempfile.NamedTemporaryFile("w", dir=config_path.parent, delete=False) as tf:
        json.dump({"active_area": polygon}, tf)
        temp_name = tf.name
    
    # Đổi tên (nguyên tử trên POSIX, thay thế nguyên tử trên Windows với Python/OS mới)
    # shutil.move xử lý việc di chuyển giữa các filesystem nếu cần, nhưng os.replace là nguyên tử trên cùng fs
    os.replace(temp_name, config_path)


def load_config(env_path: Optional[str] = None) -> AppConfig:
    """
    Tải cấu hình từ file .env và các file config khác.
    
    Args:
        env_path: Đường dẫn tùy chọn tới file .env. Mặc định là thư mục gốc của dự án.
    
    Returns:
        AppConfig với tất cả các cài đặt đã được tải.
    """
    if env_path:
        load_dotenv(env_path)
    else:
        # Thử tải từ thư mục gốc của dự án
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    
    return AppConfig(
        # MinIO
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
        minio_bucket=os.getenv("MINIO_BUCKET", "lake"),
        minio_secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        
        # RabbitMQ
        rabbit_host=os.getenv("RABBIT_HOST", "localhost"),
        rabbit_port=int(os.getenv("RABBIT_PORT", "5672")),
        rabbit_user=os.getenv("RABBIT_USER", "admin"),
        rabbit_pass=os.getenv("RABBIT_PASS", "admin123"),
        rabbit_exchange=os.getenv("RABBIT_EXCHANGE", "vision.alerts"),
        
        # Camera
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        camera_id=os.getenv("CAMERA_ID", "webcam0"),
        
        # Detection
        conf_threshold=float(os.getenv("CONF_THRES", "0.35")),
        infer_every_n=int(os.getenv("INFER_EVERY_N", "1")),
        
        # Event aggregation
        emit_every_sec=int(os.getenv("EMIT_EVERY_SEC", "5")),
        session_gap_sec=int(os.getenv("SESSION_GAP_SEC", "2")),
        
        # Storage prefixes
        s3_prefix_snapshots=os.getenv("S3_PREFIX_SNAPSHOTS", "raw/vision/person_snapshots"),
        s3_prefix_events=os.getenv("S3_PREFIX_EVENTS", "raw/events/person_detection"),
        s3_prefix_sessions=os.getenv("S3_PREFIX_SESSIONS", "raw/vision/presence_sessions"),
        
        # Snapshot
        snapshot_jpeg_quality=int(os.getenv("SNAPSHOT_JPEG_QUALITY", "85")),
        
        # Polygon
        polygon=load_polygon(),
        
        # Model
        model_path=os.getenv("YOLO_MODEL_PATH", "yolo11s.pt"),
    )
