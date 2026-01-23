"""
Vision Event Pipeline - Person Detection in Forbidden Zone

Clean Architecture implementation with:
- MinIO storage for events (Parquet) and frames (JPEG)
- RabbitMQ messaging for real-time alerts
- 5-second window event aggregation

Usage:
    python main.py

Controls:
    - Left click: Add point to polygon
    - Right click: Finalize polygon (forbidden zone)
    - 'c': Clear polygon
    - 'q': Quit

Requirements:
    pip install ultralytics opencv-python minio pika python-dotenv pandas pyarrow
"""
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    try:
        from src.infrastructure.config import load_config
        from src.presentation.main_loop import VisionApp
        
        logger.info("=" * 60)
        logger.info("Vision Event Pipeline v1.0")
        logger.info("=" * 60)
        
        # Load configuration
        config = load_config()
        logger.info(f"Camera: {config.camera_id} (index={config.camera_index})")
        logger.info(f"MinIO: {config.minio_endpoint}/{config.minio_bucket}")
        logger.info(f"RabbitMQ: {config.rabbit_host}:{config.rabbit_port}")
        logger.info(f"Window: {config.emit_every_sec}s | Gap: {config.session_gap_sec}s")
        
        # Create and run application
        app = VisionApp(config)
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
