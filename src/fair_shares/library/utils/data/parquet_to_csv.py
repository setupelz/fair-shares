"""
Convert allocation parquet files to user-friendly wide-format CSV.

This script reads allocations_absolute.parquet and allocations_relative.parquet
and produces a single wide-format CSV with decomposed metadata columns and
summarized configuration strings.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from fair_shares.library.exceptions import DataProcessingError


def build_approach_short_column(
    df: pd.DataFrame,
    config_prefixes: dict[str, str] | None = None,
    approach_names: dict[str, str] | None = None,
) -> pd.Series:
    """
    Build the approach-short column with summarized configuration.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing approach and parameter columns
    config_prefixes : dict[str, str], optional
        Mapping of parameter names to their prefixes. If None, uses all
        available parameters.
    approach_names : dict[str, str], optional
        Mapping of approach names to short codes. If None, uses approach name as-is.

    Returns
    -------
    pd.Series
        The approach-short column with summarized configuration strings
    """
    default_approach_names = {
        # Pathway approaches
        "equal-per-capita": "EPC",
        "per-capita-adjusted": "PC-Adj",
        "per-capita-adjusted-gini": "PC-Adj-Gini",
        "per-capita-convergence": "PCC",
        "cumulative-per-capita-convergence": "CPCC",
        "cumulative-per-capita-convergence-adjusted": "CPCC-Adj",
        "cumulative-per-capita-convergence-gini-adjusted": "CPCC-Adj-Gini",
        # Budget approaches
        "equal-per-capita-budget": "EPC-B",
        "per-capita-adjusted-budget": "PC-Adj-B",
        "per-capita-adjusted-gini-budget": "PC-Adj-Gini-B",
    }
    if approach_names:
        default_approach_names.update(approach_names)

    default_prefixes = {
        "first-allocation-year": "y",
        "allocation-year": "ay",
        "preserve-first-allocation-year-shares": "pfa",
        "preserve-allocation-year-shares": "pa",
        "convergence-year": "c",
        "convergence-speed": "cs",
        "responsibility-weight": "rw",
        "capability-weight": "cw",
        "historical-responsibility-year": "hr",
        "responsibility-per-capita": "rpc",
        "capability-per-capita": "cpc",
        "responsibility-exponent": "re",
        "capability-exponent": "ce",
        "responsibility-functional-form": "rff",
        "capability-functional-form": "cff",
        "max-deviation-sigma": "s",
        "income-floor": "if",
        "max-gini-adjustment": "ga",
        "max-convergence-speed": "mcs",
        "strict": "strict",
    }

    if config_prefixes is not None:
        # Use only the specified parameters
        approach_config_columns = list(config_prefixes.keys())
        prefixes_to_use = config_prefixes
    else:
        # Use all available parameters from default list that exist in the dataframe
        approach_config_columns = [
            col for col in default_prefixes.keys() if col in df.columns
        ]
        prefixes_to_use = default_prefixes

    base_names = df["approach"].map(lambda x: default_approach_names.get(x, x))

    suffix_parts = []
    for col in approach_config_columns:
        if col not in df.columns:
            continue
        values = df[col]
        if col in {
            "first-allocation-year",
            "allocation-year",
            "convergence-year",
            "income-floor",
            "historical-responsibility-year",
        }:
            values = values.astype("Int64").astype("string")
        else:
            values = values.astype("string")
        prefix = prefixes_to_use.get(col, col[:2])
        suffix_parts.append(
            (prefix + values).where(values.notna() & (values != "<NA>"), "")
        )

    if suffix_parts:
        combined_suffixes = pd.concat(suffix_parts, axis=1).apply(
            lambda row: "-".join([p for p in row if p]), axis=1
        )
        approach_short = (base_names + "-" + combined_suffixes).str.rstrip("-")
    else:
        approach_short = base_names

    return approach_short


def format_warnings(val):
    """
    Format warnings for human readability.

    Parameters
    ----------
    val : str or float
        The warnings value from the parquet file

    Returns
    -------
    str
        Formatted warnings string
    """
    if pd.isna(val) or val == "":
        return ""

    # Parse the warnings string (format: "warning1; warning2")
    warnings = []
    for warning in str(val).split("; "):
        if warning.strip() == "not-fair-share":
            warnings.append("Not a fair-share approach")
        elif warning.strip().startswith("missing-net-negative:"):
            amount = warning.split(":")[1]
            msg = f"Missing net-negative: {amount} MtCO2e"
            warnings.append(msg)
        elif warning.strip().startswith("strict=false:"):
            # Keep the strict=false warnings as-is (they are already formatted)
            warnings.append(warning.strip())
        elif warning.strip():
            # Keep any other warnings as-is
            warnings.append(warning.strip())

    return "; ".join(warnings) if warnings else ""


def convert_parquet_to_wide_csv(
    allocations_dir: Path,
    output_path: Path | None = None,
    config_prefixes: dict[str, str] | None = None,
    approach_names: dict[str, str] | None = None,
) -> Path:
    """
    Convert allocation parquet files to wide-format CSV.

    Parameters
    ----------
    allocations_dir : Path
        Directory containing allocations_absolute.parquet and
        allocations_relative.parquet
    output_path : Path, optional
        Path for the output CSV file. If None, saves to
        allocations_dir/allocations_wide.csv
    config_prefixes : dict[str, str], optional
        Mapping of parameter names to prefixes for approach-short column.
        If None, includes all available parameters.
    approach_names : dict[str, str], optional
        Mapping of approach names to short codes. If None, uses defaults.

    Returns
    -------
    Path
        Path to the created CSV file

    Raises
    ------
    FileNotFoundError
        If allocations directory doesn't exist or no parquet files found
    DataProcessingError
        If data processing fails
    """
    allocations_dir = Path(allocations_dir)
    if not allocations_dir.exists():
        raise FileNotFoundError(
            f"Allocations directory does not exist: {allocations_dir}"
        )

    parquet_targets = {
        "absolute": allocations_dir / "allocations_absolute.parquet",
        "relative": allocations_dir / "allocations_relative.parquet",
    }
    type_to_path = {k: v for k, v in parquet_targets.items() if v.exists()}
    if not type_to_path:
        raise FileNotFoundError(
            "No absolute or relative allocation parquet files found in "
            f"{allocations_dir}"
        )

    combined_data = []

    for data_type, parquet_path in type_to_path.items():
        df = pd.read_parquet(parquet_path)

        # Add data_type column
        df.insert(0, "data_type", data_type)

        # Build approach-short column
        df["approach_short"] = build_approach_short_column(
            df, config_prefixes=config_prefixes, approach_names=approach_names
        )

        # Extract decomposed columns from data_context if available
        # The parquet files should already have these columns, but we'll rename them
        # to match the spec's snake_case convention

        # Rename columns to snake_case as per spec
        column_mapping = {
            "iso3c": "iso3c",  # Already correct
            "unit": "unit",  # Already correct
            "emission-category": "emission_category",
            "climate-assessment": "climate_assessment",
            "quantile": "quantile",
            "approach": "approach",
            "approach-short": "approach_short",
            "source": "source",
            "source-id": "source_id",
            "allocation-folder": "allocation_folder",
            "target-source": "target_source",
            "emissions-source": "emissions_source",
            "gdp-source": "gdp_source",
            "population-source": "population_source",
            "gini-source": "gini_source",
            "missing-net-negative-mtco2e": "missing_net_negative_mtco2e",
            "warnings": "warnings",
        }

        # Only rename columns that exist
        existing_renames = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=existing_renames)

        # Format warnings if present
        if "warnings" in df.columns:
            df["warnings"] = df["warnings"].apply(format_warnings)

        # Build the coded variable column for compatibility
        # Format: {emission_category}|{target_source}|{source}|
        #         {climate_assessment}|{quantile}|{approach_short}
        variable_parts = []
        if "emission_category" in df.columns:
            variable_parts.append(df["emission_category"].astype(str))
        if "target_source" in df.columns:
            variable_parts.append(df["target_source"].astype(str))
        if "source" in df.columns:
            variable_parts.append(df["source"].astype(str))
        if "climate_assessment" in df.columns:
            variable_parts.append(df["climate_assessment"].astype(str))
        if "quantile" in df.columns:
            variable_parts.append(df["quantile"].astype(str))
        if "approach_short" in df.columns:
            variable_parts.append(df["approach_short"].astype(str))

        if variable_parts:
            variable = variable_parts[0]
            for part in variable_parts[1:]:
                variable = variable + "|" + part
            df["variable"] = variable

        combined_data.append(df)

    # Combine absolute and relative data
    combined_df = pd.concat(combined_data, ignore_index=True)

    # Identify year columns
    year_cols = [c for c in combined_df.columns if str(c).isdigit()]
    if not year_cols:
        raise DataProcessingError("No year columns detected in parquet files")

    # Sort year columns
    year_cols_sorted = sorted(year_cols, key=lambda x: int(x))

    # Define column order as per spec
    # 1. Data Context
    metadata_cols = ["source_id", "allocation_folder"]
    # 2. Source Data (emissions, gdp, population, gini sources)
    source_data_cols = []
    if "emissions_source" in combined_df.columns:
        source_data_cols.append("emissions_source")
    if "gdp_source" in combined_df.columns:
        source_data_cols.append("gdp_source")
    if "population_source" in combined_df.columns:
        source_data_cols.append("population_source")
    if "gini_source" in combined_df.columns:
        source_data_cols.append("gini_source")
    # 3. Target source
    target_cols = []
    if "target_source" in combined_df.columns:
        target_cols.append("target_source")
    # 4. Approach & Summarized Configuration (only approach_short and
    #    variable, no individual columns)
    approach_cols = ["data_type", "approach_short", "variable"]
    # 5. Identity & Units
    identity_cols = ["iso3c", "unit"]
    # 6. Quality & Notes
    quality_cols = []
    if "warnings" in combined_df.columns:
        quality_cols.append("warnings")
    if "missing_net_negative_mtco2e" in combined_df.columns:
        quality_cols.append("missing_net_negative_mtco2e")

    # Build final column order
    ordered_cols = []
    for col_list in [
        metadata_cols,
        source_data_cols,
        target_cols,
        approach_cols,
        identity_cols,
        quality_cols,
    ]:
        for col in col_list:
            if col in combined_df.columns and col not in ordered_cols:
                ordered_cols.append(col)

    # Define columns to exclude
    # 1. Parameter columns (summarized in approach_short)
    # 2. Columns already in variable (target_source, source,
    #    emission_category, climate_assessment, quantile, approach)
    # 3. Extra metadata not needed
    cols_to_exclude = {
        # Parameter columns (summarized in approach_short)
        "first-allocation-year",
        "allocation-year",
        "preserve-first-allocation-year-shares",
        "preserve-allocation-year-shares",
        "convergence-year",
        "convergence-speed",
        "responsibility-weight",
        "capability-weight",
        "historical-responsibility-year",
        "responsibility-per-capita",
        "capability-per-capita",
        "responsibility-exponent",
        "capability-exponent",
        "responsibility-functional-form",
        "capability-functional-form",
        "max-deviation-sigma",
        "income-floor",
        "max-gini-adjustment",
        "max-convergence-speed",
        "strict",
        # Columns already encoded in variable
        "emission_category",
        "climate_assessment",
        "quantile",
        "source",
        "approach",
        # Additional metadata columns that aren't needed
        "rcb-source",
        "scenario-source",
        "total-budget",
    }

    # Add any remaining non-year columns that weren't explicitly ordered
    # (excluding columns we want to remove)
    for col in combined_df.columns:
        if (
            col not in ordered_cols
            and col not in year_cols_sorted
            and col not in cols_to_exclude
        ):
            ordered_cols.append(col)

    # Final column order: metadata columns + year columns
    final_cols = ordered_cols + year_cols_sorted
    combined_df = combined_df[[col for col in final_cols if col in combined_df.columns]]

    # Convert all column names to kebab-case
    def to_kebab_case(name):
        """Convert column name to kebab-case."""
        # If it's a year column (all digits), leave it as-is
        if str(name).isdigit():
            return name
        # Replace underscores with hyphens
        return name.replace("_", "-")

    combined_df.columns = [to_kebab_case(col) for col in combined_df.columns]

    # Determine output path
    if output_path is None:
        output_path = allocations_dir / "allocations_wide.csv"
    else:
        output_path = Path(output_path)

    # Save to CSV
    combined_df.to_csv(output_path, index=False)

    return output_path


def main():
    """CLI entry point for parquet to CSV converter."""
    parser = argparse.ArgumentParser(
        description="Convert allocation parquet files to wide-format CSV"
    )
    parser.add_argument(
        "allocations_dir",
        type=Path,
        help="Directory containing allocation parquet files",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: allocations_dir/allocations_wide.csv)",
    )
    parser.add_argument(
        "--param-prefixes",
        type=str,
        default=None,
        help=(
            "Comma-separated list of parameter:prefix pairs "
            "(e.g., 'first-allocation-year:y,responsibility-weight:rw')"
        ),
    )

    args = parser.parse_args()

    # Parse parameter prefixes if provided
    config_prefixes = None
    if args.param_prefixes:
        config_prefixes = {}
        for pair in args.param_prefixes.split(","):
            param, prefix = pair.split(":")
            config_prefixes[param.strip()] = prefix.strip()

    try:
        output_path = convert_parquet_to_wide_csv(
            allocations_dir=args.allocations_dir,
            output_path=args.output,
            config_prefixes=config_prefixes,
        )
        print(f"Successfully created wide CSV: {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
