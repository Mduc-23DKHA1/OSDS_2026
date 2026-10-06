"""
=============================================================
    LẤY TẤT CẢ CÁC SẢN PHẨM SÁCH TRONG 1 CATEGORY CỤ THỂ
=============================================================
QUY TRÌNH:
    1. CONFIG
        - Cấu hình ban đầu cho phép lấy 1 hay nhiều category
        - Nếu chỉ 1 category thì: dữ liệu sẽ lưu có dạng "data/products/category_<ID>.csv"
        - Nếu nhiều category thì: sẽ duyệt tất cả các category trong file "categories.csv"
    2. TIKI API
        - url: https://tiki.vn/api/personalish/v1/blocks/listings
        - params cố định:
            - limit: 40
            - include: advertisement
            - aggregations: 2
            - version: home-persionalized
            - trackity_id: 065c7957-441c-ad9d-524e-4f326a13bc37
        - params thay đổi:
            - category: <ID>
            - page: <Page hiện tại> (thay đổi liên tục theo vòng lặp để gọi và lấy dữ liệu)
            - urlKey: <url_key của category hiện tại>
    3. CẤU HÌNH RETRY
        - Retry HTTP tự động đối với những lỗi tạm thời
    4. TẠO SESSION
        - Tạo session để gọi API
    5. LẤY CATEGORY
        - Lấy category từ CONFIG hoặc CSV
    6. GỌI API MỘT PAGE
        - Gọi API với params cố định và thay đổi
    7. BÓC TÁCH PRODUCT
        - Bóc tách product từ API response (lấy các thuộc tính và thông tin cần thiết)
        - Các thuộc tính lưu gồm:
            + id                (id của sách)(Khóa chính)
            + name              (tên sách)
            + url               (url của sách)
            + url_key           (url_key của sách)
            + price             (giá)
            + original_price    (giá gốc)
            + rating_average    (đánh giá trung bình)
            + review_count      (số lượt đánh giá)
            + quantity_sold     (số lượt bán)
            + category_id       (id của category)(Khóa ngoại)
    8. LƯU VÀO CSV
        - Lưu products vào file csv dạng: data/products/category_<ID>.csv
"""

import os
import time
import random
import requests
import pandas as pd

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# 1. CONFIG
# ============================================================

# Chọn cách lấy category:
# "config"  -> dùng CATEGORY_ID + URL_KEY bên dưới
# "random"  -> lấy ngẫu nhiên 1 category từ CATEGORY_CSV
CATEGORY_MODE = "random"

# Nếu CATEGORY_MODE = "config"
CATEGORY_ID = 67992
URL_KEY = "but-ky-tu-truyen"

# Nếu CATEGORY_MODE = "random"
CATEGORY_CSV = "data/SachThieuNhi_url_link.csv"

# File output
OUTPUT_DIR = "Khang/API_Crawl/data/products"

# Nếu config thì file sẽ có dạng:
# data/products/category_900.csv
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"category_{CATEGORY_ID}.csv")


# ============================================================
# 2. TIKI API
# ============================================================

API_URL = "https://tiki.vn/api/personalish/v1/blocks/listings"


# Các params cố định
FIXED_PARAMS = {
    "limit": 40,
    "include": "advertisement",
    "aggregations": 2,
    "version": "home-persionalized",
    "trackity_id": "065c7957-441c-ad9d-524e-4f326a13bc37",
}


# ============================================================
# 3. CẤU HÌNH RETRY
# ============================================================

# Retry HTTP tự động đối với những lỗi tạm thời
RETRY_STRATEGY = Retry(
    total=5,
    connect=5,
    read=5,
    status=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)


# ============================================================
# 4. TẠO SESSION
# ============================================================

session = requests.Session()

adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)

session.mount("https://", adapter)
session.mount("http://", adapter)

session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    }
)


# ============================================================
# 5. LẤY CATEGORY
# ============================================================


