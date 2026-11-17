-- 1. Monthly merchandise value and true month-over-month gross sales growth.
WITH monthly AS (
    SELECT strftime('%Y-%m', invoice_date) AS month,
           SUM(CASE WHEN is_cancellation=0 THEN amount_pence ELSE 0 END)/100.0 AS gross_sales_gbp,
           -SUM(CASE WHEN is_cancellation=1 THEN amount_pence ELSE 0 END)/100.0 AS cancellation_value_gbp,
           SUM(amount_pence)/100.0 AS net_recorded_value_gbp
    FROM invoice_lines GROUP BY month
), lagged AS (
    SELECT *, LAG(gross_sales_gbp) OVER (ORDER BY month) AS previous_month_gbp FROM monthly
)
SELECT *, 100.0*(gross_sales_gbp-previous_month_gbp)/NULLIF(previous_month_gbp,0) AS mom_growth_pct
FROM lagged ORDER BY month;

-- 2. Country sales and distinct purchasing customers. Anonymous sales are included.
SELECT country, COUNT(DISTINCT customer_id) AS known_customers,
       COUNT(DISTINCT invoice_no) AS purchase_invoices, SUM(amount_pence)/100.0 AS gross_sales_gbp
FROM purchases GROUP BY country ORDER BY gross_sales_gbp DESC;

-- 3. Product sales, no invented merchant or category labels.
SELECT p.stock_code, p.description, SUM(l.quantity) AS units,
       SUM(l.amount_pence)/100.0 AS gross_sales_gbp
FROM purchases l JOIN products p USING(stock_code)
GROUP BY p.stock_code, p.description ORDER BY gross_sales_gbp DESC LIMIT 20;

-- 4. Cancellation invoice share (not a payment-failure or matched return rate).
SELECT country, COUNT(DISTINCT invoice_no) AS recorded_invoices,
       COUNT(DISTINCT CASE WHEN is_cancellation=1 THEN invoice_no END) AS cancellation_invoices,
       100.0*COUNT(DISTINCT CASE WHEN is_cancellation=1 THEN invoice_no END)/COUNT(DISTINCT invoice_no) AS cancellation_invoice_share_pct
FROM invoice_lines GROUP BY country HAVING COUNT(DISTINCT invoice_no)>=30
ORDER BY cancellation_invoice_share_pct DESC;

-- 5. Actual adjacent-month customer retention among known purchasing customers.
WITH activity AS (
 SELECT DISTINCT customer_id, date(invoice_date,'start of month') AS month
 FROM purchases WHERE customer_id IS NOT NULL
), boundary AS (SELECT MAX(month) AS last_month FROM activity)
SELECT a.month, COUNT(*) AS active_customers, COUNT(b.customer_id) AS next_month_returners,
       100.0*COUNT(b.customer_id)/COUNT(*) AS next_month_retention_pct
FROM activity a LEFT JOIN activity b
 ON a.customer_id=b.customer_id AND b.month=date(a.month,'+1 month')
WHERE a.month < (SELECT last_month FROM boundary)
GROUP BY a.month ORDER BY a.month;
-- First/last calendar months can be partial, consult coverage before interpretation.

-- 6. Cohort retention grid using first observed purchase, not signup.
WITH activity AS (
 SELECT DISTINCT customer_id, date(invoice_date,'start of month') AS month
 FROM purchases WHERE customer_id IS NOT NULL
), cohorts AS (
 SELECT customer_id, MIN(month) AS cohort_month FROM activity GROUP BY customer_id
), sizes AS (
 SELECT cohort_month, COUNT(*) AS cohort_size FROM cohorts GROUP BY cohort_month
)
SELECT c.cohort_month, a.month AS activity_month,
       (CAST(strftime('%Y',a.month) AS INTEGER)-CAST(strftime('%Y',c.cohort_month) AS INTEGER))*12
       +CAST(strftime('%m',a.month) AS INTEGER)-CAST(strftime('%m',c.cohort_month) AS INTEGER) AS months_since_first_purchase,
       COUNT(*) AS active_customers, s.cohort_size,
       100.0*COUNT(*)/s.cohort_size AS retention_pct
FROM activity a JOIN cohorts c USING(customer_id) JOIN sizes s USING(cohort_month)
GROUP BY c.cohort_month,a.month ORDER BY c.cohort_month,a.month;

-- 7. Anonymous coverage: missing IDs are excluded from RFM, not total sales.
SELECT COUNT(*) AS purchase_lines,
       SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS anonymous_purchase_lines,
       SUM(CASE WHEN customer_id IS NULL THEN amount_pence ELSE 0 END)/100.0 AS anonymous_sales_gbp
FROM purchases;
