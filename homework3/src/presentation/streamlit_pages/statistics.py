"""Trang Bảng điều khiển Thống kê - Phân tích với các truy vấn Trino và biểu đồ."""
import streamlit as st
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def render_statistics(trino_client, minio_repo):
    """Hiển thị trang bảng điều khiển thống kê."""
    
    st.header("📈 Bảng Thống kê")
    st.markdown("Phân tích và thông tin chi tiết từ dữ liệu sự kiện thị giác")
    
    # Kiểm tra kết nối
    trino_connected = trino_client and trino_client.is_connected
    minio_connected = minio_repo and minio_repo.is_connected
    
    # Hàng trạng thái
    status_cols = st.columns(4)
    with status_cols[0]:
        st.metric("Trino", "🟢 Đã kết nối" if trino_connected else "🔴 Ngoại tuyến")
    with status_cols[1]:
        st.metric("MinIO", "🟢 Đã kết nối" if minio_connected else "🔴 Ngoại tuyến")
    
    st.divider()
    
    # Layout dựa trên Tab
    tab_overview, tab_events, tab_query = st.tabs([
        "📊 Tổng quan", "📅 Dòng thời gian Sự kiện", "🔍 Truy vấn Tùy chỉnh"
    ])
    
    # === Tab 1: Tổng quan ===
    with tab_overview:
        _render_overview(trino_client, minio_repo, trino_connected, minio_connected)
    
    # === Tab 2: Dòng thời gian Sự kiện ===
    with tab_events:
        _render_event_timeline(trino_client, trino_connected)
    
    # === Tab 3: Truy vấn Tùy chỉnh ===
    with tab_query:
        _render_custom_query(trino_client, trino_connected)


def _render_overview(trino_client, minio_repo, trino_connected, minio_connected):
    """Hiển thị thống kê tổng quan."""
    
    st.subheader("📊 Tổng quan Hệ thống")
    
    # Thống kê lưu trữ từ MinIO
    if minio_connected:
        st.markdown("### 💾 Thống kê Lưu trữ")
        
        buckets = minio_repo.list_buckets()
        bucket_cols = st.columns(len(buckets) if buckets else 1)
        
        for i, bucket in enumerate(buckets[:4]):  # Giới hạn 4 buckets
            with bucket_cols[i]:
                with st.spinner(f"Đang tải {bucket}..."):
                    stats = minio_repo.get_bucket_stats(bucket)
                    
                    st.metric(
                        label=f"🗂️ {bucket}",
                        value=f"{stats.get('object_count', 0)} objects",
                        delta=f"{stats.get('total_size_mb', 0)} MB"
                    )
    
    # Thống kê sự kiện từ Trino
    if trino_connected:
        st.markdown("### 📊 Thống kê Sự kiện")
        
        with st.spinner("Đang tải thống kê sự kiện..."):
            stats_df = trino_client.get_event_statistics()
            
            if stats_df is not None and not stats_df.empty:
                # Các chỉ số tóm tắt
                metric_cols = st.columns(4)
                
                total_events = stats_df["event_count"].sum()
                avg_persons = stats_df["avg_person_count"].mean()
                avg_conf = stats_df["avg_confidence"].mean()
                cameras = stats_df["camera_id"].nunique()
                
                with metric_cols[0]:
                    st.metric("Tổng Sự kiện", int(total_events))
                with metric_cols[1]:
                    st.metric("Số người TB/Sự kiện", f"{avg_persons:.1f}")
                with metric_cols[2]:
                    st.metric("Độ tin cậy TB", f"{avg_conf:.2%}")
                with metric_cols[3]:
                    st.metric("Camera Hoạt động", cameras)
                
                # Phân bố loại sự kiện
                st.markdown("#### Phân bố Loại Sự kiện")
                
                event_type_df = stats_df.groupby("event_type")["event_count"].sum().reset_index()
                
                # Biểu đồ cột
                st.bar_chart(
                    event_type_df.set_index("event_type")
                )
                
                # Bảng chi tiết
                st.dataframe(stats_df, hide_index=True)
            else:
                st.info("Không có dữ liệu sự kiện. Hãy bắt đầu phát hiện để tạo sự kiện.")
    else:
        st.warning("Trino chưa kết nối. Thống kê sự kiện không khả dụng.")


