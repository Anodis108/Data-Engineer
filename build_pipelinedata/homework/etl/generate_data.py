import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

OUT_DIR = os.path.join(os.path.dirname(__file__), "out")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=3)
    days = 3
    freq = "1min"  # 1 phút / điểm

    for d in range(days):
        day_start = start + timedelta(days=d)
        day_end = day_start + timedelta(days=1)

        ts = pd.date_range(day_start, day_end, freq=freq, inclusive="left")
        n = len(ts)

        # giả lập “pump sensor”
        pressure = np.random.normal(loc=120, scale=20, size=n).astype(float)
        velocity = np.random.normal(loc=10, scale=2, size=n).astype(float)
        speed = np.random.normal(loc=1800, scale=150, size=n).astype(float)

        # tạo vài spike pressure > 150 để test alarm
        spike_idx = np.random.choice(n, size=max(5, n // 200), replace=False)
        pressure[spike_idx] += np.random.uniform(40, 80, size=len(spike_idx))

        df = pd.DataFrame({
            "event_timestamp": ts,
            "pressure": pressure,
            "velocity": velocity,
            "speed": speed,
        })

        out_path = os.path.join(OUT_DIR, f"pump_{day_start.date().isoformat()}.parquet")
        df.to_parquet(out_path, engine="pyarrow", index=False)
        print("✅ Wrote:", out_path, "rows=", len(df))

if __name__ == "__main__":
    main()
