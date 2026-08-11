-- schema.sql
-- Normalized relational schema for the digital payments analytics database.
-- Written in standard SQL; compatible with PostgreSQL and SQLite.

DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS merchants;

CREATE TABLE users (
    user_id            VARCHAR(10) PRIMARY KEY,
    city                VARCHAR(50) NOT NULL,
    signup_month_offset INTEGER NOT NULL,
    archetype           VARCHAR(30)
);

CREATE TABLE merchants (
    merchant_id     VARCHAR(10) PRIMARY KEY,
    merchant_name   VARCHAR(100) NOT NULL,
    category        VARCHAR(50) NOT NULL
);

CREATE TABLE transactions (
    txn_id       VARCHAR(10) PRIMARY KEY,
    user_id      VARCHAR(10) NOT NULL REFERENCES users(user_id),
    merchant_id  VARCHAR(10) NOT NULL REFERENCES merchants(merchant_id),
    category     VARCHAR(50) NOT NULL,
    amount       NUMERIC(10, 2) NOT NULL,
    txn_date     DATE NOT NULL,
    city         VARCHAR(50) NOT NULL,
    status       VARCHAR(10) NOT NULL
);

CREATE INDEX idx_txn_user ON transactions(user_id);
CREATE INDEX idx_txn_date ON transactions(txn_date);
CREATE INDEX idx_txn_category ON transactions(category);
