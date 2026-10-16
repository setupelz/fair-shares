---
title: Country fair shares
description: Divide a carbon budget or an emissions pathway between individual countries
---

# Country fair shares

Divide a carbon budget or an emissions pathway between individual countries.

## Which notebook

`301_custom_fair_share_allocation` is the blank workspace. You set every option in its one configuration cell, then run all cells.
If you are new, start from a worked example and change it once it runs:

| Notebook | What it does |
| --- | --- |
| `302_example_templates_budget_allocations` | Budgets: one cumulative number per country. Runs unchanged. |
| `303_example_templates_pathway_allocations` | Pathways: a value per country per year. Runs unchanged. |

Each notebook builds the processed data it needs on its first run, which takes a few minutes. Later runs reuse it.
Budget runs (`rcbs`) also read three files you place by hand once ([Files you place yourself](../quickstart.md#files-you-place-yourself)).

## 1. Choose the data

`emission_category` sets the gases:

| Category | Covers | Notes |
| --- | --- | --- |
| `co2-ffi` | CO₂ from fossil fuels and industry | |
| `co2` | `co2-ffi` plus land-use CO₂ | National-inventory land use; start years from 2000 |
| `all-ghg-ex-co2-lulucf` | All greenhouse gases except land-use CO₂ | GWP100 AR6. Historical PRIMAP data also exclude land-use CH₄ and N₂O |
| `all-ghg` (default in 301) | All greenhouse gases | GWP100 AR6; start years from 2000 |

`active_sources["target"]` sets what is divided:

| Target | Approaches | Divides |
| --- | --- | --- |
| `rcbs` | Budget | A remaining carbon budget, one cumulative value per country |
| `pathway` | Pathway | Scenario pathways such as IPCC AR6 |
| `rcb-pathways` | Pathway | A budget turned into a global pathway, then divided year by year ([RCB pathway generation](../science/other-operations.md#rcb-pathway-generation)) |

The other entries of `active_sources` pick the emissions, population, GDP, Gini and land-use sources.
The comments in the cell list the options. [Data & licences](data-sources.md) gives each source's coverage and terms.

## 2. Choose the approaches

`allocations` maps each approach to a list of parameter sets. The notebook runs every combination in each set:

```python
allocations = {
    "equal-per-capita-budget": [
        {"allocation_year": [2020], "preserve_allocation_year_shares": [False]}
    ],
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [2020],
            "preserve_allocation_year_shares": [False],
            "pre_allocation_responsibility_weight": [0.5],
            "capability_weight": [0.5],
        }
    ],
}
```

The second entry shows the structure only. [From principle to code](../science/principle-to-code.md) has complete worked configurations.
For `all-ghg`, the notebook derives the non-CO₂ pathway approaches from the budget approaches.

Budget approaches: `equal-per-capita-budget`, `per-capita-adjusted-budget` (responsibility and capability), `per-capita-adjusted-gini-budget` (plus inequality within countries).

Pathway approaches: `equal-per-capita`, `per-capita-adjusted`, `per-capita-adjusted-gini`, `cumulative-per-capita-convergence` and its `-adjusted` and `-gini-adjusted` forms, and `per-capita-convergence`.
`per-capita-convergence` is for comparison only, because convergence from current levels embeds grandfathering during the transition ([Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7)).

The [Approach catalog](approach-catalog.md) describes each approach, and [Allocation approaches](../science/allocations.md) its parameters.
The five entry points of [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f) help you decide: foundational principles, allocation quantity, allocation approach, indicators, and implications for all others.

## 3. Read the results

Results land in `output/{source_id}/allocations/{allocation_folder}/`. A folder of the same name is overwritten.

| File | Holds |
| --- | --- |
| `allocations_relative.parquet` | Relative shares, summing to 1 |
| `allocations_absolute.parquet` | Relative share × global target, in Mt CO₂e |
| `allocations_wide.csv` | Wide format for spreadsheets |
| `param_manifest.csv` | Every parameter combination |

The `approach` column separates the approaches. [Outputs](output-schema.md) documents every column.

!!! note "Negative allocations"
    A negative allocation means past emissions exceed the allocation. It is an expected result for high historical emitters, for example under equal cumulative per capita from 1990. [Negative allocation](../science/glossary.md#negative-allocation) gives how the literature reads it.

To subtract observed emissions and spread a budget into an annual pathway, see [Remaining budgets and annual pathways](pipeline-map.md#4-remaining-budgets-and-annual-pathways-notebook-601-and-the-python-api).
