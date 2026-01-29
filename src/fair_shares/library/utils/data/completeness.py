"""
Timeseries completeness utilities for the fair-shares library.

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils.dataframes import get_year_columns
from fair_shares.library.validation.pipeline_validation import (
    validate_has_year_columns,
    validate_index_structure,
)

if TYPE_CHECKING:
    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def get_world_totals_timeseries(
    df: TimeseriesDataFrame,
    world_key: str,
    expected_index_names: list[str] | None,
    verbose: bool = True,
) -> TimeseriesDataFrame:
    """
    Extract world totals from a TimeseriesDataFrame.

    Parameters
    ----------
    df : TimeseriesDataFrame
        TimeseriesDataFrame with MultiIndex and years as columns
    world_key : str
        The key used to identify world totals (e.g., "EARTH", "WLD", "World")
    expected_index_names : list, optional
        Expected index level names for validation (e.g., ['iso3c', 'unit'] for GDP
        or ['iso3c', 'unit', 'emission-category'] for emissions)
    verbose : bool, optional
        Whether to print status messages

    Returns
    -------
    TimeseriesDataFrame
        TimeseriesDataFrame containing world totals with same MultiIndex structure
    """
    validate_index_structure(
        df,
        dataset_name_for_error_msg="world totals data",
        expected_index_names=expected_index_names,
    )
    validate_has_year_columns(df, "world totals data")

    world_mask = df.index.get_level_values("iso3c") == world_key
    world_data = df[world_mask]

    if world_data.empty:
        if verbose:
            print(f"Warning: No world data found with key '{world_key}'")
        return pd.DataFrame()

    if verbose:
        year_cols = get_year_columns(world_data)
        if year_cols:
            print(f"World data found for {world_key}: {len(year_cols)} years")

    return world_data


def get_complete_iso3c_timeseries(
    df: TimeseriesDataFrame,
    expected_index_names: list[str] | None,
    start: int = 1990,
    end: int = 2019,
    verbose: bool = True,
) -> set:
    """
    Get countries with complete data for the time period in TimeseriesDataFrame format.

    Parameters
    ----------
    df : TimeseriesDataFrame
        TimeseriesDataFrame with MultiIndex and years as columns
    expected_index_names : list, optional
        Expected index level names for validation (e.g., ['iso3c', 'unit'] for GDP
        or ['iso3c', 'unit', 'emission-category'] for emissions)
    start : int
        Start year for completeness check
    end : int
        End year for completeness check
    verbose : bool, optional
        Whether to print status messages

    Returns
    -------
    set
        Set of iso3c codes for countries with complete data
    """
    validate_index_structure(
        df,
        dataset_name_for_error_msg="complete data check",
        expected_index_names=expected_index_names,
    )
    validate_has_year_columns(df, "complete data check")

    # Get year columns in the range
    year_cols = get_year_columns(df)
    year_cols = [col for col in year_cols if start <= int(col) <= end]

    if not year_cols:
        if verbose:
            print(f"Warning: No year columns found in range {start}-{end}")
        return set()

    # Check for complete data (no NaN values) in the specified year range
    complete_mask = df[year_cols].notna().all(axis=1)
    complete_countries = df[complete_mask].index.get_level_values("iso3c")
    complete_countries = complete_countries.unique().tolist()

    if verbose:
        print(f"Found {len(complete_countries)} with complete data for {start}-{end}")
        print(f"Checked: {len(year_cols)} years ({min(year_cols)}-{max(year_cols)})")

    return set(complete_countries)


def add_row_timeseries(
    df: TimeseriesDataFrame,
    analysis_iso3c: set,
    world_data: TimeseriesDataFrame,
    expected_index_names: list[str] | None,
    world_code: str = "ROW",
    verbose: bool = True,
) -> TimeseriesDataFrame:
    """
    Add Rest of World (ROW) timeseries to a TimeseriesDataFrame to ensure completeness.

    This function calculates Rest of World values by subtracting the sum of analysis
    countries from world totals for each year. This ensures that the
    analysis dataset plus ROW equals the world total for all years.

    Parameters
    ----------
    df : TimeseriesDataFrame
        TimeseriesDataFrame with MultiIndex and years as columns
    analysis_iso3c : set or list
        Set of ISO3 country codes to include in the analysis (analysis countries)
    expected_index_names : list, optional
        Expected index level names for validation (e.g., ['iso3c', 'unit'] for GDP
        or ['iso3c', 'unit', 'emission-category'] for emissions)
    world_data : TimeseriesDataFrame
        World totals TimeseriesDataFrame with same MultiIndex structure
    world_code : str, optional
        ISO3-like code to assign to Rest of World entries (default: "ROW")
    verbose : bool, optional
        Whether to print status messages

    Returns
    -------
    TimeseriesDataFrame
        Combined TimeseriesDataFrame containing:
        - All original data for analysis countries
        - Calculated ROW values for each year

        ROW values are calculated as: World Total - Sum(Analysis Countries)
    """
    validate_index_structure(
        df,
        dataset_name_for_error_msg="analysis data",
        expected_index_names=expected_index_names,
    )
    validate_has_year_columns(df, "analysis data")
    validate_index_structure(
        world_data,
        dataset_name_for_error_msg="world data",
        expected_index_names=expected_index_names,
    )
    validate_has_year_columns(world_data, "world data")

    # Subset to analysis countries
    filtered = df[df.index.get_level_values("iso3c").isin(analysis_iso3c)].copy()

    if filtered.empty:
        raise DataProcessingError("No analysis countries found in dataset")

    if world_data.empty:
        raise DataProcessingError("No world data provided")

    # Extract world series (should be single row)
    if len(world_data) != 1:
        raise DataProcessingError(
            f"Expected single world row, got {len(world_data)} rows"
        )
    world_series = world_data.iloc[0]

    # Get year columns that exist in both datasets (preserve original labels)
    year_cols = [
        col
        for col in get_year_columns(df, return_type="original")
        if col in world_series.index
    ]

    if not year_cols:
        raise DataProcessingError(
            "No matching year cols found in analysis and world data"
        )

    # Calculate analysis countries sum for each year
    analysis_sum = filtered[year_cols].sum()

    # Calculate ROW values: World - Analysis
    row_values = world_series[year_cols] - analysis_sum

    # Create ROW row with 'ROW' as iso3c code
    # Get the index structure from the first row of filtered data
    first_row_index = filtered.index[0]
    if isinstance(first_row_index, tuple):
        # MultiIndex case: replace the iso3c level with 'ROW'
        index_levels = list(filtered.index.names)
        iso3c_level_idx = index_levels.index("iso3c")
        new_index_values = list(first_row_index)
        new_index_values[iso3c_level_idx] = world_code
        row_index = tuple(new_index_values)
    else:
        # Single-level index case
        row_index = world_code

    row_df = pd.DataFrame([row_values], index=[row_index])
    if isinstance(filtered.index, pd.MultiIndex):
        row_df.index = pd.MultiIndex.from_tuples(
            [row_index], names=filtered.index.names
        )

    # Combine with filtered data
    result = pd.concat([filtered, row_df])

    # Validation: check that sum matches world for each year
    if verbose:
        combined_sum = result[year_cols].sum()
        world_vals = world_series[year_cols]

        # Only compare where both values are not NaN
        valid_mask = ~(combined_sum.isna() | world_vals.isna())
        if valid_mask.any():
            mismatch = (combined_sum[valid_mask] - world_vals[valid_mask]).abs() > 1
            if mismatch.any():
                mismatch_years = list(combined_sum[valid_mask][mismatch].index)
                raise DataProcessingError(
                    f"Data integrity failure: (analysis + ROW) "
                    f"!== world total for years {mismatch_years}"
                )

        row_mask = result.index.get_level_values("iso3c") == world_code
        row_count = sum(row_mask)
        analysis_count = len(analysis_iso3c)
        print(
            f"Added {row_count} ROW entries (should be 1) alongside "
            f"{analysis_count} countries with complete data"
        )

    return result


def get_cumulative_budget_from_timeseries(
    df: TimeseriesDataFrame,
    allocation_year: str,
    expected_index_names: list[str] | None,
    world_key: str = "World",
    verbose: bool = True,
) -> TimeseriesDataFrame:
    """
    Calculate cumulative budget from allocation year to 2100 for budget allocations.

    This function extracts the cumulative emissions budget from a timeseries by summing
    all years from the allocation year to 2100. This is used for budget allocation
    calculations where we need the total remaining budget to distribute.

    Parameters
    ----------
    df : TimeseriesDataFrame
        TimeseriesDataFrame with MultiIndex and years as columns
    allocation_year : int
        The allocation year to start cumulative calculation from
    expected_index_names : list, optional
        Expected index level names for validation (e.g., ['iso3c', 'unit'] for GDP
        or ['iso3c', 'unit', 'emission-category'] for emissions)
    world_key : str, optional
        The key used to identify world totals (default: "World")
    verbose : bool, optional
        Whether to print status messages (default: True)

    Returns
    -------
    TimeseriesDataFrame
        Cumulative budget data with same MultiIndex structure and one year column
        containing the cumulative sum from allocation_year to 2100

    Raises
    ------
    DataProcessingError
        If the allocation year is not found or no world data is found
    """
    validate_index_structure(
        df,
        dataset_name_for_error_msg="cumulative budget data",
        expected_index_names=expected_index_names,
    )
    validate_has_year_columns(df, "cumulative budget data")

    # Get year columns from allocation_year to 2100
    year_cols = get_year_columns(df)
    year_cols = [col for col in year_cols if allocation_year <= int(col) <= 2100]

    # Extract the relevant years and calculate cumulative sum
    result = df[year_cols].sum(axis=1).to_frame(name=allocation_year)

    # Verify world data exists
    world_mask = result.index.get_level_values("iso3c") == world_key
    world_data = result[world_mask]
    if world_data.empty:
        raise DataProcessingError(
            f"No world data found with key '{world_key}' for cumulative budget"
        )

    if verbose:
        print(
            f"Calculated cumulative budget from {allocation_year} to "
            f"{max(year_cols)} ({len(year_cols)} years)"
        )

    return result
