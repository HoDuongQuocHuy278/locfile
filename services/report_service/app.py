"""
app.py – Module 3: Report Service (Data Stitching)

Chức năng:
- Kết nối đồng thời MySQL (orders) và PostgreSQL (transactions)
- Data Stitching: merge 2 nguồn dữ liệu theo order_id
- Tính tổng doanh thu theo từng khách hàng
- Phân trang (Pagination): LIMIT/OFFSET
- Endpoint: GET /api/report, GET /api/products, GET /api/stats
"""

import os
import time
import logging
from datetime import datetime
import mysql.connector
from mysql.connector import Error as MySQLError
import psycopg2
from psycopg2 import OperationalError as PGError
from flask import Flask, jsonify, request
from flask_cors import CORS

# ─── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("report_service")

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

# ─── Flask App ─────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)


# ─── Retry Connections ─────────────────────────────────────────────
def get_mysql(max_retries=5, delay=5):
    for i in range(1, max_retries + 1):
        try:
            return mysql.connector.connect(
                host=MYSQL_HOST, port=MYSQL_PORT,
                database=MYSQL_DB, user=MYSQL_USER,
                password=MYSQL_PASSWORD, connection_timeout=10
            )
        except MySQLError as e:
            log.warning(f"MySQL retry {i}/{max_retries}: {e}")
            if i < max_retries: time.sleep(delay)
    raise MySQLError("Cannot connect to MySQL")


def get_postgres(max_retries=5, delay=5):
    for i in range(1, max_retries + 1):
        try:
            return psycopg2.connect(
                host=POSTGRES_HOST, port=POSTGRES_PORT,
                dbname=POSTGRES_DB, user=POSTGRES_USER,
                password=POSTGRES_PASSWORD, connect_timeout=10
            )
        except PGError as e:
            log.warning(f"PostgreSQL retry {i}/{max_retries}: {e}")
            if i < max_retries: time.sleep(delay)
    raise PGError("Cannot connect to PostgreSQL")


# ─── Endpoints ─────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def root():
    return jsonify({"service": "NOAH Report Service", "status": "running"})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/api/products", methods=["GET"])
