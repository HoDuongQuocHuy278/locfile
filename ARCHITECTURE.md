# NOAH Retail – System Architecture (Kiến Trúc Hệ Thống)

## 1. Tổng Quan Kiến Trúc

Hệ thống NOAH Retail Unified Commerce được thiết kế theo kiến trúc **Microservices**, chia thành **5 tầng** (Layers), chạy trên **Docker Compose** với 8 containers giao tiếp qua mạng nội bộ `noah-network`.

---

## 2. Sơ Đồ Kiến Trúc Tổng Thể

```
 ┌─────────────────────────────────────────────────────────────────────────────────┐
 │                          EXTERNAL / CLIENT LAYER                               │
 │                                                                                │
 │   ┌────────────────────┐          ┌────────────────────────────┐               │
 │   │  📁 Legacy System  │          │  🌐 Dashboard / Browser    │               │
 │   │  (AS/400)          │          │  (HTML + JS + Chart.js)    │               │
 │   │                    │          │                            │               │
 │   │  inventory.csv ────┼──┐       │  http://localhost:8000     │               │
 │   └────────────────────┘  │       └─────────────┬──────────────┘               │
 │                           │                     │                              │
 └───────────────────────────┼─────────────────────┼──────────────────────────────┘
                             │                     │
 ┌───────────────────────────┼─────────────────────┼──────────────────────────────┐
 │                           │    SECURITY LAYER   │                              │
 │                           │   ┌─────────────────▼──────────────────┐           │
 │                           │   │      🛡️ KONG API GATEWAY           │           │
 │                           │   │      Container: noah_kong          │           │
 │                           │   │      Port: 8000 (Proxy)            │           │
 │                           │   │                                    │           │
 │                           │   │  ┌──────────┐ ┌───────────────┐   │           │
 │                           │   │  │ Key Auth │ │ Rate Limiting │   │           │
 │                           │   │  │ (apikey) │ │ 10-30 req/min │   │           │
 │                           │   │  └──────────┘ └───────────────┘   │           │
 │                           │   │  ┌──────────┐ ┌───────────────┐   │           │
 │                           │   │  │  CORS    │ │ Reverse Proxy │   │           │
 │                           │   │  └──────────┘ └───────────────┘   │           │
 │                           │   │                                    │           │
 │                           │   │  Routes:                           │           │
 │                           │   │   /orders → order_api:5001         │           │
 │                           │   │   /report → report_service:5002    │           │
 │                           │   └──────┬──────────────┬──────────────┘           │
 │                           │          │              │                          │
 └───────────────────────────┼──────────┼──────────────┼──────────────────────────┘
                             │          │              │
 ╔═══════════════════════════╪══════════╪══════════════╪══════════════════════════╗
 ║  DOCKER NETWORK: noah-network (bridge)                                        ║
 ║                                                                               ║
 ║  ┌────────────────────────────── APPLICATION LAYER ──────────────────────────┐ ║
 ║  │                                                                          │ ║
 ║  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │ ║
 ║  │  │ 📂 Module 1     │  │ 📦 Module 2A    │  │ 📊 Module 3             │  │ ║
 ║  │  │ LEGACY ADAPTER  │  │ ORDER API       │  │ REPORT SERVICE          │  │ ║
 ║  │  │                 │  │                 │  │                         │  │ ║
 ║  │  │ Container:      │  │ Container:      │  │ Container:              │  │ ║
 ║  │  │ noah_legacy_    │  │ noah_order_api  │  │ noah_report_service     │  │ ║
 ║  │  │ adapter         │  │                 │  │                         │  │ ║
 ║  │  │                 │  │ Framework:      │  │ Framework: Flask        │  │ ║
 ║  │  │ • CSV Polling   │  │ FastAPI         │  │ Port: 5002 (internal)   │  │ ║
 ║  │  │   (mỗi 10s)    │  │ Port: 5001      │  │                         │  │ ║
 ║  │  │ • Data Validate │  │ (internal)      │  │ • GET /api/report       │  │ ║
 ║  │  │ • UPDATE MySQL  │  │                 │  │ • GET /api/products     │  │ ║
 ║  │  │ • File Cleanup  │  │ • POST /orders  │  │ • GET /api/stats        │  │ ║
 ║  │  │ • Retry (5x)    │  │ • Validate      │  │ • Data Stitching        │  │ ║
 ║  │  │                 │  │ • Publish MQ    │  │   (MySQL + Postgres)    │  │ ║
 ║  │  └────────┬────────┘  └───┬─────────┬───┘  └──────┬──────────┬──────┘  │ ║
 ║  │           │               │         │              │          │         │ ║
 ║  └───────────┼───────────────┼─────────┼──────────────┼──────────┼─────────┘ ║
 ║              │               │         │              │          │           ║
 ║  ┌───────────┼───────────────┼─────────┼──────────────┼──────────┼─────────┐ ║
 ║  │           │          MESSAGE LAYER  │              │          │         │ ║
 ║  │           │               │  ┌──────▼──────────┐   │          │         │ ║
 ║  │           │               │  │ 🐇 RABBITMQ 3   │   │          │         │ ║
 ║  │           │               │  │                  │   │          │         │ ║
 ║  │           │               │  │ Container:       │   │          │         │ ║
 ║  │           │               │  │ noah_rabbitmq    │   │          │         │ ║
 ║  │           │               └─▶│                  │   │          │         │ ║
 ║  │           │      (publish)   │ Queue:           │   │          │         │ ║
 ║  │           │                  │ order_queue      │   │          │         │ ║
 ║  │           │                  │ (durable)        │   │          │         │ ║
 ║  │           │                  │                  │   │          │         │ ║
 ║  │           │                  │ Port: 15672 (UI) │   │          │         │ ║
 ║  │           │                  └────────┬─────────┘   │          │         │ ║
 ║  │           │                           │             │          │         │ ║
 ║  │           │                  ┌────────▼──────────┐  │          │         │ ║
 ║  │           │                  │ ⚙️ Module 2B      │  │          │         │ ║
 ║  │           │                  │ ORDER WORKER      │  │          │         │ ║
 ║  │           │                  │                   │  │          │         │ ║
 ║  │           │                  │ Container:        │  │          │         │ ║
 ║  │           │                  │ noah_order_worker │  │          │         │ ║
 ║  │           │                  │                   │  │          │         │ ║
 ║  │           │                  │ • Consume message │  │          │         │ ║
 ║  │           │                  │ • Sleep 1-2s      │  │          │         │ ║
 ║  │           │                  │ • INSERT Postgres │  │          │         │ ║
 ║  │           │                  │ • UPDATE MySQL    │  │          │         │ ║
 ║  │           │                  │ • Manual ACK      │  │          │         │ ║
 ║  │           │                  │ • Async Notify    │  │          │         │ ║
 ║  │           │                  └──┬─────────────┬──┘  │          │         │ ║
 ║  │           │                     │             │     │          │         │ ║
 ║  └───────────┼─────────────────────┼─────────────┼─────┼──────────┼─────────┘ ║
 ║              │                     │             │     │          │           ║
 ║  ┌───────────┼─────────────────────┼─────────────┼─────┼──────────┼─────────┐ ║
 ║  │           │              DATA LAYER           │     │          │         │ ║
 ║  │           │                     │             │     │          │         │ ║
 ║  │  ┌────────▼─────────────────────▼────────┐  ┌─▼─────▼──────────▼──────┐ │ ║
 ║  │  │  🐬 MYSQL 8.0                        │  │ 🐘 POSTGRESQL 15       │ │ ║
 ║  │  │  Container: noah_mysql               │  │ Container: noah_postgres│ │ ║
 ║  │  │  Database: noah_store                │  │ Database: noah_finance  │ │ ║
 ║  │  │  Port: 3306 (internal only)          │  │ Port: 5432 (internal)  │ │ ║
 ║  │  │                                      │  │                        │ │ ║
 ║  │  │  ┌──────────────┐ ┌───────────────┐  │  │ ┌──────────────────┐   │ │ ║
 ║  │  │  │  products    │ │   orders      │  │  │ │  transactions    │   │ │ ║
 ║  │  │  │  (200 items) │ │   (200+ rows) │  │  │ │  (order_id UK)   │   │ │ ║
 ║  │  │  │              │ │               │  │  │ │                  │   │ │ ║
 ║  │  │  │  id (PK)     │ │  id (PK,AI)   │  │  │ │  id (PK)         │   │ │ ║
 ║  │  │  │  name        │ │  user_id      │  │  │ │  order_id (UK)   │   │ │ ║
 ║  │  │  │  price       │ │  product_id FK│  │  │ │  user_id         │   │ │ ║
 ║  │  │  │  stock       │ │  quantity     │  │  │ │  amount          │   │ │ ║
 ║  │  │  │  updated_at  │ │  total_price  │  │  │ │  product_id      │   │ │ ║
 ║  │  │  │              │ │  status       │  │  │ │  quantity         │   │ │ ║
 ║  │  │  │              │ │  created_at   │  │  │ │  processed_at    │   │ │ ║
 ║  │  │  └──────────────┘ └───────────────┘  │  │ │  note            │   │ │ ║
 ║  │  │                                      │  │ └──────────────────┘   │ │ ║
 ║  │  │                                      │  │                        │ │ ║
 ║  │  │  Healthcheck: mysqladmin ping        │  │ ┌──────────────────┐   │ │ ║
 ║  │  │  Volume: mysql_data                  │  │ │  customers (10)  │   │ │ ║
 ║  │  │                                      │  │ │  id, name, email │   │ │ ║
 ║  │  │                                      │  │ │  phone           │   │ │ ║
 ║  │  │                                      │  │ └──────────────────┘   │ │ ║
 ║  │  │                                      │  │                        │ │ ║
 ║  │  │                                      │  │ Healthcheck: pg_isready│ │ ║
 ║  │  │                                      │  │ Volume: postgres_data  │ │ ║
 ║  │  └──────────────────────────────────────┘  └────────────────────────┘ │ ║
 ║  └──────────────────────────────────────────────────────────────────────┘ ║
 ╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 3. Luồng Dữ Liệu (Data Flow)

### 3.1. Luồng Đồng Bộ Kho (Module 1)

```
  Legacy AS/400                                       Docker
  ┌──────────┐    CSV File     ┌──────────────┐      ┌──────────┐
  │ Warehouse│ ──────────────▶ │ Legacy       │ ────▶│ MySQL    │
  │ System   │  inventory.csv  │ Adapter      │      │ products │
  └──────────┘  (5% dirty)    │              │      │ .stock   │
                               │ 1. Poll /10s │      └──────────┘
                               │ 2. Validate  │
                               │ 3. UPDATE DB │
                               │ 4. Move file │
                               └──────────────┘
                                     │
                                     ▼
                               /app/processed/
                               inventory_YYYYMMDD.csv
