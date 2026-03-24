---
title: Architecture Walkthrough
description: End-to-end code path walkthrough for fair-shares allocations
icon: material/map-marker-path
---

# Architecture Walkthrough

This document traces the full execution path of a fair-shares allocation, from
the notebook configuration cell to the final parquet file on disk. Use it to
build a mental model of the codebase before making changes.

**Intended audience:** Developers who need to understand _where_ code runs and
_why_ the layers exist, not the climate science behind the equity principles
(see [Scientific Documentation](../science/allocations.md) for that).

---

## Layer Map

The codebase has four layers. A request flows top-to-bottom; data flows
bottom-to-top.

```
 Layer 0  Notebook / CLI                 notebooks/301_*.py
 Layer 1  Helpers                        notebook_helpers.py
 Layer 2  Manager                        allocations/manager.py
 Layer 3  Math                           allocations/budgets/per_capita.py
                                         allocations/pathways/per_capita.py
                                         allocations/pathways/per_capita_convergence.py
                                         allocations/pathways/cumulative_per_capita_convergence.py
```

| Layer | Module | Responsibility | Key entry point |
|-------|--------|----------------|-----------------|
| 0 | `notebooks/301_custom_fair_share_allocation.py` | User configuration, data pipeline trigger, visualization | Config cell (lines 57-106), execution cell (lines 250-286) |
| 1 | `src/.../notebook_helpers.py` | Extract boilerplate from notebooks; load data, run all allocations, print summary | `load_allocation_data()`, `run_all_allocations()`, `run_and_save_category_allocations()` |
| 2 | `src/.../allocations/manager.py` | Approach registry, parameter grid expansion, single allocation dispatch, result saving, budget/pathway classification | `run_parameter_grid()`, `run_allocation()`, `get_function()`, `is_budget_approach()` |
| 3 | `src/.../allocations/budgets/per_capita.py` | Actual math: population shares, capability/responsibility adjustments | `_per_capita_budget_core()`, `equal_per_capita_budget()` |

**Result containers** live alongside the math layer:

| Container | Module | Holds |
|-----------|--------|-------|
| `BudgetAllocationResult` | `allocations/results/__init__.py` | `relative_shares_cumulative_emission` -- single-year column, sums to 1.0 |
| `PathwayAllocationResult` | `allocations/results/__init__.py` | `relative_shares_pathway_emissions` -- multi-year columns, each sums to 1.0 |

Both containers store **relative shares** (dimensionless fractions). Absolute
emissions are computed later by multiplying shares by a global budget or world
pathway.

---

## Worked Example 1: Budget Allocation for CO2-FFI under RCBs

This traces what happens when a user configures notebook 301 with:

```python
emission_category = "co2-ffi"
active_sources = {"target": "rcbs", ...}
allocations = {
    "equal-per-capita-budget": [{"allocation_year": [2015], "preserve_allocation_year_shares": [False]}]
}
```

### Step 1: Data Pipeline (notebook 301, lines 144-187)

The notebook calls `setup_data()` from `src/.../utils/data/setup.py`. This
function:

1. **Validates config** via `build_data_config()` (`utils/data/config.py`)
   which loads `conf/data_sources/data_sources_unified.yaml`, filters to the
   selected target, and validates with Pydantic (`config/models.py`).
2. **Builds paths** via `build_data_paths()` (`utils/data/setup.py`).
3. **Generates a Snakemake command** via `generate_snakemake_command()`
   (`utils/data/setup.py`).
4. **Executes Snakemake** via `execute_snakemake_setup()`
   (`utils/data/setup.py`). This runs the `Snakefile` which
   orchestrates the 100-series preprocessing notebooks (emissions, GDP,
   population, Gini, scenarios) and produces CSV files under
   `output/<source_id>/intermediate/processed/`.

The Snakefile (`Snakefile`, line 174 `rule all`) chains:
`compose_config` -> `preprocess_emiss` -> `preprocess_gdp` ->
`preprocess_population` -> `preprocess_gini` -> `preprocess_lulucf` ->
`master_preprocess`.

For `target=rcbs`, the master notebook is `100_data_preprocess_rcbs`
(Snakefile line 101-105). No scenario notebook runs because RCBs are
cumulative budgets, not pathways.

**Output:** `output/<source_id>/intermediate/processed/` containing:

