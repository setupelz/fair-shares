---
title: Method overview
description: The full fair-shares method in five steps, from a published global carbon budget to national budgets and pathways, with the source for each step
---

# Method overview

fair-shares computes national fair shares of a global emissions limit.
This page walks the full chain in five steps.
Each step names its sources and links to the page with the detail.

**In short:**

- The starting point is a published global remaining carbon budget.
- fair-shares adjusts that budget so that it matches what countries report in their national inventories ([Weber 2026](https://doi.org/10.1038/s41467-026-69078-9)).
- Equity-based allocation approaches split the adjusted budget among countries ([Pelz 2025a](https://doi.org/10.1073/pnas.2409316122); [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f)).
- CO₂ is allocated as a budget and the other greenhouse gases as an annual pathway from scenarios at the same warming level ([Weber 2026b](https://doi.org/10.1038/s43247-026-03832-1)).
- Observed emissions to date give each country's remaining budget, which can be spread into an annual pathway.

---

## 1. Published global budget {#published-global-budget}

A remaining carbon budget is the net CO₂ the world can still emit until CO₂ reaches net zero, for a warming level and a likelihood.
The library ships budgets from five sources, for example 500 Gt CO₂ from 2020 for 1.5 °C at 50% in IPCC AR6.
Each budget limits CO₂ only.

**Sources:** [IPCC 2021 SPM](https://doi.org/10.1017/9781009157896.001); [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5); [Forster 2024](https://doi.org/10.5194/essd-16-2625-2024); [Forster 2026](https://doi.org/10.5194/essd-18-3889-2026).
**Detail:** [Published budgets](remaining-carbon-budgets.md#published-budgets), [What a budget label means](scenario-sets.md#what-a-budget-label-means).

## 2. Allocatable budget {#allocatable-budget}

Every budget is rebased to start in 2020 with observed emissions.
International aviation and shipping leave the budget, because no national inventory holds them.
For fossil CO₂ the projected land-use share leaves the budget. For total CO₂ land use switches to the national-inventory convention, which lowers the budget.

**Sources:** [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9); scenarios from [Gidden 2023](https://doi.org/10.5281/zenodo.10158920).
**Detail:** [Remaining carbon budgets](remaining-carbon-budgets.md), [Scenario sets](scenario-sets.md).

## 3. Allocation approaches {#allocation-approaches}

An allocation approach turns an equity principle into each country's share of the budget.
The approaches start from equal per capita shares and can adjust them for historical responsibility, capability and inequality within countries.
Budget approaches give one cumulative value per country, and pathway approaches give annual values.

**Sources:** [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122); [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f).
**Detail:** [Allocation approaches](allocations.md), [From principle to code](principle-to-code.md), [Parameter effects](parameter-effects.md).

## 4. Greenhouse gases {#greenhouse-gases}

Four categories are available: `co2-ffi`, `co2`, `all-ghg-ex-co2-lulucf` and `all-ghg`.
A carbon budget limits CO₂ only, so an all-GHG result is a CO₂ budget plus a non-CO₂ annual pathway, both allocated with the same equity approach.
The non-CO₂ pathway comes from scenarios at the budget's warming level, because the budget depends on the methane pathway it assumes.

**Sources:** [Weber 2026b](https://doi.org/10.1038/s43247-026-03832-1); [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) for land-use CO₂.
**Detail:** [Greenhouse gases](greenhouse-gases.md).

## 5. Remaining budgets and pathways {#remaining-budgets-and-pathways}

A country's remaining budget is its allocation minus its observed emissions from the allocation year to the last observed year.
A remaining budget can be negative when past emissions exceed the allocation.
An annual pathway to an end year such as 2100 spreads it: each country moves from its current share towards an equal per capita share, and a deviation term makes the pathway sum to its remaining budget.

**Detail:** [Past non-CO₂ use](greenhouse-gases.md#historical-deviation), [Python API](../api/python-api.md#the-orchestrated-timeseries-api), [RCB pathway generation](other-operations.md#rcb-pathway-generation).

---

## Pages in this section

- **[Remaining carbon budgets](remaining-carbon-budgets.md)**: published budgets and the adjustments to an allocatable budget
- **[Greenhouse gases](greenhouse-gases.md)**: fossil CO₂, land-use CO₂ and the non-CO₂ gases
- **[Scenario sets](scenario-sets.md)**: budget labels and the scenarios behind each budget term
- **[Allocation approaches](allocations.md)**: design, parameters and rationale for each approach
- **[From principle to code](principle-to-code.md)**: how equity principles become configuration choices
- **[Parameter effects](parameter-effects.md)**: how parameter choices change allocations
- **[Data processing](other-operations.md)**: harmonisation, pathway generation, validation and the country set
- **[Glossary](glossary.md)** and **[References](references.md)**

!!! note "Scope"

    These pages draw on a working subset of the climate equity literature. Corrections and additions are welcome.
