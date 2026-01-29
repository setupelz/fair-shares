"""
Input and output validation for cumulative per capita convergence allocation.

This module contains validation functions specific to convergence pathway
allocations, including weight validation, data requirements, and share
calculation checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import AllocationError

if TYPE_CHECKING:
    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def validate_weights(
    responsibility_weight: float,
    capability_weight: float,
) -> None:
    """
    Validate that adjustment weights are non-negative and sum to <= 1.0.

    Parameters
    ----------
    responsibility_weight : float
        Weight for responsibility adjustment (historical emissions).
    capability_weight : float
        Weight for capability adjustment (GDP-based).

    Raises
    ------
    AllocationError
        If weights are negative or sum exceeds 1.0.
    """
    if responsibility_weight < 0:
        raise AllocationError(
            "Invalid weight parameter.\n\n"
            "WHAT HAPPENED:\n"
            f"  responsibility_weight={responsibility_weight} is negative.\n\n"
            "VALID RANGE:\n"
            "  responsibility_weight must be >= 0.0\n\n"
            "HOW TO FIX:\n"
            "  Use a non-negative value:\n"
            "  >>> result = manager.run_allocation(..., responsibility_weight=0.5)"
        )
    if capability_weight < 0:
        raise AllocationError(
            "Invalid weight parameter.\n\n"
            "WHAT HAPPENED:\n"
            f"  capability_weight={capability_weight} is negative.\n\n"
            "VALID RANGE:\n"
            "  capability_weight must be >= 0.0\n\n"
            "HOW TO FIX:\n"
            "  Use a non-negative value:\n"
            "  >>> result = manager.run_allocation(..., capability_weight=0.3)"
        )
    if responsibility_weight + capability_weight > 1.0:
        raise AllocationError(
            format_error(
                "weights_exceed_limit",
                resp=responsibility_weight,
                cap=capability_weight,
                total=responsibility_weight + capability_weight,
            )
        )


def validate_adjustment_data_requirements(
    capability_weight: float,
    gdp_ts: TimeseriesDataFrame | None,
    gini_s: pd.DataFrame | None,
) -> None:
    """
    Validate that required data is provided when adjustment weights are used.

    Parameters
    ----------
    capability_weight : float
        Weight for capability adjustment.
    gdp_ts : TimeseriesDataFrame | None
        GDP data (required if capability_weight > 0 or gini_s provided).
    gini_s : pd.DataFrame | None
        Gini coefficient data (requires gdp_ts if provided).

    Raises
    ------
    AllocationError
        If required data is missing for requested adjustments.
    """
    if capability_weight > 0 and gdp_ts is None:
        raise AllocationError(
            format_error(
                "missing_required_data",
                adjustment_type="capability",
                weight_name="capability_weight",
                weight_value=capability_weight,
                data_name="GDP data",
                explanation=(
                    "Capability adjustment reduces allocation for wealthier "
                    "countries based on GDP per capita."
                ),
                function_name="cumulative_per_capita_convergence_adjusted",
                data_param="gdp_ts",
            )
        )
    if gini_s is not None and gdp_ts is None:
        raise AllocationError(
            format_error(
                "missing_required_data",
                adjustment_type="Gini",
                weight_name="(via gini_s parameter)",
                weight_value="provided",
                data_name="GDP data",
                explanation=(
                    "Gini adjustment requires GDP data to apply inequality "
                    "corrections to GDP per capita calculations."
                ),
                function_name="cumulative_per_capita_convergence_gini_adjusted",
                data_param="gdp_ts",
            )
        )


def validate_emissions_data(
    emissions_numeric: pd.DataFrame,
    emission_category: str,
    group_level: str,
) -> None:
    """
    Validate emissions data structure and content.

    Parameters
    ----------
    emissions_numeric : pd.DataFrame
        Emissions data after unit processing.
    emission_category : str
        The emission category being analyzed.
    group_level : str
        Index level for country grouping (e.g., 'iso3c').

    Raises
    ------
    AllocationError
        If emissions data is empty, missing required index, or contains no countries.
    """
    if emissions_numeric.empty:
        raise AllocationError(
            f"Empty emissions dataset.\n\n"
            f"WHAT HAPPENED:\n"
            f"  Emissions data has no rows after filtering for "
            f"emission_category='{emission_category}'.\n\n"
            f"LIKELY CAUSE:\n"
            f"  The emission category may not exist in your data source.\n\n"
            f"HOW TO FIX:\n"
            f"  1. Check available categories in your emissions dataset\n"
            f"  2. Use a common category like 'co2-ffi' or 'all-ghg'\n"
            f"  3. Verify the data loaded correctly:\n"
            f"     >>> print(emissions_df.index.get_level_values("
            f"'emission-category').unique())"
        )
    if group_level not in emissions_numeric.index.names:
        raise AllocationError(
            f"Index structure error in emissions data.\n\n"
            f"WHAT HAPPENED:\n"
            f"  Group level '{group_level}' not found in emissions data index.\n"
            f"  Expected index to contain: {group_level}\n"
            f"  Actual index names: {emissions_numeric.index.names}\n\n"
            f"LIKELY CAUSE:\n"
            f"  Emissions data doesn't have the required multi-index structure.\n\n"
            f"HOW TO FIX:\n"
            f"  Ensure emissions data has '{group_level}' in its index:\n"
            f"  >>> df = df.set_index(['{group_level}', 'unit', 'emission-category'])"
        )


def validate_country_data_present(
    emissions_countries: pd.DataFrame,
    group_level: str,
) -> None:
    """
    Validate that emissions data contains country-level data, not just World totals.

    Parameters
    ----------
    emissions_countries : pd.DataFrame
        Emissions data after filtering out World rows.
    group_level : str
        Index level for country grouping (e.g., 'iso3c').

    Raises
    ------
    AllocationError
        If no country data is found (only World totals present).
    """
    if emissions_countries.empty:
        raise AllocationError(
            "No country data found in emissions.\n\n"
            "WHAT HAPPENED:\n"
            "  All emissions rows appear to be 'World' totals - no individual "
            "countries.\n\n"
            "LIKELY CAUSE:\n"
            "  The emissions data only contains global aggregates.\n\n"
            "HOW TO FIX:\n"
            "  Load emissions data that includes individual countries:\n"
            "  >>> # Verify your data has country rows\n"
            "  >>> print(emissions_df.index.get_level_values('iso3c').unique())\n"
            "  >>> # Should show: ['USA', 'CHN', 'IND', ...] not just ['World']"
        )


def validate_year_in_data(
    year: int,
    year_to_label: dict[int, str | int | float],
    dataset_name: str,
    available_columns: list[str],
) -> None:
    """
    Validate that a required year is present in the dataset.

    Parameters
    ----------
    year : int
        Required year.
    year_to_label : dict[int, str | int | float]
        Mapping from integer years to column labels.
    dataset_name : str
        Name of dataset for error message (e.g., "country emissions").
    available_columns : list[str]
        Available column labels in dataset.

    Raises
    ------
    AllocationError
        If the required year is not found in the dataset.
    """
    if year not in year_to_label:
        available_years = sorted(
            [int(y) for y in available_columns if str(y).isdigit()]
        )
        raise AllocationError(
            format_error(
                "missing_year_range",
                dataset_name=dataset_name,
                required_years=f"{year}",
                available_years=f"{min(available_years)} to {max(available_years)}"
                if available_years
                else "none",
                missing_years=f"{year}",
            )
        )


def validate_world_emissions_present(
    world_numeric: pd.DataFrame,
) -> None:
    """
    Validate that world scenario emissions data is not empty.

    Parameters
    ----------
    world_numeric : pd.DataFrame
        World scenario emissions after processing.

    Raises
    ------
    AllocationError
        If world emissions data is empty.
    """
    if world_numeric.empty:
        raise AllocationError(
            "World emissions missing.\n\n"
            "WHAT HAPPENED:\n"
            "  World scenario emissions data is empty after processing.\n\n"
            "LIKELY CAUSE:\n"
            "  The world scenario may not contain data for the requested "
            "emission category.\n\n"
            "HOW TO FIX:\n"
            "  1. Verify world scenario contains the emission category\n"
            "  2. Check that year range matches country emissions\n"
            "  3. Ensure units are compatible:\n"
            "     >>> print(world_scenario_emissions_ts.index.get_level_values("
            "'unit').unique())"
        )


def validate_country_world_consistency(
    country_sum: float,
    world_total: float,
    first_allocation_year: int,
    tolerance: float = 1e-6,
) -> None:
    """
    Validate that country emissions sum to world total at allocation start year.

    Parameters
    ----------
    country_sum : float
        Sum of all country emissions at start year.
    world_total : float
        World total emissions at start year.
    first_allocation_year : int
        Year when allocation begins.
    tolerance : float, optional
        Absolute tolerance for comparison (default: 1e-6).

    Raises
    ------
    AllocationError
        If country and world totals don't match within tolerance.
    """
    if abs(country_sum - world_total) > tolerance:
        raise AllocationError(
            f"Data inconsistency detected.\n\n"
            f"WHAT HAPPENED:\n"
            f"  Country emissions don't add up to world total at year "
            f"{first_allocation_year}.\n"
            f"  Sum of country emissions: {country_sum:.2f}\n"
            f"  World total emissions: {world_total:.2f}\n"
            f"  Difference: {abs(country_sum - world_total):.2e}\n\n"
            f"LIKELY CAUSE:\n"
            f"  The country-level and world-level emissions come from different "
            f"sources\n"
            f"  or have different coverage/aggregation methods.\n\n"
            f"HOW TO FIX:\n"
            f"  Ensure both datasets use the same source and emission category:\n"
            f"  >>> # Both should be from same source (e.g., PRIMAP)\n"
            f"  >>> # Both should use same emission-category (e.g., 'co2-ffi')"
        )


def validate_sufficient_time_horizon(
    sorted_columns: list[str],
    start_column: str,
    first_allocation_year: int,
) -> None:
    """
    Validate that there are enough years after start for convergence.

    Parameters
    ----------
    sorted_columns : list[str]
        Sorted list of year column labels.
    start_column : str
        Column label for first allocation year.
    first_allocation_year : int
        Year when allocation begins.

    Raises
    ------
    AllocationError
        If no years exist after the first allocation year.
    """
    start_idx = sorted_columns.index(start_column)
    if start_idx + 1 >= len(sorted_columns):
        raise AllocationError(
            f"Insufficient time horizon for convergence.\n\n"
            f"WHAT HAPPENED:\n"
            f"  No years found after first_allocation_year={first_allocation_year}.\n"
            f"  Convergence allocation requires at least 2 years.\n\n"
            f"LIKELY CAUSE:\n"
            f"  The world scenario emissions only contains the starting year.\n\n"
            f"HOW TO FIX:\n"
            f"  Use a world scenario with multiple years:\n"
            f"  >>> # Scenario should cover {first_allocation_year} through at "
            f"least 2050"
        )


def validate_share_calculation(
    shares: pd.Series | pd.DataFrame,
    step_description: str,
) -> None:
    """
    Validate that calculated shares are valid (not NaN, positive sum).

    Parameters
    ----------
    shares : pd.Series | pd.DataFrame
        Calculated shares to validate.
    step_description : str
        Description of calculation step for error message.

    Raises
    ------
    AllocationError
        If shares contain NaN or sum to invalid total.
    """
    if isinstance(shares, pd.Series):
        has_na = shares.isna().any()
        total = shares.sum()
    else:
        has_na = shares.isna().any().any()
        total = shares.sum().sum() if not shares.empty else 0

    if has_na:
        raise AllocationError(
            f"Share calculation error.\n\n"
            f"WHAT HAPPENED:\n"
            f"  {step_description} resulted in missing (NaN) values.\n\n"
            f"LIKELY CAUSE:\n"
            f"  Data mismatch or numerical issue during calculation.\n\n"
            f"HOW TO FIX:\n"
            f"  This is likely a bug. Please report with:\n"
            f"  - Parameter values\n"
            f"  - Data shapes and sample values\n"
            f"  - Which countries show NaN values"
        )

    if pd.isna(total) or total <= 0:
        raise AllocationError(
            f"Convergence calculation error.\n\n"
            f"WHAT HAPPENED:\n"
            f"  {step_description} produced invalid totals (NaN or <= 0).\n\n"
            f"LIKELY CAUSE:\n"
            f"  Numerical instability in the calculation.\n\n"
            f"HOW TO FIX:\n"
            f"  This is likely a bug. Please report with:\n"
            f"  - Parameter values\n"
            f"  - Data shapes and sample values"
        )


def validate_world_weights_aligned(
    year_fractions: pd.Series,
    required_columns: pd.Index,
) -> None:
    """
    Validate that world weight fractions are available for all required years.

    Parameters
    ----------
    year_fractions : pd.Series
        Year-based weight fractions (reindexed to required_columns).
    required_columns : pd.Index
        Required year columns.

    Raises
    ------
    AllocationError
        If any required years are missing from world weights.
    """
    if year_fractions.isna().any():
        missing = year_fractions[year_fractions.isna()].index.tolist()
        raise AllocationError(
            f"Missing world weights.\n\n"
            f"WHAT HAPPENED:\n"
            f"  World weights (year fractions) are missing for years: {missing}\n\n"
            f"LIKELY CAUSE:\n"
            f"  Mismatch between country and world scenario year coverage.\n\n"
            f"HOW TO FIX:\n"
            f"  Ensure world scenario covers all years in country data:\n"
            f"  >>> print(world_scenario_emissions_ts.columns)  "
            f"# Should include {missing}"
        )
