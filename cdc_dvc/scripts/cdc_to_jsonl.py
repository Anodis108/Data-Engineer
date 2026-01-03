import json
import os
from datetime import datetime, timezone
from kafka import KafkaConsumer

TOPIC = "pgserver1.public.customers"
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

def out_path():
    # partition theo ngày UTC (bạn có thể đổi sang Asia/Ho_Chi_Minh)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(f"lake/raw/cdc/customers/dt={day}", exist_ok=True)
    return f"lake/raw/cdc/customers/dt={day}/events.jsonl"

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=[BOOTSTRAP],
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
)

path = out_path()
with open(path, "a", encoding="utf-8") as f:
    for msg in consumer:
        # Debezium JSON Converter có schema+payload => lấy payload
        value = msg.value
        payload = value.get("payload", value)
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        f.flush()
