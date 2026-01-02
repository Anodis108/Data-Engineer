import pika
import json
import time
import statistics

RABBITMQ_HOST = "localhost"
USERNAME = "admin"
PASSWORD = "admin123"

QUEUE_NAME = "demo_queue"
PROCESS_TIME = 0.001  # giả lập xử lý 1ms

latencies = []
count = 0
start = time.time()

def callback(ch, method, properties, body):
    global count
    msg = json.loads(body)
    latency = time.time() - msg["ts"]
    latencies.append(latency)

    time.sleep(PROCESS_TIME)  # giả lập xử lý
    ch.basic_ack(delivery_tag=method.delivery_tag)

    count += 1
    if count % 1000 == 0:
        print(f"Processed {count}")

credentials = pika.PlainCredentials(USERNAME, PASSWORD)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=credentials,
        heartbeat=600
    )
)
channel = connection.channel()

channel.basic_qos(prefetch_count=50)
channel.queue_declare(queue=QUEUE_NAME, durable=True)

channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

print("🚀 Consumer started")
channel.start_consuming()

# Khi stop thủ công (Ctrl+C)
end = time.time()
print("\n📊 Stats")
print(f"Messages: {count}")
print(f"Elapsed: {end - start:.2f}s")
print(f"Avg latency: {statistics.mean(latencies):.4f}s")
print(f"P95 latency: {statistics.quantiles(latencies, n=20)[18]:.4f}s")
