"""DataFrame utilities for the fair-shares library.

This module provides utilities for working with timeseries DataFrames including:
- Type definitions (TimeseriesDataFrame)
- Year column handling (ensure_string_year_columns, get_year_columns)
- Path validation (validate_path_exists)
- Data processing (IAMC data, country codes, grouping, etc.)
"""

from __future__ import annotations

import inspect
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import country_converter as coco
import numpy as np
import pandas as pd
from pandas_openscm.grouping import groupby_except
from pyprojroot import here

from fair_shares.library.exceptions import (
    ConfigurationError,
    DataLoadingError,
    DataProcessingError,
)

if TYPE_CHECKING:
    pass

__all__ = [
    # Type definition
    "TimeseriesDataFrame",
    # Year column utilities
    "ensure_string_year_columns",
    "get_year_columns",
    # Path validation
    "validate_path_exists",
    # Data processing
    "convert_country_name_to_iso3c",
    "derive_probability_based_categories",
    "determine_processing_categories",
    "filter_function_parameters",
    "groupby_except_robust",
    "normalize_metadata_column",
    "normalize_metadata_columns",
    "process_iamc_zip",
    "set_post_net_zero_emissions_to_nan",
]

_COUNTRY_CONVERTER = coco.CountryConverter()


# ============================================================================
# Type Definitions
# ============================================================================

TimeseriesDataFrame = pd.DataFrame
"""A pandas DataFrame that contains timeseries data.

The columns should always be the time points (years) and units, with rows representing
countries or scenarios. Values should be numeric, with NaN for missing data.

Example:

# Simple (e.g. population)

                    2000  2020
iso3c  unit
USA    million      10    15
CHN    million      800   1000
...

# Complex (e.g. scenario data)

                                                2000  2020
climate_assessment  quantile iso3c  unit
ssp245              0.5      World  Mt * CO2e   10    20
"""


# ============================================================================
# Year Column Utilities
# ============================================================================


def ensure_string_year_columns(
    df: TimeseriesDataFrame, *, inplace: bool = False
) -> TimeseriesDataFrame:
    """Coerce numeric-looking year column labels to strings.

    This is used to deal with TimeseriesDataFrames that have year columns often stored
    as ints or other types. We want to coerce these to strings so that merges are not
    problematic.

    Parameters
    ----------
    df
        TimeseriesDataFrame that may contain year columns stored as ints or other types.
    inplace
        If ``True``, rename the columns on ``df`` and return it. If ``False`` (default),
        return a TimeseriesDataFrame with renamed columns and leave ``df`` untouched.

    Returns
    -------
    TimeseriesDataFrame
        TimeseriesDataFrame whose year columns are strings. The returned object is
        ``df`` when ``inplace`` is ``True``; otherwise it is a renamed copy.
    """
    rename_map: dict = {}
    for col in df.columns:
        col_str = str(col)
        if col_str.isdigit() and col != col_str:
            rename_map[col] = col_str

    if not rename_map:
        return df if inplace else df.copy()

    if inplace:
        df.rename(columns=rename_map, inplace=True)
        return df

    return df.rename(columns=rename_map)


def get_year_columns(df: TimeseriesDataFrame, return_type: str = "string") -> list:
    """Return columns that look like years in the requested type.

    This is used to deal with TimeseriesDataFrames that have year columns.
    We usually want these to do stuff with them.

    Parameters
    ----------
    df
        TimeseriesDataFrame whose columns should be inspected.
    return_type
        Output type: ``"string"`` (default), ``"int"``, or ``"original"``.

    Returns
    -------
    list
        Ordered list of column labels matching the year pattern.
    """
    if return_type not in {"string", "int", "original"}:
        raise DataProcessingError(
            f"return_type must be 'string', 'int', or 'original', got {return_type}"
        )

    year_columns: list = []
    for col in df.columns:
        col_str = str(col)
        if not col_str.isdigit():
            continue

        if return_type == "string":
            year_columns.append(col_str)
        elif return_type == "int":
            year_columns.append(int(col_str))
        else:  # "original"
            year_columns.append(col)

    return year_columns


# ============================================================================
# Path Validation
# ============================================================================


def validate_path_exists(path_str: str, file_type: str = "data file") -> str:
    """Validate that the path exists (relative to project root).

    Args:
        path_str: The path string to validate
        file_type: Type of file for error message (e.g., "Emissions data file",
            "GDP data file")

    Returns
    -------
    The validated path string

    Raises
    ------
    ConfigurationError: If the path does not exist
    """
    if path_str.startswith("/") or ":" in path_str:  # Absolute path
        path = Path(path_str)
    else:  # Relative path - resolve from project root
        try:
            project_root = here()
            path = project_root / path_str
        except Exception:
            path = Path(path_str)

    if not path.exists():
        raise ConfigurationError(f"{file_type} not found: {path_str}")
    return path_str


