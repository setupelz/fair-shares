---
title: Glossary
description: Definitions of key terms, parameters, and data structures in fair-shares
icon: material/book-alphabet
---

# Glossary

This page provides definitions for key terms used throughout the fair-shares documentation and codebase.

---

## Allocation Approaches

All approach names use `kebab-case` notation. See the [Approach Catalog](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/) for complete details.

### Budget Approaches

**`equal-per-capita-budget`**
: Allocates a cumulative carbon budget proportional to population shares at the allocation year. Operationalizes the equal rights to atmosphere principle without historical responsibility or capability adjustments.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/budgets/#equal_per_capita_budget) · [Egalitarianism](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`per-capita-adjusted-budget`**
: Allocates a cumulative carbon budget based on population, adjusted by historical responsibility and economic capability. Operationalizes CBDR-RC principles.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_budget) · [CBDR-RC](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`per-capita-adjusted-gini-budget`**
: Allocates a cumulative carbon budget with responsibility and capability adjustments, accounting for intra-national inequality via the Gini coefficient. Operationalizes capability (ability to pay) with subsistence protection.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_gini_budget) · [Subsistence Protection](https://setupelz.github.io/fair-shares/science/principle-to-code/)

### Pathway Approaches (Standard)

**`equal-per-capita`**
: Allocates annual emissions along a pathway proportional to population shares. Equal rights to atmosphere principle applied year-by-year.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/pathways/#equal_per_capita) · [Egalitarianism](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`per-capita-adjusted`**
: Allocates annual emissions along a pathway with historical responsibility and capability adjustments. CBDR-RC principles applied year-by-year.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted) · [CBDR-RC](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`per-capita-adjusted-gini`**
: Allocates annual emissions along a pathway with responsibility, capability, and inequality adjustments. Includes subsistence protection.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted_gini) · [Subsistence Protection](https://setupelz.github.io/fair-shares/science/principle-to-code/)

### Pathway Approaches (Convergence)

**`per-capita-convergence`**
: Transitions from current emission patterns toward equal per capita emissions by a convergence year. **Note:** Privileges current emission patterns during transition and is not considered a fair share approach.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_convergence) · [Convergence](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`cumulative-per-capita-convergence`**
: Budget-preserving convergence approach that distributes equal cumulative per capita shares from current emissions over time. Preserves cumulative per capita totals while creating smooth transition pathways. Can lead to steep curves when starting from current emissions. **This is a fair share approach** (unlike `per-capita-convergence` which includes grandfathering).
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence) · [Historical Responsibility](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`cumulative-per-capita-convergence-adjusted`**
: Cumulative convergence approach with additional historical responsibility and capability adjustments via weighting parameters.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence_adjusted)

**`cumulative-per-capita-convergence-gini-adjusted`**
: Cumulative convergence approach with responsibility, capability, and inequality adjustments.
: See: [API Reference](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence_adjusted_gini)

---

## Parameters

### Core Parameters

