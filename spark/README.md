# Ví dụ Spark: Đếm số lần xuất hiện của từ (Word Count)

Ví dụ này minh họa cách sử dụng PySpark để thực hiện đếm số lần xuất hiện của từng từ trong một file văn bản. Bạn có thể sử dụng ví dụ này làm nền tảng cho các bài toán xử lý dữ liệu phức tạp hơn.

## Yêu cầu
- PySpark

## Cách chạy chương trình
1. Cài đặt PySpark nếu chưa có:
   ```bash
   pip install pyspark
   ```
2. Đặt file văn bản tên là `input.txt` vào cùng thư mục với script này, hoặc sửa đường dẫn trong script cho phù hợp với dữ liệu của bạn.
3. Chạy script:
   ```bash
   python word_count.py
   ```

---

## Giải thích tác dụng của Spark trong code này

Apache Spark là một nền tảng xử lý dữ liệu lớn (Big Data) mạnh mẽ, cho phép xử lý song song trên nhiều máy hoặc nhiều lõi CPU. Trong code này, Spark giúp:

- Đọc dữ liệu lớn từ file một cách hiệu quả.
- Xử lý, biến đổi dữ liệu (tách từ, đếm số lần xuất hiện) bằng các thao tác phân tán.
- Tận dụng sức mạnh tính toán phân tán để xử lý dữ liệu nhanh hơn nhiều so với các phương pháp truyền thống.

## Ứng dụng thực tế của Spark

Spark thường được sử dụng trong các bài toán:
- Phân tích log, dữ liệu lớn (Big Data Analytics)
- Xử lý dữ liệu thời gian thực (Real-time Data Processing)
- Học máy (Machine Learning) trên tập dữ liệu lớn
- ETL (Extract, Transform, Load) cho kho dữ liệu

Ví dụ: Đếm số lần xuất hiện của từ trong hàng triệu dòng log, phân tích dữ liệu khách hàng, xử lý dữ liệu cảm biến IoT, v.v.
