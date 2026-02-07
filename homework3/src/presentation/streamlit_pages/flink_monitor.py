"""Trang Streamlit để giám sát cụm Apache Flink."""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from src.infrastructure.flink_client import FlinkClient


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


def format_bytes(bytes_val: int) -> str:
    """Định dạng bytes thành chuỗi dễ đọc."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"


def get_state_icon(state: str) -> str:
    """Lấy biểu tượng cho trạng thái công việc."""
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
    Hiển thị trang giám sát Flink.
    
    Args:
        flink_client: FlinkClient instance để gọi API
    """
    st.header("🌊 Giám sát Apache Flink")
    st.markdown("Giám sát thời gian thực cụm Flink và các streaming jobs")
    
    # Kiểm tra trạng thái kết nối
    if not flink_client:
        st.error("❌ Flink client chưa được khởi tạo")
        st.info("""
        **Để khởi động cụm Flink:**
        ```bash
        cd mini_datalake_cdc_dvc
        docker compose up -d flink-jobmanager flink-taskmanager
        ```
        """)
        return
    
    # Làm mới kết nối
    if st.button("🔄 Làm mới Kết nối"):
        flink_client.refresh_connection()
        st.rerun()
    
    if not flink_client.is_connected:
        st.error("❌ Không thể kết nối với Flink JobManager")
        st.warning(f"Đã thử kết nối tới: `{flink_client.config.jobmanager_url}`")
        
        with st.expander("🔧 Khắc phục sự cố"):
            st.markdown("""
            1. **Kiểm tra xem Flink có đang chạy không:**
               ```bash
               docker ps | grep flink
               ```
            
            2. **Khởi động cụm Flink:**
               ```bash
               cd mini_datalake_cdc_dvc
               docker compose up -d flink-jobmanager flink-taskmanager
               ```
            
            3. **Kiểm tra logs của Flink:**
               ```bash
               docker logs flink-jobmanager
               docker logs flink-taskmanager
               ```
            
            4. **Xác minh ánh xạ cổng:**
               - Web UI: http://localhost:8092
               - RPC: localhost:6123
            """)
        return
    
    st.success("✅ Đã kết nối với Flink JobManager")
    
    # ============================================
    # Tổng quan Cụm
    # ============================================
    st.subheader("📊 Tổng quan Cụm")
    
    overview = flink_client.get_cluster_overview()
    
    if overview:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Phiên bản Flink",
                overview.get("flink_version", "Không xác định"),
                help="Phiên bản cụm Flink"
            )
        
        with col2:
            st.metric(
                "TaskManagers",
                overview.get("taskmanagers", 0),
                help="Số lượng TaskManagers"
            )
        
        with col3:
            slots_avail = overview.get("slots_available", 0)
            slots_total = overview.get("slots_total", 0)
            st.metric(
                "Slots",
                f"{slots_avail} / {slots_total}",
                help="Slots khả dụng / Tổng số slots"
            )
        
        with col4:
            st.metric(
                "Jobs đang chạy",
                overview.get("jobs_running", 0),
                help="Số lượng jobs đang chạy"
            )
        
        # Tóm tắt Jobs
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Jobs đã hoàn thành", overview.get("jobs_finished", 0))
        with col2:
            st.metric("🚫 Jobs đã hủy", overview.get("jobs_cancelled", 0))
        with col3:
            st.metric("❌ Jobs thất bại", overview.get("jobs_failed", 0))
    
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
                    st.markdown(f"**Slots:** {tm.free_slots} / {tm.slots_number} trống")
                    st.markdown(f"**Cổng dữ liệu:** {tm.data_port}")
                
                with col2:
                    st.markdown(f"**CPU Cores:** {tm.hardware_cpu_cores}")
                    st.markdown(f"**Bộ nhớ vật lý:** {format_bytes(tm.hardware_physical_memory)}")
                
                with col3:
                    heartbeat_sec = tm.time_since_heartbeat / 1000
                    st.markdown(f"**Nhịp tim cuối:** {heartbeat_sec:.1f}s trước")
                    st.markdown(f"**Đường dẫn:** `{tm.path}`")
    else:
        st.info("Không tìm thấy TaskManagers nào")
    
    st.divider()
    
    # ============================================
    # Jobs
    # ============================================
    st.subheader("📋 Jobs")
    
    tab_running, tab_completed = st.tabs(["🟢 Đang chạy", "📜 Tất cả Jobs"])
    
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
            st.info("Không có jobs đang chạy")
            st.markdown("Gửi một job sử dụng Flink CLI hoặc REST API")
    
    with tab_completed:
        all_jobs = flink_client.get_jobs(status="all")
        
        if all_jobs:
            jobs_data = []
            for job in all_jobs:
                jobs_data.append({
                    "Job ID": job.job_id[:12] + "...",
                    "Tên": job.name,
                    "Trạng thái": f"{get_state_icon(job.state)} {job.state}",
                    "Thời lượng": format_duration(job.duration_ms),
                    "Thời gian bắt đầu": job.start_time.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            df = pd.DataFrame(jobs_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Không tìm thấy jobs nào")
    
    st.divider()
    
    # ============================================
    # Thao tác nhanh
    # ============================================
    st.subheader("🚀 Thao tác nhanh")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.link_button(
            "🌐 Mở Flink UI",
            "http://localhost:8092",
            use_container_width=True
        )
    
    with col2:
        if st.button("🔄 Làm mới Dữ liệu", use_container_width=True):
            st.rerun()
    
    with col3:
        if st.button("📋 Hiện Cấu hình", use_container_width=True):
            config = flink_client.get_cluster_config()
            if config:
                st.session_state["show_flink_config"] = True
    
    # Hiện modal cấu hình
    if st.session_state.get("show_flink_config", False):
        config = flink_client.get_cluster_config()
        with st.expander("🔧 Cấu hình Cụm", expanded=True):
            for key, value in list(config.items())[:20]:
                st.markdown(f"`{key}`: {value}")
            if len(config) > 20:
                st.caption(f"... và {len(config) - 20} mục khác")
        st.session_state["show_flink_config"] = False
    
    # Thông tin gửi job
    with st.expander("📝 Gửi Flink Job"):
        st.markdown("""
        **Sử dụng Flink CLI:**
        ```bash
        docker exec flink-jobmanager flink run \\
            -py /opt/flink/jobs/stream_processor.py
        ```
        
        **Sử dụng REST API:**
        ```bash
        curl -X POST http://localhost:8092/jars/upload \\
            -H "Content-Type: multipart/form-data" \\
            -F "jarfile=@your-job.jar"
        ```
        
        **Chạy Python job ở chế độ demo:**
        ```bash
        cd homework3
        python flink/jobs/stream_processor.py
        ```
        """)
