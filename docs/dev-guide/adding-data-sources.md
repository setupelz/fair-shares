---
title: Adding Data Sources
description: Step-by-step guide for integrating new data sources into the fair-shares pipeline
icon: material/database-plus
---

# Adding Data Sources

This guide explains how to add new data sources to fair-shares.

---

## Overview

Data sources are configured in `conf/data_sources/data_sources_unified.yaml` and processed through preprocessing notebooks in the `notebooks/1xx_*.py` series.

### Data Types

| Type         | Purpose                   | Current Sources     |
| ------------ | ------------------------- | ------------------- |
| `emissions`  | Historical emissions      | PRIMAP-hist         |
| `gdp`        | Economic capability       | World Bank WDI, IMF |
| `population` | Per capita calculations   | UN/OWID             |
| `gini`       | Within-country inequality | UNU-WIDER, WID      |
| `targets`    | Global constraints        | AR6 scenarios, RCBs |

---

## Step 1: Add Raw Data

Place your data files in the appropriate subdirectory:

```
data/
├── emissions/
│   └── my-source-YYYY/
│       └── raw_data_file.csv
├── gdp/
│   └── my-source-YYYY/
├── population/
├── gini/
├── scenarios/
└── rcbs/
```

Use the naming convention `{source}-{year}/` for versioning.

---

## Step 2: Configure the Source

Add an entry to `conf/data_sources/data_sources_unified.yaml`:

```yaml
# Example: Adding a new emissions source
emissions:
  primap-202503:
    # ... existing source ...

  my-source-2026: # New source
    path: "data/emissions/my-source-2026/emissions_data.csv"
    data_parameters:
      available_categories:
        - co2-ffi
        - all-ghg
      world_key: "WORLD" # How the source identifies global totals
```

### Common Configuration Parameters

| Parameter              | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `path`                 | Relative path to data file                        |
| `available_categories` | Which emission categories this source provides    |
| `world_key`            | String used to identify global totals in the data |

---

## Step 3: Create Preprocessing Notebook

Create a preprocessing notebook in the `1xx` series:

```
notebooks/
├── 100_preprocess_emissions_primap.py       # Existing
├── 101_preprocess_gdp_wdi.py               # Existing
├── 102_preprocess_population_un_owid.py    # Existing
├── 105_preprocess_my_source.py             # New notebook
```

### Preprocessing Pattern

```python
"""
Preprocess my-source-2026 data.

Input: Raw data file
Output: Standardized DataFrame with proper index structure
"""

import pandas as pd
from pyprojroot import here

# Load raw data
raw_path = here() / "data/emissions/my-source-2026/emissions_data.csv"
df = pd.read_csv(raw_path)

# Standardize country codes to ISO3c
df["iso3c"] = convert_to_iso3c(df["country_column"])

# Set standard index
df = df.set_index(["iso3c", "unit", "emission-category"])

# Ensure year columns are strings
from fair_shares.library.utils import ensure_string_year_columns
df = ensure_string_year_columns(df)

# Add World row if missing
if "World" not in df.index.get_level_values("iso3c"):
    world_row = df.groupby(["unit", "emission-category"]).sum()
    world_row["iso3c"] = "World"
    df = pd.concat([df, world_row.set_index("iso3c", append=True)])

# Save processed data
output_path = here() / "data/processed/my-source-2026/emissions.csv"
output_path.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_path)
```

---

## Step 4: Index Structure Requirements

All data must follow standardized MultiIndex structures:

### Emissions

```python
# Index: iso3c, unit, emission-category
# Columns: year columns as strings ("1990", "2000", ...)
df.index.names == ["iso3c", "unit", "emission-category"]
```

### GDP / Population

```python
# Index: iso3c, unit
# Columns: year columns as strings
df.index.names == ["iso3c", "unit"]
```

### Gini (Stationary)

```python
# Index: iso3c, unit
# Columns: "gini" (single value, not time-varying)
df.index.names == ["iso3c", "unit"]
df.columns == ["gini"]
```

---

## Step 5: Integrate with Pipeline

The Snakemake workflow automatically picks up sources from the configuration. Ensure your preprocessing notebook:

1. Reads from the path specified in the config
2. Outputs to the standard processed data location
3. Uses consistent index structures

---

## Step 6: Test

1. **Run preprocessing notebook** - Verify it completes without errors
2. **Run allocation with new source** - Use in 301 notebook
3. **Check results** - Verify country coverage and data ranges

```python
# In 301 notebook:
active_sources = {
    "target": "rcbs",
    "emissions": "my-source-2026",  # Use new source
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
}
```

---

## Validation Requirements

New data sources should:

1. **Cover expected countries** - At minimum, major emitters
2. **Include World total** - Required for validation
3. **Use standard units** - Mt CO2e for emissions, persons for population
4. **Handle missing values** - Document any gaps

---

## Existing Notebooks as Examples

| Notebook                               | Data Type  | Good Example Of                         |
| -------------------------------------- | ---------- | --------------------------------------- |
| `100_preprocess_emissions_primap.py`   | Emissions  | NetCDF processing, category mapping     |
| `101_preprocess_gdp_wdi.py`            | GDP        | CSV processing, country code mapping    |
| `102_preprocess_population_un_owid.py` | Population | Combining historical and projected data |

---

## See Also

- **Data Sources Config**: `conf/data_sources/data_sources_unified.yaml` in the repository
- **[Validation Utilities](https://setupelz.github.io/fair-shares/api/utils/validation/)** - Data validation functions
