---
title: Output columns
description: What every column of the fair-shares outputs holds
---

<!-- Generated from src/fair_shares/conf/output_columns.yaml by
     python -m fair_shares.library.utils.output_columns. Do not edit. -->

# Output columns

Every output folder also holds `columns.csv` with the entries of its own columns.
`<year>` stands for every year column.

## Identifiers

| Column | Meaning | Unit |
| --- | --- | --- |
| `iso3c` | Country code (ISO 3166-1 alpha-3); in notebook 405 also the region name for the region row |  |
| `region` | Region of the row in the IAMC files, the region name or a member's ISO3 code |  |
| `approach` | Allocation approach, for example equal-per-capita-budget |  |
| `climate-assessment` | Warming level of the budget or scenario set, for example 1.7C |  |
| `quantile` | Likelihood of staying below the warming level, for example 0.5 |  |
| `category` | Emission category of the run, for example all-ghg |  |
| `emission-category` | Part of the category the row holds, the CO2 part, non-co2, or combined for their sum |  |
| `unit` | Unit of the values in the row |  |
| `<year>` | Value for that year, stored as a string column name; the unit is in the row or the file description |  |

## Data sources

| Column | Meaning | Unit |
| --- | --- | --- |
| `source-id` | Composite identifier of the run's data sources; includes the land-use source when the category uses one |  |
| `allocation-folder` | Output folder name of the run |  |
| `source` | Source within the target, for example the budget source forster_2026 |  |
| `target-source` | Target type, rcbs, pathway or rcb-pathways |  |
| `rcb-generator` | Pathway generator for rcb-pathways; empty otherwise |  |
| `emissions-source` | Historical emissions dataset |  |
| `gdp-source` | GDP dataset |  |
| `population-source` | Population dataset |  |
| `gini-source` | Gini coefficient dataset |  |
| `lulucf-source` | Land-use CO2 dataset, which sets the land-use basis |  |
| `total-budget` | Global budget total behind the allocation | Mt CO2e |

## Parameters

| Column | Meaning | Unit |
| --- | --- | --- |
| `allocation-year` | Budget approaches, the year the budget is allocated from |  |
| `first-allocation-year` | Pathway approaches, the first year allocated |  |
| `preserve-allocation-year-shares` | Budget approaches, whether population shares are frozen at the allocation year |  |
| `preserve-first-allocation-year-shares` | Pathway approaches, whether population shares are frozen at the first allocation year |  |
| `cumulative-end-year` | Budget approaches, last year of the cumulative population window |  |
| `pre-allocation-responsibility-weight` | Weight of responsibility for emissions before the allocation year |  |
| `pre-allocation-responsibility-year` | First year whose emissions count towards responsibility |  |
| `pre-allocation-responsibility-per-capita` | Whether responsibility uses emissions per person (true) or a country's total emissions (false) |  |
| `pre-allocation-responsibility-exponent` | Exponent of the responsibility adjustment |  |
| `pre-allocation-responsibility-functional-form` | Functional form of the responsibility adjustment, asinh or power |  |
| `capability-weight` | Weight of capability (GDP-based) in the adjustment |  |
| `capability-per-capita` | Whether capability uses GDP per person (true) or total GDP (false) |  |
| `capability-exponent` | Exponent of the capability adjustment |  |
| `capability-functional-form` | Functional form of the capability adjustment, asinh or power |  |
| `capability-reference-year` | Year whose GDP per capita is held across the window; empty when capability is computed year by year |  |
| `capability-window` | Inclusive years of cumulative GDP over cumulative population, as start-end |  |
| `max-deviation-sigma` | Cap on how far an adjusted allocation can move from equal per capita, in standard deviations |  |
| `income-floor` | Gini-adjusted approaches, development threshold below which income does not count towards capability | dollars per person |
| `max-gini-adjustment` | Gini-adjusted approaches, largest share of GDP the income floor can remove from capability |  |
| `convergence-year` | Convergence approaches and pathway distribution, the year the convergence completes |  |
| `convergence-speed` | Convergence approaches, the share of the remaining distance to the long-run target closed per year |  |

## Quality

| Column | Meaning | Unit |
| --- | --- | --- |
| `warnings` | Quality warnings, if any |  |
| `moved-to-row` | Analysis countries placed in rest of world for this allocation only, separated by ; |  |
| `missing-net-negative-mtco2e` | Net-negative emissions the allocation needs but could not place | Mt CO2e |

## Remaining budgets

| Column | Meaning | Unit |
| --- | --- | --- |
| `netting-end-year` | Last year of observed emissions subtracted from the allocation, the last year every part of the category covers |  |
| `remaining-from-year` | First year of the remaining budget, netting-end-year + 1; in notebook 405 the first year of the model's first period |  |
| `allocated-total` | Allocation from the allocation year | Mt CO2e |
| `consumed-actuals` | Observed emissions from the allocation year to netting-end-year | Mt CO2e |
| `remaining-budget` | allocated-total minus consumed-actuals; for a non-CO2 pathway part, its allocation after netting-end-year. Can be negative | Mt CO2e |
| `historical-deviation` | Non-CO2 parts only, observed minus allocated emissions up to netting-end-year | Mt CO2e |

