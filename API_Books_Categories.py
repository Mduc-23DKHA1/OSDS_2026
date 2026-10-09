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

# =============== CONFIG =================
"""
    "config"      -> dùng CATEGORY_ID + URL_KEY bên dưới
    "all"         -> lấy tất cả các category từ CATEGORY_CSV
"""

# ------------------------------------------------------------
CATEGORY_MODE = "all"  # Config hiện tại
# ------------------------------------------------------------
CATEGORY_ID = 847  # Nếu CATEGORY_MODE = "config"
# ------------------------------------------------------------
CATEGORY_CSV = "data/full_url_link.csv"  # Nếu CATEGORY_MODE = "all"
# ------------------------------------------------------------
OUTPUT_DIR = "data/products"

# DATA có dạng : data/products/category_<ID>.csv
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"category_{CATEGORY_ID}.csv")

# ======================== API TIKI ===========================
API_URL = "https://tiki.vn/api/personalish/v1/blocks/listings"

FIXED_PARAMS = {
    "limit": 40,
    "include": "advertisement",
    "aggregations": 2,
    "version": "home-persionalized",
    "trackity_id": "065c7957-441c-ad9d-524e-4f326a13bc37",
}

# ======================== CẤU HÌNH RETRY & Session ============================
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

# Session
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


# =========================== RUNNING =================================
def get_category():
    """
    Trả về:
        category_id
        url_key
    """
    print("[CATEGORY] Đọc category từ CSV...")
    df = pd.read_csv(CATEGORY_CSV)
    features = ["id", "url_key"]

    if df.empty:
        raise ValueError("CATEGORY_CSV không có dữ liệu.")

    # --------------------------------------------------------
    # Cách 1: lấy từ CONFIG
    # --------------------------------------------------------

    if CATEGORY_MODE == "config":
        print("[CATEGORY] Dùng category trong CONFIG")
        return CATEGORY_MODE, df[features][df["id"] == CATEGORY_ID]

    # --------------------------------------------------------
    # Cách 2: lấy tất cả từ CSV
    # --------------------------------------------------------

    elif CATEGORY_MODE == "all":
        return CATEGORY_MODE, df[features]

    else:
        raise ValueError("CATEGORY_MODE phải là 'config' hoặc 'all'")


# ============================================================
#                       GỌI API MỘT PAGE
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
    params.update({"category": category_id, "page": page, "urlKey": url_key})

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
#                        BÓC TÁCH PRODUCT
# ============================================================
def extract_product(product, category_id):
    """
    Chỉ lấy những field cần thiết.
    """

    product_id = product.get("id")
    url_key = product.get("url_key")

    # Tạo url sản phẩm nếu chưa có
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
#                   CRAWL TOÀN BỘ CATEGORY
# ============================================================
def crawl_category(category_id, url_key):
    """
    Crawl từ page 1 cho đến khi xác nhận
    data=[] sau nhiều lần retry.
    """

    all_products = []  # Lưu tất cả sản phẩm
    seen_ids = set()  # Chống duplicate product

    page = 1
    print()
    print("=" * 60)
    print("START CRAWL")
    print(f"Category ID : {category_id}")
    print(f"URL Key     : {url_key}")
    print("=" * 60)

    while True:
        """
        Vòng lặp chạy cho đến khi xác nhận data=[] sau nhiều lần 3 retry.
        - Nếu có dữ liệu -> Break và lọc dữ liệu, rồi chuyển sang trang kế
        - Nếu không có dữ liệu -> thử lại 3 lần để break
        """
        print()
        print(f"[REQUEST] page={page}")

        empty_retry = 0

        while True:
            try:
                data = get_page(category_id, url_key, page)

                if data:  # Nếu có dữ liệu
                    print(f"[OK] page={page} " f"-> {len(data)} products")
                    break

                # Nếu không có dữ liệu
                empty_retry += 1
                print(f"[EMPTY] page={page} " f"-> data=[] " f"(retry {empty_retry}/3)")

                if empty_retry >= 3:
                    print(f"[STOP] page={page} " f"-> xác nhận data=[]")
                    return all_products

                # Chờ 1 khoảng trước khi gọi lại
                wait_time = 3 * empty_retry

                print(f"[WAIT] {wait_time}s...")

                time.sleep(wait_time)

            except requests.RequestException as e:
                """
                requests sẽ tự retry các lỗi HTTP tạm thời
                như 429, 500, 503, 504...
                Và lặp lại đến khi hết timeout thì ném error hoặc trả về data rỗng
                """
                print(f"[ERROR] page={page}: {e}")
                print("[INFO] requests đã tự retry " "các lỗi HTTP tạm thời.")

                time.sleep(5)

            except ValueError as e:
                """
                Response không phải JSON -> dừng.
                """
                print(f"[JSON ERROR] page={page}: {e}")
                time.sleep(5)

        # --------------------------------
        # Phân tách lấy dữ liệu cần thiết
        # --------------------------------
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

        print(f"[EXTRACT] page={page} new={new_count} duplicate={duplicate_count}")

        print(f"[TOTAL] {len(all_products)} products")

        # -------------------------------
        # Chuyển sang page kế và lặp lại
        # -------------------------------

        page += 1
        time.sleep(random.uniform(1.0, 2.0))


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


    # Nếu không có data -> Return 
    if df.empty:
        print("[ERROR] Không thể tạo DataFrame do không có data trong thể loại này")
        return

    df = df[columns]
    df.to_csv(output_file, index=False, encoding="utf-8-sig")

    print()
    print("=" * 60)
    print("DONE")
    print(f"Products : {len(df)}")
    print(f"Output   : {output_file}")
    print("=" * 60)

    return output_file


def should_crawl(category_id):
    """
    Kiểm tra file sản phẩm trước khi gọi API.

    - Chưa có file: cho phép cào.
    - Đã có file và số lượng đạt ít nhất 95% của 2000:
      bỏ qua category.
    - Đã có file nhưng số lượng dưới 95%:
      cào lại.
    """
    output_file = os.path.join(OUTPUT_DIR, f"category_{category_id}.csv")

    # Trường hợp 1: Chưa tồn tại file
    if not os.path.exists(output_file):
        print(f"[NEW] Chưa có file: {output_file}")
        return True

    # Trường hợp 2: File đã tồn tại
    try:
        df_existing = pd.read_csv(output_file)
        current_count = len(df_existing)

        print(f"[CHECK] đã có file, {current_count} sách hiện có")
        return False

    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as e:
        print(f"[WARNING] Không đọc được file {output_file}: {e}")
        print("[RECRAWL] Cho phép cào lại.")
        return True


# ============================================================
#                           MAIN
# ============================================================


def main():
    MODE, df = get_category()

    if MODE == "config":
        data = df[df["id"] == CATEGORY_ID]

        if data.empty:
            raise ValueError(
                f"Không tìm thấy CATEGORY_ID={CATEGORY_ID} " f"trong {CATEGORY_CSV}"
            )

        category_id = data["id"].iloc[0]
        url_key = data["url_key"].iloc[0]

        if not should_crawl(category_id):
            return

        products = crawl_category(category_id, url_key)
        save_csv(products, category_id)

    else:
        for row in range(len(df)):
            category_id = df["id"].iloc[row]
            url_key = df["url_key"].iloc[row]

            # Kiểm tra file trước khi gọi API
            if not should_crawl(category_id):
                continue

            products = crawl_category(category_id, url_key)
            save_csv(products, category_id)


if __name__ == "__main__":
    main()
