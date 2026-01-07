import json
import pika
import os

RABBIT_HOST = os.getenv("RABBIT_HOST", "localhost")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", "5672"))
RABBIT_USER = os.getenv("RABBIT_USER", "admin")
RABBIT_PASS = os.getenv("RABBIT_PASS", "admin123")

EXCHANGE = os.getenv("RABBIT_EXCHANGE", "vision.alerts")
ROUTING_KEY = os.getenv("RABBIT_KEY", "person.present")
QUEUE = os.getenv("RABBIT_QUEUE", "q_person_present")

creds = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
params = pika.ConnectionParameters(host=RABBIT_HOST, port=RABBIT_PORT, credentials=creds, heartbeat=30)

conn = pika.BlockingConnection(params)
ch = conn.channel()

ch.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
ch.queue_declare(queue=QUEUE, durable=True)
ch.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key=ROUTING_KEY)

print(f"[*] Waiting messages on queue={QUEUE} bind={EXCHANGE}:{ROUTING_KEY}. Ctrl+C to stop.")

def on_msg(channel, method, properties, body: bytes):
    try:
        msg = json.loads(body.decode("utf-8"))
    except Exception:
        msg = body.decode("utf-8", errors="ignore")
    print("[x] received:", msg)
    channel.basic_ack(delivery_tag=method.delivery_tag)

ch.basic_consume(queue=QUEUE, on_message_callback=on_msg, auto_ack=False)
ch.start_consuming()
