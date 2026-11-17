import numpy as np
import pandas as pd
import pytest
from forecasting import weekly_sales, predict, evaluate_and_forecast, metrics


def weekly_series():
    t=np.arange(110)
    return pd.Series(1000+3*t+100*np.sin(2*np.pi*t/52), index=pd.date_range('2009-12-06',periods=110,freq='W-SUN'))


def test_partial_weeks_excluded_and_zero_weeks_kept():
    lines=pd.DataFrame({'invoice_date':pd.to_datetime(['2011-01-05','2011-01-10','2011-01-24','2011-01-27']), 'is_cancellation':[0,0,0,0], 'amount_pence':[99900,10000,88800,77700]})
    result=weekly_sales(lines)
    assert list(result.index)==[pd.Timestamp('2011-01-16'),pd.Timestamp('2011-01-23')]
    assert list(result)==[100,0]


def test_cancelled_lines_do_not_inflate_gross_sales():
    lines=pd.DataFrame({'invoice_date':pd.to_datetime(['2011-01-03','2011-01-05','2011-01-09']), 'is_cancellation':[0,1,0], 'amount_pence':[10000,-5000,10000]})
    assert weekly_sales(lines).iloc[0]==200


def test_selection_never_uses_final_holdout():
    original=weekly_series()
    first=evaluate_and_forecast(original)
    changed=original.copy()
    changed.iloc[-13:]*=10
    second=evaluate_and_forecast(changed)
    pd.testing.assert_frame_equal(first['validation_metrics'],second['validation_metrics'])
    assert first['metadata']['selected_model']==second['metadata']['selected_model']
    assert not first['holdout_metrics'].equals(second['holdout_metrics'])


def test_rolling_predictions_are_strictly_after_training():
    results=evaluate_and_forecast(weekly_series())
    predictions=results['validation_predictions']
    assert (predictions.week>predictions.training_end).all()
    assert len(results['forecast'])==13
    assert results['forecast'].week.min()>weekly_series().index.max()


def test_seasonal_naive_uses_last_year():
    assert list(predict(np.arange(60),3,'seasonal_naive'))==[8,9,10]


def test_small_series_rejected():
    with pytest.raises(ValueError,match='at least'):
        evaluate_and_forecast(weekly_series().iloc[:60])


def test_missing_week_rejected():
    with pytest.raises(ValueError,match='continuous'):
        evaluate_and_forecast(weekly_series().drop(weekly_series().index[70]))


def test_wape_handles_zero_actuals():
    score=metrics([0,0],[1,1])
    assert score['wape_pct'] is None
    assert score['mae_gbp']==1
