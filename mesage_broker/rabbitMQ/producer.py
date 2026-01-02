import pika
import time
import json
import uuid

RABBITMQ_HOST = "localhost"
USERNAME = "admin"
PASSWORD = "admin123"

QUEUE_NAME = "demo_queue"
TOTAL_MESSAGES = 10_000

credentials = pika.PlainCredentials(USERNAME, PASSWORD)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=credentials,
        heartbeat=600
    )
)
channel = connection.channel()

channel.queue_declare(queue=QUEUE_NAME, durable=True)

start_time = time.time()

for i in range(TOTAL_MESSAGES):
    msg = {
        "id": str(uuid.uuid4()),
        "index": i,
        "ts": time.time()
    }
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(msg),
        properties=pika.BasicProperties(
            delivery_mode=2  # persistent
        )
    )

end_time = time.time()

elapsed = end_time - start_time
print("✅ Producer finished")
print(f"Total messages: {TOTAL_MESSAGES}")
print(f"Total time: {elapsed:.2f}s")
print(f"Throughput: {TOTAL_MESSAGES / elapsed:.2f} msg/s")

connection.close()
