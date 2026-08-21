# TransactIQ — Digital Payments Transaction Analytics & Customer Segmentation

An end-to-end analytics platform simulating a digital payments platform's transaction data, built to answer core business and financial operations questions: *Where is revenue coming from? Which customer segments drive growth? What is our near-term trajectory?*

The project combines **SQL-driven business analysis**, **RFM-based K-Means customer segmentation** with cluster validation (Elbow & Silhouette), **harmonic seasonal revenue forecasting**, an **interactive Streamlit dashboard**, and a **25-test pytest suite** on a 79,000+ row multi-dimensional transactional dataset (2,000 users, 150 merchants, 12 months, 9 spend categories, 10 cities).

---

## 🎯 Key Business Insights

- **Pareto-Distributed Customer Value**: The top **~5.7% of users** (*High-Value Loyalists* — high frequency, high spend, active within <1 day) generate **36.3% of total revenue**, while **~3.1%** (*At-Risk/Dormant* — inactive for >150 days on average) contribute virtually 0.2%. This provides an empirical basis for targeted VIP retention programs and automated re-engagement workflows.
- **Strong Seasonal Growth & Forecasting**: Revenue scaled ~17x over 12 months (₹4.3L → ₹72L/month) with sharp festive period surges. A seasonal linear regression model (incorporating yearly harmonic terms) projects **~24% growth over the next quarter**, providing capacity planning inputs.
- **Category & City Reliability Hotspots**: SQL aggregations surfaced city-category combinations with elevated payment failure rates (>5%), pinpointing gateway/network reliability bottlenecks for engineering and merchant operations teams.

---

## 🛠️ Tech Stack

- **SQL** (SQLite, PostgreSQL-portable) — Relational schema design, indexes, aggregations, correlated subqueries, CASE expressions, window-style metrics.
- **Python & Pandas / NumPy** — Data simulation, ETL, and vector feature transformations.
- **scikit-learn** — Standard scaling, K-Means clustering, silhouette scoring, linear & seasonal regression modeling.
- **Matplotlib** — Multi-panel visual reports (segmentation, elbow curve, forecast bands).
- **Streamlit** — Executive KPI and analytics dashboard.
- **pytest** — Comprehensive unit testing suite (25 test cases across segmentation and forecasting).

---

## 📁 Project Structure

```
TransactIQ/
├── data/
│   ├── generate_data.py          # Synthetic transaction generator (5 behavioral archetypes)
│   ├── users.csv                 # 2,000 users
│   ├── merchants.csv             # 150 merchants
│   ├── transactions.csv          # 79,374 transactions
│   └── customer_segments.csv     # Segment-labeled user dataset
├── sql/
│   ├── schema.sql                # Normalized relational schema with index definitions
│   └── analysis_queries.sql      # 7 business analytics & diagnostic SQL queries
├── src/
│   ├── load_to_db.py             # Relational SQLite loader
│   ├── segmentation.py           # RFM extraction, Elbow/Silhouette analysis & K-Means
│   ├── forecasting.py            # Trend & harmonic seasonal forecasting with R²/RMSE
│   └── dashboard.py              # Interactive Streamlit analytics dashboard
├── tests/
│   ├── test_segmentation.py      # Unit tests for RFM & segmentation logic
│   └── test_forecasting.py       # Unit tests for aggregation & forecasting logic
├── visuals/
│   ├── customer_segments.png     # Frequency vs Monetary & segment share plot
│   ├── elbow_silhouette.png      # Inertia elbow curve & silhouette score evaluation
│   └── revenue_forecast.png      # Actual vs Linear & Seasonal forecast bands
├── requirements.txt              # Pinned direct dependencies
├── .gitignore
└── README.md
```

---

## ⚙️ Architecture & Pipeline Walkthrough

### 1. Relational Schema & SQL Layer
- `sql/schema.sql`: Normalized 3-table relational schema (`users`, `merchants`, `transactions`) with foreign keys and query-optimized indexes on `user_id`, `txn_date`, and `category`.
- `sql/analysis_queries.sql`: 7 standalone analytical queries covering MoM growth, category concentration, geographic revenue per user, Monthly Active Users (MAU), top merchant partners, failure hotspots, and base RFM features.

### 2. Customer Segmentation (RFM + K-Means + Validation)
- Pulls per-user **Recency, Frequency, and Monetary** metrics via SQL.
- Evaluates $k=2..8$ using **Inertia (Elbow Method)** and **Silhouette Coefficient** analysis.
- Clusters users using `StandardScaler` + `KMeans(k=4)`.
- Applies domain-driven centroid rule mapping (e.g., classifying users as *At-Risk / Dormant* only if recency strictly exceeds the median and 30-day thresholds).

### 3. Revenue Forecasting (Trend & Harmonic Seasonality)
- Fits linear baseline and harmonic seasonal regression ($\\sin(2\\pi t / 12), \\cos(2\\pi t / 12)$) models.
- Quantifies model performance using $R^2$ and RMSE metrics.
- Projects 3-month forward estimates with 95% confidence bounds ($\\pm 1.96\\sigma$).

### 4. Interactive Dashboard & Automated Testing
- **Dashboard**: Run with `streamlit run src/dashboard.py` to view top-level KPIs, forecast charts, and segment breakdowns.
- **Testing**: 25 automated unit tests with `pytest` testing data integrity, bounds, segment assignments, and forecast constraints.

---

## 🚀 Quickstart

```bash
# 1. Clone repository & install dependencies
git clone https://github.com/yourusername/TransactIQ.git
cd TransactIQ
pip install -r requirements.txt

# 2. Generate transaction data & load into SQLite database
python data/generate_data.py
python src/load_to_db.py

# 3. Run segmentation (generates elbow/silhouette & segment plots)
python src/segmentation.py

# 4. Run forecasting (computes R²/RMSE & forecast plots)
python src/forecasting.py

# 5. Run test suite
pytest

# 6. Launch the interactive dashboard
streamlit run src/dashboard.py
```

---

## 🔄 PostgreSQL Migration Note
The schema in `sql/schema.sql` is ANSI-SQL compliant. To use PostgreSQL:
1. Replace `sqlite3.connect` with `psycopg2` / `SQLAlchemy` engine connections.
2. In SQL queries, replace SQLite's `strftime('%Y-%m', txn_date)` with `TO_CHAR(txn_date, 'YYYY-MM')`, and `JULIANDAY()` date subtraction with `CURRENT_DATE - txn_date`.
