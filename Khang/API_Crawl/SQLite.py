import csv
import glob
import os
import sqlite3

FOLDER = os.path.join("Khang", "API_Crawl", "data", "reviews")
DB_PATH = "Khang/API_Crawl/data/reviews/categories.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS CategoriesReview (
    ReviewID    INTEGER PRIMARY KEY AUTOINCREMENT,
    CustomerID  INTEGER,
    content     TEXT,
    star        INTEGER,
    time_review TEXT,
    BookID      INTEGER,
    spid        INTEGER,
    FOREIGN KEY (BookID) REFERENCES Categories(BookID)
);
""")

insert_sql = """
INSERT INTO CategoriesReview
    (CustomerID, content, star, time_review, BookID, spid)
VALUES (?, ?, ?, ?, ?, ?)
"""

def to_int(value):
    value = (value or "").strip()
    return int(value) if value else None

def to_text(value):
    value = (value or "").strip()
    return value if value else None

total_read = 0
for file_path in sorted(glob.glob(os.path.join(FOLDER, "*.csv"))):
    rows = []
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append((
                to_int(r.get("CustomerID")),
                r.get("content") or "",          # giữ nguyên, rỗng thì lưu chuỗi rỗng
                to_int(r.get("star")),
                to_text(r.get("time_review")),   # rỗng thì lưu NULL
                to_int(r.get("BookID")),
                to_int(r.get("spid")),
            ))

    cursor.executemany(insert_sql, rows)
    conn.commit()
    total_read += len(rows)
    print(f"{os.path.basename(file_path)}: đọc {len(rows)} dòng, đã import {len(rows)} dòng")

cursor.execute("SELECT COUNT(*) FROM CategoriesReview")
total_db = cursor.fetchone()[0]
print(f"Tổng dòng đọc từ CSV: {total_read} | Tổng dòng trong bảng: {total_db}")

conn.close()