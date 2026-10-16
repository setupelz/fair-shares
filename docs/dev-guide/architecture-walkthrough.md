---
title: Architecture
description: End-to-end code path of a fair-shares allocation, from the notebook to the parquet file
---

# Architecture

This page traces one allocation from the notebook configuration cell to the parquet file on disk.
Read it before changing the code. The [Pipeline map](../user-guide/pipeline-map.md) lists every stage, notebook and output file, and the [Science](../science/allocations.md) pages explain the equity principles.

## Layer map

A request flows down the layers, and data flows back up.

| Layer | Module | Responsibility | Entry points |
|-------|--------|----------------|--------------|
| 0 Notebook | `notebooks/301_custom_fair_share_allocation.py` | Configuration, data pipeline trigger, plots | "Configuration (edit this)" and "Execution (Run All from here)" |
| 1 Helpers | `notebook_helpers.py` | Load data, run every allocation, print a summary | `load_allocation_data()`, `run_all_allocations()`, `run_and_save_category_allocations()` |
| 2 Manager | `allocations/manager.py` | Approach registry, parameter grid, single dispatch, saving, budget or pathway classification | `run_parameter_grid()`, `run_allocation()`, `get_function()`, `is_budget_approach()` |
| 3 Maths | `allocations/budgets/per_capita.py`, `allocations/pathways/*.py` | Population shares and the responsibility and capability adjustments | `_per_capita_budget_core()`, `equal_per_capita_budget()` |

The maths returns **relative shares** in two containers from `allocations/results/__init__.py`:
`BudgetAllocationResult` (`relative_shares_cumulative_emission`, one year column) and `PathwayAllocationResult` (`relative_shares_pathway_emissions`, one column per year). Each column sums to 1.0.
The helpers multiply shares by a global budget or pathway later. The same allocation therefore applies to any budget estimate or scenario without rerunning the maths.

The manager classifies an approach as a budget approach when its name ends in `-budget`. Keep that convention for new approaches.

---

## Example 1: a `co2-ffi` budget

Notebook 301 configured with:

```python
emission_category = "co2-ffi"
active_sources = {"target": "rcbs", ...}
allocations = {
    "equal-per-capita-budget": [{"allocation_year": [2015], "preserve_allocation_year_shares": [False]}]
}
```

### 1. Data pipeline

The notebook calls `setup_data()` (`utils/data/setup.py`). It:

1. validates the configuration with `build_data_config()` (`utils/data/config.py`), which reads `conf/data_sources/data_sources_unified.yaml` and checks it with Pydantic (`config/models.py`);
2. builds the paths and the Snakemake command;
3. compares the provenance stamp `output/<source_id>/.provenance_stamp.json` (`utils/data/provenance.py`) with fresh hashes. A missing or different stamp adds `--forceall` and logs what changed. `FAIR_SHARES_TRUST_CACHE=1` or `trust_cache=True` skips the check. The check needs a checkout, so an installed package reuses a prebuilt tree as it is;
4. runs Snakemake when files are missing or the stamp differs, and writes a fresh stamp after a successful run.

The `Snakefile` runs the preprocessing notebooks in dependency order and ends with the master notebook, `100_data_preprocess_rcbs` for budgets (`MASTER_NOTEBOOKS`).
With `active_scenario_source: ar6`, notebook 104 also selects the scenario sets of every budget (`utils/data/scenario_sets.py`) and writes `rcb_scenario_adjustments.yaml`, one `scenario_set_{source}_{label}.csv` per budget and `bunker_share_reporters.csv`.
The processed CSVs land in `output/<source_id>/intermediate/processed/`.

### 2. Load data

`load_allocation_data()` reads the processed CSVs:

- `emissions_data["co2-ffi"]`: country emissions indexed by `iso3c`, `unit`, `emission-category`;
- `rcbs_data["co2-ffi"]`: one row per budget with `source`, `climate-assessment`, `quantile` and `rcb_2020_nghgi_mt`, plus each budget's deductions and the provenance of its scenario sets;
- `world_emissions_data["co2-ffi"]`: world history, which converts a budget from 2020 to a budget from the allocation year;
- GDP, population and Gini, validated.

### 3. Run allocations

`run_all_allocations()` splits the approaches into budget and pathway with `is_budget_approach()`, loops over `final_categories` (here only `co2-ffi`) and calls `run_and_save_category_allocations()`.

