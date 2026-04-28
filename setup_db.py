"""
setup_db.py – Khởi tạo (Reset) database MySQL từ init.sql.
Trả về dict để Flask API gọi trực tiếp.

CẢNH BÁO: Sẽ XÓA và TẠO LẠI database 'mydb'.
"""

import os
import sys
import mysql.connector
from mysql.connector import Error
from src.logger import get_logger

log = get_logger("setup_db")

SQL_FILE = "data/sql/init.sql"
DB_HOST  = "localhost"
DB_USER  = "root"
DB_PASS  = ""


def setup_database() -> dict:
    """
    Xóa và tạo lại database 'mydb', rồi thực thi init.sql.

    Returns:
        dict: {"success": bool, "message": str, "stats": {...}}
    """
    log.info("=" * 50)
    log.info("Bắt đầu khởi tạo database...")

    if not os.path.exists(SQL_FILE):
        msg = f"Không tìm thấy file SQL: {SQL_FILE}"
        log.error(msg)
        return {"success": False, "message": msg, "stats": {}}

    try:
        conn   = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()

        log.info("Kết nối MySQL thành công. Đang reset database 'mydb'...")
        cursor.execute("DROP DATABASE IF EXISTS mydb")
        cursor.execute("CREATE DATABASE mydb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute("USE mydb")

        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        executed = 0
        failed   = 0

        for stmt in sql_content.split(';'):
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                cursor.execute(stmt)
                executed += 1
            except Error as e:
                log.warning(f"SQL bị bỏ qua: {e} | stmt: {stmt[:80]}...")
                failed += 1

        conn.commit()

        stats = {"executed": executed, "failed": failed}
        msg   = f"Khởi tạo CSDL thành công! ({executed} câu lệnh)"
        log.info(f"✔ {msg} | Stats: {stats}")
        log.info("=" * 50)
        return {"success": True, "message": msg, "stats": stats}

    except Error as e:
        msg = f"Lỗi kết nối MySQL: {e}"
        log.error(msg)
        return {"success": False, "message": msg, "stats": {}}

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()
            log.info("Đã đóng kết nối MySQL.")


# Cho phép chạy độc lập qua CLI
if __name__ == "__main__":
    result = setup_database()
    print(result["message"])
    if not result["success"]:
        sys.exit(1)
