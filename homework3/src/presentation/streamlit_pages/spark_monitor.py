"""Streamlit page for Apache Spark cluster monitoring."""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from src.infrastructure.spark_client import SparkClient


def format_duration(ms: int) -> str:
    """Format milliseconds to human readable duration."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    elif ms < 3600000:
        return f"{ms / 60000:.1f}m"
    else:
        return f"{ms / 3600000:.1f}h"


def format_memory(mb: int) -> str:
    """Format memory in MB to human readable."""
    if mb < 1024:
        return f"{mb} MB"
    else:
        return f"{mb / 1024:.1f} GB"


def render_spark_monitor(spark_client: Optional[SparkClient]):
    """
    Render Spark monitoring dashboard page.
    
    Args:
        spark_client: SparkClient instance for API calls
    """
    st.header("🔥 Apache Spark Monitor")
    st.markdown("Real-time monitoring of Spark cluster and applications")
    
    # Connection status check
    if not spark_client:
        st.error("❌ Spark client not initialized")
        st.info("""
        **To start Spark cluster:**
        ```bash
        cd mini_datalake_cdc_dvc
        docker compose up -d spark-master spark-worker
        ```
        """)
        return
    
    # Refresh connection
    if st.button("🔄 Refresh Connection"):
        spark_client.refresh_connection()
        st.rerun()
    
    if not spark_client.is_connected:
        st.error("❌ Cannot connect to Spark Master")
        st.warning(f"Tried connecting to: `{spark_client.config.master_url}`")
        
        with st.expander("🔧 Troubleshooting"):
            st.markdown("""
            1. **Check if Spark is running:**
               ```bash
               docker ps | grep spark
               ```
            
            2. **Start Spark cluster:**
               ```bash
               cd mini_datalake_cdc_dvc
               docker compose up -d spark-master spark-worker
               ```
            
            3. **Check Spark Master logs:**
               ```bash
               docker logs spark-master
               ```
            
            4. **Verify port mapping:**
               - Master UI: http://localhost:8090
               - Master RPC: spark://localhost:7077
            """)
        return
    
    st.success("✅ Connected to Spark Master")
    
    # ============================================
    # Cluster Overview
    # ============================================
    st.subheader("📊 Cluster Overview")
    
    cluster_info = spark_client.get_cluster_info()
    
    if cluster_info:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Status",
                cluster_info.get("status", "UNKNOWN"),
                help="Cluster status"
            )
        
        with col2:
            st.metric(
                "Workers",
                cluster_info.get("workers_alive", 0),
                help="Number of alive workers"
            )
        
        with col3:
            cores_used = cluster_info.get("cores_used", 0)
            cores_total = cluster_info.get("cores_total", 0)
            st.metric(
                "Cores",
                f"{cores_used} / {cores_total}",
                help="Cores in use / total"
            )
        
        with col4:
            mem_used = cluster_info.get("memory_used_mb", 0)
            mem_total = cluster_info.get("memory_total_mb", 0)
            st.metric(
                "Memory",
                f"{format_memory(mem_used)} / {format_memory(mem_total)}",
                help="Memory used / total"
            )
        
        # Apps summary
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Active Applications", cluster_info.get("active_apps", 0))
        with col2:
            st.metric("Completed Applications", cluster_info.get("completed_apps", 0))
    
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
                "State": w.state,
                "Cores": f"{w.cores_used} / {w.cores}",
                "Memory": f"{format_memory(w.memory_used)} / {format_memory(w.memory)}"
            })
        
        df = pd.DataFrame(workers_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No workers found")
    
    st.divider()
    
    # ============================================
    # Applications
    # ============================================
    st.subheader("📋 Applications")
    
    tab_running, tab_completed = st.tabs(["🟢 Running", "✅ Completed"])
    
    with tab_running:
        running_apps = spark_client.get_applications(status="running")
        
        if running_apps:
            apps_data = []
            for app in running_apps:
                apps_data.append({
                    "App ID": app.app_id,
                    "Name": app.name,
                    "State": "🟢 " + app.state,
                    "Duration": format_duration(app.duration_ms),
                    "Cores": app.cores
                })
            
            df = pd.DataFrame(apps_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No running applications")
    
    with tab_completed:
        completed_apps = spark_client.get_applications(status="completed")
        
        if completed_apps:
            apps_data = []
            for app in completed_apps[-10:]:  # Last 10
                apps_data.append({
                    "App ID": app.app_id,
                    "Name": app.name,
                    "State": "✅ " + app.state,
                    "Duration": format_duration(app.duration_ms)
                })
            
            df = pd.DataFrame(apps_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No completed applications")
    
    st.divider()
    
    # ============================================
    # Quick Actions
    # ============================================
    st.subheader("🚀 Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.link_button(
            "🌐 Open Spark UI",
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
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
    
    # Job submission info
    with st.expander("📝 Submit Spark Job"):
        st.markdown("""
        **Submit a batch job:**
        ```bash
        docker exec spark-master spark-submit \\
            --master spark://spark-master:7077 \\
            --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \\
            /opt/bitnami/spark/jobs/batch_vision_aggregator.py
        ```
        
        **Submit a streaming job:**
        ```bash
        docker exec spark-master spark-submit \\
            --master spark://spark-master:7077 \\
            --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \\
            /opt/bitnami/spark/jobs/streaming_kafka_processor.py
        ```
        """)
