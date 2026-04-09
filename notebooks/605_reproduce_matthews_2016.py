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
# # 604 — Reproducing Gignac & Matthews (2015) / Matthews (2016): Fossil Carbon Debt
#
# **Papers:**
# - Matthews, H. D. (2016). Quantifying historical carbon and climate debts among nations.
#   *Nature Climate Change*, 6, 60--64. DOI: [10.1038/nclimate2774](https://doi.org/10.1038/nclimate2774)
# - Gignac, R. & Matthews, H. D. (2015). Allocating a 2 °C cumulative carbon budget to
#   countries. *Environmental Research Letters*, 10, 075004.
#   DOI: [10.1088/1748-9326/10/7/075004](https://doi.org/10.1088/1748-9326/10/7/075004)
#
# **Scope:** fossil-fuel CO2 carbon debt over both 1990-2013
# (Gignac & Matthews 2015 methodology) and 1960-2013 (Matthews 2016 primary baseline).
# Matthews 2016 also extends to "climate debt" via temperature attribution; that
# extension is not reproduced here -- see the gaps section.

# %% [markdown]
# ---
# ## 1. Method Extraction
#
# ### 1.1 Carbon Debt (Gignac & Matthews 2015, Equation 1; extended in Matthews 2016)
#
# The carbon debt of a country is defined as the cumulative difference between
# its actual CO2 emissions and the emissions it would have been entitled to under
# an equal per capita allocation of global emissions:
#
# $$
# \text{Carbon debt}_{\text{country}} = \sum_{t=t_{\text{start}}}^{t_{\text{end}}}
# \left[
#   E_{\text{country}}(t)
#   - E_{\text{world}}(t) \times \frac{P_{\text{country}}(t)}{P_{\text{world}}(t)}
# \right]
# $$
#
# where:
# - $E_{\text{country}}(t)$ = actual CO2 emissions of the country in year $t$
#   (paper uses fossil fuel + land use; allocation uses fossil fuel only --
#   see Gaps section; units: MtCO2/yr)
# - $E_{\text{world}}(t)$ = total global CO2 emissions in year $t$
# - $P_{\text{country}}(t)$ = population of the country in year $t$
# - $P_{\text{world}}(t)$ = world population in year $t$
# - $t_{\text{start}}$ = 1990 (Gignac & Matthews 2015, Methods: "commonly cited as
#   the year in which the scientific basis of anthropogenic climate change was
#   sufficiently well established")
# - $t_{\text{end}}$ = year of assessment (2013 for the historical calculation in
#   both papers)
#
# A positive value indicates a **carbon debt** (country has emitted more than its
# equal per capita share). A negative value indicates a **carbon credit** (country
# has emitted less than its share).
#
# ### 1.2 Equal Per Capita Share (the counterfactual benchmark)
#
# The equal per capita allocation embedded in the carbon debt equation assigns each
# country a share of global emissions proportional to its share of world population
# in each year:
#
# $$
# E_{\text{country}}^{\text{epc}}(t) = E_{\text{world}}(t) \times
# \frac{P_{\text{country}}(t)}{P_{\text{world}}(t)}
# $$
#
# This is an annual flow allocation, not a budget allocation. The carbon debt is
# the cumulative sum of the annual difference between actual and EPC emissions.
#
# ### 1.3 Climate Debt (Matthews 2016 extension)
#
# Matthews 2016 extends carbon debt to "climate debt" by converting cumulative CO2
# overshoot to a temperature contribution using the Transient Climate Response to
# cumulative CO2 Emissions (TCRE):
#
# A first-order approximation (not what the paper uses):
#
# $$
# \text{Climate debt}_{\text{country}} \approx \text{TCRE} \times
# \text{Carbon debt}_{\text{country}}
# $$
#
# The TCRE relates cumulative CO2 emissions linearly to global temperature change
# (Matthews et al. 2009; Allen et al. 2009). Matthews 2016 converts carbon debt
# to temperature contributions using the methodology of Matthews et al. (2014),
# which attributes national contributions to observed warming. The exact
# conversion method in Matthews 2016 is not reproducible from the Gignac &
# Matthews 2015 companion paper alone -- it is the primary novel contribution
# of the 2016 paper.
#
# ### 1.4 Key Parameters
#
# | Parameter | Value | Source |
# |-----------|-------|--------|
# | Start year for debt accounting | **Two cases: 1990-2013 (Gignac & Matthews 2015) and 1960-2013 (Matthews 2016 primary baseline)** | Matthews 2016 uses 1960 as the primary baseline for fossil fuel carbon debt (Fig. 1, Fig. 2; reports ~500 GtCO2 world debt 1960-2013). 1990 is used in Matthews 2016 only for the climate debt calculation (non-CO2 data limits). Gignac & Matthews 2015 uses 1990 exclusively. Both cases are run. |
# | End year (historical) | 2013 | Gignac & Matthews 2015 |
# | Gases for carbon debt | CO2 (fossil fuel + land use) | Gignac & Matthews 2015 Methods: "we have already emitted 1970 Gt CO2 up to the year 2013 (including both fossil fuel and land-use emissions)"; uses CDIAC data which includes both |
# | Emissions dataset | PRIMAP-hist v2.6.1 (2025); **CDIAC via Global Carbon Budget 2014 in Matthews 2016 and Gignac & Matthews 2015** | PRIMAP-hist is a different dataset with different vintage and methodology. PRIMAP's 1990-2013 fossil CO2 world total (~700 GtCO2) is materially higher than Matthews 2016's reported 630 GtCO2 (which also includes LULUCF). Absolute debt numbers and mid-tier country rankings will differ from the paper. Disclosed as a deviation; not easily fixable without ingesting a historical GCB series. |
# | Population data | UN World Population Prospects | Gignac & Matthews 2015 Methods |
# | Global carbon budget (for C&C) | 1000 GtCO2 from 2014 | Gignac & Matthews 2015 |
# | Convergence years tested | 2035, 2050 | Gignac & Matthews 2015; C&C with linear transition from current emission shares to equal per capita at convergence year |

