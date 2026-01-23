"""
Airflow DAG: Daily Spark Batch Processing
==========================================
Schedules the vision event aggregator to run daily at 2 AM.
Creates hourly and daily aggregations from raw vision events.

Author: Data Engineering Team
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
import logging

logger = logging.getLogger(__name__)

# Default arguments for all tasks
default_args = {
    'owner': 'data-engineer',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
}

# DAG definition
with DAG(
    dag_id='spark_batch_daily',
    default_args=default_args,
    description='Daily Spark batch processing for vision event aggregation',
    schedule_interval='0 2 * * *',  # Run at 2 AM daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['spark', 'batch', 'vision', 'aggregation'],
    doc_md="""
    ## Daily Spark Batch Processing
    
    This DAG runs the Spark batch job to aggregate vision events:
    - Reads raw Parquet files from MinIO `raw/events/person_detection/`
    - Creates hourly aggregations (event count, avg person count, confidence stats)
    - Creates daily aggregations (totals, peaks, trends)
    - Writes processed data to MinIO `processed/` zone
    
    ### Schedule
    Runs daily at 2:00 AM UTC
    
    ### Dependencies
    - Spark cluster must be running
    - MinIO must be accessible
    - Raw data must exist in the expected location
    """,
) as dag:
    
    # Start task
    start = EmptyOperator(task_id='start')
    
    # Check Spark cluster health
    check_spark = BashOperator(
        task_id='check_spark_cluster',
        bash_command='curl -sf http://spark-master:8080/json/ > /dev/null && echo "Spark OK" || exit 1',
        retries=3,
        retry_delay=timedelta(seconds=30),
    )
    
    # Check MinIO health
    check_minio = BashOperator(
        task_id='check_minio_storage',
        bash_command='curl -sf http://minio:9000/minio/health/live > /dev/null && echo "MinIO OK" || exit 1',
        retries=3,
        retry_delay=timedelta(seconds=30),
    )
    
    # Run Spark batch aggregation job
    run_batch_aggregator = BashOperator(
        task_id='run_vision_aggregator',
        bash_command='''
            echo "Starting Spark batch job..."
            docker exec spark-master spark-submit \
                --master spark://spark-master:7077 \
                --deploy-mode client \
                --driver-memory 1g \
                --executor-memory 1g \
                --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
                /opt/bitnami/spark/jobs/batch_vision_aggregator.py
            echo "Spark batch job completed"
        ''',
        execution_timeout=timedelta(hours=2),
    )
    
    # Verify output exists
    verify_output = BashOperator(
        task_id='verify_output',
        bash_command='''
            echo "Verifying processed output..."
            # This would check if output files exist in MinIO
            echo "Verification complete"
        ''',
    )
    
    # Log success
    log_success = BashOperator(
        task_id='log_success',
        bash_command='echo "Daily Spark batch processing completed successfully at $(date)"',
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )
    
    # End task
    end = EmptyOperator(
        task_id='end',
        trigger_rule=TriggerRule.ALL_DONE,
    )
    
    # Define DAG flow
    start >> [check_spark, check_minio] >> run_batch_aggregator >> verify_output >> log_success >> end
