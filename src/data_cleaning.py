"""
data_cleaning.py – Module 1: Làm sạch dữ liệu tồn kho.

Chiến lược lỗi của nhóm 7: DUPLICATES
- Các dòng có cùng product_id được cộng dồn quantity.
- Validation: bỏ qua dòng có quantity < 0 hoặc product_id <= 0.
- Trả về dict để Flask API gọi trực tiếp.
"""

import csv
import os
from src.logger import get_logger

log = get_logger("data_cleaning")

INPUT_FILE  = "data/raw/inventory.csv"
OUTPUT_FILE = "data/processed/clean_inventory.csv"


def clean_data() -> dict:
    """
    Đọc inventory.csv, xử lý DUPLICATES, kiểm tra dữ liệu hợp lệ,
    ghi ra clean_inventory.csv.

    Returns:
        dict: {"success": bool, "message": str, "stats": {...}}
    """
    log.info("=" * 50)
    log.info("Bắt đầu quá trình làm sạch dữ liệu...")

    if not os.path.exists(INPUT_FILE):
        msg = f"Không tìm thấy file đầu vào: {INPUT_FILE}"
        log.error(msg)
        return {"success": False, "message": msg, "stats": {}}

    inventory  = {}
    skipped    = 0
    total_rows = 0

    try:
        with open(INPUT_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames or \
               'product_id' not in reader.fieldnames or \
               'quantity'   not in reader.fieldnames:
                msg = "File CSV thiếu cột 'product_id' hoặc 'quantity'."
                log.error(msg)
                return {"success": False, "message": msg, "stats": {}}

            for row in reader:
                total_rows += 1
                try:
                    product_id = int(row['product_id'].strip())
                    quantity   = int(row['quantity'].strip())

                    if product_id <= 0:
                        raise ValueError(f"product_id không hợp lệ: {product_id}")
                    if quantity < 0:
                        raise ValueError(f"quantity âm: {quantity}")

                    # ── Xử lý DUPLICATES: cộng dồn ──
                    inventory[product_id] = inventory.get(product_id, 0) + quantity

                except (ValueError, KeyError) as e:
                    skipped += 1
                    log.warning(f"Bỏ qua dòng #{total_rows}: {dict(row)} – {e}")

    except Exception as e:
        msg = f"Lỗi khi đọc CSV: {e}"
        log.error(msg, exc_info=True)
        return {"success": False, "message": msg, "stats": {}}

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    try:
        with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["product_id", "quantity"])
            for pid, qty in sorted(inventory.items()):
                writer.writerow([pid, qty])
    except Exception as e:
        msg = f"Lỗi khi ghi file output: {e}"
        log.error(msg, exc_info=True)
        return {"success": False, "message": msg, "stats": {}}

    stats = {
        "total_rows":     total_rows,
        "unique_products": len(inventory),
        "skipped":        skipped,
    }
    msg = f"Làm sạch thành công! {len(inventory)} sản phẩm, bỏ qua {skipped} dòng lỗi."
    log.info(f"✔ {msg} | Stats: {stats}")
    log.info("=" * 50)

    return {"success": True, "message": msg, "stats": stats}