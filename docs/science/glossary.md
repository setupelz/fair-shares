---
title: Glossary
description: Definitions of key terms, parameters, and data structures in fair-shares
icon: material/book-alphabet
---

# Glossary

This page provides definitions for key terms used throughout the fair-shares documentation and codebase.

---

## Allocation Approaches

All approach names use `kebab-case` notation. For complete details, see the [Approach Catalog](../user-guide/approach-catalog.md).

!!! info "Key concept: allocation_year"

    All approaches incorporate historical responsibility via `allocation_year` (budget) or `first_allocation_year` (pathway). When set in the past, emissions from that year to present are subtracted, leaving different **remaining allocations** for each country. The `*-adjusted` approaches add further weighting on top of this mechanism.

### Budget Approaches

**`equal-per-capita-budget`**
: Population-proportional allocation. Historical accountability via `allocation_year` only.

**`per-capita-adjusted-budget`**
: Adds `responsibility_weight` and `capability_weight` adjustments. CBDR-RC.

**`per-capita-adjusted-gini-budget`**
: Adds Gini adjustment for within-country inequality. Subsistence protection.

### Pathway Approaches (Standard)

**`equal-per-capita`**
: Annual population-proportional shares. Historical accountability via `first_allocation_year`.

**`per-capita-adjusted`**
: Annual shares with responsibility/capability adjustments. CBDR-RC.

**`per-capita-adjusted-gini`**
: Annual shares with Gini adjustment. Subsistence protection.

### Pathway Approaches (Convergence)

**`per-capita-convergence`**
: Gradual transition to equal per capita. **Not a fair share approach**—includes grandfathering.

**`cumulative-per-capita-convergence`**
: Budget-preserving convergence. Distributes cumulative per capita shares over time. **Fair share approach.**

**`cumulative-per-capita-convergence-adjusted`** / **`-gini-adjusted`**
: Convergence with responsibility/capability/Gini adjustments.

See: [API Reference](../api/allocations/budgets.md) · [From Principle to Code](principle-to-code.md)

---

## Parameters

For detailed parameter effects and examples, see [Parameter Effects](parameter-effects.md).

### Core Parameters

**`allocation_year`** / **`first_allocation_year`** (type: `int`)
: Start year for cumulative accounting. Past emissions subtracted → different remaining allocations. No neutral default.
: Budget approaches use `allocation_year`; pathway approaches use `first_allocation_year`.

**`convergence_year`** (type: `int`)
: Target year for per capita convergence. Must be > allocation year. Convergence approaches only.

**`emission_category`** (type: `str`)
: Emission species (e.g., `"co2-ffi"`, `"co2"`, `"all-ghg"`, `"all-ghg-ex-co2-lulucf"`, `"non-co2"`). Must match data sources.

**`group_level`** (type: `str`, default: `"iso3c"`)
: Index level for countries/regions (ISO 3166-1 alpha-3 codes).

### Adjustment Weights

Constraint: `responsibility_weight + capability_weight ≤ 1.0`

**`responsibility_weight`** (type: `float`, default: `0.0`)
: Weight for historical emissions adjustment. Higher = more reduction for high emitters.

**`capability_weight`** (type: `float`, default: `0.0`)
: Weight for GDP-based adjustment. Higher = more reduction for wealthy countries.

### Responsibility Parameters

**`historical_responsibility_year`** (type: `int`, default: `1990`)
: Start year for cumulative emissions in responsibility calculation. Must be ≤ `allocation_year`.

**`responsibility_per_capita`** (type: `bool`, default: `True`)
: Per capita (True) or absolute (False) emissions for responsibility calculation.

**`responsibility_exponent`** (type: `float`, default: `1.0`)
: Exponent for responsibility adjustment. >1.0 increases non-linearity.

**`responsibility_functional_form`** (type: `str`, default: `"asinh"`)
: Functional form: `"asinh"` or `"power"`.

### Capability Parameters

**`capability_per_capita`** (type: `bool`, default: `True`)
: Per capita (True) or absolute (False) GDP for capability calculation.

**`capability_exponent`** (type: `float`, default: `1.0`)
: Exponent for capability adjustment. >1.0 increases non-linearity.

**`capability_functional_form`** (type: `str`, default: `"asinh"`)
: Functional form: `"asinh"` or `"power"`.

### Inequality Parameters

**`income_floor`** (type: `float`, default: `0.0`)
: Income below this threshold excluded from capability (subsistence protection).

**`max_gini_adjustment`** (type: `float`, default: `0.8`)
: Maximum Gini-based adjustment magnitude.

### Constraint Parameters

**`max_deviation_sigma`** (type: `float | None`, default: `2.0`)
: Outlier constraint (standard deviations from mean).

**`preserve_allocation_year_shares`** / **`preserve_first_allocation_year_shares`** (type: `bool`, default: `False`)
: Fix population shares at allocation year rather than recalculating dynamically.

---

## Result Types

### BudgetAllocationResult

