# TransactIQ — Digital Payments Transaction Analytics & Customer Segmentation

An end-to-end analytics project simulating a digital payments platform's transaction
data, built to answer the kind of business questions a data/analytics team is asked
daily: *Where is revenue coming from? Which customers matter most? What's coming next?*

The project combines **SQL-driven analysis**, **customer segmentation**, and
**revenue forecasting** on a ~79,000-row multi-dimensional transactional dataset
(2,000 users, 150 merchants, 12 months, 9 spend categories, 10 cities).

## Why this project

Digital payments companies operate on transaction-scale data and need to constantly:
1. Track revenue and growth trends across time, geography, and category
2. Identify which customer segments drive the business, and which are at risk
3. Forecast near-term revenue to inform planning

This project builds all three capabilities from raw transaction data to
stakeholder-ready insight.

## Key Business Insights

- **Revenue is Pareto-distributed across customers**: the top ~6% of users
  (High-Value Loyalists — high frequency, high spend, active very recently)
  generate **36% of total revenue**, while the bottom ~3% (At-Risk/Dormant —
  inactive for 150+ days on average) contribute virtually nothing. This is a
  direct case for a retention/loyalty intervention targeted at the high-value
  segment before they churn, and a re-engagement campaign for the dormant one.
- **Revenue grew ~17x over 12 months** (₹4.3L → ₹72L monthly), with visible
  seasonal spikes in festive months. A linear trend forecast projects
  **~24% revenue growth over the next 3 months**, which can feed directly into
  capacity and business planning.
- **Category concentration**: a small number of categories account for a
  disproportionate share of revenue — useful for merchant partnership
  prioritization (see `sql/analysis_queries.sql`, query 2).
- **Failure-rate hotspots** exist in specific category-city combinations,
  flagging a reliability issue worth investigating with the payments/infra team
  (query 6) — the kind of cross-functional, first-principles problem this role
  is explicitly built around.

## Tech Stack

- **SQL** (SQLite, portable to PostgreSQL) — schema design, joins, aggregations, window-style analysis
- **Python** — Pandas/NumPy for data processing
- **scikit-learn** — K-Means clustering for RFM-based customer segmentation
- **Linear regression** — revenue forecasting with confidence intervals
- **Matplotlib** — static visualizations
- **Streamlit** — interactive dashboard

## Project Structure

```
TransactIQ/
├── data/
│   ├── generate_data.py       # synthetic data generator (users, merchants, transactions)
│   ├── users.csv
│   ├── merchants.csv
│   ├── transactions.csv
│   └── customer_segments.csv  # output of segmentation.py
├── sql/
│   ├── schema.sql             # normalized relational schema
│   └── analysis_queries.sql   # 7 business-analytics queries
├── src/
│   ├── load_to_db.py          # loads CSVs into SQLite using schema.sql
│   ├── segmentation.py        # RFM feature extraction + K-Means clustering
│   ├── forecasting.py         # revenue trend forecasting
│   └── dashboard.py           # Streamlit dashboard
├── visuals/
│   ├── customer_segments.png
│   └── revenue_forecast.png
└── README.md
```

## How It Works

### 1. Data Layer (SQL)
`sql/schema.sql` defines a normalized 3-table schema (`users`, `merchants`,
`transactions`) with foreign keys and indexes on the columns queries actually
filter/join on. `sql/analysis_queries.sql` contains 7 standalone business
queries — monthly revenue trend, category contribution, city-level performance,
monthly active users, top merchants, failure-rate hotspots, and the RFM base
query that feeds the segmentation step.

### 2. Customer Segmentation (RFM + K-Means)
`src/segmentation.py` pulls per-user **Recency, Frequency, Monetary** metrics
directly via SQL, scales them, and clusters users with K-Means. Clusters are
labeled using explicit business rules on their centroids (not just a generic
rank) — e.g. a cluster is only called "At-Risk/Dormant" if its average recency
is *both* above the median and more than 30 days, so the label actually means
what it says rather than being an artifact of the clustering.

### 3. Revenue Forecasting
`src/forecasting.py` fits a linear regression on the monthly revenue trend
extracted via SQL, projects 3 months forward, and computes a 95% confidence
band from residual variance.

### 4. Dashboard
`src/dashboard.py` brings the KPIs, forecast chart, and segment table together
in a single interactive Streamlit view.

## Running It

```bash
# 1. Install dependencies
pip install pandas numpy scikit-learn matplotlib streamlit

# 2. Generate the synthetic dataset
python data/generate_data.py

# 3. Load it into the database
python src/load_to_db.py

# 4. Run the analysis
python src/segmentation.py
python src/forecasting.py

# 5. Launch the interactive dashboard
streamlit run src/dashboard.py
```

## Using PostgreSQL instead of SQLite

The schema in `sql/schema.sql` is standard SQL and runs on PostgreSQL as-is.
To switch: replace `sqlite3.connect(DB_PATH)` in `src/load_to_db.py`,
`src/segmentation.py`, and `src/forecasting.py` with a `psycopg2`/`SQLAlchemy`
Postgres connection, and swap the SQLite-specific `strftime()`/`JULIANDAY()`
calls in `sql/analysis_queries.sql` for Postgres's `TO_CHAR()` and
`CURRENT_DATE - date_column` equivalents. SQLite was used here for
zero-setup portability when sharing/demoing the project.

## Notes on the Dataset

The dataset is synthetically generated (`data/generate_data.py`) but designed
to mimic realistic payments behavior: seasonal spikes, five customer
archetypes (power users, regulars, occasional users, users going dormant, and
new signups) with different transaction frequency/value distributions, and a
4% baseline transaction failure rate. This was a deliberate choice over
scraping real data — it keeps the project fully reproducible, avoids any data
privacy concerns, and lets the segmentation/forecasting logic be validated
against known ground truth (the archetypes) rather than being a black box.
