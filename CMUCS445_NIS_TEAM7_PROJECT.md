# NOAH PROJECT – Unified Commerce System

> **CMU-CS 445 INTEGRATION PRACTICE**  
> **International School – NIS**  
> **Version 1.2 | Date: May 1, 2026**

---

## Document Information

| Field | Value |
|---|---|
| **Title** | GROUP Project Document |
| **Author(s)** | Team 7 |
| **Date** | April 4th, 2026 |
| **File** | `CMUCS445_NIS_TEAM7_PROJECT.doc` |

## Revision History

| Version | Date | Comments | Author |
|---|---|---|---|
| 1.0 | April 4, 2026 | Initial Document | Team |
| 1.1 | April 4, 2026 | Business Context | Team |
| 1.2 | May 1, 2026 | Full Technical Document | Team |

## Team Member & Task Assignment

| Member | Student ID | Name | Task (Module) | Document | Tel |
|---|---|---|---|---|---|
| 1 | 29219051113 | Bao, Cao Dinh | Module 1: Legacy Adapter | Docker, DB Diagram | 0328942713 |
| 2 | 29219020704 | Hoang, Vo Duy | Module 3: Dashboard & Report | UI Mockup | 0796506825 |
| 3 | 29219036559 | Huy, Ho Duong Quoc | Module 2: Order Pipeline | Component Diagram | 0775999005 |
| 4 | 29219020597 | Thien, Pham Hai | Module 4: Security Gateway | Deployment Diagram | 0868010105 |

---

## Table of Contents

