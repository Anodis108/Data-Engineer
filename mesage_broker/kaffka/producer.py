from confluent_kafka import Producer
from monitor import ResourceMonitorThread  # 👈 Import bộ đo song song
import time, json

def cb(err, msg):
    if err:
        print(f"❌ Failed: {err}")
    elif msg.offset() % 100 == 0:  # Log mỗi 100 tin
        print(f"✅ Sent: {msg.topic()} [{msg.partition()}] offset {msg.offset()}")

# Khởi tạo Kafka Producer với cấu hình phù hợp cho 1000 messages
p = Producer({
    'bootstrap.servers': 'localhost:9092',
    'batch.num.messages': 1000,
    'queue.buffering.max.messages': 100000,
    'queue.buffering.max.ms': 10,
})

text = input("📤 Nhập nội dung để gửi 1,000 message:\n> ")

monitor = ResourceMonitorThread(interval=0.2)
monitor.start()

start = time.time()

try:
    for i in range(1000):
        payload = {
            'text': f"{text} #{i+1}",
            'sent_at': time.time()
        }

        p.poll(0)
        p.produce('sos', json.dumps(payload).encode(), callback=cb)

        if (i + 1) % 100 == 0:
            print(f"📦 Đã gửi: {i + 1:,} messages")

    print("⌛ Đang flush producer...")
    p.flush()

    elapsed = time.time() - start
    print(f"🎉 Gửi xong 1,000 messages trong {elapsed*1000:.2f} ms")
    time.sleep(0.2)

except KeyboardInterrupt:
    print("\n🛑 Đã hủy bởi người dùng.")
finally:
    print("🧹 Đang dừng monitor và flush Kafka...")
    monitor.stop()
    monitor.join()
    p.flush()

    avg_cpu, avg_ram = monitor.get_average_usage()
    print(f"📊 CPU trung bình (monitor): {avg_cpu:.2f}% | RAM trung bình: {avg_ram:.2f} MB")