def get_category():
    """
    Trả về:
        category_id
        url_key
    """

    # --------------------------------------------------------
    # Cách 1: lấy từ CONFIG
    # --------------------------------------------------------

    if CATEGORY_MODE == "config":

        print("[CATEGORY] Dùng category trong CONFIG")

        return CATEGORY_ID, URL_KEY

    # --------------------------------------------------------
    # Cách 2: lấy random từ CSV
    # --------------------------------------------------------

    elif CATEGORY_MODE == "random":

        print("[CATEGORY] Đọc category từ CSV...")

        df = pd.read_csv(CATEGORY_CSV)

        if df.empty:
            raise ValueError("CATEGORY_CSV không có dữ liệu.")

        # Lấy ngẫu nhiên 1 dòng
        row = df.sample(n=1, random_state=None).iloc[0]

        category_id = int(row["id"])
        url_key = row["url_key"]

        print(f"[CATEGORY] Random category: " f"{category_id} | {url_key}")

        return category_id, url_key

    else:
        raise ValueError("CATEGORY_MODE phải là 'config' hoặc 'random'")


# ============================================================
# 6. GỌI API MỘT PAGE
# ============================================================


def get_page(category_id, url_key, page):
    """
    Gọi Tiki Listing API cho một page.

    Return:
        list sản phẩm
    """

    # =========================
    # 1. Copy params cố định
    # =========================
    params = FIXED_PARAMS.copy()

    # =========================
    # 2. Các params thay đổi
    # =========================
    params.update(
        {
            "category": category_id,
            "page": page,
            "urlKey": url_key,
        }
    )

    print(f"\n[REQUEST] page={page}")

    # =========================
    # 3. Gọi API
    # =========================
    response = session.get(API_URL, params=params, timeout=20)

    # =========================
    # 4. Kiểm tra HTTP
    # =========================
    print(f"[STATUS] {response.status_code}")

    response.raise_for_status()

    # =========================
    # 5. Kiểm tra response
    # =========================
    if not response.text.strip():
        raise ValueError(f"Response rỗng ở page={page}")

    # =========================
    # 6. Parse JSON
    # =========================
    try:
        result = response.json()

    except ValueError as e:
        print(f"[ERROR] Response không phải JSON ở page={page}")
        print(f"[ERROR] {e}")

        print("[CONTENT-TYPE]", response.headers.get("Content-Type"))

        print("[RESPONSE ĐẦU]")
        print(response.text[:500])

        raise

    # =========================
    # 7. Lấy data
    # =========================
    data = result.get("data", [])

    print(f"[DATA] {len(data)} items")

    # =========================
    # 8. Trả về danh sách sản phẩm
    # =========================
    return data


# ============================================================
# 7. BÓC TÁCH PRODUCT
# ============================================================


def extract_product(product, category_id):
    """
    Chỉ lấy những field cần thiết.
    """

    product_id = product.get("id")

    url_key = product.get("url_key")

    # Tạo URL sản phẩm
    product_url = None

    if url_key:
        product_url = "https://tiki.vn/" + str(url_key) + ".html"

    # quantity_sold có dạng:
    #
    # "quantity_sold": {
    #     "value": 123
    # }
    #
    # nên cần lấy value bên trong.

    quantity_sold = product.get("quantity_sold")

    if isinstance(quantity_sold, dict):
        quantity_sold = quantity_sold.get("value")

    return {
        "id": product_id,
        "url_key": url_key,
        "url": product_url,
        "name": product.get("name"),
        "rating_average": product.get("rating_average"),
        "review_count": product.get("review_count"),
        "original_price": product.get("original_price"),
        "price": product.get("price"),
        "quantity_sold": quantity_sold,
        # Giữ lại category_id để sau này
        # liên kết với category.
        "category_id": category_id,
    }


# ============================================================
# 8. CRAWL TOÀN BỘ CATEGORY
# ============================================================


