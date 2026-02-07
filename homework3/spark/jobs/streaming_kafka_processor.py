"""
Job Spark Structured Streaming: Xử lý Kafka CDC
====================================================
Tiêu thụ các sự kiện CDC từ Kafka và ghi dữ liệu đã xử lý vào MinIO.

Job này minh họa:
- Xử lý luồng thời gian thực từ Kafka bằng Structured Streaming
- Phân tích định dạng Debezium CDC
- Ghi kết quả luồng vào S3/MinIO theo từng micro-batch

Cách dùng:
    spark-submit --master spark://spark-master:7077 \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
                   org.apache.hadoop:hadoop-aws:3.3.4,\
                   com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        /opt/bitnami/spark/jobs/streaming_kafka_processor.py
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType
import logging
import os

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cấu hình tham số
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPICS = os.getenv("KAFKA_TOPICS", "pgserver1.public.customers")
CHECKPOINT_LOCATION = os.getenv("CHECKPOINT_LOCATION", "/tmp/spark-checkpoint/cdc")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "s3a://lake/processed/cdc_events/")


def create_spark_session():
    """Tạo session Spark với cấu hình Kafka và S3."""
    return SparkSession.builder \
        .appName("KafkaCDCProcessor") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.sql.shuffle.partitions", "2") \
        .getOrCreate()


def read_kafka_stream(spark):
    """Tạo nguồn luồng dữ liệu từ Kafka."""
    logger.info(f"Đang kết nối tới Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"Đang đăng ký các topic: {KAFKA_TOPICS}")
    
    return spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPICS) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()


def parse_cdc_events(kafka_df):
    """Phân tích các sự kiện CDC từ thông điệp Kafka."""
    # Trích xuất giá trị dưới dạng string và phân tích JSON
    parsed_df = kafka_df \
        .selectExpr(
            "CAST(key AS STRING) as kafka_key",
            "CAST(value AS STRING) as json_value",
            "topic",
            "partition",
            "offset",
            "timestamp as kafka_timestamp"
        ) \
        .select(
            "kafka_key",
            "topic",
            "partition", 
            "offset",
            "kafka_timestamp",
            # Phân tích payload Debezium CDC
            F.get_json_object("json_value", "$.payload.op").alias("operation"),
            F.get_json_object("json_value", "$.payload.before").alias("before_data"),
            F.get_json_object("json_value", "$.payload.after").alias("after_data"),
            F.get_json_object("json_value", "$.payload.source.table").alias("source_table"),
            F.get_json_object("json_value", "$.payload.source.db").alias("source_db"),
            F.get_json_object("json_value", "$.payload.ts_ms").alias("event_ts_ms")
        ) \
        .withColumn("processing_time", F.current_timestamp()) \
        .withColumn("operation_name", 
            F.when(F.col("operation") == "c", "INSERT")
            .when(F.col("operation") == "u", "UPDATE")
            .when(F.col("operation") == "d", "DELETE")
            .when(F.col("operation") == "r", "READ")
            .otherwise("UNKNOWN")
        ) \
        .withColumn("event_date", F.to_date("kafka_timestamp"))
    
    return parsed_df


def write_to_console(df, output_mode="append"):
    """Ghi luồng dữ liệu ra console để theo dõi (debug)."""
    query = df.writeStream \
        .format("console") \
        .outputMode(output_mode) \
        .option("truncate", "false") \
        .trigger(processingTime="10 seconds") \
        .start()
    
    return query


def write_to_minio(df):
    """Ghi luồng dữ liệu vào MinIO dưới dạng file Parquet."""
    logger.info(f"Đang ghi luồng dữ liệu vào: {OUTPUT_PATH}")
    
    query = df.writeStream \
        .format("parquet") \
        .outputMode("append") \
        .option("path", OUTPUT_PATH) \
        .option("checkpointLocation", CHECKPOINT_LOCATION) \
        .partitionBy("event_date", "operation_name") \
        .trigger(processingTime="30 seconds") \
        .start()
    
    return query


def main():
    """Điểm khởi đầu chính cho job streaming."""
    logger.info("=" * 60)
    logger.info("Đang bắt đầu Kafka CDC Processor (Spark Streaming)")
    logger.info("=" * 60)
    
    # Tạo session Spark
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    # Đọc từ Kafka
    kafka_df = read_kafka_stream(spark)
    
    # Phân tích các sự kiện CDC
    parsed_df = parse_cdc_events(kafka_df)
    
    # Chọn các cột để xuất dữ liệu
    output_df = parsed_df.select(
        "topic",
        "partition",
        "offset",
        "kafka_timestamp",
        "operation_name",
        "source_table",
        "source_db",
        "before_data",
        "after_data",
        "processing_time",
        "event_date"
    )
    
    # Ghi ra console để giám sát
    console_query = write_to_console(output_df)
    
    # Có thể ghi vào MinIO bằng cách bỏ chú thích:
    # minio_query = write_to_minio(output_df)
    
    logger.info("✅ Job streaming đã bắt đầu. Đang chờ dữ liệu...")
    logger.info(f"   Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"   Topics: {KAFKA_TOPICS}")
    
    # Chờ cho đến khi dừng job
    console_query.awaitTermination()
    
    spark.stop()


if __name__ == "__main__":
    main()
