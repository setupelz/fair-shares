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
# # Fair Shares Allocation Analysis
#
# **Your main workspace for allocating carbon budgets or emission pathways among countries.**
#
# This notebook translates climate equity principles into quantitative allocations.
# Start with principles, not parameters. Any allocation involves ethical choices—
# this workflow helps make those choices explicit.
#
# **Before configuring, read:**
#
# - [From Principle to Code]({DOCS_ROOT}/science/principle-to-code/) - Principles-first workflow
# - [Climate Equity Concepts]({DOCS_ROOT}/science/climate-equity-concepts/) - Foundational concepts
#
# **Pre-configured examples:**
#
# - `302_example_templates_budget_allocations.py` - Budget templates
# - `303_example_templates_pathway_allocations.py` - Pathway templates
#
# **Workflow:**
# 1. Configure Data
# 2. Define Approaches
# 3. Run Pipeline
# 4. Run Allocations
# 5. Explore Results

# %%
# Imports (run this first)
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from pyprojroot import here
from tqdm.auto import tqdm

# Import fair-shares library components
from fair_shares.library.allocations import AllocationManager
from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.exceptions import (
    ConfigurationError,
    DataProcessingError,
)
from fair_shares.library.utils import (
    calculate_budget_from_rcb,
    convert_parquet_to_wide_csv,
    ensure_string_year_columns,
    get_compatible_approaches,
    get_cumulative_budget_from_timeseries,
    get_world_totals_timeseries,
    setup_custom_data_pipeline,
    validate_data_source_config,
)
from fair_shares.library.validation import (
    validate_has_year_columns,
    validate_index_structure,
    validate_stationary_dataframe,
)

# Set matplotlib style
plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()

# %% [markdown]
# ---
# ## Quick Start
#
# Principle-based options - Each operationalizes different equity values:
#
# - **Option A**: Egalitarianism (equal rights)
# - **Option B**: CBDR-RC (historical responsibility + capability)
#
# Uncomment ONE option, run cell, skip to Step 3.
#
# See [From Principle to Code]({DOCS_ROOT}/science/principle-to-code/) for principle-approach mapping.

# %%
# =============================================================================
# OPTION A: Egalitarianism
# =============================================================================
# Principle: Egalitarianism (equal per capita entitlement)
# See: docs/science/climate-equity-concepts.md
#
# emission_category = "co2-ffi"
# active_sources = {
#     "target": "rcbs",
#     "emissions": "primap-202503",
#     "gdp": "wdi-2025",
#     "population": "un-owid-2025",
#     "gini": "unu-wider-2025",
# }
# allocation_folder = "quick_start_egalitarian"
# allocations = {
#     "equal-per-capita-budget": [
#         {"allocation_year": [2020], "preserve_allocation_year_shares": [False]}
#     ]
# }
# print("Option A configured: Egalitarianism")

# %%
# =============================================================================
# OPTION B: CBDR-RC
# =============================================================================
# Principle: Historical responsibility + capability
# See: docs/science/climate-equity-concepts.md
#
# emission_category = "co2-ffi"
# active_sources = {
#     "target": "rcbs",
#     "emissions": "primap-202503",
#     "gdp": "wdi-2025",
#     "population": "un-owid-2025",
#     "gini": "unu-wider-2025",
# }
# allocation_folder = "quick_start_cbdr_rc"
# allocations = {
#     "per-capita-adjusted-budget": [
#         {
#             "allocation_year": [2020],
#             "preserve_allocation_year_shares": [False],
#             "responsibility_weight": [0.5],
#             "capability_weight": [0.5],
#         }
#     ]
# }
# print("Option B configured: CBDR-RC (equal weighting)")

# %% [markdown]
# ---
# **Note:** Used Quick Start above? Skip to Step 3. Otherwise, continue for full control.

# %% [markdown]
# ---
# ## Step 1: Configure Data Sources
#
# Select datasets that inform allocation calculations:
# - **Emissions**: Historical emissions by country
# - **Population**: For per capita calculations
# - **GDP**: For capability-based adjustments
# - **Gini**: Within-country inequality measures
# - **Target**: The global constraint being allocated
#
# **Emission categories:**
# - `co2-ffi` - CO2 from fossil fuels and industry (recommended)
# - `all-ghg-ex-co2-lulucf` - All GHGs excluding land use CO2
# - `all-ghg` - All greenhouse gases including land use
#
# **Target types:**
# - `rcbs` - Remaining Carbon Budgets (cumulative, single-year)
# - `ar6` - IPCC AR6 scenarios (time-series pathways)
#
# [Full guide]({DOCS_ROOT}/user-guide/country-fair-shares/)

# %%
# CONFIGURE YOUR DATA SOURCES HERE