def get_products():
    """Danh sách sản phẩm với tồn kho - có phân trang."""
    page  = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit

    conn   = None
    cursor = None
    try:
        conn   = get_mysql()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) as total FROM products")
        total = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT id, name, price, stock FROM products ORDER BY stock DESC LIMIT %s OFFSET %s",
            (limit, offset)
        )
        products = cursor.fetchall()

        for p in products:
            if p.get("price"): p["price"] = int(p["price"])

        return jsonify({
            "status": "success",
            "total":  total,
            "page":   page,
            "limit":  limit,
            "pages":  (total + limit - 1) // limit,
            "data":   products
        })
    except Exception as e:
        log.error(f"Lỗi /api/products: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


@app.route("/api/report", methods=["GET"])
def get_report():
    """
    Data Stitching: join MySQL orders với PostgreSQL transactions.
    Trả về đơn hàng đã đối soát (reconciled) và doanh thu theo user.
    """
    page  = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit

    mysql_conn = pg_conn = None
    try:
        # ── 1. Lấy dữ liệu từ MySQL ────────────────────────────────
        mysql_conn = get_mysql()
        mc = mysql_conn.cursor(dictionary=True)

        mc.execute("SELECT COUNT(*) as total FROM orders")
        total_orders = mc.fetchone()["total"]

        mc.execute(
            """SELECT o.id as order_id, o.user_id, o.product_id,
                      p.name as product_name, o.quantity,
                      o.total_price, o.status, o.created_at
               FROM orders o
               LEFT JOIN products p ON o.product_id = p.id
               ORDER BY o.id DESC
               LIMIT %s OFFSET %s""",
            (limit, offset)
        )
        orders = mc.fetchall()
        mc.close()

        # Chuyển datetime sang string
        order_ids = []
        for o in orders:
            if o.get("created_at"):
                o["created_at"] = o["created_at"].isoformat()
            if o.get("total_price"):
                o["total_price"] = int(o["total_price"])
            order_ids.append(o["order_id"])

        # ── 2. Lấy transactions từ PostgreSQL ──────────────────────
        pg_conn = get_postgres()
        pc = pg_conn.cursor()

        transactions_map = {}
        if order_ids:
            placeholders = ','.join(['%s'] * len(order_ids))
            pc.execute(
                f"""SELECT order_id, amount, processed_at
                    FROM transactions WHERE order_id IN ({placeholders})""",
                order_ids
            )
            for row in pc.fetchall():
                transactions_map[row[0]] = {
                    "amount":       int(row[1]),
                    "processed_at": row[2].isoformat() if row[2] else None
                }
        pc.close()

        # ── 3. Data Stitching: khâu 2 nguồn dữ liệu ───────────────
        for order in orders:
            oid = order["order_id"]
            if oid in transactions_map:
                order["synced"]       = True
                order["amount_paid"]  = transactions_map[oid]["amount"]
                order["processed_at"] = transactions_map[oid]["processed_at"]
            else:
                order["synced"]       = False
                order["amount_paid"]  = None
                order["processed_at"] = None

        # ── 4. Tổng doanh thu theo user_id ────────────────────────
        mc2 = mysql_conn.cursor(dictionary=True)
        mc2.execute(
            """SELECT o.user_id, SUM(t.amount) as revenue, COUNT(*) as order_count
               FROM orders o
               JOIN (
                   SELECT o2.id, o2.user_id, o2.total_price as amount
                   FROM orders o2 WHERE o2.status = 'COMPLETED'
               ) t ON t.id = o.id
               GROUP BY o.user_id
               ORDER BY revenue DESC
               LIMIT 10"""
        )
        top_customers = mc2.fetchall()
        mc2.close()

        for c in top_customers:
            if c.get("revenue"): c["revenue"] = int(c["revenue"])

        # ── 5. Thống kê tổng hợp ──────────────────────────────────
        mc3 = mysql_conn.cursor(dictionary=True)
        mc3.execute(
            """SELECT
               COUNT(*) as total_orders,
               SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) as pending,
               SUM(CASE WHEN status='COMPLETED' THEN total_price ELSE 0 END) as total_revenue
               FROM orders"""
        )
        stats = mc3.fetchone()
        mc3.close()

        if stats.get("total_revenue"): stats["total_revenue"] = int(stats["total_revenue"])

        log.info(f"[API] GET /api/report – page={page}, rows={len(orders)}")
        return jsonify({
            "status":        "success",
            "total_orders":  total_orders,
            "page":          page,
            "limit":         limit,
            "pages":         (total_orders + limit - 1) // limit,
            "stats":         stats,
            "top_customers": top_customers,
            "orders":        orders
        })

    except Exception as e:
        log.error(f"Lỗi /api/report: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if mysql_conn and mysql_conn.is_connected(): mysql_conn.close()
        if pg_conn: pg_conn.close()


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Thống kê nhanh cho Dashboard cards."""
    mysql_conn = pg_conn = None
    try:
        mysql_conn = get_mysql()
        mc = mysql_conn.cursor(dictionary=True)

        mc.execute(
            """SELECT
               COUNT(*) as total_orders,
               SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) as completed_orders,
               SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) as pending_orders,
               SUM(CASE WHEN status='COMPLETED' THEN total_price ELSE 0 END) as total_revenue,
               COUNT(DISTINCT user_id) as unique_customers
               FROM orders"""
        )
        order_stats = mc.fetchone()
        if order_stats.get("total_revenue"):
            order_stats["total_revenue"] = int(order_stats["total_revenue"])

        mc.execute("SELECT COUNT(*) as total_products, SUM(stock) as total_stock FROM products")
        product_stats = mc.fetchone()
        mc.close()

        pg_conn = get_postgres()
        pc = pg_conn.cursor()
        pc.execute("SELECT COUNT(*) FROM transactions")
        tx_count = pc.fetchone()[0]
        pc.close()

        return jsonify({
            "status":          "success",
            "orders":          order_stats,
            "products":        product_stats,
            "transactions":    tx_count
        })

    except Exception as e:
        log.error(f"Lỗi /api/stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if mysql_conn and mysql_conn.is_connected(): mysql_conn.close()
        if pg_conn: pg_conn.close()


if __name__ == "__main__":
    log.info("=" * 55)
    log.info(" NOAH RETAIL – REPORT SERVICE ĐÃ KHỞI ĐỘNG")
    log.info("=" * 55)
    app.run(host="0.0.0.0", port=5002, debug=False)
