# TransactIQ: findings from real retail records

Source: UCI Online Retail II (Daqing Chen, CC BY 4.0).

- 1,067,371 original invoice lines; 1,021,434 retained after documented cleaning.
- Merchandise gross sales: GBP 19,645,754.64; recorded cancellation value: GBP 722,660.09.
- 4,261 identified purchasing customers in the latest 365-day segmentation window.
- Earlier segments had later 90-day purchase rates of 78.3% (High-value active, 1,473 customers) versus 36.5% (At-risk / inactive, 2,829 customers). These are observed group differences, not retention lift.
- Forecast selected using earlier rolling validation: seasonal_naive. Untouched final 13-week holdout MAE: GBP 43,423.99; WAPE: 15.6%.

## Decisions supported

Prioritize customer-service and retention experiments by purchasing behaviour; plan sales capacity using a forecast benchmarked against simple alternatives; investigate countries/products with elevated recorded cancellations.

## Interpretation limits

This is an offline historical case study from 2009–2011, not a deployed retailer system. Segment association does not establish campaign effectiveness. No retention lift, cost reduction or revenue uplift is claimed. Sales values are merchandise invoice values, not audited revenue or profit. A cancellation is not a failed payment, and cancellations are not matched back to original invoices. Missing customer IDs remain in sales totals but not customer analyses. Exact duplicates are removed under a disclosed assumption. The final calendar month is partial; weekly forecasting excludes boundary partial weeks. Forecasts extend from the historical data end, not today's date.
