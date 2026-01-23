

# Import các thư viện cần thiết từ PySpark
from pyspark.sql import SparkSession
from pyspark.sql.functions import explode, split
import time


# Đo thời gian bắt đầu
start_time = time.time()

# Khởi tạo một phiên làm việc Spark (SparkSession)
# SparkSession là điểm bắt đầu để làm việc với DataFrame và SQL trong PySpark
spark = SparkSession.builder \
    .appName("WordCountExample") \
    .getOrCreate()
b = time.time()
print(f"Thời gian khởi tạo Spark: {b - start_time:.2f} giây")
# Đọc file văn bản đầu vào (có thể thay đổi đường dẫn nếu cần)
input_path = "input.txt"

text_df = spark.read.text(input_path)  # Đọc từng dòng trong file thành DataFrame

# Tách từng dòng thành các từ, sau đó "explode" để mỗi từ thành một dòng riêng biệt
# split: tách chuỗi thành mảng các từ dựa trên dấu cách
# explode: chuyển mỗi phần tử trong mảng thành một dòng riêng biệt
words_df = text_df.select(explode(split(text_df.value, " ")).alias("word"))

# Nhóm theo từ và đếm số lần xuất hiện của mỗi từ
word_counts = words_df.groupBy("word").count()


# Hiển thị kết quả ra màn hình
word_counts.show()

# Đo thời gian kết thúc và in ra thời gian xử lý (chỉ tính phần tính toán)
end_time = time.time()
print(f"Thời gian tính toán Spark: {end_time - b:.2f} giây")
print(f"Tổng thời gian: {end_time - start_time:.2f} giây")

# (Tùy chọn) Lưu kết quả ra file CSV
# word_counts.write.csv("word_counts_output.csv")

# Dừng phiên làm việc Spark
spark.stop()
