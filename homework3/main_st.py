"""
Vision Data Lake Dashboard - Ứng dụng Streamlit Đa trang

Một ứng dụng web toàn diện sử dụng hệ hạ tầng mini data lake:
- MinIO (S3) để lưu trữ
- RabbitMQ cho cảnh báo thời gian thực
- Trino để phân tích SQL
- Kafka để giám sát CDC
- Apache Spark để xử lý batch và streaming
- Apache Flink để xử lý luồng thời gian thực

Cách dùng:
    streamlit run main_st.py
"""
import streamlit as st
import logging
import os

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

# Cấu hình trang - PHẢI là lệnh Streamlit đầu tiên
st.set_page_config(
    page_title="Vision Data Lake Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Nhập các thành phần hạ tầng
from src.infrastructure.config import load_config
from src.infrastructure.minio_client import MinioRepository
from src.infrastructure.rabbitmq_client import RabbitMQPublisher

# Nhập các trang (sử dụng lazy import để tối ưu)
def get_pages():
    # Bỏ try-except để lỗi hiển thị trực tiếp cho mục đích học tập
    from src.presentation.streamlit_pages.live_detection import render_live_detection
    from src.presentation.streamlit_pages.data_explorer import render_data_explorer
    from src.presentation.streamlit_pages.statistics import render_statistics
    from src.presentation.streamlit_pages.alerts import render_alerts
    from src.presentation.streamlit_pages.cdc_monitor import render_cdc_monitor
    from src.presentation.streamlit_pages.system_status import render_system_status
    from src.presentation.streamlit_pages.spark_monitor import render_spark_monitor
    from src.presentation.streamlit_pages.flink_monitor import render_flink_monitor
    from src.presentation.streamlit_pages.processing_demo import render_processing_demo
    from src.presentation.streamlit_pages.monitoring_dashboard import render_monitoring_dashboard
    return {
        "live": render_live_detection,
        "explorer": render_data_explorer,
        "stats": render_statistics,
        "alerts": render_alerts,
        "cdc": render_cdc_monitor,
        "status": render_system_status,
        "spark": render_spark_monitor,
        "flink": render_flink_monitor,
        "processing": render_processing_demo,
        "monitoring": render_monitoring_dashboard
    }


# ============================================================
# Bộ nhớ đệm tài nguyên (Resource Caching)
# ============================================================

@st.cache_resource
def get_config():
    """Tải và lưu trữ cấu hình ứng dụng vào bộ nhớ đệm."""
    return load_config()


@st.cache_resource
def get_minio_client(_config):
    """Khởi tạo và lưu trữ MinIO client vào bộ nhớ đệm."""
    # Quy trình khởi tạo trực tiếp không cần bắt lỗi
    return MinioRepository(
        endpoint=_config.minio_endpoint,
        access_key=_config.minio_access_key,
        secret_key=_config.minio_secret_key,
        bucket=_config.minio_bucket,
        secure=_config.minio_secure
    )


@st.cache_resource
def get_rabbitmq_client(_config):
    """Khởi tạo và lưu trữ RabbitMQ client vào bộ nhớ đệm."""
    return RabbitMQPublisher(
        host=_config.rabbit_host,
        port=_config.rabbit_port,
        user=_config.rabbit_user,
        password=_config.rabbit_pass,
        exchange=_config.rabbit_exchange
    )


@st.cache_resource
def get_trino_client():
    """Khởi tạo và lưu trữ Trino client vào bộ nhớ đệm."""
    from src.infrastructure.trino_client import TrinoClient, TrinoConfig
    return TrinoClient(TrinoConfig())


@st.cache_resource
def get_kafka_client():
    """Khởi tạo và lưu trữ Kafka client vào bộ nhớ đệm."""
    from src.infrastructure.kafka_client import KafkaClient, KafkaConfig
    return KafkaClient(KafkaConfig())


@st.cache_resource
def get_spark_client():
    """Khởi tạo và lưu trữ Spark client vào bộ nhớ đệm."""
    from src.infrastructure.spark_client import SparkClient, SparkConfig
    return SparkClient(SparkConfig())


@st.cache_resource
def get_flink_client():
    """Khởi tạo và lưu trữ Flink client vào bộ nhớ đệm."""
    from src.infrastructure.flink_client import FlinkClient, FlinkConfig
    return FlinkClient(FlinkConfig())


# ============================================================
# Điều hướng Sidebar
# ============================================================

def render_sidebar():
    """Hiển thị sidebar với các phím điều hướng và trạng thái."""
    
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px;">
        <h1 style="color: #00ff88; margin: 0;">📊</h1>
        <h3 style="margin: 5px 0;">Vision Data Lake</h3>
        <p style="color: #888; font-size: 12px; margin: 0;">Dashboard v1.0</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    # Danh mục điều hướng
    pages_items = {
        "🎥 Phát hiện Trực tiếp": "live",
        "📁 Khám phá Dữ liệu": "explorer",
        "📈 Thống kê Chi tiết": "stats",
        "🔔 Cảnh báo Thời gian thực": "alerts",
        "🔄 Giám sát CDC": "cdc",
        "🔥 Giám sát Spark": "spark",
        "🌊 Giám sát Flink": "flink",
        "⚡ Demo Tầng Xử lý": "processing",
        "📊 Bảng điều khiển Giám sát": "monitoring",
        "⚙️ Trạng thái Hệ thống": "status"
    }
    
    selected = st.sidebar.radio(
        "Điều hướng",
        list(pages_items.keys()),
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    # Các nhãn hiển thị trạng thái nhanh
    st.sidebar.markdown("### 🏥 Trạng thái Nhanh")
    
    config = get_config()
    minio = get_minio_client(config)
    rabbitmq = get_rabbitmq_client(config)
    trino = get_trino_client()
    kafka = get_kafka_client()
    spark = get_spark_client()
    flink = get_flink_client()
    
    status_items = [
        ("MinIO", minio and minio.is_connected),
        ("RabbitMQ", rabbitmq and rabbitmq.is_connected),
        ("Trino", trino and trino.is_connected),
        ("Kafka", kafka and kafka.is_connected),
        ("Spark", spark and spark.is_connected),
        ("Flink", flink and flink.is_connected),
    ]
    
    for name, connected in status_items:
        icon = "🟢" if connected else "🔴"
        st.sidebar.markdown(f"{icon} {name}")
    
    return pages_items[selected]


# ============================================================
# CSS Tùy chỉnh (Custom CSS)
# ============================================================

def inject_custom_css():
    """Chèn CSS tùy chỉnh để làm đẹp giao diện."""
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(180deg, #0e1117 0%, #1a1f2e 100%); }
        [data-testid="stSidebar"] { background: linear-gradient(180deg, #0a0d12 0%, #151a24 100%); }
        h1 { background: linear-gradient(90deg, #00ff88, #00ccff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# Ứng dụng Chính
# ============================================================

def main():
    """Điểm vào của ứng dụng chính."""
    inject_custom_css()
    
    # Tải các tài nguyên
    config = get_config()
    minio_repo = get_minio_client(config)
    rabbitmq_pub = get_rabbitmq_client(config)
    trino_client = get_trino_client()
    kafka_client = get_kafka_client()
    spark_client = get_spark_client()
    flink_client = get_flink_client()
    
    # Hiển thị trang được chọn
    page_id = render_sidebar()
    
    # Tải các hàm xử lý trang
    pages = get_pages()
    
    # Điều hướng đến trang tương ứng
    if page_id == "live":
        pages["live"](config, minio_repo, rabbitmq_pub)
    elif page_id == "explorer":
        pages["explorer"](minio_repo)
    elif page_id == "stats":
        pages["stats"](trino_client, minio_repo)
    elif page_id == "alerts":
        pages["alerts"](rabbitmq_pub)
    elif page_id == "cdc":
        pages["cdc"](kafka_client)
    elif page_id == "spark":
        pages["spark"](spark_client)
    elif page_id == "flink":
        pages["flink"](flink_client)
    elif page_id == "processing":
        pages["processing"](minio_repo, spark_client, flink_client)
    elif page_id == "monitoring":
        pages["monitoring"]()
    elif page_id == "status":
        pages["status"](config, minio_repo, rabbitmq_pub, trino_client, kafka_client)


if __name__ == "__main__":
    main()
