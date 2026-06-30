"""Rolling Value at Risk (VaR) estimation engine.

Reusable functions for computing rolling VaR and exceedance counts on a daily
return series. The driver script ``var_backtest.py`` imports this as ``vl`` and
calls ``vl.rolling_var`` / ``vl.rolling_exceedance_count``.

``rolling_var`` supports six methods, selected by the ``method`` argument:

    "SD-Scaled"               - trailing std dev, scaled by the normal z-score
    "Historical"              - empirical worst-tail return
    "ES-Equiv-Historical"     - mean of the worst-tail returns (expected shortfall)
    "EW-SD-Scaled"            - half-life weighted std dev, scaled by the z-score
    "EW-Historical"           - half-life weighted worst-tail return
                                (Boudoukh-Richardson-Whitelaw weighted-quantile)
    "EW-ES-Equiv-Historical"  - half-life weighted mean of the worst-tail returns

The confidence level is supplied per call via ``var_percentile`` (e.g. 0.99 for
plain VaR; 0.9745 for the expected-shortfall methods, whose 97.45% tail mean
equals the 99% normal VaR). Quantile methods use a tail probability of
``1 - var_percentile``.

All VaR figures are reported as a positive loss magnitude (e.g. 0.0233 == a
2.33% loss). Estimates are "beginning of day": the window for day t ends on day
t-1, so a day's return is never used in its own estimate and can serve as an
out-of-sample test. A value is only emitted once the full trailing window of
history is available; earlier rows are NaN.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

TRADING_DAYS_PER_YEAR = 252
EXCEEDANCE_WINDOW_YEARS = 1


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


def weighted_expected_shortfall(
    values: np.ndarray, weights: np.ndarray, tail_probability: float
) -> float:
    """Mean of the worst ``tail_probability`` of weight mass (positive loss).

    Sorts values ascending, then averages exactly the worst ``tail_probability``
    of the total weight mass, fractionally including the single boundary
    observation so the averaged mass is exactly ``tail_probability``. With equal
    weights this is the expected shortfall at the ``1 - tail_probability`` level.
    """
    order = np.argsort(values)
    sorted_values = values[order]
    mass = weights[order] / np.sum(weights)
    mass_before = np.cumsum(mass) - mass                       # mass strictly worse than each obs
    take = np.clip(tail_probability - mass_before, 0.0, mass)  # each obs's mass inside the tail
    return float(-np.sum(take * sorted_values) / tail_probability)


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
        One of "SD-Scaled", "Historical", "ES-Equiv-Historical", "EW-SD-Scaled",
        "EW-Historical", "EW-ES-Equiv-Historical".
    var_percentile : float
        Confidence level of interest. Pass 0.99 for the plain VaR methods and
        0.9745 for the expected-shortfall methods (whose 97.45% tail mean equals
        the 99% normal VaR).
    years : int
        Length of the trailing window, in years (converted to trading days).
    half_life_years : float
        Half-life for the EW methods ("EW-SD-Scaled", "EW-Historical",
        "EW-ES-Equiv-Historical"), in years.
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
    methods use a tail probability of ``1 - var_percentile``; the std-dev methods
    (``SD-Scaled``, ``EW-SD-Scaled``) scale by ``norm.ppf(var_percentile)``.
    """
    tail_probability = 1 - var_percentile

    if method == "SD-Scaled":
        return norm.ppf(var_percentile) * window.std(ddof=1)

    if method == "Historical":
        return -np.quantile(window, tail_probability)

    if method == "ES-Equiv-Historical":
        equal_weights = np.ones(len(window))
        return weighted_expected_shortfall(window, equal_weights, tail_probability)

    if method == "EW-SD-Scaled":
        # Half-life weighted std dev, matching the pandas ewm(halflife=)
        # convention used in equity_risklib, but restricted to this window.
        ewma_std = (
            pd.Series(window)
            .ewm(halflife=half_life_days, adjust=True)
            .std()
            .iloc[-1]
        )
        return norm.ppf(var_percentile) * ewma_std

    if method == "EW-Historical":
        weights = half_life_weights(len(window), half_life_days)
        return -weighted_quantile(window, weights, tail_probability)

    if method == "EW-ES-Equiv-Historical":
        # Expected-shortfall analogue of EW-Historical: the half-life weighted
        # mean of the worst tail of returns (by weight mass), integrating to
        # exactly the tail mass with a fractional boundary observation.
        weights = half_life_weights(len(window), half_life_days)
        return weighted_expected_shortfall(window, weights, tail_probability)

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
    reported once a full window of defined exceedance indicators exists. The
    returned series renames the ``var_`` column prefix to ``exc_``.
    """
    window_days = years * TRADING_DAYS_PER_YEAR

    # Exceedance flag, left undefined (NaN) on days with no VaR estimate so the
    # full-window requirement below is judged on genuinely comparable days.
    is_exceedance = (returns < -var_estimates).astype(float)
    is_exceedance[var_estimates.isna()] = np.nan

    counts = is_exceedance.rolling(window=window_days, min_periods=window_days).sum()
    return counts.rename(var_estimates.name.replace("var_", "exc_"))
