-- ─────────────────────────────────────────────────────────────────
-- NOAH Retail – PostgreSQL Init Script (Finance Database)
-- Database: noah_finance
-- ─────────────────────────────────────────────────────────────────

-- ── Bảng Khách Hàng ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    email      VARCHAR(255) UNIQUE,
    phone      VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Bảng Giao Dịch Tài Chính ────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id           SERIAL PRIMARY KEY,
    order_id     INT NOT NULL UNIQUE,
    user_id      INT NOT NULL,
    amount       BIGINT NOT NULL DEFAULT 0,
    product_id   INT NOT NULL,
    quantity     INT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note         TEXT
);

-- ── Index để tăng tốc query ─────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_order_id ON transactions(order_id);
CREATE INDEX IF NOT EXISTS idx_transactions_processed_at ON transactions(processed_at);

-- ── Dữ liệu khách hàng mẫu ─────────────────────────────────────
INSERT INTO customers (name, email, phone) VALUES
('Nguyễn Văn An', 'an.nguyen@email.com', '0901234567'),
('Trần Thị Bình', 'binh.tran@email.com', '0912345678'),
('Lê Quốc Cường', 'cuong.le@email.com', '0923456789'),
('Phạm Thị Dung', 'dung.pham@email.com', '0934567890'),
('Hoàng Văn Em', 'em.hoang@email.com', '0945678901'),
('Vũ Thị Phương', 'phuong.vu@email.com', '0956789012'),
('Đặng Minh Quân', 'quan.dang@email.com', '0967890123'),
('Bùi Thị Hoa', 'hoa.bui@email.com', '0978901234'),
('Đỗ Văn Hùng', 'hung.do@email.com', '0989012345'),
('Ngô Thị Lan', 'lan.ngo@email.com', '0990123456');
