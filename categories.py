import json
import csv


def dfs_category(cur, parent_id, rows):
    """
    Duyệt cây category theo DFS.
    """

    # -------------------------
    # 1. Kiểm tra children
    # -------------------------
    children = cur.get("children", [])

    # Đảm bảo nếu API trả None thì vẫn xem như không có children
    if children is None:
        children = []

    children_count = len(children)

    # -------------------------
    # 2. Lưu thông tin hiện tại
    # -------------------------
    row = {
        "id": cur.get("id"),
        "parent_id": parent_id,
        "name": cur.get("name"),
        "url_key": cur.get("url_key"),
        "product_count": cur.get("product_count"),
        "children_count": children_count,
    }

    rows.append(row)

    # -------------------------
    # 3. Nếu có children → DFS
    # -------------------------
    if children_count > 0:
        for child in children:
            dfs_category(child, cur.get("id"), rows)


def main():

    # =========================
    # Đọc JSON
    # =========================
    with open("categories_316.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []

    # =========================
    # DFS từ 24 category gốc
    # =========================
    for root in data["data"]:

        dfs_category(root, root.get("parent_id"), rows)

    fieldnames = [
        "id",
        "parent_id",
        "name",
        "url_key",
        "product_count",
        "children_count",
    ]

    with open("categories.csv", "w", newline="", encoding="utf-8-sig") as f:

        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(rows)

    print(f"Đã ghi {len(rows)} categories " f"vào categories.csv")


if __name__ == "__main__":
    main()
