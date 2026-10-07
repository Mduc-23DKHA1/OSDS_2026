# 📚 Tiki Book Data Crawling

Dự án thu thập dữ liệu sách và bình luận sách từ hệ thống Tiki thông qua API.

# Quy Trình Chạy
Optional:
- Tạo môi trường: ```python -m venv .env```
- Kích hoạt môi trường:
  - Windows: ```.env\Scripts\activate```
  - Linux/macOS: ```source .env/bin/activate```
- Cài đặt dependencies:```pip install -r requirements.txt```

## Chạy chính:
- py run.py

*Lưu ý: Không chạy những gì có trong thư mục utils*
## 2 File API này sẽ chạy xoay quanh để lấy dữ liệu ở Tiki về:
- API_Books_Categories.py : 
  - Lấy tất cả các sách trong 1 danh mục sách cụ thể 
- API_Reviews_Books.py :
  - Lấy tất cả bình luận trong 1 cuốn sách cụ thể 
