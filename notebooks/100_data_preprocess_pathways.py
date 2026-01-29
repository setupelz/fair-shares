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
# # Master Data Preprocessing Script - Scenarios
#
# This script loads all processed historical emissions, GDP, population data, Gini data,
# and scenario-based future emissions from the 100-series notebooks. It then determines
# the set of analysis countries (iso3c) with data in all datasets over years 1990-2019,
# filters each dataset to these countries, computes and appends Rest of World (ROW)
# totals for missing countries and territories using the World aggregates, and saves the
# results as CSV. It also outputs a CSV of missing countries.

# %% [markdown]
# ## Set paths and library imports

# %%
# Imports
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.exceptions import (
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
    set_post_net_zero_emissions_to_nan,
)
from fair_shares.library.validation import (
    validate_all_datasets_totals,
    validate_emissions_data,
    validate_gdp_data,
    validate_gini_data,
    validate_population_data,
    validate_scenarios_data,
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

# Extract config values
emission_category = config["emission_category"]
emissions_data_parameters = config["emissions"][active_emissions_source][
    "data_parameters"
]

# Determine which historical emissions categories were processed
available_categories = emissions_data_parameters.get("available_categories")
processing_info = determine_processing_categories(
    emission_category, available_categories
)
final_categories = processing_info["final"]
emissions_world_key = emissions_data_parameters.get("world_key")

# Extract GDP parameters
gdp_data_parameters = config["gdp"][active_gdp_source]["data_parameters"]
active_gdp_variant = gdp_data_parameters.get("gdp_variant")
gdp_world_key = gdp_data_parameters.get("world_key")

# Extract population parameters
population_data_parameters = config["population"][active_population_source][
    "data_parameters"
]
active_population_projection = population_data_parameters.get("projected_variant")
population_historical_world_key = population_data_parameters.get("historical_world_key")
population_projected_world_key = population_data_parameters.get("projected_world_key")

# Get region mapping
region_mapping = pd.read_csv(project_root / config["general"]["region_mapping"]["path"])

# %%
# Construct source-specific intermediate dirs from active sources and data
emiss_intermediate_dir_str = f"output/{source_id}/intermediate/emissions"
gdp_intermediate_dir_str = f"output/{source_id}/intermediate/gdp"
pop_intermediate_dir_str = f"output/{source_id}/intermediate/population"
gini_intermediate_dir_str = f"output/{source_id}/intermediate/gini"
scenario_intermediate_dir_str = f"output/{source_id}/intermediate/scenarios"
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
scenario_intermediate_dir = project_root / scenario_intermediate_dir_str
root_intermediate_dir = project_root / root_intermediate_dir_str

emiss_intermediate_dir.mkdir(parents=True, exist_ok=True)
gdp_intermediate_dir.mkdir(parents=True, exist_ok=True)
pop_intermediate_dir.mkdir(parents=True, exist_ok=True)
gini_intermediate_dir.mkdir(parents=True, exist_ok=True)
scenario_intermediate_dir.mkdir(parents=True, exist_ok=True)
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

# Load scenarios data
# Note: For some targets like rcb-pathways, scenarios may only be available for the
# primary requested category, not for derived categories like "all-other"
scenarios_data = {}
for category in final_categories:
    scenarios_path = scenario_intermediate_dir / f"scenarios_{category}_timeseries.csv"
    if scenarios_path.exists():
        scenarios_df = pd.read_csv(scenarios_path)
        scenarios_df = scenarios_df.set_index(
            [
                "climate-assessment",
                "quantile",
                "source",
                "iso3c",
                "unit",
                "emission-category",
            ]
        )
        scenarios_df = ensure_string_year_columns(scenarios_df)
        scenarios_data[category] = scenarios_df
        print(f"  Loaded scenarios for {category}: {scenarios_path.name}")
    elif category == "all-other":
        # all-other is a derived category - scenarios may not exist for it
        print(
            f"  Skipping scenarios for {category} (derived category, no scenario file)"
        )
    else:
        # Primary categories should always have scenarios
        raise DataLoadingError(
            f"Scenarios file not found for category {category}: {scenarios_path}"
        )


# %% [markdown]
# ## Data validation

# %%
# Validate dataset structures
for category in final_categories:
    validate_emissions_data(emissions_data[category], f"Emissions ({category})")

validate_gdp_data(gdp, "GDP")
validate_population_data(population, "Population")
validate_gini_data(gini, "Gini")

# Validate scenarios that were actually loaded
for category in scenarios_data.keys():
    validate_scenarios_data(scenarios_data[category], f"Scenarios ({category})")

print("All datasets validated successfully")

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
    f"\nData coverage summary saved to: {
        root_intermediate_dir / 'processed' / 'country_data_coverage_summary.csv'
    }"
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
# ## Complete scenarios data processing

