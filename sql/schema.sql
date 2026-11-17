PRAGMA foreign_keys = ON;
CREATE TABLE customers (customer_id TEXT PRIMARY KEY);
CREATE TABLE products (stock_code TEXT PRIMARY KEY, description TEXT NOT NULL);
CREATE TABLE invoice_lines (
    line_id INTEGER PRIMARY KEY,
    invoice_no TEXT NOT NULL,
    stock_code TEXT NOT NULL REFERENCES products(stock_code),
    customer_id TEXT REFERENCES customers(customer_id),
    invoice_date TEXT NOT NULL,
    country TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity != 0),
    unit_price REAL NOT NULL CHECK(unit_price > 0),
    is_cancellation INTEGER NOT NULL CHECK(is_cancellation IN (0, 1)),
    amount_pence INTEGER NOT NULL,
    CHECK ((is_cancellation = 0 AND amount_pence > 0) OR (is_cancellation = 1 AND amount_pence < 0))
);
CREATE INDEX idx_lines_customer_date ON invoice_lines(customer_id, invoice_date);
CREATE INDEX idx_lines_date ON invoice_lines(invoice_date);
CREATE INDEX idx_lines_product ON invoice_lines(stock_code);
CREATE VIEW purchases AS SELECT * FROM invoice_lines WHERE is_cancellation = 0;
