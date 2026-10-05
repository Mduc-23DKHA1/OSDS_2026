# 📚 Tiki Book Data Crawling

Dự án thu thập dữ liệu sách và bình luận sách từ hệ thống Tiki thông qua API.

## 📌 Quy trình tổng quát

Quá trình thu thập dữ liệu được thực hiện theo thứ tự:

```text
API Review Books
       │
       ▼
Lấy danh sách các thể loại con
       │
       ▼
Extract Categories
       │
       ▼
Lấy toàn bộ category nhánh (leaf categories)
       │
       ├───────────────┐
       ▼               ▼
API Books Categories   API Reviews Books
       │               │
       ▼               ▼
Danh sách sách         Bình luận sách
theo category          theo category