# ============================================================================
# Data Processing Utilities
# ============================================================================


def _standardize_column_label(column: str) -> str:
    """Normalize arbitrary column strings to match our IAMC loader casing."""
    return str(column).strip().lower().capitalize()


def _standardize_column_labels(columns: list[str]) -> list[str]:
    """Vectorized helper mirroring the IAMC casing normalization."""
    return [_standardize_column_label(col) for col in columns]


def normalize_metadata_column(label: str) -> str:
    """Public helper to normalize metadata columns to IAMC casing."""
    return _standardize_column_label(label)


def normalize_metadata_columns(columns: list[str]) -> list[str]:
    """Normalize a list of metadata column labels."""
    return _standardize_column_labels(columns)


def derive_probability_based_categories(
    df: pd.DataFrame,
    category_specs: list[dict] | None,
) -> pd.DataFrame:
    """
    Expand datasets by duplicating scenarios that meet probability thresholds.

    Parameters
    ----------
    df
        IAMC-style dataframe containing metadata columns.
    category_specs
        Each spec must define:
            - label: New category name (e.g., "C1_67")
            - source_categories: Existing categories to subset (e.g., ["C1"])
            - probability_columns: Ordered list of metadata columns to use.
              The first non-null value per row is used.
            - max_exceedance_probability (optional): Upper bound (<=)
            - min_exceedance_probability (optional): Lower bound (>=)

    Returns
    -------
    pd.DataFrame
        Dataframe including any newly derived category rows appended.
    """
    if not category_specs:
        return df

    required_columns: set[str] = set()
    for spec in category_specs:
        for col in spec.get("probability_columns", []):
            required_columns.add(normalize_metadata_column(col))

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise DataProcessingError(
            "Requested probability-based climate assessments require metadata "
            f"columns that are missing from the IAMC dataset: {missing}"
        )

    augmented_frames = [df]
    for spec in category_specs:
        label = spec["label"]
        source_categories = spec.get("source_categories", [])
        probability_columns = [
            normalize_metadata_column(col)
            for col in spec.get("probability_columns", [])
        ]
        max_exceedance = spec.get("max_exceedance_probability")
        min_exceedance = spec.get("min_exceedance_probability")

        source_df = df[df["Category"].isin(source_categories)].copy()
        if source_df.empty:
            print(
                f"  No rows found for probability-derived category '{label}'. "
                f"Source categories: {source_categories}"
            )
            continue

        probability = pd.Series(np.nan, index=source_df.index, dtype=float)
        for col in probability_columns:
            col_values = pd.to_numeric(source_df[col], errors="coerce")
            probability = probability.fillna(col_values)

        mask = probability.notna()
        if max_exceedance is not None:
            mask &= probability <= max_exceedance
        if min_exceedance is not None:
            mask &= probability >= min_exceedance

        filtered = source_df[mask].copy()
        if filtered.empty:
            threshold_desc = []
            if max_exceedance is not None:
                threshold_desc.append(f"<= {max_exceedance}")
            if min_exceedance is not None:
                threshold_desc.append(f">= {min_exceedance}")
            print(
                f"  No scenarios satisfied thresholds for '{label}' "
                f"({', '.join(threshold_desc)})"
            )
            continue

        filtered["Category"] = label
        augmented_frames.append(filtered[df.columns])
        print(
            f"  Created {len(filtered)} pathways for derived category '{label}' "
            f"using probability columns {probability_columns}"
        )

    if len(augmented_frames) == 1:
        return df
    return pd.concat(augmented_frames, ignore_index=True)


def convert_country_name_to_iso3c(
    country_name: str | float | None,
    *,
    world_key: str,
) -> str | None:
    """Convert a source country label to ISO3C."""
    if pd.isna(country_name):
        return None

    country_name_str = str(country_name).strip()

    if country_name_str == world_key:
        return world_key

    iso3c = _COUNTRY_CONVERTER.convert(
        names=country_name_str,
        to="ISO3",
        not_found=None,
    )
    if iso3c is None or iso3c == country_name_str or len(str(iso3c)) != 3:
        return None
    return iso3c


