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
# # AR6 (Gidden et al. 2023) Scenarios Data Preprocessing Script
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
    derive_probability_based_categories,
    determine_processing_categories,
    ensure_string_year_columns,
    get_default_unit_registry,
    get_world_totals_timeseries,
    harmonize_to_historical_with_convergence,
    interpolate_scenarios_data,
    normalize_metadata_column,
    process_iamc_zip,
)
from fair_shares.library.utils.units import _clean_unit_string

# %% tags=["parameters"]
emission_category = None
active_target_source = None
active_emissions_source = None
active_gdp_source = None
active_population_source = None
active_gini_source = None
# Available MAGICC exceedance probability columns by temperature target
MAGICC_PROBABILITY_COLUMNS = {
    "1.5C": "Exceedance Probability 1.5C (MAGICCv7.5.3)",
    "2C": "Exceedance Probability 2C (MAGICCv7.5.3)",
}


def get_probability_column(temperature_target: str) -> str:
    """
    Get the MAGICC probability column name for a given temperature target.

    Parameters
    ----------
    temperature_target : str
        Temperature target: "1.5C" or "2C"

    Returns
    -------
    str
        Column name for the exceedance probability
    """
    temp_key = str(temperature_target).strip()
    if temp_key not in MAGICC_PROBABILITY_COLUMNS:
        raise ConfigurationError(
            f"Unsupported temperature_target '{temperature_target}'. "
            f"Choose one of: {list(MAGICC_PROBABILITY_COLUMNS.keys())}"
        )
    return MAGICC_PROBABILITY_COLUMNS[temp_key]


# Additional climate assessments that aren't in the original metadata
# Each spec can define:
#   - label: Custom label for the derived category (e.g., "peak_1p5_67")
#   - temperature_target: "1.5C" or "2C" (automatically selects correct column)
#   - max_exceedance_probability: Upper bound (<=) for exceedance probability
#   - min_exceedance_probability: Lower bound (>=) for exceedance probability
#     (optional)
#   - source_categories: List of source categories to filter from
#     (optional, uses all if not specified)
probability_category_specs = [
    {
        "label": "peak_1p5_33",
        "temperature_target": "1.5C",
        # 33% chance of meeting 1.5 degC peak, <=66% exceedance probability
        "max_exceedance_probability": 0.66,
    },
]

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


# Get active sources and scenario configuration
active_target_source = config["active_target_source"]
scenario_config = config["targets"][active_target_source]
scenario_path = scenario_config["path"]
scenario_data_parameters = scenario_config["data_parameters"]
available_categories = scenario_data_parameters.get("available_categories", [])
interpolation_method = scenario_data_parameters.get("interpolation_method")
world_key = scenario_data_parameters.get("world_key")

# Extract config values
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
supported_categories = ["co2-ffi", "all-ghg-ex-co2-lulucf", "all-ghg"]

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
create_all_other = processing_info["create_all_other"]
final_categories = processing_info["final"]

print(f"Processing categories: {processing_categories}")
print(f"Create all-other: {create_all_other}")
print(f"Final categories: {final_categories}")

# Filter to only process supported categories
timeseries_specs = processing_categories

# Process probability_category_specs to convert temperature_target to column names
# and collect all required metadata columns
processed_probability_specs = []
probability_metadata_columns = set()

if probability_category_specs:
    for spec in probability_category_specs:
        processed_spec = spec.copy()

        # Convert temperature_target to actual column name
        if "temperature_target" in processed_spec:
            temperature_target = processed_spec.pop("temperature_target")
            probability_column = get_probability_column(temperature_target)
            processed_spec["probability_columns"] = [probability_column]
            # Track which metadata columns we need
            probability_metadata_columns.add(probability_column)
        elif "probability_columns" in processed_spec:
            # If probability_columns already specified, use as-is
            for col in processed_spec["probability_columns"]:
                probability_metadata_columns.add(col)
        else:
            raise ConfigurationError(
                "Each probability_category_spec must specify either "
                "'temperature_target' (1.5C or 2C) or 'probability_columns'"
            )

        processed_probability_specs.append(processed_spec)

# Convert metadata columns set to sorted list for use in process_iamc_zip
probability_metadata_columns = sorted(
    {normalize_metadata_column(col) for col in probability_metadata_columns}
)

# Extract derived climate assessment labels
derived_climate_assessments = [spec["label"] for spec in processed_probability_specs]

# Always include the canonical AR6 categories plus any probability-derived ones.
default_climate_assessments = ["C1", "C2", "C3", "C4"]
extra_climate_assessments = [
    ca for ca in derived_climate_assessments if ca not in default_climate_assessments
]
desired_climate_assessments = default_climate_assessments + extra_climate_assessments

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
df = process_iamc_zip(
    project_root / scenario_path,
    metadata_columns=probability_metadata_columns,
)

if processed_probability_specs:
    print("Applying probability-based climate assessment filters...")
    df_before = len(df)
    df = derive_probability_based_categories(df, processed_probability_specs)
    df_after = len(df)
    print(f"  Added {df_after - df_before} rows from probability-based categories")

    # Verify derived categories were created
    if "Category" in df.columns:
        categories_after = df["Category"].unique()
        missing_derived = [
            ca for ca in derived_climate_assessments if ca not in categories_after
        ]
        if missing_derived:
            print(f"  WARNING: Derived categories not found in data: {missing_derived}")
        else:
            print(f"  All derived categories present: {derived_climate_assessments}")

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
    emiss_path = emiss_intermediate_dir / f"emiss_{category}_timeseries.csv"
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


