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
from pathlib import Path

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
)

# %% tags=["parameters"]
emission_category = None
active_target_source = None
active_emissions_source = None
active_gdp_source = None
active_population_source = None
active_gini_source = None
active_lulucf_source = None
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
    emission_category = "co2-ffi"  # or "co2"
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

# Extract config values — Papermill parameter takes precedence for decomposition
# where per-pass emission_category differs from the config's category.
if not _running_via_papermill:
    emission_category = config["emission_category"]

# RCB-pathways are only available for co2-ffi and co2
if emission_category not in ("co2-ffi", "co2"):
    raise ConfigurationError(
        f"RCB-pathway allocations only support 'co2-ffi' and 'co2' emission "
        f"categories. Got: {emission_category}. Please use target: 'ar6'"
        f" in your configuration for other emission categories."
    )

print(f"Emission category validated: {emission_category}")

# Get pathway parameters from config
rcb_pathways_config = config["targets"].get("rcb-pathways", {})
pathway_params = rcb_pathways_config.get("data_parameters", {}).get(
    "pathway_parameters", {}
)

# Pathway start year: use harmonisation_year from config when available,
# so pathways begin where historical data is spliced to scenarios.
# Falls back to pathway_parameters config, then 2020.
start_year = config.get("harmonisation_year") or pathway_params.get("start_year", 2020)
end_year = pathway_params.get("end_year", 2100)

# Get generator from top-level config (set by build_data_config)
# This is provided via active_sources['rcb_generator'] and validated during config building
generator = config.get("rcb_generator", "exponential-decay")

print("\nPathway generation parameters:")
print(f"  Generator: {generator}")
print(f"  Start year: {start_year}")
print(f"  End year: {end_year}")

# Get RCB adjustment configuration (NGHGI-consistent timeseries)
from fair_shares.library.config.models import AdjustmentsConfig

rcb_data_parameters = rcb_pathways_config.get("data_parameters", {})
rcb_adjustments_raw = rcb_data_parameters.get("adjustments", {})
adjustments_config = AdjustmentsConfig.model_validate(rcb_adjustments_raw)

print("\nRCB adjustments (NGHGI-consistent, Weber et al. 2026):")
print(f"  LULUCF NGHGI source: {adjustments_config.lulucf_nghgi.path}")
print(f"  Bunkers source: {adjustments_config.bunkers.path}")
print(f"  Precautionary LULUCF cap: {adjustments_config.precautionary_lulucf}")

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
# For co2-ffi: load emissions directly from emiss_co2-ffi_timeseries.csv
# For co2: load co2-ffi and co2-lulucf components, then construct
# NGHGI-consistent world CO2 using build_nghgi_world_co2_timeseries(),
# mirroring run_rcb_preprocessing() in the orchestrator.


def _load_world_emissions(
    emissions_dir: Path, category: str, world_keys: list[str]
) -> pd.DataFrame:
    """Load emissions and extract world totals for a single category."""
    emiss_path = emissions_dir / f"emiss_{category}_timeseries.csv"
    if not emiss_path.exists():
        raise DataLoadingError(
            f"Emissions data not found at: {emiss_path}. "
            f"Run 101_data_preprocess_emiss first."
        )
    emiss_df = pd.read_csv(emiss_path)
    emiss_df = emiss_df.set_index(["iso3c", "unit", "emission-category"])
    emiss_df = ensure_string_year_columns(emiss_df)

    # Find world key
    world_key_found = None
    for key in world_keys:
        if key in emiss_df.index.get_level_values("iso3c"):
            world_key_found = key
            break
    if world_key_found is None:
        raise DataLoadingError(
            f"No world emissions found in {category} emissions data. "
            f"Tried keys: {world_keys}"
        )

    world_df = emiss_df[
        emiss_df.index.get_level_values("iso3c") == world_key_found
    ].copy()
    world_df = world_df.reset_index()
    world_df["iso3c"] = "World"
    world_df = world_df.set_index(["iso3c", "unit", "emission-category"])
    return world_df


world_keys = ["EARTH", "World", "WLD", "OWID_WRL"]

if emission_category == "co2":
    # NGHGI-consistent world CO2 = fossil - bunkers + LULUCF(NGHGI)
    # This mirrors run_rcb_preprocessing() lines 454-480 in orchestrator.py
    from fair_shares.library.preprocessing.rcbs import _load_shared_timeseries
    from fair_shares.library.utils.data.nghgi import build_nghgi_world_co2_timeseries

    # Load component timeseries
    world_co2_ffi_df = _load_world_emissions(
        emissions_intermediate_dir, "co2-ffi", world_keys
    )
    world_co2_lulucf_df = _load_world_emissions(
        emissions_intermediate_dir, "co2-lulucf", world_keys
    )

    # Load NGHGI LULUCF world timeseries and bunker timeseries
    nghgi_ts, bunker_ts, splice_year = _load_shared_timeseries(
        adjustments_config, project_root, source_id=source_id, verbose=True
    )

    # Build NGHGI-consistent world CO2 timeseries
    world_emissions_df = build_nghgi_world_co2_timeseries(
        fossil_ts=world_co2_ffi_df,
        nghgi_ts=nghgi_ts,
        bunker_ts=bunker_ts,
    )

    print("\nNGHGI-consistent world CO2 timeseries constructed:")
    print("  fossil = co2-ffi (PRIMAP)")
    print(f"  LULUCF = NGHGI actual ({splice_year} end year, no BM splicing)")
    print("  bunkers = international bunker fuel")
    print("  Formula: total CO2 = fossil - bunkers + LULUCF")

else:
    # co2-ffi: load directly
    world_emissions_df = _load_world_emissions(
        emissions_intermediate_dir, emission_category, world_keys
    )

# Extract start year emissions value for later use
start_emissions = float(world_emissions_df[str(start_year)].iloc[0])

print(f"\nWorld emissions for pathway generation ({emission_category}):")
print(
    f"  Years available: {world_emissions_df.columns[0]} to {world_emissions_df.columns[-1]}"
)
print(f"  Start year emissions ({start_year}): {start_emissions:,.0f} Mt CO2")

# %% [markdown]
# ## Process RCB data to 2020 baseline
#
# Uses `load_and_process_rcbs` — the same NGHGI-consistent pipeline as
# notebook 100. This ensures per-category net-zero years, BM LULUCF
# shift in the rebase, and the precautionary BM LULUCF cap are all applied.

# %%
from fair_shares.library.preprocessing.rcbs import load_and_process_rcbs

# Always pass PRIMAP fossil (co2-ffi) as world emissions;
# for total CO2, also pass BM LULUCF for rebase
if emission_category == "co2":
    _fossil_for_rcb = world_co2_ffi_df
    _bm_lulucf_for_rcb = world_co2_lulucf_df
else:
    _fossil_for_rcb = world_emissions_df  # already co2-ffi
    _bm_lulucf_for_rcb = None

rcbs_df = load_and_process_rcbs(
    rcb_yaml_path=rcb_yaml_path,
    world_fossil_emissions=_fossil_for_rcb,
    emission_category=emission_category,
    adjustments_config=adjustments_config,
    project_root=project_root,
    source_id=source_id,
    actual_bm_lulucf_emissions=_bm_lulucf_for_rcb,
    verbose=True,
)

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
