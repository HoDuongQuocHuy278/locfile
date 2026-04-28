# Hướng Dẫn Test Hệ Thống API bằng Postman & cURL

Trong bản cập nhật Flask API mới nhất, hệ thống đã cung cấp 5 endpoints RESTful hoàn chỉnh trả về chuẩn JSON.

Dưới đây là tài liệu để bạn dễ dàng test thông qua Postman hoặc sử dụng lệnh cURL trực tiếp trên Terminal.

## 1. Cách dùng qua Postman (Tự động)

Hệ thống đã chuẩn bị sẵn file Collection để bạn import trực tiếp vào Postman:
1. Mở ứng dụng Postman.
2. Nhấn nút **Import** (hoặc nhấn Ctrl+O / Cmd+O).
3. Chọn thẻ **File** hoặc **Raw text**, kéo thả file `postman_collection.json` nằm trong thư mục gốc dự án.
4. Bạn sẽ thấy collection **"ETL Inventory System API - Nhóm 7"** xuất hiện. Bấm "Send" để test từng API.

---

## 2. Danh Sách Endpoint & Lệnh cURL (Test thủ công)

Bạn cũng có thể mở Terminal / Command Prompt và copy trực tiếp các lệnh cURL sau để kiểm tra:

### 2.1. Kiểm Tra Trạng Thái Server
**Endpoint:** `GET /status`
**Mô tả:** Kiểm tra hệ thống có đang hoạt động không và pipeline ở bước nào (setup_done, clean_done).

**cURL:**
```bash
curl -X GET http://localhost:8000/status
```

**Kết quả mong đợi:**
```json
{
  "pipeline": {
    "clean_done": false,
    "setup_done": false
  },
  "status": "running"
}
```

---

### 2.2. Khởi Tạo / Reset Database (Cần chạy đầu tiên)
**Endpoint:** `POST /setup`
**Mô tả:** Xóa và tạo lại Database `mydb`, nạp dữ liệu mẫu ban đầu.

**cURL:**
```bash
curl -X POST http://localhost:8000/setup
```

**Kết quả mong đợi (thành công):**
```json
{
  "message": "Khởi tạo CSDL thành công! (9 câu lệnh)",
  "stats": {"executed": 9, "failed": 0},
  "status": "success"
}
```

---

### 2.3. Làm Sạch Dữ Liệu (Module 1)
**Endpoint:** `POST /clean`
**Mô tả:** Đọc `inventory.csv`, xử lý lỗi DUPLICATE, sinh ra `clean_inventory.csv`. 

**cURL:**
```bash
curl -X POST http://localhost:8000/clean
```

**Kết quả mong đợi:**
```json
{
  "message": "Làm sạch thành công! 4850 sản phẩm, bỏ qua 150 dòng lỗi.",
  "stats": {
    "skipped": 150,
    "total_rows": 5000,
    "unique_products": 4850
  },
  "status": "success"
}
```

---

### 2.4. Nạp Dữ Liệu Lên MySQL (Module 2)
**Endpoint:** `POST /import`
**Mô tả:** Đọc `clean_inventory.csv` cập nhật MySQL.  
⚠️ **Rằng buộc (Guard):** Nếu chưa gọi `/clean`, API này sẽ từ chối truy cập (Workflow rule).

**cURL (thử ngay khi chưa chạy /clean để thấy lỗi 400):**
```bash
curl -X POST http://localhost:8000/import
```
**Kết quả mong đợi (Lỗi Workflow):**
```json
{
  "message": "Hãy chạy /clean trước khi nạp dữ liệu vào database.",
  "status": "error"
}
```

**Kết quả mong đợi (Sau khi chạy /clean thành công):**
```json
{
  "message": "Import thành công! Đã cập nhật 4850 sản phẩm.",
  "stats": {
    "not_found": 0,
    "skipped": 0,
    "updated": 4850
  },
  "status": "success"
}
```

---

### 2.5. Truy Vấn Top 20 Sản Phẩm Tồn Kho
**Endpoint:** `GET /products`
**Mô tả:** Lấy danh sách Top 20 sản phẩm có Stock lớn nhất.  
⚠️ **Rằng buộc (Guard):** Cần đảm bảo `/setup` ít nhất đã chạy 1 lần.

**cURL:**
```bash
curl -X GET http://localhost:8000/products
```

**Kết quả mong đợi:**
```json
{
  "count": 20,
  "data": [
    {
      "id": 1004,
      "name": "Sản phẩm A",
      "price": 25000.0,
      "stock": 5000
    },
    ...
  ],
  "status": "success"
}
```
