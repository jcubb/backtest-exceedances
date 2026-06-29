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
- `var_backtest.py` — reads the xlsx, computes the six VaR columns and six
  exceedance-count columns, writes `var_backtest_results.csv`.
- `returns.xlsx`, `var_backtest_results.csv` — generated outputs, git-ignored
  (reproducible from the two scripts).

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
  `ES_TAIL_PROBABILITY` globals. Quantile methods use `1 - var_percentile`;
  parametric methods scale by `norm.ppf(var_percentile)`, computed in-method.
- **ES trick:** the 97.45% expected shortfall of a normal equals its 99% VaR, so
  the ES methods are called with `var_percentile = 0.9745` (→ worst 2.55% tail).
  The plain VaR methods are called with `0.99`.

## The six VaR methods (`_window_var`)
| method key | column | idea |
| --- | --- | --- |
| `parametric` | `var_param_3y` | std × z (`norm.ppf(var_percentile)`) |
| `historical` | `var_hist_3y` | empirical 1% quantile |
| `expected_shortfall` | `var_es_3y` | mean of worst 2.55% |
| `ewma` | `var_ewma_3y` | half-life weighted std × z (windowed `ewm`) |
| `brw` | `var_brw_3y` | half-life weighted 1% quantile (BRW) |
| `brw_es` | `var_brw_es_3y` | half-life weighted mean of worst 2.55% (ES form of BRW) |

The example `main()` runs all six on a **3-year** window. Column names encode the
window (`_3y`); if you change `years`, rename the columns to match.

Naming note: column abbreviations differ from method keys (`parametric`→`param`,
`historical`→`hist`, `expected_shortfall`→`es`). "BRW" = Boudoukh-Richardson-
Whitelaw (not "bsw").

## Exceedance counts (`rolling_exceedance_count`)
For each VaR column, the count of days in the trailing 252 days **inclusive of
today** where `Return_Value < -VaR`. Column names mirror the VaR columns with
`var_` → `exc_`. NaN until a full year of defined indicators exists. Expected
count for a well-calibrated 99% VaR ≈ 2.5 (1% of 252). Note the counts overlap
day-to-day, so they're a smoothed tally, not independent observations.

## Known wrinkles (quantile discreteness)
- **Two different interpolation conventions.** The equal-weight methods
  (`historical`, and the `expected_shortfall` threshold) use `np.quantile`'s
  default linear/**R-7** estimator (virtual index `p·(n−1)`). The weighted
  methods (`brw`, `brw_es`) use `weighted_quantile`, whose `cumsum(w) − 0.5·w`
  plotting position reduces to the **Hazen (type-5)** position `(k+0.5)/n` when
  weights are equal. So `historical` and `brw` do **not** numerically agree in
  the equal-weight limit (they differ by ~½ a rank). This is a deliberate,
  un-fixed inconsistency — left as-is on purpose; do not "harmonize" it without
  asking.
- **ES integrates to exact mass.** Both ES methods (`expected_shortfall`,
  `brw_es`) go through `weighted_expected_shortfall`, which averages exactly the
  worst `tail_probability` of weight mass with a fractional boundary observation
  — so there is no whole-observation discreteness on the ES side. (This was a
  prior wrinkle, now resolved.)

## How to extend
- **Add a VaR method:** add a branch in `_window_var`, then one `results[...] =
  rolling_var(...)` line in `main()` and append the column name to `var_columns`
  (so it also gets an exceedance count).
- **Add a weighted tail statistic:** reuse `weighted_quantile` (underpins `brw`)
  or `weighted_expected_shortfall` (underpins `expected_shortfall` and `brw_es`,
  with equal weights vs half-life weights respectively).

## Running
```bash
python generate_data.py   # -> returns.xlsx
python var_backtest.py    # -> var_backtest_results.csv
```
Needs `pandas`, `numpy`, `scipy`, `openpyxl`. Use a Python env that has them
installed (a project venv or whichever interpreter the user has provisioned).
