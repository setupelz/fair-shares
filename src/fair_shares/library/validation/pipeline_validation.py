"""
Pipeline validation functions for the fair-shares library.

"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils.dataframes import TimeseriesDataFrame, get_year_columns


def validate_paths(notebook_path, output_path):
    """
    Validate notebook and output paths.

    Parameters
    ----------
    notebook_path : Path
        Path to input notebook
    output_path : Path
        Path for output notebook

    Raises
    ------
    SystemExit
        If paths are invalid or inaccessible
    """
    # Check input notebook exists
    if not notebook_path.exists():
        print("\n" + "=" * 60)
        print("INPUT NOTEBOOK NOT FOUND!")
        print("=" * 60)
        print(f"Notebook path: {notebook_path}")
        print(f"Absolute path: {notebook_path.absolute()}")
        print(f"Current working directory: {Path.cwd()}")
        print("\n" + "=" * 60)
        sys.exit(1)

    # Check input notebook is readable
    if not os.access(notebook_path, os.R_OK):
        print("\n" + "=" * 60)
        print("INPUT NOTEBOOK NOT READABLE!")
        print("=" * 60)
        print(f"Notebook path: {notebook_path}")
        print("Check file permissions.")
        print("\n" + "=" * 60)
        sys.exit(1)

    # Check output directory is writable
    output_dir = output_path.parent
    if output_dir.exists() and not os.access(output_dir, os.W_OK):
        print("\n" + "=" * 60)
        print("OUTPUT DIRECTORY NOT WRITABLE!")
        print("=" * 60)
        print(f"Output directory: {output_dir}")
        print("Check directory permissions.")
        print("\n" + "=" * 60)
        sys.exit(1)


def validate_index_structure(
    df: TimeseriesDataFrame,
    dataset_name_for_error_msg: str,
    expected_index_names: list[str] | None = None,
) -> None:
    """
    Validate that TimeseriesDataFrame has expected index structure.

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
    Validate that a year exists in the dataset.

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


def validate_incremental_annual_timeseries(
    df: TimeseriesDataFrame, dataset_name_for_error_msg: str, verbose: bool = True
) -> None:
    """
    Validate that TimeseriesDataFrame has incremental annual year columns.

    This checks that there are no gaps larger than 1 year across the year columns.

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
        If validation fails (non-incremental years found)
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


def validate_dataset_totals(
    complete_df: TimeseriesDataFrame,
    world_series: pd.Series | pd.DataFrame,
    dataset_name_for_error_msg: str,
    verbose: bool = True,
) -> bool:
    """
    Validate that analysis iso3c's + ROW = World totals for a dataset.

    Parameters
    ----------
    complete_df : TimeseriesDataFrame
        TimeseriesDataFrame with analysis countries + ROW
    world_series : pd.Series
        World totals with years as index
    dataset_name_for_error_msg : str
        Name of the dataset for error messages
    verbose : bool, optional
        Whether to print validation details (default: True)

    Returns
    -------
    bool
        True if validation passes, False otherwise
    """
    # If world totals provided as a DataFrame, require single row and convert to Series
    if isinstance(world_series, pd.DataFrame):
        if len(world_series) != 1:
            if verbose:
                print(
                    f"Warning: Expected a single world row for "
                    f"{dataset_name_for_error_msg}, got {len(world_series)} rows"
                )
            return False
        world_row = world_series.iloc[0]
    else:
        world_row = world_series

    # Find common year columns between df and world data
    common_years = [
        col for col in get_year_columns(complete_df) if col in world_row.index
    ]

    if not common_years:
        if verbose:
            print(f"Warning: No matching year columns for {dataset_name_for_error_msg}")
        return False

    # Prepare aligned views using string-based year labels
    complete_df_aligned = complete_df.copy()
    complete_df_aligned.columns = [str(c) for c in complete_df_aligned.columns]
    world_series_aligned = world_row.copy()
    world_series_aligned.index = [str(i) for i in world_series_aligned.index]

    # Sum all countries (analysis + ROW) for each year
    analysis_total = complete_df_aligned[common_years].sum()
    world_vals = world_series_aligned[common_years]

    # Check for discrepancies (allowing small floating point differences)
    valid_mask = ~(analysis_total.isna() | world_vals.isna())
    if valid_mask.any():
        differences = (analysis_total[valid_mask] - world_vals[valid_mask]).abs()
        max_diff = differences.max()

        if max_diff > 1:  # Allow for rounding differences
            if verbose:
                print(
                    f"WARNING: {dataset_name_for_error_msg} analysis + ROW"
                    f" != world total!"
                )
                print(f"  Maximum difference: {max_diff:.2f}")
                large_diffs = differences[differences > 1]
                if len(large_diffs) > 0:
                    print(f"  Years with large diff: {list(large_diffs.index[:5])}")
            return False
        else:
            if verbose:
                print(
                    f"{dataset_name_for_error_msg}: analysis + ROW = world total "
                    f"(max diff: {max_diff:.2f})"
                )
            return True
    else:
        if verbose:
            print(f"No valid data for {dataset_name_for_error_msg} validation")
        return False


def validate_all_datasets_totals(
    datasets_dict: dict, world_totals_dict: dict, verbose: bool = True
) -> dict:
    """
    Validate that analysis iso3c's + ROW = World totals for multiple datasets.

    Parameters
    ----------
    datasets_dict : dict
        Dictionary mapping dataset names to complete DataFrames
    world_totals_dict : dict
        Dictionary mapping dataset names to world total Series
    verbose : bool, optional
        Whether to print validation details (default: True)

    Returns
    -------
    dict
        Dictionary mapping dataset names to validation results (bool)
    """
    results = {}

    if verbose:
        print("Validating that analysis datasets match world totals...")

    for dataset_name_for_error_msg in datasets_dict:
        if dataset_name_for_error_msg in world_totals_dict:
            result = validate_dataset_totals(
                datasets_dict[dataset_name_for_error_msg],
                world_totals_dict[dataset_name_for_error_msg],
                dataset_name_for_error_msg,
                verbose,
            )
            results[dataset_name_for_error_msg] = result
        else:
            if verbose:
                print(
                    f"Warning: No world totals found for {dataset_name_for_error_msg}"
                )
            results[dataset_name_for_error_msg] = False

    if verbose:
        passed = sum(results.values())
        total = len(results)
        print(f"\nValidation complete: {passed}/{total} datasets passed")

    return results
