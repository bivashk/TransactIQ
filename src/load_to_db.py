"""Validate and atomically replace the retail database; preserve the old DB on failure."""
import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
from config import DB_PATH, ROOT, REPORTS

LOG = logging.getLogger(__name__)


def load_lines(lines, db_path=DB_PATH):
    if lines.empty:
        raise ValueError('No valid retail lines; refusing to replace the database')
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(suffix='.db', dir=db_path.parent)
    os.close(handle)
    try:
        with sqlite3.connect(temporary) as conn:
            conn.executescript((ROOT / 'sql/schema.sql').read_text())
            customers = lines[['customer_id']].dropna().drop_duplicates()
            products = lines[['stock_code', 'description']].drop_duplicates('stock_code', keep='last')
            customers.to_sql('customers', conn, if_exists='append', index=False)
            products.to_sql('products', conn, if_exists='append', index=False)
            columns = ['invoice_no', 'stock_code', 'customer_id', 'invoice_date', 'country', 'quantity', 'unit_price', 'is_cancellation', 'amount_pence']
            lines[columns].to_sql('invoice_lines', conn, if_exists='append', index=False, chunksize=10000)
            if conn.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Foreign-key validation failed')
            count, value = conn.execute('SELECT COUNT(*), SUM(amount_pence) FROM invoice_lines').fetchone()
            if count != len(lines) or value != int(lines['amount_pence'].sum()):
                raise ValueError('Database totals do not reconcile to cleaned data')
            conn.commit()
        os.replace(temporary, db_path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    LOG.info('Loaded %s retail lines into %s', len(lines), db_path)


def read_lines(db_path=DB_PATH):
    if not Path(db_path).exists():
        raise FileNotFoundError('Run python src/pipeline.py to build the real-data database first.')
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query('SELECT * FROM invoice_lines ORDER BY invoice_date, line_id', conn)
    df['invoice_date'] = pd.to_datetime(df['invoice_date'])
    return df


def main():
    from prepare_data import prepare
    lines, report = prepare()
    load_lines(lines)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