def extract_unit_from_data(var_df, timeseries_name, df_all):
    """Extract unit information from processed or original dataframe."""
    if "Unit" in var_df.columns:
        unique_units = var_df["Unit"].unique()
        if len(unique_units) == 1:
            return unique_units[0]
        else:
            raise DataProcessingError(f"Multiple units found: {unique_units}")

    # Map timeseries names to AR6 variable names
    variable_mapping = {
        "all-ghg": (
            "AR6 Reanalysis|OSCARv3.2|Emissions|"
            "Kyoto Gases - Direct and Indirect Fluxes"
        ),
        "co2-ffi": (
            "AR6 Reanalysis|OSCARv3.2|Emissions|CO2 - Direct and Indirect Fluxes"
        ),
        "all-ghg-ex-co2-lulucf": (
            "AR6 Reanalysis|OSCARv3.2|Emissions|"
            "Kyoto Gases - Direct and Indirect Fluxes"
        ),
    }

    dataset_variable = variable_mapping.get(timeseries_name)
    if not dataset_variable:
        raise DataProcessingError(f"Unknown timeseries_name: {timeseries_name}")

    original_var_units = df_all[df_all["Variable"] == dataset_variable]["Unit"].unique()

    if len(original_var_units) == 1:
        return original_var_units[0]
    else:
        raise DataProcessingError(
            f"Could not determine unique units: {original_var_units}"
        )


# %% [markdown]
# ## Analysis

# %%
# Process AR6 scenarios data for all timeseries
print(f"Processing scenarios data from {active_target_source}")

# Rename 'Category' to 'climate-assessment' for clarity
df = df.rename(columns={"Category": "climate-assessment"})

# Filter to only desired climate assessments early (before processing)
print(f"Filtering to desired climate assessments: {desired_climate_assessments}")
df_before_filter = len(df)
df = df[df["climate-assessment"].isin(desired_climate_assessments)].copy()
print(f"  Filtered from {df_before_filter} to {len(df)} rows")

# Verify all desired categories are present
categories_present = df["climate-assessment"].unique()
missing = [ca for ca in desired_climate_assessments if ca not in categories_present]
if missing:
    print(f"  WARNING: Desired categories not found in data: {missing}")
else:
    print(f"  All desired categories present: {sorted(categories_present)}")

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
        original_units = extract_unit_from_data(var_df, timeseries_name, df)
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
        var_grouped["quantile"] = 0.5

        timeseries_wide = var_grouped.pivot_table(
            index=["climate-assessment", "quantile", "iso3c"],
            columns="year",
            values=timeseries_name,
            fill_value=None,
        )
        timeseries_wide = ensure_string_year_columns(timeseries_wide)

        # Add source, unit and emission-category to index
        # Source is the target source (e.g., 'ar6') to match structure with rcb-pathways
        timeseries_wide.index = pd.MultiIndex.from_tuples(
            [
                (ca, q, active_target_source, iso3c, target_unit, timeseries_name)
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
# ## Generate "all-other" timeseries

# %%
if create_all_other and "all-ghg" in all_timeseries:
    print("Creating 'all-other' timeseries (all-ghg minus requested category)")

    # Prepare dataframes for subtraction
    all_ghg_df = all_timeseries["all-ghg"]
    subtract_df = all_timeseries[emission_category]

    # Drop emission-category from index temporarily
    all_other_df = all_ghg_df.reset_index(level="emission-category", drop=True).copy()
    df_subtract = subtract_df.reset_index(level="emission-category", drop=True)

    # Align indices and subtract
    common_indices = all_other_df.index.intersection(df_subtract.index)
    all_other_df = (
        all_other_df.loc[common_indices]
        .sub(df_subtract.loc[common_indices], fill_value=0)
        .clip(lower=0)
    )

    # Restore multi-index with 'all-other' as emission-category
    all_other_df = all_other_df.reset_index()
    all_other_df["emission-category"] = "all-other"
    all_other_df = all_other_df.set_index(
        [
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ]
    )

    all_timeseries["all-other"] = all_other_df
    print(f"Created 'all-other' timeseries with shape: {all_other_df.shape}")

    # Print summary statistics
    all_other_long = (
        all_other_df.reset_index(level=["unit", "emission-category"], drop=True)
        .stack()
        .reset_index()
    )
    all_other_long.columns = [
        "climate-assessment",
        "quantile",
        "iso3c",
        "year",
        "all-other",
    ]
    world_all_other = all_other_long[all_other_long["iso3c"] == world_key]

    if not world_all_other.empty:
        latest_year = world_all_other["year"].max()
        latest_value = world_all_other["all-other"].iloc[-1]
        peak_value = world_all_other["all-other"].max()
        print("  World 'all-other' emissions:")
        print(f"    Latest ({latest_year}): {latest_value:.1f} Mt * CO2e")
        print(f"    Peak: {peak_value:.1f} Mt * CO2e")
elif not create_all_other:
    print("'all-other' not created (processing all-ghg* categories)")
elif "all-ghg" not in all_timeseries:
    raise DataProcessingError(
        "'all-ghg' timeseries required but not present for 'all-other' creation"
    )

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

    # Plot scenarios
    for ca in climate_assessments:
        ca_data = timeseries_long[timeseries_long["climate-assessment"] == ca]

        if not ca_data.empty:
            # Plot scenario
            ax.plot(
                ca_data["year"],
                ca_data[timeseries_name],
                label=f"{ca}",
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