# Name for your allocation output folder (overwrites folders of the same name)
allocation_folder = "my_custom_analysis"  # EDIT THIS: name your analysis

# Choose your emission category
emission_category = "co2-ffi"

# Choose your data sources
active_sources = {
    # Target source - What you're allocating
    # - "rcbs": Remaining Carbon Budgets (for budget allocations)
    # - "ar6": IPCC AR6 scenarios (for pathway allocations)
    "target": "rcbs",
    # Historical emissions - Required for responsibility calculations
    # - "primap-202503": PRIMAP-hist v2.6 (March 2025), 1850-2023
    "emissions": "primap-202503",
    # GDP - Used for capability-based adjustments
    # - "wdi-2025": World Bank World Development Indicators (2025)
    "gdp": "wdi-2025",
    # Population - Required for per capita calculations
    # - "un-owid-2025": UN Population Prospects + Our World in Data (2025)
    "population": "un-owid-2025",
    # Gini coefficient - For within-country inequality adjustments
    # - "unu-wider-2025": UNU-WIDER World Income Inequality Database (2025)
    "gini": "unu-wider-2025",
    # RCB pathway generator - Optional, defaults to "exponential-decay"
    # "rcb_generator": "exponential-decay",
}

# For pathways allocations only - choose harmonisation year to historical data
desired_harmonisation_year = 2020

# %%
# Storing configuration for later use and confirming ready for Step 2

target = active_sources.get("target")
active_target_source = active_sources["target"]
active_emissions_source = active_sources["emissions"]
active_gdp_source = active_sources["gdp"]
active_population_source = active_sources["population"]
active_gini_source = active_sources["gini"]
if target != "rcbs":
    harmonisation_year = desired_harmonisation_year
else:
    harmonisation_year = None  # Not needed for RCBs

print("Configuration set!")
print(f"  - Emission category: {emission_category}")
print(f"  - Target source: {target}")
print(f"  - Emissions: {active_emissions_source}")
if harmonisation_year is not None:
    print(f"  - Harmonisation year: {harmonisation_year}")
print("\nReady to proceed to Step 2.")

# %%
# Validate configuration (recommended - catches issues early)

print("Validating configuration...")
validation_result = validate_data_source_config(
    emission_category=emission_category, active_sources=active_sources, verbose=True
)

if validation_result["valid"]:
    print("\nConfiguration is valid!")
    print(f"   Target type: {validation_result['target_type']}")
    print(
        f"   Compatible approaches: {len(validation_result['compatible_approaches'])} available"
    )
else:
    print("\nConfiguration has issues:")
    for issue in validation_result["issues"]:
        print(f"   - {issue}")
    raise ConfigurationError(
        "Configuration validation failed. Please fix the issues above before proceeding."
    )

# %% [markdown]
# ---
# ## Step 2: Define Allocation Approaches
#
# Translate your principles into allocation formulas.
#
# Ask yourself:
#
# 1. Which principles matter? Egalitarianism? Historical responsibility? Capability?
# 2. What weights? If combining principles, what relative importance?
# 3. Subsistence protection? Should basic-needs emissions be excluded?
#
# See [From Principle to Code]({DOCS_ROOT}/science/principle-to-code/) for principle-approach mapping.
#
# **Available approaches:**
#
# - Budget (`target="rcbs"`): `equal-per-capita-budget`, `per-capita-adjusted-budget`, `per-capita-adjusted-gini-budget`
# - Pathway (`target="ar6"` or `"rcb-pathways"`): `equal-per-capita`, `per-capita-adjusted`, `cumulative-per-capita-convergence`, `*-gini-adjusted`
#
# See [Allocation Approaches]({DOCS_ROOT}/science/allocations/) for parameters.

# %%
# CONFIGURE YOUR ALLOCATION APPROACHES HERE
#
# Instructions: Edit the configuration dictionary below to define which allocation
# approaches you want to use and their parameters.
#
# The codebase will run every permutation within the approach definition below,
# so if you wish to set specific permutations (e.g. allocate from 2015 with fixed
# shares and allocate from 1990 with dynamic shares), you can provide a list of
# configuration dictionaries for each approach.

# %%
allocations = {
    "equal-per-capita-budget": [
        {
            "allocation_year": [2015],
            "preserve_allocation_year_shares": [False],
        }
    ],
}

print("Allocation approaches defined!")
print(f"  - Number of approaches: {len(allocations)}")
print(f"  - Approaches: {', '.join(sorted(allocations.keys()))}")
print(f"  - Output folder: {allocation_folder}")
print("\nReady to run data pipeline and allocations!")

# %%
# Validate allocation approaches (recommended - catches incompatibilities early)

print("Validating allocation approaches...")
print()

# Get compatible approaches for the selected target
compatible_approaches = get_compatible_approaches(target)

