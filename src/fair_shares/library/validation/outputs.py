"""
Output share validation functions for the fair-shares library.

This module contains validation functions for allocation output data including:
- Share summation validation (ensuring shares sum to 1.0)
- Year column matching between datasets
- Emission category matching
- World data presence checks
- Output data completeness and consistency
"""

from __future__ import annotations

import pandas as pd

from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import AllocationError, DataProcessingError
from fair_shares.library.utils.dataframes import TimeseriesDataFrame, get_year_columns


def validate_shares_sum_to_one(
    shares_df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str,
    tolerance: float = 1e-6,
) -> None:
    """
    Validate that allocation shares sum to 1.0 for each year.

    Parameters
    ----------
    shares_df : TimeseriesDataFrame
        DataFrame with allocation shares
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    tolerance : float
        Tolerance for floating point comparison

    Raises
    ------
    AllocationError
        If shares don't sum to 1.0

    Notes
    -----
    Years containing NaN values are skipped, as these may represent
    post-net-zero periods where allocations are intentionally incomplete.
    """
    year_cols = get_year_columns(shares_df, return_type="original")

    for year in year_cols:
        # Skip validation for years with NaN values (e.g., post-net-zero)
        if shares_df[year].isnull().any():
            continue

        year_sum = shares_df[year].sum()
        if abs(year_sum - 1.0) > tolerance:
            error_msg = format_error(
                "shares_not_sum_to_one", actual_sum=year_sum, difference=year_sum - 1.0
            )
            raise AllocationError(
                f"{dataset_name_for_error_msg} shares for year {year}:\n{error_msg}"
            )


def validate_exactly_one_year_column(
    df: TimeseriesDataFrame, dataset_name_for_error_msg: str
) -> None:
    """
    Validate that a DataFrame has exactly one year column.

    Parameters
    ----------
    df : TimeseriesDataFrame
        DataFrame to validate
    dataset_name_for_error_msg : str
        Name of the dataset for error messages

    Raises
    ------
    AllocationError
        If validation fails
    """
    year_cols = get_year_columns(df)

    if len(year_cols) == 0:
        raise DataProcessingError(
            f"No year columns found in {dataset_name_for_error_msg}"
        )

    if len(year_cols) != 1:
        # Show a more readable error message for long year lists
        if len(year_cols) > 10:
            year_range = (
                f"{min(year_cols)}-{max(year_cols)} " f"({len(year_cols)} years total)"
            )
        else:
            year_range = str(year_cols)
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} should have exactly one "
            f"year column, found: {year_range}"
        )


def validate_years_match(
    df1: TimeseriesDataFrame,
    df2: TimeseriesDataFrame,
    df1_name_for_error_msg: str,
    df2_name_for_error_msg: str,
) -> None:
    """
    Validate that two DataFrames have compatible year columns.

    For budget: expects exactly one year in each and they must match.
    For pathway: expects years in df2 (pathway shares) to exist in df1 (world pathway).

    Parameters
    ----------
    df1 : TimeseriesDataFrame
        First DataFrame to check (typically world pathway data)
    df2 : TimeseriesDataFrame
        Second DataFrame to check (typically pathway shares)
    df1_name_for_error_msg : str
        Name of the first dataset for error messages
    df2_name_for_error_msg : str
        Name of the second dataset for error messages

    Raises
    ------
    AllocationError
        If years are not compatible
    """
    year1_cols = get_year_columns(df1)
    year2_cols = get_year_columns(df2)

    if not year1_cols:
        raise DataProcessingError(f"No year columns found in {df1_name_for_error_msg}")

    if not year2_cols:
        raise DataProcessingError(f"No year columns found in {df2_name_for_error_msg}")

    # For budget allocations, we expect exactly one year in each
    if len(year1_cols) == 1 and len(year2_cols) == 1:
        year1 = str(year1_cols[0])
        year2 = str(year2_cols[0])
        if year1 != year2:
            raise AllocationError(
                f"{df1_name_for_error_msg} year {year1} does not match "
                f"{df2_name_for_error_msg} year {year2}"
            )
    else:
        # For pathway allocations, check that all years in df2 exist in df1
        # This handles the case where pathway shares have a subset (e.g., 1990-2100)
        # while world pathway has full range (e.g., 1850-2100)
        missing_years = [year for year in year2_cols if year not in year1_cols]
        if missing_years:
            raise AllocationError(
                f"Years in {df2_name_for_error_msg} ({missing_years}) not found in "
                f"{df1_name_for_error_msg} "
                f"(available years: {sorted(year1_cols)})"
            )


