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
# # PRIMAP Emissions Data Preprocessing
#
# The script processes emissions data for multiple variables and categories, and outputs
# data for either HIST-TP (third party) or HIST-CR (country-reported) based on the
# data_parameter configuration.

# %% [markdown]
# ## Set paths and library imports

# %%
# Imports
import matplotlib.pyplot as plt
import pandas as pd
import xarray as xr
import yaml
from pyprojroot import here

from fair_shares.library.exceptions import (
    ConfigurationError,
    DataLoadingError,
    DataProcessingError,
)
from fair_shares.library.utils import (
    build_source_id,
    convert_unit_robust,
    determine_processing_categories,
    ensure_string_year_columns,
    get_default_unit_registry,
    set_single_unit,
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

# Get emissions config from active source
emissions_config = config["emissions"][active_emissions_source]

# Extract paths and parameters
emissions_path = emissions_config["path"]
emissions_data_parameters = emissions_config["data_parameters"]

# Construct intermediate_dir from output directory structure
intermediate_dir_str = f"output/{source_id}/intermediate/emissions"
intermediate_dir = project_root / intermediate_dir_str
intermediate_dir.mkdir(parents=True, exist_ok=True)

# Unpack required nested parameters
available_categories = emissions_data_parameters.get("available_categories", [])
world_key = emissions_data_parameters.get("world_key")
scenario = emissions_data_parameters.get("scenario")

# Get global emission categories from the config
emission_category = config["emission_category"]

# Check required parameters are specified
if not emission_category:
    raise ConfigurationError("'emission_category' must be specified in global config")

if not available_categories:
    raise ConfigurationError(
        "'available_categories' must be specified in emissions data_parameters"
    )

# Validate that requested emission category is available in this data source
if emission_category not in available_categories:
    raise ConfigurationError(
        f"Requested emission category '{emission_category}' not available in data "
        f"source. Available categories: {available_categories}"
    )

# Determine which categories to process using utility function
processing_info = determine_processing_categories(
    emission_category, available_categories
)
processing_categories = processing_info["process"]
create_all_other = processing_info["create_all_other"]
final_categories = processing_info["final"]

print(f"Processing categories: {processing_categories}")
print(f"Create all-other: {create_all_other}")

# Define variable mappings for timeseries processing based on emission categories
variable_mappings = {
    "co2-ffi": {
        "emission": "CO2",
        "category": ["1", "2"],  # Energy + IPPU
    },
    "co2-lulucf": {
        "emission": "CO2",
        "category": ["M.LULUCF"],  # LULUCF
    },
    "ch4-ffi": {
        "emission": "CH4",
        "category": ["1", "2", "4", "5"],  # Non-AFOLU: Energy, IPPU, Waste, Other
    },
    "ch4-afolu": {
        "emission": "CH4",
        "category": ["M.AG", "M.LULUCF"],  # AFOLU = Agriculture + LULUCF
    },
    "n2o": {
        "emission": "N2O",
        "category": ["0"],  # All sectors
    },
    "all-ghg": {
        "emission": "KYOTOGHG (AR6GWP100)",
        "category": ["0"],  # Total all sectors and gases
    },
    "all-ghg-ex-co2-lulucf": {
        "emission": "KYOTOGHG (AR6GWP100)",
        "category": ["M.0.EL"],  # Total excl. CO2 LULUCF
    },
}

# Filter variable mappings to only include categories that are requested
timeseries_specs = {}
for category in processing_categories:
    if category in variable_mappings:
        timeseries_specs[category] = {
            "column": [variable_mappings[category]["emission"]],
            "category": variable_mappings[category]["category"]
            if isinstance(variable_mappings[category]["category"], list)
            else [variable_mappings[category]["category"]],
        }

# Print out the parameters for debugging.
print(f"Active emissions source: {active_emissions_source}")
print(f"Emissions data path: {emissions_path}")
print(f"Emission category: {emission_category}")
print(f"PRIMAP scenario: {scenario}")
print(f"World key: {world_key}")
print(f"Intermediate directory: {intermediate_dir_str}")

# %% [markdown]
# ## Load data

# %%
print(f"Opening emissions file: {emissions_path}")
ds = xr.open_dataset(project_root / emissions_path)

# List all variables in the dataset for reference
print("Available variables in dataset:", list(ds.variables.keys()))

# %% [markdown]
# ## Process data

# %%
print(f"Processing emissions data from {active_emissions_source}")
print(f"PRIMAP scenario: {scenario}")

# Dictionary to store all processed timeseries
all_timeseries = {}

for timeseries_name, spec in timeseries_specs.items():
    print(f"\n--- Processing {timeseries_name} ---")

    # Get the variable and categories for this timeseries
    variables = spec["column"]
    categories = spec["category"]

    print(f"Variables: {variables}")
    print(f"Categories: {categories}")

    # Initialize list to store data for this timeseries
    timeseries_data = []

    for variable in variables:
        for category in categories:
            print(f"  Processing variable: {variable}, category: {category}")

            try:
                # Select the specified variable and category from the dataset
                emissions = ds[variable]
                emissions_df = (
                    emissions.sel({"category (IPCC2006_PRIMAP)": category})
                    .to_dataframe()
                    .reset_index()
                )

                # Filter for the specified scenario
                emissions_df = emissions_df[
                    emissions_df["scenario (PRIMAP-hist)"] == scenario
                ]

                if len(emissions_df) == 0:
                    raise DataLoadingError(
                        f"No data found for variable '{variable}' and category "
                        f"'{category}' in scenario '{scenario}'"
                    )

                # Convert the time column to integer year
                emissions_df["year"] = emissions_df["time"].dt.year.astype(int)

                # Rename columns for clarity and filter the data
                emissions_df = emissions_df.rename(columns={"area (ISO3)": "iso3c"})
                emissions_df = emissions_df[(emissions_df["year"] >= 1850)]

                # Set up TimeseriesDataFrame format
                source_units = ds[variable].attrs.get("units")
                target_units = "Mt * CO2e"
                # Select only the columns we need for conversion
                emissions_df = emissions_df[["iso3c", "year", variable]].copy()
                # Set up DataFrame with unit in index
                emissions_df = emissions_df.set_index(["iso3c", "year"])
                emissions_df["unit"] = source_units
                emissions_df = emissions_df.set_index("unit", append=True)

                # Convert units
                target_units = "Mt * CO2e"
                # First ensure single unit, then convert
                emissions_df = set_single_unit(
                    df=emissions_df, unit_level="unit", ur=get_default_unit_registry()
                )
                converted_df = convert_unit_robust(
                    emissions_df,
                    target_units,
                    unit_level="unit",
                    ur=get_default_unit_registry(),
                )

                converted_df = converted_df.reset_index()
                converted_df = converted_df.rename(columns={variable: timeseries_name})
                timeseries_data.append(converted_df)

            except Exception as e:
                raise DataProcessingError(
                    f"Error processing {variable}, {category}: {e}"
                )

    # Group if we need multiple PRIMAP categories to create desired emission category
    combined_df = pd.concat(timeseries_data, ignore_index=True)
    combined_df = (
        combined_df.groupby(["iso3c", "year"])[timeseries_name].sum().reset_index()
    )

    # Convert to TimeseriesDataFrame format
    timeseries_wide = combined_df.pivot_table(
        index=["iso3c"], columns="year", values=timeseries_name, fill_value=None
    )

    # Enforce string year columns
    timeseries_wide = ensure_string_year_columns(timeseries_wide)

    # Convert to MultiIndex format with unit and emission category information
    # All data is now in Mt * CO2e
    timeseries_wide.index = pd.MultiIndex.from_tuples(
        [(iso3c, "Mt * CO2e", timeseries_name) for iso3c in timeseries_wide.index],
        names=["iso3c", "unit", "emission-category"],
    )

    all_timeseries[timeseries_name] = timeseries_wide
    print(f"  TimeseriesDataFrame shape: {timeseries_wide.shape}")

# %%
# [Optional if emission category is not 'all-ghg*']
if create_all_other and "all-ghg" in all_timeseries:
    # Generate "all-other" timeseries
    print("Creating 'all-other' timeseries (all-ghg minus requested emission category)")

    # Get the all-ghg timeseries
    all_ghg_df = all_timeseries["all-ghg"]

    # Get the timeseries that should be subtracted (the requested emission category)
    subtract_df = all_timeseries[emission_category]

    # Temporarily drop emission category from index for subtraction
    all_other_df = all_ghg_df.reset_index(level="emission-category", drop=True).copy()
    df_subtract = subtract_df.reset_index(level="emission-category", drop=True)

    # Ensure both dataframes have the same index structure (now just iso3c and unit)
    common_indices = all_other_df.index.intersection(df_subtract.index)
    all_other_df = all_other_df.loc[common_indices]
    df_subtract = df_subtract.loc[common_indices]

    # Subtract the values (handling NaN values)
    all_other_df = all_other_df.sub(df_subtract, fill_value=0)

    # Update the MultiIndex to reflect that this is 'all-other' data, not 'all-ghg'
    all_other_df = all_other_df.reset_index()
    all_other_df["emission-category"] = "all-other"
    all_other_df = all_other_df.set_index(["iso3c", "unit", "emission-category"])

    # Add to the timeseries dictionary
    all_timeseries["all-other"] = all_other_df
    print(f"Created 'all-other' timeseries with shape: {all_other_df.shape}")

    # Print summary statistics for all-other
    all_other_long = (
        all_other_df.reset_index(level=["unit", "emission-category"], drop=True)
        .stack()
        .reset_index()
    )
    all_other_long.columns = ["iso3c", "year", "all-other"]
    world_all_other = all_other_long[all_other_long["iso3c"] == world_key]

    if not world_all_other.empty:
        print("  World 'all-other' emissions summary:")
        print(
            f"    Latest value ({world_all_other['year'].max()}): {world_all_other['all-other'].iloc[-1]:.1f} Mt * CO2e"
        )
        print(f"    Peak value: {world_all_other['all-other'].max():.1f} Mt * CO2e")
else:
    if not create_all_other:
        print(
            "'all-other' timeseries not created: Processing logic indicates no 'all-other' needed (requested 'all-ghg*' categories)"
        )
    elif "all-ghg" not in all_timeseries:
        raise DataLoadingError(
            "Cannot create 'all-other' timeseries: 'all-ghg' timeseries is required but not present in the data"
        )

# %%
# Save only explicitly requested timeseries (plus 'all-other' if generated)
print("\n--- Saving TimeseriesDataFrames ---")

for timeseries_name, timeseries_df in all_timeseries.items():
    # Save originally requested timeseries and 'all-other' if it was created
    if timeseries_name in final_categories:
        timeseries_output_path = (
            intermediate_dir / f"emiss_{timeseries_name}_timeseries.csv"
        )
        # Ensure string year columns before saving
        timeseries_df = ensure_string_year_columns(timeseries_df)
        timeseries_df.reset_index().to_csv(timeseries_output_path, index=False)
        print(f"Saved {timeseries_name} to: {timeseries_output_path}")
    else:
        print(f"  Skipped saving {timeseries_name} (not explicitly requested)")

# %% [markdown]
# ## Plot World Emissions Data

# %%
# Create plots for each timeseries that was saved
print("\n--- Generating World Emissions Plots ---")

for timeseries_name, timeseries_df in all_timeseries.items():
    # Only plot timeseries saved (originally requested + 'all-other' if created)
    if timeseries_name not in final_categories:
        continue
    # Convert back to long format for plotting
    timeseries_long = (
        timeseries_df.reset_index(level=["unit", "emission-category"], drop=True)
        .stack()
        .reset_index()
    )
    timeseries_long.columns = ["iso3c", "year", timeseries_name]

    # Convert year column to integer for plotting
    timeseries_long["year"] = timeseries_long["year"].astype(int)

    # Get the units from the MultiIndex - get unique values only
    units = timeseries_df.index.get_level_values("unit").unique()[0]

    # Filter for world data using the world_key
    world_emissions = timeseries_long[timeseries_long["iso3c"] == world_key].copy()

    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 8))

    # Plot the emissions time series
    ax.plot(
        world_emissions["year"],
        world_emissions[timeseries_name],
        linewidth=2,
        color="steelblue",
        marker="o",
        markersize=3,
    )

    # Customize the plot with cleaner labels
    ax.set_title(
        f"processed: {timeseries_name}\n"
        f"from source: {active_emissions_source} ({scenario} scenario)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel(f"Emissions ({units})", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()

    # Show the plot
    plt.show()

    # Print summary statistics
    print(f"\n=== {timeseries_name} emissions summary ({world_key}) ===")
    print(
        f"Time period: {world_emissions['year'].min()} - {world_emissions['year'].max()}"
    )
    print(
        f"Peak emissions: {world_emissions[timeseries_name].max():.1f} {units} in {world_emissions.loc[world_emissions[timeseries_name].idxmax(), 'year']}"
    )
    print(
        f"Latest emissions ({world_emissions['year'].max()}): {world_emissions[timeseries_name].iloc[-1]:.1f} {units}"
    )
    print(f"Total countries in dataset: {timeseries_long['iso3c'].nunique()}")
    print(f"Unit conversion: PRIMAP units converted to {units} using AR6 GWP100 values")

print(f"\nEmissions data processing completed successfully for {scenario} scenario!")
print(f"Processed {len(all_timeseries)} timeseries: {list(all_timeseries.keys())}")

# %%