# Check each approach in allocations
has_warnings = False
for approach in sorted(allocations.keys()):
    if approach not in compatible_approaches:
        has_warnings = True
        if target == "rcbs":
            print(f"WARNING: '{approach}' is not compatible with target='rcbs'")
            print("    Budget targets (RCBs) require approaches ending in '-budget'")
            print(f"    Compatible approaches: {', '.join(compatible_approaches)}")
        else:
            print(f"WARNING: '{approach}' is a budget approach but target='{target}'")
            print(
                "    Scenario targets require pathway approaches (no '-budget' suffix)"
            )
            print(f"    Compatible approaches: {', '.join(compatible_approaches)}")
        print()

if not has_warnings:
    print("All approaches are compatible with the selected target!")
    target_type = "Budget (RCB)" if target == "rcbs" else "Pathway (Scenario)"
    print(f"   Target type: {target_type}")
    print(f"   All {len(allocations)} approach(es) validated successfully")
else:
    print("Please review the warnings above and adjust your allocation approaches")
    print("   or target source to ensure compatibility.")

print("\nReady for Step 3.")

# %% [markdown]
# ---
# ## Step 3: Run Data Pipeline
#
# **Automated** - Just run the cell below.
#
# Processes all data based on your Step 1 configuration. Takes 2-5 minutes.
#
# Pipeline stages: Load raw data → Process emissions/GDP/population → Process targets → Validate → Save

# %%
print("=" * 70)
print("RUNNING DATA PIPELINE")
print("=" * 70)
print("\nThis may take several minutes...")
print(f"Processing: {emission_category} emissions")
print(f"Target: {target}")
print("")

# Define pipeline steps for progress tracking
pipeline_steps = [
    "Validating configuration",
    "Building data paths",
    "Generating Snakemake command",
    "Executing data preprocessing",
    "Verifying data setup",
]

# Run the complete data setup pipeline with progress bar
with tqdm(
    total=len(pipeline_steps), desc="Data Pipeline Progress", unit="step"
) as pbar:
    # The function handles all steps internally,
    # but we'll show a simple progress indicator
    pbar.set_description("Validating configuration")
    pbar.update(1)

    # Run the complete data setup pipeline
    # Note: The function itself has verbose output that will show detailed progress
    pbar.set_description("Running Snakemake pipeline")
    setup_info = setup_custom_data_pipeline(
        project_root=project_root,
        emission_category=emission_category,
        active_sources=active_sources,
        harmonisation_year=harmonisation_year,
        verbose=True,
    )
    pbar.update(len(pipeline_steps) - 1)  # Complete remaining steps
    pbar.set_description("Pipeline complete")

# Extract key information for later use
source_id = setup_info["source_id"]
processed_dir = setup_info["paths"]["processed_dir"]
emission_category = setup_info["emission_category"]
harmonisation_year = setup_info["config"].harmonisation_year

print("\n" + "=" * 70)
print("DATA PIPELINE COMPLETED SUCCESSFULLY!")
print("=" * 70)
print(f"Source ID: {source_id}")
print(f"Emission category: {emission_category}")
print(f"Processed data saved to: {processed_dir}")
print("\nReady to run allocations!")

# %% [markdown]
# ---
# ## Data Quality Summary
#
# The cell below provides an overview of the processed data to help you verify
# the pipeline completed successfully and understand the scope of your analysis.

# %%
print("=" * 70)
print("DATA QUALITY SUMMARY")
print("=" * 70)
print("\nLoading processed data for quality check...")

# Load all processed datasets
emiss_check_path = (
    processed_dir / f"country_emissions_{emission_category}_timeseries.csv"
)
emiss_check_df = pd.read_csv(emiss_check_path)
emiss_check_df = emiss_check_df.set_index(["iso3c", "unit", "emission-category"])
emiss_check_df = ensure_string_year_columns(emiss_check_df)

gdp_check_df = pd.read_csv(processed_dir / "country_gdp_timeseries.csv")
gdp_check_df = gdp_check_df.set_index(["iso3c", "unit"])
gdp_check_df = ensure_string_year_columns(gdp_check_df)

pop_check_df = pd.read_csv(processed_dir / "country_population_timeseries.csv")
pop_check_df = pop_check_df.set_index(["iso3c", "unit"])
pop_check_df = ensure_string_year_columns(pop_check_df)

gini_check_df = pd.read_csv(processed_dir / "country_gini_stationary.csv")
gini_check_df = gini_check_df.set_index(["iso3c", "unit"])

