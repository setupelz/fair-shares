"""
Allocation validation for fair shares analysis.

Validates data integrity and methodological consistency in fair shares calculations.
See docs/science/ for theoretical foundations of validation requirements.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import pandas as pd

from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import (
    AllocationError,
    ConfigurationError,
    DataProcessingError,
)
from fair_shares.library.utils.dataframes import TimeseriesDataFrame, get_year_columns

from .pipeline_validation import (
    validate_incremental_annual_timeseries,
    validate_index_structure,
    validate_stationary_dataframe,
    validate_timeseries_values,
)


def validate_single_emission_category(
    df: TimeseriesDataFrame, dataset_name_for_error_msg: str
) -> None:
    """
    Validate that only one emission category is present.

    Parameters
    ----------
    df : TimeseriesDataFrame
        DataFrame to check
    dataset_name_for_error_msg : str
        Name of the dataset for error messages

    Raises
    ------
    AllocationError
        If multiple emission categories are found
    DataProcessingError
        If no emission categories are found
    """
    if not isinstance(df.index, pd.MultiIndex):
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} must have MultiIndex with "
            f"'emission-category' level"
        )

    if "emission-category" not in df.index.names:
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} must have "
            f"'emission-category' in index levels"
        )

    emission_category = df.index.get_level_values("emission-category").unique().tolist()

    if len(emission_category) == 0:
        raise DataProcessingError(
            f"No emission categories found in {dataset_name_for_error_msg}"
        )

    if len(emission_category) > 1:
        raise AllocationError(
            f"Only one emission category allowed per allocation, "
            f"found: {emission_category}. Please filter to one category before "
            f"allocation."
        )


def validate_gini_range(
    df: pd.DataFrame, dataset_name_for_error_msg: str, gini_column: str = "gini"
) -> None:
    """
    Validate that Gini coefficients are in the valid range [0, 1].

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to check
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    gini_column : str
        Name of the Gini coefficient column

    Raises
    ------
    DataProcessingError
        If Gini coefficients are out of range
    """
    if gini_column not in df.columns:
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} missing required column: {gini_column}"
        )

    gini_min = df[gini_column].min()
    gini_max = df[gini_column].max()

    if gini_min < 0 or gini_max > 1:
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} Gini coefficients out of valid range 0-1:\n"
            f"Min: {gini_min:.3f}, Max: {gini_max:.3f}"
        )


def validate_shares_sum_to_one(
    shares_df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str,
    tolerance: float = 1e-6,
) -> None:
    """
    Validate that allocation shares sum to 1.0 for each year.

    Years containing NaN values are skipped (may represent post-net-zero periods).

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
            year_range = f"{min(year_cols)}-{max(year_cols)} ({len(year_cols)} "
            "years total)"
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

    For budget allocations, expects exactly one year in each DataFrame.
    For pathway allocations, expects years in df2 to exist in df1.

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


def validate_function_parameters(
    func: Callable,
    provided_params: dict[str, Any],
    required_context: dict[str, str] | None = None,
) -> None:
    """
    Validate that required function parameters are provided.

    Parameters
    ----------
    func : Callable
        The function whose parameters to validate
    provided_params : dict[str, Any]
        Parameters provided by the caller
    required_context : Optional[dict[str, str]]
        Context for parameter requirements

    Raises
    ------
    AllocationError
        If required parameters are missing
    """
    sig = inspect.signature(func)
    func_args = {}

    # Start with provided parameters
    for k, v in provided_params.items():
        if k in sig.parameters and v is not None:
            func_args[k] = v

    # Validate required parameters
    for param_name, param in sig.parameters.items():
        if param.default == inspect.Parameter.empty and param_name not in func_args:
            # Provide error messages for common missing parameters
            error_context = (
                required_context.get(param_name, "") if required_context else ""
            )
            context_msg = f" for {error_context}" if error_context else ""

            if param_name == "first_allocation_year":
                raise AllocationError(
                    f"first_allocation_year required{context_msg} for pathway "
                    "approaches"
                )
            elif param_name == "allocation_year":
                raise AllocationError(
                    f"allocation_year required{context_msg} for budget approaches"
                )
            elif param_name == "gdp_ts":
                error_msg = format_error(
                    "missing_required_data",
                    adjustment_type="capability",
                    weight_name="capability_weight",
                    weight_value="> 0.0",
                    data_name="GDP data (gdp_ts)",
                    explanation=(
                        "Capability-based adjustments require GDP data to "
                        "calculate per-capita GDP for countries."
                    ),
                    function_name=func.__name__,
                    data_param="gdp_ts",
                )
                raise AllocationError(error_msg)
            elif param_name == "gini_s":
                error_msg = format_error(
                    "missing_required_data",
                    adjustment_type="inequality",
                    weight_name="(approach uses Gini)",
                    weight_value="",
                    data_name="Gini data (gini_s)",
                    explanation=(
                        "Gini-adjusted approaches require Gini coefficient "
                        "data to account for within-country inequality."
                    ),
                    function_name=func.__name__,
                    data_param="gini_s",
                )
                raise AllocationError(error_msg)
            elif param_name == "country_actual_emissions_ts":
                raise AllocationError(
                    f"Emissions data required{context_msg} for pathway convergence "
                    "approaches"
                )
            elif param_name == "emission_category":
                raise AllocationError(
                    f"emission_category parameter required{context_msg} for allocation "
                    "approaches"
                )
            elif param_name == "convergence_year":
                raise AllocationError(
                    f"convergence_year parameter required{context_msg} for "
                    "per-capita-convergence approach"
                )
            else:
                raise ConfigurationError(f"Missing required parameter: {param_name}")


