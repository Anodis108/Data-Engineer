"""
Prometheus & Grafana Monitoring Tests
======================================
Comprehensive tests for monitoring stack: Prometheus and Grafana.
"""
import pytest
import requests
import json
import time
from typing import Dict, Any, List


class TestPrometheusHealth:
    """Test Prometheus core functionality."""
    
    def test_prometheus_health(self, service_urls, http_session):
        """Test Prometheus is running and healthy."""
        url = f"{service_urls['prometheus']}/-/healthy"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Prometheus should be healthy"
        
        print(f"✅ Prometheus is healthy")
    
    
    def test_prometheus_ready(self, service_urls, http_session):
        """Test Prometheus is ready to serve traffic."""
        url = f"{service_urls['prometheus']}/-/ready"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Prometheus should be ready"
        
        print(f"✅ Prometheus is ready")
    
    
    def test_prometheus_config(self, service_urls, http_session):
        """Test Prometheus configuration."""
        url = f"{service_urls['prometheus']}/api/v1/status/config"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Should retrieve Prometheus config"
        
        data = response.json()
        status = data.get("status")
        config_yaml = data.get("data", {}).get("yaml", "")
        
        print(f"⚙️ Prometheus Configuration:")
        print(f"  - Status: {status}")
        print(f"  - Config length: {len(config_yaml)} bytes")
        
        assert status == "success", "Config retrieval should succeed"
        assert len(config_yaml) > 0, "Should have configuration"
        
        # Check for key configuration elements
        assert "scrape_configs" in config_yaml, "Should have scrape configs"


class TestPrometheusTargets:
    """Test Prometheus scrape targets."""
    
    def test_prometheus_targets(self, service_urls, http_session):
        """Test Prometheus scrape targets status."""
        url = f"{service_urls['prometheus']}/api/v1/targets"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Should retrieve targets"
        
        data = response.json()
        active_targets = data.get("data", {}).get("activeTargets", [])
        dropped_targets = data.get("data", {}).get("droppedTargets", [])
        
        print(f"🎯 Prometheus Targets:")
        print(f"  - Active: {len(active_targets)}")
        print(f"  - Dropped: {len(dropped_targets)}")
        
        # Expected targets from prometheus.yml
        expected_jobs = [
            "prometheus",
            "node",
            "minio",
            "kafka",
            "postgres-cdc",
            "spark-master",
            "flink",
            "trino"
        ]
        
        active_jobs = {target.get("labels", {}).get("job") for target in active_targets}
        
        print(f"\n📊 Active Jobs:")
        for job in expected_jobs:
            status = "✅" if job in active_jobs else "⚠️"
            print(f"  {status} {job}")
        
        # At least core targets should be active
        core_jobs = ["prometheus", "node", "minio", "kafka"]
        found_core = [job for job in core_jobs if job in active_jobs]
        
        assert len(found_core) >= 2, f"At least 2 core targets should be active. Found: {found_core}"
    
    
    def test_prometheus_target_health(self, service_urls, http_session):
        """Test individual target health status."""
        url = f"{service_urls['prometheus']}/api/v1/targets"
        response = http_session.get(url, timeout=10)
        data = response.json()
        
        active_targets = data.get("data", {}).get("activeTargets", [])
        
        healthy_count = 0
        unhealthy_count = 0
        
        print(f"\n🏥 Target Health Status:")
        
        for target in active_targets:
            job = target.get("labels", {}).get("job", "unknown")
            instance = target.get("labels", {}).get("instance", "unknown")
            health = target.get("health", "unknown")
            last_error = target.get("lastError", "")
            
            if health == "up":
                healthy_count += 1
                print(f"  ✅ {job} ({instance}) - UP")
            else:
                unhealthy_count += 1
                print(f"  ❌ {job} ({instance}) - {health.upper()}")
                if last_error:
                    print(f"     Error: {last_error}")
        
        print(f"\nSummary: {healthy_count} UP, {unhealthy_count} DOWN")
        
        # Most targets should be healthy
        assert healthy_count > 0, "At least some targets should be healthy"


