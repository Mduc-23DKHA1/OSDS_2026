"""
Gọi API tại thể loại "Sách tiếng Việt" trong Tiki-shop
và lấy tất cả các thông tin về các thể loại con và thể loại cháu
---------------------------------------------------------------
Sau đó trả về file json với tên gọi "categories_316.json" nằm trong mục data
"""

import requests
import json
import os

# ================= CONFIG =================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(DATA_DIR, "categories_316.json")
# ==========================================

url = "https://tiki.vn/api/v2/categories"

params = {"include": "children", "parent_id": 316}

response = requests.get(url, params=params)
response.raise_for_status()

data = response.json()

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
