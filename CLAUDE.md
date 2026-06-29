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
- **99% z-score:** `Z_SCORE_99 = norm.ppf(0.99)` (~2.3263), not hard-coded.
- **ES trick:** the 97.45% expected shortfall of a normal equals its 99% VaR, so
  ES-style methods average the worst `ES_TAIL_PROBABILITY = 0.0255` of returns.

## The six VaR methods (`_window_var`)
| method key | column | idea |
| --- | --- | --- |
| `parametric` | `var_param_3y` | std × z99 |
| `historical` | `var_hist_3y` | empirical 1% quantile |
| `expected_shortfall` | `var_es_3y` | mean of worst 2.55% |
| `ewma` | `var_ewma_5y` | half-life weighted std × z99 (windowed `ewm`) |
| `brw` | `var_brw_5y` | half-life weighted 1% quantile (BRW) |
| `brw_es` | `var_brw_es_5y` | half-life weighted mean of worst 2.55% (ES form of BRW) |

Naming note: column abbreviations differ from method keys (`parametric`→`param`,
`historical`→`hist`, `expected_shortfall`→`es`). "BRW" = Boudoukh-Richardson-
Whitelaw (not "bsw").

## Exceedance counts (`rolling_exceedance_count`)
For each VaR column, the count of days in the trailing 252 days **inclusive of
today** where `Return_Value < -VaR`. Column names mirror the VaR columns with
`var_` → `exc_`. NaN until a full year of defined indicators exists. Expected
count for a well-calibrated 99% VaR ≈ 2.5 (1% of 252). Note the counts overlap
day-to-day, so they're a smoothed tally, not independent observations.

## How to extend
- **Add a VaR method:** add a branch in `_window_var`, then one `results[...] =
  rolling_var(...)` line in `main()` and append the column name to `var_columns`
  (so it also gets an exceedance count).
- **Add a weighted tail statistic:** reuse `weighted_quantile`; it underpins both
  `brw` and `brw_es`.

## Running
```bash
python generate_data.py   # -> returns.xlsx
python var_backtest.py    # -> var_backtest_results.csv
```
Needs `pandas`, `numpy`, `scipy`, `openpyxl`. Use a Python env that has them
installed (a project venv or whichever interpreter the user has provisioned).
