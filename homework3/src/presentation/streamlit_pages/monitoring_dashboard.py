"""Streamlit page for Monitoring Dashboard with Airflow, Prometheus, and Grafana."""
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def get_prometheus_targets() -> List[Dict[str, Any]]:
    """Get Prometheus scrape targets and their status."""
    try:
        resp = requests.get("http://localhost:9090/api/v1/targets", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("activeTargets", [])
        return []
    except Exception as e:
        logger.error(f"Failed to get Prometheus targets: {e}")
        return []


def get_prometheus_alerts() -> List[Dict[str, Any]]:
    """Get active Prometheus alerts."""
    try:
        resp = requests.get("http://localhost:9090/api/v1/alerts", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("alerts", [])
        return []
    except Exception as e:
        logger.error(f"Failed to get Prometheus alerts: {e}")
        return []


def query_prometheus(query: str) -> Optional[float]:
    """Execute a PromQL query and return the result."""
    try:
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
    except Exception as e:
        logger.error(f"Prometheus query failed: {e}")
        return None


def get_airflow_dags() -> List[Dict[str, Any]]:
    """Get list of Airflow DAGs."""
    try:
        resp = requests.get(
            "http://localhost:8085/api/v1/dags",
            auth=("admin", "admin123"),
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json().get("dags", [])
        return []
    except Exception as e:
        logger.error(f"Failed to get Airflow DAGs: {e}")
        return []


def get_airflow_dag_runs(dag_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get recent DAG runs for a specific DAG."""
    try:
        resp = requests.get(
            f"http://localhost:8085/api/v1/dags/{dag_id}/dagRuns",
            params={"limit": limit, "order_by": "-execution_date"},
            auth=("admin", "admin123"),
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json().get("dag_runs", [])
        return []
    except Exception as e:
        logger.error(f"Failed to get DAG runs: {e}")
        return []


def check_service_health(url: str, timeout: int = 3) -> bool:
    """Check if a service is reachable."""
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code == 200
    except:
        return False


def render_monitoring_dashboard():
    """Render the monitoring dashboard page."""
    st.header("📊 Monitoring Dashboard")
    st.markdown("Centralized monitoring for the entire data platform using **Airflow**, **Prometheus**, and **Grafana**.")
    
    # ============================================
    # Service Status Overview
    # ============================================
    st.subheader("🏥 Monitoring Services Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        airflow_ok = check_service_health("http://localhost:8085/health")
        if airflow_ok:
            st.success("✅ **Airflow**: Online")
            st.caption("Orchestration & Scheduling")
        else:
            st.error("❌ **Airflow**: Offline")
            st.caption("Start: `docker compose up -d airflow-webserver airflow-scheduler`")
    
    with col2:
        prometheus_ok = check_service_health("http://localhost:9090/-/ready")
        if prometheus_ok:
            st.success("✅ **Prometheus**: Online")
            st.caption("Metrics Collection")
        else:
            st.error("❌ **Prometheus**: Offline")
            st.caption("Start: `docker compose up -d prometheus`")
    
    with col3:
        grafana_ok = check_service_health("http://localhost:3000/api/health")
        if grafana_ok:
            st.success("✅ **Grafana**: Online")
            st.caption("Visualization")
        else:
            st.error("❌ **Grafana**: Offline")
            st.caption("Start: `docker compose up -d grafana`")
    
    st.divider()
    
    # ============================================
    # Tabs for Different Views
    # ============================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔄 Airflow DAGs",
        "📈 Prometheus Metrics",
        "🎨 Grafana Dashboards",
        "🚨 Alerts"
    ])
    
    # ============================================
    # Tab 1: Airflow DAGs
    # ============================================
    with tab1:
        st.markdown("### Apache Airflow - Workflow Orchestration")
        
        if not airflow_ok:
            st.warning("Airflow is not running. Please start the Airflow services.")
            st.code("""
cd mini_datalake_cdc_dvc
docker compose up -d airflow-postgres airflow-init
docker compose up -d airflow-webserver airflow-scheduler
            """, language="bash")
        else:
            st.link_button("🌐 Open Airflow UI", "http://localhost:8085", use_container_width=True)
            st.caption("Login: admin / admin123")
            
            st.markdown("#### Available DAGs")
            
            dags = get_airflow_dags()
            
            if dags:
                for dag in dags:
                    dag_id = dag.get("dag_id", "Unknown")
                    is_paused = dag.get("is_paused", True)
                    status_icon = "⏸️" if is_paused else "▶️"
                    
                    with st.expander(f"{status_icon} {dag_id}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Description:** {dag.get('description', 'N/A')}")
                            st.markdown(f"**Schedule:** `{dag.get('schedule_interval', 'None')}`")
                        with col2:
                            st.markdown(f"**Status:** {'Paused' if is_paused else 'Active'}")
                            st.markdown(f"**Tags:** {', '.join(dag.get('tags', []))}")
                        
                        # Show recent runs
                        runs = get_airflow_dag_runs(dag_id, 3)
                        if runs:
                            st.markdown("**Recent Runs:**")
                            for run in runs:
                                state = run.get("state", "unknown")
                                state_icon = {"success": "✅", "failed": "❌", "running": "🔄"}.get(state, "⚪")
                                st.markdown(f"- {state_icon} {run.get('execution_date', 'N/A')[:19]}")
            else:
                st.info("No DAGs loaded yet. DAGs will appear after Airflow starts.")
                
                st.markdown("**Expected DAGs:**")
                st.markdown("""
                - 📊 `spark_batch_daily` - Daily vision event aggregation
                - ✅ `data_quality_check` - Data validation
                - 🔄 `pipeline_orchestrator` - Full pipeline coordination
                """)
    
    # ============================================
    # Tab 2: Prometheus Metrics
    # ============================================
    with tab2:
        st.markdown("### Prometheus - Metrics Collection")
        
        if not prometheus_ok:
            st.warning("Prometheus is not running. Please start the Prometheus service.")
            st.code("docker compose up -d prometheus", language="bash")
        else:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.link_button("🌐 Open Prometheus UI", "http://localhost:9090", use_container_width=True)
            
            with col2:
                if st.button("🔄 Refresh Metrics"):
                    st.rerun()
            
            st.markdown("#### Scrape Targets")
            
            targets = get_prometheus_targets()
            
            if targets:
                targets_data = []
                for target in targets:
                    health = target.get("health", "unknown")
                    health_icon = {"up": "🟢", "down": "🔴", "unknown": "🟡"}.get(health, "⚪")
                    
                    targets_data.append({
                        "Status": health_icon,
                        "Job": target.get("labels", {}).get("job", "N/A"),
                        "Instance": target.get("labels", {}).get("instance", "N/A"),
                        "Last Scrape": target.get("lastScrape", "N/A")[:19] if target.get("lastScrape") else "N/A"
                    })
                
                df = pd.DataFrame(targets_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No scrape targets found. Prometheus may still be starting.")
            
            st.markdown("#### Quick Metrics")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                cpu = query_prometheus('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')
                if cpu is not None:
                    st.metric("CPU Usage", f"{cpu:.1f}%")
                else:
                    st.metric("CPU Usage", "N/A")
            
            with col2:
                mem = query_prometheus('(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')
                if mem is not None:
                    st.metric("Memory Usage", f"{mem:.1f}%")
                else:
                    st.metric("Memory Usage", "N/A")
            
            with col3:
                up_count = query_prometheus('count(up == 1)')
                total = query_prometheus('count(up)')
                if up_count is not None and total is not None:
                    st.metric("Services Up", f"{int(up_count)} / {int(total)}")
                else:
                    st.metric("Services Up", "N/A")
    
    # ============================================
    # Tab 3: Grafana Dashboards
    # ============================================
    with tab3:
        st.markdown("### Grafana - Metrics Visualization")
        
        if not grafana_ok:
            st.warning("Grafana is not running. Please start the Grafana service.")
            st.code("docker compose up -d grafana", language="bash")
        else:
            st.link_button("🌐 Open Grafana", "http://localhost:3000", use_container_width=True)
            st.caption("Login: admin / admin123")
            
            st.markdown("#### Pre-configured Dashboards")
            
            dashboards = [
                {
                    "name": "Data Pipeline Overview",
                    "description": "Service health, system resources, Kafka/PostgreSQL metrics",
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
                        st.link_button("Open", dash['url'])
            
            st.markdown("#### Dashboard Features")
            st.markdown("""
            - **Service Health**: Real-time status of all data lake components
            - **System Resources**: CPU, memory, disk usage
            - **Kafka Metrics**: Topic offsets, consumer lag, message rates
            - **PostgreSQL**: Connections, transactions, replication
            - **Alerts**: Visual indicators when thresholds are exceeded
            """)
    
    # ============================================
    # Tab 4: Alerts
    # ============================================
    with tab4:
        st.markdown("### Active Alerts")
        
        if not prometheus_ok:
            st.warning("Prometheus is not running. Cannot fetch alerts.")
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
                        st.markdown(f"**Severity:** {severity}")
                        st.markdown(f"**State:** {alert.get('state', 'unknown')}")
                        st.markdown(f"**Summary:** {alert.get('annotations', {}).get('summary', 'N/A')}")
                        st.markdown(f"**Description:** {alert.get('annotations', {}).get('description', 'N/A')}")
            else:
                st.success("✅ No active alerts! All systems operating normally.")
            
            st.markdown("#### Configured Alert Rules")
            st.markdown("""
            | Alert | Severity | Condition |
            |-------|----------|-----------|
            | ServiceDown | Critical | Any service down >1m |
            | KafkaConsumerLag | Warning | Lag >10,000 messages |
            | HighCPUUsage | Warning | CPU >80% for 5m |
            | HighMemoryUsage | Warning | Memory >85% for 5m |
            | MinIOHighDiskUsage | Warning | Storage >85% |
            | SparkMasterDown | Critical | Spark Master down >2m |
            | FlinkJobManagerDown | Critical | Flink down >2m |
            """)
    
    st.divider()
    
    # ============================================
    # Quick Start Guide
    # ============================================
    with st.expander("📚 Quick Start Guide"):
        st.markdown("""
        ### Starting the Monitoring Stack
        
        ```bash
        cd homework3/mini_datalake_cdc_dvc
        
        # Start Airflow
        docker compose up -d airflow-postgres airflow-init
        docker compose up -d airflow-webserver airflow-scheduler
        
        # Start Prometheus & Grafana
        docker compose up -d prometheus grafana node-exporter
        
        # Start metric exporters
        docker compose up -d kafka-exporter postgres-exporter
        ```
        
        ### Accessing the UIs
        
        | Service | URL | Credentials |
        |---------|-----|-------------|
        | Airflow | http://localhost:8085 | admin / admin123 |
        | Prometheus | http://localhost:9090 | - |
        | Grafana | http://localhost:3000 | admin / admin123 |
        
        ### Useful PromQL Queries
        
        ```promql
        # Service availability
        up
        
        # CPU usage percentage
        100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
        
        # Memory usage percentage
        (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
        
        # Kafka consumer lag
        kafka_consumer_group_lag
        ```
        """)
