# Real-data provenance

- **Dataset:** Online Retail II
- **Creator:** Daqing Chen
- **Citation:** Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.
- **DOI:** https://doi.org/10.24432/C5CG6D
- **Source:** https://archive.ics.uci.edu/dataset/502/online+retail+ii
- **Archive:** https://archive.ics.uci.edu/static/public/502/online%2Bretail%2Bii.zip
- **License:** Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/).
- **Original scope:** 1,067,371 invoice line items, UK retailer, December 2009–December 2011; GBP.
- **Local input:** `raw/online_retail_ii.zip` (ignored in Git).
- **Source hash:** See `reports/data_quality.json` after importing.

Derived results are modified versions: exact duplicate removal, audited invalid/
non-merchandise exclusions, cancellation signing, monetary rounding, feature
engineering and aggregation. See the main README for policies and limitations.
Original simulated files live only in `legacy/synthetic/`.
