"""
Spark & Flink Processing Tests
===============================
Comprehensive tests for Apache Spark and Apache Flink clusters.
"""
import pytest
import requests
import json
import time
from typing import Dict, Any


class TestSparkCluster:
    """Test Apache Spark Master and Worker."""
    
    def test_spark_master_health(self, service_urls, http_session):
        """Test Spark Master is running and healthy."""
        url = f"{service_urls['spark_master']}/json/"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Spark Master should be accessible"
        
        data = response.json()
        assert data.get("status") == "ALIVE", "Spark Master should be ALIVE"
        print(f"✅ Spark Master: {data.get('url')} - Status: {data.get('status')}")
    
    
    def test_spark_master_info(self, service_urls, http_session):
        """Test Spark Master configuration and info."""
        url = f"{service_urls['spark_master']}/json/"
        response = http_session.get(url, timeout=10)
        data = response.json()
        
        # Verify core configuration
        assert "cores" in data, "Should report total cores"
        assert "memory" in data, "Should report total memory"
        assert "workers" in data, "Should report workers list"
        
        cores = data.get("cores", 0)
        memory = data.get("memory", 0)
        workers = data.get("workers", [])
        
        print(f"📊 Spark Cluster:")
        print(f"  - Cores: {cores}")
        print(f"  - Memory: {memory} MB")
        print(f"  - Workers: {len(workers)}")
        
        assert cores >= 0, "Should have cores available"
    
    
    def test_spark_workers_registered(self, service_urls, http_session):
        """Test that Spark Workers are registered with Master."""
        url = f"{service_urls['spark_master']}/json/"
        response = http_session.get(url, timeout=10)
        data = response.json()
        
        workers = data.get("workers", [])
        alive_workers = data.get("aliveworkers", 0)
        
        print(f"👷 Spark Workers:")
        print(f"  - Total workers: {len(workers)}")
        print(f"  - Alive workers: {alive_workers}")
        
        for idx, worker in enumerate(workers):
            worker_id = worker.get("id", "unknown")
            worker_state = worker.get("state", "unknown")
            worker_cores = worker.get("cores", 0)
            worker_memory = worker.get("memory", 0)
            
            print(f"  - Worker {idx+1}: {worker_id}")
            print(f"    State: {worker_state}, Cores: {worker_cores}, Memory: {worker_memory} MB")
            
            assert worker_state == "ALIVE", f"Worker {worker_id} should be ALIVE"
        
        # At least 1 worker should be registered
        assert alive_workers >= 1, "At least 1 worker should be alive"
    
    
    def test_spark_worker_health(self, service_urls, http_session):
        """Test Spark Worker web UI is accessible."""
        url = f"{service_urls['spark_worker']}/json/"
        
        try:
            response = http_session.get(url, timeout=10)
            assert response.status_code == 200, "Spark Worker should be accessible"
            
            data = response.json()
            print(f"✅ Spark Worker: {data.get('masterwebuiurl', 'N/A')}")
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Spark Worker UI not accessible: {e}")
    
    
    def test_spark_applications_list(self, service_urls, http_session):
        """Test Spark can list applications."""
        url = f"{service_urls['spark_master']}/json/"
        response = http_session.get(url, timeout=10)
        data = response.json()
        
        # Check for applications
        active_apps = data.get("activeapps", [])
        completed_apps = data.get("completedapps", [])
        
        print(f"📱 Spark Applications:")
        print(f"  - Active: {len(active_apps)}")
        print(f"  - Completed: {len(completed_apps)}")
        
        # Should be able to retrieve app info (even if empty)
        assert isinstance(active_apps, list), "Should return active apps list"
        assert isinstance(completed_apps, list), "Should return completed apps list"


