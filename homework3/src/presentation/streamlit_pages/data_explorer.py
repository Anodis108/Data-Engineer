"""Trang Data Explorer - Duyệt MinIO buckets và xem trước tệp tin."""
import streamlit as st
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def render_data_explorer(minio_repo):
    """Hiển thị trang data lake explorer."""
    
    st.header("📁 Data Lake Explorer")
    st.markdown("Duyệt các bucket MinIO, xem các sự kiện và snapshot đã lưu trữ")
    
    if not minio_repo or not minio_repo.is_connected:
        st.error("❌ MinIO chưa kết nối. Vui lòng kiểm tra cấu hình.")
        st.info("Đảm bảo MinIO đang chạy tại `localhost:9000`")
        return
    
    # Lấy danh sách buckets
    buckets = minio_repo.list_buckets()
    
    if not buckets:
        st.warning("Không tìm thấy bucket nào trong MinIO")
        return
    
    # Sidebar để chọn bucket
    col_nav, col_content = st.columns([1, 3])
    
    with col_nav:
        st.subheader("🗂️ Điều hướng")
        
        # Chọn bucket
        selected_bucket = st.selectbox(
            "Chọn Bucket",
            buckets,
            index=0 if "lake" not in buckets else buckets.index("lake")
        )
        
        # Lấy thống kê bucket
        if st.button("📊 Làm mới Thống kê"):
            with st.spinner("Đang tính toán..."):
                stats = minio_repo.get_bucket_stats(selected_bucket)
                st.session_state[f"bucket_stats_{selected_bucket}"] = stats
        
        # Hiển thị thống kê nếu có
        stats_key = f"bucket_stats_{selected_bucket}"
        if stats_key in st.session_state:
            stats = st.session_state[stats_key]
            st.metric("Đối tượng", stats.get("object_count", 0))
            st.metric("Kích thước (MB)", stats.get("total_size_mb", 0))
        
        st.divider()
        
        # Nhập đường dẫn
        current_path = st.text_input(
            "Tiền tố đường dẫn",
            value="",
            placeholder="ví dụ: raw/events/"
        )
    
    with col_content:
        st.subheader(f"📂 {selected_bucket}{('/' + current_path) if current_path else ''}")
        
        # Liệt kê đối tượng
        objects = minio_repo.list_objects(
            prefix=current_path,
            bucket=selected_bucket,
            max_keys=100
        )
        
        if not objects:
            st.info("📭 Không tìm thấy đối tượng nào ở vị trí này")
            return
        
        # Tách thư mục và tệp tin
        folders = [o for o in objects if o.get("is_dir")]
        files = [o for o in objects if not o.get("is_dir")]
        
        # Hiển thị thư mục trước
        if folders:
            st.markdown("**📁 Thư mục**")
            folder_cols = st.columns(4)
            for i, folder in enumerate(folders):
                with folder_cols[i % 4]:
                    folder_name = folder["name"].rstrip("/").split("/")[-1]
                    if st.button(f"📁 {folder_name}", key=f"folder_{folder['name']}"):
                        st.session_state["explorer_path"] = folder["name"]
                        st.rerun()
        
        # Hiển thị tệp tin
        if files:
            st.markdown("**📄 Tệp tin**")
            
            # Tạo dataframe cho tệp tin
            file_data = []
            for f in files:
                name = f["name"].split("/")[-1]
                size_kb = f.get("size", 0) / 1024
                modified = f.get("last_modified", "")
                if modified:
                    modified = modified.strftime("%Y-%m-%d %H:%M") if hasattr(modified, 'strftime') else str(modified)
                
                file_data.append({
                    "Tên": name,
                    "Kích thước (KB)": round(size_kb, 2),
                    "Đã sửa đổi": modified,
                    "Đường dẫn đầy đủ": f["name"]
                })
            
            df = pd.DataFrame(file_data)
            
            # Chọn tệp tin
            selected_file = st.selectbox(
                "Chọn tệp tin để xem trước",
                options=df["Đường dẫn đầy đủ"].tolist(),
                format_func=lambda x: x.split("/")[-1]
            )
            
            # Hiển thị bảng tệp tin
            st.dataframe(
                df[["Tên", "Kích thước (KB)", "Đã sửa đổi"]],
                hide_index=True
            )
            
            # Phần xem trước
            if selected_file:
                st.divider()
                _preview_file(minio_repo, selected_bucket, selected_file)


def _preview_file(minio_repo, bucket, object_name):
    """Xem trước tệp tin dựa trên loại của nó."""
    
    file_name = object_name.split("/")[-1].lower()
    
    col_info, col_action = st.columns([3, 1])
    
    with col_info:
        st.markdown(f"**Xem trước:** `{object_name}`")
    
    with col_action:
        # Tạo liên kết tải xuống
        url = minio_repo.get_object_url(object_name, bucket)
        if url:
            st.link_button("⬇️ Tải xuống", url)
    
    # Xem trước dựa trên loại tệp tin
    if file_name.endswith(".parquet"):
        with st.spinner("Đang tải tệp Parquet..."):
            df = minio_repo.preview_parquet(object_name, bucket)
            if df is not None:
                st.success(f"✅ Đã tải {len(df)} hàng")
                
                # Hiển thị schema
                with st.expander("📋 Schema"):
                    schema_df = pd.DataFrame({
                        "Cột": df.columns,
                        "Loại": [str(df[col].dtype) for col in df.columns]
                    })
                    st.dataframe(schema_df, hide_index=True)
                
                # Hiển thị dữ liệu
                st.dataframe(df, hide_index=True)
            else:
                st.error("Không thể tải tệp Parquet")
    
    elif file_name.endswith((".jpg", ".jpeg", ".png", ".gif")):
        with st.spinner("Đang tải ảnh..."):
            content = minio_repo.get_object_content(object_name, bucket)
            if content:
                st.image(content, caption=file_name, use_column_width=True)
            else:
                st.error("Không thể tải ảnh")
    
    elif file_name.endswith(".json"):
        with st.spinner("Đang tải JSON..."):
            content = minio_repo.get_object_content(object_name, bucket)
            if content:
                import json
                # Phân tích và hiển thị JSON
                data = json.loads(content.decode("utf-8"))
                st.json(data)
            else:
                st.error("Không thể tải JSON")
    
    elif file_name.endswith((".txt", ".log", ".csv")):
        with st.spinner("Đang tải văn bản..."):
            content = minio_repo.get_object_content(object_name, bucket)
            if content:
                text = content.decode("utf-8", errors="replace")
                if file_name.endswith(".csv"):
                    # Phân tích và hiển thị CSV
                    import io
                    df = pd.read_csv(io.StringIO(text))
                    st.dataframe(df)
                else:
                    st.code(text[:5000])
            else:
                st.error("Không thể tải tệp tin")
    
    else:
        st.info(f"Xem trước không khả dụng cho loại tệp tin này. Sử dụng nút tải xuống.")
