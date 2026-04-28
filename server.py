"""
server.py – NOAH Retail Unified Commerce – Local Development Server

Chế độ LOCAL: Chạy trực tiếp không cần Docker.
Cung cấp tất cả API mà Dashboard cần, kết nối MySQL cục bộ (mydb).

Endpoints gốc (tương thích cũ):
    POST /setup         – Khởi tạo database từ init.sql
    POST /clean         – Module 1: làm sạch inventory.csv
    POST /import        – Module 2: nạp dữ liệu vào MySQL
    GET  /products      – Top 20 sản phẩm (backward compat)

Endpoints mới – NOAH Dashboard:
    GET  /report/api/stats      – Thống kê tổng hợp
    GET  /report/api/report     – Đơn hàng + data stitching
    GET  /report/api/products   – Tồn kho sản phẩm (phân trang)
    POST /orders/api/orders     – Tạo đơn hàng mới
    GET  /orders/api/orders     – Danh sách đơn hàng (phân trang)
    GET  /api/health            – Health check
"""

import os
import time
import logging
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
import mysql.connector
from mysql.connector import Error as MySQLError

# ── Cấu hình logging ──
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("server")

app = Flask(__name__)

# ─── CORS ──────────────────────────────────────────────────────────
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,apikey"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp

@app.route("/<path:path>", methods=["OPTIONS"])
def options_preflight(path):
    return jsonify({}), 200

# ─── MySQL Local Config ────────────────────────────────────────────
# Tự động thử cả database 'mydb' (cũ) và 'noah_store' (mới)
def get_db(db_name: str = None):
    """Retry MySQL connection 3 lần."""
    cfg = {
        "host":     os.getenv("MYSQL_HOST", "localhost"),
        "user":     os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": db_name or os.getenv("MYSQL_DB", "mydb"),
    }
    last_err = None
    for i in range(3):
        try:
            return mysql.connector.connect(**cfg)
        except MySQLError as e:
            last_err = e
            if e.errno == 1045 and cfg["user"] != "root":
                log.warning("[DB] Access denied. Thử lại bằng root (XAMPP mặc định).")
                cfg["user"] = "root"
                cfg["password"] = ""
                try:
                    return mysql.connector.connect(**cfg)
                except Exception:
                    pass
            if i < 2:
                time.sleep(2)
    raise last_err

# ─── Fake transactions (giả lập PostgreSQL khi chạy local) ────────
# order_id → {"amount": int, "processed_at": str}
fake_tx: dict = {}

# ══════════════════════════════════════════════════════════════════
# ROUTES CŨ – Đã được gỡ bỏ (hệ thống thay thế bằng Legacy Adapter / Docker)
# ══════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    dashboard_dir = os.path.join(os.getcwd(), "giao diện")
    return send_from_directory(dashboard_dir, "Dashboard.html")

@app.route("/status", methods=["GET"])
def route_status():
    return jsonify({"status": "running", "mode": "local server"}), 200