def _render_event_timeline(trino_client, trino_connected):
    """Hiển thị biểu đồ dòng thời gian sự kiện."""
    
    st.subheader("📅 Dòng thời gian Sự kiện")
    
    if not trino_connected:
        st.warning("Trino chưa kết nối")
        return
    
    # Bộ lọc
    col_filters = st.columns(3)
    
    with col_filters[0]:
        camera_filter = st.text_input("Camera ID (tùy chọn)", "")
    
    with col_filters[1]:
        time_range = st.selectbox(
            "Khoảng Thời gian",
            ["24 Giờ qua", "7 Ngày qua", "30 Ngày qua", "Tất cả"],
            index=0
        )
    
    with col_filters[2]:
        if st.button("🔄 Làm mới"):
            st.rerun()
    
    # Lấy dữ liệu
    with st.spinner("Đang tải dữ liệu dòng thời gian..."):
        events_df = trino_client.get_events_by_hour(
            camera_id=camera_filter if camera_filter else None
        )
        
        if events_df is not None and not events_df.empty:
            # Chuyển đổi cột giờ sang datetime nếu cần
            if "hour" in events_df.columns:
                events_df["hour"] = pd.to_datetime(events_df["hour"])
            
            # Pivot cho biểu đồ xếp chồng
            pivot_df = events_df.pivot_table(
                index="hour",
                columns="event_type",
                values="event_count",
                aggfunc="sum",
                fill_value=0
            )
            
            # Biểu đồ đường
            st.line_chart(pivot_df)
            
            # Tóm tắt
            st.markdown("#### Tóm tắt Sự kiện Gần đây")
            st.dataframe(
                events_df.head(50),
                hide_index=True
            )
        else:
            st.info("Không có dữ liệu dòng thời gian")
    
    # Bảng sự kiện gần đây
    st.markdown("### 📋 Sự kiện Gần đây")
    
    with st.spinner("Đang tải sự kiện gần đây..."):
        recent_df = trino_client.get_recent_events(limit=20)
        
        if recent_df is not None and not recent_df.empty:
            st.dataframe(
                recent_df,
                hide_index=True,
                column_config={
                    "frame_uri": st.column_config.LinkColumn("Frame URI")
                }
            )
        else:
            st.info("Không tìm thấy sự kiện nào")


def _render_custom_query(trino_client, trino_connected):
    """Hiển thị giao diện truy vấn SQL tùy chỉnh."""
    
    st.subheader("🔍 Truy vấn SQL Tùy chỉnh")
    
    if not trino_connected:
        st.warning("Trino chưa kết nối")
        return
    
    # Các truy vấn mẫu
    st.markdown("**Các truy vấn mẫu:**")
    
    examples = {
        "Hiển thị schemas": "SHOW SCHEMAS FROM hive",
        "Hiển thị bảng": "SHOW TABLES FROM raw",
        "Số lượng sự kiện theo camera": """
SELECT camera_id, COUNT(*) as event_count 
FROM raw.vision_events 
GROUP BY camera_id
""",
        "Độ tin cậy trung bình theo loại sự kiện": """
SELECT event_type, AVG(conf_avg) as avg_confidence, COUNT(*) as count
FROM raw.vision_events
GROUP BY event_type
""",
        "Sự kiện gần đây": """
SELECT event_id, camera_id, event_type, person_count, ts_start
FROM raw.vision_events
ORDER BY ts_start DESC
LIMIT 10
"""
    }
    
    selected_example = st.selectbox(
        "Tải truy vấn mẫu",
        ["-- Chọn --"] + list(examples.keys())
    )
    
    default_query = examples.get(selected_example, "")
    
    # Trình chỉnh sửa truy vấn
    query = st.text_area(
        "Truy vấn SQL",
        value=default_query,
        height=150,
        placeholder="Nhập truy vấn Trino SQL của bạn ở đây..."
    )
    
    col_run, col_info = st.columns([1, 3])
    
    with col_run:
        run_query = st.button("▶️ Chạy Truy vấn", type="primary")
    
    with col_info:
        st.caption("Các truy vấn được thực thi trên catalog Trino hive")
    
    # Thực thi truy vấn
    if run_query and query.strip():
        with st.spinner("Đang thực thi truy vấn..."):
            # Thực thi truy vấn với Trino
            result = trino_client.execute_query(query)
            
            if result is not None:
                st.success(f"✅ Truy vấn trả về {len(result)} hàng")
                st.dataframe(result, hide_index=True)
                
                # Nút tải xuống
                csv = result.to_csv(index=False)
                st.download_button(
                    "⬇️ Tải xuống CSV",
                    csv,
                    "query_result.csv",
                    "text/csv"
                )
            else:
                st.warning("Truy vấn không trả về kết quả nào")
