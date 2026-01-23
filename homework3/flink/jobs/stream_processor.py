"""
Flink Stream Processing Job: Vision Event Processor
====================================================
Real-time event processing with Apache Flink (PyFlink).

This job demonstrates:
- Reading from Kafka using Flink's Kafka connector
- Stream transformations and filtering
- Windowed aggregations
- Writing results to stdout (can be extended to sinks)

Requirements:
    pip install apache-flink==1.18.0

Usage:
    # Submit to Flink cluster
    flink run -py /opt/flink/jobs/stream_processor.py
"""
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_vision_event(event_str: str) -> Optional[Dict[str, Any]]:
    """Process individual vision event JSON string."""
    try:
        event = json.loads(event_str)
        return {
            "camera_id": event.get("camera_id", "unknown"),
            "person_count": event.get("person_count", 0),
            "conf_avg": event.get("conf_avg", 0.0),
            "event_type": event.get("event_type", "unknown"),
            "processed_at": datetime.now().isoformat()
        }
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse event: {e}")
        return None


def process_cdc_event(event_str: str) -> Optional[Dict[str, Any]]:
    """Process CDC event from Debezium."""
    try:
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
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse CDC event: {e}")
        return None


def run_with_pyflink():
    """Run the job using PyFlink (requires pyflink package)."""
    try:
        from pyflink.datastream import StreamExecutionEnvironment
        from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer
        from pyflink.common.serialization import SimpleStringSchema
        from pyflink.common import WatermarkStrategy
    except ImportError:
        logger.error("PyFlink not installed. Install with: pip install apache-flink")
        return
    
    # Configuration
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    kafka_topic = os.getenv("KAFKA_TOPIC", "pgserver1.public.customers")
    
    logger.info("=" * 60)
    logger.info("Starting Flink Stream Processor")
    logger.info(f"Kafka: {kafka_servers}")
    logger.info(f"Topic: {kafka_topic}")
    logger.info("=" * 60)
    
    # Create execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(2)
    
    # Kafka consumer properties
    kafka_props = {
        "bootstrap.servers": kafka_servers,
        "group.id": "flink-vision-processor",
        "auto.offset.reset": "latest"
    }
    
    # Create Kafka source
    kafka_consumer = FlinkKafkaConsumer(
        topics=kafka_topic,
        deserialization_schema=SimpleStringSchema(),
        properties=kafka_props
    )
    kafka_consumer.set_start_from_latest()
    
    # Stream processing pipeline
    stream = env.add_source(kafka_consumer)
    
    # Process CDC events
    processed = stream \
        .map(process_cdc_event) \
        .filter(lambda x: x is not None)
    
    # Output to stdout
    processed.print()
    
    # Execute
    env.execute("FlinkVisionEventProcessor")


def run_demo_mode():
    """Run in demo mode without Flink (for testing)."""
    logger.info("=" * 60)
    logger.info("Running in DEMO mode (no Flink)")
    logger.info("=" * 60)
    
    # Sample events for demo
    sample_events = [
        '{"camera_id": "cam_01", "person_count": 2, "conf_avg": 0.85, "event_type": "person_present"}',
        '{"camera_id": "cam_02", "person_count": 0, "conf_avg": 0.0, "event_type": "no_person"}',
        '{"payload": {"op": "c", "after": {"id": 1, "name": "Test"}, "source": {"table": "customers"}}}',
    ]
    
    logger.info("\n📊 Processing sample vision events:")
    for event in sample_events[:2]:
        result = process_vision_event(event)
        if result:
            logger.info(f"  → {result}")
    
    logger.info("\n📊 Processing sample CDC events:")
    for event in sample_events[2:]:
        result = process_cdc_event(event)
        if result:
            logger.info(f"  → {result}")
    
    logger.info("\n✅ Demo completed!")


def main():
    """Main entry point."""
    # Check if running in Flink environment
    use_flink = os.getenv("USE_FLINK", "false").lower() == "true"
    
    if use_flink:
        run_with_pyflink()
    else:
        # Run demo mode for testing
        run_demo_mode()
        logger.info("\nTo run with Flink, set USE_FLINK=true")


if __name__ == "__main__":
    main()
