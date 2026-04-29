# NOAH Retail – Unified Commerce System
## Nhóm 7 · CMU-CS 445 System Integration Practices

---

## 🏗️ Kiến Trúc Hệ Thống

```
Legacy CSV → [Legacy Adapter] → MySQL (products, orders)
                                      ↓
Client → Kong Gateway → [Order API] → RabbitMQ → [Order Worker] → PostgreSQL
           │                                                            ↓
Dashboard ←┘ ← [Report Service] (Data Stitching: MySQL + PostgreSQL)
(Nginx Frontend)
```

## 🚀 Khởi Động Nhanh

```bash
# 1. Khởi động toàn bộ hệ thống
docker-compose up --build -d

# 2. Kiểm tra tất cả services đang chạy
docker-compose ps

# 3. Chờ ~60s để MySQL/PostgreSQL khởi tạo, sau đó mở Dashboard
# http://localhost:8000/Dashboard.html  (qua Kong Gateway)
# http://localhost:15672 (RabbitMQ Management UI)
```

## 📁 Cấu Trúc Thư Mục

```
Đồ án nhóm 7/
├── docker-compose.yml          # Orchestration 8 services
├── .env                        # Environment variables
├── admin_data_generator.py     # Script sinh dữ liệu test
├── mysql/init_mysql.sql        # MySQL schema + 200 products + 200 orders
├── postgres/init_postgres.sql  # PostgreSQL schema
├── kong/kong.yml               # Kong Gateway config (Key Auth + Rate Limit)
├── input/                      # Thư mục input CSV (shared volume)
├── processed/                  # Thư mục output CSV sau xử lý
├── services/
│   ├── legacy_adapter/         # Module 1: CSV → MySQL (batch update)
│   ├── order_api/              # Module 2A: FastAPI Producer (atomic stock check)
│   ├── order_worker/           # Module 2B: RabbitMQ Consumer (DB retry + DLQ)
│   └── report_service/         # Module 3: Data Stitching API
└── giao diện/Dashboard.html    # Module 6: Web Dashboard (Served by Nginx)
```

## 🧪 Test Các Module

### Module 1 – Legacy Adapter (CSV Polling)
```bash
# Sinh file inventory.csv với 5% dữ liệu bẩn
python admin_data_generator.py --mode csv --count 200

# File tự động xuất hiện trong input/ → adapter phát hiện sau 10s
# Kiểm tra log:
docker logs noah_legacy_adapter -f
# Output: [INFO] Processed 190 records. Skipped 10 invalid records.
```


chạy web dashboard
http://localhost:8000/Dashboard.html

### Module 2 – Order Pipeline
```bash
# Test qua Kong Gateway (cần apikey header)
curl -X POST http://localhost:8000/orders/api/orders \
  -H "apikey: noah-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 42, "product_id": 101, "quantity": 2}'

# Response: {"message": "Order received", "order_id": 201, "status": "PENDING"}
# Sau 1-2s Worker xử lý → status chuyển sang COMPLETED
```

### Module 3 – Report (Data Stitching)
```bash
curl -X GET "http://localhost:8000/report/api/report?page=1&limit=20" \
  -H "apikey: noah-secret-key"
```

### Module 4 – Security (Kong)
```bash
# Không có apikey → 401 Unauthorized
curl -X GET http://localhost:8000/report/api/report

# Gửi 11 request liên tục → request thứ 11 nhận 429 Too Many Requests
```

## 🔑 API Endpoints (qua Kong :8000)

| Method | Path | Mô Tả |
|--------|------|--------|
| GET  | / | Proxy sang Nginx load UI frontend (giao diện) |
| POST | /orders/api/orders | Tạo đơn hàng mới (Kèm trừ stock) |
| GET  | /orders/api/orders | Danh sách đơn hàng |
| GET  | /report/api/report | Báo cáo đối soát |
| GET  | /report/api/products | Danh sách sản phẩm |
| GET  | /report/api/stats | Thống kê tổng hợp |

**Header bắt buộc (nếu gọi API):** `apikey: noah-secret-key`

## 🌐 Ports

| Service | Port | Mô Tả |
|---------|------|--------|
| Kong Proxy | 8000 | Public Gateway duy nhất |
| Kong Admin | 8001 | Admin API |
| RabbitMQ UI | 15672 | Management Console |

> ⚠️ MySQL (:3306) và PostgreSQL (:5432) KHÔNG được expose ra ngoài.

## 👥 Nhóm 7

Môn học: CMU-CS 445 System Integration Practices  
Đề tài: Xây dựng hệ thống "Unified Commerce" cho NOAH Retail
