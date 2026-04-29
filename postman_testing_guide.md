# Hướng Dẫn Test Hệ Thống Microservices (Docker) bằng Postman & cURL

Hệ thống hiện tại đã chuyển sang kiến trúc Microservices chạy trên Docker Compose, được bảo mật bởi **Kong Gateway**. Tất cả các request phải đi qua port **8000** và kèm theo Header `apikey`.

---

## 🔑 Thông Tin Kết Nối Chung

| Thành phần | Giá trị |
|---|---|
| **Base URL** | `http://localhost:8000` |
| **API Key Header** | `apikey: noah-secret-key` |
| **Dashboard UI** | `http://localhost:8000/Dashboard.html` |
| **RabbitMQ UI** | `http://localhost:15672` (u: guest, p: guest) |

---

## 1. Test Module 1: Legacy Adapter (CSV Sync)

Không có API trực tiếp, bạn test bằng cách thả file:
1. Mở folder dự án, vào thư mục `input/`.
2. Tạo file `inventory.csv` hoặc dùng script `python admin_data_generator.py --mode csv`.
3. Quan sát log: `docker logs noah_legacy_adapter -f`.
4. Sau 10s, file sẽ bị di chuyển sang `processed/` và MySQL products sẽ được cập nhật.

---

## 2. Test Module 2: Order Pipeline (FastAPI + MQ)

### 2.1. Kiểm tra tồn kho (Stock Check)
**Endpoint:** `GET /report/api/products?page=1&limit=5`  
**cURL:**
```bash
curl -X GET "http://localhost:8000/report/api/products?page=1&limit=5" -H "apikey: noah-secret-key"
```

### 2.2. Đặt hàng thành công (Happy Path)
**Endpoint:** `POST /orders/api/orders`  
**JSON Body:**
```json
{
  "user_id": 42,
  "product_id": 105,
  "quantity": 2
}
```
**cURL:**
```bash
curl -X POST http://localhost:8000/orders/api/orders \
  -H "apikey: noah-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 42, "product_id": 105, "quantity": 2}'
```
**Kết quả:** Nhận `202 Accepted`. Sau 2-3s, kiểm tra Dashboard sẽ thấy status chuyển từ `PENDING` sang `COMPLETED`.

### 2.3. Test Stock Check (Lỗi không đủ hàng)
Thử đặt số lượng cực lớn (ví dụ 999999) để nhận lỗi `400 Bad Request`.

---

## 3. Test Module 3: Report Service (Data Stitching)

### 3.1. Báo cáo đối soát (MySQL + Postgres Join)
**Endpoint:** `GET /report/api/report?page=1`  
**cURL:**
```bash
curl -X GET "http://localhost:8000/report/api/report" -H "apikey: noah-secret-key"
```
**Mô tả:** Trả về danh sách đơn hàng từ MySQL kèm cột `synced` (xác nhận đã có transaction tương ứng bên PostgreSQL).

---

## 4. Test Module 4: Security (Kong Gateway)

### 4.1. Sai API Key
Thử bỏ header `apikey` hoặc nhập sai:
```bash
curl -I http://localhost:8000/report/api/stats
```
**Kết quả:** `401 Unauthorized`.

### 4.2. Rate Limiting
Gửi liên tục 11 request trong 1 phút vào endpoint `/orders`.
**Kết quả:** Request thứ 11 nhận `429 Too Many Requests`.

---

## 5. Test Module 10/10 (Advanced Features)

### 5.1. Dead Letter Queue (DLQ)
Nếu bạn cố tình làm Worker lỗi (ví dụ: tắt container Postgres), message sẽ retry 3 lần rồi được đẩy vào queue `order_queue_dlq`.
Kiểm tra tại RabbitMQ UI: `http://localhost:15672/#/queues`.

### 5.2. Async Notification
Kiểm tra log của Worker khi xử lý đơn hàng thành công:
`docker logs noah_order_worker -f`
Bạn sẽ thấy dòng `[THÔNG BÁO TỚI KHÁCH HÀNG]` xuất hiện sau khi order đã xong.
