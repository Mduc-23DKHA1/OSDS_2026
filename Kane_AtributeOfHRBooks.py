import json
import random
import re
import time

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ======================================================================
# CẤU HÌNH
# ======================================================================
INPUT_JSON = "Kane_ListOfHumanResourceBook.json"   # File JSON chứa danh sách sản phẩm (có trường "url")
OUTPUT_FILE = "Kane_AtributeOfHRBooks.csv"
OUTPUT_JSON = "Kane_AtributeOfHRBooks.json"
SAVE_JSON = True

MAX_PRODUCTS = 8          # None = cào hết; hoặc số nguyên để chạy thử
MAX_LOAD_MORE = None      # None = bấm "Xem thêm" đến khi hết
MAX_REVIEW_PAGES = None   # None = lật trang review đến hết
MAX_SCROLL_ROUNDS = 60    # Số vòng cuộn tối đa để tải hết review
CHECKPOINT_EVERY = 10     # Lưu tạm sau mỗi N sản phẩm
HEADLESS = False          # Chạy ổn định thì đổi True

PAGE_LOAD_TIMEOUT = 60000
NETWORK_IDLE_TIMEOUT = 10000
REVIEW_BLOCK_TIMEOUT = 8000
PAGE_CHANGE_TIMEOUT = 10  # Số giây chờ nội dung đổi sau khi bấm sang trang
DELAY_MIN, DELAY_MAX = 1.5, 3.5

# Selector (dùng class ổn định, không dùng class hash của styled-components)
SEL_POINT = ".review-rating__point"
SEL_TOTAL = ".review-rating__total"
SEL_STARS = ".review-rating__stars"
SEL_REVIEW = ".review-comment"

SEL_PAGINATION = (
    ".customer-reviews__pagination, [class*='pagination'], [class*='Pagination']"
)
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
NEXT_TEXT_PATTERN = re.compile(r"^\s*(›|>|»|→|Sau|Tiếp|Trang sau|Next)\s*$", re.I)
LOAD_MORE_PATTERN = re.compile(r"Xem thêm.*đánh giá", re.I | re.S)

COLUMNS = [
    "url", "name",
    "rating_point", "rating_total", "rating_stars",
    "review_user", "review_stars", "review_title", "review_content",
    "error",
]

# ======================================================================
# JAVASCRIPT
# ======================================================================
# Đếm số sao "sáng" (có màu) trong 1 khối chứa các icon sao
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

# Lấy tất cả review đang có trên trang trong 1 lần gọi
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

# "Chữ ký" của danh sách review hiện tại (để biết trang đã đổi chưa)
JS_SIGNATURE = r"""
(sel) => {
    const els = Array.from(document.querySelectorAll(sel));
    if (!els.length) return '';
    const first = els[0].innerText.slice(0, 200);
    const last = els[els.length - 1].innerText.slice(0, 200);
    return els.length + '|' + first + '|' + last;
}
"""

# Kiểm tra 1 element có bị vô hiệu hoá không
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
# HÀM TIỆN ÍCH & CHE GIẤU BOT
# ======================================================================
def apply_stealth(page):
    """Che giấu dấu hiệu bot — không cần thư viện ngoài"""
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'en-US', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
    """)


def launch_browser(playwright):
    """Tạo trình duyệt + context + trang mới"""
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        locale="vi-VN",
        timezone_id="Asia/Ho_Chi_Minh",
    )
    page = context.new_page()
    apply_stealth(page)
    return browser, context, page


def random_sleep(low, high):
    time.sleep(random.uniform(low, high))


def wait_page_ready(page):
    page.wait_for_load_state("domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
    try:
        page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
    except PWTimeout:
        pass


def get_text(page, selector):
    element = page.locator(selector)
    if element.count() == 0:
        return None
    try:
        return element.first.inner_text(timeout=2000).strip()
    except Exception:
        return None


def count_stars(page, selector):
    element = page.locator(selector)
    if element.count() == 0:
        return None
    try:
        return element.first.evaluate(JS_COUNT_STARS)
    except Exception:
        return None


def load_urls(path):
    """Đọc danh sách url từ file JSON (dạng list[dict] hoặc dict)"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = list(data.values())

    items, seen = [], set()
    for it in data:
        url = it.get("url") if isinstance(it, dict) else None
        if url and url not in seen:
            seen.add(url)
            items.append({"url": url, "name": it.get("name")})
    return items


def review_key(r):
    return (r.get("review_user"), r.get("review_stars"),
            r.get("review_title"), r.get("review_content"))


# ======================================================================
# CUỘN & TẢI THÊM REVIEW
# ======================================================================
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
    """Cuộn tới review cuối cho đến khi số review ngừng tăng"""
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
            if stagnant >= 3:
                break
        else:
            stagnant = 0
            last = cur


def click_load_more(page):
    """Bấm 'Xem thêm ... đánh giá' đến khi hết nút hoặc không tăng thêm review"""
    clicks = 0
    stagnant = 0

    while MAX_LOAD_MORE is None or clicks < MAX_LOAD_MORE:
        btn = page.locator("a, button").filter(has_text=LOAD_MORE_PATTERN)
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

    scroll_until_all_loaded(page)


