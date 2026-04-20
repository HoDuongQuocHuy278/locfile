import csv
from src.db_connection import get_connection


def import_data():
    file_path = "data/processed/clean_inventory.csv"

    conn = None
    cursor = None

    success_count = 0
    error_count = 0
    not_found_count = 0

    try:
        # Kết nối DB
        conn = get_connection()
        cursor = conn.cursor()

        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            for row in reader:
                try:
                    product_id = int(row['product_id'])
                    quantity = int(row['quantity'])

                    # Update stock
                    query = """
                        UPDATE products
                        SET stock = stock + %s
                        WHERE id = %s
                    """
                    cursor.execute(query, (quantity, product_id))

                    # Kiểm tra có product tồn tại không
                    if cursor.rowcount == 0:
                        not_found_count += 1
                    else:
                        success_count += 1

                except Exception as e:
                    error_count += 1
                    print(f"⚠ Lỗi dòng: {row} - Cụ thể: {e}")
                    continue

        conn.commit()

        print("✔ Import vào DB thành công!")
        print(f"✔ Updated: {success_count} sản phẩm")
        print(f"⚠ Không tồn tại trong DB: {not_found_count}")
        print(f"❌ Lỗi dòng: {error_count}")

    except FileNotFoundError:
        print("❌ Không tìm thấy file clean_inventory.csv")

    except Exception as e:
        print("❌ Lỗi kết nối hoặc SQL:", e)

    finally:
        # Đóng kết nối an toàn
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()