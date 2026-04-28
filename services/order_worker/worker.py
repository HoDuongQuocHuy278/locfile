"""
worker.py – Module 2B: Order Worker (RabbitMQ Consumer)

Chức năng:
- Lắng nghe liên tục queue 'order_queue'
- Giả lập xử lý thanh toán (sleep 1-2s)
- INSERT vào PostgreSQL (transactions)
- UPDATE MySQL: PENDING → COMPLETED
- Manual ACK sau khi xử lý xong (đảm bảo không mất message)
"""

import os
import json
import time
import random
import logging
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import Error as MySQLError
import psycopg2
from psycopg2 import OperationalError as PGError
import pika

# ─── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("order_worker")

# ─── Config ────────────────────────────────────────────────────────
MYSQL_HOST     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT     = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DB       = os.getenv("MYSQL_DB", "noah_store")
MYSQL_USER     = os.getenv("MYSQL_USER", "noah")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "noah123")

POSTGRES_HOST     = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT     = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB       = os.getenv("POSTGRES_DB", "noah_finance")
POSTGRES_USER     = os.getenv("POSTGRES_USER", "noah")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "noah123")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "noah")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "noah123")
QUEUE_NAME    = "order_queue"


# ─── Retry Connections ─────────────────────────────────────────────
def retry_mysql(max_retries=5, delay=5):
    for attempt in range(1, max_retries + 1):
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST, port=MYSQL_PORT,
                database=MYSQL_DB, user=MYSQL_USER,
                password=MYSQL_PASSWORD, connection_timeout=10
            )
            return conn
        except MySQLError as e:
            log.warning(f"MySQL retry {attempt}/{max_retries}: {e}")
            if attempt < max_retries: time.sleep(delay)
    raise MySQLError("Cannot connect to MySQL")


def retry_postgres(max_retries=5, delay=5):
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST, port=POSTGRES_PORT,
                dbname=POSTGRES_DB, user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                connect_timeout=10
            )
            return conn
        except PGError as e:
            log.warning(f"PostgreSQL retry {attempt}/{max_retries}: {e}")
            if attempt < max_retries: time.sleep(delay)
    raise PGError("Cannot connect to PostgreSQL")


def retry_rabbitmq(max_retries=10, delay=5):
    for attempt in range(1, max_retries + 1):
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            params      = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
                connection_attempts=3
            )
            connection = pika.BlockingConnection(params)
            return connection
        except Exception as e:
            log.warning(f"RabbitMQ retry {attempt}/{max_retries}: {e}")
            if attempt < max_retries: time.sleep(delay)
    raise Exception("Cannot connect to RabbitMQ")


def send_async_notification(user_id, order_id, total, processed_time):
    """
    OPTION 1 (Bonus): Notification System.
    Gửi thông báo bất đồng bộ (Fire-and-Forget) qua luồng phụ để không treo Worker.
    Tạo độ trễ giả lập gửi Email/Telegram.
    """
    time.sleep(1) # Giả lập I/O delay của SMTP/Telegram API
    log.info(f"{'─'*45}")
    log.info(f"[THÔNG BÁO TỚI KHÁCH HÀNG] ✉️")
    log.info(f"Xin chào User {user_id}, đơn hàng #{order_id} trị giá {int(total):,}đ đã được xác nhận thanh toán thành công lúc {processed_time}.")
    log.info(f"{'─'*45}")

