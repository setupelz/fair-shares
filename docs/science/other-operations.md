---
title: Other Operations
description: Supporting operations for allocation calculations
---

# Other Operations

Operations that support allocation calculations: scenario harmonization, RCB pathway generation, data preprocessing, and validation.

---

## Scenario Harmonization

### Harmonization with Convergence

Aligns emission pathways with historical data at an anchor year, then converges back to the original scenario trajectory.

1. Replace scenario values with historical data for years ≤ anchor year
2. Linearly interpolate for anchor year < year < convergence year
3. Use original scenario values for years ≥ convergence year

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/core/)** | `src/fair_shares/library/utils/timeseries.py`

### Cumulative Peak Preservation

Preserves the peak cumulative emissions using time-varying scaling when `preserve_cumulative_peak=True`.

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/core/)** | `src/fair_shares/library/utils/timeseries.py`

### Post-Net-Zero Handling in Global Pathways

Some AR6 scenario pathways have the **global** emission trajectory going net-negative (i.e., the world as a whole achieves net-negative emissions). The allocation framework cannot meaningfully distribute negative global emissions across countries, so years after the global pathway crosses zero are set to NaN and reported.

This is a preprocessing step applied to global scenario pathways before allocation. Pre-net-zero years are preserved unchanged.

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/core/)** | `src/fair_shares/library/utils/dataframes.py::set_post_net_zero_emissions_to_nan`

---

## RCB Pathway Generation

Converts the **global** remaining carbon budget into a **global** annual emission pathway. This is a prerequisite step before country-level pathway allocation — it does not produce country pathways directly.

### How it works

1. Takes the global RCB (in Mt CO₂) and current global emissions as inputs
2. Generates a single global pathway using normalized shifted exponential decay
3. The pathway starts at current global emissions and reaches exactly zero at the end year (default 2100)
4. The discrete annual sum equals the original carbon budget by construction

Country allocations happen **after** this step, using pathway allocation approaches (e.g., `equal-per-capita`, `per-capita-adjusted`). The pathway shape does not prescribe country net-zero years — those emerge from the allocation step. When a country's allocated share approaches zero, that approximates their implied net-zero year.

The default generator is `exponential-decay` (shifted exponential). The `generator` parameter supports extensibility — other functional forms can be added without changing the allocation pipeline.

**[API Reference →](https://setupelz.github.io/fair-shares/api/utils/math/#rcb-pathway-generation)**

---

## Data Preprocessing

### Interpolation

Fills missing values using linear or stepwise interpolation.

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/core/)** | `src/fair_shares/library/utils/timeseries.py::interpolate_scenarios_data`

### Unit Conversion

Standardizes units (emissions: kt/Mt/Gt CO2e, population: million).

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/core/)** | `src/fair_shares/library/utils/units.py`

---

## Data Validation

### TimeseriesDataFrame Validation

Validates structure (MultiIndex format) and content (non-negative values, complete time series).

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/validation/)** | `src/fair_shares/library/validation/pipeline_validation.py`

### Cross-Dataset Validation

Verifies analysis countries + ROW = world totals, and ensures temporal/spatial alignment.

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/validation/)** | `src/fair_shares/library/validation/pipeline_validation.py`

---

## Data Completeness

### Analysis Country Selection

Identifies countries with complete data across all datasets and computes Rest of World totals for remaining countries.

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/core/)** | `src/fair_shares/library/utils/data/completeness.py`

### World Total Extraction

Extracts world totals for validation. Supports keys: "EARTH", "WLD", "World".

**[Implementation →](https://setupelz.github.io/fair-shares/api/utils/core/)** | `src/fair_shares/library/utils/data/completeness.py`

---

## See Also

- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** — Design choices
- **[API Reference](https://setupelz.github.io/fair-shares/api/)** — Function documentation
