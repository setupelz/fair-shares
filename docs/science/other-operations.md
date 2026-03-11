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

## NGHGI-Consistent RCB Corrections

Remaining carbon budgets (RCBs) are reported relative to a reference year (e.g., January 2020) and typically use **bookkeeping model (BM)** estimates for land-use CO₂ fluxes. National GHG inventories (NGHGIs) use a different convention that includes passive carbon fluxes (CO₂ fertilization, climate feedbacks on terrestrial sinks). Converting IPCC RCBs to an NGHGI-consistent basis requires two corrections [Weber 2026]:

1. **LULUCF convention gap** — the systematic difference between NGHGI and bookkeeping LULUCF estimates
2. **Bunker fuel subtraction** — international aviation and shipping emissions that appear in global totals but are excluded from national inventories

These corrections ensure that country-level fair share allocations are comparable with nationally reported emissions.


### Per-scenario net-zero years as integration bounds

We shift RCBs to the year 2020 and correct for the LULUCF convention gap and bunker fuels by integrating from 2020 to the **scenario-specific net-zero year** $t_{\text{nz},i}$ — the first year when that scenario's total CO₂ emissions (`Emissions|CO2` = fossil + BM LULUCF) reach zero. This prevents post-net-zero negative emissions from inflating the LULUCF correction and respects that scenarios within a category reach net-zero at different times.

Per-scenario net-zero years are computed by `load_gidden_per_scenario_nz_years` from the Gidden et al. AR6 reanalysis (OSCAR v3.2) data. Category-level summary statistics (median, quartiles) are stored in `data/rcbs/ar6_category_constants.yaml`; the full per-scenario detail is in `data/rcbs/ar6_scenario_nz_years.parquet`. The category-level median NZ year is used only for bunker fuel integration (which is observational, not scenario-dependent).

Scenarios that never reach net-zero total CO₂ before 2100 are assigned 2100 as a conservative upper integration bound.

### Why two LULUCF conventions matter

Bookkeeping models (e.g., BLUE, OSCAR) estimate only **direct human-caused** land-use fluxes — deforestation, afforestation, land management. NGHGIs additionally include **indirect effects** such as CO₂ fertilization of managed forests and climate-driven changes in soil carbon. The NGHGI total is therefore systematically different from the bookkeeping total, even for the same physical land area.

The global difference is substantial: NGHGI-reported LULUCF is a larger net sink than BM estimates, creating a 5–7 GtCO₂/yr discrepancy primarily because CO₂ fertilization enhances carbon uptake on managed land [Weber 2026].

### Correction for fossil-only budgets (CO₂-FFI)

RCBs are a **total** anthropogenic CO₂ budget shared between fossil and land-use emissions. To isolate the fossil-only budget, the bookkeeping model (BM) LULUCF pathway assumed in the corresponding AR6 scenarios is subtracted. Each scenario is integrated to its own net-zero year, then the median is taken. A **precautionary cap** (default: on) ensures that the median projected BM LULUCF sink cannot increase the fossil budget — only sources can reduce it:

$$
\text{RCB}_{\text{fossil}} = \text{RCB}_{\text{IPCC}} - \max\!\left(0,\; \underset{i}{\text{median}}\left[\sum_{t=2020}^{t_{\text{nz},i}} \text{LULUCF}_{\text{BM},i}(t)\right]\right) - \sum_{t=2020}^{t_{\text{nz,med}}} \text{Bunkers}(t)
$$

Where:

- $\text{LULUCF}_{\text{BM},i}(t)$ is the Gidden et al. AR6 reanalysis AFOLU|Direct for scenario $i$ — the bookkeeping model component only (not NGHGI, not Indirect)
- The median is taken over all scenarios $i$ within the AR6 category (e.g., all C1 scenarios), each integrated to its own $t_{\text{nz},i}$
- $t_{\text{nz},i}$ is the year when scenario $i$'s `Emissions|CO2` (fossil + BM LULUCF) first reaches ≤ 0. Scenarios that never reach net-zero are integrated to 2100.
- $t_{\text{nz,med}}$ is the category-level median net-zero year, used only for the bunker extrapolation endpoint
- Bunkers use GCB2024 historical data with the last observed annual rate extrapolated to $t_{\text{nz,med}}$ (observational, not scenario-dependent)
- The $\max(0, \cdot)$ cap applies the precautionary principle: when the median cumulative BM LULUCF is a net sink (negative), the cap zeros it out so projected reforestation does not inflate the fossil budget. When it is a net source (positive), the full amount still reduces the fossil budget. Configurable via `precautionary_lulucf` in the adjustments config (default: `true`; set to `false` for sensitivity analysis without the cap).

### Correction for total CO₂ budgets (CO₂)

For budgets covering **total CO₂** including land use (`co2`), LULUCF stays in the budget — but the convention must switch from bookkeeping to NGHGI. Only the **convention gap** is deducted. Each scenario is integrated to its own net-zero year, then the median is taken:

$$
\text{RCB}_{\text{total}} = \text{RCB}_{\text{IPCC}} - \underset{i}{\text{median}}\!\left[\text{Gap}_i\right] - \sum_{t=2020}^{t_{\text{nz,med}}} \text{Bunkers}(t)
$$

Where the per-scenario convention gap $\text{Gap}_i$ decomposes into two segments:

**Historical** ($2020 \leq t \leq 2022$): Grassi NGHGI (reported values, same for all scenarios) minus Gidden Direct for scenario $i$ (a bookkeeping proxy from the AR6 reanalysis):

$$
\text{Gap}_{i,\text{hist}} = \sum_{t=\text{start}}^{\min(\text{splice},\, t_{\text{nz},i})} \left[\text{Grassi}(t) - \text{Gidden}_{\text{Direct},i}(t)\right]
$$

**Future** ($t > 2022$): Only the Gidden Indirect component for scenario $i$ (CO₂ fertilization and other passive fluxes), because the Direct components cancel in the gap:

$$
\text{Gap}_{i,\text{future}} = \sum_{t=\text{splice}+1}^{t_{\text{nz},i}} \text{Gidden}_{\text{Indirect},i}(t)
$$

The total per-scenario gap is $\text{Gap}_i = \text{Gap}_{i,\text{hist}} + \text{Gap}_{i,\text{future}}$, and the median is taken across all scenarios $i$ in the AR6 category. Each scenario's integration ends at its own $t_{\text{nz},i}$.

For C1 scenarios (1.5°C), the median convention gap is approximately −84 GtCO₂ (dominated by the cumulative indirect effect), while the median BM LULUCF used for the fossil-only conversion is approximately −35 GtCO₂ (direct anthropogenic land-use change only). The indirect effect is larger because CO₂ fertilization enhances carbon uptake across all managed land, whereas direct land-use change is limited to areas where human activity alters land cover.

### World CO₂ timeseries for backward extension

