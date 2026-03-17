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

| Category                | Description                           | Notes                                 |
| ----------------------- | ------------------------------------- | ------------------------------------- |
| `co2-ffi` **(default)** | CO₂ from fossil fuels and industry    |                                       |
| `all-ghg-ex-co2-lulucf` | All GHGs excluding CO₂ from land use  | Avoids LULUCF measurement uncertainty |
| `all-ghg`               | All greenhouse gases including LULUCF | Uses GWP100 AR6 values                |

### Target Source

| Source         | Allocation Functions | Description                                                             |
| -------------- | -------------------- | ----------------------------------------------------------------------- |
| `rcbs`         | Budget approaches    | Remaining Carbon Budgets -- single cumulative value per country         |
| `pathway`      | Pathway approaches   | IPCC AR6 scenarios -- allocate existing scenario pathways               |
| `rcb-pathways` | Pathway approaches   | RCB to global pathway, then allocated annually using pathway approaches |

### Supporting Data

| Data Type    | Purpose                                              |
| ------------ | ---------------------------------------------------- |
| `emissions`  | Historical emissions for responsibility calculations |
| `population` | Per capita calculations                              |
| `gdp`        | Capability-based adjustments                         |
| `gini`       | Within-country inequality adjustments                |

Available sources are configured in `conf/data_sources/`.

---

!!! note "Entry Points Framework"
Before configuring approaches and parameters, it helps to work through the five entry points for fair share quantification [Pelz 2025b]: (1) foundational principles, (2) allocation quantity, (3) allocation approach, (4) indicators, (5) implications for all others. The steps below map directly onto these decision stages. See [Climate Equity Concepts](../science/climate-equity-concepts.md) for details.

## Step 2: Allocation Approaches

<!-- REFERENCE: Approach implementations in src/fair_shares/library/allocations/
     Budget approaches: budgets/per_capita.py
     Pathway approaches: pathways/per_capita.py, pathways/cumulative_per_capita_convergence.py
     Mathematical details and design rationale: docs/science/allocations.md
-->

### Budget Approaches (for `target="rcbs"`)

These implement Equal Cumulative Per Capita (ECPC) allocation when `allocation_year` is set to a historical start year (e.g., 1990). The choice of start year is normatively significant — 1990 corresponds to the IPCC First Assessment Report and the "excusable ignorance" threshold in the equity literature [Baer 2013; Pelz 2025b].

| Approach                          | Description                                    |
| --------------------------------- | ---------------------------------------------- |
| `equal-per-capita-budget`         | Equal share per person                         |
| `per-capita-adjusted-budget`      | Adjusted for responsibility and capability     |
| `per-capita-adjusted-gini-budget` | Further adjusted for within-country inequality |

### Pathway Approaches (for `target="pathway"` or `target="rcb-pathways"`)

| Approach                                          | Description                                                                                                                                                                         |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `equal-per-capita`                                | Equal share per person per year                                                                                                                                                     |
| `per-capita-adjusted`                             | Adjusted for responsibility and capability                                                                                                                                          |
| `per-capita-adjusted-gini`                        | Further adjusted for within-country inequality                                                                                                                                      |
| `per-capita-convergence`                          | Transition from current emissions to equal per capita (comparison only — convergence from current levels embeds implicit grandfathering during the transition period [Kartha 2018]) |
| `cumulative-per-capita-convergence`               | Budget-preserving transition from current emissions to cumulative targets                                                                                                           |
| `cumulative-per-capita-convergence-adjusted`      | Cumulative convergence with responsibility and capability adjustments                                                                                                               |
| `cumulative-per-capita-convergence-gini-adjusted` | Cumulative convergence accounting for intra-national inequality                                                                                                                     |

For detailed explanations, see [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/).

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
| `param_manifest.csv`           | CSV     | All parameter combinations   |

### Output Types

- **Relative shares**: Country fractions summing to 1.0 per year
- **Absolute emissions**: Relative share × global target in physical units

!!! note "Negative allocations under principled approaches"
Under approaches like ECPC from 1990, some developed regions have already exhausted their fair share and will show negative remaining allocations. This is a feature, not a bug — it signals the need for maximum domestic ambition and active support for international cooperation to compensate for past overshoot.

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

- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** - Theoretical foundations
- **[API Reference](https://setupelz.github.io/fair-shares/api/allocations/budgets/)** - Function signatures
- **[Other Operations](https://setupelz.github.io/fair-shares/science/other-operations/)** - RCB pathway generation, net-negative handling