**`allocation_year`** (type: `int`)
: The year when entitlements begin. Operationalizes historical responsibility: earlier years imply historical over-emitters have already consumed their fair share from that date forward. No neutral default—this is a normative choice.
: Constraints: Must be ≥ `historical_responsibility_year` if responsibility adjustment is used
: See: [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/) · [Historical Responsibility](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`convergence_year`** (type: `int`)
: Target year by which per capita emissions converge to equality. Used only in convergence approaches.
: Constraints: Must be > `allocation_year`
: See: [Convergence](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`emission_category`** (type: `str`)
: The emission species being allocated (e.g., `"CO2"`, `"Kyoto GHG"`). Must match data sources.
: See: [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)

**`group_level`** (type: `str`, default: `"iso3c"`)
: MultiIndex level representing countries/regions (typically `"iso3c"` for ISO 3166-1 alpha-3 codes).
: See: [TimeseriesDataFrame](#timeseriesdataframe)

### Adjustment Weights

All weights must satisfy: `responsibility_weight + capability_weight ≤ 1.0`

**`responsibility_weight`** (type: `float`, range: `[0.0, 1.0]`, default: `0.0`)
: Weight for historical responsibility adjustment. Reduces allocation for countries with higher historical emissions.
: Constraints: `0.0 ≤ responsibility_weight ≤ 1.0`, requires `country_actual_emissions_ts` if > 0
: See: [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/) · [Historical Responsibility](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`capability_weight`** (type: `float`, range: `[0.0, 1.0]`, default: `0.0`)
: Weight for capability (ability to pay) adjustment. Reduces allocation for countries with higher GDP per capita.
: Constraints: `0.0 ≤ capability_weight ≤ 1.0`, requires `gdp_ts` if > 0
: See: [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/) · [Capability](https://setupelz.github.io/fair-shares/science/principle-to-code/)

### Responsibility Parameters

**`historical_responsibility_year`** (type: `int`, default: `1990`)
: Starting year for cumulative historical emissions accounting. Must be ≤ `allocation_year`.
: See: [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/) · [Historical Responsibility](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`responsibility_per_capita`** (type: `bool`, default: `True`)
: If `True`, calculate responsibility adjustment using per capita emissions. If `False`, use absolute emissions.
: See: [Historical Responsibility](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`responsibility_exponent`** (type: `float`, default: `1.0`)
: Exponent applied to responsibility adjustment. Values > 1.0 increase non-linearity.
: See: [Historical Responsibility](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`responsibility_functional_form`** (type: `str`, default: `"asinh"`)
: Functional form for responsibility adjustment. Options: `"asinh"` (inverse hyperbolic sine), `"linear"`.
: See: [Historical Responsibility](https://setupelz.github.io/fair-shares/science/principle-to-code/)

### Capability Parameters

**`capability_per_capita`** (type: `bool`, default: `True`)
: If `True`, calculate capability adjustment using GDP per capita. If `False`, use absolute GDP.
: See: [Capability](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`capability_exponent`** (type: `float`, default: `1.0`)
: Exponent applied to capability adjustment. Values > 1.0 increase non-linearity.
: See: [Capability](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`capability_functional_form`** (type: `str`, default: `"asinh"`)
: Functional form for capability adjustment. Options: `"asinh"`, `"linear"`.
: See: [Capability](https://setupelz.github.io/fair-shares/science/principle-to-code/)

### Inequality Parameters

**`income_floor`** (type: `float`, range: `[0.0, ∞)`, default: `0.0`)
: Minimum income threshold (in GDP per capita units) below which Gini adjustment is not applied. Implements subsistence protection.
: See: [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/) · [Subsistence Protection](https://setupelz.github.io/fair-shares/science/principle-to-code/)

**`max_gini_adjustment`** (type: `float`, range: `[0.0, 1.0]`, default: `0.8`)
: Maximum magnitude of Gini-based allocation adjustment. Caps the effect of within-country inequality.
: See: [Subsistence Protection](https://setupelz.github.io/fair-shares/science/principle-to-code/)

### Constraint Parameters

**`max_deviation_sigma`** (type: `float | None`, default: `2.0`)
: Standard deviations from mean for outlier detection. If not `None`, constrains extreme allocations.
: See: [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)

**`preserve_allocation_year_shares`** (type: `bool`, default: `False`)
: If `True`, pathway allocations maintain allocation_year shares throughout (no dynamic convergence). Used for internal calculations.
: See: [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)

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
3. `emission-category` (str): Emission species (e.g., `"CO2"`, `"Kyoto GHG"`)

**Columns:**

- Year columns as strings (e.g., `"2020"`, `"2021"`, ...)
- **Important:** Year columns must be strings, not integers. Use `ensure_string_year_columns(df)` after loading data.

**Example:**

```python
                                            2020    2021    2022
iso3c  unit       emission-category
USA    Mt CO2/yr  CO2                      5000    4900    4800
IND    Mt CO2/yr  CO2                      2500    2600    2700
World  Mt CO2/yr  CO2                     35000   34500   34000
```

See: [Function Signature](https://setupelz.github.io/fair-shares/dev-guide/adding-approaches/#function-signature) for implementation details

### MultiIndex

A hierarchical index for pandas DataFrames. All fair-shares data uses a 3-level MultiIndex with levels `["iso3c", "unit", "emission-category"]`.

Operations like `.loc[]`, `.xs()`, and `.groupby()` can select/aggregate along specific index levels.

See: [pandas MultiIndex documentation](https://pandas.pydata.org/docs/user_guide/advanced.html)

---

## Equity Principles

### CBDR-RC

**Common But Differentiated Responsibilities and Respective Capabilities**. Foundational principle of the UNFCCC recognizing that:

1. All countries share responsibility for addressing climate change
2. Historical emissions and economic capacity create differentiated responsibilities
3. Developed countries should take the lead given their historical contribution and greater means

Operationalized via `responsibility_weight` and `capability_weight` parameters.

See: [CBDR-RC](https://setupelz.github.io/fair-shares/science/principle-to-code/) · [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)

### Egalitarianism (Ethical Tradition)

A framework of distributive justice that emphasizes equal treatment and equal rights among all persons. In climate equity, egalitarianism grounds the principle of equal rights to the atmosphere.

See: [Egalitarianism](https://setupelz.github.io/fair-shares/science/principle-to-code/) · [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)

### Equal Rights to Atmosphere (Principle)

The principle that every person has an equal per capita entitlement to atmospheric space. Derives from egalitarian ethical tradition. Every person has an equal claim to emit greenhouse gases.

Operationalized by setting `responsibility_weight = 0` and `capability_weight = 0`.

See: [Egalitarianism](https://setupelz.github.io/fair-shares/science/principle-to-code/) · [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)

### Grandfathering

**Anti-pattern.** Allocates future entitlements based on current emission shares. Widely critiqued as lacking ethical basis—rewarding past over-consumption. The `per-capita-convergence` approach contains grandfathering elements and is available for comparison only, not recommended as a fair share approach.

See: [Per-capita Convergence](https://setupelz.github.io/fair-shares/science/principle-to-code/)

### Historical Responsibility

The principle that countries should bear differentiated responsibilities based on their cumulative historical emissions. Past emissions have consumed limited atmospheric capacity.

Operationalized via:

- `allocation_year` (earlier years = more historical responsibility)
- `responsibility_weight` (direct adjustment based on historical emissions)
- Cumulative approaches (e.g., `cumulative-per-capita-convergence`)

See: [Historical Responsibility](https://setupelz.github.io/fair-shares/science/principle-to-code/) · [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)

### Subsistence Protection

The principle that basic needs for development should be protected when allocating emission rights. Poor populations should not be penalized for within-country inequality.

Operationalized via:

- `income_floor` (exempts low-income populations from Gini adjustment)
- Gini-adjusted approaches (account for intra-national inequality)

See: [Subsistence Protection](https://setupelz.github.io/fair-shares/science/principle-to-code/) · [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)

---

## Abbreviations

**API**
: Application Programming Interface. In this documentation, refers to the function-level reference for allocation approaches.

**AR6**
: IPCC Sixth Assessment Report (2021-2023). Source of global emissions scenarios used in fair-shares.

**BAU**
: Business As Usual. Baseline emissions scenario without climate policy. **Anti-pattern:** Treating deviation from BAU as a "sacrifice" is inconsistent with CBDR-RC.

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

**PRIMAP-hist**
: Historical emissions dataset from PIK (Potsdam Institute for Climate Impact Research).

**RCB**
: Remaining Carbon Budget. The amount of CO2 that can still be emitted while staying within a temperature target (e.g., 1.5°C).

**SSP**
: Shared Socioeconomic Pathway. Scenarios combining socioeconomic projections with climate mitigation levels (e.g., SSP1-1.9, SSP2-4.5).

**TCRE**
: Transient Climate Response to Cumulative Emissions. The near-linear relationship between cumulative CO2 emissions and global temperature increase.

**UNFCCC**
: United Nations Framework Convention on Climate Change.
