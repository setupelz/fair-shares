---
title: Glossary
description: Definitions of terms used in the fair-shares documentation and code
---

# Glossary

Parameters are explained in [Parameter effects](parameter-effects.md) and in the [API reference](../api/allocations/budgets.md). Approach names use kebab-case; the [Approach catalog](../user-guide/approach-catalog.md) lists them all.

## Approaches

**Budget approach**
: Allocates one cumulative budget: `equal-per-capita-budget`, `per-capita-adjusted-budget` (responsibility and capability) and `per-capita-adjusted-gini-budget` (plus inequality within countries). The name ends in `-budget`.

**Pathway approach**
: Allocates a value for every year: `equal-per-capita`, `per-capita-adjusted`, `per-capita-adjusted-gini`, and the convergence approaches.

**Convergence approach**
: Moves each country from its current emission share to a target share. `cumulative-per-capita-convergence` and its `-adjusted` and `-gini-adjusted` forms preserve the cumulative budget. `per-capita-convergence` does not, and it includes grandfathering, so it is for comparison only.
: See: [Convergence](allocations.md#convergence-mechanism-pathways-only)

**ECPC**
: Equal cumulative per capita: cumulative population from the allocation year sets each country's share of a budget.

**Allocation year**
: `allocation_year` (budget) or `first_allocation_year` (pathway). Cumulative population from this year sets the shares. It decides whether past emissions create present obligations, so it has no neutral default.
: See: [Allocation year](allocations.md#allocation-year)

## Concepts

**Carbon debt**
: The emissions by which a country has exceeded its fair share of atmospheric space, read as an obligation. Can be quantified in tonnes CO2 or monetary terms. [Matthews 2016](https://doi.org/10.1038/NCLIMATE2774) calculates debts against an equal per capita benchmark; [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122) introduces a net-zero framing that makes post-peak obligations explicit. Moral grounding: [Pickering 2012](https://doi.org/10.1080/13698230.2012.727311).

**Cascading biases**
: Systematic methodological choices in effort-sharing frameworks that compound to favor wealthy nations. [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) identifies three types: scope bias (including cost-effectiveness alongside equity approaches), framing bias (late base years that embed grandfathering), and aggregation bias (equal weighting of ethically unequal approaches).
: See: [Allocation Approaches](allocations.md#approaches-debated-in-the-literature)

**CBDR-RC**
: Common But Differentiated Responsibilities and Respective Capabilities. UNFCCC foundational principle: all countries share responsibility, but obligations differ based on historical emissions and economic capacity. For the legal interpretation in its normative environment, see [Rajamani 2024](https://doi.org/10.1093/clp/cuae011); for operational interpretations under the Paris Agreement, see [Rajamani 2021](https://doi.org/10.1080/14693062.2021.1970504).
: See: [Allocation Approaches](allocations.md)

**Egalitarianism**
: Ethical tradition grounding equal per capita entitlement to atmospheric space. [Agarwal 1991](https://cdn.cseindia.org/userfiles/GlobalWarming%20Book.pdf) makes the foundational per-capita argument from an anti-colonial standpoint; [Caney 2009](https://doi.org/10.1080/17449620903110300) develops the philosophical case for egalitarian allocation of greenhouse gas emission rights.
: See: [Allocation Approaches](allocations.md)

**Equal per capita**
: Each person has an equal entitlement to atmospheric space. Historical accountability enters through an early `allocation_year`, not through weights.
: See: [Allocation approaches](allocations.md)

**Grandfathering**
: Allocating future entitlements based on current emission shares. Critiqued as lacking an ethical basis: [Caney 2009](https://doi.org/10.1080/17449620903110300) calls it "morally perverse" and [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8) finds "virtually no support" for it among moral and political philosophers. `per-capita-convergence` includes grandfathering elements.
: See: [Allocation Approaches](allocations.md#approaches-debated-in-the-literature)

**Historical responsibility**
: Past emissions reduce a country's remaining fair share. Two mechanisms put it into practice: an early `allocation_year` (cumulative accounting, which can give negative allocations) and `pre_allocation_responsibility_weight` (multiplicative rescaling by emissions in a past window).
: See: [The two mechanisms](allocations.md#building-blocks)

<a id="negative-allocation"></a>
**Negative allocation**
: A remaining allocation below zero: a country's past emissions exceed its allocation. It is an expected result for high historical emitters under an early allocation year. [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f) report a negative remaining allocation for the EU27 as of 2023 under 1.5 °C budgets. [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122) and [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f) read it as calling for the highest possible domestic ambition, net-negative targets through carbon dioxide removal (CDR) and international support for others, and stress minimising the duration and magnitude of overshoot. It does not prescribe timing or mechanism, and reporting it rather than clipping it to zero keeps that information.
: See: [Allocation Approaches](allocations.md) · [From Principle to Code](principle-to-code.md)

**Relative and absolute results**
: The allocation functions return relative shares that sum to 1. Absolute results multiply them by a global budget or pathway.
: See: [Outputs](../user-guide/output-schema.md)

**Remaining budget**
: A country's allocation minus its observed emissions from the allocation year to the last observed year.
: See: [Remaining budgets and annual pathways](../user-guide/pipeline-map.md#4-remaining-budgets-and-annual-pathways-notebook-601-and-the-python-api)

**Subsistence protection**
: Basic needs emissions protected from mitigation burdens. Grounded in [Shue 2014](references.md#shue-2014)'s distinction between subsistence and luxury emissions; operationalised in the [Greenhouse Development Rights framework (Baer 2009)](https://doi.org/10.1080/13668790903195495) via a development threshold that excludes both income and emissions of low-income individuals from a country's responsibility and capacity calculations. In fair-shares, implemented via `income_floor` and Gini adjustments. [Shue 2014](references.md#shue-2014) also notes that people in poverty need energy rather than emissions rights, which makes the development threshold of [Baer 2013](https://doi.org/10.1002/wcc.201) the closer operational concept.
: See: [Allocation Approaches](allocations.md#gini-adjustment)

## Data and budget terms

**Analysis countries and rest of world (ROW)**
: Countries with complete emissions, GDP and population data are allocated individually. The ROW row is the world total minus them.
: See: [Analysis countries](other-operations.md#analysis-countries)

**Budget label (`TpL`)**
: The key of a budget in `rcbs.yaml`, for example `1.7p67`. $T$ is the warming when CO₂ reaches net zero; $L$ is the likelihood of staying below it. Each source records what $L$ covers (`likelihood_scope`) and what $T$ measures (`budget_metric`). See: [What a budget label means](scenario-sets.md#what-a-budget-label-means)

**Bookkeeping (BM)**
: Land-use accounting that estimates only direct human-caused fluxes (deforestation, afforestation, land management). IPCC budgets use it. National inventories also count indirect effects.
: See: [Convention gap](remaining-carbon-budgets.md#convention-gap)

**Bunkers**
: CO₂ from international aviation and shipping. Global totals include it and national inventories do not, so it leaves the allocatable budget [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9).
: See: [Bunker deduction](remaining-carbon-budgets.md#bunker-deduction)

**Composite category**
: `all-ghg` or `all-ghg-ex-co2-lulucf`. A remaining carbon budget limits CO₂ only, so the run allocates a CO₂ budget and a non-CO₂ pathway with the same equity approach.
: See: [Greenhouse gases](greenhouse-gases.md#decomposition-rules)

**GCB 2025**
: Global Carbon Budget 2025 fossil CO₂ dataset, version 2025v15 ([Friedlingstein 2026](references.md)). Opt-in emissions source `gcb-2025`, `co2-ffi` only, 1850-2024. Its world row excludes international bunkers and the 1991 Kuwaiti oil fires. The same file supplies the observed bunker series of every run (`bunkers_source: gcb-2025`, the default).

**GCB 2025 global workbook**
: The Global Carbon Budget 2025 global workbook (`gcb-2025-global`, manual download). It supplies observed global net CO₂, which expresses each budget from the start of 2020 for its volume-matched scenario set. See: [RCB sources and scenario sets](scenario-sets.md#budget-from-2020)

**IGCC 2025 (`forster_2026`)**
: Indicators of Global Climate Change 2025 ([Forster 2026](references.md)). RCB source `forster_2026` in `rcbs.yaml` takes its Table 8 budgets from the start of 2026, for eight temperature and likelihood labels in the defaults. Its scenario-derived terms use the role-matched scenario sets.

**Melo et al. (2026)**
: Country-reported NGHGI LULUCF CO₂ timeseries from the LULUCF Data Hub. Two versions are configured. `melo-2026-v4` (v4.0.0, 2026 NGHGI release, default) covers 187 countries, 2000-2024. `melo-2026` (v3.1.1, opt-in) covers 185 countries, 2000-2023. See: [NGHGI-Consistent RCB Corrections](remaining-carbon-budgets.md#allocatable-budget)

**NGHGI**
: National greenhouse gas inventory, reported under the UNFCCC. Its land-use estimates include indirect fluxes such as CO₂ fertilisation, unlike bookkeeping models.
: See: [From published budget to allocatable budget](remaining-carbon-budgets.md#allocatable-budget)

**NGHGI-BM convention gap**
: The systematic difference between NGHGI and bookkeeping (BM) LULUCF CO₂ estimates. NGHGI includes indirect effects (CO₂ fertilization of managed forests) that BM excludes, making NGHGI a larger net sink. This package computes a cumulative gap of -91.4 GtCO₂ from 2020 to net-zero CO₂ and -65.6 GtCO₂ from 2024 (median of the AR6 C1 scenarios, `melo-2026-v4`; the gap does not depend on the emissions source). [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) reports that in 2024 the adjustment "reduces the global RCB by 63 (41–121) GtCO2 for 1.5 °C (50%)" (Results, "The global NGHGI-consistent RCB"). See: [National-inventory convention gap](remaining-carbon-budgets.md#convention-gap)

**Non-CO₂ debt mode**
: How past non-CO₂ over-use is settled in a composite category: `report-only` (reported, no penalty) or `co2-debit` (subtracted from the remaining CO₂ budget and retired).
: See: [Greenhouse gases](greenhouse-gases.md)

**Presets**
: Named parameter grids that reproduce a published study (`fair_shares.library.presets`). `esabcc_2023_allocations()` returns the ESABCC 2023 / PRR2023 grid that notebook 601 runs. See: [Python API](../api/python-api.md)

**PRIMAP-hist**
: Historical emissions dataset from PIK (Potsdam Institute for Climate Impact Research). v2.8 (`primap-202609`, data to 2025, CC BY-NC-SA 4.0) is the default emissions source. v2.6.1 (`primap-202503`, data to 2023, CC BY 4.0) is opt-in. See: [Data Sources & Licensing](../user-guide/data-sources.md)

**RCB**
: Remaining carbon budget: the net CO₂ the world can still emit from a start year until CO₂ reaches net zero, for a warming level and a likelihood. Published budgets use bookkeeping land use and include bunkers, so they need corrections before allocation [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9).
: See: [Remaining carbon budgets](remaining-carbon-budgets.md)

**Scenario Compass (SCI)**
: The Scenario Compass Initiative pathways ensemble (`sci-2026` v2.0, or `sci-2025` v1.0; manual download). Research use under the embargo terms of its workbook until Riahi et al. is published. fair-shares reads it for bunker reporters and, opt-in, for the non-CO₂ set. See: [Scenario Compass](scenario-sets.md#scenario-compass)

**Scenario selection rule**
: The rule in `rcbs.yaml` (`scenario_selection`) that picks the scenarios behind the scenario-derived terms of a budget. The default, `role-matched`, takes the LULUCF, convention-gap and bunker-window terms from a volume-matched set (cumulative net CO₂ from 2020 to net zero within 50 Gt of the budget from 2020) and the non-CO₂ pathway from a temperature-matched set (median warming at net zero within ±0.05 °C of the budget temperature). `ar6-category` pairs `1.5p50` with AR6 C1, `2p67` with C3 and `2p50` with C4. See: [RCB sources and scenario sets](scenario-sets.md#role-matched-scenario-sets)

**Scenario sets (volume-matched, temperature-matched)**
: The volume-matched set of a budget holds the scenarios whose cumulative net CO₂ from 2020 to net zero lies within 50 Gt of the budget from 2020. It supplies the land-use, convention-gap and bunker terms. The temperature-matched set holds the scenarios whose median warming at net zero lies within ±0.05 °C of the budget temperature. It supplies the non-CO₂ pathway. See: [Role-matched scenario sets](scenario-sets.md#role-matched-scenario-sets)

**TimeseriesDataFrame**
: A pandas DataFrame indexed by `iso3c` and `unit` (plus `emission-category` for emissions), with one string column per year (`"2020"`).

**WDI Gini**
: World Bank Gini index (`SI.POV.GINI`, from the Poverty and Inequality Platform), source `wdi-2025`. It is the default Gini source. Each country takes its latest value within 2015-2023. UNU-WIDER WIID (`unu-wider-2025`) is opt-in.

## Abbreviations

- **AR6**: IPCC Sixth Assessment Report (2021-2023).
- **BAU**: business as usual. Treating deviation from BAU as a cost has been critiqued as inconsistent with CBDR-RC, because fair shares are assessed relative to other parties ([Winkler 2018](https://doi.org/10.1007/s10784-017-9381-x); [Rajamani 2021](https://doi.org/10.1080/14693062.2021.1970504); [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f)).
- **GDP**: gross domestic product.
- **GHG**: greenhouse gas. "Kyoto GHG" is the basket of the Kyoto Protocol.
- **IAMC**: Integrated Assessment Modeling Consortium, and its data format.
- **IPCC**: Intergovernmental Panel on Climate Change.
- **ISO 3166-1 alpha-3**: three-letter country codes (`USA`, `IND`, `DEU`), the `iso3c` index level.
- **Mt CO2/yr**: megatonnes of CO₂ per year.
- **SSP**: Shared Socioeconomic Pathway.
- **TCRE**: transient climate response to cumulative emissions.
- **UNFCCC**: United Nations Framework Convention on Climate Change.
