"""
Input DataFrame validation for fair shares analysis.

This module validates input data structures used in fair shares calculations.
See docs/science/ for conceptual foundations of validation requirements.

Validation functions:
- Index structure validation (country codes, emission categories)
- Year column detection and range validation
- Value range checks (positive values, Gini in [0,1])
- Null value detection with contextual error messages
- Dataset-specific validators (emissions, GDP, population, Gini, scenarios)
"""

from __future__ import annotations

import pandas as pd

from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import AllocationError, DataProcessingError
from fair_shares.library.utils.dataframes import get_year_columns
from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def validate_not_empty(
    df: TimeseriesDataFrame, dataset_name_for_error_msg: str
) -> None:
    """
    Validate that DataFrame is not empty.

    Empty DataFrames cause cryptic errors downstream. This check catches
    the issue early with a clear error message.

    Parameters
    ----------
    df : TimeseriesDataFrame
        DataFrame to validate
    dataset_name_for_error_msg : str
        Name of the dataset for error messages

    Raises
    ------
    DataProcessingError
        If DataFrame is empty
    """
    if df.empty:
        raise DataProcessingError(
            format_error(
                "empty_dataframe",
                dataset_name=dataset_name_for_error_msg,
            )
        )


def validate_index_structure(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str,
    expected_index_names: list[str] | None = None,
) -> None:
    """
    Validate that TimeseriesDataFrame has the expected index structure.

    Index levels identify entities (countries via ISO3C codes) and metadata
    (emission categories, units).

    Parameters
    ----------
    df : TimeseriesDataFrame
        TimeseriesDataFrame to validate
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    expected_index_names : list[str], optional
        Expected index level names (default: ['iso3c'])

    Raises
    ------
    DataProcessingError
        If index structure does not match expected
    """
    expected_index_names = expected_index_names or ["iso3c"]

    if isinstance(df.index, pd.MultiIndex):
        actual_index_names = list(df.index.names)
    else:
        actual_index_names = [df.index.name] if df.index.name else ["index"]

    if actual_index_names != expected_index_names:
        raise DataProcessingError(
            format_error(
                "index_structure_mismatch",
                dataset_name=dataset_name_for_error_msg,
                expected=expected_index_names,
                actual=actual_index_names,
            )
        )


def validate_has_year_columns(
    df: TimeseriesDataFrame, dataset_name_for_error_msg: str
) -> None:
    """
    Validate that TimeseriesDataFrame has at least one year column.

    Year columns are required for time-series allocations (budgets and pathways).

    Parameters
    ----------
    df : TimeseriesDataFrame
        TimeseriesDataFrame to validate
    dataset_name_for_error_msg : str
        Name of the dataset for error messages

    Raises
    ------
    DataProcessingError
        If no year columns are found
    """
    year_cols = get_year_columns(df)
    if len(year_cols) == 0:
        # Show first 5 columns to help user understand what's in the DataFrame
        found_columns = list(df.columns[:5])
        if len(df.columns) > 5:
            found_columns.append("...")
        raise DataProcessingError(
            format_error(
                "year_columns_missing",
                dataset_name=dataset_name_for_error_msg,
                found_columns=found_columns,
            )
        )


def validate_stationary_dataframe(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str,
    expected_columns: list[str],
    verbose: bool = True,
) -> None:
    """
    Validate stationary DataFrame format (no time dimension).

    Used for time-invariant data (e.g., Gini coefficients assumed constant).

    Parameters
    ----------
    df : TimeseriesDataFrame
        Stationary DataFrame with index as countries and data columns
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    expected_columns : list
        Expected column names
    verbose : bool, optional
        Whether to print validation details (default: True)

    Raises
    ------
    DataProcessingError
        If validation fails
    """
    missing_cols = [col for col in expected_columns if col not in df.columns]

    if missing_cols:
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} missing required cols: "
            f"{missing_cols}. Available cols: {list(df.columns)}"
        )

    unexpected_cols = [col for col in df.columns if col not in expected_columns]
    if unexpected_cols and verbose:
        print(
            f"Warning: {dataset_name_for_error_msg} has unexpected cols: "
            f"{unexpected_cols}"
        )

    if verbose:
        print(f"{dataset_name_for_error_msg} stationary structure validated")
        print(f"  Index: {df.index.name}")
        print(f"  Columns: {list(df.columns)}")