```

### 3.2. Luồng Đặt Hàng (Module 2A + 2B)

```
  Client                Kong          Order API        RabbitMQ       Worker
    │                    │               │                │              │
    │ POST /orders ─────▶│               │                │              │
    │ apikey: noah-...   │──validate──▶ │                │              │
    │                    │   key+rate   │                │              │
    │                    │              │──SELECT product─│──────────────│──▶ MySQL
    │                    │              │──INSERT PENDING─│──────────────│──▶ MySQL
    │                    │              │──publish msg───▶│              │
    │◀── 202 Accepted ──│◀─────────────│                │              │
    │                    │              │                │──consume────▶│
    │                    │              │                │  (auto=False)│
    │                    │              │                │              │──▶ PostgreSQL
    │                    │              │                │              │    (INSERT)
    │                    │              │   MySQL ◀──────│──────────────│
    │                    │              │   (UPDATE      │              │
    │                    │              │    COMPLETED)  │◀──── ACK ───│
    │                    │              │                │              │
    │                    │              │                │     ┌────────│
    │                    │              │                │     │ Notify │
    │                    │              │                │     │ (async)│
    │                    │              │                │     └────────│
```

### 3.3. Luồng Báo Cáo Đối Soát (Module 3)

```
  Dashboard             Kong          Report Service    MySQL        PostgreSQL
    │                    │               │                │              │
    │ GET /api/report ──▶│               │                │              │
    │ apikey: noah-...   │──validate──▶ │                │              │
    │                    │              │──SELECT orders──│──────────────│──▶ MySQL
    │                    │              │◀── orders[] ───│──────────────│
    │                    │              │                │              │
    │                    │              │──SELECT tx─────│──────────────│──▶ PostgreSQL
    │                    │              │◀── tx_map{} ──│──────────────│
    │                    │              │                │              │
    │                    │              │ DATA STITCHING:│              │
    │                    │              │ merge by       │              │
    │                    │              │ order_id       │              │
    │                    │              │                │              │
    │◀── JSON Response ─│◀─────────────│                │              │
    │  {orders, stats,  │              │                │              │
    │   top_customers}  │              │                │              │
