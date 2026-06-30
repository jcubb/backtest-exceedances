# backtest-exceedances

Rolling 99% daily Value at Risk (VaR) on a simulated return series, estimated
six different ways, with trailing-year exceedance counts to compare how well
each method is calibrated.

## What it does

1. **`generate_data.py`** simulates 10 years of fake daily (weekday) returns —
   iid Normal with mean zero and a 1% daily standard deviation — and writes them
   to `returns.xlsx` (one sheet, columns `Return_Date` and `Return_Value`).

2. **`var_backtest.py`** reads that file and adds, for every day, six rolling
   VaR estimates plus a trailing-year exceedance count for each, then writes
   `var_backtest_results.csv`. It's a thin driver: the VaR/exceedance engine
   lives in **`varlib.py`** (imported as `vl`), which it calls for every metric.

## VaR methods

All figures are reported as a positive loss magnitude (e.g. `0.0233` = a 2.33%
loss). Each estimate is a **beginning-of-day** figure: the trailing window for
day *t* ends on day *t-1*, so a day's return is never used in its own estimate
and can serve as an out-of-sample test.

Result columns are named `var_<name>_<window>_<percentile>[_hl<half_life>y]`, so
each series carries its own window, VaR threshold, and (for the exponentially
weighted methods) half-life — e.g. `var_ES-Equiv-Historical_3y_97.45` or
`var_EW-Historical_3y_99_hl1y`.

| Name | Method | Window |
| --- | --- | --- |
| `SD-Scaled` | Equal-weight standard deviation, scaled to VaR with the Normal z-score | 3 years |
| `Historical` | Empirical worst-tail return over the window | 3 years |
| `ES-Equiv-Historical` | Mean of the worst-tail returns, at the shortfall level that equals the Normal VaR | 3 years |
| `EW-SD-Scaled` | Exponentially weighted standard deviation, scaled to VaR with the Normal z-score | 3 years |
| `EW-Historical` | Exponentially weighted empirical worst-tail return (Boudoukh-Richardson-Whitelaw weighted-quantile) | 3 years |
| `EW-ES-Equiv-Historical` | Exponentially weighted mean of the worst-tail returns (weighted expected shortfall) | 3 years |

The confidence level is supplied per call via `rolling_var(..., var_percentile=...)`:
pass `0.99` for the plain VaR methods and `0.9745` for the expected-shortfall
methods (whose 97.45% tail mean equals the 99% normal VaR). Quantile methods use
a tail probability of `1 - var_percentile`; the std-dev methods scale by
`norm.ppf(var_percentile)`.

## Exceedance counts

| Column | Meaning |
| --- | --- |
| One `exc_<name>_<window>_<percentile>` per VaR column | Number of days in the trailing 1 year (252 trading days, **inclusive of the current day**) whose realised return fell below `-VaR`. For a well-calibrated 99% VaR the expected count is ~2.5 (1% of 252). |

## Design notes

- Trailing windows are expressed in trading days via a `years` argument, so
  switching a method from, say, 3 years to 4 years is a one-line change at the
  call site.
- The half-life weighting uses the same `0.5 ** (age / half_life)` convention as
  pandas' `ewm(halflife=)`.
- The engine lives in `varlib.py`: `rolling_var()` (dispatches the six methods),
  `weighted_quantile()` and `weighted_expected_shortfall()` (the weighted-tail
  helpers behind the EW methods), and `rolling_exceedance_count()`.
  `var_backtest.py` just configures the metric list and calls them.

## Running it

```bash
python generate_data.py   # writes returns.xlsx
python var_backtest.py    # writes var_backtest_results.csv
```

Requires `pandas`, `numpy`, `scipy`, and `openpyxl`.

## Viewing the results

`report.html` is a standalone, dependency-free report — no server, no build step.
Open it in any browser, then load (or drag in) a `var_backtest_results.csv`. It
detects which metrics are present, lets you toggle any subset on/off, and draws
two charts: the rolling VaR estimates and the trailing-year exceedance counts.
A `Historical` series, if present, is drawn as a dotted line (the current
methodology); every other metric gets a solid line in a distinct color. Each
series name shows its window and VaR threshold, e.g. `(3y, 97.45)`. Hovering
shows the values for every selected metric on that date.

To embed the report **inside a Jupyter notebook**, open `embed_report.ipynb` and
run the cell (or copy it into your own notebook). It bakes the CSV into the page
and displays it via an `IFrame` — a Markdown cell won't work, because Jupyter
strips the report's `<script>` for security.

## License

[MIT](LICENSE)