# %% [markdown]
# ---
# ## 2. Mapping to fair-shares
#
# | Paper approach | fair-shares function | Key parameters | Notes |
# |---|---|---|---|
# | Equal per capita share (annual) | `equal-per-capita` (pathway) | `first_allocation_year=1990` | Produces annual population-based shares; this is exactly the counterfactual in Eq. 1 |
# | Equal per capita budget | `equal-per-capita-budget` | `allocation_year=2015` | **Reference comparison only** -- not a reproduction of any paper formula. The paper computes annual flow-based debt (Eq. 1), not cumulative budget shares. Included to show how fair-shares' budget allocation relates to the paper's concept. |
# | Carbon debt (cumulative overshoot) | Post-processing | Computed from actual emissions minus EPC allocation | Not a direct fair-shares function |
# | Climate debt (temperature from debt) | Not expressible | Requires TCRE / simple climate model | See Gaps section |
#
# **Mapping strategy:** The carbon debt calculation is fundamentally a comparison
# between actual historical emissions and a counterfactual equal per capita
# allocation. We can:
#
# 1. Run fair-shares `equal-per-capita` (pathway) to get year-by-year population
#    shares, then compute cumulative overshoot from those shares
# 2. Independently compute the carbon debt using the raw annual formula from the
#    paper (Eq. 1), working directly with fair-shares preprocessed emissions and
#    population data
#
# We take approach (2) because the carbon debt formula operates on annual flows
# (actual minus EPC per year), summed cumulatively. This is more transparent and
# directly maps to the paper's equation. The `equal-per-capita-budget` allocation
# (run in Section 4.2) is included as a reference comparison only -- it shows
# how population-based budget shares relate to the paper's concept but does not
# reproduce any formula from the paper.

# %% [markdown]
# ---
# ## 3. Configuration

# %%
# =============================================================================
# CONFIGURATION
# =============================================================================

allocation_folder = "605_matthews_2016"

