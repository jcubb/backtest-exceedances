"""Driver: build the rolling-VaR backtest results CSV.

Reads the simulated returns produced by generate_data.py, computes six rolling
VaR estimates (plus a trailing-year exceedance count for each) using the engine
in ``varlib`` (imported as ``vl``), and writes them to var_backtest_results.csv.

Each metric is one row of the ``metrics`` table below: a display name, the
``varlib`` method key, the VaR percentile, and (for the exponentially weighted
methods) a half-life in years. Result columns encode all of that:

    var_<name>_<years>y_<percentile>[_hl<half_life>y]

e.g. ``var_ES-Equiv-Historical_3y_97.45`` (no half-life) or
``var_EW-Historical_3y_99_hl1y`` (1-year half-life). The matching exceedance
columns use the same suffix with an ``exc_`` prefix. report.html parses these
names to label each series with its window, threshold, and half-life.

The six metrics:

    (1) SD-Scaled               - trailing std dev, scaled by the normal z-score
    (2) Historical              - empirical worst-tail return
    (3) ES-Equiv-Historical     - mean of the worst-tail returns, at the
                                  shortfall level that equals the normal VaR
    (4) EW-SD-Scaled            - half-life weighted std dev, scaled by the z-score
    (5) EW-Historical           - half-life weighted worst-tail return
    (6) EW-ES-Equiv-Historical  - half-life weighted mean of the worst-tail returns
"""

from pathlib import Path

import pandas as pd

import varlib as vl

INPUT_FILE = Path(__file__).parent / "returns.xlsx"
OUTPUT_FILE = Path(__file__).parent / "var_backtest_results.csv"


def _column_name(name: str, years: int, percentile: float, half_life_years: float | None) -> str:
    """Build a result column name encoding name, window, threshold, half-life."""
    column = f"var_{name}_{years}y_{round(percentile * 100, 6):g}"
    if half_life_years is not None:
        column += f"_hl{half_life_years:g}y"
    return column


def main() -> None:
    returns = pd.read_excel(INPUT_FILE, sheet_name="Returns")
    returns = returns.set_index("Return_Date")["Return_Value"]

    years = 3
    # (display name, varlib method, VaR percentile, half-life in years). The
    # percentile is 0.99 for plain VaR and 0.9745 for the expected-shortfall
    # methods (their 97.45% shortfall equals the 99% VaR under normality). The
    # half-life is None for the equal-weight methods. Add rows here to compare,
    # e.g. EW metrics at different half-lives.
    metrics = [
        ("SD-Scaled", "parametric", 0.99, None),
        ("Historical", "historical", 0.99, None),
        ("ES-Equiv-Historical", "expected_shortfall", 0.9745, None),
        ("EW-SD-Scaled", "ewma", 0.99, 1.0),
        ("EW-Historical", "brw", 0.99, 1.0),
        ("EW-ES-Equiv-Historical", "brw_es", 0.9745, 1.0),
    ]

    results = returns.to_frame()
    var_columns = []
    for name, method, percentile, half_life in metrics:
        column = _column_name(name, years, percentile, half_life)
        results[column] = vl.rolling_var(
            returns, method, percentile, years=years,
            half_life_years=(half_life if half_life is not None else 1.0),
        )
        var_columns.append(column)

    for column in var_columns:
        counts = vl.rolling_exceedance_count(returns, results[column])
        results[counts.name] = counts

    results.to_csv(OUTPUT_FILE)
    print(f"Wrote {len(results):,} rows to {OUTPUT_FILE}")
    print(results.dropna().describe())


if __name__ == "__main__":
    main()