- `country_emissions_co2-ffi_timeseries.csv`
- `world_emissions_co2-ffi_timeseries.csv`
- `rcbs_co2-ffi.csv`
- `country_gdp_timeseries.csv`
- `country_population_timeseries.csv`
- `country_gini_stationary.csv`

### Step 2: Load Data (notebook 301, lines 250-263)

`load_allocation_data()` (`notebook_helpers.py`) reads the processed CSVs
into DataFrames. For RCB runs, it loads:

- `emissions_data["co2-ffi"]` -- country emissions indexed by
  `[iso3c, unit, emission-category]`
- `rcbs_data["co2-ffi"]` -- RCB table with columns: `source`,
  `climate-assessment`, `quantile`, `rcb_2020_mt`
- `world_emissions_data["co2-ffi"]` -- world historical emissions (used to
  convert RCB values to total budgets)
- Socioeconomic DataFrames: GDP, population, Gini (with validation)

### Step 3: Run Allocations (notebook 301, lines 278-286)

`run_all_allocations()` (`notebook_helpers.py`) orchestrates the full run:

1. **Splits approaches** into budget vs pathway using
   `is_budget_approach()` from the manager.
2. **Iterates over `final_categories`**. For `co2-ffi` with RCBs,
   there is one category: `("co2-ffi",)`.
3. **Delegates** to `run_and_save_category_allocations()`.

### Step 4: Category-Level Budget Runner (notebook_helpers.py)

`_run_budget_allocations()` does two things:

**4a. Compute share allocations:**

Calls `run_parameter_grid()` from `manager.py` with all budget approach
configs. This is called **once** per category because shares depend only on
socioeconomic data and approach parameters, not on individual RCB values.

**4b. Iterate over RCB rows:**

For each row in the RCB table (e.g., "1.5C|0.5 from IPCC AR6"):

1. Convert the RCB value (GtCO2 remaining from 2020) to a total budget for
   the allocation year using `calculate_budget_from_rcb()`.
2. Multiply relative shares by the total budget:
   `result.get_absolute_budgets(cumulative_budget)` -- calls
   `BudgetAllocationResult.get_absolute_budgets()`.
3. Save via `save_allocation_result()` to a parquet file.

### Step 5: Parameter Grid Expansion (manager.py)

`run_parameter_grid()` expands the config:

```python
{"equal-per-capita-budget": [{"allocation_year": [2015], "preserve_allocation_year_shares": [False]}]}
```

1. **Validates** target-source compatibility and allocation years.
2. **Iterates approaches**. For each approach:
   - Converts kebab-case keys to snake_case.
   - Validates parameters.
   - Expands parameter lists into combinations via `_expand_parameters()`.
     Here: 1 year x 1 preserve setting = 1 combination.
3. **Calls `run_allocation()`** for each combination.

### Step 6: Single Allocation Dispatch (manager.py)

`run_allocation()`:

1. Looks up the function: `get_function("equal-per-capita-budget")` from the
   approach registry in `manager.py`, which returns `equal_per_capita_budget`.
2. Builds `func_args` dict with all data + parameters.
3. Validates (`validate_function_parameters()`) and filters to only the
   parameters the function accepts (`filter_function_parameters()`).
4. Calls the math function.

### Step 7: The Math (budgets/per_capita.py)

`equal_per_capita_budget()` delegates to `_per_capita_budget_core()`
with `responsibility_weight=0.0` and `capability_weight=0.0`.

Inside `_per_capita_budget_core()`:

1. **Filter population** to allocation year onwards.
2. **Convert units** to common scale.
3. Since no adjustments, skip capability/responsibility blocks.
4. **Calculate shares**:
   - `group_totals = base_population.sum(axis=1)` -- sum each country's
     population from allocation year onward.
   - `world_totals = groupby_except_robust(group_totals, group_level)` --
     sum across all countries.
   - `shares = group_totals / world_totals` -- each country's fraction.
5. **Apply deviation constraint** if `max_deviation_sigma` is set.
6. **Return** a `BudgetAllocationResult` with the shares DataFrame.

### Step 8: Result Serialization

Back in `_run_budget_allocations()` (`notebook_helpers.py`),
`save_allocation_result()` (`manager.py`) delegates to
`results/serializers.py`. The serializer:

1. Adds metadata columns (approach, climate-assessment, quantile, data
   sources) from `results/metadata.py`.
