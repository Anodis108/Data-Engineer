import time, json
from confluent_kafka import Consumer
from monitor import ResourceMonitorThread  # Đo CPU/RAM song song

NUM_EXPECTED = 1000  # 👈 Sửa lại số lượng cần nhận

# Khởi tạo Kafka Consumer
c = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'simple-consumer-group',
    'auto.offset.reset': 'earliest',
})
c.subscribe(['sos'])

print(f"📥 Đang lắng nghe {NUM_EXPECTED:,} message... (Ctrl+C để thoát)")

received_count = 0
total_latency_ms = 0
start = time.time()

monitor = ResourceMonitorThread(interval=0.2)
monitor.start()

try:
    while received_count < NUM_EXPECTED:
        msg = c.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"❌ {msg.error()}")
            continue

        now = time.time()
        try:
            data = json.loads(msg.value().decode())
            latency_ms = (now - data['sent_at']) * 1000
            total_latency_ms += latency_ms
            received_count += 1

            if received_count % 100 == 0:
                print(f"📨 Đã nhận: {received_count:,} messages")
        except Exception as e:
            print(f"❌ Lỗi đọc message: {e}")

except KeyboardInterrupt:
    print("\n🛑 Đã dừng bởi người dùng.")
finally:
    c.close()
    monitor.stop()
    monitor.join()
    end = time.time()

    print("\n📊 Tổng kết:")
    print(f"✅ Tổng nhận: {received_count:,} messages")

    duration_ms = (end - start) * 1000
    print(f"⏱️ Thời gian thực tế: {duration_ms:.2f} ms")

    if received_count > 0:
        avg_latency = total_latency_ms / received_count
        print(f"📈 Độ trễ trung bình: {avg_latency:.2f} ms")

    avg_cpu, avg_ram = monitor.get_average_usage()
    print(f"📊 CPU trung bình (monitor): {avg_cpu:.2f}% | RAM trung bình: {avg_ram:.2f} MB")