`_run_budget_allocations()` calls `run_parameter_grid()` **once** per category, because shares depend only on the socioeconomic data and the parameters. Then, for each budget row, it:

1. converts the budget from 2020 to a budget from the allocation year with `calculate_budget_from_rcb()`;
2. multiplies the shares by it with `BudgetAllocationResult.get_absolute_budgets()`;
3. saves the result with `save_allocation_result()`.

### 4. Parameter grid and dispatch

`run_parameter_grid()` validates the target and allocation years, converts kebab-case keys to snake_case, and expands each list into combinations with `_expand_parameters()` (`itertools.product`; here one combination).
`run_allocation()` then:

1. looks up the function with `get_function("equal-per-capita-budget")`;
2. checks the user's parameters against the function signature. An unknown parameter raises `AllocationError` that names the approach, the rejected parameters and the accepted ones, so every configured parameter reaches the approach;
3. passes the data frames the function accepts (`validate_function_parameters()`, `filter_function_parameters()`) and calls it.

### 5. Maths

`equal_per_capita_budget()` calls `_per_capita_budget_core()` with both weights at 0.0.
It filters population to the allocation year onwards, converts units, sums each country's population, divides by the world total, applies `max_deviation_sigma` if set, and returns a `BudgetAllocationResult`.

### 6. Saving

`save_allocation_result()` (`manager.py`) hands over to `results/serializers.py`. It adds metadata columns from `results/metadata.py` and appends rows to `allocations_relative.parquet` and `allocations_absolute.parquet`.
After the last budget row, `create_param_manifest()` writes `param_manifest.csv`, and `generate_readme()` the README files.

---

## Example 2: an `all-ghg` budget {#composite-category-decomposition}

The same configuration with `emission_category = "all-ghg"`.
A remaining carbon budget limits CO₂ only, so the run splits into a CO₂ budget and a non-CO₂ pathway. `utils/data/config.py` decides this:
`is_composite_category("all-ghg")` and `needs_decomposition("rcbs", "all-ghg")` are `True`, and `get_final_categories("rcbs", "all-ghg")` returns `("co2", "non-co2")`.

**Pipeline.** The Snakefile preprocesses emissions for `co2-ffi`, `co2`, `co2-lulucf` and `all-ghg-ex-co2-lulucf`, and scenarios for `co2-ffi` and `all-ghg-ex-co2-lulucf`.
It derives non-CO₂ by subtraction (rules `derive_non_co2_emissions`, `derive_non_co2_scenarios`): `all-ghg-ex-co2-lulucf - co2-ffi`.
In budget mode the subtraction runs on the median pathway of each budget's non-CO₂ set, so non-CO₂ rows carry the budget's `source`.
The master step runs twice: `100_data_preprocess_rcbs` for `co2` and `100_data_preprocess_pathways` for `non-co2`.

