"""
Data transformation utilities for the fair-shares library.

This module provides utilities for transforming and reshaping timeseries data,
including filtering time columns, broadcasting shares across periods, and
expanding non-annual data to annual values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pandas as pd

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils.dataframes import ensure_string_year_columns

if TYPE_CHECKING:
    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def filter_time_columns(
    df: TimeseriesDataFrame, allocation_time: int
) -> TimeseriesDataFrame:
    """Filter DataFrame to include only numeric columns >= allocation_time."""
    df = ensure_string_year_columns(df)
    try:
        numeric_cols = pd.to_numeric(df.columns, errors="coerce")
        return df.loc[:, numeric_cols >= allocation_time]
    except Exception as e:
        raise DataProcessingError(f"Cannot filter time columns: {e}") from e


def broadcast_shares_to_periods(
    shares: pd.Series, target_columns: pd.Index
) -> TimeseriesDataFrame:
    """Broadcast 1D shares to all target time periods."""
    return pd.DataFrame({col: shares for col in target_columns})


def expand_to_annual(
    ts: pd.DataFrame,
    start_year: int,
    end_year: int,
    method: Literal["bfill", "linear"] = "bfill",
) -> pd.DataFrame:
    """
    Expand non-annual timeseries to annual values.

    For data with multi-year intervals (e.g., 5-year or 10-year timesteps),
    this creates annual columns and fills intermediate values.

    Parameters
    ----------
    ts
        Timeseries DataFrame with string year columns (wide format).
    start_year
        First year of output range.
    end_year
        Last year of output range (inclusive).
    method
        Interpolation method:

        - "bfill": Backward fill. Each data point fills the preceding
          interval. For 5-year data, the 2020 value fills 2016-2020.
          This is appropriate for period-weighted cumulative calculations
          where each observation represents the END of an interval.
        - "linear": Linear interpolation between data points. Values change
          smoothly between observations.

    Returns
    -------
    pd.DataFrame
        Timeseries with annual columns.

    Examples
    --------
    With bfill (default): 2015=100, 2020=120 becomes
    2015=100, 2016=120, 2017=120, 2018=120, 2019=120, 2020=120
    (2015 stays at 100, years 2016-2020 get the 2020 value)

    With linear: 2015=100, 2020=120 becomes
    2015=100, 2016=104, 2017=108, 2018=112, 2019=116, 2020=120
    """
    if method not in ("bfill", "linear"):
        raise DataProcessingError(
            f"Invalid interpolation method: '{method}'. Must be 'bfill' or 'linear'."
        )

    # Get existing year columns as integers
    existing_years = sorted([int(c) for c in ts.columns if c.isdigit()])

    # Create annual range
    annual_years = list(range(start_year, end_year + 1))

    # Create new DataFrame with annual columns
    annual_ts = pd.DataFrame(index=ts.index, columns=[str(y) for y in annual_years])

    # Copy existing values
    for year in existing_years:
        year_str = str(year)
        if year_str in annual_ts.columns and year_str in ts.columns:
            annual_ts[year_str] = ts[year_str]

    # Convert to float before interpolation
    annual_ts = annual_ts.astype(float)

    if method == "bfill":
        # Backward fill: each value fills the preceding interval
        # For years after the last data point, forward fill to avoid NaN
        annual_ts = annual_ts.bfill(axis=1).ffill(axis=1)
    elif method == "linear":
        # Linear interpolation between data points
        annual_ts = annual_ts.interpolate(method="linear", axis=1)

    return annual_ts
