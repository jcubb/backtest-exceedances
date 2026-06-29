"""Compute several rolling estimates of 99% daily Value at Risk (VaR).

Reads the simulated returns produced by generate_data.py, then adds six rolling
VaR estimates, each built with a different methodology (all on a 3yr window in
the example ``main``):

    (1) var_param_3y   - trailing std dev, scaled by the normal z-score
    (2) var_hist_3y    - empirical worst 1% return
    (3) var_es_3y      - mean of the worst 2.55% of returns
                         (97.45% expected shortfall == 99% VaR under normality)
    (4) var_ewma_3y    - one-year half-life std dev, scaled by the normal z-score
    (5) var_brw_3y     - Boudoukh-Richardson-Whitelaw weighted-quantile: the
                         worst-1% empirical return, observations weighted with a
                         one-year half-life
    (6) var_brw_es_3y  - expected-shortfall form of BRW: half-life weighted mean
                         of the worst 2.55% of returns

The confidence level is supplied per call via ``var_percentile``: pass 0.99 for
the plain VaR methods (1, 2, 4, 5) and 0.9745 for the expected-shortfall methods
(3, 6). Quantile methods use a tail probability of ``1 - var_percentile``.

All VaR figures are reported as a positive loss magnitude (e.g. 0.0233 == a
2.33% loss). A value is only emitted once the full trailing window of history
is available; earlier rows are NaN.

The trailing window of every method is controlled by a ``years`` argument, so
switching, say, from 3 years to 4 years is a one-line change at the call site.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

TRADING_DAYS_PER_YEAR = 252
EXCEEDANCE_WINDOW_YEARS = 1

INPUT_FILE = Path(__file__).parent / "returns.xlsx"
OUTPUT_FILE = Path(__file__).parent / "var_backtest_results.csv"


def weighted_quantile(values: np.ndarray, weights: np.ndarray, probability: float) -> float:
    """Return the lower-tail quantile of ``values`` under sample ``weights``.

    Sorts values ascending, accumulates the normalised weights from the worst
    value upward, and linearly interpolates the return at which the cumulative
    weight crosses ``probability``. With equal weights this reduces to an
    ordinary empirical quantile.
    """
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]

    cumulative_weight = np.cumsum(sorted_weights) - 0.5 * sorted_weights
    cumulative_weight /= np.sum(sorted_weights)

    return float(np.interp(probability, cumulative_weight, sorted_values))


def half_life_weights(window_length: int, half_life_days: float) -> np.ndarray:
    """Exponentially decaying weights, heaviest on the most recent observation.

    The observation ``age`` days in the past receives weight 0.5 ** (age /
    half_life_days), matching the convention used by pandas' ``ewm(halflife=)``.
    Index 0 is the oldest observation in the window; the last index is newest.
    """
    ages = np.arange(window_length - 1, -1, -1)
    return 0.5 ** (ages / half_life_days)


def rolling_var(
    returns: pd.Series,
    method: str,
    var_percentile: float = 0.99,
    years: int = 3,
    half_life_years: float = 1.0,
) -> pd.Series:
    """Compute a rolling VaR series for one of the supported methods.

    Parameters
    ----------
    returns : pd.Series
        Daily return series indexed by date.
    method : str
        One of "parametric", "historical", "expected_shortfall", "ewma",
        "brw", "brw_es".
    var_percentile : float
        Confidence level of interest. Pass 0.99 for the plain VaR methods and
        0.9745 for the expected-shortfall methods (whose 97.45% tail mean equals
        the 99% normal VaR).
    years : int
        Length of the trailing window, in years (converted to trading days).
    half_life_years : float
        Half-life for the weighted methods ("ewma", "brw", "brw_es"), in years.
    """
    window_days = years * TRADING_DAYS_PER_YEAR
    half_life_days = half_life_years * TRADING_DAYS_PER_YEAR
    values = returns.to_numpy()
    var_estimates = np.full(len(values), np.nan)

    # Each estimate is a "beginning of day" figure: the window for day t ends on
    # day t-1, so today's return is never used in today's VaR and can serve as
    # an out-of-sample test of the estimate.
    for day in range(window_days, len(values)):
        window = values[day - window_days:day]
        var_estimates[day] = _window_var(window, method, half_life_days, var_percentile)

    return pd.Series(var_estimates, index=returns.index, name=f"var_{method}_{years}y")


def _window_var(
    window: np.ndarray,
    method: str,
    half_life_days: float,
    var_percentile: float,
) -> float:
    """Compute a single VaR figure (positive loss) for one trailing window.

    ``var_percentile`` is the confidence level of interest: 0.99 for the plain
    VaR methods, 0.9745 for the expected-shortfall methods. Quantile-based
    methods use a tail probability of ``1 - var_percentile``; the parametric
    methods scale the std dev by ``norm.ppf(var_percentile)``.
    """
    tail_probability = 1 - var_percentile

    if method == "parametric":
        return norm.ppf(var_percentile) * window.std(ddof=1)

    if method == "historical":
        return -np.quantile(window, tail_probability)

    if method == "expected_shortfall":
        threshold = np.quantile(window, tail_probability)
        tail_losses = window[window <= threshold]
        return -tail_losses.mean()

    if method == "ewma":
        # One-year half-life weighted std dev, matching the pandas ewm(halflife=)
        # convention used in equity_risklib, but restricted to this window.
        ewma_std = (
            pd.Series(window)
            .ewm(halflife=half_life_days, adjust=True)
            .std()
            .iloc[-1]
        )
        return norm.ppf(var_percentile) * ewma_std

    if method == "brw":
        weights = half_life_weights(len(window), half_life_days)
        return -weighted_quantile(window, weights, tail_probability)

    if method == "brw_es":
        # Expected-shortfall analogue of the BRW method: the half-life weighted
        # average of the worst tail of returns (by weight mass). Pass 0.9745 so
        # the worst 2.55% are averaged, which equals the 99% VaR under
        # normality. The weighted threshold reuses the same weighted-quantile
        # logic as the BRW method; the tail below it is then averaged using the
        # observations' exponential weights.
        weights = half_life_weights(len(window), half_life_days)
        threshold = weighted_quantile(window, weights, tail_probability)
        in_tail = window <= threshold
        return -np.average(window[in_tail], weights=weights[in_tail])

    raise ValueError(f"Unknown method: {method!r}")


def rolling_exceedance_count(
    returns: pd.Series,
    var_estimates: pd.Series,
    years: int = EXCEEDANCE_WINDOW_YEARS,
) -> pd.Series:
    """Count VaR exceedances over a trailing window, inclusive of the current day.

    A day is an exceedance when its realised return falls below ``-VaR`` (i.e.
    the loss is worse than the VaR estimate). The count looks back ``years`` of
    history and *includes* the current day's return, so it answers "how many of
    the last year's returns breached their VaR estimate". The count is only
    reported once a full window of defined exceedance indicators exists.
    """
    window_days = years * TRADING_DAYS_PER_YEAR

    # Exceedance flag, left undefined (NaN) on days with no VaR estimate so the
    # full-window requirement below is judged on genuinely comparable days.
    is_exceedance = (returns < -var_estimates).astype(float)
    is_exceedance[var_estimates.isna()] = np.nan

    counts = is_exceedance.rolling(window=window_days, min_periods=window_days).sum()
    return counts.rename(var_estimates.name.replace("var_", "exc_"))


def main() -> None:
    returns = pd.read_excel(INPUT_FILE, sheet_name="Returns")
    returns = returns.set_index("Return_Date")["Return_Value"]

    # Pass 0.99 for the plain VaR methods and 0.9745 for the expected-shortfall
    # methods (so they average the worst 2.55%, == 99% VaR under normality).
    results = returns.to_frame()
    results["var_param_3y"] = rolling_var(returns, "parametric", 0.99, years=3)
    results["var_hist_3y"] = rolling_var(returns, "historical", 0.99, years=3)
    results["var_es_3y"] = rolling_var(returns, "expected_shortfall", 0.9745, years=3)
    results["var_ewma_3y"] = rolling_var(returns, "ewma", 0.99, years=3, half_life_years=1.0)
    results["var_brw_3y"] = rolling_var(returns, "brw", 0.99, years=3, half_life_years=1.0)
    results["var_brw_es_3y"] = rolling_var(returns, "brw_es", 0.9745, years=3, half_life_years=1.0)

    var_columns = [
        "var_param_3y", "var_hist_3y", "var_es_3y", "var_ewma_3y", "var_brw_3y", "var_brw_es_3y",
    ]
    for column in var_columns:
        counts = rolling_exceedance_count(returns, results[column])
        results[counts.name] = counts

    results.to_csv(OUTPUT_FILE)
    print(f"Wrote {len(results):,} rows to {OUTPUT_FILE}")
    print(results.dropna().describe())


if __name__ == "__main__":
    main()
