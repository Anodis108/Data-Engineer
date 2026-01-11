"""Data Explorer Page - Browse MinIO buckets and preview files."""
import streamlit as st
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def render_data_explorer(minio_repo):
    """Render the data lake explorer page."""
    
    st.header("📁 Data Lake Explorer")
    st.markdown("Browse MinIO buckets, view stored events and snapshots")
    
    if not minio_repo or not minio_repo.is_connected:
        st.error("❌ MinIO is not connected. Please check your configuration.")
        st.info("Make sure MinIO is running at `localhost:9000`")
        return
    
    # Get available buckets
    buckets = minio_repo.list_buckets()
    
    if not buckets:
        st.warning("No buckets found in MinIO")
        return
    
    # Sidebar for bucket selection
    col_nav, col_content = st.columns([1, 3])
    
    with col_nav:
        st.subheader("🗂️ Navigation")
        
        # Bucket selector
        selected_bucket = st.selectbox(
            "Select Bucket",
            buckets,
            index=0 if "lake" not in buckets else buckets.index("lake")
        )
        
        # Get bucket stats
        if st.button("📊 Refresh Stats"):
            with st.spinner("Calculating..."):
                stats = minio_repo.get_bucket_stats(selected_bucket)
                st.session_state[f"bucket_stats_{selected_bucket}"] = stats
        
        # Display stats if available
        stats_key = f"bucket_stats_{selected_bucket}"
        if stats_key in st.session_state:
            stats = st.session_state[stats_key]
            st.metric("Objects", stats.get("object_count", 0))
            st.metric("Size (MB)", stats.get("total_size_mb", 0))
        
        st.divider()
        
        # Path input
        current_path = st.text_input(
            "Path Prefix",
            value="",
            placeholder="e.g., raw/events/"
        )
    
    with col_content:
        st.subheader(f"📂 {selected_bucket}{('/' + current_path) if current_path else ''}")
        
        # List objects
        objects = minio_repo.list_objects(
            prefix=current_path,
            bucket=selected_bucket,
            max_keys=100
        )
        
        if not objects:
            st.info("📭 No objects found in this location")
            return
        
        # Separate folders and files
        folders = [o for o in objects if o.get("is_dir")]
        files = [o for o in objects if not o.get("is_dir")]
        
        # Display folders first
        if folders:
            st.markdown("**📁 Folders**")
            folder_cols = st.columns(4)
            for i, folder in enumerate(folders):
                with folder_cols[i % 4]:
                    folder_name = folder["name"].rstrip("/").split("/")[-1]
                    if st.button(f"📁 {folder_name}", key=f"folder_{folder['name']}"):
                        st.session_state["explorer_path"] = folder["name"]
                        st.rerun()
        
        # Display files
        if files:
            st.markdown("**📄 Files**")
            
            # Create dataframe for files
            file_data = []
            for f in files:
                name = f["name"].split("/")[-1]
                size_kb = f.get("size", 0) / 1024
                modified = f.get("last_modified", "")
                if modified:
                    modified = modified.strftime("%Y-%m-%d %H:%M") if hasattr(modified, 'strftime') else str(modified)
                
                file_data.append({
                    "Name": name,
                    "Size (KB)": round(size_kb, 2),
                    "Modified": modified,
                    "Full Path": f["name"]
                })
            
            df = pd.DataFrame(file_data)
            
            # File selection
            selected_file = st.selectbox(
                "Select file to preview",
                options=df["Full Path"].tolist(),
                format_func=lambda x: x.split("/")[-1]
            )
            
            # Display file table
            st.dataframe(
                df[["Name", "Size (KB)", "Modified"]],
                hide_index=True
            )
            
            # Preview section
            if selected_file:
                st.divider()
                _preview_file(minio_repo, selected_bucket, selected_file)


def _preview_file(minio_repo, bucket, object_name):
    """Preview a file based on its type."""
    
    file_name = object_name.split("/")[-1].lower()
    
    col_info, col_action = st.columns([3, 1])
    
    with col_info:
        st.markdown(f"**Preview:** `{object_name}`")
    
    with col_action:
        # Generate download link
        url = minio_repo.get_object_url(object_name, bucket)
        if url:
            st.link_button("⬇️ Download", url)
    
    # Preview based on file type
    if file_name.endswith(".parquet"):
        with st.spinner("Loading Parquet file..."):
            df = minio_repo.preview_parquet(object_name, bucket)
            if df is not None:
                st.success(f"✅ Loaded {len(df)} rows")
                
                # Show schema
                with st.expander("📋 Schema"):
                    schema_df = pd.DataFrame({
                        "Column": df.columns,
                        "Type": [str(df[col].dtype) for col in df.columns]
                    })
                    st.dataframe(schema_df, hide_index=True)
                
                # Show data
                st.dataframe(df, hide_index=True)
            else:
                st.error("Failed to load Parquet file")
    
    elif file_name.endswith((".jpg", ".jpeg", ".png", ".gif")):
        with st.spinner("Loading image..."):
            content = minio_repo.get_object_content(object_name, bucket)
            if content:
                st.image(content, caption=file_name, use_column_width=True)
            else:
                st.error("Failed to load image")
    
    elif file_name.endswith(".json"):
        with st.spinner("Loading JSON..."):
            content = minio_repo.get_object_content(object_name, bucket)
            if content:
                import json
                try:
                    data = json.loads(content.decode("utf-8"))
                    st.json(data)
                except json.JSONDecodeError:
                    st.code(content.decode("utf-8"), language="json")
            else:
                st.error("Failed to load JSON")
    
    elif file_name.endswith((".txt", ".log", ".csv")):
        with st.spinner("Loading text file..."):
            content = minio_repo.get_object_content(object_name, bucket)
            if content:
                text = content.decode("utf-8", errors="replace")
                if file_name.endswith(".csv"):
                    try:
                        import io
                        df = pd.read_csv(io.StringIO(text))
                        st.dataframe(df)
                    except Exception:
                        st.code(text[:5000])
                else:
                    st.code(text[:5000])
            else:
                st.error("Failed to load file")
    
    else:
        st.info(f"Preview not available for this file type. Use download button.")
