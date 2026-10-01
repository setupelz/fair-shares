"""
NGHGI correction utilities for NGHGI-consistent RCB processing.

Functions for loading LULUCF and bunker fuel timeseries data and computing
the cumulative deductions needed to convert IPCC-based RCBs to NGHGI-consistent
budgets, following the methodology of Weber et al. (2026).

Sign conventions:
- Emissions (fossil, bunkers): positive = source
- LULUCF: positive = net source, negative = net sink
- Deductions returned as positive floats (calling code negates as needed)

Data structure notes:
- NGHGI LULUCF file: CSV produced by notebook 107 from the active LULUCF
  source (Melo et al., v3.1.1 or v4.0.0)
- Bunker file: CSV produced by notebook 108 from the active bunker source
- AR6 category constants: YAML produced by notebook 104 (scenario preprocessing)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fair_shares.library.exceptions import DataLoadingError, DataProcessingError

def load_world_co2_lulucf(path: str | Path) -> tuple[pd.DataFrame, int]:
    """Load world-total NGHGI LULUCF CO2 timeseries from notebook-produced CSV.

    Reads the world-total NGHGI-reported LULUCF CO2 values produced by
    notebook 107 from the active LULUCF source (Melo et al., v3.1.1 or
    v4.0.0). The CSV has a single row with a "source" index
    and string year columns. Values are in MtCO2/yr (negative = net sink).

    The splice year (last year of NGHGI data) is derived dynamically from the
    data rather than being hardcoded.

    Parameters
    ----------
    path : str or Path
        Path to ``world_co2-lulucf_timeseries.csv``

    Returns
    -------
    tuple[pd.DataFrame, int]
        (nghgi_ts, splice_year) where nghgi_ts is a single-row DataFrame
        indexed by ["source"] with string year columns, and splice_year is
        the last year of NGHGI data coverage.

    Raises
    ------
    DataLoadingError
        If the file does not exist or expected structure is missing
    """
    path = Path(path)
    if not path.exists():
        raise DataLoadingError(
            f"NGHGI LULUCF world timeseries not found: {path}. "
            "Run notebook 107 (Melo LULUCF preprocessing) first."
        )

    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise DataLoadingError(f"Failed to read NGHGI LULUCF file {path}: {e}") from e

    if "source" not in df.columns:
        raise DataLoadingError(
            f"'source' column not found in {path}. "
            f"Available columns: {list(df.columns)}"
        )

    df = df.set_index("source")

    # Derive splice year from the data
    year_cols = [c for c in df.columns if _is_year(c)]
    if not year_cols:
        raise DataLoadingError(f"No year columns found in {path}")

    splice_year = max(int(c) for c in year_cols)

    return df, splice_year


def load_bunker_timeseries(path: str | Path) -> pd.DataFrame:
    """Load international bunker fuel CO2 timeseries from notebook-produced CSV.

    Reads the intermediate CSV produced by notebook 107 (LULUCF & bunker
    preprocessing). The CSV has a single row with a "source" index and
    string year columns. Values are already in MtCO2/yr.

    Parameters
    ----------
    path : str or Path
        Path to ``bunker_timeseries.csv``

    Returns
    -------
    pd.DataFrame
        Single-row DataFrame indexed by ["source"] with string year columns
        and values in MtCO2/yr

    Raises
    ------
    DataLoadingError
        If the file does not exist or expected structure is missing
    """
    path = Path(path)
    if not path.exists():
        raise DataLoadingError(
            f"Bunker timeseries CSV not found: {path}. "
            "Run notebook 108 (bunker preprocessing) first."
        )

    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise DataLoadingError(f"Failed to read bunker timeseries {path}: {e}") from e

    if "source" not in df.columns:
        raise DataLoadingError(
            f"'source' column not found in {path}. "
            f"Available columns: {list(df.columns)}"
        )

    df = df.set_index("source")
    return df


def compute_cumulative_emissions(
    timeseries: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> float:
    """Integrate a single-row timeseries DataFrame over a year range.

    Sums values for all years from start_year to end_year (inclusive). Missing
    years are skipped (not interpolated) since gap-filling is the caller's
    responsibility.

    Parameters
    ----------
    timeseries : pd.DataFrame
        Single-row DataFrame with string year columns (as produced by the
        load_* functions in this module)
    start_year : int
        First year to include (inclusive)
    end_year : int
        Last year to include (inclusive)

    Returns
    -------
    float
        Cumulative sum over the requested year range

    Raises
    ------
    DataProcessingError
        If no year columns fall within the requested range
    """
    year_cols = [
        str(y) for y in range(start_year, end_year + 1) if str(y) in timeseries.columns
    ]
    if not year_cols:
        raise DataProcessingError(
            f"No data found for years {start_year}-{end_year}. "
            f"Available years: {list(timeseries.columns[:5])}..."
        )
    return float(timeseries[year_cols].sum(axis=1).iloc[0])


def compute_bunker_deduction(
    bunker_ts: pd.DataFrame,
    start_year: int,
    net_zero_year: int,
    historical_end_year: int | None = None,
) -> float:
    """Compute cumulative international bunker fuel CO2 deduction.

    Combines historical year-by-year values from the bunker timeseries with
    extrapolation from the last observed annual rate for years beyond the
    historical record.

    Parameters
    ----------
    bunker_ts : pd.DataFrame
        Bunker fuel CO2 timeseries (from load_bunker_timeseries) in MtCO2/yr
    start_year : int
        Start of integration window (inclusive)
    net_zero_year : int
        End of integration window (inclusive)
    historical_end_year : int, optional
        Last year taken from the historical timeseries (default: the last
        year with a value in ``bunker_ts``)

    Returns
    -------
    float
        Total cumulative bunker deduction in MtCO2 (always positive)

    Raises
    ------
    DataProcessingError
        If historical data is insufficient for the start_year
    """
    if historical_end_year is None:
        observed = bunker_ts.iloc[0].dropna()
        historical_end_year = max(int(c) for c in observed.index if _is_year(c))

    historical_end = min(historical_end_year, net_zero_year)
    historical_bunkers = compute_cumulative_emissions(
        bunker_ts, start_year, historical_end
    )

    # Future component: extrapolate last observed rate beyond historical record
    future_bunkers = 0.0
    if net_zero_year > historical_end_year:
        last_rate = float(bunker_ts[str(historical_end_year)].iloc[0])
        future_years = net_zero_year - historical_end_year
        future_bunkers = last_rate * future_years

    return historical_bunkers + future_bunkers


def build_nghgi_world_co2_timeseries(
    fossil_ts: pd.DataFrame,
    nghgi_ts: pd.DataFrame,
) -> pd.DataFrame:
    """Construct NGHGI-consistent world total CO2 timeseries.

    For backward extension of allocation years < 2020, Weber Eq. 3 requires
    per-year world CO2 = fossil - bunkers + LULUCF. The world CO2-FFI series
    already excludes international bunkers, so the result is fossil + LULUCF,
    where LULUCF uses:
    - 2000 onwards: NGHGI LULUCF (e.g. Melo et al.)
    - Pre-2000: NaN (no fallback — NGHGI coverage only)

    No NGHGI/BM splicing is performed. Years outside NGHGI coverage are NaN.

    Parameters
    ----------
    fossil_ts : pd.DataFrame
        World CO2-FFI emissions timeseries (e.g. PRIMAP) in Mt CO2/yr,
        excluding international bunkers. Must have string year columns and a
        MultiIndex with (iso3c, unit, emission-category).
    nghgi_ts : pd.DataFrame
        NGHGI LULUCF historical timeseries (from load_world_co2_lulucf)
        in MtCO2/yr. Single-row DataFrame with string year columns.

    Returns
    -------
    pd.DataFrame
        Single-row DataFrame with same index structure as fossil_ts but
        emission-category label set to "co2", containing per-year
        NGHGI-consistent total CO2 = fossil + LULUCF.
        Years outside NGHGI LULUCF coverage will be NaN.
    """
    # Get all year columns from fossil_ts
    year_cols = [c for c in fossil_ts.columns if _is_year(c)]

    # Extract numeric arrays for fast computation
    fossil_vals = fossil_ts[year_cols].iloc[0]

    # Build LULUCF timeseries: NGHGI where available, NaN otherwise
    lulucf_vals = pd.Series(np.nan, index=year_cols, dtype=float)
    for y in year_cols:
        if y in nghgi_ts.columns:
            lulucf_vals[y] = nghgi_ts[y].iloc[0]

    # NGHGI-consistent total CO2 = fossil (excluding bunkers) + LULUCF
    total_co2 = fossil_vals + lulucf_vals

    # Build result with same index structure as fossil_ts but co2 label
    old_idx = fossil_ts.index[0]
    if isinstance(fossil_ts.index, pd.MultiIndex):
        # Replace emission-category level with "co2"
        idx_names = fossil_ts.index.names
        cat_pos = idx_names.index("emission-category")
        new_tuple = list(old_idx)
        new_tuple[cat_pos] = "co2"
        new_index = pd.MultiIndex.from_tuples([tuple(new_tuple)], names=idx_names)
    else:
        new_index = fossil_ts.index

    result = pd.DataFrame(
        [total_co2.values],
        columns=year_cols,
        index=new_index,
    )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_year(value: object) -> bool:
    """Return True if value looks like a calendar year (1800-2200)."""
    try:
        y = int(value)
        return 1800 <= y <= 2200
    except (ValueError, TypeError):
        return False
