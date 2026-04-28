"""
adapter.py – Module 1: Legacy Adapter (CSV → MySQL Polling)

Chức năng:
- Polling thư mục /app/input mỗi POLL_INTERVAL giây
- Validate dữ liệu: bỏ qua quantity < 0 hoặc dòng sai định dạng
- UPDATE bảng products trong MySQL (không INSERT)
- Move file sang /app/processed sau khi xử lý xong
- Retry connection 5 lần khi MySQL chưa sẵn sàng
"""

import os
import csv
import time
import shutil
import logging
from datetime import datetime
import mysql.connector
from mysql.connector import Error

# ─── Cấu hình Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("legacy_adapter")

# ─── Cấu hình từ Environment Variables ────────────────────────────
MYSQL_HOST     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT     = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DB       = os.getenv("MYSQL_DB", "noah_store")
MYSQL_USER     = os.getenv("MYSQL_USER", "noah")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "noah123")
POLL_INTERVAL  = int(os.getenv("POLL_INTERVAL", "10"))

INPUT_DIR     = "/app/input"
PROCESSED_DIR = "/app/processed"


# ─── Hàm Retry Connection ─────────────────────────────────────────
def retry_connection(max_retries: int = 5, delay: int = 5):
    """
    Thử kết nối MySQL tối đa max_retries lần.
    Nếu thất bại vẫn sau đó raise exception.
    """
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                database=MYSQL_DB,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                connection_timeout=10
            )
            log.info(f"Kết nối MySQL thành công (lần {attempt}).")
            return conn
        except Error as e:
            last_err = e
            log.warning(
                f"Kết nối MySQL thất bại ({attempt}/{max_retries}): {e}. "
                f"Thử lại sau {delay}s..."
            )
            if attempt < max_retries:
                time.sleep(delay)
    log.error(f"Không thể kết nối MySQL sau {max_retries} lần thử.")
    raise last_err


# ─── Xử lý 1 File CSV ─────────────────────────────────────────────
def process_csv(filepath: str) -> dict:
    """
    Đọc file CSV, validate, update MySQL products.stock, move file.

    Returns:
        dict: {"processed": int, "skipped": int, "not_found": int}
    """
    processed  = 0
    skipped    = 0
    not_found  = 0

    log.info(f"{'='*55}")
    log.info(f"Đang xử lý file: {os.path.basename(filepath)}")

    conn   = None
    cursor = None

    try:
        conn   = retry_connection()
        cursor = conn.cursor()

        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # ── Kiểm tra header ──
            if not reader.fieldnames or \
               'product_id' not in reader.fieldnames or \
               'quantity'   not in reader.fieldnames:
                log.error("File CSV thiếu cột 'product_id' hoặc 'quantity'. Bỏ qua.")
                return {"processed": 0, "skipped": 0, "not_found": 0}

            for lineno, row in enumerate(reader, start=2):
                try:
                    pid_raw = row.get('product_id', '').strip()
                    qty_raw = row.get('quantity', '').strip()

                    # ── Validate: thiếu dữ liệu ──
                    if not pid_raw or not qty_raw:
                        log.warning(f"  [Dòng {lineno}] Thiếu dữ liệu: {dict(row)} → Bỏ qua.")
                        skipped += 1
                        continue

                    product_id = int(pid_raw)
                    quantity   = int(qty_raw)

                    # ── Validate: ID âm ──
                    if product_id <= 0:
                        log.warning(f"  [Dòng {lineno}] product_id={product_id} không hợp lệ → Bỏ qua.")
                        skipped += 1
                        continue

                    # ── Validate: Số lượng âm ──
                    if quantity < 0:
                        log.warning(f"  [Dòng {lineno}] quantity={quantity} âm → Bỏ qua.")
                        skipped += 1
                        continue

                    # ── UPDATE MySQL ──
                    cursor.execute(
                        "UPDATE products SET stock = %s WHERE id = %s",
                        (quantity, product_id)
                    )

                    if cursor.rowcount == 0:
                        log.warning(f"  [Dòng {lineno}] product_id={product_id} không tồn tại trong DB.")
                        not_found += 1
                    else:
                        processed += 1

                except (ValueError, KeyError) as e:
                    log.warning(f"  [Dòng {lineno}] Sai định dạng: {dict(row)} – {e} → Bỏ qua.")
                    skipped += 1
                except Exception as e:
                    log.error(f"  [Dòng {lineno}] Lỗi SQL: {e} → Bỏ qua dòng này.")
                    skipped += 1

        conn.commit()
        log.info("✔ Commit transaction thành công.")

    except Exception as e:
        log.error(f"Lỗi kết nối hoặc đọc file: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"processed": 0, "skipped": 0, "not_found": 0}

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    # ── Cleanup: Move file sang /processed ──────────────────────────
    try:
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_name = f"inventory_{ts}.csv"
        dest_path = os.path.join(PROCESSED_DIR, dest_name)
        shutil.move(filepath, dest_path)
        log.info(f"✔ Đã di chuyển file → {dest_name}")
    except Exception as e:
        log.error(f"Lỗi khi di chuyển file: {e}")

    log.info(
        f"[INFO] Processed {processed} records. "
        f"Skipped {skipped + not_found} invalid records."
    )
    return {"processed": processed, "skipped": skipped, "not_found": not_found}


# ─── Vòng Lặp Polling Chính ───────────────────────────────────────
def main():
    log.info("=" * 55)
    log.info(" NOAH RETAIL – LEGACY ADAPTER ĐÃ KHỞI ĐỘNG")
    log.info(f" Thư mục input   : {INPUT_DIR}")
    log.info(f" Thư mục output  : {PROCESSED_DIR}")
    log.info(f" Chu kỳ polling  : {POLL_INTERVAL} giây")
    log.info("=" * 55)

    os.makedirs(INPUT_DIR,     exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # ── Chờ MySQL sẵn sàng trước khi bắt đầu poll ──
    log.info("Đang chờ MySQL sẵn sàng...")
    while True:
        try:
            conn = retry_connection(max_retries=3, delay=5)
            conn.close()
            break
        except Exception:
            log.warning("MySQL chưa sẵn sàng, thử lại sau 10s...")
            time.sleep(10)

    log.info("MySQL đã sẵn sàng. Bắt đầu polling...")

    while True:
        try:
            target = os.path.join(INPUT_DIR, "inventory.csv")

            if os.path.isfile(target):
                process_csv(target)
            else:
                log.debug(f"Không có file mới trong {INPUT_DIR}. Chờ...")

        except Exception as e:
            log.error(f"Lỗi polling: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
