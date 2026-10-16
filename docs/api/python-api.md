---
title: Python API
description: In-memory allocation timeseries API for downstream consumers who do not run notebooks
---

# Python API

There are two ways to use fair-shares from your own code, and they have very
different requirements.

## The allocation functions, on data you supply

The allocation functions take population (and, for capability-adjusted
approaches, GDP) as pandas dataframes and hand back a result object. They read
no files, need no data directory, and take no configuration. A plain
`pip install "fair-shares @ git+https://github.com/setupelz/fair-shares"` is enough, and the code below runs from any directory:

```python
import pandas as pd
from fair_shares.library.allocations.budgets.per_capita import equal_per_capita_budget

years = [str(y) for y in range(2020, 2051)]
population = pd.DataFrame(
    [[50.0] * len(years), [10.0] * len(years)],
    index=pd.MultiIndex.from_tuples(
        [("AAA", "million"), ("BBB", "million")], names=["iso3c", "unit"]
    ),
    columns=years,
)

result = equal_per_capita_budget(
    population_ts=population,
    allocation_year=2020,
    emission_category="co2-ffi",
)

print(result.relative_shares_cumulative_emission["2020"])
```

Country AAA gets 50/60 of the budget, BBB gets 10/60. Multiply those shares by
your global budget to get absolute numbers. The dataframe needs one row per
country, a two-level index of country code and unit, and one column per year
labelled as a string.

The full set is in [Budget Functions](allocations/budgets.md)
and [Pathway Functions](allocations/pathways.md).

## The orchestrated timeseries API

`calculate_allocation_timeseries` runs one allocation end to end in memory: the budget allocation, each country's remaining budget after observed emissions, and an annual pathway that spreads it.
It takes one budget anchor (`rcb_source`, `climate_assessment`, `quantile`), one emission category and one approach with scalar parameters.
It reads processed data from disk and builds it on the first run.
Notebook `601_reproduce_esabcc_2023` calls the same remaining-budget and pathway functions for its whole grid. `tests/integration/test_python_api_reproduces_notebook.py` checks that the single-allocation route gives the same numbers as the notebook's grid run. If you change either, regenerate its fixtures with `uv run python tests/fixtures/save_python_api_fixture.py`.

```python
from fair_shares.library.python_api import calculate_allocation_timeseries

result = calculate_allocation_timeseries(
    emission_category="co2-ffi",
    rcb_source="lamboll_2023",
    climate_assessment="1.5C",
    quantile=0.5,
    allocation={
        "equal-per-capita-budget": {
            "allocation_year": 2020,
            "preserve_allocation_year_shares": False,
        }
    },
    shape="half-sine",            # how the pathway redresses past over-use
    deviation_end_year=2050,      # year that redress ends
    convergence_year=2050,        # year per-capita emissions converge
    nonco2_debt_mode=None,        # "report-only" or "co2-debit" for all-GHG categories
    pathway_end_year=2100,
    base_share_floor_mt=0.001,    # floor for net-sink countries' starting share
    desired_harmonisation_year=2020,
    emissions_source="primap-202609",
    gdp_source="wdi-2025",
    population_source="un-owid-2025",
    gini_source="wdi-2025",
    lulucf_source="melo-2026-v4",
    allocation_folder="my-run",
)

pathways = result.allocation_timeseries   # one row per country, one column per year
in_2030 = pathways["2030"].groupby(level="iso3c").sum()   # Mt CO2 in 2030
print(in_2030[["IND", "USA", "DEU"]])
```

The distribution settings are normative choices. [Outputs](../user-guide/output-schema.md#python-api-result) lists what the result holds, and [EU budgets](../user-guide/eu-budgets.md) sums the result over a group of countries.
Loop over approaches, anchors and settings to build a larger set. Parameter grids and pathway targets run in the notebooks.

Inside a checkout the function finds `data/` and `output/` itself. From an installed package, set `FAIR_SHARES_DATA_DIR` and `FAIR_SHARES_OUTPUT_DIR`, or pass `data_dir=` and `output_dir=`.
Building missing processed data needs Snakemake, from the `pipeline` extra.

## Computing Allocation Timeseries

### calculate_allocation_timeseries

::: fair_shares.library.python_api.calculate_allocation_timeseries
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## Presets

A preset holds the parameter set of a published study, because several library defaults differ from published settings.
`fair_shares.library.presets` holds the ESABCC 2023 preset that notebook 601 runs.
`esabcc_2023_allocations(category)` returns the grid for `run_all_allocations`, and `esabcc_2023_allocation_list(category)` the same runs one by one for `calculate_allocation_timeseries`.
[The ESABCC presets](../user-guide/eu-budgets.md) runs it.

::: fair_shares.library.presets.esabcc_2023.esabcc_2023_allocations
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

::: fair_shares.library.presets.esabcc_2023.esabcc_2023_allocation_list
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

::: fair_shares.library.presets.esabcc_2023.ESABCC_2023_RCB_ANCHOR
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

::: fair_shares.library.presets.esabcc_2023.ESABCC_2023_CATEGORIES
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## Allocation Steps

`calculate_allocation_timeseries` composes these steps. Call them directly when you already hold an allocations frame.

### compute_remaining_budgets

::: fair_shares.library.python_api.compute_remaining_budgets
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### distribute_remaining_pathways

::: fair_shares.library.python_api.distribute_remaining_pathways
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### build_history

::: fair_shares.library.python_api.build_history
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## Results

### ResultContainer

::: fair_shares.library.python_api.ResultContainer
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: true

### save_results

::: fair_shares.library.python_api.save_results
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## Citing a run

`save_results` writes a `CITATIONS.md` next to the results. It lists the software and exactly the data sources the run used.
To get the list in code, or from the command line:

```python
from fair_shares.library.citations import citations

run = citations(active_sources, emission_category="all-ghg")
print(run.text())     # software, then each data source with DOI and licence
print(run.bibtex())
```

```bash
uv run fair-shares cite --sources gini=wdi-2025,target=pathway --bibtex
```

Sources without a DOI (World Bank, OWID, UN WPP) are credited by name.
Terms that ask for more than attribution get their own section: the Global Carbon Project's co-authorship request, CMIP7's component datasets, the non-commercial share-alike licence of PRIMAP-hist v2.8, WIID's non-commercial clause and the Scenario Compass embargo terms.
[Data & licences](../user-guide/data-sources.md) explains what this means for outputs.

::: fair_shares.library.citations.citations
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
