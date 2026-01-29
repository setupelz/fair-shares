---
title: Country-Level Fair Shares
description: Guide to calculating fair share allocations for individual countries
---

# country-fair-shares

The `301_custom_fair_share_allocation.ipynb` notebook calculates fair share allocations for individual countries.

---

## Workflow

```mermaid
graph LR
    A[1. Data Sources] --> B[2. Approaches]
    B --> C[3. Pipeline]
    C --> D[4. Allocations]
    D --> E[5. Results]
```

| Step             | Action                                     |
| ---------------- | ------------------------------------------ |
| **Data Sources** | Select emissions, population, GDP datasets |
| **Approaches**   | Configure allocation approach parameters   |
| **Pipeline**     | Run data preprocessing (automated)         |
| **Allocations**  | Calculate country shares                   |
| **Results**      | Export to Parquet/CSV                      |

---

## Step 1: Data Sources

### Emission Category

| Category                | Description                           |
| ----------------------- | ------------------------------------- |
| `co2-ffi` **(default)** | CO2 from fossil fuels and industry    |
| `all-ghg-ex-co2-lulucf` | All GHGs excluding CO2 from land use  |
| `all-ghg`               | All greenhouse gases including LULUCF |

### Target Source

| Source         | Description                                         |
| -------------- | --------------------------------------------------- |
| `rcbs`         | Remaining Carbon Budgets - single cumulative values |
| `ar6`          | IPCC AR6 scenarios - time-series pathways           |
| `rcb-pathways` | Remaining Carbon Budgets - time-series pathways     |

### Supporting Data

| Data Type    | Purpose                                              |
| ------------ | ---------------------------------------------------- |
| `emissions`  | Historical emissions for responsibility calculations |
| `population` | Per capita calculations                              |
| `gdp`        | Capability-based adjustments                         |
| `gini`       | Within-country inequality adjustments                |

Available sources are configured in `conf/data_sources/`.

---

## Step 2: Allocation Approaches

<!-- REFERENCE: Approach implementations in src/fair_shares/library/allocations/
     Budget approaches: budgets/per_capita.py
     Pathway approaches: pathways/per_capita.py, pathways/cumulative_per_capita_convergence.py
     Mathematical details and design rationale: docs/science/allocations.md
-->

### Budget Approaches (for `target="rcbs"`)

| Approach                          | Description                                    |
| --------------------------------- | ---------------------------------------------- |
| `equal-per-capita-budget`         | Equal share per person                         |
| `per-capita-adjusted-budget`      | Adjusted for responsibility and capability     |
| `per-capita-adjusted-gini-budget` | Further adjusted for within-country inequality |

### Pathway Approaches (for `target="ar6"`)

| Approach                            | Description                                                               |
| ----------------------------------- | ------------------------------------------------------------------------- |
| `equal-per-capita`                  | Equal share per person per year                                           |
| `per-capita-adjusted`               | Adjusted for responsibility and capability                                |
| `cumulative-per-capita-convergence` | Budget-preserving transition from current emissions to cumulative targets |

For detailed explanations, see [Allocation Approaches]({DOCS_ROOT}/science/allocations/).

---

## Step 3: Data Pipeline

The pipeline runs automatically when you execute the Step 3 cell. It:

1. Validates your configuration
2. Loads raw data files
3. Processes emissions, GDP, population data
4. Prepares target scenarios or budgets
5. Saves processed files for allocation

Processing typically takes 1-3 minutes depending on data sources.

---

## Step 4: Run Allocations

The allocation step:

1. Loads processed data from the pipeline
2. Runs each approach with all parameter combinations
3. Calculates relative shares (summing to 1)
4. Computes absolute emissions (Mt CO2e)
5. Saves results to parquet and CSV

---

## Step 5: Explore Results

### Output Files

Results are saved to `output/{source_id}/allocations/{allocation_folder}/`:

| File                           | Format  | Description                  |
| ------------------------------ | ------- | ---------------------------- |
| `allocations_relative.parquet` | Parquet | Relative shares (0-1)        |
| `allocations_absolute.parquet` | Parquet | Absolute emissions (Mt CO2e) |
| `allocations_wide.csv`         | CSV     | Wide format for spreadsheets |
| `parameter_manifest.csv`       | CSV     | All parameter combinations   |

### Output Types

- **Relative shares**: Country fractions summing to 1.0 per year
- **Absolute emissions**: Relative share × global target in physical units

---

## Comparing Approaches

To compare multiple allocation approaches:

```python
allocations = {
    "equal-per-capita-budget": [
        {"allocation_year": [2020], "preserve_allocation_year_shares": [False]}
    ],
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [2020],
            "preserve_allocation_year_shares": [False],
            "responsibility_weight": [0.5],
            "capability_weight": [0.5],
        }
    ],
}
```

Both approaches run in a single pipeline execution. Results include an `approach` column for filtering.

---

## Reference Notebooks

| Notebook                                       | Purpose                     |
| ---------------------------------------------- | --------------------------- |
| `302_example_templates_budget_allocations.py`  | Budget allocation examples  |
| `303_example_templates_pathway_allocations.py` | Pathway allocation examples |

---

## See Also

- **[Allocation Approaches]({DOCS_ROOT}/science/allocations/)** - Theoretical foundations
- **[API Reference]({DOCS_ROOT}/api/allocations/budgets/)** - Function signatures
- **[Other Operations]({DOCS_ROOT}/science/other-operations/)** - RCB pathway generation, net-negative handling
