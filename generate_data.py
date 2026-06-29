"""Generate 10 years of fake daily (weekday) returns and save to an Excel file.

Output: returns.xlsx, one sheet, two columns: Return_Date and Return_Value.
Returns are drawn iid Normal with mean zero and a 1% daily standard deviation.
"""

from pathlib import Path

import numpy as np
import pandas as pd

DAILY_MEAN = 0.0
DAILY_STD = 0.01
YEARS_OF_HISTORY = 10
RANDOM_SEED = 42
OUTPUT_FILE = Path(__file__).parent / "returns.xlsx"


def generate_returns(years: int = YEARS_OF_HISTORY, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Build a DataFrame of weekday dates and simulated daily returns."""
    end_date = pd.Timestamp("2026-06-26")
    start_date = end_date - pd.DateOffset(years=years)
    return_dates = pd.bdate_range(start=start_date, end=end_date)

    rng = np.random.default_rng(seed)
    return_values = rng.normal(loc=DAILY_MEAN, scale=DAILY_STD, size=len(return_dates))

    return pd.DataFrame({"Return_Date": return_dates, "Return_Value": return_values})


def main() -> None:
    returns = generate_returns()
    returns.to_excel(OUTPUT_FILE, sheet_name="Returns", index=False)
    print(f"Wrote {len(returns):,} rows to {OUTPUT_FILE}")
    print(returns["Return_Value"].describe())


if __name__ == "__main__":
    main()
