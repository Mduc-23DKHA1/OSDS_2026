"""
=========================================================================================
LẤY TẤT CẢ CÁC BÌNH LUẬN SÁCH CỦA TỪNG ID_SÁCH TRONG CÁC FILE category_<ID_Category>.csv
=========================================================================================

* Có 2 loại file CSV chính:

  * category_<ID_Category>_reviews.csv : Lưu tất cả các bình luận của ID sách thuộc thể loại <ID_Category>
  * review_checkpoint.csv              : Dùng chung cho tất cả category, xác định tiến trình cào của từng ID sách

---

CÁCH THỨC HOẠT ĐỘNG:
- Đọc danh sách category từ file full_url_link.csv
- Lấy danh sách ID sách từ file category_<ID_Category>.csv tương ứng
- Đọc file review_checkpoint.csv để kiểm tra tiến trình cào của từng ID sách
- Tìm kiếm ID sách trong file review_checkpoint.csv
    + Nếu chưa tìm thấy      -> Bắt đầu cào từ trang đầu tiên
    + Nếu đã hoàn thành      -> Bỏ qua ID sách
    + Nếu quá ít review      -> Bỏ qua ID sách
    + Nếu đang cào dở        -> Tiếp tục từ trang tiếp theo
    + Nếu gặp lỗi            -> Thử cào lại ID sách
- Sau khi xử lý xong một category -> Tự động chuyển sang category tiếp theo
- Tất cả category sử dụng chung một file review_checkpoint.csv

---

LƯU Ý:
- Nếu chưa chạy lần nào:
    + Tạo mới file review_checkpoint.csv
    + Tạo thư mục reviews nếu chưa tồn tại
    + Bắt đầu cào từ category đầu tiên
- Nếu đã chạy nhưng bị dừng:
    + Đọc file review_checkpoint.csv
    + Bỏ qua các ID sách đã hoàn thành
    + Tiếp tục cào các ID sách còn thiếu hoặc gặp lỗi
- Nếu đã chạy hoàn tất:
    + Bỏ qua các ID sách đã hoàn thành
    + Hiển thị thông báo khi toàn bộ category đã được xử lý
- Nếu AUTO_CATEGORIES = True:
    + Tự động lấy danh sách category từ file full_url_link.csv
- Nếu AUTO_CATEGORIES = False:
    + Chỉ cào category được chỉ định trong CATEGORY_ID
- Trước khi chạy, cần có các file category_<ID_Category>.csv
  được tạo từ bước lấy dữ liệu sách
- Không xóa file review_checkpoint.csv nếu muốn tiếp tục tiến trình cào
- File checkpoint chỉ theo dõi tiến trình cào, không thay thế file lưu review

---

QUY TRÌNH:
1. CONFIG
- AUTO_CATEGORIES : Bật/tắt chế độ tự động chạy nhiều category
- CATEGORY_ID     : ID category hiện tại nếu không chạy tự động
- CATEGORY_LIST_FILE : Đường dẫn file full_url_link.csv
- REVIEW_LIMIT    : Số review lấy trong mỗi request
- MIN_REVIEW_COUNT: Số review tối thiểu để crawl
- SELLER_ID       : Seller mặc định của Tiki
- REVIEW_API_URL  : URL API review

2. LOAD_DATA
    - Đọc danh sách category từ file full_url_link.csv
    - Đọc file category_<ID_Category>.csv tương ứng
    - Lấy danh sách ID sách và số lượng review của từng sách

3. REQUESTS SESSION + RETRY
    - Tạo session để gọi API
    - Cấu hình retry khi request gặp lỗi
    - Xử lý các lỗi HTTP thường gặp như 429, 500, 502, 503, 504

4. CLEAN CONTENT
    - Làm sạch nội dung review trước khi lưu
    - Thay thế các ký tự xuống dòng như "\\n", "\\r\\n", "\\r" bằng khoảng trắng
    - Gom nhiều khoảng trắng liên tiếp thành một khoảng trắng
    - Tránh làm sai cấu trúc dữ liệu khi ghi vào CSV

5. LOAD / SAVE / UPDATE CHECKPOINT
    - Đọc file review_checkpoint.csv dùng chung cho tất cả category
    - Kiểm tra trạng thái của từng ID sách
    - Cập nhật tiến trình cào sau mỗi trang review
    - Lưu các thông tin:
        + IdSach          : ID của sách
        + status          : Trạng thái cào
        + review_count    : Tổng số review theo dữ liệu sản phẩm
        + reviews_crawled : Số review đã cào
        + last_page       : Trang cuối cùng đã xử lý thành công
        + error           : Nội dung lỗi nếu có
    - Các trạng thái chính:
        + running         : Đang cào
        + completed       : Đã hoàn thành
        + skipped_too_few : Số review thấp hơn mức tối thiểu
        + error           : Gặp lỗi trong quá trình cào

6. GET REVIEW PAGE
    - Gọi Tiki Review API để lấy review theo từng trang
    - Sử dụng product_id để xác định ID sách
    - Lấy dữ liệu theo REVIEW_LIMIT
    - Tiếp tục từ trang kế tiếp nếu ID sách đã được cào dở
    - Lưu checkpoint sau mỗi trang để hạn chế mất tiến trình khi chương trình bị dừng

7. PROCESS PRODUCT
    - Xử lý từng ID sách trong category
    - Kiểm tra review_count trước khi gọi API
    - Bỏ qua sách không đạt MIN_REVIEW_COUNT
    - Chuyển dữ liệu review JSON thành các bản ghi CSV
    - Các thuộc tính được lưu:
        + "CustomerID" : ID của khách hàng
        + "content"    : Nội dung review
        + "star"       : Điểm đánh giá
        + "time_review": Thời gian review
        + "BookID"     : ID của sách (product_id)
        + "spid"       : ID của sản phẩm (các tuyển tập trong cùng 1 ID sách)

8. SAVE REVIEWS
    - Lưu review vào file category_<ID_Category>_reviews.csv
    - Nếu file chưa tồn tại -> Tạo file mới kèm header
    - Nếu file đã tồn tại -> Ghi nối tiếp dữ liệu mới
    - Lưu dữ liệu sau mỗi trang để hạn chế mất dữ liệu khi chương trình bị gián đoạn

9. AUTO RUN CATEGORIES
    - Nếu AUTO_CATEGORIES = True:
        + Lần lượt xử lý các category trong full_url_link.csv
        + Mỗi category sử dụng file sản phẩm và file review riêng
        + Tất cả category dùng chung review_checkpoint.csv
    - Nếu AUTO_CATEGORIES = False:
        + Chỉ xử lý category được khai báo trong CATEGORY_ID

10. FINISH
    - Hiển thị đường dẫn file review sau khi xử lý category
    - Hiển thị đường dẫn file checkpoint dùng chung
    - Thông báo khi quá trình cào hoàn tất
"""

