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

### Net-zero year as integration bound

We shift RCBs to the year 2020 and correct for the LULUCF convention gap and bunker fuels by integrating from 2020 to the **scenario-specific net-zero year** $t_{\text{nz}}$ — the first year when category-median total CO₂ emissions reach zero, which varies by AR6 warming category. Stricter categories (C1) reach net zero earlier than less stringent ones (C3).

Per-category net-zero years are extracted from Gidden et al. AR6 reanalysis (OSCAR v3.2) category medians by the **RCB preprocessing notebook** and stored in `data/rcbs/ar6_category_constants.yaml`. Both NGHGI-convention and scientific (BM) convention net-zero years are computed; the pipeline uses the NGHGI convention value (= BM total CO₂ + AFOLU|Indirect), since NGHGI includes passive fluxes that delay the crossing of zero.

### Why two LULUCF conventions matter

Bookkeeping models (e.g., BLUE, OSCAR) estimate only **direct human-caused** land-use fluxes — deforestation, afforestation, land management. NGHGIs additionally include **indirect effects** such as CO₂ fertilization of managed forests and climate-driven changes in soil carbon. The NGHGI total is therefore systematically different from the bookkeeping total, even for the same physical land area.

The global difference is substantial: NGHGI-reported LULUCF is a larger net sink than BM estimates, creating a 5–7 GtCO₂/yr discrepancy primarily because CO₂ fertilization enhances carbon uptake on managed land [Weber 2026].

### Correction for fossil-only budgets (CO₂-FFI)

RCBs are a **total** anthropogenic CO₂ budget shared between fossil and land-use emissions. To isolate the fossil-only budget, the bookkeeping model (BM) LULUCF pathway assumed in the corresponding AR6 scenarios is subtracted. A **precautionary cap** (default: on) ensures that projected BM LULUCF sinks cannot increase the fossil budget — only sources can reduce it:

$$
\text{RCB}_{\text{fossil}} = \text{RCB}_{\text{IPCC}} - \max\!\left(0,\; \sum_{t=2020}^{t_{\text{nz}}} \text{LULUCF}_{\text{BM}}(t)\right) - \sum_{t=2020}^{t_{\text{nz}}} \text{Bunkers}(t)
$$

Where:

- $\text{LULUCF}_{\text{BM}}(t)$ uses Gidden et al. AR6 reanalysis AFOLU|Direct — the bookkeeping model component only (not NGHGI, not Indirect)
- $t_{\text{nz}}$ is the per-category net-zero year from `data/rcbs/ar6_category_constants.yaml`
- Bunkers use GCB2024 historical data with the last observed annual rate extrapolated to $t_{\text{nz}}$
- The $\max(0, \cdot)$ cap applies the precautionary principle: when BM LULUCF is a cumulative sink (negative sum), the cap zeros it out so projected reforestation does not inflate the fossil budget. When BM LULUCF is a cumulative source (positive sum), the full amount still reduces the fossil budget. Configurable via `precautionary_lulucf` in the adjustments config (default: `true`; set to `false` for sensitivity analysis without the cap).

### Correction for total CO₂ budgets (CO₂)

For budgets covering **total CO₂** including land use (`co2`), LULUCF stays in the budget — but the convention must switch from bookkeeping to NGHGI. Only the **convention gap** is deducted:

$$
\text{RCB}_{\text{total}} = \text{RCB}_{\text{IPCC}} - \underbrace{\sum_{t=2020}^{t_{\text{nz}}} \left[\text{NGHGI}(t) - \text{BM}(t)\right]}_{\text{convention gap}} - \sum_{t=2020}^{t_{\text{nz}}} \text{Bunkers}(t)
$$

The convention gap decomposes into two segments:

**Historical** ($2020 \leq t \leq 2022$): Grassi NGHGI minus Gidden Direct (a bookkeeping proxy from the AR6 reanalysis):

