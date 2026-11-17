"""Browse real retail sales, retention validation and forecast evidence."""
import json
import sqlite3

import pandas as pd
import streamlit as st
from config import DB_PATH, REPORTS, SOURCE_PAGE
from load_to_db import read_lines

st.set_page_config(page_title='TransactIQ | Retail customer analytics', page_icon='📊', layout='wide')
st.title('TransactIQ — Retail customer & sales analytics')
st.caption('Real historical retail records · GBP · Customer retention and sales planning')
st.info('Historical case study (2009–2011). Recommendations support business experiments; no deployed business impact is claimed.')

required_reports = ['run_manifest.json', 'data_quality.json', 'segment_summary.csv', 'segment_validation.csv', 'segment_validation.json', 'forecast_metadata.json', 'validation_metrics.csv', 'holdout_metrics.csv', 'weekly_sales.csv', 'holdout_predictions.csv', 'forecast.csv', 'customer_segments.csv', 'monthly_retention.csv', 'cohort_retention.csv', 'cluster_evaluation.csv']
if not DB_PATH.exists() or any(not (REPORTS / name).exists() for name in required_reports):
    st.warning('The real-data analysis has not been built yet. Follow the setup steps in README.md and run the pipeline.')
    st.stop()


manifest = json.loads((REPORTS / 'run_manifest.json').read_text())
if manifest.get('database_mtime_ns') != DB_PATH.stat().st_mtime_ns:
    st.warning('The database has changed since the reports were generated. Rebuild the analysis before browsing.')
    st.stop()


@st.cache_data
def load_data(db_modified):
    return read_lines()


def report(name):
    return pd.read_csv(REPORTS / f'{name}.csv')


def json_report(name):
    return json.loads((REPORTS / f'{name}.json').read_text())


lines = load_data(DB_PATH.stat().st_mtime_ns)
quality = json_report('data_quality')
with st.sidebar:
    st.header('Explore sales')
    countries = st.multiselect('Countries', sorted(lines.country.unique()), help='Leave empty to include every country.')
    start, end = lines.invoice_date.min().date(), lines.invoice_date.max().date()
    period = st.date_input('Invoice date range', value=(start, end), min_value=start, max_value=end)
    st.caption('Filters apply to the Sales tab. Model evaluations use the full historical dataset.')
    st.link_button('Original UCI dataset', SOURCE_PAGE)

sales_tab, customer_tab, forecast_tab, quality_tab = st.tabs(['Sales & cancellations', 'Customer retention', 'Forecast validation', 'Data quality & methods'])
with sales_tab:
    filtered = lines
    if countries:
        filtered = filtered.loc[filtered.country.isin(countries)]
    if len(period) == 2:
        filtered = filtered.loc[(filtered.invoice_date >= pd.Timestamp(period[0])) & (filtered.invoice_date < pd.Timestamp(period[1])+pd.Timedelta(days=1))]
    if filtered.empty:
        st.warning('No invoice lines match these filters.')
    else:
        purchases = filtered.loc[filtered.is_cancellation.eq(0)]
        cancellations = filtered.loc[filtered.is_cancellation.eq(1)]
        gross = purchases.amount_pence.sum()/100
        cancelled = -cancellations.amount_pence.sum()/100
        invoice_count = filtered.invoice_no.nunique()
        cols = st.columns(4)
        cols[0].metric('Gross merchandise sales', f'£{gross:,.0f}')
        cols[1].metric('Recorded cancellation value', f'£{cancelled:,.0f}')
        cols[2].metric('Known purchasing customers', f'{purchases.customer_id.nunique():,}')
        cols[3].metric('Cancellation invoice share', f'{cancellations.invoice_no.nunique()/invoice_count:.1%}')
        st.caption('Cancellation share = distinct cancellation invoices / all distinct recorded invoices. It is not a payment-failure rate or a matched order-return rate.')
        daily = filtered.assign(day=filtered.invoice_date.dt.normalize()).groupby('day').agg(net_value_pence=('amount_pence','sum'))/100
        st.subheader('Daily net recorded merchandise value (£)')
        st.line_chart(daily.rename(columns={'net_value_pence':'Net recorded value'}))
        left, right = st.columns(2)
        with left:
            st.subheader('Gross sales by country (£)')
            st.bar_chart((purchases.groupby('country').amount_pence.sum()/100).nlargest(12))
        with right:
            st.subheader('Top products by gross sales (£)')
            with sqlite3.connect(DB_PATH) as conn:
                descriptions = pd.read_sql_query('SELECT * FROM products', conn)
            products = (purchases.groupby('stock_code').amount_pence.sum()/100).nlargest(12).rename('gross_sales_gbp').reset_index().merge(descriptions, on='stock_code')
            st.dataframe(products[['description','gross_sales_gbp']], hide_index=True, width='stretch')
        st.subheader('Cancellation hotspots by country')
        totals = filtered.groupby('country').invoice_no.nunique().rename('recorded_invoices')
        cancel_counts = cancellations.groupby('country').invoice_no.nunique().rename('cancellation_invoices')
        hotspots = pd.concat([totals, cancel_counts], axis=1).fillna(0)
        hotspots = hotspots.loc[hotspots.recorded_invoices >= 30].copy()
        hotspots['cancellation_invoice_share_pct'] = 100*hotspots.cancellation_invoices/hotspots.recorded_invoices
        st.dataframe(hotspots.sort_values('cancellation_invoice_share_pct', ascending=False).round(1), width='stretch')
        st.caption('Only countries with at least 30 recorded invoices in the selected period are shown. Differences warrant investigation; they do not establish a cause.')
        st.download_button('Download filtered invoice lines', filtered.to_csv(index=False), file_name='retail_invoice_lines.csv', mime='text/csv')
        st.caption('Boundary calendar months may be partial. These are merchandise values, not platform revenue or profit.')

