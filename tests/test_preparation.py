import sqlite3
import pandas as pd
import pytest
from prepare_data import clean_lines
from load_to_db import load_lines, read_lines


def test_reconciliation_and_anonymous_sales(raw_lines):
    clean, excluded, audit = clean_lines(raw_lines)
    assert len(excluded) == 0
    assert audit['source_rows'] == audit['retained_lines'] + audit['excluded_lines']
    assert audit['gross_sales_gbp'] == 12.5
    assert audit['cancellation_value_gbp'] == 3.5
    assert audit['net_recorded_value_gbp'] == 9
    assert audit['retained_lines_missing_customer'] == 1


def test_exclusion_reasons_are_mutually_exclusive(raw_lines):
    bad = raw_lines.iloc[[0]].copy()
    bad['Price'] = 0
    bad['Quantity'] = 0
    raw = pd.concat([raw_lines, raw_lines.iloc[[0]], bad], ignore_index=True)
    clean, excluded, audit = clean_lines(raw)
    assert len(clean) == 4
    assert audit['exclusion_counts'] == {'exact_duplicate':1, 'invalid_quantity':1}
    assert len(excluded) == 2


@pytest.mark.parametrize('field,value,reason', [
    ('Invoice',None,'missing_invoice_or_product'),
    ('InvoiceDate','invalid','invalid_date'),
    ('Quantity',float('inf'),'invalid_quantity'),
    ('Quantity',1.5,'invalid_quantity'),
    ('Price',-2,'invalid_price'),
    ('StockCode','POST','non_merchandise_adjustment'),
])
def test_invalid_source_lines_are_audited(raw_lines, field, value, reason):
    raw_lines[field] = raw_lines[field].astype(object)
    raw_lines.loc[0,field] = value
    _, excluded, _ = clean_lines(raw_lines)
    assert excluded.iloc[0].exclusion_reason == reason


def test_positive_cancellation_is_signed_negative(raw_lines):
    raw_lines.loc[0,'Invoice'] = 'C100'
    clean, _, _ = clean_lines(raw_lines)
    assert clean.iloc[0].amount_pence == -700


def test_database_rebuild_is_idempotent(clean, tmp_path):
    path = tmp_path/'retail.db'
    clean['invoice_date'] = clean.invoice_date.dt.strftime('%Y-%m-%d %H:%M:%S')
    load_lines(clean,path)
    load_lines(clean,path)
    persisted = read_lines(path)
    assert len(persisted) == len(clean)
    assert persisted.amount_pence.sum() == clean.amount_pence.sum()
    with sqlite3.connect(path) as conn:
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_invalid_rebuild_preserves_previous_database(clean, tmp_path):
    path=tmp_path/'retail.db'
    clean['invoice_date']=clean.invoice_date.dt.strftime('%Y-%m-%d %H:%M:%S')
    load_lines(clean,path)
    original=path.read_bytes()
    broken=clean.copy()
    broken.loc[0,'amount_pence']=-100
    with pytest.raises(Exception):
        load_lines(broken,path)
    assert path.read_bytes()==original