$$
\text{Gap}_{\text{hist}} = \sum_{t=\text{start}}^{\text{splice}} \left[\text{Grassi}(t) - \text{Gidden}_{\text{Direct}}(t)\right]
$$

**Future** ($t > 2022$): Only the Gidden Indirect component (CO₂ fertilization and other passive fluxes), because the Direct components cancel in the gap:

$$
\text{Gap}_{\text{future}} = \sum_{t=\text{splice}+1}^{t_{\text{nz}}} \text{Gidden}_{\text{Indirect}}(t)
$$

For C1 scenarios (1.5°C), the convention gap is approximately −83 GtCO₂ (dominated by the cumulative indirect effect), while the BM LULUCF used for the fossil-only conversion is approximately −40 GtCO₂ (direct anthropogenic land-use change only). The indirect effect is larger because CO₂ fertilization enhances carbon uptake across all managed land, whereas direct land-use change is limited to areas where human activity alters land cover.

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

| Component       | Source                                        | Coverage                        |
| --------------- | --------------------------------------------- | ------------------------------- |
| NGHGI LULUCF    | Grassi et al. NGHGI LULUCF dataset            | 1990–2022, global aggregate     |
| BM LULUCF proxy | Gidden et al. AR6 reanalysis, AFOLU\|Direct   | 2015–2100, AR6 category medians |
| Passive flux    | Gidden et al. AR6 reanalysis, AFOLU\|Indirect | 2015–2100, AR6 category medians |
| Bunker fuels    | GCB2024 historical + rate extrapolation       | Historical + extrapolated to NZ |
| Fossil CO₂      | PRIMAP-hist v2.6                              | 1750–present                    |

