"""
==============================================================================
||  Kiểm tra xem các category có đầy đủ những thuộc tính cần quan tâm?      ||
||  - id             : Mã số id của category                                ||
||  - parent_id      : Mã số id của category cha                            ||
||  - name           : Tên của category                                     ||
||  - url_path       : Đường dẫn của category                               ||
||  - product_count  : Số lượng sản phẩm của category                       ||
||  - children       : Danh sách các category con                           ||
||  - is_leaf        : True nếu category không có con, False nếu có con     ||
==============================================================================
"""

import json
with open("../data/categories_316.json", "r", encoding="utf-8") as f:
    data = json.load(f)

def check_attributes(categories):
    for i, category in enumerate(categories):
        if "id" not in category:
            print(f"Category {i} is missing id")
        if "parent_id" not in category:
            print(f"Category {i} is missing parent_id")
        if "name" not in category:
            print(f"Category {i} is missing name")
        if "url_path" not in category:
            print(f"Category {i} is missing url_path")
        if "product_count" not in category:
            print(f"Category {i} is missing product_count")
        if "children" not in category:
            print(f"Category {i} is missing children")
        if "is_leaf" not in category:
            print(f"Category {i} is missing is_leaf")

check_attributes(data["data"])