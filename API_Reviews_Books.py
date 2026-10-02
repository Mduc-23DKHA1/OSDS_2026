"""
=========================================================================================
    LẤY TẤT CẢ CÁC BÌNH LUẬN SÁCH CỦA TỪNG ID_SÁCH TRONG FILE category_<ID_Category>.csv
=========================================================================================
- Có 2 file csv:
    + category_<ID_Category>_reviews.csv : Lưu tất cả các bình luận của ID sách thuộc thể loại <ID_Category>
    + review_checkpoint.csv              : Xác định tiến trình cào đã hoàn thành, hay thiếu ở ID sách

-------------------------------------------------------------
CÁCH THỨC HOẠT ĐỘNG:
    - Lấy danh sách ID sách từ file category_<ID_Category>.csv
    - Đọc file review_checkpoint.csv
    - Tìm kiếm ID sách trong file review_checkpoint.csv
        + Nếu tìm thấy ->  tiếp tục cào từ trang tiếp theo
        + Nếu không    ->  bắt đầu cào từ trang đầu tiên

-------------------------------------------------------------
LƯU Ý:
    - Nếu chưa chạy lần nào: tạo mới 2 file
    - Nếu đã chạy nhưng bị dừng: tiếp tục từ file checkpoint
    - Nếu đã chạy hoàn tất: hiển thị thông báo

-------------------------------------------------------------
QUY TRÌNH:
    1. CONFIG
        - CATEGORY_ID : ID category hiện tại
        (LƯU Ý: bắt buộc phải chạy file "API_Books_Category.py" trước để có được file "category_<ID>.csv" )
        - REVIEW_LIMIT: số review lấy trong mỗi request
        - MIN_REVIEW_COUNT: số review tối thiểu để crawl
        - SELLER_ID: seller mặc định của Tiki
        - REVIEW_API_URL: URL API review
    2. LOAD_DATA
        - Load file category_<ID_Category>.csv
    3. REQUESTS SESSION + RETRY
        - Tạo session để gọi API
        - Cấu hình retry cho session
    4. CLEAN CONTENT
        - Hàm làm sạch nội dung review
        (Bình luận có thể có xuống dòng hay "\n" , "\r\n", ... → thay thế bằng " " để tránh lỗi lưu csv)
    5. LOAD / SAVE / UPDATE CHECKPOINT
        - Load file review_checkpoint.csv
        - Cập nhật file review_checkpoint.csv (trạng thái: "processing", "completed", "error")
    6. GET REVIEW PAGE
        - Lấy review từ API
    7. PROCESS PRODUCT
        - Xử lý product và lưu các thuộc tính cần thiết:
            + "CustomerID" : ID của khách hàng
            + "content"    : Nội dung review
            + "star"       : Điểm đánh giá
            + "time_review": Thời gian review
            + "BookID"     : ID của sách (product_id)
            + "spid"       : ID của sản phẩm (các tuyển tập trong cùng 1 ID sách)
    8. SAVE REVIEWS
        - Lưu vào file category_<ID_Category>_reviews.csv
"""

import os
import time
import pandas as pd
import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# 1. CẤU HÌNH
# ============================================================

# ID category hiện tại
CATEGORY_ID = 847

# Số review lấy trong mỗi request
# Có thể thay đổi, ví dụ 10, 20...
REVIEW_LIMIT = 20

# Chỉ crawl sản phẩm có từ 10 review trở lên
MIN_REVIEW_COUNT = 10

# Seller mặc định của Tiki
SELLER_ID = 1

# API review
REVIEW_API_URL = "https://tiki.vn/api/v2/reviews"


# ============================================================
# 2. ĐƯỜNG DẪN FILE
# ============================================================

PRODUCT_FILE = f"data/products/category_{CATEGORY_ID}.csv"

REVIEW_DIR = "data/reviews"

REVIEW_FILE = f"{REVIEW_DIR}/category_{CATEGORY_ID}_reviews.csv"

CHECKPOINT_FILE = "data/review_checkpoint.csv"


# Tạo thư mục nếu chưa tồn tại
os.makedirs(REVIEW_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)


# ============================================================
# 3. REQUEST SESSION + RETRY
# ============================================================