# Country counts
print("\nCOUNTRY COUNTS")
print("-" * 70)
emiss_countries = emiss_check_df.index.get_level_values("iso3c").unique()
emiss_n_countries = len([c for c in emiss_countries if c != "World"])
gdp_countries = gdp_check_df.index.get_level_values("iso3c").unique()
gdp_n_countries = len([c for c in gdp_countries if c != "World"])
pop_countries = pop_check_df.index.get_level_values("iso3c").unique()
pop_n_countries = len([c for c in pop_countries if c != "World"])
gini_countries = gini_check_df.index.get_level_values("iso3c").unique()
gini_n_countries = len([c for c in gini_countries if c != "World"])

print(f"Emissions:   {emiss_n_countries} countries + World total")
print(f"GDP:         {gdp_n_countries} countries + World total")
print(f"Population:  {pop_n_countries} countries + World total")
print(f"Gini:        {gini_n_countries} countries")

# Year ranges
print("\nYEAR RANGES")
print("-" * 70)
emiss_years = [col for col in emiss_check_df.columns if col.isdigit()]
gdp_years = [col for col in gdp_check_df.columns if col.isdigit()]
pop_years = [col for col in pop_check_df.columns if col.isdigit()]

if emiss_years:
    print(
        f"Emissions:   {emiss_years[0]} - {emiss_years[-1]} ({len(emiss_years)} years)"
    )
if gdp_years:
    print(f"GDP:         {gdp_years[0]} - {gdp_years[-1]} ({len(gdp_years)} years)")
if pop_years:
    print(f"Population:  {pop_years[0]} - {pop_years[-1]} ({len(pop_years)} years)")
print("Gini:        Single year (stationary)")

# Missing values check
print("\nMISSING VALUES")
print("-" * 70)
emiss_missing = emiss_check_df.isna().sum().sum()
gdp_missing = gdp_check_df.isna().sum().sum()
pop_missing = pop_check_df.isna().sum().sum()
gini_missing = gini_check_df.isna().sum().sum()

print(f"Emissions:   {emiss_missing} missing values")
print(f"GDP:         {gdp_missing} missing values")
print(f"Population:  {pop_missing} missing values")
print(f"Gini:        {gini_missing} missing values")

if emiss_missing + gdp_missing + pop_missing + gini_missing == 0:
    print("\nAll datasets are complete with no missing values!")
else:
    print("\nSome missing values detected - this is normal for countries with")
    print("   incomplete data. These will be aggregated into 'Rest of World' (ROW).")

# Check for 'World' and 'ROW' rows
print("\nAGGREGATES")
print("-" * 70)
has_world_emiss = "World" in emiss_countries
has_row_emiss = "ROW" in emiss_countries
has_world_gdp = "World" in gdp_countries
has_row_gdp = "ROW" in gdp_countries
has_world_pop = "World" in pop_countries
has_row_pop = "ROW" in pop_countries

print(
    f"World total row:        {'Yes' if has_world_emiss else 'No'} Emissions  "
    f"{'Yes' if has_world_gdp else 'No'} GDP  "
    f"{'Yes' if has_world_pop else 'No'} Population"
)
print(
    f"Rest of World (ROW):    {'Yes' if has_row_emiss else 'No'} Emissions  "
    f"{'Yes' if has_row_gdp else 'No'} GDP  "
    f"{'Yes' if has_row_pop else 'No'} Population"
)

print("\n" + "=" * 70)
print("DATA QUALITY CHECK COMPLETE")
print("=" * 70)
print("\nYour data is ready for allocation calculations!")

# %% [markdown]
# ---
# ## Step 4: Run Allocations
#
# **Automated** - Just run the cell below.
#
# Calculates allocations for all approaches defined in Step 2.
#
# Process: Load data → Run approaches → Calculate absolute emissions → Save results + metadata


# %%
print("=" * 70)
print("RUNNING ALLOCATIONS")
print("=" * 70)
print(f"\nAllocations to run: {', '.join(sorted(allocations.keys()))}")
print(f"Output folder: {allocation_folder}")
print("\nLoading processed data...")

# Load country data
emiss_path = processed_dir / f"country_emissions_{emission_category}_timeseries.csv"
country_emissions_df = pd.read_csv(emiss_path)
country_emissions_df = country_emissions_df.set_index(
    ["iso3c", "unit", "emission-category"]
)
country_emissions_df = ensure_string_year_columns(country_emissions_df)

country_gdp_df = pd.read_csv(processed_dir / "country_gdp_timeseries.csv")
country_gdp_df = country_gdp_df.set_index(["iso3c", "unit"])
country_gdp_df = ensure_string_year_columns(country_gdp_df)
validate_index_structure(country_gdp_df, "Country GDP", ["iso3c", "unit"])
validate_has_year_columns(country_gdp_df, "Country GDP")

country_population_df = pd.read_csv(processed_dir / "country_population_timeseries.csv")
country_population_df = country_population_df.set_index(["iso3c", "unit"])
country_population_df = ensure_string_year_columns(country_population_df)
validate_index_structure(country_population_df, "Country population", ["iso3c", "unit"])
validate_has_year_columns(country_population_df, "Country population")

