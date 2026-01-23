"""Real-time Alerts Page - RabbitMQ consumer with live alerts feed."""
import streamlit as st
import pandas as pd
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def render_alerts(rabbitmq_pub):
    """Render the real-time alerts page."""
    
    st.header("🔔 Real-time Alerts")
    st.markdown("View alerts from RabbitMQ queues")
    
    # Connection status
    is_connected = rabbitmq_pub and rabbitmq_pub.is_connected
    
    status_col, action_col = st.columns([3, 1])
    
    with status_col:
        if is_connected:
            st.success(f"🟢 Connected to RabbitMQ | Exchange: `{rabbitmq_pub.exchange}`")
        else:
            st.error("🔴 RabbitMQ is not connected")
            st.info("Make sure RabbitMQ is running at `localhost:5672`")
            return
    
    with action_col:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    st.divider()
    
    # Alert queues info
    st.subheader("📬 Alert Queues")
    
    queues = [
        {"name": "q_person_present", "routing_key": "person.present", "description": "Person detected in zone"},
        {"name": "q_person_still_present", "routing_key": "person.still_present", "description": "Person still in zone (heartbeat)"},
        {"name": "q_person_left", "routing_key": "person.left", "description": "Person left the zone"},
    ]
    
    queue_cols = st.columns(3)
    
    for i, queue in enumerate(queues):
        with queue_cols[i]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-radius: 10px;
                padding: 18px;
                border-left: 4px solid {'#00ff88' if i == 0 else '#ffaa00' if i == 1 else '#ff4444'};
                min-height: 120px;
            ">
                <h4 style="margin: 0;">{queue['name']}</h4>
                <p style="color: #888; font-size: 11px; margin: 5px 0;">
                    Routing: <code>{queue['routing_key']}</code>
                </p>
                <p style="margin: 0; font-size: 12px;">{queue['description']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.divider()
    
    # Alert consumption logic
    st.subheader("📨 Alert Management")
    
    # Simulate alert history (stored in session state)
    if "alert_history" not in st.session_state:
        st.session_state.alert_history = []
    
    # Fetch real alerts from RabbitMQ
    new_alerts_count = 0
    for queue in queues:
        try:
            # We use a small limit to not hang the page, but enough to get recent activity
            payloads = rabbitmq_pub.consume_alerts(queue['name'], limit=50)
            for p in payloads:
                st.session_state.alert_history.append({
                    "timestamp": datetime.fromtimestamp(p.ts / 1000),
                    "event_type": p.event_type,
                    "routing_key": queue['routing_key'],
                    "status": "📥 Received (Real Data)"
                })
                new_alerts_count += 1
        except Exception as e:
            logger.error(f"Error fetching from {queue['name']}: {e}")
    
    if new_alerts_count > 0:
        st.toast(f"📥 Received {new_alerts_count} new alerts from RabbitMQ!", icon="🔔")
    
    st.divider()
    
    # Alert simulator
    st.markdown("**Test Alert Simulator:**")
    
    col_sim1, col_sim2, col_sim3 = st.columns(3)
    
    with col_sim1:
        if st.button("🟢 Person Present"):
            _publish_test_alert(rabbitmq_pub, "person_present_start", "person.present")
    
    with col_sim2:
        if st.button("🟡 Still Present"):
            _publish_test_alert(rabbitmq_pub, "person_still_present", "person.still_present")
    
    with col_sim3:
        if st.button("🔴 Person Left"):
            _publish_test_alert(rabbitmq_pub, "person_left", "person.left")
    
    # Alert history
    st.subheader("📜 Alert History")
    
    if st.session_state.alert_history:
        # Convert to DataFrame
        df = pd.DataFrame(st.session_state.alert_history)
        df = df.sort_values("timestamp", ascending=False)
        
        st.dataframe(
            df,
            hide_index=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn("Time", format="HH:mm:ss"),
                "event_type": st.column_config.TextColumn("Event Type"),
                "routing_key": st.column_config.TextColumn("Routing Key"),
                "status": st.column_config.TextColumn("Status")
            }
        )
        
        if st.button("🗑️ Clear History"):
            st.session_state.alert_history = []
            st.rerun()
    else:
        st.info("No alerts in history. Try the simulator above!")


def _publish_test_alert(rabbitmq_pub, event_type: str, routing_key: str):
    """Publish a test alert to RabbitMQ."""
    
    import uuid
    from src.domain.value_objects import AlertPayload
    
    try:
        payload = AlertPayload(
            event_id=str(uuid.uuid4()),
            camera_id="test_camera",
            ts=int(datetime.now().timestamp() * 1000),
            event_type=event_type,
            person_count=1,
            note="Test alert from Streamlit"
        )
        
        success = rabbitmq_pub.publish_alert(payload, routing_key)
        
        # Add to history
        st.session_state.alert_history.append({
            "timestamp": datetime.now(),
            "event_type": event_type,
            "routing_key": routing_key,
            "status": "✅ Published" if success else "❌ Failed"
        })
        
        if success:
            st.toast(f"✅ Published: {event_type}", icon="🔔")
        else:
            st.error("Failed to publish alert")
            
    except Exception as e:
        st.error(f"Error: {e}")