# DEVIATION: The paper uses total CO2 (fossil fuel + land use change), citing
# CDIAC data that "includes both fossil fuel and land-use emissions" (Gignac &
# Matthews 2015 Methods). We use co2-ffi (fossil fuel only) because total CO2
# ("co2") requires NGHGI LULUCF preprocessing (notebooks 105/107). The carbon
# debt formula is identical regardless of emission scope -- the conceptual
# reproduction is valid, but absolute values will differ, particularly for
# countries with large LULUCF fluxes (Brazil, Indonesia). See Gaps section.
emission_category = "co2-ffi"

# DEVIATION: This calculation uses production-based (territorial) emissions.
# Matthews 2016 discusses consumption-based emissions as a sensitivity
# (Supplementary Methods + Supplementary Fig. 3), finding transfers of >35%
# for Japan, Germany, UK (as net importers), Russia (as a net exporter), and
# China (whose exported carbon debt is almost twice its production-based
# carbon credit). fair-shares uses PRIMAP-hist production-based data by
# default; consumption-based reproduction is not attempted here.

active_sources = {
    "target": "rcbs",
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
    "lulucf": "melo-2026",
}

# --- Carbon debt parameters ---
# Two baseline windows: 1990 (Gignac & Matthews 2015 primary) and 1960 (Matthews 2016 primary).
DEBT_START_YEAR = 1990
DEBT_END_YEAR = 2013

# --- Fair-shares allocation for comparison ---
allocations = {
    # APPROACH 1: EPC budget — reference comparison against paper's annual-flow debt formula
    "equal-per-capita-budget": [
        {
            "allocation_year": [2015],
            "preserve_allocation_year_shares": [False],
        }
    ],
}

# Carbon debt (Gignac & Matthews 2015 Eq. 1): computed as post-processing
# in §4.3 from preprocessed emissions and population data.

# Climate debt (Matthews 2016): requires per-country TCRE-based temperature
# attribution. Not expressible in fair-shares.

EXAMPLE_COUNTRIES = ["USA", "CHN", "IND", "DEU", "BRA", "RUS", "GBR", "FRA", "CAN"]
PLOT_START_YEAR = 1990

# %% [markdown]
# ---
# ## 4. Run Allocation
#
# We use already-processed data from a previous `all-ghg` pipeline run, which
# includes co2-ffi emissions, population, and GDP data. This avoids re-running
# the full Snakemake pipeline.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyprojroot import here

from fair_shares.library.allocations import run_parameter_grid
from fair_shares.library.utils.dataframes import ensure_string_year_columns

plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()

# %% [markdown]
# ### 4.1 Load Pre-processed Data
#
# Use data from the existing all-ghg pipeline run (which includes co2-ffi).

# %%
# Locate the processed data directory from a previous all-ghg run
source_id = "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_melo-2026_rcbs_all-ghg"
processed_dir = project_root / "output" / source_id / "intermediate" / "processed"

assert processed_dir.exists(), f"Processed data not found at {processed_dir}"

# Load country emissions (co2-ffi)
country_emissions = pd.read_csv(
    processed_dir / "country_emissions_co2-ffi_timeseries.csv"
).set_index(["iso3c", "unit", "emission-category"])
country_emissions = ensure_string_year_columns(country_emissions)
print(f"Country emissions: {country_emissions.shape}")

# Load world emissions (co2-ffi)
world_emissions_ts = pd.read_csv(
    processed_dir / "world_emissions_co2-ffi_timeseries.csv"
).set_index(["iso3c", "unit", "emission-category"])
world_emissions_ts = ensure_string_year_columns(world_emissions_ts)
print(f"World emissions: {world_emissions_ts.shape}")

# Load population
country_population = pd.read_csv(
    processed_dir / "country_population_timeseries.csv"
).set_index(["iso3c", "unit"])
country_population = ensure_string_year_columns(country_population)
print(f"Population: {country_population.shape}")

print("\nData loaded successfully.")

# %% [markdown]
# ### 4.2 Run EPC Budget Allocation (fair-shares reference)
#
# Run the standard fair-shares equal per capita budget allocation for comparison.
# This shows the population-share-based allocation of remaining carbon budgets.

# %%
results = run_parameter_grid(
    allocations_config=allocations,
    population_ts=country_population,
    country_actual_emissions_ts=country_emissions,
    world_scenario_emissions_ts=world_emissions_ts,
    emission_category="co2-ffi",
    target_source="rcbs",
)

