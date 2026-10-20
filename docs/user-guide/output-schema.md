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
| `columns.csv` | Meaning and unit of every column of the parquet files |
| `README_relative.txt`, `README_absolute.txt` | A short description of the folder |
| `CITATIONS.md` | The software and every data source the run used |
| `allocations_wide.csv` | Wide format for spreadsheets. The notebooks write it with `convert_parquet_to_wide_csv()` |

Notebook 601 adds two products to the same folder:

| File | Holds |
| --- | --- |
| `remaining_budgets_from_<year>.csv` | Each country's remaining budget after observed emissions ([Remaining budgets](#remaining-budgets)) |
| `distributed_remaining_pathways.parquet` and `.csv` | Each remaining budget spread into an annual pathway ([Annual pathways](#annual-pathways)) |

## Allocation columns

The parquet files hold every result with its identifiers, data sources, parameters, year columns and quality flags.
[Output columns](output-columns.md) gives the meaning and unit of every column, and each output folder holds `columns.csv` with the entries of its own columns.

**Note:** Year columns are stored as **strings**, not integers. Always use `"2020"`, not `2020`.

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
It keeps the identifier and parameter columns above and adds the [remaining-budget columns](output-columns.md#remaining-budgets).

A remaining budget can be negative.
[`compute_remaining_budgets`](../api/python-api.md#compute_remaining_budgets) computes this table.

## Annual pathways

`distributed_remaining_pathways` has one row per country, configuration and distribution setting, with one column per year to the pathway end year.
Each country's pathway sums to its remaining budget. It adds the [annual-pathway columns](output-columns.md#annual-pathways).

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