When the allocation year is before 2020, historical emissions must be added back to the RCB (see [RCB Pathway Generation](#rcb-pathway-generation) above). For total CO₂, the per-year world emissions use the NGHGI convention:

$$
E_{\text{world}}(t) = E_{\text{fossil}}(t) - E_{\text{bunkers}}(t) + \text{LULUCF}(t)
$$

Where LULUCF uses:

- **1990 onwards**: Grassi NGHGI LULUCF (nationally aggregated inventory data)
- **Pre-1990**: Bookkeeping LULUCF from PRIMAP (no global NGHGI data available before 1990)

This ensures the world timeseries passed to `calculate_budget_from_rcb` is NGHGI-consistent, and that function works identically for both `co2-ffi` and `co2` categories.

### Data sources

| Component       | Source                                        | Coverage                                |
| --------------- | --------------------------------------------- | --------------------------------------- |
| NGHGI LULUCF    | Grassi et al. NGHGI LULUCF dataset            | 1990–2022, global aggregate             |
| BM LULUCF proxy | Gidden et al. AR6 reanalysis, AFOLU\|Direct   | 2015–2100, per scenario within category |
| Passive flux    | Gidden et al. AR6 reanalysis, AFOLU\|Indirect | 2015–2100, per scenario within category |
| Net-zero years  | Gidden et al. AR6 reanalysis, Emissions\|CO2  | Per scenario (first year total CO₂ ≤ 0) |
| Bunker fuels    | GCB2024 historical + rate extrapolation       | Historical + extrapolated to median NZ  |
| Fossil CO₂      | PRIMAP-hist v2.6                              | 1750–present                            |

**[API Reference →](https://setupelz.github.io/fair-shares/api/utils/data/#nghgi-corrections)** | `src/fair_shares/library/utils/data/nghgi.py`

### Worked example: 1.5°C 50% budget cascade

Using the AR6 WG1 1.5°C 50% RCB (500 GtCO₂ total from January 2020, C1 category). All values in GtCO₂. The LULUCF adjustments shown below are the **median of per-scenario cumulative totals**, where each scenario is integrated to its own total CO₂ net-zero year (median ~2050 for C1, range ~2035–2070). Bunkers use the category-level median net-zero year.

#### Step 1: NGHGI-consistent adjustments

These adjustments convert the raw IPCC RCB into a budget that is consistent with NGHGI-convention national inventories and excludes international bunker fuels. They are always applied, regardless of allocation year.

|                            | CO₂-FFI                | CO₂                      |
| -------------------------- | ---------------------- | ------------------------ |
| IPCC RCB (total CO₂)       | 500                    | 500                      |
| LULUCF adjustment          | **0** (BM sink capped) | **−84** (convention gap) |
| Bunker subtraction         | −35                    | −35                      |
| **Adjusted RCB from 2020** | **465**                | **381**                  |

**CO₂-FFI:** The 500 GtCO₂ total budget is shared between fossil and land-use emissions. BM LULUCF is currently a next source (~+2.8 GtCO₂/yr), but C1 scenarios project a transition to a net sink around 2027. The median of per-scenario cumulative BM LULUCF (each integrated to its own NZ year, median ~2050) is ~−35 GtCO₂ — i.e., a net sink over the full period. Under the **precautionary cap** (default), this median projected sink is not credited to the fossil budget — the LULUCF adjustment is capped at zero — because the sink relies on uncertain future reforestation. Subtracting 35 GtCO₂ of bunker fuels leaves **465 GtCO₂** for country-level allocation. Without the precautionary cap (`precautionary_lulucf: false`), the fossil budget would be 509 GtCO₂.

**CO₂:** Countries report under NGHGI convention, which includes indirect effects (CO₂ fertilization) that make the land sink appear ~83 GtCO₂ larger than BM over the same period. This −84 GtCO₂ figure is the median of per-scenario convention gaps across all C1 scenarios (each integrated to its own NZ year). Since the RCB was calculated under BM convention, using it unchanged with NGHGI-convention inventories would allow countries to claim credit for natural carbon uptake already accounted for in the Earth System Models underlying the RCB. The convention gap (−84 GtCO₂) and bunker subtraction (−35 GtCO₂) reduce the budget to **381 GtCO₂**.

#### Step 2: Allocation year adjustment

The adjusted RCB is the budget **from 2020 onwards**. The `allocation_year` parameter shifts the starting point by adding historical emissions (if before 2020) or subtracting already-used emissions (if after 2020). This determines the total budget to be shared across countries.

**From 1990** (`allocation_year = 1990`):

|                              | CO₂-FFI       | CO₂                          |
| ---------------------------- | ------------- | ---------------------------- |
| Adjusted RCB from 2020       | 465           | 381                          |
| + World emissions 1990–2019  | +863 (fossil) | +810 (fossil + NGHGI LULUCF) |
| **Total budget to allocate** | **~1,328**    | **~1,191**                   |

Earlier allocation years produce larger total budgets because more historical emissions are included. This is intentional: the total budget from 1990 represents all emissions from 1990 onwards (historical + remaining). The allocation approach (e.g., equal-per-capita) then determines each country's share. Countries with high historical emissions have already used a larger portion of the total, leaving less of their "fair share" for the future.

**From 2020** (`allocation_year = 2020`):

|                              | CO₂-FFI | CO₂     |
| ---------------------------- | ------- | ------- |
| **Total budget to allocate** | **465** | **381** |

The adjusted RCB is used directly — no historical adjustment needed.

**From 2025** (`allocation_year = 2025`):

|                                    | CO₂-FFI       | CO₂                          |
| ---------------------------------- | ------------- | ---------------------------- |
| Adjusted RCB from 2020             | 465           | 381                          |
| − Emissions already used 2020–2024 | −181 (fossil) | −167 (fossil + NGHGI LULUCF) |
| **Total budget to allocate**       | **~284**      | **~214**                     |

Later allocation years produce smaller budgets — emissions already used since 2020 are subtracted. This is equivalent to asking: given what the world has already emitted, how much remains to allocate?

!!! note "Data availability"

    The 2020–2024 values are approximate. PRIMAP-hist v2.6.1 extends to 2023; the 2024 value is extrapolated from the most recent annual rate. Exact figures depend on the emissions data source configured in the pipeline.

#### Summary: how the budget depends on emission category and allocation year

| Allocation year | CO₂-FFI (Gt) | CO₂ (Gt) | Key difference                          |
| --------------- | ------------ | -------- | --------------------------------------- |
| 1990            | ~1,328       | ~1,191   | FFI > CO₂ because of the land sink      |
| 2020            | 465          | 381      | Same direction, no historical component |
| 2025            | ~284         | ~214     | Less remains after 5 years of emissions |

!!! note "Without precautionary cap"

    With `precautionary_lulucf: false`, the CO₂-FFI values increase by ~35 GtCO₂ (the cumulative BM LULUCF sink): 500 (2020), ~1,363 (1990), ~319 (2025).

The CO₂-FFI budget is consistently larger than the CO₂ budget at every allocation year. With the precautionary cap on, the gap equals the **convention gap** (median of per-scenario indirect effects, ~84 GtCO₂). Without the cap, the gap equals the full **cumulative NGHGI LULUCF sink** (median of per-scenario BM Direct + convention gap, ~119 GtCO₂). For example, at 2020: 465 − 381 = 84 GtCO₂ (convention gap only, since the BM sink is capped at zero).

The full NGHGI LULUCF decomposition for C1 (median of per-scenario cumulative totals, each integrated to its own NZ year):

| Period            | NGHGI LULUCF | Source                                   |
| ----------------- | ------------ | ---------------------------------------- |
| 2020–2024         | ~−14 Gt      | Grassi historical (~−2.8 Gt/yr)          |
| 2025–~NZ (median) | ~−105 Gt     | Remainder to net-zero (varies by scenario) |
| **2020–~NZ**      | **~−119 Gt** | = BM Direct (−35) + Convention gap (−83) |

This ~−119 Gt total decomposes into the BM component (~−1.5 Gt/yr median, direct anthropogenic land-use change) and the indirect component (~−3.5 Gt/yr median, CO₂ fertilization on managed land). Under the precautionary cap, only the convention gap (−83 GtCO₂) reduces the fossil budget; the BM Direct sink (−35 GtCO₂) is zeroed out. Note that the per-scenario integration windows vary (C1 scenarios reach total CO₂ net-zero between ~2035 and ~2070); the values shown are medians across scenarios.

---

## See Also

- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** — Design choices
- **[API Reference](https://setupelz.github.io/fair-shares/api/)** — Function documentation
