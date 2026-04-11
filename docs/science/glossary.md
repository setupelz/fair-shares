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

    All approaches incorporate historical differentiation via `allocation_year` (budget) or `first_allocation_year` (pathway). When set in the past, cumulative population from that year determines each country's share of the total budget — leaving different **remaining allocations** for each country. The `*-adjusted` approaches additionally apply pre-allocation responsibility and capability rescaling on top of this mechanism.

### Budget Approaches

**`equal-per-capita-budget`**
: Population-proportional allocation. Historical accountability via `allocation_year` only.

**`per-capita-adjusted-budget`**
: Adds `pre_allocation_responsibility_weight` (backward-looking from allocation year) and `capability_weight` (forward-looking from allocation year onwards) adjustments. CBDR-RC.

**`per-capita-adjusted-gini-budget`**
: Adds Gini adjustment for within-country inequality. Subsistence protection.

### Pathway Approaches (Standard)

**`equal-per-capita`**
: Annual population-proportional shares. Historical accountability via `first_allocation_year`.

**`per-capita-adjusted`**
: Annual shares with pre-allocation responsibility (backward-looking) and capability (from allocation year onwards) adjustments. CBDR-RC.

**`per-capita-adjusted-gini`**
: Annual shares with Gini adjustment. Subsistence protection.

### Pathway Approaches (Convergence)

**`per-capita-convergence`**
: Gradual transition to equal per capita. **Not a fair share approach**—includes grandfathering.

**`cumulative-per-capita-convergence`**
: Budget-preserving convergence. Distributes cumulative per capita shares over time. **Fair share approach.**

**`cumulative-per-capita-convergence-adjusted`** / **`-gini-adjusted`**
: Convergence with pre-allocation responsibility/capability/Gini adjustments.

See: [API Reference](../api/allocations/budgets.md) · [From Principle to Code](principle-to-code.md)

---

## Parameters

For detailed parameter effects and examples, see [Parameter Effects](parameter-effects.md).

### Core Parameters

**`allocation_year`** / **`first_allocation_year`** (type: `int`)
: Start year for cumulative accounting. Cumulative population from this year determines each country's share of the total budget. No neutral default: the choice operationalises whether past emissions create present obligations.
: Budget approaches use `allocation_year`; pathway approaches use `first_allocation_year`.

