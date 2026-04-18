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
from fair_shares.library.preprocessing import emissions_path
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
        "emissions": "primap-202503",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "unu-wider-2025",
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

# 1:1 mapping from AR6 category to RCB scenario label.
# Each AR6 category corresponds to exactly one RCB scenario.
# The scenario label encodes temperature target + probability (e.g. "1.5p50").
# Used internally during processing; converted to clean (assessment, quantile)
# format at output time via _SCENARIO_TO_ASSESSMENT / _SCENARIO_TO_QUANTILE.
_AR6_TO_SCENARIO = {"C1": "1.5p50", "C2": "2p83", "C3": "2p66"}
_AR6_CATEGORIES_TO_PROCESS = list(_AR6_TO_SCENARIO.keys())
desired_climate_assessments = list(_AR6_TO_SCENARIO.values())

# Output mappings: split scenario label into clean climate-assessment + quantile
# to match RCB format (e.g. climate-assessment="1.5C", quantile=0.5)
_SCENARIO_TO_ASSESSMENT = {"1.5p50": "1.5C", "2p83": "2C", "2p66": "2C"}
_SCENARIO_TO_QUANTILE = {"1.5p50": 0.5, "2p83": 0.83, "2p66": 0.66}

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
# Process the scenario source
print(f"Processing {active_target_source} scenarios...")
df = process_iamc_zip(project_root / scenario_path)

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
    emiss_path = emissions_path(
        emiss_intermediate_dir, category, active_lulucf_source
    )
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

# Filter to AR6 categories that have a corresponding RCB scenario
print(f"Filtering to AR6 categories: {_AR6_CATEGORIES_TO_PROCESS}")
df_before_filter = len(df)
df = df[df["climate-assessment"].isin(_AR6_CATEGORIES_TO_PROCESS)].copy()
print(f"  Filtered from {df_before_filter} to {len(df)} rows")

# Relabel AR6 categories to RCB scenario labels (e.g. C1 → 1.5p50)
df["climate-assessment"] = df["climate-assessment"].map(_AR6_TO_SCENARIO)
print(
    f"  Relabelled to RCB scenario labels: {sorted(df['climate-assessment'].unique())}"
)

# Dictionary to store all processed timeseries
all_timeseries = {}

# Dictionary to store harmonization comparison data for plotting
harmonization_comparison = {}

# Extract variables needed for NGHGi calculations
print("Extracting variables for NGHGi calculations...")

