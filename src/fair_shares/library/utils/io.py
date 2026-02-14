"""
I/O utilities for the fair-shares library.

This module provides functions for reading/writing allocation data and
generating human-readable documentation of allocation results.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from fair_shares.library.exceptions import DataLoadingError
from fair_shares.library.utils.dataframes import get_year_columns


def generate_parquet_readme(
    df: pd.DataFrame,
    output_dir: Path,
    parquet_filename: str,
    extra_notes: Iterable[str] | None = None,
    run_metadata: Mapping[str, Any] | None = None,
    readme_filename: str = "README_Parquet_Structure.txt",
) -> Path:
    """
    Generate a README file describing a parquet dataset that was just written.

    Parameters
    ----------
    df
        The dataframe whose structure should be documented
    output_dir
        Directory where the parquet (and README) live
    parquet_filename
        Filename of the parquet file for display in the README
    extra_notes
        Optional additional bullet points to include at the end
    run_metadata
        Optional metadata about the run for context
    readme_filename
        Filename for the generated README file

    Returns
    -------
    :
        Path to the generated README file

    Raises
    ------
    DataLoadingError
        If the output directory does not exist
    """
    if not output_dir.exists():
        raise DataLoadingError(f"Output directory does not exist: {output_dir}")

    readme_path = output_dir / readme_filename

    # Determine file type (relative or absolute) for enhanced documentation
    is_relative = "relative" in parquet_filename.lower()
    is_absolute = "absolute" in parquet_filename.lower()

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("ALLOCATION RESULTS\n")
        f.write("==================\n\n")

        f.write(f"Dataset: {parquet_filename}\n")
        f.write(f"Generated: {pd.Timestamp.now().isoformat()}\n")
        if run_metadata and "source-id" in run_metadata:
            f.write(f"Source ID: {run_metadata['source-id']}\n")
        f.write("\n")

        # FILES IN THIS DIRECTORY section
        f.write("FILES IN THIS DIRECTORY\n")
        f.write("-----------------------\n")
        f.write(
            "- allocations_relative.parquet: Country shares (sum to 1.0 globally)\n"
        )
        f.write("- allocations_absolute.parquet: Country emissions in Mt CO2e\n")
        f.write("- allocations_wide.csv: Excel-friendly wide format\n")
        f.write("- param_manifest.csv: All parameter combinations\n")
        f.write("- README_relative.txt: Documentation for relative allocations\n")
        f.write("- README_absolute.txt: Documentation for absolute allocations\n\n")

        # HOW TO USE THESE FILES section
        f.write("HOW TO USE THESE FILES\n")
        f.write("----------------------\n\n")
        f.write("In Excel:\n")
        f.write("  Open allocations_wide.csv directly\n\n")
        f.write("In R:\n")
        f.write("  library(arrow)\n")
        f.write(f'  df <- read_parquet("{parquet_filename}")\n\n')
        f.write("In Python:\n")
        f.write("  import pandas as pd\n")
        f.write(f'  df = pd.read_parquet("{parquet_filename}")\n\n')

        # COLUMN REFERENCE section
        f.write("COLUMN REFERENCE\n")
        f.write("----------------\n\n")
        f.write("Identifier columns:\n")
        f.write("  iso3c              - Country code (e.g., 'USA', 'CHN')\n")
        f.write(
            "  approach           - Allocation method "
            "(e.g., 'equal-per-capita-budget')\n"
        )
        f.write("  climate-assessment - Climate scenario (e.g., '1.5C', '2C')\n")
        f.write(
            "  quantile           - Probability percentile (e.g., '0.5' for median)\n"
        )
        f.write("  emission-category  - Type of emissions (e.g., 'co2-ffi')\n\n")

        f.write("Metadata columns:\n")
        f.write("  source-id          - Composite data source identifier\n")
        f.write("  emissions-source   - Historical emissions dataset\n")
        f.write("  gdp-source         - GDP dataset\n")
        f.write("  population-source  - Population dataset\n")
        f.write("  gini-source        - Gini coefficient dataset\n")
        f.write("  target-source      - Target type (e.g., 'rcbs', 'ar6')\n\n")

        f.write("Year columns (e.g., '2020', '2030', '2050'):\n")
        if is_relative:
            f.write("  - Fractions (0.0-1.0), sum to 1.0 across countries\n")
            f.write("  - Unit: dimensionless\n")
        elif is_absolute:
            f.write("  - Million tonnes CO2 equivalent (Mt CO2e)\n")
            f.write("  - Unit: Mt CO2e\n")
        else:
            f.write("  - Values vary by file type\n")
        f.write("\n")

        f.write("Note: Year columns are stored as STRINGS, not integers!\n\n")

        # EXAMPLE VALUES section
        f.write("EXAMPLE VALUES\n")
        f.write("--------------\n\n")
        if len(df) > 0:
            f.write("First 3 rows:\n\n")
            # Get first 3 rows with limited columns for display
            year_cols = get_year_columns(df)
            display_cols = [col for col in df.columns if col not in year_cols]
            # Add a few year columns for demonstration
            if year_cols:
                display_cols.extend(sorted(year_cols)[:3])

            sample_df = df.head(3)[display_cols] if display_cols else df.head(3)
            f.write(sample_df.to_string())
            f.write("\n\n")
        else:
            f.write("(Empty dataset)\n\n")

        # Basic info
        f.write("TECHNICAL DETAILS\n")
        f.write("-----------------\n\n")
        f.write(f"Shape: {df.shape[0]:,} rows x {df.shape[1]:,} columns\n")
        f.write(
            f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB\n\n"
        )

        # Index information
        f.write("Index Structure:\n")
        if isinstance(df.index, pd.MultiIndex):
            f.write(f"MultiIndex with {len(df.index.names)} levels:\n")
            for i, name in enumerate(df.index.names):
                level_values = df.index.get_level_values(i).nunique()
                f.write(f"  {i}: {name} ({level_values:,} unique values)\n")
        else:
            unique_count = df.index.nunique()
            f.write(f"Single index: {df.index.name} ({unique_count:,} unique values)\n")
        f.write("\n")

        # Column information
        f.write("Column Structure:\n")
        year_cols = get_year_columns(df)
        non_year_cols = [col for col in df.columns if col not in year_cols]

        if year_cols:
            year_range = f"{min(year_cols)}-{max(year_cols)}"
            f.write(f"Year columns: {len(year_cols)} columns ({year_range})\n")
        if non_year_cols:
            f.write(f"Non-year columns: {len(non_year_cols)} columns\n")
            for col in non_year_cols[:10]:  # Show first 10
                f.write(f"  - {col}\n")
            if len(non_year_cols) > 10:
                f.write(f"  ... and {len(non_year_cols) - 10} more\n")
        f.write("\n")

        # Data types
        f.write("Data Types:\n")
        dtype_counts = df.dtypes.value_counts()
        for dtype, count in dtype_counts.items():
            f.write(f"{dtype}: {count} columns\n")
        f.write("\n")

        # Missing values
        missing_counts = df.isnull().sum()
        missing_cols = missing_counts[missing_counts > 0]
        if len(missing_cols) > 0:
            f.write("Missing Values:\n")
            for col, count in missing_cols.items():
                pct = 100 * count / len(df)
                f.write(f"{col}: {count:,} ({pct:.1f}%)\n")
        else:
            f.write("Missing Values: None\n")
        f.write("\n")

        # Run metadata
        if run_metadata:
            f.write("Run Metadata:\n")
            for key, value in run_metadata.items():
                f.write(f"{key}: {value}\n")
            f.write("\n")

        # Extra notes
        if extra_notes:
            f.write("Additional Notes:\n")
            for note in extra_notes:
                f.write(f"- {note}\n")
            f.write("\n")

        # Link to documentation
        from fair_shares.library.config.urls import docs_url

        f.write("FOR MORE INFORMATION\n")
        f.write("--------------------\n")
        f.write("Full column documentation:\n")
        f.write(f"{docs_url('user-guide/output-schema')}\n\n")

        f.write("Generated automatically during data processing.\n")

    return readme_path


def generate_readme(output_dir: Path, data_context: dict | None = None) -> None:
    """
    Generate README files for relative and absolute parquet files.

    Creates human-readable documentation of the allocation outputs,
    including column descriptions and data sources. This supports
    the transparency goal of enabling users to understand and
    critically assess the choices embedded in each allocation.

    Parameters
    ----------
    output_dir : Path
        Directory containing parquet files
    data_context : dict, optional
        Context about data sources and processing
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find parquet files with the correct pattern
    parquet_files = list(output_dir.glob("allocations_*.parquet"))

    if not parquet_files:
        print("No parquet files found for README generation")
        return

    parquet_names = [f.name for f in parquet_files]
    print(f"Found {len(parquet_files)} parquet files: {parquet_names}")

    # Generate README for each parquet file
    for parquet_file in parquet_files:
        try:
            df = pd.read_parquet(parquet_file)

            # Determine if this is relative or absolute based on filename
            if "relative" in parquet_file.name:
                readme_name = "README_relative.txt"
            elif "absolute" in parquet_file.name:
                readme_name = "README_absolute.txt"
            else:
                print(
                    f"Skipping {parquet_file.name} - "
                    "cannot determine if relative or absolute"
                )
                continue

            generate_parquet_readme(
                df=df,
                output_dir=output_dir,
                parquet_filename=parquet_file.name,
                extra_notes=[],
                run_metadata=data_context or {},
                readme_filename=readme_name,
            )
            print(f"Generated {readme_name}")

        except Exception as e:
            print(f"Error generating README for {parquet_file.name}: {e}")


