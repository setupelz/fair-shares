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
# Start with principles, not parameters. Any allocation involves ethical choices --
# this workflow helps make those choices explicit.
#
# **Before configuring, read:**
#
# - [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/) - Principles-first workflow
#
# **Pre-configured examples:**
#
# - `302_example_templates_budget_allocations.py` - Budget templates
# - `303_example_templates_pathway_allocations.py` - Pathway templates
#
# **Workflow:** Configure once below, then Run All.

# %% [markdown]
# ---
# ## Configuration (edit this)
#
# All user-editable settings live in this single cell. Everything below runs
# automatically.
#
# **Data sources:**
# - **Emission categories:** `co2-ffi`, `co2-lulucf`, `co2`, `non-co2`, `all-ghg`, `all-ghg-ex-co2-lulucf`
# - **Target types:** `rcbs` (cumulative budgets), `ar6` (IPCC AR6 pathways), `rcb-pathways` (budget-derived pathways)
#
# **Allocation approaches:**
# - Budget (`target="rcbs"`): `equal-per-capita-budget`, `per-capita-adjusted-budget`, `per-capita-adjusted-gini-budget`
# - Pathway (`target="pathway"` or `"rcb-pathways"`): `equal-per-capita`, `per-capita-adjusted`, `cumulative-per-capita-convergence`, `*-gini-adjusted`
#
# See [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/) for principle-approach mapping.
# See [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/) for parameters.
# See [Full guide](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/) for data source details.

# %%
# ── CONFIGURATION ────────────────────────────────────────────────────────────

# Output folder name (overwrites folders of the same name)
allocation_folder = "my_custom_analysis"

# Emission category: "co2-ffi" | "co2-lulucf" | "co2" | "non-co2" | "all-ghg" | "all-ghg-ex-co2-lulucf"
emission_category = "all-ghg"

# Data sources
active_sources = {
    # Target source - What you're allocating
    # - "rcbs": Remaining Carbon Budgets (for budget allocations)
    # - "pathway": IPCC AR6 scenarios (for pathway allocations)
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
    # LULUCF - Required for NGHGI-consistent RCB corrections
    # - "melo-2026": Melo et al. (2026) NGHGI v3.1 data
    "lulucf": "melo-2026",
    # RCB pathway generator - Optional, defaults to "exponential-decay"
    # "rcb_generator": "exponential-decay",
}

# Allocation approaches — the codebase runs every permutation within each
# definition, so provide a list of config dicts per approach.
# For composite categories (all-ghg), non-CO2 pathway equivalents are
# auto-derived from budget approaches — no need to define them separately.
allocations = {
    "equal-per-capita-budget": [
        {
            "allocation_year": [2015],
            "preserve_allocation_year_shares": [False],
        }
    ],
}

# For pathway allocations only — harmonisation year to historical data
desired_harmonisation_year = 2020

# Exploration settings
EXAMPLE_COUNTRIES = ["USA", "CHN", "IND", "DEU", "BRA"]
PLOT_START_YEAR = 2015

# %% [markdown]
# ---
# ## Execution (Run All from here)

# %%
# Validate configuration
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.utils import validate_data_source_config
from fair_shares.library.utils.data.config import is_composite_category

project_root = here()
target = active_sources["target"]

# Harmonisation year: needed for pathways and composite categories
if target != "rcbs" or is_composite_category(emission_category):
    harmonisation_year = desired_harmonisation_year
else:
    harmonisation_year = None

validation_result = validate_data_source_config(
    emission_category=emission_category, active_sources=active_sources, verbose=True
)
if not validation_result["valid"]:
    for issue in validation_result["issues"]:
        print(f"  - {issue}")
    raise ConfigurationError(
        "Configuration validation failed. Fix the issues above before proceeding."
    )

print(f"\nTarget type: {validation_result['target_type']}")
print(
    f"Compatible approaches: {len(validation_result['compatible_approaches'])} available"
)

# %%
# Run data pipeline
from fair_shares.library.utils import setup_data

setup_info = setup_data(
    project_root=project_root,
    emission_category=emission_category,
    active_sources=active_sources,
    harmonisation_year=harmonisation_year,
    verbose=True,
)

# Extract pipeline outputs
source_id = setup_info["source_id"]
processed_dir = setup_info["paths"]["processed_dir"]
original_emission_category = emission_category
emission_category = setup_info["emission_category"]
final_categories = setup_info["final_categories"]
harmonisation_year = setup_info["config"].harmonisation_year

print(f"\nSource ID: {source_id}")
print(f"Emission category: {emission_category}")
if len(final_categories) > 1:
    print(f"Final categories: {', '.join(final_categories)}")