# Dataset-specific validation functions
def validate_emissions_data(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str = "Emissions",
    verbose: bool = True,
) -> None:
    """
    Validate emissions data in TimeseriesDataFrame format.

    Negative emissions are allowed (LULUCF sinks, carbon removal).

    Parameters
    ----------
    df : TimeseriesDataFrame
        Emissions TimeseriesDataFrame with MultiIndex
            ['iso3c', 'unit', 'emission-category']
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    validate_index_structure(
        df, dataset_name_for_error_msg, ["iso3c", "unit", "emission-category"]
    )
    year_cols = get_year_columns(df)
    if len(year_cols) == 0:
        raise AllocationError(f"{dataset_name_for_error_msg} has no year columns")
    validate_timeseries_values(
        df,
        dataset_name_for_error_msg,
        "emissions",
        should_be_positive=False,
        verbose=verbose,
    )
    validate_incremental_annual_timeseries(
        df, dataset_name_for_error_msg, verbose=verbose
    )


def validate_gdp_data(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str = "GDP",
    verbose: bool = True,
) -> None:
    """
    Validate GDP data in TimeseriesDataFrame format.

    Parameters
    ----------
    df : TimeseriesDataFrame
        GDP TimeseriesDataFrame
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    validate_index_structure(df, dataset_name_for_error_msg, ["iso3c", "unit"])
    year_cols = get_year_columns(df)
    if len(year_cols) == 0:
        raise AllocationError(f"{dataset_name_for_error_msg} has no year columns")
    validate_timeseries_values(
        df, dataset_name_for_error_msg, "GDP", should_be_positive=True, verbose=verbose
    )


def validate_population_data(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str = "Population",
    verbose: bool = True,
) -> None:
    """
    Validate population data in TimeseriesDataFrame format.

    Parameters
    ----------
    df : TimeseriesDataFrame
        Population TimeseriesDataFrame
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    validate_index_structure(df, dataset_name_for_error_msg, ["iso3c", "unit"])
    year_cols = get_year_columns(df)
    if len(year_cols) == 0:
        raise AllocationError(f"{dataset_name_for_error_msg} has no year columns")
    validate_timeseries_values(
        df,
        dataset_name_for_error_msg,
        "population",
        should_be_positive=True,
        verbose=verbose,
    )


def validate_gini_data(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str = "Gini",
    verbose: bool = True,
) -> None:
    """
    Validate Gini coefficient data in stationary format.

    Parameters
    ----------
    df : TimeseriesDataFrame
        Gini stationary DataFrame
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    validate_stationary_dataframe(df, dataset_name_for_error_msg, ["gini"], verbose)

    # Validate Gini coefficient range (0-1)
    if "gini" in df.columns:
        gini_min = df["gini"].min()
        gini_max = df["gini"].max()

        if gini_min < 0 or gini_max > 1:
            raise AllocationError(
                f"{dataset_name_for_error_msg} coefficients out of valid range 0-1. "
                f"Min: {gini_min:.3f}, Max: {gini_max:.3f}"
            )

        if verbose:
            print(
                f"{dataset_name_for_error_msg} coefficients validated: "
                f"all values in range 0-1"
            )
            print(f"  Range: {gini_min:.3f} - {gini_max:.3f}")


def validate_scenarios_data(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str = "Scenarios",
    verbose: bool = True,
) -> None:
    """
    Validate scenario pathway data in TimeseriesDataFrame format.

    Parameters
    ----------
    df : TimeseriesDataFrame
        Scenarios TimeseriesDataFrame with MultiIndex
            ['climate-assessment', 'quantile', 'source', 'iso3c', 'unit',
            'emission-category']
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    expected_index = [
        "climate-assessment",
        "quantile",
        "source",
        "iso3c",
        "unit",
        "emission-category",
    ]
    validate_index_structure(df, dataset_name_for_error_msg, expected_index)
    year_cols = get_year_columns(df)
    if len(year_cols) == 0:
        raise AllocationError(f"{dataset_name_for_error_msg} has no year columns")
    validate_timeseries_values(
        df,
        dataset_name_for_error_msg,
        "emissions",
        should_be_positive=False,
        verbose=verbose,
    )
    validate_incremental_annual_timeseries(
        df, dataset_name_for_error_msg, verbose=verbose
    )
