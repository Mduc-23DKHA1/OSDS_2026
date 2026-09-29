import json
import os
import random
import time
import pandas as pd
from playwright.sync_api import sync_playwright

# ======================================================================
# CẤU HÌNH
# ======================================================================
CATEGORY_ID = 4144  # ID danh mục c4144: Sách Quản Trị Nhân Lực
LIMIT_PER_PAGE = 40  # Số sản phẩm tối đa Tiki trả về mỗi trang API
OUTPUT_FILE = "Kane_2_QTNhanLuc.csv"
OUTPUT_JSON = "Kane_2_QTNhanLuc.json"  # Lưu thêm file JSON nếu cần
DEBUG_DIR = "debug"
HEADLESS = False  # Để True khi cào qua API

SKIP_ADS = False  # True: bỏ sản phẩm quảng cáo
FULL_SIZE_IMAGE = True  # True: bỏ '/cache/280x280' để lấy ảnh chất lượng cao

COLUMNS = ["url", "name", "rating_average", "review_count", "image", "error"]


# ======================================================================
# HÀM TIỆN ÍCH
# ======================================================================
def random_sleep(low=1.0, high=2.5):
    """Nghỉ ngẫu nhiên để tránh tần suất request quá dồn dập"""
    time.sleep(random.uniform(low, high))


def parse_item(item):
    """Trích xuất và định dạng dữ liệu từng sản phẩm"""
    image = item.get("thumbnail_url")
    if image and FULL_SIZE_IMAGE:
        image = image.replace("/cache/280x280", "")

    url_path = item.get("url_path")
    # Tiki đôi khi trả về url_path dạng 'product-name-p12345.html' hoặc full URL
    if url_path:
        url = (
            f"https://tiki.vn/{url_path}"
            if not url_path.startswith("http")
            else url_path
        )
    else:
        url = None

    return {
        "url": url,
        "name": item.get("name"),
        "rating_average": item.get("rating_average"),
        "review_count": item.get("review_count"),
        "image": image,
        "error": None,
    }


def is_ad(item):
    """Kiểm tra xem sản phẩm có phải quảng cáo không"""
    try:
        return bool(item["impression_info"][0]["metadata"].get("is_ad"))
    except (KeyError, IndexError, TypeError):
        return False


# ======================================================================
# CHƯƠNG TRÌNH CHÍNH
# ======================================================================
def main():
    products = {}  # pid -> dict (loại bỏ trùng lặp)

    with sync_playwright() as p:
        print("🚀 Đang khởi tạo trình duyệt Playwright...")
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            locale="vi-VN",
        )

        page = context.new_page()

        # Gọi trang chủ 1 lần để thiết lập cookies & session hợp lệ của Tiki
        print("🌐 Đang kết nối tới Tiki...")
        page.goto("https://tiki.vn/", timeout=60000)
        random_sleep(2, 3)

        page_no = 1
        last_page = 1

        while page_no <= last_page:
            # Endpoint API chuẩn của danh mục Tiki
            api_url = (
                f"https://tiki.vn/api/v2/products"
                f"?limit={LIMIT_PER_PAGE}&include=advertisement&aggregations=2"
                f"&version=home-persionalized&category={CATEGORY_ID}&page={page_no}"
            )

            try:
                # Gọi API trực tiếp thông qua session Playwright (vượt Cloudflare tốt hơn)
                response = page.request.get(
                    api_url,
                    headers={
                        "Referer": f"https://tiki.vn/sach-quan-tri-nhan-luc/c{CATEGORY_ID}",
                        "Accept": "application/json, text/plain, */*",
                    },
                )

                if response.status != 200:
                    print(
                        f"  ⚠️ Trang {page_no}: API trả về status code {response.status}"
                    )
                    break

                data = response.json()
                items = data.get("data", [])
                paging = data.get("paging", {})

                # Cập nhật tổng số trang từ phản hồi của Tiki
                last_page = paging.get("last_page", last_page)

                if not items:
                    print(f"  ℹ️ Trang {page_no}: Không có sản phẩm nào, dừng.")
                    break

                added = 0
                for it in items:
                    pid = it.get("id")
                    if pid is None or pid in products:
                        continue
                    if SKIP_ADS and is_ad(it):
                        continue

                    products[pid] = parse_item(it)
                    added += 1

                print(
                    f"  ✅ Trang {page_no}/{last_page}: +{added} sản phẩm mới "
                    f"(Tổng tích lũy: {len(products)})"
                )

                page_no += 1
                random_sleep(1.5, 3.0)

            except Exception as e:
                print(f"  ❌ Lỗi tại trang {page_no}: {e}")
                break

        browser.close()

    results = list(products.values())

    if not results:
        print("\n❌ Không thu được sản phẩm nào!")
        return

    # Xuất ra file CSV (UTF-8 BOM để mở Excel không lỗi tiếng Việt)
    df = pd.DataFrame(results, columns=COLUMNS)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    # Xuất thêm file JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    ok_count = df["error"].isna().sum()
    print(
        f"\n🎉 HOÀN THÀNH: Đã xuất {len(df)} sản phẩm ({ok_count} thành công)"
    )
    print(f"📁 File CSV: {OUTPUT_FILE}")
    print(f"📁 File JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()