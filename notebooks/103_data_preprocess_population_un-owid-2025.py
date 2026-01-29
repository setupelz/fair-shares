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
# # Population Data Preprocessing Script (UN + OWID 2025 Source)
#
# This script processes population data from UN and OWID sources.
# This is the UN + OWID 2025 source-specific version.

# %% [markdown]
# ## Set paths and library imports

# %%
# Imports
from datetime import datetime

import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.utils import build_source_id, ensure_string_year_columns

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
        "gdp": "wdi-2025",
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

# Get population configuration
population_config = config["population"][active_population_source]

# Extract population paths and parameters
population_historical_path = population_config["path_historical"]
population_projected_path = population_config["path_projected"]
population_historical_world_key = population_config["data_parameters"].get(
    "historical_world_key"
)
population_projected_world_key = population_config["data_parameters"].get(
    "projected_world_key"
)
projected_variant = population_config["data_parameters"].get("projected_variant")

# Construct source-specific intermediate_dir
intermediate_dir_str = f"output/{source_id}/intermediate/population"
intermediate_dir = project_root / intermediate_dir_str
intermediate_dir.mkdir(parents=True, exist_ok=True)

# Print out the parameters for debugging
print(f"Active population source: {active_population_source}")
print(f"Historical population path: {population_historical_path}")
print(f"Projected population path: {population_projected_path}")
print(f"Projected population variant: {projected_variant}")
print(f"Historical world key: {population_historical_world_key}")
print(f"Projected world key: {population_projected_world_key}")
print(f"Intermediate directory: {intermediate_dir_str}")

# %% [markdown]
# ## Load data

# %%
# Load historical population data (OWID)
historical_pop = pd.read_csv(project_root / population_historical_path)
print(f"Historical population data shape: {historical_pop.shape}")

# Load projected population data (UN)
projected_pop = pd.read_excel(
    project_root / population_projected_path, sheet_name="Median", header=16
)
print(f"Projected population data shape: {projected_pop.shape}")

# %% [markdown]
# ## Analysis

# %%
# Process historical population data (OWID)
print("Processing historical population data...")
# Read the CSV file
historical_df = pd.read_csv(project_root / population_historical_path)

# Filter out rows where Code is NaN (these are typically regional aggregates without ISO codes)
historical_df = historical_df[historical_df["Code"].notna()]

# Filter the data to start from 1850
historical_df = historical_df[historical_df["Year"] >= 1850]

# Rename columns for consistency with our pipeline
historical_df = historical_df.rename(
    columns={
        "Code": "iso3c",
        "Year": "year",
        "Population (historical estimates)": "population",
    }
)

# Convert from capita to millions
historical_df["population"] = historical_df["population"] * 1e-6

# Keep only the columns we need and drop any rows with NaN values
historical_df = historical_df[["iso3c", "year", "population"]].dropna()

# Sort the dataframe by country and year
historical_df = historical_df.sort_values(by=["iso3c", "year"])

print(f"Historical population data processed: {historical_df.shape}")

# Process projected population data (UN)
print("Processing projected population data...")
# Read the Excel file with appropriate header
projected_df = pd.read_excel(
    project_root / population_projected_path, sheet_name="Median", header=16
)

# Print available headers
print(f"Available headers: {projected_df.columns}")

# Melt the dataframe to convert year columns to rows
# First, identify year columns (these should be numeric and represent years)
year_columns = [
    col for col in projected_df.columns if isinstance(col, (int, float)) and col >= 1850
]

# Keep relevant columns plus year columns - include both ISO3 and region name columns
# World data is in the region name column, not ISO3
id_vars = ["ISO3 Alpha-code", "Region, subregion, country or area *"]
projected_df = projected_df.melt(
    id_vars=id_vars, value_vars=year_columns, var_name="year", value_name="population"
)

# Handle world data as the label "World" is stored in the region name column, not ISO3
world_mask = (projected_df["ISO3 Alpha-code"].isna()) & (
    projected_df["Region, subregion, country or area *"]
    == population_projected_world_key
)
projected_df.loc[world_mask, "ISO3 Alpha-code"] = population_projected_world_key
projected_df = projected_df.drop(columns=["Region, subregion, country or area *"])

# Filter out rows where ISO3 code is still NaN (these are regional aggregates we don't need)
projected_df = projected_df[projected_df["ISO3 Alpha-code"].notna()]

# Convert year to integer
projected_df["year"] = projected_df["year"].astype(int)

# Convert population from thousands to millions
projected_df["population"] = projected_df["population"] * 1e-3

# Remove rows with NaN population values
projected_df = projected_df.dropna(subset=["population"])

# Rename columns for consistency
projected_df = projected_df.rename(columns={"ISO3 Alpha-code": "iso3c"})