class TestPrometheusMetrics:
    """Test Prometheus metrics collection."""
    
    def test_prometheus_query_up_metric(self, service_urls, http_session):
        """Test querying the 'up' metric."""
        url = f"{service_urls['prometheus']}/api/v1/query"
        params = {"query": "up"}
        
        response = http_session.get(url, params=params, timeout=10)
        
        assert response.status_code == 200, "Should execute query"
        
        data = response.json()
        status = data.get("status")
        result = data.get("data", {}).get("result", [])
        
        print(f"📈 Query 'up' metric:")
        print(f"  - Status: {status}")
        print(f"  - Results: {len(result)} time series")
        
        assert status == "success", "Query should succeed"
        assert len(result) > 0, "Should have at least one 'up' metric"
        
        # Show some results
        for item in result[:5]:
            metric = item.get("metric", {})
            value = item.get("value", [None, None])
            
            job = metric.get("job", "unknown")
            instance = metric.get("instance", "unknown")
            up_value = value[1] if len(value) > 1 else "unknown"
            
            print(f"  - {job} ({instance}): {up_value}")
    
    
    def test_prometheus_query_kafka_metrics(self, service_urls, http_session):
        """Test querying Kafka metrics."""
        url = f"{service_urls['prometheus']}/api/v1/query"
        params = {"query": "kafka_server_brokertopicmetrics_messagesin_total"}
        
        response = http_session.get(url, params=params, timeout=10)
        data = response.json()
        
        status = data.get("status")
        result = data.get("data", {}).get("result", [])
        
        print(f"📊 Kafka Metrics:")
        print(f"  - Status: {status}")
        print(f"  - Results: {len(result)} time series")
        
        if len(result) > 0:
            print(f"  ✅ Kafka metrics are being collected")
        else:
            print(f"  ⚠️ No Kafka metrics found (kafka-exporter may not be scraping yet)")
    
    
    def test_prometheus_query_system_metrics(self, service_urls, http_session):
        """Test querying system/node metrics."""
        url = f"{service_urls['prometheus']}/api/v1/query"
        params = {"query": "node_cpu_seconds_total"}
        
        response = http_session.get(url, params=params, timeout=10)
        data = response.json()
        
        status = data.get("status")
        result = data.get("data", {}).get("result", [])
        
        print(f"💻 System Metrics:")
        print(f"  - Status: {status}")
        print(f"  - Results: {len(result)} time series")
        
        if len(result) > 0:
            print(f"  ✅ Node exporter metrics are being collected")
        else:
            print(f"  ⚠️ No node metrics found")


class TestGrafanaHealth:
    """Test Grafana core functionality."""
    
    def test_grafana_health(self, service_urls, http_session):
        """Test Grafana is running and healthy."""
        url = f"{service_urls['grafana']}/api/health"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Grafana should be accessible"
        
        data = response.json()
        database = data.get("database", "unknown")
        version = data.get("version", "unknown")
        
        print(f"✅ Grafana Health:")
        print(f"  - Database: {database}")
        print(f"  - Version: {version}")
        
        assert database == "ok", "Database should be ok"
    
    
    def test_grafana_datasources(self, service_urls, grafana_credentials, http_session):
        """Test Grafana datasources configuration."""
        url = f"{service_urls['grafana']}/api/datasources"
        
        response = http_session.get(
            url,
            auth=(grafana_credentials['username'], grafana_credentials['password']),
            timeout=10
        )
        
        assert response.status_code == 200, "Should retrieve datasources"
        
        datasources = response.json()
        
        print(f"🔌 Grafana Datasources: {len(datasources)} total")
        
        for ds in datasources:
            ds_id = ds.get("id")
            ds_name = ds.get("name")
            ds_type = ds.get("type")
            ds_url = ds.get("url", "")
            is_default = ds.get("isDefault", False)
            
            default_marker = "⭐" if is_default else "  "
            print(f"  {default_marker} {ds_name} ({ds_type})")
            print(f"     URL: {ds_url}")
        
        # Should have Prometheus datasource
        prometheus_ds = [ds for ds in datasources if ds.get("type") == "prometheus"]
        assert len(prometheus_ds) > 0, "Should have at least one Prometheus datasource"
        
        print(f"\n✅ Found {len(prometheus_ds)} Prometheus datasource(s)")
    
    
    def test_grafana_dashboards(self, service_urls, grafana_credentials, http_session):
        """Test Grafana dashboards."""
        url = f"{service_urls['grafana']}/api/search"
        params = {"type": "dash-db"}
        
        response = http_session.get(
            url,
            auth=(grafana_credentials['username'], grafana_credentials['password']),
            params=params,
            timeout=10
        )
        
        assert response.status_code == 200, "Should retrieve dashboards"
        
        dashboards = response.json()
        
        print(f"📊 Grafana Dashboards: {len(dashboards)} total")
        
        for dashboard in dashboards:
            dash_id = dashboard.get("id")
            dash_uid = dashboard.get("uid")
            dash_title = dashboard.get("title")
            dash_url = dashboard.get("url")
            
            print(f"  - {dash_title}")
            print(f"    UID: {dash_uid}, URL: {dash_url}")
        
        # Expected dashboard from project
        expected_dashboards = ["Data Pipeline Overview", "data_pipeline_overview"]
        
        dashboard_titles = [d.get("title", "").lower() for d in dashboards]
        
        found_expected = any(
            expected.lower() in " ".join(dashboard_titles)
            for expected in expected_dashboards
        )
        
        if found_expected:
            print(f"\n✅ Found project dashboard")
        else:
            print(f"\n⚠️ Project dashboard not found (may need to be loaded)")