**`convergence_year`** (type: `int`)
: Year by which allocations converge to equal per capita shares. Must be > allocation year. Required when `convergence_method="sine-deviation"`. Earlier convergence years demand steeper near-term reductions; later years spread the transition. Convergence approaches only. See [Parameter Effects](parameter-effects.md#convergence_method-convergence-only).

**`emission_category`** (type: `str`)
: Emission species (e.g., `"co2-ffi"`, `"co2"`, `"all-ghg"`, `"all-ghg-ex-co2-lulucf"`, `"non-co2"`). Must match data sources. Both `all-ghg` and `all-ghg-ex-co2-lulucf` use GWP100 AR6 values to convert non-CO2 gases to CO2-equivalent. Composite categories (`all-ghg`, `all-ghg-ex-co2-lulucf`) trigger [decomposition into CO2 + non-CO2](other-operations.md#all-ghg-allocations-with-rcbs) when used with RCB targets, because RCBs constrain CO2 only and non-CO2 requires scenario pathway data.

**`group_level`** (type: `str`, default: `"iso3c"`)
: Index level for countries/regions (ISO 3166-1 alpha-3 codes).

### Adjustment Weights

Constraint: `pre_allocation_responsibility_weight + capability_weight ≤ 1.0`

Only the **ratio** between the two weights matters -- they are normalized by their sum before use. `(0.3, 0.7)` and `(0.15, 0.35)` produce identical results. When one weight is 0, the other is the sole adjustment regardless of its specific value -- `(0.0, 0.3)` is identical to `(0.0, 1.0)`.

**`pre_allocation_responsibility_weight`** (type: `float`, default: `0.0`)
: Weight for relative per-capita rescaling based on emissions in [`pre_allocation_responsibility_year`, `allocation_year`). Higher relative to `capability_weight` = more reduction for countries with high per-capita emissions in that window. Separate from the cumulative accounting done by early `allocation_year`. Always produces positive allocations if `allocation_year` is the present.

**`capability_weight`** (type: `float`, default: `0.0`)
: Weight for GDP-based adjustment (applies from allocation year onwards). Higher relative to `pre_allocation_responsibility_weight` = more reduction for wealthy countries. Note the temporal asymmetry: pre-allocation responsibility looks backward from the allocation year, while capability looks forward from it.

### Pre-allocation Responsibility Parameters

**`pre_allocation_responsibility_year`** (type: `int`, default: `1990`)
: Start year for cumulative emissions in the pre-allocation responsibility window. Must be strictly less than `allocation_year` for the adjustment to have effect — when equal, the window is empty.

**`pre_allocation_responsibility_per_capita`** (type: `bool`, default: `False`)
: Per capita (True) or absolute (False) emissions for pre-allocation responsibility calculation. Default is `False` (absolute) to match the polluter-pays framing used in most of the historical-responsibility literature, which treats responsibility as a country's total cumulative contribution to atmospheric CO2 — see [Matthews 2016](https://doi.org/10.1038/NCLIMATE2774) (absolute cumulative emissions as the debt metric) and the [Greenhouse Development Rights framework (Baer 2009)](https://doi.org/10.1080/13668790903195495), which starts from country-level absolute cumulative emissions and applies a within-country subsistence filter (not a per-capita normalisation). Set to `True` if your research framing genuinely calls for per-capita historical responsibility.

**`pre_allocation_responsibility_exponent`** (type: `float`, default: `1.0`)
: Exponent for pre-allocation responsibility adjustment. >1.0 increases non-linearity.

**`pre_allocation_responsibility_functional_form`** (type: `str`, default: `"asinh"`)
: Functional form: `"asinh"` or `"power"`.

### Capability Parameters

**`capability_per_capita`** (type: `bool`, default: `True`)
: Per capita (True) or absolute (False) GDP for capability calculation.

**`capability_exponent`** (type: `float`, default: `1.0`)
: Exponent for capability adjustment (applies from allocation year onwards). >1.0 increases non-linearity.

**`capability_functional_form`** (type: `str`, default: `"asinh"`)
: Functional form: `"asinh"` or `"power"`.

### Inequality Parameters

**`income_floor`** (type: `float`, default: `0.0`)
: Income below this threshold (USD PPP per capita) is excluded from capability calculations, protecting subsistence needs. At `0.0`, all income counts. The GDR framework default is `7500` ($7,500/year 2010 PPP). Higher floors reduce measured capability for all countries, with the largest effect on middle-income countries where population clusters around the threshold. See [Parameter Effects](parameter-effects.md#income_floor).

**`max_gini_adjustment`** (type: `float`, default: `0.8`)
: Maximum proportional reduction from the Gini-based capability correction. Caps the influence of extreme inequality (Gini > 0.6) on measured capability, preventing outsized adjustments from dominating the allocation. At 0.8, the Gini adjustment can reduce a country's measured GDP by at most 80%. Available on `*-gini-*` approaches only.

### Discounting Parameters

**`historical_discount_rate`** (type: `float`, default: `0.0`)
: Weights earlier historical emissions less when computing pre-allocation responsibility adjustments. `0.0` treats all years equally. Available on `*-adjusted` functions only. See [Parameter Effects](parameter-effects.md#historical_discount_rate).

### Convergence Parameters

**`convergence_method`** (type: `str`, default: `"minimum-speed"`)
: Solver for convergence pathway. `"minimum-speed"` finds the minimum exponential speed satisfying cumulative constraints. `"sine-deviation"` uses iterative sine-shaped deviation from a PCC baseline (requires `convergence_year`). Convergence approaches only.

**`max_convergence_speed`** (type: `float`, default: `0.9`)
: Upper bound on exponential convergence speed. Lower values force slower transitions but may cause infeasibility. Convergence approaches only.

**`strict`** (type: `bool`, default: `True`)
: Controls behavior on infeasible convergence targets. `True` raises an error; `False` clips infeasible long-run shares and reports per-country deviation ratios. Convergence approaches only. See [Parameter Effects](parameter-effects.md#strict-convergence-only).

### Constraint Parameters

**`max_deviation_sigma`** (type: `float | None`, default: `None`)
: Optional outlier constraint (standard deviations from mean). Default `None` means no constraint — the raw, unconstrained adjustment is returned. Set to a positive float (e.g. `2.0`) to opt into a ±N-σ cap that compresses extreme values. Only relevant when applying scaling adjustments. See [Parameter Effects](parameter-effects.md#max_deviation_sigma).

**`preserve_allocation_year_shares`** / **`preserve_first_allocation_year_shares`** (type: `bool`, default: `False`)
: When `True`, freezes population (and adjustment) shares at the allocation year instead of recalculating as demographics evolve. The choice reflects whether future population growth should increase a country's atmospheric entitlement. See [Parameter Effects](parameter-effects.md#preserve_allocation_year_shares-preserve_first_allocation_year_shares).

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

## Key Concepts

Brief definitions. For detailed explanations and operationalization, see [Allocation Approaches](allocations.md) and [From Principle to Code](principle-to-code.md).

**Carbon Debt**
: Obligation owed by high-emitting nations that have exceeded their fair share of atmospheric space. Can be quantified in tonnes CO2 or monetary terms. [Matthews 2016](https://doi.org/10.1038/NCLIMATE2774) calculates debts against an equal per capita benchmark; [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122) introduces a net-zero framing that makes post-peak obligations explicit. Moral grounding: [Pickering 2012](https://doi.org/10.1080/13698230.2012.727311).
: See: [References](references.md)

**Cascading Biases**
: Systematic methodological choices in effort-sharing frameworks that compound to favor wealthy nations. [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) identifies three types: scope bias (including cost-effectiveness alongside equity approaches), framing bias (late base years that embed grandfathering), and aggregation bias (equal weighting of ethically unequal approaches).
: See: [Allocation Approaches](allocations.md#approaches-debated-in-the-literature)

**CBDR-RC**
: Common But Differentiated Responsibilities and Respective Capabilities. UNFCCC foundational principle: all countries share responsibility, but obligations differ based on historical emissions and economic capacity. For the legal interpretation in its normative environment, see [Rajamani 2024](https://doi.org/10.1093/clp/cuae011); for operational interpretations under the Paris Agreement, see [Rajamani 2021](https://doi.org/10.1080/14693062.2021.1970504).
: See: [Allocation Approaches](allocations.md)

**Egalitarianism**
: Ethical tradition grounding equal per capita entitlement to atmospheric space. [Agarwal 1991](https://cdn.cseindia.org/userfiles/GlobalWarming%20Book.pdf) makes the foundational per-capita argument from an anti-colonial standpoint; [Caney 2009](https://doi.org/10.1080/17449620903110300) develops the philosophical case for egalitarian allocation of greenhouse gas emission rights.
: See: [Allocation Approaches](allocations.md)

**Equal per capita**
: Each person has equal entitlement to atmospheric space. In fair-shares, historical accountability is usually incorporated via `allocation_year` (cumulative accounting includes past emissions), not via weight adjustments.
: See: [Allocation Approaches](allocations.md)

**Grandfathering**
: Allocating future entitlements based on current emission shares. Critiqued as lacking ethical basis — [Caney 2009](https://doi.org/10.1080/17449620903110300) calls it "morally perverse" and [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8) finds "virtually no support" for it among moral and political philosophers. `per-capita-convergence` includes grandfathering elements.
: See: [Allocation Approaches](allocations.md#approaches-debated-in-the-literature)

**Historical responsibility**
: Past emissions reduce remaining fair share. Two distinct mechanisms: (1) early `allocation_year` — cumulative accounting where cumulative population from that year determines shares (can produce negative allocations as a mathematical consequence); (2) `pre_allocation_responsibility_weight` in `*-adjusted` approaches — multiplicative rescaling of shares by relative per-capita emissions in a historical window (always positive).
: See: [Allocation Approaches](allocations.md#historical-responsibility)

**Negative Allocation**
: When a party's remaining fair share under a carbon budget is negative — its past emissions have already exceeded its equal per capita entitlement. Signals the need for highest possible domestic ambition, negative emissions targets (CDR), and international support. Negative allocations are a feature, not a bug: they communicate the scale of overshoot and the urgency of minimizing its duration and magnitude. [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f)
: See: [Allocation Approaches](allocations.md) · [From Principle to Code](principle-to-code.md)

**Subsistence protection**
: Basic needs emissions protected from mitigation burdens. Grounded in [Shue 2014](references.md#shue-2014)'s distinction between subsistence and luxury emissions; operationalised in the [Greenhouse Development Rights framework (Baer 2009)](https://doi.org/10.1080/13668790903195495) via a development threshold that excludes both income and emissions of low-income individuals from a country's responsibility and capacity calculations. In fair-shares, implemented via `income_floor` and Gini adjustments.
: See: [Allocation Approaches](allocations.md#gini-adjustment)

---

## Abbreviations and Terms

**API**
: Application Programming Interface. In this documentation, refers to the function-level reference for allocation approaches.

**AR6**
: IPCC Sixth Assessment Report (2021-2023). Source of global emissions scenarios used in fair-shares.

**BAU**
: Business As Usual. Baseline emissions scenario without climate policy. Note: framing deviation from BAU as a "cost" or "sacrifice" has been critiqued as inconsistent with CBDR-RC — fair shares must be assessed relative to other parties, not against a country's own BAU ([Winkler 2018](https://doi.org/10.1007/s10784-017-9381-x); [Rajamani 2021](https://doi.org/10.1080/14693062.2021.1970504); [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f)).

**Bookkeeping (BM)**
: LULUCF accounting method that estimates only direct human-caused land-use fluxes (deforestation, afforestation, land management). Used by IPCC for RCBs. Contrast with NGHGI, which additionally includes indirect effects. See: [NGHGI-Consistent RCB Corrections](other-operations.md#why-two-lulucf-conventions-matter)

**Bunker fuels**
: CO₂ emissions from international aviation and shipping. Included in global emission totals but excluded from national inventories (no country claims responsibility). Must be subtracted when converting global RCBs to country-allocatable budgets [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9).

**ECPC**
: Equal Cumulative Per Capita. An allocation approach that distributes a carbon budget equally on a cumulative per-capita basis. Cumulative population from the allocation year determines each country's share.

**GDP**
: Gross Domestic Product. Economic output measure used for capability adjustments (from the allocation year onwards).

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
: The systematic difference between NGHGI and bookkeeping (BM) LULUCF CO₂ estimates. NGHGI includes indirect effects (CO₂ fertilization of managed forests) that BM excludes, making NGHGI a larger net sink. ~90 GtCO₂ for 1.5°C scenarios [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9). See: [NGHGI-Consistent RCB Corrections](other-operations.md#correction-for-total-co2-budgets-co2)

**PRIMAP-hist**
: Historical emissions dataset from PIK (Potsdam Institute for Climate Impact Research).

**RCB**
: Remaining Carbon Budget. The amount of CO2 that can still be emitted while staying within a temperature target (e.g., 1.5°C). IPCC RCBs use bookkeeping LULUCF and include bunker fuels — conversion to NGHGI-consistent values requires corrections [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9). See: [NGHGI-Consistent RCB Corrections](other-operations.md#weber-rcb-corrections)

**SSP**
: Shared Socioeconomic Pathway. Scenarios combining socioeconomic projections with climate mitigation levels (e.g., SSP1-1.9, SSP2-4.5).

**TCRE**
: Transient Climate Response to Cumulative Emissions. The near-linear relationship between cumulative CO2 emissions and global temperature increase.

**UNFCCC**
: United Nations Framework Convention on Climate Change.
