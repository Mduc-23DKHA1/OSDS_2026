import pandas as pd
import sqlite3
# Kết nối đến cơ sở dữ liệu SQLite
conn = sqlite3.connect("Khang/API_Crawl/data/reviews/categoriesReview.db")
# Đọc dữ liệu từ bảng CategoriesReview và xuất ra file CSV
df = pd.read_sql_query("SELECT * FROM CategoriesReview", conn)
# Xuất dữ liệu ra file CSV với encoding UTF-8 và không bao gồm chỉ số
df.to_csv("Khang/API_Crawl/data/reviews/categoriesReview.csv", index=False, encoding="utf-8-sig")
# Đóng kết nối cơ sở dữ liệu
conn.close()
print("Dữ liệu đã được xuất ra file CSV thành công.")