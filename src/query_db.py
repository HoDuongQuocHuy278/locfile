"""
query_db.py – Truy vấn bảng products, trả về list dict.

Cải tiến:
  - Trả về list thay vì print JSON (Flask API gọi trực tiếp)
  - ORDER BY stock DESC, LIMIT 20
  - Dùng db_connection.get_connection (có retry)
"""

from src.db_connection import get_connection
from src.logger import get_logger

log = get_logger("query_db")


def fetch_data() -> list:
    """
    Lấy top 20 sản phẩm có tồn kho cao nhất.

    Returns:
        list[dict]: danh sách sản phẩm {"id", "name", "price", "stock"}

    Raises:
        Exception: nếu query thất bại (để Flask API bắt và trả 500)
    """
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT id, name, price, stock "
        "FROM   products "
        "ORDER  BY stock DESC "
        "LIMIT  20"
    )
    rows = cursor.fetchall()

    # Ép kiểu Decimal → float để jsonify không lỗi
    for row in rows:
        if row.get("price") is not None:
            row["price"] = float(row["price"])

    cursor.close()
    conn.close()

    log.info(f"Truy vấn thành công – {len(rows)} sản phẩm.")
    return rows
