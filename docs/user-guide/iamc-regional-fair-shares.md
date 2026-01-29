---
title: iamc-regional-fair-shares
description: Calculate fair share allocations for IAMC model regions
---

# iamc-regional-fair-shares

The `401_custom_iamc_allocation.ipynb` notebook calculates fair share allocations for IAMC model regions and prepares remaining budgets for IAM model input.

**For allocation examples without model preparation, see:**

- `402_example_iamc_budget_allocations.ipynb` - Budget allocation examples
- `403_example_iamc_pathway_allocations.ipynb` - Pathway allocation examples

Use this workflow with IAMC-format scenario data (model, scenario, region, variable, year columns). For country-level allocations, use [country-fair-shares](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/).

---

## Data Requirements

### IAMC Format

Your data should have columns:

| Column       | Description                                         |
| ------------ | --------------------------------------------------- |
| `model`      | Model name (e.g., "SSP_SSP2_v6.3_ES")               |
| `scenario`   | Scenario name (e.g., "ECPC-2015-800Gt")             |
| `region`     | Region identifier                                   |
| `variable`   | Variable name                                       |
| Year columns | `1990`, `1995`, `2000`, `2015`, `2020`, `2025`, ... |

### Required Variables

| Variable             | Purpose                                 |
| -------------------- | --------------------------------------- |
| `Population`         | Per capita calculations                 |
| `GDP\|PPP`           | Capability adjustments (optional)       |
| `Emissions\|Covered` | Actual emissions for budget subtraction |

---

## Key Functions

<!-- REFERENCE: Function implementations in src/fair_shares/library/utils/data/iamc.py
     See load_iamc_data() docstring for complete parameter documentation
-->

### Loading Data

```python
from fair_shares.library.utils.data.iamc import load_iamc_data

data = load_iamc_data(
    data_file="data/scenarios/iamc_example/iamc_reporting_example.xlsx",
    population_variable="Population",
    gdp_variable="GDP|PPP",
    regions=["AFR", "CHN", "EEU", "FSU", "LAM", "MEA", "NAM", "PAO", "PAS", "RCPA", "SAS", "WEU"],
    allocation_start_year=2015,
    budget_end_year=2100,
    expand_to_annual=True,  # Interpolate non-annual data
)
```

<!-- REFERENCE: Allocation approaches documented in docs/science/allocations.md
     Budget allocation implementations:
     - equal_per_capita_budget() in src/fair_shares/library/allocations/budgets/per_capita.py
     - per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py
     Parameter behaviors and theoretical foundations in function docstrings and science docs
-->

### Equal Per Capita Allocation

```python
from fair_shares.library.allocations.budgets.per_capita import equal_per_capita_budget

# Extract dataframes from loaded data
population_ts = data["population"].rename_axis(index={"region": "iso3c"})

result = equal_per_capita_budget(
    population_ts=population_ts,
    allocation_year=2015,
    emission_category="all-ghg-ex-lulucf",
    preserve_allocation_year_shares=False,
    group_level="iso3c",
)

shares = result.relative_shares_cumulative_emission["2015"]
```

### Capability-Adjusted Allocation

```python
from fair_shares.library.allocations.budgets.per_capita import per_capita_adjusted_budget

# Extract dataframes from loaded data
population_ts = data["population"].rename_axis(index={"region": "iso3c"})
gdp_ts = data["gdp"].rename_axis(index={"region": "iso3c"})

result = per_capita_adjusted_budget(
    population_ts=population_ts,
    gdp_ts=gdp_ts,
    allocation_year=2015,
    emission_category="all-ghg-ex-lulucf",
    capability_weight=0.5,
    responsibility_weight=0.0,
    historical_responsibility_year=1990,
    preserve_allocation_year_shares=False,
    group_level="iso3c",
)
```

---

## Preparing Remaining Budgets for IAM Model Input

**Use notebook 401** for model input preparation. Notebooks 402/403 show allocation examples only.

### Understanding Timesteps vs Periods

IAM models (MESSAGE-ix, GCAM, REMIND) often use timestep labels that represent multi-year periods:

| Model      | Timestep Label | Period Represented |
| ---------- | -------------- | ------------------ |
| MESSAGE-ix | 2030           | 2026-2030          |
| MESSAGE-ix | 2040           | 2031-2040          |
| MESSAGE-ix | 2050           | 2041-2050          |

**Critical:** Your remaining budget must start from the first year of the first period, not the timestep label.

### Calculation Method

If allocating from 2015 and your first model period is 2026-2030:

```
Remaining Budget (from 2026) = Fair Share Allocation (2015→) - Actual Emissions (2015-2025)
```

**Steps:**

1. Run allocation from your allocation year (e.g., 2015)
2. Subtract cumulative actual emissions from allocation year to (first period start - 1)
3. Export remaining budget in Mt CO2e
4. Use as cumulative emission constraint in your model (e.g., `bound_emission` in MESSAGE-ix)

### Example Workflow in Notebook 401

See "Step 7: Prepare for IAM Model Input" in notebook 401 for:

- Configuration cells for model timestep/period
- Automated calculation of remaining budgets
- Export in model-ready format

**Important:**

- Emissions must be annual (use `expand_to_annual=True` when loading data)
- Units should match your model (typically Mt CO2e)
- Negative remaining budgets indicate the region has exceeded its allocation

---

## Handling Model Timesteps

The notebook automatically handles different timestep patterns from IAMC models:

- **Annual data** (2020, 2021, 2022, ...) - No interpolation needed
- **5-year intervals** (2020, 2025, 2030, ...) - Interpolates to annual when `expand_to_annual=True`
- **10-year intervals** (2020, 2030, 2040, ...) - Interpolates to annual when `expand_to_annual=True`
- **Mixed patterns** - Handles non-uniform timesteps automatically

---

## See Also

- **[country-fair-shares](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/)** - Full pipeline for country-level analysis
- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** - Theoretical foundations
- **[Budget Functions API](https://setupelz.github.io/fair-shares/api/allocations/budgets/)** - Function signatures