def validate_year_in_data(
    year: int, df: TimeseriesDataFrame, dataset_name_for_error_msg: str
) -> None:
    """
    Validate that a specific year exists in the dataset.

    Required for allocation approaches that depend on specific historical
    or base years.

    Parameters
    ----------
    year : int
        Year to check for
    df : TimeseriesDataFrame
        DataFrame to check
    dataset_name_for_error_msg : str
        Name of the dataset for error messages

    Raises
    ------
    DataProcessingError
        If the year is not found
    """
    # Check both string and integer representations of the year
    year_str = str(year)
    year_int = int(year)

    if year_str not in df.columns and year_int not in df.columns:
        # Get available years for better error message
        year_cols = sorted(get_year_columns(df), key=int)

        if year_cols:
            raise DataProcessingError(
                format_error(
                    "missing_year_range",
                    dataset_name=dataset_name_for_error_msg,
                    required_years=f"{year}",
                    available_years=f"{year_cols[0]}-{year_cols[-1]}",
                    missing_years=f"{year}",
                )
            )
        else:
            # No year columns at all - use year_columns_missing error
            found_columns = list(df.columns[:5])
            if len(df.columns) > 5:
                found_columns.append("...")
            raise DataProcessingError(
                format_error(
                    "year_columns_missing",
                    dataset_name=dataset_name_for_error_msg,
                    found_columns=found_columns,
                )
            )


def validate_positive_values(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str,
    value_name: str,
    allow_negative: bool = False,
    verbose: bool = False,
) -> None:
    """
    Validate that values are positive (unless negative values are allowed).

    Population and GDP must be positive. Emissions may be negative (LULUCF
    sinks, carbon removal).

    Parameters
    ----------
    df : TimeseriesDataFrame
        DataFrame to check
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    value_name : str
        Name of the values being validated
    allow_negative : bool
        Whether negative values are allowed
    verbose : bool
        Whether to print validation details

    Raises
    ------
    DataProcessingError
        If validation fails
    """
    if not allow_negative:
        year_cols = get_year_columns(df)
        negative_mask = (df[year_cols] < 0).any(axis=1)
        negative_count = negative_mask.sum()

        if negative_count > 0:
            raise DataProcessingError(
                format_error(
                    "negative_values",
                    dataset_name=dataset_name_for_error_msg,
                    value_type=value_name,
                    count=negative_count,
                )
            )


def validate_timeseries_values(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str,
    value_name: str,
    should_be_positive: bool = True,
    verbose: bool = True,
) -> None:
    """
    Validate values in TimeseriesDataFrame format.

    Checks for negative values (when inappropriate) and reports data coverage.

    Parameters
    ----------
    df : TimeseriesDataFrame
        TimeseriesDataFrame with index as countries and years as columns
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    value_name : str
        Name of the value type for error messages
    should_be_positive : bool, optional
        Whether values should be positive (default: True)
    verbose : bool, optional
        Whether to print validation details (default: True)

    Raises
    ------
    DataProcessingError
        If validation fails
    """
    # Get year columns
    year_cols = get_year_columns(df)

    if not year_cols:
        return  # No year columns to validate

    # Check for negative values if required
    if should_be_positive:
        negative_mask = df[year_cols] < 0
        if negative_mask.any().any():
            negative_count = negative_mask.sum().sum()
            total_values = len(df) * len(year_cols)
            raise DataProcessingError(
                f"{dataset_name_for_error_msg} has {negative_count} "
                f"negative {value_name} values out of {total_values} total values"
            )

    # Check for missing values
    missing_values = df[year_cols].isna().sum().sum()
    total_values = len(df) * len(year_cols)
    coverage = ((total_values - missing_values) / total_values) * 100

    if verbose:
        print(
            f"  Data coverage: {coverage:.1f}% ({total_values - missing_values}"
            f"/{total_values} values)"
        )


