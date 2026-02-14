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
# # Gini Data Preprocessing Script (WID 2025 Source)
#
# This script processes Gini coefficient data from WID.world Excel files.
# This is the WID 2025 source-specific version.

# %% [markdown]
# ## Set paths and library imports

# %%
# Imports
import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.utils import build_source_id

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
        "gini": "wid-2025",
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

# Get Gini configuration (active source already set via papermill or interactive mode)
gini_config = config["gini"][active_gini_source]

# Extract Gini paths and parameters
gini_path = gini_config["path"]

# Construct source-specific intermediate_dir
intermediate_dir_str = f"output/{source_id}/intermediate/gini"
intermediate_dir = project_root / intermediate_dir_str
intermediate_dir.mkdir(parents=True, exist_ok=True)

# Print out the parameters for debugging
print(f"Active Gini source: {active_gini_source}")
print(f"Gini path: {gini_path}")
print(f"Intermediate directory: {intermediate_dir_str}")

# %% [markdown]
# ## Load data

# %%
# Load Gini data
print("Loading Gini data...")
gini_data = pd.read_excel(project_root / gini_path)
print(f"Gini data shape: {gini_data.shape}")
print(f"Gini data columns: {list(gini_data.columns)}")

# %% [markdown]
# ## Analysis

# %%
# Extract and rename required columns
print("Extracting required columns...")
gini_analysis = gini_data[["c3", "year", "gini", "quality"]].copy()
gini_analysis = gini_analysis.rename(columns={"c3": "iso3c"})

print(f"Initial data shape: {gini_analysis.shape}")
print(f"Columns: {list(gini_analysis.columns)}")

# Display sample of data
print("\nSample of extracted data:")
print(gini_analysis.head())

# Check for missing values
print("\nMissing values:")
print(gini_analysis.isnull().sum())

# Filter for the best quality data per country
print("\nFiltering for best quality data per country...")


# For each iso3c, get latest year with High quality, or latest year if no High quality
def get_best_quality_data(group):
    high_quality = group[group["quality"] == "High"]

    if len(high_quality) > 0:
        return high_quality.loc[high_quality["year"].idxmax()]
    else:
        return group.loc[group["year"].idxmax()]


# Group by iso3c and apply the filtering function
gini_filtered = (
    gini_analysis.groupby("iso3c").apply(get_best_quality_data).reset_index(drop=True)
)

print(f"Filtered data shape: {gini_filtered.shape}")
print(f"Unique countries: {gini_filtered['iso3c'].nunique()}")

# Display quality distribution
print("\nQuality distribution after filtering:")
print(gini_filtered["quality"].value_counts())

# Drop the year column as requested
gini_processed = gini_filtered.drop(["year", "quality"], axis=1)

# Convert Gini coefficients from 0-100 range to 0-1 range
gini_processed["gini"] = gini_processed["gini"] / 100.0

print("\nGini coefficient conversion:")
print(f"Sample values after conversion: {gini_processed['gini'].head().tolist()}")

# Drop all missing data before saving
print("\nBefore dropping missing data:")
print(f"Shape: {gini_processed.shape}")
print(f"Missing values: {gini_processed.isnull().sum().sum()}")

gini_processed = gini_processed.dropna()

print("\nAfter dropping missing data:")
print(f"Shape: {gini_processed.shape}")
print(f"Missing values: {gini_processed.isnull().sum().sum()}")

print("Final columns:", list(gini_processed.columns))

# Display sample of final data
print("\nSample of final processed data:")
print(gini_processed.head())

# %% [markdown]
# ## Output

# %%
# Convert to Stationary DataFrame format (for cross-sectional data)
print("Converting to Stationary DataFrame format...")

# Add source information for consistency
gini_stationary = gini_processed.copy()

# Create stationary DataFrame with MultiIndex ['iso3c', 'unit']
# Since Gini is cross-sectional (no time dimension), we use a different format
gini_stationary_df = gini_stationary.set_index(["iso3c"])[["gini"]]

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