1. [Requirements Analysis](#1-requirements-analysis)
2. [Architecture Design](#2-architecture-design)
3. [Integration Strategies](#3-integration-strategies)
4. [Data & UI Design](#4-data--ui-design)
5. [Integration Testing](#5-integration-testing)
6. [Conclusion](#6-conclusion)
7. [References](#7-references)

---

# 1. REQUIREMENTS ANALYSIS

## 1.1. Business Context

NOAH Retail là chuỗi bán lẻ điện tử tầm trung tại Miền Trung, khởi nghiệp từ năm 2010. Sau 15 năm phát triển, NOAH sở hữu 5 cửa hàng vật lý và 1 kênh bán hàng Online. Hạ tầng CNTT phát triển "chắp vá", mỗi bộ phận mua phần mềm riêng lẻ, tạo ra **"Ốc đảo dữ liệu" (Data Silos)**.

### Các hệ thống thành phần và vấn đề hiện tại:

**Legacy Warehouse (Hệ thống Kho – AS/400):**
- Không có API hiện đại
- Chỉ xuất được file CSV (`inventory.csv`) vào lúc 3h sáng
- Dữ liệu chứa ~5% lỗi: trùng lặp (duplicate), số lượng âm, ký tự không hợp lệ
- Không kết nối trực tiếp được với database

**Web Store (MySQL):**
- Website bán hàng hiện đại
- Không kết nối với Kho → bán lố hàng (Overselling) vì không biết tồn kho thực tế
- Dữ liệu lưu 2 bảng chính: `products` (200 sản phẩm) và `orders` (200+ đơn hàng mẫu)

**Finance (PostgreSQL):**
- Hệ thống tài chính mới chuyển đổi
- Nhân viên nhập liệu thủ công đơn hàng từ Web sang → chậm trễ, sai sót
- Đối soát dữ liệu giữa 2 hệ thống khó khăn

## 1.2. User Story & Feature

**Mục tiêu chính:** Xây dựng hệ thống Middleware tự động hóa dòng chảy dữ liệu giữa 3 hệ thống, loại bỏ "khoảng cách dữ liệu" giữa online và offline.

### Các tính năng tích hợp chính:

| Feature | Mô tả | Luồng dữ liệu |
|---|---|---|
| **Inventory Sync** | Đồng bộ tồn kho từ Legacy CSV → MySQL | `CSV → Legacy Adapter → MySQL (products.stock)` |
| **Order Processing** | Xử lý đơn hàng bất đồng bộ qua Message Queue | `API → MySQL (PENDING) → RabbitMQ → Worker → PostgreSQL + MySQL (COMPLETED)` |
| **Reconciliation Report** | Đối soát dữ liệu giữa bán hàng và tài chính | `MySQL (orders) + PostgreSQL (transactions) → Data Stitching → JSON` |

### Acceptance Criteria:

1. ✅ Hệ thống chạy hoàn chỉnh bằng `docker-compose up`
2. ✅ File CSV được tự động quét, làm sạch, và cập nhật MySQL (không crash khi gặp dữ liệu bẩn)
3. ✅ Đơn hàng được xử lý: `PENDING → RabbitMQ → COMPLETED + PostgreSQL`
4. ✅ Dashboard hiển thị dữ liệu tổng hợp từ cả 2 database, có phân trang
5. ✅ Truy cập qua Kong Gateway với `apikey: noah-secret-key`, dashboard chạy bằng Nginx container.
6. ✅ Hệ thống có retry connection, atomic stock check và Dead Letter Queue cho độ tin cậy cực cao.

---

# 2. ARCHITECTURE DESIGN

## 2.1. Technology Stack

| Công nghệ | Vai trò | Lý do lựa chọn |
|---|---|---|
| **Python 3.11** | Ngôn ngữ chính cho tất cả services | Cú pháp đơn giản, hệ sinh thái phong phú (`pika`, `mysql-connector`, `psycopg2`), hỗ trợ tốt CSV & REST API |
| **MySQL 8.0** | Database Web Store (Products, Orders) | CRUD hiệu suất cao, phổ biến cho ứng dụng web, tương thích tốt với Python |
| **PostgreSQL 15** | Database Finance (Transactions, Customers) | Hỗ trợ `ON CONFLICT`, Index mạnh, phù hợp cho dữ liệu tài chính |
| **RabbitMQ 3** | Message Broker | Đảm bảo message không bị mất (durable queue, manual ACK), hỗ trợ xử lý bất đồng bộ |
| **Kong Gateway 3.4** | API Gateway & Security | Reverse Proxy, Key Authentication, Rate Limiting, CORS – tất cả bằng file cấu hình YAML |
| **FastAPI** | Framework cho Order API (Module 2A) | Hỗ trợ async, tự động validate dữ liệu via Pydantic, tự sinh OpenAPI docs |
| **Flask** | Framework cho Report Service (Module 3) và Local Server | Nhẹ, linh hoạt, dễ tích hợp kết nối đa database |
| **Docker Compose** | Orchestration tất cả services | Tất cả chạy bằng 1 lệnh, networking tự động theo tên container |
| **Chart.js** | Biểu đồ Dashboard | Nhẹ, responsive, hỗ trợ nhiều loại biểu đồ |

## 2.2. Logical View (Component Diagram)

Hệ thống gồm **8 containers** chạy trên Docker Compose, giao tiếp qua mạng nội bộ `noah-network`:

```
                    ┌──────────────────────────────────────────────────┐
                    │               Docker Network: noah-network       │
                    │                                                  │
  CSV File ───────▶ │  ┌──────────────┐    ┌────────────┐              │
  (inventory.csv)   │  │ Legacy       │───▶│  MySQL 8.0 │◀────┐       │
                    │  │ Adapter      │    │ (noah_store)│     │       │
                    │  └──────────────┘    └──────┬─────┘     │       │
                    │                             │           │       │
  Client ──────────▶│  ┌──────────────┐    ┌──────┴─────┐     │       │
  (HTTP POST)       │  │  Kong        │───▶│ Order API  │     │       │
                    │  │  Gateway     │    │ (FastAPI)  │     │       │
                    │  │  :8000       │    └──────┬─────┘     │       │
                    │  │              │           │           │       │
                    │  │              │    ┌──────▼─────┐     │       │
                    │  │              │    │ RabbitMQ 3 │     │       │
                    │  │              │    │ (Broker)   │     │       │
                    │  │              │    └──────┬─────┘     │       │
                    │  │              │           │           │       │
                    │  │              │    ┌──────▼──────┐    │       │
                    │  │              │    │ Order Worker │────┘       │
                    │  │              │    │ (Consumer)   │────┐       │
                    │  │              │    └─────────────┘    │       │
                    │  │              │                 ┌─────▼──────┐│
                    │  │              │───▶┌────────────┤ PostgreSQL ││
                    │  │              │    │ Report     │ (Finance)  ││
  Dashboard ───────▶│  │              │    │ Service    │            ││
  (Browser)         │  └──────────────┘    └────────────┴────────────┘│
                    └──────────────────────────────────────────────────┘
```

**Mô tả các thành phần:**

| Component | Container Name | Port | Mô tả |
|---|---|---|---|
| MySQL 8.0 | `noah_mysql` | Internal only | Lưu `products` (200 SP) và `orders` |
| PostgreSQL 15 | `noah_postgres` | Internal only | Lưu `transactions` và `customers` |
| RabbitMQ 3 | `noah_rabbitmq` | 15672 (UI) | Message Broker, queue `order_queue` |
| Kong Gateway | `noah_kong` | **8000** (proxy), 8001 (admin) | Reverse Proxy, Security |
| Legacy Adapter | `noah_legacy_adapter` | None | Polling `/app/input`, update MySQL |
| Order API | `noah_order_api` | Internal (5001) | FastAPI, insert PENDING, publish queue |
| Order Worker | `noah_order_worker` | None | Consumer, insert Postgres, update MySQL |
| Report Service | `noah_report_service` | Internal (5002) | Flask, data stitching, pagination |

## 2.3. Deployment View (Docker Compose)

**File:** `docker-compose.yml` (211 dòng)

```yaml
# Tóm tắt cấu hình
version: "3.9"
networks:
  noah-network:
    driver: bridge

volumes:
  mysql_data:      # Persistent data cho MySQL
  postgres_data:   # Persistent data cho PostgreSQL
  rabbitmq_data:   # Persistent data cho RabbitMQ

services:
  mysql:           # image: mysql:8.0, healthcheck, init script
  postgres:        # image: postgres:15, healthcheck, init script
  rabbitmq:        # image: rabbitmq:3-management, port 15672
  kong:            # image: kong:3.4, declarative config, port 8000/8001
  legacy_adapter:  # build: ./services/legacy_adapter, volumes: input/processed
  order_api:       # build: ./services/order_api, depends_on: mysql, rabbitmq
  order_worker:    # build: ./services/order_worker, depends_on: all DBs + MQ
  report_service:  # build: ./services/report_service, depends_on: mysql, postgres
```

**Networking & Volumes:**
- Tất cả services giao tiếp qua `noah-network` (bridge). Gọi nhau bằng **tên container** (DNS), ví dụ: `host=mysql`, `host=rabbitmq`.
- **Không hard-code IP** – tuân thủ Heuristics 1 (Independence).
- Volume mapping: `./input:/app/input` và `./processed:/app/processed` cho Legacy Adapter.
- Healthcheck cấu hình cho MySQL, Postgres, RabbitMQ → `depends_on: condition: service_healthy`.

**Bảo mật Port:**
- ⚠️ MySQL, Postgres: **KHÔNG expose port** ra ngoài Docker network.
- ⚠️ Order API (5001), Report Service (5002): **KHÔNG expose** – truy cập qua Kong Gateway.
- ✅ Chỉ expose: Kong `:8000` (proxy), RabbitMQ `:15672` (management UI).

## 2.4. Process View (Sequence Diagram – Luồng đặt hàng)

```
Client        Kong:8000       Order API       MySQL      RabbitMQ    Worker      PostgreSQL
  │               │               │              │           │          │            │
  │──POST /orders─▶               │              │           │          │            │
  │  +apikey      │──validate key─▶              │           │          │            │
  │               │  +rate check  │              │           │          │            │
  │               │               │──GET product─▶           │          │            │
  │               │               │◀──price,name─┤           │          │            │
  │               │               │──INSERT order─▶          │          │            │
  │               │               │  (PENDING)   │           │          │            │
  │               │               │◀──order_id───┤           │          │            │
  │               │               │──publish msg─────────────▶          │            │
  │               │               │              │           │          │            │
  │◀──202 Accepted─◀──────────────┤              │           │          │            │
  │               │               │              │           │          │            │
  │               │               │              │    ┌──consume──┐     │            │
  │               │               │              │    │ sleep 1-2s│     │            │
  │               │               │              │    └───────────┘     │            │
  │               │               │              │           │──INSERT transaction──▶│
  │               │               │              │           │          │◀──OK───────┤
  │               │               │              │◀──UPDATE COMPLETED───┤            │
  │               │               │              │           │◀──ACK────┤            │
  │               │               │              │           │   ┌──────┤            │
  │               │               │              │           │   │Notify│            │
  │               │               │              │           │   │(async)            │
  │               │               │              │           │   └──────┘            │
```

---

# 3. INTEGRATION STRATEGIES

---

## 3.1. Module 1: Legacy Adapter (Đồng bộ kho)

> **Phụ trách:** Bao, Cao Dinh  
> **Cơ chế tích hợp:** File Transfer + Polling  
> **Lab tham khảo:** Lab 3 (File Transfer), Lab 1 (Docker Volume)

### Các file phụ trách

| File | Đường dẫn | Chức năng |
|---|---|---|
| `adapter.py` | `services/legacy_adapter/adapter.py` (227 dòng) | Logic polling, validate, UPDATE MySQL, di chuyển file |
| `data_cleaning.py` | `src/data_cleaning.py` (96 dòng) | Module phụ: làm sạch CSV, xử lý DUPLICATE, ghi clean file |
| `Dockerfile` | `services/legacy_adapter/Dockerfile` | Container image cho service |
| `requirements.txt` | `services/legacy_adapter/requirements.txt` | Dependencies: `mysql-connector-python` |

### Cách xử lý – Luồng hoạt động

```
Vòng lặp Polling (mỗi 10 giây)
          │
          ▼
  ┌──────────────┐    Không        ┌──────────┐
  │ Kiểm tra file│───────────────▶ │  sleep   │
  │ inventory.csv│                 │ 10 giây  │──▶ (lặp lại)
  └──────┬───────┘                 └──────────┘
         │ Có file
         ▼
  ┌──────────────┐
  │ Mở CSV,      │
  │ đọc header   │──▶ Thiếu cột? → LOG ERROR, bỏ qua
  └──────┬───────┘
         │
         ▼
  ┌──────────────────┐
  │ Đọc từng dòng:   │
  │ • product_id ≤ 0? → SKIP, log warning
  │ • quantity < 0?   → SKIP, log warning
  │ • Sai format?     → SKIP, log warning (try-except)
  │ • Hợp lệ?        → UPDATE products SET stock=%s WHERE id=%s
  │ • ID not found?   → log warning, đếm not_found
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ conn.commit()    │
  │ Move file →      │
  │ /processed/      │
  │ inventory_       │
  │ YYYYMMDD_HHMMSS  │
  │ .csv             │
  └──────────────────┘
         │
         ▼
  [INFO] Processed 195 records. Skipped 10 invalid records.
```

### Giải quyết các thách thức

**1. Dữ liệu bẩn (Dirty Data – 5%):**
- Xử lý `try-except` cho mỗi dòng → **hệ thống không bao giờ crash**.
- 4 loại lỗi được xử lý: `negative_qty`, `zero_id`, `missing_field`, `invalid_char`.
- Biến đếm: `processed`, `skipped`, `not_found` – log chi tiết.

**2. Khởi động lạnh (Cold Start Retry):**
```python
# adapter.py – retry_connection()
def retry_connection(max_retries=5, delay=5):
    for attempt in range(1, max_retries + 1):
        try:
            conn = mysql.connector.connect(...)
            return conn
        except Error as e:
            log.warning(f"Retry {attempt}/{max_retries}: {e}")
            time.sleep(delay)
    raise last_err
```

**3. Cleanup (Di chuyển file):**
```python
# Đổi tên file kèm timestamp để tránh trùng
shutil.move(filepath, f"/app/processed/inventory_{timestamp}.csv")
```

**3. Xử lý nâng cao (Achievement 10/10):**
- **Deduplication:** Sử dụng cơ chế "last-write-wins" cho các dòng CSV trùng `product_id` trong một lần quét.
- **Batch Update:** Dùng `cursor.executemany()` để cập nhật hàng loạt trong một Transaction, tối ưu hóa I/O database.
- **Retry Logic:** Tự động kết nối lại MySQL với exponential backoff.
- **File Cleanup:** Di chuyển file sang `/processed` với timestamp sau khi xử lý thành công.

---

## 3.2. Module 2: Order Pipeline (Xử lý đơn hàng)

> **Phụ trách:** Huy, Ho Duong Quoc  
> **Cơ chế tích hợp:** REST API + Asynchronous Messaging  
> **Lab tham khảo:** Lab 4 (Direct API), Lab 5 (Messaging)

### Thành phần 2A: Order API (Producer)

#### Các file phụ trách

| File | Đường dẫn | Chức năng |
|---|---|---|
| `main.py` | `services/order_api/main.py` (245 dòng) | FastAPI app, validate, insert MySQL, publish RabbitMQ |
| `Dockerfile` | `services/order_api/Dockerfile` | Container image |
| `requirements.txt` | `services/order_api/requirements.txt` | Dependencies: `fastapi`, `uvicorn`, `mysql-connector-python`, `pika` |

#### Cách xử lý – Luồng hoạt động

```
Client gửi POST /api/orders
  │  {"user_id": 1, "product_id": 101, "quantity": 2}
  │
  ▼
┌─────────────────────────┐
│ 1. Pydantic Validation  │ → quantity ≤ 0? → 422 Error
│    (OrderRequest model) │ → user_id/product_id ≤ 0? → 422 Error
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 2. Stock Check & Lock   │ → SELECT stock FROM products ...
│    (Atomic deduction)   │ → UPDATE products SET stock = stock - ? WHERE stock >= ?
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 3. INSERT INTO orders   │ → total_price = price × quantity
│    status = 'PENDING'   │ → Idempotent creation
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 4. Publish RabbitMQ     │ → Queue: order_queue (durable)
│    JSON message         │ → delivery_mode=2 (persistent)
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 5. Response 202 Accepted│ → {"message": "Order received",
│    (Trả về ngay lập tức)│     "order_id": 123, "status": "PENDING"}
└─────────────────────────┘
```

#### Các Endpoint

| Method | Path | Mô tả | Response |
|---|---|---|---|
| `POST` | `/api/orders` | Tạo đơn hàng mới | `202` + JSON `{order_id, status, total}` |
| `GET` | `/api/orders` | Danh sách đơn hàng (phân trang) | `200` + JSON `{data, total, page, pages}` |
| `GET` | `/api/health` | Health check | `200` + `{status: "ok"}` |

---

### Thành phần 2B: Order Worker (Consumer)

#### Các file phụ trách

| File | Đường dẫn | Chức năng |
|---|---|---|
| `worker.py` | `services/order_worker/worker.py` (231 dòng) | RabbitMQ consumer, insert Postgres, update MySQL, async notification |
| `Dockerfile` | `services/order_worker/Dockerfile` | Container image |
| `requirements.txt` | `services/order_worker/requirements.txt` | Dependencies: `pika`, `mysql-connector-python`, `psycopg2-binary` |

#### Cách xử lý – Luồng hoạt động

```
Worker khởi động
  │
  ├── retry_rabbitmq(max_retries=10)  ← Chờ RabbitMQ sẵn sàng
  ├── queue_declare("order_queue", durable=True)
  ├── basic_qos(prefetch_count=1)     ← Chỉ xử lý 1 message/lần
  └── basic_consume(auto_ack=False)   ← Manual ACK
          │
          ▼ (Mỗi khi có message)
    ┌─────────────────────────────┐
    │ Bước 1: JSON.loads(body)    │
    │ Lấy order_id, user_id, ... │
    └──────────┬──────────────────┘
               ▼
    ┌─────────────────────────────┐
    │ Bước 2: Giả lập thanh toán │
    │ time.sleep(random 1-2s)    │
    └──────────┬──────────────────┘
               ▼
    ┌─────────────────────────────┐
    │ Bước 3: DB Operation Retry │ ← Exponential backoff (2s, 4s, 8s)
    │ → INSERT PostgreSQL        │ ← PostgreSQL transactions
    │ → UPDATE MySQL COMPLETED   │ ← Đảm bảo consistency
    └──────────┬──────────────────┘
               ▼
    ┌─────────────────────────────┐
    │ Bước 4: DLQ Management     │ ← Nếu lỗi > 3 lần → chuyển vào
    │ → basic_ack() or DLQ       │   order_queue_dlq (Poison message)
    └──────────┬──────────────────┘
               ▼
    ┌─────────────────────────────┐
    │ Bước 5: Async Notification  │ ← threading.Thread (Fire-and-Forget)
    │ "Đơn hàng thanh toán xong"  │
    └─────────────────────────────┘
```

#### Xử lý lỗi trong Worker

```python
except Exception as e:
    # NACK với requeue=True → message quay lại queue
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
```
→ Nếu Worker chết giữa chừng, message **không bị mất** mà được xử lý lại.

### Module 2 cần gì?

| Yêu cầu | Giải pháp |
|---|---|
| Validate input | Pydantic `@field_validator` (FastAPI) |
| Lưu trạng thái sơ bộ | `INSERT INTO orders ... status='PENDING'` |
| Bất đồng bộ | RabbitMQ `order_queue` (durable, persistent) |
| Phản hồi nhanh | `return 202 Accepted` ngay lập tức |
| Đồng bộ Finance | Worker INSERT vào PostgreSQL `transactions` |
| Cập nhật trạng thái | Worker UPDATE MySQL `PENDING → COMPLETED` |
| Chống mất message | Manual ACK + NACK with requeue |
| Chống trùng | PostgreSQL `ON CONFLICT (order_id) DO NOTHING` |
| Thông báo | `threading.Thread` → Fire-and-Forget notification |

---

## 3.3. Module 3: Dashboard & Report (Trung tâm chỉ huy)

> **Phụ trách:** Hoang, Vo Duy  
> **Cơ chế tích hợp:** Data Stitching (Multi-source Query + Code-side Join)  
> **Lab tham khảo:** Lab 2 (ETL/Data Integration)

### Các file phụ trách

| File | Đường dẫn | Chức năng |
|---|---|---|
| `app.py` | `services/report_service/app.py` (306 dòng) | Flask API, kết nối đồng thời MySQL + Postgres, data stitching, phân trang |
| `Dashboard.html` | `giao diện/Dashboard.html` (1475 dòng) | Frontend UI: sidebar, stat cards, bảng đơn hàng, biểu đồ Chart.js, form đặt hàng, console log |
| `Dockerfile` | `services/report_service/Dockerfile` | Container image |
| `requirements.txt` | `services/report_service/requirements.txt` | Dependencies: `flask`, `flask-cors`, `mysql-connector-python`, `psycopg2-binary` |

### Cách xử lý – Data Stitching

```
┌───────────┐         ┌───────────────┐         ┌──────────────┐
│  MySQL    │         │ Report Service│         │ PostgreSQL   │
│ (orders + │◀────────┤    app.py     ├────────▶│(transactions)│
│  products)│  Query  │               │  Query  │              │
└───────────┘         └───────┬───────┘         └──────────────┘
                              │
                  ┌───────────▼───────────┐
                  │ Data Stitching:       │
                  │ for order in orders:  │
                  │   if order_id in      │
                  │     transactions_map: │
                  │     order["synced"]   │
                  │       = True          │
                  │     order["amount_    │
                  │       paid"] = tx amt │
                  │   else:              │
                  │     order["synced"]   │
                  │       = False        │
                  └───────────┬───────────┘
                              │
                              ▼
                    JSON Response với:
                    - orders (đối soát)
                    - top_customers
                    - stats tổng hợp
```

### Các Endpoint REST API

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/report?page=1&limit=20` | Đối soát: orders + transactions stitching, top 10 customers, thống kê |
| `GET` | `/api/products?page=1&limit=20` | Danh sách sản phẩm + tồn kho (phân trang, max 100/page) |
| `GET` | `/api/stats` | Thống kê nhanh: total orders, completed, pending, revenue, total products, transactions count |
| `GET` | `/api/health` | Health check |

### Dashboard UI (Frontend)

Dashboard là giao diện SPA (Single Page Application) gồm 5 section:

| Section | Chức năng |
|---|---|
| **Tổng Quan** | 4 stat cards (đơn hàng, doanh thu, sản phẩm, giao dịch) + biểu đồ Chart.js + top khách hàng |
| **Đơn Hàng** | Bảng orders với phân trang, badge trạng thái (COMPLETED/PENDING), cột đối soát (synced) |
| **Tồn Kho** | Bảng products sắp xếp theo stock DESC, phân trang |
| **Đặt Hàng** | Form tạo đơn hàng mới (user_id, product_id, quantity) → gọi POST /api/orders |
| **Pipeline** | Hiển thị trạng thái pipeline: CSV → MySQL → RabbitMQ → Worker → PostgreSQL + Console log |

### Module 3 cần gì?

| Yêu cầu | Giải pháp |
|---|---|
| Kết nối đa nguồn | `get_mysql()` + `get_postgres()` đồng thời |
| Data Stitching | Query MySQL orders → Query Postgres transactions → Code-side join theo `order_id` |
| Phân trang | `LIMIT %s OFFSET %s` (max 100 records/page) |
| Biểu đồ | Chart.js (doanh thu, đơn hàng theo trạng thái) |
| Responsive | CSS Grid + Media queries cho mobile/tablet |

---

## 3.4. Module 4: Security & Governance (Kong Gateway)

> **Phụ trách:** Thien, Pham Hai  
> **Cơ chế tích hợp:** API Gateway (Reverse Proxy) + Plugin-based Security  
> **Lab tham khảo:** Lab 6 (API Gateway)

### Các file phụ trách

| File | Đường dẫn | Chức năng |
|---|---|---|
| `kong.yml` | `kong/kong.yml` (87 dòng) | Declarative config: services, routes, consumers, plugins |
| `docker-compose.yml` | `docker-compose.yml` (mục kong) | Container config, port mapping 8000/8001 |

### Cấu hình Kong Gateway

```yaml
# kong.yml – Tóm tắt cấu hình

consumers:
  - username: noah-dashboard
    keyauth_credentials:
      - key: noah-secret-key      # ← API Key duy nhất

services:
  # ── Order API ──
  - name: order-api-service
    url: http://order_api:5001     # ← Trỏ vào container name
    routes:
      - paths: [/orders, /api/orders]
        methods: [POST, GET, OPTIONS]
    plugins:
      - name: key-auth             # ← Bắt buộc gửi header apikey
      - name: rate-limiting        # ← 10 req/phút
        config: { minute: 10 }
      - name: cors                 # ← Cho phép Dashboard gọi cross-origin

  # ── Report Service ──
  - name: report-service
    url: http://report_service:5002
    routes:
      - paths: [/report, /api/report]
      - paths: [/api/products]
    plugins:
      - name: key-auth
      - name: rate-limiting
        config: { minute: 30 }     # ← Report cho 30 req/phút
      - name: cors
```

### Cách hoạt động – Reverse Proxy

```
Client (Browser/Postman)
    │
    │ GET http://localhost:8000/report/api/stats
    │ Header: apikey: noah-secret-key
    │
    ▼
┌──────────────────┐
│   Kong Gateway   │
│   (:8000)        │
│                  │
│ 1. Check apikey  │ → Sai key? → 401 Unauthorized
│ 2. Rate limit    │ → Quá 10 req/min? → 429 Too Many Requests
│ 3. Proxy forward │ → http://report_service:5002/api/stats
└──────┬───────────┘
       ▼
┌──────────────┐
│ Report       │
│ Service      │
│ (internal)   │
└──────────────┘
```

### Bảo mật đạt được

| Lớp bảo mật | Cơ chế | Chi tiết |
|---|---|---|
| **Network Isolation** | Docker network | MySQL, Postgres không expose port ra ngoài |
| **API Key Auth** | Kong `key-auth` plugin | Client phải gửi `apikey: noah-secret-key` |
| **Rate Limiting** | Kong `rate-limiting` plugin | Order: 10 req/min, Report: 30 req/min |
| **CORS** | Kong `cors` plugin | Cho phép origins `*`, headers: `Content-Type, apikey` |
| **Env Variables** | `.env` + Docker env | Mật khẩu DB không hard-code trong source |
| **Input Validation** | Pydantic (FastAPI) + try-except | Chặn dữ liệu bất hợp lệ trước khi vào hệ thống |

### Module 4 cần gì?

| Yêu cầu | Giải pháp |
|---|---|
| Reverse Proxy | Kong Gateway declarative mode (`KONG_DATABASE: "off"`) |
| Authentication | Plugin `key-auth` + consumer `noah-dashboard` |
| Rate Limiting | Plugin `rate-limiting` (10 req/min cho orders, 30 req/min cho report) |
| Ẩn port nội bộ | Không expose port 5001, 5002 trong `docker-compose.yml` |
| CORS | Plugin `cors` cho phép Dashboard frontend gọi API |

---

## Tính năng mở rộng: OPTION 1 – Notification System

> **Tích hợp trong:** `services/order_worker/worker.py` (Bước 5-6)

**Cơ chế:** Fire-and-Forget bằng `threading.Thread(daemon=True)`. Worker không bị treo khi gửi thông báo.

```python
# worker.py dòng 102-112
def send_async_notification(user_id, order_id, total, processed_time):
    time.sleep(1)  # Giả lập SMTP/Telegram delay
    log.info(f"Xin chào User {user_id}, đơn hàng #{order_id} trị giá "
             f"{int(total):,}đ đã thanh toán thành công lúc {processed_time}.")

# Gọi bất đồng bộ
threading.Thread(target=send_async_notification, args=(...), daemon=True).start()
```

**Output log:**
```
[INFO] Order #123 synced. Processing complete.
[INFO] Triggered background async notification for Order #123.
[THÔNG BÁO TỚI KHÁCH HÀNG] ✉️
Xin chào User 440, đơn hàng #123 trị giá 14,920,000đ đã thanh toán thành công lúc 15:30:45.
```

---

# 4. DATA & UI DESIGN

## 4.1. ERD & Data Dictionary

### MySQL Database: `noah_store`

**Bảng `products`** (200 sản phẩm, ID 100–299)

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `INT PRIMARY KEY` | Mã sản phẩm (100–299) |
| `name` | `VARCHAR(255) NOT NULL` | Tên sản phẩm (VD: "Điện Thoại NOAH X1") |
| `price` | `DECIMAL(12,0) NOT NULL` | Giá (VND) |
| `stock` | `INT NOT NULL DEFAULT 0` | Số lượng tồn kho (cập nhật bởi Legacy Adapter) |
| `updated_at` | `TIMESTAMP` | Thời gian cập nhật cuối |

**Bảng `orders`** (200+ đơn hàng mẫu)

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `INT AUTO_INCREMENT PK` | Mã đơn hàng |
| `user_id` | `INT NOT NULL` | Mã người dùng |
| `product_id` | `INT NOT NULL FK` | Mã sản phẩm → `products(id)` |
| `quantity` | `INT NOT NULL` | Số lượng |
| `total_price` | `DECIMAL(12,0) NOT NULL` | Tổng giá trị = price × quantity |
| `status` | `VARCHAR(50) DEFAULT 'PENDING'` | Trạng thái: `PENDING` → `COMPLETED` |
| `created_at` | `TIMESTAMP` | Thời gian tạo |

### PostgreSQL Database: `noah_finance`

**Bảng `transactions`**

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | ID giao dịch |
| `order_id` | `INT NOT NULL UNIQUE` | Mã đơn hàng (1:1 với MySQL orders) |
| `user_id` | `INT NOT NULL` | Mã người dùng |
| `amount` | `BIGINT NOT NULL` | Số tiền thanh toán |
| `product_id` | `INT NOT NULL` | Mã sản phẩm |
| `quantity` | `INT NOT NULL` | Số lượng |
| `processed_at` | `TIMESTAMP` | Thời gian xử lý |
| `note` | `TEXT` | Ghi chú Worker |

**Indexes:** `idx_transactions_user_id`, `idx_transactions_order_id`, `idx_transactions_processed_at`

**Bảng `customers`** (10 khách hàng mẫu)

| Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | ID khách hàng |
| `name` | `VARCHAR(255) NOT NULL` | Tên |
| `email` | `VARCHAR(255) UNIQUE` | Email |
| `phone` | `VARCHAR(20)` | Số điện thoại |
| `created_at` | `TIMESTAMP` | Thời gian tạo |

### Data Mapping (CSV → MySQL)

| CSV Field | MySQL Column | Xử lý |
|---|---|---|
| `product_id` | `products.id` | `int()`, validate > 0 |
| `quantity` | `products.stock` | `int()`, validate ≥ 0, UPDATE (không INSERT) |

## 4.2. UI Mockup – Dashboard

Dashboard được thiết kế theo phong cách **Dark Mode Premium** với các đặc điểm:

- **Font:** Inter (Google Fonts) – 300 đến 800 weight
- **Color Palette:** Deep navy (`#0a0e1a`), surface (`#111827`), accent blue-purple gradient
- **Layout:** Sidebar (240px) + Main content, responsive với media queries
- **Components:** Stat cards (4 loại), Data tables (phân trang), Chart.js, Form đặt hàng, Console log, Toast notifications

**5 Section chính:**

| # | Section | Icon | Nội dung |
|---|---|---|---|
| 1 | Tổng Quan | 📊 | 4 stat cards + biểu đồ doanh thu + top 10 khách hàng |
| 2 | Đơn Hàng | 📦 | Bảng orders (phân trang 20/page) + badge COMPLETED/PENDING + cột đối soát |
| 3 | Tồn Kho | 🏭 | Bảng products (sắp theo stock giảm dần) + phân trang |
| 4 | Đặt Hàng | 🛒 | Form nhập user_id, product_id, quantity → POST /api/orders |
| 5 | Pipeline | ⚡ | Trạng thái pipeline (CSV → MySQL → RabbitMQ → Postgres) + console log |

**Luồng dữ liệu Dashboard:**
```
Dashboard (HTML/JS) ──▶ Kong Gateway (:8000) ──▶ Report Service ──▶ MySQL + PostgreSQL
                        Header: apikey: noah-secret-key
```

---

# 5. INTEGRATION TESTING

## 5.1. Happy Path (Luồng thành công)

| # | Kịch bản | Input | Expected Output |
|---|---|---|---|
| 1 | Đồng bộ tồn kho | Đặt `inventory.csv` vào `./input/` | MySQL `products.stock` cập nhật, file di chuyển sang `./processed/` |
| 2 | Đặt đơn hàng | `POST /orders/api/orders` qua Kong | MySQL insert PENDING → RabbitMQ message → Worker process → Postgres transaction + MySQL COMPLETED |
| 3 | Xem báo cáo đối soát | `GET /report/api/report` | JSON chứa orders + synced status + amount_paid từ Postgres |
| 4 | Dashboard phân trang | `GET /report/api/products?page=2&limit=20` | 20 sản phẩm trang 2, `total=200`, `pages=10` |
| 5 | Bảo mật Gateway | `GET localhost:8000/report` không có apikey | `401 Unauthorized` |

## 5.2. Exception Path (Luồng xử lý lỗi)

| # | Kịch bản | Expected Behavior |
|---|---|---|
| 1 | CSV chứa `quantity = -5` | Legacy Adapter bỏ qua dòng đó, log warning, tiếp tục xử lý |
| 2 | CSV chứa `product_id = "ABC!@#"` | `ValueError` caught, skip dòng, hệ thống không crash |
| 3 | CSV thiếu cột `quantity` | Log error "thiếu cột", bỏ qua toàn bộ file |
| 4 | POST order với `quantity = -1` | FastAPI trả `422 Validation Error` |
| 5 | POST order với `product_id = 9999` (không tồn tại) | Trả `404 Not Found` |
| 6 | Gửi request không có apikey | Kong trả `401 Unauthorized` |
| 7 | Gửi > 10 requests/phút | Kong trả `429 Too Many Requests` |

## 5.3. Chaos Testing (Kiểm thử sự cố)

| # | Kịch bản | Expected Behavior |
|---|---|---|
| 1 | MySQL khởi động chậm (10-20s) | Tất cả services dùng `retry_connection()` → tự kết nối lại sau 5s |
| 2 | Worker chết giữa chừng xử lý | Message chưa được ACK → RabbitMQ tự requeue → Worker khác xử lý lại |
| 3 | RabbitMQ mất kết nối | Worker tự reconnect sau 10s (`while True: ... except: sleep(10)`) |
| 4 | CSV 200+ dòng với 5% lỗi | Xử lý ~190 dòng hợp lệ, skip ~10 dòng lỗi, không crash |
| 5 | Truy cập trực tiếp port 5001/5002 | Port không được expose → Connection refused |

## 5.4. Script sinh dữ liệu test

```bash
# Sinh inventory.csv (200 dòng, 5% dữ liệu bẩn)
python admin_data_generator.py --mode csv --count 200 --dirty 0.05

# Sinh SQL orders mẫu
python admin_data_generator.py --mode orders --count 50

# Sinh cả hai
python admin_data_generator.py --mode both --count 100
```

---

# 6. CONCLUSION

## 6.1. Kết quả đạt được

| Mục tiêu ban đầu | Kết quả |
|---|---|
| Tự động hóa đồng bộ Kho → Web Store | ✅ Legacy Adapter polling CSV, validate, UPDATE MySQL mỗi 10 giây |
| Xử lý đơn hàng bất đồng bộ | ✅ Order API → RabbitMQ → Worker pipeline, manual ACK |
| Đồng bộ Bán hàng → Tài chính | ✅ Worker tự động INSERT vào PostgreSQL, UPDATE MySQL `COMPLETED` |
| Dashboard đối soát dữ liệu | ✅ Data Stitching MySQL + PostgreSQL, phân trang, biểu đồ |
| Bảo mật API Gateway | ✅ Kong Gateway: key-auth, rate-limiting, CORS, port isolation |
| Hệ thống chịu lỗi (Fault-tolerant) | ✅ Retry connection, try-except, NACK+requeue, healthcheck |
| Tính năng mở rộng | ✅ Option 1: Notification System (async, fire-and-forget) |

## 6.2. Hạn chế và hướng phát triển

| Hạn chế hiện tại | Hướng phát triển (Heuristics 2: Extensibility) |
|---|---|
| Notification chỉ giả lập bằng log | Tích hợp SMTP/Telegram Bot API thực tế |
| Chưa có Redis chống bán lố | Thêm Option 2: Redis `DECR` atomic cho High Concurrency |
| Dashboard không real-time | Thêm Option 4: WebSocket cho live update |
| Chưa có trang mua hàng cho khách | Thêm Option 5: Client Storefront (React/Vue) |
| Chưa có AI phân tích | Thêm Option 3: OpenAI/Gemini API cho insight |
| Worker chạy đơn luồng | Scale horizontal bằng Docker Compose `replicas` |

---

# 7. REFERENCES

| # | Category | References |
|---|---|---|
| 1 | Scrum Model | https://en.wikipedia.org/wiki/Scrum_(software_development) · https://www.atlassian.com/agile/scrum · https://www.scrum.org/resources/scrum-guide |
| 2 | Technical | https://docs.docker.com/ · https://dev.mysql.com/doc/ · https://flask.palletsprojects.com/ · https://fastapi.tiangolo.com/ · https://www.rabbitmq.com/tutorials · https://docs.konghq.com/ |
| 3 | Standards | https://www.mckinsey.com/industries/travel-logistics-and-infrastructure/our-insights/digital-transformation · https://commerce.orisha.com/blog/unified-commerce-future-retail-sector/ |