print(f"\nEPC budget allocation completed: {len(results)} result(s)")
for r in results:
    shares = r.relative_shares_cumulative_emission
    year_col = shares.columns[0]
    print(f"  {r.approach} (year={year_col})")
    print(f"  Shares sum: {shares[year_col].sum():.6f} (should be ~1.0)")

    # Show shares for example countries
    example_shares = shares.loc[
        shares.index.get_level_values("iso3c").isin(EXAMPLE_COUNTRIES)
    ].droplevel([l for l in shares.index.names if l != "iso3c"])
    print(f"\n  Example country shares (population-based):")
    for country in EXAMPLE_COUNTRIES:
        if country in example_shares.index:
            print(f"    {country}: {example_shares.loc[country, year_col]:.4f}")

# %% [markdown]
# > **Reference only, not paper reproduction.** The `equal-per-capita-budget`
# > allocation above is included to show how fair-shares' population-based
# > budget shares relate conceptually to the paper's equal-per-capita
# > counterfactual. It does **not** reproduce any formula from Matthews 2016 or
# > Gignac & Matthews 2015 -- both papers use the annual flow-based carbon debt
# > formula (Eq. 1), which is computed in Section 4.3 below.

# %% [markdown]
# ---
# ### 4.3 Carbon Debt Calculation (Matthews Formula)
#
# This section implements Equation (1) from Gignac & Matthews (2015) directly,
# using the preprocessed emissions and population data from fair-shares.
#
# The carbon debt is computed year-by-year as the difference between actual
# country emissions and the equal per capita share of world emissions, then
# summed cumulatively.

# %%
# Prepare data for carbon debt calculation
# Drop index levels for numeric operations
emissions_numeric = country_emissions.droplevel(["unit", "emission-category"])
population_numeric = country_population.droplevel("unit")

# Identify year columns within the debt accounting period
year_cols = sorted(
    [c for c in emissions_numeric.columns if DEBT_START_YEAR <= int(c) <= DEBT_END_YEAR],
    key=int,
)

# Ensure both DataFrames have the same countries and years
common_countries = emissions_numeric.index.intersection(population_numeric.index)
emissions_subset = emissions_numeric.loc[common_countries, year_cols]
population_subset = population_numeric.loc[common_countries, year_cols]

print(f"Countries in both datasets: {len(common_countries)}")
print(f"Year range: {year_cols[0]} to {year_cols[-1]}")
print(f"Number of years: {len(year_cols)}")

# %%
# =============================================================================
# CARBON DEBT CALCULATION (Gignac & Matthews 2015, Equation 1)
# =============================================================================

# World totals per year
world_emissions_annual = emissions_subset.sum(axis=0)
world_population_annual = population_subset.sum(axis=0)

# Equal per capita allocation (annual):
# EPC_country(t) = E_world(t) * P_country(t) / P_world(t)
pop_shares = population_subset.div(world_population_annual, axis=1)
epc_allocation = pop_shares.mul(world_emissions_annual, axis=1)

# Annual overshoot: actual - EPC
annual_overshoot = emissions_subset - epc_allocation

# Cumulative carbon debt: running sum of annual overshoot
cumulative_debt = annual_overshoot.cumsum(axis=1)

# Final carbon debt at end year
carbon_debt_final = cumulative_debt[str(DEBT_END_YEAR)]

print(f"\nCarbon debt at end of {DEBT_END_YEAR} (top 10 debtors, MtCO2):")
print(carbon_debt_final.sort_values(ascending=False).head(10).round(0))
print(f"\nCarbon credit at end of {DEBT_END_YEAR} (top 10 creditors, MtCO2):")
print(carbon_debt_final.sort_values(ascending=True).head(10).round(0))

# %%
# =============================================================================
# NUMERICAL CROSS-CHECK AGAINST PAPER HEADLINES (1990-2013, fossil-only)
# =============================================================================
# Compare against the headline numbers reported in Gignac & Matthews 2015 and
# Matthews 2016. Differences are EXPECTED because:
#   (a) PRIMAP-hist v2.6.1 vs CDIAC/GCB-2014 (different dataset, different vintage),
#   (b) fossil-only here vs fossil + LULUCF in the paper.
# This is a sanity check on order of magnitude, not a pass/fail validation.

