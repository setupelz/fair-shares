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
# # Parameter Effects Documentation Examples
#
# **Purpose:** Generate real allocation examples showing how parameters affect outcomes.
#
# This notebook produces tables for `docs/science/parameter-effects.md` demonstrating:
# - `allocation_year` / `first_allocation_year` effects
# - `pre_allocation_responsibility_weight` effects
# - `capability_weight` effects
# - `income_floor` effects
#
# **Output:** Markdown tables with real numeric values for USA, India, Germany

# %%
# Imports

import pandas as pd
from pyprojroot import here

from fair_shares.library.allocations.budgets import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)
from fair_shares.library.allocations.results import BudgetAllocationResult
from fair_shares.library.utils import (
    calculate_budget_from_rcb,
    ensure_string_year_columns,
    setup_data,
)

project_root = here()

# %% [markdown]
# ## Setup Data Pipeline
#
# Load required datasets for allocation calculations

# %%
# Data source configuration
active_sources = {
    "target": "rcbs",
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
    "lulucf": "melo-2026",
}

emission_category = "co2-ffi"

# Setup data pipeline
print("Setting up data pipeline...")
setup_info = setup_data(
    project_root=project_root,
    active_sources=active_sources,
    emission_category=emission_category,
    verbose=False,
)

# Extract paths and metadata
processed_dir = setup_info["paths"]["processed_dir"]
print(f"Data processed in: {processed_dir}")

# Load country data
print("Loading country data...")
emiss_path = processed_dir / f"country_emissions_{emission_category}_timeseries.csv"
emissions_ts = pd.read_csv(emiss_path)
emissions_ts = emissions_ts.set_index(["iso3c", "unit", "emission-category"])
emissions_ts = ensure_string_year_columns(emissions_ts)

gdp_ts = pd.read_csv(processed_dir / "country_gdp_timeseries.csv")
gdp_ts = gdp_ts.set_index(["iso3c", "unit"])
gdp_ts = ensure_string_year_columns(gdp_ts)

population_ts = pd.read_csv(processed_dir / "country_population_timeseries.csv")
population_ts = population_ts.set_index(["iso3c", "unit"])
population_ts = ensure_string_year_columns(population_ts)

gini_ts = pd.read_csv(processed_dir / "country_gini_stationary.csv")
gini_ts = gini_ts.set_index(["iso3c", "unit"])

# Load RCB data and world emissions
rcbs_df = pd.read_csv(processed_dir / f"rcbs_{emission_category}.csv")
world_emiss_path = processed_dir / f"world_emissions_{emission_category}_timeseries.csv"
world_emissions_df = pd.read_csv(world_emiss_path)
world_emissions_df = world_emissions_df.set_index(
    ["iso3c", "unit", "emission-category"]
)
world_emissions_df = ensure_string_year_columns(world_emissions_df)

# Extract RCB value for 1.5C scenario (50% probability)
rcb_row = rcbs_df[
    (rcbs_df["climate-assessment"] == "1.5C") & (rcbs_df["quantile"] == 0.5)
].iloc[0]
rcb_value = rcb_row["rcb_2020_nghgi_mt"]

# Calculate carbon budget
budget = calculate_budget_from_rcb(
    rcb_value=rcb_value,
    allocation_year=2025,
    world_scenario_emissions_ts=world_emissions_df,
    verbose=False,
)

print(f"RCB value (2020): {rcb_value / 1e9:.1f} GtCO2")
print(f"Global carbon budget (2025): {budget / 1e9:.1f} GtCO2")
print("Data loaded successfully!")

# %% [markdown]
# ## Example 1: allocation_year Effects
#
# Show how different allocation years affect remaining budgets from 2020.
# The main effect is historical emissions subtraction, not population shifts.