import os
import re
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# 1. CONFIG
# ============================================================

# True: tự lấy danh sách category từ data/full_url_link.csv
# False: chỉ chạy category được khai báo ở CATEGORY_ID
AUTO_CATEGORIES = True
CATEGORY_ID = 847
CATEGORY_LIST_FILE = "data/full_url_link.csv"

REVIEW_LIMIT = 20  # Tiki cho phép từ 5 đến 20
MIN_REVIEW_COUNT = 10  # Chỉ crawl sách có ít nhất số review này
SELLER_ID = 1
REVIEW_API_URL = "https://tiki.vn/api/v2/reviews"

PRODUCT_DIR = Path("data/products")
REVIEW_DIR = Path("data/reviews")
CHECKPOINT_FILE = Path("data/review_checkpoint.csv")

REQUEST_TIMEOUT = 20
PAGE_DELAY = 1.5
PRODUCT_DELAY = 2

CHECKPOINT_COLUMNS = [
    "IdSach",
    "status",
    "review_count",
    "reviews_crawled",
    "last_page",
    "error",
]
REVIEW_COLUMNS = ["CustomerID", "content", "star", "time_review", "BookID", "spid"]

if not 5 <= REVIEW_LIMIT <= 20:
    raise ValueError("REVIEW_LIMIT phải nằm trong khoảng 5–20.")

PRODUCT_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. REQUEST SESSION + RETRY
# ============================================================

session = requests.Session()
retry_strategy = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)
session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Referer": "https://tiki.vn/",
    }
)


# ============================================================
# 3. HELPERS
# ============================================================


