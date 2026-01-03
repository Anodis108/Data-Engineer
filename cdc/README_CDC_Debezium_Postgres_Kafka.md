# CDC with PostgreSQL + Debezium + Confluent Kafka (Hands-on)

## Mục tiêu

Xây dựng và thực hành **Change Data Capture (CDC)** để bắt các thay đổi
`INSERT / UPDATE / DELETE` trong PostgreSQL và stream realtime vào Kafka
bằng Debezium.

------------------------------------------------------------------------

## Kiến trúc tổng thể

PostgreSQL\
→ WAL (Write-Ahead Log)\
→ Debezium PostgreSQL Connector (Kafka Connect)\
→ Kafka Topic (event log)\
→ Consumer / Data Lake / Feature Store

------------------------------------------------------------------------

## Thành phần sử dụng

-   PostgreSQL (nguồn dữ liệu OLTP)
-   Debezium (CDC engine)
-   Kafka (Confluent distribution)
-   Kafka Connect (runtime chạy Debezium)
-   Kafka UI (quan sát topic & connector)
-   Docker Compose (dựng môi trường)

------------------------------------------------------------------------

## Bước 1: Dựng hạ tầng bằng Docker Compose

Các service: - zookeeper - kafka - postgres (image debezium/postgres) -
connect (debezium/connect) - kafka-ui

Mục đích: - Kafka + Zookeeper: event streaming backbone - PostgreSQL:
database nguồn - Kafka Connect: nơi chạy Debezium connector - Kafka UI:
kiểm tra topic, connector

------------------------------------------------------------------------

## Bước 2: Tạo bảng và dữ liệu trong PostgreSQL

``` sql
CREATE TABLE public.customers (
  id SERIAL PRIMARY KEY,
  name TEXT,
  email TEXT
);

INSERT INTO public.customers(name, email)
VALUES ('Alice', 'alice@example.com');
```

Mục đích: - Có bảng thực tế để CDC theo dõi - Có Primary Key (bắt buộc
cho CDC)

------------------------------------------------------------------------

## Bước 3: Tạo Debezium PostgreSQL Connector

1️⃣ Vì sao bước 3 (POST connector) thường làm bằng lệnh?  
Thực tế Debezium/Kafka Connect:  
- Kafka Connect chỉ là runtime
- Connector là stateful object
- Connector được quản lý bằng REST API  

👉 Design của Kafka Connect cố ý tách:  
- Runtime (container)
- Job definition (connector config)

📌 Đây là triết lý platform, không phải thiếu tính năng.

``` bash
curl -X POST http://localhost:8083/connectors   -H "Content-Type: application/json"   -d '{
    "name": "pg-cdc",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "tasks.max": "1",
      "database.hostname": "cdc-postgres",
      "database.port": "5432",
      "database.user": "dbz",
      "database.password": "dbz",
      "database.dbname": "inventory",
      "topic.prefix": "pgserver1",
      "plugin.name": "pgoutput",
      "slot.name": "debezium_slot",
      "publication.autocreate.mode": "filtered",
      "table.include.list": "public.customers",
      "snapshot.mode": "initial"
    }
  }'
```

Mục đích từng cấu hình quan trọng: - `plugin.name=pgoutput`: logical
decoding chuẩn của PostgreSQL - `slot.name`: giữ vị trí đọc WAL
(checkpoint) - `topic.prefix`: tiền tố topic Kafka -
`snapshot.mode=initial`: snapshot dữ liệu ban đầu -
`table.include.list`: chỉ capture bảng cần thiết

------------------------------------------------------------------------

## Bước 4: Kiểm tra trạng thái connector

``` bash
curl http://localhost:8083/connectors/pg-cdc/status
```

Kết quả mong đợi:

``` json
"state": "RUNNING"
```
Ý nghĩa: - Connector đã được Kafka Connect load - Debezium đã bắt đầu
đọc WAL

------------------------------------------------------------------------

## Bước 5: Kiểm tra Kafka topic

``` bash
docker exec -it cdc-kafka-1 kafka-topics   --bootstrap-server kafka:9092 --list
```

Topic CDC được tạo tự động:

    pgserver1.public.customers

------------------------------------------------------------------------

## Bước 6: Consume CDC events từ Kafka (CHECK QUAN TRỌNG NHẤT)

``` bash
docker exec -it cdc-kafka-1 kafka-console-consumer   --bootstrap-server kafka:9092   --topic pgserver1.public.customers   --from-beginning
```

Mục đích: - Kiểm tra CDC có thực sự chảy vào Kafka hay không - Xác nhận
realtime event

------------------------------------------------------------------------

## Bước 7: Test INSERT / UPDATE / DELETE

Trong PostgreSQL:

``` sql
INSERT INTO public.customers(name, email)
VALUES ('Bob', 'bob@example.com');

UPDATE public.customers
SET name = 'Alice Smith'
WHERE id = 1;

DELETE FROM public.customers
WHERE name = 'Bob';
```

Quan sát terminal consumer để thấy event mới xuất hiện.

------------------------------------------------------------------------

## Ý nghĩa trường `op` trong message

  op   Ý nghĩa
  ---- -------------------------
  r    snapshot (read ban đầu)
  c    insert
  u    update
  d    delete

------------------------------------------------------------------------

## Cấu trúc message Debezium

``` json
{
  "before": {...},
  "after": {...},
  "op": "u",
  "source": {...},
  "ts_ms": 1700000000000
}
```

Ý nghĩa: - `before`: dữ liệu cũ - `after`: dữ liệu mới - `op`: loại thay
đổi - `source`: metadata (db, table, lsn) - `ts_ms`: timestamp

------------------------------------------------------------------------

## Bổ sung: REPLICA IDENTITY FULL

Để UPDATE / DELETE có `before` đầy đủ:

``` sql
ALTER TABLE public.customers REPLICA IDENTITY FULL;
```

------------------------------------------------------------------------

## Ý nghĩa thực tế

Pipeline này dùng trong: 
- Realtime Data Lake ingestion 
- Event-driven microservices 
- Audit & data lineage 
- Feature Store realtime cho ML

CDC cung cấp **realtime**,\
DVC (ở bước tiếp theo) dùng để **version hóa snapshot dữ liệu**.

------------------------------------------------------------------------

## Hướng phát triển tiếp theo

1.  Unwrap Debezium message (SMT)
2.  Consumer Python → ghi Parquet / Iceberg
3.  DVC version hóa dataset CDC
4.  So sánh CDC vs batch snapshot

------------------------------------------------------------------------

## Kết luận

Bạn đã xây dựng thành công: - CDC chuẩn production - Không poll DB -
Không batch - Không mất thứ tự

Đây là nền tảng cốt lõi của **Data Engineering realtime pipeline**.
