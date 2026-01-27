"""
Pytest Configuration & Shared Fixtures
======================================
Shared fixtures for testing the data pipeline.
"""
import pytest
import requests
import time
from typing import Dict, Any


@pytest.fixture(scope="session")
def service_urls() -> Dict[str, str]:
    """Service URLs for testing."""
    return {
        # Processing Layer
        "spark_master": "http://localhost:8090",
        "spark_worker": "http://localhost:8091",
        "flink_jobmanager": "http://localhost:8092",
        
        # Orchestration Layer
        "airflow": "http://localhost:8085",
        
        # Monitoring Layer
        "prometheus": "http://localhost:9090",
        "grafana": "http://localhost:3000",
        
        # Storage & Query Layer
        "minio": "http://localhost:9000",
        "trino": "http://localhost:8080",
        "kafka_ui": "http://localhost:8081",
        "kafka_connect": "http://localhost:8083",
        "rabbitmq": "http://localhost:15672",
    }


@pytest.fixture(scope="session")
def airflow_credentials() -> Dict[str, str]:
    """Airflow login credentials."""
    return {
        "username": "admin",
        "password": "admin123"
    }


@pytest.fixture(scope="session")
def grafana_credentials() -> Dict[str, str]:
    """Grafana login credentials."""
    return {
        "username": "admin",
        "password": "admin123"
    }


def wait_for_service(url: str, timeout: int = 30, check_interval: int = 2) -> bool:
    """
    Wait for a service to become available.
    
    Args:
        url: Service URL to check
        timeout: Maximum wait time in seconds
        check_interval: Time between checks in seconds
        
    Returns:
        True if service is available, False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code < 500:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(check_interval)
    return False


@pytest.fixture(scope="session", autouse=True)
def wait_for_core_services(service_urls):
    """Wait for core services to be ready before running tests."""
    print("\n⏳ Waiting for core services to be ready...")
    
    critical_services = [
        ("MinIO", f"{service_urls['minio']}/minio/health/live"),
        ("Spark Master", f"{service_urls['spark_master']}/json/"),
        ("Flink JobManager", f"{service_urls['flink_jobmanager']}/overview"),
        ("Airflow", f"{service_urls['airflow']}/health"),
        ("Prometheus", f"{service_urls['prometheus']}/-/ready"),
        ("Grafana", f"{service_urls['grafana']}/api/health"),
    ]
    
    for service_name, url in critical_services:
        print(f"  Checking {service_name}...", end=" ")
        if wait_for_service(url, timeout=60):
            print("✅")
        else:
            print("❌")
            pytest.skip(f"{service_name} not available")
    
    print("✅ All core services ready!\n")


@pytest.fixture
def http_session():
    """Reusable HTTP session for tests."""
    session = requests.Session()
    session.headers.update({"User-Agent": "pytest-data-pipeline"})
    yield session
    session.close()
