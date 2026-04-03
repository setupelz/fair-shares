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

| Type         | Purpose                              | Current Sources        |
| ------------ | ------------------------------------ | ---------------------- |
| `emissions`  | Historical non-LULUCF emissions      | PRIMAP-hist            |
| `gdp`        | Economic capability                  | World Bank WDI, IMF    |
| `population` | Per capita calculations              | UN/OWID                |
| `gini`       | Within-country inequality            | UNU-WIDER, WID         |
| `lulucf`     | NGHGI-consistent LULUCF emissions    | Melo et al. (2026)     |
| `targets`    | Global constraints                   | AR6 scenarios, RCBs    |

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
├── lulucf/
│   └── my-source-YYYY/
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
      scenario: "HISTCR" # Historical scenario identifier
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
├── 101_data_preprocess_emiss_primap-202503.py       # Existing
├── 102_data_preprocess_gdp_wdi-2025.py              # Existing
├── 103_data_preprocess_population_un-owid-2025.py   # Existing
├── 1xx_data_preprocess_my_source.py                 # New notebook
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
    "lulucf": "melo-2026",
}
```

---

## LULUCF Data Sources

LULUCF data provides NGHGI-consistent land-use CO2 emissions that replace
the bookkeeping model (BM) estimates in PRIMAP. This is required for total
CO2 (`co2`) and all-GHG (`all-ghg`) categories — see
[NGHGI Corrections](../science/other-operations.md) for the science.

### What LULUCF preprocessing produces

Notebook 107 reads the raw LULUCF source and outputs:

- `emiss_co2-lulucf_timeseries.csv` — country-level NGHGI LULUCF emissions
  (overwrites the PRIMAP BM version from notebook 101)
- `world_co2-lulucf_timeseries.csv` — world-total LULUCF for RCB corrections
- `bunker_timeseries.csv` — international bunker fuel emissions
- `lulucf_metadata.yaml` — NGHGI start year (enforces allocation year ≥ 2000
  for `co2` category)

### Adding a new LULUCF source

1. Place data in `data/lulucf/{source-name}/`
2. Add config entry under `lulucf:` in `data_sources_unified.yaml` with
   `data_parameters` including `format`, `iso3_column`, `year_column`,
   `value_column`, `category_filter`, `gas_filter`, and `exclude_regions`
3. Create `107_data_preprocess_lulucf_{source-name}.py` following the pattern
   of `107_data_preprocess_lulucf_melo-2026.py`
4. The Snakefile will pick it up via `active_lulucf_source`

### Which categories use LULUCF?

| Emission category | Uses LULUCF? | Why |
|-------------------|-------------|-----|
| `co2-ffi` | No | Fossil fuels only |
| `co2` | **Yes** | Total CO2 = fossil − bunkers + NGHGI LULUCF |
| `all-ghg` | **Yes** | Decomposes into `co2` (NGHGI) + `non-co2` |
| `all-ghg-ex-co2-lulucf` | No | CO2 component is `co2-ffi` |
| `co2-lulucf` | Indirect | IS the LULUCF data |
| `non-co2` | No | Derived by subtraction |

---

## Scenario Data and NGHGI Consistency

When adding or updating scenario data (AR6 or custom), ensure the scenarios
use NGHGI-consistent emissions conventions. The pipeline applies NGHGI
corrections to remaining carbon budgets (RCBs) to account for the gap
between bookkeeping model and NGHGI LULUCF estimates, but scenario pathways
must already be internally consistent.

**For AR6 scenarios:** The Gidden et al. reanalysis provides scenarios that
are consistent with PRIMAP historical emissions. NGHGI corrections are
applied at the RCB level (adjusting the budget), not at the scenario pathway
level.

**For custom scenarios:** If your scenario data uses a different emissions
convention than PRIMAP/NGHGI, apply the necessary corrections in the
preprocessing notebook (`104_data_preprocess_scenarios.py`) before
the data enters the pipeline. Do not rely on downstream corrections — the
allocation functions assume scenario data is already convention-consistent.

---

## Normative Implications

Some data source choices carry normative weight. Contributors should document the rationale for their data source choices. For example, some decision points include:

- **GDP:** PPP vs. MER measurement can significantly affect allocation results — PPP tends to raise developing-country capacity shares [Pelz 2025b].
- **Emissions:** Production vs. consumption accounting embeds different theories of responsibility. Production accounting (territorial) excludes embedded imports; consumption accounting includes them.
- **Population:** Projection method choices (UN median, SSP scenarios) affect per capita allocations, particularly for countries with high projected growth.

---

## Validation Requirements

New data sources should:

1. **Cover expected countries** - At minimum, major emitters
2. **Include World total** - Required for validation
3. **Use standard units** - Mt CO2e for emissions, persons for population
4. **Handle missing values** - Document any gaps

---

## Existing Notebooks as Examples

| Notebook                                         | Data Type  | Good Example Of                                    |
| ------------------------------------------------ | ---------- | -------------------------------------------------- |
| `101_data_preprocess_emiss_primap-202503.py`     | Emissions  | NetCDF processing, category mapping                |
| `102_data_preprocess_gdp_wdi-2025.py`            | GDP        | CSV processing, country code mapping               |
| `103_data_preprocess_population_un-owid-2025.py` | Population | Combining historical and projected data            |
| `105_data_preprocess_gini_unu-wider-2025.py`     | Gini       | Quality filtering, stationary output               |
| `105_data_preprocess_gini_wid-2025.py`           | Gini       | WID.world processing, stationary output            |
| `107_data_preprocess_lulucf_melo-2026.py`        | LULUCF     | NGHGI corrections, metadata export, world totals   |

---

## See Also

- **Data Sources Config**: `conf/data_sources/data_sources_unified.yaml` in the repository
- **[Validation Utilities](https://setupelz.github.io/fair-shares/api/utils/validation/)** - Data validation functions
