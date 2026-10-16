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
# # Scenario Data Preprocessing Script
#
# This script uses the NGHGi (National Greenhouse Gas Inventories) corrections to
# the AR6 scenarios database from Gidden et al. 2023 (10.1038/s41586-023-06724-y).
# NGHGi treats LULUCF as direct + indirect land CO2 fluxes on managed land.
#
# ### Variables (shorthand = full variable name from Gidden et al. 2023):
# - CO2 = Emissions|CO2
# - CO2_NGHGI = Emissions|CO2 - Direct and Indirect Fluxes
# - AFOLU_direct = Emissions|CO2|AFOLU|Direct
# - AFOLU_indirect = Emissions|CO2|AFOLU|Indirect
# - KYOTO = Emissions|Kyoto Gases
# - KYOTO_NGHGI = Emissions|Kyoto Gases - Direct and Indirect Fluxes
#
# ### Emission category formulas:
# - co2-ffi = CO2 - AFOLU_direct
# - all-ghg-ex-co2-lulucf = KYOTO - AFOLU_direct
# - all-ghg = KYOTO_NGHGI

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
    ConfigurationError,
    DataProcessingError,
)
from fair_shares.library.paths import resolve_source_path
from fair_shares.library.preprocessing import emissions_path
from fair_shares.library.utils import (
    build_source_id,
    determine_processing_categories,
    ensure_string_year_columns,
    get_default_unit_registry,
    get_world_totals_timeseries,
    harmonize_to_historical_with_convergence,
    interpolate_scenarios_data,
    process_iamc_zip,
)
from fair_shares.library.utils.data.gcb import gcb_global_net_co2
from fair_shares.library.utils.data.rcb import (
    AR6_CATEGORY_BY_RCB_LABEL,
    DEFAULT_REBASE_FILL_MAX_YEARS,
    convention_gap_from_baseline,
    integrate,
    parse_rcb_scenario,
)
from fair_shares.library.utils.data.scenario_sets import (
    NET_ZERO_CROSSING,
    SHARE_START_YEARS,
    add_source_non_co2_members,
    build_budget_sets,
    bunker_share,
    bunker_share_table,
    median_pathways_by_budget,
    scenario_accounting,
    scenario_set_settings,
)
from fair_shares.library.utils.data.scenario_sources import (
    annual_pathways,
    apply_derived_net_zero,
    ar6_at_net_zero,
    bunker_reporter_series,
    derived_source_inputs,
    get_scenario_source,
    metadata_column_names,
)
from fair_shares.library.utils.dataframes import normalize_metadata_column
from fair_shares.library.utils.units import _clean_unit_string

# %% tags=["parameters"]
emission_category = None
active_target_source = None
active_emissions_source = None
active_gdp_source = None
active_population_source = None
active_gini_source = None
active_lulucf_source = None
active_scenario_source = None  # NEW
source_id = None

# %%
_running_via_papermill = emission_category is not None

