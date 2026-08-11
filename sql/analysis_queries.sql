-- analysis_queries.sql
-- Core business-analytics queries demonstrating SQL proficiency on
-- multi-dimensional transactional data.

-- 1. Month-over-month revenue and transaction volume trend
SELECT
    strftime('%Y-%m', txn_date) AS month,
    COUNT(*) AS total_txns,
    SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END) AS total_revenue,
    ROUND(100.0 * SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS failure_rate_pct
FROM transactions
GROUP BY month
ORDER BY month;

-- 2. Category-wise contribution to revenue
SELECT
    category,
    COUNT(*) AS txn_count,
    SUM(amount) AS total_revenue,
    ROUND(AVG(amount), 2) AS avg_txn_value,
    ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM transactions WHERE status='SUCCESS'), 2) AS pct_of_total_revenue
FROM transactions
WHERE status = 'SUCCESS'
GROUP BY category
ORDER BY total_revenue DESC;

-- 3. Top 10 cities by revenue and average transaction value
SELECT
    city,
    COUNT(DISTINCT user_id) AS active_users,
    SUM(amount) AS total_revenue,
    ROUND(SUM(amount) / COUNT(DISTINCT user_id), 2) AS revenue_per_user
FROM transactions
WHERE status = 'SUCCESS'
GROUP BY city
ORDER BY total_revenue DESC
LIMIT 10;

-- 4. Monthly active users and retention proxy (users active in consecutive months)
SELECT
    strftime('%Y-%m', txn_date) AS month,
    COUNT(DISTINCT user_id) AS monthly_active_users
FROM transactions
WHERE status = 'SUCCESS'
GROUP BY month
ORDER BY month;

-- 5. Top merchants by revenue (identifying high-value partners)
SELECT
    m.merchant_name,
    m.category,
    COUNT(*) AS txn_count,
    SUM(t.amount) AS total_revenue
FROM transactions t
JOIN merchants m ON t.merchant_id = m.merchant_id
WHERE t.status = 'SUCCESS'
GROUP BY m.merchant_id
ORDER BY total_revenue DESC
LIMIT 10;

-- 6. Payment failure hotspots — categories/cities with elevated failure rates
-- (useful for flagging reliability issues to stakeholders)
SELECT
    category,
    city,
    COUNT(*) AS total_txns,
    ROUND(100.0 * SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS failure_rate_pct
FROM transactions
GROUP BY category, city
HAVING COUNT(*) > 30
ORDER BY failure_rate_pct DESC
LIMIT 10;

-- 7. RFM base query — Recency, Frequency, Monetary value per user
-- (feeds directly into the Python segmentation step)
SELECT
    user_id,
    JULIANDAY((SELECT MAX(txn_date) FROM transactions)) - JULIANDAY(MAX(txn_date)) AS recency_days,
    COUNT(*) AS frequency,
    SUM(amount) AS monetary
FROM transactions
WHERE status = 'SUCCESS'
GROUP BY user_id;
