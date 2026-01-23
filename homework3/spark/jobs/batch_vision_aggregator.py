"""
Spark Batch Job: Vision Event Aggregator
=========================================
Reads raw vision events from MinIO (S3) and creates hourly/daily aggregations.

This job demonstrates:
- Reading Parquet files from S3-compatible storage (MinIO)
- Data transformation and aggregation with Spark SQL
- Writing processed data back to S3 with partitioning

Usage:
    spark-submit --master spark://spark-master:7077 \
        --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        /opt/bitnami/spark/jobs/batch_vision_aggregator.py
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_spark_session():
    """Create Spark session with S3/MinIO configuration."""
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
    """Define schema for vision events Parquet files."""
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
    """Read raw vision events from MinIO."""
    logger.info(f"Reading raw events from: {input_path}")
    
    try:
        df = spark.read \
            .schema(get_vision_events_schema()) \
            .parquet(input_path)
        
        count = df.count()
        logger.info(f"Loaded {count} raw events")
        return df
    except Exception as e:
        logger.warning(f"No data found at {input_path}: {e}")
        # Return empty DataFrame with schema
        return spark.createDataFrame([], get_vision_events_schema())


def aggregate_hourly(df):
    """Create hourly aggregations."""
    logger.info("Creating hourly aggregations...")
    
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
    """Create daily aggregations."""
    logger.info("Creating daily aggregations...")
    
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
    """Write aggregated data to MinIO."""
    logger.info(f"Writing aggregations to: {output_path}")
    
    if df.count() == 0:
        logger.warning("No data to write, skipping...")
        return
    
    df.write \
        .mode("overwrite") \
        .partitionBy(*partition_cols) \
        .parquet(output_path)
    
    logger.info(f"Successfully wrote {df.count()} records")


def main():
    """Main entry point for the batch job."""
    logger.info("=" * 60)
    logger.info("Starting Vision Event Aggregator Job")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    # Create Spark session
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    try:
        # Read raw events
        raw_df = read_raw_events(
            spark, 
            "s3a://lake/raw/events/person_detection/"
        )
        
        if raw_df.count() > 0:
            # Cache for multiple aggregations
            raw_df.cache()
            
            # Hourly aggregation
            hourly_agg = aggregate_hourly(raw_df)
            write_aggregations(
                hourly_agg,
                "s3a://lake/processed/vision_hourly_stats/",
                ["camera_id"]
            )
            
            # Daily aggregation
            daily_agg = aggregate_daily(raw_df)
            write_aggregations(
                daily_agg,
                "s3a://lake/processed/vision_daily_stats/",
                ["camera_id"]
            )
            
            # Show sample results
            logger.info("\n📊 Sample Hourly Aggregation:")
            hourly_agg.show(5, truncate=False)
            
            logger.info("\n📊 Sample Daily Aggregation:")
            daily_agg.show(5, truncate=False)
            
            raw_df.unpersist()
        else:
            logger.info("No raw events found. Creating sample output...")
            
        logger.info("=" * 60)
        logger.info("✅ Vision Event Aggregator Job Completed Successfully")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Job failed: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