session = requests.Session()

retry_strategy = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

adapter = HTTPAdapter(max_retries=retry_strategy)

session.mount("https://", adapter)
session.mount("http://", adapter)


# ============================================================
# 4. HÀM CLEAN CONTENT
# ============================================================


def clean_content(content):
    """
    Chuẩn hóa nội dung review.

    Xóa:
    - \\r\\n
    - \\n
    - \\r

    Sau đó gom nhiều khoảng trắng thành 1 khoảng trắng.

    Ví dụ:

    Sách rất hay.
    Tôi đọc rất thích.

    ->

    Sách rất hay. Tôi đọc rất thích.
    """

    if content is None:
        return ""

    content = str(content)

    content = content.replace("\r\n", " ")
    content = content.replace("\n", " ")
    content = content.replace("\r", " ")

    # Gom nhiều khoảng trắng thành 1
    content = " ".join(content.split())

    return content


# ============================================================
# 5. LOAD CHECKPOINT
# ============================================================


def load_checkpoint():
    """
    Đọc checkpoint nếu đã tồn tại.

    Nếu chưa có thì tạo DataFrame rỗng.
    """

    columns = [
        "IdSach",
        "status",
        "review_count",
        "reviews_crawled",
        "last_page",
        "error",
    ]

    if not os.path.exists(CHECKPOINT_FILE):
        return pd.DataFrame(columns=columns)

    try:
        checkpoint = pd.read_csv(
            CHECKPOINT_FILE,
            dtype={
                "IdSach": str,
            },
        )

        # Đảm bảo các cột cần thiết tồn tại
        for col in columns:
            if col not in checkpoint.columns:
                checkpoint[col] = None

        return checkpoint[columns]

    except Exception as e:
        print(f"[WARNING] Không đọc được checkpoint: {e}")

        return pd.DataFrame(columns=columns)


# ============================================================
# 6. SAVE CHECKPOINT
# ============================================================


def save_checkpoint(checkpoint):
    """
    Lưu checkpoint xuống CSV.
    """

    checkpoint.to_csv(CHECKPOINT_FILE, index=False, encoding="utf-8-sig")


# ============================================================
# 7. UPDATE CHECKPOINT
# ============================================================


def update_checkpoint(
    checkpoint,
    product_id,
    status,
    review_count=None,
    reviews_crawled=None,
    last_page=None,
    error=None,
):
    """
    Cập nhật trạng thái của 1 sản phẩm.
    """

    product_id = str(product_id)

    mask = checkpoint["IdSach"].astype(str) == product_id

    new_data = {
        "IdSach": product_id,
        "status": status,
        "review_count": review_count,
        "reviews_crawled": reviews_crawled,
        "last_page": last_page,
        "error": error,
    }

    if mask.any():

        checkpoint.loc[mask, "status"] = status
        checkpoint.loc[mask, "review_count"] = review_count
        checkpoint.loc[mask, "reviews_crawled"] = reviews_crawled
        checkpoint.loc[mask, "last_page"] = last_page
        checkpoint.loc[mask, "error"] = error

    else:

        checkpoint.loc[len(checkpoint)] = new_data

    save_checkpoint(checkpoint)


# ============================================================
# 8. GỌI REVIEW API
# ============================================================


def get_review_page(product_id, page):
    """
    Gọi Tiki Review API.

    Trả về:
        result JSON
    """

    params = {
        "limit": REVIEW_LIMIT,
        "include": ("comments," "contribute_info," "attribute_vote_summary"),
        "sort": "score|desc,id|desc,stars|all",
        "page": page,
        "product_id": product_id,
        "seller_id": SELLER_ID,
    }

    print(f"[REQUEST] " f"product_id={product_id} | " f"page={page}")

    response = session.get(REVIEW_API_URL, params=params, timeout=20)

    print(f"[STATUS] " f"{response.status_code}")

    response.raise_for_status()

    # Kiểm tra response rỗng
    if not response.text.strip():
        raise ValueError(f"Response rỗng: " f"product_id={product_id}, " f"page={page}")

    # Parse JSON
    try:
        result = response.json()

    except ValueError as e:

        print("[ERROR] Response không phải JSON")

        print("[CONTENT-TYPE]", response.headers.get("Content-Type"))

        print("[RESPONSE ĐẦU]")

        print(response.text[:500])

        raise e

    return result


