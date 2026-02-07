"""Kafka client cho việc giám sát CDC và duyệt topic."""
import logging
import json
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class KafkaConfig:
    """Cấu hình kết nối Kafka."""
    bootstrap_servers: str = "localhost:9092"
    consumer_group: str = "streamlit-monitor"
    auto_offset_reset: str = "latest"


@dataclass 
class CDCEvent:
    """Đại diện cho một sự kiện CDC từ Debezium."""
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
        """Phân tích sự kiện CDC từ tin nhắn Kafka."""
        # Phân tích nội dung tin nhắn (giả định là JSON)
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


class KafkaClient:
    """Client để duyệt Kafka topic và giám sát CDC."""
    
    def __init__(self, config: Optional[KafkaConfig] = None):
        """
        Khởi tạo Kafka client.
        
        Args:
            config: Cấu hình kết nối Kafka
        """
        self.config = config or KafkaConfig()
        self._connected = False
        self._admin_client = None
        self._consumer = None
        
        # Kết nối tới Kafka
        from kafka import KafkaAdminClient, KafkaConsumer
        from kafka.errors import NoBrokersAvailable
        
        self._admin_client = KafkaAdminClient(
            bootstrap_servers=self.config.bootstrap_servers,
            client_id="streamlit-admin"
        )
        
        self._connected = True
        logger.info(f"Kafka connected: {self.config.bootstrap_servers}")
    
    @property
    def is_connected(self) -> bool:
        """Kiểm tra xem Kafka đã kết nối chưa."""
        return self._connected and self._admin_client is not None
    
    def list_topics(self) -> list[str]:
        """Lấy danh sách các Kafka topics có sẵn."""
        if not self.is_connected:
            return []
        
        # Liệt kê topics sử dụng admin client
        topics = self._admin_client.list_topics()
        # Lọc bỏ các topics nội bộ
        return [t for t in topics if not t.startswith("__") and not t.startswith("connect_")]
    
    def get_topic_info(self, topic: str) -> Optional[dict]:
        """Lấy metadata về một topic."""
        if not self.is_connected:
            return None
        
        # Lấy topic metadata sử dụng consumer tạm thời
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
    
    def get_recent_messages(self, topic: str, max_messages: int = 20) -> list[CDCEvent]:
        """
        Lấy các tin nhắn gần đây từ một topic.
        
        Args:
            topic: Tên topic cần consume
            max_messages: Số lượng tin nhắn tối đa cần lấy
            
        Returns:
            Danh sách các đối tượng CDCEvent
        """
        if not self.is_connected:
            return []
        
        events = []
        
        # Consume tin nhắn từ topic
        from kafka import KafkaConsumer, TopicPartition
        
        consumer = KafkaConsumer(
            bootstrap_servers=self.config.bootstrap_servers,
            auto_offset_reset="latest",
            consumer_timeout_ms=3000,
            value_deserializer=lambda x: x  # Giữ nguyên bytes
        )
        
        # Lấy partitions
        partitions = consumer.partitions_for_topic(topic)
        if not partitions:
            consumer.close()
            return []
        
        # Gán tất cả partitions
        tps = [TopicPartition(topic, p) for p in partitions]
        consumer.assign(tps)
        
        # Seek tới cuối và lùi lại
        consumer.seek_to_end()
        
        for tp in tps:
            end_offset = consumer.position(tp)
            start_offset = max(0, end_offset - max_messages)
            consumer.seek(tp, start_offset)
        
        # Consume tin nhắn
        msg_count = 0
        for msg in consumer:
            event = CDCEvent.from_kafka_message(msg)
            if event:
                events.append(event)
            msg_count += 1
            if msg_count >= max_messages:
                break
        
        consumer.close()
        
        return events
    
    def get_cdc_topics(self) -> list[str]:
        """Lấy danh sách các topics liên quan đến CDC (từ Debezium)."""
        topics = self.list_topics()
        # Các topic CDC thường có định dạng: <prefix>.<schema>.<table>
        return [t for t in topics if "." in t or "cdc" in t.lower() or "pgserver" in t.lower()]
    
    def close(self) -> None:
        """Đóng kết nối Kafka."""
        if self._admin_client:
            # Đóng admin client
            self._admin_client.close()
            logger.info("Kafka admin client closed")
        
        if self._consumer:
            # Đóng consumer
            self._consumer.close()
        
        self._connected = False