## Annual pathways

| Column | Meaning | Unit |
| --- | --- | --- |
| `adjusted-target` | Total the pathway sums to, the remaining budget less any non-CO2 debt in co2-debit mode | Mt CO2e |
| `shape` | Distribution setting, the shape of the pathway |  |
| `deviation-end-year` | Distribution setting, the year the deviation from the baseline ends |  |
| `nonco2-debt-mode` | Composite categories only, how past non-CO2 over-use is settled, report-only or co2-debit |  |
| `nonco2-debt-paid` | Composite categories only, the non-CO2 over-use subtracted from the CO2 budget | Mt CO2e |

## One region (notebook 405)

| Column | Meaning | Unit |
| --- | --- | --- |
| `n-countries` | Number of member countries summed into the row |  |
| `nonco2-overuse` | Composite categories only, the members' past non-CO2 over-use, summed over the members that over-used | Mt CO2e |
| `co2-budget` | CO2 budget of the area, cumulative from remaining-from-year to global net-zero CO2, after any non-CO2 debit | Mt CO2 |
| `start-adjustment` | Change that moved the budget to the model's first period, the observed emissions added back (positive) or the years before the period subtracted (negative) | Mt CO2 |
| `start-adjustment-estimated-years` | Years in start-adjustment without observed data, held at the last observed value, separated by ; |  |
| `budget` | Label of the global budget, source, warming level and likelihood |  |
| `allocation` | Label of the approach and its parameters (ay allocation year, rw responsibility weight, hr responsibility year, cw capability weight, re and ce exponents, rpc per-capita responsibility) |  |
| `scenario` | IAMC scenario name, prefix\|budget\|allocation, plus the debt mode for composite categories |  |
| `countries` | Member countries of the region, separated by ; |  |
| `regions` | Regions in the IAMC files, the region name and each member's ISO3 code |  |
| `co2-budget-definition` | What the CO2 row of the IAMC files holds, its variable, unit and years |  |
| `co2-accounting` | Which CO2 the budget covers and how land use is counted |  |
| `land-use-condition` | co2-ffi only, the condition on land-use CO2 under which the fossil budget is a fair share |  |
| `first-model-period` | The model's first period, first-last year |  |
| `non-co2-pathway` | Composite categories only, what the non-CO2 rows of the IAMC files hold |  |

## Land-use condition (notebook 405, co2-ffi)

| Column | Meaning | Unit |
| --- | --- | --- |
| `land-term-removed-mt` | Global land-use CO2 (bookkeeping basis) the fossil budget removed, from land-from-year to land-to-year; 0 when the precautionary cap counts a projected sink as zero | Mt CO2 |
| `land-share` | The area's share of the global allocation |  |
| `land-allowance-mt` | Land-use CO2 (bookkeeping basis) the area may emit net from land-from-year to land-to-year, land-share times land-term-removed-mt; a net source above it comes off the fossil budget | Mt CO2 |
| `land-allowance-mt-per-yr` | land-allowance-mt per year of the window | Mt CO2/yr |
| `land-from-year` | First year of the land-use window, the budget's baseline year |  |
| `land-to-year` | Last year of the land-use window, the median net-zero year of the budget's scenario set |  |
| `land-observed-years` | Years of the observed land-use CO2 columns, first-last |  |
| `bookkeeping-observed-median` | Observed land-use CO2 of the area, bookkeeping basis (Global Carbon Budget), median over land-observed-years | Mt CO2/yr |
| `bookkeeping-observed-min` | As bookkeeping-observed-median, the lowest year | Mt CO2/yr |
| `bookkeeping-observed-max` | As bookkeeping-observed-median, the highest year | Mt CO2/yr |
| `inventory-observed-median` | Observed land-use CO2 of the area, inventory basis (LULUCF Data Hub), median over land-observed-years | Mt CO2/yr |
| `inventory-observed-min` | As inventory-observed-median, the lowest year | Mt CO2/yr |
| `inventory-observed-max` | As inventory-observed-median, the highest year | Mt CO2/yr |
| `indirect-gap-median` | Inventory minus bookkeeping land-use CO2 per year, mostly indirect uptake the global budget counts as climate response; median over land-observed-years | Mt CO2/yr |
| `indirect-gap-min` | As indirect-gap-median, the lowest year | Mt CO2/yr |
| `indirect-gap-max` | As indirect-gap-median, the highest year | Mt CO2/yr |
| `inventory-equivalent-median` | Inventory land-use CO2 that meets the allowance, land-allowance-mt-per-yr plus indirect-gap-median | Mt CO2/yr |
| `inventory-equivalent-min` | As inventory-equivalent-median, with indirect-gap-min | Mt CO2/yr |
| `inventory-equivalent-max` | As inventory-equivalent-median, with indirect-gap-max | Mt CO2/yr |

## IAMC files

| Column | Meaning | Unit |
| --- | --- | --- |
| `Model` | Model name |  |
| `Scenario` | Scenario name |  |
| `Region` | Region name |  |
| `Variable` | Variable name, in the model's naming |  |
| `Unit` | Unit of the values |  |
