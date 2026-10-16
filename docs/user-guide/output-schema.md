---
title: Outputs
description: Files and columns of allocation results, remaining budgets, annual pathways and the Python API result
---

# Outputs

## Files

An allocation run writes to `output/<source-id>/allocations/<allocation_folder>/`:

| File | Holds |
| --- | --- |
| `allocations_relative.parquet` | Shares summing to 1, every column below |
| `allocations_absolute.parquet` | Share × global target in Mt CO₂e, every column below |
| `param_manifest.csv` | Every parameter combination of the run |
| `README_relative.txt`, `README_absolute.txt` | A short description of the folder |
| `CITATIONS.md` | The software and every data source the run used |
| `allocations_wide.csv` | Wide format for spreadsheets. The notebooks write it with `convert_parquet_to_wide_csv()` |

Notebook 601 adds two products to the same folder:

| File | Holds |
| --- | --- |
| `remaining_budgets_from_<year>.csv` | Each country's remaining budget after observed emissions ([Remaining budgets](#remaining-budgets)) |
| `distributed_remaining_pathways.parquet` and `.csv` | Each remaining budget spread into an annual pathway ([Annual pathways](#annual-pathways)) |

## Allocation columns

The parquet files hold every result with its metadata and parameters.

### Identifier Columns

| Column               | Type   | Description                                         |
| -------------------- | ------ | --------------------------------------------------- |
| `iso3c`              | string | Country code (e.g., 'USA', 'CHN')                   |
| `approach`           | string | Allocation method (e.g., 'equal-per-capita-budget') |
| `climate-assessment` | string | Normalised temperature target from the scenario source (e.g., '1.5C', '2C' for AR6) |
| `quantile`           | float  | Normalised probability percentile from the scenario source (e.g., 0.5 for AR6 C1 median) |
| `emission-category`  | string | Emission type (e.g., 'co2-ffi', 'all-ghg')          |

### Data Source Columns

| Column              | Type   | Description                       |
| ------------------- | ------ | --------------------------------- |
| `source-id`         | string | Composite data source identifier; includes the LULUCF source when the category uses one |
| `allocation-folder` | string | Output folder name of the run     |
| `emissions-source`  | string | Historical emissions dataset      |
| `gdp-source`        | string | GDP dataset                       |
| `population-source` | string | Population dataset                |
| `gini-source`       | string | Gini coefficient dataset          |
| `target-source`     | string | Target type ('rcbs', 'pathway', 'rcb-pathways') |
| `rcb-generator`     | string | Pathway generator for `rcb-pathways`; empty otherwise |
| `source`            | string | Specific source within the target (e.g., the RCB source 'lamboll_2023') |
| `total-budget`      | float  | Global budget total behind the allocation |

### Parameter Columns

Individual parameter columns for each allocation approach:

| Column                                  | Type   | Used By                   |
| --------------------------------------- | ------ | ------------------------- |
| `allocation-year`                       | int    | Budget approaches         |
| `first-allocation-year`                 | int    | Pathway approaches        |
| `preserve-allocation-year-shares`       | bool   | Budget approaches         |
| `preserve-first-allocation-year-shares` | bool   | Pathway approaches        |
| `cumulative-end-year`                   | int    | Budget approaches         |
| `pre-allocation-responsibility-weight`                 | float  | Adjusted approaches       |
| `capability-weight`                     | float  | Adjusted approaches       |
| `capability-reference-year`             | int    | Adjusted approaches       |
| `capability-window`                     | string | Per-capita adjusted approaches (`"start-end"`, e.g. `"1990-2019"`) |
| `pre-allocation-responsibility-year`        | int    | Adjusted approaches       |
| `pre-allocation-responsibility-per-capita` | bool   | Adjusted approaches       |
| `capability-per-capita`                 | bool   | Adjusted approaches       |
| `pre-allocation-responsibility-exponent` | float  | Adjusted approaches       |
| `capability-exponent`                   | float  | Adjusted approaches       |
| `pre-allocation-responsibility-functional-form` | string | Adjusted approaches       |
| `capability-functional-form`            | string | Adjusted approaches       |
| `max-deviation-sigma`                   | float  | All approaches (optional) |
| `income-floor`                          | float  | Gini-adjusted approaches  |
| `max-gini-adjustment`                   | float  | Gini-adjusted approaches  |
| `convergence-year`                      | int    | Convergence approaches    |
| `convergence-speed`                     | float  | Convergence approaches    |

### Year Columns

| Column Pattern | Type  | Description                               |
| -------------- | ----- | ----------------------------------------- |
| `"2020"` etc.  | float | Allocation values for each year (strings) |

**Note:** Year columns are stored as **strings**, not integers. Always use `"2020"`, not `2020`.

### Quality Columns

| Column                        | Type   | Description                    |
| ----------------------------- | ------ | ------------------------------ |
| `warnings`                    | string | Quality warnings (if any)      |
| `moved-to-row`                | string | Analysis countries placed in rest of world for this allocation only, `;`-separated ([Analysis countries](../science/other-operations.md#analysis-countries)) |
| `missing-net-negative-mtco2e` | float  | Missing net-negative emissions |

---

## Wide CSV

`allocations_wide.csv` holds relative and absolute values in one file for spreadsheets.
A `data-type` column says which: `relative` (shares) or `absolute` (Mt CO₂e).
The parameter columns collapse into `approach-short`, and the metadata into `variable`.
The columns run: data context, sources, `target-source`, `data-type`, `approach-short`, `variable`, `iso3c`, `unit`, quality columns, then years in order.

### approach-short

Format: `{approach-code}-{param1}{value1}-{param2}{value2}...`

| Parquet Columns                                                                        | CSV `approach-short` |
| -------------------------------------------------------------------------------------- | -------------------- |
| `approach="equal-per-capita"`, `first-allocation-year=2020`                            | `EPC-y2020`          |
| `approach="per-capita-adjusted"`, `pre-allocation-responsibility-weight=0.5`, `capability-weight=0.5` | `PC-Adj-rw0.5-cw0.5` |
| `approach="cumulative-per-capita-convergence"`, `convergence-speed=0.42`               | `CPCC-cs0.42`        |

Approach codes:

| Full Approach Name                                | Short Code      |
| ------------------------------------------------- | --------------- |
| `equal-per-capita`                                | `EPC`           |
| `per-capita-adjusted`                             | `PC-Adj`        |
| `per-capita-adjusted-gini`                        | `PC-Adj-Gini`   |
| `per-capita-convergence`                          | `PCC`           |
| `cumulative-per-capita-convergence`               | `CPCC`          |
| `cumulative-per-capita-convergence-adjusted`      | `CPCC-Adj`      |
| `cumulative-per-capita-convergence-gini-adjusted` | `CPCC-Adj-Gini` |
| `equal-per-capita-budget`                         | `EPC-B`         |
| `per-capita-adjusted-budget`                      | `PC-Adj-B`      |
| `per-capita-adjusted-gini-budget`                 | `PC-Adj-Gini-B` |

Parameter prefixes:

| Parameter                               | Prefix |
| --------------------------------------- | ------ |
| `first-allocation-year`                 | `y`    |
| `allocation-year`                       | `ay`   |
| `preserve-first-allocation-year-shares` | `pfa`  |
| `preserve-allocation-year-shares`       | `pa`   |
| `convergence-year`                      | `c`    |
| `convergence-speed`                     | `cs`   |
| `pre-allocation-responsibility-weight`                 | `rw`   |
| `capability-weight`                     | `cw`   |
| `pre-allocation-responsibility-year`        | `hr`   |
| `pre-allocation-responsibility-per-capita` | `rpc`  |
| `capability-per-capita`                 | `cpc`  |
| `pre-allocation-responsibility-exponent` | `re`   |
| `capability-exponent`                   | `ce`   |
| `pre-allocation-responsibility-functional-form` | `rff`  |
| `capability-functional-form`            | `cff`  |
| `capability-reference-year`             | `cref` |
| `capability-window`                     | `cwin` |
| `max-deviation-sigma`                   | `s`    |
| `income-floor`                          | `if`   |
| `max-gini-adjustment`                   | `ga`   |

### variable

Format: `{emission-category}|{target-source}|{source}|{climate-assessment}|{quantile}|{approach-short}`, for example `co2-ffi|rcbs|lamboll_2023|1.5C|0.5|EPC-B-ay2020`.

`convert_parquet_to_wide_csv()` takes `config_prefixes` and `approach_names` to change the codes, for example `{"capability-weight": "cap"}` or `{"equal-per-capita": "Equal"}`.

## Remaining budgets

`remaining_budgets_from_<year>.csv` has one row per country and configuration.
It keeps the identifier and parameter columns above and adds:

| Column | Meaning |
| --- | --- |
| `category` | The emission category of the run, for example `all-ghg` |
| `emission-category` | The part of that category: the CO₂ part, `non-co2`, or `combined` for their sum |
| `netting-end-year` | The last observed year that every part of the category covers |
| `remaining-from-year` | `netting-end-year` + 1 |
| `allocated-total` | The allocation from the allocation year |
| `consumed-actuals` | Observed emissions from the allocation year to `netting-end-year` |
| `remaining-budget` | `allocated-total` minus `consumed-actuals`. For a non-CO₂ pathway part: its allocation after `netting-end-year` |
| `historical-deviation` | Non-CO₂ parts only: observed minus allocated emissions up to `netting-end-year` |

A remaining budget can be negative.
[`compute_remaining_budgets`](../api/python-api.md#compute_remaining_budgets) computes this table.

## Annual pathways

`distributed_remaining_pathways` has one row per country, configuration and distribution setting, with one column per year to the pathway end year.
Each country's pathway sums to its remaining budget. It adds:

| Column | Meaning |
| --- | --- |
| `adjusted-target` | The total the pathway sums to: the remaining budget, less any non-CO₂ debt in `co2-debit` mode |
| `shape`, `deviation-end-year`, `convergence-year` | The distribution setting |
| `nonco2-debt-mode` | Composite categories only: `report-only` or `co2-debit` |
| `nonco2-debt-paid` | Composite categories only: the non-CO₂ over-use subtracted from the CO₂ budget |

[`distribute_remaining_pathways`](../api/python-api.md#distribute_remaining_pathways) computes this table. [Greenhouse gases](../science/greenhouse-gases.md) explains the two debt modes.

## Python API result

[`calculate_allocation_timeseries`](../api/python-api.md#calculate_allocation_timeseries) returns a `ResultContainer`:

| Attribute | Holds |
| --- | --- |
| `allocation_timeseries` | The annual pathways. The MultiIndex holds every identifying column above; the columns are years |
| `history` | Observed emissions, indexed by `coverage`, `unit` and `iso3c`, including the `combined` basket |
| `netting_end_year`, `pathway_end_year`, `harmonisation_year` | The years of the run |
| `emission_category`, `rcb_source`, `climate_assessment`, `quantile` | The budget anchor |
| `source_id` and the five `*_source` attributes | The data sources |
| `shape`, `deviation_end_year`, `convergence_year`, `nonco2_debt_mode`, `base_share_floor_mt` | The distribution setting |
| `unit`, `allocation_folder`, `metadata` | Unit, label and any approach-specific extras |

[`save_results`](../api/python-api.md#save_results) writes `allocation_timeseries.parquet`, `history.parquet`, `metadata.json` with every scalar attribute, and `CITATIONS.md`.

## Reading the files

```python
import pandas as pd

df = pd.read_parquet("allocations_relative.parquet")
epc = df[df["approach"] == "equal-per-capita"]
high_responsibility = df[df["pre-allocation-responsibility-weight"] >= 0.5]
```

In R, `arrow::read_parquet()` reads the same files.
