# CLAUDE.md — backtest-exceedances

Context for working on this project. The user-facing overview is in `README.md`;
this file records the **conventions and design decisions** so future changes stay
consistent.

## Purpose
Estimate rolling 99% daily VaR on a simulated return series six ways and score
each with trailing-year exceedance counts. It's a self-contained demo of VaR
estimation methods, not a production risk system.

## Files
- `generate_data.py` — simulates 10yr of weekday returns, N(0, 0.01), seeded
  (`RANDOM_SEED = 42`), writes `returns.xlsx` (sheet "Returns", columns
  `Return_Date`, `Return_Value`).
- `varlib.py` — the **VaR engine** (imported as `vl`): `rolling_var`,
  `weighted_quantile`, `weighted_expected_shortfall`, `half_life_weights`,
  `_window_var`, `rolling_exceedance_count`, and the `TRADING_DAYS_PER_YEAR` /
  `EXCEEDANCE_WINDOW_YEARS` constants. No I/O, no `main`.
- `var_backtest.py` — thin **driver**: reads the xlsx, holds the `metrics` config
  table, calls `vl.rolling_var` / `vl.rolling_exceedance_count` per metric, writes
  `var_backtest_results.csv`.
- `returns.xlsx`, `var_backtest_results.csv` — generated outputs, git-ignored
  (reproducible from the scripts).

## Conventions (keep these consistent)
- **VaR sign:** positive loss magnitude (e.g. `0.0233` = a 2.33% loss).
- **Window unit:** trailing windows are in trading days via a `years` argument
  (`TRADING_DAYS_PER_YEAR = 252`). Changing 3yr→4yr is a one-line change at the
  call site in `main()`. Never hard-code day counts elsewhere.
- **Beginning-of-day estimate:** the window for day *t* ends on day *t-1*
  (`values[day - window_days:day]`, result stored at `day`). Today's return is
  excluded from today's VaR so it can serve as an out-of-sample test.
- **Warm-up:** VaR is NaN until a full trailing window exists.
- **Half-life weighting:** `0.5 ** (age / half_life_days)`, half_life_days =
  `half_life_years * 252`. This matches pandas `ewm(halflife=)` and the
  `equity_risklib.risk_model` convention used elsewhere in the user's code.
- **Confidence level:** passed per call as `var_percentile` (one argument
  threaded `rolling_var` → `_window_var`); there are no `CONFIDENCE`/`Z_SCORE_99`/
  `ES_TAIL_PROBABILITY` globals. Quantile methods use `1 - var_percentile`; the
  std-dev methods (`SD-Scaled`, `EW-SD-Scaled`) scale by `norm.ppf(var_percentile)`.
- **ES trick:** the 97.45% expected shortfall of a normal equals its 99% VaR, so
  the ES methods are called with `var_percentile = 0.9745` (→ worst 2.55% tail).
  The plain VaR methods are called with `0.99`.

## The six VaR methods (`varlib._window_var`)
The method name IS the dispatch key — there is no separate display name. The
engine understands these strings directly:

| method | idea |
| --- | --- |
| `SD-Scaled` | std × z (`norm.ppf(var_percentile)`) |
| `Historical` | empirical worst-tail quantile |
| `ES-Equiv-Historical` | mean of worst-tail (ES) |
| `EW-SD-Scaled` | half-life weighted std × z (windowed `ewm`) |
| `EW-Historical` | half-life weighted worst-tail quantile (BRW) |
| `EW-ES-Equiv-Historical` | half-life weighted mean of worst-tail (BRW-ES) |

`var_backtest.py:main()` holds a `metrics` list of
`(method, var_percentile, half_life_years)` (half-life is `None` for the
equal-weight methods) and builds columns as
**`var_<method>_<years>y_<pct>[_hl<hl>y]`** — e.g. `var_ES-Equiv-Historical_3y_97.45`
or `var_EW-Historical_3y_99_hl1y`. The method names carry no underscores, so
`report.html` splits on `_` into method / window / threshold / half-life and
labels each series accordingly. (Engine moved to `varlib.py` and methods renamed
to these unified names 2026-06-30 — there is no longer a `parametric`/`brw`/etc.
key.)

The example `main()` runs all six on a **3-year** window at 0.99 (VaR methods) or
0.9745 (ES methods), EW methods at a 1-year half-life. Add rows to `metrics` to
compare, e.g. EW metrics at different half-lives — each gets its own column and
series. Changing `years` flows into the column names automatically.

## Exceedance counts (`rolling_exceedance_count`)
For each VaR column, the count of days in the trailing 252 days **inclusive of
today** where `Return_Value < -VaR`. Column names mirror the VaR columns with
`var_` → `exc_`. NaN until a full year of defined indicators exists. Expected
count for a well-calibrated 99% VaR ≈ 2.5 (1% of 252). Note the counts overlap
day-to-day, so they're a smoothed tally, not independent observations.

## Known wrinkles (quantile discreteness)
- **Two different interpolation conventions.** The equal-weight methods
  (`Historical`, and the `ES-Equiv-Historical` threshold) use `np.quantile`'s
  default linear/**R-7** estimator (virtual index `p·(n−1)`). The weighted
  methods (`EW-Historical`, `EW-ES-Equiv-Historical`) use `weighted_quantile`,
  whose `cumsum(w) − 0.5·w` plotting position reduces to the **Hazen (type-5)**
  position `(k+0.5)/n` when weights are equal. So `Historical` and `EW-Historical`
  do **not** numerically agree in the equal-weight limit (they differ by ~½ a
  rank). This is a deliberate, un-fixed inconsistency — left as-is on purpose; do
  not "harmonize" it without asking.
- **ES integrates to exact mass.** Both ES methods (`ES-Equiv-Historical`,
  `EW-ES-Equiv-Historical`) go through `weighted_expected_shortfall`, which averages exactly the
  worst `tail_probability` of weight mass with a fractional boundary observation
  — so there is no whole-observation discreteness on the ES side. (This was a
  prior wrinkle, now resolved.)

## How to extend
- **Add a metric run:** append a row to the `metrics` table in
  `var_backtest.py:main()` — `(method, percentile, half_life_years)`. The loop
  builds its column (and exceedance count) automatically. Use this to compare EW
  methods at different half-lives or different windows/thresholds.
- **Add a new VaR method:** add a branch in `varlib._window_var` keyed on the new
  method name, then reference that name from a `metrics` row.
- **Add a weighted tail statistic:** reuse `varlib.weighted_quantile` (underpins
  `EW-Historical`) or `varlib.weighted_expected_shortfall` (underpins
  `ES-Equiv-Historical` and `EW-ES-Equiv-Historical`, with equal vs half-life
  weights).

## Running
```bash
python generate_data.py   # -> returns.xlsx
python var_backtest.py    # -> var_backtest_results.csv
```
Needs `pandas`, `numpy`, `scipy`, `openpyxl`. Use a Python env that has them
installed (a project venv or whichever interpreter the user has provisioned).
