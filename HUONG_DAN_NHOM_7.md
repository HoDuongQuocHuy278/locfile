# Hướng Dẫn Kỹ Thuật Đồ Án - Nhóm 7 (Chiến Lược: DUPLICATES)

Tài liệu này mô tả chi tiết ý nghĩa của các file, luồng chạy của hệ thống và giải thích cụ thể cách nhóm sử dụng `try-except` để xử lý dữ liệu dơ (Dirty Data), hoàn thiện Module 1.

---

## 1. Cấu Trúc File & Ý Nghĩa

Hệ thống được chia làm nhiều tệp tin (Module) khác nhau để dễ hình dung thành các giai đoạn độc lập:

- **`data/raw/inventory.csv`**: Dữ liệu thô bắt đầu của nhóm. File này chứa 5000 báo cáo tồn kho nhưng cố tình được chèn **Dirty Data** (những dòng thiếu ID, rỗng số lượng, chuỗi ký tự không hợp lệ `abc`, và các file `product_id` trùng lặp).
- **`data/sql/init.sql`**: Chứa hơn 20.000 dòng mã SQL dùng để thiết lập toàn bộ cơ sở dữ liệu (tạo bảng `products`, bảng `orders` và cắm sẵn dữ liệu mẫu). Bắt buộc phải import file này vào MySQL Server (Localhost) trước khi chạy code.
- **`setup_db.py`**: Mã lệnh Python đóng vai trò "Trợ lý khởi tạo DB" - tự động quét và load toàn bộ nội dung file `init.sql` lên `localhost` MySQL bằng `mysql.connector`. (Thay thế thao tác gõ vào phpMyAdmin bằng tay).
- **`src/data_cleaning.py` (Module 1)**: Trái tim của bài toán! Chịu trách nhiệm duyệt qua từng dòng của file CSV dơ. Bằng cách dùng chiến thuật bắt lỗi, nó vứt đi những dữ liệu dị thường, sau đó **cộng dồn `quantity`** của các dòng có cùng một ID (Chiến lược DUPLICATES), và lưu danh sách sản phẩm đã được tổng hợp ra file `clean_inventory.csv`.
- **`src/import_to_db.py` (Module 2)**: Nhiệm vụ đồng bộ hóa! File này đọc mảng dữ liệu đã sạch từ `clean_inventory.csv` và tạo lệnh UPDATE để chỉnh sửa `stock` trong DB `mydb`.
- **`main.py`**: Tổng tư lệnh. Gọi Module 1 chạy xong mới kích hoạt tiếp Module 2, đảm bảo toàn bộ quy trình đi từ Tệp Thô -> Tệp Sạch -> Database diễn ra mượt mà theo 1 cú click.

---

## 2. Quy Trình và Luồng Chạy (Execution Flow)

Luồng chạy của hệ thống đi qua **3 chốt chặn** chính:

### Bước 1: Khởi Tạo Database (SQL Setup)
- Chạy `python setup_db.py` (hoặc import manual) nhằm tạo Database `mydb` gốc. Nếu thiếu bước này, ở chặng cuối cùng sẽ bị lỗi: `Table 'mydb.products' doesn't exist` khiến import thất bại.
  
### Bước 2: Bắt Lỗi và Nhặt Rác (Module 1 Data Cleaning)
Khi chạy `main.py`, Module 1 lập tức khởi động:
1. Python mở từng dòng trong `inventory.csv`.
2. Đối với mỗi mẩu dữ liệu (cell), code ép kiểu bằng `int()`.
3. Nếu ký tự là rỗng (thiếu mã ID) hoặc chứa chữ ("abc"), Python không chuyển sang kiểu số `int` được, nó sẽ văng lỗi **ValueError** lập tức.
4. Nhờ khối **`try...except`** bọc xung quanh, lỗi này thay vì làm sập chương trình thì sẽ bị chặn lại. Hệ thống kích hoạt `error_count += 1` (đếm lỗi) và lặng lẽ `continue` lướt qua để nhảy sang dòng mới tinh tiếp theo. Nhờ logic này, **387 dòng dơ đã lọt lưới nhặt rác hoàn hảo**.
5. Đối với những ID hợp lệ, nó gộp bằng code `inventory[product_id] += quantity` nếu phát hiện có sự trùng nhau trước đó.
6. Kết quả xuất hiện **200 ID** còn sống sót, được ghi vào file sạch hoàn thiện `clean_inventory.csv`.

