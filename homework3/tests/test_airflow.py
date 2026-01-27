"""
Apache Airflow Orchestration Tests
===================================
Comprehensive tests for Airflow webserver, scheduler, and DAGs.
"""
import pytest
import requests
import json
import time
from typing import Dict, Any, Optional


class TestAirflowHealth:
    """Test Airflow core services health."""
    
    def test_airflow_webserver_health(self, service_urls, http_session):
        """Test Airflow webserver is running and healthy."""
        url = f"{service_urls['airflow']}/health"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Airflow webserver should be accessible"
        
        data = response.json()
        
        # Check metadatabase status
        metadatabase_status = data.get("metadatabase", {}).get("status")
        scheduler_status = data.get("scheduler", {}).get("status")
        
        print(f"✅ Airflow Health:")
        print(f"  - Metadatabase: {metadatabase_status}")
        print(f"  - Scheduler: {scheduler_status}")
        
        assert metadatabase_status == "healthy", "Metadatabase should be healthy"
        assert scheduler_status == "healthy", "Scheduler should be healthy"
    
    
    def test_airflow_version(self, service_urls, airflow_credentials, http_session):
        """Test Airflow version info."""
        url = f"{service_urls['airflow']}/api/v1/version"
        
        # Airflow API requires authentication
        response = http_session.get(
            url,
            auth=(airflow_credentials['username'], airflow_credentials['password']),
            timeout=10
        )
        
        assert response.status_code == 200, "Should retrieve version info"
        
        data = response.json()
        version = data.get("version", "unknown")
        git_version = data.get("git_version", "unknown")
        
        print(f"📦 Airflow Version:")
        print(f"  - Version: {version}")
        print(f"  - Git Version: {git_version}")
        
        assert version != "unknown", "Should have valid version"


class TestAirflowDAGs:
    """Test Airflow DAGs management."""
    
    def test_list_dags(self, service_urls, airflow_credentials, http_session):
        """Test listing all DAGs."""
        url = f"{service_urls['airflow']}/api/v1/dags"
        
        response = http_session.get(
            url,
            auth=(airflow_credentials['username'], airflow_credentials['password']),
            timeout=10
        )
        
        assert response.status_code == 200, "Should list DAGs"
        
        data = response.json()
        dags = data.get("dags", [])
        total_entries = data.get("total_entries", 0)
        
        print(f"📋 Airflow DAGs: {total_entries} total")
        
        # Expected DAGs in the project
        expected_dags = [
            "pipeline_orchestrator",
            "data_quality_check",
            "spark_batch_daily"
        ]
        
        dag_ids = [dag.get("dag_id") for dag in dags]
        
        for expected_dag in expected_dags:
            if expected_dag in dag_ids:
                print(f"  ✅ {expected_dag}")
            else:
                print(f"  ❌ {expected_dag} - NOT FOUND")
        
        # At least our project DAGs should exist
        found_dags = [dag_id for dag_id in expected_dags if dag_id in dag_ids]
        assert len(found_dags) >= 1, f"At least one project DAG should exist. Found: {found_dags}"
    
    
    def test_dag_details(self, service_urls, airflow_credentials, http_session):
        """Test retrieving DAG details."""
        dag_id = "pipeline_orchestrator"
        url = f"{service_urls['airflow']}/api/v1/dags/{dag_id}"
        
        response = http_session.get(
            url,
            auth=(airflow_credentials['username'], airflow_credentials['password']),
            timeout=10
        )
        
        if response.status_code == 404:
            pytest.skip(f"DAG '{dag_id}' not found")
        
        assert response.status_code == 200, f"Should retrieve DAG '{dag_id}' details"
        
        data = response.json()
        
        print(f"📊 DAG: {dag_id}")
        print(f"  - Is Paused: {data.get('is_paused', 'unknown')}")
        print(f"  - Is Active: {data.get('is_active', 'unknown')}")
        print(f"  - Schedule Interval: {data.get('schedule_interval', 'unknown')}")
        print(f"  - Tags: {data.get('tags', [])}")
        
        assert data.get("dag_id") == dag_id, "Should return correct DAG"
    
    
    def test_dag_tasks(self, service_urls, airflow_credentials, http_session):
        """Test retrieving DAG tasks."""
        dag_id = "pipeline_orchestrator"
        url = f"{service_urls['airflow']}/api/v1/dags/{dag_id}/tasks"
        
        response = http_session.get(
            url,
            auth=(airflow_credentials['username'], airflow_credentials['password']),
            timeout=10
        )
        
        if response.status_code == 404:
            pytest.skip(f"DAG '{dag_id}' not found")
        
        assert response.status_code == 200, f"Should retrieve tasks for DAG '{dag_id}'"
        
        data = response.json()
        tasks = data.get("tasks", [])
        
        print(f"📝 Tasks in '{dag_id}': {len(tasks)} tasks")
        
        for task in tasks[:10]:  # Show first 10 tasks
            task_id = task.get("task_id", "unknown")
            operator = task.get("operator_name", "unknown")
            print(f"  - {task_id} ({operator})")
        
        assert len(tasks) > 0, "DAG should have tasks"


