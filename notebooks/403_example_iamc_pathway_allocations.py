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
# # IAMC Pathway Allocation Examples (Reference)
#
# **Pre-configured pathway examples for IAMC model regions demonstrating equity principles.**
# For custom analysis, use **notebook 401**.
#
# **What's included:**
#
# - **Equal per capita** - Operationalizes equal rights (annual)
# - **Capability-adjusted** - Capability
# - **Convergence** - Smooth transitions preserving equity budgets
#
# Each demonstrates how principles translate to time-varying IAMC regional pathways.
#
# [From Principle to Code]({DOCS_ROOT}/science/principle-to-code/) | [Climate Equity Concepts]({DOCS_ROOT}/science/climate-equity-concepts/)

# %%
# Imports (run this first)
import matplotlib.pyplot as plt
import pandas as pd
from pyprojroot import here

# Import fair-shares library components
from fair_shares.library.allocations.pathways import (
    cumulative_per_capita_convergence,
    equal_per_capita,
    per_capita_adjusted,
)
from fair_shares.library.utils import ensure_string_year_columns
from fair_shares.library.utils.data.iamc import (
    calculate_world_total_timeseries,
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

# Add emission-category to emissions_ts index for adjusted allocation functions
emissions_ts = emissions_ts.assign(**{"emission-category": emission_category})
emissions_ts = emissions_ts.set_index("emission-category", append=True)

# Calculate world scenario emissions using utility function
print("\nCalculating world total emissions from regional data...")

world_emissions_ts = calculate_world_total_timeseries(
    regional_ts=emissions_ts,
    unit_level="unit",
    group_level="iso3c",
)

# Verify the sum for a sample year
sample_year = "2050"
regional_sum = emissions_ts[sample_year].sum()
world_total = world_emissions_ts[sample_year].iloc[0]
print(f"\nVerification (year {sample_year}):")
print(f"  Sum of regional emissions: {regional_sum:.2f} Mt CO2e/yr")
print(f"  World total: {world_total:.2f} Mt CO2e/yr")
print(f"  Match: {'Yes' if abs(regional_sum - world_total) < 0.01 else 'No'}")

# %% [markdown]
# ---
# ## Step 2: Equal Per Capita Pathway Allocation
#
# **Principle: Egalitarianism** - Each person gets an equal annual emission allowance.
#
# Formula: Regional share(year) = population(year) / world_population(year)
#
# See: docs/science/climate-equity-concepts.md (Equal Rights to Atmosphere)

# %%
# Calculate EPC allocation from 2015
result_epc = equal_per_capita(
    population_ts=population_ts,
    first_allocation_year=2015,
    emission_category=emission_category,
    preserve_first_allocation_year_shares=False,
    group_level="iso3c",
)

# Extract shares for sample years
sample_years = ["2015", "2030", "2050", "2075", "2100"]
shares_epc = result_epc.relative_shares_pathway_emissions[sample_years]

print(f"Approach: {result_epc.approach}\n")
print("Regional Pathway Shares (Equal Per Capita):\n")
print(f"{'Region':8s} {' '.join([f'{y:>7s}' for y in sample_years])}")
print("-" * (8 + len(sample_years) * 8))
for region in sorted(shares_epc.index.get_level_values("iso3c").unique()):
    region_data = shares_epc[shares_epc.index.get_level_values("iso3c") == region]
    values = [f"{region_data[y].values[0]*100:6.2f}%" for y in sample_years]
    print(f"{region:8s} {' '.join(values)}")

# Verify shares sum to 100%
print("\n" + "-" * 70)
print("VERIFICATION: Shares sum to 100% for each year")
print("-" * 70)
for year in sample_years:
    total_share = shares_epc[year].sum()
    print(
        f"  {year}: {total_share*100:.4f}% {'Yes' if abs(total_share - 1.0) < 0.0001 else 'No'}"
    )

# Show absolute emissions for one year as example
print("\n" + "-" * 70)
print(f"ABSOLUTE EMISSIONS (year {sample_years[2]}) - Mt CO2e/yr")
print("-" * 70)
world_total = world_emissions_ts[sample_years[2]].iloc[0]
print(f"World scenario total: {world_total:.2f} Mt CO2e/yr\n")
print("Regional allocations:")
regional_total = 0
for region in sorted(shares_epc.index.get_level_values("iso3c").unique()):
    region_data = shares_epc[shares_epc.index.get_level_values("iso3c") == region]
    share = region_data[sample_years[2]].values[0]
    allocation = share * world_total
    regional_total += allocation
    print(f"  {region:8s}: {allocation:8.2f} Mt CO2e/yr ({share*100:5.2f}%)")
print(f"  {'TOTAL':8s}: {regional_total:8.2f} Mt CO2e/yr")
print(
    f"\nAllocations sum to world total: {'Yes' if abs(regional_total - world_total) < 0.01 else 'No'}"
)

# %% [markdown]
# ---
# ## Step 3: Capability-Adjusted Pathway Allocation
#
# **Principle: Capability** - Wealthier regions contribute more mitigation effort each year.
#
# Key parameter: `capability_weight` (0.0-1.0)
# - 0.0 = Pure equal per capita
# - 0.5 = Balanced between population and capability
# - 1.0 = Fully weighted by GDP
#
# See: docs/science/climate-equity-concepts.md (Ability to Pay)

# %%
# Capability-adjusted allocation (50% weight on GDP)
result_cap = per_capita_adjusted(
    population_ts=population_ts,
    gdp_ts=gdp_ts,
    country_actual_emissions_ts=emissions_ts,
    first_allocation_year=2015,
    emission_category=emission_category,
    capability_weight=0.5,
    responsibility_weight=0.0,
    historical_responsibility_year=1990,  # Not used when responsibility_weight=0
    preserve_first_allocation_year_shares=False,
    group_level="iso3c",
)

shares_cap = result_cap.relative_shares_pathway_emissions[sample_years]

print(f"Approach: {result_cap.approach}\n")
print("Regional Pathway Shares (Capability 50%):\n")
print(f"{'Region':8s} {' '.join([f'{y:>7s}' for y in sample_years])}")
print("-" * (8 + len(sample_years) * 8))
for region in sorted(shares_cap.index.get_level_values("iso3c").unique()):
    region_data = shares_cap[shares_cap.index.get_level_values("iso3c") == region]
    values = [f"{region_data[y].values[0]*100:6.2f}%" for y in sample_years]
    print(f"{region:8s} {' '.join(values)}")

# %% [markdown]
# ---
# ## Step 4: Cumulative Per Capita Convergence
#
# **Principle: Equal rights with smooth transitions** - Transitions to equal per capita
# while preserving cumulative equity budgets.
#
# Unlike simple per capita convergence (which includes grandfathering), this approach:
# - Preserves cumulative equal per capita budgets
# - Allows flexible transition speeds
# - Avoids locking in current inequalities
#
# See: docs/science/principle-to-code.md (Convergence)

# %%
# Cumulative per capita convergence
result_conv = cumulative_per_capita_convergence(
    population_ts=population_ts,
    country_actual_emissions_ts=emissions_ts,
    world_scenario_emissions_ts=world_emissions_ts,
    first_allocation_year=2015,
    emission_category=emission_category,
    strict=False,
    group_level="iso3c",
)

shares_conv = result_conv.relative_shares_pathway_emissions[sample_years]

print(f"Approach: {result_conv.approach}\n")
print("Regional Pathway Shares (Cumulative Convergence):\n")
print(f"{'Region':8s} {' '.join([f'{y:>7s}' for y in sample_years])}")
print("-" * (8 + len(sample_years) * 8))
for region in sorted(shares_conv.index.get_level_values("iso3c").unique()):
    region_data = shares_conv[shares_conv.index.get_level_values("iso3c") == region]
    values = [f"{region_data[y].values[0]*100:6.2f}%" for y in sample_years]
    print(f"{region:8s} {' '.join(values)}")

# %% [markdown]
# ---
# ## Step 5: Compare Approaches
#
# Visualize how different approaches allocate emissions over time for a sample region.

# %%
# Select a region to visualize
TEST_REGION = "NAM"  # North America

# Extract data for this region
epc_region = shares_epc[shares_epc.index.get_level_values("iso3c") == TEST_REGION]
cap_region = shares_cap[shares_cap.index.get_level_values("iso3c") == TEST_REGION]
conv_region = shares_conv[shares_conv.index.get_level_values("iso3c") == TEST_REGION]

# Get all year columns
year_cols = [col for col in epc_region.columns if col.isdigit()]
years = [int(y) for y in year_cols]

# Create plot
fig, ax = plt.subplots(figsize=(12, 6))

ax.plot(
    years,
    epc_region[year_cols].values[0] * 100,
    marker="o",
    markersize=4,
    linewidth=2,
    label="Equal Per Capita",
    color="#2ecc71",
)

ax.plot(
    years,
    cap_region[year_cols].values[0] * 100,
    marker="s",
    markersize=4,
    linewidth=2,
    label="Capability 50%",
    color="#3498db",
)

ax.plot(
    years,
    conv_region[year_cols].values[0] * 100,
    marker="^",
    markersize=4,
    linewidth=2,
    label="Cumulative Convergence",
    color="#e74c3c",
)

ax.set_xlabel("Year", fontsize=12)
ax.set_ylabel("Regional Share (%)", fontsize=12)
ax.set_title(
    f"Pathway Allocation Shares Over Time - {TEST_REGION}",
    fontsize=14,
    fontweight="bold",
)
ax.legend(loc="best", fontsize=10)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.show()

# %% [markdown]
# ---
# ## Summary
#
# **Key takeaways:**
# 1. **Equal per capita**: Constant share = population share
# 2. **Capability-adjusted**: Higher-GDP regions get larger shares
# 3. **Cumulative convergence**: Smooth transition while matching equity budgets
#
# **For model input preparation**, see notebook 401.
#
# [Full guide]({DOCS_ROOT}/user-guide/country-fair-shares/)

# %%