### Bước 3: Đồng Bộ Hóa Dữ Liệu Lên Doanh Nghiệp (Module 2 Import)
Xong bước 2, `main.py` sẽ đẩy cờ khởi chạy Module 2:
1. Python đọc lần lượt từng dòng từ `clean_inventory.csv` (dữ liệu bây giờ đã là ID số chuẩn chỉ).
2. Xây dựng câu truy vấn SQL an toàn cho từng nhóm ID: `UPDATE products SET stock = stock + (số_lượng_gộp) WHERE id = (id_chuẩn)`.
3. Thông báo `Updated: 200 sản phẩm` cho 200 vòng lặp cập nhật database. System báo Cập Nhật Khớp Dữ Liệu Hoàn Chỉnh!

---

## 3. Cách Mở Chạy Lại Trên Máy Mới (Demo)

Thuyết trình nhanh trong 2 bước demo:

```bash
# 1. Khởi tạo DB để có CSDL mydb chuẩn
python setup_db.py
```

```bash
# 2. Chạy luồng quét dọn sạch -> load lên Web Server
python main.py
```

> Trong file `main.py`, nhóm đã chủ động chèn thêm thư viện giới hạn `import sys; sys.stdout.reconfigure(encoding='utf-8')`. Dòng này giúp Terminal trên Windows đọc hiểu được các Emoji chữ báo trạng thái như (✔ hay ⚠) tránh triệt để tình trạng sập Terminal và loạn dấu ký tự bảng mã Tiếng Việt lúc Demo cho giáo viên.

---

## 4. Báo Cáo Kết Quả & Trình Bày Chứng Thực

Khi toàn bộ đoạn code chạy thành công, kết quả bạn thu lại và bằng chứng để **chứng thực (verify)** bảo vệ trước giáo viên như sau:

#### A. Kết quả nhận được ngay lập tức:
- **Terminal (Console)** sẽ in trực tiếp báo cáo gồm 4 dòng:
  1. `✔ Clean thành công! Tổng sản phẩm: 200`
  2. `⚠ Bỏ qua 387 dòng lỗi`
  3. `✔ Import vào DB thành công!`
  4. `✔ Updated: 200 sản phẩm` (Và 0 lỗi).
- **Thư mục mới `data/processed/clean_inventory.csv`** sẽ được tạo ra trên ổ cứng và chứa 201 dòng (1 dòng tiêu đề + 200 ID hàng).

#### B. Cách chứng thực (thuyết trình / test thử):
1. **Minh chứng 1 (Bắt lỗi Missing Data):**
   Mở file `data/raw/inventory.csv`, chỉ cho giáo viên dòng số `9` (Nội dung: `,399`). Explain: "Dòng này không có mã ID". Mở tệp đầu ra `data/processed/clean_inventory.csv` rà soát, không hề có sản phẩm nào ghi khống ID, minh chứng Code đã chặn (try-except) lỗi dữ liệu rỗng xuất sắc.
2. **Minh chứng 2 (Gộp DUPLICATES):**
   Trong raw csv, dòng `2` đang chứa dữ liệu `275,467` và dòng `28` chứa dữ liệu `275,484`. Khi mở file `clean_inventory.csv` tại ID `275`, giá trị chốt hạ phải lớn hơn `951` do được gộp nhiều lần. Minh chứng thuật toán gộp nhóm thành công.
3. **Minh chứng cuối (Thực tế Database):**
   Truy cập vào công cụ MySQL (hoặc phpMyAdmin) gõ lệnh: `SELECT * FROM mydb.products WHERE id = 275;`.
   Cột **`stock`** của nó giờ đã được đổ đầy (không còn là `0`) tương ứng trọn vẹn với file CSV sạch. Chứng minh kết nối Python ➝ MySQL hoạt động thực tế.