def validate_no_null_values(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str,
    context: str = "",
    first_allocation_year: int | None = None,
    reference_data: TimeseriesDataFrame | None = None,
) -> None:
    """
    Validate that there are no null values in the TimeseriesDataFrame.

    Missing data can systematically bias allocations. The reference_data
    parameter allows expected NaN values (e.g., post-net-zero pathway years).

    Parameters
    ----------
    df : TimeseriesDataFrame
        DataFrame to check for null values
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    context : str
        Additional context for error messages
    first_allocation_year : int, optional
        If provided, check specifically for nulls in years >= first_allocation_year
    reference_data : TimeseriesDataFrame, optional
        If provided, NaN values in df are allowed if the corresponding year columns
        in reference_data are also NaN (e.g., for post-net-zero pathway years)

    Raises
    ------
    DataProcessingError
        If null values are found (excluding those that match reference_data
        NaN patterns)
    """
    # Check for any null values
    total_nulls = df.isnull().sum().sum()
    if total_nulls == 0:
        return  # No nulls found, validation passes

    # Find specific locations of null values
    null_mask = df.isnull()

    # If first_allocation_year is provided, focus on years >= first_allocation_year
    if first_allocation_year is not None:
        year_cols = [
            col for col in get_year_columns(df) if int(col) >= first_allocation_year
        ]
        if year_cols:
            year_null_mask = null_mask[year_cols]
            year_nulls = year_null_mask.sum().sum()
            if year_nulls > 0:
                # If reference_data provided, check if NaN values are expected
                if reference_data is not None:
                    # Get year columns from reference data
                    ref_year_cols = [
                        col
                        for col in get_year_columns(reference_data)
                        if col in year_cols
                    ]

                    # Check which years have NaN in reference data
                    unexpected_nulls = []
                    affected_countries_set = set()
                    for col in year_cols:
                        if year_null_mask[col].any():
                            # Check if this year has NaN in reference data
                            if col in ref_year_cols:
                                ref_is_nan = reference_data[col].isnull().any()
                                if not ref_is_nan:
                                    # NaN in result but not in reference -
                                    # this is unexpected
                                    null_countries = df.index[
                                        year_null_mask[col]
                                    ].tolist()
                                    unexpected_nulls.append(
                                        f"Year {col}: {len(null_countries)} countries"
                                    )
                                    affected_countries_set.update(null_countries)
                            else:
                                # Year not in reference data - unexpected
                                null_countries = df.index[year_null_mask[col]].tolist()
                                unexpected_nulls.append(
                                    f"Year {col}: {len(null_countries)} countries"
                                )
                                affected_countries_set.update(null_countries)

                    # If all NaN values are expected (match reference data),
                    # validation passes
                    if not unexpected_nulls:
                        return

                    # Convert to list and show which countries are affected
                    affected_countries = sorted(affected_countries_set)

                    # Report only unexpected nulls
                    error_msg = (
                        f"Found unexpected null values in "
                        f"{dataset_name_for_error_msg} "
                        f"for years >= {first_allocation_year}. "
                        f"These NaN values do not match the reference data "
                        f"pattern.\n\n"
                        f"Unexpected null locations: "
                        f"{'; '.join(unexpected_nulls[:5])}\n"
                        f"Affected countries ({len(affected_countries)}): "
                        f"{', '.join(str(c) for c in affected_countries[:20])}"
                        f"{'...' if len(affected_countries) > 20 else ''}\n\n"
                        f"This usually indicates missing input data (population, "
                        f"GDP, emissions, or Gini). "
                        f"Check your data preprocessing notebooks to ensure all "
                        f"countries have complete data."
                    )
                else:
                    # No reference data - report all nulls as errors
                    null_locations = []
                    affected_countries_set = set()
                    for col in year_cols:
                        if year_null_mask[col].any():
                            null_countries = df.index[year_null_mask[col]].tolist()
                            null_locations.append(
                                f"Year {col}: {len(null_countries)} countries"
                            )
                            affected_countries_set.update(null_countries)

                    # Convert to list and show which countries are affected
                    affected_countries = sorted(affected_countries_set)

                    error_msg = (
                        f"Found {year_nulls} null values in "
                        f"{dataset_name_for_error_msg} "
                        f"for years >= {first_allocation_year}. "
                        f"This should not happen; all countries should have "
                        f"complete data.\n\n"
                        # Show first 5 years to avoid too long messages
                        f"Null locations: {'; '.join(null_locations[:5])}\n"
                        f"Affected countries ({len(affected_countries)}): "
                        f"{', '.join(str(c) for c in affected_countries[:20])}"
                        f"{'...' if len(affected_countries) > 20 else ''}\n\n"
                        f"This usually indicates missing input data (population, "
                        f"GDP, emissions, or Gini). "
                        f"Check your data preprocessing notebooks to ensure all "
                        f"countries have complete data."
                    )

                if context:
                    error_msg += f" Context: {context}"

                raise DataProcessingError(error_msg)

    # General null check (if no specific year focus)
    error_msg = f"Found {total_nulls} null values in {dataset_name_for_error_msg}."
    if context:
        error_msg += f" Context: {context}"

    raise DataProcessingError(error_msg)