def process_iamc_zip(
    zip_path: Path,
    metadata_columns: list[str] | None = None,
) -> TimeseriesDataFrame:
    """
    Process scenario data from zipped IAMC format files.

    This function extracts, loads, and merges IAMC (Integrated Assessment Modeling
    Consortium) data and metadata files from a zip archive. It handles both Excel
    and CSV formats and standardizes the output structure.

    Parameters
    ----------
    zip_path : pathlib.Path
        Path to the zip file containing IAMC data and metadata files
    metadata_columns : list[str] | None, optional
        Additional metadata columns (beyond ``Category``) to retain from the
        metadata file. Column names can be supplied in their original casing
        and will be normalized using the same logic as IAMC inputs. ``Category``
        is always included even if ``metadata_columns`` is not specified.

    Returns
    -------
    TimeseriesDataFrame
        Merged DataFrame with data and metadata, containing columns:
        - Category: climate assessment category (moved to first column)
        - Model: model name
        - Scenario: scenario name
        - Variable: variable name
        - Unit: units
        - Year columns: numerical values for each year

        Data is merged on Model and Scenario fields.

    Raises
    ------
    DataProcessingError
        If both data and metadata files cannot be found in the zip archive,
        or if the 'Category' column is missing from metadata

    Notes
    -----
    The function performs the following operations:
    1. Extracts zip contents to the same directory as the zip file
    2. Identifies data and metadata files (metadata files contain 'metadata' in name)
    3. Loads files using appropriate readers (Excel sheet 0 or CSV)
    4. Standardizes column names to sentence case
    5. Merges data and metadata on Model and Scenario columns
    6. Moves Category column to first position

    Expected file structure in zip:
    - One data file (Excel or CSV)
    - One metadata file (Excel or CSV) with 'metadata' in filename
    - Both files must have Model and Scenario columns for merging
    """
    # Normalize caller-provided metadata column names
    metadata_columns = metadata_columns or []
    normalized_metadata_cols = _standardize_column_labels(metadata_columns)
    if "Category" not in normalized_metadata_cols:
        normalized_metadata_cols = ["Category"] + [
            col for col in normalized_metadata_cols if col != "Category"
        ]

    extract_dir = zip_path.parent
    # Extract all files from the zip archive to the same directory as the zip
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
    # Identify data and metadata files
    files = list(extract_dir.glob("*.*"))
    # Only consider files that were just extracted (by checking zip contents)
    extracted_names = set(zip_ref.namelist())
    files = [f for f in files if f.name in extracted_names]
    data_file = None
    meta_file = None
    for f in files:
        if "metadata" in f.name.lower():
            meta_file = f
        else:
            data_file = f
    if data_file is None or meta_file is None:
        raise DataLoadingError(
            f"Could not find both data and metadata files in {zip_path}"
        )
    # Load the data file
    if data_file.suffix.lower() in [".xlsx", ".xls"]:
        df_data = pd.read_excel(data_file, sheet_name=0)
    else:
        df_data = pd.read_csv(data_file)
    # Load the metadata file
    if meta_file.suffix.lower() in [".xlsx", ".xls"]:
        meta_df = pd.read_excel(meta_file, sheet_name=0)
    else:
        meta_df = pd.read_csv(meta_file)
    # Convert column names to strings and standardize
    df_data.columns = _standardize_column_labels([str(c) for c in df_data.columns])
    meta_df.columns = _standardize_column_labels([str(c) for c in meta_df.columns])
    print(f"Data columns for {data_file.name}: {df_data.columns.tolist()}")
    print(f"Meta columns for {meta_file.name}: {meta_df.columns.tolist()}")
    # Ensure required metadata columns exist
    if "Category" not in meta_df.columns:
        raise DataProcessingError(f"No 'Category' column in metadata file {meta_file}")

    missing_meta_cols = [
        col for col in normalized_metadata_cols if col not in meta_df.columns
    ]
    if missing_meta_cols:
        raise DataProcessingError(
            "Missing requested metadata columns "
            f"in {meta_file.name}: {missing_meta_cols}"
        )

    # Merge on Model and Scenario (inner join)
    metadata_subset = ["Model", "Scenario"] + [
        col for col in normalized_metadata_cols if col not in ("Model", "Scenario")
    ]
    merged = pd.merge(
        df_data,
        meta_df[metadata_subset],
        on=["Model", "Scenario"],
        how="inner",
    )
    # Move category to first column
    cols = list(merged.columns)
    if "Category" in cols:
        cols = ["Category"] + [c for c in cols if c != "Category"]
        merged = merged[cols]
    return merged


