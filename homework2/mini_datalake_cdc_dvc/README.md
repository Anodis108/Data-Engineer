# Mini Data Lake (Batch) + CDC + DVC — Layer 1 → Layer 3 (Source → Ingestion → Raw Storage)

Bạn đang build đúng theo hình pipeline “Modern Data Stack” ở **mức Layer 1 → Layer 3**:

- **Layer 1 (Source Systems)**: PostgreSQL OLTP (`cdc-postgres`) + (batch files giả lập IoT)
- **Layer 2 (Ingestion)**: Kafka + Debezium (CDC) + Python consumer
- **Layer 3 (Raw Storage / Data Lake)**: MinIO (S3 compatible) lưu **raw dataset**  
  - batch: Parquet `s3://iot-time-series/pump/`
  - cdc: JSONL `s3://lake/raw/cdc/customers/dt=YYYY-MM-DD/events.jsonl`
- (Giữ lại từ bài tập cũ) **Hive Metastore + Trino** để bạn query/verify end-to-end khi cần.

---

## 1) Công nghệ và vai trò trong luồng pipeline

### Docker Compose
- IaC: dựng toàn bộ hệ thống bằng 1 file `docker-compose.yml`.

### PostgreSQL (cdc-postgres)
- Nguồn OLTP sinh ra thay đổi `INSERT/UPDATE/DELETE`.
- Debezium đọc WAL để tạo stream event log.

### Kafka + Zookeeper
- “Event log backbone” (layer ingest).
- Topic CDC tự tạo theo prefix, ví dụ: `pgserver1.public.customers`.

### Kafka Connect + Debezium Connector
- Runtime của connector: container `connect`.
- Job CDC: `scripts/register_connector.json` (auto POST bởi `connector-init`).

### MinIO (Object Storage / S3 Compatible)
- Raw zone dùng để lưu file dạng dataset:
  - `iot-time-series` cho bài batch IoT.
  - `lake` cho raw CDC và cấu trúc lake.
  - `dvcstore` làm remote storage cho DVC.

### DVC (Data Version Control)
- Version hóa dataset (raw CDC) giống cách bạn version code bằng Git.
- Cho phép rollback dataset theo commit.

### Trino + Hive Metastore (giữ lại để kiểm chứng)
- Hive Metastore lưu metadata schema/table trỏ tới location trong MinIO.
- Trino query trực tiếp dữ liệu trên S3 (MinIO) qua Hive connector.

---

## 2) Khởi động hệ thống (Infrastructure)

```bash
cd mini_datalake_cdc_dvc
docker compose up -d
docker compose ps
```

Truy cập:
- MinIO Console: http://localhost:9001 (minioadmin / minioadmin123)
- Trino UI: http://localhost:8080
- Kafka UI: http://localhost:8081
- Kafka Connect REST: http://localhost:8083

---

## 3) Verify CDC (Layer 1 → Layer 2)

### 3.1 Topic CDC đã tạo chưa?
```bash
docker exec -it cdc-kafka kafka-topics --bootstrap-server kafka:9092 --list
```
Bạn sẽ thấy topic:
- `pgserver1.public.customers`

### 3.2 Bắn thay đổi vào PostgreSQL source
```bash
docker exec -it cdc-postgres psql -U dbz -d inventory
```

Thử:
```sql
INSERT INTO public.customers(name, email) VALUES ('Dung', 'dung@example.com');
UPDATE public.customers SET name='Dung Nguyen' WHERE email='dung@example.com';
DELETE FROM public.customers WHERE email='dung@example.com';
```

---

## 4) CDC → Raw dataset (Layer 2 → Layer 3)

### 4.1 Consume CDC → JSONL (local)
> Chạy theo “time window” 30 giây (đúng tư duy batch window cho stream).

```bash
pip install -r requirements.txt
python scripts/cdc_to_jsonl.py --seconds 30 --out lake/raw/cdc/customers
```

Kết quả:
- `lake/raw/cdc/customers/dt=YYYY-MM-DD/events.jsonl`

### 4.2 Upload raw CDC lên MinIO (bucket `lake`)
```bash
python scripts/upload_cdc_to_minio.py --local lake/raw/cdc --bucket lake --prefix raw/cdc
```

Mở MinIO Console kiểm tra:
- bucket `lake` → `raw/cdc/customers/dt=.../events.jsonl`

---

## 5) DVC version hóa dataset CDC

### 5.1 Init DVC + cấu hình remote MinIO
```bash
git init
dvc init
dvc remote add -d minio s3://dvcstore/mini-datalake
dvc remote modify minio endpointurl http://localhost:9000
dvc remote modify minio access_key_id minioadmin
dvc remote modify minio secret_access_key minioadmin123
dvc remote modify minio use_ssl false
```

### 5.2 Track dataset CDC
```bash
dvc add lake/raw/cdc/customers
git add lake/raw/cdc/customers.dvc .gitignore
git commit -m "Add CDC customers raw dataset"
dvc push
```

### 5.3 Nâng cấp: dùng DVC pipeline (dvc.yaml)
```bash
dvc repro cdc_customers_to_jsonl
dvc repro upload_cdc_to_minio
git add dvc.yaml dvc.lock
git commit -m "Add DVC stages for CDC ingestion"
dvc push
```

Rollback:
```bash
git checkout <old_commit>
dvc checkout
```

---

## 6) Batch IoT (giữ lại từ bài tập cũ để bạn hoàn chỉnh end-to-end)

### 6.1 Generate Parquet
```bash
python scripts/generate_data.py
```

### 6.2 Upload lên MinIO
```bash
python scripts/ingest_to_minio.py
```

---

## 7) (Optional) Query bằng Trino (verify)

Mở file:
- `scripts/trino_ddl.sql` (DDL)
- `scripts/trino_queries.sql` (Analytics)

Chạy trên DBeaver hoặc Trino UI.

---

## 8) Mapping đúng theo ảnh pipeline

- **Source Systems**: `cdc-postgres` (OLTP) + batch file generator (IoT)
- **Ingestion**: Kafka + Debezium (CDC), Python consumer (stream → file)
- **Raw Storage**: MinIO buckets `lake` & `iot-time-series`
- **DataOps**: DVC versioning dataset raw (CDC)

Bạn đã build đúng “xương sống” của data platform:
> **event log (Kafka) + object storage (S3/MinIO) + dataset versioning (DVC)**

