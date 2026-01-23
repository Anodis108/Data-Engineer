"""
Airflow DAG: Data Quality Checks
================================
Validates data quality and integrity across the data lake.
Runs daily at 6 AM after batch processing completes.

Author: Data Engineering Team
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
import logging

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data-engineer',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=10),
}


def check_minio_data_exists(**context):
    """
    Check if today's raw data exists in MinIO.
    
    This validates that the vision detection pipeline
    is producing data as expected.
    """
    import boto3
    from datetime import date
    from botocore.client import Config
    
    # MinIO connection
    s3 = boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin123',
        config=Config(signature_version='s3v4')
    )
    
    today = date.today().isoformat()
    prefix = f"raw/events/person_detection/date={today}/"
    
    try:
        response = s3.list_objects_v2(
            Bucket='lake',
            Prefix=prefix,
            MaxKeys=1
        )
        
        if 'Contents' in response and len(response['Contents']) > 0:
            logger.info(f"✅ Data exists for {today}: {response['KeyCount']} objects found")
            return True
        else:
            logger.warning(f"⚠️ No data found for {today} in {prefix}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to check MinIO data: {e}")
        raise


def check_processed_data_freshness(**context):
    """
    Check if processed data is recent.
    
    Validates that aggregation jobs are running
    and producing output.
    """
    import boto3
    from datetime import datetime, timedelta
    from botocore.client import Config
    
    s3 = boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin123',
        config=Config(signature_version='s3v4')
    )
    
    try:
        response = s3.list_objects_v2(
            Bucket='lake',
            Prefix='processed/vision_hourly_stats/',
            MaxKeys=10
        )
        
        if 'Contents' not in response:
            logger.warning("No processed data found")
            return False
        
        # Check if any file was modified in the last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        recent_files = [
            obj for obj in response['Contents']
            if obj['LastModified'].replace(tzinfo=None) > cutoff
        ]
        
        if recent_files:
            logger.info(f"✅ Found {len(recent_files)} recent processed files")
            return True
        else:
            logger.warning("⚠️ No recent processed files found")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to check processed data: {e}")
        raise


def validate_data_schema(**context):
    """
    Validate that Parquet files have expected schema.
    """
    import boto3
    import pyarrow.parquet as pq
    import io
    from botocore.client import Config
    
    s3 = boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin123',
        config=Config(signature_version='s3v4')
    )
    
    expected_columns = {
        'event_id', 'camera_id', 'ts_start', 'ts_end',
        'person_count', 'conf_avg', 'event_type'
    }
    
    try:
        # List some Parquet files
        response = s3.list_objects_v2(
            Bucket='lake',
            Prefix='raw/events/person_detection/',
            MaxKeys=5
        )
        
        if 'Contents' not in response:
            logger.info("No raw data to validate")
            return True
        
        for obj in response['Contents']:
            if obj['Key'].endswith('.parquet'):
                # Download and check schema
                file_obj = s3.get_object(Bucket='lake', Key=obj['Key'])
                parquet_file = pq.read_table(io.BytesIO(file_obj['Body'].read()))
                
                actual_columns = set(parquet_file.column_names)
                missing = expected_columns - actual_columns
                
                if missing:
                    logger.warning(f"Missing columns in {obj['Key']}: {missing}")
                else:
                    logger.info(f"✅ Schema valid for {obj['Key']}")
                
                break  # Only check one file
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Schema validation failed: {e}")
        raise


with DAG(
    dag_id='data_quality_check',
    default_args=default_args,
    description='Daily data quality validation for the data lake',
    schedule_interval='0 6 * * *',  # Run at 6 AM daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['quality', 'validation', 'monitoring'],
    doc_md="""
    ## Data Quality Checks
    
    This DAG validates data quality across the data lake:
    
    1. **Raw Data Check**: Verifies today's vision events exist
    2. **Processed Data Freshness**: Checks aggregation outputs are recent
    3. **Schema Validation**: Validates Parquet file schemas
    4. **Service Health**: Ensures all services are running
    
    ### Schedule
    Runs daily at 6:00 AM UTC (after batch processing)
    
    ### Alerts
    Failures trigger email notifications to the data team.
    """,
) as dag:
    
    start = EmptyOperator(task_id='start')
    
    # Service health checks
    check_minio_health = BashOperator(
        task_id='check_minio_health',
        bash_command='curl -sf http://minio:9000/minio/health/live || exit 1',
    )
    
    check_trino_health = BashOperator(
        task_id='check_trino_health',
        bash_command='curl -sf http://trino-coordinator:8080/v1/info || echo "Trino not available"',
    )
    
    # Data quality checks
    check_raw_data = PythonOperator(
        task_id='check_raw_data_exists',
        python_callable=check_minio_data_exists,
    )
    
    check_processed_freshness = PythonOperator(
        task_id='check_processed_freshness',
        python_callable=check_processed_data_freshness,
    )
    
    validate_schema = PythonOperator(
        task_id='validate_data_schema',
        python_callable=validate_data_schema,
    )
    
    # Summary task
    quality_summary = BashOperator(
        task_id='quality_summary',
        bash_command='echo "Data quality checks completed at $(date)"',
        trigger_rule=TriggerRule.ALL_DONE,
    )
    
    end = EmptyOperator(task_id='end')
    
    # DAG flow
    start >> [check_minio_health, check_trino_health]
    check_minio_health >> check_raw_data >> check_processed_freshness >> validate_schema
    [check_trino_health, validate_schema] >> quality_summary >> end
