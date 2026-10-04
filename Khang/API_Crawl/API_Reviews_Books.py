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
# Đường dẫn tính theo vị trí của file .py này, không phụ thuộc thư mục đang chạy
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
 
PRODUCT_DIR = os.path.join(BASE_DIR, "data", "products")
REVIEW_DIR = os.path.join(BASE_DIR, "data", "reviews")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "data", "review_checkpoint.csv")
 
REVIEW_LIMIT = 20
MIN_REVIEW_COUNT = 10
SELLER_ID = 1
REVIEW_API_URL = "https://tiki.vn/api/v2/reviews"
 
# Số lần thử lại khi ghi file bị lỗi (file đang bị khóa, antivirus quét, ...)
WRITE_RETRIES = 6
 
CHECKPOINT_COLUMNS = [
    "CategoryID",
    "IdSach",
    "status",
    "review_count",
    "reviews_crawled",
    "last_page",
    "error",
]
REVIEW_COLUMNS = ["CustomerID", "content", "star", "time_review", "BookID", "spid"]
 
os.makedirs(PRODUCT_DIR, exist_ok=True)
os.makedirs(REVIEW_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
 
# ============================================================
# 2. SESSION + RETRY
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
# 3. CLEAN CONTENT
# ============================================================
def clean_content(content):
    """Thay xuống dòng bằng khoảng trắng, gom nhiều khoảng trắng thành 1."""
    if content is None:
        return ""
    content = str(content)
    content = content.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return " ".join(content.split())
 
 
# ============================================================
# 4. GHI FILE AN TOÀN (có thử lại)
# ============================================================
def write_csv_with_retry(df, path, mode="w", header=True):
    """
    Ghi DataFrame ra CSV, thử lại nếu gặp OSError (file bị khóa tạm thời).
 
    Trả về True nếu ghi thành công, False nếu thất bại sau mọi lần thử.
    """
    for attempt in range(1, WRITE_RETRIES + 1):
        try:
            df.to_csv(path, mode=mode, header=header, index=False, encoding="utf-8-sig")
            return True
        except OSError as e:
            print(f"[WARNING] Ghi {os.path.basename(path)} lỗi " f"(lần {attempt}/{WRITE_RETRIES}): {e}")
            time.sleep(0.5 * attempt)
    return False
 
 
# ============================================================
# 5. CHECKPOINT
# ============================================================
def load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return pd.DataFrame(columns=CHECKPOINT_COLUMNS)
    try:
        cp = pd.read_csv(CHECKPOINT_FILE, dtype={"CategoryID": str, "IdSach": str})
        for col in CHECKPOINT_COLUMNS:
            if col not in cp.columns:
                cp[col] = None
        return cp[CHECKPOINT_COLUMNS]
    except Exception as e:
        print(f"[WARNING] Không đọc được checkpoint: {e}")
        return pd.DataFrame(columns=CHECKPOINT_COLUMNS)
 
 
def save_checkpoint(checkpoint):
    """
    Ghi checkpoint xuống đĩa an toàn:
        ghi ra file .tmp  ->  os.replace sang file thật.
    Nếu thất bại thì chỉ cảnh báo, KHÔNG làm chương trình sập.
    """
    tmp_file = CHECKPOINT_FILE + ".tmp"
 
    for attempt in range(1, WRITE_RETRIES + 1):
        try:
            checkpoint.to_csv(tmp_file, index=False, encoding="utf-8-sig")
            os.replace(tmp_file, CHECKPOINT_FILE)
            return True
        except OSError as e:
            print(f"[WARNING] Lưu checkpoint lỗi " f"(lần {attempt}/{WRITE_RETRIES}): {e}")
            time.sleep(0.5 * attempt)
 
    print("[WARNING] Chưa lưu được checkpoint, sẽ thử lại ở lần cập nhật sau.")
    return False
 
 
def get_checkpoint_row(checkpoint, category_id, product_id):
    """Trả về dòng checkpoint của (category, sách) hoặc None."""
    if checkpoint.empty:
        return None
    mask = (checkpoint["CategoryID"].astype(str) == str(category_id)) & (
        checkpoint["IdSach"].astype(str) == str(product_id)
    )
    if not mask.any():
        return None
    return checkpoint[mask].iloc[0]
 
 
def update_checkpoint(
    checkpoint,
    category_id,
    product_id,
    status,
    review_count=None,
    reviews_crawled=None,
    last_page=None,
    error=None,
    save=True,
):
    """
    Cập nhật trạng thái 1 sách trong bộ nhớ.
 
    save=True  -> ghi xuống đĩa ngay
    save=False -> chỉ cập nhật trong bộ nhớ (dùng cho sách bị skip, tránh ghi quá nhiều)
    """
    category_id = str(category_id)
    product_id = str(product_id)
 
    mask = (checkpoint["CategoryID"].astype(str) == category_id) & (
        checkpoint["IdSach"].astype(str) == product_id
    )
 
    if mask.any():
        checkpoint.loc[mask, "status"] = status
        checkpoint.loc[mask, "review_count"] = review_count
        checkpoint.loc[mask, "reviews_crawled"] = reviews_crawled
        checkpoint.loc[mask, "last_page"] = last_page
        checkpoint.loc[mask, "error"] = error
    else:
        checkpoint.loc[len(checkpoint)] = [
            category_id,
            product_id,
            status,
            review_count,
            reviews_crawled,
            last_page,
            error,
        ]
 
    if save:
        save_checkpoint(checkpoint)
 
 
# ============================================================
# 6. GỌI REVIEW API
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
    response = session.get(REVIEW_API_URL, params=params, timeout=20)
    print(f"[STATUS] {response.status_code}")
    response.raise_for_status()
 
    if not response.text.strip():
        raise ValueError(f"Response rỗng: product_id={product_id}, page={page}")
 
    try:
        return response.json()
    except ValueError:
        print("[ERROR] Response không phải JSON")
        print("[CONTENT-TYPE]", response.headers.get("Content-Type"))
        print("[RESPONSE ĐẦU]", response.text[:500])
        raise
 
 
# ============================================================
# 7. PARSE + SAVE REVIEW
# ============================================================
def parse_review(review, product_id):
    timeline = review.get("timeline") or {}
    return {
        "CustomerID": review.get("customer_id"),
        "content": clean_content(review.get("content")),
        "star": review.get("rating"),
        "time_review": timeline.get("review_created_date"),
        "BookID": product_id,
        "spid": review.get("spid"),
    }
 
 
def save_reviews(rows, review_file):
    """
    Append review vào review_file (tạo header nếu file chưa có).
 
    Nếu ghi thất bại sau mọi lần thử -> raise OSError để crawl_product
    đánh dấu "error" và lần chạy sau tiếp tục lại đúng trang đó.
    """
    if not rows:
        return
 
    df = pd.DataFrame(rows)[REVIEW_COLUMNS]
    file_exists = os.path.exists(review_file)
 
    ok = write_csv_with_retry(df, review_file, mode="a", header=not file_exists)
    if not ok:
        raise OSError(f"Không ghi được file review: {review_file}")
 
    print(f"[SAVE] {len(df)} reviews -> {review_file}")
 
 
# ============================================================
# 8. CRAWL 1 SẢN PHẨM
# ============================================================
def crawl_product(category_id, product_id, review_count, checkpoint, review_file):
    product_id = str(product_id)
 
    # ---- review_count không hợp lệ ----
    if pd.isna(review_count):
        print(f"[SKIP] product={product_id} | review_count không hợp lệ")
        update_checkpoint(
            checkpoint, category_id, product_id, "error",
            None, 0, 0, "review_count không hợp lệ",
            save=False,
        )
        return
 
    review_count = int(review_count)
 
    # ---- quá ít review (chỉ cập nhật trong bộ nhớ) ----
    if review_count < MIN_REVIEW_COUNT:
        print(f"[SKIP] product={product_id} | review_count={review_count} < {MIN_REVIEW_COUNT}")
        update_checkpoint(
            checkpoint, category_id, product_id, "skipped_too_few",
            review_count, 0, 0, None,
            save=False,
        )
        return
 
    total_pages = (review_count + REVIEW_LIMIT - 1) // REVIEW_LIMIT
 
    # ---- resume: tiếp tục từ trang kế tiếp nếu đã cào dở ----
    start_page = 1
    all_count = 0
    row = get_checkpoint_row(checkpoint, category_id, product_id)
    if row is not None and row["status"] in ("running", "error"):
        last_page = row["last_page"]
        crawled = row["reviews_crawled"]
        if pd.notna(last_page) and int(last_page) > 0:
            start_page = int(last_page) + 1
            all_count = int(crawled) if pd.notna(crawled) else 0
            print(f"[RESUME] product={product_id} | tiếp tục từ page={start_page}")
 
    print()
    print("=" * 70)
    print(f"[START] Category: {category_id} | Product ID: {product_id}")
    print(f"[INFO] Review count: {review_count} | pages dự kiến: {total_pages}")
    print("=" * 70)
 
    update_checkpoint(
        checkpoint, category_id, product_id, "running",
        review_count, all_count, start_page - 1, None,
    )
 
    last_done_page = start_page - 1
 
    for page in range(start_page, total_pages + 1):
        try:
            result = get_review_page(product_id, page)
            reviews = result.get("data", [])
 
            if not reviews:
                print(f"[STOP] product={product_id} | page={page} -> data=[]")
                break
 
            rows = [parse_review(r, product_id) for r in reviews]
 
            # Lưu ngay sau mỗi page vào file của danh mục hiện tại
            save_reviews(rows, review_file)
 
            all_count += len(rows)
            last_done_page = page
 
            update_checkpoint(
                checkpoint, category_id, product_id, "running",
                review_count, all_count, page, None,
            )
 
            print(f"[PAGE DONE] page={page} | got={len(rows)} | total={all_count}")
            time.sleep(1.5)
 
        except Exception as e:
            print(f"[ERROR] product={product_id} | page={page} | {e}")
            update_checkpoint(
                checkpoint, category_id, product_id, "error",
                review_count, all_count, last_done_page, str(e),
            )
            return
 
    update_checkpoint(
        checkpoint, category_id, product_id, "completed",
        review_count, all_count, last_done_page, None,
    )
    print(f"[COMPLETED] product={product_id} | reviews={all_count}")
 
 
# ============================================================
# 9. XỬ LÝ 1 DANH MỤC (1 file category_<ID>.csv)
# ============================================================
def process_category(file_name, checkpoint):
    category_id = file_name.replace("category_", "").replace(".csv", "")
    product_file = os.path.join(PRODUCT_DIR, file_name)
    review_file = os.path.join(REVIEW_DIR, f"category_{category_id}_reviews.csv")
 
    print(f"\n{'=' * 70}")
    print(f"[BẮT ĐẦU DANH MỤC] {file_name}")
    print(f"[CATEGORY_ID] {category_id}")
    print(f"[OUTPUT] {review_file}")
    print("=" * 70)
 
    try:
        products = pd.read_csv(product_file)
    except Exception as e:
        print(f"[ERROR] Không đọc được {file_name}: {e}")
        return
 
    missing = [c for c in ("id", "review_count") if c not in products.columns]
    if missing:
        print(f"[ERROR] {file_name} thiếu cột: {', '.join(missing)}")
        return
 
    print(f"[INFO] Tổng sản phẩm: {len(products)}")
 
    for _, product in products.iterrows():
        product_id = product["id"]
        review_count = product["review_count"]
 
        row = get_checkpoint_row(checkpoint, category_id, product_id)
        if row is not None and row["status"] in ("completed", "skipped_too_few"):
            print(f"[SKIP] Sản phẩm {product_id} -> {row['status']}")
            continue
 
        crawl_product(category_id, product_id, review_count, checkpoint, review_file)
        time.sleep(2)
 
    # Ghi checkpoint đầy đủ sau khi xong danh mục (gồm cả các sách bị skip)
    save_checkpoint(checkpoint)
    print(f"[HOÀN THÀNH DANH MỤC] {file_name} -> {review_file}")
 
 
# ============================================================
# 10. MAIN
# ============================================================
def get_category_files():
    """Danh sách category_<ID>.csv, sắp xếp theo ID số tăng dần."""
    files = [
        f
        for f in os.listdir(PRODUCT_DIR)
        if f.startswith("category_") and f.endswith(".csv")
    ]
 
    def sort_key(name):
        cid = name.replace("category_", "").replace(".csv", "")
        return (0, int(cid)) if cid.isdigit() else (1, cid)
 
    return sorted(files, key=sort_key)
 
 
def main():
    print("=" * 70)
    print("TIKI REVIEW CRAWLER - DUYỆT TỪNG DANH MỤC")
    print("=" * 70)
    print(f"[PRODUCT_DIR]    {PRODUCT_DIR}")
    print(f"[REVIEW_DIR]     {REVIEW_DIR}")
    print(f"[CHECKPOINT]     {CHECKPOINT_FILE}")
 
    all_files = get_category_files()
 
    if not all_files:
        print("[ERROR] Không có file category_*.csv nào trong thư mục products!")
        return
 
    print(f"[INFO] Tìm thấy {len(all_files)} file danh mục:")
    for idx, f in enumerate(all_files, 1):
        print(f"       {idx}. {f}")
 
    checkpoint = load_checkpoint()
 
    try:
        # Xong hẳn danh mục này (đã lưu vào REVIEW_DIR) rồi mới sang danh mục kế tiếp
        for file_name in all_files:
            process_category(file_name, checkpoint)
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n[DỪNG] Người dùng dừng chương trình, đang lưu checkpoint...")
    finally:
        save_checkpoint(checkpoint)
 
    print("\n" + "=" * 70)
    print("KẾT THÚC!")
    print(f"[CHECKPOINT] {CHECKPOINT_FILE}")
    print(f"[REVIEW_DIR] {REVIEW_DIR}")
 
    errors = checkpoint[checkpoint["status"] == "error"]
    if not errors.empty:
        print(f"[CẢNH BÁO] Còn {len(errors)} sách bị lỗi, chạy lại để cào tiếp từ trang dừng.")
    print("=" * 70)
 
 
if __name__ == "__main__":
    main()
 