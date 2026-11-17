"""One command to reproduce the real-data database, evaluations and reports."""
import argparse
import json
import logging
import os
import sqlite3
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / '.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from config import ROOT, DB_PATH, REPORTS
from prepare_data import prepare
from load_to_db import load_lines, read_lines
from segmentation import run_segmentation, summarize_segments, validate_segments
from forecasting import weekly_sales, evaluate_and_forecast

LOG = logging.getLogger(__name__)
QUERY_NAMES = ['monthly_sales', 'country_sales', 'product_sales', 'cancellation_hotspots', 'monthly_retention', 'cohort_retention', 'anonymous_coverage']


def export_sql(db_path=DB_PATH):
    queries = (ROOT / 'sql/analysis_queries.sql').read_text().split(';')
    with sqlite3.connect(db_path) as conn:
        actual = [q for q in queries if any(line.strip() and not line.strip().startswith('--') for line in q.splitlines())]
        if len(actual) != len(QUERY_NAMES):
            raise ValueError('SQL report names and query count differ')
        for name, query in zip(QUERY_NAMES, actual):
            pd.read_sql_query(query, conn).to_csv(REPORTS / f'{name}.csv', index=False)


def plot_reports(rfm, evaluation, retention, series, results):
    visual = ROOT / 'visuals'
    visual.mkdir(exist_ok=True)
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for name, group in rfm.groupby('segment'):
        axes[0].scatter(group.frequency, group.monetary, s=12, alpha=.4, label=name)
    axes[0].set(xscale='log', yscale='log', xlabel='Distinct purchase invoices (last 365 days)', ylabel='Gross customer spend (GBP)', title='Observed customer purchasing profiles')
    axes[0].legend(fontsize=7)
    axes[1].plot(evaluation.k, evaluation.silhouette_score, marker='o', color='#5F259F')
    axes[1].set(xlabel='Number of clusters', ylabel='Silhouette score', title='Cluster-count evaluation (log RFM + scaling)')
    fig.tight_layout()
    fig.savefig(visual / 'retail_customer_segments.png', dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(retention.segment, retention.repeat_purchase_rate*100, color='#5F259F')
    ax.errorbar(retention.segment, retention.repeat_purchase_rate*100, yerr=[(retention.repeat_purchase_rate-retention.repeat_rate_lower_95)*100, (retention.repeat_rate_upper_95-retention.repeat_purchase_rate)*100], fmt='none', color='black', capsize=4)
    ax.set(ylabel='Purchased again in later 90 days (%)', title='Historical segment validation | 95% Wilson intervals', ylim=(0, 105))
    ax.tick_params(axis='x', labelsize=9)
    fig.tight_layout()
    fig.savefig(visual / 'retail_repeat_purchase.png', dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(series.index, series.values, label='Actual complete-week gross sales', color='#5F259F')
    selected = results['metadata']['selected_model']
    held = results['holdout_predictions'].query('model == @selected')
    ax.plot(held.week, held.predicted_gbp, label=f'Untouched holdout: {selected}', linestyle='--', color='#dc6b27')
    future = results['forecast']
    ax.plot(future.week, future.forecast_gbp, label='Historical forward projection (refit)', linestyle='--', color='#008d9c')
    ax.axvline(held.week.min(), color='grey', linestyle=':', label='Final holdout starts')
    ax.set(ylabel='Weekly gross merchandise sales (GBP)', title='Time-ordered forecast evaluation | no calibrated intervals claimed')
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(visual / 'retail_sales_forecast.png', dpi=150)
    plt.close(fig)


def main(source=None, reuse_db=False):
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / 'run_manifest.json').unlink(missing_ok=True)
    if reuse_db:
        lines = read_lines()
        if not (REPORTS / 'data_quality.json').exists():
            raise ValueError('A previous complete import is required for --reuse-db')
        quality = json.loads((REPORTS / 'data_quality.json').read_text())
    else:
        lines, quality = prepare(source)
        load_lines(lines)
        # Read the validated persisted representation for every downstream analysis.
        lines = read_lines()
    LOG.info('Exporting business SQL reports')
    export_sql()
    LOG.info('Fitting customer segments and validating subsequent purchases')
    rfm, centroids, evaluation = run_segmentation(lines)
    summary = summarize_segments(rfm)
    rfm.to_csv(REPORTS / 'customer_segments.csv', index=False)
    centroids.to_csv(REPORTS / 'cluster_centroids.csv')
    evaluation.to_csv(REPORTS / 'cluster_evaluation.csv', index=False)
    summary.to_csv(REPORTS / 'segment_summary.csv', index=False)
    retention, observed, retention_meta = validate_segments(lines)
    retention.to_csv(REPORTS / 'segment_validation.csv', index=False)
    observed.to_csv(REPORTS / 'customer_future_outcomes.csv', index=False)
    (REPORTS / 'segment_validation.json').write_text(json.dumps(retention_meta, indent=2))
    LOG.info('Evaluating weekly sales models against baselines')
    series = weekly_sales(lines)
    series.to_csv(REPORTS / 'weekly_sales.csv', index_label='week')
    results = evaluate_and_forecast(series)
    for name, frame in results.items():
        if name != 'metadata':
            frame.to_csv(REPORTS / f'{name}.csv', index=False)
    (REPORTS / 'forecast_metadata.json').write_text(json.dumps(results['metadata'], indent=2))
    plot_reports(rfm, evaluation, retention, series, results)
    selected = results['metadata']['selected_model']
    score = results['holdout_metrics'].query('model == @selected').iloc[0]
    best_segment = retention.sort_values('repeat_purchase_rate', ascending=False).iloc[0]
    least_repeat = retention.sort_values('repeat_purchase_rate').iloc[0]
    findings = f'''# TransactIQ: findings from real retail records

Source: UCI Online Retail II (Daqing Chen, CC BY 4.0).

- {quality['source_rows']:,} original invoice lines; {quality['retained_lines']:,} retained after documented cleaning.
- Merchandise gross sales: GBP {quality['gross_sales_gbp']:,.2f}; recorded cancellation value: GBP {quality['cancellation_value_gbp']:,.2f}.
- {len(rfm):,} identified purchasing customers in the latest 365-day segmentation window.
- Earlier segments had later 90-day purchase rates of {best_segment['repeat_purchase_rate']:.1%} ({best_segment['segment']}, {int(best_segment['customers']):,} customers) versus {least_repeat['repeat_purchase_rate']:.1%} ({least_repeat['segment']}, {int(least_repeat['customers']):,} customers). These are observed group differences, not retention lift.
- Forecast selected using earlier rolling validation: {selected}. Untouched final {results['metadata']['holdout_weeks']}-week holdout MAE: GBP {score.mae_gbp:,.2f}; WAPE: {score.wape_pct:.1f}%.

## Decisions supported

Prioritize customer-service and retention experiments by purchasing behaviour; plan sales capacity using a forecast benchmarked against simple alternatives; investigate countries/products with elevated recorded cancellations.

## Interpretation limits

This is an offline historical case study from 2009–2011, not a deployed retailer system. Segment association does not establish campaign effectiveness. No retention lift, cost reduction or revenue uplift is claimed. Sales values are merchandise invoice values, not audited revenue or profit. A cancellation is not a failed payment, and cancellations are not matched back to original invoices. Missing customer IDs remain in sales totals but not customer analyses. Exact duplicates are removed under a disclosed assumption. The final calendar month is partial; weekly forecasting excludes boundary partial weeks. Forecasts extend from the historical data end, not today's date.
'''
    (REPORTS / 'findings.md').write_text(findings)
    (REPORTS / 'run_manifest.json').write_text(json.dumps({'status': 'complete', 'database_mtime_ns': DB_PATH.stat().st_mtime_ns, 'source_sha256': quality['sha256']}, indent=2))
    LOG.info('Complete. Findings: %s', REPORTS / 'findings.md')
    print(findings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Optional original UCI .zip or .xlsx path')
    parser.add_argument('--reuse-db', action='store_true', help='Rebuild reports without importing Excel again')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    main(args.source, args.reuse_db)
