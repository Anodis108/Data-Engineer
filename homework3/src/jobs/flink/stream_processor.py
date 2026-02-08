"""
Job Xử lý Luồng Flink: Bộ xử lý Sự kiện Thị giác
====================================================
Xử lý sự kiện thời gian thực với Apache Flink (PyFlink).

Job này minh họa:
- Đọc từ Kafka sử dụng Kafka connector của Flink
- Biến đổi và lọc luồng dữ liệu
- Tổng hợp theo cửa sổ (windowed aggregations)
- Ghi kết quả ra stdout (có thể mở rộng sang các sink khác)

Yêu cầu:
    pip install apache-flink==1.18.0

Cách dùng:
    # Gửi tới cụm Flink
    flink run -py /opt/flink/jobs/stream_processor.py
"""
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_vision_event(event_str: str) -> Optional[Dict[str, Any]]:
    """Xử lý từng chuỗi JSON sự kiện thị giác."""
    # Bỏ try-except để hiển thị lỗi trực tiếp
    event = json.loads(event_str)
    return {
        "camera_id": event.get("camera_id", "unknown"),
        "person_count": event.get("person_count", 0),
        "conf_avg": event.get("conf_avg", 0.0),
        "event_type": event.get("event_type", "unknown"),
        "processed_at": datetime.now().isoformat()
    }


def process_cdc_event(event_str: str) -> Optional[Dict[str, Any]]:
    """Xử lý sự kiện CDC từ Debezium."""
    # Bỏ try-except để hiển thị lỗi trực tiếp
    event = json.loads(event_str)
    payload = event.get("payload", event)
    
    op_map = {"c": "INSERT", "u": "UPDATE", "d": "DELETE", "r": "READ"}
    operation = payload.get("op", "")
    
    return {
        "operation": op_map.get(operation, operation),
        "table": payload.get("source", {}).get("table", "unknown"),
        "before": payload.get("before"),
        "after": payload.get("after"),
        "ts_ms": payload.get("ts_ms"),
        "processed_at": datetime.now().isoformat()
    }


def run_with_pyflink():
    """Chạy job sử dụng PyFlink."""
    # Bỏ try-except để hiển thị lỗi import trực tiếp
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.common import WatermarkStrategy
    
    # Cấu hình tham số
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    kafka_topic = os.getenv("KAFKA_TOPIC", "pgserver1.public.customers")
    
    logger.info("=" * 60)
    logger.info("Đang bắt đầu Flink Stream Processor")
    logger.info(f"Kafka: {kafka_servers}")
    logger.info(f"Topic: {kafka_topic}")
    logger.info("=" * 60)
    
    # Tạo execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(2)
    
    # Thuộc tính Kafka consumer
    kafka_props = {
        "bootstrap.servers": kafka_servers,
        "group.id": "flink-vision-processor",
        "auto.offset.reset": "latest"
    }
    
    # Tạo nguồn Kafka
    kafka_consumer = FlinkKafkaConsumer(
        topics=kafka_topic,
        deserialization_schema=SimpleStringSchema(),
        properties=kafka_props
    )
    kafka_consumer.set_start_from_latest()
    
    # Đường ống xử lý luồng
    stream = env.add_source(kafka_consumer)
    
    # Xử lý các sự kiện CDC
    processed = stream \
        .map(process_cdc_event) \
        .filter(lambda x: x is not None)
    
    # Xuất ra stdout
    processed.print()
    
    # Thực thi
    env.execute("FlinkVisionEventProcessor")


def run_demo_mode():
    """Chạy ở chế độ demo không có Flink (để kiểm tra)."""
    logger.info("=" * 60)
    logger.info("Đang chạy ở chế độ DEMO (không có Flink)")
    logger.info("=" * 60)
    
    # Các sự kiện mẫu cho bản demo
    sample_events = [
        '{"camera_id": "cam_01", "person_count": 2, "conf_avg": 0.85, "event_type": "person_present"}',
        '{"camera_id": "cam_02", "person_count": 0, "conf_avg": 0.0, "event_type": "no_person"}',
        '{"payload": {"op": "c", "after": {"id": 1, "name": "Test"}, "source": {"table": "customers"}}}',
    ]
    
    logger.info("\n📊 Đang xử lý các sự kiện thị giác mẫu:")
    for event in sample_events[:2]:
        result = process_vision_event(event)
        if result:
            logger.info(f"  → {result}")
    
    logger.info("\n📊 Đang xử lý các sự kiện CDC mẫu:")
    for event in sample_events[2:]:
        result = process_cdc_event(event)
        if result:
            logger.info(f"  → {result}")
    
    logger.info("\n✅ Hoàn thành Demo!")


def main():
    """Điểm khởi đầu chính."""
    # Kiểm tra xem có đang chạy trong môi trường Flink hay không
    use_flink = os.getenv("USE_FLINK", "false").lower() == "true"
    
    if use_flink:
        run_with_pyflink()
    else:
        # Chạy chế độ demo để kiểm tra
        run_demo_mode()
        logger.info("\nĐể chạy với Flink, hãy đặt USE_FLINK=true")


if __name__ == "__main__":
    main()
