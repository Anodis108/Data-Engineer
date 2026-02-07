"""Trang Bảng điều khiển Giám sát với Airflow, Prometheus và Grafana."""
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def get_prometheus_targets() -> List[Dict[str, Any]]:
    """Lấy danh sách các mục tiêu scrape của Prometheus và trạng thái của chúng."""
    # Lấy các mục tiêu hoạt động từ Prometheus
    resp = requests.get("http://localhost:9090/api/v1/targets", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("data", {}).get("activeTargets", [])
    return []


def get_prometheus_alerts() -> List[Dict[str, Any]]:
    """Lấy danh sách các cảnh báo đang hoạt động của Prometheus."""
    # Lấy cảnh báo từ Prometheus
    resp = requests.get("http://localhost:9090/api/v1/alerts", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("data", {}).get("alerts", [])
    return []


def query_prometheus(query: str) -> Optional[float]:
    """Thực thi truy vấn PromQL và trả về kết quả."""
    # Truy vấn API Prometheus
    resp = requests.get(
        "http://localhost:9090/api/v1/query",
        params={"query": query},
        timeout=5
    )
    if resp.status_code == 200:
        data = resp.json()
        results = data.get("data", {}).get("result", [])
        if results and len(results) > 0:
            return float(results[0].get("value", [0, 0])[1])
    return None


def get_airflow_dags() -> List[Dict[str, Any]]:
    """Lấy danh sách các DAGs của Airflow."""
    # Lấy DAGs từ API Airflow
    resp = requests.get(
        "http://localhost:8085/api/v1/dags",
        auth=("admin", "admin123"),
        timeout=5
    )
    if resp.status_code == 200:
        return resp.json().get("dags", [])
    return []


def get_airflow_dag_runs(dag_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Lấy danh sách các lần chạy gần đây cho một DAG cụ thể."""
    # Lấy danh sách chạy DAG từ API Airflow
    resp = requests.get(
        f"http://localhost:8085/api/v1/dags/{dag_id}/dagRuns",
        params={"limit": limit, "order_by": "-execution_date"},
        auth=("admin", "admin123"),
        timeout=5
    )
    if resp.status_code == 200:
        return resp.json().get("dag_runs", [])
    return []


def check_service_health(url: str, timeout: int = 3) -> bool:
    """Kiểm tra xem dịch vụ có thể truy cập được không."""
    # Kiểm tra sức khỏe dịch vụ
    resp = requests.get(url, timeout=timeout)
    return resp.status_code == 200


def render_monitoring_dashboard():
    """Hiển thị trang bảng điều khiển giám sát."""
    st.header("📊 Bảng điều khiển Giám sát")
    st.markdown("Giám sát tập trung cho toàn bộ nền tảng dữ liệu sử dụng **Airflow**, **Prometheus**, và **Grafana**.")
    
    # ============================================
    # Tổng quan Trạng thái Dịch vụ
    # ============================================
    st.subheader("🏥 Trạng thái Dịch vụ Giám sát")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        airflow_ok = check_service_health("http://localhost:8085/health")
        if airflow_ok:
            st.success("✅ **Airflow**: Trực tuyến")
            st.caption("Điều phối & Lập lịch")
        else:
            st.error("❌ **Airflow**: Ngoại tuyến")
            st.caption("Khởi động: `docker compose up -d airflow-webserver airflow-scheduler`")
    
    with col2:
        prometheus_ok = check_service_health("http://localhost:9090/-/ready")
        if prometheus_ok:
            st.success("✅ **Prometheus**: Trực tuyến")
            st.caption("Thu thập chỉ số")
        else:
            st.error("❌ **Prometheus**: Ngoại tuyến")
            st.caption("Khởi động: `docker compose up -d prometheus`")
    
    with col3:
        grafana_ok = check_service_health("http://localhost:3000/api/health")
        if grafana_ok:
            st.success("✅ **Grafana**: Trực tuyến")
            st.caption("Trực quan hóa")
        else:
            st.error("❌ **Grafana**: Ngoại tuyến")
            st.caption("Khởi động: `docker compose up -d grafana`")
    
    st.divider()
    
    # ============================================
    # Các tab cho các chế độ xem khác nhau
    # ============================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔄 Airflow DAGs",
        "📈 Metrics Prometheus",
        "🎨 Bảng điều khiển Grafana",
        "🚨 Cảnh báo"
    ])
    
    # ============================================
    # Tab 1: Airflow DAGs
    # ============================================
    with tab1:
        st.markdown("### Apache Airflow - Điều phối Quy trình làm việc")
        
        if not airflow_ok:
            st.warning("Airflow không chạy. Vui lòng khởi động các dịch vụ Airflow.")
            st.code("""
cd mini_datalake_cdc_dvc
docker compose up -d airflow-postgres airflow-init
docker compose up -d airflow-webserver airflow-scheduler
            """, language="bash")
        else:
            st.link_button("🌐 Mở Airflow UI", "http://localhost:8085", use_container_width=True)
            st.caption("Đăng nhập: admin / admin123")
            
            st.markdown("#### Các DAG có sẵn")
            
            dags = get_airflow_dags()
            
            if dags:
                for dag in dags:
                    dag_id = dag.get("dag_id", "Không xác định")
                    is_paused = dag.get("is_paused", True)
                    status_icon = "⏸️" if is_paused else "▶️"
                    
                    with st.expander(f"{status_icon} {dag_id}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Mô tả:** {dag.get('description', 'N/A')}")
                            st.markdown(f"**Lịch trình:** `{dag.get('schedule_interval', 'None')}`")
                        with col2:
                            st.markdown(f"**Trạng thái:** {'Đã tạm dừng' if is_paused else 'Đang hoạt động'}")
                            st.markdown(f"**Tags:** {', '.join(dag.get('tags', []))}")
                        
                        # Hiển thị các lần chạy gần đây
                        runs = get_airflow_dag_runs(dag_id, 3)
                        if runs:
                            st.markdown("**Các lần chạy gần đây:**")
                            for run in runs:
                                state = run.get("state", "không xác định")
                                state_icon = {"success": "✅", "failed": "❌", "running": "🔄"}.get(state, "⚪")
                                st.markdown(f"- {state_icon} {run.get('execution_date', 'N/A')[:19]}")
            else:
                st.info("Chưa tải DAG nào. DAG sẽ xuất hiện sau khi Airflow khởi động.")
                
                st.markdown("**Các DAG dự kiến:**")
                st.markdown("""
                - 📊 `spark_batch_daily` - Tổng hợp sự kiện thị giác hàng ngày
                - ✅ `data_quality_check` - Xác thực dữ liệu
                - 🔄 `pipeline_orchestrator` - Điều phối toàn bộ quy trình
                """)
    
    # ============================================
    # Tab 2: Metrics Prometheus
    # ============================================
    with tab2:
        st.markdown("### Prometheus - Thu thập Chỉ số")
        
        if not prometheus_ok:
            st.warning("Prometheus không chạy. Vui lòng khởi động dịch vụ Prometheus.")
            st.code("docker compose up -d prometheus", language="bash")
        else:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.link_button("🌐 Mở Prometheus UI", "http://localhost:9090", use_container_width=True)
            
            with col2:
                if st.button("🔄 Làm mới Metrics"):
                    st.rerun()
            
            st.markdown("#### Mục tiêu Scrape")
            
            targets = get_prometheus_targets()
            
            if targets:
                targets_data = []
                for target in targets:
                    health = target.get("health", "unknown")
                    health_icon = {"up": "🟢", "down": "🔴", "unknown": "🟡"}.get(health, "⚪")
                    
                    targets_data.append({
                        "Trạng thái": health_icon,
                        "Công việc": target.get("labels", {}).get("job", "N/A"),
                        "Instance": target.get("labels", {}).get("instance", "N/A"),
                        "Lần Scrape cuối": target.get("lastScrape", "N/A")[:19] if target.get("lastScrape") else "N/A"
                    })
                
                df = pd.DataFrame(targets_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Không tìm thấy mục tiêu scrape nào. Prometheus có thể vẫn đang khởi động.")
            
            st.markdown("#### Chỉ số Nhanh")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                cpu = query_prometheus('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')
                if cpu is not None:
                    st.metric("Sử dụng CPU", f"{cpu:.1f}%")
                else:
                    st.metric("Sử dụng CPU", "N/A")
            
            with col2:
                mem = query_prometheus('(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')
                if mem is not None:
                    st.metric("Sử dụng Bộ nhớ", f"{mem:.1f}%")
                else:
                    st.metric("Sử dụng Bộ nhớ", "N/A")
            
            with col3:
                up_count = query_prometheus('count(up == 1)')
                total = query_prometheus('count(up)')
                if up_count is not None and total is not None:
                    st.metric("Dịch vụ Hoạt động", f"{int(up_count)} / {int(total)}")
                else:
                    st.metric("Dịch vụ Hoạt động", "N/A")
    
    # ============================================
    # Tab 3: Bảng điều khiển Grafana
    # ============================================
    with tab3:
        st.markdown("### Grafana - Trực quan hóa Chỉ số")
        
        if not grafana_ok:
            st.warning("Grafana không chạy. Vui lòng khởi động dịch vụ Grafana.")
            st.code("docker compose up -d grafana", language="bash")
        else:
            st.link_button("🌐 Mở Grafana", "http://localhost:3000", use_container_width=True)
            st.caption("Đăng nhập: admin / admin123")
            
            st.markdown("#### Bảng điều khiển được cấu hình sẵn")
            
            dashboards = [
                {
                    "name": "Tổng quan Data Pipeline",
                    "description": "Sức khỏe dịch vụ, tài nguyên hệ thống, chỉ số Kafka/PostgreSQL",
                    "url": "http://localhost:3000/d/pipeline-overview"
                }
            ]
            
            for dash in dashboards:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{dash['name']}**")
                        st.caption(dash['description'])
                    with col2:
                        st.link_button("Mở", dash['url'])
            
            st.markdown("#### Tính năng Bảng điều khiển")
            st.markdown("""
            - **Sức khỏe Dịch vụ**: Trạng thái thời gian thực của tất cả thành phần data lake
            - **Tài nguyên Hệ thống**: CPU, bộ nhớ, sử dụng đĩa
            - **Chỉ số Kafka**: Topic offsets, độ trễ consumer, tốc độ tin nhắn
            - **PostgreSQL**: Kết nối, giao dịch, sao chép (replication)
            - **Cảnh báo**: Chỉ báo trực quan khi vượt quá ngưỡng
            """)
    
    # ============================================
    # Tab 4: Cảnh báo
    # ============================================
    with tab4:
        st.markdown("### Cảnh báo Đang hoạt động")
        
        if not prometheus_ok:
            st.warning("Prometheus không chạy. Không thể lấy cảnh báo.")
        else:
            alerts = get_prometheus_alerts()
            
            if alerts:
                for alert in alerts:
                    severity = alert.get("labels", {}).get("severity", "info")
                    severity_colors = {
                        "critical": "🔴",
                        "warning": "🟡",
                        "info": "🔵"
                    }
                    icon = severity_colors.get(severity, "⚪")
                    
                    with st.expander(f"{icon} {alert.get('labels', {}).get('alertname', 'Unknown Alert')}"):
                        st.markdown(f"**Mức độ:** {severity}")
                        st.markdown(f"**Trạng thái:** {alert.get('state', 'unknown')}")
                        st.markdown(f"**Tóm tắt:** {alert.get('annotations', {}).get('summary', 'N/A')}")
                        st.markdown(f"**Mô tả:** {alert.get('annotations', {}).get('description', 'N/A')}")
            else:
                st.success("✅ Không có cảnh báo đang hoạt động! Tất cả hệ thống hoạt động bình thường.")
            
            st.markdown("#### Quy tắc Cảnh báo đã cấu hình")
            st.markdown("""
            | Cảnh báo | Mức độ | Điều kiện |
            |-------|----------|-----------|
            | ServiceDown | Nghiêm trọng | Bất kỳ dịch vụ nào ngừng hoạt động >1m |
            | KafkaConsumerLag | Cảnh báo | Độ trễ >10,000 tin nhắn |
            | HighCPUUsage | Cảnh báo | CPU >80% trong 5m |
            | HighMemoryUsage | Cảnh báo | Bộ nhớ >85% trong 5m |
            | MinIOHighDiskUsage | Cảnh báo | Lưu trữ >85% |
            | SparkMasterDown | Nghiêm trọng | Spark Master ngừng hoạt động >2m |
            | FlinkJobManagerDown | Nghiêm trọng | Flink ngừng hoạt động >2m |
            """)
    
    st.divider()
    
    # ============================================
    # Hướng dẫn Bắt đầu Nhanh
    # ============================================
    with st.expander("📚 Hướng dẫn Bắt đầu Nhanh"):
        st.markdown("""
        ### Khởi động Stack Giám sát
        
        ```bash
        cd homework3/mini_datalake_cdc_dvc
        
        # Khởi động Airflow
        docker compose up -d airflow-postgres airflow-init
        docker compose up -d airflow-webserver airflow-scheduler
        
        # Khởi động Prometheus & Grafana
        docker compose up -d prometheus grafana node-exporter
        
        # Khởi động các metric exporters
        docker compose up -d kafka-exporter postgres-exporter
        ```
        
        ### Truy cập các giao diện người dùng (UIs)
        
        | Dịch vụ | URL | Thông tin đăng nhập |
        |---------|-----|-------------|
        | Airflow | http://localhost:8085 | admin / admin123 |
        | Prometheus | http://localhost:9090 | - |
        | Grafana | http://localhost:3000 | admin / admin123 |
        
        ### Các truy vấn PromQL hữu ích
        
        ```promql
        # Tính sẵn sàng của dịch vụ
        up
        
        # Tỷ lệ sử dụng CPU
        100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
        
        # Tỷ lệ sử dụng bộ nhớ
        (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
        
        # Độ trễ consumer Kafka
        kafka_consumer_group_lag
        ```
        """)
