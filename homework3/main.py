"""
Pipeline Sự kiện Thị giác - Phát hiện Người trong Vùng cấm

Triển khai Kiến trúc Sạch (Clean Architecture) với:
- Lưu trữ MinIO cho sự kiện (Parquet) và khung hình (JPEG)
- Hệ thống tin nhắn RabbitMQ cho cảnh báo thời gian thực
- Tổng hợp sự kiện trong cửa sổ 5 giây

Cách dùng:
    python main.py

Điều khiển:
    - Chuột trái: Thêm điểm vào đa giác
    - Chuột phải: Kết thúc đa giác (vùng cấm)
    - 'c': Xóa đa giác
    - 'q': Thoát

Yêu cầu:
    pip install ultralytics opencv-python minio pika python-dotenv pandas pyarrow
"""
import logging
import sys

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)


def main():
    """Điểm khởi đầu chính của ứng dụng."""
    # Bỏ try-except để lỗi hiển thị trực tiếp cho mục đích học tập
    from src.infrastructure.config import load_config
    from src.presentation.main_loop import VisionApp
    
    logger.info("=" * 60)
    logger.info("Vision Event Pipeline v1.0")
    logger.info("=" * 60)
    
    # Tải cấu hình
    config = load_config()
    logger.info(f"Camera: {config.camera_id} (index={config.camera_index})")
    logger.info(f"MinIO: {config.minio_endpoint}/{config.minio_bucket}")
    logger.info(f"RabbitMQ: {config.rabbit_host}:{config.rabbit_port}")
    logger.info(f"Window: {config.emit_every_sec}s | Gap: {config.session_gap_sec}s")
    
    # Khởi tạo và chạy ứng dụng
    app = VisionApp(config)
    app.run()


if __name__ == "__main__":
    main()
