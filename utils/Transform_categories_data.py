"""
Hàm trả về các thể loại sách con (không còn thể loại nhỏ nữa)
Và các đường link dẫn đến sách để trả về
"""

import pandas as pd
from pathlib import Path

# ==================== CONFIG ===================
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

INPUT_FILE = DATA_DIR / "categories.csv"
OUTPUT_FILE = DATA_DIR / "full_url_link.csv"
# ================================================

# Trả về lỗi nếu file không tồn tại
if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Không tìm thấy file categories.csv:\n{INPUT_FILE}")

df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")


# Kiểm tra các thuộc tính cần kiểm tra
required_columns = [
    "id",
    "name",
    "url_key",
    "product_count",
    "children_count",
    "parent_id",
]

missing_columns = [column for column in required_columns if column not in df.columns]

if missing_columns:
    raise ValueError(f"categories.csv thiếu các cột: {missing_columns}")


# Chỉ lấy category lá
# children_count = 0 → category không còn category con nào nữa.

leaf_categories = df[df["children_count"] == 0].copy()


# TẠO LINK TIKI
leaf_categories["link"] = (
    "https://tiki.vn/"
    + leaf_categories["url_key"].astype(str)
    + "/c"
    + leaf_categories["id"].astype(str)
)


# SẮP XẾP THEO SỐ LƯỢNG SẢN PHẨM
# Nhiều sách → ít sách.
# NaN được giữ nguyên và đưa xuống cuối.

leaf_categories = leaf_categories.sort_values(
    by="product_count", ascending=False, na_position="last"
)


# Lưu file
result = leaf_categories[
    ["id", "name", "url_key", "product_count", "link", "parent_id"]
].copy()
result.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print("=" * 60)
print("EXTRACT CATEGORIES HOÀN TẤT")
print("=" * 60)

print(f"File đầu vào           : {INPUT_FILE}")
print(f"File đầu ra            : {OUTPUT_FILE}")
print(f"Tổng category ban đầu  : {len(df):,}")
print(f"Số category lá         : {len(result):,}")
print(f"Product count bị trống : {result['product_count'].isna().sum():,}")

print("\n5 category đầu tiên:")
print(result.head())

print("\nĐã lưu thành công!")
