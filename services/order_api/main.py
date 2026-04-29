"""
main.py – Module 2A: Order API (FastAPI Producer)

Endpoints:
  POST /api/orders  – Nhận đơn hàng, insert MySQL PENDING, publish RabbitMQ
  GET  /api/health  – Health check
  GET  /            – Status
"""

import os
import json
import time
import logging
from datetime import datetime
import mysql.connector
from mysql.connector import Error as MySQLError
import pika
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

# ─── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("order_api")

# ─── Config từ Environment ─────────────────────────────────────────
MYSQL_HOST     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT     = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DB       = os.getenv("MYSQL_DB", "noah_store")
MYSQL_USER     = os.getenv("MYSQL_USER", "noah")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "noah123")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "noah")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "noah123")
QUEUE_NAME    = "order_queue"

# ─── FastAPI App ───────────────────────────────────────────────────
app = FastAPI(title="NOAH Order API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic Model ────────────────────────────────────────────────
class OrderRequest(BaseModel):
    user_id:    int
    product_id: int
    quantity:   int

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity phải > 0")
        return v

    @field_validator("user_id", "product_id")
    @classmethod
    def id_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("ID phải > 0")
        return v


# ─── Retry MySQL Connection ────────────────────────────────────────
def get_mysql_connection(max_retries: int = 5, delay: int = 5):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST, port=MYSQL_PORT,
                database=MYSQL_DB, user=MYSQL_USER,
                password=MYSQL_PASSWORD, connection_timeout=10
            )
            return conn
        except MySQLError as e:
            last_err = e
            log.warning(f"MySQL retry {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(delay)
    raise last_err


# ─── Publish RabbitMQ ──────────────────────────────────────────────
def publish_to_queue(message: dict, max_retries: int = 3):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            params      = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                credentials=credentials,
                heartbeat=30,
                connection_attempts=3
            )
            connection = pika.BlockingConnection(params)
            channel    = connection.channel()

            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_publish(
                exchange='',
                routing_key=QUEUE_NAME,
                body=json.dumps(message, ensure_ascii=False),
                properties=pika.BasicProperties(delivery_mode=2)  # persistent
            )
            connection.close()
            log.info(f"✔ Published order #{message.get('order_id')} vào queue.")
            return True
        except Exception as e:
            last_err = e
            log.warning(f"RabbitMQ retry {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(3)
    log.error(f"Không thể publish vào RabbitMQ: {last_err}")
    raise last_err


# ─── Endpoints ─────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"service": "NOAH Order API", "status": "running", "version": "1.0.0"}


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/orders", status_code=202)
def create_order(order: OrderRequest):
    """
    Nhận đơn hàng → Check stock → Trừ stock atomic → Insert MySQL PENDING → Publish RabbitMQ → 202 Accepted
    """
    log.info(f"[ORDER] Nhận đơn hàng: user={order.user_id}, product={order.product_id}, qty={order.quantity}")

    conn   = None
    cursor = None
    try:
        # ── 1. Lấy thông tin sản phẩm ──
        conn   = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, price, stock FROM products WHERE id = %s", (order.product_id,))
        product = cursor.fetchone()

        if not product:
            raise HTTPException(status_code=404, detail=f"Sản phẩm {order.product_id} không tồn tại.")

        # ── 2. Kiểm tra tồn kho (Stock Check) ──
        if product["stock"] < order.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Không đủ tồn kho. Hiện có: {product['stock']}, yêu cầu: {order.quantity}"
            )

        # ── 3. Trừ stock ATOMIC (tránh overselling bằng WHERE lock) ──
        cursor.execute(
            "UPDATE products SET stock = stock - %s WHERE id = %s AND stock >= %s",
            (order.quantity, order.product_id, order.quantity)
        )
        if cursor.rowcount == 0:
            conn.rollback()
            raise HTTPException(
                status_code=400,
                detail="Tồn kho đã thay đổi. Vui lòng thử lại."
            )

        # ── 4. Insert đơn hàng với status PENDING ──
        total_price = product["price"] * order.quantity
        cursor.execute(
            """INSERT INTO orders (user_id, product_id, quantity, total_price, status, created_at)
               VALUES (%s, %s, %s, %s, 'PENDING', NOW())""",
            (order.user_id, order.product_id, order.quantity, total_price)
        )
        conn.commit()
        order_id = cursor.lastrowid
        log.info(f"✔ Insert đơn hàng #{order_id} vào MySQL (PENDING). Stock trừ {order.quantity}.")

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Lỗi MySQL: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi tạo đơn hàng: {str(e)}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    # ── 5. Publish vào RabbitMQ (không chờ worker xử lý) ──
    message = {
        "order_id":    order_id,
        "user_id":     order.user_id,
        "product_id":  order.product_id,
        "quantity":    order.quantity,
        "total_price": int(total_price),
        "product_name": product["name"],
        "created_at":  datetime.now().isoformat()
    }

    try:
        publish_to_queue(message)
    except Exception as e:
        log.error(f"Lỗi publish RabbitMQ (đơn hàng vẫn đã lưu): {e}")
        # Đơn hàng đã được lưu MySQL, chỉ log lỗi queue

    # ── 6. Trả về ngay lập tức ──
    return {
        "message":  "Order received",
        "order_id": order_id,
        "status":   "PENDING",
        "total":    int(total_price),
        "product":  product["name"]
    }


@app.get("/api/orders")
def list_orders(page: int = 1, limit: int = 20):
    """Lấy danh sách đơn hàng có phân trang."""
    offset = (page - 1) * limit
    conn   = None
    cursor = None
    try:
        conn   = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) as total FROM orders")
        total = cursor.fetchone()["total"]

        cursor.execute(
            """SELECT o.id, o.user_id, o.product_id, p.name as product_name,
                      o.quantity, o.total_price, o.status, o.created_at
               FROM orders o
               LEFT JOIN products p ON o.product_id = p.id
               ORDER BY o.id DESC
               LIMIT %s OFFSET %s""",
            (limit, offset)
        )
        orders = cursor.fetchall()

        for o in orders:
            if o.get("created_at"):
                o["created_at"] = o["created_at"].isoformat()
            if o.get("total_price"):
                o["total_price"] = int(o["total_price"])

        return {
            "status": "success",
            "total":  total,
            "page":   page,
            "limit":  limit,
            "pages":  (total + limit - 1) // limit,
            "data":   orders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