# %%
def get_country_shares(
    result: BudgetAllocationResult, countries: list[str]
) -> dict[str, float]:
    """Extract allocation shares for specified countries as percentages."""
    shares = result.relative_shares_cumulative_emission
    country_shares = {}
    for country in countries:
        if country in shares.index.get_level_values("iso3c"):
            # Get share for this country (sum to 1, so multiply by 100 for percentage)
            # Extract the scalar value from the series
            share_value = shares.loc[country].values[0] * 100
            country_shares[country] = float(share_value)
        else:
            country_shares[country] = 0.0
    return country_shares


# Countries to compare
example_countries = ["USA", "IND", "DEU"]

# Test different allocation years — show remaining budget from 2020
allocation_years = [2020, 1990, 1900]
allocation_year_remaining = {}

for year in allocation_years:
    # Global budget from allocation_year
    year_budget = calculate_budget_from_rcb(
        rcb_value=rcb_value,
        allocation_year=year,
        world_scenario_emissions_ts=world_emissions_df,
        verbose=False,
    )

    # Get population shares
    result = equal_per_capita_budget(
        population_ts=population_ts,
        allocation_year=year,
        emission_category=emission_category,
    )
    shares = result.relative_shares_cumulative_emission

    # Remaining budget = (share × global budget) - actual emissions to 2020
    country_remaining = {}
    for c in example_countries:
        share = float(shares.loc[c].values[0])
        alloc = share * year_budget  # in Mt
        emiss_cols = [
            str(y) for y in range(year, 2020) if str(y) in emissions_ts.columns
        ]
        if c in emissions_ts.index.get_level_values("iso3c") and emiss_cols:
            actual = float(emissions_ts.loc[c][emiss_cols].sum(axis=1).values[0])
        else:
            actual = 0.0
        country_remaining[c] = (alloc - actual) / 1e3  # Mt to Gt
    allocation_year_remaining[year] = country_remaining

# Create markdown table
print("## allocation_year Effects (Remaining Budget from 2020)\n")
print(
    "| Country | allocation_year=2020 | allocation_year=1990 | allocation_year=1900 |"
)
print("|---------|---------------------|---------------------|---------------------|")
for country in example_countries:
    country_name = {"USA": "USA", "IND": "India", "DEU": "Germany"}[country]
    remaining = [allocation_year_remaining[year][country] for year in allocation_years]
    print(
        f"| {country_name} | {remaining[0]:+.1f} GtCO2 | {remaining[1]:+.1f} GtCO2 | {remaining[2]:+.1f} GtCO2 |"
    )
print()

# %% [markdown]
# ## Example 2: pre_allocation_responsibility_weight Effects
#
# Show how responsibility weighting affects shares for per-capita-adjusted-budget

# %%
# Test responsibility ON vs OFF (with capability_weight=0.0).
# When capability_weight=0.0, any non-zero pre_allocation_responsibility_weight
# is the sole adjustment — its specific value doesn't matter (only the ratio
# between weights affects results). So we show OFF (0.0) vs ON (1.0).
pre_allocation_responsibility_weights = [0.0, 1.0]
responsibility_results = {}

for weight in pre_allocation_responsibility_weights:
    result = per_capita_adjusted_budget(
        population_ts=population_ts,
        country_actual_emissions_ts=emissions_ts,
        gdp_ts=gdp_ts,
        allocation_year=2020,
        emission_category=emission_category,
        pre_allocation_responsibility_weight=weight,
        capability_weight=0.0,  # Isolate responsibility effect
        pre_allocation_responsibility_year=1990,
    )
    responsibility_results[weight] = get_country_shares(result, example_countries)

# Create markdown table
print("## pre_allocation_responsibility_weight Effects\n")
print("Note: with capability_weight=0.0, any non-zero responsibility weight")
print("is the sole adjustment — 0.5 and 1.0 produce identical results.\n")
print("| Country | weight=0.0 (no adjustment) | weight=1.0 (responsibility only) |")
print("|---------|---------------------------|----------------------------------|")
for country in example_countries:
    country_name = {"USA": "USA", "IND": "India", "DEU": "Germany"}[country]
    shares = [
        responsibility_results[weight][country] for weight in pre_allocation_responsibility_weights
    ]
    print(
        f"| {country_name} | {shares[0]:.1f}% | {shares[1]:.1f}% |"
    )
