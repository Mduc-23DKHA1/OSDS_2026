import sqlite3
def connect_db():
    return sqlite3.connect("Khang/API_Crawl/data/reviews/categories.db")

def run_query():
    conn = connect_db()
    cursor = conn.cursor()
    return conn, cursor

def option_1():
    conn, cursor = run_query()

    # 1. Đổi 'users' thành 'products'
    sql = "SELECT CustomerID, content, star, time_review, BookID, spid FROM CategoriesReview"
    cursor.execute(sql)
    products = cursor.fetchall()
    conn.close()

    # 2. In Tiêu đề với độ rộng phù hợp
    header = f"{'CustomerID':<15} | {'content':<30} | {'star':<6} | {'time_review':<20} | {'BookID':<12} | {'spid':<12}"
    print(header)
    print("-" * len(header))

    # 3. Duyệt và in từng dòng (cắt gọn Tên sản phẩm nếu quá dài)
    for p in products:
        customer_id, content, star, time_review, book_id, spid = p

        # Cắt ngắn tên nếu dài hơn 32 ký tự để không làm vỡ khung
        short_name = content[:15] + "..." if len(str(content)) > 15 else content

        print(
            f"{str(customer_id):<15} | {short_name:<30} | {str(star):<6} | {str(time_review):<20} | {str(book_id):<12} | {str(spid):<12}"
        )

    print("-" * len(header))
    
option_1()