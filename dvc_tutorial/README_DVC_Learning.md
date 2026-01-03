# DVC (Data Version Control) -- Học & Thực Hành Từng Bước

## Mục tiêu học DVC

-   Hiểu vì sao Git không phù hợp cho data/model lớn
-   Biết DVC giải quyết vấn đề gì trong Data Engineering / ML
-   Thực hành version hóa dataset
-   Biết cách rollback dữ liệu như rollback code
-   Chuẩn bị tư duy để kết hợp DVC với CDC / Kafka / Data Lake

------------------------------------------------------------------------

## DVC là gì?

DVC (Data Version Control) là công cụ quản lý version cho: - Dataset
(CSV, Parquet, images, video...) - Model (pth, pt, onnx...) - Artifact
sinh ra từ pipeline

DVC không thay thế Git, mà bổ sung cho Git.

-   Git: code + metadata
-   DVC: data + model (file lớn)

------------------------------------------------------------------------

## Kiến trúc tư duy DVC

Git repo:

    .
    ├── data/
    │   └── train.csv
    ├── data/train.csv.dvc
    ├── scripts/
    ├── dvc.yaml
    └── dvc.lock

-   File `.dvc` chỉ chứa metadata
-   Dữ liệu thật nằm trong DVC cache / remote

------------------------------------------------------------------------

## Cài đặt DVC

``` bash
pip install dvc
```

Khởi tạo project:

``` bash
git init
dvc init
```

------------------------------------------------------------------------

## Track dataset với DVC

``` bash
dvc add data/train.csv
git add data/train.csv.dvc .gitignore
git commit -m "Track training dataset with DVC"
```

------------------------------------------------------------------------

## DVC Remote

``` bash
mkdir ../dvc-storage
dvc remote add -d localstore ../dvc-storage
dvc push
```

------------------------------------------------------------------------

## Update & version dataset

``` bash
dvc add data/train.csv
git add data/train.csv.dvc
git commit -m "Update dataset v2"
dvc push
```

------------------------------------------------------------------------

## Rollback dataset

``` bash
git checkout <commit_cu>
dvc checkout
```

------------------------------------------------------------------------

## DVC Pipeline

``` bash
dvc stage add -n preprocess   -d scripts/preprocess.py   -d data/raw.csv   -o data/processed.csv   python scripts/preprocess.py
```

``` bash
dvc repro
```

------------------------------------------------------------------------

## Khi nào dùng DVC?

-   Dataset lớn
-   Data thay đổi theo thời gian
-   Cần reproducibility
-   Kết hợp ML / AI / Data Engineering

------------------------------------------------------------------------

## Tóm tắt

-   DVC = version control cho data
-   Git + DVC = chuẩn industry
-   CDC tạo dòng dữ liệu
-   DVC version snapshot dữ liệu

------------------------------------------------------------------------

## Giải thích lệnh `dvc stage add` (RẤT QUAN TRỌNG)

Ví dụ:

``` bash
dvc stage add -n preprocess   -d scripts/preprocess.py   -d data/raw.csv   -o data/processed.csv   python scripts/preprocess.py
```

### Lệnh này dùng để làm gì?

Lệnh này **khai báo một bước (stage) trong DVC pipeline**, nói với DVC
rằng:

> "Để tạo ra `data/processed.csv` thì cần chạy
> `python scripts/preprocess.py`,\
> và kết quả này phụ thuộc vào code + dữ liệu đầu vào nào."

------------------------------------------------------------------------

### Giải thích từng phần

**`dvc stage add`**\
Tạo một stage mới trong pipeline (tương tự step trong Airflow /
Makefile).

**`-n preprocess`**\
Tên stage -- giúp đọc pipeline, debug và gọi lại stage.

**`-d scripts/preprocess.py`**\
Dependency (phụ thuộc): nếu code xử lý thay đổi → stage phải chạy lại.

**`-d data/raw.csv`**\
Dependency dữ liệu đầu vào: nếu raw data đổi → output không còn hợp lệ.

**`-o data/processed.csv`**\
Output của stage: file này sẽ được DVC theo dõi và version hóa.

**`python scripts/preprocess.py`**\
Lệnh thực tế để sinh ra output.\
DVC không xử lý dữ liệu, DVC chỉ quản lý **khi nào cần chạy lại**.

------------------------------------------------------------------------

### Sau khi chạy lệnh này sẽ có gì?

DVC tự động sinh:

**`dvc.yaml`**

``` yaml
stages:
  preprocess:
    cmd: python scripts/preprocess.py
    deps:
      - scripts/preprocess.py
      - data/raw.csv
    outs:
      - data/processed.csv
```

**`dvc.lock`**

``` yaml
stages:
  preprocess:
    deps:
      data/raw.csv:
        md5: ...
    outs:
      data/processed.csv:
        md5: ...
```

`dvc.lock` là **sự thật tuyệt đối** của pipeline tại thời điểm đó.

------------------------------------------------------------------------

### Chạy lại pipeline

``` bash
dvc repro
```

DVC sẽ: - So sánh hash của dependencies - Chỉ chạy lại stage **khi input
hoặc code thay đổi** - Không chạy thừa

------------------------------------------------------------------------

### Khi nào nên dùng `dvc stage add`?

-   Xử lý dữ liệu (raw → processed)
-   Transform / feature engineering
-   Sinh dataset trung gian
-   Pipeline nhiều bước

### Khi nào KHÔNG nên dùng?

-   Streaming job chạy vô hạn (Kafka consumer realtime)
-   Job không có output file cố định

------------------------------------------------------------------------

### Tóm tắt nhanh

`dvc stage add` = **khai báo 1 bước xử lý dữ liệu có input -- output --
command rõ ràng**,\
giúp pipeline **reproducible, incremental và dễ quản lý**.
