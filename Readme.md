# Quy trình tổng hợp và làm sạch dữ liệu đánh giá sách

## 1. Cấu trúc thư mục

```text
Crawl_Data/
├── analysist/
│   └── phan_tich_data.ipynb
├── data/
│   ├── products/
│   ├── reviews/
│   │   ├── category_369_reviews.csv
│   │   ├── category_372_reviews.csv
│   │   └── ...
│   └── raw_data.csv          # được tạo sau khi chạy script
├── merge_reviews.py
└── README.md
```

## 2. Bước hiện tại: gộp các file review

Chạy script từ thư mục gốc dự án:

```bash
python merge_reviews.py
```

Script thực hiện đúng các việc sau:

1. Tìm các file có đuôi `.csv` nằm trực tiếp trong `data/reviews/`.
2. Đọc từng file và kiểm tra cột index có thể phát sinh khi lưu DataFrame ra CSV, thường có tên `Unnamed: 0`; đồng thời nhận diện `index` hoặc `level_0` nếu các giá trị là dãy số thứ tự liên tiếp.
3. Chỉ bỏ cột index được nhận diện. Các cột dữ liệu còn lại và nội dung review không bị chỉnh sửa.
4. Nối các dòng của tất cả file thành một DataFrame.
5. Lưu kết quả thành `data/raw_data.csv` — trực tiếp trong thư mục `data/`, không nằm trong `products/` hay `reviews/`.

File đầu ra được lưu với `index=False`, vì vậy script không tạo thêm một cột index mới. Script **không** xóa dòng trùng lặp, không sửa giá trị thiếu, không chuẩn hóa văn bản và không thay đổi kiểu dữ liệu. Đây là bước tổng hợp dữ liệu thô, chưa phải bước làm sạch.

Các cột thường gặp trong dữ liệu hiện tại:

| Cột | Ý nghĩa dự kiến | Lưu ý khi làm sạch |
|---|---|---|
| `CustomerID` | Mã khách hàng | Xem là mã định danh, không phải đại lượng để tính toán. |
| `content` | Nội dung đánh giá | Kiểm tra thiếu/rỗng; giữ nguyên văn bản gốc ở bản raw. |
| `star` | Số sao đánh giá | Kiểm tra có chuyển được sang số và có nằm trong miền hợp lệ 1–5 hay không. |
| `time_review` | Thời điểm đánh giá | Kiểm tra định dạng và các giá trị không chuyển được sang ngày giờ. |
| `BookID` | Mã sách | Xem là mã định danh; không tự suy ra thứ tự từ giá trị số. |
| `spid` | Mã nhóm/sản phẩm theo nguồn thu thập | Cần xác minh ý nghĩa và mức độ duy nhất trước khi dùng làm khóa. |

Nếu các file nguồn có cột dữ liệu thực sự khác tên hoặc khác cấu trúc, cần xem thông báo và danh sách cột của `raw_data.csv` trước khi làm bước tiếp theo.

## 3. Quy trình đề xuất để tạo bộ dữ liệu sạch cơ bản

Giữ `raw_data.csv` làm bản tổng hợp thô, không ghi đè lên nó. Sau đó thực hiện từng bước dưới đây và lưu kết quả sạch sang một file riêng, chẳng hạn `data/clean_data.csv`.

### Bước 1 — Xác định cấu trúc và kiểu dữ liệu

- Xác nhận đơn vị của một dòng là một lượt đánh giá.
- Kiểm tra tên cột, số dòng, số cột, số lượng giá trị thiếu và kiểu dữ liệu thực tế.
- Đọc `CustomerID`, `BookID` và `spid` như các mã định danh; không ép chúng thành số nếu có nguy cơ mất số 0 ở đầu.
- Chuyển `star` sang kiểu số sau khi kiểm tra các giá trị không hợp lệ; chuyển `time_review` sang kiểu ngày giờ sau khi thống kê các giá trị không parse được.
- Ghi lại mọi sai khác so với cấu trúc dự kiến, thay vì âm thầm sửa dữ liệu.

