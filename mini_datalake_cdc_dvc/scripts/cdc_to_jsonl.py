import argparse
import json
import os
import time
from datetime import datetime, timezone

from kafka import KafkaConsumer

TOPIC = os.getenv("CDC_TOPIC", "pgserver1.public.customers")
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

def utc_day():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def main():
    ap = argparse.ArgumentParser(description="Consume Debezium CDC from Kafka -> JSONL raw files")
    ap.add_argument("--out", default="lake/raw/cdc/customers", help="output base folder")
    ap.add_argument("--seconds", type=int, default=30, help="run time window (seconds)")
    ap.add_argument("--max-messages", type=int, default=0, help="stop after N messages (0 = unlimited)")
    args = ap.parse_args()

    dt = utc_day()
    out_dir = os.path.join(args.out, f"dt={dt}")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "events.jsonl")

    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=[BOOTSTRAP],
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    print(f"📥 Consuming topic={TOPIC} bootstrap={BOOTSTRAP}")
    print(f"📝 Writing to {out_file}")
    start = time.time()
    count = 0

    with open(out_file, "a", encoding="utf-8") as f:
        for msg in consumer:
            val = msg.value
            payload = val.get("payload", val)
            # Keep full payload (before/after/op/source/ts_ms)
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            f.flush()

            count += 1
            if args.max_messages and count >= args.max_messages:
                break
            if time.time() - start >= args.seconds:
                break

    print(f"✅ Done. messages={count}")

if __name__ == "__main__":
    main()
