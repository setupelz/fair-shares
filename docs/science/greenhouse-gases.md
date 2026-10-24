---
title: Greenhouse gases
description: How fair-shares combines fossil CO2, land-use CO2 and the other greenhouse gases
---

# Greenhouse gases

fair-shares allocates four emission categories.
Two hold CO₂ only, and two hold all greenhouse gases.
A carbon budget limits CO₂ only, so the other gases follow a different route.
This page explains how the library combines them.

**In short:**

- The four categories are `co2-ffi` (fossil CO₂), `co2` (fossil and land-use CO₂), `all-ghg-ex-co2-lulucf` and `all-ghg`.
- The library holds no single greenhouse-gas budget. A multi-gas result is a CO₂ budget plus a non-CO₂ annual pathway.
- The non-CO₂ pathway comes from scenarios at the budget's warming level, and the same equity approach allocates both parts.
- The budget depends on the methane pathway it assumes ([Weber 2026b](https://doi.org/10.1038/s43247-026-03832-1)). The pairing keeps the two consistent.
- Categories with land-use CO₂ (`co2`, `all-ghg`) start in 2000 or later with national-inventory land-use data, and from 1850 with the bookkeeping source `gcb-2025-luc`.

---

## The four emission categories {#categories}

| Category | Covers | CO₂ part | Earliest history |
| -------- | ------ | -------- | ---------------- |
| `co2-ffi` | CO₂ from fossil fuels and industry | Itself | 1850 |
| `co2` | `co2-ffi` plus land-use CO₂ on the basis of the LULUCF source: national inventory (NGHGI, default) or bookkeeping models | Itself | 2000 (inventory), 1850 (bookkeeping) |
| `all-ghg-ex-co2-lulucf` | All greenhouse gases without land-use CO₂ | `co2-ffi` | 1850 |
| `all-ghg` | All greenhouse gases including land-use CO₂ | `co2` | 2000 (inventory), 1850 (bookkeeping) |

Both all-GHG categories convert non-CO₂ gases to CO₂-equivalent with GWP100 values from AR6.
`non-co2` is the non-CO₂ part of the two all-GHG categories.

---

## No single greenhouse-gas budget {#no-single-ghg-budget}

Remaining carbon budgets constrain **CO₂ only**.
They rest on the near-linear relationship between cumulative CO₂ emissions and global warming ([IPCC 2021](https://doi.org/10.1017/9781009157896); [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) on budget size and uncertainty).
Each published budget assumes a pathway for the non-CO₂ gases (CH₄, N₂O, F-gases), and the budget itself covers CO₂ only.
The library therefore holds no single greenhouse-gas budget number.

## How the budget and the non-CO₂ pathway combine {#decomposition-rules}

An all-GHG allocation against a budget (`rcbs` or `rcb-pathways` target) splits into two parts:

| Part | Gas scope | Allocation | Data |
| ---- | --------- | ---------- | ---- |
| CO₂ | `co2` or `co2-ffi` | Budget approach | [Remaining carbon budgets](remaining-carbon-budgets.md) |
| Non-CO₂ | `non-co2` | Pathway approach | Median pathway of the budget's temperature-matched set |

The CO₂ part depends on the category:

- **`all-ghg`** takes `co2`: total CO₂ including land use, with the NGHGI corrections.
- **`all-ghg-ex-co2-lulucf`** takes `co2-ffi`: fossil CO₂ only, with no NGHGI corrections.

The non-CO₂ pathway of a budget comes from the scenarios whose median warming at net-zero CO₂ matches the budget temperature, or from its AR6 category ([Role-matched scenario sets](scenario-sets.md#role-matched-scenario-sets)).
Every label in `rcbs.yaml` therefore gets a non-CO₂ pathway.
A set below `min_scenarios` raises an error.

The non-CO₂ rows of a budget hold one row per budget.
Each row carries the label of the budget as `climate-assessment` and `quantile`, and the budget source key as `source`.
The CO₂ part pairs with the non-CO₂ part on `source`, `climate-assessment` and `quantile`.
A budget row without a non-CO₂ partner raises an error.

### The same equity approach for both parts {#auto-derivation-of-pathway-approaches}

Users name only the budget approach, for example `equal-per-capita-budget`.
The library derives the matching pathway approach for the non-CO₂ part.
The same equity principle then governs both parts, adapted to budget and pathway allocation.
This needs scenario pathways for the requested climate assessments in the active source set.

??? info "How parameters carry over"

    - `equal-per-capita-budget` → `equal-per-capita`
    - `per-capita-adjusted-budget` → `per-capita-adjusted`
    - `per-capita-adjusted-gini-budget` → `per-capita-adjusted-gini`
    - `allocation_year` → `first_allocation_year`
    - `preserve_allocation_year_shares` → `preserve_first_allocation_year_shares`
    - `cumulative_end_year` → removed. It bounds the cumulative population window of budget allocations, and pathway shares are computed per year.

    Keys may be kebab-case or snake_case. The derived config uses snake_case.
    All other parameters pass through unchanged, including `capability_reference_year` and `capability_window`.
    Pathway approaches support both with the same meaning as budgets.
    A derived config therefore names exactly the parameters that will run.
    `run_allocation` rejects any parameter its approach lacks.

### Scenario pathway targets {#single-pass-exception}

With `target=pathway`, the all-GHG categories stay whole.
When the scenario source provides direct data for `all-ghg` or `all-ghg-ex-co2-lulucf` (as AR6 does), the library runs one pathway allocation.

---

## Methane pairing {#methane-pairing}

A budget depends on the methane pathway it assumes.
An additional sustained linear 10% cut in methane emissions to 2050 raises the 2 °C (50%) budget by about 165 Gt CO₂ ([Weber 2026b](https://doi.org/10.1038/s43247-026-03832-1)).
The library therefore takes the non-CO₂ pathway from scenarios of the same climate target as the budget.
A different methane pathway needs a matching budget.

---

## Non-CO₂ history and scenarios {#non-co2-derivation}

Non-CO₂ emissions are not a native category.
The library derives them by subtraction, with different inputs for history and for scenarios.

**History.** The pipeline subtracts fossil CO₂ from all-GHG without land-use CO₂, country by country.
The historical non-CO₂ series holds no land-use CH₄ or N₂O (see the PRIMAP note below).

**Scenarios.** Notebook 104 harmonises each AR6 pathway to history.
It takes the median of each category over the non-CO₂ set of every budget, then subtracts the medians.
The AR6 non-CO₂ series includes AFOLU CH₄ and N₂O.
Harmonisation to the 2020 historical value removes the level difference to the historical series at the harmonisation year.

??? note "Equations and files"

    History (`derive_non_co2_country_timeseries()` in `src/fair_shares/library/utils/data/non_co2.py`):

    $$
    \text{non-CO}_2 = \text{all-ghg-ex-co2-lulucf} - \text{co2-ffi}
    $$

    Scenarios:

    $$
    \text{non-CO}_2 = \text{median}(\text{all-ghg}) - \text{median}(\text{co2})
    $$

    The result is a difference of medians.
    In a decomposition run the two medians are those of `all-ghg-ex-co2-lulucf` and `co2-ffi`.
    Notebook 104 writes them per budget to `scenarios_{category}_by_budget_timeseries.csv` (`median_pathways_by_budget()` in `src/fair_shares/library/utils/data/scenario_sets.py`).
    Each budget gets the median of its own non-CO₂ set.

??? info "PRIMAP category `M.0.EL`"

    PRIMAP category `M.0.EL` excludes all land-use emissions: CO₂, CH₄ and N₂O.
    Agriculture (`M.AG`) stays in.
    `all-ghg-ex-co2-lulucf` therefore also excludes land-use CH₄ and N₂O. The name stays for compatibility.

---

## Start-year limits {#start-year-limits}

NGHGI land-use CO₂ data start in 2000.
With an inventory source (`melo-2026-v4`, the default, or `melo-2026`), `co2` and `all-ghg` therefore take allocation years from 2000 onward.
The bookkeeping source `gcb-2025-luc` runs from 1850, so on the model basis they can start from 1850.
`co2-ffi` and `all-ghg-ex-co2-lulucf` hold no land-use CO₂, and their history starts in 1850.
An allocation year before the first year of the data raises an error that names the first available year.
[Allocation years other than 2020](remaining-carbon-budgets.md#allocation-year) explains why the land-use series starts in 2000.

---

## Past non-CO₂ use in remaining budgets {#historical-deviation}

A country's remaining budget nets its observed emissions through the last observed year.
The two parts net differently:

- **CO₂ budget part.** Remaining = allocated total minus observed emissions from the allocation year. Past over-use is a debt, and the remaining budget can go negative.
- **Non-CO₂ pathway part.** Remaining = the allocation for the years after the last observed year. The `historical-deviation` column reports observed minus allocated non-CO₂ over the past years. A positive value is over-use.

Two modes settle past non-CO₂ over-use (`nonco2_debt_mode`):

- **`report-only`.** The CO₂ budget stays as it is. The deviation is reported and carries no penalty. `free-rider`, the earlier name, still works and warns that it is deprecated.
- **`co2-debit`.** Each country's past non-CO₂ over-use is subtracted from its remaining CO₂ budget and retired. The global CO₂ pathway is rebuilt to the reduced total, so the country pathways stay consistent.

In both modes past under-use earns nothing, and the forward non-CO₂ pathways stay as allocated.
The `co2-debit` results depend on the GWP100 metric. Equating past methane excess with future CO₂ space is an accounting convention.
The functions are `compute_remaining_budgets()` and `distribute_remaining_pathways()` in the [Python API](../api/python-api.md#compute_remaining_budgets).

The sources cited here are on the [References](references.md) page.
