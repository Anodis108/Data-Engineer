"""
Spark Streaming Job: Real-time Vision Event Processor
======================================================
Processes vision events from RabbitMQ/Kafka in real-time.

This job demonstrates:
- Real-time event processing with windowed aggregations
- Alert generation based on thresholds
- Writing streaming results to console and optionally to storage

Usage:
    spark-submit --master spark://spark-master:7077 \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
        /opt/bitnami/spark/jobs/streaming_vision_events.py
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
VISION_TOPIC = os.getenv("VISION_TOPIC", "vision.events")
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD", "3"))  # Alert if > 3 persons
WINDOW_DURATION = os.getenv("WINDOW_DURATION", "1 minute")
SLIDE_DURATION = os.getenv("SLIDE_DURATION", "30 seconds")


def create_spark_session():
    """Create Spark session for streaming."""
    return SparkSession.builder \
        .appName("VisionEventStreamProcessor") \
        .config("spark.sql.shuffle.partitions", "2") \
        .getOrCreate()


def get_vision_event_schema():
    """Schema for vision event JSON messages."""
    return StructType([
        StructField("event_id", StringType(), True),
        StructField("camera_id", StringType(), True),
        StructField("ts_start", StringType(), True),  # ISO format string
        StructField("person_count", IntegerType(), True),
        StructField("conf_avg", DoubleType(), True),
        StructField("event_type", StringType(), True)
    ])


def read_vision_stream(spark):
    """Read vision events from Kafka."""
    logger.info(f"Connecting to Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"Topic: {VISION_TOPIC}")
    
    return spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", VISION_TOPIC) \
        .option("startingOffsets", "latest") \
        .load()


def parse_vision_events(kafka_df):
    """Parse vision event JSON from Kafka messages."""
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
    """Create sliding window aggregations."""
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
    """Detect alerts when person count exceeds threshold."""
    return df \
        .filter(F.col("max_persons") > ALERT_THRESHOLD) \
        .withColumn("alert_type", F.lit("HIGH_PERSON_COUNT")) \
        .withColumn("alert_message", 
            F.concat(
                F.lit("⚠️ Camera "),
                F.col("camera_id"),
                F.lit(": Detected "),
                F.col("max_persons").cast("string"),
                F.lit(" persons (threshold: "),
                F.lit(str(ALERT_THRESHOLD)),
                F.lit(")")
            )
        ) \
        .withColumn("alert_time", F.current_timestamp())


def main():
    """Main entry point for vision event streaming."""
    logger.info("=" * 60)
    logger.info("Starting Vision Event Stream Processor")
    logger.info(f"Alert threshold: {ALERT_THRESHOLD} persons")
    logger.info(f"Window: {WINDOW_DURATION}, Slide: {SLIDE_DURATION}")
    logger.info("=" * 60)
    
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    try:
        # Read from Kafka
        kafka_df = read_vision_stream(spark)
        
        # Parse events
        events_df = parse_vision_events(kafka_df)
        
        # Create windowed aggregations
        windowed_df = create_windowed_aggregations(events_df)
        
        # Detect alerts
        alerts_df = detect_alerts(windowed_df)
        
        # Output windowed stats to console
        stats_query = windowed_df.writeStream \
            .format("console") \
            .outputMode("update") \
            .option("truncate", "false") \
            .trigger(processingTime="30 seconds") \
            .queryName("windowed_stats") \
            .start()
        
        # Output alerts to console
        alerts_query = alerts_df.writeStream \
            .format("console") \
            .outputMode("update") \
            .option("truncate", "false") \
            .trigger(processingTime="10 seconds") \
            .queryName("alerts") \
            .start()
        
        logger.info("✅ Vision event streaming started!")
        logger.info("   Waiting for events...")
        
        # Wait for any query to terminate
        spark.streams.awaitAnyTermination()
        
    except Exception as e:
        logger.error(f"Streaming job failed: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
