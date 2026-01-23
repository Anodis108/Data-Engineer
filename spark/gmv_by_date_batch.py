"""
Bài tập Spark batch tính GMV theo ngày, partition theo date, backfill 7 ngày
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as spark_sum, to_date
import time

# Khởi tạo SparkSession
spark = SparkSession.builder \
    .appName("GMVByDate") \
    .getOrCreate()

# Giả lập dữ liệu giao dịch (transaction) cho 7 ngày
# Trong thực tế, bạn sẽ đọc từ file hoặc database
import pandas as pd
from datetime import datetime, timedelta
import random

data = []
start_date = datetime.today() - timedelta(days=6)
for i in range(7):
    date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
    for j in range(1000):  # 1000 giao dịch mỗi ngày
        data.append({
            'order_id': f'{date}_{j}',
            'order_date': date,
            'amount': random.randint(100, 1000)
        })

# Tạo DataFrame từ dữ liệu giả lập
pdf = pd.DataFrame(data)
df = spark.createDataFrame(pdf)

# Đo thời gian bắt đầu
start_time = time.time()

# Tính GMV (Gross Merchandise Value) theo ngày
# Partition theo date (thực tế khi ghi ra file, ở đây chỉ minh họa)
gmv_by_date = df.groupBy('order_date').agg(spark_sum('amount').alias('gmv'))

# Hiển thị kết quả
gmv_by_date.show()

# (Tùy chọn) Lưu ra file partition theo date
# gmv_by_date.write.partitionBy('order_date').csv('output_gmv_by_date')

# Đo thời gian kết thúc
end_time = time.time()
print(f"Thời gian tính toán Spark: {end_time - start_time:.2f} giây")

# Giải thích shuffle:
print("\nGiải thích shuffle:")
print("Shuffle xảy ra khi thực hiện groupBy('order_date') để tính tổng amount theo ngày. Spark phải di chuyển dữ liệu giữa các node để gom các bản ghi cùng ngày lại với nhau, từ đó mới tính được tổng GMV cho từng ngày. Đây là một trong những nguyên nhân khiến job Spark có thể chậm nếu dữ liệu lớn hoặc số lượng partition không hợp lý.")

spark.stop()