### Bước 2 — Kiểm tra giá trị thiếu và bản ghi không dùng được

- Thống kê giá trị thiếu theo từng cột.
- Xác định riêng các dòng không có `content`, nội dung chỉ gồm khoảng trắng, hoặc thiếu mã định danh cần thiết.
- Không tự động xóa mọi dòng có giá trị thiếu. Quyết định giữ, loại hoặc đánh dấu từng loại trường hợp dựa trên mục tiêu của bộ dữ liệu và ghi lại số dòng bị ảnh hưởng.

### Bước 3 — Kiểm tra tính hợp lệ và nhất quán

- `star`: kiểm tra giá trị thuộc miền 1–5; giữ các giá trị sai trong báo cáo lỗi để rà soát trước khi quyết định xử lý.
- `time_review`: kiểm tra ngày không hợp lệ và các định dạng ngày giờ khác nhau.
- `CustomerID`, `BookID`, `spid`: kiểm tra giá trị rỗng và các dạng biểu diễn không nhất quán.
- `content`: kiểm tra khoảng trắng thừa ở đầu/cuối và các nội dung rỗng. Nếu tạo bản văn bản đã chuẩn hóa, giữ nguyên `raw_data.csv` để có thể đối chiếu.

### Bước 4 — Phát hiện trùng lặp một cách thận trọng

- Thống kê số dòng trùng hoàn toàn trên các cột trước khi loại bỏ.
- Rà soát các trường hợp có cùng khách hàng, sách, thời điểm và nội dung để tìm bản ghi có khả năng bị thu thập lặp.
- Không loại bản ghi chỉ vì nội dung review giống nhau: hai người có thể viết cùng một nội dung, hoặc một người có thể gửi đánh giá tương tự nhiều lần.
- Ghi rõ quy tắc loại trùng và số dòng được loại trong báo cáo.

### Bước 5 — Kiểm tra phạm vi dữ liệu và quan hệ giữa các mã

- Đếm số đánh giá, khách hàng, sách và mã `spid` duy nhất.
- Kiểm tra một `BookID` có thể liên quan đến nhiều `spid` hay không; không mặc định `spid` là mã sách duy nhất nếu chưa xác minh từ nguồn.
- Kiểm tra khoảng thời gian, phân bố số sao và số lượng bản ghi theo từng danh mục để phát hiện dữ liệu bất thường.

### Bước 6 — Tạo bản sạch và báo cáo chất lượng

Sau khi áp dụng các quy tắc đã thống nhất, lưu dữ liệu sang `clean_data.csv`, không ghi đè bản raw. Kèm một báo cáo ngắn gồm:

- Số file nguồn và số dòng trước xử lý.
- Số dòng sau mỗi bước, số dòng thiếu/rỗng, sai kiểu hoặc sai miền giá trị.
- Số bản ghi bị loại và lý do loại.
- Danh sách cột, ý nghĩa, kiểu dữ liệu và các quy tắc đã áp dụng.
- Những giới hạn đã biết của dữ liệu nguồn.

## 4. Tiêu chí hoàn thành benchmark dữ liệu cơ bản

Bộ dữ liệu có thể xem là đã được làm sạch ở mức cơ bản khi:

- Có bản raw được giữ nguyên và bản clean được tạo riêng.
- Cấu trúc cột và ý nghĩa mỗi cột đã được mô tả.
- Giá trị thiếu, sai định dạng, sai miền và bản ghi trùng đã được thống kê, xử lý theo quy tắc có thể giải thích.
- Mỗi quyết định loại hoặc sửa dữ liệu có lý do và có thể kiểm tra lại.
- Có báo cáo tóm tắt chất lượng trước và sau xử lý.

Phạm vi này chỉ tập trung vào chất lượng và tính nhất quán của dữ liệu. **Chưa** bao gồm tiền xử lý NLP hoặc chuẩn bị mô hình như tokenization, vectorization, padding, embedding hay huấn luyện mô hình.