2. Writes two parquet files per allocation:
   - `*_relative.parquet` -- dimensionless shares
   - `*_absolute.parquet` -- shares multiplied by the global budget (MtCO2)

After all RCB rows and approaches, `create_param_manifest()` writes
`param_manifest.csv` and `generate_readme()` writes documentation markdown.

---

## Worked Example 2: Pathway Allocation for all-GHG (Decomposition)

This traces a more complex case:

```python
emission_category = "all-ghg"
active_sources = {"target": "rcbs", ...}
allocations = {
    "equal-per-capita-budget": [{"allocation_year": [2015], "preserve_allocation_year_shares": [False]}]
}
```

### Why decomposition?

RCBs only constrain CO2. For all-GHG, the system must **decompose** into:

- **CO2 component** (`co2`): allocated via budget approach (RCBs)
- **non-CO2 component** (`non-co2`): allocated via pathway approach (AR6
  scenarios)

This logic lives in `utils/data/config.py`:

- `is_composite_category("all-ghg")` returns `True`
- `needs_decomposition("rcbs", "all-ghg")` returns `True`
- `get_final_categories("rcbs", "all-ghg")` returns `("co2", "non-co2")`
- `get_co2_component("all-ghg")` returns `"co2"`

### Step 1: Data Pipeline (Snakefile decomposition)

The Snakefile detects `is_multi_category = True` and:

1. Runs emissions preprocessing for all PRIMAP source categories:
   `co2-ffi`, `co2`, `co2-lulucf`, `all-ghg-ex-co2-lulucf` (Snakefile
   lines 228-251).
2. Runs AR6 scenario preprocessing for derivation sources: `co2-ffi` and
   `all-ghg-ex-co2-lulucf` (Snakefile lines 331-374).
3. **Derives non-CO2** by subtraction (Snakefile lines 386-429):
   - Historical: `non-co2 = all-ghg-ex-co2-lulucf - co2-ffi`
   - Scenarios: same subtraction on AR6 scenario data.
4. Runs master preprocessing twice (Snakefile lines 470-487):
   - CO2 pass: `100_data_preprocess_rcbs.ipynb` for `co2`
   - non-CO2 pass: `100_data_preprocess_pathways.ipynb` for `non-co2`

### Step 2: Auto-Derive Pathway Approaches

In `run_all_allocations()` (`notebook_helpers.py`):

The user only defined budget approaches (`equal-per-capita-budget`). But
non-CO2 needs pathway approaches. The helper auto-derives them:

```python
if budget_allocs and not pathway_allocs:
    pathway_allocs = derive_pathway_allocations(budget_allocs)
```

`derive_pathway_allocations()` (`manager.py`) maps:

- `equal-per-capita-budget` -> `equal-per-capita`
- `allocation_year` -> `first_allocation_year`
- `preserve_allocation_year_shares` -> `preserve_first_allocation_year_shares`

### Step 3: Category Loop

`run_all_allocations()` iterates over `final_categories = ("co2", "non-co2")`:

**Pass 1: `co2` (budget)**

- `is_budget_target("rcbs", "co2")` returns `True` (`config.py`)
- Uses `budget_allocs` dict
- Follows the same path as Worked Example 1

**Pass 2: `non-co2` (pathway)**

- `is_budget_target("rcbs", "non-co2")` returns `False`
- Uses auto-derived `pathway_allocs` dict
- Calls `_run_pathway_allocations()` (`notebook_helpers.py`)

### Step 4: Pathway Runner

`_run_pathway_allocations()` (`notebook_helpers.py`):

1. **Groups scenarios** by `climate-assessment` and `quantile`.
2. For each group, extracts the World totals timeseries.
3. Calls `run_parameter_grid()` with pathway approaches and the world
   scenario data.
4. For each result:
   - `PathwayAllocationResult.get_absolute_emissions(world_ts)` multiplies
     year-by-year shares by the global pathway.
   - Saves to parquet.

### Step 5: Pathway Math

Pathway allocations flow through `pathways/per_capita.py`
(`_per_capita_core()`). The key difference from budget math:

- Uses `first_allocation_year` instead of `allocation_year`.
- Produces **multi-year shares** (one column per year from
  `first_allocation_year` onward).
- If `preserve_first_allocation_year_shares=False`, each year's shares
  reflect that year's population (dynamic shares).
- Returns `PathwayAllocationResult` instead of `BudgetAllocationResult`.

