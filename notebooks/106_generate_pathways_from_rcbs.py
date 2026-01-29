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
# # Generate Pathways from RCBs
#
# This notebook converts Remaining Carbon Budgets (RCBs) into emission pathways
# using a configurable pathway generator (default: exponential decay).
#
# **Input**: Processed RCBs from `100_data_preprocess_rcbs.py`
# **Output**: World emission pathways in the same format as AR6 scenarios
#
# The generated pathways can be used with pathway allocation approaches like
# `equal-per-capita`, `per-capita-adjusted`, or `cumulative-per-capita-convergence`.

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
)
from fair_shares.library.utils import (
    build_source_id,
    ensure_string_year_columns,
    generate_rcb_pathway_scenarios,
    process_rcb_to_2020_baseline,
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
    emission_category = "co2-ffi"  # RCB-pathways only support co2-ffi
    active_sources = {
        "emissions": "primap-202503",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "unu-wider-2025",
        "target": "rcb-pathways",  # RCB pathways mode
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

# RCB-pathways are only available for co2-ffi
if emission_category != "co2-ffi":
    raise ConfigurationError(
        f"RCB-pathway allocations only support 'co2-ffi' emission category. "
        f"Got: {emission_category}. Please use target: 'ar6' or 'cr'"
        f" in your configuration for other emission categories."
    )

print(f"Emission category validated: {emission_category}")

# Get pathway parameters from config
rcb_pathways_config = config["targets"].get("rcb-pathways", {})
pathway_params = rcb_pathways_config.get("data_parameters", {}).get(
    "pathway_parameters", {}
)

# Default pathway parameters
start_year = pathway_params.get("start_year", 2020)
end_year = pathway_params.get("end_year", 2100)

# Get generator from top-level config (set by build_data_config)
# This is provided via active_sources['rcb_generator'] and validated during config building
generator = config.get("rcb_generator", "exponential-decay")

print("\nPathway generation parameters:")
print(f"  Generator: {generator}")
print(f"  Start year: {start_year}")
print(f"  End year: {end_year}")

# Get RCB adjustments
rcb_adjustments = rcb_pathways_config.get("data_parameters", {}).get("adjustments", {})
bunkers_2020_2100 = rcb_adjustments.get("bunkers_2020_2100", 0.0)
lulucf_2020_2100 = rcb_adjustments.get("lulucf_2020_2100", 0.0)

print("\nRCB adjustments:")
print(f"  Bunkers (2020-2100): {bunkers_2020_2100:,.0f} Mt CO2")
print(f"  LULUCF (2020-2100): {lulucf_2020_2100:,.0f} Mt CO2")

# %%
# Construct paths to intermediate data
emissions_intermediate_dir_str = f"output/{source_id}/intermediate/emissions"
scenarios_intermediate_dir_str = f"output/{source_id}/intermediate/scenarios"

emissions_intermediate_dir = project_root / emissions_intermediate_dir_str
scenarios_intermediate_dir = project_root / scenarios_intermediate_dir_str

# Create scenarios output directory
scenarios_intermediate_dir.mkdir(parents=True, exist_ok=True)

# Get RCB source path from config
# Note: rcb-pathways uses the same RCB YAML source as rcbs
# Get the path from whichever target is configured (rcbs or rcb-pathways)
if "rcb-pathways" in config["targets"]:
    rcb_config = config["targets"]["rcb-pathways"]
elif "rcbs" in config["targets"]:
    rcb_config = config["targets"]["rcbs"]
else:
    raise ConfigurationError(
        "No RCB configuration found in config (expected 'rcbs' or 'rcb-pathways' in targets)"
    )

rcb_yaml_path = project_root / rcb_config["path"]

print("\nPaths:")
print(f"  RCB YAML: {rcb_yaml_path}")
print(f"  Emissions directory: {emissions_intermediate_dir}")
print(f"  Output directory: {scenarios_intermediate_dir}")

# %% [markdown]
# ## Load and process RCB data from YAML

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
    print(f"    Scenarios: {list(first_data.get('scenarios', {}).keys())}")

# %% [markdown]
# ## Load emissions data and extract world totals

# %%
# Load emissions for the emission category
emissions_path = (
    emissions_intermediate_dir / f"emiss_{emission_category}_timeseries.csv"
)

if not emissions_path.exists():
    raise DataLoadingError(
        f"Emissions data not found at: {emissions_path}. "
        f"Run 101_data_preprocess_emiss first."
    )

emissions_df = pd.read_csv(emissions_path)
emissions_df = emissions_df.set_index(["iso3c", "unit", "emission-category"])
emissions_df = ensure_string_year_columns(emissions_df)

# Extract world emissions (needed for start value and RCB processing)
# Look for EARTH, World, WLD, or OWID_WRL as potential world keys
world_keys = ["EARTH", "World", "WLD", "OWID_WRL"]
world_key_found = None

for key in world_keys:
    if key in emissions_df.index.get_level_values("iso3c"):
        world_key_found = key
        break

if world_key_found is None:
    raise DataLoadingError(
        f"No world emissions found in emissions data. Tried keys: {world_keys}"
    )

world_emissions_df = emissions_df[
    emissions_df.index.get_level_values("iso3c") == world_key_found
].copy()

# Reset index to rename World key to standard "World"
world_emissions_df = world_emissions_df.reset_index()
world_emissions_df["iso3c"] = "World"
world_emissions_df = world_emissions_df.set_index(
    ["iso3c", "unit", "emission-category"]
)

# Extract start year emissions value for later use
start_emissions = float(world_emissions_df[str(start_year)].iloc[0])

print(f"\nWorld emissions extracted from emissions data (key: {world_key_found})")
print(
    f"  Years available: {world_emissions_df.columns[0]} to {world_emissions_df.columns[-1]}"
)
print(f"  Start year emissions ({start_year}): {start_emissions:,.0f} Mt CO2")

# %% [markdown]
# ## Process RCB data to 2020 baseline

# %%
print("\nProcessing RCBs with adjustments:")
print("  Target baseline year: 2020")
print(f"  Bunkers adjustment: {bunkers_2020_2100:,.0f} Mt CO2")
print(f"  LULUCF adjustment: {lulucf_2020_2100:,.0f} Mt CO2")

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

    print(f"    Baseline year: {baseline_year}, Scenarios: {len(scenarios)}")

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
            verbose=False,
        )

        # Create record with parsed climate assessment and quantile
        record = {
            "source": source_key,
            "scenario": scenario,
            "climate-assessment": climate_assessment,
            "quantile": quantile,
            "emission-category": emission_category,
            "rcb_2020_mt": result["rcb_2020_mt"],
        }

        rcb_records.append(record)

# Convert to DataFrame
rcbs_df = pd.DataFrame(rcb_records)

print(f"\nProcessed {len(rcbs_df)} RCB records")
print("\nRCB scenarios:")
print(rcbs_df[["source", "climate-assessment", "quantile", "rcb_2020_mt"]].to_string())

# %% [markdown]
# ## Generate pathways from RCBs

# %%
# Generate pathway scenarios
print(f"\nGenerating pathways using '{generator}' generator...")

scenarios_df = generate_rcb_pathway_scenarios(
    rcbs_df=rcbs_df,
    world_emissions_df=world_emissions_df,
    start_year=start_year,
    end_year=end_year,
    emission_category=emission_category,
    generator=generator,
)

print(f"\nGenerated {len(scenarios_df)} pathway scenarios")
print(f"  Index levels: {scenarios_df.index.names}")
print(f"  Years: {scenarios_df.columns[0]} to {scenarios_df.columns[-1]}")

# %% [markdown]
# ## Validate pathways

# %%
# Verify conservation for each scenario
print("\nPathway validation (budget conservation):")

# Get expected budgets from RCBs (including source)
expected_budgets = rcbs_df.set_index(["climate-assessment", "quantile", "source"])[
    "rcb_2020_mt"
]

for idx in scenarios_df.index:
    climate_assessment = idx[0]
    quantile = idx[1]
    source = idx[2]

    pathway_sum = scenarios_df.loc[idx].sum()
    expected = expected_budgets.loc[(climate_assessment, quantile, source)]

    relative_error = abs(pathway_sum - expected) / expected
    status = "PASS" if relative_error < 1e-5 else "FAIL"

    print(
        f"  {source}: {climate_assessment} q={quantile}: "
        f"sum={pathway_sum:,.0f} Mt, expected={expected:,.0f} Mt, "
        f"error={relative_error:.2e} [{status}]"
    )

# %%
# Show sample pathway profile
print("\nSample pathway profile (first scenario):")
first_scenario = scenarios_df.iloc[0]
sample_years = ["2020", "2030", "2040", "2050", "2060", "2070", "2080", "2090", "2100"]
available_sample_years = [y for y in sample_years if y in first_scenario.index]

for year in available_sample_years:
    print(f"  {year}: {first_scenario[year]:,.0f} Mt CO2")

# %% [markdown]
# ## Save Generated Scenarios
#
# Save all individual pathways (one per RCB source) for use in allocations.

# %%
# Save scenarios in the same format as AR6/CR scenarios
output_path = (
    scenarios_intermediate_dir / f"scenarios_{emission_category}_timeseries.csv"
)

# Reset index to save as CSV (includes 'source' column)
scenarios_output = scenarios_df.reset_index()
scenarios_output.to_csv(output_path, index=False)

print(f"\nSaved pathways to: {output_path}")
print(f"  Rows: {len(scenarios_output)} (one per RCB source)")
print(
    f"  Columns: {list(scenarios_output.columns[:6])} ... {list(scenarios_output.columns[-3:])}"
)
print(
    f"\nAll {len(scenarios_df)} individual source pathways are preserved for allocations"
)

# %% [markdown]
# ## Visualize Generated Pathways

# %%
import matplotlib.pyplot as plt
import numpy as np

print("\n--- Generating Pathway Visualization ---")

# Reshape data for plotting
plot_data = scenarios_df.reset_index()
plot_data = plot_data.melt(
    id_vars=[
        "source",
        "climate-assessment",
        "quantile",
        "iso3c",
        "unit",
        "emission-category",
    ],
    var_name="year",
    value_name="emissions",
)
plot_data["year"] = plot_data["year"].astype(int)

# Get climate assessments and assign colors
climate_assessments = sorted(plot_data["climate-assessment"].unique())
palette = dict(
    zip(climate_assessments, plt.cm.tab10(np.linspace(0, 1, len(climate_assessments))))
)

# Source marker styles (to distinguish between sources)
sources = sorted(plot_data["source"].unique())
source_markers = {
    sources[i]: {"marker": ["o", "s", "^"][i % 3], "markersize": 4}
    for i in range(len(sources))
}

# Quantile line styles
quantile_styles = {
    "0.5": {"linestyle": "-", "linewidth": 2.0, "alpha": 0.9},
    "0.66": {"linestyle": "--", "linewidth": 1.8, "alpha": 0.8},
    "0.83": {"linestyle": ":", "linewidth": 1.8, "alpha": 0.7},
}

# Create figure
fig, ax = plt.subplots(1, 1, figsize=(16, 9))

# Plot each pathway (source x climate-assessment x quantile)
for source in sources:
    source_data = plot_data[plot_data["source"] == source]

    for ca in climate_assessments:
        ca_data = source_data[source_data["climate-assessment"] == ca]

        for quantile, style in quantile_styles.items():
            quant_data = ca_data[ca_data["quantile"] == quantile]

            if not quant_data.empty:
                # Create label with source, temp, and probability
                prob_pct = int(float(quantile) * 100)
                label = f"{source}: {ca} ({prob_pct}%)"

                ax.plot(
                    quant_data["year"],
                    quant_data["emissions"],
                    label=label,
                    color=palette[ca],
                    linestyle=style["linestyle"],
                    linewidth=style["linewidth"],
                    alpha=style["alpha"],
                    marker=source_markers[source]["marker"],
                    markersize=source_markers[source]["markersize"],
                    markevery=10,  # Show marker every 10 years
                )

# Add vertical line at start year
ax.axvline(
    x=start_year,
    color="red",
    linestyle=":",
    alpha=0.5,
    linewidth=2,
    label=f"Start year ({start_year})",
)

# Formatting
unit_label = scenarios_df.index.get_level_values("unit")[0]
ax.set_ylabel(f"Emissions ({unit_label})", fontsize=12)
ax.set_xlabel("Year", fontsize=12)
ax.set_title(
    f"RCB-Derived Emission Pathways ({emission_category})\n"
    f"Generated using {generator} from Remaining Carbon Budgets",
    fontsize=14,
    fontweight="bold",
)
ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=10)
ax.grid(True, alpha=0.3)

