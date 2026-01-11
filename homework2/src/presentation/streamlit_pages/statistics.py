"""Statistics Dashboard Page - Analytics with Trino queries and charts."""
import streamlit as st
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def render_statistics(trino_client, minio_repo):
    """Render the statistics dashboard page."""
    
    st.header("📈 Statistics Dashboard")
    st.markdown("Analytics and insights from your vision events data")
    
    # Check connections
    trino_connected = trino_client and trino_client.is_connected
    minio_connected = minio_repo and minio_repo.is_connected
    
    # Status row
    status_cols = st.columns(4)
    with status_cols[0]:
        st.metric("Trino", "🟢 Connected" if trino_connected else "🔴 Offline")
    with status_cols[1]:
        st.metric("MinIO", "🟢 Connected" if minio_connected else "🔴 Offline")
    
    st.divider()
    
    # Tab-based layout
    tab_overview, tab_events, tab_query = st.tabs([
        "📊 Overview", "📅 Event Timeline", "🔍 Custom Query"
    ])
    
    # === Tab 1: Overview ===
    with tab_overview:
        _render_overview(trino_client, minio_repo, trino_connected, minio_connected)
    
    # === Tab 2: Event Timeline ===
    with tab_events:
        _render_event_timeline(trino_client, trino_connected)
    
    # === Tab 3: Custom Query ===
    with tab_query:
        _render_custom_query(trino_client, trino_connected)


def _render_overview(trino_client, minio_repo, trino_connected, minio_connected):
    """Render overview statistics."""
    
    st.subheader("📊 System Overview")
    
    # Storage stats from MinIO
    if minio_connected:
        st.markdown("### 💾 Storage Statistics")
        
        buckets = minio_repo.list_buckets()
        bucket_cols = st.columns(len(buckets) if buckets else 1)
        
        for i, bucket in enumerate(buckets[:4]):  # Limit to 4 buckets
            with bucket_cols[i]:
                with st.spinner(f"Loading {bucket}..."):
                    stats = minio_repo.get_bucket_stats(bucket)
                    
                    st.metric(
                        label=f"🗂️ {bucket}",
                        value=f"{stats.get('object_count', 0)} objects",
                        delta=f"{stats.get('total_size_mb', 0)} MB"
                    )
    
    # Event stats from Trino
    if trino_connected:
        st.markdown("### 📊 Event Statistics")
        
        with st.spinner("Loading event statistics..."):
            stats_df = trino_client.get_event_statistics()
            
            if stats_df is not None and not stats_df.empty:
                # Summary metrics
                metric_cols = st.columns(4)
                
                total_events = stats_df["event_count"].sum()
                avg_persons = stats_df["avg_person_count"].mean()
                avg_conf = stats_df["avg_confidence"].mean()
                cameras = stats_df["camera_id"].nunique()
                
                with metric_cols[0]:
                    st.metric("Total Events", int(total_events))
                with metric_cols[1]:
                    st.metric("Avg Persons/Event", f"{avg_persons:.1f}")
                with metric_cols[2]:
                    st.metric("Avg Confidence", f"{avg_conf:.2%}")
                with metric_cols[3]:
                    st.metric("Active Cameras", cameras)
                
                # Event type distribution
                st.markdown("#### Event Type Distribution")
                
                event_type_df = stats_df.groupby("event_type")["event_count"].sum().reset_index()
                
                # Bar chart
                st.bar_chart(
                    event_type_df.set_index("event_type")
                )
                
                # Detailed table
                st.dataframe(stats_df, hide_index=True)
            else:
                st.info("No event data available. Start detection to generate events.")
    else:
        st.warning("Trino is not connected. Event statistics unavailable.")


def _render_event_timeline(trino_client, trino_connected):
    """Render event timeline chart."""
    
    st.subheader("📅 Event Timeline")
    
    if not trino_connected:
        st.warning("Trino is not connected")
        return
    
    # Filters
    col_filters = st.columns(3)
    
    with col_filters[0]:
        camera_filter = st.text_input("Camera ID (optional)", "")
    
    with col_filters[1]:
        time_range = st.selectbox(
            "Time Range",
            ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
            index=0
        )
    
    with col_filters[2]:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    # Get data
    with st.spinner("Loading timeline data..."):
        events_df = trino_client.get_events_by_hour(
            camera_id=camera_filter if camera_filter else None
        )
        
        if events_df is not None and not events_df.empty:
            # Convert hour column to datetime if needed
            if "hour" in events_df.columns:
                events_df["hour"] = pd.to_datetime(events_df["hour"])
            
            # Pivot for stacked chart
            pivot_df = events_df.pivot_table(
                index="hour",
                columns="event_type",
                values="event_count",
                aggfunc="sum",
                fill_value=0
            )
            
            # Line chart
            st.line_chart(pivot_df)
            
            # Summary
            st.markdown("#### Recent Events Summary")
            st.dataframe(
                events_df.head(50),
                hide_index=True
            )
        else:
            st.info("No timeline data available")
    
    # Recent events table
    st.markdown("### 📋 Recent Events")
    
    with st.spinner("Loading recent events..."):
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
            st.info("No recent events found")


def _render_custom_query(trino_client, trino_connected):
    """Render custom SQL query interface."""
    
    st.subheader("🔍 Custom SQL Query")
    
    if not trino_connected:
        st.warning("Trino is not connected")
        return
    
    # Example queries
    st.markdown("**Example Queries:**")
    
    examples = {
        "Show schemas": "SHOW SCHEMAS FROM hive",
        "Show tables": "SHOW TABLES FROM raw",
        "Event count by camera": """
SELECT camera_id, COUNT(*) as event_count 
FROM raw.vision_events 
GROUP BY camera_id
""",
        "Average confidence by event type": """
SELECT event_type, AVG(conf_avg) as avg_confidence, COUNT(*) as count
FROM raw.vision_events
GROUP BY event_type
""",
        "Recent events": """
SELECT event_id, camera_id, event_type, person_count, ts_start
FROM raw.vision_events
ORDER BY ts_start DESC
LIMIT 10
"""
    }
    
    selected_example = st.selectbox(
        "Load example query",
        ["-- Select --"] + list(examples.keys())
    )
    
    default_query = examples.get(selected_example, "")
    
    # Query editor
    query = st.text_area(
        "SQL Query",
        value=default_query,
        height=150,
        placeholder="Enter your Trino SQL query here..."
    )
    
    col_run, col_info = st.columns([1, 3])
    
    with col_run:
        run_query = st.button("▶️ Run Query", type="primary")
    
    with col_info:
        st.caption("Queries execute against Trino hive catalog")
    
    # Execute query
    if run_query and query.strip():
        with st.spinner("Executing query..."):
            try:
                result = trino_client.execute_query(query)
                
                if result is not None:
                    st.success(f"✅ Query returned {len(result)} rows")
                    st.dataframe(result, hide_index=True)
                    
                    # Download button
                    csv = result.to_csv(index=False)
                    st.download_button(
                        "⬇️ Download CSV",
                        csv,
                        "query_result.csv",
                        "text/csv"
                    )
                else:
                    st.warning("Query returned no results")
                    
            except Exception as e:
                st.error(f"Query error: {e}")
