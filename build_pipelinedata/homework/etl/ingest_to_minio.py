import os
from minio import Minio
from minio.error import S3Error

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

BUCKET = "iot-time-series"
PREFIX = "pump/"

OUT_DIR = os.path.join(os.path.dirname(__file__), "out")

def main():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )

    # bucket đã được tạo bởi minio-init, nhưng check cho chắc
    found = client.bucket_exists(BUCKET)
    if not found:
        client.make_bucket(BUCKET)

    files = [f for f in os.listdir(OUT_DIR) if f.endswith(".parquet")]
    if not files:
        raise RuntimeError("No parquet files found. Run generate_data.py first.")

    for f in files:
        local_path = os.path.join(OUT_DIR, f)
        object_name = PREFIX + f
        print(f"⬆️ Uploading {local_path} -> s3://{BUCKET}/{object_name}")
        client.fput_object(BUCKET, object_name, local_path)

    print("✅ Done upload.")

if __name__ == "__main__":
    try:
        main()
    except S3Error as e:
        print("❌ MinIO error:", e)
        raise
