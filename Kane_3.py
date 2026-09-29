import json
import os
import random
import re
import time

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ======================================================================
# CẤU HÌNH
# ======================================================================
INPUT_JSON = "sach_quan_tri_nhan_luc.json"   # File JSON chứa danh sách sản phẩm (có trường "url")
OUTPUT_FILE = "sach_quan_tri_nhan_luc_reviews.csv"
OUTPUT_JSON = "sach_quan_tri_nhan_luc_reviews.json"
DEBUG_DIR = "debug"

HEADLESS = False          # Nên để False lúc test; chạy ổn định thì đổi True
MAX_PRODUCTS = 8          # None = cào hết; hoặc số nguyên để chạy thử (vd: 5)
MAX_LOAD_MORE = None      # None = bấm "Xem thêm" đến khi hết; hoặc số nguyên để giới hạn
MAX_REVIEW_PAGES = None   # None = lật trang review đến hết; hoặc số nguyên để giới hạn (vd: 5)
MAX_SCROLL_ROUNDS = 60    # Số vòng cuộn tối đa để tải hết review (chống lặp vô hạn)
PAGE_CHANGE_TIMEOUT = 10  # Số giây chờ nội dung đổi sau khi bấm sang trang
CHECKPOINT_EVERY = 10     # Lưu tạm ra file sau mỗi N sản phẩm
SAVE_JSON = True

# Selector (dùng class ổn định, KHÔNG dùng class hash như 'sc-a236768f-0 fFhahK'
# vì chuỗi hash của styled-components sẽ đổi mỗi khi Tiki cập nhật giao diện)
SEL_POINT = ".review-rating__point"
SEL_TOTAL = ".review-rating__total"
SEL_STARS = ".review-rating__stars"
SEL_REVIEW = ".review-comment"

# Vùng phân trang của review
SEL_PAGINATION = (
    ".customer-reviews__pagination, [class*='pagination'], [class*='Pagination']"
)
# Các selector ứng viên cho nút "trang sau" (thử lần lượt)
NEXT_SELECTORS = [
    ".customer-reviews__pagination a.next",
    ".customer-reviews__pagination .btn.next",
    ".customer-reviews__pagination .next",
    "a[rel='next']",
    "[class*='pagination'] [aria-label*='next' i]",
    "[class*='pagination'] [aria-label*='sau' i]",
    "[class*='pagination'] .next",
    "[class*='pagination'] [class*='next']",
    "[class*='Pagination'] [class*='next']",
]
# Nút "trang sau" dạng ký tự / chữ
NEXT_TEXT_PATTERN = re.compile(r"^\s*(›|>|»|→|Sau|Tiếp|Trang sau|Next)\s*$", re.I)

COLUMNS = [
    "url", "name",
    "rating_point", "rating_total", "rating_stars",
    "review_user", "review_stars", "review_title", "review_content",
    "error",
]

# ======================================================================
# JS: đếm số sao "sáng" trong 1 khối chứa các icon sao
# Sao sáng = có màu (vàng), sao tối = màu xám (r≈g≈b)
# ======================================================================
JS_COUNT_STARS = r"""
el => {
    if (!el) return null;
    const icons = el.querySelectorAll('svg, img');
    if (!icons.length) return null;
    let filled = 0;
    icons.forEach(ic => {
        if (ic.tagName.toLowerCase() === 'img') {
            const src = (ic.getAttribute('src') || '').toLowerCase();
            if (!/(gray|grey|inactive|empty|outline|disable)/.test(src)) filled++;
            return;
        }
        const nodes = [ic, ...ic.querySelectorAll('path, polygon, g, circle')];
        let colored = false;
        for (const n of nodes) {
            const f = getComputedStyle(n).fill;
            const m = f && f.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
            if (m) {
                const r = +m[1], g = +m[2], b = +m[3];
                if (Math.max(r, g, b) - Math.min(r, g, b) > 40) { colored = true; break; }
            }
        }
        if (colored) filled++;
    });
    return filled;
}
"""

