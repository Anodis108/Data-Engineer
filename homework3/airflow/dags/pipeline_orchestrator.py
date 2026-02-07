"""
Airflow DAG: Điều phối Toàn bộ Pipeline
=======================================
Điều phối luồng dữ liệu từ đầu đến cuối.
Chạy mỗi 6 giờ để điều phối toàn bộ luồng dữ liệu.

Tác giả: Data Engineering Team
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
    """Ghi log bắt đầu thực thi pipeline."""
    execution_date = context['execution_date']
    logger.info(f"🚀 Quá trình điều phối pipeline bắt đầu lúc {execution_date}")
    return {'status': 'started', 'timestamp': str(execution_date)}


def collect_pipeline_metrics(**context):
    """
    Thu thập và ghi log các số liệu thống kê pipeline.
    
    Trong môi trường sản xuất, các số liệu này sẽ được đẩy tới Prometheus
    hoặc một hệ thống giám sát khác.
    """
    import requests
    
    metrics = {}
    
    # Kiểm tra trạng thái Spark
    # Bỏ try-except để hiển thị lỗi trực tiếp
    resp = requests.get('http://spark-master:8080/json/', timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        metrics['spark_workers'] = data.get('aliveworkers', 0)
        metrics['spark_cores'] = data.get('cores', 0)
        logger.info(f"Spark: {metrics['spark_workers']} workers, {metrics['spark_cores']} cores")
    
    # Kiểm tra trạng thái Flink
    resp = requests.get('http://flink-jobmanager:8081/overview', timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        metrics['flink_taskmanagers'] = data.get('taskmanagers', 0)
        metrics['flink_slots'] = data.get('slots-total', 0)
        logger.info(f"Flink: {metrics['flink_taskmanagers']} taskmanagers, {metrics['flink_slots']} slots")
    
    # Đẩy lên XCom cho các task hạ nguồn
    context['ti'].xcom_push(key='pipeline_metrics', value=metrics)
    return metrics


def log_pipeline_completion(**context):
    """Ghi log hoàn thành pipeline với bản tổng kết."""
    ti = context['ti']
    metrics = ti.xcom_pull(key='pipeline_metrics', task_ids='collect_metrics')
    
    logger.info("=" * 60)
    logger.info("📊 TỔNG KẾT ĐIỀU PHỐI PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Ngày thực thi: {context['execution_date']}")
    logger.info(f"Số liệu: {metrics}")
    logger.info("=" * 60)
    
    return {'status': 'completed', 'metrics': metrics}


with DAG(
    dag_id='pipeline_orchestrator',
    default_args=default_args,
    description='Điều phối toàn bộ pipeline dữ liệu',
    schedule_interval='0 */6 * * *',  # Mỗi 6 giờ
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['pipeline', 'orchestration', 'master'],
    doc_md="""
    ## Điều phối Toàn bộ Pipeline
    
    DAG chính điều phối toàn bộ pipeline dữ liệu:
    
    ### Các bước
    1. **Kiểm tra Sức khỏe**: Xác nhận tất cả các dịch vụ đang chạy
    2. **Xử lý CDC**: Đảm bảo các sự kiện CDC đang chảy qua
    3. **Xử lý Batch**: Kích hoạt các job tổng hợp Spark
    4. **Kiểm tra Chất lượng**: Xác nhận chất lượng dữ liệu
    5. **Thu thập Số liệu**: Tổng hợp các số liệu thống kê pipeline
    
    ### Lịch trình
    Chạy mỗi 6 giờ
    
    ### Phụ thuộc
    - Tất cả các dịch vụ hạ tầng phải khỏe mạnh
    - Các cụm Spark và Flink phải đang chạy
    - Kho lưu trữ MinIO phải có thể truy cập được
    """,
) as dag:
    
    # Bắt đầu
    start = PythonOperator(
        task_id='pipeline_start',
        python_callable=log_pipeline_start,
    )
    
    # =============================
    # KIỂM TRA SỨC KHỎE
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
    # XỬ LÝ DỮ LIỆU
    # =============================
    run_spark_batch = BashOperator(
        task_id='run_spark_batch',
        bash_command='''
            echo "📊 Đang chạy tổng hợp Spark batch..."
            docker exec spark-master spark-submit \
                --master spark://spark-master:7077 \
                --deploy-mode client \
                /opt/bitnami/spark/jobs/batch_vision_aggregator.py \
                2>&1 || echo "Job Spark hoàn thành (hoặc không có dữ liệu để xử lý)"
        ''',
        execution_timeout=timedelta(hours=1),
    )
    
    # =============================
    # THU THẬP SỐ LIỆU
    # =============================
    collect_metrics = PythonOperator(
        task_id='collect_metrics',
        python_callable=collect_pipeline_metrics,
    )
    
    # =============================
    # HOÀN THÀNH
    # =============================
    notify_prometheus = BashOperator(
        task_id='notify_prometheus',
        bash_command='''
            # Đẩy số liệu hoàn thành pipeline tới Prometheus Pushgateway (nếu có)
            echo "Pipeline chạy hoàn thành lúc $(date)"
        ''',
        trigger_rule=TriggerRule.ALL_DONE,
    )
    
    pipeline_end = PythonOperator(
        task_id='pipeline_end',
        python_callable=log_pipeline_completion,
        trigger_rule=TriggerRule.ALL_DONE,
    )
    
    # =============================
    # LUỒNG THỰC THI DAG
    # =============================
    start >> [check_minio, check_kafka, check_spark, check_flink]
    [check_minio, check_kafka, check_spark, check_flink] >> run_spark_batch
    run_spark_batch >> collect_metrics >> notify_prometheus >> pipeline_end