```

---

## 4. Port Mapping & Network

### 4.1. Bảng Port

| Service | Container | Internal Port | External Port | Truy cập |
|---|---|---|---|---|
| Kong Gateway | noah_kong | 8000, 8001 | **8000**, 8001 | ✅ Public (Proxy) |
| RabbitMQ UI | noah_rabbitmq | 15672 | **15672** | ✅ Dev only |
| MySQL | noah_mysql | 3306 | ❌ None | 🔒 Internal only |
| PostgreSQL | noah_postgres | 5432 | ❌ None | 🔒 Internal only |
| Order API | noah_order_api | 5001 | ❌ None | 🔒 Via Kong |
| Report Service | noah_report_service | 5002 | ❌ None | 🔒 Via Kong |
| Legacy Adapter | noah_legacy_adapter | None | ❌ None | 🔒 Background |
| Order Worker | noah_order_worker | None | ❌ None | 🔒 Background |

### 4.2. Docker Network

```
noah-network (bridge)
├── noah_mysql          (hostname: mysql)
├── noah_postgres       (hostname: postgres)
├── noah_rabbitmq       (hostname: rabbitmq)
├── noah_kong           (hostname: kong)
├── noah_legacy_adapter (hostname: legacy_adapter)
├── noah_order_api      (hostname: order_api)
├── noah_order_worker   (hostname: order_worker)
└── noah_report_service (hostname: report_service)
```

Tất cả services gọi nhau bằng **hostname** (DNS), không hard-code IP.
Ví dụ: `MYSQL_HOST=mysql`, `RABBITMQ_HOST=rabbitmq`, `url: http://order_api:5001`

