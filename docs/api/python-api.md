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
no files, need no data directory, and take no configuration — a plain
`pip install fair-shares` is enough, and the code below runs from any directory:

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

The full set is in [Budget Functions](https://setupelz.github.io/fair-shares/api/allocations/budgets/)
and [Pathway Functions](https://setupelz.github.io/fair-shares/api/allocations/pathways/).

## The orchestrated timeseries API

The `fair_shares.library.python_api` module runs a whole allocation — budget,
remaining budget, and annual pathway — in memory and returns it as a dataclass,
so downstream consumers never have to execute a notebook or manage its output
directories. Unlike the functions above, it loads processed data from disk.

## Overview

Notebook `601_reproduce_esabcc_2023` computes, for one remaining-carbon-budget *anchor* (a `rcb_source` / `climate_assessment` / `quantile` triple) and one emission category:

- budget allocations of the remaining carbon budget (§ 4),
- each country's remaining budget after netting observed emissions (§ 5), and
- an annual pathway to `pathway_end_year` that spreads that remaining budget under a normative distribution grid, plus the non-CO2 and combined parts (§ 6).

[`calculate_allocation_timeseries`](#calculate_allocation_timeseries) performs exactly that computation and returns a [`ResultContainer`](#resultcontainer). The heavy lifting stays in the existing library functions; this module ports the notebook's § 5 / § 6 orchestration and ties it together per (anchor, category).

The notebook and this module are two implementations of the same calculation. `tests/integration/test_python_api_reproduces_notebook.py` is the guard against them drifting apart: it re-runs `calculate_allocation_timeseries` against fixtures saved from the notebook. If you change either side, regenerate the fixtures with `uv run python tests/fixtures/save_python_api_fixture.py` and confirm that test still passes.

!!! note "Scope"

    This module computes remaining-carbon-budget allocations only (`TARGET = "rcbs"`), for a single fully-specified allocation under a single RCB anchor. Loop over allocations, distribution settings and debt modes around it to build a fuller set. To run parameter grids or pathway targets, use the notebook workflows described in the [User Guide](https://setupelz.github.io/fair-shares/user-guide/).

!!! note "Data location"

    `calculate_allocation_timeseries` reads processed data from disk. Inside a
    checkout it finds `data/` and `output/` on its own. From an installed wheel,
    set `FAIR_SHARES_DATA_DIR` and `FAIR_SHARES_OUTPUT_DIR`, or pass `data_dir=`
    and `output_dir=`. If the processed files are missing it rebuilds them with
    Snakemake, which only ships in the `pipeline` extra — so a plain
    `pip install fair-shares` works against a data tree that has already been
    built, but not one that has to be built first. (The older `project_root`
    argument still works and maps onto the two directories, but is deprecated.)

## Computing Allocation Timeseries

### calculate_allocation_timeseries

::: fair_shares.library.python_api.calculate_allocation_timeseries
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## Allocation Steps

These are the individual steps `calculate_allocation_timeseries` composes. Call them directly when you already hold an allocations frame and want only part of the calculation.

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

Most inputs are third-party datasets that require attribution, and which ones a
run uses depends on its settings: a budget run subtracts international bunker
emissions, a composite category such as `all-ghg` also draws on the AR6 scenario
ensemble, and the Gini source is whichever you chose.

`save_results` writes a `CITATIONS.md` into the output directory alongside the
parquet files, so a saved run always records what to cite. Runs kept in memory
produce no file, since there is no directory to put one in.

To get the same list directly:

```python
from fair_shares.library.citations import citations

run = citations(active_sources, emission_category="all-ghg")
print(run.text())     # software, then each data source with DOI and licence
print(run.bibtex())   # the same as BibTeX entries
```

Or from the command line, without writing any code:

```bash
uv run fair-shares cite
uv run fair-shares cite --sources gini=wdi-2025,target=pathway --bibtex
```

Sources with no DOI issued (World Bank, OWID, UN WPP) are credited by name, and
the output says so rather than leaving a blank field. Sources whose terms ask
for more than attribution — the Global Carbon Project's co-authorship request,
CMIP7's component datasets, WIID's non-commercial clause — are called out in a
separate section.

::: fair_shares.library.citations.citations
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## See Also

- **[Allocation Manager](https://setupelz.github.io/fair-shares/api/allocations/manager/)**: The allocation engine this module calls into
- **[Math Utilities](https://setupelz.github.io/fair-shares/api/utils/math/)**: The convergence and pathway-distribution solvers used by § 6
- **[Output Schema](https://setupelz.github.io/fair-shares/user-guide/output-schema/)**: Column meanings for the returned frames
