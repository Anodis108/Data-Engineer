"""
Job Spark Batch: Tổng hợp Sự kiện Thị giác
=========================================
Đọc sự kiện thị giác thô từ MinIO (S3) và tạo các bản tổng hợp theo giờ/ngày.

Job này minh họa:
- Đọc file Parquet từ kho lưu trữ tương thích S3 (MinIO)
- Biến đổi và tổng hợp dữ liệu với Spark SQL
- Ghi dữ liệu đã xử lý trở lại S3 với phân vùng (partitioning)

Cách dùng:
    spark-submit --master spark://spark-master:7077 \
        --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        /opt/bitnami/spark/jobs/batch_vision_aggregator.py
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
import logging
from datetime import datetime

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_spark_session():
    """Tạo session Spark với cấu hình S3/MinIO."""
    return SparkSession.builder \
        .appName("VisionEventAggregator") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()


def get_vision_events_schema():
    """Định nghĩa schema cho các file Parquet sự kiện thị giác."""
    return StructType([
        StructField("event_id", StringType(), True),
        StructField("camera_id", StringType(), True),
        StructField("ts_start", TimestampType(), True),
        StructField("ts_end", TimestampType(), True),
        StructField("person_count", IntegerType(), True),
        StructField("conf_avg", DoubleType(), True),
        StructField("conf_max", DoubleType(), True),
        StructField("frame_uri", StringType(), True),
        StructField("event_type", StringType(), True)
    ])


def read_raw_events(spark, input_path: str):
    """Đọc sự kiện thị giác thô từ MinIO."""
    logger.info(f"Đang đọc sự kiện thô từ: {input_path}")
    
    # Bỏ try-except để hiển thị lỗi trực tiếp
    df = spark.read \
        .schema(get_vision_events_schema()) \
        .parquet(input_path)
    
    count = df.count()
    logger.info(f"Đã tải {count} sự kiện thô")
    return df


def aggregate_hourly(df):
    """Tạo tổng hợp theo giờ."""
    logger.info("Đang tạo tổng hợp theo giờ...")
    
    return df \
        .withColumn("hour", F.date_trunc("hour", "ts_start")) \
        .groupBy("camera_id", "hour") \
        .agg(
            F.count("*").alias("event_count"),
            F.sum("person_count").alias("total_person_detections"),
            F.avg("person_count").alias("avg_person_count"),
            F.max("person_count").alias("max_person_count"),
            F.min("person_count").alias("min_person_count"),
            F.avg("conf_avg").alias("avg_confidence"),
            F.max("conf_max").alias("max_confidence"),
            F.countDistinct("event_type").alias("unique_event_types")
        ) \
        .withColumn("processed_at", F.current_timestamp())


def aggregate_daily(df):
    """Tạo tổng hợp theo ngày."""
    logger.info("Đang tạo tổng hợp theo ngày...")
    
    return df \
        .withColumn("date", F.to_date("ts_start")) \
        .groupBy("camera_id", "date") \
        .agg(
            F.count("*").alias("event_count"),
            F.sum("person_count").alias("total_person_detections"),
            F.avg("person_count").alias("avg_person_count"),
            F.max("person_count").alias("max_person_count"),
            F.first("ts_start").alias("first_event"),
            F.last("ts_start").alias("last_event"),
            F.avg("conf_avg").alias("avg_confidence")
        ) \
        .withColumn("processed_at", F.current_timestamp())


def write_aggregations(df, output_path: str, partition_cols: list):
    """Ghi dữ liệu tổng hợp vào MinIO."""
    logger.info(f"Đang ghi dữ liệu tổng hợp vào: {output_path}")
    
    if df.count() == 0:
        logger.warning("Không có dữ liệu để ghi, đang bỏ qua...")
        return
    
    df.write \
        .mode("overwrite") \
        .partitionBy(*partition_cols) \
        .parquet(output_path)
    
    logger.info(f"Đã ghi thành công {df.count()} bản ghi")


def main():
    """Điểm khởi đầu chính cho job batch."""
    logger.info("=" * 60)
    logger.info("Bắt đầu Job Tổng hợp Sự kiện Thị giác")
    logger.info(f"Thời điểm: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    # Tạo session Spark
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    # Đọc sự kiện thô
    raw_df = read_raw_events(
        spark, 
        "s3a://lake/raw/events/person_detection/"
    )
    
    if raw_df.count() > 0:
        # Cache để sử dụng cho nhiều lần tổng hợp
        raw_df.cache()
        
        # Tổng hợp theo giờ
        hourly_agg = aggregate_hourly(raw_df)
        write_aggregations(
            hourly_agg,
            "s3a://lake/processed/vision_hourly_stats/",
            ["camera_id"]
        )
        
        # Tổng hợp theo ngày
        daily_agg = aggregate_daily(raw_df)
        write_aggregations(
            daily_agg,
            "s3a://lake/processed/vision_daily_stats/",
            ["camera_id"]
        )
        
        # Hiển thị kết quả mẫu
        logger.info("\n📊 Mẫu Tổng hợp theo Giờ:")
        hourly_agg.show(5, truncate=False)
        
        logger.info("\n📊 Mẫu Tổng hợp theo Ngày:")
        daily_agg.show(5, truncate=False)
        
        raw_df.unpersist()
    else:
        logger.info("Không tìm thấy sự kiện thô.")
        
    logger.info("=" * 60)
    logger.info("✅ Hoàn thành Job Tổng hợp Sự kiện Thị giác thành công")
    logger.info("=" * 60)
    
    spark.stop()


if __name__ == "__main__":
    main()