total_positive_debt = carbon_debt_final[carbon_debt_final > 0].sum()
total_negative_debt = carbon_debt_final[carbon_debt_final < 0].sum()
world_cumulative_emissions = world_emissions_annual.sum()
debt_fraction = total_positive_debt / world_cumulative_emissions

print(f"\n--- 1990-2013 fossil-only headline cross-check ---")
print(f"Total positive carbon debt:   {total_positive_debt / 1000:>8.1f} GtCO2")
print(f"Total negative carbon credit: {total_negative_debt / 1000:>8.1f} GtCO2")
print(f"World cumulative fossil CO2:  {world_cumulative_emissions / 1000:>8.1f} GtCO2")
print(f"Debt as fraction of total:    {debt_fraction:>8.1%}")
print(
    f"\nReference (Gignac & Matthews 2015, fossil + LULUCF, CDIAC):"
    f"\n  ~250 GtCO2 positive carbon debt 1990-2013"
)
print(
    f"\nNote: divergence here is expected -- PRIMAP-hist"
    f"\nfossil-only data, not the CDIAC/GCB-2014 fossil + LULUCF series."
)

# %% [markdown]
# ### 4.4 Visualize Carbon Debt Over Time

# %%
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# --- Panel 1: Cumulative carbon debt over time for selected countries ---
ax1 = axes[0]
years_int = [int(y) for y in year_cols]
for country in EXAMPLE_COUNTRIES:
    if country in cumulative_debt.index:
        values = cumulative_debt.loc[country].values.astype(float)
        ax1.plot(years_int, values / 1000, label=country, linewidth=2)

ax1.axhline(y=0, color="black", linewidth=0.5, linestyle="-")
ax1.set_xlabel("Year")
ax1.set_ylabel("Cumulative carbon debt (GtCO2)")
ax1.set_title(
    f"Cumulative carbon debt ({DEBT_START_YEAR}\u2013{DEBT_END_YEAR})\n"
    "Positive = debt (exceeded EPC share), Negative = credit"
)
ax1.legend(loc="best", fontsize=9)

# --- Panel 2: Bar chart of final carbon debt ---
ax2 = axes[1]
debt_selected = carbon_debt_final.loc[
    [c for c in EXAMPLE_COUNTRIES if c in carbon_debt_final.index]
].sort_values(ascending=True)

colors = ["#2ecc71" if v < 0 else "#e74c3c" for v in debt_selected.values]
ax2.barh(debt_selected.index, debt_selected.values / 1000, color=colors)
ax2.set_xlabel("Carbon debt at end of 2013 (GtCO2)")
ax2.set_title(
    f"Carbon debt by country (end {DEBT_END_YEAR})\n"
    "Red = debt, Green = credit"
)
ax2.axvline(x=0, color="black", linewidth=0.5)

plt.tight_layout()
plt.show()

# %% [markdown]
# ### 4.5 Per Capita Carbon Debt

# %%
# Per capita carbon debt = carbon debt / population at end year
pop_end_year = population_subset[str(DEBT_END_YEAR)]
per_capita_debt = carbon_debt_final / pop_end_year  # MtCO2 / millions = tCO2/person

fig, ax = plt.subplots(figsize=(10, 6))
debt_pc_selected = per_capita_debt.loc[
    [c for c in EXAMPLE_COUNTRIES if c in per_capita_debt.index]
].sort_values(ascending=True)

colors = ["#2ecc71" if v < 0 else "#e74c3c" for v in debt_pc_selected.values]
ax.barh(debt_pc_selected.index, debt_pc_selected.values, color=colors)
ax.set_xlabel("Per capita carbon debt (tCO2/person)")
ax.set_title(
    f"Per capita carbon debt at end of {DEBT_END_YEAR}\n"
    "(cumulative overshoot of equal per capita share since 1990)"
)
ax.axvline(x=0, color="black", linewidth=0.5)

plt.tight_layout()
plt.show()