**Auto-derived pathway approaches.** You define only budget approaches. `run_all_allocations()` derives the pathway approaches with `derive_pathway_allocations()` (`manager.py`), which maps each budget approach to its pathway form and renames or drops budget-only parameters ([the mapping](../science/greenhouse-gases.md#auto-derivation-of-pathway-approaches)).

**Category loop.** The `co2` pass follows example 1. The `non-co2` pass calls `_run_pathway_allocations()`, which groups scenarios by `climate-assessment`, `quantile` and, for budget runs, `source`, takes each group's world pathway, runs the grid, and multiplies year-by-year shares by the pathway with `PathwayAllocationResult.get_absolute_emissions()`.
The pathway maths (`pathways/per_capita.py`, `_per_capita_core()`) uses `first_allocation_year` and returns one column per year. With `preserve_first_allocation_year_shares=False`, each year's shares follow that year's population.

**Scenario labels.** Notebook 104 maps each scenario source's categories to normalised `climate-assessment` and `quantile` fields, and downstream code reads only these ([Scenario labels](../science/scenario-sets.md#scenario-labels)).

**Missing pathways.** A budget label whose non-CO₂ set holds fewer than `min_scenarios` scenarios raises a `ConfigurationError` in notebook 104 that names the label. The Python API raises a `ValueError` when a budget row has no non-CO₂ pathway ([Decomposition](../science/greenhouse-gases.md#decomposition-rules)).

---

## Preprocessing

| Module | Location | Purpose |
|--------|----------|---------|
| `DataPreprocessor` | `pipeline/preprocessing.py` | Load, validate, filter to analysis countries, add rest of world |
| `run_rcb_preprocessing()` | `pipeline/preprocessing.py` | Budget corrections and processing |
| `run_pathway_preprocessing()` | `pipeline/preprocessing.py` | Scenario loading and processing |
| `run_composite_preprocessing()` | `pipeline/preprocessing.py` | The two passes of an all-GHG run |
| `run_non_co2_preprocessing()` | `pipeline/preprocessing.py` | Non-CO₂ by subtraction, then pathway processing |

`DataPreprocessor` keeps the countries with complete emissions, GDP and population from 1990 and adds a rest-of-world row: the world total minus those countries. Allocations therefore cover all global emissions.
Gini does not decide membership. A country without a Gini value stays in and gets an imputed value under `general.gini_missing_policy` (default `fallback-mean`).
An emissions source can add a coverage rule (`coverage_exclusions` in `preprocessing/coverage.py`; [Analysis countries](../science/other-operations.md#analysis-countries)).

```
output/<source_id>/
  .provenance_stamp.json        input hashes; decides reuse or rebuild
  config.yaml                   validated configuration
  notebooks/                    executed preprocessing notebooks
  intermediate/
    emissions/                  per-category CSVs, world_co2-lulucf_timeseries.csv,
                                bunker_timeseries.csv, lulucf_metadata.yaml
    gdp/  population/  gini/
    scenarios/                  scenario timeseries; budget mode adds rcb_scenario_adjustments.yaml,
                                scenario_set_*.csv, bunker_share_reporters.csv
    processed/                  country_*.csv; rcbs_*.csv and world_emissions_*.csv (budgets);
                                world_scenarios_*_complete.csv (pathways)
  allocations/<folder>/         see Outputs
```

[Outputs](../user-guide/output-schema.md) documents the allocation files.

---

## Where do I change X?

| I want to... | File(s) | Function or class |
|---------------|---------|-------------------|
| Add an allocation approach | `allocations/budgets/*.py` or `allocations/pathways/*.py`, then `allocations/manager.py` | The maths function, and an entry in `get_allocation_functions()` |
| Change how parameters expand | `allocations/manager.py` | `_expand_parameters()`, `run_parameter_grid()` |
| Add a data source | `conf/data_sources/data_sources_unified.yaml`, a `notebooks/10x_*.py`, `Snakefile` | Config entry, preprocessing notebook, Snakefile rule |
| Change validation rules | `validation/` | `validate_allocation_parameters()`, `validate_target_source_compatibility()` |
| Change the parquet schema | `allocations/results/metadata.py` | `DATA_CONTEXT_COLUMNS`, `ALLOCATION_PARAMETER_COLUMNS` |
| Add an emission category | `utils/data/config.py` | `get_final_categories()`, `get_emission_preprocessing_categories()` |
| Change budget processing | `preprocessing/rcbs.py`, `utils/data/rcb.py` | `load_and_process_rcbs()`, `calculate_budget_from_rcb()` |
| Change the scenario sets behind budget terms | `utils/data/scenario_sets.py`, `data/rcbs/rcbs.yaml` | `build_budget_sets()`, `bunker_share()` |
| Add a scenario source | `conf/scenario_sources.yaml`, `utils/data/scenario_sources.py` | `get_scenario_source()` |
| Change the NGHGI corrections | `utils/data/nghgi.py`, `config/models.py` (`AdjustmentsConfig`) | `build_nghgi_world_co2_timeseries()` |
| Change the notebook helpers | `notebook_helpers.py` | `load_allocation_data()`, `run_all_allocations()`, `run_and_save_category_allocations()` |
| Change the Snakemake pipeline | `Snakefile`, `utils/data/setup.py` | Snakefile rules, `setup_data()` |
| Add a plot | `visualization/` | `plot_allocation_comparison()`, `plot_decomposition_summary()` |
| Change composite decomposition | `utils/data/config.py`, `pipeline/preprocessing.py` | `needs_decomposition()`, `run_composite_preprocessing()` |
| Change result saving | `allocations/results/serializers.py` | `save_allocation_result()` |
| Change the budget-to-pathway derivation | `allocations/manager.py` | `_BUDGET_TO_PATHWAY`, `_PARAM_RENAMES`, `derive_pathway_allocations()` |
