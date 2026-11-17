"""Download and reconcile the original UCI workbook; never fabricate fields."""
import argparse
import hashlib
import json
import logging
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from config import RAW, REPORTS, SOURCE_URL, SOURCE_PAGE

LOG = logging.getLogger(__name__)
COLUMNS = {
    'Invoice': 'invoice_no', 'InvoiceNo': 'invoice_no',
    'StockCode': 'stock_code', 'Description': 'description',
    'Quantity': 'quantity', 'InvoiceDate': 'invoice_date',
    'Price': 'unit_price', 'UnitPrice': 'unit_price',
    'Customer ID': 'customer_id', 'CustomerID': 'customer_id', 'Country': 'country',
}
# Explicit accounting/fulfilment codes, not merchandise. Retained in the audit.
ADJUSTMENT_CODES = {'POST', 'D', 'M', 'BANK CHARGES', 'C2', 'CRUK', 'DOT', 'AMAZONFEE', 'B', 'ADJUST', 'ADJUST2', 'TEST001', 'TEST002'}


def download_source():
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / 'online_retail_ii.zip'
    if not path.exists():
        temporary = path.with_suffix('.download')
        LOG.info('Downloading the original UCI archive')
        try:
            with urllib.request.urlopen(SOURCE_URL, timeout=120) as response, temporary.open('wb') as out:
                import shutil
                shutil.copyfileobj(response, out)
            with zipfile.ZipFile(temporary) as archive:
                if not any(n.lower().endswith('.xlsx') for n in archive.namelist()):
                    raise ValueError('Archive does not contain an Excel workbook')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return path


def read_workbook(path):
    path = Path(path)
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith('.xlsx')]
            if len(names) != 1:
                raise ValueError('Expected exactly one workbook in the source archive')
            with archive.open(names[0]) as stream:
                sheets = pd.read_excel(stream, sheet_name=None, engine='openpyxl')
    else:
        sheets = pd.read_excel(path, sheet_name=None, engine='openpyxl')
    LOG.info('Loaded sheets: %s', {name: len(df) for name, df in sheets.items()})
    return pd.concat([df.rename(columns=COLUMNS) for df in sheets.values()], ignore_index=True)


def clean_lines(raw):
    """Apply mutually exclusive rejection reasons and return a reconciled audit.

    Exact duplicate rows are removed under an explicit assumption: the source has
    no line identifier with which to distinguish an accidental duplicate from an
    identical legitimate line. This assumption is reported, not hidden.
    """
    df = raw.rename(columns=COLUMNS).copy()
    required = {'invoice_no', 'stock_code', 'description', 'quantity', 'invoice_date', 'unit_price', 'customer_id', 'country'}
    if missing := required - set(df.columns):
        raise ValueError(f'Missing source columns: {sorted(missing)}')
    df = df[sorted(required)].copy()
    df['source_row'] = np.arange(1, len(df) + 1)
    reason = pd.Series('', index=df.index, dtype='string')

    def reject(mask, label):
        reason.loc[mask & reason.eq('')] = label

    reject(df.drop(columns='source_row').duplicated(), 'exact_duplicate')
    for col in ['invoice_no', 'stock_code', 'customer_id', 'country']:
        df[col] = df[col].astype('string').str.strip().replace('', pd.NA)
    df['customer_id'] = df['customer_id'].str.replace(r'\.0$', '', regex=True)
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], errors='coerce', format='mixed')
    for col in ['quantity', 'unit_price']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    reject(df['invoice_no'].isna() | df['stock_code'].isna(), 'missing_invoice_or_product')
    reject(df['invoice_date'].isna(), 'invalid_date')
    reject(~np.isfinite(df['quantity']) | df['quantity'].eq(0) | df['quantity'].mod(1).ne(0), 'invalid_quantity')
    reject(~np.isfinite(df['unit_price']) | df['unit_price'].le(0), 'invalid_price')
    reject(df['stock_code'].str.upper().isin(ADJUSTMENT_CODES), 'non_merchandise_adjustment')
    value = df['quantity'].abs() * df['unit_price'] * 100
    reject(~np.isfinite(value) | value.gt(1e14) | value.round().lt(1), 'invalid_line_value')
    excluded = df.loc[reason.ne('')].copy()
    excluded['exclusion_reason'] = reason[reason.ne('')]
    clean = df.loc[reason.eq('')].copy()
    clean['country'] = clean['country'].fillna('Unknown')
    clean['description'] = clean['description'].fillna('Unknown')
    clean['quantity'] = clean['quantity'].astype('int64')
    clean['is_cancellation'] = (clean['invoice_no'].str.upper().str.startswith('C') | clean['quantity'].lt(0)).astype(int)
    clean['amount_pence'] = (clean['quantity'].abs() * clean['unit_price'] * 100).round().astype('int64')
    clean.loc[clean['is_cancellation'].eq(1), 'amount_pence'] *= -1
    clean['invoice_date'] = clean['invoice_date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    report = {
        'source_rows': len(raw), 'retained_lines': len(clean), 'excluded_lines': len(excluded),
        'exclusion_counts': {str(k): int(v) for k, v in excluded['exclusion_reason'].value_counts().items()},
        'retained_lines_missing_customer': int(clean['customer_id'].isna().sum()),
        'purchase_lines': int(clean['is_cancellation'].eq(0).sum()),
        'cancellation_lines': int(clean['is_cancellation'].sum()),
        'gross_sales_gbp': int(clean.loc[clean['is_cancellation'].eq(0), 'amount_pence'].sum()) / 100,
        'cancellation_value_gbp': -int(clean.loc[clean['is_cancellation'].eq(1), 'amount_pence'].sum()) / 100,
        'net_recorded_value_gbp': int(clean['amount_pence'].sum()) / 100,
        'first_date': clean['invoice_date'].min() if len(clean) else None,
        'last_date': clean['invoice_date'].max() if len(clean) else None,
        'duplicate_policy': 'Remove exact source-row duplicates; identical legitimate lines cannot be distinguished.',
        'value_policy': 'Merchandise values only; cancellation/negative-quantity lines signed negative. Not audited revenue or profit.',
    }
    assert report['source_rows'] == report['retained_lines'] + report['excluded_lines']
    return clean, excluded, report


def prepare(path=None):
    source = Path(path) if path else download_source()
    clean, excluded, report = clean_lines(read_workbook(source))
    REPORTS.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as stream:
        source_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    report.update(source=SOURCE_PAGE, source_file=source.name, sha256=source_hash)
    excluded.to_csv(REPORTS / 'excluded_lines.csv', index=False)
    (REPORTS / 'data_quality.json').write_text(json.dumps(report, indent=2))
    LOG.info('Reconciliation: %s retained, %s excluded', len(clean), len(excluded))
    return clean, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    _, report = prepare(args.source)
    print(json.dumps(report, indent=2))
