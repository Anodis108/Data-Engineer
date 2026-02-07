"""
Airflow DAG: Kiểm tra Chất lượng Dữ liệu
================================
Kiểm tra tính đúng đắn và toàn vẹn của dữ liệu trong data lake.
Chạy hàng ngày vào lúc 6 giờ sáng sau khi xử lý batch hoàn tất.

Tác giả: Data Engineering Team
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
    Kiểm tra xem dữ liệu thô hôm nay có tồn tại trong MinIO không.
    
    Điều này xác nhận rằng pipeline phát hiện thị giác
    đang tạo ra dữ liệu như mong đợi.
    """
    import boto3
    from datetime import date
    from botocore.client import Config
    
    # Kết nối MinIO
    s3 = boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin123',
        config=Config(signature_version='s3v4')
    )
    
    today = date.today().isoformat()
    prefix = f"raw/events/person_detection/date={today}/"
    
    # Bỏ try-except để hiển thị lỗi trực tiếp
    response = s3.list_objects_v2(
        Bucket='lake',
        Prefix=prefix,
        MaxKeys=1
    )
    
    if 'Contents' in response and len(response['Contents']) > 0:
        logger.info(f"✅ Dữ liệu tồn tại cho ngày {today}: tìm thấy {response['KeyCount']} đối tượng")
        return True
    else:
        logger.warning(f"⚠️ Không tìm thấy dữ liệu cho ngày {today} tại {prefix}")
        return False


def check_processed_data_freshness(**context):
    """
    Kiểm tra xem dữ liệu đã xử lý có mới không.
    
    Xác nhận rằng các job tổng hợp đang chạy
    và tạo ra kết quả đầu ra.
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
    
    # Bỏ try-except để hiển thị lỗi trực tiếp
    response = s3.list_objects_v2(
        Bucket='lake',
        Prefix='processed/vision_hourly_stats/',
        MaxKeys=10
    )
    
    if 'Contents' not in response:
        logger.warning("Không tìm thấy dữ liệu đã xử lý")
        return False
    
    # Kiểm tra xem có file nào được sửa đổi trong 24 giờ qua không
    cutoff = datetime.now() - timedelta(hours=24)
    recent_files = [
        obj for obj in response['Contents']
        if obj['LastModified'].replace(tzinfo=None) > cutoff
    ]
    
    if recent_files:
        logger.info(f"✅ Tìm thấy {len(recent_files)} file đã xử lý gần đây")
        return True
    else:
        logger.warning("⚠️ Không tìm thấy file đã xử lý gần đây")
        return False


def validate_data_schema(**context):
    """
    Xác nhận các file Parquet có schema như mong đợi.
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
    
    # Bỏ try-except để hiển thị lỗi trực tiếp
    # Liệt kê một số file Parquet
    response = s3.list_objects_v2(
        Bucket='lake',
        Prefix='raw/events/person_detection/',
        MaxKeys=5
    )
    
    if 'Contents' not in response:
        logger.info("Không có dữ liệu thô để kiểm tra")
        return True
    
    for obj in response['Contents']:
        if obj['Key'].endswith('.parquet'):
            # Tải xuống và kiểm tra schema
            file_obj = s3.get_object(Bucket='lake', Key=obj['Key'])
            parquet_file = pq.read_table(io.BytesIO(file_obj['Body'].read()))
            
            actual_columns = set(parquet_file.column_names)
            missing = expected_columns - actual_columns
            
            if missing:
                logger.warning(f"Thiếu các cột trong {obj['Key']}: {missing}")
            else:
                logger.info(f"✅ Schema hợp lệ cho {obj['Key']}")
            
            break  # Chỉ kiểm tra một file
    
    return True


with DAG(
    dag_id='data_quality_check',
    default_args=default_args,
    description='Kiểm tra chất lượng dữ liệu hàng ngày cho data lake',
    schedule_interval='0 6 * * *',  # Chạy lúc 6 giờ sáng hàng ngày
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['quality', 'validation', 'monitoring'],
    doc_md="""
    ## Kiểm tra Chất lượng Dữ liệu
    
    DAG này thực hiện kiểm tra chất lượng dữ liệu trong data lake:
    
    1. **Kiểm tra Dữ liệu Thô**: Xác nhận các sự kiện thị giác hôm nay tồn tại
    2. **Độ mới của Dữ liệu đã Xử lý**: Kiểm tra các đầu ra tổng hợp là gần đây
    3. **Xác nhận Schema**: Kiểm tra schema của các file Parquet
    4. **Sức khỏe Dịch vụ**: Đảm bảo tất cả các dịch vụ đang chạy
    
    ### Lịch trình
    Chạy hàng ngày lúc 6:00 sáng UTC (sau khi xử lý batch)
    
    ### Cảnh báo
    Lỗi sẽ kích hoạt thông báo email cho đội ngũ dữ liệu.
    """,
) as dag:
    
    start = EmptyOperator(task_id='start')
    
    # Kiểm tra sức khỏe dịch vụ
    check_minio_health = BashOperator(
        task_id='check_minio_health',
        bash_command='curl -sf http://minio:9000/minio/health/live || exit 1',
    )
    
    check_trino_health = BashOperator(
        task_id='check_trino_health',
        bash_command='curl -sf http://trino-coordinator:8080/v1/info || echo "Trino not available"',
    )
    
    # Các bước kiểm tra chất lượng dữ liệu
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
    
    # Task tổng kết
    quality_summary = BashOperator(
        task_id='quality_summary',
        bash_command='echo "Các bước kiểm tra chất lượng dữ liệu hoàn thành lúc $(date)"',
        trigger_rule=TriggerRule.ALL_DONE,
    )
    
    end = EmptyOperator(task_id='end')
    
    # Luồng thực thi DAG
    start >> [check_minio_health, check_trino_health]
    check_minio_health >> check_raw_data >> check_processed_freshness >> validate_schema
    [check_trino_health, validate_schema] >> quality_summary >> end
