"""
Flink SQL Job: Vision Analytics
================================
Real-time analytics using Flink SQL API.

This job demonstrates:
- Flink Table/SQL API for stream processing
- Windowed aggregations using SQL
- Real-time statistics computation

Requirements:
    pip install apache-flink==1.18.0

Usage:
    flink run -py /opt/flink/jobs/flink_sql_analytics.py
"""
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_sql_demo():
    """Run SQL analytics demo (without Flink cluster)."""
    logger.info("=" * 60)
    logger.info("Flink SQL Analytics Demo")
    logger.info("=" * 60)
    
    # Sample SQL queries that would run on Flink
    sql_queries = {
        "Create Vision Events Table": """
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
        
        "Tumbling Window Aggregation": """
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
        
        "Alert Detection": """
            SELECT 
                camera_id,
                ts_start,
                person_count,
                'HIGH_PERSON_COUNT' as alert_type
            FROM vision_events
            WHERE person_count > 3
        """,
        
        "CDC Events Processing": """
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
        # Clean and display SQL
        clean_sql = "\n".join(line.strip() for line in sql.strip().split("\n"))
        for line in clean_sql.split("\n"):
            logger.info(f"   {line}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ SQL Analytics Demo Complete")
    logger.info("These queries would run on a Flink cluster with Table API")
    logger.info("=" * 60)


def run_with_flink_sql():
    """Run with actual Flink SQL API."""
    try:
        from pyflink.table import EnvironmentSettings, TableEnvironment
    except ImportError:
        logger.error("PyFlink not installed. Running demo mode.")
        run_sql_demo()
        return
    
    logger.info("Creating Flink Table Environment...")
    
    # Create streaming table environment
    settings = EnvironmentSettings.new_instance() \
        .in_streaming_mode() \
        .build()
    
    t_env = TableEnvironment.create(settings)
    
    # Set parallelism
    t_env.get_config().set("parallelism.default", "2")
    
    # Create source table
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
    
    # Windowed aggregation query
    result = t_env.sql_query("""
        SELECT 
            camera_id,
            TUMBLE_START(event_time, INTERVAL '1' MINUTE) as window_start,
            COUNT(*) as event_count,
            AVG(person_count) as avg_persons
        FROM vision_source
        GROUP BY camera_id, TUMBLE(event_time, INTERVAL '1' MINUTE)
    """)
    
    # Print results
    result.execute().print()


def main():
    """Main entry point."""
    use_flink = os.getenv("USE_FLINK", "false").lower() == "true"
    
    if use_flink:
        run_with_flink_sql()
    else:
        run_sql_demo()


if __name__ == "__main__":
    main()
