"""Configuration loader for vision event pipeline."""
import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


@dataclass
class AppConfig:
    """Application configuration loaded from .env and config files."""
    
    # MinIO settings
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    
    # RabbitMQ settings
    rabbit_host: str
    rabbit_port: int
    rabbit_user: str
    rabbit_pass: str
    rabbit_exchange: str
    
    # Camera settings
    camera_index: int
    camera_id: str
    
    # Detection settings
    conf_threshold: float
    infer_every_n: int
    
    # Event aggregation settings
    emit_every_sec: int
    session_gap_sec: int
    
    # Storage prefixes
    s3_prefix_snapshots: str
    s3_prefix_events: str
    s3_prefix_sessions: str
    
    # Snapshot settings
    snapshot_jpeg_quality: int
    
    # Polygon (forbidden zone)
    polygon: list[list[int]]
    
    # YOLO model path
    model_path: str


def load_polygon(config_path: Optional[str] = None) -> list[list[int]]:
    """Load polygon from JSON config file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "resource" / "config" / "polygon.json"
    
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
            return data.get("active_area", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_polygon(polygon: list[list[int]], config_path: Optional[str] = None) -> None:
    """Save polygon to JSON config file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "resource" / "config" / "polygon.json"
    
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump({"active_area": polygon}, f)


def load_config(env_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from .env file and other config files.
    
    Args:
        env_path: Optional path to .env file. Defaults to project root.
    
    Returns:
        AppConfig with all settings loaded.
    """
    if env_path:
        load_dotenv(env_path)
    else:
        # Try to load from project root
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