# ======================================================================
# PHÂN TRANG REVIEW
# ======================================================================
def _is_disabled(el):
    try:
        return bool(el.evaluate(JS_IS_DISABLED))
    except Exception:
        return False


def _first_usable(locator):
    """Element đầu tiên đang hiển thị và chưa bị disabled, không có thì None"""
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
    for sel in NEXT_SELECTORS:
        el = _first_usable(page.locator(sel))
        if el is not None:
            return el
    return None


def _find_next_by_text(page):
    cands = page.locator(SEL_PAGINATION).locator("a, button, li").filter(
        has_text=NEXT_TEXT_PATTERN
    )
    return _first_usable(cands)


def _find_next_by_number(page):
    """Tìm trang đang active (số N) rồi lấy nút số N+1"""
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
    """Bấm sang trang review kế tiếp. True nếu đã sang trang mới, False nếu hết trang."""
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


# ======================================================================
# THU THẬP REVIEW
# ======================================================================
def extract_page_reviews(page):
    """Lấy toàn bộ review đang hiển thị trên trang hiện tại, loại trùng"""
    raw = page.evaluate(JS_EXTRACT_REVIEWS, {"selReview": SEL_REVIEW})

    unique, seen = [], set()
    for r in raw:
        if not (r.get("review_title") or r.get("review_content")):
            continue
        key = review_key(r)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def collect_all_reviews(page):
    """Bấm 'Xem thêm' + cuộn, rồi lần lượt trích review và lật trang đến hết"""
    click_load_more(page)

    all_reviews, seen = [], set()
    page_no = 1

    while True:
        scroll_until_all_loaded(page)

        new = 0
        for r in extract_page_reviews(page):
            key = review_key(r)
            if key in seen:
                continue
            seen.add(key)
            all_reviews.append(r)
            new += 1

        print(f"     ↳ trang review {page_no}: +{new} (tổng {len(all_reviews)})")

        if new == 0:
            break
        if MAX_REVIEW_PAGES and page_no >= MAX_REVIEW_PAGES:
            break
        if not go_next_page(page):
            break

        page_no += 1
        page.wait_for_timeout(800)

    return all_reviews


# ======================================================================
# CÀO CHI TIẾT SẢN PHẨM
# ======================================================================
def scrape_product(page, item):
    """Cào 1 sản phẩm -> list các dòng (mỗi review 1 dòng)"""
    base = {c: None for c in COLUMNS}
    base.update({"url": item["url"], "name": item.get("name")})

    page.goto(item["url"], timeout=PAGE_LOAD_TIMEOUT)
    wait_page_ready(page)
    scroll_to_reviews(page)

    try:
        page.wait_for_selector(SEL_POINT, timeout=REVIEW_BLOCK_TIMEOUT)
    except PWTimeout:
        base["error"] = "Không tìm thấy khối đánh giá"
        return [base]

    base["rating_point"] = get_text(page, SEL_POINT)
    base["rating_total"] = get_text(page, SEL_TOTAL)
    base["rating_stars"] = count_stars(page, SEL_STARS)

    rows = []
    for rv in collect_all_reviews(page):
        row = dict(base)
        row.update(rv)
        rows.append(row)

    # Có tổng quan nhưng chưa có review chi tiết -> vẫn giữ 1 dòng
    return rows or [base]


# ======================================================================
# LƯU KẾT QUẢ
# ======================================================================
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
    # === Bước 1: Đọc danh sách url ===
    items = load_urls(INPUT_JSON)
    if MAX_PRODUCTS:
        items = items[:MAX_PRODUCTS]
    print(f"Bước 1: Đọc được {len(items)} url từ {INPUT_JSON}\n")

    if not items:
        print("Không có url nào để cào.")
        return

    # === Bước 2: Cào chi tiết — mỗi sản phẩm = 1 trình duyệt mới ===
    print("Bước 2: Cào review từng sản phẩm (mỗi link = trình duyệt mới)...")
    results = []

    with sync_playwright() as p:
        for idx, item in enumerate(items, start=1):
            brw = None
            try:
                brw, ctx, pg = launch_browser(p)
                rows = scrape_product(pg, item)
                results.extend(rows)

                n_rv = sum(1 for r in rows if r["review_content"] or r["review_title"])
                err = rows[0]["error"]
                status = f"⚠️ {err}" if err else f"✅ {n_rv} review"
                print(f"  [{idx}/{len(items)}] {status} | {item['url']}")
            except Exception as e:
                print(f"  [{idx}/{len(items)}] ❌ Lỗi: {str(e)[:100]} | {item['url']}")
                row = {c: None for c in COLUMNS}
                row.update({"url": item["url"], "name": item.get("name"),
                            "error": str(e)[:200]})
                results.append(row)
            finally:
                if brw:
                    brw.close()

            if idx % CHECKPOINT_EVERY == 0:
                save(results)
                print(f"  💾 Đã lưu tạm {len(results)} dòng")

            random_sleep(DELAY_MIN, DELAY_MAX)

    # === Lưu kết quả ===
    df = save(results)
    ok_count = df["error"].isna().sum()
    print(f"\n🎉 HOÀN THÀNH: {len(df)} dòng ({ok_count} thành công) từ {len(items)} sản phẩm")
    print(f"📁 File CSV: {OUTPUT_FILE}")
    if SAVE_JSON:
        print(f"📁 File JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()