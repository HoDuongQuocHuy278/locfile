import csv
import os

def clean_data():
    input_file = "data/raw/inventory.csv"
    output_file = "data/processed/clean_inventory.csv"

    inventory = {}
    error_count = 0

    try:
        with open(input_file, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            for row in reader:
                try:
                    product_id = int(row['product_id'].strip())
                    quantity = int(row['quantity'].strip())

                    # Xử lý duplicate
                    if product_id in inventory:
                        inventory[product_id] += quantity
                    else:
                        inventory[product_id] = quantity

                except Exception:
                    error_count += 1
                    continue

        # Tạo thư mục nếu chưa có
        os.makedirs("data/processed", exist_ok=True)

        # Ghi file clean
        with open(output_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["product_id", "quantity"])

            for pid, qty in inventory.items():
                writer.writerow([pid, qty])

        print(f"✔ Clean thành công! Tổng sản phẩm: {len(inventory)}")
        print(f"⚠ Bỏ qua {error_count} dòng lỗi")

    except FileNotFoundError:
        print("❌ Không tìm thấy inventory.csv")