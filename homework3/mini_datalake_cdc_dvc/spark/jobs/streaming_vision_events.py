"""
Job Spark Streaming: Xử lý Sự kiện Thị giác Thời gian thực
======================================================
Xử lý các sự kiện thị giác từ RabbitMQ/Kafka theo thời gian thực.

Job này minh họa:
- Xử lý sự kiện thời gian thực với các phép tổng hợp theo cửa sổ (windowed aggregations)
- Tạo cảnh báo dựa trên các ngưỡng định sẵn
- Ghi kết quả luồng ra console và (tùy chọn) vào kho lưu trữ

Cách dùng:
    spark-submit --master spark://spark-master:7077 \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
        /opt/bitnami/spark/jobs/streaming_vision_events.py
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
import logging
import os

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cấu hình tham số
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
VISION_TOPIC = os.getenv("VISION_TOPIC", "vision.events")
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD", "3"))  # Cảnh báo nếu > 3 người
WINDOW_DURATION = os.getenv("WINDOW_DURATION", "1 minute")
SLIDE_DURATION = os.getenv("SLIDE_DURATION", "30 seconds")


def create_spark_session():
    """Tạo session Spark cho xử lý luồng (streaming)."""
    return SparkSession.builder \
        .appName("VisionEventStreamProcessor") \
        .config("spark.sql.shuffle.partitions", "2") \
        .getOrCreate()


def get_vision_event_schema():
    """Schema cho các thông điệp JSON sự kiện thị giác."""
    return StructType([
        StructField("event_id", StringType(), True),
        StructField("camera_id", StringType(), True),
        StructField("ts_start", StringType(), True),  # Định dạng chuỗi ISO
        StructField("person_count", IntegerType(), True),
        StructField("conf_avg", DoubleType(), True),
        StructField("event_type", StringType(), True)
    ])


def read_vision_stream(spark):
    """Đọc dữ liệu sự kiện thị giác từ Kafka."""
    logger.info(f"Đang kết nối tới Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"Topic: {VISION_TOPIC}")
    
    return spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", VISION_TOPIC) \
        .option("startingOffsets", "latest") \
        .load()


def parse_vision_events(kafka_df):
    """Phân tích JSON sự kiện thị giác từ các thông điệp Kafka."""
    schema = get_vision_event_schema()
    
    return kafka_df \
        .selectExpr("CAST(value AS STRING) as json_str", "timestamp as kafka_timestamp") \
        .select(
            F.from_json("json_str", schema).alias("event"),
            "kafka_timestamp"
        ) \
        .select(
            "event.event_id",
            "event.camera_id",
            F.to_timestamp("event.ts_start").alias("event_time"),
            "event.person_count",
            "event.conf_avg",
            "event.event_type",
            "kafka_timestamp"
        ) \
        .withWatermark("event_time", "2 minutes")


def create_windowed_aggregations(df):
    """Tạo các phép tổng hợp theo cửa sổ trượt (sliding window)."""
    return df \
        .groupBy(
            F.window("event_time", WINDOW_DURATION, SLIDE_DURATION),
            "camera_id"
        ) \
        .agg(
            F.count("*").alias("event_count"),
            F.sum("person_count").alias("total_persons"),
            F.avg("person_count").alias("avg_persons"),
            F.max("person_count").alias("max_persons"),
            F.avg("conf_avg").alias("avg_confidence")
        ) \
        .select(
            "camera_id",
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "event_count",
            "total_persons",
            "avg_persons",
            "max_persons",
            "avg_confidence"
        )


def detect_alerts(df):
    """Phát hiện cảnh báo khi số lượng người vượt ngưỡng."""
    return df \
        .filter(F.col("max_persons") > ALERT_THRESHOLD) \
        .withColumn("alert_type", F.lit("HIGH_PERSON_COUNT")) \
        .withColumn("alert_message", 
            F.concat(
                F.lit("⚠️ Camera "),
                F.col("camera_id"),
                F.lit(": Phát hiện "),
                F.col("max_persons").cast("string"),
                F.lit(" người (ngưỡng: "),
                F.lit(str(ALERT_THRESHOLD)),
                F.lit(")")
            )
        ) \
        .withColumn("alert_time", F.current_timestamp())


def main():
    """Điểm khởi đầu chính cho xử lý luồng sự kiện thị giác."""
    logger.info("=" * 60)
    logger.info("Đang bắt đầu Vision Event Stream Processor")
    logger.info(f"Ngưỡng cảnh báo: {ALERT_THRESHOLD} người")
    logger.info(f"Cửa sổ: {WINDOW_DURATION}, Trượt: {SLIDE_DURATION}")
    logger.info("=" * 60)
    
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    # Đọc từ Kafka
    kafka_df = read_vision_stream(spark)
    
    # Phân tích sự kiện
    events_df = parse_vision_events(kafka_df)
    
    # Tạo tổng hợp theo cửa sổ
    windowed_df = create_windowed_aggregations(events_df)
    
    # Phát hiện cảnh báo
    alerts_df = detect_alerts(windowed_df)
    
    # Xuất số liệu thống kê ra console
    stats_query = windowed_df.writeStream \
        .format("console") \
        .outputMode("update") \
        .option("truncate", "false") \
        .trigger(processingTime="30 seconds") \
        .queryName("windowed_stats") \
        .start()
    
    # Xuất các cảnh báo ra console
    alerts_query = alerts_df.writeStream \
        .format("console") \
        .outputMode("update") \
        .option("truncate", "false") \
        .trigger(processingTime="10 seconds") \
        .queryName("alerts") \
        .start()
    
    logger.info("✅ Luồng xư lý sự kiện thị giác đã bắt đầu!")
    logger.info("   Đang chờ sự kiện...")
    
    # Chờ cho đến khi bất kỳ query nào dừng lại
    spark.streams.awaitAnyTermination()
    
    spark.stop()


if __name__ == "__main__":
    main()
