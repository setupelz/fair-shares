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

## All-GHG Allocations with RCBs

Remaining carbon budgets constrain **CO₂ only** — they are derived from the
near-linear relationship between cumulative CO₂ emissions and global warming
[IPCC AR6 WG1]. Non-CO₂ greenhouse gases (CH₄, N₂O, F-gases) pathways are an
assumption used in deriving the remaining carbon budget quantity.

To produce all-GHG fair share allocations under RCBs, the system
**decomposes** the problem into two components:

| Component | Gas scope          | Allocation method                | Data source              |
| --------- | ------------------ | -------------------------------- | ------------------------ |
| CO₂       | `co2` or `co2-ffi` | Budget approach (RCBs)           | Remaining carbon budgets |
| Non-CO₂   | `non-co2`          | Pathway approach (AR6 scenarios) | AR6 median pathways      |

### Decomposition rules

The CO₂ component depends on the requested emission category:

- **`all-ghg`** → CO₂ component is `co2` (total CO₂ including LULUCF,
  NGHGI-corrected)
- **`all-ghg-ex-co2-lulucf`** → CO₂ component is `co2-ffi` (fossil only,
  no NGHGI corrections needed)

### Non-CO₂ derivation

Non-CO₂ emissions are not a native category. They are derived by subtraction:

$$
\text{non-CO}_2 = \text{all-ghg-ex-co2-lulucf} - \text{co2-ffi}
$$

This subtraction is applied to both historical emissions (from PRIMAP) and
future scenarios (from AR6), producing non-CO₂ timeseries that are used for
pathway allocation.

### Scenario labels

AR6 categories are mapped to clean climate-assessment names and quantiles
during preprocessing in notebook 104. The mapping splits the combined
AR6 category label into separate fields matching the RCB convention:

- C1 → `climate-assessment="1.5C"`, `quantile=0.5`
- C3 → `climate-assessment="2C"`, `quantile=0.66`
- C2 → `climate-assessment="2C"`, `quantile=0.83`

Internally, notebook 104 uses combined labels (e.g., "1.5p50") during
median calculation to keep C2 and C3 distinct, then remaps to the clean
format at output. All downstream code — including non-CO₂ pathways —
uses the clean format directly.

### Auto-derivation of pathway approaches

Users only specify budget approaches (e.g., `equal-per-capita-budget`). The
system automatically derives equivalent pathway approaches for non-CO₂:

- `equal-per-capita-budget` → `equal-per-capita`
- `per-capita-adjusted-budget` → `per-capita-adjusted`
- `per-capita-adjusted-gini-budget` → `per-capita-adjusted-gini`
- `allocation_year` → `first_allocation_year`

This ensures methodological consistency: the same equity principle governs
both gases, adapted to the different allocation modes.

### AR6 single-pass exception

When `target=pathway`, composite categories are **not** decomposed. AR6
provides direct scenario data for `all-ghg` and `all-ghg-ex-co2-lulucf`,
so the system runs a single pathway allocation pass.

---

## Weber RCB Corrections

Remaining carbon budgets (RCBs) are published relative to a baseline year (e.g., 2020 for AR6 WGI, 2023 for Lamboll et al.) and use **bookkeeping model (BM)** estimates for land-use CO₂ fluxes. To produce country-level fair share allocations that are comparable with nationally reported emissions, the published RCB must be:

1. **Rebased** to the allocation reference year (2020) using actual observational data
2. **Decomposed** to isolate the fossil-allocatable or NGHGI-consistent portion
3. **Adjusted** for international bunker fuels excluded from national inventories

The correction methodology follows Weber et al. (2026). A central design principle is the strict separation of **actual observations** (used for the rebase) from **scenario projections** (used only for forward-looking quantities).

### Notation

