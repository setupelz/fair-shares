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
# # Gini Data Preprocessing Script (World Bank WDI 2025 Source)
#
# Processes Gini coefficients from the World Bank WDI bulk CSV export of
# indicator SI.POV.GINI. The indicator republishes the World Bank's Poverty and
# Inequality Platform (PIP) estimates, which are consumption-based for most low-
# and middle-income countries and income-based elsewhere. WIID pools
# income-based series, so values are not directly comparable between the two
# sources — see docs/user-guide/data-sources.md.
#
# One observation per country: the latest available within the configured year
# window. Survey Gini is sparse in any single year, so a single-year rule would
# cover roughly 70 countries instead of 150.

# %% [markdown]
# ## Set paths and library imports

# %%
# Imports
import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError

# %% tags=["parameters"]
emission_category = None
active_target_source = None
active_emissions_source = None
active_gdp_source = None
active_population_source = None
active_gini_source = None
active_lulucf_source = None
active_scenario_source = None
source_id = None

# %%
if emission_category is not None:
    # Running via Papermill — source_id is injected by the Snakefile
    print("Running via Papermill")

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
        "gini": "wdi-2025",
        "target": "pathway",
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

# Get Gini configuration (active source already set via papermill or interactive mode)
gini_config = config["gini"][active_gini_source]

# Extract Gini paths and parameters
gini_path = gini_config["path"]
gini_parameters = gini_config["data_parameters"]
selection = gini_parameters["selection"]
year_window = gini_parameters.get("year_window")

if selection != "latest-available":
    raise ConfigurationError(
        f"The WDI Gini notebook implements selection 'latest-available', "
        f"got '{selection}'. WDI publishes no quality flag, so a "
        f"quality-preferring rule cannot be applied to it."
    )

# Region mapping decides what counts as a country. The WDI bulk CSV mixes
# countries with regional and income-group aggregates (AFE, WLD, ...) that
# carry ISO3-shaped codes.
region_mapping_path = config["general"]["region_mapping"]["path"]

# Construct source-specific intermediate_dir
intermediate_dir_str = f"output/{source_id}/intermediate/gini"
intermediate_dir = project_root / intermediate_dir_str
intermediate_dir.mkdir(parents=True, exist_ok=True)

# Print out the parameters for debugging
print(f"Active Gini source: {active_gini_source}")
print(f"Gini path: {gini_path}")
print(f"Selection rule: {selection}")
print(f"Year window: {year_window}")
print(f"Intermediate directory: {intermediate_dir_str}")

# %% [markdown]
# ## Load data

# %%
# Read CSV, skip metadata rows (first 4 rows are headers/notes)
print("Loading Gini data...")
gini_data = pd.read_csv(project_root / gini_path, skiprows=4)
print(f"Gini data shape: {gini_data.shape}")

region_mapping = pd.read_csv(project_root / region_mapping_path)
countries = set(region_mapping["iso3c"].unique())
print(f"Countries in region mapping: {len(countries)}")

# %% [markdown]
# ## Analysis

# %%
# Melt the wide year columns to long format
id_cols = ["Country Name", "Country Code"]
year_cols = [col for col in gini_data.columns if col.isdigit()]
gini_long = gini_data[id_cols + year_cols].melt(
    id_vars=id_cols, value_vars=year_cols, var_name="year", value_name="gini"
)
gini_long = gini_long.rename(columns={"Country Code": "iso3c"})
gini_long["year"] = gini_long["year"].astype(int)
gini_long = gini_long.dropna(subset=["gini"])

print(f"Observations with a value: {len(gini_long)}")
print(f"Codes with any observation: {gini_long['iso3c'].nunique()}")

# Drop aggregates (regional and income-group rows)
aggregates = sorted(set(gini_long["iso3c"]) - countries)
gini_long = gini_long[gini_long["iso3c"].isin(countries)]
print(f"Codes dropped as not countries: {aggregates}")

# Restrict to the configured year window
if year_window:
    first_year, last_year = year_window
    gini_long = gini_long[
        (gini_long["year"] >= first_year) & (gini_long["year"] <= last_year)
    ]
    print(f"Observations within {first_year}-{last_year}: {len(gini_long)}")

# One observation per country: the latest year available
gini_filtered = gini_long.sort_values(["iso3c", "year"]).groupby("iso3c").tail(1)

print(f"Countries with a selected observation: {gini_filtered['iso3c'].nunique()}")
print("\nObservation years selected:")
print(gini_filtered["year"].value_counts().sort_index())

# Convert Gini coefficients from 0-100 range to 0-1 range
gini_processed = gini_filtered[["iso3c", "gini"]].copy()
gini_processed["gini"] = gini_processed["gini"] / 100.0

out_of_range = gini_processed[(gini_processed["gini"] < 0) | (gini_processed["gini"] > 1)]
if not out_of_range.empty:
    raise ValueError(f"Gini values outside 0-1 after conversion:\n{out_of_range}")

print("\nGini summary after conversion:")
print(gini_processed["gini"].describe())

# %% [markdown]
# ## Output

# %%
# Convert to Stationary DataFrame format (for cross-sectional data)
print("Converting to Stationary DataFrame format...")

gini_stationary_df = gini_processed.set_index(["iso3c"])[["gini"]]

# Convert to MultiIndex with unit information
gini_stationary_df.index = pd.MultiIndex.from_tuples(
    [(iso3c, "unitless") for iso3c in gini_stationary_df.index], names=["iso3c", "unit"]
)

print(f"Stationary DataFrame shape: {gini_stationary_df.shape}")
print(f"Stationary DataFrame index levels: {list(gini_stationary_df.index.names)}")
print(f"Stationary DataFrame columns: {list(gini_stationary_df.columns)}")

# Save Stationary DataFrame
stationary_output_path = intermediate_dir / "gini_stationary.csv"
gini_stationary_df.reset_index().to_csv(stationary_output_path, index=False)
print(f"Stationary DataFrame saved to: {stationary_output_path}")

# Display sample
print("\nSample of stationary data:")
print(gini_stationary_df.head())

# %%