country_gini_df = pd.read_csv(processed_dir / "country_gini_stationary.csv")
country_gini_df = country_gini_df.set_index(["iso3c", "unit"])
validate_stationary_dataframe(country_gini_df, "Country Gini", ["gini"])

print("Country data loaded")

# Load data based on target
if target == "rcbs":  # RCBs
    rcbs_df = pd.read_csv(processed_dir / "rcbs.csv")
    world_scenarios_df = None

    # Load world emissions for RCB budget calculations
    world_emiss_path = (
        processed_dir / f"world_emissions_{emission_category}_timeseries.csv"
    )
    world_emissions_df = pd.read_csv(world_emiss_path)
    world_emissions_df = world_emissions_df.set_index(
        ["iso3c", "unit", "emission-category"]
    )
    world_emissions_df = ensure_string_year_columns(world_emissions_df)
    print("RCB data loaded")
else:  # pathways
    scenarios_path = processed_dir / f"world_scenarios_{emission_category}_complete.csv"
    world_scenarios_df = pd.read_csv(scenarios_path)
    world_scenarios_df = world_scenarios_df.set_index(
        ["climate-assessment", "quantile", "iso3c", "unit", "emission-category"]
    )
    world_scenarios_df = ensure_string_year_columns(world_scenarios_df)
    rcbs_df = None
    world_emissions_df = None
    print("Scenario data loaded")

    # Load net-negative emissions metadata
    net_negative_metadata_path = processed_dir / "net_negative_emissions_metadata.yaml"
    if net_negative_metadata_path.exists():
        with open(net_negative_metadata_path) as f:
            net_negative_metadata = yaml.safe_load(f) or {}
        print("Net-negative emissions metadata loaded")
    else:
        net_negative_metadata = {}
        print("Warning: No net-negative emissions metadata found")

print("\nInitializing allocation manager...")

# Initialize allocation manager
allocation_manager = AllocationManager()

# Create output directory
output_dir = project_root / "output" / source_id / "allocations" / allocation_folder
output_dir.mkdir(parents=True, exist_ok=True)

# Build data context for parquet schema
data_context = {
    "source-id": source_id,
    "allocation-folder": allocation_folder,
    "emission-category": emission_category,
    "target-source": active_target_source,
    "emissions-source": active_sources["emissions"],
    "gdp-source": active_sources["gdp"],
    "population-source": active_sources["population"],
    "gini-source": active_sources["gini"],
}

# Track all processed parameter combinations for manifest
param_manifest_rows = []

# Delete existing parquet files before starting allocations
allocation_manager._delete_existing_parquet_files(output_dir)

print("Output directories created")
print("\nRunning allocation calculations...")
print("(This may take a few minutes)")

# Run allocations
if target == "rcbs":
    # Create progress bar for RCB allocations
    with tqdm(total=len(rcbs_df), desc="RCB Allocations", unit="budget") as pbar:
        for idx, rcb_row in rcbs_df.iterrows():
            rcb_source = rcb_row["source"]
            climate_assessment = rcb_row["climate-assessment"]
            quantile = rcb_row["quantile"]
            rcb_value = rcb_row["rcb_2020_mt"]

            pbar.set_description(f"Processing {climate_assessment} {quantile}")

            results = allocation_manager.run_parameter_grid(
                allocations_config=allocations,
                population_ts=country_population_df,
                gdp_ts=country_gdp_df,
                gini_s=country_gini_df,
                country_actual_emissions_ts=country_emissions_df,
                emission_category=emission_category,
                target_source=target,
                harmonisation_year=harmonisation_year,
            )

            for result in results:
                allocation_year = result.parameters.get("allocation_year")
                total_budget_allocated = calculate_budget_from_rcb(
                    rcb_value=rcb_value,
                    allocation_year=allocation_year,
                    world_scenario_emissions_ts=world_emissions_df,
                    verbose=False,
                )

                cumulative_budget = pd.DataFrame(
                    {str(allocation_year): [total_budget_allocated]},
                    index=world_emissions_df.index,
                )

                absolute_emissions = result.get_absolute_budgets(cumulative_budget)

                data_context_with_rcb = data_context.copy()
                data_context_with_rcb["rcb-source"] = rcb_source
                data_context_with_rcb["missing-net-negative-mtco2e"] = None

                allocation_manager.save_allocation_result(
                    result=result,
                    output_dir=output_dir,
                    absolute_emissions=absolute_emissions,
                    climate_assessment=climate_assessment,
                    quantile=quantile,
                    data_context=data_context_with_rcb,
                    **{"total-budget": total_budget_allocated},
                )

                manifest_row = {
                    "approach": result.approach,
                    "climate-assessment": climate_assessment,
                    "quantile": quantile,
                    "emission-category": emission_category,
                    "rcb-source": rcb_source,
                }
                if result.parameters:
                    manifest_row.update(result.parameters)
                if data_context_with_rcb:
                    manifest_row.update(data_context_with_rcb)
                param_manifest_rows.append(manifest_row)

            # Update progress bar
            pbar.update(1)