def validate_world_data_present(
    df: TimeseriesDataFrame, dataset_name_for_error_msg: str, world_key: str = "World"
) -> None:
    """
    Validate that world data is present in the dataset.

    This is used for absolute allocation calculations where world totals
    are needed to convert relative shares to absolute emissions.

    Parameters
    ----------
    df : TimeseriesDataFrame
        DataFrame to check
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    world_key : str
        Key used to identify world data

    Raises
    ------
    AllocationError
        If world data is not found
    """
    if not isinstance(df.index, pd.MultiIndex):
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} must have MultiIndex with 'iso3c' level"
        )

    if "iso3c" not in df.index.names:
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} must have 'iso3c' in index levels"
        )

    world_mask = df.index.get_level_values("iso3c") == world_key
    if not world_mask.any():
        raise AllocationError(
            f"No '{world_key}' data found in {dataset_name_for_error_msg}. "
            f"Data must include world totals for allocation."
        )


def validate_emission_category_match(
    shares_df: TimeseriesDataFrame,
    budget_df: TimeseriesDataFrame,
    shares_name: str = "relative shares",
    budget_name: str = "budget data",
) -> None:
    """
    Validate that emission categories match between shares and budget data.

    This ensures that the emission category used in the allocation result
    matches the emission category in the budget/emissions data before
    performing absolute calculations.

    Parameters
    ----------
    shares_df : TimeseriesDataFrame
        DataFrame containing relative shares with emission-category in index
    budget_df : TimeseriesDataFrame
        DataFrame containing budget/emissions data with emission-category in index
    shares_name : str
        Name of the shares dataset for error messages
    budget_name : str
        Name of the budget dataset for error messages

    Raises
    ------
    AllocationError
        If emission categories don't match or if data structure is invalid
    """
    # Validate that both DataFrames have emission-category in their index
    if (
        not isinstance(shares_df.index, pd.MultiIndex)
        or "emission-category" not in shares_df.index.names
    ):
        raise AllocationError(
            f"{shares_name} must have MultiIndex with 'emission-category' level"
        )

    if (
        not isinstance(budget_df.index, pd.MultiIndex)
        or "emission-category" not in budget_df.index.names
    ):
        raise AllocationError(
            f"{budget_name} must have MultiIndex with 'emission-category' level"
        )

    # Extract emission categories
    shares_categories = (
        shares_df.index.get_level_values("emission-category").unique().tolist()
    )
    budget_categories = (
        budget_df.index.get_level_values("emission-category").unique().tolist()
    )

    # Validate single emission category in each dataset
    if len(shares_categories) != 1:
        raise AllocationError(
            f"{shares_name} must contain exactly one emission category, "
            f"found: {shares_categories}"
        )

    if len(budget_categories) != 1:
        raise AllocationError(
            f"{budget_name} must contain exactly one emission category, "
            f"found: {budget_categories}"
        )

    shares_category = shares_categories[0]
    budget_category = budget_categories[0]

    # Validate that categories match
    if shares_category != budget_category:
        raise AllocationError(
            f"Emission category in {shares_name} ('{shares_category}') does not match "
            f"that in {budget_name} ('{budget_category}')"
        )
