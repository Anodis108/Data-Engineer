"""CDC Monitor Page - Kafka topics and CDC events viewer."""
import streamlit as st
import pandas as pd
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def render_cdc_monitor(kafka_client):
    """Render the CDC monitor page."""
    
    st.header("🔄 CDC Monitor")
    st.markdown("View Kafka topics and Change Data Capture events from Debezium")
    
    # Connection status
    is_connected = kafka_client and kafka_client.is_connected
    
    status_col, action_col = st.columns([3, 1])
    
    with status_col:
        if is_connected:
            st.success("🟢 Connected to Kafka broker")
        else:
            st.error("🔴 Kafka is not connected")
            st.info("Make sure Kafka is running at `localhost:9092`")
            return
    
    with action_col:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    st.divider()
    
    # Topics overview
    tab_topics, tab_cdc, tab_messages = st.tabs([
        "📋 All Topics", "🔀 CDC Topics", "📨 View Messages"
    ])
    
    # === Tab 1: All Topics ===
    with tab_topics:
        _render_all_topics(kafka_client)
    
    # === Tab 2: CDC Topics ===
    with tab_cdc:
        _render_cdc_topics(kafka_client)
    
    # === Tab 3: Messages ===
    with tab_messages:
        _render_messages(kafka_client)


def _render_all_topics(kafka_client):
    """Render all Kafka topics."""
    
    st.subheader("📋 Kafka Topics")
    
    topics = kafka_client.list_topics()
    
    if not topics:
        st.info("No topics found in Kafka")
        return
    
    st.metric("Total Topics", len(topics))
    
    # Topic list
    topic_data = []
    for topic in topics:
        info = kafka_client.get_topic_info(topic)
        topic_data.append({
            "Topic": topic,
            "Partitions": info.get("partitions", "N/A") if info else "N/A",
            "Type": _categorize_topic(topic)
        })
    
    df = pd.DataFrame(topic_data)
    
    # Filter by type
    types = df["Type"].unique().tolist()
    selected_type = st.multiselect(
        "Filter by Type",
        types,
        default=types
    )
    
    filtered_df = df[df["Type"].isin(selected_type)]
    
    st.dataframe(
        filtered_df,
        hide_index=True,
        column_config={
            "Topic": st.column_config.TextColumn("Topic Name"),
            "Partitions": st.column_config.NumberColumn("Partitions"),
            "Type": st.column_config.TextColumn("Type")
        }
    )


def _render_cdc_topics(kafka_client):
    """Render CDC-specific topics."""
    
    st.subheader("🔀 CDC Topics (Debezium)")
    
    cdc_topics = kafka_client.get_cdc_topics()
    
    if not cdc_topics:
        st.info("No CDC topics found. Make sure Debezium connector is running.")
        return
    
    st.success(f"Found {len(cdc_topics)} CDC topics")
    
    for topic in cdc_topics:
        with st.expander(f"📌 {topic}"):
            info = kafka_client.get_topic_info(topic)
            
            if info:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Partitions", info.get("partitions", 0))
                with col2:
                    st.metric("Partition IDs", str(info.get("partition_ids", [])))
            
            # Show recent messages
            st.markdown("**Recent Messages:**")
            
            messages = kafka_client.get_recent_messages(topic, max_messages=5)
            
            if messages:
                for msg in messages:
                    _render_cdc_event(msg)
            else:
                st.caption("No recent messages")


def _render_messages(kafka_client):
    """Render message viewer."""
    
    st.subheader("📨 Message Viewer")
    
    topics = kafka_client.list_topics()
    
    if not topics:
        st.warning("No topics available")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_topic = st.selectbox(
            "Select Topic",
            topics,
            index=0
        )
    
    with col2:
        max_messages = st.number_input(
            "Max Messages",
            min_value=1,
            max_value=50,
            value=10
        )
    
    if st.button("📥 Fetch Messages", type="primary"):
        with st.spinner(f"Fetching from {selected_topic}..."):
            messages = kafka_client.get_recent_messages(
                selected_topic,
                max_messages=max_messages
            )
            
            if messages:
                st.success(f"Fetched {len(messages)} messages")
                
                for i, msg in enumerate(messages):
                    with st.expander(
                        f"Message #{i+1} | Offset: {msg.offset} | {msg.timestamp.strftime('%H:%M:%S')}",
                        expanded=(i == 0)
                    ):
                        _render_cdc_event(msg)
            else:
                st.info("No messages found in topic")


def _render_cdc_event(event):
    """Render a single CDC event."""
    
    cols = st.columns(4)
    
    with cols[0]:
        st.caption("Operation")
        op_colors = {"INSERT": "🟢", "UPDATE": "🟡", "DELETE": "🔴", "READ": "⚪"}
        st.markdown(f"{op_colors.get(event.operation, '⚫')} **{event.operation}**")
    
    with cols[1]:
        st.caption("Table")
        st.markdown(f"`{event.source_table}`")
    
    with cols[2]:
        st.caption("Partition")
        st.markdown(f"{event.partition}")
    
    with cols[3]:
        st.caption("Offset")
        st.markdown(f"{event.offset}")
    
    # Before/After data
    if event.operation in ["UPDATE", "DELETE"] and event.before:
        st.markdown("**Before:**")
        st.json(event.before)
    
    if event.operation in ["INSERT", "UPDATE", "READ"] and event.after:
        st.markdown("**After:**")
        st.json(event.after)


def _categorize_topic(topic: str) -> str:
    """Categorize a topic by its name."""
    if topic.startswith("__"): return "Internal"
    elif topic.startswith("connect_"): return "Connect"
    elif "." in topic: return "CDC"
    else: return "Application"
