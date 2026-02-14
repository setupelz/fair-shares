"""
Serialization utilities for allocation results.

This module provides functions for saving allocation results to parquet files
with comprehensive metadata to enable transparent, replicable analysis.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.allocations.results.metadata import (
    ALLOCATION_PARAMETER_COLUMNS,
    DATA_CONTEXT_COLUMNS,
    NUMERIC_COLUMN_TYPES,
    REQUIRED_COLUMNS,
    get_all_metadata_columns,
)
from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils.dataframes import ensure_string_year_columns
from fair_shares.library.utils.dataframes import TimeseriesDataFrame

logger = logging.getLogger(__name__)


def save_allocation_result(
    result: BudgetAllocationResult | PathwayAllocationResult,
    output_dir: Path,
    absolute_emissions: TimeseriesDataFrame | None = None,
    climate_assessment: str | None = None,
    quantile: float | None = None,
    data_context: dict | None = None,
    **metadata,
) -> dict[str, Path]:
    """
    Save allocation results to parquet files.

    Persists allocation results with comprehensive metadata to enable
    transparent, replicable analysis. Following the transparency principles
    recommended for transparency, all parameter choices and data sources
    are recorded to allow critical assessment of the normative choices embedded
    in each allocation.

    Parameters
    ----------
    result : Union[BudgetAllocationResult, PathwayAllocationResult]
        The allocation result to save
    output_dir : Path
        Directory to save results
    absolute_emissions : TimeseriesDataFrame, optional
        Absolute emissions data (if None, only relative shares are saved)
    climate_assessment : str, optional
        Climate assessment name (e.g., "AR6")
    quantile : float, optional
        Quantile value for scenario (e.g., 0.5 for median)
    data_context : dict, optional
        Context about data sources and processing. Should include sources for
        population, GDP, emissions, and other input data to enable verification.
    **metadata
        Additional metadata to include

    Returns
    -------
    dict[str, Path]
        Paths to saved parquet files

    Raises
    ------
    DataProcessingError
        If data preparation fails
    IOError
        If file writing fails

    Notes
    -----
    The output includes a ``warnings`` column that flags allocations requiring
    attention, such as:

    - ``not-fair-share``: Approaches like per-capita-convergence that privilege
      current emission patterns during transition
    - ``missing-net-negative``: Scenarios where negative emissions were excluded
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    is_budget = isinstance(result, BudgetAllocationResult)

    # Get relative shares data
    if is_budget:
        relative_data = result.relative_shares_cumulative_emission
    else:
        relative_data = result.relative_shares_pathway_emissions

    saved_files = {}

    # Save relative allocations
    try:
        relative_path = _save_to_parquet(
            data=relative_data,
            result=result,
            output_dir=output_dir,
            data_type="relative",
            climate_assessment=climate_assessment,
            quantile=quantile,
            data_context=data_context,
            **metadata,
        )
        saved_files["relative"] = relative_path
    except Exception as e:
        raise DataProcessingError(f"Failed to save relative allocations: {e}")

    # Save absolute allocations if provided
    if absolute_emissions is not None:
        try:
            absolute_path = _save_to_parquet(
                data=absolute_emissions,
                result=result,
                output_dir=output_dir,
                data_type="absolute",
                climate_assessment=climate_assessment,
                quantile=quantile,
                data_context=data_context,
                **metadata,
            )
            saved_files["absolute"] = absolute_path
        except Exception as e:
            raise DataProcessingError(f"Failed to save absolute allocations: {e}")

    return saved_files


def _save_to_parquet(
    data: TimeseriesDataFrame,
    result: BudgetAllocationResult | PathwayAllocationResult,
    output_dir: Path,
    data_type: str,
    climate_assessment: str | None = None,
    quantile: float | None = None,
    data_context: dict | None = None,
    **metadata,
) -> Path:
    """Save data to parquet file."""
    # Prepare DataFrame with metadata
    df = _prepare_dataframe(
        data=data,
        result=result,
        climate_assessment=climate_assessment,
        quantile=quantile,
        data_context=data_context,
        is_budget=isinstance(result, BudgetAllocationResult),
        **metadata,
    )

    filename = f"allocations_{data_type}.parquet"
    file_path = output_dir / filename

    # Write to parquet with append logic
    _write_parquet_with_append(df, file_path)

    return file_path


def delete_existing_parquet_files(output_dir: Path) -> None:
    """Delete existing parquet files in the output directory."""
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return

    # Find and delete existing parquet files
    parquet_files = list(output_dir.glob("allocations_*.parquet"))
    if parquet_files:
        print(f"Deleting {len(parquet_files)} existing parquet files:")
        for file_path in parquet_files:
            try:
                file_path.unlink()
                print(f"  Deleted: {file_path.name}")
            except Exception as e:
                print(f"  Failed to delete {file_path.name}: {e}")
    else:
        print("No existing parquet files found to delete")


