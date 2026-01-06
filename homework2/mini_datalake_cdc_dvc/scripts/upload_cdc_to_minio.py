import argparse
import os
from minio import Minio

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

def main():
    ap = argparse.ArgumentParser(description="Upload local raw CDC folder to MinIO lake bucket")
    ap.add_argument("--local", default="lake/raw/cdc", help="local raw root")
    ap.add_argument("--bucket", default="lake", help="MinIO bucket")
    ap.add_argument("--prefix", default="raw/cdc", help="prefix in bucket")
    args = ap.parse_args()

    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )

    if not client.bucket_exists(args.bucket):
        client.make_bucket(args.bucket)

    # Upload all files under local folder preserving relative path
    local_root = os.path.abspath(args.local)
    for root, _, files in os.walk(local_root):
        for fn in files:
            lp = os.path.join(root, fn)
            rel = os.path.relpath(lp, local_root).replace("\\", "/")
            obj = f"{args.prefix}/{rel}"
            print(f"⬆️ {lp} -> s3://{args.bucket}/{obj}")
            client.fput_object(args.bucket, obj, lp)

    print("✅ Upload done")

if __name__ == "__main__":
    main()