### Step 6: Scenario Labels

AR6 categories (C1, C2, C3) are relabeled to RCB scenario labels
(`1.5p50`, `2p83`, `2p66`) during preprocessing in notebook 104.
This is a 1:1 mapping — each RCB scenario corresponds to exactly one
AR6 category. The relabeling happens once at data loading time, so
all downstream code (including non-CO2 pathways) uses the RCB labels
directly without runtime translation.

---

## Data Preprocessing Pipeline

The preprocessing pipeline transforms raw data sources into analysis-ready
CSVs. It runs via Snakemake, orchestrated by the Snakefile.

### Pipeline Architecture

```
conf/data_sources/data_sources_unified.yaml   (source of truth for config)
        |
        v
   Snakefile                                   (DAG orchestration)
        |
        +---> compose_config                   (Pydantic validation)
        |         |
        +---> preprocess_emiss (101_*.ipynb)   (per emission category)
        +---> preprocess_gdp   (102_*.ipynb)
        +---> preprocess_population (103_*.ipynb)
        +---> preprocess_gini  (105_*.ipynb)
        +---> preprocess_lulucf (107_*.ipynb)  (NGHGI LULUCF, bunkers, metadata)
        +---> preprocess_scenarios (104/106_*.ipynb)  (if pathway/rcb-pathways)
        |         |
        +---> [derive_non_co2]                 (if decomposition)
        |         |
        +---> master_preprocess (100_*.ipynb)  (combines all, produces final CSVs)
```

### Key Preprocessing Modules

| Module | Location | Purpose |
|--------|----------|---------|
| `DataPreprocessor` | `pipeline/preprocessing.py` | Common preprocessing: load, validate, filter to analysis countries, add ROW |
| `run_rcb_preprocessing()` | `pipeline/preprocessing.py` | RCB-specific: NGHGI corrections, RCB processing |
| `run_pathway_preprocessing()` | `pipeline/preprocessing.py` | Pathway-specific: scenario loading and processing |
| `run_composite_preprocessing()` | `pipeline/preprocessing.py` | Composite: 2-pass decomposition for all-GHG |
| `run_non_co2_preprocessing()` | `pipeline/preprocessing.py` | Derive non-CO2 by subtraction, then pathway-process |

### Output Directory Structure

```
output/<source_id>/
  config.yaml                          (validated configuration)
  notebooks/                           (executed preprocessing notebooks)
  intermediate/
    emissions/                         (per-category emission CSVs)
      world_co2-lulucf_timeseries.csv  (NGHGI world LULUCF for RCB corrections)
      bunker_timeseries.csv            (international bunker emissions)
      lulucf_metadata.yaml             (NGHGI start year, splice year)
    gdp/                               (GDP timeseries)
    population/                        (population timeseries)
    gini/                              (Gini coefficients)
    processed/                         (final analysis-ready CSVs)
      country_emissions_*.csv
      country_gdp_timeseries.csv
      country_population_timeseries.csv
      country_gini_stationary.csv
      rcbs_*.csv                       (budget mode only)
      world_emissions_*.csv            (budget mode only)
      world_scenarios_*_complete.csv   (pathway mode only)
  allocations/
    <folder_name>/
      *_relative.parquet               (dimensionless shares)
      *_absolute.parquet               (MtCO2/MtCO2eq)
      param_manifest.csv               (all parameter combinations)
      README_*.md                      (auto-generated docs)
```

---

## "Where Do I Change X?" Quick Reference

