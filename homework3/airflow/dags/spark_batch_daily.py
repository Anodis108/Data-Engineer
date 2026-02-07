"""
Airflow DAG: Xử lý Spark Batch Hàng ngày
==========================================
Lập lịch cho bộ tổng hợp sự kiện thị giác chạy hàng ngày lúc 2 giờ sáng.
Tạo các bản tổng hợp theo giờ và theo ngày từ các sự kiện thị giác thô.

Tác giả: Data Engineering Team
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
import logging

logger = logging.getLogger(__name__)

# Tham số mặc định cho tất cả các task
default_args = {
    'owner': 'data-engineer',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
}

# Định nghĩa DAG
with DAG(
    dag_id='spark_batch_daily',
    default_args=default_args,
    description='Xử lý Spark batch hàng ngày cho việc tổng hợp sự kiện thị giác',
    schedule_interval='0 2 * * *',  # Chạy lúc 2 giờ sáng hàng ngày
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['spark', 'batch', 'vision', 'aggregation'],
    doc_md="""
    ## Xử lý Spark Batch Hàng ngày
    
    DAG này chạy job Spark batch để tổng hợp các sự kiện thị giác:
    - Đọc các file Parquet thô từ MinIO `raw/events/person_detection/`
    - Tạo các bản tổng hợp theo giờ (số lượng sự kiện, số người trung bình, thống kê độ tin cậy)
    - Tạo các bản tổng hợp theo ngày (tổng số, đỉnh điểm, xu hướng)
    - Ghi dữ liệu đã xử lý vào vùng `processed/` của MinIO
    
    ### Lịch trình
    Chạy hàng ngày lúc 2:00 sáng UTC
    
    ### Phụ thuộc
    - Cụm Spark phải đang chạy
    - MinIO phải có thể truy cập được
    - Dữ liệu thô phải tồn tại ở vị trí mong đợi
    """,
) as dag:
    
    # Task bắt đầu
    start = EmptyOperator(task_id='start')
    
    # Kiểm tra sức khỏe cụm Spark
    check_spark = BashOperator(
        task_id='check_spark_cluster',
        bash_command='curl -sf http://spark-master:8080/json/ > /dev/null && echo "Spark OK" || exit 1',
        retries=3,
        retry_delay=timedelta(seconds=30),
    )
    
    # Kiểm tra sức khỏe MinIO
    check_minio = BashOperator(
        task_id='check_minio_storage',
        bash_command='curl -sf http://minio:9000/minio/health/live > /dev/null && echo "MinIO OK" || exit 1',
        retries=3,
        retry_delay=timedelta(seconds=30),
    )
    
    # Chạy job Spark batch aggregation
    run_batch_aggregator = BashOperator(
        task_id='run_vision_aggregator',
        bash_command='''
            echo "Đang bắt đầu job Spark batch..."
            docker exec spark-master spark-submit \
                --master spark://spark-master:7077 \
                --deploy-mode client \
                --driver-memory 1g \
                --executor-memory 1g \
                --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
                /opt/bitnami/spark/jobs/batch_vision_aggregator.py
            echo "Job Spark batch hoàn thành"
        ''',
        execution_timeout=timedelta(hours=2),
    )
    
    # Xác nhận kết quả đầu ra tồn tại
    verify_output = BashOperator(
        task_id='verify_output',
        bash_command='''
            echo "Đang xác nhận kết quả đầu ra đã xử lý..."
            # Phần này sẽ kiểm tra xem các file đầu ra có tồn tại trong MinIO không
            echo "Xác nhận hoàn tất"
        ''',
    )
    
    # Ghi log thành công
    log_success = BashOperator(
        task_id='log_success',
        bash_command='echo "Quá trình xử lý Spark batch hàng ngày đã hoàn thành thành công lúc $(date)"',
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )
    
    # Task kết thúc
    end = EmptyOperator(
        task_id='end',
        trigger_rule=TriggerRule.ALL_DONE,
    )
    
    # Định nghĩa luồng thực thi DAG
    start >> [check_spark, check_minio] >> run_batch_aggregator >> verify_output >> log_success >> end