| Symbol                                | Definition                                                                          |
| ------------------------------------- | ----------------------------------------------------------------------------------- |
| $\text{RCB}_{\text{BM}}(\text{base})$ | Published Remaining Carbon Budget from baseline year, in BM convention              |
| $F_{\text{actual}}(a, b)$             | Cumulative actual fossil CO₂ emissions from year $a$ to year $b$ (PRIMAP)           |
| $L_{\text{BM}}(a, b)$                 | Cumulative BM LULUCF CO₂ from AR6 scenario median (AFOLU\|Direct), years $a$ to $b$ |
| $L_{\text{BM,actual}}(a, b)$          | Cumulative actual observed BM LULUCF CO₂ (PRIMAP co2-lulucf), years $a$ to $b$      |
| $B(a, b)$                             | Cumulative international bunker fuel CO₂ emissions, years $a$ to $b$                |
| $\text{gap}(a, b)$                    | Cumulative NGHGI--BM convention gap for CO₂, years $a$ to $b$                       |
| $\text{NZ}$                           | Net-zero year (from scenario data)                                                  |
| $\text{base}$                         | RCB baseline year (e.g., 2023 for Lamboll, 2020 for AR6 WGI)                        |

### Correction for fossil-only budgets (co2-ffi)

The fossil-allocatable budget isolates the portion of the total carbon budget available for fossil CO₂ emissions, after removing the land-use share and international bunkers:

$$
\text{fossil\_budget}(2020) = \text{RCB}_{\text{BM}}(\text{base})
  + F_{\text{actual}}(2020,\, \text{base}{-}1)
  - L_{\text{BM}}(\text{base},\, \text{NZ})
  - B(2020,\, \text{NZ})
$$

The four terms are:

1. **$\text{RCB}_{\text{BM}}(\text{base})$** -- the published carbon budget, which covers _total_ anthropogenic CO₂ (fossil + BM LULUCF) from the baseline year onward.

2. **$F_{\text{actual}}(2020,\, \text{base}{-}1)$** -- the fossil rebase. When the published baseline is after 2020, actual fossil emissions from 2020 to $\text{base}{-}1$ are added back. This uses only observational data (PRIMAP), never scenario projections. When $\text{base} = 2020$, this term is zero.

3. **$L_{\text{BM}}(\text{base},\, \text{NZ})$** -- the LULUCF decomposition. Removes the BM LULUCF share of the budget from the baseline year to the scenario net-zero year, using AR6 scenario median pathways (AFOLU|Direct). This is the only way to separate the fossil and land-use portions of the total budget.

4. **$B(2020,\, \text{NZ})$** -- the bunker deduction. Removes international aviation and shipping emissions that appear in global totals but are excluded from national inventories. Integrated from 2020 to NZ regardless of baseline year.

#### Why LULUCF is absent from the co2-ffi rebase

The rebase needs to shift the budget's starting point from $\text{base}$ to 2020. A naive approach would add _all_ actual emissions (fossil + LULUCF) for the rebase period. But the LULUCF decomposition already covers the full range from $\text{base}$ to NZ, so adding actual BM LULUCF from 2020 to $\text{base}{-}1$ alongside decomposing from $\text{base}$ to NZ is equivalent to decomposing from 2020 to NZ:

$$
\underbrace{L_{\text{BM,actual}}(2020,\, \text{base}{-}1)}_{\text{rebase LULUCF}}
+ \underbrace{L_{\text{BM}}(\text{base},\, \text{NZ})}_{\text{decomposition}}
\approx L_{\text{BM}}(2020,\, \text{NZ})
$$

Since we would need to subtract $L_{\text{BM}}(2020,\, \text{NZ})$ to isolate the fossil budget anyway, the rebase LULUCF and the decomposition LULUCF from 2020 to $\text{base}{-}1$ cancel algebraically. The formula therefore omits actual LULUCF from the rebase and starts the LULUCF decomposition at $\text{base}$, not 2020. The result is the same, but the formula is simpler and avoids mixing actual and scenario data for overlapping years.

#### Precautionary cap on BM LULUCF

A **precautionary cap** (default: on) ensures that the projected BM LULUCF sink cannot increase the fossil budget -- only sources can reduce it:

$$
L_{\text{BM}}^{\text{capped}} = \max\!\left(0,\; \sum_{t=\text{base}}^{\text{NZ}} \underset{i}{\text{median}}\left[L_{\text{BM},i}(t)\right]\right)
$$

The per-year median is computed across all scenarios in notebook 104 and stored as a timeseries (`lulucf_shift_median_{scenario}.csv`). At runtime, this timeseries is integrated from `base` to the median net-zero year `NZ`. When the cumulative sum is negative (net sink), the cap zeros it out because the sink relies on uncertain future reforestation. Configurable via `precautionary_lulucf` in the adjustments config (default: `true`; set to `false` for sensitivity analysis).