with customer_tab:
    st.subheader('Current historical customer segments')
    st.caption('Latest 365 days relative to the dataset end. RFM uses positive purchases with known customer IDs, distinct-invoice frequency, log transforms, and scaling. Segment names are heuristic business interpretations.')
    summary = report('segment_summary')
    st.dataframe(summary, hide_index=True, width='stretch')
    evaluation = report('cluster_evaluation')
    st.line_chart(evaluation.set_index('k')['silhouette_score'])
    st.subheader('Did earlier segments predict later purchasing behaviour?')
    validation = report('segment_validation')
    meta = json_report('segment_validation')
    st.caption(f"Segments were fitted strictly before {meta['cutoff_exclusive_training']}; later purchases observed through {meta['observation_end_exclusive']} (exclusive). Newly acquired customers are excluded from this validation.")
    st.bar_chart(validation.set_index('segment')['repeat_purchase_rate'])
    st.dataframe(validation, hide_index=True, width='stretch')
    association = meta['association']
    if association.get('p_value') is not None:
        st.caption(f"Chi-square association p-value: {association['p_value']:.3g}; minimum expected cell count: {association['minimum_expected_count']:.1f}. Association is not evidence that an offer improves retention.")
    st.subheader('Monthly retention and acquisition cohorts')
    st.caption('Cohort = first observed purchase, not signup. Adjacent-month retention = customers purchasing next month / this month’s customers. Boundary months may be partial.')
    retention = report('monthly_retention')
    st.line_chart(retention.set_index('month')['next_month_retention_pct'])
    cohort = report('cohort_retention')
    st.dataframe(cohort.pivot(index='cohort_month', columns='months_since_first_purchase', values='retention_pct').round(1), width='stretch')
    segments = report('customer_segments')
    st.download_button('Download customer segments and recommended experiments', segments.to_csv(index=False), file_name='customer_segments.csv', mime='text/csv')

with forecast_tab:
    meta = json_report('forecast_metadata')
    st.subheader('Weekly gross sales forecasting')
    st.write(f"Selected model: **{meta['selected_model']}**, chosen by lowest MAE across three earlier rolling validation windows. The final 13 weeks were reserved for testing.")
    left, right = st.columns(2)
    with left:
        st.write('Earlier rolling-validation performance')
        st.dataframe(report('validation_metrics'), hide_index=True)
    with right:
        st.write('Untouched final holdout performance')
        st.dataframe(report('holdout_metrics'), hide_index=True)
    actual = report('weekly_sales').assign(week=lambda x: pd.to_datetime(x.week)).set_index('week')
    held = report('holdout_predictions')
    held = held.loc[held.model.eq(meta['selected_model'])].assign(week=lambda x: pd.to_datetime(x.week)).set_index('week')
    future = report('forecast').assign(week=lambda x: pd.to_datetime(x.week)).set_index('week')
    chart = pd.concat([actual.gross_sales_gbp.rename('Actual'), held.predicted_gbp.rename('Holdout prediction'), future.forecast_gbp.rename('Historical forward projection')], axis=1)
    st.line_chart(chart)
    st.caption('Only complete Monday–Sunday weeks are included. WAPE = sum of absolute errors / sum of actual sales. No calibrated prediction intervals are claimed. Forecast dates follow the historical dataset end, not today.')
    st.download_button('Download 13-week historical projection', future.to_csv(), file_name='sales_forecast.csv', mime='text/csv')

with quality_tab:
    st.subheader('Source and reconciliation')
    st.markdown(f'[UCI Online Retail II]({SOURCE_PAGE}) · Daqing Chen (2012) · CC BY 4.0 · DOI: 10.24432/C5CG6D')
    st.json(quality)
    st.write('Rows with missing customer IDs contribute to sales but cannot be segmented. Exact duplicate source rows are removed under a disclosed assumption. Non-merchandise adjustments, zero/invalid prices, and invalid quantities/dates are audited separately.')
    st.write('Cancellation invoices and negative quantities are recorded as negative merchandise values. They are not reliably matched to original sales and do not reveal payment failures. Gross sales exclude these lines; net recorded value subtracts them.')
    st.write('Customer segments suggest experiments, not measured retention improvements. Compare randomized treatment and control groups before claiming campaign impact. Two annual cycles provide limited evidence for stable seasonality.')
    st.download_button('Download reconciliation report', json.dumps(quality, indent=2), file_name='data_quality.json', mime='application/json')