# Set x-axis ticks
all_years = sorted(plot_data["year"].unique())
tick_years = all_years[::10]  # Every 10 years
ax.set_xticks(tick_years)
ax.tick_params(axis="x", rotation=45)

# Clean up spines
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.show()

print("  Generated pathway visualization")

# %% [markdown]
# ## Show Individual RCB Sources

# %%
# Display the underlying RCB data used to generate these pathways
print("\n--- RCB Sources Used for Pathway Generation ---")
print(f"\nTotal RCBs: {len(rcbs_df)}")
print(f"Total pathways generated: {len(scenarios_df)}")
print(f"Sources: {len(rcbs_df['source'].unique())}")
print(
    f"Unique temperature/probability combinations: {len(rcbs_df.groupby(['climate-assessment', 'quantile']))}"
)
print("\nNote: Each RCB source generates a separate pathway (not averaged)")

# Show detailed RCB info
rcb_summary = rcbs_df.pivot_table(
    index=["climate-assessment", "quantile"],
    columns="source",
    values="rcb_2020_mt",
    aggfunc="first",
)

print("\nRCB Values by Source (Mt CO2 from 2020):")
print(rcb_summary.to_string())

# Calculate statistics across sources for each temperature/probability combination
print("\n--- RCB Statistics by Temperature/Probability ---")
print("(Statistics show variation across different RCB sources)")
for (ca, q), group in rcbs_df.groupby(["climate-assessment", "quantile"]):
    values = group["rcb_2020_mt"].values
    mean_val = values.mean()
    std_val = values.std()
    min_val = values.min()
    max_val = values.max()
    n_sources = len(values)

    print(f"\n{ca} (q={q}): {n_sources} separate pathways generated")
    print("  RCB values:")
    for source, rcb in zip(group["source"], group["rcb_2020_mt"]):
        print(f"    - {source}: {rcb:,.0f} Mt CO2")
    print(f"  Mean:   {mean_val:,.0f} Mt CO2")
    print(f"  Std Dev: {std_val:,.0f} Mt CO2")
    print(f"  Range:  {min_val:,.0f} - {max_val:,.0f} Mt CO2")

# %%
# Summary
print("\n" + "=" * 60)
print("RCB PATHWAY GENERATION COMPLETE")
print("=" * 60)
print(f"Generator used: {generator}")
print(f"Individual pathways generated: {len(scenarios_df)} (one per RCB source)")
print(f"Pathways saved for allocations: {len(scenarios_df)} (all sources preserved)")
print(f"Time range: {start_year} to {end_year}")
print(f"Output: {output_path}")
print("\nPathway characteristics:")
print(f"  - Start year emissions: {start_emissions:,.0f} Mt CO2")
print("  - End year emissions: 0.0 Mt CO2 (exact zero)")
print("  - Budget conservation: All pathways sum to their respective RCBs")
print("\nThese pathways can now be used with pathway allocation approaches:")
print("  - equal-per-capita")
print("  - per-capita-adjusted")
print("  - per-capita-adjusted-gini")
print("  - cumulative-per-capita-convergence")