# ======================================================================
# JS: lấy TẤT CẢ review đang có trên trang trong 1 lần gọi
# ======================================================================
JS_EXTRACT_REVIEWS = r"""
(args) => {
    const { selReview } = args;

    const countStars = (el) => {
        if (!el) return null;
        const icons = el.querySelectorAll('svg, img');
        if (!icons.length) return null;
        let filled = 0;
        icons.forEach(ic => {
            if (ic.tagName.toLowerCase() === 'img') {
                const src = (ic.getAttribute('src') || '').toLowerCase();
                if (!/(gray|grey|inactive|empty|outline|disable)/.test(src)) filled++;
                return;
            }
            const nodes = [ic, ...ic.querySelectorAll('path, polygon, g, circle')];
            let colored = false;
            for (const n of nodes) {
                const f = getComputedStyle(n).fill;
                const m = f && f.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
                if (m) {
                    const r = +m[1], g = +m[2], b = +m[3];
                    if (Math.max(r, g, b) - Math.min(r, g, b) > 40) { colored = true; break; }
                }
            }
            if (colored) filled++;
        });
        return filled;
    };

    const txt = (root, sel) => {
        const e = root.querySelector(sel);
        return e ? e.innerText.trim() : null;
    };

    return Array.from(document.querySelectorAll(selReview)).map(rv => ({
        review_user:    txt(rv, '.review-comment__user-name'),
        review_stars:   countStars(rv.querySelector('.review-comment__rating')),
        review_title:   txt(rv, '.review-comment__title'),
        review_content: txt(rv, '.review-comment__content'),
    }));
}
"""

# ======================================================================
# JS: "chữ ký" của danh sách review hiện tại (dùng để biết trang đã đổi chưa)
# ======================================================================
JS_SIGNATURE = r"""
(sel) => {
    const els = Array.from(document.querySelectorAll(sel));
    if (!els.length) return '';
    const first = els[0].innerText.slice(0, 200);
    const last = els[els.length - 1].innerText.slice(0, 200);
    return els.length + '|' + first + '|' + last;
}
"""

# ======================================================================
# JS: kiểm tra 1 element có bị vô hiệu hoá (disabled) không
# ======================================================================
JS_IS_DISABLED = r"""
e => {
    const cls = (e.className || '').toString().toLowerCase();
    return e.disabled === true
        || e.getAttribute('aria-disabled') === 'true'
        || /(^|\s)(disabled|inactive)(\s|$)/.test(cls)
        || e.closest('[aria-disabled="true"], .disabled') !== null;
}
"""


# ======================================================================
# HÀM TIỆN ÍCH
# ======================================================================
def random_sleep(low=1.0, high=2.5):
    time.sleep(random.uniform(low, high))


