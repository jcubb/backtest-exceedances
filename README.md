# backtest-exceedances

Rolling 99% daily Value at Risk (VaR) on a simulated return series, estimated
six different ways, with trailing-year exceedance counts to compare how well
each method is calibrated.

## What it does

1. **`generate_data.py`** simulates 10 years of fake daily (weekday) returns —
   iid Normal with mean zero and a 1% daily standard deviation — and writes them
   to `returns.xlsx` (one sheet, columns `Return_Date` and `Return_Value`).

2. **`var_backtest.py`** reads that file and adds, for every day, six rolling
   estimates of 99% VaR plus a trailing-year exceedance count for each. Results
   are written to `var_backtest_results.csv`.

## VaR methods

All figures are reported as a positive loss magnitude (e.g. `0.0233` = a 2.33%
loss). Each estimate is a **beginning-of-day** figure: the trailing window for
day *t* ends on day *t-1*, so a day's return is never used in its own estimate
and can serve as an out-of-sample test.

| Column | Method | Window |
| --- | --- | --- |
| `var_param_3y` | Trailing standard deviation × 99% normal z-score | 3 years |
| `var_hist_3y` | Empirical worst-1% historical return | 3 years |
| `var_es_3y` | Mean of the worst 2.55% of returns (97.45% expected shortfall = 99% normal VaR) | 3 years |
| `var_ewma_3y` | One-year half-life weighted std dev × 99% normal z-score | 3 years |
| `var_brw_3y` | Boudoukh-Richardson-Whitelaw weighted-quantile: worst-1% return with one-year half-life observation weights | 3 years |
| `var_brw_es_3y` | Expected-shortfall form of BRW: half-life weighted average of the worst 2.55% of returns (the weighted analogue of `var_es_3y`) | 3 years |

The confidence level is supplied per call via `rolling_var(..., var_percentile=...)`:
pass `0.99` for the plain VaR methods and `0.9745` for the expected-shortfall
methods (whose 97.45% tail mean equals the 99% normal VaR). Quantile methods use
a tail probability of `1 - var_percentile`; the parametric methods scale by
`norm.ppf(var_percentile)`.

## Exceedance counts

| Column | Meaning |
| --- | --- |
| `exc_param_3y`, `exc_hist_3y`, `exc_es_3y`, `exc_ewma_3y`, `exc_brw_3y`, `exc_brw_es_3y` | Number of days in the trailing 1 year (252 trading days, **inclusive of the current day**) whose realised return fell below `-VaR`. For a well-calibrated 99% VaR the expected count is ~2.5 (1% of 252). |

## Design notes

- Trailing windows are expressed in trading days via a `years` argument, so
  switching a method from, say, 3 years to 4 years is a one-line change at the
  call site.
- The half-life weighting uses the same `0.5 ** (age / half_life)` convention as
  pandas' `ewm(halflife=)`.
- The two core functions are `rolling_var()` (dispatches the six methods) and
  `weighted_quantile()` (the weighted-quantile helper behind both BRW methods).

## Running it

```bash
python generate_data.py   # writes returns.xlsx
python var_backtest.py    # writes var_backtest_results.csv
```

Requires `pandas`, `numpy`, `scipy`, and `openpyxl`.

## License

[MIT](LICENSE)