else:
    scenario_groups = world_scenarios_df.groupby(["climate-assessment", "quantile"])
    # Create progress bar for pathway allocations
    with tqdm(
        total=len(scenario_groups), desc="Pathway Allocations", unit="scenario"
    ) as pbar:
        for scenario_idx, scenario_group in scenario_groups:
            climate_assessment, quantile = scenario_idx

            pbar.set_description(f"Processing {climate_assessment} {quantile}")

            expected_idx = [
                "climate-assessment",
                "quantile",
                "iso3c",
                "unit",
                "emission-category",
            ]
            world_data = get_world_totals_timeseries(
                scenario_group, "World", expected_index_names=expected_idx
            )

            # Get net-negative emissions metadata for this climate assessment
            missing_net_negative = None
            if emission_category in net_negative_metadata:
                pathways = net_negative_metadata[emission_category].get("pathways", [])
                for pathway in pathways:
                    if pathway.get("climate-assessment") == climate_assessment:
                        missing_net_negative = pathway.get(
                            "cumulative_net_negative_emissions", 0.0
                        )
                        break

            results = allocation_manager.run_parameter_grid(
                allocations_config=allocations,
                population_ts=country_population_df,
                gdp_ts=country_gdp_df,
                gini_s=country_gini_df,
                country_actual_emissions_ts=country_emissions_df,
                emission_category=emission_category,
                world_scenario_emissions_ts=world_data,
                target_source=target,
                harmonisation_year=harmonisation_year,
            )

            for result in results:
                if isinstance(result, BudgetAllocationResult):
                    allocation_year = result.parameters.get("allocation_year")
                    cumulative_budget = get_cumulative_budget_from_timeseries(
                        world_data, allocation_year, expected_index_names=expected_idx
                    )
                    absolute_emissions = result.get_absolute_budgets(cumulative_budget)
                elif isinstance(result, PathwayAllocationResult):
                    absolute_emissions = result.get_absolute_emissions(world_data)
                else:
                    raise DataProcessingError(f"Unknown result type: {type(result)}")

                # Update data context with net-negative metadata for this scenario
                data_context_with_metadata = data_context.copy()
                data_context_with_metadata["missing-net-negative-mtco2e"] = (
                    missing_net_negative
                )

                allocation_manager.save_allocation_result(
                    result=result,
                    output_dir=output_dir,
                    absolute_emissions=absolute_emissions,
                    climate_assessment=climate_assessment,
                    quantile=quantile,
                    data_context=data_context_with_metadata,
                )

                manifest_row = {
                    "approach": result.approach,
                    "climate-assessment": climate_assessment,
                    "quantile": quantile,
                    "emission-category": emission_category,
                }
                if result.parameters:
                    manifest_row.update(result.parameters)
                if data_context_with_metadata:
                    manifest_row.update(data_context_with_metadata)
                param_manifest_rows.append(manifest_row)

            # Update progress bar
            pbar.update(1)

print("\nSaving metadata and documentation...")

# Save parameter manifest
allocation_manager.create_param_manifest(param_manifest_rows, output_dir)

# Generate README files
allocation_manager.generate_readme(output_dir=output_dir, data_context=data_context)

# Summarize executed approaches (with optional display mapping)
executed_approaches = sorted({row["approach"] for row in param_manifest_rows})
print("\nExecuted allocation approaches:")
for app in executed_approaches:
    print(f"  - {app}")

print("\n" + "=" * 70)
print("ALLOCATIONS COMPLETED SUCCESSFULLY!")
print("=" * 70)
print(f"Results saved to: {output_dir}")
print(f"Total parameter combinations: {len(param_manifest_rows)}")
print(f"Approaches: {', '.join(sorted(allocations.keys()))}")

# %% [markdown]
# ---
# ## Understanding Results
#
# **Output files** in `output/{source_id}/allocations/{allocation_folder}/`:
# - `allocations_relative.parquet` - Relative shares (0-1, sums to 100%)
# - `allocations_absolute.parquet` - Absolute emissions (Mt CO2e)
# - `*.csv` - Wide-format for Excel
# - `parameter_manifest.csv` - All parameter combinations
# - `README.md` - Documentation
#
# **Interpretation:**
# - **Relative shares** (0.15) = Country gets 15% of total budget/pathway
# - **Absolute values** (500 Mt) = Country's actual emission allowance
# - Negative values = Fair share already exceeded under this climate target
#
# [Output guide]({DOCS_ROOT}/user-guide/custom-analysis.md/#output-files) | [Allocation concepts]({DOCS_ROOT}/science/allocations/)
#
# ---
#
# ## Step 5: Explore Results
#
# Visualize allocations for a specific country. Edit `TEST_COUNTRY` to change (use ISO 3166-1 alpha-3 codes: USA, CHN, IND, GBR, AUS, etc.).

