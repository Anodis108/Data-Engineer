"""RabbitMQ publisher for vision event alerts."""
import logging
from typing import Optional

import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.domain.value_objects import AlertPayload


logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """Publisher for sending alerts to RabbitMQ."""
    
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        exchange: str
    ):
        """
        Initialize RabbitMQ publisher.
        
        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            user: Username
            password: Password
            exchange: Exchange name for publishing
        """
        self.exchange = exchange
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel = None
        self._connected = False
        
        try:
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
            
            # Declare exchange
            self._channel.exchange_declare(
                exchange=exchange,
                exchange_type="topic",
                durable=True
            )
            
            # Declare queues and bind them
            self._setup_queues()
            
            self._connected = True
            logger.info(f"RabbitMQ connected: host={host}:{port}, exchange={exchange}")
            
        except AMQPConnectionError as e:
            logger.error(f"RabbitMQ connection failed (host={host}:{port}): {e}. Messaging disabled.")
        except AMQPChannelError as e:
            logger.error(f"RabbitMQ channel error: {e}. Messaging disabled.")
        except Exception as e:
            logger.error(f"RabbitMQ unexpected error: {e}. Messaging disabled.")
    
    def _setup_queues(self) -> None:
        """Setup default queues for vision alerts."""
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
        """Check if RabbitMQ is connected and ready."""
        return self._connected and self._channel is not None
    
    def publish_alert(self, payload: AlertPayload, routing_key: str) -> bool:
        """
        Publish alert message to RabbitMQ.
        
        Args:
            payload: Alert payload to publish
            routing_key: Routing key (e.g., 'person.present', 'person.left')
        
        Returns:
            True if published successfully, False otherwise
        """
        if not self.is_connected:
            return False
        
        try:
            self._channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=payload.to_bytes(),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2  # Persistent
                )
            )
            
            logger.debug(f"Published alert: {routing_key} -> {payload.event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish alert: {e}")
            return False
    
    def close(self) -> None:
        """Close RabbitMQ connection."""
        if self._connection and not self._connection.is_closed:
            try:
                self._connection.close()
                logger.info("RabbitMQ connection closed")
            except Exception as e:
                logger.warning(f"Error closing RabbitMQ: {e}")
        
        self._connected = False