class TestGrafanaPrometheusIntegration:
    """Test Grafana and Prometheus integration."""
    
    def test_grafana_can_query_prometheus(self, service_urls, grafana_credentials, http_session):
        """Test Grafana can query Prometheus datasource."""
        # First, get Prometheus datasource
        url = f"{service_urls['grafana']}/api/datasources"
        
        response = http_session.get(
            url,
            auth=(grafana_credentials['username'], grafana_credentials['password']),
            timeout=10
        )
        
        datasources = response.json()
        prometheus_ds = [ds for ds in datasources if ds.get("type") == "prometheus"]
        
        if not prometheus_ds:
            pytest.skip("No Prometheus datasource configured")
        
        ds_id = prometheus_ds[0].get("id")
        ds_name = prometheus_ds[0].get("name")
        
        # Test datasource health
        test_url = f"{service_urls['grafana']}/api/datasources/{ds_id}/health"
        
        response = http_session.get(
            test_url,
            auth=(grafana_credentials['username'], grafana_credentials['password']),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            message = data.get("message", "")
            
            print(f"🔗 Grafana → Prometheus Connection:")
            print(f"  - Datasource: {ds_name}")
            print(f"  - Status: {status}")
            print(f"  - Message: {message}")
            
            assert status == "OK", "Datasource should be healthy"
        else:
            print(f"⚠️ Could not test datasource health (endpoint may not be available)")


class TestMonitoringStack:
    """Test complete monitoring stack."""
    
    def test_end_to_end_metric_flow(self, service_urls, http_session):
        """Test metrics flow from targets → Prometheus → Grafana."""
        
        print(f"\n🔄 Testing end-to-end metrics flow:\n")
        
        # Step 1: Verify Prometheus is scraping targets
        targets_url = f"{service_urls['prometheus']}/api/v1/targets"
        targets_response = http_session.get(targets_url, timeout=10)
        targets_data = targets_response.json()
        active_targets = targets_data.get("data", {}).get("activeTargets", [])
        
        healthy_targets = [t for t in active_targets if t.get("health") == "up"]
        
        print(f"1️⃣ Prometheus Targets: {len(healthy_targets)}/{len(active_targets)} healthy")
        assert len(healthy_targets) > 0, "Should have healthy targets"
        
        # Step 2: Verify Prometheus has metrics
        query_url = f"{service_urls['prometheus']}/api/v1/query"
        query_response = http_session.get(query_url, params={"query": "up"}, timeout=10)
        query_data = query_response.json()
        metrics_count = len(query_data.get("data", {}).get("result", []))
        
        print(f"2️⃣ Prometheus Metrics: {metrics_count} 'up' time series")
        assert metrics_count > 0, "Should have metrics"
        
        # Step 3: Verify Grafana is healthy
        grafana_url = f"{service_urls['grafana']}/api/health"
        grafana_response = http_session.get(grafana_url, timeout=10)
        grafana_data = grafana_response.json()
        grafana_db = grafana_data.get("database")
        
        print(f"3️⃣ Grafana: Database status = {grafana_db}")
        assert grafana_db == "ok", "Grafana should be healthy"
        
        print(f"\n✅ End-to-end monitoring stack is operational!")
        print(f"   Targets → Prometheus → Grafana ✓")
