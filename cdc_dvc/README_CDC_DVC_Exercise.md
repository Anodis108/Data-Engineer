# Bài Tập: Kết Hợp CDC (Debezium + Kafka) Với DVC

## Mục tiêu bài tập

-   Hiểu vai trò CDC vs DVC
-   Biết cách biến stream CDC → dataset
-   Version hóa dataset sinh ra từ CDC bằng DVC
-   Rollback dataset CDC theo thời gian

------------------------------------------------------------------------

## Kiến trúc tổng thể

PostgreSQL\
→ Debezium\
→ Kafka\
→ Consumer\
→ Data Lake\
→ DVC

------------------------------------------------------------------------

## Phân vai

  Thành phần   Vai trò
  ------------ -----------------------
  Debezium     Bắt thay đổi realtime
  Kafka        Event log
  Consumer     Stream → file
  Data Lake    Lưu dataset
  DVC          Version dataset

------------------------------------------------------------------------

## Tạo cấu trúc project

``` bash
mkdir -p lake/raw/cdc/customers
mkdir scripts
```

------------------------------------------------------------------------

## Consumer CDC → JSONL

``` python
import json, os
from datetime import datetime
from kafka import KafkaConsumer

TOPIC = "pgserver1.public.customers"

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=["localhost:9092"],
    auto_offset_reset="earliest",
    value_deserializer=lambda v: json.loads(v.decode())
)

date = datetime.utcnow().strftime("%Y-%m-%d")
os.makedirs(f"lake/raw/cdc/customers/dt={date}", exist_ok=True)

with open(f"lake/raw/cdc/customers/dt={date}/events.jsonl", "a") as f:
    for msg in consumer:
        payload = msg.value.get("payload", msg.value)
        f.write(json.dumps(payload) + "\n")
        f.flush()
```

------------------------------------------------------------------------

## Track dataset CDC bằng DVC

``` bash
dvc add lake/raw/cdc/customers
git add lake/raw/cdc/customers.dvc
git commit -m "Add CDC customers dataset snapshot"
dvc push
```

------------------------------------------------------------------------

## Update & rollback

``` bash
dvc add lake/raw/cdc/customers
git commit -am "Update CDC customers dataset"
dvc push
```

``` bash
git checkout <commit_cu>
dvc checkout
```

------------------------------------------------------------------------

## Kết luận

Bạn đã kết hợp thành công: - CDC realtime - DVC versioning - Tư duy Data
Engineering chuẩn production

## Nâng cao (dùng cho product)
Thay vì chạy tay, bạn biến “build dataset từ CDC” thành stage.

``` bash
dvc stage add -n cdc_customers_to_jsonl \
  -d scripts/cdc_to_jsonl.py \
  -o lake/raw/cdc/customers \
  python scripts/cdc_to_jsonl.py
```
Sau đó:
``` bash
dvc repro
git add dvc.yaml dvc.lock
git commit -m "Add DVC stage for CDC customers ingestion"
```
Thực tế production bạn không để stage chạy vô hạn; bạn chạy theo “window” (5 phút/1 giờ/1 ngày). Nhưng để học, stage dạng này giúp bạn hiểu tư duy pipeline.