# ============================================================
# 9. PARSE REVIEW
# ============================================================


def parse_review(review, product_id):
    """
    Chuyển 1 review JSON thành 1 record CSV.

    Các trường lấy:
        CustomerID
        content
        star
        time_review
        BookID
        spid
    """

    timeline = review.get("timeline", {})

    return {
        "CustomerID": review.get("customer_id"),
        "content": clean_content(review.get("content")),
        "star": review.get("rating"),
        "time_review": timeline.get("review_created_date"),
        "BookID": product_id,
        # LẤY THÊM SPID
        "spid": review.get("spid"),
    }


# ============================================================
# 10. LƯU REVIEW
# ============================================================


def save_reviews(rows):
    """
    Append các review mới vào CSV.

    Nếu file chưa tồn tại:
        tạo header.

    Nếu đã tồn tại:
        append, không tạo header.
    """

    if not rows:
        return

    df = pd.DataFrame(rows)

    columns = [
        "CustomerID",
        "content",
        "star",
        "time_review",
        "BookID",
        "spid",
    ]

    df = df[columns]

    file_exists = os.path.exists(REVIEW_FILE)

    df.to_csv(
        REVIEW_FILE, mode="a", header=not file_exists, index=False, encoding="utf-8-sig"
    )

    print(f"[SAVE] " f"{len(df)} reviews -> " f"{REVIEW_FILE}")


# ============================================================
# 11. CRAWL 1 PRODUCT
# ============================================================


def crawl_product(product_id, review_count, checkpoint):
    """
    Crawl toàn bộ review của 1 sản phẩm.

    Quy tắc:

    review_count < 10
        -> skip

    review_count >= 10
        -> crawl
    """

    product_id = str(product_id)

    # --------------------------------------------------------
    # Kiểm tra review_count
    # --------------------------------------------------------

    if pd.isna(review_count):

        print(f"[SKIP] product={product_id} " f"| review_count không hợp lệ")

        update_checkpoint(
            checkpoint=checkpoint,
            product_id=product_id,
            status="error",
            review_count=None,
            reviews_crawled=0,
            last_page=0,
            error="review_count không hợp lệ",
        )

        return

    review_count = int(review_count)

    # --------------------------------------------------------
    # Skip nếu quá ít review
    # --------------------------------------------------------

    if review_count < MIN_REVIEW_COUNT:

        print(
            f"[SKIP] product={product_id} "
            f"| review_count={review_count} "
            f"< {MIN_REVIEW_COUNT}"
        )

        update_checkpoint(
            checkpoint=checkpoint,
            product_id=product_id,
            status="skipped_too_few",
            review_count=review_count,
            reviews_crawled=0,
            last_page=0,
            error=None,
        )

        return

    # --------------------------------------------------------
    # Đánh dấu running
    # --------------------------------------------------------

    update_checkpoint(
        checkpoint=checkpoint,
        product_id=product_id,
        status="running",
        review_count=review_count,
        reviews_crawled=0,
        last_page=0,
        error=None,
    )

    print()
    print("=" * 70)
    print(f"[START] Product ID: {product_id}")
    print(f"[INFO] Review count: {review_count}")
    print("=" * 70)

    # --------------------------------------------------------
    # Tính số page
    # --------------------------------------------------------

    total_pages = (review_count + REVIEW_LIMIT - 1) // REVIEW_LIMIT

    print(f"[INFO] Dự kiến pages: " f"{total_pages}")

    all_count = 0

    # --------------------------------------------------------
    # Crawl từng page
    # --------------------------------------------------------

    for page in range(1, total_pages + 1):

        try:

            result = get_review_page(product_id, page)

            # ------------------------------------------------
            # Lấy data
            # ------------------------------------------------

            reviews = result.get("data", [])

            # ------------------------------------------------
            # Nếu API trả data rỗng
            # ------------------------------------------------

            if not reviews:

                print(
                    f"[STOP] " f"product={product_id} " f"| page={page} " f"-> data=[]"
                )

                break

            # ------------------------------------------------
            # Parse
            # ------------------------------------------------

            rows = []

            for review in reviews:

                row = parse_review(review, product_id)

                rows.append(row)

            # ------------------------------------------------
            # Save ngay sau mỗi page
            # ------------------------------------------------

            save_reviews(rows)

            all_count += len(rows)

            # ------------------------------------------------
            # Update checkpoint
            # ------------------------------------------------

            update_checkpoint(
                checkpoint=checkpoint,
                product_id=product_id,
                status="running",
                review_count=review_count,
                reviews_crawled=all_count,
                last_page=page,
                error=None,
            )

            print(
                f"[PAGE DONE] "
                f"page={page} | "
                f"got={len(rows)} | "
                f"total={all_count}"
            )

            # ------------------------------------------------
            # Delay giữa các page
            # ------------------------------------------------

            time.sleep(1.5)

        except Exception as e:

            print(f"[ERROR] " f"product={product_id} | " f"page={page} | " f"{e}")

            update_checkpoint(
                checkpoint=checkpoint,
                product_id=product_id,
                status="error",
                review_count=review_count,
                reviews_crawled=all_count,
                last_page=page,
                error=str(e),
            )

            return

    # --------------------------------------------------------
    # Hoàn thành
    # --------------------------------------------------------

    update_checkpoint(
        checkpoint=checkpoint,
        product_id=product_id,
        status="completed",
        review_count=review_count,
        reviews_crawled=all_count,
        last_page=(page if "page" in locals() else 0),
        error=None,
    )

    print(f"[COMPLETED] " f"product={product_id} | " f"reviews={all_count}")


