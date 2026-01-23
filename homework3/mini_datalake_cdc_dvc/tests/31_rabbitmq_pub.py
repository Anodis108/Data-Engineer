import json
import pika
import os
import time
import uuid

RABBIT_HOST = os.getenv("RABBIT_HOST", "localhost")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", "5672"))
RABBIT_USER = os.getenv("RABBIT_USER", "admin")
RABBIT_PASS = os.getenv("RABBIT_PASS", "admin123")

EXCHANGE = os.getenv("RABBIT_EXCHANGE", "vision.alerts")
ROUTING_KEY = os.getenv("RABBIT_KEY", "person.present")

creds = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
params = pika.ConnectionParameters(host=RABBIT_HOST, port=RABBIT_PORT, credentials=creds, heartbeat=30)

conn = pika.BlockingConnection(params)
ch = conn.channel()

ch.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)

msg = {
    "event_id": str(uuid.uuid4()),
    "camera_id": "cam01",
    "ts": int(time.time() * 1000),
    "person_count": 1,
    "note": "test publish from python",
}

ch.basic_publish(
    exchange=EXCHANGE,
    routing_key=ROUTING_KEY,
    body=json.dumps(msg).encode("utf-8"),
    properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
)

print("✅ published:", msg)
conn.close()
