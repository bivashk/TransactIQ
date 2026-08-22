"""
load_to_db.py
Loads the generated CSV data into a SQLite database using the schema
defined in sql/schema.sql. SQLite is used here for zero-setup portability
(runs anywhere with no server); the schema is written in standard SQL
and is directly portable to PostgreSQL (see README for the one-line swap).
"""

import sqlite3
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "transactiq.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "sql", "schema.sql")

def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    with open(SCHEMA_PATH, "r") as f:
        cur.executescript(f.read())

    users = pd.read_csv(os.path.join(BASE_DIR, "data", "users.csv"))
    merchants = pd.read_csv(os.path.join(BASE_DIR, "data", "merchants.csv"))
    transactions = pd.read_csv(os.path.join(BASE_DIR, "data", "transactions.csv"))

    users.to_sql("users", conn, if_exists="append", index=False)
    merchants.to_sql("merchants", conn, if_exists="append", index=False)
    transactions.to_sql("transactions", conn, if_exists="append", index=False)

    conn.commit()

    # sanity check
    for table in ["users", "merchants", "transactions"]:
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows loaded")

    conn.close()
    print(f"\nDatabase created at {DB_PATH}")

if __name__ == "__main__":
    main()
