"""Trang Cảnh báo Thời gian thực - RabbitMQ consumer với luồng cảnh báo trực tiếp."""
import streamlit as st
import pandas as pd
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def render_alerts(rabbitmq_pub):
    """Hiển thị trang cảnh báo thời gian thực."""
    
    st.header("🔔 Cảnh báo Thời gian thực")
    st.markdown("Xem cảnh báo từ hàng đợi RabbitMQ")
    
    # Trạng thái kết nối
    is_connected = rabbitmq_pub and rabbitmq_pub.is_connected
    
    status_col, action_col = st.columns([3, 1])
    
    with status_col:
        if is_connected:
            st.success(f"🟢 Đã kết nối với RabbitMQ | Exchange: `{rabbitmq_pub.exchange}`")
        else:
            st.error("🔴 RabbitMQ chưa kết nối")
            st.info("Đảm bảo RabbitMQ đang chạy tại `localhost:5672`")
            return
    
    with action_col:
        if st.button("🔄 Làm mới"):
            st.rerun()
    
    st.divider()
    
    # Thông tin hàng đợi cảnh báo
    st.subheader("📬 Hàng đợi Cảnh báo")
    
    queues = [
        {"name": "q_person_present", "routing_key": "person.present", "description": "Phát hiện người trong vùng cấm"},
        {"name": "q_person_still_present", "routing_key": "person.still_present", "description": "Người vẫn ở trong vùng cấm (heartbeat)"},
        {"name": "q_person_left", "routing_key": "person.left", "description": "Người đã rời khỏi vùng cấm"},
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
    
    # Logic tiêu thụ cảnh báo
    st.subheader("📨 Quản lý Cảnh báo")
    
    # Mô phỏng lịch sử cảnh báo (lưu trong session state)
    if "alert_history" not in st.session_state:
        st.session_state.alert_history = []
    
    # Lấy cảnh báo thực từ RabbitMQ
    new_alerts_count = 0
    for queue in queues:
        # Lấy cảnh báo từ queue
        # Sử dụng giới hạn nhỏ để không làm treo trang, nhưng đủ để lấy hoạt động gần đây
        payloads = rabbitmq_pub.consume_alerts(queue['name'], limit=50)
        for p in payloads:
            st.session_state.alert_history.append({
                "timestamp": datetime.fromtimestamp(p.ts / 1000),
                "event_type": p.event_type,
                "routing_key": queue['routing_key'],
                "status": "📥 Đã nhận (Dữ liệu thực)"
            })
            new_alerts_count += 1
    
    if new_alerts_count > 0:
        st.toast(f"📥 Đã nhận {new_alerts_count} cảnh báo mới từ RabbitMQ!", icon="🔔")
    
    st.divider()
    
    # Trình mô phỏng cảnh báo
    st.markdown("**Trình mô phỏng cảnh báo thử nghiệm:**")
    
    col_sim1, col_sim2, col_sim3 = st.columns(3)
    
    with col_sim1:
        if st.button("🟢 Có người"):
            _publish_test_alert(rabbitmq_pub, "person_present_start", "person.present")
    
    with col_sim2:
        if st.button("🟡 Vẫn còn người"):
            _publish_test_alert(rabbitmq_pub, "person_still_present", "person.still_present")
    
    with col_sim3:
        if st.button("🔴 Người đã rời đi"):
            _publish_test_alert(rabbitmq_pub, "person_left", "person.left")
    
    # Lịch sử cảnh báo
    st.subheader("📜 Lịch sử Cảnh báo")
    
    if st.session_state.alert_history:
        # Chuyển đổi sang DataFrame
        df = pd.DataFrame(st.session_state.alert_history)
        df = df.sort_values("timestamp", ascending=False)
        
        st.dataframe(
            df,
            hide_index=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn("Thời gian", format="HH:mm:ss"),
                "event_type": st.column_config.TextColumn("Loại sự kiện"),
                "routing_key": st.column_config.TextColumn("Routing Key"),
                "status": st.column_config.TextColumn("Trạng thái")
            }
        )
        
        if st.button("🗑️ Xóa Lịch sử"):
            st.session_state.alert_history = []
            st.rerun()
    else:
        st.info("Chưa có cảnh báo nào trong lịch sử. Hãy thử trình mô phỏng ở trên!")


def _publish_test_alert(rabbitmq_pub, event_type: str, routing_key: str):
    """Gửi một cảnh báo thử nghiệm đến RabbitMQ."""
    
    import uuid
    from src.domain.value_objects import AlertPayload
    
    # Tạo và gửi payload thử nghiệm
    payload = AlertPayload(
        event_id=str(uuid.uuid4()),
        camera_id="test_camera",
        ts=int(datetime.now().timestamp() * 1000),
        event_type=event_type,
        person_count=1,
        note="Test alert from Streamlit"
    )
    
    success = rabbitmq_pub.publish_alert(payload, routing_key)
    
    # Thêm vào lịch sử
    st.session_state.alert_history.append({
        "timestamp": datetime.now(),
        "event_type": event_type,
        "routing_key": routing_key,
        "status": "✅ Đã gửi" if success else "❌ Thất bại"
    })
    
    if success:
        st.toast(f"✅ Đã gửi: {event_type}", icon="🔔")
    else:
        st.error("Gửi cảnh báo thất bại")
