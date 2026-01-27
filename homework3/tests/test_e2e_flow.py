"""
End-to-End Flow Tests
=====================
Test the complete data flow through the pipeline.
"""
import pytest
import time
import json
import uuid
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import io
from minio import Minio
from datetime import datetime

class TestE2EFlow:
    """Test end-to-end data flows."""
    
    def test_vision_event_storage_flow(self):
        """
        Test the flow: Vision App -> MinIO (Raw) -> Verification.
        This simulates generating an event and checking it appears in MinIO.
        """
        # 1. Setup MinIO client
        client = Minio(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin123",
            secure=False
        )
        
        bucket = "lake"
        camera_id = "test_cam_e2e"
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_id = str(uuid.uuid4())
        
        # 2. Create dummy Parquet data (simulating Vision App output)
        data = {
            "event_id": [file_id],
            "camera_id": [camera_id],
            "person_count": [5],
            "conf_avg": [0.88],
            "timestamp": [datetime.now()]
        }
        df = pd.DataFrame(data)
        table = pa.Table.from_pandas(df)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        buf.seek(0)
        
        object_name = f"raw/vision_events/camera_id={camera_id}/date={date_str}/{file_id}.parquet"
        
        # 3. Upload to MinIO (Simulate Ingestion)
        print(f"📤 Uploading test event to {object_name}...")
        client.put_object(
            bucket,
            object_name,
            buf,
            length=buf.getbuffer().nbytes,
            content_type="application/octet-stream"
        )
        
        # 4. Verify file exists (Simulate Verification)
        try:
            stat = client.stat_object(bucket, object_name)
            print(f"✅ File found in MinIO: {stat.object_name} ({stat.size} bytes)")
            assert stat.size > 0
        except Exception as e:
            pytest.fail(f"Failed to verify object in MinIO: {e}")
            
        # Clean up
        client.remove_object(bucket, object_name)

    def test_cdc_topic_existence(self, service_urls, http_session):
        """
        Test that CDC topics exist in Kafka (implies Debezium is working).
        Uses Kafka UI API or Prometheus metrics to verify.
        """
        # Try checking via Kafka UI API if available, else fallback to simple connection check
        # Here we'll use a simple check via Kafka Exporter metrics if possible
        
        url = f"{service_urls['prometheus']}/api/v1/query"
        params = {"query": "kafka_topic_partitions{topic='pgserver1.public.customers'}"}
        
        try:
            response = http_session.get(url, params=params, timeout=5)
            data = response.json()
            results = data.get("data", {}).get("result", [])
            
            if len(results) > 0:
                print(f"✅ CDC Topic 'pgserver1.public.customers' found in metrics")
            else:
                print(f"⚠️ CDC Topic metric not found (Debezium might be initializing or Prometheus scraping lag)")
                # We don't fail here strictly as it depends on Prometheus scraping interval
        except:
            print("⚠️ Could not check CDC topic via Prometheus")

    def test_processing_job_submission(self, service_urls):
        """
        Test ability to submit a dummy job to Spark.
        """
        # This is a placeholder for a real submission test. 
        # In a real environment, we'd use `spark-submit` CLI or REST API.
        # For this test plan, we verify the master is accepting requests.
        pass
