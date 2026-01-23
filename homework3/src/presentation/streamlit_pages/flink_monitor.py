"""Streamlit page for Apache Flink cluster monitoring."""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from src.infrastructure.flink_client import FlinkClient


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


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human readable."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"


def get_state_icon(state: str) -> str:
    """Get icon for job state."""
    state_icons = {
        "RUNNING": "🟢",
        "FINISHED": "✅",
        "FAILED": "❌",
        "CANCELED": "🚫",
        "CANCELLING": "⏳",
        "CREATED": "🔵",
        "RESTARTING": "🔄"
    }
    return state_icons.get(state, "❓")


def render_flink_monitor(flink_client: Optional[FlinkClient]):
    """
    Render Flink monitoring dashboard page.
    
    Args:
        flink_client: FlinkClient instance for API calls
    """
    st.header("🌊 Apache Flink Monitor")
    st.markdown("Real-time monitoring of Flink cluster and streaming jobs")
    
    # Connection status check
    if not flink_client:
        st.error("❌ Flink client not initialized")
        st.info("""
        **To start Flink cluster:**
        ```bash
        cd mini_datalake_cdc_dvc
        docker compose up -d flink-jobmanager flink-taskmanager
        ```
        """)
        return
    
    # Refresh connection
    if st.button("🔄 Refresh Connection"):
        flink_client.refresh_connection()
        st.rerun()
    
    if not flink_client.is_connected:
        st.error("❌ Cannot connect to Flink JobManager")
        st.warning(f"Tried connecting to: `{flink_client.config.jobmanager_url}`")
        
        with st.expander("🔧 Troubleshooting"):
            st.markdown("""
            1. **Check if Flink is running:**
               ```bash
               docker ps | grep flink
               ```
            
            2. **Start Flink cluster:**
               ```bash
               cd mini_datalake_cdc_dvc
               docker compose up -d flink-jobmanager flink-taskmanager
               ```
            
            3. **Check Flink logs:**
               ```bash
               docker logs flink-jobmanager
               docker logs flink-taskmanager
               ```
            
            4. **Verify port mapping:**
               - Web UI: http://localhost:8092
               - RPC: localhost:6123
            """)
        return
    
    st.success("✅ Connected to Flink JobManager")
    
    # ============================================
    # Cluster Overview
    # ============================================
    st.subheader("📊 Cluster Overview")
    
    overview = flink_client.get_cluster_overview()
    
    if overview:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Flink Version",
                overview.get("flink_version", "Unknown"),
                help="Flink cluster version"
            )
        
        with col2:
            st.metric(
                "TaskManagers",
                overview.get("taskmanagers", 0),
                help="Number of TaskManagers"
            )
        
        with col3:
            slots_avail = overview.get("slots_available", 0)
            slots_total = overview.get("slots_total", 0)
            st.metric(
                "Slots",
                f"{slots_avail} / {slots_total}",
                help="Available / Total slots"
            )
        
        with col4:
            st.metric(
                "Running Jobs",
                overview.get("jobs_running", 0),
                help="Number of running jobs"
            )
        
        # Jobs summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Finished Jobs", overview.get("jobs_finished", 0))
        with col2:
            st.metric("🚫 Cancelled Jobs", overview.get("jobs_cancelled", 0))
        with col3:
            st.metric("❌ Failed Jobs", overview.get("jobs_failed", 0))
    
    st.divider()
    
    # ============================================
    # TaskManagers
    # ============================================
    st.subheader("🖥️ TaskManagers")
    
    taskmanagers = flink_client.get_taskmanagers()
    
    if taskmanagers:
        for tm in taskmanagers:
            with st.expander(f"TaskManager: `{tm.tm_id[:16]}...`"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"**Slots:** {tm.free_slots} / {tm.slots_number} free")
                    st.markdown(f"**Data Port:** {tm.data_port}")
                
                with col2:
                    st.markdown(f"**CPU Cores:** {tm.hardware_cpu_cores}")
                    st.markdown(f"**Physical Memory:** {format_bytes(tm.hardware_physical_memory)}")
                
                with col3:
                    heartbeat_sec = tm.time_since_heartbeat / 1000
                    st.markdown(f"**Last Heartbeat:** {heartbeat_sec:.1f}s ago")
                    st.markdown(f"**Path:** `{tm.path}`")
    else:
        st.info("No TaskManagers found")
    
    st.divider()
    
    # ============================================
    # Jobs
    # ============================================
    st.subheader("📋 Jobs")
    
    tab_running, tab_completed = st.tabs(["🟢 Running", "📜 All Jobs"])
    
    with tab_running:
        running_jobs = flink_client.get_jobs(status="running")
        
        if running_jobs:
            for job in running_jobs:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{job.name}**")
                        st.caption(f"ID: `{job.job_id}`")
                    
                    with col2:
                        st.markdown(f"{get_state_icon(job.state)} {job.state}")
                    
                    with col3:
                        st.markdown(f"⏱️ {format_duration(job.duration_ms)}")
                    
                    st.divider()
        else:
            st.info("No running jobs")
            st.markdown("Submit a job using the Flink CLI or REST API")
    
    with tab_completed:
        all_jobs = flink_client.get_jobs(status="all")
        
        if all_jobs:
            jobs_data = []
            for job in all_jobs:
                jobs_data.append({
                    "Job ID": job.job_id[:12] + "...",
                    "Name": job.name,
                    "State": f"{get_state_icon(job.state)} {job.state}",
                    "Duration": format_duration(job.duration_ms),
                    "Start Time": job.start_time.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            df = pd.DataFrame(jobs_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No jobs found")
    
    st.divider()
    
    # ============================================
    # Quick Actions
    # ============================================
    st.subheader("🚀 Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.link_button(
            "🌐 Open Flink UI",
            "http://localhost:8092",
            use_container_width=True
        )
    
    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
    
    with col3:
        if st.button("📋 Show Config", use_container_width=True):
            config = flink_client.get_cluster_config()
            if config:
                st.session_state["show_flink_config"] = True
    
    # Show config modal
    if st.session_state.get("show_flink_config", False):
        config = flink_client.get_cluster_config()
        with st.expander("🔧 Cluster Configuration", expanded=True):
            for key, value in list(config.items())[:20]:
                st.markdown(f"`{key}`: {value}")
            if len(config) > 20:
                st.caption(f"... and {len(config) - 20} more")
        st.session_state["show_flink_config"] = False
    
    # Job submission info
    with st.expander("📝 Submit Flink Job"):
        st.markdown("""
        **Using Flink CLI:**
        ```bash
        docker exec flink-jobmanager flink run \\
            -py /opt/flink/jobs/stream_processor.py
        ```
        
        **Using REST API:**
        ```bash
        curl -X POST http://localhost:8092/jars/upload \\
            -H "Content-Type: multipart/form-data" \\
            -F "jarfile=@your-job.jar"
        ```
        
        **Run Python job in demo mode:**
        ```bash
        cd homework3
        python flink/jobs/stream_processor.py
        ```
        """)