print(f"Processed data: {processed_dir}")

# %%
# Data quality summary
import pandas as pd

from fair_shares.library.utils import ensure_string_year_columns

display_category = final_categories[0]

emiss_df = pd.read_csv(
    processed_dir / f"country_emissions_{display_category}_timeseries.csv"
).set_index(["iso3c", "unit", "emission-category"])
emiss_df = ensure_string_year_columns(emiss_df)
gdp_df = pd.read_csv(processed_dir / "country_gdp_timeseries.csv").set_index(
    ["iso3c", "unit"]
)
gdp_df = ensure_string_year_columns(gdp_df)
pop_df = pd.read_csv(processed_dir / "country_population_timeseries.csv").set_index(
    ["iso3c", "unit"]
)
pop_df = ensure_string_year_columns(pop_df)
gini_df = pd.read_csv(processed_dir / "country_gini_stationary.csv").set_index(
    ["iso3c", "unit"]
)

datasets = {
    "Emissions": emiss_df,
    "GDP": gdp_df,
    "Population": pop_df,
    "Gini": gini_df,
}

print("COUNTRY COUNTS")
print("-" * 50)
for name, df in datasets.items():
    countries = df.index.get_level_values("iso3c").unique()
    n = len([c for c in countries if c != "World"])
    suffix = " + World total" if "World" in countries else ""
    print(f"  {name:<12s} {n} countries{suffix}")

print("\nYEAR RANGES")
print("-" * 50)
for name, df in datasets.items():
    yr = [c for c in df.columns if c.isdigit()]
    if yr:
        print(f"  {name:<12s} {yr[0]} - {yr[-1]} ({len(yr)} years)")
    else:
        print(f"  {name:<12s} Stationary")

print("\nMISSING VALUES")
print("-" * 50)
total_missing = 0
for name, df in datasets.items():
    n_miss = int(df.isna().sum().sum())
    total_missing += n_miss
    print(f"  {name:<12s} {n_miss}")
if total_missing == 0:
    print("\n  All datasets complete.")
else:
    print("\n  Some missing values (normal — aggregated into ROW).")

# %%
# Load data + run allocations
from fair_shares.library.notebook_helpers import (
    load_allocation_data,
    run_all_allocations,
)

print("Loading processed data...")
loaded_data = load_allocation_data(
    processed_dir=processed_dir,
    target=target,
    final_categories=final_categories,
    emission_category=emission_category,
)

output_dir = project_root / "output" / source_id / "allocations" / allocation_folder

data_context = {
    "source-id": source_id,
    "allocation-folder": allocation_folder,
    "emission-category": emission_category,
    "target-source": active_sources["target"],
    "emissions-source": active_sources["emissions"],
    "gdp-source": active_sources["gdp"],
    "population-source": active_sources["population"],
    "gini-source": active_sources["gini"],
    "lulucf-source": active_sources.get("lulucf", "none"),
}

print("\nRunning allocations...")
param_manifest_rows = run_all_allocations(
    allocations=allocations,
    loaded_data=loaded_data,
    output_dir=output_dir,
    data_context=data_context,
    target=target,
    final_categories=final_categories,
    harmonisation_year=harmonisation_year,
)

print(f"\nTotal parameter combinations: {len(param_manifest_rows)}")
print(f"Approaches: {', '.join(sorted(allocations.keys()))}")

# %%
# Quick check — example allocation for a few countries
import matplotlib.pyplot as plt

from fair_shares.library.visualization import plot_example_result

plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

fig = plot_example_result(
    output_dir=output_dir,
    countries=EXAMPLE_COUNTRIES,
    plot_start_year=PLOT_START_YEAR,
    processed_dir=processed_dir,
    emission_category=original_emission_category,
    final_categories=final_categories,
)
plt.show()

# %%
# CSV export
from fair_shares.library.utils import convert_parquet_to_wide_csv

allocation_param_prefixes = {
    "first-allocation-year": "y",
    "allocation-year": "ay",
    "pre-allocation-responsibility-weight": "rw",
    "capability-weight": "cw",
    "pre-allocation-responsibility-year": "hr",
    "income-floor": "floor",
    "max-gini-adjustment": "gini",
    "convergence-year": "cy",
}

csv_path = convert_parquet_to_wide_csv(
    allocations_dir=output_dir,
    config_prefixes=allocation_param_prefixes,
)
print(f"Wide-format CSV created: {csv_path}")

# %%
# Results summary
from fair_shares.library.notebook_helpers import print_results_summary

print_results_summary(
    output_dir=output_dir,
    param_manifest_rows=param_manifest_rows,
    allocations=allocations,
)

# %%