def validate_year_parameter(year: int, parameter_name: str) -> None:
    """
    Validate that a year parameter is an integer.

    Year parameters must be integers to prevent confusing type errors.
    Common mistake: passing year as string '2020' instead of int 2020.

    Parameters
    ----------
    year : int
        Year value to validate
    parameter_name : str
        Name of the parameter for error messages

    Raises
    ------
    AllocationError
        If year is not an integer
    """
    if not isinstance(year, int):
        raise AllocationError(
            f"{parameter_name} must be an integer, got {type(year).__name__}: {year}"
        )


def validate_incremental_annual_timeseries(
    df: TimeseriesDataFrame, dataset_name_for_error_msg: str, verbose: bool = True
) -> None:
    """
    Validate that TimeseriesDataFrame has consecutive annual year columns.

    Required for cumulative calculations, interpolation, and pathway tracking.

    Parameters
    ----------
    df : TimeseriesDataFrame
        TimeseriesDataFrame with years as columns
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    verbose : bool, optional
        Whether to print validation details (default: True)

    Raises
    ------
    DataProcessingError
        If validation fails (non-consecutive years found)
    """
    # Get year columns and sort them
    year_cols = sorted([int(col) for col in get_year_columns(df)])

    if len(year_cols) < 2:
        return  # Need at least 2 years to check for gaps

    # Check for gaps larger than 1 year
    gaps = []
    for i in range(len(year_cols) - 1):
        gap = year_cols[i + 1] - year_cols[i]
        if gap > 1:
            gaps.append((year_cols[i], year_cols[i + 1], gap))

    if gaps:
        gap_details = [f"{start}-{end} (gap: {gap} years)" for start, end, gap in gaps]
        raise DataProcessingError(
            f"{dataset_name_for_error_msg} has non-incremental year"
            f"columns. Gaps "
            f"found: {gap_details}. Expected: consecutive years."
        )

    if verbose:
        print(f"{dataset_name_for_error_msg} incremental annual timeseries validated")
        print(f"  Range: {min(year_cols)} - {max(year_cols)} ({len(year_cols)} years)")


def validate_single_emission_category(
    df: TimeseriesDataFrame, dataset_name_for_error_msg: str
) -> None:
    """
    Validate that only one emission category is present.

    Different emission categories (CO2-FFI, CO2-LULUCF, CH4) must be
    allocated separately.

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
            ['iso3c', 'unit','emission-category']
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    validate_not_empty(df, dataset_name_for_error_msg)
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

    Used for capability-based allocation. See docs/science/capability.md.

    Parameters
    ----------
    df : TimeseriesDataFrame
        GDP TimeseriesDataFrame
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    validate_not_empty(df, dataset_name_for_error_msg)
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

    Required for per capita allocation approaches. See docs/science/per-capita.md.

    Parameters
    ----------
    df : TimeseriesDataFrame
        Population TimeseriesDataFrame
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    validate_not_empty(df, dataset_name_for_error_msg)
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

    Used for intra-national equity adjustments. See docs/science/inequality.md.

    Parameters
    ----------
    df : TimeseriesDataFrame
        Gini stationary DataFrame
    dataset_name_for_error_msg : str, optional
        Name for error messages
    verbose : bool, optional
        Whether to print validation details
    """
    validate_not_empty(df, dataset_name_for_error_msg)
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


def validate_no_nan_shares(
    shares: TimeseriesDataFrame, dataset_name_for_error_msg: str = "Shares"
) -> None:
    """
    Validate that allocation shares contain no NaN values.

    Mixed NaN shares (some valid, some missing) can cause subtle downstream
    issues in allocation calculations and result interpretation.

    Parameters
    ----------
    shares : TimeseriesDataFrame
        Allocation shares DataFrame
    dataset_name_for_error_msg : str, optional
        Name for error messages (default: "Shares")

    Raises
    ------
    AllocationError
        If shares contain any NaN values
    """
    if shares.isna().any().any():
        # Find countries with NaN values in any year
        nan_countries = shares[shares.isna().any(axis=1)].index.tolist()
        raise AllocationError(
            f"{dataset_name_for_error_msg} contain NaN values for countries: "
            f"{nan_countries}. Ensure all countries have complete share data."
        )


def validate_scenarios_data(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str = "Scenarios",
    verbose: bool = True,
) -> None:
    """
    Validate scenario pathway data in TimeseriesDataFrame format.

    Scenario choice affects allocations. See docs/science/scenarios.md.

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
    validate_not_empty(df, dataset_name_for_error_msg)
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
