"""Emission difference and combination utilities."""

import pandas as pd

from fair_shares.library.exceptions import DataProcessingError


def calculate_emission_difference(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    id_vars: list[str],
    year_cols: list[str],
    suffix1: str,
    suffix2: str,
) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Calculate the difference between two emission variables (df1 - df2).

    Inner-merges df1 and df2 on id_vars, then computes df1[year] - df2[year]
    for each year in year_cols.

    Parameters
    ----------
    df1 : pd.DataFrame
        First DataFrame (minuend).
    df2 : pd.DataFrame
        Second DataFrame (subtrahend).
    id_vars : list[str]
        Columns to merge on (e.g. ["climate-assessment", "Model", "Scenario", "Region"]).
    year_cols : list[str]
        Year columns to compute differences for.
    suffix1 : str
        Suffix applied to df1 columns after merge (e.g. "co2").
    suffix2 : str
        Suffix applied to df2 columns after merge (e.g. "afolu_direct").

    Returns
    -------
    tuple[pd.DataFrame, dict[str, pd.Series]]
        merged : the inner-merged DataFrame (with suffixed year columns)
        year_data : mapping of year -> Series of (df1[year] - df2[year])

    Raises
    ------
    DataProcessingError
        If no rows match on id_vars, or if expected year columns are missing
        from the merged result.
    """
    # Clean string id columns for robust merging (copy once to avoid mutating inputs)
    df1 = df1.copy()
    df2 = df2.copy()
    for col in id_vars:
        if col in df1.columns:
            df1[col] = df1[col].astype(str).str.strip()
        if col in df2.columns:
            df2[col] = df2[col].astype(str).str.strip()

    merged = pd.merge(
        df1[id_vars + year_cols],
        df2[id_vars + year_cols],
        on=id_vars,
        suffixes=(f"_{suffix1}", f"_{suffix2}"),
        how="inner",
    )

    if merged.empty:
        raise DataProcessingError(
            f"No matching rows found between '{suffix1}' and '{suffix2}' "
            f"on id_vars={id_vars}"
        )

    year_data: dict[str, pd.Series] = {}
    for year in year_cols:
        col1 = f"{year}_{suffix1}"
        col2 = f"{year}_{suffix2}"
        if col1 not in merged.columns or col2 not in merged.columns:
            raise DataProcessingError(
                f"Missing merged columns for year {year}: "
                f"expected '{col1}' and '{col2}'"
            )
        year_data[year] = merged[col1] - merged[col2]

    return merged, year_data