def crawl_category(category_id, url_key):
    """
    Crawl từ page 1 cho đến khi xác nhận
    data=[] sau nhiều lần retry.
    """

    all_products = []

    # Dùng set để chống duplicate product
    seen_ids = set()

    page = 1

    print()
    print("=" * 60)
    print("START CRAWL")
    print(f"Category ID : {category_id}")
    print(f"URL Key     : {url_key}")
    print("=" * 60)

    while True:

        print()
        print(f"[REQUEST] page={page}")

        # ----------------------------------------------------
        # Retry khi API trả data=[]
        # ----------------------------------------------------

        empty_retry = 0

        while True:

            try:

                data = get_page(category_id, url_key, page)

                # --------------------------------------------
                # Có dữ liệu
                # --------------------------------------------

                if data:

                    print(f"[OK] page={page} " f"-> {len(data)} products")

                    break

                # --------------------------------------------
                # data=[]
                # --------------------------------------------

                empty_retry += 1

                print(f"[EMPTY] page={page} " f"-> data=[] " f"(retry {empty_retry}/3)")

                if empty_retry >= 3:

                    print(f"[STOP] page={page} " f"-> xác nhận data=[]")

                    return all_products

                # Chờ trước khi retry
                wait_time = 3 * empty_retry

                print(f"[WAIT] {wait_time}s...")

                time.sleep(wait_time)

            except requests.RequestException as e:

                print(f"[ERROR] page={page}: {e}")

                print("[INFO] requests đã tự retry " "các lỗi HTTP tạm thời.")

                # Nếu vẫn exception sau Retry của
                # requests/urllib3 thì nghỉ thêm
                time.sleep(5)

                # Ở đây không return.
                # Tiếp tục thử page hiện tại.

            except ValueError as e:

                print(f"[JSON ERROR] page={page}: {e}")

                time.sleep(5)

        # ----------------------------------------------------
        # BÓC TÁCH SẢN PHẨM
        # ----------------------------------------------------

        new_count = 0
        duplicate_count = 0

        for product in data:

            product_id = product.get("id")

            # Không có ID -> bỏ
            if product_id is None:
                continue

            # Chống duplicate
            if product_id in seen_ids:

                duplicate_count += 1
                continue

            seen_ids.add(product_id)

            row = extract_product(product, category_id)

            all_products.append(row)

            new_count += 1

        print(
            f"[EXTRACT] page={page} " f"new={new_count} " f"duplicate={duplicate_count}"
        )

        print(f"[TOTAL] {len(all_products)} products")

        # ----------------------------------------------------
        # PAGE TIẾP THEO
        # ----------------------------------------------------

        page += 1

        # Nghỉ nhẹ giữa các request
        time.sleep(random.uniform(1.0, 2.0))


# ============================================================
# 9. LƯU CSV
# ============================================================


def save_csv(products, category_id):

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_file = os.path.join(OUTPUT_DIR, f"category_{category_id}.csv")

    df = pd.DataFrame(products)

    # Đảm bảo thứ tự cột
    columns = [
        "id",
        "url_key",
        "url",
        "name",
        "rating_average",
        "review_count",
        "original_price",
        "price",
        "quantity_sold",
        "category_id",
    ]

    df = df[columns]

    df.to_csv(output_file, index=False, encoding="utf-8-sig")

    print()
    print("=" * 60)
    print("DONE")
    print(f"Products : {len(df)}")
    print(f"Output   : {output_file}")
    print("=" * 60)

    return output_file


# ============================================================
# 10. HÀM CHẠY NHIỀU DANH MỤC
# ============================================================
def run_all_categories():
    """Đọc toàn bộ danh mục từ CSV và chạy lần lượt"""
    print("=" * 60)
    print("ĐỌC DANH SÁCH DANH MỤC TỪ FILE...")
    df = pd.read_csv("Khang/API_Crawl/data/SachThieuNhi_url_link.csv")
    
    if df.empty:
        raise ValueError("File SachThieuNhi_url_link.csv không có dữ liệu!")
    
    total = len(df)
    print(f"Tìm thấy {total} danh mục")
    print("=" * 60)
    
    # Duyệt từng dòng, chạy lần lượt
    for idx, row in df.iterrows():
        category_id = int(row["id"])
        url_key = row["url_key"]
        
        print(f"\n[{idx+1}/{total}] Đang xử lý: {category_id} | {url_key}")
        print("-" * 60)
        
        try:
            products = crawl_category(category_id, url_key)
            save_csv(products, category_id)
        except Exception as e:
            print(f"[LỖI] Danh mục {category_id} thất bại: {e}")
            print("Tiếp tục danh mục tiếp theo...")
            time.sleep(3)  # Nghỉ trước khi tiếp tục
    
    print("\n" + "=" * 60)
    print("✅ HOÀN THÀNH TẤT CẢ!")
    print("=" * 60)

# ============================================================
# 11. MAIN
# ============================================================
def main():
    # Chọn 1 trong 2 dòng dưới đây:
    # Cách 1: Chạy ngẫu nhiên 1 danh mục
    # category_id, url_key = get_category()
    # products = crawl_category(category_id, url_key)
    # save_csv(products, category_id)
    
    # Cách 2: Chạy TẤT CẢ danh mục trong file
    run_all_categories()

if __name__ == "__main__":
    main()