# ══════════════════════════════════════════════════════════════════
# ROUTES MỚI – NOAH Dashboard API (mô phỏng Kong Gateway locally)
# ══════════════════════════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
@app.route("/report/api/health", methods=["GET"])
@app.route("/orders/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "mode": "local", "timestamp": datetime.now().isoformat()})


# ─── GET /report/api/stats – Thống kê tổng hợp ────────────────────
@app.route("/report/api/stats", methods=["GET"])
def api_stats():
    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        # Tự động detect tên database
        cursor.execute("SHOW DATABASES LIKE 'noah_store'")
        if cursor.fetchone():
            cursor.execute("USE noah_store")
        else:
            cursor.execute("USE mydb")

        # Thống kê orders
        cursor.execute(
            """SELECT
               COUNT(*) as total_orders,
               SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) as completed_orders,
               SUM(CASE WHEN status='PENDING'   THEN 1 ELSE 0 END) as pending_orders,
               SUM(CASE WHEN status='COMPLETED' THEN total_price ELSE 0 END) as total_revenue,
               COUNT(DISTINCT user_id) as unique_customers
               FROM orders"""
        )
        order_stats = cursor.fetchone() or {}
        if order_stats.get("total_revenue"):
            order_stats["total_revenue"] = int(order_stats["total_revenue"])

        # Thống kê products
        cursor.execute("SELECT COUNT(*) as total_products, SUM(stock) as total_stock FROM products")
        product_stats = cursor.fetchone() or {}

        cursor.close()
        conn.close()

        log.info("[API] GET /report/api/stats – OK")
        return jsonify({
            "status":       "success",
            "orders":       order_stats,
            "products":     product_stats,
            "transactions": len(fake_tx),   # fake PostgreSQL count
        })
    except Exception as e:
        log.error(f"[API] /report/api/stats lỗi: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── GET /report/api/products – Sản phẩm (phân trang) ─────────────
@app.route("/report/api/products", methods=["GET"])
def api_products_paged():
    page  = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit

    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SHOW DATABASES LIKE 'noah_store'")
        if cursor.fetchone():
            cursor.execute("USE noah_store")
        else:
            cursor.execute("USE mydb")

        cursor.execute("SELECT COUNT(*) as total FROM products")
        total = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT id, name, price, stock FROM products ORDER BY stock DESC LIMIT %s OFFSET %s",
            (limit, offset)
        )
        products = cursor.fetchall()
        for p in products:
            if p.get("price"): p["price"] = int(p["price"])

        cursor.close()
        conn.close()
        return jsonify({
            "status": "success",
            "total":  total,
            "page":   page,
            "limit":  limit,
            "pages":  max(1, (total + limit - 1) // limit),
            "data":   products,
        })
    except Exception as e:
        log.error(f"[API] /report/api/products lỗi: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── GET /report/api/report – Data Stitching ──────────────────────
@app.route("/report/api/report", methods=["GET"])
def api_report():
    page  = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit

    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SHOW DATABASES LIKE 'noah_store'")
        if cursor.fetchone():
            cursor.execute("USE noah_store")
        else:
            cursor.execute("USE mydb")

        cursor.execute("SELECT COUNT(*) as total FROM orders")
        total_orders = cursor.fetchone()["total"]

        cursor.execute(
            """SELECT o.id as order_id, o.user_id, o.product_id,
                      COALESCE(p.name, CONCAT('Product ',o.product_id)) as product_name,
                      o.quantity, o.total_price, o.status, o.created_at
               FROM orders o
               LEFT JOIN products p ON o.product_id = p.id
               ORDER BY o.id DESC
               LIMIT %s OFFSET %s""",
            (limit, offset)
        )
        orders = cursor.fetchall()

        # Tổng doanh thu theo user
        cursor.execute(
            """SELECT user_id,
                      SUM(total_price) as revenue,
                      COUNT(*) as order_count
               FROM orders
               WHERE status='COMPLETED'
               GROUP BY user_id
               ORDER BY revenue DESC
               LIMIT 10"""
        )
        top_customers = cursor.fetchall()
        for c in top_customers:
            if c.get("revenue"): c["revenue"] = int(c["revenue"])

        # Stats tổng hợp
        cursor.execute(
            """SELECT COUNT(*) total_orders,
                      SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) completed,
                      SUM(CASE WHEN status='PENDING'   THEN 1 ELSE 0 END) pending,
                      SUM(CASE WHEN status='COMPLETED' THEN total_price ELSE 0 END) total_revenue
               FROM orders"""
        )
        stats = cursor.fetchone() or {}
        if stats.get("total_revenue"): stats["total_revenue"] = int(stats["total_revenue"])

        cursor.close()
        conn.close()

        # ── Data Stitching: merge với fake_tx (giả lập PostgreSQL) ──
        for o in orders:
            if o.get("created_at"):
                o["created_at"] = o["created_at"].isoformat()
            if o.get("total_price"):
                o["total_price"] = int(o["total_price"])

            oid = o["order_id"]
            if oid in fake_tx:
                o["synced"]       = True
                o["amount_paid"]  = fake_tx[oid]["amount"]
                o["processed_at"] = fake_tx[oid]["processed_at"]
            elif o["status"] == "COMPLETED":
                # Đơn hàng COMPLETED trong DB gốc → coi như đã sync
                o["synced"]       = True
                o["amount_paid"]  = o["total_price"]
                o["processed_at"] = o["created_at"]
            else:
                o["synced"]       = False
                o["amount_paid"]  = None
                o["processed_at"] = None

        log.info(f"[API] GET /report/api/report page={page} – {len(orders)} orders")
        return jsonify({
            "status":        "success",
            "total_orders":  total_orders,
            "page":          page,
            "limit":         limit,
            "pages":         max(1, (total_orders + limit - 1) // limit),
            "stats":         stats,
            "top_customers": top_customers,
            "orders":        orders,
        })
    except Exception as e:
        log.error(f"[API] /report/api/report lỗi: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── POST /orders/api/orders – Tạo đơn hàng ──────────────────────
@app.route("/orders/api/orders", methods=["POST"])
def api_create_order():
    data = request.get_json(force=True, silent=True) or {}
    user_id    = data.get("user_id")
    product_id = data.get("product_id")
    quantity   = data.get("quantity")

    if not all([user_id, product_id, quantity]) or int(quantity) <= 0:
        return jsonify({"status": "error", "message": "Dữ liệu không hợp lệ (quantity phải > 0)"}), 400

    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SHOW DATABASES LIKE 'noah_store'")
        if cursor.fetchone():
            cursor.execute("USE noah_store")
        else:
            cursor.execute("USE mydb")

        cursor.execute("SELECT id, name, price FROM products WHERE id = %s", (int(product_id),))
        product = cursor.fetchone()
        if not product:
            cursor.close(); conn.close()
            return jsonify({"status": "error", "message": f"Sản phẩm {product_id} không tồn tại"}), 404

        total_price = int(product["price"]) * int(quantity)
        cursor.execute(
            """INSERT INTO orders (user_id, product_id, quantity, total_price, status, created_at)
               VALUES (%s, %s, %s, %s, 'PENDING', NOW())""",
            (int(user_id), int(product_id), int(quantity), total_price)
        )
        conn.commit()
        order_id = cursor.lastrowid

        # Giả lập Worker xử lý: update trạng thái COMPLETED + fake transaction
        cursor.execute("UPDATE orders SET status='COMPLETED' WHERE id=%s", (order_id,))
        conn.commit()
        fake_tx[order_id] = {
            "amount":       total_price,
            "processed_at": datetime.now().isoformat()
        }

        cursor.close()
        conn.close()

        log.info(f"[API] POST /orders/api/orders → order #{order_id} (COMPLETED, local mode)")
        return jsonify({
            "message":  "Order received",
            "order_id": order_id,
            "status":   "PENDING",
            "total":    total_price,
            "product":  product["name"],
        }), 202

    except Exception as e:
        log.error(f"[API] /orders/api/orders lỗi: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── GET /orders/api/orders – Danh sách đơn hàng ─────────────────
@app.route("/orders/api/orders", methods=["GET"])
def api_list_orders():
    page  = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit

    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SHOW DATABASES LIKE 'noah_store'")
        if cursor.fetchone():
            cursor.execute("USE noah_store")
        else:
            cursor.execute("USE mydb")

        cursor.execute("SELECT COUNT(*) as total FROM orders")
        total = cursor.fetchone()["total"]

        cursor.execute(
            """SELECT o.id as order_id, o.user_id, o.product_id,
                      COALESCE(p.name, CONCAT('Product ',o.product_id)) as product_name,
                      o.quantity, o.total_price, o.status, o.created_at
               FROM orders o
               LEFT JOIN products p ON o.product_id = p.id
               ORDER BY o.id DESC LIMIT %s OFFSET %s""",
            (limit, offset)
        )
        orders = cursor.fetchall()
        cursor.close()
        conn.close()

        for o in orders:
            if o.get("created_at"): o["created_at"] = o["created_at"].isoformat()
            if o.get("total_price"): o["total_price"] = int(o["total_price"])

        return jsonify({
            "status": "success",
            "total":  total,
            "page":   page,
            "limit":  limit,
            "pages":  max(1, (total + limit - 1) // limit),
            "data":   orders,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = 8000
    log.info("=" * 55)
    log.info(" NOAH RETAIL – LOCAL SERVER ĐANG CHẠY")
    log.info(f" URL: http://localhost:{port}")
    log.info(" Endpoints Dashboard:")
    log.info(f"   GET  http://localhost:{port}/report/api/stats")
    log.info(f"   GET  http://localhost:{port}/report/api/report")
    log.info(f"   GET  http://localhost:{port}/report/api/products")
    log.info(f"   POST http://localhost:{port}/orders/api/orders")
    log.info(" Endpoints cũ (compatible):")
    log.info(f"   POST http://localhost:{port}/setup")
    log.info(f"   POST http://localhost:{port}/clean  →  /import")
    log.info(f"   GET  http://localhost:{port}/products")
    log.info(" (Bấm Ctrl+C để tắt)")
    log.info("=" * 55)
    app.run(host="0.0.0.0", port=port, debug=False)
