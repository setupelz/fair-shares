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
# # Budget Allocation Examples (Reference)
#
# **Pre-configured examples demonstrating different equity principles.**
# For custom analysis, use **notebook 301**.
#
# **What's included:**
#
# - **Equal per capita** - Operationalizes equal rights to atmosphere
# - **Responsibility and capability adjusted** - Operationalizes CBDR-RC principles
# - **Gini-adjusted** - Adds within-country inequality adjustment for subsistence protection
#
# Each example demonstrates how different equity principles translate to budget allocations.
#
# [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/)

# %% [markdown]
# ---
# ## Configuration
#
# All settings in one place. Edit this cell and re-run the notebook.
#
# **Budget approaches only** — define CO2 budget allocations below. For composite
# categories (all-ghg), non-CO2 pathway approaches are **auto-derived** from the
# budget approaches (e.g. `equal-per-capita-budget` → `equal-per-capita` with
# `allocation_year` → `first_allocation_year`). No need to define them manually.
# The mapping is: `equal-per-capita-budget` → `equal-per-capita`,
# `per-capita-adjusted-budget` → `per-capita-adjusted`,
# `per-capita-adjusted-gini-budget` → `per-capita-adjusted-gini`.

# %%
# =============================================================================
# CONFIGURATION — edit this cell, then run all below
# =============================================================================

# Output folder name
allocation_folder = "reference_budget_allocations"

# Emission category: "co2-ffi" | "co2" | "all-ghg-ex-co2-lulucf" | "all-ghg"
emission_category = "all-ghg"

# Data sources
active_sources = {
    "target": "rcbs",
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
    "lulucf": "melo-2026",
}

# Budget allocation approaches (CO2).
# For composite categories, non-CO2 pathway equivalents are auto-derived.
allocations = {
    # APPROACH 1: Equal Per Capita Budget
    # Principle: Equal per capita — equal rights to atmosphere
    # See: docs/science/principle-to-code.md (Equal Per Capita)
    "equal-per-capita-budget": [
        {
            "allocation_year": [2015],
            "preserve_allocation_year_shares": [False],
        }
    ],
    # APPROACH 2: Per Capita Adjusted Budget
    # Principle: Pre-allocation responsibility + capability (CBDR-RC)
    # See: docs/science/principle-to-code.md (CBDR-RC)
    "per-capita-adjusted-budget": [
        # Configuration A: Pre-allocation responsibility only
        {
            "allocation_year": [2015],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [2000],
            "preserve_allocation_year_shares": [False],
        },
        # Configuration B: Capability only
        {
            "allocation_year": [2015],
            "capability_weight": [1.0],
            "capability_exponent": [1.0],
            "preserve_allocation_year_shares": [False],
        },
        # Configuration C: Combined responsibility and capability
        {
            "allocation_year": [2015],
            "pre_allocation_responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_year": [2000],
            "preserve_allocation_year_shares": [False],
        },
    ],
    # APPROACH 3: Per Capita Adjusted with Gini
    # Principle: Subsistence protection
    # See: docs/science/principle-to-code.md (Subsistence Protection)
    "per-capita-adjusted-gini-budget": [
        # Configuration A: Gini-adjusted capability only
        {
            "allocation_year": [2015],
            "capability_weight": [1.0],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "preserve_allocation_year_shares": [False],
        },
        # Configuration B: Responsibility plus Gini-adjusted capability
        {
            "allocation_year": [2015],
            "pre_allocation_responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_year": [2000],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "preserve_allocation_year_shares": [False],
        },
    ],
}

# Visualization settings
EXAMPLE_COUNTRIES = ["USA", "CHN", "IND", "DEU", "BRA"]
PLOT_START_YEAR = 2015

# For pathway allocations (used when emission_category is composite)
desired_harmonisation_year = 2020

# %% [markdown]
# ---
# ## Validate and Store Configuration

# %%
import matplotlib.pyplot as plt
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.notebook_helpers import (
    load_allocation_data,
    print_results_summary,
    run_all_allocations,
)
from fair_shares.library.utils import (
    convert_parquet_to_wide_csv,
    setup_data,
)
from fair_shares.library.utils.data.config import (
    is_composite_category,
    validate_data_source_config,
)
from fair_shares.library.visualization import plot_example_result

plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()

# Validate data sources before running anything
validation = validate_data_source_config(emission_category, active_sources)
if not validation["valid"]:
    raise ConfigurationError(
        "Configuration errors:\n" + "\n".join(f"  - {i}" for i in validation["issues"])
    )

# Determine harmonisation year
target = active_sources["target"]
if target != "rcbs" or is_composite_category(emission_category):
    harmonisation_year = desired_harmonisation_year
else:
    harmonisation_year = None

# %% [markdown]
# ---
# ## Run Data Pipeline
#
# **Automated** - Run cell below. Takes 2-5 minutes.

# %%
setup_info = setup_data(
    project_root=project_root,
    emission_category=emission_category,
    active_sources=active_sources,
    harmonisation_year=harmonisation_year,
    verbose=True,
)

source_id = setup_info["source_id"]
processed_dir = setup_info["paths"]["processed_dir"]
original_emission_category = emission_category
emission_category = setup_info["emission_category"]
final_categories = setup_info["final_categories"]
harmonisation_year = setup_info["config"].harmonisation_year

# %% [markdown]
# ---
# ## Load Data and Run Allocations
#
# **Outputs**: `allocations_relative.parquet`, `allocations_absolute.parquet`,
# `param_manifest.csv`, `README.md`

# %%
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
    "target-source": target,
    "emissions-source": active_sources["emissions"],
    "gdp-source": active_sources["gdp"],
    "population-source": active_sources["population"],
    "gini-source": active_sources["gini"],
}

param_manifest_rows = run_all_allocations(
    allocations=allocations,
    loaded_data=loaded_data,
    output_dir=output_dir,
    data_context=data_context,
    target=target,
    final_categories=final_categories,
    harmonisation_year=harmonisation_year,
)

# %% [markdown]
# ---
# ## Quick Check
#
# Example allocation for a few key countries. For composite categories,
# shows CO₂ budget alongside non-CO₂ pathway.

# %%
fig = plot_example_result(
    output_dir=output_dir,
    countries=EXAMPLE_COUNTRIES,
    plot_start_year=PLOT_START_YEAR,
    processed_dir=processed_dir,
    emission_category=original_emission_category,
    final_categories=final_categories,
)
plt.show()

# %% [markdown]
# ---
# ## Export to CSV (Optional)
#
# Convert parquet results to wide-format CSV for Excel or other tools.

# %%
allocation_param_prefixes = {
    "first-allocation-year": "y",
    "allocation-year": "ay",
    "pre-allocation-responsibility-weight": "rw",
    "capability-weight": "cw",
    "pre-allocation-responsibility-year": "hr",
    "income-floor": "floor",
    "max-gini-adjustment": "gini",
}

csv_path = convert_parquet_to_wide_csv(
    allocations_dir=output_dir,
    config_prefixes=allocation_param_prefixes,
)

# %% [markdown]
# ---
# ## Results Summary

# %%
print_results_summary(
    output_dir=output_dir,
    param_manifest_rows=param_manifest_rows,
    allocations=allocations,
)

# %%