# ============================================================
# 12. MAIN
# ============================================================


def main():

    print("=" * 70)
    print("TIKI REVIEW CRAWLER")
    print("=" * 70)

    # --------------------------------------------------------
    # Kiểm tra file product
    # --------------------------------------------------------

    if not os.path.exists(PRODUCT_FILE):

        print(f"[ERROR] Không tìm thấy file:")

        print(PRODUCT_FILE)

        return

    # --------------------------------------------------------
    # Đọc product CSV
    # --------------------------------------------------------

    print(f"[LOAD] {PRODUCT_FILE}")

    products = pd.read_csv(PRODUCT_FILE)

    print(f"[INFO] Tổng products: " f"{len(products)}")

    # --------------------------------------------------------
    # Kiểm tra column
    # --------------------------------------------------------

    required_columns = [
        "id",
        "review_count",
    ]

    for col in required_columns:

        if col not in products.columns:

            print(f"[ERROR] Thiếu column: " f"{col}")

            return

    # --------------------------------------------------------
    # Load checkpoint
    # --------------------------------------------------------

    checkpoint = load_checkpoint()

    # --------------------------------------------------------
    # Crawl từng product
    # --------------------------------------------------------

    for index, product in products.iterrows():

        product_id = product["id"]

        review_count = product["review_count"]

        product_id_str = str(product_id)

        # ----------------------------------------------------
        # Kiểm tra checkpoint
        # ----------------------------------------------------

        if not checkpoint.empty:

            mask = checkpoint["IdSach"].astype(str) == product_id_str

            if mask.any():

                status = checkpoint.loc[mask, "status"].iloc[0]

                if status in ["completed", "skipped_too_few"]:

                    print(
                        f"[SKIP CHECKPOINT] "
                        f"product={product_id} "
                        f"| status={status}"
                    )

                    continue

        # ----------------------------------------------------
        # Crawl
        # ----------------------------------------------------

        crawl_product(
            product_id=product_id, review_count=review_count, checkpoint=checkpoint
        )

        # ----------------------------------------------------
        # Delay giữa products
        # ----------------------------------------------------

        time.sleep(2)

    print()
    print("=" * 70)
    print("ĐÃ HOÀN TẤT CRAWL")
    print("=" * 70)

    print(f"[OUTPUT] {REVIEW_FILE}")

    print(f"[CHECKPOINT] " f"{CHECKPOINT_FILE}")


# ============================================================
# 13. RUN
# ============================================================

if __name__ == "__main__":
    main()
