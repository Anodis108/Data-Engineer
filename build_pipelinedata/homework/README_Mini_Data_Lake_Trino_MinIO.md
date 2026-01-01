
# Mini Data Lake with Trino & MinIO

## 1. Mục tiêu bài tập
Xây dựng một **mini data lake** mô phỏng kiến trúc thực tế của Data Engineer, bao gồm:
- Sinh dữ liệu IoT (pump sensor)
- Lưu trữ dữ liệu dạng Parquet trên Object Storage (MinIO – S3 compatible)
- Định nghĩa schema & table bằng Trino (Hive connector)
- Phân tích dữ liệu (aggregation & alarm detection)

---

## 2. Kiến trúc tổng thể

```
[generate_data.py]
        |
        v
   Parquet files
        |
        v
[ingest_to_minio.py]
        |
        v
   MinIO (S3)
        |
        v
 Hive Metastore
        |
        v
      Trino
        |
        v
   Analytics / SQL (DBeaver, Trino UI)
```

---

## 3. Công nghệ sử dụng & vai trò

### 3.1 Docker & Docker Compose
- **Vai trò**: Dựng toàn bộ hạ tầng bằng Infrastructure as Code
- **Lợi ích**:
  - Tái sử dụng
  - Dễ triển khai, teardown
  - Mô phỏng môi trường production

---

### 3.2 MinIO (Object Storage – S3 Compatible)
- **Vai trò**: Data Lake Storage
- **Lưu trữ**: File Parquet sinh từ Python
- **Ưu điểm**:
  - Tương thích S3
  - Dùng local nhưng kiến trúc giống cloud (AWS S3)

Bucket sử dụng:
- `iot-time-series/pump/`

---

### 3.3 Python (Data Generation & Ingestion)

#### generate_data.py
- Sinh dữ liệu cảm biến:
  - event_timestamp
  - pressure
  - velocity
  - speed
- Xuất dữ liệu sang **Parquet**

#### ingest_to_minio.py
- Upload Parquet files lên MinIO
- Đóng vai trò **Data Ingestion Layer**

---

### 3.4 Hive Metastore
- **Vai trò**: Metadata Store
- Lưu:
  - Schema
  - Table
  - Location (S3 path)
- Cho phép nhiều engine (Trino, Spark) dùng chung metadata

---

### 3.5 Trino (Distributed SQL Engine)
- **Vai trò**: Query Engine
- Truy vấn trực tiếp dữ liệu trên S3 thông qua Hive Connector
- Không cần load dữ liệu vào DB

Trino đảm nhiệm:
- Schema definition (DDL)
- Analytics query (aggregation, filtering)

---

### 3.6 DBeaver / Trino Web UI
- **Vai trò**: Client query
- Chạy SQL
- Quan sát execution, query history

---

## 4. Các bước thực hiện (Pipeline Flow)

### Bước 1: Khởi động hạ tầng
```bash
docker compose up -d
```

---

### Bước 2: Sinh dữ liệu
```bash
python generate_data.py
```

Kết quả:
- Tạo file `.parquet` trong thư mục `out/`

---

### Bước 3: Ingest dữ liệu vào MinIO
```bash
python ingest_to_minio.py
```

Kết quả:
- File Parquet nằm tại:
```
s3://iot-time-series/pump/
```

---

### Bước 4: Định nghĩa Schema & Table bằng Trino

#### Tạo schema
```sql
CREATE SCHEMA IF NOT EXISTS hive.iot_dw
WITH (location = 's3://iot-time-series/iot_dw/');
```

#### Tạo bảng pump
```sql
CREATE TABLE hive.iot_dw.pump (
    event_timestamp TIMESTAMP,
    pressure DOUBLE,
    velocity DOUBLE,
    speed DOUBLE
)
WITH (
    format = 'PARQUET',
    external_location = 's3://iot-time-series/pump/'
);
```

---

## 5. Phân tích dữ liệu

### 5.1 Giá trị trung bình theo giờ
```sql
SELECT
    date_trunc('hour', event_timestamp) AS hour,
    avg(pressure) AS avg_pressure,
    avg(speed) AS avg_speed
FROM hive.iot_dw.pump
GROUP BY 1
ORDER BY 1;
```

---

### 5.2 Phát hiện áp suất vượt ngưỡng (>150)

#### Đếm số bản ghi alarm
```sql
SELECT count(*) AS alarm_count
FROM hive.iot_dw.pump
WHERE pressure > 150;
```

#### Liệt kê chi tiết
```sql
SELECT event_timestamp, pressure
FROM hive.iot_dw.pump
WHERE pressure > 150
ORDER BY event_timestamp;
```

---

## 6. Ý nghĩa Data Engineering

Pipeline này mô phỏng:
- **Bronze layer**: Raw Parquet trên S3
- **Metadata layer**: Hive Metastore
- **Query layer**: Trino
- **Analytics layer**: SQL aggregation & alert

Có thể mở rộng:
- Partition theo ngày
- Incremental ingestion
- BI dashboard (Superset)
- Streaming (Kafka)

---

## 7. Kết luận
Bài tập hoàn thành đầy đủ vòng đời dữ liệu:
**Generate → Ingest → Store → Query → Analyze**

Đây là nền tảng chuẩn để phát triển thành:
- Data Lakehouse
- Real-time analytics
- Production Data Platform
