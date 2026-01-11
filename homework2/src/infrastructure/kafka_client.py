"""Kafka client for CDC monitoring and topic browsing."""
import logging
import json
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class KafkaConfig:
    """Kafka connection configuration."""
    bootstrap_servers: str = "localhost:9092"
    consumer_group: str = "streamlit-monitor"
    auto_offset_reset: str = "latest"


@dataclass 
class CDCEvent:
    """Represents a CDC event from Debezium."""
    topic: str
    partition: int
    offset: int
    timestamp: datetime
    operation: str  # c=create, u=update, d=delete, r=read
    before: Optional[dict]
    after: Optional[dict]
    source_table: str
    
    @classmethod
    def from_kafka_message(cls, msg) -> Optional["CDCEvent"]:
        """Parse CDC event from Kafka message."""
        try:
            value = json.loads(msg.value.decode("utf-8")) if msg.value else {}
            
            payload = value.get("payload", value)
            source = payload.get("source", {})
            
            op_map = {"c": "INSERT", "u": "UPDATE", "d": "DELETE", "r": "READ"}
            operation = op_map.get(payload.get("op", ""), payload.get("op", "UNKNOWN"))
            
            return cls(
                topic=msg.topic,
                partition=msg.partition,
                offset=msg.offset,
                timestamp=datetime.fromtimestamp(msg.timestamp / 1000) if msg.timestamp else datetime.now(),
                operation=operation,
                before=payload.get("before"),
                after=payload.get("after"),
                source_table=source.get("table", msg.topic.split(".")[-1] if "." in msg.topic else msg.topic)
            )
        except Exception as e:
            logger.warning(f"Failed to parse CDC event: {e}")
            return None


class KafkaClient:
    """Client for Kafka topic browsing and CDC monitoring."""
    
    def __init__(self, config: Optional[KafkaConfig] = None):
        """
        Initialize Kafka client.
        
        Args:
            config: Kafka connection configuration
        """
        self.config = config or KafkaConfig()
        self._connected = False
        self._admin_client = None
        self._consumer = None
        
        try:
            from kafka import KafkaAdminClient, KafkaConsumer
            from kafka.errors import NoBrokersAvailable
            
            self._admin_client = KafkaAdminClient(
                bootstrap_servers=self.config.bootstrap_servers,
                client_id="streamlit-admin"
            )
            
            self._connected = True
            logger.info(f"Kafka connected: {self.config.bootstrap_servers}")
            
        except ImportError:
            logger.error("kafka-python package not installed. Run: pip install kafka-python")
        except Exception as e:
            logger.error(f"Kafka connection failed: {e}")
    
    @property
    def is_connected(self) -> bool:
        """Check if Kafka is connected."""
        return self._connected and self._admin_client is not None
    
    def list_topics(self) -> list[str]:
        """Get list of available Kafka topics."""
        if not self.is_connected:
            return []
        
        try:
            topics = self._admin_client.list_topics()
            # Filter out internal topics
            return [t for t in topics if not t.startswith("__") and not t.startswith("connect_")]
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []
    
    def get_topic_info(self, topic: str) -> Optional[dict]:
        """Get metadata about a topic."""
        if not self.is_connected:
            return None
        
        try:
            from kafka import KafkaConsumer
            
            consumer = KafkaConsumer(
                bootstrap_servers=self.config.bootstrap_servers,
                auto_offset_reset="latest"
            )
            
            partitions = consumer.partitions_for_topic(topic)
            consumer.close()
            
            if partitions:
                return {
                    "topic": topic,
                    "partitions": len(partitions),
                    "partition_ids": list(partitions)
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get topic info: {e}")
            return None
    
    def get_recent_messages(self, topic: str, max_messages: int = 20) -> list[CDCEvent]:
        """
        Get recent messages from a topic.
        
        Args:
            topic: Topic name to consume from
            max_messages: Maximum number of messages to retrieve
            
        Returns:
            List of CDCEvent objects
        """
        if not self.is_connected:
            return []
        
        events = []
        
        try:
            from kafka import KafkaConsumer, TopicPartition
            
            consumer = KafkaConsumer(
                bootstrap_servers=self.config.bootstrap_servers,
                auto_offset_reset="latest",
                consumer_timeout_ms=3000,
                value_deserializer=lambda x: x  # Keep as bytes
            )
            
            # Get partitions
            partitions = consumer.partitions_for_topic(topic)
            if not partitions:
                consumer.close()
                return []
            
            # Assign all partitions
            tps = [TopicPartition(topic, p) for p in partitions]
            consumer.assign(tps)
            
            # Seek to end and go back
            consumer.seek_to_end()
            
            for tp in tps:
                end_offset = consumer.position(tp)
                start_offset = max(0, end_offset - max_messages)
                consumer.seek(tp, start_offset)
            
            # Consume messages
            msg_count = 0
            for msg in consumer:
                event = CDCEvent.from_kafka_message(msg)
                if event:
                    events.append(event)
                msg_count += 1
                if msg_count >= max_messages:
                    break
            
            consumer.close()
            
        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}")
        
        return events
    
    def get_cdc_topics(self) -> list[str]:
        """Get list of CDC-related topics (from Debezium)."""
        topics = self.list_topics()
        # CDC topics typically have format: <prefix>.<schema>.<table>
        return [t for t in topics if "." in t or "cdc" in t.lower() or "pgserver" in t.lower()]
    
    def close(self) -> None:
        """Close Kafka connections."""
        if self._admin_client:
            try:
                self._admin_client.close()
                logger.info("Kafka admin client closed")
            except Exception as e:
                logger.warning(f"Error closing Kafka admin client: {e}")
        
        if self._consumer:
            try:
                self._consumer.close()
            except Exception:
                pass
        
        self._connected = False
