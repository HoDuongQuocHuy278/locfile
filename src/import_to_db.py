"""
import_to_db.py – Module 2: Nạp dữ liệu đã làm sạch vào MySQL.

Cải tiến:
  - Trả về dict kết quả thay vì print (để Flask API dùng)
  - Transaction: commit khi thành công, rollback khi lỗi
  - Retry DB connection (qua db_connection.get_connection)
  - IDEMPOTENT: SET stock = qty (không cộng dồn)
  - Kiểm tra file clean trước khi kết nối DB
"""

import csv
import os
from src.db_connection import get_connection
from src.logger import get_logger

log = get_logger("import_to_db")

CLEAN_FILE = "data/processed/clean_inventory.csv"


def import_data() -> dict:
    """
    Đọc clean_inventory.csv và cập nhật cột stock trong bảng products.

    Returns:
        dict: {"success": bool, "message": str, "stats": {...}}
    """
    log.info("=" * 50)
    log.info("Bắt đầu quá trình nạp dữ liệu vào MySQL...")

    # ── Pipeline Safety: file clean phải tồn tại ──
    if not os.path.exists(CLEAN_FILE):
        msg = f"Không tìm thấy: {CLEAN_FILE}. Hãy chạy Module 1 (Clean Data) trước!"
        log.error(msg)
        return {"success": False, "message": msg, "stats": {}}

    conn   = None
    cursor = None

    success_count   = 0
    not_found_count = 0
    error_count     = 0
    skipped_count   = 0

    try:
        conn   = get_connection()
        cursor = conn.cursor()
        log.info("Kết nối MySQL thành công.")

        with open(CLEAN_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            for row in reader:
                try:
                    product_id = int(row['product_id'])
                    quantity   = int(row['quantity'])

                    # ── Validation ──
                    if product_id <= 0 or quantity < 0:
                        log.warning(f"Bỏ qua dòng không hợp lệ: {row}")
                        skipped_count += 1
                        continue

                    # ── IDEMPOTENT UPDATE ──
                    cursor.execute(
                        "UPDATE products SET stock = %s WHERE id = %s",
                        (quantity, product_id)
                    )

                    if cursor.rowcount == 0:
                        log.warning(f"product_id={product_id} không tồn tại trong DB.")
                        not_found_count += 1
                    else:
                        success_count += 1

                except (ValueError, KeyError) as e:
                    log.warning(f"Dòng không hợp lệ: {row} – {e}")
                    error_count += 1
                except Exception as e:
                    log.error(f"Lỗi SQL dòng {row}: {e}", exc_info=True)
                    error_count += 1

        # ── Transaction commit ──
        conn.commit()
        log.info("✔ Commit transaction thành công.")

    except Exception as e:
        msg = f"Lỗi kết nối hoặc SQL: {e}"
        log.error(msg, exc_info=True)
        if conn:
            try:
                conn.rollback()
                log.warning("Đã rollback transaction.")
            except Exception:
                pass
        return {"success": False, "message": msg, "stats": {}}

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
            log.info("Đã đóng kết nối MySQL.")

    stats = {
        "updated":   success_count,
        "not_found": not_found_count,
        "skipped":   skipped_count + error_count,
    }
    log.info(f"✔ Import hoàn tất! Stats: {stats}")
    log.info("=" * 50)

    return {
        "success": True,
        "message": f"Import thành công! Đã cập nhật {success_count} sản phẩm.",
        "stats": stats,
    }