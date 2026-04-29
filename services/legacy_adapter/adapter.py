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
    Đọc file CSV, validate, deduplicate, batch update MySQL products.stock, move file.

    Cải tiến:
    - Duplicate handling: nếu CSV có nhiều dòng cùng product_id → last-write-wins
    - Batch UPDATE: gom tất cả update hợp lệ → executemany 1 lần commit

    Returns:
        dict: {"processed": int, "skipped": int, "not_found": int, "duplicates": int}
    """
    processed  = 0
    skipped    = 0
    not_found  = 0
    duplicates = 0

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
                return {"processed": 0, "skipped": 0, "not_found": 0, "duplicates": 0}

            # ── Phase 1: Validate + Deduplicate (last-write-wins) ──
            valid_updates = {}   # product_id → quantity (giữ giá trị cuối)
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

                    # ── Duplicate check: nếu đã có → đếm duplicate, ghi đè ──
                    if product_id in valid_updates:
                        duplicates += 1
                        log.info(f"  [Dòng {lineno}] Duplicate product_id={product_id} → Ghi đè (last-write-wins).")

                    valid_updates[product_id] = quantity

                except (ValueError, KeyError) as e:
                    log.warning(f"  [Dòng {lineno}] Sai định dạng: {dict(row)} – {e} → Bỏ qua.")
                    skipped += 1

        if not valid_updates:
            log.info("Không có dữ liệu hợp lệ để cập nhật.")
            return {"processed": 0, "skipped": skipped, "not_found": 0, "duplicates": duplicates}

        log.info(f"  Deduplicated: {len(valid_updates)} unique products (bỏ {duplicates} dòng trùng).")

        # ── Phase 2: Batch UPDATE bằng executemany ──
        batch_data = [(qty, pid) for pid, qty in valid_updates.items()]
        cursor.executemany(
            "UPDATE products SET stock = %s WHERE id = %s",
            batch_data
        )

        # Đếm kết quả: kiểm tra từng product_id có tồn tại không
        for pid in valid_updates:
            cursor.execute("SELECT id FROM products WHERE id = %s", (pid,))
            if cursor.fetchone():
                processed += 1
            else:
                not_found += 1
                log.warning(f"  product_id={pid} không tồn tại trong DB → Bỏ qua.")

        conn.commit()
        log.info("✔ Batch commit transaction thành công.")

    except Exception as e:
        log.error(f"Lỗi kết nối hoặc đọc file: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"processed": 0, "skipped": 0, "not_found": 0, "duplicates": 0}

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
        f"[INFO] Processed {processed} records, "
        f"Skipped {skipped} invalid, Not found {not_found}, "
        f"Duplicates merged {duplicates}."
    )
    return {"processed": processed, "skipped": skipped, "not_found": not_found, "duplicates": duplicates}


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
