import os
import io
import time
from datetime import datetime, timezone
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS", "minioadmin")
MINIO_SECRET = os.getenv("MINIO_SECRET", "minioadmin123")
BUCKET = os.getenv("MINIO_BUCKET", "lake")

camera_id = os.getenv("CAMERA_ID", "cam01")

now = datetime.now(timezone.utc)
date = now.strftime("%Y-%m-%d")
hour = now.strftime("%H")

# fake 3 rows of 5-second windows
rows = []
base_ts = int(time.time() * 1000)
for i in range(3):
    ts_start = base_ts + i * 5000
    ts_end = ts_start + 5000
    rows.append(
        dict(
            event_id=f"test-{ts_start}",
            camera_id=camera_id,
            ts_start=pd.to_datetime(ts_start, unit="ms", utc=True).tz_convert(None),
            ts_end=pd.to_datetime(ts_end, unit="ms", utc=True).tz_convert(None),    
            person_count=1 + (i % 2),
            conf_avg=0.75,
            conf_max=0.92,
            frame_uri=f"s3://{BUCKET}/raw/vision_media/camera_id={camera_id}/date={date}/hour={hour}/{ts_start}.jpg",
        )
    )

df = pd.DataFrame(rows)

table = pa.Table.from_pandas(df)
buf = io.BytesIO()
pq.write_table(table, buf, compression="snappy")
buf.seek(0)

key = f"raw/vision_events/camera_id={camera_id}/date={date}/hour={hour}/events_test.parquet"

client = Minio(MINIO_ENDPOINT, MINIO_ACCESS, MINIO_SECRET, secure=False)
client.put_object(
    BUCKET,
    key,
    buf,
    length=buf.getbuffer().nbytes,
    content_type="application/octet-stream",
)

print(f"✅ Wrote parquet: s3://{BUCKET}/{key} rows={len(df)}")