| I want to... | File(s) to edit | Key function/class |
|---------------|-----------------|-------------------|
| Add a new allocation approach | `allocations/budgets/*.py` or `allocations/pathways/*.py`, then `allocations/manager.py` | Write the math function, add to `get_allocation_functions()` dict in `manager.py` |
| Change how parameters are expanded | `allocations/manager.py` | `_expand_parameters()`, `run_parameter_grid()` |
| Add a new data source | `conf/data_sources/data_sources_unified.yaml`, new `notebooks/10x_*.py`, update `Snakefile` | Add YAML config, write preprocessing notebook, add Snakefile rule |
| Change validation rules | `src/.../validation/` | `validate_allocation_parameters()`, `validate_target_source_compatibility()` |
| Modify output parquet schema | `allocations/results/metadata.py` | `DATA_CONTEXT_COLUMNS`, `ALLOCATION_PARAMETER_COLUMNS` |
| Add a new emission category | `utils/data/config.py` | `get_final_categories()`, `get_emission_preprocessing_categories()` |
| Change how RCBs are processed | `preprocessing/rcbs.py`, `utils/data/rcb.py` | `load_and_process_rcbs()`, `calculate_budget_from_rcb()` |
| Add/modify NGHGI corrections | `utils/data/nghgi.py`, `config/models.py` (`AdjustmentsConfig`) | `build_nghgi_world_co2_timeseries()` |
| Change the notebook helpers | `notebook_helpers.py` | `load_allocation_data()`, `run_all_allocations()`, `run_and_save_category_allocations()` |
| Change Snakemake pipeline | `Snakefile`, `utils/data/setup.py` | Rules in Snakefile, `setup_data()` |
| Add a visualization | `visualization/` | `plot_allocation_comparison()`, `plot_decomposition_summary()` |
| Change how composite categories decompose | `utils/data/config.py`, `pipeline/preprocessing.py` | `needs_decomposition()`, `run_composite_preprocessing()` |
| Change result serialization | `allocations/results/serializers.py` | `save_allocation_result()` |
| Modify the budget-to-pathway derivation | `allocations/manager.py` | `_BUDGET_TO_PATHWAY` dict, `derive_pathway_allocations()` |

---

## Key Concepts

### Relative Shares vs Absolute Emissions

The system separates **allocation** (who gets what fraction) from
**quantification** (how large the pie is). Math functions return relative
shares (dimensionless, sum to 1.0). The helpers layer multiplies these by a
concrete global budget or pathway to produce absolute emissions.

This separation means the same equity-based allocation can be applied to
different RCB estimates or scenario pathways without re-running the math.

### Budget vs Pathway Approaches

**Budget approaches** (names ending in `-budget`) produce a single column of
shares for one allocation year. They answer: "What fraction of the remaining
cumulative budget does each country get?"

**Pathway approaches** produce a column per year. They answer: "What fraction
of each year's global emissions does each country get?"

The manager (`manager.py`) classifies approaches by checking whether the
name ends in `-budget`. This convention is load-bearing.

### The Parameter Grid

Users specify parameters as lists in the config:

```python
{"allocation_year": [2015, 2020], "capability_weight": [0.25, 0.5]}
```

`_expand_parameters()` (`manager.py`) uses `itertools.product` to create
all combinations (here: 4). `run_parameter_grid()` iterates over them and
calls `run_allocation()` for each.

### Composite Category Decomposition

When `emission_category="all-ghg"` and `target="rcbs"`, the system cannot
allocate all-GHG directly because RCBs only constrain CO2. The solution:

1. Decompose into CO2 (budget allocation via RCBs) + non-CO2 (pathway
   allocation via AR6 scenarios).
2. Derive non-CO2 data by subtraction: `all-ghg-ex-co2-lulucf - co2-ffi`.
3. Auto-derive pathway approach configs from budget configs (the user only
   specifies budget approaches).

The final outputs for each sub-category can be recombined downstream.

### Kebab-Case vs Snake-Case Convention

Config keys and approach names use kebab-case (`allocation-year`,
`equal-per-capita-budget`). Python identifiers use snake_case
(`allocation_year`, `equal_per_capita_budget`). The manager converts between
them:

```python
params = {k.replace("-", "_"): v for k, v in params.items()}
```

### Year Columns as Strings

All DataFrames use string year columns (`"2020"`, not `2020`). Call
`ensure_string_year_columns(df)` after loading any CSV. This convention
prevents pandas from treating years as integer indices, which causes subtle
alignment bugs.

### The Rest-of-World (ROW) Pattern

During preprocessing, the `DataPreprocessor` (`pipeline/preprocessing.py`)
filters datasets to countries with complete data across all sources, then
adds a "ROW" (Rest of World) row as the residual between the world total and
the sum of included countries. This ensures allocations always cover 100% of
global emissions.

---

## See Also

- [Developer Guide](index.md) -- Module overview and conventions
- [Adding Allocation Approaches](adding-approaches.md) -- Step-by-step guide for new approaches
- [Adding Data Sources](adding-data-sources.md) -- Step-by-step guide for new datasets
- [Scientific Documentation](../science/allocations.md) -- Theoretical foundations
- [API Reference](../api/index.md) -- Function-level documentation