**[API Reference →](https://setupelz.github.io/fair-shares/api/utils/data/#nghgi-corrections)** | `src/fair_shares/library/utils/data/nghgi.py`

### Worked example: 1.5°C 50% budget cascade

Using the AR6 WG1 1.5°C 50% RCB (500 GtCO₂ total from January 2020, C1 category). All values in GtCO₂.

#### Step 1: NGHGI-consistent adjustments

These adjustments convert the raw IPCC RCB into a budget that is consistent with NGHGI-convention national inventories and excludes international bunker fuels. They are always applied, regardless of allocation year.

|                            | CO₂-FFI                | CO₂                      |
| -------------------------- | ---------------------- | ------------------------ |
| IPCC RCB (total CO₂)       | 500                    | 500                      |
| LULUCF adjustment          | **0** (BM sink capped) | **−83** (convention gap) |
| Bunker subtraction         | −31                    | −31                      |
| **Adjusted RCB from 2020** | **469**                | **386**                  |

**CO₂-FFI:** The 500 GtCO₂ total budget is shared between fossil and land-use emissions. BM LULUCF is currently a net source (~+2.8 GtCO₂/yr), but C1 scenarios project a transition to a net sink around 2027. Cumulatively from 2020 to the net-zero year (2047), BM LULUCF is ~−40 GtCO₂ — i.e., a net sink over the full period. Under the **precautionary cap** (default), this projected sink is not credited to the fossil budget — the LULUCF adjustment is capped at zero — because the sink relies on uncertain future reforestation. Subtracting 31 Gt of bunker fuels leaves **469 GtCO₂** for country-level allocation. Without the precautionary cap (`precautionary_lulucf: false`), the fossil budget would be 509 GtCO₂.

**CO₂:** Countries report under NGHGI convention, which includes indirect effects (CO₂ fertilization) that make the land sink appear ~83 GtCO₂ larger than BM over the same period. Since the RCB was calculated under BM convention, using it unchanged with NGHGI-convention inventories would allow countries to claim credit for natural carbon uptake already accounted for in the Earth System Models underlying the RCB. The convention gap (−83 Gt) and bunker subtraction (−31 Gt) reduce the budget to **386 GtCO₂**.

#### Step 2: Allocation year adjustment

The adjusted RCB is the budget **from 2020 onwards**. The `allocation_year` parameter shifts the starting point by adding historical emissions (if before 2020) or subtracting already-used emissions (if after 2020). This determines the total budget to be shared across countries.

**From 1990** (`allocation_year = 1990`):

|                              | CO₂-FFI       | CO₂                          |
| ---------------------------- | ------------- | ---------------------------- |
| Adjusted RCB from 2020       | 469           | 386                          |
| + World emissions 1990–2019  | +863 (fossil) | +810 (fossil + NGHGI LULUCF) |
| **Total budget to allocate** | **~1,332**    | **~1,196**                   |

Earlier allocation years produce larger total budgets because more historical emissions are included. This is intentional: the total budget from 1990 represents all emissions from 1990 onwards (historical + remaining). The allocation approach (e.g., equal-per-capita, grandfathering) then determines each country's share. Countries with high historical emissions have already used a larger portion of the total, leaving less of their "fair share" for the future.

**From 2020** (`allocation_year = 2020`):

|                              | CO₂-FFI | CO₂     |
| ---------------------------- | ------- | ------- |
| **Total budget to allocate** | **469** | **386** |

The adjusted RCB is used directly — no historical adjustment needed.

**From 2025** (`allocation_year = 2025`):

|                                    | CO₂-FFI       | CO₂                          |
| ---------------------------------- | ------------- | ---------------------------- |
| Adjusted RCB from 2020             | 469           | 386                          |
| − Emissions already used 2020–2024 | −181 (fossil) | −167 (fossil + NGHGI LULUCF) |
| **Total budget to allocate**       | **~288**      | **~219**                     |

Later allocation years produce smaller budgets — emissions already used since 2020 are subtracted. This is equivalent to asking: given what the world has already emitted, how much remains to allocate?

!!! note "Data availability"

    The 2020–2024 values are approximate. PRIMAP-hist v2.6.1 extends to 2023; the 2024 value is extrapolated from the most recent annual rate. Exact figures depend on the emissions data source configured in the pipeline.

#### Summary: how the budget depends on emission category and allocation year

| Allocation year | CO₂-FFI (Gt) | CO₂ (Gt) | Key difference                          |
| --------------- | ------------ | -------- | --------------------------------------- |
| 1990            | ~1,332       | ~1,196   | FFI > CO₂ because of the land sink      |
| 2020            | 469          | 386      | Same direction, no historical component |
| 2025            | ~288         | ~219     | Less remains after 5 years of emissions |

!!! note "Without precautionary cap"

    With `precautionary_lulucf: false`, the CO₂-FFI values increase by ~40 Gt (the cumulative BM LULUCF sink): 509 (2020), ~1,372 (1990), ~328 (2025).

The CO₂-FFI budget is consistently larger than the CO₂ budget at every allocation year. With the precautionary cap on, the gap equals the **convention gap** (indirect effects only, ~83 Gt from 2020 to net-zero). Without the cap, the gap equals the full **cumulative NGHGI LULUCF sink** (BM Direct + convention gap, ~123 Gt). For example, at 2020: 469 − 386 = 83 GtCO₂ (convention gap only, since the BM sink is capped at zero).

The full NGHGI LULUCF decomposition for C1:

| Period        | NGHGI LULUCF | Source                                   |
| ------------- | ------------ | ---------------------------------------- |
| 2020–2024     | ~−14 Gt      | Grassi historical (~−2.8 Gt/yr)          |
| 2025–2047     | ~−109 Gt     | Remainder to net-zero                    |
| **2020–2047** | **~−123 Gt** | = BM Direct (−40) + Convention gap (−83) |

This ~−123 Gt total decomposes into the BM component (~−1.5 Gt/yr, direct anthropogenic land-use change) and the indirect component (~−3.5 Gt/yr, CO₂ fertilization on managed land). Under the precautionary cap, only the convention gap (−83 Gt) reduces the fossil budget; the BM Direct sink (−40 Gt) is zeroed out.

---

## See Also

- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** — Design choices
- **[API Reference](https://setupelz.github.io/fair-shares/api/)** — Function documentation
