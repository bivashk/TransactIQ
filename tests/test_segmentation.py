import pandas as pd
import numpy as np
from segmentation import get_rfm_data, run_segmentation, summarize_segments, validate_segments


def test_rfm_counts_invoices_and_excludes_anonymous_and_returns(clean):
    rfm=get_rfm_data(clean, as_of='2011-01-12')
    assert len(rfm)==1
    assert rfm.iloc[0].frequency==1
    assert rfm.iloc[0].monetary==9
    assert 8 < rfm.iloc[0].recency_days < 9


def test_rfm_is_strictly_before_cutoff(clean):
    clean.loc[0,'invoice_date']=pd.Timestamp('2011-01-03')
    rfm=get_rfm_data(clean, as_of='2011-01-03')
    assert rfm.empty


def test_future_values_cannot_change_training_features(customer_history):
    cutoff=pd.Timestamp('2011-08-04')
    original=get_rfm_data(customer_history, as_of=cutoff)
    altered=customer_history.copy()
    altered.loc[altered.invoice_date>=cutoff,'amount_pence']=999999999
    pd.testing.assert_frame_equal(original,get_rfm_data(altered, as_of=cutoff))


def test_segmentation_selection_and_summary(customer_history):
    rfm, _, evaluation=run_segmentation(customer_history)
    assert rfm.cluster.nunique()==int(evaluation.loc[evaluation.silhouette_score.idxmax(),'k'])
    assert rfm.segment.notna().all()
    summary=summarize_segments(rfm)
    assert np.isclose(summary.sales_share_pct.sum(),100)
    assert np.isclose(summary.customer_share_pct.sum(),100)


def test_later_outcomes_do_not_refit_earlier_segments(customer_history):
    summary, observed, meta=validate_segments(customer_history)
    altered=customer_history.copy()
    cutoff=pd.Timestamp(meta['cutoff_exclusive_training'])
    altered.loc[altered.invoice_date>=cutoff,'amount_pence']*=100
    _, changed, _=validate_segments(altered)
    pd.testing.assert_series_equal(observed.segment,changed.segment)
    pd.testing.assert_series_equal(observed.monetary,changed.monetary)
    assert summary.repeat_purchase_rate.between(0,1).all()
    assert (summary.repeat_rate_lower_95<=summary.repeat_purchase_rate).all()
    assert (summary.repeat_rate_upper_95>=summary.repeat_purchase_rate).all()