# %%
# Set country and year to explore
TEST_COUNTRY = "AUS"  # EDIT THIS: country code to explore
PLOT_START_YEAR = 2015  # EDIT THIS: year to start plotting

# %%
# Load and plot results for a sample country
absolute_parquet_path = output_dir / "allocations_absolute.parquet"
if absolute_parquet_path.exists():
    absolute_df = pd.read_parquet(absolute_parquet_path)
    country_data = absolute_df[absolute_df["iso3c"] == TEST_COUNTRY]

    year_cols = [
        col
        for col in country_data.columns
        if col.isdigit() and int(col) >= PLOT_START_YEAR
    ]
    non_year_cols = [col for col in country_data.columns if not col.isdigit()]
    country_data = country_data[non_year_cols + year_cols]

    if not country_data.empty:
        # Get all unique approaches from the data for this country
        available_approaches = country_data["approach"].unique()
        configured_approaches = sorted(allocations.keys())

        # Debug output
        print(
            f"\nDebug: Approaches in data for {TEST_COUNTRY}: {list(available_approaches)}"
        )
        print(f"Debug: Configured approaches: {configured_approaches}")

        # Use all configured approaches that exist in the data
        approaches = [a for a in configured_approaches if a in available_approaches]

        if len(approaches) != len(configured_approaches):
            missing = set(configured_approaches) - set(approaches)
            print(f"Warning: Some configured approaches not found in data: {missing}")
            print(
                f"Available approaches in full dataset: {list(absolute_df['approach'].unique())}"
            )

        grp = country_data.groupby(["climate-assessment", "quantile"]).size()
        scenario_groups = grp.reset_index()[["climate-assessment", "quantile"]]

        n_approaches = len(approaches)
        n_scenarios = len(scenario_groups)

        fig, axes = plt.subplots(
            n_scenarios,
            n_approaches,
            figsize=(6 * n_approaches, 5 * n_scenarios),
            sharex=True,
            sharey=True,
        )
        if not isinstance(axes, np.ndarray):
            axes = np.array([[axes]])
        elif axes.ndim == 1:
            if n_scenarios == 1:
                axes = axes[np.newaxis, :]
            else:
                axes = axes[:, np.newaxis]

        for i, (_, scenario) in enumerate(scenario_groups.iterrows()):
            ca = scenario["climate-assessment"]
            q = scenario["quantile"]
            scenario_data = country_data[
                (country_data["climate-assessment"] == ca)
                & (country_data["quantile"] == q)
            ]

            for j, approach in enumerate(approaches):
                ax = axes[i, j]
                approach_data = scenario_data[scenario_data["approach"] == approach]

                if approach_data.empty:
                    ax.text(
                        0.5,
                        0.5,
                        f"No data for {approach}",
                        ha="center",
                        va="center",
                        transform=ax.transAxes,
                    )
                    ax.set_title(
                        f"{approach}\n{ca} {q}", fontsize=12, fontweight="bold"
                    )
                    ax.set_xlabel("Year", fontsize=10)
                    ax.set_ylabel("Emissions (Mt CO2e)", fontsize=10)
                    continue

                year_cols = [col for col in approach_data.columns if col.isdigit()]
                years = [int(col) for col in year_cols]

                colors = plt.cm.Set3(np.linspace(0, 1, len(approach_data)))
                for idx, (row_idx, row) in enumerate(approach_data.iterrows()):
                    emissions = row[year_cols].values
                    ax.plot(
                        years,
                        emissions,
                        marker="o",
                        markersize=4,
                        linewidth=2,
                        color=colors[idx],
                        alpha=0.8,
                    )

                try:
                    hist_path = (
                        processed_dir
                        / f"country_emissions_{emission_category}_timeseries.csv"
                    )
                    if hist_path.exists():
                        hist_df = pd.read_csv(hist_path, index_col=[0, 1, 2])
                        country_actual = hist_df[
                            (hist_df.index.get_level_values("iso3c") == TEST_COUNTRY)
                            & (
                                hist_df.index.get_level_values("emission-category")
                                == emission_category
                            )
                        ]
                        if not country_actual.empty:
                            year_cols = [
                                col
                                for col in country_actual.columns
                                if str(col).isdigit() and int(col) >= PLOT_START_YEAR
                            ]
                            non_year_cols = [
                                col
                                for col in country_actual.columns
                                if not str(col).isdigit()
                            ]
                            country_actual = country_actual[non_year_cols + year_cols]

                            actual_years = [int(col) for col in year_cols]
                            actual_emissions = country_actual[year_cols].iloc[0].values
                            ax.plot(
                                actual_years,
                                actual_emissions,
                                color="black",
                                linewidth=3,
                                alpha=0.9,
                                label="Historical",
                            )
                except Exception:
                    pass

                # Add dashed zero line
                ax.axhline(
                    y=0, color="black", linestyle="--", linewidth=1, alpha=0.5, zorder=0
                )

                ax.set_title(f"{approach}\n{ca} {q}", fontsize=12, fontweight="bold")
                ax.set_xlabel("Year", fontsize=10)
                ax.set_ylabel("Emissions (Mt CO2e)", fontsize=10)
                if i == 0 and j == 0:
                    ax.legend(loc="upper right", fontsize=8)

        plt.suptitle(
            f"Emissions Allocations for {TEST_COUNTRY}", fontsize=16, fontweight="bold"
        )
        plt.tight_layout()
        plt.show()