Container for budget allocation results. Contains relative shares of a cumulative carbon budget.

**Attributes:**

- `approach` (str): Name of allocation approach (e.g., `"equal-per-capita-budget"`)
- `parameters` (dict): Parameter values used for allocation
- `relative_shares_cumulative_emission` ([TimeseriesDataFrame](#timeseriesdataframe)): Relative shares (fractions summing to 1.0) for each country. Has exactly one year column representing the allocation year.
- `country_warnings` (dict[str, str] | None): Optional warnings about data quality issues

**Methods:**

- `get_absolute_budgets(remaining_budget)`: Multiply relative shares by a global budget to get absolute country-level budgets

See: [Budget Approaches](https://setupelz.github.io/fair-shares/science/allocations/)

### PathwayAllocationResult

Container for pathway allocation results. Contains relative shares of annual emissions across multiple years.

**Attributes:**

- `approach` (str): Name of allocation approach (e.g., `"per-capita-adjusted"`)
- `parameters` (dict): Parameter values used for allocation
- `relative_shares_pathway_emissions` ([TimeseriesDataFrame](#timeseriesdataframe)): Relative shares (fractions summing to 1.0) for each country and year. Has multiple year columns.
- `country_warnings` (dict[str, str] | None): Optional warnings about data quality issues

**Methods:**

- `get_absolute_emissions(annual_emissions_budget)`: Multiply relative shares by global annual budgets to get absolute country-level pathways

See: [Pathway Approaches](https://setupelz.github.io/fair-shares/science/allocations/)

---

## Data Structures

### TimeseriesDataFrame

A `pandas.DataFrame` with a `pandas.MultiIndex` and year columns. The standard structure for all timeseries data in fair-shares.

**Index levels (in order):**

1. `iso3c` (str): ISO 3166-1 alpha-3 country code (e.g., `"USA"`, `"IND"`, `"DEU"`)
2. `unit` (str): Physical unit for the data (e.g., `"Mt CO2/yr"`, `"billion 2011 USD"`)
3. `emission-category` (str): Emission species (e.g., `"co2-ffi"`, `"all-ghg"`, `"non-co2"`)

**Columns:**

- Year columns as strings (e.g., `"2020"`, `"2021"`, ...)
- **Important:** Year columns must be strings, not integers. Use `ensure_string_year_columns(df)` after loading data.

**Example:**

```python
                                            2020    2021    2022
iso3c  unit       emission-category
USA    Mt CO2/yr  co2-ffi                  5000    4900    4800
IND    Mt CO2/yr  co2-ffi                  2500    2600    2700
World  Mt CO2/yr  co2-ffi                 35000   34500   34000
```

See: [Function Signature](https://setupelz.github.io/fair-shares/dev-guide/adding-approaches/#function-signature) for implementation details

### MultiIndex

A hierarchical index for pandas DataFrames. All fair-shares data uses a 3-level MultiIndex with levels `["iso3c", "unit", "emission-category"]`.

Operations like `.loc[]`, `.xs()`, and `.groupby()` can select/aggregate along specific index levels.

See: [pandas MultiIndex documentation](https://pandas.pydata.org/docs/user_guide/advanced.html)

---

## Equity Principles

Brief definitions. For detailed explanations and operationalization, see [Climate Equity Concepts](climate-equity-concepts.md) and [From Principle to Code](principle-to-code.md).

**Carbon Debt**
: Obligation owed by high-emitting nations that have exceeded their fair share of atmospheric space. Can be quantified in tonnes CO2 or monetary terms. Matthews [2016] calculates debts against an equal per capita benchmark; Pelz [2025a] introduces a net-zero framing. [Pickering 2012; Pelz 2025a; Matthews 2016]
: See: [Climate Equity Concepts](climate-equity-concepts.md#scientific-foundations)

**Cascading Biases**
: Systematic methodological choices in effort-sharing frameworks that compound to favor wealthy nations. Kartha [2018] identifies three types: scope bias (including cost-effectiveness alongside equity approaches), framing bias (late base years that embed grandfathering), and aggregation bias (equal weighting of ethically unequal approaches). [Kartha 2018]
: See: [Climate Equity Concepts](climate-equity-concepts.md#grandfathering)

**CBDR-RC**
: Common But Differentiated Responsibilities and Respective Capabilities. UNFCCC foundational principle: all countries share responsibility, but obligations differ based on historical emissions and economic capacity.
: See: [Climate Equity Concepts](climate-equity-concepts.md#overview)

**Egalitarianism**
: Ethical tradition grounding equal per capita entitlement to atmospheric space.
: See: [Climate Equity Concepts](climate-equity-concepts.md#equal-per-capita-entitlement)

**Equal per capita**
: Each person has equal entitlement to atmospheric space. In fair-shares, historical accountability is incorporated via `allocation_year` (past emissions subtracted), not via weight adjustments.
: See: [From Principle to Code](principle-to-code.md#equal-per-capita)

**Grandfathering**
: Allocating future entitlements based on current emission shares. Critiqued as lacking ethical basis. `per-capita-convergence` includes grandfathering elements.
: See: [Climate Equity Concepts](climate-equity-concepts.md#grandfathering)

**Historical responsibility**
: Past emissions reduce remaining fair share. Primary mechanism: `allocation_year` (earlier = more subtracted). Secondary: `responsibility_weight` in `*-adjusted` approaches.
: See: [From Principle to Code](principle-to-code.md#historical-responsibility)

**Negative Allocation**
: When a party's remaining fair share under a carbon budget is negative — its past emissions have already exceeded its equal per capita entitlement. Signals the need for highest possible domestic ambition, negative emissions targets (CDR), and international support. Negative allocations are a feature, not a bug: they communicate the scale of overshoot and the urgency of minimizing its duration and magnitude. [Pelz 2025b]
: See: [Allocation Approaches](allocations.md) · [Guidance](climate-equity-concepts.md)

**Subsistence protection**
: Basic needs emissions protected from mitigation burdens. Operationalized via `income_floor` and Gini adjustments.
: See: [From Principle to Code](principle-to-code.md#subsistence-protection)

---

## Abbreviations

**API**
: Application Programming Interface. In this documentation, refers to the function-level reference for allocation approaches.

**AR6**
: IPCC Sixth Assessment Report (2021-2023). Source of global emissions scenarios used in fair-shares.

**BAU**
: Business As Usual. Baseline emissions scenario without climate policy. Note: framing deviation from BAU as a "cost" or "sacrifice" has been critiqued in the literature as inconsistent with CBDR-RC (see Kartha 2018).

**Bookkeeping (BM)**
: LULUCF accounting method that estimates only direct human-caused land-use fluxes (deforestation, afforestation, land management). Used by IPCC for RCBs. Contrast with NGHGI, which additionally includes indirect effects. See: [NGHGI-Consistent RCB Corrections](other-operations.md#why-two-lulucf-conventions-matter)

**Bunker fuels**
: CO₂ emissions from international aviation and shipping. Included in global emission totals but excluded from national inventories (no country claims responsibility). Must be subtracted when converting global RCBs to country-allocatable budgets [Weber 2026].

**ECPC**
: Equal Cumulative Per Capita. An allocation approach that distributes a carbon budget equally on a cumulative per-capita basis, with past emissions subtracted from future entitlements.

**GDP**
: Gross Domestic Product. Economic output measure used for capability adjustments.

**GHG**
: Greenhouse Gas (e.g., CO2, CH4, N2O). "Kyoto GHG" refers to the basket of gases covered by the Kyoto Protocol.

**IAMC**
: Integrated Assessment Modeling Consortium. Data format used for AR6 scenarios.

**IPCC**
: Intergovernmental Panel on Climate Change.

**ISO 3166-1 alpha-3**
: Three-letter country codes (e.g., `USA`, `IND`, `DEU`). Standard for the `iso3c` index level.

**Mt CO2/yr**
: Megatonnes of CO2 per year. Common unit for annual emissions.

**Melo et al. (2026)**
: Country-reported NGHGI LULUCF CO₂ timeseries (v3.1). Covers 187 countries, 2000-2023. Replaces Grassi et al. (2023) with higher coverage and an additional year. See: [NGHGI-Consistent RCB Corrections](other-operations.md#weber-rcb-corrections)

**NGHGI**
: National Greenhouse Gas Inventory. Country-level emissions reporting under UNFCCC. Includes passive carbon fluxes (CO₂ fertilization, climate feedbacks) in LULUCF estimates, unlike bookkeeping models. See: [NGHGI-Consistent RCB Corrections](other-operations.md#weber-rcb-corrections)

**NGHGI-BM convention gap**
: The systematic difference between NGHGI and bookkeeping (BM) LULUCF CO₂ estimates. NGHGI includes indirect effects (CO₂ fertilization of managed forests) that BM excludes, making NGHGI a larger net sink. ~84 GtCO₂ for 1.5°C scenarios [Weber 2026]. See: [NGHGI-Consistent RCB Corrections](other-operations.md#correction-for-total-co2-budgets-co2)

**PRIMAP-hist**
: Historical emissions dataset from PIK (Potsdam Institute for Climate Impact Research).

**RCB**
: Remaining Carbon Budget. The amount of CO2 that can still be emitted while staying within a temperature target (e.g., 1.5°C). IPCC RCBs use bookkeeping LULUCF and include bunker fuels — conversion to NGHGI-consistent values requires corrections [Weber 2026]. See: [NGHGI-Consistent RCB Corrections](other-operations.md#weber-rcb-corrections)

**SSP**
: Shared Socioeconomic Pathway. Scenarios combining socioeconomic projections with climate mitigation levels (e.g., SSP1-1.9, SSP2-4.5).

**TCRE**
: Transient Climate Response to Cumulative Emissions. The near-linear relationship between cumulative CO2 emissions and global temperature increase.

**UNFCCC**
: United Nations Framework Convention on Climate Change.
