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
# # IAMC Budget Allocation Examples (Reference)
#
# **Pre-configured examples for IAMC model regions demonstrating equity principles.**
# For custom analysis, use **notebook 401**.
#
# **What's included:**
#
# - **Equal per capita** - Egalitarianism
# - **Capability-adjusted** - Capability
#
# Each demonstrates how principles translate to IAMC regional allocations.
#
# **For model input preparation**, see notebook 401.
#
# [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/) | [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)

# %%
# Imports (run this first)
import matplotlib.pyplot as plt
import pandas as pd
from pyprojroot import here

# Import fair-shares library components
from fair_shares.library.allocations.budgets.per_capita import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
)
from fair_shares.library.utils import ensure_string_year_columns
from fair_shares.library.utils.data.iamc import (
    load_iamc_data,
)

# Set matplotlib style
plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()

# %% [markdown]
# ---
# ## Step 1: Load IAMC Data
#
# Pre-configured for MESSAGE-ix 12-region data with all GHGs excluding LULUCF.
#
# **Datasets**: Population, GDP|PPP, Emissions|Covered

# %%
# =============================================================================
# DATA SOURCE CONFIGURATION
# =============================================================================

# Example file with 12-region SSP2 data
DATA_FILE = (
    project_root / "data" / "scenarios" / "iamc_example" / "iamc_reporting_example.xlsx"
)

# IAMC variable names
POPULATION_VARIABLE = "Population"
GDP_VARIABLE = "GDP|PPP"
EMISSIONS_VARIABLE = "Emissions|Covered"

# Emission category
emission_category = "all-ghg-ex-lulucf"

# Allocation settings
allocation_start_year = 2015
budget_end_year = 2100
expand_to_annual = True

# Load region list
df = pd.read_excel(DATA_FILE)
df = ensure_string_year_columns(df)
regions = [r for r in df["region"].unique() if r != "World"]

print(f"Data file: {DATA_FILE}")
print(f"Regions: {', '.join(sorted(regions))}")

# %%
# Load IAMC data
data = load_iamc_data(
    data_file=DATA_FILE,
    population_variable=POPULATION_VARIABLE,
    gdp_variable=GDP_VARIABLE,
    regions=regions,
    allocation_start_year=allocation_start_year,
    budget_end_year=budget_end_year,
    expand_to_annual=expand_to_annual,
    emissions_variable=EMISSIONS_VARIABLE,
)

print("\nYes Data loaded successfully!")
print(f"Variables: {data['metadata']['variables_loaded']}")
print(f"Time range: {data['metadata']['year_range']}")

# Rename index for allocation functions
population_ts = data["population"].rename_axis(index={"region": "iso3c"})
gdp_ts = data["gdp"].rename_axis(index={"region": "iso3c"})
emissions_ts = data["emissions"].rename_axis(index={"region": "iso3c"})

# %% [markdown]
# ---
# ## Step 2: Equal Per Capita Budget Allocation
#
# **Principle: Egalitarianism** - Each person gets an equal share of the
# remaining carbon budget from allocation year onwards.
#
# Formula: Regional share = cumulative population (allocation_year → end_year) / world cumulative population
#
# See: docs/science/climate-equity-concepts.md (Equal Rights to Atmosphere)

# %%
# Calculate ECPC allocation from 2015
result_epc = equal_per_capita_budget(
    population_ts=population_ts,
    allocation_year=2015,
    emission_category=emission_category,
    preserve_allocation_year_shares=False,  # Use cumulative population (ECPC)
    group_level="iso3c",
)

# Extract shares
shares_epc = result_epc.relative_shares_cumulative_emission["2015"]
shares_epc = shares_epc.droplevel(["unit", "emission-category"])

print(f"Approach: {result_epc.approach}\n")
print("Regional Budget Shares (ECPC from 2015):\n")
print(f"{'Region':8s} {'Share':>10s}")
print("-" * 20)
for region in sorted(shares_epc.index):
    print(f"{region:8s} {shares_epc[region]*100:9.2f}%")

# %% [markdown]
# ---
# ## Step 3: Capability-Adjusted Budget Allocation
#
# **Principle: Capability** - Wealthier regions can contribute more mitigation effort
# without threatening basic well-being.
#
# Key parameter: `capability_weight` (0.0-1.0)
# - 0.0 = Pure equal per capita
# - 0.5 = Balanced between population and capability
# - 1.0 = Fully weighted by GDP
#
# See: docs/science/climate-equity-concepts.md (Ability to Pay)

# %%
# Capability-adjusted allocation (50% weight on GDP)
result_cap = per_capita_adjusted_budget(
    population_ts=population_ts,
    gdp_ts=gdp_ts,
    allocation_year=2015,
    emission_category=emission_category,
    capability_weight=0.5,
    responsibility_weight=0.0,
    historical_responsibility_year=1990,  # Not used when responsibility_weight=0
    preserve_allocation_year_shares=False,
    group_level="iso3c",
)

shares_cap = result_cap.relative_shares_cumulative_emission["2015"]
shares_cap = shares_cap.droplevel(["unit", "emission-category"])

print(f"Approach: {result_cap.approach}\n")
print("Regional Budget Shares (Capability 50%):\n")
print(f"{'Region':8s} {'Share':>10s}")
print("-" * 20)
for region in sorted(shares_cap.index):
    print(f"{region:8s} {shares_cap[region]*100:9.2f}%")

# %% [markdown]
# ---
# ## Step 4: Compare Approaches
#
# Visualize how capability adjustment changes regional allocations.

# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Sort by EPC share for consistent ordering
sorted_regions = shares_epc.sort_values(ascending=True).index

# Left: Compare approaches
ax1 = axes[0]
x = range(len(sorted_regions))
width = 0.35

ax1.barh(
    [i - width / 2 for i in x],
    shares_epc[sorted_regions] * 100,
    width,
    label="Equal Per Capita",
    color="#2ecc71",
)
ax1.barh(
    [i + width / 2 for i in x],
    shares_cap[sorted_regions] * 100,
    width,
    label="Capability 50%",
    color="#3498db",
)

ax1.set_yticks(x)
ax1.set_yticklabels(sorted_regions)
ax1.set_xlabel("Budget Share (%)")
ax1.set_title("Budget Shares by Approach")
ax1.legend(loc="lower right")
ax1.grid(axis="x", alpha=0.3)

# Right: Change from EPC to Capability
ax2 = axes[1]
delta = (shares_cap - shares_epc) * 100
colors = ["#e74c3c" if d > 0 else "#2ecc71" for d in delta[sorted_regions]]

ax2.barh(sorted_regions, delta[sorted_regions], color=colors)
ax2.axvline(0, color="black", linewidth=0.5)
ax2.set_xlabel("Change in Share (%-points)")
ax2.set_title("Change: EPC → Capability 50%")
ax2.grid(axis="x", alpha=0.3)

ax2.text(
    0.02,
    0.02,
    "← Reduced obligation     Increased obligation →",
    transform=ax2.transAxes,
    fontsize=9,
    style="italic",
    color="gray",
)

plt.tight_layout()
plt.show()

# %%