# %% [markdown]
# ### 4.6 Accounting Identity: Carbon Debts Sum to Zero Globally
#
# By construction, the sum of carbon debts and credits is **identically zero**
# at every year because the EPC allocation is defined as a redistribution of
# the same world emissions across population shares. This is an algebraic
# accounting identity, **not a validation against the paper**. It only confirms
# that the cumulative-sum and division operations preserved arithmetic
# precision -- it tells us nothing about whether the dataset, scope, or
# start year match Matthews 2016.

# %%
global_sum = carbon_debt_final.sum()
print(f"Global sum of carbon debts: {global_sum:.2f} MtCO2")
print(
    f"Accounting identity holds (residual < 1 MtCO2): "
    f"{'OK' if abs(global_sum) < 1.0 else 'NUMERICAL DRIFT'}"
)
print("(This is a self-consistency check, NOT a paper validation.)")

# %% [markdown]
# ### 4.7 Parallel 1960-2013 Case (Matthews 2016 Primary Baseline)
#
# Sections 4.3-4.6 above implement the Gignac & Matthews (2015) methodology with
# `DEBT_START_YEAR = 1990`. Matthews 2016's **primary** baseline for fossil
# carbon debt is 1960 (Fig. 1, Fig. 2; ~500 GtCO2 world positive debt 1960-2013).
# This cell reruns the same Eq. 1 calculation with `start_year = 1960` and
# prints the headline numbers for cross-checking against Matthews 2016.
#
# This is an additional cross-check, not a refactor of the primary calculation
# flow. The plots and per-capita debt analysis above stay anchored to the
# 1990-2013 window for consistency with Gignac & Matthews 2015.

# %%
# =============================================================================
# CARBON DEBT CALCULATION (Matthews 2016 primary baseline: 1960-2013)
# =============================================================================

start_year_1960 = 1960

# Identify year columns within the 1960-2013 window
year_cols_1960 = sorted(
    [
        c
        for c in emissions_numeric.columns
        if start_year_1960 <= int(c) <= DEBT_END_YEAR
    ],
    key=int,
)

# Some countries may not have data back to 1960; intersect on common availability
# and drop rows that are entirely NaN over the 1960 window.
emissions_subset_1960 = emissions_numeric.loc[common_countries, year_cols_1960]
population_subset_1960 = population_numeric.loc[common_countries, year_cols_1960]

# Drop countries with no emissions data anywhere in the 1960 window
emissions_subset_1960 = emissions_subset_1960.dropna(how="all")
population_subset_1960 = population_subset_1960.loc[emissions_subset_1960.index]

print(f"Year range: {year_cols_1960[0]} to {year_cols_1960[-1]}")
print(f"Number of years: {len(year_cols_1960)}")
print(f"Countries with emissions data over 1960-2013: {len(emissions_subset_1960)}")

# World totals per year (1960-2013)
world_emissions_annual_1960 = emissions_subset_1960.sum(axis=0)
world_population_annual_1960 = population_subset_1960.sum(axis=0)

# Equal per capita allocation (annual)
pop_shares_1960 = population_subset_1960.div(world_population_annual_1960, axis=1)
epc_allocation_1960 = pop_shares_1960.mul(world_emissions_annual_1960, axis=1)

# Annual overshoot and cumulative carbon debt
annual_overshoot_1960 = emissions_subset_1960 - epc_allocation_1960
cumulative_debt_1960 = annual_overshoot_1960.cumsum(axis=1)
carbon_debt_final_1960 = cumulative_debt_1960[str(DEBT_END_YEAR)]

# Headline numbers
total_positive_debt_1960 = carbon_debt_final_1960[carbon_debt_final_1960 > 0].sum()
total_negative_debt_1960 = carbon_debt_final_1960[carbon_debt_final_1960 < 0].sum()
world_cumulative_emissions_1960 = world_emissions_annual_1960.sum()