# Define shorthand dictionary for variables from Gidden et al. 2023
shorthand_variables = {
    "CO2": "AR6 Reanalysis|OSCARv3.2|Emissions|CO2",
    "CO2_NGHGI": (
        "AR6 Reanalysis|OSCARv3.2|Emissions|CO2 - Direct and Indirect Fluxes"
    ),
    "AFOLU_direct": ("AR6 Reanalysis|OSCARv3.2|Emissions|CO2|AFOLU|Direct"),
    "AFOLU_indirect": ("AR6 Reanalysis|OSCARv3.2|Emissions|CO2|AFOLU|Indirect"),
    "KYOTO": "AR6 Reanalysis|OSCARv3.2|Emissions|Kyoto Gases",
    "KYOTO_NGHGI": (
        "AR6 Reanalysis|OSCARv3.2|Emissions|Kyoto Gases - Direct and Indirect Fluxes"
    ),
}

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
        var_original_median = (
            var_long_annual.groupby(groupby_cols)
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
                var_long_harmonized_only.groupby(groupby_cols)
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
                var_long_harmonized.groupby(groupby_cols)
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

        # Calculate median across pathways and convert to wide format
        var_grouped = (
            var_long_harmonized.groupby(groupby_cols)
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

# %%
_scenario_index_levels = [
    "climate-assessment",
    "quantile",
    "source",
    "iso3c",
    "unit",
    "emission-category",
]


def _derive_category(minuend_key, subtrahend_key, new_category):
    """Derive a new category by subtracting two existing all_timeseries entries."""
    if minuend_key not in all_timeseries or subtrahend_key not in all_timeseries:
        print(
            f"  Cannot derive {new_category}: "
            f"missing {minuend_key} or {subtrahend_key}"
        )
        return None

    a = (
        all_timeseries[minuend_key]
        .reset_index(level="emission-category", drop=True)
        .copy()
    )
    b = all_timeseries[subtrahend_key].reset_index(level="emission-category", drop=True)

    common_idx = a.index.intersection(b.index)
    result = a.loc[common_idx].sub(b.loc[common_idx], fill_value=0)

    # Re-attach emission-category
    result = result.reset_index()
    result["emission-category"] = new_category
    result = result.set_index(_scenario_index_levels)

    return result


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

# %% [markdown]
# ## Pre-compute RCB adjustment scalars per AR6 category
#
# For RCB-based allocations, the library needs per-AR6-category adjustment scalars
# to convert IPCC RCBs (BM convention) to NGHGI-consistent budgets. These are
# pre-computed here from the Gidden scenario data so that the library never needs
# to handle the Direct/Indirect AFOLU decomposition directly.
#
# Scalars computed per AR6 category:
# - `bm_lulucf_cumulative_median`: median of per-scenario cumulative BM LULUCF
#   (= AFOLU|Direct), each integrated to its own NZ year
# - `convention_gap_median`: median of per-scenario cumulative convention gap
#   (historical NGHGI-Direct + future Indirect), each integrated to its own NZ year
# - `nz_year_median`, `nz_year_min`, `nz_year_max`: net-zero year statistics
# - `n_scenarios`: number of scenarios in the category

# %%
print("\n--- Pre-computing RCB adjustment scalars per scenario category ---")

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

# Compute per-scenario-category adjustment scalars
rcb_adjustments = {}

for ar6_cat in desired_climate_assessments:
    # Filter to scenarios in this AR6 category
    cat_direct = scenario_data["AFOLU_direct"][
        scenario_data["AFOLU_direct"]["climate-assessment"] == ar6_cat
    ]
    cat_total = scenario_data["CO2"][
        scenario_data["CO2"]["climate-assessment"] == ar6_cat
    ]

    if cat_direct.empty or cat_total.empty:
        print(f"  {ar6_cat}: no data, skipping")
        continue

    sample_df = next(iter(scenario_data.values()))
    year_cols = [col for col in sample_df.columns if col.isdigit()]
    sorted_year_cols = sorted(year_cols, key=int)

    # --- Per-scenario NZ years (from total CO2 BM crossing zero) ---
    total_indexed = cat_total.set_index(["Model", "Scenario"])[sorted_year_cols]
    nz_years_dict = {}
    for scenario_key in total_indexed.index:
        row = total_indexed.loc[scenario_key]
        for yc in sorted_year_cols:
            if row[yc] <= 0:
                nz_years_dict[scenario_key] = int(yc)
                break
        else:
            nz_years_dict[scenario_key] = 2100

    if not nz_years_dict:
        print(f"  {ar6_cat}: no NZ years computed, skipping")
        continue

    nz_series = pd.Series(nz_years_dict, dtype=int)

    # --- Per-scenario cumulative BM LULUCF (= Direct) ---
    direct_indexed = cat_direct.set_index(["Model", "Scenario"])[sorted_year_cols]
    common_scenarios = direct_indexed.index.intersection(
        pd.MultiIndex.from_tuples(nz_series.index)
    )

    bm_lulucf_per_scenario = []
    for sk in common_scenarios:
        nz = nz_series[sk]
        cols = [str(y) for y in range(2020, nz + 1) if str(y) in sorted_year_cols]
        if cols:
            bm_lulucf_per_scenario.append(float(direct_indexed.loc[sk, cols].sum()))

    bm_median = (
        float(pd.Series(bm_lulucf_per_scenario).median())
        if bm_lulucf_per_scenario
        else 0.0
    )

    # --- Per-scenario convention gap (historical NGHGI-Direct + future Indirect) ---
    gap_median = 0.0
    if nghgi_world_available:
        cat_indirect = scenario_data["AFOLU_indirect"][
            scenario_data["AFOLU_indirect"]["climate-assessment"] == ar6_cat
        ]
        indirect_indexed = cat_indirect.set_index(["Model", "Scenario"])[
            sorted_year_cols
        ]
        common_all = common_scenarios.intersection(indirect_indexed.index)

        per_scenario_gaps = []
        for sk in common_all:
            nz = nz_series[sk]
            hist_end = min(nghgi_splice_year, nz)

            # Historical: NGHGI - Direct
            from fair_shares.library.utils.data.nghgi import (
                compute_cumulative_emissions,
            )

            nghgi_hist = compute_cumulative_emissions(nghgi_world_df, 2020, hist_end)
            hist_cols = [
                str(y) for y in range(2020, hist_end + 1) if str(y) in sorted_year_cols
            ]
            direct_hist = (
                float(direct_indexed.loc[sk, hist_cols].sum()) if hist_cols else 0.0
            )
            hist_gap = nghgi_hist - direct_hist

            # Future: Indirect only (Direct cancels in the gap)
            future_gap = 0.0
            if nz > nghgi_splice_year:
                future_cols = [
                    str(y)
                    for y in range(nghgi_splice_year + 1, nz + 1)
                    if str(y) in sorted_year_cols
                ]
                if future_cols:
                    future_gap = float(indirect_indexed.loc[sk, future_cols].sum())

            per_scenario_gaps.append(hist_gap + future_gap)

        gap_median = (
            float(pd.Series(per_scenario_gaps).median()) if per_scenario_gaps else 0.0
        )

    # Store results
    rcb_adjustments[ar6_cat] = {
        "bm_lulucf_cumulative_median": round(bm_median, 1),
        "convention_gap_median": round(gap_median, 1),
        "nz_year_median": int(nz_series.median()),
        "nz_year_min": int(nz_series.min()),
        "nz_year_max": int(nz_series.max()),
        "n_scenarios": len(nz_series),
        "n_reaching_nz": int((nz_series < 2100).sum()),
    }

    print(
        f"  {ar6_cat}: n={len(nz_series)}, NZ_med={int(nz_series.median())}, "
        f"BM_LULUCF={bm_median:.0f} Mt, gap={gap_median:.0f} Mt"
    )

# Save RCB adjustments as YAML
if rcb_adjustments:
    rcb_adj_path = intermediate_dir / "rcb_scenario_adjustments.yaml"
    with open(rcb_adj_path, "w") as f:
        yaml.dump(rcb_adjustments, f, default_flow_style=False, sort_keys=False)
    print(f"\nSaved RCB adjustment scalars to: {rcb_adj_path}")


# %% [markdown]
# ## Pre-compute baseline-shift LULUCF medians per AR6 category
#
# For RCB baseline-year shifting, `process_rcb_to_2020_baseline()` needs the
# year-by-year median AFOLU|Direct timeseries (BM LULUCF proxy) per AR6
# category. Pre-computing these here avoids loading the raw Gidden Excel at
# runtime in the library.

# %%
print("\n--- Pre-computing baseline-shift LULUCF median timeseries ---")

sample_df = next(iter(scenario_data.values()))
year_cols = sorted([col for col in sample_df.columns if col.isdigit()], key=int)

for ar6_cat in desired_climate_assessments:
    cat_direct = scenario_data["AFOLU_direct"][
        scenario_data["AFOLU_direct"]["climate-assessment"] == ar6_cat
    ]

    if cat_direct.empty:
        print(f"  {ar6_cat}: no AFOLU_direct data, skipping")
        continue

    # Year-by-year median across scenarios
    median_vals = cat_direct[year_cols].median(axis=0)

    source_label = f"gidden_direct_{ar6_cat}"
    median_df = pd.DataFrame(
        [median_vals.values],
        columns=year_cols,
        index=pd.Index([source_label], name="source"),
    )

    out_path = intermediate_dir / f"lulucf_shift_median_{ar6_cat}.csv"
    median_df.reset_index().to_csv(out_path, index=False)
    print(f"  {ar6_cat}: saved {len(cat_direct)} scenarios -> {out_path}")

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
