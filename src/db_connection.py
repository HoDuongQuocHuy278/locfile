"""
db_connection.py – Kết nối MySQL với cơ chế retry tự động.

Thử kết nối tối đa MAX_RETRIES lần trước khi báo lỗi.
"""

import time
import mysql.connector
from mysql.connector import Error
from src.logger import get_logger

log = get_logger("db_connection")

DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "",
    "database": "mydb",
}

MAX_RETRIES = 3
RETRY_DELAY = 2  # giây


def get_connection():
    """
    Trả về kết nối MySQL. Tự động thử lại tối đa MAX_RETRIES lần
    nếu kết nối thất bại.

    Raises:
        mysql.connector.Error: nếu vẫn thất bại sau tất cả lần thử.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if attempt > 1:
                log.info(f"Kết nối MySQL thành công (lần thử {attempt}).")
            return conn
        except Error as e:
            last_error = e
            log.warning(
                f"Kết nối MySQL thất bại (lần {attempt}/{MAX_RETRIES}): {e}. "
                f"Thử lại sau {RETRY_DELAY}s..."
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    log.error(f"Không thể kết nối MySQL sau {MAX_RETRIES} lần thử.")
    raise last_error