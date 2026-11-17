import sqlite3
from pathlib import Path
from load_to_db import load_lines
from pipeline import QUERY_NAMES


def queries():
    text=(Path(__file__).resolve().parents[1]/'sql/analysis_queries.sql').read_text()
    return [q for q in text.split(';') if any(line.strip() and not line.strip().startswith('--') for line in q.splitlines())]


def test_business_queries_execute_on_valid_database(clean,tmp_path):
    path=tmp_path/'retail.db'
    clean['invoice_date']=clean.invoice_date.dt.strftime('%Y-%m-%d %H:%M:%S')
    load_lines(clean,path)
    statements=queries()
    assert len(statements)==len(QUERY_NAMES)
    with sqlite3.connect(path) as conn:
        results=[conn.execute(query).fetchall() for query in statements]
    # Monthly gross sales retain the anonymous purchase, returns signed separately.
    month=results[0][0]
    assert month[1:4]==(12.5,3.5,9.0)
    assert results[6][0]==(3,1,3.5)
