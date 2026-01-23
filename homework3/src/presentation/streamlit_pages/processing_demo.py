"""Streamlit page demonstrating the Processing Layer capabilities."""
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
    """Generate sample hourly statistics data."""
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
    """Generate sample daily statistics data."""
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
    Render Processing Layer demo page.
    
    Args:
        minio_repo: MinIO repository for data access
        spark_client: Spark client for status check
        flink_client: Flink client for status check
    """
    st.header("⚡ Processing Layer Demo")
    st.markdown("""
    This page demonstrates the **Processing Layer** (Layer 4) of our 6-layer data pipeline,
    powered by **Apache Spark** and **Apache Flink**.
    """)
    
    # ============================================
    # Architecture Overview
    # ============================================
    with st.expander("📐 Architecture Overview", expanded=False):
        st.markdown("""
        ```
        ┌─────────────────────────────────────────────────────────────────────────┐
        │                      DATA PIPELINE ARCHITECTURE                          │
        ├─────────────────────────────────────────────────────────────────────────┤
        │                                                                          │
        │   ┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐   │
        │   │ RAW STORAGE  │────▶│    PROCESSING    │────▶│ SERVING STORAGE  │   │
        │   │   (MinIO)    │     │  (Spark/Flink)   │     │     (MinIO)      │   │
        │   └──────────────┘     └──────────────────┘     └──────────────────┘   │
        │         │                      │                          │             │
        │         │              ┌───────┴───────┐                  │             │
        │         │              │               │                  │             │
        │         ▼              ▼               ▼                  ▼             │
        │   ┌──────────┐   ┌──────────┐   ┌──────────┐      ┌──────────────┐    │
        │   │ Parquet  │   │  Spark   │   │  Flink   │      │    Trino     │    │
        │   │  Files   │   │  Batch   │   │ Streaming│      │   (Query)    │    │
        │   └──────────┘   └──────────┘   └──────────┘      └──────────────┘    │
        │                                                                          │
        └─────────────────────────────────────────────────────────────────────────┘
        ```
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **🔥 Apache Spark:**
            - Batch processing (hourly/daily aggregations)
            - Structured Streaming for Kafka CDC
            - Read/Write Parquet on MinIO
            - Distributed computation
            """)
        
        with col2:
            st.markdown("""
            **🌊 Apache Flink:**
            - True streaming processing
            - Low-latency event handling
            - Stateful stream computations
            - Exactly-once semantics
            """)
    
    st.divider()
    
    # ============================================
    # Engine Status
    # ============================================
    st.subheader("🏥 Processing Engines Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if spark_client and spark_client.is_connected:
            st.success("🔥 **Spark**: Online")
            cluster_info = spark_client.get_cluster_info()
            if cluster_info:
                st.caption(f"Workers: {cluster_info.get('workers_alive', 0)} | "
                          f"Cores: {cluster_info.get('cores_total', 0)}")
        else:
            st.error("🔥 **Spark**: Offline")
    
    with col2:
        if flink_client and flink_client.is_connected:
            st.success("🌊 **Flink**: Online")
            overview = flink_client.get_cluster_overview()
            if overview:
                st.caption(f"TaskManagers: {overview.get('taskmanagers', 0)} | "
                          f"Slots: {overview.get('slots_total', 0)}")
        else:
            st.error("🌊 **Flink**: Offline")
    
    with col3:
        if minio_repo and minio_repo.is_connected:
            st.success("🗄️ **MinIO**: Online")
            stats = minio_repo.get_bucket_stats()
            st.caption(f"Objects: {stats.get('object_count', 0)} | "
                      f"Size: {stats.get('total_size_mb', 0)} MB")
        else:
            st.error("🗄️ **MinIO**: Offline")
    
    st.divider()
    
    # ============================================
    # Processed Data Visualization
    # ============================================
    st.subheader("📈 Processed Data Visualization")
    
    st.info("💡 Showing sample aggregated data. In production, this would be read from "
            "the **processed/** zone in MinIO, computed by Spark batch jobs.")
    
    # Generate sample data
    hourly_df = generate_sample_hourly_data(24)
    daily_df = generate_sample_daily_data(7)
    
    tab1, tab2, tab3 = st.tabs(["📊 Hourly Stats", "📅 Daily Stats", "🎯 Real-time Alerts"])
    
    with tab1:
        st.markdown("### Hourly Event Aggregations")
        st.caption("*Computed by Spark batch job: `batch_vision_aggregator.py`*")
        
        # Line chart for event count
        fig = px.line(
            hourly_df.sort_values("hour"),
            x="hour",
            y="event_count",
            title="Vision Events per Hour",
            labels={"hour": "Time", "event_count": "Event Count"}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Bar chart for person count
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                hourly_df.sort_values("hour").tail(12),
                x="hour",
                y="avg_person_count",
                title="Avg Person Count (Last 12 Hours)",
                color="avg_person_count",
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                hourly_df.sort_values("hour").tail(12),
                x="hour",
                y="avg_confidence",
                title="Avg Detection Confidence",
                color="avg_confidence",
                color_continuous_scale="RdYlGn"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        with st.expander("📋 View Raw Hourly Data"):
            st.dataframe(
                hourly_df.sort_values("hour", ascending=False),
                use_container_width=True,
                hide_index=True
            )
    
    with tab2:
        st.markdown("### Daily Aggregations")
        st.caption("*Computed by Spark batch job: `batch_vision_aggregator.py`*")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                daily_df.sort_values("date"),
                x="date",
                y="total_events",
                title="Total Events per Day",
                color="total_events",
                color_continuous_scale="Blues"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                daily_df.sort_values("date"),
                x="date",
                y="total_persons",
                title="Total Person Detections per Day",
                color="total_persons",
                color_continuous_scale="Oranges"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Metrics
        latest = daily_df.sort_values("date", ascending=False).iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Today's Events", f"{latest['total_events']:,}")
        with col2:
            st.metric("Person Detections", f"{latest['total_persons']:,}")
        with col3:
            st.metric("Peak Hour", f"{latest['peak_hour']}:00")
        with col4:
            st.metric("Avg Confidence", f"{latest['avg_confidence']:.1%}")
    
    with tab3:
        st.markdown("### Real-time Alert Detection")
        st.caption("*Computed by Spark/Flink streaming jobs*")
        
        st.markdown("""
        **Alert Rules:**
        - 🔴 **HIGH_PERSON_COUNT**: Person count > 3 in detection window
        - 🟡 **LOW_CONFIDENCE**: Average confidence < 0.5
        - 🔵 **LONG_PRESENCE**: Person present for > 5 minutes
        """)
        
        # Sample alerts
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
    st.subheader("🔧 Processing Jobs")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔥 Spark Jobs")
        
        jobs = [
            {"name": "batch_vision_aggregator.py", "type": "Batch", 
             "desc": "Hourly/Daily aggregations"},
            {"name": "streaming_kafka_processor.py", "type": "Streaming",
             "desc": "CDC events from Kafka"},
            {"name": "streaming_vision_events.py", "type": "Streaming",
             "desc": "Real-time vision events"}
        ]
        
        for job in jobs:
            with st.expander(f"📄 {job['name']}"):
                st.markdown(f"**Type:** {job['type']}")
                st.markdown(f"**Description:** {job['desc']}")
                st.code(f"""
# Submit this job:
docker exec spark-master spark-submit \\
    --master spark://spark-master:7077 \\
    /opt/bitnami/spark/jobs/{job['name']}
                """, language="bash")
    
    with col2:
        st.markdown("#### 🌊 Flink Jobs")
        
        flink_jobs = [
            {"name": "stream_processor.py", "type": "Streaming",
             "desc": "Vision and CDC event processing"},
            {"name": "flink_sql_analytics.py", "type": "SQL",
             "desc": "Real-time SQL analytics"}
        ]
        
        for job in flink_jobs:
            with st.expander(f"📄 {job['name']}"):
                st.markdown(f"**Type:** {job['type']}")
                st.markdown(f"**Description:** {job['desc']}")
                st.code(f"""
# Run in demo mode:
cd homework3
python flink/jobs/{job['name']}

# Or with PyFlink:
USE_FLINK=true python flink/jobs/{job['name']}
                """, language="bash")