if _running_via_papermill:
    # Running via Papermill
    print("Running via Papermill")

    # Use source_id from Snakefile if provided (essential for allghg triple-pass
    # where per-pass emission_category differs from the source_id's category).
    if source_id is None:
        source_id = build_source_id(
            emissions=active_emissions_source,
            gdp=active_gdp_source,
            population=active_population_source,
            gini=active_gini_source,
            lulucf=active_lulucf_source,
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
        "emissions": "primap-202609",
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
    active_scenario_source = "ar6"

# %% [markdown]
# ## Prepare parameters

# %%
project_root = here()
print(f"Project root: {project_root}")


# Get scenario configuration from the scenarios section.
# This notebook processes whatever scenario source is configured —
# the source is selected via active_scenario_source, not hard-coded.
_active_scenario = active_scenario_source or config.get("active_scenario_source")
if not _active_scenario:
    # Fallback: infer from target's scenario_source field
    _pipeline_target = config.get("active_target_source", active_target_source)
    _target_cfg = config["targets"].get(_pipeline_target, {})
    _active_scenario = _target_cfg.get("scenario_source", _pipeline_target)

# Read from scenarios section if available, fall back to targets for backwards compat
if "scenarios" in config and _active_scenario in config["scenarios"]:
    scenario_config = config["scenarios"][_active_scenario]
    scenario_data_parameters = scenario_config.get("data_parameters", {})
    scenario_path = scenario_config["path"]
    world_key = scenario_data_parameters.get("world_key", "World")
    interpolation_method = scenario_data_parameters.get(
        "interpolation_method", "linear"
    )
    available_categories = scenario_data_parameters.get("available_categories", [])
else:
    # Backwards compatibility: read from targets section
    _pipeline_target = config.get("active_target_source", active_target_source)
    if "pathway" in config.get("targets", {}):
        scenario_config = config["targets"]["pathway"]
    else:
        scenario_config = config["targets"][_pipeline_target]
    scenario_data_parameters = scenario_config.get("data_parameters", {})

    allghg_scenarios = scenario_data_parameters.get("all_ghg_scenarios")
    if allghg_scenarios and not scenario_data_parameters.get("world_key"):
        scenario_path = allghg_scenarios["path"]
        world_key = allghg_scenarios["world_key"]
        interpolation_method = allghg_scenarios.get("interpolation_method")
        available_categories = ["co2-ffi", "co2", "all-ghg", "all-ghg-ex-co2-lulucf"]
    else:
        scenario_path = scenario_config["path"]
        world_key = scenario_data_parameters.get("world_key")
        interpolation_method = scenario_data_parameters.get("interpolation_method")
        available_categories = scenario_data_parameters.get("available_categories", [])

# Extract config values — Papermill parameter takes precedence for allghg triple-pass
if not _running_via_papermill:
    emission_category = config["emission_category"]
emissions_config = config["emissions"][active_emissions_source]
emissions_data_parameters = emissions_config["data_parameters"]

# Construct intermediate_dir from output directory structure
intermediate_dir_str = f"output/{source_id}/intermediate/scenarios"
intermediate_dir = project_root / intermediate_dir_str
intermediate_dir.mkdir(parents=True, exist_ok=True)

# Check required parameters are specified
if not emission_category:
    raise ConfigurationError("'emission_category' must be specified in global config")

if not available_categories:
    raise ConfigurationError(
        "'available_categories' must be specified in scenario data_parameters"
    )

if not world_key:
    raise ConfigurationError(
        "'world_key' must be specified in scenario data_parameters"
    )

# Validate that requested emission category is available in this data source
if emission_category not in available_categories:
    raise ConfigurationError(
        f"Requested emission category '{emission_category}' not available in data "
        f"source. Available categories: {available_categories}"
    )

# AR6 Emission Category Processing Configuration
#
# AR6 uses hierarchical variable names with pipe separators and some emission categories
# require combining multiple variables. The mapping is defined below:

# Define which emission categories we can process for AR6
# Primary categories are computed from Gidden variables in the main loop.
# Derived categories (co2-lulucf, non-co2) are computed after the loop
# from already-processed primary categories.
supported_categories = [
    "co2-ffi",
    "co2-lulucf",
    "co2",
    "non-co2",
    "all-ghg-ex-co2-lulucf",
    "all-ghg",
]
# Categories computed directly from Gidden variables (processed in main loop)
_primary_categories = ["co2-ffi", "co2", "all-ghg-ex-co2-lulucf", "all-ghg"]
# Categories derived from primary categories (processed after main loop)
_derived_categories = ["co2-lulucf", "non-co2"]

# Check that requested category is supported
if emission_category not in supported_categories:
    raise ConfigurationError(
        f"Emission category '{emission_category}' is not yet supported for AR6. "
        f"Supported: {supported_categories}"
    )

# Determine which categories to process using utility function
processing_info = determine_processing_categories(
    emission_category, supported_categories
)
processing_categories = processing_info["process"]
final_categories = processing_info["final"]

# Primary categories go through the main loop (computed from Gidden variables).
# Derived categories are computed after the loop from the primaries.
primary_to_process = [c for c in processing_categories if c in _primary_categories]
derived_to_process = [c for c in processing_categories if c in _derived_categories]

# Always process the primaries needed for derivation
# co2-lulucf needs: co2, co2-ffi
# non-co2 needs: all-ghg, co2 OR all-ghg-ex-co2-lulucf, co2-ffi
if "co2-lulucf" in derived_to_process:
    for dep in ["co2", "co2-ffi"]:
        if dep not in primary_to_process:
            primary_to_process.append(dep)
if "non-co2" in derived_to_process:
    for dep in ["all-ghg", "co2"]:
        if dep not in primary_to_process:
            primary_to_process.append(dep)

print(f"Processing categories: {processing_categories}")
print(f"Final categories: {final_categories}")

# Filter to only primary categories for the main processing loop
timeseries_specs = primary_to_process

# AR6 category paired with each budget label (C1 1.5p50, C3 2p67, C4 2p50).
# The category medians carry the label; the output splits it into a clean
# climate assessment and quantile (e.g. "1.5C", 0.5) to match the RCB format.
_AR6_TO_SCENARIO = {
    category: label for label, category in AR6_CATEGORY_BY_RCB_LABEL.items()
}
_AR6_CATEGORIES_TO_PROCESS = list(_AR6_TO_SCENARIO.keys())
desired_climate_assessments = list(_AR6_TO_SCENARIO.values())
_SCENARIO_TO_ASSESSMENT = {
    label: parse_rcb_scenario(label)[0] for label in desired_climate_assessments
}
_SCENARIO_TO_QUANTILE = {
    label: float(parse_rcb_scenario(label)[1]) for label in desired_climate_assessments
}

# Print out the parameters for debugging
print(f"Scenario source: {active_target_source}")
print(f"Scenario path: {scenario_path}")
print(f"Emission categories: {emission_category}")
print(f"Interpolation method: {interpolation_method}")
print(f"World key: {world_key}")
print(f"Intermediate directory: {intermediate_dir_str}")
print(f"Processing these emission categories: {timeseries_specs}")
print(f"Desired scenarios: {desired_climate_assessments}")

# %% [markdown]
# ## Load data

# %%
# The registry entry of the scenario source declares its variables, the
# metadata columns of the selection rules and its bunker series.
scenario_source = get_scenario_source(_active_scenario)
_selection_columns = metadata_column_names(scenario_source)

# Process the scenario source
print(f"Processing {active_target_source} scenarios...")
df = process_iamc_zip(project_root / scenario_path, metadata_columns=_selection_columns)

# Scenario metadata, one row per scenario, for the RCB scenario sets.
_normalised = {normalize_metadata_column(c): c for c in _selection_columns}
_normalised["Category"] = "Category"
scenario_metadata = (
    df[["Model", "Scenario", *_normalised]]
    .drop_duplicates()
    .rename(columns=_normalised)
    .set_index(["Model", "Scenario"])
)
df = df.drop(columns=[c for c in _normalised if c != "Category"])
_set_columns = {
    "category": scenario_source["category_column"],
    **scenario_source["metadata_columns"],
}

# %% [markdown]
# ## Load historical emissions for harmonisation
#
# Load historical emissions data to harmonize individual AR6 pathways before
# aggregating to the median. This ensures all pathways match historical at the
# anchor year.

# %%
print("Loading historical emissions data for harmonisation...")
emiss_intermediate_dir = project_root / f"output/{source_id}/intermediate/emissions"
emissions_world_key = emissions_data_parameters.get("world_key")

historical_emissions_data = {}
for category in timeseries_specs:
    emiss_path = emissions_path(emiss_intermediate_dir, category, active_lulucf_source)
    if emiss_path.exists():
        emiss_df = pd.read_csv(emiss_path)
        emiss_df = emiss_df.set_index(["iso3c", "unit", "emission-category"])
        emiss_df = ensure_string_year_columns(emiss_df)
        world_emiss = get_world_totals_timeseries(
            emiss_df,
            emissions_world_key,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )
        historical_emissions_data[category] = world_emiss
        print(f"  Loaded historical emissions for {category}")
    else:
        print(f"  Warning: Historical emissions not found for {category}")
        historical_emissions_data[category] = None

anchor_year = config.get("harmonisation_year")
if anchor_year is None:
    raise ConfigurationError(
        "harmonisation_year must be specified in config for harmonisation"
    )
convergence_year = anchor_year + 10
print(f"Harmonisation: anchor year {anchor_year}, convergence year {convergence_year}")

# %% [markdown]
# ## Helper Functions


# %%
def clean_columns_for_merge(df1, df2, id_vars):
    """Clean string columns in both dataframes for merging."""
    for col in id_vars:
        df1[col] = df1[col].astype(str).str.strip()
        df2[col] = df2[col].astype(str).str.strip()


def calculate_emission_difference(df1, df2, id_vars, year_cols, suffix1, suffix2):
    """
    Calculate the difference between two emission variables (df1 - df2).

    Returns merged dataframe with year_data dict containing calculated
    differences.
    """
    # Clean group columns for merging
    clean_columns_for_merge(df1, df2, id_vars)

    # Merge on group columns
    merged = pd.merge(
        df1[id_vars + year_cols],
        df2[id_vars + year_cols],
        on=id_vars,
        suffixes=(f"_{suffix1}", f"_{suffix2}"),
        how="inner",
    )

    if merged.empty:
        raise DataProcessingError(f"No matches found between {suffix1} and {suffix2}")

    # Calculate difference for each year
    year_data = {}
    for year in year_cols:
        col1 = f"{year}_{suffix1}"
        col2 = f"{year}_{suffix2}"
        if col1 in merged.columns and col2 in merged.columns:
            year_data[year] = merged[col1] - merged[col2]
        else:
            raise DataProcessingError(f"Missing columns for year {year}")

    return merged, year_data


def extract_unit_from_data(var_df):
    """Extract unit from the processed DataFrame's Unit column."""
    if "Unit" not in var_df.columns:
        raise DataProcessingError("DataFrame has no 'Unit' column")
    unique_units = var_df["Unit"].unique()
    if len(unique_units) == 1:
        return unique_units[0]
    raise DataProcessingError(f"Multiple units found: {unique_units}")


# %% [markdown]
# ## Analysis

# %%
# Process AR6 scenarios data for all timeseries
print(f"Processing scenarios data from {active_target_source}")

# Rename 'Category' to 'climate-assessment' and relabel to RCB scenario labels
df = df.rename(columns={"Category": "climate-assessment"})

# The budget scenario sets draw on every category.
df_all_categories = df

# Shorthand for the variables that the scenario source registry declares
_registry_variables = scenario_source["variables"]
shorthand_variables = {
    "CO2": _registry_variables["co2"],
    "CO2_NGHGI": _registry_variables["co2_nghgi"],
    "AFOLU_direct": _registry_variables["afolu_direct"],
    "AFOLU_indirect": _registry_variables["afolu_indirect"],
    "KYOTO": _registry_variables["kyoto"],
    "KYOTO_NGHGI": _registry_variables["kyoto_nghgi"],
}

# %% [markdown]
# ## Scenario sets of every budget
#
# Each budget in rcbs.yaml takes its scenario-derived terms from sets matched
# to their role (`fair_shares.library.utils.data.scenario_sets`):
#
# - volume-matched set (land-use deduction, convention gap, bunker window):
#   scenarios that reach net-zero CO2 and whose cumulative net CO2 from 2020
#   to net zero lies within `volume_tolerance_gt` of the budget from 2020
# - temperature-matched set (non-CO2 pathway): median warming at net zero
#   within `temperature_half_width` of the budget temperature
# - AR6 category pool under `scenario_selection: ar6-category` (C1 1.5p50,
#   C3 2p67, C4 2p50), for every term
#
# Cumulatives are trapezoid integrals of the reported years to the
# interpolated net-zero crossing. A budget from 2020 adds observed global net
# CO2 (Global Carbon Budget) of 2020 to the year before its baseline.

# %%
# World rows of the variables behind the adjustments, for every AR6 category.
rcb_scenario_data = {
    var_name: df_all_categories[
        (df_all_categories["Variable"] == shorthand_variables[var_name])
        & (df_all_categories["Region"] == world_key)
    ]
    for var_name in ["CO2", "AFOLU_direct", "AFOLU_indirect"]
}


def _world_frame(var_df):
    """One row per scenario, indexed by (Model, Scenario), sorted year columns."""
    years = sorted([c for c in var_df.columns if c.isdigit()], key=int)
    return var_df.set_index(["Model", "Scenario"])[years].astype(float)


# Net-zero crossing and cumulative CO2 from 2020 to it, from the CO2 series of
# the scenario source (AR6: the reanalysis total CO2).
_co2_world = _world_frame(rcb_scenario_data["CO2"])
scenario_accounts = scenario_accounting(_co2_world)
scenario_metadata = scenario_metadata.join(scenario_accounts, how="left")

# At-net-zero columns derived in the AR6 convention (warming_at_net_zero): the
# AR6 metadata hold 2100 warming for scenarios that reach net zero only under
# the 100 Mt threshold of Table SPM.2.
_derived_net_zero = ar6_at_net_zero(_active_scenario)
if _derived_net_zero is not None:
    scenario_metadata, _changed = apply_derived_net_zero(
        scenario_metadata, _derived_net_zero
    )
    print(f"  Derived at-net-zero columns; net-zero year changed for {len(_changed)}")

# Select the scenario sets of every budget in the RCB file of the active target.
# A target without an RCB file (pathway mode) needs no RCB adjustments.
_rcb_target = config.get("active_target_source", active_target_source)
_rcb_path = config["targets"].get(_rcb_target, {}).get("path")
if _rcb_path:
    with open(project_root / _rcb_path) as f:
        _rcb_yaml = yaml.safe_load(f)
    _set_settings = scenario_set_settings(_rcb_yaml)
    observed_net_co2 = gcb_global_net_co2(
        resolve_source_path(_set_settings["observed_co2_path"])
    )
    budget_sets = build_budget_sets(
        _rcb_yaml,
        scenario_metadata,
        observed_net_co2,
        _set_columns,
        _rcb_yaml.get("rebase_fill_max_years", DEFAULT_REBASE_FILL_MAX_YEARS),
    )
    # The LULUCF terms of a budget start at the baseline year of its source.
    rcb_baseline_years = sorted(
        {source["baseline_year"] for source in _rcb_yaml["rcb_data"].values()}
    )
else:
    _rcb_yaml = None
    budget_sets = {}
    rcb_baseline_years = []
    print(f"  Target '{_rcb_target}' has no RCB file: no RCB adjustments computed.")

# Sources of non_co2.scenario_sources beyond the active one (SCI, ScenarioMIP)
# add their temperature-matched scenarios to the non-CO2 set of every budget.
# AR6 carry-overs count once. An absent workbook leaves its source out.
extra_non_co2_pathways = {}
if budget_sets:
    for _name in _set_settings["non_co2"]["scenario_sources"]:
        if _name == _active_scenario:
            continue
        _inputs = derived_source_inputs(_name, exclude_ar6_duplicates=True)
        if _inputs is None:
            continue
        _extra_meta, extra_non_co2_pathways[_name] = _inputs
        _added = add_source_non_co2_members(
            budget_sets,
            _name,
            _extra_meta,
            get_scenario_source(_name)["metadata_columns"],
            _set_settings["temperature_half_width"],
        )
        print(f"  Non-CO2 scenarios added from {_name}: {_added}")

for _key, _entry in budget_sets.items():
    _record = _entry["record"]
    print(
        f"  {_key}: from 2020 {_record['budget_2020_gt']:.0f} Gt, "
        f"terms n={_record['terms_set']['n']}, "
        f"non-CO2 n={_record['non_co2_set']['n']}"
    )

# Scenarios of any budget set; they are harmonised with the category scenarios.
_rcb_set_members = (
    pd.DataFrame(
        sorted(
            {m for e in budget_sets.values() for m in e["terms"].union(e["non_co2"])}
        ),
        columns=["Model", "Scenario"],
    )
    .drop_duplicates()
    .assign(_in_rcb_set=True)
    if budget_sets
    else pd.DataFrame(columns=["Model", "Scenario", "_in_rcb_set"])
)

# %%
# Keep the AR6 categories paired with a budget label and the scenarios of any budget set
print(f"Filtering to AR6 categories: {_AR6_CATEGORIES_TO_PROCESS} and budget sets")
df_before_filter = len(df)
df = df.merge(_rcb_set_members, on=["Model", "Scenario"], how="left")
df = df[
    df["climate-assessment"].isin(_AR6_CATEGORIES_TO_PROCESS)
    | df["_in_rcb_set"].eq(True)
].drop(columns="_in_rcb_set")
print(f"  Filtered from {df_before_filter} to {len(df)} rows")

# Relabel AR6 categories to RCB scenario labels (e.g. C1 → 1.5p50); others keep theirs
df["climate-assessment"] = (
    df["climate-assessment"].map(_AR6_TO_SCENARIO).fillna(df["climate-assessment"])
)
print(f"  RCB scenario labels: {desired_climate_assessments}")

# Dictionary to store all processed timeseries
all_timeseries = {}

# Median pathway of every budget's scenario set, per timeseries
budget_timeseries = {}

# Harmonised pathway of every scenario, per timeseries
per_scenario_harmonised = {}

# Dictionary to store harmonization comparison data for plotting
harmonization_comparison = {}

# Extract variables needed for NGHGi calculations
print("Extracting variables for NGHGi calculations...")

# Extract and store variables with shorthand names
scenario_data = {}
for var_name, var_path in shorthand_variables.items():
    print(f"  Extracting {var_name}: {var_path}")
    var_df = df[df["Variable"] == var_path].copy()
    var_df = var_df[var_df["Region"] == world_key]

    if len(var_df) == 0:
        raise DataProcessingError(f"No data found for variable {var_name}: {var_path}")

    scenario_data[var_name] = var_df

for timeseries_name in timeseries_specs:
    print(f"\n--- Processing {timeseries_name} ---")

    try:
        # Get year columns and identification variables
        sample_df = next(iter(scenario_data.values()))
        year_cols = [col for col in sample_df.columns if col.isdigit()]
        id_vars = ["climate-assessment", "Model", "Scenario", "Region"]

        # Process each emission category using the NGHGi methodology
        if timeseries_name == "co2-ffi":
            print("  co2-ffi = CO2 - AFOLU_direct")
            merged, year_data = calculate_emission_difference(
                scenario_data["CO2"],
                scenario_data["AFOLU_direct"],
                id_vars,
                year_cols,
                "co2",
                "afolu_direct",
            )
            var_df = pd.concat([merged[id_vars], pd.DataFrame(year_data)], axis=1)
            var_df["Variable"] = timeseries_name
            var_df["Unit"] = scenario_data["CO2"]["Unit"].iloc[0]
            print(f"    Successfully calculated co2-ffi with {len(var_df)} scenarios")

        elif timeseries_name == "co2":
            print("  co2 = CO2_NGHGI")
            var_df = scenario_data["CO2_NGHGI"].copy()
            var_df["Variable"] = timeseries_name
            var_df["Unit"] = scenario_data["CO2_NGHGI"]["Unit"].iloc[0]
            print(f"    Successfully extracted co2 with {len(var_df)} scenarios")

        elif timeseries_name == "all-ghg-ex-co2-lulucf":
            print("  all-ghg-ex-co2-lulucf = KYOTO - AFOLU_direct")
            merged, year_data = calculate_emission_difference(
                scenario_data["KYOTO"],
                scenario_data["AFOLU_direct"],
                id_vars,
                year_cols,
                "kyoto",
                "afolu_direct",
            )
            var_df = pd.concat([merged[id_vars], pd.DataFrame(year_data)], axis=1)
            var_df["Variable"] = timeseries_name
            var_df["Unit"] = scenario_data["KYOTO"]["Unit"].iloc[0]
            print(
                f"    Successfully calculated All-GHG excluding LULUCF "
                f"with {len(var_df)} scenarios"
            )

        elif timeseries_name == "all-ghg":
            print("  all-ghg = KYOTO_NGHGI")
            var_df = scenario_data["KYOTO_NGHGI"].copy()
            var_df["Variable"] = timeseries_name
            print(f"    Successfully extracted All-GHG with {len(var_df)} scenarios")

        else:
            print(
                f"Warning: Emission category '{timeseries_name}' "
                f"not implemented for AR6. Skipping."
            )
            continue

        # Common processing for all categories
        if len(var_df) == 0:
            raise DataProcessingError(f"No data found for {timeseries_name}")

        # Extract unit information
        year_cols = [col for col in var_df.columns if col.isdigit()]
        id_vars = ["climate-assessment", "Model", "Scenario"]
        original_units = extract_unit_from_data(var_df)
        print(f"    Original units: {original_units}")

        # Convert units
        target_unit = "Mt * CO2e"
        print(f"    Converting units: {original_units} to {target_unit}")

        try:
            if original_units == target_unit:
                print("    No conversion needed - units already match")
            else:
                ur = get_default_unit_registry()

                clean_original = _clean_unit_string(original_units)
                clean_target = _clean_unit_string(target_unit)
                conversion_factor = ur(f"1 {clean_original}").to(clean_target).magnitude

                print(f"    Conversion factor: {conversion_factor}")

                # Apply conversion to all year columns
                for year_col in year_cols:
                    var_df[year_col] = (
                        pd.to_numeric(var_df[year_col], errors="coerce")
                        * conversion_factor
                    )

            print(f"    Successfully converted to {target_unit}")
        except Exception as e:
            raise DataProcessingError(f"Unit conversion failed: {e}")
        # Melt to long format and prepare for processing
        melt_id_vars = [col for col in id_vars if col in var_df.columns]
        if "Unit" in var_df.columns:
            melt_id_vars.append("Unit")

        var_long = var_df.melt(
            id_vars=melt_id_vars,
            value_vars=year_cols,
            var_name="year",
            value_name=timeseries_name,
        )
        var_long["year"] = var_long["year"].astype(int)

        # Filter to IAMC timesteps (5-yearly then 10-yearly)
        iamc_years = list(range(2020, 2060, 5)) + list(range(2060, 2110, 10))
        var_long = var_long[var_long["year"].isin(iamc_years)]

        # Standardize column names
        var_long = var_long.rename(columns={"Model": "model", "Scenario": "scenario"})
        var_long["iso3c"] = world_key
        var_long["unit"] = target_unit

        # Interpolate to annual timesteps before harmonisation
        print("    Interpolating to annual timesteps...")
        pathway_index_cols = [
            "climate-assessment",
            "model",
            "scenario",
            "iso3c",
            "unit",
            "year",
        ]
        var_long_annual = interpolate_scenarios_data(
            var_long, interpolation_method, pathway_index_cols
        )

        # Calculate median of original pathways for comparison
        groupby_cols = ["climate-assessment", "iso3c", "unit", "year"]

        def _labelled(frame):
            """Rows of the AR6 categories mapped to a budget label."""
            return frame[frame["climate-assessment"].isin(desired_climate_assessments)]

        var_original_median = (
            _labelled(var_long_annual)
            .groupby(groupby_cols)
            .agg({timeseries_name: "median"})
            .reset_index()
        )
        var_original_median["stage"] = "original"

        # Harmonize individual pathways if historical data available
        hist_data = historical_emissions_data.get(timeseries_name)
        if hist_data is not None:
            print("    Harmonizing individual pathways...")

            # Prepare data for harmonization
            pathway_id_cols = [
                "climate-assessment",
                "model",
                "scenario",
                "iso3c",
                "unit",
            ]
            var_wide = var_long_annual.pivot_table(
                index=pathway_id_cols,
                columns="year",
                values=timeseries_name,
                fill_value=None,
            )
            var_wide = ensure_string_year_columns(var_wide)

            # Broadcast historical data to match each pathway
            historical_broadcast = pd.DataFrame(
                [hist_data.iloc[0] for _ in var_wide.index],
                index=pd.MultiIndex.from_tuples(
                    var_wide.index, names=var_wide.index.names
                ),
            )
            historical_broadcast = ensure_string_year_columns(historical_broadcast)

            # Harmonize WITHOUT cumulative preservation (for comparison)
            var_wide_harmonized_only = harmonize_to_historical_with_convergence(
                var_wide,
                historical_broadcast,
                anchor_year,
                convergence_year,
                preserve_cumulative_peak=False,
            )

            var_long_harmonized_only = var_wide_harmonized_only.reset_index().melt(
                id_vars=pathway_id_cols, var_name="year", value_name=timeseries_name
            )
            var_long_harmonized_only["year"] = var_long_harmonized_only["year"].astype(
                int
            )

            var_harmonized_only_median = (
                _labelled(var_long_harmonized_only)
                .groupby(groupby_cols)
                .agg({timeseries_name: "median"})
                .reset_index()
            )
            var_harmonized_only_median["stage"] = "harmonized_only"

            # Harmonize WITH cumulative preservation (final approach)
            var_wide_harmonized = harmonize_to_historical_with_convergence(
                var_wide,
                historical_broadcast,
                anchor_year,
                convergence_year,
                preserve_cumulative_peak=True,
            )

            var_long_harmonized = var_wide_harmonized.reset_index().melt(
                id_vars=pathway_id_cols, var_name="year", value_name=timeseries_name
            )
            var_long_harmonized["year"] = var_long_harmonized["year"].astype(int)
            print(f"    Harmonized {len(var_wide)} individual pathways")

            # Prepare comparison data for plotting
            var_harmonized_preserved_median = (
                _labelled(var_long_harmonized)
                .groupby(groupby_cols)
                .agg({timeseries_name: "median"})
                .reset_index()
            )
            var_harmonized_preserved_median["stage"] = "harmonized_and_preserved"

            harmonization_comparison[timeseries_name] = pd.concat(
                [
                    var_original_median,
                    var_harmonized_only_median,
                    var_harmonized_preserved_median,
                ],
                ignore_index=True,
            )
        else:
            print("    Skipping harmonisation (no historical data)")
            var_long_harmonized = var_long_annual
            harmonization_comparison[timeseries_name] = None

        # Median pathway of every budget's non-CO2 set, from the same harmonised pathways
        if budget_sets:
            _per_scenario = ensure_string_year_columns(
                var_long_harmonized.pivot_table(
                    index=["model", "scenario"], columns="year", values=timeseries_name
                )
            )
            per_scenario_harmonised[timeseries_name] = _per_scenario
            # Scenarios of other non-CO2 sources have no row here; their
            # non-CO2 enters below.
            _by_budget = median_pathways_by_budget(_per_scenario, budget_sets)
            _by_budget.index = pd.MultiIndex.from_tuples(
                [
                    (ca, q, src, world_key, target_unit, timeseries_name)
                    for ca, q, src in _by_budget.index
                ],
                names=[
                    "climate-assessment",
                    "quantile",
                    "source",
                    "iso3c",
                    "unit",
                    "emission-category",
                ],
            )
            budget_timeseries[timeseries_name] = _by_budget
            print(f"    Median pathways for {len(_by_budget)} budgets")

        # Calculate median across pathways and convert to wide format
        var_grouped = (
            _labelled(var_long_harmonized)
            .groupby(groupby_cols)
            .agg({timeseries_name: "median"})
            .reset_index()
        )
        var_grouped["quantile"] = var_grouped["climate-assessment"].map(
            _SCENARIO_TO_QUANTILE
        )

        timeseries_wide = var_grouped.pivot_table(
            index=["climate-assessment", "quantile", "iso3c"],
            columns="year",
            values=timeseries_name,
            fill_value=None,
        )
        timeseries_wide = ensure_string_year_columns(timeseries_wide)

        # Add source, unit and emission-category to index
        # Remap climate-assessment from scenario label (e.g. "1.5p50") to clean
        # temperature format ("1.5C") to match RCB conventions
        timeseries_wide.index = pd.MultiIndex.from_tuples(
            [
                (
                    _SCENARIO_TO_ASSESSMENT.get(ca, ca),
                    q,
                    active_scenario_source,
                    iso3c,
                    target_unit,
                    timeseries_name,
                )
                for ca, q, iso3c in timeseries_wide.index
            ],
            names=[
                "climate-assessment",
                "quantile",
                "source",
                "iso3c",
                "unit",
                "emission-category",
            ],
        )

        all_timeseries[timeseries_name] = timeseries_wide
        print(f"  TimeseriesDataFrame shape: {timeseries_wide.shape}")

    except Exception as e:
        raise DataProcessingError(f"Error processing {timeseries_name}: {e}")

print("\nVariable processing complete")

# %% [markdown]
# ## Derive co2-lulucf and non-co2 from primary categories
#
# These are computed from the already-harmonized median pathways:
# - co2-lulucf (NGHGI) = co2 - co2-ffi
# - non-co2 = all-ghg - co2
#
# Non-CO2 is also derived per budget, from the median pathways of the budget's
# own scenario set.

# %%
_scenario_index_levels = [
    "climate-assessment",
    "quantile",
    "source",
    "iso3c",
    "unit",
    "emission-category",
]


def _derive_category(minuend_key, subtrahend_key, new_category, timeseries=None):
    """Derive a new category by subtracting two existing timeseries entries."""
    timeseries = all_timeseries if timeseries is None else timeseries
    if minuend_key not in timeseries or subtrahend_key not in timeseries:
        print(
            f"  Cannot derive {new_category}: "
            f"missing {minuend_key} or {subtrahend_key}"
        )
        return None

    a = timeseries[minuend_key].reset_index(level="emission-category", drop=True).copy()
    b = timeseries[subtrahend_key].reset_index(level="emission-category", drop=True)

    common_idx = a.index.intersection(b.index)
    result = a.loc[common_idx].sub(b.loc[common_idx], fill_value=0)

    # Re-attach emission-category
    result = result.reset_index()
    result["emission-category"] = new_category
    result = result.set_index(_scenario_index_levels)

    return result


def _budget_index(by_budget, category):
    """Index levels of the per-budget timeseries."""
    result = by_budget.copy()
    result.index = pd.MultiIndex.from_tuples(
        [(ca, q, src, world_key, "Mt * CO2e", category) for ca, q, src in result.index],
        names=_scenario_index_levels,
    )
    return result


def _harmonise_non_co2(pathways):
    """Annual non-CO2 of another source, harmonised to historical all-GHG minus CO2."""
    iamc_years = [str(y) for y in [*range(2020, 2060, 5), *range(2060, 2110, 10)]]
    annual = annual_pathways(pathways[[y for y in iamc_years if y in pathways]])
    hist_ghg = historical_emissions_data.get("all-ghg")
    hist_co2 = historical_emissions_data.get("co2")
    if hist_ghg is None or hist_co2 is None:
        return annual
    keys = [(m, s, world_key, "Mt * CO2e") for m, s in annual.index]
    index = pd.MultiIndex.from_tuples(
        keys, names=["model", "scenario", "iso3c", "unit"]
    )
    history = hist_ghg.iloc[0].sub(hist_co2.iloc[0])
    harmonised = harmonize_to_historical_with_convergence(
        annual.set_axis(index),
        ensure_string_year_columns(pd.DataFrame([history] * len(index), index=index)),
        anchor_year,
        convergence_year,
        preserve_cumulative_peak=True,
    )
    return harmonised.droplevel(["iso3c", "unit"])


if "co2-lulucf" in derived_to_process or "co2-lulucf" in final_categories:
    print("Deriving co2-lulucf (NGHGI) = co2 - co2-ffi...")
    co2_lulucf = _derive_category("co2", "co2-ffi", "co2-lulucf")
    if co2_lulucf is not None:
        all_timeseries["co2-lulucf"] = co2_lulucf
        print(f"  co2-lulucf shape: {co2_lulucf.shape}")

if "non-co2" in derived_to_process or "non-co2" in final_categories:
    print("Deriving non-co2 = all-ghg - co2...")
    non_co2 = _derive_category("all-ghg", "co2", "non-co2")
    if non_co2 is not None:
        all_timeseries["non-co2"] = non_co2
        print(f"  non-co2 shape: {non_co2.shape}")
    non_co2_by_budget = _derive_category(
        "all-ghg", "co2", "non-co2", timeseries=budget_timeseries
    )
    if non_co2_by_budget is not None and extra_non_co2_pathways:
        # Pooled sources: median over the set of each scenario's non-CO2.
        _pooled = [
            per_scenario_harmonised["all-ghg"].sub(per_scenario_harmonised["co2"]),
            *(_harmonise_non_co2(p) for p in extra_non_co2_pathways.values()),
        ]
        non_co2_by_budget = _budget_index(
            median_pathways_by_budget(pd.concat(_pooled), budget_sets), "non-co2"
        )
    if non_co2_by_budget is not None:
        budget_timeseries["non-co2"] = non_co2_by_budget

# %% [markdown]
# ## Pre-compute RCB adjustment scalars per budget
#
# Scalars per budget, from the members of its volume-matched set (or AR6
# category) that reach net zero, each integrated to its own net-zero crossing:
# - `bm_lulucf_median_from`: one entry per RCB baseline year, the median BM
#   LULUCF (AFOLU|Direct) from that year to net zero
# - `convention_gap_median_from`: one entry per RCB baseline year, the median
#   convention gap (observed NGHGI minus Direct up to the splice year,
#   Indirect after it) from that year to net zero
# - the provenance of the sets (`terms_set`, `non_co2_set`, `consistency`)
# - `bunkers`: the reporters behind the bunker share, by source and model
#
# Bunker share: every scenario of `bunkers.scenario_sources` that reports
# international aviation and shipping and reaches net zero (AR6: 0.6 x
# Aviation plus Maritime; SCI: its international bunker variables).
# `bunker_share_reporters.csv` holds each reporter's cumulative bunkers and net
# CO2 from each possible start year to its net zero, and
# `scenario_set_{source}_{label}.csv` the cumulative net CO2 of each set member.
# The RCB step adds observed bunkers to the last observed year, then the median
# reporter share times the median net CO2 of the set from the next year to net
# zero. An AR6 category budget applies the same share to its category set.

# %%
print("\n--- Pre-computing RCB adjustment scalars per budget ---")

# Load NGHGI world timeseries for historical convention gap computation.
# Only needed for co2/all-ghg (NGHGI corrections); co2-ffi uses BM LULUCF
# from scenario data (AFOLU_direct) which is convention-independent.
nghgi_world_path = (
    intermediate_dir.parent / "emissions" / "world_co2-lulucf_timeseries.csv"
)
nghgi_world_available = nghgi_world_path.exists()

if nghgi_world_available:
    nghgi_world_df = pd.read_csv(nghgi_world_path).set_index("source")
    nghgi_splice_year = max(int(c) for c in nghgi_world_df.columns if c.isdigit())
    print(f"  Loaded NGHGI world LULUCF (splice year: {nghgi_splice_year})")
else:
    print(
        f"  NGHGI world LULUCF not found at: {nghgi_world_path}\n"
        f"  Convention gap will be zero (fine for co2-ffi; run notebook 107 for co2/all-ghg)."
    )

# Bunker reporters of every configured scenario source: every scenario that
# reports bunkers, without historical vetting, with the model's own net CO2.
share_sources = {}
if budget_sets:
    _bunker_sources = _set_settings["bunkers"]["scenario_sources"]
    for _name in _bunker_sources:
        _loaded = bunker_reporter_series(_name, pool=_bunker_sources)
        if _loaded is not None:
            share_sources[_name] = _loaded
    share_table = bunker_share_table(share_sources)
    share_table.to_csv(intermediate_dir / "bunker_share_reporters.csv", index=False)
    # The share from the first possible start year must clear the guards.
    share_info = bunker_share(
        share_table,
        SHARE_START_YEARS[0],
        _set_settings["bunkers"]["min_reporters"],
        _set_settings["bunkers"]["min_families"],
        _set_settings["bunkers"]["min_runs_per_family"],
    )
    print(
        f"  Bunker reporters reaching net zero: {share_info['n_by_source']}, "
        f"families {share_info['families']}"
    )

_direct_world = _world_frame(rcb_scenario_data["AFOLU_direct"])
_indirect_world = _world_frame(rcb_scenario_data["AFOLU_indirect"])
rcb_adjustments = {}

for budget_key, entry in budget_sets.items():
    spec = entry["spec"]
    terms = entry["terms"]
    crossings = scenario_metadata.loc[terms, NET_ZERO_CROSSING].dropna()
    members = crossings.index.intersection(_direct_world.index)
    if members.empty:
        raise DataProcessingError(
            f"Budget '{budget_key}': no AFOLU|Direct data for its {len(terms)} "
            f"scenarios"
        )

    # Per-scenario BM LULUCF and convention gap from each baseline year, then the median
    bm_from, gap_from = {}, {}
    for baseline_year in rcb_baseline_years:
        bm_from[baseline_year] = float(
            pd.Series(
                [
                    integrate(_direct_world.loc[k], baseline_year, crossings[k])
                    for k in members
                ]
            ).median()
        )
        gap_from[baseline_year] = 0.0
        if nghgi_world_available:
            gap_members = members.intersection(_indirect_world.index)
            gap_from[baseline_year] = float(
                pd.Series(
                    [
                        convention_gap_from_baseline(
                            nghgi_lulucf=nghgi_world_df.iloc[0],
                            bm_direct=_direct_world.loc[k],
                            indirect=_indirect_world.loc[k],
                            baseline_year=baseline_year,
                            nz_year=crossings[k],
                            splice_year=nghgi_splice_year,
                        )
                        for k in gap_members
                    ]
                ).median()
            )

    # Members with their net-zero crossings and net CO2 from each share start year
    _members = scenario_metadata.loc[members].copy()
    for year in SHARE_START_YEARS:
        _members[f"co2_from_{year}"] = [
            integrate(_co2_world.loc[k], year, crossings[k]) for k in members
        ]
    _members.reset_index().to_csv(
        intermediate_dir / f"scenario_set_{spec.file_key}.csv", index=False
    )

    rcb_adjustments[budget_key] = {
        **entry["record"],
        "bunkers": {
            "rule": (
                "share of net CO2 of the "
                + (
                    f"AR6 category {entry['category']}"
                    if entry["category"]
                    else "volume-matched"
                )
                + " set after the last observed year"
            ),
            "reporters": share_info["n"],
            "reporters_by_source": share_info["n_by_source"],
            "families": sorted(share_info["families"]),
            "excluded_families": share_info["excluded_families"],
            "components": {
                s: dict(get_scenario_source(s)["bunkers"].get("components", {}))
                for s in share_sources
            },
        },
        "bm_lulucf_median_from": {int(y): round(v, 1) for y, v in bm_from.items()},
        "convention_gap_median_from": {
            int(y): round(v, 1) for y, v in gap_from.items()
        },
    }

    print(
        f"  {budget_key}: n={len(members)}, "
        f"BM LULUCF from baseline (Mt): {', '.join(f'{y}: {v:.0f}' for y, v in bm_from.items())}, "
        f"gap (Mt): {', '.join(f'{y}: {v:.0f}' for y, v in gap_from.items())}"
    )

# Save RCB adjustments as YAML
if rcb_adjustments:
    rcb_adj_path = intermediate_dir / "rcb_scenario_adjustments.yaml"
    with open(rcb_adj_path, "w") as f:
        yaml.dump(rcb_adjustments, f, default_flow_style=False, sort_keys=False)
    print(f"\nSaved RCB adjustment scalars to: {rcb_adj_path}")


# %% [markdown]
# ## Output

# %%
print("\n--- Saving TimeseriesDataFrames ---")

for timeseries_name, timeseries_df in all_timeseries.items():
    if timeseries_name in final_categories:
        timeseries_df = ensure_string_year_columns(timeseries_df)
        output_path = intermediate_dir / f"scenarios_{timeseries_name}_timeseries.csv"
        timeseries_df.reset_index().to_csv(output_path, index=False)
        print(f"Saved {timeseries_name} to: {output_path}")
        # Per-budget medians feed the non-CO2 pathway paired with each budget
        if timeseries_name in budget_timeseries:
            budget_path = (
                intermediate_dir
                / f"scenarios_{timeseries_name}_by_budget_timeseries.csv"
            )
            budget_df = ensure_string_year_columns(budget_timeseries[timeseries_name])
            budget_df.reset_index().to_csv(budget_path, index=False)
            print(f"Saved {timeseries_name} per budget to: {budget_path}")
    else:
        print(f"  Skipped {timeseries_name} (not in final categories)")

# %% [markdown]
# ## Plot Harmonization Comparison

# %%
# Plot comparison of original, harmonized, and harmonized+preserved medians
print("\n--- Generating Harmonization Comparison Plots ---")

for timeseries_name, comp_data in harmonization_comparison.items():
    if comp_data is None or timeseries_name not in final_categories:
        continue

    print(f"Plotting harmonization comparison for {timeseries_name}...")

    # Filter to world region only
    world_comp = comp_data[comp_data["iso3c"] == world_key].copy()

    if world_comp.empty:
        print(f"  No world data for {timeseries_name}, skipping")
        continue

    # Get units
    units = (
        world_comp["unit"].unique()[0] if "unit" in world_comp.columns else "Mt * CO2e"
    )

    # Climate assessments
    climate_assessments = world_comp["climate-assessment"].unique()
    palette = dict(
        zip(
            climate_assessments,
            plt.cm.tab10(np.linspace(0, 1, len(climate_assessments))),
        )
    )

    # Stages
    stage_styles = {
        "original": {"linestyle": ":", "alpha": 0.5, "linewidth": 1.5},
        "harmonized_only": {"linestyle": "--", "alpha": 0.7, "linewidth": 2},
        "harmonized_and_preserved": {"linestyle": "-", "alpha": 1.0, "linewidth": 2.5},
    }

    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(15, 8))

    # Plot each climate assessment with all three stages
    for ca in climate_assessments:
        ca_data = world_comp[world_comp["climate-assessment"] == ca]

        for stage, style in stage_styles.items():
            stage_data = ca_data[ca_data["stage"] == stage]

            if not stage_data.empty:
                label = f"{ca} - {stage.replace('_', ' ')}"
                ax.plot(
                    stage_data["year"],
                    stage_data[timeseries_name],
                    label=label,
                    color=palette[ca],
                    **style,
                )

    # Add vertical line at anchor year
    ax.axvline(
        x=anchor_year,
        color="red",
        linestyle=":",
        alpha=0.5,
        linewidth=2,
        label=f"Anchor year ({anchor_year})",
    )

    # Formatting
    ax.set_ylabel(f"Emissions ({units})", fontsize=12)
    ax.set_xlabel("Year", fontsize=12)
    ax.set_title(
        f"{timeseries_name} - Harmonization Comparison\n"
        "Original vs Harmonized vs Harmonized+Preserved "
        "(median pathways)",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    # Set x-axis ticks
    all_years = world_comp["year"].unique()
    years_sorted = sorted(all_years)
    tick_years = years_sorted[::10]
    ax.set_xticks(tick_years)
    ax.tick_params(axis="x", rotation=45)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.show()

    print(f"  Generated harmonization comparison plot for {timeseries_name}")

# %% [markdown]
# ## Plot Scenario Emissions Data

# %%
# Create plots for each timeseries that was saved
print("\n--- Generating Scenario Emissions Plots ---")

for timeseries_name, timeseries_df in all_timeseries.items():
    # Only plot timeseries that are in the final categories list
    if timeseries_name not in final_categories:
        continue
    print(f"Plotting {timeseries_name}...")

    # Convert to long format for plotting
    timeseries_df = ensure_string_year_columns(timeseries_df)
    timeseries_long = timeseries_df.reset_index().melt(
        id_vars=[
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ],
        var_name="year",
        value_name=timeseries_name,
    )

    # Convert year column to integer for proper plotting
    timeseries_long["year"] = timeseries_long["year"].astype(int)

    # Get the units from the MultiIndex
    units = timeseries_df.index.get_level_values("unit").unique()[0]

    # Pick a color palette for climate assessments
    climate_assessments = timeseries_long["climate-assessment"].unique()
    palette = dict(
        zip(
            climate_assessments,
            plt.cm.tab10(np.linspace(0, 1, len(climate_assessments))),
        )
    )

    # Create the plot
    fig, ax = plt.subplots(1, 1, figsize=(15, 8))

    # Plot one line per (climate-assessment, quantile). Pooling quantiles into
    # a single ax.plot call interleaves year-by-year rows and produces a
    # sawtooth between the quantile trajectories.
    for ca in climate_assessments:
        ca_data = timeseries_long[timeseries_long["climate-assessment"] == ca]
        if ca_data.empty:
            continue
        for quantile, q_data in ca_data.groupby("quantile"):
            q_sorted = q_data.sort_values("year")
            n_q = ca_data["quantile"].nunique()
            label = f"{ca}" if n_q == 1 else f"{ca} (q={quantile})"
            ax.plot(
                q_sorted["year"],
                q_sorted[timeseries_name],
                label=label,
                color=palette[ca],
                alpha=0.9,
                linewidth=2,
                linestyle="-",
            )

    # Customize the plot
    ax.set_ylabel(f"Emissions ({units})", fontsize=12)
    ax.set_title(
        f"{timeseries_name}\nsource: {active_target_source}",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(title="Climate Assessment", bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.grid(True, alpha=0.3)

    # Set x-axis ticks to show every 10th year and rotate labels
    all_years = timeseries_long["year"].unique()
    years_sorted = sorted(all_years)
    tick_years = years_sorted[::10]
    ax.set_xticks(tick_years)
    ax.tick_params(axis="x", rotation=45)

    # Add some styling
    # Remove top and right spines for cleaner look
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.show()

    print(f"Generated plot for {timeseries_name}")

print("\nScenario data processing completed successfully!")
# Only report timeseries that were saved (those in final_categories)
saved_timeseries = [name for name in all_timeseries.keys() if name in final_categories]
print(f"Saved {len(saved_timeseries)} timeseries: {saved_timeseries}")

# %%
