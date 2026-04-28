"""
logger.py – Module logging trung tâm cho toàn hệ thống.
Ghi log cả ra console (INFO) và file logs/system.log (DEBUG).
"""
import logging
import os

# Tạo thư mục logs nếu chưa có
os.makedirs("logs", exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    """
    Trả về logger đã được cấu hình cho module được chỉ định.
    Tránh thêm handler trùng nếu logger đã được khởi tạo trước đó.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Đã được cấu hình, không thêm handler trùng

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler ghi ra file
    file_handler = logging.FileHandler("logs/system.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Handler ghi ra console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