def set_post_net_zero_emissions_to_nan(
    df: pd.DataFrame,
    emissions_col: str,
) -> tuple[pd.DataFrame, dict]:
    """
    Set post-net-zero emissions to NaN for scenario pathways.

    Finds the first year where emissions go net-negative, sets all emissions
    from that year onwards inclusive to NaN, and reports what was removed.

    Parameters
    ----------
    df
        Long-format DataFrame with 'year' column and emissions column.
    emissions_col
        Name of the column containing emission values.

    Returns
    -------
    tuple[pd.DataFrame, dict]
        Tuple of (adjusted DataFrame, metadata dict with net_zero_year and
        cumulative_net_negative_emissions).
    """
    result = df.copy()
    result = result.sort_values("year")

    emissions = result[emissions_col].values
    years = result["year"].values

    # Find first negative emission (net-zero year)
    negative_mask = emissions < 0
    if not negative_mask.any():
        # No net-zero reached - return unchanged
        return result, {"net_zero_year": None, "cumulative_net_negative_emissions": 0.0}

    first_negative_idx = np.argmax(negative_mask)
    net_zero_year = int(years[first_negative_idx])

    # Calculate cumulative net-negative before setting to NaN
    post_net_zero = emissions[first_negative_idx:]
    cumulative_net_negative = abs(np.nansum(post_net_zero[post_net_zero < 0]))

    # Set post-net-zero emissions to NaN
    result.loc[result["year"] >= net_zero_year, emissions_col] = np.nan

    # Get unit for warning message
    unit = result["unit"].iloc[0] if "unit" in result.columns else "units"
    print(
        f"WARNING: Net-zero reached in {net_zero_year}. "
        f"{cumulative_net_negative:.2f} {unit} of net-negative emissions set to NaN."
    )

    return result, {
        "net_zero_year": net_zero_year,
        "cumulative_net_negative_emissions": cumulative_net_negative,
    }


def determine_processing_categories(
    requested_category: str, supported_categories: list[str]
) -> dict[str, list[str] | bool]:
    """
    Determine emission categories to process based on requested categories.

    Simple logic:
    - If requested category is NOT like 'all-ghg', process it AND 'all-ghg'
      (for all-other calculation)
    - If requested category IS like 'all-ghg', just process that

    Parameters
    ----------
    requested_category
        Single requested emission category
    supported_categories
        List of supported emission categories

    Returns
    -------
    Dictionary with keys:
        - 'process': List of categories to process
        - 'create_all_other': Boolean indicating whether to create "all-other"
          timeseries
        - 'final': List of final categories that will be available (for
          loading/display)
    """
    # If requesting all-ghg*, just use that. Otherwise, add all-other.
    if requested_category.startswith("all-ghg"):
        process_categories = [requested_category]
        create_all_other = False
        final_categories = [requested_category]
    else:
        # Need all-ghg to create all-other
        process_categories = [requested_category, "all-ghg"]
        create_all_other = True
        final_categories = [requested_category, "all-other"]

    # Filter to supported categories only
    process_categories = [
        cat for cat in process_categories if cat in supported_categories
    ]

    return {
        "process": process_categories,
        "create_all_other": create_all_other,
        "final": final_categories,
    }


def groupby_except_robust(
    data: TimeseriesDataFrame | pd.Series, group_level: str
) -> TimeseriesDataFrame | pd.Series:
    """
    Robust groupby that handles both MultiIndex and single-level index cases.

    For MultiIndex: uses groupby_except to group by all levels except group_level
    For single-level index: uses simple sum() across rows

    Parameters
    ----------
    data
        DataFrame or Series to group
    group_level
        Level name to exclude from grouping (typically "iso3c")

    Returns
    -------
    Grouped data with totals calculated appropriately for the index structure
    """
    if isinstance(data.index, pd.MultiIndex):
        return groupby_except(data, group_level).sum()
    else:
        return data.sum(axis="rows")


def filter_function_parameters(
    func: Callable, provided_params: dict[str, Any]
) -> dict[str, Any]:
    """
    Filter and prepare function parameters using function signatures.

    This function inspects the target function's signature and filters the provided
    parameters to only include those that exist in the function signature and are
    not None.

    Parameters
    ----------
    func : Callable
        The function whose parameters to filter
    provided_params : dict[str, Any]
        Parameters provided by the caller

    Returns
    -------
    dict[str, Any]
        Filtered function arguments ready for function call
    """
    sig = inspect.signature(func)
    func_args = {}

    # Filter provided parameters to only include those in function signature
    # and not None
    for k, v in provided_params.items():
        if k in sig.parameters and v is not None:
            func_args[k] = v

    return func_args


def _extract_notebook_error(stderr: str) -> str | None:
    """Extract the actual notebook error from Snakemake output."""
    lines = stderr.split("\n")

    # Find the notebook error section
    in_error_section = False
    error_lines = []

    for line in lines:
        if "NOTEBOOK EXECUTION FAILED" in line:
            in_error_section = True
            continue
        if in_error_section:
            if line.startswith("RuleException:") or line.startswith("["):
                break
            error_lines.append(line)

    if error_lines:
        return "\n".join(error_lines).strip()
    return None
