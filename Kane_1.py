import json
import requests


def scrape_tiki_category(parent_id: int):
    # Endpoint và tham số truy vấn
    url = "https://tiki.vn/api/v2/categories"
    params = {"include": "children", "parent_id": parent_id}

    # Headers giả lập trình duyệt thực tế
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://tiki.vn/",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            filename = f"Kane_1_{parent_id}.json"

            # Lưu ra file JSON với định dạng tiếng Việt đúng
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            print(
                f"Lấy dữ liệu thành công cho parent_id={parent_id}! Đã lưu vào file '{filename}'."
            )
            return data
        else:
            print(
                f"Lỗi khi gọi API (parent_id={parent_id}). Mã lỗi: {response.status_code}"
            )

    except requests.exceptions.RequestException as e:
        print(f"Lỗi kết nối: {e}")


# Thực thi cào dữ liệu cho parent_id = 846
if __name__ == "__main__":
    scrape_tiki_category(846)