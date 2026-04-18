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
# # 402 — IAMC budget allocation examples (reference)
#
# Pre-configured budget examples for IAMC model regions. Runs on the
# output of notebook 400 (`output/iamc/iamc_covered.xlsx`). Run
# 400 first.
#
# - **Equal per capita** — equal rights to the atmosphere
# - **Capability-adjusted** — wealthier regions shoulder more mitigation
#
# For custom analysis or model-ready remaining budgets, use notebook 401.
#
# [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/)

# %%
# Imports (run this first)
import matplotlib.pyplot as plt
import pyam
from pyprojroot import here

# Import fair-shares library components
from fair_shares.library.allocations.budgets.per_capita import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
)
from fair_shares.library.utils.data.iamc import (
    load_iamc_data,
)

# Set matplotlib style
plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

BLUE = "#005baa"

project_root = here()

# %% [markdown]
# ---
# ## Step 1: Load IAMC data (output of notebook 400)
#
# Needs Population, GDP|PPP, Emissions|Covered.

# %%
DATA_FILE = project_root / "output" / "iamc" / "iamc_covered.xlsx"
if not DATA_FILE.exists():
    raise FileNotFoundError(
        f"Data file not found: {DATA_FILE}. Run notebook 400 first."
    )

# IAMC variable names
POPULATION_VARIABLE = "Population"
GDP_VARIABLE = "GDP|PPP"
EMISSIONS_VARIABLE = "Emissions|Covered"  # The emissions being allocated

# Time range configuration
EARLIEST_DATA_YEAR = 1990  # Data must be available from this year
MODEL_HORIZON_YEAR = 2100  # Last year in model time horizon

# Load region list via pyam (handles case-insensitive columns)
regions = [r for r in pyam.IamDataFrame(DATA_FILE).region if r != "World"]

print(f"Data file: {DATA_FILE}")
print(f"Regions: {', '.join(sorted(regions))}")

# %%
# Load IAMC data
data = load_iamc_data(
    data_file=DATA_FILE,
    population_variable=POPULATION_VARIABLE,
    gdp_variable=GDP_VARIABLE,
    emissions_variable=EMISSIONS_VARIABLE,
    regions=regions,
    allocation_start_year=EARLIEST_DATA_YEAR,
    budget_end_year=MODEL_HORIZON_YEAR,
)

print("\nData loaded.")
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
# **Principle: Equal per capita** - Each person gets an equal share of the
# remaining carbon budget from allocation year onwards.
#
# Formula: Regional share = cumulative population (allocation_year -> end_year) / world cumulative population
#
# See: docs/science/principle-to-code.md (Equal Per Capita)

# %%
# Calculate ECPC allocation from 2015
result_epc = equal_per_capita_budget(
    population_ts=population_ts,
    allocation_year=2015,
    emission_category=EMISSIONS_VARIABLE,
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
# **Principle: Capability** - Wealthier regions contribute more mitigation effort.
#
# Applies GDP per capita adjustment to equal per capita shares.
#
# See [Weight Normalization](https://setupelz.github.io/fair-shares/science/allocations/#weight-normalization)

# %%
# Capability-adjusted allocation (capability only — pre_allocation_responsibility_weight
# defaults to 0.0, so capability is the sole adjustment and its specific value doesn't
# matter; 1.0 is used for clarity)
result_cap = per_capita_adjusted_budget(
    population_ts=population_ts,
    gdp_ts=gdp_ts,
    allocation_year=2015,
    emission_category=EMISSIONS_VARIABLE,
    capability_weight=1.0,
    preserve_allocation_year_shares=False,
    group_level="iso3c",
)

shares_cap = result_cap.relative_shares_cumulative_emission["2015"]
shares_cap = shares_cap.droplevel(["unit", "emission-category"])

print(f"Approach: {result_cap.approach}\n")
print("Regional Budget Shares (Capability-only):\n")
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
fig, ax = plt.subplots(figsize=(10, 6))

# Sort by EPC share for consistent ordering
sorted_regions = shares_epc.sort_values(ascending=True).index
x = range(len(sorted_regions))
width = 0.35

ax.barh(
    [i - width / 2 for i in x],
    shares_epc[sorted_regions] * 100,
    width,
    label="Equal Per Capita",
    color=BLUE,
)
ax.barh(
    [i + width / 2 for i in x],
    shares_cap[sorted_regions] * 100,
    width,
    label="Capability-Adjusted",
)

ax.set_yticks(x)
ax.set_yticklabels(sorted_regions)
ax.set_xlabel("Budget Share (%)")
ax.set_title("Budget Shares by Approach")
ax.legend(loc="lower right")
ax.grid(axis="x", alpha=0.3)

plt.tight_layout()
plt.show()

# %%
