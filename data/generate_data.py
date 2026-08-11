"""
generate_data.py
Generates a realistic synthetic dataset simulating digital payment
transactions (PhonePe-style) for 12 months: users, merchants, categories,
transaction amounts, with seasonal growth and built-in customer behavior
segments (so the segmentation step has real signal to find).
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

N_USERS = 2000
N_MERCHANTS = 150
START_DATE = datetime(2025, 8, 1)
MONTHS = 12

CATEGORIES = [
    "Recharge & Bills", "Grocery", "Food Delivery", "Travel",
    "Entertainment", "Shopping", "P2P Transfer", "Fuel", "Healthcare"
]

CITIES = ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune",
          "Chennai", "Kolkata", "Rourkela", "Bhubaneswar", "Ahmedabad"]

# --- 1. Build users with hidden behavioral archetypes ---
# Archetype drives frequency & spend patterns -> gives segmentation something real to discover
archetypes = np.random.choice(
    ["power_user", "regular", "occasional", "dormant_recent", "new_user"],
    size=N_USERS,
    p=[0.12, 0.38, 0.30, 0.10, 0.10]
)

users = pd.DataFrame({
    "user_id": [f"U{100000+i}" for i in range(N_USERS)],
    "city": np.random.choice(CITIES, N_USERS),
    "signup_month_offset": np.random.randint(0, MONTHS, N_USERS),
    "archetype": archetypes
})

merchants = pd.DataFrame({
    "merchant_id": [f"M{5000+i}" for i in range(N_MERCHANTS)],
    "merchant_name": [f"Merchant_{i}" for i in range(N_MERCHANTS)],
    "category": np.random.choice(CATEGORIES, N_MERCHANTS)
})

# --- 2. Generate transactions per user based on archetype ---
ARCHETYPE_PARAMS = {
    # (avg txns/month, avg amount, amount_std, trend)
    "power_user":     (14, 850, 400, 1.03),
    "regular":        (6,  450, 200, 1.02),
    "occasional":     (2,  300, 150, 1.00),
    "dormant_recent": (1,  500, 250, 0.85),  # active early, fades out
    "new_user":       (3,  350, 180, 1.10),  # ramping up
}

rows = []
txn_id_counter = 0

for _, u in users.iterrows():
    avg_n, avg_amt, amt_std, trend = ARCHETYPE_PARAMS[u["archetype"]]
    active_months = range(u["signup_month_offset"], MONTHS)

    for m_idx, month_offset in enumerate(active_months):
        # seasonal boost in festive months (Oct-Nov = months offset 2,3 from Aug start) + trend growth
        seasonal_mult = 1.35 if month_offset in (2, 3, 10, 11) else 1.0
        month_n_txns = np.random.poisson(avg_n * (trend ** m_idx) * seasonal_mult)

        # dormant_recent archetype: sharply drop off in later months
        if u["archetype"] == "dormant_recent" and month_offset > 6:
            month_n_txns = np.random.poisson(0.3)

        month_start = START_DATE + timedelta(days=30 * month_offset)

        for _ in range(month_n_txns):
            txn_id_counter += 1
            merchant = merchants.sample(1).iloc[0]
            amount = max(10, np.random.normal(avg_amt, amt_std))
            day_offset = np.random.randint(0, 28)
            txn_date = month_start + timedelta(days=day_offset)

            rows.append({
                "txn_id": f"T{txn_id_counter:07d}",
                "user_id": u["user_id"],
                "merchant_id": merchant["merchant_id"],
                "category": merchant["category"],
                "amount": round(amount, 2),
                "txn_date": txn_date.strftime("%Y-%m-%d"),
                "city": u["city"],
                "status": np.random.choice(["SUCCESS", "FAILED"], p=[0.96, 0.04])
            })

transactions = pd.DataFrame(rows)

users.to_csv("data/users.csv", index=False)
merchants.to_csv("data/merchants.csv", index=False)
transactions.to_csv("data/transactions.csv", index=False)

print(f"Generated {len(users)} users, {len(merchants)} merchants, {len(transactions)} transactions")
print(transactions.head())
