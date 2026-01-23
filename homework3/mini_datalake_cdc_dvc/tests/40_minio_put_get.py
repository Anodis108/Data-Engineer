import os
import io
from minio import Minio

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS", "minioadmin")
MINIO_SECRET = os.getenv("MINIO_SECRET", "minioadmin123")
BUCKET = os.getenv("MINIO_BUCKET", "lake")

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS,
    secret_key=MINIO_SECRET,
    secure=False,
)

key = "raw/tests/hello.txt"
data = b"hello from minio test\n"

if not client.bucket_exists(BUCKET):
    raise RuntimeError(f"Bucket {BUCKET} not found")

client.put_object(
    BUCKET,
    key,
    io.BytesIO(data),
    length=len(data),
    content_type="text/plain",
)

resp = client.get_object(BUCKET, key)
out = resp.read()
resp.close()
resp.release_conn()

assert out == data, f"Mismatch: {out!r}"
print(f"✅ MinIO put/get OK: s3://{BUCKET}/{key}")
