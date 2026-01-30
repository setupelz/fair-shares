# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags,title,-all
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
# # Master Data Preprocessing Script - target = 'rcbs'
#
# This script loads all processed historical emissions, GDP, population data, Gini data,
# and RCB-based future emissions from the 100-series notebooks. It then determines
# the set of analysis countries (iso3c) with data in all datasets over years 1990-2019,
# filters each dataset to these countries, computes and appends Rest of World (ROW)
# totals for missing countries and territories using the World aggregates, and saves the
# results as CSV. It also outputs a CSV of missing countries.
#
# Remaining Carbon Budget (RCB) data is processed from a YAML config in /data/rcbs.yaml
# RCB are processed to 2020 baseline and adjusted for bunkers and LULUCF emissions. This
# returns budgets in Mt * CO2 from 2020 onwards, in terms of CO2-FFI emissions (or
# all CO2 emissions excluding LULUCF and bunkers).

# %% [markdown]
# ## Set paths and library imports

# %%
# Imports
import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.exceptions import (
    ConfigurationError,
    DataLoadingError,
    DataProcessingError,
)
from fair_shares.library.utils import (
    add_row_timeseries,
    build_source_id,
    determine_processing_categories,
    ensure_string_year_columns,
    get_complete_iso3c_timeseries,
    get_world_totals_timeseries,
    process_rcb_to_2020_baseline,
)
from fair_shares.library.validation import (
    validate_all_datasets_totals,
    validate_emissions_data,
    validate_gdp_data,
    validate_gini_data,
    validate_population_data,
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
    emission_category = "co2-ffi"  # RCBs only support co2-ffi
    active_sources = {
        "emissions": "primap-202503",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "unu-wider-2025",
        "target": "rcbs",  # RCB mode
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

# Extract config values
emission_category = config["emission_category"]
emissions_data_parameters = config["emissions"][active_emissions_source][
    "data_parameters"
]

available_categories = emissions_data_parameters.get("available_categories")
emissions_world_key = emissions_data_parameters.get("world_key")
emissions_scenario = emissions_data_parameters.get("scenario")

# Determine which categories to process
processing_info = determine_processing_categories(
    emission_category, available_categories
)
final_categories = processing_info["final"]

print(f"Final emission categories: {final_categories}")

# RCBs are only available when the emission category is "co2-ffi"
if emission_category != "co2-ffi":
    raise ConfigurationError(
        f"RCB-based budget allocations only support 'co2-ffi' emission category. "
        f"Got: {emission_category}. Please use target: 'ar6' or 'cr'"
        f" in your configuration for other emission categories."
    )

print(f"Emission category validated: {emission_category} (compatible with RCBs)")

# Extract GDP parameters
gdp_data_parameters = config["gdp"][active_gdp_source]["data_parameters"]
population_data_parameters = config["population"][active_population_source][
    "data_parameters"
]
region_mapping_path = config["general"]["region_mapping"]["path"]
rcb_config = config["targets"]["rcbs"]

active_gdp_variant = gdp_data_parameters.get("gdp_variant")
gdp_world_key = gdp_data_parameters.get("world_key")

# Extract population parameters
active_population_projection = population_data_parameters.get("projected_variant")
population_historical_world_key = population_data_parameters.get("historical_world_key")
population_projected_world_key = population_data_parameters.get("projected_world_key")
rcb_yaml_path = project_root / rcb_config.get("path")

# Get RCB adjustment parameters (bunkers and LULUCF emissions)
rcb_data_parameters = rcb_config.get("data_parameters", {})
rcb_adjustments = rcb_data_parameters.get("adjustments", {})
bunkers_2020_2100 = rcb_adjustments.get("bunkers_2020_2100")
lulucf_2020_2100 = rcb_adjustments.get("lulucf_2020_2100")

print("RCB adjustments:")
print(f"  Bunkers (2020-2100): {bunkers_2020_2100} Mt CO2")
print(f"  LULUCF (2020-2100): {lulucf_2020_2100} Mt CO2")

# %%
# Construct source-specific intermediate dirs from active sources and data
emiss_intermediate_dir_str = f"output/{source_id}/intermediate/emissions"
gdp_intermediate_dir_str = f"output/{source_id}/intermediate/gdp"
pop_intermediate_dir_str = f"output/{source_id}/intermediate/population"
gini_intermediate_dir_str = f"output/{source_id}/intermediate/gini"
root_intermediate_dir_str = f"output/{source_id}/intermediate"

# Create output processed intermediate directory
processed_intermediate_dir_str = f"output/{source_id}/intermediate/processed"
processed_intermediate_dir = project_root / processed_intermediate_dir_str
processed_intermediate_dir.mkdir(parents=True, exist_ok=True)

# Ensure all intermediate_dirs are Path objects and exist
emiss_intermediate_dir = project_root / emiss_intermediate_dir_str
gdp_intermediate_dir = project_root / gdp_intermediate_dir_str
pop_intermediate_dir = project_root / pop_intermediate_dir_str
gini_intermediate_dir = project_root / gini_intermediate_dir_str
root_intermediate_dir = project_root / root_intermediate_dir_str

emiss_intermediate_dir.mkdir(parents=True, exist_ok=True)
gdp_intermediate_dir.mkdir(parents=True, exist_ok=True)
pop_intermediate_dir.mkdir(parents=True, exist_ok=True)
gini_intermediate_dir.mkdir(parents=True, exist_ok=True)
root_intermediate_dir.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Load data

# %%
# Load emission data
emissions_data = {}
for category in final_categories:
    emiss_path = emiss_intermediate_dir / f"emiss_{category}_timeseries.csv"
    if emiss_path.exists():
        emiss_df = pd.read_csv(emiss_path)
        emiss_df = emiss_df.set_index(["iso3c", "unit", "emission-category"])
        emiss_df = ensure_string_year_columns(emiss_df)
        emissions_data[category] = emiss_df
    else:
        raise DataLoadingError(
            f"Emissions file not found for requested category {category}: {emiss_path}"
        )

# Load GDP data
gdp_path = gdp_intermediate_dir / "gdp_timeseries.csv"
if not gdp_path.exists():
    raise DataLoadingError(
        f"GDP file not found: {gdp_path}. "
        "Ensure the GDP preprocessing notebook has been run successfully."
    )
gdp = pd.read_csv(gdp_path)
gdp = gdp.set_index(["iso3c", "unit"])
gdp = ensure_string_year_columns(gdp)
gdp_variant = gdp_data_parameters.get("gdp_variant")
gdp_world_key = gdp_data_parameters.get("world_key")

# Load population data
population_path = pop_intermediate_dir / "population_timeseries.csv"
if not population_path.exists():
    raise DataLoadingError(
        f"Population file not found: {population_path}. "
        "Ensure the population preprocessing notebook has been run successfully."
    )
population = pd.read_csv(population_path)
population = population.set_index(["iso3c", "unit"])
population = ensure_string_year_columns(population)
population_variant = population_data_parameters.get("population_variant")

# Load Gini data
gini_path = gini_intermediate_dir / "gini_stationary.csv"
if not gini_path.exists():
    raise DataLoadingError(
        f"Gini file not found: {gini_path}. "
        "Ensure the Gini preprocessing notebook has been run successfully."
    )
gini = pd.read_csv(gini_path)
gini = gini.set_index(["iso3c", "unit"])

# %% [markdown]
# ## Data validation

# %%
# Validate dataset structures
for category in final_categories:
    validate_emissions_data(emissions_data[category], f"Emissions ({category})")
validate_gdp_data(gdp, "GDP")
validate_population_data(population, "Population")
validate_gini_data(gini, "Gini")

# %% [markdown]
# ## Data coverage completion (Rest Of World additions)

# %%
# Get world totals for each dataset
world_emiss = {}
for category in final_categories:
    if category in emissions_data:
        world_emiss[category] = get_world_totals_timeseries(
            emissions_data[category],
            emissions_world_key,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )

world_gdp = get_world_totals_timeseries(
    gdp, gdp_world_key, expected_index_names=["iso3c", "unit"]
)

world_population = get_world_totals_timeseries(
    population, population_historical_world_key, expected_index_names=["iso3c", "unit"]
)

# %%
# Get countries with complete data over desired period
emiss_analysis_countries = {}
for category in final_categories:
    if category in emissions_data:
        emiss_analysis_countries[category] = get_complete_iso3c_timeseries(
            emissions_data[category],
            expected_index_names=["iso3c", "unit", "emission-category"],
            start=1990,
            end=2019,
        )

gdp_analysis_countries = get_complete_iso3c_timeseries(
    gdp, expected_index_names=["iso3c", "unit"], start=1990, end=2023
)
population_analysis_countries = get_complete_iso3c_timeseries(
    population, expected_index_names=["iso3c", "unit"], start=1990, end=2019
)
gini_analysis_countries = set(gini.index.get_level_values("iso3c").tolist())

# Find intersection of all datasets
analysis_countries = (
    gdp_analysis_countries & population_analysis_countries & gini_analysis_countries
)

for category in final_categories:
    if category in emiss_analysis_countries:
        analysis_countries = analysis_countries & emiss_analysis_countries[category]

# %% [markdown]
# ## Create data coverage summary

# %%
# Load region mapping to get the full list of countries
region_mapping = pd.read_csv(project_root / region_mapping_path)
all_region_countries = set(region_mapping["iso3c"].unique())

# Create summary dataframe
coverage_summary = pd.DataFrame({"iso3c": sorted(all_region_countries)})

# Add coverage indicators for each dataset
coverage_summary["has_emissions"] = True
for category in final_categories:
    if category in emiss_analysis_countries:
        coverage_summary["has_emissions"] = coverage_summary[
            "has_emissions"
        ] & coverage_summary["iso3c"].isin(emiss_analysis_countries[category])

coverage_summary["has_gdp"] = coverage_summary["iso3c"].isin(gdp_analysis_countries)
coverage_summary["has_population"] = coverage_summary["iso3c"].isin(
    population_analysis_countries
)
coverage_summary["has_gini"] = coverage_summary["iso3c"].isin(gini_analysis_countries)

# Add final analysis indicator
coverage_summary["in_analysis"] = coverage_summary["iso3c"].isin(analysis_countries)

# Add ROW indicator (countries that are in region mapping but not in final analysis)
coverage_summary["in_row"] = coverage_summary["iso3c"].isin(
    all_region_countries
) & ~coverage_summary["iso3c"].isin(analysis_countries)

# Calculate summary statistics
total_countries = len(coverage_summary)
countries_with_emissions = coverage_summary["has_emissions"].sum()
countries_with_gdp = coverage_summary["has_gdp"].sum()
countries_with_population = coverage_summary["has_population"].sum()
countries_with_gini = coverage_summary["has_gini"].sum()
countries_in_analysis = coverage_summary["in_analysis"].sum()
countries_in_row = coverage_summary["in_row"].sum()

print("\n=== Data Coverage Summary ===")
print(f"Total countries in region mapping: {total_countries}")
print(
    f"Countries with emissions data: {countries_with_emissions} "
    f"({countries_with_emissions / total_countries * 100:.1f}%)"
)
print(
    f"Countries with GDP data ({gdp_variant}): {countries_with_gdp} "
    f"({countries_with_gdp / total_countries * 100:.1f}%)"
)
print(
    f"Countries with population data: {countries_with_population} "
    f"({countries_with_population / total_countries * 100:.1f}%)"
)
print(
    f"Countries with Gini data: {countries_with_gini} "
    f"({countries_with_gini / total_countries * 100:.1f}%)"
)

print("\n=== Countries composition in final dataset ===")
print(
    f"Countries independently complete in final dataset: {countries_in_analysis} "
    f"({countries_in_analysis / total_countries * 100:.1f}%)"
)
print(
    f"Countries clubbed in ROW in final dataset: {countries_in_row} "
    f"({countries_in_row / total_countries * 100:.1f}%)"
)

# Show countries that are in ROW
row_countries = coverage_summary[coverage_summary["in_row"]]["iso3c"].tolist()
print(f"\nCountries in ROW: {sorted(row_countries)}")

# Show countries missing from each dataset
missing_emissions = coverage_summary[~coverage_summary["has_emissions"]][
    "iso3c"
].tolist()
missing_gdp = coverage_summary[~coverage_summary["has_gdp"]]["iso3c"].tolist()
missing_population = coverage_summary[~coverage_summary["has_population"]][
    "iso3c"
].tolist()
missing_gini = coverage_summary[~coverage_summary["has_gini"]]["iso3c"].tolist()

print(f"\nCountries missing emissions data: {sorted(missing_emissions)}")
print(f"Countries missing GDP data ({gdp_variant}): {sorted(missing_gdp)}")
print(f"Countries missing population data: {sorted(missing_population)}")
print(f"Countries missing Gini data: {sorted(missing_gini)}")

# Save the coverage summary
coverage_summary.to_csv(
    root_intermediate_dir / "processed" / "country_data_coverage_summary.csv",
    index=False,
)
print(
    f"\nData coverage summary saved to: {root_intermediate_dir / 'processed' / 'country_data_coverage_summary.csv'}"
)

# %% [markdown]
# ## Create analysis datasets with ROW added

# %%
# Add ROW (Rest Of World) to each dataset
emiss_complete = {}
for category in final_categories:
    if category in emissions_data and category in world_emiss:
        emiss_complete[category] = add_row_timeseries(
            emissions_data[category],
            analysis_countries,
            world_emiss[category],
            expected_index_names=["iso3c", "unit", "emission-category"],
        )

gdp_complete = add_row_timeseries(
    gdp, analysis_countries, world_gdp, expected_index_names=["iso3c", "unit"]
)
population_complete = add_row_timeseries(
    population,
    analysis_countries,
    world_population,
    expected_index_names=["iso3c", "unit"],
)

gini_analysis = gini[
    gini.index.get_level_values("iso3c").isin(analysis_countries)
].copy()

if gini_analysis.empty:
    raise DataProcessingError(
        "No Gini coefficient data found for analysis countries. "
        "Cannot calculate ROW average without data."
    )

gini_analysis_average = gini_analysis["gini"].mean()
gini_row = pd.DataFrame(
    {"gini": [gini_analysis_average]},
    index=pd.MultiIndex.from_tuples([("ROW", "unitless")], names=["iso3c", "unit"]),
)
gini_complete = pd.concat([gini_analysis, gini_row])

# %% [markdown]
# ## Validation of analysis datasets

# %%
# GDP and population datasets
analysis_datasets = {"GDP": gdp_complete, "Population": population_complete}
world_totals = {"GDP": world_gdp, "Population": world_population}

# Emissions datasets
for category in final_categories:
    if category in emiss_complete and category in world_emiss:
        analysis_datasets[f"Emissions ({category})"] = emiss_complete[category]
        world_totals[f"Emissions ({category})"] = world_emiss[category]

# Validate all
validation_results = validate_all_datasets_totals(analysis_datasets, world_totals)

if not validation_results or not all(validation_results.values()):
    failed_datasets = [
        name for name, success in validation_results.items() if not success
    ]
    raise DataProcessingError(
        f"Validation failed for datasets: {failed_datasets}. "
        "See logs above for details."
    )

# Save the analysis datasets
for category, category_emiss_complete in emiss_complete.items():
    emiss_output_path = (
        processed_intermediate_dir / f"country_emissions_{category}_timeseries.csv"
    )
    category_emiss_complete = ensure_string_year_columns(category_emiss_complete)
    category_emiss_complete.reset_index().to_csv(emiss_output_path, index=False)

gdp_output_path = processed_intermediate_dir / "country_gdp_timeseries.csv"
gdp_complete = ensure_string_year_columns(gdp_complete)
gdp_complete.reset_index().to_csv(gdp_output_path, index=False)

pop_output_path = processed_intermediate_dir / "country_population_timeseries.csv"
population_complete = ensure_string_year_columns(population_complete)
population_complete.reset_index().to_csv(pop_output_path, index=False)

gini_output_path = processed_intermediate_dir / "country_gini_stationary.csv"
gini_complete.reset_index().to_csv(gini_output_path, index=False)

# %% [markdown]
# ## Save world emissions (historical only)

# %%
# Save world emissions for each category
for category in final_categories:
    if category in world_emiss:
        world_output_path = (
            processed_intermediate_dir / f"world_emissions_{category}_timeseries.csv"
        )
        world_category_data = world_emiss[category]
        world_values = world_category_data.reset_index(drop=True)
        world_category_df = world_values.copy()
        world_category_df.index = pd.MultiIndex.from_tuples(
            [("World", unit, cat) for _, unit, cat in world_emiss[category].index],
            names=["iso3c", "unit", "emission-category"],
        )
        world_category_df = ensure_string_year_columns(world_category_df)
        world_category_df.reset_index().to_csv(world_output_path, index=False)
        print(f"  Saved world emissions ({category}): {world_output_path}")

print("World emissions (historical) saved")

# %% [markdown]
# ## Load and process RCB data

# %%
# Load the RCB YAML data
if not rcb_yaml_path.exists():
    raise DataLoadingError(f"RCB YAML file not found: {rcb_yaml_path}")

with open(rcb_yaml_path) as file:
    rcb_data = yaml.safe_load(file)

print("Loaded RCB data structure:")
print(f"  Sources: {list(rcb_data['rcb_data'].keys())}")
if rcb_data["rcb_data"]:
    first_source = next(iter(rcb_data["rcb_data"].keys()))
    first_data = rcb_data["rcb_data"][first_source]
    print(f"  Example source ({first_source}):")
    print(f"    Baseline year: {first_data.get('baseline_year')}")
    print(f"    Unit: {first_data.get('unit')}")
    print(f"    Scenarios: {list(first_data.get('scenarios', {}).keys())}")

# %% [markdown]
# ## Process RCB data to 2020 baseline

# %%
# Get world emissions timeseries for RCB processing
world_emissions_df = world_emiss[emission_category]
world_emissions_df = ensure_string_year_columns(world_emissions_df)

print("\nProcessing RCBs with adjustments:")
print("  Target baseline year: 2020")
print(f"  Bunkers adjustment: {bunkers_2020_2100} Mt CO2e")
print(f"  LULUCF adjustment: {lulucf_2020_2100} Mt CO2e")

# Create a list to store all RCB records
rcb_records = []

# Process each source
for source_key, source_data in rcb_data["rcb_data"].items():
    print(f"\n  Processing source: {source_key}")

    # Extract metadata from source
    baseline_year = source_data.get("baseline_year")
    unit = source_data.get("unit", "Gt CO2")
    scenarios = source_data.get("scenarios", {})

    # Validate required fields
    if baseline_year is None:
        raise ConfigurationError(
            f"RCB source '{source_key}' missing required field 'baseline_year'"
        )
    if not scenarios:
        raise ConfigurationError(f"RCB source '{source_key}' has no scenarios defined")

    print(f"    Baseline year: {baseline_year}")
    print(f"    Unit: {unit}")
    print(f"    Scenarios: {len(scenarios)}")

    # Process each scenario for this source
    for scenario, rcb_value in scenarios.items():
        # Parse scenario string into climate assessment and quantile
        # Format: "TEMPpPROB" (e.g., "1.5p50" -> 1.5C warming, 50% probability)
        parts = scenario.split("p")
        if len(parts) == 2:
            temperature = parts[0]
            probability = parts[1]
            climate_assessment = f"{temperature}C"
            quantile = str(int(probability) / 100)
        else:
            raise ValueError(f"Invalid RCB scenario format: {scenario}")

        # Process RCB to 2020 baseline
        result = process_rcb_to_2020_baseline(
            rcb_value=rcb_value,
            rcb_unit=unit,
            rcb_baseline_year=baseline_year,
            world_co2_ffi_emissions=world_emissions_df,
            bunkers_2020_2100=bunkers_2020_2100,
            lulucf_2020_2100=lulucf_2020_2100,
            target_baseline_year=2020,
            source_name=source_key,
            scenario=scenario,
            verbose=True,
        )

        # Create record with parsed climate assessment and quantile
        record = {
            "source": source_key,
            "scenario": scenario,
            "climate-assessment": climate_assessment,
            "quantile": quantile,
            "emission-category": emission_category,
            "baseline_year": baseline_year,
            "rcb_original_value": result["rcb_original_value"],
            "rcb_original_unit": result["rcb_original_unit"],
            "rcb_2020_mt": result["rcb_2020_mt"],
            "emissions_adjustment_mt": result["emissions_adjustment_mt"],
            "bunkers_adjustment_mt": result["bunkers_adjustment_mt"],
            "lulucf_adjustment_mt": result["lulucf_adjustment_mt"],
            "total_adjustment_mt": result["total_adjustment_mt"],
        }

        rcb_records.append(record)

# %% [markdown]
# ## Save processed RCB data

# %%
# Convert to DataFrame
rcb_df = pd.DataFrame(rcb_records)

# Display the processed data
print("\nProcessed RCB data:")
print(rcb_df.to_string(index=False))

# Save to processed intermediate directory
rcb_output_path = processed_intermediate_dir / "rcbs.csv"
rcb_df.to_csv(rcb_output_path, index=False)

print(f"\nSaved processed RCB data to: {rcb_output_path}")