# %%
# Create wide-format CSV from parquet files

# You can set which configuration parameters should be used in the approach_short column.
# Remove keys you do NOT want in the approach_short summarized configuration string.
# If you want ALL parameters included, set allocation_param_prefixes = None
allocation_param_prefixes = {
    "first-allocation-year": "y",
    "allocation-year": "ay",
    # "preserve-first-allocation-year-shares": "pfa",
    # "preserve-allocation-year-shares": "pa",
    # "convergence-year": "cy",
    # "convergence-speed": "cs",
    "responsibility-weight": "rw",
    "capability-weight": "cw",
    "historical-responsibility-year": "hr",
    # "responsibility-per-capita": "rpc",
    # "capability-per-capita": "cpc",
    # "responsibility-exponent": "re",
    # "capability-exponent": "ce",
    # "responsibility-functional-form": "rff",
    # "capability-functional-form": "cff",
    # "max-deviation-sigma": "sigma",
    # "income-floor": "if",
    # "max-gini-adjustment": "gini",
}

# Create wide-format CSV
csv_path = convert_parquet_to_wide_csv(
    allocations_dir=output_dir,
    config_prefixes=allocation_param_prefixes,
)

print(f"\nWide-format CSV created: {csv_path}")

# %% [markdown]
# ---
# ## Results Summary
#
# Below is a summary of all files created and a preview of your allocation results.

# %%
# Results Summary

print("\n" + "=" * 70)
print("ALLOCATION RESULTS SUMMARY")
print("=" * 70)

parquet_files = sorted(output_dir.glob("*.parquet"))
csv_files = sorted(output_dir.glob("*.csv"))
other_files = sorted(output_dir.glob("*.md"))

print(f"\nOutput directory: {output_dir}")
print("\nFiles created:")
print("\nParquet files (optimized for Python/R):")
for f in parquet_files:
    size_kb = os.path.getsize(f) / 1024
    print(f"  {f.name} ({size_kb:.1f} KB)")

print("\nCSV files (for Excel/spreadsheets):")
for f in csv_files:
    size_kb = os.path.getsize(f) / 1024
    print(f"  {f.name} ({size_kb:.1f} KB)")

print("\nDocumentation:")
for f in other_files:
    size_kb = os.path.getsize(f) / 1024
    print(f"  {f.name} ({size_kb:.1f} KB)")

# Quick preview of results
if parquet_files:
    print("\n" + "=" * 70)
    print("QUICK PREVIEW (first 5 rows of allocations_absolute.parquet)")
    print("=" * 70)

    # Try to find the absolute allocations file
    abs_file = output_dir / "allocations_absolute.parquet"
    if abs_file.exists():
        preview_df = pd.read_parquet(abs_file)

        # Show a subset of columns for readability
        excluded_cols = [
            "source-id",
            "emissions-source",
            "gdp-source",
            "population-source",
            "gini-source",
            "target-source",
        ]
        display_cols = [col for col in preview_df.columns if col not in excluded_cols]

        # Limit to first few columns plus a few year columns
        year_cols = [col for col in display_cols if col.isdigit()]
        if year_cols:
            # Show first non-year columns and first 3 year columns
            non_year_cols = [col for col in display_cols if not col.isdigit()]
            sample_year_cols = year_cols[:3]
            display_cols = non_year_cols + sample_year_cols

        print(preview_df[display_cols].head())
        print(f"\n... and {len(preview_df) - 5} more rows")
        print(f"Total year columns: {len(year_cols)}")
    else:
        print("(allocations_absolute.parquet not found)")
else:
    print("\n(No parquet files found - check if allocations completed successfully)")

print("\n" + "=" * 70)
print("Analysis complete! Check the output directory for full results.")
print("=" * 70)

# %%
