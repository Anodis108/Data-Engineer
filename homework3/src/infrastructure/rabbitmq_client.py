"""Publisher RabbitMQ cho các cảnh báo sự kiện thị giác."""
import logging
from typing import Optional

import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.domain.value_objects import AlertPayload


logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """Publisher để gửi cảnh báo tới RabbitMQ."""
    
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        exchange: str
    ):
        """
        Khởi tạo RabbitMQ publisher.
        
        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            user: Tên đăng nhập
            password: Mật khẩu
            exchange: Tên exchange để publish
        """
        self.exchange = exchange
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel = None
        self._connected = False
        
        # Thiết lập kết nối tới RabbitMQ
        credentials = pika.PlainCredentials(user, password)
        params = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=credentials,
            heartbeat=30,
            connection_attempts=3,
            retry_delay=1
        )
        
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        
        # Khai báo exchange
        self._channel.exchange_declare(
            exchange=exchange,
            exchange_type="topic",
            durable=True
        )
        
        # Khai báo queues và bind chúng
        self._setup_queues()
        
        self._connected = True
        logger.info(f"RabbitMQ connected: host={host}:{port}, exchange={exchange}")
    
    def _setup_queues(self) -> None:
        """Thiết lập các queues mặc định cho cảnh báo thị giác."""
        queues = [
            ("q_person_present", "person.present"),
            ("q_person_still_present", "person.still_present"),
            ("q_person_left", "person.left"),
        ]
        
        for queue_name, routing_key in queues:
            self._channel.queue_declare(queue=queue_name, durable=True)
            self._channel.queue_bind(
                queue=queue_name,
                exchange=self.exchange,
                routing_key=routing_key
            )
    
    @property
    def is_connected(self) -> bool:
        """Kiểm tra RabbitMQ đã kết nối và sẵn sàng chưa."""
        if self._connection is None or self._connection.is_closed:
            return False
        if self._channel is None or self._channel.is_closed:
            return False
        return self._connected
    
    def publish_alert(self, payload: AlertPayload, routing_key: str) -> bool:
        """
        Gửi tin nhắn cảnh báo tới RabbitMQ.
        
        Args:
            payload: Payload cảnh báo cần gửi
            routing_key: Routing key (ví dụ: 'person.present', 'person.left')
        
        Returns:
            True nếu gửi thành công, False nếu thất bại
        """
        if not self.is_connected:
            logger.warning("RabbitMQ not connected. Dropping alert.")
            return False
        
        # Gửi tin nhắn tới exchange với routing key
        self._channel.basic_publish(
            exchange=self.exchange,
            routing_key=routing_key,
            body=payload.to_bytes(),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2  # Persistent (bền vững)
            )
        )
        
        logger.debug(f"Published alert: {routing_key} -> {payload.event_id}")
        return True
    
    def consume_alerts(self, queue_name: str, limit: int = 10) -> list[AlertPayload]:
        """
        Lấy (consume) tin nhắn từ queue mà không blocking.
        
        Args:
            queue_name: Tên queue để lấy tin nhắn
            limit: Số lượng tối đa tin nhắn cần lấy
            
        Returns:
            Danh sách các đối tượng AlertPayload
        """
        if not self.is_connected:
            return []
            
        alerts = []
        # Lấy tin nhắn từ queue (không blocking)
        for _ in range(limit):
            method_frame, header_frame, body = self._channel.basic_get(queue=queue_name, auto_ack=True)
            if method_frame:
                payload = AlertPayload.from_json(body.decode("utf-8"))
                alerts.append(payload)
            else:
                # Không còn tin nhắn trong queue này
                break
            
        return alerts

    def close(self) -> None:
        """Đóng kết nối RabbitMQ."""
        if self._connection and not self._connection.is_closed:
            # Đóng kết nối để giải phóng tài nguyên
            self._connection.close()
            logger.info("RabbitMQ connection closed")
        
        self._connected = False
