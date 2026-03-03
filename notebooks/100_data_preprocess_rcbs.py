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
    emission_category = "co2-ffi"  # or "co2"
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

# RCBs are only available for co2-ffi and co2
if emission_category not in ("co2-ffi", "co2"):
    raise ConfigurationError(
        f"RCB-based budget allocations only support 'co2-ffi' and 'co2' emission "
        f"categories. Got: {emission_category}. Please use target: 'ar6'"
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

# Get RCB adjustment configuration (NGHGI-consistent timeseries)
# Import here (not top-level) to avoid circular import — utils must initialise first
from fair_shares.library.config.models import AdjustmentsConfig

rcb_data_parameters = rcb_config.get("data_parameters", {})
rcb_adjustments_raw = rcb_data_parameters.get("adjustments", {})
adjustments_config = AdjustmentsConfig.model_validate(rcb_adjustments_raw)

print("RCB adjustments (NGHGI-consistent, Weber et al. 2026):")
print(f"  LULUCF NGHGI source: {adjustments_config.lulucf_nghgi.path}")
print(f"  Bunkers source: {adjustments_config.bunkers.path}")
print(f"  AR6 constants: {adjustments_config.ar6_constants_path}")
print(f"  Precautionary LULUCF cap: {adjustments_config.precautionary_lulucf}")

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
# ## Compute AR6 category constants from Gidden reanalysis
#
# Extracts scenario-specific net-zero years from the Gidden et al. AR6
# reanalysis data, for each AR6 warming category (C1, C2, C3).
#
# **Why this matters:** Weber (2026) integrates LULUCF and bunker deductions
# "until net zero CO₂ is reached" — which is scenario-specific. Using a
# single end year (e.g. 2100) over-integrates by 30-50 years for stricter
# categories.
#
# **Outputs:** `data/rcbs/ar6_category_constants.yaml` with per-category:
# - `net_zero_year_nghgi`: first year median NGHGI-convention CO₂ ≤ 0
# - `net_zero_year_scientific`: first year median BM-convention CO₂ ≤ 0
# - `n_scenarios`: number of scenarios in the category

# %%
from fair_shares.library.utils.data.nghgi import (
    _AFOLU_INDIRECT_VAR,
    _is_year,
)

gidden_path = project_root / "data/scenarios/ipcc_ar6_gidden/ar6_gidden.xlsx"
meta_path = project_root / "data/scenarios/ipcc_ar6_gidden/metadata_ar6_gidden.xlsx"
ar6_constants_output_path = project_root / "data/rcbs/ar6_category_constants.yaml"

print(f"Gidden data: {gidden_path}")
print(f"Metadata: {meta_path}")
print(f"Output: {ar6_constants_output_path}")

# %%
print("Loading metadata...")
ar6_meta_df = pd.read_excel(meta_path, sheet_name="meta", header=0)
print(f"  {len(ar6_meta_df)} scenarios total")
print(f"  Categories: {sorted(ar6_meta_df['Category'].dropna().unique())}")

# %%
print("Loading Gidden data (this may take a moment)...")
ar6_data_df = pd.read_excel(gidden_path, sheet_name="data", header=0)
print(f"  {len(ar6_data_df)} rows")
print(f"  Variables: {ar6_data_df['Variable'].nunique()}")

# %% [markdown]
# ### Discover available CO₂ variables

# %%
co2_vars = sorted(
    ar6_data_df[ar6_data_df["Variable"].str.contains("Emissions|CO2", regex=False)][
        "Variable"
    ].unique()
)
print(f"Found {len(co2_vars)} CO2-related variables:")
for v in co2_vars:
    print(f"  {v}")

# %% [markdown]
# ### Define variable names and compute net-zero years
#
# In the Gidden AR6 reanalysis (OSCAR v3.2):
# - `Emissions|CO2` uses BM convention (fossil + direct LULUCF only)
# - NGHGI-consistent total = `Emissions|CO2` + `AFOLU|Indirect`
#
# We compute both net-zero years:
# - **Scientific (BM)**: year when `Emissions|CO2` median ≤ 0
# - **NGHGI**: year when (`Emissions|CO2` + `AFOLU|Indirect`) median ≤ 0

# %%
_OSCAR_PREFIX = "AR6 Reanalysis|OSCARv3.2|"
_TOTAL_CO2_VAR = f"{_OSCAR_PREFIX}Emissions|CO2"

# Verify variables exist
for var_name, label in [
    (_TOTAL_CO2_VAR, "Total CO2 (BM)"),
    (_AFOLU_INDIRECT_VAR, "AFOLU|Indirect"),
]:
    n_rows = (ar6_data_df["Variable"] == var_name).sum()
    if n_rows == 0:
        alt_vars = [v for v in co2_vars if var_name.split("|")[-1] in v]
        raise ValueError(
            f"Variable '{var_name}' ({label}) not found in data. "
            f"Similar variables: {alt_vars}"
        )
    print(f"  {label}: {n_rows} rows for '{var_name}'")


# %%
from fair_shares.library.utils.data.nghgi import find_net_zero_year

# %%
# Year columns and World filter
ar6_year_cols = [c for c in ar6_data_df.columns if _is_year(c)]
ar6_year_ints = sorted(int(c) for c in ar6_year_cols)
print(f"Year range in data: {min(ar6_year_ints)}-{max(ar6_year_ints)}")

world_mask = ar6_data_df["Region"] == "World"
print(f"World rows: {world_mask.sum()} of {len(ar6_data_df)}")

# %%
categories = ["C1", "C2", "C3"]
ar6_results = {}

for cat in categories:
    print(f"\n{'=' * 60}")
    print(f"Category {cat}")
    print(f"{'=' * 60}")

    cat_meta = ar6_meta_df[ar6_meta_df["Category"] == cat]
    n_scenarios = len(cat_meta)
    cat_pairs = set(zip(cat_meta["model"], cat_meta["scenario"]))
    print(f"  {n_scenarios} scenarios")

    data_pairs = pd.MultiIndex.from_frame(ar6_data_df[["Model", "Scenario"]])
    cat_mi = pd.MultiIndex.from_tuples(list(cat_pairs))
    mask_cat = data_pairs.isin(cat_mi)

    # Scientific convention (BM): Emissions|CO2
    mask_total = ar6_data_df["Variable"] == _TOTAL_CO2_VAR
    bm_rows = ar6_data_df[world_mask & mask_cat & mask_total]
    print(f"  BM total CO2 rows: {len(bm_rows)}")

    bm_median = bm_rows[ar6_year_cols].median(axis=0)
    bm_median.index = bm_median.index.astype(int)
    bm_median = bm_median.sort_index()

    nz_scientific = find_net_zero_year(bm_median)
    print(f"  Scientific NZ year: {nz_scientific}")

    # NGHGI convention: Emissions|CO2 + AFOLU|Indirect
    mask_indirect = ar6_data_df["Variable"] == _AFOLU_INDIRECT_VAR
    indirect_rows = ar6_data_df[world_mask & mask_cat & mask_indirect]
    print(f"  AFOLU|Indirect rows: {len(indirect_rows)}")

    bm_indexed = bm_rows.set_index(["Model", "Scenario"])[ar6_year_cols].rename(
        columns=str
    )
    indirect_indexed = indirect_rows.set_index(["Model", "Scenario"])[
        ar6_year_cols
    ].rename(columns=str)

    common_idx = bm_indexed.index.intersection(indirect_indexed.index)
    print(f"  Scenarios with both variables: {len(common_idx)}")

    nghgi_total = bm_indexed.loc[common_idx] + indirect_indexed.loc[common_idx]
    nghgi_median = nghgi_total.median(axis=0)
    nghgi_median.index = nghgi_median.index.astype(int)
    nghgi_median = nghgi_median.sort_index()

    nz_nghgi = find_net_zero_year(nghgi_median)
    print(f"  NGHGI NZ year: {nz_nghgi}")

    # Verification: print key years around NZ
    for label, median_ts, nz_year in [
        ("Scientific", bm_median, nz_scientific),
        ("NGHGI", nghgi_median, nz_nghgi),
    ]:
        if nz_year:
            window = range(
                max(nz_year - 3, min(ar6_year_ints)),
                min(nz_year + 4, max(ar6_year_ints) + 1),
            )
            vals = {y: f"{median_ts.get(y, float('nan')):.0f}" for y in window}
            print(f"  {label} around NZ: {vals}")

    ar6_results[cat] = {
        "net_zero_year_nghgi": nz_nghgi,
        "net_zero_year_scientific": nz_scientific,
        "n_scenarios": n_scenarios,
    }

# %% [markdown]
# ### Summary and save AR6 constants

# %%
print("\nAR6 Category Constants:")
print("-" * 50)
for cat, vals in sorted(ar6_results.items()):
    print(
        f"  {cat}: NGHGI NZ={vals['net_zero_year_nghgi']}, "
        f"Scientific NZ={vals['net_zero_year_scientific']}, "
        f"n={vals['n_scenarios']}"
    )

# Sanity checks
for cat, vals in ar6_results.items():
    nz_nghgi = vals["net_zero_year_nghgi"]
    nz_sci = vals["net_zero_year_scientific"]

    if nz_nghgi is None:
        print(f"  WARNING: {cat} NGHGI total CO2 never reaches zero!")
    if nz_sci is None:
        print(f"  WARNING: {cat} scientific total CO2 never reaches zero!")
    if nz_nghgi and nz_sci and nz_nghgi > nz_sci:
        print(
            f"  NOTE: {cat} NGHGI NZ ({nz_nghgi}) > scientific NZ ({nz_sci}) — "
            "expected since NGHGI LULUCF sink is larger"
        )

# %%
yaml_header = (
    "# AR6 category constants — auto-generated by notebook 100_data_preprocess_rcbs\n"
    "# Source: Gidden et al. AR6 reanalysis (OSCARv3.2)\n"
    "# DO NOT EDIT MANUALLY — re-run the notebook to regenerate\n"
    "#\n"
    "# net_zero_year_nghgi: first year category-median NGHGI-convention CO2 <= 0\n"
    "# net_zero_year_scientific: first year category-median BM-convention CO2 <= 0\n"
    "# n_scenarios: number of AR6 scenarios in this category\n"
)

with open(ar6_constants_output_path, "w") as f:
    f.write(yaml_header)
    yaml.dump(ar6_results, f, default_flow_style=False, sort_keys=True)

print(f"\nSaved to: {ar6_constants_output_path}")

with open(ar6_constants_output_path) as f:
    print(f.read())

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
#
# Delegates to `load_and_process_rcbs()` which handles NGHGI-consistent
# timeseries-based adjustments (LULUCF deduction + bunker subtraction)
# with per-category net-zero years following Weber et al. (2026).

# %%
from fair_shares.library.preprocessing.rcbs import load_and_process_rcbs

# Get world emissions timeseries for RCB processing
world_emissions_df = world_emiss[emission_category]
world_emissions_df = ensure_string_year_columns(world_emissions_df)

rcb_df = load_and_process_rcbs(
    rcb_yaml_path=rcb_yaml_path,
    world_emissions_df=world_emissions_df,
    emission_category=emission_category,
    adjustments_config=adjustments_config,
    project_root=project_root,
    verbose=True,
)

# %% [markdown]
# ## Save processed RCB data

# %%
# Display the processed data
print("\nProcessed RCB data:")
print(rcb_df.to_string(index=False))

# Save to processed intermediate directory
rcb_output_path = processed_intermediate_dir / "rcbs.csv"
rcb_df.to_csv(rcb_output_path, index=False)

print(f"\nSaved processed RCB data to: {rcb_output_path}")