---

## 5. Dependency Graph (Thứ tự khởi động)

```
                    ┌──────────┐
                    │  MySQL   │ ◀── healthcheck: mysqladmin ping
                    └────┬─────┘
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             │             ▼
  ┌────────────────┐     │    ┌──────────────┐
  │ Legacy Adapter │     │    │  PostgreSQL   │ ◀── healthcheck: pg_isready
  │ (depends: my)  │     │    └──────┬───────┘
  └────────────────┘     │           │
                         │           │
                    ┌────▼─────┐     │
                    │ RabbitMQ │ ◀── healthcheck: rabbitmq-diagnostics
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          │          ▼
     ┌─────────────┐     │   ┌──────────────┐
     │  Order API  │     │   │ Order Worker  │
     │ (my + mq)   │     │   │ (my+pg+mq)   │
     └──────┬──────┘     │   └──────────────┘
            │            │
            │    ┌───────▼────────┐
            │    │ Report Service │
            │    │ (my + pg)      │
            │    └───────┬────────┘
            │            │
            ▼            ▼
       ┌──────────────────────┐
       │    Kong Gateway      │
       │ (depends: order_api, │
       │  report_service)     │
       └──────────────────────┘
```

---

## 6. Volume Mapping

| Host Path | Container Path | Sử dụng bởi | Mục đích |
|---|---|---|---|
| `./input/` | `/app/input/` | Legacy Adapter | Thư mục chứa CSV đầu vào |
| `./processed/` | `/app/processed/` | Legacy Adapter | Thư mục lưu CSV đã xử lý |
| `./mysql/init_mysql.sql` | `/docker-entrypoint-initdb.d/` | MySQL | Khởi tạo database + seed data |
| `./postgres/init_postgres.sql` | `/docker-entrypoint-initdb.d/` | PostgreSQL | Khởi tạo database + seed data |
| `./kong/kong.yml` | `/etc/kong/kong.yml` | Kong | Declarative config |
| `mysql_data` (named) | `/var/lib/mysql` | MySQL | Persistent data |
| `postgres_data` (named) | `/var/lib/postgresql/data` | PostgreSQL | Persistent data |
| `rabbitmq_data` (named) | `/var/lib/rabbitmq` | RabbitMQ | Persistent data |

---

## 7. Tóm Tắt Công Nghệ Theo Tầng

| Tầng | Công nghệ | Vai trò |
|---|---|---|
| **Presentation** | HTML, CSS, JavaScript, Chart.js, Inter Font | Dashboard UI (Dark mode, responsive) |
| **Security** | Kong Gateway 3.4, key-auth, rate-limiting, CORS | Reverse Proxy, Authentication, Throttling |
| **Application** | Python 3.11, FastAPI, Flask, Pydantic, pika | Business Logic, REST API, Message Publishing |
| **Messaging** | RabbitMQ 3 | Asynchronous order processing (durable queue) |
| **Data** | MySQL 8.0, PostgreSQL 15 | Web Store DB, Finance DB |
| **Infrastructure** | Docker Compose 3.9, bridge network | Container orchestration, service discovery |
