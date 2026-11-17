import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import pandas as pd
import pytest
from prepare_data import clean_lines


@pytest.fixture
def raw_lines():
    return pd.DataFrame([
        ['100', 'P1', 'A gift', 2, '2011-01-03 10:00', 3.5, 1, 'UK'],
        ['100', 'P2', 'Another gift', 1, '2011-01-03 10:00', 2.0, 1, 'UK'],
        ['101', 'P1', 'A gift', 1, '2011-01-10 10:00', 3.5, None, 'UK'],
        ['C102', 'P1', 'A gift', -1, '2011-01-11 10:00', 3.5, 1, 'UK'],
    ], columns=['Invoice','StockCode','Description','Quantity','InvoiceDate','Price','Customer ID','Country'])


@pytest.fixture
def clean(raw_lines):
    result, _, _ = clean_lines(raw_lines)
    result['invoice_date'] = pd.to_datetime(result.invoice_date)
    return result


@pytest.fixture
def customer_history():
    rows = []
    for i in range(40):
        count = 1 + (i % 8)
        for j in range(count):
            rows.append({'invoice_no':f'{i}-{j}', 'customer_id':str(i), 'stock_code':'P1', 'invoice_date':pd.Timestamp('2011-08-01')-pd.Timedelta(days=(i%4)*40+j*3), 'country':'UK', 'quantity':1, 'unit_price':float(5+i*3), 'amount_pence':(5+i*3)*100, 'is_cancellation':0, 'description':'Gift'})
        if i % 3 == 0:
            rows.append({'invoice_no':f'future-{i}', 'customer_id':str(i), 'stock_code':'P1', 'invoice_date':pd.Timestamp('2011-11-01'), 'country':'UK', 'quantity':1, 'unit_price':20., 'amount_pence':2000, 'is_cancellation':0, 'description':'Gift'})
    return pd.DataFrame(rows)
