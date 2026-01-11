import os
import logging
from dotenv import load_dotenv
from minio import Minio
import pika

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("TestConn")

def test_minio():
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    bucket = os.getenv("MINIO_BUCKET", "lake")
    
    logger.info(f"Testing MinIO at {endpoint}...")
    try:
        client = Minio(endpoint, access_key=access, secret_key=secret, secure=False)
        if client.bucket_exists(bucket):
            logger.info(f"✅ MinIO Connected! Bucket '{bucket}' exists.")
        else:
            logger.warning(f"❌ MinIO Connected, but bucket '{bucket}' NOT FOUND.")
    except Exception as e:
        logger.error(f"❌ MinIO Failed: {e}")

def test_rabbitmq():
    host = os.getenv("RABBIT_HOST", "localhost")
    port = int(os.getenv("RABBIT_PORT", "5672"))
    user = os.getenv("RABBIT_USER", "admin")
    password = os.getenv("RABBIT_PASS", "admin123")
    
    logger.info(f"Testing RabbitMQ at {host}:{port}...")
    try:
        credentials = pika.PlainCredentials(user, password)
        params = pika.ConnectionParameters(host=host, port=port, credentials=credentials, connection_attempts=1)
        connection = pika.BlockingConnection(params)
        logger.info("✅ RabbitMQ Connected!")
        connection.close()
    except Exception as e:
        logger.error(f"❌ RabbitMQ Failed: {e}")

if __name__ == "__main__":
    load_dotenv()
    test_minio()
    test_rabbitmq()
