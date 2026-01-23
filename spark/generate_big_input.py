"""
Script này sẽ nhân bản nội dung file input.txt thành file input_big.txt với số dòng lớn (big data)
"""
import os

INPUT_FILE = "input.txt"
OUTPUT_FILE = "input_big.txt"
REPEAT = 1000000  # Số lần lặp lại, có thể điều chỉnh để tạo file lớn hơn hoặc nhỏ hơn

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Không tìm thấy file {INPUT_FILE}")
        return
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for _ in range(REPEAT):
            f.writelines(lines)
    print(f"Đã tạo file {OUTPUT_FILE} với khoảng {len(lines) * REPEAT} dòng.")

if __name__ == "__main__":
    main()