---
title: Output Schema
description: Detailed reference for allocation output file formats and column structures
---

# Output Schema

This page documents the structure of allocation outputs and how parquet files are transformed to CSV format.

---

## Output Files

All allocation runs produce four output files:

| File                           | Format  | Description                                     |
| ------------------------------ | ------- | ----------------------------------------------- |
| `allocations_relative.parquet` | Parquet | Country fractions summing to 1.0 (all columns)  |
| `allocations_absolute.parquet` | Parquet | Shares × global target in Mt CO2e (all columns) |
| `allocations_wide.csv`         | CSV     | Simplified wide format for spreadsheet use      |
| `param_manifest.csv`           | CSV     | Parameter combinations used in the run          |

---

## Parquet Format (Full Detail)

The parquet files contain the **complete** allocation results with all metadata and parameter columns.

### Identifier Columns

| Column               | Type   | Description                                         |
| -------------------- | ------ | --------------------------------------------------- |
| `iso3c`              | string | Country code (e.g., 'USA', 'CHN')                   |
| `approach`           | string | Allocation method (e.g., 'equal-per-capita-budget') |
| `climate-assessment` | string | Climate scenario (e.g., '1.5C', '2C')               |
| `quantile`           | string | Probability percentile (e.g., '0.5' for median)     |
| `emission-category`  | string | Emission type (e.g., 'co2-ffi', 'all-ghg')          |

### Data Source Columns

| Column              | Type   | Description                       |
| ------------------- | ------ | --------------------------------- |
| `source-id`         | string | Composite data source identifier  |
| `emissions-source`  | string | Historical emissions dataset      |
| `gdp-source`        | string | GDP dataset                       |
| `population-source` | string | Population dataset                |
| `gini-source`       | string | Gini coefficient dataset          |
| `target-source`     | string | Target type ('rcbs', 'ar6', etc.) |

### Parameter Columns

Individual parameter columns for each allocation approach:

| Column                                  | Type  | Used By                  |
| --------------------------------------- | ----- | ------------------------ |
| `allocation-year`                       | int   | Budget approaches        |
| `first-allocation-year`                 | int   | Pathway approaches       |
| `preserve-allocation-year-shares`       | bool  | Budget approaches        |
| `preserve-first-allocation-year-shares` | bool  | Pathway approaches       |
| `responsibility-weight`                 | float | Adjusted approaches      |
| `capability-weight`                     | float | Adjusted approaches      |
| `historical-responsibility-year`        | int   | Adjusted approaches      |
| `responsibility-per-capita`             | bool  | Adjusted approaches      |
| `capability-per-capita`                 | bool  | Adjusted approaches      |
| `responsibility-exponent`               | float | Adjusted approaches      |
| `capability-exponent`                   | float | Adjusted approaches      |
| `income-floor`                          | float | Gini-adjusted approaches |
| `max-gini-adjustment`                   | float | Gini-adjusted approaches |
| `convergence-year`                      | int   | Convergence approaches   |
| `convergence-speed`                     | float | Convergence approaches   |
| `max-convergence-speed`                 | float | Convergence approaches   |
| `strict`                                | bool  | Convergence approaches   |

### Year Columns

| Column Pattern | Type  | Description                               |
| -------------- | ----- | ----------------------------------------- |
| `"2020"` etc.  | float | Allocation values for each year (strings) |

**Note:** Year columns are stored as **strings**, not integers. Always use `"2020"`, not `2020`.

### Quality Columns

| Column                        | Type   | Description                    |
| ----------------------------- | ------ | ------------------------------ |
| `warnings`                    | string | Quality warnings (if any)      |
| `missing-net-negative-mtco2e` | float  | Missing net-negative emissions |

---

## CSV Format (Simplified)

The `allocations_wide.csv` file **simplifies** the parquet structure for spreadsheet use by:

1. **Combining relative and absolute** into one file with a `data-type` column
2. **Collapsing parameter columns** into `approach-short`
3. **Collapsing metadata columns** into `variable`
4. **Excluding redundant columns**
5. **Converting to kebab-case** for consistency

### Column Transformation

#### 1. Data Type Column (Added)

| Column      | Type   | Values                 |
| ----------- | ------ | ---------------------- |
| `data-type` | string | 'relative', 'absolute' |

Indicates whether values are fractions (relative) or Mt CO2e (absolute).

#### 2. Approach Short (Collapsed)

The `approach-short` column **collapses all parameter columns** into a compact code:

**Format:** `{approach-code}-{param1}{value1}-{param2}{value2}...`

**Example transformations:**

| Parquet Columns                                                                        | CSV `approach-short` |
| -------------------------------------------------------------------------------------- | -------------------- |
| `approach="equal-per-capita"`, `first-allocation-year=2020`                            | `EPC-y2020`          |
| `approach="per-capita-adjusted"`, `responsibility-weight=0.5`, `capability-weight=0.5` | `PC-Adj-rw0.5-cw0.5` |
| `approach="cumulative-per-capita-convergence"`, `strict=False`                         | `CPCC-strictFalse`   |

**Approach codes:**