# ─── Xử Lý Message ────────────────────────────────────────────────
def process_order(ch, method, properties, body):
    """
    Callback khi nhận được message từ RabbitMQ.
    """
    try:
        order = json.loads(body)
        order_id    = order.get("order_id")
        user_id     = order.get("user_id")
        product_id  = order.get("product_id")
        quantity    = order.get("quantity")
        total_price = order.get("total_price", 0)

        log.info(f"{'─'*45}")
        log.info(f"[WORKER] Nhận đơn hàng #{order_id} | User: {user_id} | Sản phẩm: {product_id} | Qty: {quantity}")

        # ── Bước 1: Giả lập xử lý thanh toán ──────────────────────
        delay = random.uniform(1, 2)
        log.info(f"[WORKER] Đang xử lý thanh toán... ({delay:.1f}s)")
        time.sleep(delay)

        # ── Bước 2: INSERT vào PostgreSQL (Finance) ─────────────────
        pg_conn   = retry_postgres(max_retries=3)
        pg_cursor = pg_conn.cursor()
        try:
            pg_cursor.execute(
                """INSERT INTO transactions (order_id, user_id, amount, product_id, quantity, processed_at, note)
                   VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                   ON CONFLICT (order_id) DO NOTHING""",
                (order_id, user_id, total_price, product_id, quantity,
                 f"Xử lý bởi Order Worker lúc {datetime.now().strftime('%H:%M:%S')}")
            )
            pg_conn.commit()
            log.info(f"[WORKER] ✔ INSERT vào PostgreSQL (transactions) thành công.")
        except Exception as e:
            pg_conn.rollback()
            log.error(f"[WORKER] Lỗi PostgreSQL: {e}")
            raise
        finally:
            pg_cursor.close()
            pg_conn.close()

        # ── Bước 3: UPDATE MySQL PENDING → COMPLETED ───────────────
        mysql_conn   = retry_mysql(max_retries=3)
        mysql_cursor = mysql_conn.cursor()
        try:
            mysql_cursor.execute(
                "UPDATE orders SET status = 'COMPLETED' WHERE id = %s AND status = 'PENDING'",
                (order_id,)
            )
            mysql_conn.commit()
            log.info(f"[WORKER] ✔ UPDATE MySQL orders #{order_id}: PENDING → COMPLETED.")
        except Exception as e:
            mysql_conn.rollback()
            log.error(f"[WORKER] Lỗi MySQL UPDATE: {e}")
            raise
        finally:
            mysql_cursor.close()
            mysql_conn.close()

        # ── Bước 4: ACK – xác nhận xử lý xong ─────────────────────
        ch.basic_ack(delivery_tag=method.delivery_tag)
        log.info(f"[INFO] Order #{order_id} synced. Processing complete.")

        # ── Bước 5: Gửi thông báo bất đồng bộ (Option 1) ──────────
        process_time_str = datetime.now().strftime('%H:%M:%S')
        threading.Thread(
            target=send_async_notification, 
            args=(user_id, order_id, total_price, process_time_str),
            daemon=True
        ).start()
        log.info(f"[INFO] Triggered background async notification for Order #{order_id}.")

    except Exception as e:
        log.error(f"[WORKER] Lỗi xử lý message: {e}")
        # NACK với requeue=True để message quay lại queue
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# ─── Main Loop ─────────────────────────────────────────────────────
def main():
    log.info("=" * 55)
    log.info(" NOAH RETAIL – ORDER WORKER ĐÃ KHỞI ĐỘNG")
    log.info(f" Queue: {QUEUE_NAME}")
    log.info("=" * 55)

    # Chờ tất cả services sẵn sàng
    log.info("Đang chờ MySQL, PostgreSQL, RabbitMQ sẵn sàng...")
    time.sleep(5)  # Initial delay

    while True:
        try:
            connection = retry_rabbitmq()
            channel    = connection.channel()

            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)  # Chỉ lấy 1 message mỗi lần

            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=process_order,
                auto_ack=False  # Manual ACK
            )

            log.info(f"✔ Đang lắng nghe queue '{QUEUE_NAME}'. Nhấn Ctrl+C để dừng.")
            channel.start_consuming()

        except KeyboardInterrupt:
            log.info("Worker dừng theo yêu cầu.")
            break
        except Exception as e:
            log.error(f"Mất kết nối RabbitMQ: {e}. Kết nối lại sau 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()
