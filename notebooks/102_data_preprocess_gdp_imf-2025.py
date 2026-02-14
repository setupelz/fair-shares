# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags,-all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # GDP Data Preprocessing Script (IMF 2025 Source)
#
# This script processes GDP data (PPP and MER) from IMF Excel files.
# This is the IMF 2025 source-specific version.

# %% [markdown]
# ## Set paths and library imports

# %%
# Imports
import warnings

import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.utils import (
    build_source_id,
    convert_country_name_to_iso3c,
    ensure_string_year_columns,
)

# %% tags=["parameters"]
emission_category = None
active_target_source = None
active_emissions_source = None
active_gdp_source = None
active_population_source = None
active_gini_source = None

# %%
if emission_category is not None:
    # Running via Papermill
    print("Running via Papermill")

    # Construct path to composed config (created by compose_config rule in Snakefile)
    source_id = build_source_id(
        emissions=active_emissions_source,
        gdp=active_gdp_source,
        population=active_population_source,
        gini=active_gini_source,
        target=active_target_source,
        emission_category=emission_category,
    )

    config_path = here() / f"output/{source_id}/config.yaml"

    print(f"Loading config from: {config_path}")
    with open(config_path) as f:
        config = yaml.safe_load(f)

else:
    # Running interactively
    print("Running interactively - build desired config")

    # Interactive development configuration
    emission_category = "all-ghg-ex-co2-lulucf"
    active_sources = {
        "emissions": "primap-202503",
        "gdp": "imf-2025",
        "population": "un-owid-2025",
        "gini": "unu-wider-2025",
        "target": "ar6",
    }

    # Build interactive development config using the same logic as the pipeline
    from fair_shares.library.utils.data.config import build_data_config

    config, source_id = build_data_config(emission_category, active_sources)
    # Convert Pydantic model to dict for consistency with pipeline
    config = config.model_dump()

    # Set interactive development runtime parameters
    active_target_source = active_sources["target"]
    active_emissions_source = active_sources["emissions"]
    active_gdp_source = active_sources["gdp"]
    active_population_source = active_sources["population"]
    active_gini_source = active_sources["gini"]

# %% [markdown]
# ## Prepare parameters

# %%
project_root = here()
print(f"Project root: {project_root}")

# Get GDP configuration
gdp_config = config["gdp"][active_gdp_source]

# Extract GDP paths and parameters
gdp_ppp_path = gdp_config["path_ppp"]
gdp_mer_path = gdp_config["path_mer"]
gdp_world_key = gdp_config["data_parameters"].get("world_key")

# Get GDP variant from config (default to PPP if not specified)
gdp_variant = gdp_config["data_parameters"].get("gdp_variant")
if gdp_variant not in ["PPP", "MER"]:
    raise ConfigurationError(
        f"Invalid GDP variant '{gdp_variant}'. Must be 'PPP' or 'MER'."
    )

# Construct source-specific intermediate_dir
intermediate_dir_str = f"output/{source_id}/intermediate/gdp"
intermediate_dir = project_root / intermediate_dir_str
intermediate_dir.mkdir(parents=True, exist_ok=True)

# Print out the parameters for debugging
print(f"Active GDP source: {active_gdp_source}")
print(f"GDP variant: {gdp_variant}")
print(f"GDP PPP path: {gdp_ppp_path}")
print(f"GDP MER path: {gdp_mer_path}")
print(f"GDP world key: {gdp_world_key}")
print(f"Intermediate directory: {intermediate_dir_str}")

# %% [markdown]
#
#

# %% [markdown]
# ## Load data

# %% [markdown]
# ## Analysis

# %%
# Process GDP data based on selected variant
print(f"Processing {gdp_variant} GDP data...")

# Determine which path to use
if gdp_variant == "PPP":
    gdp_path = gdp_ppp_path
    value_col_name = "gdp-ppp"
else:  # MER
    gdp_path = gdp_mer_path
    value_col_name = "gdp-mer"