class TestAirflowDagRuns:
    """Test Airflow DAG runs."""
    
    def test_list_dag_runs(self, service_urls, airflow_credentials, http_session):
        """Test listing DAG runs."""
        dag_id = "pipeline_orchestrator"
        url = f"{service_urls['airflow']}/api/v1/dags/{dag_id}/dagRuns"
        
        response = http_session.get(
            url,
            auth=(airflow_credentials['username'], airflow_credentials['password']),
            timeout=10
        )
        
        if response.status_code == 404:
            pytest.skip(f"DAG '{dag_id}' not found")
        
        assert response.status_code == 200, f"Should list DAG runs for '{dag_id}'"
        
        data = response.json()
        dag_runs = data.get("dag_runs", [])
        total_entries = data.get("total_entries", 0)
        
        print(f"🏃 DAG Runs for '{dag_id}': {total_entries} total")
        
        # Show recent runs
        for run in dag_runs[:5]:
            run_id = run.get("dag_run_id", "unknown")
            state = run.get("state", "unknown")
            execution_date = run.get("execution_date", "unknown")
            
            print(f"  - {run_id}")
            print(f"    State: {state}, Execution: {execution_date}")
        
        # It's OK if no runs yet
        assert isinstance(dag_runs, list), "Should return list of DAG runs"
    
    
    def test_trigger_dag_run(self, service_urls, airflow_credentials, http_session):
        """Test triggering a DAG run (manual trigger)."""
        dag_id = "data_quality_check"  # Use quality check DAG for testing
        url = f"{service_urls['airflow']}/api/v1/dags/{dag_id}/dagRuns"
        
        # Trigger a new DAG run
        payload = {
            "conf": {},
            "note": "Test run triggered by pytest"
        }
        
        response = http_session.post(
            url,
            auth=(airflow_credentials['username'], airflow_credentials['password']),
            json=payload,
            timeout=10
        )
        
        if response.status_code == 404:
            pytest.skip(f"DAG '{dag_id}' not found")
        
        if response.status_code == 409:
            # DAG run already exists or is running
            print(f"⚠️ DAG run already exists or is running")
            return
        
        assert response.status_code in [200, 201], f"Should trigger DAG run. Got: {response.status_code}"
        
        data = response.json()
        run_id = data.get("dag_run_id", "unknown")
        state = data.get("state", "unknown")
        
        print(f"🚀 Triggered DAG run:")
        print(f"  - Run ID: {run_id}")
        print(f"  - State: {state}")
        
        assert state in ["queued", "running"], "New run should be queued or running"


class TestAirflowConnections:
    """Test Airflow connections configuration."""
    
    def test_list_connections(self, service_urls, airflow_credentials, http_session):
        """Test listing configured connections."""
        url = f"{service_urls['airflow']}/api/v1/connections"
        
        response = http_session.get(
            url,
            auth=(airflow_credentials['username'], airflow_credentials['password']),
            timeout=10
        )
        
        assert response.status_code == 200, "Should list connections"
        
        data = response.json()
        connections = data.get("connections", [])
        
        print(f"🔗 Airflow Connections: {len(connections)} total")
        
        # Expected connections from docker-compose.yml
        expected_connections = [
            "spark_default",
            "minio_s3",
            "cdc_postgres",
            "kafka_default",
            "hive_metastore",
            "trino_default",
            "rabbitmq_default"
        ]
        
        conn_ids = [conn.get("connection_id") for conn in connections]
        
        for expected_conn in expected_connections:
            if expected_conn in conn_ids:
                print(f"  ✅ {expected_conn}")
            else:
                print(f"  ⚠️ {expected_conn} - Not found (may be defined via env vars)")
        
        # Connections can be defined via environment variables
        # so it's OK if they don't appear in the list
        assert isinstance(connections, list), "Should return connections list"


class TestAirflowIntegration:
    """Test Airflow integration with other services."""
    
    def test_airflow_can_reach_spark(self, service_urls, http_session):
        """Test if Airflow can reach Spark cluster."""
        # This tests internal network connectivity
        # In reality, Airflow would use spark-master:7077 internally
        
        # From external perspective, we verify Spark is accessible
        spark_url = f"{service_urls['spark_master']}/json/"
        response = http_session.get(spark_url, timeout=10)
        
        assert response.status_code == 200, "Spark should be accessible for Airflow"
        
        spark_data = response.json()
        spark_workers = spark_data.get("aliveworkers", 0)
        
        print(f"✅ Spark accessible from test environment:")
        print(f"  - Workers: {spark_workers}")
        print(f"  - Airflow should be able to submit jobs via spark://spark-master:7077")
        
        assert spark_workers > 0, "Spark should have workers for Airflow to use"
    
    
    def test_airflow_scheduler_heartbeat(self, service_urls, airflow_credentials, http_session):
        """Test Airflow scheduler is running and processing."""
        url = f"{service_urls['airflow']}/health"
        
        # Check scheduler health multiple times
        for i in range(3):
            response = http_session.get(url, timeout=10)
            data = response.json()
            
            scheduler_status = data.get("scheduler", {}).get("status")
            latest_heartbeat = data.get("scheduler", {}).get("latest_scheduler_heartbeat")
            
            print(f"💓 Scheduler heartbeat check {i+1}/3:")
            print(f"  - Status: {scheduler_status}")
            print(f"  - Latest heartbeat: {latest_heartbeat}")
            
            assert scheduler_status == "healthy", "Scheduler should remain healthy"
            
            if i < 2:
                time.sleep(2)
        
        print("✅ Scheduler is consistently healthy")
