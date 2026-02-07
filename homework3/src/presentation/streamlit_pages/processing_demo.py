"""Trang Streamlit minh họa khả năng của Tầng Xử lý."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Optional
import random

from src.infrastructure.spark_client import SparkClient
from src.infrastructure.flink_client import FlinkClient
from src.infrastructure.minio_client import MinioRepository


def generate_sample_hourly_data(hours: int = 24) -> pd.DataFrame:
    """Tạo dữ liệu thống kê mẫu theo giờ."""
    now = datetime.now()
    data = {
        "hour": [now - timedelta(hours=i) for i in range(hours)],
        "event_count": [random.randint(50, 200) for _ in range(hours)],
        "avg_person_count": [round(random.uniform(1, 5), 2) for _ in range(hours)],
        "max_person_count": [random.randint(3, 10) for _ in range(hours)],
        "avg_confidence": [round(random.uniform(0.7, 0.95), 2) for _ in range(hours)]
    }
    return pd.DataFrame(data)


def generate_sample_daily_data(days: int = 7) -> pd.DataFrame:
    """Tạo dữ liệu thống kê mẫu theo ngày."""
    now = datetime.now()
    data = {
        "date": [now.date() - timedelta(days=i) for i in range(days)],
        "total_events": [random.randint(1000, 5000) for _ in range(days)],
        "total_persons": [random.randint(2000, 8000) for _ in range(days)],
        "peak_hour": [random.randint(8, 20) for _ in range(days)],
        "avg_confidence": [round(random.uniform(0.75, 0.92), 2) for _ in range(days)]
    }
    return pd.DataFrame(data)


def render_processing_demo(
    minio_repo: Optional[MinioRepository],
    spark_client: Optional[SparkClient],
    flink_client: Optional[FlinkClient]
):
    """
    Hiển thị trang demo Tầng Xử lý.
    
    Args:
        minio_repo: MinIO repository để truy cập dữ liệu
        spark_client: Spark client để kiểm tra trạng thái
        flink_client: Flink client để kiểm tra trạng thái
    """
    st.header("⚡ Demo Tầng Xử lý")
    st.markdown("""
    Trang này minh họa **Tầng Xử lý** (Layer 4) của pipeline dữ liệu 6 tầng,
    được vận hành bởi **Apache Spark** và **Apache Flink**.
    """)
    
    # ============================================
    # Tổng quan Kiến trúc
    # ============================================
    with st.expander("📐 Tổng quan Kiến trúc", expanded=False):
        st.markdown("""
        ```
        ┌─────────────────────────────────────────────────────────────────────────┐
        │                      KIẾN TRÚC DATA PIPELINE                             │
        ├─────────────────────────────────────────────────────────────────────────┤
        │                                                                          │
        │   ┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐   │
        │   │ LƯU TRỮ THÔ  │────▶│      XỬ LÝ       │────▶│ LƯU TRỮ PHỤC VỤ  │   │
        │   │   (MinIO)    │     │  (Spark/Flink)   │     │     (MinIO)      │   │
        │   └──────────────┘     └──────────────────┘     └──────────────────┘   │
        │         │                      │                          │             │
        │         │              ┌───────┴───────┐                  │             │
        │         │              │               │                  │             │
        │         ▼              ▼               ▼                  ▼             │
        │   ┌──────────┐   ┌──────────┐   ┌──────────┐      ┌──────────────┐    │
        │   │  Parquet │   │  Spark   │   │  Flink   │      │    Trino     │    │
        │   │   Files  │   │  Batch   │   │ Streaming│      │   (Query)    │    │
        │   └──────────┘   └──────────┘   └──────────┘      └──────────────┘    │
        │                                                                          │
        └─────────────────────────────────────────────────────────────────────────┘
        ```
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **🔥 Apache Spark:**
            - Xử lý Batch (tổng hợp theo giờ/ngày)
            - Structured Streaming cho Kafka CDC
            - Đọc/Ghi Parquet trên MinIO
            - Tính toán phân tán
            """)
        
        with col2:
            st.markdown("""
            **🌊 Apache Flink:**
            - Xử lý streaming thực thụ (True streaming)
            - Xử lý sự kiện độ trễ thấp
            - Tính toán stream có trạng thái (Stateful)
            - Ngữ nghĩa chính xác một lần (Exactly-once)
            """)
    
    st.divider()
    
    # ============================================
    # Trạng thái Engine
    # ============================================
    st.subheader("🏥 Trạng thái Các Engine Xử lý")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if spark_client and spark_client.is_connected:
            st.success("🔥 **Spark**: Trực tuyến")
            cluster_info = spark_client.get_cluster_info()
            if cluster_info:
                st.caption(f"Workers: {cluster_info.get('workers_alive', 0)} | "
                          f"Cores: {cluster_info.get('cores_total', 0)}")
        else:
            st.error("🔥 **Spark**: Ngoại tuyến")
    
    with col2:
        if flink_client and flink_client.is_connected:
            st.success("🌊 **Flink**: Trực tuyến")
            overview = flink_client.get_cluster_overview()
            if overview:
                st.caption(f"TaskManagers: {overview.get('taskmanagers', 0)} | "
                          f"Slots: {overview.get('slots_total', 0)}")
        else:
            st.error("🌊 **Flink**: Ngoại tuyến")
    
    with col3:
        if minio_repo and minio_repo.is_connected:
            st.success("🗄️ **MinIO**: Trực tuyến")
            stats = minio_repo.get_bucket_stats()
            st.caption(f"Objects: {stats.get('object_count', 0)} | "
                      f"Size: {stats.get('total_size_mb', 0)} MB")
        else:
            st.error("🗄️ **MinIO**: Ngoại tuyến")
    
    st.divider()
    
    # ============================================
    # Trực quan hóa Dữ liệu Đã xử lý
    # ============================================
    st.subheader("📈 Trực quan hóa Dữ liệu Đã xử lý")
    
    st.info("💡 Hiển thị dữ liệu tổng hợp mẫu. Trong thực tế, dữ liệu này sẽ được đọc từ "
            "zone **processed/** trong MinIO, được tính toán bởi các Spark batch jobs.")
    
    # Tạo dữ liệu mẫu
    hourly_df = generate_sample_hourly_data(24)
    daily_df = generate_sample_daily_data(7)
    
    tab1, tab2, tab3 = st.tabs(["📊 Thống kê theo Giờ", "📅 Thống kê theo Ngày", "🎯 Cảnh báo Thời gian thực"])
    
    with tab1:
        st.markdown("### Tổng hợp Sự kiện theo Giờ")
        st.caption("*Được tính toán bởi Spark batch job: `batch_vision_aggregator.py`*")
        
        # Biểu đồ đường cho số lượng sự kiện
        fig = px.line(
            hourly_df.sort_values("hour"),
            x="hour",
            y="event_count",
            title="Sự kiện Thị giác mỗi Giờ",
            labels={"hour": "Thời gian", "event_count": "Số lượng Sự kiện"}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Biểu đồ cột cho số người
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                hourly_df.sort_values("hour").tail(12),
                x="hour",
                y="avg_person_count",
                title="Số người Trung bình (12 giờ qua)",
                color="avg_person_count",
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                hourly_df.sort_values("hour").tail(12),
                x="hour",
                y="avg_confidence",
                title="Độ tin cậy Phát hiện Trung bình",
                color="avg_confidence",
                color_continuous_scale="RdYlGn"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Bảng dữ liệu
        with st.expander("📋 Xem Dữ liệu Thô theo Giờ"):
            st.dataframe(
                hourly_df.sort_values("hour", ascending=False),
                use_container_width=True,
                hide_index=True
            )
    
    with tab2:
        st.markdown("### Tổng hợp theo Ngày")
        st.caption("*Được tính toán bởi Spark batch job: `batch_vision_aggregator.py`*")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                daily_df.sort_values("date"),
                x="date",
                y="total_events",
                title="Tổng Sự kiện mỗi Ngày",
                color="total_events",
                color_continuous_scale="Blues"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                daily_df.sort_values("date"),
                x="date",
                y="total_persons",
                title="Tổng Phát hiện Người mỗi Ngày",
                color="total_persons",
                color_continuous_scale="Oranges"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Metrics
        latest = daily_df.sort_values("date", ascending=False).iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Sự kiện Hôm nay", f"{latest['total_events']:,}")
        with col2:
            st.metric("Phát hiện Người", f"{latest['total_persons']:,}")
        with col3:
            st.metric("Giờ Cao điểm", f"{latest['peak_hour']}:00")
        with col4:
            st.metric("Độ tin cậy TB", f"{latest['avg_confidence']:.1%}")
    
    with tab3:
        st.markdown("### Phát hiện Cảnh báo Thời gian thực")
        st.caption("*Được tính toán bởi các Spark/Flink streaming jobs*")
        
        st.markdown("""
        **Quy tắc Cảnh báo:**
        - 🔴 **HIGH_PERSON_COUNT**: Số người > 3 trong cửa sổ phát hiện
        - 🟡 **LOW_CONFIDENCE**: Độ tin cậy trung bình < 0.5
        - 🔵 **LONG_PRESENCE**: Người xuất hiện trong > 5 phút
        """)
        
        # Cảnh báo mẫu
        alerts = [
            {"time": datetime.now() - timedelta(minutes=5), "type": "HIGH_PERSON_COUNT", 
             "camera": "cam_01", "message": "Detected 5 persons (threshold: 3)"},
            {"time": datetime.now() - timedelta(minutes=15), "type": "LONG_PRESENCE",
             "camera": "cam_02", "message": "Person present for 7 minutes"},
            {"time": datetime.now() - timedelta(minutes=30), "type": "HIGH_PERSON_COUNT",
             "camera": "cam_01", "message": "Detected 4 persons (threshold: 3)"},
        ]
        
        for alert in alerts:
            icon = "🔴" if alert["type"] == "HIGH_PERSON_COUNT" else "🔵"
            
            with st.container():
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.markdown(f"### {icon}")
                with col2:
                    st.markdown(f"**{alert['type']}** - `{alert['camera']}`")
                    st.caption(f"{alert['time'].strftime('%H:%M:%S')} - {alert['message']}")
            
            st.divider()
    
    st.divider()
    
    # ============================================
    # Pipeline Jobs
    # ============================================
    st.subheader("🔧 Các Job Xử lý")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔥 Các Job Spark")
        
        jobs = [
            {"name": "batch_vision_aggregator.py", "type": "Batch", 
             "desc": "Tổng hợp theo Giờ/Ngày"},
            {"name": "streaming_kafka_processor.py", "type": "Streaming",
             "desc": "CDC events từ Kafka"},
            {"name": "streaming_vision_events.py", "type": "Streaming",
             "desc": "Sự kiện thị giác thời gian thực"}
        ]
        
        for job in jobs:
            with st.expander(f"📄 {job['name']}"):
                st.markdown(f"**Loại:** {job['type']}")
                st.markdown(f"**Mô tả:** {job['desc']}")
                st.code(f"""
# Gửi job này:
docker exec spark-master spark-submit \\
    --master spark://spark-master:7077 \\
    /opt/bitnami/spark/jobs/{job['name']}
                """, language="bash")
    
    with col2:
        st.markdown("#### 🌊 Các Job Flink")
        
        flink_jobs = [
            {"name": "stream_processor.py", "type": "Streaming",
             "desc": "Xử lý sự kiện Vision và CDC"},
            {"name": "flink_sql_analytics.py", "type": "SQL",
             "desc": "Phân tích SQL thời gian thực"}
        ]
        
        for job in flink_jobs:
            with st.expander(f"📄 {job['name']}"):
                st.markdown(f"**Loại:** {job['type']}")
                st.markdown(f"**Mô tả:** {job['desc']}")
                st.code(f"""
# Chạy ở chế độ demo:
cd homework3
python flink/jobs/{job['name']}

# Hoặc với PyFlink:
USE_FLINK=true python flink/jobs/{job['name']}
                """, language="bash")