| Full Approach Name                           | Short Code      |
| -------------------------------------------- | --------------- |
| `equal-per-capita`                           | `EPC`           |
| `per-capita-adjusted`                        | `PC-Adj`        |
| `per-capita-adjusted-gini`                   | `PC-Adj-Gini`   |
| `per-capita-convergence`                     | `PCC`           |
| `cumulative-per-capita-convergence`          | `CPCC`          |
| `cumulative-per-capita-convergence-adjusted` | `CPCC-Adj`      |
| `equal-per-capita-budget`                    | `EPC-B`         |
| `per-capita-adjusted-budget`                 | `PC-Adj-B`      |
| `per-capita-adjusted-gini-budget`            | `PC-Adj-Gini-B` |

**Parameter prefixes:**

| Parameter                               | Prefix   |
| --------------------------------------- | -------- |
| `first-allocation-year`                 | `y`      |
| `allocation-year`                       | `ay`     |
| `preserve-first-allocation-year-shares` | `pfa`    |
| `preserve-allocation-year-shares`       | `pa`     |
| `convergence-year`                      | `c`      |
| `convergence-speed`                     | `cs`     |
| `responsibility-weight`                 | `rw`     |
| `capability-weight`                     | `cw`     |
| `historical-responsibility-year`        | `hr`     |
| `income-floor`                          | `if`     |
| `max-gini-adjustment`                   | `ga`     |
| `strict`                                | `strict` |

#### 3. Variable Column (Collapsed)

The `variable` column **encodes key metadata** in pipe-delimited format:

**Format:** `{emission-category}|{target-source}|{source}|{climate-assessment}|{quantile}|{approach-short}`

**Example:**

```
co2-ffi|rcbs|primap-hist-v2.5|1.5C|0.5|EPC-y2020
```

This enables filtering and pivoting in spreadsheet software.

#### 4. CSV Column Order

The CSV uses this column order:

1. **Data Context**: `source-id`, `allocation-folder`
2. **Source Data**: `emissions-source`, `gdp-source`, `population-source`, `gini-source`
3. **Target**: `target-source`
4. **Approach**: `data-type`, `approach-short`, `variable`
5. **Identity**: `iso3c`, `unit`
6. **Quality**: `warnings`, `missing-net-negative-mtco2e`
7. **Years**: `2020`, `2021`, ..., `2100` (in chronological order)

#### 5. Excluded Columns

These columns from parquet are **excluded** from CSV:

**Parameter columns** (collapsed into `approach-short`):

- All individual parameter columns listed in Parquet Format section

**Metadata columns** (collapsed into `variable` or redundant):

- `approach` (encoded in `approach-short`)
- `emission-category` (encoded in `variable`)
- `climate-assessment` (encoded in `variable`)
- `quantile` (encoded in `variable`)
- `source` (encoded in `variable`)

---

## Customizing CSV Output

The CSV transformation can be customized when calling `convert_parquet_to_wide_csv()`:

### Custom Parameter Prefixes

```python
from fair_shares.library.utils.data.parquet_to_csv import convert_parquet_to_wide_csv

# Use custom prefixes for specific parameters
custom_prefixes = {
    "responsibility-weight": "resp",
    "capability-weight": "cap",
}

convert_parquet_to_wide_csv(
    allocations_dir="output/example/allocations/run-001/",
    config_prefixes=custom_prefixes
)
```

Result: `PC-Adj-resp0.5-cap0.5` instead of `PC-Adj-rw0.5-cw0.5`

### Custom Approach Names

```python
# Use custom short codes for approaches
custom_names = {
    "equal-per-capita": "Equal",
    "per-capita-adjusted": "Adjusted",
}

convert_parquet_to_wide_csv(
    allocations_dir="output/example/allocations/run-001/",
    approach_names=custom_names
)
```

Result: `Equal-y2020` instead of `EPC-y2020`

---

## Working with Outputs

### In Python (Parquet)

```python
import pandas as pd

# Load full detail
df_relative = pd.read_parquet("allocations_relative.parquet")
df_absolute = pd.read_parquet("allocations_absolute.parquet")

# Filter by approach
epc = df_relative[df_relative["approach"] == "equal-per-capita"]

# Filter by parameter value
high_responsibility = df_relative[df_relative["responsibility-weight"] >= 0.5]
```

### In Python (CSV)

```python
import pandas as pd

# Load simplified format
df = pd.read_csv("allocations_wide.csv")

# Separate relative and absolute
relative = df[df["data-type"] == "relative"]
absolute = df[df["data-type"] == "absolute"]

# Filter by approach-short
epc = df[df["approach-short"].str.startswith("EPC")]
```

### In R (Parquet)

```r
library(arrow)

# Load full detail
df_relative <- read_parquet("allocations_relative.parquet")
df_absolute <- read_parquet("allocations_absolute.parquet")

# Filter by approach
epc <- df_relative %>%
  filter(approach == "equal-per-capita")
```

### In Excel (CSV)

1. Open `allocations_wide.csv` directly
2. Filter by `data-type` column to see relative or absolute
3. Filter by `approach-short` to compare approaches
4. Use pivot tables with `variable` column for cross-cutting analysis

---

## See Also

- **[User Guide](https://setupelz.github.io/fair-shares/user-guide/)** - Workflows for running allocations
- **[API Reference](https://setupelz.github.io/fair-shares/api/)** - Function documentation
- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** - Approach descriptions and parameters