print(f"\n--- 1960-2013 vs 1990-2013 headline comparison (fossil-only, PRIMAP-hist) ---")
print(
    f"Total positive carbon debt 1960-2013: "
    f"{total_positive_debt_1960 / 1000:>7.1f} GtCO2  "
    f"(Matthews 2016 primary headline: ~500)"
)
print(
    f"Total positive carbon debt 1990-2013: "
    f"{total_positive_debt / 1000:>7.1f} GtCO2  "
    f"(Gignac & Matthews 2015: ~250)"
)
print(
    f"\nWorld cumulative fossil CO2 1960-2013: "
    f"{world_cumulative_emissions_1960 / 1000:.1f} GtCO2"
)
print(
    f"World cumulative fossil CO2 1990-2013: "
    f"{world_cumulative_emissions / 1000:.1f} GtCO2"
)

print(f"\nTop 10 debtors 1960-2013 (GtCO2):")
print((carbon_debt_final_1960.sort_values(ascending=False).head(10) / 1000).round(1))
print(f"\nTop 10 creditors 1960-2013 (GtCO2):")
print((carbon_debt_final_1960.sort_values(ascending=True).head(10) / 1000).round(1))

print(
    f"\nNote: divergence from Matthews 2016 headline numbers is expected --"
    f"\nPRIMAP-hist v2.6.1 fossil-only data is used here, not the"
    f"\nCDIAC/GCB-2014 fossil + LULUCF series Matthews 2016 used."
)

# %% [markdown]
# ---
# ## 5. Implementation Notes
#
# This notebook implements the carbon debt methodology from Gignac & Matthews
# (2015) and Matthews (2016) using fair-shares' canonical data stack. The
# equations in § 1 are realised with the configurations in § 3; this section
# documents the implementation choices.
#
# ### 5.1 Data stack
#
# | Source role | Dataset |
# |---|---|
# | Emissions | PRIMAP-hist v2.6.1 (`primap-202503`) |
# | Population | UN WPP via Our World in Data (`un-owid-2025`) |
# | GDP | World Development Indicators (`wdi-2025`) |
# | Gini | UNU-WIDER (`unu-wider-2025`) |
# | LULUCF | Melo et al. 2026 (`melo-2026`) |
# | RCB anchor | Remaining Carbon Budgets (`rcbs`) |
#
# GDP and Gini are loaded as part of the standard pipeline initialisation even
# though the carbon debt formula itself only requires emissions and population.
# The `equal-per-capita-budget` reference allocation in § 4.2 is driven by
# population shares alone.
#
# ### 5.2 Key architectural choices
#
# Matthews 2016 and Gignac & Matthews 2015 use an equal per capita counterfactual
# applied to annual emissions flows: each country's carbon debt is the cumulative
# sum of the difference between its actual emissions and its population-proportional
# share of world emissions. This is a pre-allocation framing — the responsibility
# assignment is embedded in the counterfactual benchmark, not in a fair-shares
# `pre_allocation_responsibility_*` parameter. § 2 maps the paper's Eq. 1
# directly to a post-processing calculation over fair-shares preprocessed data
# rather than routing through any single library allocation function.
#
# The `equal-per-capita-budget` allocation run in § 4.2 is a reference
# comparison: it uses fair-shares' population-based budget share logic (covering
# the remaining carbon budget from an anchor year) and is structurally distinct
# from the annual-flow carbon debt formula. Both are included so readers can see
# how the two population-proportional approaches relate.
#
# ### 5.3 Where fair-shares and Matthews differ on inputs
#
# Matthews 2016 reports results in country-level terms and uses CDIAC/GCB-2014
# data covering both fossil fuel and land-use CO2. This notebook uses
# PRIMAP-hist v2.6.1 fossil-only (`co2-ffi`) because the LULUCF pipeline
# (notebooks 105/107) is not wired in here. The carbon debt formula is applied
# identically in both the 1990–2013 window (Gignac & Matthews 2015 primary
# baseline) and the 1960–2013 window (Matthews 2016 primary baseline for fossil
# carbon debt). Matthews 2016's extension to climate debt via temperature
# attribution (Eq. 2) requires country-level temperature attribution that
# fair-shares does not provide and is not implemented here.
#
# Downstream users comparing fair-shares output to Matthews' published figures
# should expect differences driven by these data stack choices — principally the
# emissions dataset (PRIMAP-hist vs CDIAC/GCB-2014) and the exclusion of LULUCF
# — rather than by methodological divergence in the carbon debt accounting.

# %%
