---
title: EU budgets with the ESABCC preset
description: National, EU27 and EEA remaining budgets with the allocation settings of the ESABCC 2023 advice
---

# EU budgets with the ESABCC preset

This guide computes remaining budgets for EU countries, the EU27 and the EEA with the settings of the ESABCC 2023 advice ([ESABCC 2023](https://doi.org/10.2800/609405); [Pelz 2023](https://pure.iiasa.ac.at/18830)).
The preset `esabcc_2023_allocations()` holds those settings. Several library defaults differ from them, so use the preset rather than building the runs by hand.
[ESABCC 2023 reproduction](../reproductions/esabcc-2023.md) compares the results with the original study.

Before you start, fetch the input data and the three manual files ([Install and data](../quickstart.md)).

## Run one allocation

The example takes the first run of the `co2-ffi` grid: equal per capita from 1990.
It uses the settings of notebook `601_reproduce_esabcc_2023`, section 3.

```python
from fair_shares.library.presets import (
    ESABCC_2023_RCB_ANCHOR,
    esabcc_2023_allocation_list,
)
from fair_shares.library.python_api import calculate_allocation_timeseries

EU27 = [
    "AUT", "BEL", "BGR", "CYP", "CZE", "DEU", "DNK", "ESP", "EST", "FIN",
    "FRA", "GRC", "HRV", "HUN", "IRL", "ITA", "LTU", "LUX", "LVA", "MLT",
    "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "SWE",
]
EEA = EU27 + ["ISL", "NOR"]  # Liechtenstein is in rest of world

allocations = esabcc_2023_allocation_list("co2-ffi")

result = calculate_allocation_timeseries(
    emission_category="co2-ffi",
    allocation=allocations[0],
    rcb_source=ESABCC_2023_RCB_ANCHOR["source"],
    climate_assessment=ESABCC_2023_RCB_ANCHOR["climate-assessment"],
    quantile=ESABCC_2023_RCB_ANCHOR["quantile"],
    shape="half-sine",
    deviation_end_year=2050,
    convergence_year=2050,
    nonco2_debt_mode=None,
    pathway_end_year=2100,
    base_share_floor_mt=0.001,
    desired_harmonisation_year=2020,
    emissions_source="primap-202609",
    gdp_source="wdi-2025",
    population_source="un-owid-2025",
    gini_source="wdi-2025",
    lulucf_source="melo-2026-v4",
    allocation_folder="eu-budgets",
)

pathways = result.allocation_timeseries
iso3c = pathways.index.get_level_values("iso3c")
future = [c for c in pathways.columns if int(c) > result.netting_end_year]
remaining = pathways[future].sum(axis=1).groupby(iso3c).sum() / 1000  # Gt CO2

print(f"Remaining from {result.netting_end_year + 1}:")
print("EU27", round(remaining[EU27].sum(), 1), "Gt CO2")
print("EEA ", round(remaining[EEA].sum(), 1), "Gt CO2")
```

The first run builds the processed data and takes a few minutes.
`allocations` holds 36 runs for `co2-ffi`. Loop over it to compute every approach of the study.

## What the result holds

`result.allocation_timeseries` has one row per country. Its index holds `iso3c` and the identifying columns listed in [Outputs](output-schema.md#annual-pathways), and its columns are the years to `pathway_end_year`. The years after `result.netting_end_year` sum to the remaining budget.
`remaining` in the example is a Series of remaining budgets in Gt CO2, indexed by `iso3c`. Summing it over a list of ISO3 codes gives a group total, as the example does for the EU27 and the EEA.

The library allocates to countries. The EU27 and EEA values are sums of their members.
For the responsibility approaches this differs from allocating to the EU27 as one region, as the original study did ([Reproduction accuracy](../reproductions/esabcc-2023.md#reproduction-accuracy)).

Each country's annual pathway to `pathway_end_year` sums to its remaining budget.
The remaining budget is the allocation minus observed emissions from the allocation year to `netting_end_year`, the last observed year: 2025 for `co2-ffi`.
A remaining budget can be negative when past emissions exceed the allocation.
`shape`, `deviation_end_year` and `convergence_year` set how the pathway spreads the budget over time. They are normative choices ([Python API](../api/python-api.md)).

Countries without complete data fall into rest of world and get no row of their own.
Liechtenstein has no GDP series, so it is in rest of world and missing from the EEA sum.
`country_data_coverage_summary.csv` in the processed folder names every country in rest of world.

## Other categories

The preset also covers `all-ghg-ex-co2-lulucf` and `all-ghg`.
Both allocate from 2015 only, and `all-ghg` starts its responsibility window in 2000, where national land-use data begin.
For these categories pass `nonco2_debt_mode`, one of `"report-only"` or `"co2-debit"`. [Greenhouse gases](../science/greenhouse-gases.md) explains the two modes.