print()

# %% [markdown]
# ## Example 3: capability_weight Effects
#
# Show how capability weighting affects shares for per-capita-adjusted-budget

# %%
# Test capability ON vs OFF (with pre_allocation_responsibility_weight=0.0).
# When pre_allocation_responsibility_weight=0.0, any non-zero capability_weight
# is the sole adjustment — its specific value doesn't matter (only the ratio
# between weights affects results). So we show OFF (0.0) vs ON (1.0).
capability_weights = [0.0, 1.0]
capability_results = {}

for weight in capability_weights:
    result = per_capita_adjusted_budget(
        population_ts=population_ts,
        country_actual_emissions_ts=emissions_ts,
        gdp_ts=gdp_ts,
        allocation_year=2020,
        emission_category=emission_category,
        pre_allocation_responsibility_weight=0.0,  # Isolate capability effect
        capability_weight=weight,
    )
    capability_results[weight] = get_country_shares(result, example_countries)

# Create markdown table
print("## capability_weight Effects\n")
print("Note: with pre_allocation_responsibility_weight=0.0, any non-zero capability weight")
print("is the sole adjustment — 0.5 and 1.0 produce identical results.\n")
print("| Country | weight=0.0 (no adjustment) | weight=1.0 (capability only) |")
print("|---------|---------------------------|------------------------------|")
for country in example_countries:
    country_name = {"USA": "USA", "IND": "India", "DEU": "Germany"}[country]
    shares = [capability_results[weight][country] for weight in capability_weights]
    print(
        f"| {country_name} | {shares[0]:.1f}% | {shares[1]:.1f}% |"
    )
print()

# %% [markdown]
# ## Example 4: income_floor Effects
#
# Show how different income floors affect shares for per-capita-adjusted-budget

# %%
# Test different income floors (USD per capita)
# Note: income_floor requires the Gini-adjusted approach
income_floors = [0, 7500, 15000]
income_floor_results = {}

for floor in income_floors:
    result = per_capita_adjusted_gini_budget(
        population_ts=population_ts,
        country_actual_emissions_ts=emissions_ts,
        gdp_ts=gdp_ts,
        gini_s=gini_ts,
        allocation_year=2020,
        emission_category=emission_category,
        pre_allocation_responsibility_weight=0.0,
        capability_weight=1.0,  # Capability only (sole adjustment when pre_allocation_responsibility_weight=0.0)
        income_floor=floor,
    )
    income_floor_results[floor] = get_country_shares(result, example_countries)

# Create markdown table
print("## income_floor Effects\n")
print("| Country | floor=0 | floor=7500 | floor=15000 |")
print("|---------|---------|-----------|-----------|")
for country in example_countries:
    country_name = {"USA": "USA", "IND": "India", "DEU": "Germany"}[country]
    shares = [income_floor_results[floor][country] for floor in income_floors]
    print(
        f"| {country_name} | {shares[0]:.1f}% | {shares[1]:.1f}% | {shares[2]:.1f}% |"
    )
print()

# %% [markdown]
# ## Summary
#
# The tables above show real allocation percentages for three representative countries:
# - **USA**: High historical emissions, high GDP
# - **India**: Large population, lower historical emissions per capita
# - **Germany**: Medium population, high historical emissions and GDP
#
# **Key patterns:**
# - Earlier `allocation_year` -> reduces shares for high historical emitters (USA, Germany)
# - Enabling pre-allocation responsibility (weight > 0) -> penalizes historical emissions
# - Enabling capability (weight > 0) -> reduces shares for wealthy countries (USA, Germany)
# - Only the ratio between the two weights matters (they are normalized by their sum)
# - Higher `income_floor` -> protects developing countries from capability adjustments
#
# Copy these tables into `docs/science/parameter-effects.md` for documentation.
