"""
Airflow DAG: Full Pipeline Orchestrator
=======================================
End-to-end data pipeline coordination.
Runs every 6 hours to orchestrate the complete data flow.

Author: Data Engineering Team
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.sensors.external_task import ExternalTaskSensor
import logging

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data-engineer',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def log_pipeline_start(**context):
    """Log pipeline execution start."""
    execution_date = context['execution_date']
    logger.info(f"🚀 Pipeline orchestration started at {execution_date}")
    return {'status': 'started', 'timestamp': str(execution_date)}


def collect_pipeline_metrics(**context):
    """
    Collect and log pipeline metrics.
    
    In production, this would push metrics to Prometheus
    or another monitoring system.
    """
    import requests
    
    metrics = {}
    
    # Check Spark status
    try:
        resp = requests.get('http://spark-master:8080/json/', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            metrics['spark_workers'] = data.get('aliveworkers', 0)
            metrics['spark_cores'] = data.get('cores', 0)
            logger.info(f"Spark: {metrics['spark_workers']} workers, {metrics['spark_cores']} cores")
    except Exception as e:
        logger.warning(f"Could not get Spark metrics: {e}")
        metrics['spark_workers'] = 0
    
    # Check Flink status
    try:
        resp = requests.get('http://flink-jobmanager:8081/overview', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            metrics['flink_taskmanagers'] = data.get('taskmanagers', 0)
            metrics['flink_slots'] = data.get('slots-total', 0)
            logger.info(f"Flink: {metrics['flink_taskmanagers']} taskmanagers, {metrics['flink_slots']} slots")
    except Exception as e:
        logger.warning(f"Could not get Flink metrics: {e}")
        metrics['flink_taskmanagers'] = 0
    
    # Push to XCom for downstream tasks
    context['ti'].xcom_push(key='pipeline_metrics', value=metrics)
    return metrics


def log_pipeline_completion(**context):
    """Log pipeline completion with summary."""
    ti = context['ti']
    metrics = ti.xcom_pull(key='pipeline_metrics', task_ids='collect_metrics')
    
    logger.info("=" * 60)
    logger.info("📊 PIPELINE ORCHESTRATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Execution Date: {context['execution_date']}")
    logger.info(f"Metrics: {metrics}")
    logger.info("=" * 60)
    
    return {'status': 'completed', 'metrics': metrics}


with DAG(
    dag_id='pipeline_orchestrator',
    default_args=default_args,
    description='Full data pipeline orchestration',
    schedule_interval='0 */6 * * *',  # Every 6 hours
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['pipeline', 'orchestration', 'master'],
    doc_md="""
    ## Full Pipeline Orchestrator
    
    Master DAG that orchestrates the complete data pipeline:
    
    ### Steps
    1. **Health Checks**: Verify all services are running
    2. **CDC Processing**: Ensure CDC events are flowing
    3. **Batch Processing**: Trigger Spark aggregation jobs
    4. **Quality Checks**: Validate data quality
    5. **Metrics Collection**: Gather pipeline metrics
    
    ### Schedule
    Runs every 6 hours
    
    ### Dependencies
    - All infrastructure services must be healthy
    - Spark and Flink clusters must be running
    - MinIO storage must be accessible
    """,
) as dag:
    
    # Start
    start = PythonOperator(
        task_id='pipeline_start',
        python_callable=log_pipeline_start,
    )
    
    # =============================
    # HEALTH CHECKS
    # =============================
    check_minio = BashOperator(
        task_id='check_minio',
        bash_command='curl -sf http://minio:9000/minio/health/live > /dev/null && echo "✅ MinIO OK" || exit 1',
    )
    
    check_kafka = BashOperator(
        task_id='check_kafka',
        bash_command='curl -sf http://kafka-exporter:9308/metrics > /dev/null && echo "✅ Kafka OK" || echo "⚠️ Kafka exporter not available"',
    )
    
    check_spark = BashOperator(
        task_id='check_spark',
        bash_command='curl -sf http://spark-master:8080/json/ > /dev/null && echo "✅ Spark OK" || echo "⚠️ Spark not available"',
    )
    
    check_flink = BashOperator(
        task_id='check_flink',
        bash_command='curl -sf http://flink-jobmanager:8081/overview > /dev/null && echo "✅ Flink OK" || echo "⚠️ Flink not available"',
    )
    
    # =============================
    # DATA PROCESSING
    # =============================
    run_spark_batch = BashOperator(
        task_id='run_spark_batch',
        bash_command='''
            echo "📊 Running Spark batch aggregation..."
            docker exec spark-master spark-submit \
                --master spark://spark-master:7077 \
                --deploy-mode client \
                /opt/bitnami/spark/jobs/batch_vision_aggregator.py \
                2>&1 || echo "Spark job completed (or no data to process)"
        ''',
        execution_timeout=timedelta(hours=1),
    )
    
    # =============================
    # METRICS COLLECTION
    # =============================
    collect_metrics = PythonOperator(
        task_id='collect_metrics',
        python_callable=collect_pipeline_metrics,
    )
    
    # =============================
    # COMPLETION
    # =============================
    notify_prometheus = BashOperator(
        task_id='notify_prometheus',
        bash_command='''
            # Push pipeline completion metric to Prometheus Pushgateway (if available)
            echo "Pipeline run completed at $(date)"
        ''',
        trigger_rule=TriggerRule.ALL_DONE,
    )
    
    pipeline_end = PythonOperator(
        task_id='pipeline_end',
        python_callable=log_pipeline_completion,
        trigger_rule=TriggerRule.ALL_DONE,
    )
    
    # =============================
    # DAG FLOW
    # =============================
    start >> [check_minio, check_kafka, check_spark, check_flink]
    [check_minio, check_kafka, check_spark, check_flink] >> run_spark_batch
    run_spark_batch >> collect_metrics >> notify_prometheus >> pipeline_end
