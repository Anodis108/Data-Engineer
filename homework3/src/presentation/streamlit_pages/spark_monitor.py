"""Trang Streamlit để giám sát cụm Apache Spark."""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from src.infrastructure.spark_client import SparkClient


def format_duration(ms: int) -> str:
    """Định dạng mili giây thành thời lượng dễ đọc."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    elif ms < 3600000:
        return f"{ms / 60000:.1f}m"
    else:
        return f"{ms / 3600000:.1f}h"


def format_memory(mb: int) -> str:
    """Định dạng bộ nhớ MB thành chuỗi dễ đọc."""
    if mb < 1024:
        return f"{mb} MB"
    else:
        return f"{mb / 1024:.1f} GB"


def render_spark_monitor(spark_client: Optional[SparkClient]):
    """
    Hiển thị trang giám sát Spark.
    
    Args:
        spark_client: SparkClient instance để gọi API
    """
    st.header("🔥 Giám sát Apache Spark")
    st.markdown("Giám sát thời gian thực cụm Spark và các ứng dụng")
    
    # Kiểm tra trạng thái kết nối
    if not spark_client:
        st.error("❌ Spark client chưa được khởi tạo")
        st.info("""
        **Để khởi động cụm Spark:**
        ```bash
        cd mini_datalake_cdc_dvc
        docker compose up -d spark-master spark-worker
        ```
        """)
        return
    
    # Làm mới kết nối
    if st.button("🔄 Làm mới Kết nối"):
        spark_client.refresh_connection()
        st.rerun()
    
    if not spark_client.is_connected:
        st.error("❌ Không thể kết nối với Spark Master")
        st.warning(f"Đã thử kết nối tới: `{spark_client.config.master_url}`")
        
        with st.expander("🔧 Khắc phục sự cố"):
            st.markdown("""
            1. **Kiểm tra xem Spark có đang chạy không:**
               ```bash
               docker ps | grep spark
               ```
            
            2. **Khởi động cụm Spark:**
               ```bash
               cd mini_datalake_cdc_dvc
               docker compose up -d spark-master spark-worker
               ```
            
            3. **Kiểm tra logs của Spark Master:**
               ```bash
               docker logs spark-master
               ```
            
            4. **Xác minh ánh xạ cổng:**
               - Master UI: http://localhost:8090
               - Master RPC: spark://localhost:7077
            """)
        return
    
    st.success("✅ Đã kết nối với Spark Master")
    
    # ============================================
    # Tổng quan Cụm
    # ============================================
    st.subheader("📊 Tổng quan Cụm")
    
    cluster_info = spark_client.get_cluster_info()
    
    if cluster_info:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Trạng thái",
                cluster_info.get("status", "KHÔNG XÁC ĐỊNH"),
                help="Trạng thái cụm"
            )
        
        with col2:
            st.metric(
                "Workers",
                cluster_info.get("workers_alive", 0),
                help="Số lượng worker đang hoạt động"
            )
        
        with col3:
            cores_used = cluster_info.get("cores_used", 0)
            cores_total = cluster_info.get("cores_total", 0)
            st.metric(
                "Cores",
                f"{cores_used} / {cores_total}",
                help="Cores đang dùng / tổng lý"
            )
        
        with col4:
            mem_used = cluster_info.get("memory_used_mb", 0)
            mem_total = cluster_info.get("memory_total_mb", 0)
            st.metric(
                "Bộ nhớ",
                f"{format_memory(mem_used)} / {format_memory(mem_total)}",
                help="Bộ nhớ đang dùng / tổng số"
            )
        
        # Tóm tắt ứng dụng
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Ứng dụng Đang chạy", cluster_info.get("active_apps", 0))
        with col2:
            st.metric("Ứng dụng Đã xong", cluster_info.get("completed_apps", 0))
    
    st.divider()
    
    # ============================================
    # Workers
    # ============================================
    st.subheader("🖥️ Workers")
    
    workers = spark_client.get_workers()
    
    if workers:
        workers_data = []
        for w in workers:
            workers_data.append({
                "Worker ID": w.worker_id[:20] + "..." if len(w.worker_id) > 20 else w.worker_id,
                "Host": w.host,
                "Trạng thái": w.state,
                "Cores": f"{w.cores_used} / {w.cores}",
                "Bộ nhớ": f"{format_memory(w.memory_used)} / {format_memory(w.memory)}"
            })
        
        df = pd.DataFrame(workers_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Không tìm thấy worker nào")
    
    st.divider()
    
    # ============================================
    # Ứng dụng
    # ============================================
    st.subheader("📋 Ứng dụng")
    
    tab_running, tab_completed = st.tabs(["🟢 Đang chạy", "✅ Đã xong"])
    
    with tab_running:
        running_apps = spark_client.get_applications(status="running")
        
        if running_apps:
            apps_data = []
            for app in running_apps:
                apps_data.append({
                    "App ID": app.app_id,
                    "Tên": app.name,
                    "Trạng thái": "🟢 " + app.state,
                    "Thời lượng": format_duration(app.duration_ms),
                    "Cores": app.cores
                })
            
            df = pd.DataFrame(apps_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Không có ứng dụng đang chạy")
    
    with tab_completed:
        completed_apps = spark_client.get_applications(status="completed")
        
        if completed_apps:
            apps_data = []
            for app in completed_apps[-10:]:  # Last 10
                apps_data.append({
                    "App ID": app.app_id,
                    "Tên": app.name,
                    "Trạng thái": "✅ " + app.state,
                    "Thời lượng": format_duration(app.duration_ms)
                })
            
            df = pd.DataFrame(apps_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Không có ứng dụng đã hoàn thành")
    
    st.divider()
    
    # ============================================
    # Thao tác nhanh
    # ============================================
    st.subheader("🚀 Thao tác nhanh")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.link_button(
            "🌐 Mở Spark UI",
            "http://localhost:8090",
            use_container_width=True
        )
    
    with col2:
        st.link_button(
            "👷 Worker UI",
            "http://localhost:8091",
            use_container_width=True
        )
    
    with col3:
        if st.button("🔄 Làm mới Dữ liệu", use_container_width=True):
            st.rerun()
    
    # Thông tin gửi job
    with st.expander("📝 Gửi Spark Job"):
        st.markdown("""
        **Gửi một batch job:**
        ```bash
        docker exec spark-master spark-submit \\
            --master spark://spark-master:7077 \\
            --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \\
            /opt/bitnami/spark/jobs/batch_vision_aggregator.py
        ```
        
        **Gửi một streaming job:**
        ```bash
        docker exec spark-master spark-submit \\
            --master spark://spark-master:7077 \\
            --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \\
            /opt/bitnami/spark/jobs/streaming_kafka_processor.py
        ```
        """)