def load_urls(path):
    """Đọc danh sách url từ file JSON (dạng list[dict] hoặc dict)"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = list(data.values())

    items = []
    seen = set()
    for it in data:
        url = it.get("url") if isinstance(it, dict) else None
        if url and url not in seen:
            seen.add(url)
            items.append({"url": url, "name": it.get("name")})
    return items


def safe_text(locator):
    """Lấy inner_text của element đầu tiên, không có thì trả None"""
    try:
        if locator.count() == 0:
            return None
        return locator.first.inner_text(timeout=2000).strip()
    except Exception:
        return None


def count_stars(locator):
    try:
        if locator.count() == 0:
            return None
        return locator.first.evaluate(JS_COUNT_STARS)
    except Exception:
        return None


def scroll_to_reviews(page):
    """Cuộn dần xuống để Tiki lazy-load phần đánh giá"""
    for _ in range(12):
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(500)
        if page.locator(SEL_POINT).count() > 0:
            break
    try:
        page.locator(SEL_POINT).first.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass


def scroll_until_all_loaded(page):
    """
    Cuộn tới review cuối cùng liên tục (cả trên trang lẫn trong popup cuộn)
    cho đến khi số review ngừng tăng -> tải hết lazy-load.
    """
    stagnant = 0
    last = page.locator(SEL_REVIEW).count()
    for _ in range(MAX_SCROLL_ROUNDS):
        try:
            page.locator(SEL_REVIEW).last.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(900)

        cur = page.locator(SEL_REVIEW).count()
        if cur <= last:
            stagnant += 1
            if stagnant >= 3:      # 3 vòng liền không có review mới -> dừng
                break
        else:
            stagnant = 0
            last = cur


def click_load_more(page):
    """
    Bấm 'Xem thêm ... đánh giá' đến khi hết nút / không tăng thêm review.
    Sau mỗi lần bấm đều cuộn để tải hết phần lazy-load.
    (Việc lật sang các trang review kế tiếp do go_next_page() đảm nhiệm.)
    """
    clicks = 0
    stagnant = 0
    pattern = re.compile(r"Xem thêm.*đánh giá", re.I | re.S)

    while MAX_LOAD_MORE is None or clicks < MAX_LOAD_MORE:
        btn = page.locator("a, button").filter(has_text=pattern)
        if btn.count() == 0:
            break

        before = page.locator(SEL_REVIEW).count()
        try:
            btn.first.scroll_into_view_if_needed(timeout=3000)
            btn.first.click(timeout=3000)
        except Exception:
            break
        clicks += 1
        page.wait_for_timeout(1500)

        scroll_until_all_loaded(page)

        after = page.locator(SEL_REVIEW).count()
        if after <= before:
            stagnant += 1
            if stagnant >= 2:
                break
        else:
            stagnant = 0

    # Kể cả khi không có nút "Xem thêm", vẫn cuộn để chắc chắn tải hết
    scroll_until_all_loaded(page)


# ----------------------------------------------------------------------
# PHÂN TRANG REVIEW
# ----------------------------------------------------------------------
def _is_disabled(el):
    try:
        return bool(el.evaluate(JS_IS_DISABLED))
    except Exception:
        return False


def _first_usable(locator):
    """Trả về element đầu tiên đang hiển thị và chưa bị disabled, không có thì None"""
    try:
        n = locator.count()
    except Exception:
        return None
    for i in range(min(n, 10)):
        el = locator.nth(i)
        try:
            if el.is_visible() and not _is_disabled(el):
                return el
        except Exception:
            continue
    return None


def _find_next_by_selector(page):
    """Cách 1: tìm nút 'trang sau' theo class / aria-label / rel=next"""
    for sel in NEXT_SELECTORS:
        el = _first_usable(page.locator(sel))
        if el is not None:
            return el
    return None


def _find_next_by_text(page):
    """Cách 2: tìm nút có nội dung là ký tự ›, >, », 'Sau', 'Tiếp'... trong vùng phân trang"""
    cands = page.locator(SEL_PAGINATION).locator("a, button, li").filter(
        has_text=NEXT_TEXT_PATTERN
    )
    return _first_usable(cands)


def _find_next_by_number(page):
    """Cách 3: tìm trang đang active (số N) rồi bấm vào nút số N+1"""
    pags = page.locator(SEL_PAGINATION)
    try:
        n = pags.count()
    except Exception:
        return None

    for i in range(min(n, 5)):
        pag = pags.nth(i)
        try:
            if not pag.is_visible():
                continue
            active = pag.locator(
                "[aria-current='true'], [aria-current='page'], "
                ".active, [class*='active'], [class*='current']"
            )
            cur = None
            for j in range(min(active.count(), 5)):
                m = re.search(r"\d+", active.nth(j).inner_text(timeout=1000) or "")
                if m:
                    cur = int(m.group())
                    break
            if cur is None:
                continue

            target = pag.locator("a, button").filter(
                has_text=re.compile(rf"^\s*{cur + 1}\s*$")
            )
            el = _first_usable(target)
            if el is not None:
                return el
        except Exception:
            continue
    return None


def _wait_signature_change(page, old_sig):
    """Chờ đến khi danh sách review đổi so với old_sig. True nếu đổi."""
    deadline = time.time() + PAGE_CHANGE_TIMEOUT
    while time.time() < deadline:
        page.wait_for_timeout(400)
        try:
            new_sig = page.evaluate(JS_SIGNATURE, SEL_REVIEW)
        except Exception:
            continue
        if new_sig and new_sig != old_sig:
            return True
    return False


def go_next_page(page):
    """
    Bấm sang trang review kế tiếp.
    Trả về True nếu đã sang trang mới (nội dung review đã đổi), False nếu hết trang.
    """
    old_sig = page.evaluate(JS_SIGNATURE, SEL_REVIEW)

    nxt = (
        _find_next_by_selector(page)
        or _find_next_by_text(page)
        or _find_next_by_number(page)
    )
    if nxt is None:
        return False

    try:
        nxt.scroll_into_view_if_needed(timeout=3000)
        nxt.click(timeout=3000)
    except Exception:
        try:
            nxt.click(timeout=3000, force=True)
        except Exception:
            return False

    return _wait_signature_change(page, old_sig)


def extract_all_reviews(page):
    """Lấy toàn bộ review đang hiển thị (trên trang hiện tại), loại trùng"""
    raw = page.evaluate(JS_EXTRACT_REVIEWS, {"selReview": SEL_REVIEW})

    unique, seen = [], set()
    for r in raw:
        if not (r.get("review_title") or r.get("review_content")):
            continue   # bỏ khối rỗng (vd: chỉ có tổng quan)
        key = (r.get("review_user"), r.get("review_stars"),
               r.get("review_title"), r.get("review_content"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def collect_all_reviews(page):
    """
    Lấy review của TẤT CẢ các trang:
      1. Bấm 'Xem thêm' + cuộn để tải hết review trang đầu
      2. Trích review -> bấm 'trang sau' -> cuộn -> trích ... đến khi hết trang
    """
    click_load_more(page)

    all_reviews, seen = [], set()
    page_no = 1

    while True:
        scroll_until_all_loaded(page)

        new = 0
        for r in extract_all_reviews(page):
            key = (r.get("review_user"), r.get("review_stars"),
                   r.get("review_title"), r.get("review_content"))
            if key in seen:
                continue
            seen.add(key)
            all_reviews.append(r)
            new += 1

        print(f"     ↳ trang review {page_no}: +{new} (tổng {len(all_reviews)})")

        # Trang này không có review mới -> đã hết (hoặc lặp trang) -> dừng
        if new == 0:
            break
        if MAX_REVIEW_PAGES and page_no >= MAX_REVIEW_PAGES:
            break
        if not go_next_page(page):
            break

        page_no += 1
        page.wait_for_timeout(800)

    return all_reviews


def scrape_product(page, item):
    """Cào 1 sản phẩm -> trả về list các dòng (mỗi review 1 dòng)"""
    url = item["url"]
    base = {c: None for c in COLUMNS}
    base.update({"url": url, "name": item.get("name")})

    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    scroll_to_reviews(page)

    try:
        page.wait_for_selector(SEL_POINT, timeout=8000)
    except PWTimeout:
        # Sản phẩm chưa có đánh giá hoặc trang không load được
        base["error"] = "Không tìm thấy khối đánh giá"
        return [base]

    # --- Tổng quan ---
    base["rating_point"] = safe_text(page.locator(SEL_POINT))
    base["rating_total"] = safe_text(page.locator(SEL_TOTAL))
    base["rating_stars"] = count_stars(page.locator(SEL_STARS))

    # --- Tải hết review của mọi trang ---
    reviews = collect_all_reviews(page)

    rows = []
    for rv in reviews:
        row = dict(base)
        row.update(rv)
        rows.append(row)

    # Có tổng quan nhưng chưa có review chi tiết -> vẫn giữ 1 dòng
    return rows or [base]


def save(results):
    df = pd.DataFrame(results, columns=COLUMNS)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    if SAVE_JSON:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
    return df


# ======================================================================
# CHƯƠNG TRÌNH CHÍNH
# ======================================================================
def main():
    os.makedirs(DEBUG_DIR, exist_ok=True)

    items = load_urls(INPUT_JSON)
    if MAX_PRODUCTS:
        items = items[:MAX_PRODUCTS]
    print(f"📂 Đọc được {len(items)} url từ {INPUT_JSON}")

    results = []

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
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()

        print("🌐 Đang kết nối tới Tiki...")
        page.goto("https://tiki.vn/", timeout=60000)
        random_sleep(2, 3)

        for idx, item in enumerate(items, 1):
            try:
                rows = scrape_product(page, item)
                results.extend(rows)
                n_rv = sum(1 for r in rows if r["review_content"] or r["review_title"])
                err = rows[0]["error"]
                status = f"⚠️ {err}" if err else f"✅ {n_rv} review"
                print(f"  [{idx}/{len(items)}] {status} | {item['url']}")
            except Exception as e:
                print(f"  [{idx}/{len(items)}] ❌ Lỗi: {e} | {item['url']}")
                row = {c: None for c in COLUMNS}
                row.update({"url": item["url"], "name": item.get("name"), "error": str(e)})
                results.append(row)
                try:
                    page.screenshot(path=f"{DEBUG_DIR}/error_{idx}.png")
                except Exception:
                    pass

            if idx % CHECKPOINT_EVERY == 0:
                save(results)
                print(f"  💾 Đã lưu tạm {len(results)} dòng")

            random_sleep(1.5, 3.5)

        browser.close()

    if not results:
        print("\n❌ Không thu được dữ liệu nào!")
        return

    df = save(results)
    ok_count = df["error"].isna().sum()
    print(f"\n🎉 HOÀN THÀNH: {len(df)} dòng ({ok_count} thành công) từ {len(items)} sản phẩm")
    print(f"📁 File CSV: {OUTPUT_FILE}")
    if SAVE_JSON:
        print(f"📁 File JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()