# IMPORTANT: Standardize world keys immediately after loading
# The historical world key is used as the standard for all population data
# This ensures consistency with the add_row_timeseries function which expects the historical world key
print(
    f"Standardizing world keys: {population_projected_world_key} -> {population_historical_world_key}"
)
projected_df.loc[projected_df["iso3c"] == population_projected_world_key, "iso3c"] = (
    population_historical_world_key
)

# Sort by country and year
projected_df = projected_df.sort_values(by=["iso3c", "year"])

print(f"Projected population data processed: {projected_df.shape}")

# Combine population data
print("Combining population data...")
print(
    f"Historical data year range: {historical_df['year'].min()}-{historical_df['year'].max()}"
)
print(
    f"Projected data year range: {projected_df['year'].min()}-{projected_df['year'].max()}"
)

# Filter projected data to only include years after the last historical year
# This ensures we don't have duplicate years, and historical data takes precedence
last_historical_year = historical_df["year"].max()
projected_df_filtered = projected_df[projected_df["year"] > last_historical_year].copy()
print(
    f"After filtering, projected data year range: {projected_df_filtered['year'].min()}-{projected_df_filtered['year'].max()}"
)
combined = pd.concat([historical_df, projected_df_filtered], ignore_index=True)
combined["year"] = combined["year"].astype(int)

# Sort by country and year to ensure proper ordering
combined = combined.sort_values(["iso3c", "year"])

# Drop duplicates, keeping the first occurrence (historical data takes precedence)
combined = combined.drop_duplicates(["iso3c", "year"], keep="first")

# Build full index of all years for each iso3c
idx = (
    combined.groupby("iso3c")["year"]
    .apply(lambda x: pd.Series(range(x.min(), x.max() + 1)))
    .reset_index(level=1, drop=True)
    .rename("year")
)
combined = (
    combined.set_index(["iso3c", "year"]).reindex(idx.reset_index()).reset_index()
)

# Ensure population is numeric for interpolation
combined["population"] = pd.to_numeric(combined["population"], errors="coerce")

# Interpolate population within each iso3c
combined["population"] = combined.groupby("iso3c")["population"].transform(
    lambda g: g.interpolate()
)

# Round to 6 decimal places for millions precision
combined["population"] = combined["population"].round(6)

# Sort by country and year
population_df = combined.sort_values(["iso3c", "year"])

print(f"Combined population data shape: {population_df.shape}")
print(f"Year range: {population_df['year'].min()}-{population_df['year'].max()}")

# Apply country population projection handling
if projected_variant == "un-median-to-2100":
    # No adjustment needed
    pass
elif projected_variant == "un-median-to-2050":
    # Freeze country population at 2050 level for years > 2050
    for iso in population_df["iso3c"].unique():
        mask_2050 = (population_df["iso3c"] == iso) & (population_df["year"] == 2050)
        if mask_2050.any():
            pop_2050 = population_df.loc[mask_2050, "population"].values[0]
            mask_future = (population_df["iso3c"] == iso) & (
                population_df["year"] > 2050
            )
            population_df.loc[mask_future, "population"] = pop_2050
elif projected_variant == "hist-frozen":
    current_year = datetime.now().year
    # Freeze country population at current year level for years > current_year
    for iso in population_df["iso3c"].unique():
        mask_current = (population_df["iso3c"] == iso) & (
            population_df["year"] == current_year
        )
        if mask_current.any():
            pop_current = population_df.loc[mask_current, "population"].values[0]
            mask_future = (population_df["iso3c"] == iso) & (
                population_df["year"] > current_year
            )
            population_df.loc[mask_future, "population"] = pop_current

# %% [markdown]
# ## Output

# %%
# Convert to TimeseriesDataFrame format and save
print("Converting to TimeseriesDataFrame format...")

# Add source information for TimeseriesDataFrame
population_ts = population_df.copy()

# Create TimeseriesDataFrame with years as columns
population_timeseries = population_ts.pivot_table(
    index=["iso3c"], columns="year", values="population", fill_value=None
)

# Enforce string year columns
population_timeseries = ensure_string_year_columns(population_timeseries)

# Convert to MultiIndex format with unit information
population_timeseries.index = pd.MultiIndex.from_tuples(
    [(iso3c, "million") for iso3c in population_timeseries.index],
    names=["iso3c", "unit"],
)

print(f"TimeseriesDataFrame shape: {population_timeseries.shape}")
print(f"TimeseriesDataFrame index levels: {list(population_timeseries.index.names)}")
print(
    f"TimeseriesDataFrame years: {population_timeseries.columns.min()} to {population_timeseries.columns.max()}"
)

# Save TimeseriesDataFrame
timeseries_output_path = intermediate_dir / "population_timeseries.csv"
population_timeseries.reset_index().to_csv(timeseries_output_path, index=False)
print(f"TimeseriesDataFrame saved to: {timeseries_output_path}")

# %%
