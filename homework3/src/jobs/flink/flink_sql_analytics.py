"""
Job Flink SQL: Phân tích Thị giác
================================
Phân tích theo thời gian thực sử dụng Flink SQL API.

Job này minh họa:
- Flink Table/SQL API cho xử lý luồng
- Tổng hợp theo cửa sổ (windowed aggregations) sử dụng SQL
- Tính toán số liệu thống kê thời gian thực

Yêu cầu:
    pip install apache-flink==1.18.0

Cách dùng:
    flink run -py /opt/flink/jobs/flink_sql_analytics.py
"""
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_sql_demo():
    """Chạy bản demo phân tích SQL (không cần cụm Flink)."""
    logger.info("=" * 60)
    logger.info("Demo Phân tích Flink SQL")
    logger.info("=" * 60)
    
    # Các câu lệnh SQL mẫu sẽ chạy trên Flink
    sql_queries = {
        "Tạo Bảng Sự kiện Thị giác": """
            CREATE TABLE vision_events (
                event_id STRING,
                camera_id STRING,
                ts_start TIMESTAMP(3),
                person_count INT,
                conf_avg DOUBLE,
                event_type STRING,
                WATERMARK FOR ts_start AS ts_start - INTERVAL '5' SECOND
            ) WITH (
                'connector' = 'kafka',
                'topic' = 'vision.events',
                'properties.bootstrap.servers' = 'kafka:29092',
                'properties.group.id' = 'flink-sql-consumer',
                'scan.startup.mode' = 'latest-offset',
                'format' = 'json'
            )
        """,
        
        "Tổng hợp Cửa sổ Tumbling": """
            SELECT 
                camera_id,
                TUMBLE_START(ts_start, INTERVAL '1' MINUTE) as window_start,
                TUMBLE_END(ts_start, INTERVAL '1' MINUTE) as window_end,
                COUNT(*) as event_count,
                SUM(person_count) as total_persons,
                AVG(person_count) as avg_persons,
                MAX(person_count) as max_persons
            FROM vision_events
            GROUP BY camera_id, TUMBLE(ts_start, INTERVAL '1' MINUTE)
        """,
        
        "Phát hiện Cảnh báo": """
            SELECT 
                camera_id,
                ts_start,
                person_count,
                'HIGH_PERSON_COUNT' as alert_type
            FROM vision_events
            WHERE person_count > 3
        """,
        
        "Xử lý Sự kiện CDC": """
            CREATE TABLE cdc_events (
                payload ROW<
                    op STRING,
                    before ROW<id INT, name STRING>,
                    after ROW<id INT, name STRING>,
                    source ROW<schema STRING, table STRING>
                >
            ) WITH (
                'connector' = 'kafka',
                'topic' = 'pgserver1.public.customers',
                'properties.bootstrap.servers' = 'kafka:29092',
                'format' = 'json'
            )
        """
    }
    
    for name, sql in sql_queries.items():
        logger.info(f"\n📋 {name}:")
        logger.info("-" * 40)
        # Làm sạch và hiển thị SQL
        clean_sql = "\n".join(line.strip() for line in sql.strip().split("\n"))
        for line in clean_sql.split("\n"):
            logger.info(f"   {line}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Hoàn thành Demo Phân tích SQL")
    logger.info("Các truy vấn này sẽ chạy trên cụm Flink với Table API")
    logger.info("=" * 60)


def run_with_flink_sql():
    """Chạy với Flink SQL API thực tế."""
    # Bỏ try-except để hiển thị lỗi import trực tiếp nếu thiếu thư viện
    from pyflink.table import EnvironmentSettings, TableEnvironment
    
    logger.info("Đang tạo Flink Table Environment...")
    
    # Tạo streaming table environment
    settings = EnvironmentSettings.new_instance() \
        .in_streaming_mode() \
        .build()
    
    t_env = TableEnvironment.create(settings)
    
    # Thiết lập mức độ song song
    t_env.get_config().set("parallelism.default", "2")
    
    # Tạo bảng nguồn
    t_env.execute_sql("""
        CREATE TABLE vision_source (
            event_id STRING,
            camera_id STRING,
            person_count INT,
            conf_avg DOUBLE,
            event_time TIMESTAMP(3),
            WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'vision.events',
            'properties.bootstrap.servers' = 'kafka:29092',
            'format' = 'json',
            'scan.startup.mode' = 'latest-offset'
        )
    """)
    
    # Truy vấn tổng hợp theo cửa sổ
    result = t_env.sql_query("""
        SELECT 
            camera_id,
            TUMBLE_START(event_time, INTERVAL '1' MINUTE) as window_start,
            COUNT(*) as event_count,
            AVG(person_count) as avg_persons
        FROM vision_source
        GROUP BY camera_id, TUMBLE(event_time, INTERVAL '1' MINUTE)
    """)
    
    # In kết quả
    result.execute().print()


def main():
    """Điểm khởi đầu chính."""
    use_flink = os.getenv("USE_FLINK", "false").lower() == "true"
    
    if use_flink:
        run_with_flink_sql()
    else:
        run_sql_demo()


if __name__ == "__main__":
    main()
