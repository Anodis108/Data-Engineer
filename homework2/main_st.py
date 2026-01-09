"""
Vision Data Lake Dashboard - Multi-page Streamlit Application

A comprehensive web application that fully utilizes the mini data lake infrastructure:
- MinIO (S3) for storage
- RabbitMQ for real-time alerts
- Trino for SQL analytics
- Kafka for CDC monitoring

Usage:
    streamlit run main_st.py
"""
import streamlit as st
import logging
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Vision Data Lake Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import infrastructure
from src.infrastructure.config import load_config
from src.infrastructure.minio_client import MinioRepository
from src.infrastructure.rabbitmq_client import RabbitMQPublisher

# Import pages (using lazy imports in main to avoid errors if files are missing during dev)
def get_pages():
    try:
        from src.presentation.streamlit_pages.live_detection import render_live_detection
        from src.presentation.streamlit_pages.data_explorer import render_data_explorer
        from src.presentation.streamlit_pages.statistics import render_statistics
        from src.presentation.streamlit_pages.alerts import render_alerts
        from src.presentation.streamlit_pages.cdc_monitor import render_cdc_monitor
        from src.presentation.streamlit_pages.system_status import render_system_status
        return {
            "live": render_live_detection,
            "explorer": render_data_explorer,
            "stats": render_statistics,
            "alerts": render_alerts,
            "cdc": render_cdc_monitor,
            "status": render_system_status
        }
    except ImportError as e:
        logger.error(f"Failed to import pages: {e}")
        return {}


# ============================================================
# Resource Caching
# ============================================================

@st.cache_resource
def get_config():
    """Load and cache application configuration."""
    return load_config()


@st.cache_resource
def get_minio_client(_config):
    """Initialize and cache MinIO client."""
    try:
        return MinioRepository(
            endpoint=_config.minio_endpoint,
            access_key=_config.minio_access_key,
            secret_key=_config.minio_secret_key,
            bucket=_config.minio_bucket,
            secure=_config.minio_secure
        )
    except Exception as e:
        logger.error(f"MinIO init failed: {e}")
        return None


@st.cache_resource
def get_rabbitmq_client(_config):
    """Initialize and cache RabbitMQ client."""
    try:
        return RabbitMQPublisher(
            host=_config.rabbit_host,
            port=_config.rabbit_port,
            user=_config.rabbit_user,
            password=_config.rabbit_pass,
            exchange=_config.rabbit_exchange
        )
    except Exception as e:
        logger.error(f"RabbitMQ init failed: {e}")
        return None


@st.cache_resource
def get_trino_client():
    """Initialize and cache Trino client."""
    try:
        from src.infrastructure.trino_client import TrinoClient, TrinoConfig
        return TrinoClient(TrinoConfig())
    except Exception as e:
        logger.error(f"Trino init failed: {e}")
        return None


@st.cache_resource
def get_kafka_client():
    """Initialize and cache Kafka client."""
    try:
        from src.infrastructure.kafka_client import KafkaClient, KafkaConfig
        return KafkaClient(KafkaConfig())
    except Exception as e:
        logger.error(f"Kafka init failed: {e}")
        return None


# ============================================================
# Sidebar Navigation
# ============================================================

def render_sidebar():
    """Render the sidebar with navigation and status."""
    
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px;">
        <h1 style="color: #00ff88; margin: 0;">📊</h1>
        <h3 style="margin: 5px 0;">Vision Data Lake</h3>
        <p style="color: #888; font-size: 12px; margin: 0;">Dashboard v1.0</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    # Navigation
    pages_items = {
        "🎥 Live Detection": "live",
        "📁 Data Explorer": "explorer",
        "📈 Statistics": "stats",
        "🔔 Real-time Alerts": "alerts",
        "🔄 CDC Monitor": "cdc",
        "⚙️ System Status": "status"
    }
    
    selected = st.sidebar.radio(
        "Navigation",
        list(pages_items.keys()),
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    # Quick status indicators
    st.sidebar.markdown("### 🏥 Quick Status")
    
    config = get_config()
    minio = get_minio_client(config)
    rabbitmq = get_rabbitmq_client(config)
    trino = get_trino_client()
    kafka = get_kafka_client()
    
    status_items = [
        ("MinIO", minio and minio.is_connected),
        ("RabbitMQ", rabbitmq and rabbitmq.is_connected),
        ("Trino", trino and trino.is_connected),
        ("Kafka", kafka and kafka.is_connected),
    ]
    
    for name, connected in status_items:
        icon = "🟢" if connected else "🔴"
        st.sidebar.markdown(f"{icon} {name}")
    
    return pages_items[selected]


# ============================================================
# Custom CSS
# ============================================================

def inject_custom_css():
    """Inject custom CSS for better styling."""
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(180deg, #0e1117 0%, #1a1f2e 100%); }
        [data-testid="stSidebar"] { background: linear-gradient(180deg, #0a0d12 0%, #151a24 100%); }
        h1 { background: linear-gradient(90deg, #00ff88, #00ccff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# Main Application
# ============================================================

def main():
    """Main application entry point."""
    inject_custom_css()
    
    # Load resources
    config = get_config()
    minio_repo = get_minio_client(config)
    rabbitmq_pub = get_rabbitmq_client(config)
    trino_client = get_trino_client()
    kafka_client = get_kafka_client()
    
    # Get selected page
    page_id = render_sidebar()
    
    # Load page functions
    pages = get_pages()
    
    if not pages:
        st.error("Missing page modules. Please check src/presentation/streamlit_pages/")
        return
    
    # Route to selected page
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
    elif page_id == "status":
        pages["status"](config, minio_repo, rabbitmq_pub, trino_client, kafka_client)


if __name__ == "__main__":
    main()