---

## 5. Sơ Đồ Luồng Hệ Thống (Flowchart) & Ghi Chú Code Chính

Để dễ hình dung quá trình tương tác, dưới đây là sơ đồ luồng hệ thống (Flow) cho phép nhìn thấy hướng đi của dữ liệu từ file thô CSV cho đến khi vào Tận Database.

```mermaid
graph TD
    A([main.py Bắt Đầu]) --> B[Hàm clean_data - Module 1]
    B --> C[Mở 'raw/inventory.csv']
    C --> D[Khối lệnh Try-Except: Duyệt từng dòng]
    D --> E{Dữ liệu rỗng / Ký tự lạ?}
    
    E -- Có lỗi --> F[Bắt lệnh ValueError]
    F --> F2[Tăng đếm lỗi <code>error_count += 1</code>]
    F2 -.-> I
    
    E -- Sạch, Hợp lệ --> G{Kiểm tra ID trong kho}
    G -- Bị Trùng (Duplicate) --> H1[Cộng dồn <code>inventory[ID] += số_lượng</code>]
    G -- Mới hoàn toàn --> H2[Thêm mới <code>inventory[ID] = số_lượng</code>]
    
    H1 --> I{Duyệt hết file?}
    H2 --> I
    
    I -- Chưa hết -.-> D
    I -- Đã duyệt xong --> J[Ghi dữ liệu sạch ra 'clean_inventory.csv']
    
    J --> K[Hàm import_data - Module 2]
    K --> L[(Cơ sở dữ liệu MySQL <code>mydb</code>)]
    L --> M[Đọc 'clean_inventory.csv']
    M --> N[Chạy SQL UPDATE stock...]
    N --> O([Kết Thúc Cập Nhật])
```

### Chú Giải Các Dòng Code Chính Phải Nhớ Trong Báo Cáo

#### Trong `src/data_cleaning.py` (Mô-đun Khử Rác)
Đoạn code "ăn tiền" nhất nhóm bạn cần giải thích là khối try-except:

```python
for row in reader:
    try:
        # 1. ÉP KIỂU NGHIÊM NGẶT - BẪY LỖI
        # int() cố dịch dữ liệu từ csv sang số. Nếu gặp khoảng trắng (thiếu giá trị) 
        # hoặc gặp chữ ("abc") -> Python sẽ văng lập tức lỗi ValueError do không hiểu!
        product_id = int(row['product_id'].strip())
        quantity = int(row['quantity'].strip())

        # 2. XỬ LÝ MÃ LỖI DUPLICATES: NẾU THUẬT TOÁN ĐÃ ĐI ĐƯỢC TỚI DÒNG NÀY (HỢP LỆ)
        if product_id in inventory:
            inventory[product_id] += quantity # Gộp lượng tồn kho cho các ID lặp lại.
        else:
            inventory[product_id] = quantity

    except Exception:
        # 3. HỨNG LỖI VÀ ĐẾM SỐ LƯỢNG
        # Toàn bộ ValueErrors văng ra ở bước ép kiểu phía trên sẽ bị lưới except này chặn lại.
        # Ngăn chương trình bị sập, hệ thống ghi nhận 'Thêm 1 lỗi rác' và bỏ qua dòng này.
        error_count += 1
        continue
```

#### Trong `src/import_to_db.py` (Mô-đun Nạp SQL)
Câu lệnh chốt chặng cuối nạp lại hệ thống MySQL:

```python
# CẬP NHẬT GỘP TỒN KHO LÊN HỆ THỐNG MYSQL
query = """
    UPDATE products
    SET stock = stock + %s
    WHERE id = %s
"""
# Đẩy số lượng thực tế (%s đầu tiên) và ID tương ứng (%s thứ 2) vào câu truy vấn.
cursor.execute(query, (quantity, product_id))
```
