"""Weekly gross merchandise sales: rolling validation, untouched holdout, baselines."""
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

MODELS = ['last_week', 'seasonal_naive', 'linear_trend', 'harmonic_trend']


def weekly_sales(lines):
    dates = pd.to_datetime(lines.invoice_date)
    if dates.empty:
        raise ValueError('No retail lines available')
    first, last = dates.min().normalize(), dates.max().normalize()
    # Only Monday-Sunday weeks fully contained within the source date range.
    first_monday = first + pd.Timedelta(days=(-first.weekday()) % 7)
    last_sunday = last - pd.Timedelta(days=(last.weekday() + 1) % 7)
    if last_sunday < first_monday:
        raise ValueError('No complete weeks in the source')
    index = pd.date_range(first_monday, last_sunday, freq='D')
    purchases = lines.loc[lines.is_cancellation.eq(0)].copy()
    purchases['day'] = pd.to_datetime(purchases.invoice_date).dt.normalize()
    daily = purchases.groupby('day').amount_pence.sum().reindex(index, fill_value=0) / 100
    return daily.resample('W-SUN').sum().rename('gross_sales_gbp')


def design(t, harmonic=False):
    t = np.asarray(t)
    columns = [t]
    if harmonic:
        columns.extend([np.sin(2*np.pi*t/52.18), np.cos(2*np.pi*t/52.18)])
    return np.column_stack(columns)


def predict(train, horizon, model):
    values = np.asarray(train, dtype=float)
    if len(values) < 2 or horizon < 1 or not np.isfinite(values).all():
        raise ValueError('Need at least two finite observations and a positive horizon')
    if model == 'last_week':
        result = np.repeat(values[-1], horizon)
    elif model == 'seasonal_naive':
        if len(values) < 52:
            raise ValueError('Seasonal naive requires at least 52 weeks')
        history = list(values)
        for _ in range(horizon):
            history.append(history[-52])
        result = np.array(history[-horizon:])
    elif model in ['linear_trend', 'harmonic_trend']:
        harmonic = model == 'harmonic_trend'
        estimator = LinearRegression().fit(design(np.arange(len(values)), harmonic), values)
        result = estimator.predict(design(np.arange(len(values), len(values)+horizon), harmonic))
    else:
        raise ValueError(f'Unknown model: {model}')
    return np.maximum(result, 0)


def metrics(actual, predicted):
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    error = actual - predicted
    denominator = float(np.abs(actual).sum())
    return {'mae_gbp': float(np.abs(error).mean()), 'rmse_gbp': float(np.sqrt(np.square(error).mean())), 'wape_pct': float(np.abs(error).sum()/denominator*100) if denominator else None}


def evaluate_and_forecast(series, horizon=13, holdout_weeks=13, validation_weeks=8, folds=3, min_train=52):
    series = series.sort_index()
    if not isinstance(series.index, pd.DatetimeIndex) or not series.index.equals(pd.date_range(series.index.min(), periods=len(series), freq='W-SUN')):
        raise ValueError('Expected a continuous weekly Sunday-indexed series')
    minimum = min_train + folds*validation_weeks + holdout_weeks
    if len(series) < minimum:
        raise ValueError(f'Need at least {minimum} complete weeks, got {len(series)}')
    if min(horizon, holdout_weeks, validation_weeks, folds) < 1:
        raise ValueError('Horizons and fold count must be positive')
    development = series.iloc[:-holdout_weeks]
    holdout = series.iloc[-holdout_weeks:]
    validation, predictions = [], []
    for name in MODELS:
        all_actual, all_pred = [], []
        for fold in range(folds):
            split = len(development) - (folds-fold)*validation_weeks
            train = development.iloc[:split]
            actual = development.iloc[split:split+validation_weeks]
            predicted = predict(train, len(actual), name)
            all_actual.extend(actual)
            all_pred.extend(predicted)
            for date, value, pred in zip(actual.index, actual, predicted):
                predictions.append({'model': name, 'fold': fold+1, 'week': date, 'actual_gbp': value, 'predicted_gbp': pred, 'training_end': train.index[-1]})
        validation.append({'model': name, **metrics(all_actual, all_pred)})
    validation = pd.DataFrame(validation).sort_values('mae_gbp').reset_index(drop=True)
    selected = str(validation.iloc[0].model)
    holdout_metrics, holdout_predictions = [], []
    for name in MODELS:
        predicted = predict(development, len(holdout), name)
        holdout_metrics.append({'model': name, 'selected_on_validation': name == selected, **metrics(holdout, predicted)})
        for date, actual, pred in zip(holdout.index, holdout, predicted):
            holdout_predictions.append({'model': name, 'week': date, 'actual_gbp': actual, 'predicted_gbp': pred})
    future_index = pd.date_range(series.index[-1]+pd.Timedelta(weeks=1), periods=horizon, freq='W-SUN')
    future = pd.DataFrame({'week': future_index, 'forecast_gbp': predict(series, horizon, selected), 'model': selected})
    metadata = {'selected_model': selected, 'selection_metric': 'Lowest pooled rolling-validation MAE', 'complete_weeks': len(series), 'validation_folds': folds, 'validation_weeks_per_fold': validation_weeks, 'holdout_weeks': holdout_weeks, 'holdout_start': str(holdout.index[0].date()), 'holdout_end': str(holdout.index[-1].date()), 'forecast_horizon_weeks': horizon, 'target': 'Weekly gross merchandise sales in GBP; excludes cancellation lines and non-merchandise adjustments.', 'uncertainty': 'No calibrated prediction intervals claimed. Two annual cycles limit seasonality evidence.', 'forecast_context': 'Historical forward projection from the dataset end, not a current sales forecast.'}
    return {'validation_metrics': validation, 'validation_predictions': pd.DataFrame(predictions), 'holdout_metrics': pd.DataFrame(holdout_metrics), 'holdout_predictions': pd.DataFrame(holdout_predictions), 'forecast': future, 'metadata': metadata}