class TestFlinkCluster:
    """Test Apache Flink JobManager and TaskManager."""
    
    def test_flink_jobmanager_health(self, service_urls, http_session):
        """Test Flink JobManager is running and healthy."""
        url = f"{service_urls['flink_jobmanager']}/overview"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Flink JobManager should be accessible"
        
        data = response.json()
        print(f"✅ Flink JobManager: Version {data.get('flink-version', 'unknown')}")
        print(f"  - Commit: {data.get('flink-commit', 'unknown')[:8]}")
    
    
    def test_flink_cluster_overview(self, service_urls, http_session):
        """Test Flink cluster overview and resources."""
        url = f"{service_urls['flink_jobmanager']}/overview"
        response = http_session.get(url, timeout=10)
        data = response.json()
        
        # Verify cluster metrics
        taskmanagers = data.get("taskmanagers", 0)
        slots_total = data.get("slots-total", 0)
        slots_available = data.get("slots-available", 0)
        jobs_running = data.get("jobs-running", 0)
        jobs_finished = data.get("jobs-finished", 0)
        
        print(f"📊 Flink Cluster Overview:")
        print(f"  - TaskManagers: {taskmanagers}")
        print(f"  - Total Slots: {slots_total}")
        print(f"  - Available Slots: {slots_available}")
        print(f"  - Running Jobs: {jobs_running}")
        print(f"  - Finished Jobs: {jobs_finished}")
        
        # At least 1 TaskManager should be registered
        assert taskmanagers >= 1, "At least 1 TaskManager should be registered"
        assert slots_total > 0, "Should have task slots available"
    
    
    def test_flink_taskmanagers_registered(self, service_urls, http_session):
        """Test that TaskManagers are registered with JobManager."""
        url = f"{service_urls['flink_jobmanager']}/taskmanagers"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Should retrieve TaskManagers list"
        
        data = response.json()
        taskmanagers = data.get("taskmanagers", [])
        
        print(f"👷 Flink TaskManagers: {len(taskmanagers)}")
        
        for idx, tm in enumerate(taskmanagers):
            tm_id = tm.get("id", "unknown")
            tm_path = tm.get("path", "unknown")
            tm_slots = tm.get("slotsNumber", 0)
            tm_free_slots = tm.get("freeSlots", 0)
            
            print(f"  - TaskManager {idx+1}: {tm_id[:8]}...")
            print(f"    Path: {tm_path}")
            print(f"    Slots: {tm_slots} (Free: {tm_free_slots})")
        
        assert len(taskmanagers) >= 1, "At least 1 TaskManager should be registered"
    
    
    def test_flink_jobs_list(self, service_urls, http_session):
        """Test Flink can list jobs."""
        url = f"{service_urls['flink_jobmanager']}/jobs"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Should retrieve jobs list"
        
        data = response.json()
        jobs = data.get("jobs", [])
        
        print(f"📱 Flink Jobs: {len(jobs)}")
        
        for idx, job in enumerate(jobs):
            job_id = job.get("id", "unknown")
            job_status = job.get("status", "unknown")
            
            print(f"  - Job {idx+1}: {job_id}")
            print(f"    Status: {job_status}")
        
        # Should be able to retrieve job info (even if empty)
        assert isinstance(jobs, list), "Should return jobs list"
    
    
    def test_flink_config(self, service_urls, http_session):
        """Test Flink configuration."""
        url = f"{service_urls['flink_jobmanager']}/config"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200, "Should retrieve config"
        
        data = response.json()
        config = data
        
        print(f"⚙️ Flink Configuration:")
        
        # Print some key configs
        key_configs = [
            "jobmanager.rpc.address",
            "parallelism.default",
            "taskmanager.numberOfTaskSlots"
        ]
        
        if isinstance(config, dict):
            for key, value in config.items():
                if key in key_configs:
                    print(f"  - {key}: {value}")
        elif isinstance(config, list):
            for item in config:
                if isinstance(item, dict):
                    key = item.get("key", "")
                    value = item.get("value", "")
                    if key in key_configs:
                        print(f"  - {key}: {value}")
        
        assert len(config) > 0, "Should have configuration items"


class TestSparkFlinkIntegration:
    """Test Spark and Flink integration scenarios."""
    
    def test_spark_flink_resources_sufficient(self, service_urls, http_session):
        """Test both Spark and Flink have sufficient resources."""
        # Get Spark resources
        spark_response = http_session.get(f"{service_urls['spark_master']}/json/", timeout=10)
        spark_data = spark_response.json()
        spark_cores = spark_data.get("cores", 0)
        spark_workers = spark_data.get("aliveworkers", 0)
        
        # Get Flink resources
        flink_response = http_session.get(f"{service_urls['flink_jobmanager']}/overview", timeout=10)
        flink_data = flink_response.json()
        flink_slots = flink_data.get("slots-total", 0)
        flink_taskmanagers = flink_data.get("taskmanagers", 0)
        
        print(f"🔄 Processing Layer Resources:")
        print(f"  Spark: {spark_workers} workers, {spark_cores} cores")
        print(f"  Flink: {flink_taskmanagers} taskmanagers, {flink_slots} slots")
        
        # Both should have resources
        assert spark_workers > 0 and spark_cores > 0, "Spark should have workers and cores"
        assert flink_taskmanagers > 0 and flink_slots > 0, "Flink should have taskmanagers and slots"
        
        print("✅ Both Spark and Flink clusters are properly resourced")
