"""Trang Trạng thái Hệ thống - Kiểm tra sức khỏe cho tất cả các dịch vụ."""
import streamlit as st
import requests
import logging
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def render_system_status(config, minio_repo, rabbitmq_pub, trino_client, kafka_client):
    """Hiển thị trang trạng thái hệ thống."""
    
    st.header("⚙️ Trạng thái Hệ thống")
    st.markdown("Kiểm tra sức khỏe và cấu hình cho tất cả các dịch vụ data lake")
    
    # Tự động làm mới
    col_refresh, col_time = st.columns([1, 3])
    
    with col_refresh:
        if st.button("🔄 Làm mới Tất cả"):
            st.rerun()
    
    with col_time:
        st.caption(f"Lần kiểm tra cuối: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    st.divider()
    
    # Lưới trạng thái dịch vụ
    st.subheader("🏥 Sức khỏe Dịch vụ")
    
    services = [
        _check_minio(minio_repo, config),
        _check_rabbitmq(rabbitmq_pub, config),
        _check_trino(trino_client, config),
        _check_kafka(kafka_client, config),
        _check_camera(config),
        _check_postgres_metastore(config),
        _check_postgres_cdc(config),
        _check_hive_metastore(config),
    ]
    
    # Hiển thị trên lưới
    cols = st.columns(4)
    for i, service in enumerate(services):
        with cols[i % 4]:
            _render_service_card(service)
    
    st.divider()
    
    # Trạng thái chi tiết
    st.subheader("📋 Trạng thái Chi tiết")
    
    tab_config, tab_endpoints = st.tabs(["⚙️ Cấu hình", "🔗 Endpoints"])
    
    with tab_config:
        _render_configuration(config)
    
    with tab_endpoints:
        _render_endpoints()


def _check_minio(minio_repo, config) -> dict:
    status = {"name": "MinIO", "icon": "🪣", "endpoint": config.minio_endpoint}
    if minio_repo and minio_repo.is_connected:
        status["status"] = "healthy"
        status["details"] = f"{len(minio_repo.list_buckets())} buckets"
    else:
        status["status"] = "unhealthy"
        status["details"] = "Kết nối thất bại"
    return status


def _check_rabbitmq(rabbitmq_pub, config) -> dict:
    status = {"name": "RabbitMQ", "icon": "🐰", "endpoint": f"{config.rabbit_host}:{config.rabbit_port}"}
    if rabbitmq_pub and rabbitmq_pub.is_connected:
        status["status"] = "healthy"
    else:
        status["status"] = "unhealthy"
    return status


def _check_trino(trino_client, config) -> dict:
    status = {"name": "Trino", "icon": "🔷", "endpoint": "localhost:8080"}
    if trino_client and trino_client.is_connected:
        status["status"] = "healthy"
    else:
        # Kiểm tra API Trino trực tiếp
        resp = requests.get("http://localhost:8080/v1/info", timeout=2)
        status["status"] = "healthy" if resp.status_code == 200 else "unhealthy"
    return status


def _check_kafka(kafka_client, config) -> dict:
    status = {"name": "Kafka", "icon": "📬", "endpoint": "localhost:9092"}
    if kafka_client and kafka_client.is_connected:
        status["status"] = "healthy"
    else:
        status["status"] = "unhealthy"
    return status


def _check_camera(config) -> dict:
    import cv2
    import platform
    status = {"name": "Camera Vision", "icon": "🎥", "endpoint": f"Index: {config.camera_index}"}
    
    backend = "DSHOW" if platform.system() == "Windows" else "ANY"
    status["details"] = f"Backend: {backend}"
    
    cap = cv2.VideoCapture(config.camera_index)
    if cap.isOpened():
        status["status"] = "healthy"
        cap.release()
    else:
        status["status"] = "unhealthy"
    return status


def _check_postgres_metastore(config) -> dict:
    status = {"name": "DB Metastore", "icon": "🐘", "endpoint": "localhost:5432"}
    # Kiểm tra kết nối Metastore DB
    import psycopg2
    conn = psycopg2.connect(host="localhost", port=5432, database="metastore", user="hive", password="hive_password", connect_timeout=2)
    conn.close()
    status["status"] = "healthy"
    return status


def _check_postgres_cdc(config) -> dict:
    status = {"name": "Postgres CDC", "icon": "🐘", "endpoint": "localhost:5433"}
    # Kiểm tra kết nối CDC Postgres
    import psycopg2
    conn = psycopg2.connect(host="localhost", port=5433, database="inventory", user="dbz", password="dbz", connect_timeout=2)
    conn.close()
    status["status"] = "healthy"
    return status


def _check_hive_metastore(config) -> dict:
    status = {"name": "Hive Metastore", "icon": "🐝", "endpoint": "localhost:9083"}
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(("localhost", 9083))
    sock.close()
    status["status"] = "healthy" if result == 0 else "unhealthy"
    return status


def _render_service_card(service: dict):
    status = service.get("status", "unknown")
    indicator = "🟢" if status == "healthy" else "🔴"
    color = "#00ff88" if status == "healthy" else "#ff4444"
    
    st.markdown(f"""
    <div style="background: #1a1f2e; border-radius: 10px; padding: 15px; margin-bottom: 15px; border-left: 4px solid {color};">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span>{service.get('icon', '📦')}</span>
            <span style="font-weight: 600;">{service.get('name')}</span>
            <span style="margin-left: auto;">{indicator}</span>
        </div>
        <div style="color: #888; font-size: 11px; margin-top: 5px;">{service.get('endpoint')}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_configuration(config):
    st.json({
        "minio": config.minio_endpoint,
        "rabbitmq": f"{config.rabbit_host}:{config.rabbit_port}",
        "camera": config.camera_index,
        "model": config.model_path
    })


def _render_endpoints():
    endpoints = [
        {"Service": "MinIO Console", "URL": "http://localhost:9001"},
        {"Service": "Trino UI", "URL": "http://localhost:8080/ui"},
        {"Service": "Kafka UI", "URL": "http://localhost:8081"},
        {"Service": "RabbitMQ UI", "URL": "http://localhost:15672"},
    ]
    st.table(endpoints)