def clean_id(value):
    """Chuẩn hóa ID đọc từ CSV, tránh ID số bị thành dạng 12345.0."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text


def clean_content(content):
    if content is None or pd.isna(content):
        return ""
    content = str(content).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return " ".join(content.split())


def get_category_ids():
    """Đọc category ID từ full_url_link.csv, ưu tiên cột ID; nếu không có thì dò URL /c<ID>."""
    path = Path(CATEGORY_LIST_FILE)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file danh sách category: {path}")

    categories = pd.read_csv(path, dtype=str)
    if categories.empty:
        raise ValueError(f"File danh sách category đang rỗng: {path}")

    # Các tên cột ID có thể gặp trong file category đã chuyển đổi.
    id_candidates = [
        "category_id",
        "CategoryID",
        "id",
        "Id",
        "ID",
        "id_category",
        "IdCategory",
        "categoryId",
    ]
    found_ids = []
    for col in id_candidates:
        if col in categories.columns:
            found_ids = [clean_id(v) for v in categories[col].tolist()]
            found_ids = [v for v in found_ids if v]
            if found_ids:
                break

    # Nếu không có cột ID phù hợp, trích ID từ URL dạng .../c123456.
    if not found_ids:
        url_columns = [
            col
            for col in categories.columns
            if any(word in col.lower() for word in ("url", "link", "path"))
        ]
        for col in url_columns:
            for value in categories[col].dropna().astype(str):
                match = re.search(r"(?:/c|\bc)(\d+)(?:\D|$)", value)
                if match:
                    found_ids.append(match.group(1))
            if found_ids:
                break

    # Bỏ trùng nhưng giữ nguyên thứ tự trong file.
    unique_ids = list(dict.fromkeys(found_ids))
    if not unique_ids:
        raise ValueError(
            "Không tìm được ID category trong full_url_link.csv. "
            "Hãy kiểm tra tên cột ID hoặc cột URL trong file."
        )
    return unique_ids


# ============================================================
# 4. LOAD / SAVE / UPDATE CHECKPOINT
# ============================================================


def load_checkpoint():
    if not CHECKPOINT_FILE.exists():
        return pd.DataFrame(columns=CHECKPOINT_COLUMNS)

    try:
        checkpoint = pd.read_csv(CHECKPOINT_FILE, dtype={"IdSach": str})
        for col in CHECKPOINT_COLUMNS:
            if col not in checkpoint.columns:
                checkpoint[col] = None
        checkpoint = checkpoint[CHECKPOINT_COLUMNS]
        checkpoint["IdSach"] = checkpoint["IdSach"].map(clean_id)
        # Nếu file cũ vô tình có nhiều dòng cho cùng ID, lấy trạng thái mới nhất.
        checkpoint = (
            checkpoint.dropna(subset=["IdSach"])
            .drop_duplicates(subset=["IdSach"], keep="last")
            .reset_index(drop=True)
        )
        return checkpoint
    except Exception as exc:
        # Không tự ghi đè file checkpoint lỗi để tránh làm mất tiến trình cũ.
        raise RuntimeError(
            f"Không đọc được checkpoint {CHECKPOINT_FILE}: {exc}"
        ) from exc


def save_checkpoint(checkpoint):
    checkpoint[CHECKPOINT_COLUMNS].to_csv(
        CHECKPOINT_FILE, index=False, encoding="utf-8-sig"
    )


def get_checkpoint_row(checkpoint, product_id):
    product_id = clean_id(product_id)
    mask = checkpoint["IdSach"].map(clean_id) == product_id
    if not mask.any():
        return None
    return checkpoint.loc[mask].iloc[-1]


def update_checkpoint(
    checkpoint,
    product_id,
    status,
    review_count=None,
    reviews_crawled=None,
    last_page=None,
    error=None,
):
    product_id = clean_id(product_id)
    mask = checkpoint["IdSach"].map(clean_id) == product_id
    new_data = {
        "IdSach": product_id,
        "status": status,
        "review_count": review_count,
        "reviews_crawled": reviews_crawled,
        "last_page": last_page,
        "error": error,
    }
    if mask.any():
        idx = checkpoint.index[mask][-1]
        for col, value in new_data.items():
            checkpoint.loc[idx, col] = value
        # Xóa dòng trùng ID nếu file cũ có dữ liệu trùng.
        duplicate_mask = (checkpoint["IdSach"].map(clean_id) == product_id) & (
            checkpoint.index != idx
        )
        checkpoint.drop(index=checkpoint.index[duplicate_mask], inplace=True)
        checkpoint.reset_index(drop=True, inplace=True)
    else:
        checkpoint.loc[len(checkpoint)] = new_data
    save_checkpoint(checkpoint)


# ============================================================
# 5. API + PARSE + SAVE REVIEWS
# ============================================================


def get_review_page(product_id, page):
    params = {
        "limit": REVIEW_LIMIT,
        "include": "comments,contribute_info,attribute_vote_summary",
        "sort": "score|desc,id|desc,stars|all",
        "page": page,
        "product_id": product_id,
        "seller_id": SELLER_ID,
    }
    print(f"[REQUEST] product_id={product_id} | page={page}")
    response = session.get(REVIEW_API_URL, params=params, timeout=REQUEST_TIMEOUT)
    print(f"[STATUS] {response.status_code}")
    response.raise_for_status()
    if not response.text.strip():
        raise ValueError(f"Response rỗng: product_id={product_id}, page={page}")
    try:
        result = response.json()
    except ValueError as exc:
        print("[ERROR] Response không phải JSON:", response.text[:300])
        raise ValueError("API trả về nội dung không phải JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("Cấu trúc JSON API không đúng dạng object")
    return result


def parse_review(review, product_id):
    timeline = review.get("timeline") or {}
    if not isinstance(timeline, dict):
        timeline = {}
    return {
        "CustomerID": review.get("customer_id"),
        "content": clean_content(review.get("content")),
        "star": review.get("rating"),
        "time_review": timeline.get("review_created_date"),
        "BookID": product_id,
        "spid": review.get("spid"),
    }


def save_reviews(rows, review_file):
    if not rows:
        return
    df = pd.DataFrame(rows, columns=REVIEW_COLUMNS)
    file_exists = review_file.exists() and review_file.stat().st_size > 0
    df.to_csv(
        review_file,
        mode="a",
        header=not file_exists,
        index=False,
        encoding="utf-8-sig",
    )
    print(f"[SAVE] {len(df)} reviews -> {review_file}")


# ============================================================
# 6. CRAWL 1 BOOK, HỖ TRỢ RESUME TỪ CHECKPOINT
# ============================================================


def crawl_product(product_id, review_count, checkpoint, review_file):
    product_id = clean_id(product_id)
    if product_id is None:
        print("[SKIP] ID sách rỗng hoặc không hợp lệ")
        return

    if pd.isna(review_count):
        update_checkpoint(
            checkpoint, product_id, "error", None, 0, 0, "review_count không hợp lệ"
        )
        print(f"[ERROR] product={product_id}: review_count không hợp lệ")
        return

    try:
        review_count = int(float(review_count))
    except (TypeError, ValueError):
        update_checkpoint(
            checkpoint,
            product_id,
            "error",
            None,
            0,
            0,
            "review_count không chuyển được sang số",
        )
        print(f"[ERROR] product={product_id}: review_count không hợp lệ")
        return

    if review_count < MIN_REVIEW_COUNT:
        update_checkpoint(
            checkpoint, product_id, "skipped_too_few", review_count, 0, 0, None
        )
        print(
            f"[SKIP] product={product_id} | review_count={review_count} < {MIN_REVIEW_COUNT}"
        )
        return

    old_row = get_checkpoint_row(checkpoint, product_id)
    if old_row is not None:
        try:
            last_page_done = max(0, int(float(old_row["last_page"] or 0)))
        except (TypeError, ValueError):
            last_page_done = 0
        try:
            old_count = max(0, int(float(old_row["reviews_crawled"] or 0)))
        except (TypeError, ValueError):
            old_count = 0
    else:
        last_page_done = 0
        old_count = 0

    total_pages = (review_count + REVIEW_LIMIT - 1) // REVIEW_LIMIT
    start_page = last_page_done + 1

    if start_page > total_pages:
        update_checkpoint(
            checkpoint,
            product_id,
            "completed",
            review_count,
            old_count,
            last_page_done,
            None,
        )
        print(f"[ALREADY COMPLETE] product={product_id}")
        return

    update_checkpoint(
        checkpoint, product_id, "running", review_count, old_count, last_page_done, None
    )

    print("\n" + "=" * 70)
    print(f"[START] Category output: {review_file}")
    print(f"[START] Product ID: {product_id} | review_count={review_count}")
    print(f"[RESUME] Bắt đầu từ page {start_page}/{total_pages}")
    print("=" * 70)

    all_count = old_count
    last_successful_page = last_page_done

    for page in range(start_page, total_pages + 1):
        try:
            result = get_review_page(product_id, page)
            reviews = result.get("data", [])
            if not isinstance(reviews, list):
                raise ValueError("Trường 'data' trong response không phải danh sách")

            if not reviews:
                print(f"[STOP] product={product_id} | page={page} | data=[]")
                # Không đánh dấu trang rỗng là lỗi; các trang trước đã lưu vẫn hợp lệ.
                break

            rows = [parse_review(review, product_id) for review in reviews]
            save_reviews(rows, review_file)
            all_count += len(rows)
            last_successful_page = page

            # Ghi checkpoint ngay sau mỗi trang đã lưu.
            update_checkpoint(
                checkpoint,
                product_id,
                "running",
                review_count,
                all_count,
                last_successful_page,
                None,
            )
            print(f"[PAGE DONE] page={page} | got={len(rows)} | total={all_count}")
            time.sleep(PAGE_DELAY)

        except Exception as exc:
            # Lưu last_successful_page, KHÔNG lưu page lỗi, để lần sau thử lại đúng trang đó.
            update_checkpoint(
                checkpoint,
                product_id,
                "error",
                review_count,
                all_count,
                last_successful_page,
                str(exc),
            )
            print(f"[ERROR] product={product_id} | page={page} | {exc}")
            return

    update_checkpoint(
        checkpoint,
        product_id,
        "completed",
        review_count,
        all_count,
        last_successful_page,
        None,
    )
    print(f"[COMPLETED] product={product_id} | reviews_crawled={all_count}")


# ============================================================
# 7. CHẠY 1 CATEGORY
# ============================================================


def crawl_category(category_id, checkpoint):
    product_file = PRODUCT_DIR / f"category_{category_id}.csv"
    review_file = REVIEW_DIR / f"category_{category_id}_reviews.csv"

    print("\n" + "#" * 80)
    print(f"[CATEGORY] {category_id}")
    print(f"[PRODUCT FILE] {product_file}")
    print(f"[REVIEW FILE] {review_file}")
    print("#" * 80)

    if not product_file.exists():
        print(
            f"[WARNING] Không tìm thấy file sản phẩm, bỏ qua category: {product_file}"
        )
        return

    try:
        products = pd.read_csv(product_file, dtype={"id": str})
    except Exception as exc:
        print(f"[ERROR] Không đọc được {product_file}: {exc}")
        return

    required_columns = {"id", "review_count"}
    missing_columns = required_columns - set(products.columns)
    if missing_columns:
        print(f"[ERROR] {product_file} thiếu cột: {', '.join(sorted(missing_columns))}")
        return

    products = products.dropna(subset=["id"]).copy()
    products["id"] = products["id"].map(clean_id)
    products = products.dropna(subset=["id"]).drop_duplicates(
        subset=["id"], keep="first"
    )

    print(f"[INFO] Tổng sách hợp lệ: {len(products)}")
    for _, product in products.iterrows():
        product_id = product["id"]
        row = get_checkpoint_row(checkpoint, product_id)
        status = (
            str(row["status"]).strip()
            if row is not None and pd.notna(row["status"])
            else ""
        )

        if status in {"completed", "skipped_too_few"}:
            print(f"[SKIP CHECKPOINT] product={product_id} | status={status}")
            continue

        crawl_product(
            product_id=product_id,
            review_count=product["review_count"],
            checkpoint=checkpoint,
            review_file=review_file,
        )
        time.sleep(PRODUCT_DELAY)

    print(f"[CATEGORY DONE] {category_id}")


# ============================================================
# 8. MAIN
# ============================================================


def main():
    print("=" * 80)
    print("TIKI REVIEW CRAWLER - AUTO CATEGORY + SHARED CHECKPOINT")
    print("=" * 80)

    try:
        if AUTO_CATEGORIES:
            category_ids = get_category_ids()
        else:
            category_ids = [str(CATEGORY_ID)]
    except Exception as exc:
        print(f"[FATAL] {exc}")
        return

    checkpoint = load_checkpoint()
    print(f"[INFO] Số category sẽ chạy: {len(category_ids)}")
    print(f"[INFO] Checkpoint dùng chung: {CHECKPOINT_FILE}")

    for index, category_id in enumerate(category_ids, start=1):
        print(f"\n[PROGRESS] Category {index}/{len(category_ids)}")
        crawl_category(category_id, checkpoint)

    print("\n" + "=" * 80)
    print("ĐÃ KẾT THÚC TOÀN BỘ DANH SÁCH CATEGORY")
    print(f"[CHECKPOINT] {CHECKPOINT_FILE}")
    print(f"[REVIEW OUTPUT DIR] {REVIEW_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