# %%
# Initialize dictionaries to store processing stages for plotting and final output
all_complete_scenarios = {}
all_world_historical = {}
all_harmonized_post_net_zero_nan = {}
net_negative_metadata_dict = {}  # Store metadata about net-negative emissions handling

# Process each emission category to create complete scenarios
# Note: Only process scenarios that were actually loaded (e.g., rcb-pathways may only have primary category)
for emission_category in scenarios_data.keys():
    if emission_category not in scenarios_data:
        raise DataProcessingError(
            f"Scenarios data for emission category '{emission_category}' not found in "
            f"loaded scenarios. Available categories: {list(scenarios_data.keys())}"
        )

    category_scenarios = scenarios_data[emission_category]
    scenario_groups = category_scenarios.index.get_level_values(
        "climate-assessment"
    ).unique()
    scenario_quantiles = category_scenarios.index.get_level_values("quantile").unique()

    # Use computed and validated historical emissions data
    category_emiss_complete_with_row = emiss_complete[emission_category]
    world_historical_emissions = category_emiss_complete_with_row.sum(axis=0)
    world_historical_df = pd.DataFrame([world_historical_emissions], index=["World"])
    world_historical_df.index.name = "iso3c"
    all_world_historical[emission_category] = world_historical_df

    # Combine historical and scenario data
    historical_years = [
        col for col in world_historical_df.columns if str(col).isdigit()
    ]
    scenario_years = [col for col in category_scenarios.columns if str(col).isdigit()]

    # Prepare world scenario time series
    world_mask_all = (category_scenarios.index.get_level_values("iso3c") == "World") & (
        category_scenarios.index.get_level_values("unit") == "Mt * CO2e"
    )
    world_scenarios_only = category_scenarios[world_mask_all]

    # Scenarios are already harmonized and aggregated to median in AR6 notebook
    year_cols = [col for col in world_scenarios_only.columns if str(col).isdigit()]
    years = [int(col) for col in year_cols]

    # Convert to long format for net-negative handling
    # Source is now a standard index level for all scenario types (ar6, cr, rcb-pathways)
    # Reset index first to get all columns
    df_reset = world_scenarios_only.reset_index()

    # Determine id_cols based on actual columns (excluding year columns)
    year_cols_in_df = [col for col in df_reset.columns if str(col).isdigit()]
    id_cols = [col for col in df_reset.columns if col not in year_cols_in_df]

    harmonized_long = df_reset.melt(
        id_vars=id_cols, var_name="year", value_name=emission_category
    )
    harmonized_long["year"] = harmonized_long["year"].astype(int)

    # Apply net-negative emissions handling to median pathway
    # Pre-net-zero: pathway stays unchanged (allow gross negative emissions)
    # Post-net-zero: set to NaN with warnings
    adjusted_groups = []
    all_metadata = []

    # Process each climate-assessment separately
    for climate_assessment in scenario_groups:
        median_df = harmonized_long[
            harmonized_long["climate-assessment"] == climate_assessment
        ].copy()

        adjusted_df, metadata = set_post_net_zero_emissions_to_nan(
            median_df, emission_category
        )
        adjusted_groups.append(adjusted_df)
        all_metadata.append({"climate-assessment": climate_assessment, **metadata})

    harmonized_adjusted = pd.concat(adjusted_groups, ignore_index=True)
    net_negative_metadata = {"pathways": all_metadata}

    # Store metadata for later use (one entry per climate-assessment)
    net_negative_metadata_dict[emission_category] = net_negative_metadata

    # Convert back to wide format
    # Use fill_value=np.nan to preserve NaN values from set_post_net_zero_emissions_to_nan
    # Source is now a standard index level for all scenario types
    harmonized_world = harmonized_adjusted.pivot_table(
        index=[
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ],
        columns="year",
        values=emission_category,
        fill_value=np.nan,
    )
    harmonized_world.columns = harmonized_world.columns.astype(str)

    # Save harmonized + post-net-zero set to NaN data for plotting
    all_harmonized_post_net_zero_nan[emission_category] = harmonized_world.copy()

    # Create complete scenarios by combining historical and harmonized data
    # Process ALL scenarios (all climate-assessments, quantiles, and sources)
    # Source is now a standard index level for all scenario types
    complete_scenarios = []

    # Filter to World scenarios only
    world_mask = (category_scenarios.index.get_level_values("iso3c") == "World") & (
        category_scenarios.index.get_level_values("unit") == "Mt * CO2e"
    )
    world_scenarios = category_scenarios[world_mask]

    # Iterate over all scenario rows
    for idx, row in world_scenarios.iterrows():
        climate_assessment = idx[0]
        quantile = idx[1]
        source = idx[2]
        scenario_series = row

        # Get all years from both datasets
        historical_years = [
            col for col in world_historical_df.columns if str(col).isdigit()
        ]
        scenario_years_available = [
            col
            for col in scenario_series.index
            if str(col).isdigit() and not pd.isna(scenario_series[col])
        ]

        # Create complete year range from historical start to scenario end
        all_years = sorted(set(historical_years + scenario_years_available))
        complete_years = [str(year) for year in all_years]

        # Create a new series with the complete year range
        complete_series = pd.Series(index=complete_years, dtype=float)

        # Fill with historical data where available
        for year in historical_years:
            if year in world_historical_df.iloc[0].index:
                complete_series[year] = world_historical_df.iloc[0][year]

        # Override with harmonized scenario data where available
        key = (
            climate_assessment,
            quantile,
            source,
            "World",
            "Mt * CO2e",
            emission_category,
        )

        for year in scenario_years_available:
            if year in harmonized_world.columns and key in harmonized_world.index:
                complete_series[year] = harmonized_world.loc[key, year]

        # Create DataFrame with standard index structure (including source)
        complete_df = pd.DataFrame(
            [complete_series],
            index=pd.MultiIndex.from_tuples(
                [key],
                names=[
                    "climate-assessment",
                    "quantile",
                    "source",
                    "iso3c",
                    "unit",
                    "emission-category",
                ],
            ),
        )
        complete_scenarios.append(complete_df)

    # Combine all complete scenarios for this emission category
    if complete_scenarios:
        complete_scenarios_df = pd.concat(complete_scenarios)
        all_complete_scenarios[emission_category] = complete_scenarios_df
    else:
        raise DataProcessingError(
            f"No complete scenarios created for {emission_category}"
        )