def create_param_manifest(
    param_manifest_rows: list[dict[str, Any]], output_dir: Path
) -> None:
    """
    Create param_manifest.csv with proper kebab-case column names.

    The parameter manifest provides a summary of all allocation configurations
    run in a batch, enabling quick comparison of different normative choices.
    This supports transparent reporting of how different parameter combinations
    affect allocation results.

    Parameters
    ----------
    param_manifest_rows : list[dict[str, Any]]
        List of parameter manifest rows, where each row contains parameters
        in snake_case format
    output_dir : Path
        Directory where param_manifest.csv will be saved
    """
    if not param_manifest_rows:
        print("Warning: No parameter manifest rows to save")
        return

    # Convert the list of dictionaries to DataFrame
    manifest_df = pd.DataFrame(param_manifest_rows)

    # Import here to avoid circular dependency
    # (allocations.results.__init__ imports from utils)
    from fair_shares.library.allocations.results.metadata import (
        ALLOCATION_PARAMETER_COLUMNS,
    )

    # Convert snake_case parameter columns to kebab-case
    for col in ALLOCATION_PARAMETER_COLUMNS:
        snake_col = col.replace("-", "_")
        if snake_col in manifest_df.columns and col not in manifest_df.columns:
            manifest_df[col] = manifest_df[snake_col]
            manifest_df.drop(columns=[snake_col], inplace=True)

    # Save to CSV
    manifest_path = output_dir / "param_manifest.csv"
    manifest_df.to_csv(manifest_path, index=False)
    print(
        f"Saved parameter manifest with {len(manifest_df)} rows to "
        f"{manifest_path.name}"
    )