# Read Excel file (no rows to skip - data starts immediately)
gdp_file_path = project_root / gdp_path
read_excel_kwargs = {}
if gdp_file_path.suffix.lower() == ".xls":
    read_excel_kwargs["engine"] = "calamine"

gdp_data = pd.read_excel(gdp_file_path, **read_excel_kwargs)

# Keep only country column (first col) and year columns
country_col = gdp_data.columns[0]
year_cols = [col for col in gdp_data.columns if str(col).isdigit()]
gdp_data = gdp_data[[country_col, *year_cols]]

# Convert country names to ISO3C codes using utility
print("Converting country names to ISO3C codes...")
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    gdp_data["iso3c"] = gdp_data[country_col].apply(
        lambda country: convert_country_name_to_iso3c(
            country,
            world_key=gdp_world_key,
        )
    )

# Check for countries that failed to convert
failed_conversions = gdp_data[gdp_data["iso3c"].isna()][country_col].unique()
if len(failed_conversions) > 0:
    print(f"Warning: {len(failed_conversions)} countries failed to convert to ISO3C:")
    for country in failed_conversions:
        print(f"  - {country}")

# Filter out rows where ISO3C conversion failed
# (world aggregate rows are already standardized)
gdp_data = gdp_data[gdp_data["iso3c"].notna()]

# Melt to long format
gdp_data = gdp_data.melt(
    id_vars=[country_col, "iso3c"],
    value_vars=year_cols,
    var_name="year",
    value_name=value_col_name,
)

# Convert year to integer
gdp_data["year"] = gdp_data["year"].astype(int)

# Handle "no data" entries - convert string "no data" to NaN
if gdp_data[value_col_name].dtype == "object":
    # Replace case-insensitive "no data" strings with NaN
    mask = gdp_data[value_col_name].astype(str).str.lower() == "no data"
    gdp_data.loc[mask, value_col_name] = pd.NA
    gdp_data[value_col_name] = pd.to_numeric(gdp_data[value_col_name], errors="coerce")

# Remove missing values and filter years >= 1990
gdp_data = gdp_data.dropna(subset=[value_col_name])
gdp_data = gdp_data[(gdp_data["year"] >= 1990) & (gdp_data["year"] <= 2024)]
gdp_data = gdp_data.sort_values(["iso3c", "year"]).reset_index(drop=True)

# Drop the original country column as we now have iso3c
gdp_data = gdp_data.drop(columns=[country_col])

# Rename the value column to generic "gdp"
gdp_data = gdp_data.rename(columns={value_col_name: "gdp"})
gdp_data = gdp_data[["iso3c", "year", "gdp"]]

# %% [markdown]
# ## Output

# %%
# Convert to TimeseriesDataFrame format and save
print("Converting to TimeseriesDataFrame format...")

# Create TimeseriesDataFrame with years as columns
gdp_timeseries = gdp_data.pivot_table(
    index=["iso3c"], columns="year", values="gdp", fill_value=None
)

# Enforce string year columns
gdp_timeseries = ensure_string_year_columns(gdp_timeseries)

# Data is already in billions USD (no conversion needed)

# Convert to MultiIndex format with unit information
gdp_timeseries.index = pd.MultiIndex.from_tuples(
    [(iso3c, "billion") for iso3c in gdp_timeseries.index], names=["iso3c", "unit"]
)

print(f"TimeseriesDataFrame shape: {gdp_timeseries.shape}")
print(f"TimeseriesDataFrame index levels: {list(gdp_timeseries.index.names)}")
print(
    f"TimeseriesDataFrame years: \
    {gdp_timeseries.columns.min()} to {gdp_timeseries.columns.max()}"
)

# Save TimeseriesDataFrame
timeseries_output_path = intermediate_dir / "gdp_timeseries.csv"
gdp_timeseries.reset_index().to_csv(timeseries_output_path, index=False)
print(f"TimeseriesDataFrame saved to: {timeseries_output_path}")

# %%