### Correction for total CO₂ budgets (co2)

For budgets covering **total CO₂** including land use, LULUCF stays in the budget but the convention must switch from BM to NGHGI. Unlike the co2-ffi case, there is no LULUCF decomposition -- only a convention gap adjustment:

$$
\text{nghgi\_budget}(2020) = \text{RCB}_{\text{BM}}(\text{base})
  + F_{\text{actual}}(2020,\, \text{base}{-}1)
  + L_{\text{BM,actual}}(2020,\, \text{base}{-}1)
  + \text{gap}(2020,\, \text{NZ})
  - B(2020,\, \text{NZ})
$$

The five terms are:

1. **$\text{RCB}_{\text{BM}}(\text{base})$** -- the published carbon budget, same as for co2-ffi.

2. **$F_{\text{actual}}(2020,\, \text{base}{-}1)$** -- the fossil rebase, identical to co2-ffi.

3. **$L_{\text{BM,actual}}(2020,\, \text{base}{-}1)$** -- the BM LULUCF rebase. Unlike co2-ffi, actual observed BM LULUCF _is_ included in the rebase. This is because there is no LULUCF decomposition to cancel with -- the budget retains the full land-use component. Source: PRIMAP co2-lulucf (already in the pipeline).

4. **$\text{gap}(2020,\, \text{NZ})$** -- the BM-to-NGHGI convention gap. Covers the full period from 2020 (not from $\text{base}$) because the BM LULUCF rebase is in BM convention — the gap for the rebase years converts it to NGHGI. This quantity is negative (NGHGI reports a larger land sink than BM), so it reduces the allocatable budget. Computed from Melo v3.1 NGHGI LULUCF and Gidden AR6 reanalysis data (see [Convention gap decomposition](#convention-gap-decomposition)).

5. **$B(2020,\, \text{NZ})$** -- the bunker deduction, same as for co2-ffi.

#### Why the co2 rebase includes actual BM LULUCF

In the co2-ffi formula, actual BM LULUCF in the rebase period cancels with the decomposition for the same years. In the co2 formula there is no LULUCF decomposition (because land-use emissions stay in the budget), so there is nothing for the rebase LULUCF to cancel with. The rebase must therefore include both fossil and BM LULUCF to correctly shift the total CO₂ budget from $\text{base}$ to 2020.

### Design principle: actual data for the rebase, scenario data for the future

The formulas enforce a strict separation:

| Quantity                                                | Data type                       | Rationale                                                             |
| ------------------------------------------------------- | ------------------------------- | --------------------------------------------------------------------- |
| Fossil rebase ($F_{\text{actual}}$)                     | Actual (PRIMAP)                 | Observed emissions -- no projection uncertainty                       |
| BM LULUCF rebase ($L_{\text{BM,actual}}$, co2 only)     | Actual (PRIMAP co2-lulucf)      | Same rationale                                                        |
| BM LULUCF decomposition ($L_{\text{BM}}$, co2-ffi only) | Scenario median (AFOLU\|Direct) | Requires future pathway to NZ; no observational data exists           |
| Convention gap ($\text{gap}$)                           | Scenario-based                  | Forward-looking NGHGI--BM difference requires modeled indirect fluxes |
| Net-zero year ($\text{NZ}$)                             | Scenario data                   | By definition a future quantity                                       |
| Bunker deduction ($B$)                                  | Observational + extrapolation   | Historical data extended at last observed rate to NZ                  |

This means that adding a new RCB source (e.g., Lamboll et al. with baseline 2023) only requires actual emissions data through 2022 for the rebase. The LULUCF decomposition integrates from $\text{base}$ (co2-ffi), while the convention gap and bunker deduction always cover the full 2020--NZ period.

### Why two LULUCF conventions matter

Bookkeeping models (e.g., BLUE, OSCAR) estimate only **direct human-caused** land-use fluxes -- deforestation, afforestation, land management. NGHGIs additionally include **indirect effects** such as CO₂ fertilization of managed forests and climate-driven changes in soil carbon. The NGHGI total is therefore systematically different from the bookkeeping total, even for the same physical land area.

The global difference is substantial: NGHGI-reported LULUCF is a larger net sink than BM estimates, creating a 5--7 GtCO₂/yr discrepancy primarily because CO₂ fertilization enhances carbon uptake on managed land [Weber 2026].

### Per-scenario net-zero years as integration bounds

Forward-looking quantities (LULUCF decomposition, convention gap, bunker deduction) are integrated from their start year to the **scenario-specific net-zero year** $t_{\text{nz},i}$ -- the first year when that scenario's total CO₂ emissions (`Emissions|CO2` = fossil + BM LULUCF) reach zero. This prevents post-net-zero negative emissions from inflating the corrections.

Per-scenario net-zero years are computed from the Gidden et al. AR6 reanalysis (OSCAR v3.2) data. Scenario-level summary statistics (median, quartiles) are stored in `data/rcbs/ar6_category_constants.yaml`, keyed by RCB scenario label (e.g., `1.5p50`). The scenario-level median NZ year is used for the bunker integration endpoint (which is observational, not scenario-dependent).

Scenarios that never reach net-zero total CO₂ before 2100 are assigned 2100 as a conservative upper integration bound.

### Convention gap decomposition

The per-scenario convention gap $\text{Gap}_i$ decomposes into two temporal segments:

**Historical** ($\text{base} \leq t \leq \text{splice\_year}$): Melo NGHGI (reported values, same for all scenarios) minus Gidden Direct for scenario $i$ (a bookkeeping proxy from the AR6 reanalysis). The splice year is derived dynamically from the data (currently 2023 with Melo v3.1):

$$
\text{Gap}_{i,\text{hist}} = \sum_{t=\text{base}}^{\min(\text{splice},\, t_{\text{nz},i})} \left[\text{Melo}(t) - \text{Gidden}_{\text{Direct},i}(t)\right]
$$

**Future** ($t > \text{splice\_year}$): Only the Gidden Indirect component for scenario $i$ (CO₂ fertilization and other passive fluxes), because the Direct components cancel in the gap:

$$
\text{Gap}_{i,\text{future}} = \sum_{t=\text{splice}+1}^{t_{\text{nz},i}} \text{Gidden}_{\text{Indirect},i}(t)
$$

The total per-scenario gap is $\text{Gap}_i = \text{Gap}_{i,\text{hist}} + \text{Gap}_{i,\text{future}}$, and the median is taken across all scenarios $i$ in the corresponding AR6 category pool. Each scenario's integration ends at its own $t_{\text{nz},i}$.

### World CO₂ timeseries for backward extension

When the allocation year is before 2020, historical emissions must be added back to the RCB (see [RCB Pathway Generation](#rcb-pathway-generation) above). For total CO₂, the per-year world emissions use the NGHGI convention:

$$
E_{\text{world}}(t) = E_{\text{fossil}}(t) - E_{\text{bunkers}}(t) + \text{LULUCF}(t)
$$

Where LULUCF uses:

- **2000 onwards**: Melo NGHGI LULUCF (nationally aggregated inventory data, v3.1)
- **Pre-2000**: Not available in NGHGI convention. Categories including LULUCF are limited to the NGHGI data range (2000+). No NGHGI/BM splicing is performed.

This ensures the world timeseries passed to `calculate_budget_from_rcb` is NGHGI-consistent, and that function works identically for both `co2-ffi` and `co2` categories.

### Data requirements for new scenario sources

When adding a new RCB source (e.g., a new publication with a different baseline year or scenario set), the following data are needed:

| Data needed                | Used for                               | Source                                  |
| -------------------------- | -------------------------------------- | --------------------------------------- |
| RCB value + baseline year  | Starting point                         | Published literature                    |
| Actual fossil CO₂          | Rebase                                 | PRIMAP (already in pipeline)            |
| Actual BM LULUCF           | co2 rebase                             | PRIMAP co2-lulucf (already in pipeline) |
| Per-year BM LULUCF pathway | co2-ffi LULUCF decomposition           | Scenario data (AFOLU\|Direct median)    |
| Net-zero year              | Integration limit for bunkers + LULUCF | Scenario data                           |
| Convention gap             | co2 BM-to-NGHGI adjustment             | NGHGI + scenario Indirect AFOLU         |
| Bunker fuel timeseries     | Bunker deduction                       | NGHGI (already in pipeline)             |

The first three rows are observational and already available in the pipeline. The remaining four require scenario data for the new source's mitigation pathway category.

### Data sources

| Component          | Source                                        | Coverage                                 |
| ------------------ | --------------------------------------------- | ---------------------------------------- |
| Fossil CO₂         | PRIMAP-hist v2.6.1                            | 1750--present                            |
| BM LULUCF (actual) | PRIMAP co2-lulucf                             | Country-level, annual                    |
| NGHGI LULUCF       | Melo et al. (2026) v3.1 NGHGI LULUCF          | 2000--2023, 187 countries + world        |
| BM LULUCF proxy    | Gidden et al. AR6 reanalysis, AFOLU\|Direct   | 2015--2100, per scenario within category |
| Passive flux       | Gidden et al. AR6 reanalysis, AFOLU\|Indirect | 2015--2100, per scenario within category |
| Net-zero years     | Gidden et al. AR6 reanalysis, Emissions\|CO2  | Per scenario (first year total CO₂ ≤ 0)  |
| Bunker fuels       | GCB2024 historical + rate extrapolation       | Historical + extrapolated to median NZ   |

**[API Reference →](https://setupelz.github.io/fair-shares/api/utils/data/#nghgi-corrections)** | `src/fair_shares/library/utils/data/nghgi.py`

### Worked example: AR6 WG1 1.5C 50% (1.5p50)

Using `ar6_2020` source: 500 GtCO₂ total from 2020, scenario `1.5p50` (70 C1 scenarios, median NZ year ~2050). Values from `make dev-pipeline-rcbs` with PRIMAP v2025.03 emissions and Melo v3.1 LULUCF.

#### Step 1: Weber corrections (RCB to allocatable budget at 2020)

|                               | co2-ffi                | co2                   |
| ----------------------------- | ---------------------- | --------------------- |
| Published RCB (total CO₂)     | 500 Gt                 | 500 Gt                |
| Fossil rebase                 | 0 (base=2020)          | 0 (base=2020)         |
| BM LULUCF rebase              | --                     | 0 (base=2020)         |
| LULUCF decomposition / gap    | **0** (BM sink capped) | **-90 Gt** (conv gap) |
| Bunker subtraction            | -35 Gt                 | -35 Gt                |
| **Allocatable budget (2020)** | **465 Gt**             | **375 Gt**            |

**co2-ffi:** The cumulative BM LULUCF (sum of per-year medians from 2020 to median NZ ~2050) is a net sink. Under the **precautionary cap** (default), this sink is not credited to the fossil budget (capped to 0). Without the cap (`precautionary_lulucf: false`), the fossil budget would increase.

**co2:** The convention gap is -90 Gt — NGHGI reports a larger land CO₂ sink than bookkeeping models, reducing the allocatable budget. The gap is computed from Melo v3.1 NGHGI LULUCF and Gidden AR6 reanalysis (see [Convention gap decomposition](#convention-gap-decomposition)). Bunker deduction is ~35 Gt (~870 Mt/yr integrated to median NZ year ~2050). The co2 budget is lower than co2-ffi because the convention gap is a significant negative adjustment.

For Lamboll 2023 (`1.5C`, 247 Gt from 2023):

|                               | co2-ffi                | co2                   |
| ----------------------------- | ---------------------- | --------------------- |
| Published RCB                 | 247 Gt                 | 247 Gt                |
| Fossil rebase (2020--2022)    | +107 Gt                | +107 Gt               |
| BM LULUCF rebase (2020--2022) | --                     | -12 Gt                |
| LULUCF decomposition / gap    | **0** (BM sink capped) | **-90 Gt** (conv gap) |
| Bunker subtraction            | -35 Gt                 | -35 Gt                |
| **Allocatable budget (2020)** | **319 Gt**             | **217 Gt**            |

#### Step 2: Allocation year adjustment

The allocatable budget is the budget **from 2020 onwards**. The `allocation_year` parameter shifts the starting point by adding historical emissions (before 2020) or subtracting already-used emissions (after 2020).

To regenerate these values, run `make dev-pipeline-rcbs`.

---

## See Also

- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** -- Design choices
- **[API Reference](https://setupelz.github.io/fair-shares/api/)** -- Function documentation
