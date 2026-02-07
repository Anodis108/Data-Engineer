"""Trang Giám sát CDC - Xem các Kafka topics và sự kiện CDC."""
import streamlit as st
import pandas as pd
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def render_cdc_monitor(kafka_client):
    """Hiển thị trang giám sát CDC."""
    
    st.header("🔄 Giám sát CDC")
    st.markdown("Xem các Kafka topics và sự kiện Change Data Capture từ Debezium")
    
    # Trạng thái kết nối
    is_connected = kafka_client and kafka_client.is_connected
    
    status_col, action_col = st.columns([3, 1])
    
    with status_col:
        if is_connected:
            st.success("🟢 Đã kết nối với Kafka broker")
        else:
            st.error("🔴 Kafka chưa kết nối")
            st.info("Đảm bảo Kafka đang chạy tại `localhost:9092`")
            return
    
    with action_col:
        if st.button("🔄 Làm mới"):
            st.rerun()
    
    st.divider()
    
    # Tổng quan topics
    tab_topics, tab_cdc, tab_messages = st.tabs([
        "📋 Tất cả Topics", "🔀 Topics CDC", "📨 Xem Tin nhắn"
    ])
    
    # === Tab 1: Tất cả Topics ===
    with tab_topics:
        _render_all_topics(kafka_client)
    
    # === Tab 2: Topics CDC ===
    with tab_cdc:
        _render_cdc_topics(kafka_client)
    
    # === Tab 3: Tin nhắn ===
    with tab_messages:
        _render_messages(kafka_client)


def _render_all_topics(kafka_client):
    """Hiển thị tất cả Kafka topics."""
    
    st.subheader("📋 Kafka Topics")
    
    topics = kafka_client.list_topics()
    
    if not topics:
        st.info("Không tìm thấy topic nào trong Kafka")
        return
    
    st.metric("Tổng số Topics", len(topics))
    
    # Danh sách topic
    topic_data = []
    for topic in topics:
        info = kafka_client.get_topic_info(topic)
        topic_data.append({
            "Topic": topic,
            "Partitions": info.get("partitions", "N/A") if info else "N/A",
            "Type": _categorize_topic(topic)
        })
    
    df = pd.DataFrame(topic_data)
    
    # Lọc theo loại
    types = df["Type"].unique().tolist()
    selected_type = st.multiselect(
        "Lọc theo loại",
        types,
        default=types
    )
    
    filtered_df = df[df["Type"].isin(selected_type)]
    
    st.dataframe(
        filtered_df,
        hide_index=True,
        column_config={
            "Topic": st.column_config.TextColumn("Tên Topic"),
            "Partitions": st.column_config.NumberColumn("Partitions"),
            "Type": st.column_config.TextColumn("Loại")
        }
    )


def _render_cdc_topics(kafka_client):
    """Hiển thị các topics CDC cụ thể."""
    
    st.subheader("🔀 Topics CDC (Debezium)")
    
    cdc_topics = kafka_client.get_cdc_topics()
    
    if not cdc_topics:
        st.info("Không tìm thấy topic CDC nào. Đảm bảo rằng Debezium connector đang chạy.")
        return
    
    st.success(f"Tìm thấy {len(cdc_topics)} topics CDC")
    
    for topic in cdc_topics:
        with st.expander(f"📌 {topic}"):
            info = kafka_client.get_topic_info(topic)
            
            if info:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Partitions", info.get("partitions", 0))
                with col2:
                    st.metric("Partition IDs", str(info.get("partition_ids", [])))
            
            # Hiển thị tin nhắn gần đây
            st.markdown("**Tin nhắn gần đây:**")
            
            messages = kafka_client.get_recent_messages(topic, max_messages=5)
            
            if messages:
                for msg in messages:
                    _render_cdc_event(msg)
            else:
                st.caption("Không có tin nhắn gần đây")


def _render_messages(kafka_client):
    """Hiển thị trình xem tin nhắn."""
    
    st.subheader("📨 Trình xem Tin nhắn")
    
    topics = kafka_client.list_topics()
    
    if not topics:
        st.warning("Không có topics khả dụng")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_topic = st.selectbox(
            "Chọn Topic",
            topics,
            index=0
        )
    
    with col2:
        max_messages = st.number_input(
            "Số tin nhắn tối đa",
            min_value=1,
            max_value=50,
            value=10
        )
    
    if st.button("📥 Lấy Tin nhắn", type="primary"):
        with st.spinner(f"Đang lấy từ {selected_topic}..."):
            messages = kafka_client.get_recent_messages(
                selected_topic,
                max_messages=max_messages
            )
            
            if messages:
                st.success(f"Đã lấy {len(messages)} tin nhắn")
                
                for i, msg in enumerate(messages):
                    with st.expander(
                        f"Tin nhắn #{i+1} | Offset: {msg.offset} | {msg.timestamp.strftime('%H:%M:%S')}",
                        expanded=(i == 0)
                    ):
                        _render_cdc_event(msg)
            else:
                st.info("Không tìm thấy tin nhắn nào trong topic")


def _render_cdc_event(event):
    """Hiển thị một sự kiện CDC đơn lẻ."""
    
    cols = st.columns(4)
    
    with cols[0]:
        st.caption("Thao tác")
        op_colors = {"INSERT": "🟢", "UPDATE": "🟡", "DELETE": "🔴", "READ": "⚪"}
        st.markdown(f"{op_colors.get(event.operation, '⚫')} **{event.operation}**")
    
    with cols[1]:
        st.caption("Bảng")
        st.markdown(f"`{event.source_table}`")
    
    with cols[2]:
        st.caption("Partition")
        st.markdown(f"{event.partition}")
    
    with cols[3]:
        st.caption("Offset")
        st.markdown(f"{event.offset}")
    
    # Dữ liệu Trước/Sau
    if event.operation in ["UPDATE", "DELETE"] and event.before:
        st.markdown("**Trước:**")
        st.json(event.before)
    
    if event.operation in ["INSERT", "UPDATE", "READ"] and event.after:
        st.markdown("**Sau:**")
        st.json(event.after)


def _categorize_topic(topic: str) -> str:
    """Phân loại topic theo tên."""
    if topic.startswith("__"): return "Internal"
    elif topic.startswith("connect_"): return "Connect"
    elif "." in topic: return "CDC"
    else: return "Application"
