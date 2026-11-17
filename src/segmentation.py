"""RFM segmentation and chronological validation on later customer behaviour."""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from scipy.stats import chi2_contingency

from load_to_db import read_lines

FEATURES = ['recency_days', 'frequency', 'monetary']
ACTIONS = {
    'High-value active': 'Prioritize service and loyalty benefits; test against a randomized control group.',
    'At-risk / inactive': 'Test a targeted re-engagement offer; inactivity is not confirmed churn.',
    'Regular active': 'Test cross-sell and repeat-purchase reminders.',
    'Recent / occasional': 'Test onboarding and a second-purchase reminder.',
}


def get_rfm_data(lines=None, as_of=None, lookback_days=365):
    """Use only purchases strictly before as_of; frequency counts invoices, not lines."""
    lines = read_lines() if lines is None else lines.copy()
    if lines.empty:
        raise ValueError('Cannot compute RFM from empty data')
    dates = pd.to_datetime(lines['invoice_date'])
    as_of = pd.Timestamp(as_of) if as_of is not None else dates.max().normalize() + pd.Timedelta(days=1)
    mask = (dates < as_of) & (dates >= as_of - pd.Timedelta(days=lookback_days))
    mask &= lines['is_cancellation'].eq(0) & lines['customer_id'].notna()
    purchases = lines.loc[mask].copy()
    purchases['invoice_date'] = dates[mask]
    rfm = purchases.groupby('customer_id').agg(last_purchase=('invoice_date', 'max'), frequency=('invoice_no', 'nunique'), monetary_pence=('amount_pence', 'sum')).reset_index()
    rfm['recency_days'] = (as_of - rfm.pop('last_purchase')).dt.total_seconds() / 86400
    rfm['monetary'] = rfm.pop('monetary_pence') / 100
    return rfm[['customer_id', *FEATURES]]


def evaluate_cluster_count(rfm, k_min=2, k_max=8):
    if len(rfm) < 3:
        raise ValueError('At least three customers are required for cluster evaluation')
    scaled = StandardScaler().fit_transform(np.log1p(rfm[FEATURES]))
    results = []
    for k in range(k_min, min(k_max, len(rfm) - 1) + 1):
        estimator = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = estimator.fit_predict(scaled)
        if len(np.unique(labels)) < 2:
            continue
        score = silhouette_score(scaled, labels, sample_size=min(2000, len(rfm)), random_state=42)
        results.append({'k': k, 'inertia': float(estimator.inertia_), 'silhouette_score': float(score)})
    if not results:
        raise ValueError('Insufficient distinct customer profiles to form clusters')
    return pd.DataFrame(results)


def run_segmentation(lines=None, as_of=None, n_clusters=None):
    rfm = get_rfm_data(lines, as_of)
    evaluation = evaluate_cluster_count(rfm)
    chosen = int(evaluation.loc[evaluation['silhouette_score'].idxmax(), 'k']) if n_clusters is None else n_clusters
    if chosen < 2 or chosen >= len(rfm):
        raise ValueError('Cluster count must be between two and customer count minus one')
    scaled = StandardScaler().fit_transform(np.log1p(rfm[FEATURES]))
    rfm['cluster'] = KMeans(n_clusters=chosen, random_state=42, n_init=10).fit_predict(scaled)
    centroids = rfm.groupby('cluster')[FEATURES].mean()
    value_score = centroids['frequency'].rank(pct=True) + centroids['monetary'].rank(pct=True)
    labels = {}
    for cluster, row in centroids.iterrows():
        if row.recency_days > 90:
            label = 'At-risk / inactive'
        elif value_score[cluster] == value_score.max():
            label = 'High-value active'
        elif row.frequency <= centroids.frequency.median():
            label = 'Recent / occasional'
        else:
            label = 'Regular active'
        labels[int(cluster)] = label
    rfm['segment'] = rfm.cluster.map(labels)
    rfm['recommended_action'] = rfm.segment.map(ACTIONS)
    return rfm, centroids, evaluation


def summarize_segments(rfm):
    summary = rfm.groupby('segment').agg(customers=('customer_id', 'count'), avg_recency_days=('recency_days', 'mean'), avg_orders=('frequency', 'mean'), avg_spend_gbp=('monetary', 'mean'), gross_sales_gbp=('monetary', 'sum')).reset_index()
    summary['customer_share_pct'] = 100 * summary.customers / summary.customers.sum()
    summary['sales_share_pct'] = 100 * summary.gross_sales_gbp / summary.gross_sales_gbp.sum()
    summary['recommended_action'] = summary.segment.map(ACTIONS)
    return summary.sort_values('gross_sales_gbp', ascending=False)


def validate_segments(lines, horizon_days=90):
    """Fit on the prior year, then observe a separate future window; no new customers.

    Purchase probability is descriptive association, not causal campaign impact.
    A purchase is a positive invoice, even if a later cancellation is recorded.
    """
    end = pd.to_datetime(lines.invoice_date).max().normalize() + pd.Timedelta(days=1)
    cutoff = end - pd.Timedelta(days=horizon_days)
    rfm, _, evaluation = run_segmentation(lines, as_of=cutoff)
    future = lines.loc[(pd.to_datetime(lines.invoice_date) >= cutoff) & (pd.to_datetime(lines.invoice_date) < end) & lines.is_cancellation.eq(0) & lines.customer_id.notna()]
    outcomes = future.groupby('customer_id').agg(future_orders=('invoice_no', 'nunique'), future_spend_pence=('amount_pence', 'sum'))
    observed = rfm.merge(outcomes, on='customer_id', how='left')
    observed[['future_orders', 'future_spend_pence']] = observed[['future_orders', 'future_spend_pence']].fillna(0)
    observed['purchased_again'] = observed.future_orders.gt(0)
    observed['future_spend_gbp'] = observed.future_spend_pence / 100
    summary = observed.groupby('segment').agg(customers=('customer_id', 'count'), repeat_customers=('purchased_again', 'sum'), repeat_purchase_rate=('purchased_again', 'mean'), avg_future_spend_gbp=('future_spend_gbp', 'mean')).reset_index()
    # Wilson intervals for a proportion; these are not campaign-effect intervals.
    n, p, z = summary.customers, summary.repeat_purchase_rate, 1.96
    center = (p + z*z / (2*n)) / (1 + z*z/n)
    radius = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    summary['repeat_rate_lower_95'] = (center - radius).clip(0, 1)
    summary['repeat_rate_upper_95'] = (center + radius).clip(0, 1)
    contingency = pd.crosstab(observed.segment, observed.purchased_again)
    association = {'test': 'Chi-square: segment vs later purchase', 'p_value': None, 'minimum_expected_count': None}
    if contingency.shape[0] >= 2 and contingency.shape[1] == 2:
        stat, pvalue, _, expected = chi2_contingency(contingency)
        association.update(chi_square=float(stat), p_value=float(pvalue), minimum_expected_count=float(expected.min()), cramers_v=float(np.sqrt(stat / contingency.to_numpy().sum() / min(contingency.shape[0]-1, contingency.shape[1]-1))))
    metadata = {'cutoff_exclusive_training': str(cutoff.date()), 'observation_end_exclusive': str(end.date()), 'horizon_days': horizon_days, 'training_lookback_days': 365, 'customers': len(observed), 'chosen_k': int(evaluation.loc[evaluation.silhouette_score.idxmax(), 'k']), 'association': association, 'limitation': 'Observational historical validation; no causal or deployed retention improvement is measured.'}
    return summary, observed, metadata