# %% [markdown]
# ## Plots

# %%
# Create plots for each emission category showing the final median pathways
# Note: Only plot scenarios that were actually loaded
for emission_category in all_harmonized_post_net_zero_nan.keys():
    scenarios_df = all_harmonized_post_net_zero_nan[emission_category]
    world_historical_df = all_world_historical[emission_category]

    climate_assessments = scenarios_df.index.get_level_values(
        "climate-assessment"
    ).unique()
    year_cols = [col for col in scenarios_df.columns if str(col).isdigit()]
    years = [int(col) for col in year_cols]

    palette = dict(
        zip(
            climate_assessments,
            plt.cm.tab10(np.linspace(0, 1, len(climate_assessments))),
        )
    )

    # Plot 1: Annual emissions
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    hist_vals = [world_historical_df.iloc[0].get(str(y), float("nan")) for y in years]
    ax.plot(years, hist_vals, "k-", linewidth=3, label="Historical (World)", alpha=0.8)

    # Get unique sources for line styles
    sources = sorted(scenarios_df.index.get_level_values("source").unique())
    linestyles = ["-", "--", "-.", ":"]

    for ca in climate_assessments:
        for i, source in enumerate(sources):
            # Get all quantiles for this climate-assessment and source combination
            mask = (scenarios_df.index.get_level_values("climate-assessment") == ca) & (
                scenarios_df.index.get_level_values("source") == source
            )
            quantiles = sorted(
                scenarios_df[mask].index.get_level_values("quantile").unique()
            )
            for quantile in quantiles:
                quantile_mask = mask & (
                    scenarios_df.index.get_level_values("quantile") == quantile
                )
                if quantile_mask.any():
                    data = scenarios_df[quantile_mask].iloc[0]
                    vals = [data.get(str(y), float("nan")) for y in years]
                    linestyle = linestyles[i % len(linestyles)]
                    ax.plot(
                        years,
                        vals,
                        linestyle,
                        color=palette[ca],
                        alpha=0.7,
                        linewidth=1.5,
                        label=f"{ca} - {source} (q={quantile})",
                    )

    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel("Emissions (Mt * CO2e)", fontsize=12)
    ax.set_title(
        f"{emission_category.replace('-', ' ').title()} Emissions: "
        f"Final Median Pathways",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.show()

    # Plot 2: Cumulative emissions
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    hist_cumulative = np.cumsum(hist_vals)
    ax.plot(
        years, hist_cumulative, "k-", linewidth=3, label="Historical (World)", alpha=0.8
    )

    for ca in climate_assessments:
        for i, source in enumerate(sources):
            # Get all quantiles for this climate-assessment and source combination
            mask = (scenarios_df.index.get_level_values("climate-assessment") == ca) & (
                scenarios_df.index.get_level_values("source") == source
            )
            quantiles = sorted(
                scenarios_df[mask].index.get_level_values("quantile").unique()
            )
            for quantile in quantiles:
                quantile_mask = mask & (
                    scenarios_df.index.get_level_values("quantile") == quantile
                )
                if quantile_mask.any():
                    data = scenarios_df[quantile_mask].iloc[0]
                    vals = [data.get(str(y), float("nan")) for y in years]
                    linestyle = linestyles[i % len(linestyles)]
                    ax.plot(
                        years,
                        np.cumsum(vals),
                        linestyle,
                        color=palette[ca],
                        alpha=0.7,
                        linewidth=1.5,
                        label=f"{ca} - {source} (q={quantile})",
                    )

    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel("Cumulative Emissions (Mt * CO2e)", fontsize=12)
    ax.set_title(
        f"{emission_category.replace('-', ' ').title()} Cumulative Emissions: "
        f"Final Median Pathways",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ## Save complete datasets

# %%
# Save all complete scenarios datasets
for emission_category, complete_scenarios_df in all_complete_scenarios.items():
    output_path = (
        processed_intermediate_dir / f"world_scenarios_{emission_category}_complete.csv"
    )
    complete_scenarios_df = ensure_string_year_columns(complete_scenarios_df)
    complete_scenarios_df.reset_index().to_csv(output_path, index=False)

# Save net-negative emissions metadata
if net_negative_metadata_dict:
    # Convert numpy types to native Python types for YAML serialization
    def convert_to_native_types(obj):
        """Recursively convert numpy types to native Python types."""
        if isinstance(obj, dict):
            return {k: convert_to_native_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native_types(item) for item in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj

    metadata_to_save = convert_to_native_types(net_negative_metadata_dict)
    metadata_output_path = (
        processed_intermediate_dir / "net_negative_emissions_metadata.yaml"
    )
    with open(metadata_output_path, "w") as f:
        yaml.dump(metadata_to_save, f, default_flow_style=False)
    print(f"\nSaved net-negative emissions metadata to: {metadata_output_path}")
