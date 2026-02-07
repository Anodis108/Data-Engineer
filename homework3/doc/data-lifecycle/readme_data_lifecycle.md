# Data Lifecycle – End-to-End Overview

## 1. Mục tiêu tài liệu

Tài liệu này mô tả **toàn bộ Data Lifecycle** của một hệ thống dữ liệu hiện đại (Modern Data Stack), từ lúc dữ liệu được sinh ra cho đến khi được sử dụng để tạo ra **giá trị kinh doanh thực tế**.

Mục tiêu:
- Thống nhất **tư duy & ngôn ngữ** giữa Product, Engineering, Data
- Làm tài liệu nền tảng cho **thiết kế – vận hành – mở rộng** hệ thống data
- Tránh các anti-pattern phổ biến khi build data platform

---

## 2. Tổng quan Data Lifecycle

Data Lifecycle bao gồm **6 stage chính**, được kết nối thành **một vòng lặp khép kín**:

```
Stage 1  → Stage 2 → Stage 3 → Stage 4 → Stage 5 → Stage 6
Source     Ingestion  Raw      Processing  Serving   Consumption
                                                ↺ (feedback loop)
```

Nguyên tắc cốt lõi:
- Mỗi stage **có vai trò riêng**
- Không stage nào nên “ôm” trách nhiệm của stage khác
- Làm đúng sớm → downstream đơn giản

---

## 3. STAGE 1 – Source Systems

### Vai trò
- Nơi dữ liệu **được sinh ra lần đầu**
- System of Record (SoR)
- Phục vụ **business operation**, không phải analytics

### Loại source phổ biến
- OLTP Databases (Postgres, MySQL)
- Application / Event logs
- External files (CSV, JSON, partner data)

### Yêu cầu bắt buộc
- Identifier (primary key / event_id)
- Timestamp (event_time / created_at)
- Schema rõ ràng, ổn định

### Không nên làm ở Stage 1
- Clean data
- Join / aggregate
- Business logic cho analytics

---

## 4. STAGE 2 – Ingestion

### Vai trò
- Đưa dữ liệu từ Source vào hệ thống data
- Decouple source & downstream
- Bảo toàn dữ liệu gốc

### Hai chiến lược ingestion

**Streaming ingestion**
- CDC từ OLTP
- Event streaming
- Realtime / near-realtime

**Batch ingestion**
- External files
- Scheduled pull
- Volume nhỏ, không realtime

### Thành phần chính
- Message broker (Kafka)
- Batch jobs (Python, Airflow)

### Nguyên tắc thiết kế
- At-least-once
- Replayable
- Không business logic
- Có monitoring & retry

---

## 5. STAGE 3 – Raw Storage (Data Lake / Bronze)

### Vai trò
- Lưu **dữ liệu nguyên bản** sau ingestion
- Single source of truth
- Cho phép replay, backfill, audit

### Đặc điểm
- Append-only
- Schema-on-read
- Không tối ưu cho query

### Công nghệ
- Object Storage (S3, GCS, MinIO)
- Columnar format (Parquet, ORC)
- Table format (Delta, Hudi, Iceberg)

### Nguyên tắc sống còn
- Raw data phải đầy đủ, không chỉnh sửa
- Partition theo time
- Có metadata catalog

---

## 6. STAGE 4 – Processing

### Vai trò
- Biến raw data → data có ý nghĩa
- Áp dụng logic kỹ thuật & business

### Hai loại processing

**Batch processing**
- Historical data
- Aggregation, join, metric
- Dễ debug, dễ backfill

**Stream processing**
- Near-realtime
- Stateful, window-based
- Chỉ dùng khi thực sự cần

### Output
- Silver layer (clean, normalized)
- Gold layer (business-ready)

### Nguyên tắc
- Idempotent
- Deterministic
- Tách technical logic & business logic

---

## 7. STAGE 5 – Serving (Data Warehouse / Gold)

### Vai trò
- Phục vụ query nhanh
- Schema thân thiện business
- Metric nhất quán

### Dữ liệu
- Fact tables
- Dimension tables
- Data marts theo domain

### Công nghệ
- Data Warehouse (BigQuery, Snowflake, Redshift)
- Lakehouse / Query Engine (Trino)

### Yêu cầu
- Schema ổn định
- Access control
- Performance cao
- Có semantic layer

---

## 8. STAGE 6 – Consumption & Activation

### Vai trò
- Biến data thành **decision & action**
- Chứng minh ROI của data platform

### Nhóm consumer
- BI & Analytics
- Product / Application
- ML / AI systems
- Reverse ETL (activation)

### Điểm mấu chốt
- Insight phải dẫn đến hành động
- Có feedback loop về source systems

---

## 9. Orchestration & Observability (xuyên suốt)

Áp dụng cho tất cả các stage:
- Orchestration (Airflow)
- Monitoring (metrics, freshness, SLA)
- Logging & alerting
- Data lineage & ownership

---

## 10. Nguyên tắc tổng kết

- Data Lifecycle ≠ toolchain
- Raw ≠ Processed ≠ Serving
- Batch + Streaming cùng tồn tại
- Data chỉ có giá trị khi được sử dụng

> Một hệ thống data thành công không phải vì nhiều công nghệ,
> mà vì **mỗi stage làm đúng vai trò của mình**.

---

## 11. Tài liệu này dùng để làm gì tiếp theo?

- Onboarding data engineer mới
- Thiết kế data platform cho product
- Review kiến trúc hiện tại
- Làm nền cho scale-up / ML / real-time use cases

