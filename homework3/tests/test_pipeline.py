"""
General Pipeline Health Tests
=============================
High-level health checks for all 7 layers of the data pipeline.
"""
import pytest
import requests
import pika
from minio import Minio
import psycopg2
from typing import Dict, Any


class TestLayer1Source:
    """Test Layer 1: Source Systems (Postgres & Camera)."""
    
    def test_postgres_source_connection(self):
        """Test connection to CDC Postgres source."""
        try:
            conn = psycopg2.connect(
                host="localhost",
                port="5433",  # Mapped port
                user="dbz",
                password="dbz",
                dbname="inventory"
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            conn.close()
            
            print(f"✅ Postgres Source: Connected")
            assert result[0] == 1
        except Exception as e:
            pytest.fail(f"Could not connect to Postgres source: {e}")


class TestLayer2Ingestion:
    """Test Layer 2: Ingestion & Messaging (Kafka & RabbitMQ)."""
    
    def test_kafka_connect_health(self, service_urls, http_session):
        """Test Kafka Connect health."""
        url = f"{service_urls['kafka_connect']}/"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Kafka Connect: {data.get('version')}")
    
    def test_rabbitmq_connection(self):
        """Test RabbitMQ connection."""
        try:
            credentials = pika.PlainCredentials('admin', 'admin123')
            parameters = pika.ConnectionParameters(
                'localhost', 
                5672, 
                '/', 
                credentials,
                connection_attempts=3,
                retry_delay=2
            )
            connection = pika.BlockingConnection(parameters)
            print(f"✅ RabbitMQ: Connected")
            connection.close()
        except Exception as e:
            pytest.fail(f"Could not connect to RabbitMQ: {e}")


class TestLayer3Storage:
    """Test Layer 3: Storage (MinIO)."""
    
    def test_minio_buckets(self, service_urls):
        """Test MinIO buckets existence."""
        try:
            client = Minio(
                "localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin123",
                secure=False
            )
            
            buckets = client.list_buckets()
            bucket_names = [b.name for b in buckets]
            
            print(f"✅ MinIO Buckets: {bucket_names}")
            
            # Verify critical buckets
            assert "lake" in bucket_names, "Bucket 'lake' missing"
            assert "dvcstore" in bucket_names, "Bucket 'dvcstore' missing"
            
        except Exception as e:
            pytest.fail(f"MinIO check failed: {e}")


class TestLayer5Query:
    """Test Layer 5: Query & Serving (Trino)."""
    
    def test_trino_health(self, service_urls, http_session):
        """Test Trino coordinator health."""
        url = f"{service_urls['trino']}/v1/info"
        response = http_session.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Trino: {data.get('nodeVersion', {}).get('version')}")
        
        assert not data.get("starting"), "Trino is still starting"


class TestFullPipelineHealth:
    """Integration health check."""
    
    def test_all_services_up(self, service_urls, http_session):
        """Quick check that all defined service URLs are reachable."""
        failures = []
        
        for name, url in service_urls.items():
            # Skip RabbitMQ here as it's AMQP mostly, and kafka usually internal
            if "rabbitmq" in name: 
                continue
                
            try:
                # Adjust path for specific services to get a 200 OK
                check_url = url
                if "prom" in name: check_url += "/-/ready"
                elif "graf" in name: check_url += "/api/health"
                elif "air" in name: check_url += "/health"
                elif "spark" in name: check_url += "/json/"
                elif "flink" in name: check_url += "/overview"
                elif "mini" in name: check_url += "/minio/health/live"
                
                resp = http_session.get(check_url, timeout=5)
                if resp.status_code >= 500:
                    failures.append(f"{name}: HTTP {resp.status_code}")
            except Exception as e:
                failures.append(f"{name}: {str(e)}")
        
        if failures:
            pytest.fail(f"Services down: {', '.join(failures)}")
        
        print("✅ All HTTP services are reachable")
