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
# # Pathway Allocation Examples (Reference)
#
# **Pre-configured examples demonstrating different equity principles for pathways.**
# For custom analysis, use **notebook 301**.
#
# **What's included:**
#
# - **Equal per capita** - Operationalizes equal rights to atmosphere (annual shares)
# - **Adjusted** - Operationalizes pre-allocation responsibility and capability (CBDR-RC)
# - **Gini-adjusted** - Adds within-country inequality adjustment for subsistence protection
# - **Cumulative convergence** - Smooth transitions while preserving cumulative equity budgets
#
# Each demonstrates how different equity principles translate to pathway allocations.
#
# [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/)

# %%
# Imports
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
    validate_data_source_config,
)
from fair_shares.library.utils.data.config import is_composite_category
from fair_shares.library.visualization import plot_example_result

plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()

# %% [markdown]
# ---
# ## Configuration
#
# All tuneable parameters in one cell. Edit here, then run everything below.
#
# **Datasets**: PRIMAP emissions (2025), WDI GDP (2025), UN population (2025), UNU-WIDER Gini (2025), exponential-decay pathway generator

# %%
# =============================================================================
# CONFIGURATION — edit this cell, then Run All below
# =============================================================================

# Output folder name
allocation_folder = "reference_pathway_allocations_rcb_pathways"

# Emission category: "co2-ffi" | "co2" | "all-ghg-ex-co2-lulucf" | "all-ghg"
emission_category = "all-ghg"

# Data sources
active_sources = {
    # Target: What climate goal to allocate
    "target": "rcb-pathways",
    # Historical emissions from PRIMAP database (March 2025 version)
    "emissions": "primap-202503",
    # GDP data from World Bank World Development Indicators (2025)
    "gdp": "wdi-2025",
    # Population projections from UN (2025)
    "population": "un-owid-2025",
    # Income inequality (Gini coefficients) from UNU-WIDER (2025)
    "gini": "unu-wider-2025",
    # LULUCF data for NGHGI-consistent corrections
    "lulucf": "melo-2026",
    # Pathway generator for rcb-pathways (optional, defaults to "exponential-decay")
    "rcb_generator": "exponential-decay",
}

# For pathway allocations only — harmonisation year to historical data
desired_harmonisation_year = 2020

# -------------------------------------------------------------------------
# ALLOCATION APPROACH CONFIGURATIONS
# -------------------------------------------------------------------------
# Six principle-based approaches:
#
# 1. Equal per capita — equal rights to atmosphere (annual shares)
# 2. Adjusted — pre-allocation responsibility + capability (CBDR-RC)
# 3. Gini-adjusted — within-country inequality adjustment for subsistence protection
# 4. Cumulative convergence — smooth transitions preserving cumulative equity budgets
# 5. Cumulative convergence adjusted — convergence + CBDR-RC adjustments
# 6. Cumulative convergence Gini — convergence + subsistence protection
#
# See: docs/science/principle-to-code.md
# [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/)

allocations = {
    # APPROACH 1: Equal Per Capita Pathway
    # Principle: Equal per capita (annual shares)
    "equal-per-capita": [
        {
            "first_allocation_year": [2015],
            "preserve_first_allocation_year_shares": [False],
        }
    ],
    # APPROACH 2: Per Capita Adjusted Pathway
    # Principle: Pre-allocation responsibility + capability (CBDR-RC)
    "per-capita-adjusted": [
        # Configuration A: Pre-allocation responsibility only
        {
            "first_allocation_year": [2015],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [2000],
            "preserve_first_allocation_year_shares": [False],
        },
        # Configuration B: Capability only
        {
            "first_allocation_year": [2015],
            "capability_weight": [1.0],
            "preserve_first_allocation_year_shares": [False],
        },
        # Configuration C: Combined responsibility and capability
        {
            "first_allocation_year": [2015],
            "pre_allocation_responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_year": [2000],
            "preserve_first_allocation_year_shares": [False],
        },
    ],
    # APPROACH 3: Per Capita Adjusted with Gini
    # Adjusts for within-country inequality using income thresholds
    "per-capita-adjusted-gini": [
        # Configuration A: Gini-adjusted capability only
        {
            "first_allocation_year": [2015],
            "capability_weight": [1.0],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "preserve_first_allocation_year_shares": [False],
        },
        # Configuration B: Responsibility plus Gini-adjusted capability
        {
            "first_allocation_year": [2015],
            "pre_allocation_responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_year": [2000],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "preserve_first_allocation_year_shares": [False],
        },
    ],
    # APPROACH 4: Cumulative Per Capita Convergence
    # Smoothly transitions to equal per capita while matching cumulative budgets
    "cumulative-per-capita-convergence": [
        {
            "first_allocation_year": [2015],
            "convergence_year": [2050],
            "strict": [False],
        }
    ],
    # APPROACH 5: Cumulative Per Capita Convergence with Adjustments
    # Convergence with responsibility and/or capability adjustments
    "cumulative-per-capita-convergence-adjusted": [
        {
            "first_allocation_year": [2015],
            "pre_allocation_responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_year": [2000],
            "convergence_year": [2050],
            "strict": [False],
        }
    ],
    # APPROACH 6: Cumulative Per Capita Convergence with Gini
    # Principle: Convergence + subsistence protection
    "cumulative-per-capita-convergence-gini-adjusted": [
        # Configuration A: Gini-adjusted capability only
        {
            "first_allocation_year": [2015],
            "capability_weight": [1.0],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "convergence_year": [2050],
            "strict": [False],
        },
        # Configuration B: Responsibility plus Gini-adjusted capability
        {
            "first_allocation_year": [2015],
            "pre_allocation_responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_year": [2000],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "convergence_year": [2050],
            "strict": [False],
        },
    ],
}

# Exploration settings
EXAMPLE_COUNTRIES = ["USA", "CHN", "IND", "DEU", "BRA"]
PLOT_START_YEAR = 2015

# %% [markdown]
# ---
# ## Validate and Store Configuration

# %%
# Derive runtime variables from config
target = active_sources["target"]
if target != "rcbs" or is_composite_category(emission_category):
    harmonisation_year = desired_harmonisation_year
else:
    harmonisation_year = None

# Validate configuration (catches issues before the pipeline runs)
validation_result = validate_data_source_config(
    emission_category=emission_category, active_sources=active_sources, verbose=True
)

if validation_result["valid"]:
    print(f"\nConfiguration valid  |  target type: {validation_result['target_type']}")
    print(
        f"Compatible approaches: {len(validation_result['compatible_approaches'])} available"
    )
else:
    print("\nConfiguration has issues:")
    for issue in validation_result["issues"]:
        print(f"  - {issue}")
    raise ConfigurationError(
        f"Invalid configuration: {'; '.join(validation_result['issues'])}"
    )

# %% [markdown]
# ---
# ## Run Data Pipeline
#
# **Automated** — takes 2-5 minutes.

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
# **Outputs**: `allocations_relative.parquet`, `allocations_absolute.parquet`, `param_manifest.csv`, `README.md`

# %%
# Load all processed data
loaded_data = load_allocation_data(
    processed_dir=processed_dir,
    target=target,
    final_categories=final_categories,
    emission_category=emission_category,
)

# Build output path and data context
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

# Run all allocation approaches
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
# Example allocation for a few key countries.

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