def _prepare_dataframe(
    data: TimeseriesDataFrame,
    result: BudgetAllocationResult | PathwayAllocationResult,
    climate_assessment: str | None = None,
    quantile: float | None = None,
    data_context: dict | None = None,
    is_budget: bool = False,
    **metadata,
) -> pd.DataFrame:
    """
    Prepare DataFrame for parquet writing with all metadata.

    Structures the allocation data with comprehensive metadata columns to
    enable transparent analysis. Records all parameter choices and data
    sources, and generates warnings for allocations that require attention.
    """
    # Convert to DataFrame and reset index
    df = data.copy()
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()
    else:
        df = df.reset_index()
        if "iso3c" not in df.columns:
            df.rename(columns={"index": "iso3c"}, inplace=True)
        if "unit" not in df.columns:
            df["unit"] = "dimensionless"

    # Validate required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise DataProcessingError(
            f"Missing required columns: {missing}. Found: {list(df.columns)}"
        )

    # Add core metadata columns (only if they don't already exist)
    # Note: climate-assessment and emission-category may already exist from index
    metadata_cols = {
        "climate-assessment": climate_assessment,
        "quantile": quantile,
        "approach": result.approach,
        **metadata,
    }

    for col, value in metadata_cols.items():
        if col not in df.columns:
            df[col] = value

    # Add data context columns (only if they don't already exist)
    data_context = data_context or {}
    for col in DATA_CONTEXT_COLUMNS:
        if col not in df.columns:
            # Skip warnings column as it will be computed below
            if col == "warnings":
                continue
            df[col] = data_context.get(col)

    # Round missing-net-negative-mtco2e to nearest integer if present
    if "missing-net-negative-mtco2e" in df.columns:
        df["missing-net-negative-mtco2e"] = df["missing-net-negative-mtco2e"].apply(
            lambda x: round(x) if pd.notna(x) and x != 0 else x
        )

    # Create warnings column based on approach, missing data, and
    # country-specific warnings. Initialize warnings column.
    # Warnings flag allocations that require attention or represent
    # normative choices that users should be aware of.
    df["warnings"] = None

    # Process warnings for each row (country)
    for idx in df.index:
        warnings_list = []

        # Check if this is a per-capita-convergence approach.
        # This approach privileges current emission patterns during the
        # transition period, which conflicts with the principle that past
        # high emissions do not establish entitlements to future emissions.
        if result.approach == "per-capita-convergence":
            warnings_list.append("not-fair-share")

        # Check for missing net-negative emissions (row-specific)
        if "missing-net-negative-mtco2e" in df.columns:
            missing_val = df.loc[idx, "missing-net-negative-mtco2e"]
            if pd.notna(missing_val) and missing_val != 0:
                warnings_list.append(f"missing-net-negative:{int(missing_val)}")

        # Add country-specific warnings from result
        if result.country_warnings:
            # Get iso3c for this row
            if "iso3c" in df.index.names:
                iso3c = df.index.get_level_values("iso3c")[df.index.get_loc(idx)]
            elif "iso3c" in df.columns:
                iso3c = df.loc[idx, "iso3c"]
            else:
                iso3c = None

            if iso3c and iso3c in result.country_warnings:
                warnings_list.append(result.country_warnings[iso3c])

        # Join warnings with semicolon separator
        df.loc[idx, "warnings"] = "; ".join(warnings_list) if warnings_list else None

    # Add allocation parameter columns (only if they don't already exist)
    params = result.parameters or {}
    for col in ALLOCATION_PARAMETER_COLUMNS:
        if col not in df.columns:
            snake_col = col.replace("-", "_")
            # Try both hyphenated and underscored versions
            value = params.get(snake_col, params.get(col))
            df[col] = value

    # Get the metadata column list
    metadata_order = get_all_metadata_columns()

    # Ensure year columns are strings for consistent selection
    df = ensure_string_year_columns(df, inplace=True)

    # Get year columns and sort them
    year_cols = [c for c in df.columns if str(c).isdigit()]
    year_cols_sorted = sorted(year_cols, key=lambda x: int(x))

    # Ensure all metadata columns exist
    for col in metadata_order:
        if col not in df.columns:
            df[col] = None

    # Order columns - include both predefined and custom metadata from **metadata
    all_non_year_cols = [c for c in df.columns if c not in year_cols_sorted]
    ordered_cols = (
        [col for col in metadata_order if col in all_non_year_cols]
        + [col for col in all_non_year_cols if col not in metadata_order]
        + year_cols_sorted
    )
    df = df[ordered_cols]

    # Fix data types
    df = _fix_data_types(df, is_budget)

    return df


def _write_parquet_with_append(df: pd.DataFrame, file_path: Path) -> None:
    """Write DataFrame to parquet file with append logic."""
    if file_path.exists():
        try:
            existing = pd.read_parquet(file_path)
            combined = pd.concat([existing, df], ignore_index=True)
            print(f"Appending {len(df)} rows to existing file: {file_path.name}")
        except Exception as e:
            print(f"Warning: Could not read existing file {file_path.name}: {e}")
            print("Writing new data only.")
            combined = df
    else:
        combined = df
        print(f"Creating new file: {file_path.name}")

    if not combined.empty:
        combined.to_parquet(file_path, index=False)
        print(f"Successfully wrote {len(combined)} rows to {file_path.name}")
    else:
        print(f"Warning: No data to write to {file_path.name}")


def _fix_data_types(df: pd.DataFrame, is_budget: bool) -> pd.DataFrame:
    """Fix data types for parquet compatibility."""
    df = df.copy()

    # Use centralized numeric column type definitions
    numeric_cols = NUMERIC_COLUMN_TYPES.copy()

    for col, dtype in numeric_cols.items():
        if col in df.columns and df[col].notna().any():
            try:
                df[col] = df[col].astype(dtype)
            except (ValueError, TypeError) as e:
                # If conversion fails, keep as object
                logger.warning(
                    f"Failed to convert column '{col}' to {dtype}: {e}. "
                    f"Keeping as {df[col].dtype}"
                )

    return df
