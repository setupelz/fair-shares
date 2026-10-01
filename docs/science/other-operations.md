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

The default (and currently only) generator is `exponential-decay` (shifted exponential). The `generator` parameter is an extensibility point — alternative functional forms (e.g., linear, sigmoid) can be added without changing the allocation pipeline, provided they satisfy the same constraint: the discrete annual sum must exactly equal the input carbon budget by the end year (typically 2100). Note that even with a 2100 end year, individual regions may reach effective net-zero much earlier when their allocated share of the global pathway becomes negligibly small.

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
([IPCC 2021](https://doi.org/10.1017/9781009157896), AR6 WG1; see also
[Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) on budget size and
uncertainty). Non-CO₂ greenhouse gases (CH₄, N₂O, F-gases) pathways are an
assumption used in deriving the remaining carbon budget quantity.

When users request an all-GHG allocation (e.g. `all-ghg` or `all-ghg-ex-co2-lulucf`) but use RCBs as the target source, a problem arises: RCBs constrain CO₂ only and say nothing about non-CO₂ gases. To produce all-GHG results, the system **decomposes** the problem into two components — allocating CO₂ via the budget approach and non-CO₂ via scenario pathways:

| Component | Gas scope          | Allocation method                | Data source              |
| --------- | ------------------ | -------------------------------- | ------------------------ |
| CO₂       | `co2` or `co2-ffi` | Budget approach (RCBs)           | Remaining carbon budgets |
| Non-CO₂   | `non-co2`          | Pathway approach (e.g. AR6 scenarios) | e.g. AR6 median pathways |

!!! note "New RCBs require matching scenario pathways"

    When adding new remaining carbon budgets, complete scenario pathways that meet their climate assessments must also be available in the active data source configuration for pathways. Without them, the non-CO₂ decomposition has no pathway data to allocate from.

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

This subtraction is applied to both historical emissions (e.g. PRIMAP) and
future scenarios (e.g. AR6), producing non-CO₂ timeseries that are used for
pathway allocation.

### Scenario labels

Scenario source categories are mapped to clean `climate-assessment` names and `quantile` fields during preprocessing (notebook 104). This normalisation ensures that all downstream code — including non-CO₂ pathways — works with a consistent format regardless of the upstream scenario source. For example, AR6 categories map as:

- C1 → `climate-assessment="1.5C"`, `quantile=0.5`
- C3 → `climate-assessment="2C"`, `quantile=0.66`
- C2 → `climate-assessment="2C"`, `quantile=0.83`

New scenario sources would define their own mapping into the same clean format. Any new data processing notebook that introduces a scenario source must output data in this normalised schema.

Internally, notebook 104 uses combined labels (e.g., "1.5p50") during
median calculation to keep C2 and C3 distinct, then remaps to the clean
format at output.

### Auto-derivation of pathway approaches

Users only specify budget approaches (e.g., `equal-per-capita-budget`). The
system automatically derives equivalent pathway approaches for non-CO₂:

- `equal-per-capita-budget` → `equal-per-capita`
- `per-capita-adjusted-budget` → `per-capita-adjusted`
- `per-capita-adjusted-gini-budget` → `per-capita-adjusted-gini`
- `allocation_year` → `first_allocation_year`
- `preserve_allocation_year_shares` → `preserve_first_allocation_year_shares`
- `cumulative_end_year` → removed (budget-only: it bounds the cumulative
  population window of budget allocations, and pathway shares are computed
  per year)

All other parameters pass through unchanged, including
`capability_reference_year`, which pathway approaches support with the same
snapshot semantics as budgets. A derived config therefore names exactly the
parameters that will run; `run_allocation` rejects any configuration
parameter its approach lacks rather than dropping it silently.

This ensures methodological consistency: the same equity principle governs
both gases, adapted to the different allocation modes. This auto-derivation only works when scenario pathway data matching the requested climate assessments is available in the active source set — without it, the non-CO₂ leg has nothing to allocate.

### Single-pass exception for direct scenario pathways

When `target=pathway`, composite categories are **not** decomposed. If the
scenario source provides direct data for `all-ghg` or `all-ghg-ex-co2-lulucf`
(as AR6 does), the system runs a single pathway allocation pass instead of
the CO₂ + non-CO₂ decomposition.

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
| $F_{\text{actual}}(a, b)$             | Cumulative actual fossil CO₂ emissions without international bunkers, years $a$ to $b$ (e.g. PRIMAP) |
| $L_{\text{BM}}(a, b)$                 | Cumulative BM LULUCF CO₂ from scenario median (AFOLU\|Direct), years $a$ to $b$     |
| $L_{\text{BM,actual}}(a, b)$          | Cumulative actual observed BM LULUCF CO₂ (e.g. PRIMAP co2-lulucf), years $a$ to $b$ |
| $B(a, b)$                             | Cumulative international bunker fuel CO₂ emissions, years $a$ to $b$                |
| $\text{gap}(a, b)$                    | Cumulative NGHGI--BM convention gap for CO₂, years $a$ to $b$                       |
| $\text{NZ}$                           | Net-zero year (from scenario data)                                                  |
| $\text{base}$                         | RCB baseline year (e.g., 2023 for Lamboll, 2020 for AR6 WGI)                        |

### Correction for fossil-only budgets (co2-ffi)

The fossil-allocatable budget isolates the portion of the total carbon budget available for fossil CO₂ emissions, after removing the land-use share and international bunkers:

$$
\mathrm{fossil{\_}budget}(2020) = \text{RCB}_{\text{BM}}(\text{base})
  + F_{\text{actual}}(2020,\, \text{base}{-}1)
  + B(2020,\, \text{base}{-}1)
  - L_{\text{BM}}(\text{base},\, \text{NZ})
  - B(2020,\, \text{NZ})
$$

The five terms are:

1. **$\text{RCB}_{\text{BM}}(\text{base})$** -- the published carbon budget, which covers _total_ anthropogenic CO₂ (fossil + international bunkers + BM LULUCF) from the baseline year onward.

2. **$F_{\text{actual}}(2020,\, \text{base}{-}1)$** -- the fossil rebase. When the published baseline is after 2020, actual fossil emissions from 2020 to $\text{base}{-}1$ are added back. This uses only observational data (e.g. PRIMAP), never scenario projections. The world fossil series excludes international bunkers: the PRIMAP world total equals the sum of its countries, and the `gcb-2025` world row is the GCB global total minus bunkers. When $\text{base} = 2020$, this term is zero.

3. **$B(2020,\, \text{base}{-}1)$** -- the bunker rebase. Observed bunker emissions from 2020 to $\text{base}{-}1$ are added back, because the published budget includes bunkers and the fossil rebase does not. When $\text{base} = 2020$, this term is zero. The output column is `rebase_bunkers_mt`.

4. **$L_{\text{BM}}(\text{base},\, \text{NZ})$** -- the LULUCF decomposition. Removes the BM LULUCF share of the budget from the baseline year to the scenario net-zero year, using AR6 scenario median pathways (AFOLU|Direct). This is the only way to separate the fossil and land-use portions of the total budget.

5. **$B(2020,\, \text{NZ})$** -- the bunker deduction. Removes international aviation and shipping emissions that appear in global totals but are excluded from national inventories. Integrated from 2020 to NZ regardless of baseline year. Observed values run to the last year of the bunker data. Later years take the rate of that last year.

#### Why the rebase adds bunkers

The two bunker terms count each bunker year once. The bunker rebase restores the published budget to a total-CO₂ budget from 2020. The deduction then removes every bunker year from 2020 to NZ:

$$
B(2020,\, \text{base}{-}1) - B(2020,\, \text{NZ}) = -B(\text{base},\, \text{NZ})
$$

The years 2020 to $\text{base}{-}1$ cancel, and the net deduction covers the years that the published budget holds. The result is the budget from 2020 without any bunker emissions, for every baseline year. A world emissions series without bunkers then extends it to other allocation years.

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
L_{\text{BM}}^{\text{capped}} = \max\!\left(0,\; \underset{i}{\text{median}}\left[\sum_{t=2020}^{t_{\text{nz},i}} L_{\text{BM},i}(t)\right] - \underset{i}{\text{median}}\left[L_{\text{BM},i}(t)\right]_{t=2020}^{\text{base}-1}\right)
$$

The LULUCF decomposition extends from the baseline year to net-zero. Thus we must use AR6 scenario pathways corresponding to the same climate category as the RCB (e.g., 1.5°C 50th percentile scenarios for a 1.5p50 budget). Each scenario's cumulative AFOLU|Direct is integrated from 2020 to its own net-zero year $t_{\text{nz},i}$, then the median across scenarios is taken (integrate per scenario, then median — consistent with the convention gap computation per Weber 2026). The pre-computed median cumulative is stored as `bm_lulucf_cumulative_median` in `rcb_scenario_adjustments.yaml`. When the RCB baseline year $\text{base} > 2020$, the 2020-to-base prefix is subtracted using the per-year median timeseries (accurate because historical BM LULUCF has negligible inter-scenario spread). When the result is negative (net sink), the cap zeros it out because the sink relies on uncertain future reforestation. Configurable via `precautionary_lulucf` in the adjustments config (default: `true`; set to `false` for sensitivity analysis).

!!! note "Why `convention_gap_median` is 0 in CO2-FFI output"
    The `rcb_scenario_adjustments.yaml` file includes a `convention_gap_median` field for every AR6 category. For **co2-ffi** allocations, this field is **not used** — the LULUCF adjustment comes from `bm_lulucf_cumulative_median` instead (see above). The convention gap only applies to **co2** allocations, where the budget must switch from the bookkeeping model convention to the NGHGI convention. Its presence in the YAML for co2-ffi scenarios is a storage artefact, not a computational input.

### Correction for total CO₂ budgets (co2)

For budgets covering **total CO₂** including land use, LULUCF stays in the budget but the convention must switch from BM to NGHGI. Unlike the co2-ffi case, there is no LULUCF decomposition -- only a convention gap adjustment:

$$
\mathrm{nghgi{\_}budget}(2020) = \text{RCB}_{\text{BM}}(\text{base})
  + F_{\text{actual}}(2020,\, \text{base}{-}1)
  + B(2020,\, \text{base}{-}1)
  + L_{\text{BM,actual}}(2020,\, \text{base}{-}1)
  + \text{gap}(2020,\, \text{NZ})
  - B(2020,\, \text{NZ})
$$

The six terms are:

1. **$\text{RCB}_{\text{BM}}(\text{base})$** -- the published carbon budget, same as for co2-ffi.

2. **$F_{\text{actual}}(2020,\, \text{base}{-}1)$** -- the fossil rebase, identical to co2-ffi.

3. **$B(2020,\, \text{base}{-}1)$** -- the bunker rebase, identical to co2-ffi.

4. **$L_{\text{BM,actual}}(2020,\, \text{base}{-}1)$** -- the BM LULUCF rebase. Unlike co2-ffi, actual observed BM LULUCF _is_ included in the rebase. This is because there is no LULUCF decomposition to cancel with -- the budget retains the full land-use component. Source: e.g. PRIMAP co2-lulucf (already in the pipeline).

5. **$\text{gap}(2020,\, \text{NZ})$** -- the BM-to-NGHGI convention gap. Covers the full period from 2020 (not from $\text{base}$) because the BM LULUCF rebase is in BM convention — the gap for the rebase years converts it to NGHGI. This quantity is negative (NGHGI reports a larger land sink than BM), so it reduces the allocatable budget. Computed from NGHGI actual LULUCF and scenario BM LULUCF (AFOLU|Direct) data (see [Convention gap decomposition](#convention-gap-decomposition)).

6. **$B(2020,\, \text{NZ})$** -- the bunker deduction, same as for co2-ffi.

#### Why the co2 rebase includes actual BM LULUCF

In the co2-ffi formula, actual BM LULUCF in the rebase period cancels with the decomposition for the same years. In the co2 formula there is no LULUCF decomposition (because land-use emissions stay in the budget), so there is nothing for the rebase LULUCF to cancel with. The rebase must therefore include both fossil and BM LULUCF to correctly shift the total CO₂ budget from $\text{base}$ to 2020.

### Design principle: actual data for the rebase, scenario data for the future

The formulas enforce a strict separation:

| Quantity                                                | Data type                       | Rationale                                                             |
| ------------------------------------------------------- | ------------------------------- | --------------------------------------------------------------------- |
| Fossil rebase ($F_{\text{actual}}$)                     | Actual (e.g. PRIMAP)            | Observed emissions -- no projection uncertainty                       |
| Bunker rebase ($B$, 2020 to $\text{base}{-}1$)          | Actual (GCB bunker series)      | Same rationale                                                        |
| BM LULUCF rebase ($L_{\text{BM,actual}}$, co2 only)     | Actual (e.g. PRIMAP co2-lulucf) | Same rationale                                                        |
| BM LULUCF decomposition ($L_{\text{BM}}$, co2-ffi only) | Scenario median (AFOLU\|Direct) | Requires future pathway to NZ; no observational data exists           |
| Convention gap ($\text{gap}$)                           | Scenario-based                  | Forward-looking NGHGI--BM difference requires modeled indirect fluxes |
| Net-zero year ($\text{NZ}$)                             | Scenario data                   | By definition a future quantity                                       |
| Bunker deduction ($B$)                                  | Observational + extrapolation   | Historical data extended at last observed rate to NZ                  |

This means that adding a new RCB source (e.g., Lamboll et al. with baseline 2023) only requires actual emissions and bunker data through 2022 for the rebase. The LULUCF decomposition integrates from $\text{base}$ (co2-ffi), while the convention gap and bunker deduction always cover the full 2020--NZ period.

The rebase needs a value for every year from 2020 to $\text{base}{-}1$ in each series it adds: fossil emissions, bunkers and, for co2, LULUCF.

#### Placeholder for unobserved rebase years

A series can end before $\text{base}{-}1$. Each later year then takes the last observed value of that series. This fill is a placeholder until observed data are published. `rebase_fill_max_years` in `rcbs.yaml` sets the largest number of years that one series may take this way (default 1; 0 turns the fill off). Every fill raises a warning that names the source, the series, the filled years and the value.

A source that needs more years than the limit is left out of the processed budgets, and the pipeline prints a warning that names the missing years. `forster_2026` (baseline 2026) needs values through 2025. With `gcb-2025` emissions and bunkers (observed to 2024) the rebase fills 2025 with the 2024 values. With PRIMAP (observed to 2023) two years are missing and the source is left out. `lamboll_2023` and `forster_2024` need no fill with either emissions source.

The bunker deduction already holds the last observed rate for later years. A filled bunker year in the rebase therefore cancels exactly against the same year in the deduction.

### RCB sources and scenario sets

`data/rcbs/rcbs.yaml` holds five sources. A budget from the start of year $X$ has `baseline_year: X`.

| Source key     | Publication                                                                                          | Budget from   | Scenario selection |
| -------------- | ---------------------------------------------------------------------------------------------------- | ------------- | ------------------ |
| `lamboll_2023` | [Lamboll et al. 2023](https://doi.org/10.1038/s41558-023-01848-5)                                    | Start of 2023 | AR6 category       |
| `forster_2024` | [Forster et al. 2024](https://doi.org/10.5194/essd-16-2625-2024), IGCC 2023                          | Start of 2024 | AR6 category       |
| `ar6_2020`     | IPCC AR6 WGI                                                                                         | Start of 2020 | AR6 category       |
| `forster_2026` | [Forster et al. 2026](https://doi.org/10.5194/essd-18-3889-2026), IGCC 2025, Table 8                 | Start of 2026 | Peak-warming band  |
| `ar6_wg1_2021` | [IPCC AR6 WGI, Table SPM.2](https://doi.org/10.1017/9781009157896.001)                               | Start of 2020 | Peak-warming band  |

The two band sources carry seven budgets each (GtCO₂, total anthropogenic CO₂):

| Label    | Temperature | Likelihood | `forster_2026` | `ar6_wg1_2021` |
| -------- | ----------- | ---------- | -------------- | -------------- |
| `1.5p50` | 1.5°C       | 50%        | 130            | 500            |
| `1.5p67` | 1.5°C       | 67%        | 80             | 400            |
| `1.7p50` | 1.7°C       | 50%        | 500            | 850            |
| `1.7p67` | 1.7°C       | 67%        | 390            | 700            |
| `2p50`   | 2°C         | 50%        | 1050           | 1350           |
| `2p67`   | 2°C         | 67%        | 860            | 1150           |
| `2p83`   | 2°C         | 83%        | 690            | 900            |

Every deduction (LULUCF decomposition, convention gap, net-zero year for bunkers) is a median over a set of AR6 scenarios. The `scenario_selection` field of each source in `rcbs.yaml` names the rule that selects the set:

- **`ar6-category`** (default when the field is absent). The set is one AR6 climate category: `1.5p50` uses C1 (70 scenarios), `2p83` uses C2 (106), `2p66` uses C3 (231). Any other label raises an error that names the source and the label.
- **`peak-warming-band`**. The set is every AR6 scenario whose `Median peak warming (MAGICCv7.5.3)` lies in $[T - 0.05,\; T + 0.05)$, where $T$ is the budget temperature, and that reaches net-zero CO₂ by 2100. A remaining carbon budget runs to net-zero CO₂, so scenarios that never reach it are excluded. The band spans AR6 categories. A band that selects no scenario raises an error that names the temperature and the band.

One band serves every likelihood of its temperature. The published likelihoods cover TCRE uncertainty only, so the 50%, 67% and 83% budgets of one temperature share the same LULUCF, convention-gap and bunker deductions.

With the Gidden et al. AR6 metadata, the bands hold 14 scenarios at 1.5°C (all in C1), 131 at 1.7°C (50 in C2, 81 in C3) and 69 at 2°C (34 in C4, 35 in C5). Of these, 14, 111 and 37 scenarios reach net-zero CO₂ by 2100 and form the scenario sets. The 1.5°C deductions rest on 14 scenarios.

The net-zero test is the one that sets the integration bounds (see [Per-scenario net-zero years](#per-scenario-net-zero-years-as-integration-bounds)): the first year in which the scenario's `Emissions|CO2` time series is at or below zero. The filter and the deduction horizon therefore use one definition.

The band half-width is the `peak_warming_band_half_width` value in `rcbs.yaml` (default 0.05). Set it to 0.1 for a sensitivity run.

Notebook 104 stores the results per scenario set in `rcb_scenario_adjustments.yaml`. Category sets are keyed by label (e.g., `1.5p50`), band sets by temperature (e.g., `peak-warming-1.7C`). The selection logic is `select_rcb_scenario_set()` in `src/fair_shares/library/utils/data/rcb.py`.

The seven-label sources serve the `co2-ffi` and `co2` budget targets. Composite targets (`all-ghg`, `all-ghg-ex-co2-lulucf`) add a non-CO₂ scenario pathway per temperature and likelihood, and those pathways exist for 1.5°C at 50%, 2°C at 66% and 2°C at 83% only.

### Why two LULUCF conventions matter

Bookkeeping models (e.g., BLUE, OSCAR) estimate only **direct human-caused** land-use fluxes -- deforestation, afforestation, land management. NGHGIs additionally include **indirect effects** such as CO₂ fertilization of managed forests and climate-driven changes in soil carbon. The NGHGI total is therefore systematically different from the bookkeeping total, even for the same physical land area.

The global difference is substantial: NGHGI-reported LULUCF is a larger net sink than BM estimates, creating a 5--7 GtCO₂/yr discrepancy primarily because CO₂ fertilization enhances carbon uptake on managed land [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9).

### Per-scenario net-zero years as integration bounds

Forward-looking quantities (LULUCF decomposition, convention gap, bunker deduction) are integrated from their start year to the **scenario-specific net-zero year** $t_{\text{nz},i}$ -- the first year when that scenario's total CO₂ emissions (`Emissions|CO2`) reach zero. This prevents post-net-zero negative emissions from inflating the corrections.

Note that `Emissions|CO2` in IAM scenario databases is fossil + BM LULUCF by convention — this is a property of how scenarios report total CO₂, not a methodological choice by fair-shares.

Per-scenario net-zero years are computed from scenario data (e.g. Gidden et al. AR6 reanalysis). Scenario-level summary statistics (median, quartiles) are stored in `rcb_scenario_adjustments.yaml` in the pipeline output directory, keyed by scenario set (e.g., `1.5p50` or `peak-warming-1.7C`; see [RCB sources and scenario sets](#rcb-sources-and-scenario-sets)). The scenario-level median NZ year is used for the bunker integration endpoint (which is observational, not scenario-dependent).

Scenarios that never reach net-zero total CO₂ by 2100 are assigned 2100 as a conservative upper integration bound. This applies to the AR6 category sets (38 of 231 scenarios in C3). The peak-warming band sets hold no such scenario.

### Convention gap decomposition

The per-scenario convention gap $\text{Gap}_i$ decomposes into two temporal segments:

**Historical** ($2020 \leq t \leq \mathrm{splice{\_}year}$): NGHGI actual LULUCF (reported values, same for all scenarios) minus BM LULUCF for scenario $i$ (the bookkeeping proxy from scenario data). The splice year is derived dynamically from the data (currently 2023). The gap always covers the full 2020--NZ range because the BM LULUCF rebase years also need convention conversion:

$$
\text{Gap}_{i,\text{hist}} = \sum_{t=2020}^{\min(\text{splice},\, t_{\text{nz},i})} \left[\text{NGHGI}_{\text{actual}}(t) - \text{BM}_{\text{Direct},i}(t)\right]
$$

Currently, NGHGI actual LULUCF is sourced from Melo et al. and BM LULUCF from the Gidden et al. AR6 reanalysis (AFOLU|Direct). These are the current data sources for these roles — alternatives providing the same quantities could be substituted.

**Future** ($t > \mathrm{splice{\_}year}$): Only the NGHGI-consistent indirect component for scenario $i$ (CO₂ fertilization and other passive fluxes), because the direct components cancel in the gap:

$$
\text{Gap}_{i,\text{future}} = \sum_{t=\text{splice}+1}^{t_{\text{nz},i}} \text{Indirect}_{i}(t)
$$

Currently sourced from the Gidden et al. AR6 reanalysis (AFOLU|Indirect).

The total per-scenario gap is $\text{Gap}_i = \text{Gap}_{i,\text{hist}} + \text{Gap}_{i,\text{future}}$, and the median is taken across all scenarios $i$ in the corresponding climate category pool. Each scenario's integration ends at its own $t_{\text{nz},i}$.

**Why per-scenario data for the BM side?** The convention gap is a per-scenario quantity — each scenario has its own AFOLU|Direct pathway, NZ year, and Indirect fluxes. Global Carbon Budget multi-model averages cannot be substituted here because they would collapse the per-scenario variation into a single number, breaking the integrate-per-scenario-then-median methodology. For actual historical emissions (the RCB rebase from baseline to 2020), observational data is used — no scenario data is involved in that step.

### World CO₂ timeseries for backward extension

When the allocation year is before 2020, historical emissions must be added back to the RCB (see [RCB Pathway Generation](#rcb-pathway-generation) above). For total CO₂, the per-year world emissions use the NGHGI convention:

$$
E_{\text{world}}(t) = E_{\text{fossil}}(t) + \text{LULUCF}(t)
$$

$E_{\text{fossil}}$ is the world fossil series, which excludes international bunkers. The series therefore matches the adjusted budget, which holds no bunker emissions. `build_nghgi_world_co2_timeseries()` and the preprocessing notebooks build the same series.

Where LULUCF uses:

- **2000 onwards**: NGHGI LULUCF (e.g. Melo v3.1, nationally aggregated inventory data)
- **Pre-2000**: Not available in NGHGI convention. Categories including LULUCF are limited to the NGHGI data range (2000+). No NGHGI/BM splicing is performed. While earlier NGHGI LULUCF estimates may exist (e.g., via Grassi et al. or historical extensions of Melo), the official NGHGI data begins in 2000. Extending to 1990 would require splicing heterogeneous datasets, which risks introducing artefacts (the BM-to-NGHGI transition around 1990 shows a large jump). We plan to extend coverage when validated pre-2000 NGHGI LULUCF data becomes available.

This ensures the world timeseries passed to `calculate_budget_from_rcb` is NGHGI-consistent, and that function works identically for both `co2-ffi` and `co2` categories. An allocation year before the first year of the world series raises an error that names the first available year.

### Data requirements for new scenario sources

When adding a new RCB source (e.g., a new publication with a different baseline year or scenario set), the following data are needed:

| Data needed                | Used for                               | Source                                  |
| -------------------------- | -------------------------------------- | --------------------------------------- |
| RCB value + baseline year  | Starting point                         | Published literature                    |
| Actual fossil CO₂          | Rebase                                 | e.g. PRIMAP (already in pipeline)       |
| Actual BM LULUCF           | co2 rebase                             | e.g. PRIMAP co2-lulucf (already in pipeline) |
| Per-year BM LULUCF pathway | co2-ffi LULUCF decomposition           | Scenario data (AFOLU\|Direct median)    |
| Net-zero year              | Integration limit for bunkers + LULUCF | Scenario data                           |
| Convention gap             | co2 BM-to-NGHGI adjustment             | NGHGI + scenario Indirect AFOLU         |
| Bunker fuel timeseries     | Bunker rebase and bunker deduction     | GCB (already in pipeline)               |

The first three rows are observational and already available in the pipeline. The remaining four require scenario data for the new source's mitigation pathway category.

### Data sources

| Component          | Source                                        | Coverage                                 |
| ------------------ | --------------------------------------------- | ---------------------------------------- |
| Fossil CO₂         | PRIMAP-hist v2.6.1                            | 1750--present                            |
| BM LULUCF (actual) | PRIMAP co2-lulucf                             | Country-level, annual                    |
| NGHGI LULUCF       | Melo et al. (2026) v3.1 NGHGI LULUCF          | 2000--2023, 185 countries + world        |
| BM LULUCF proxy    | Gidden et al. AR6 reanalysis, AFOLU\|Direct   | 2015--2100, per scenario within category |
| Passive flux       | Gidden et al. AR6 reanalysis, AFOLU\|Indirect | 2015--2100, per scenario within category |
| Net-zero years     | Gidden et al. AR6 reanalysis, Emissions\|CO2  | Per scenario (first year total CO₂ ≤ 0)  |
| Bunker fuels       | GCB historical + rate extrapolation           | Observed to the last year of the data, then that rate to median NZ |

**[API Reference →](https://setupelz.github.io/fair-shares/api/utils/data/#nghgi-corrections)** | `src/fair_shares/library/utils/data/nghgi.py`

### Worked example: AR6 WG1 1.5C 50% (1.5p50)

Using `ar6_2020` source: 500 GtCO₂ total from 2020, scenario `1.5p50` (70 C1 scenarios, median NZ year ~2050). Values from `make dev-pipeline-rcbs` with PRIMAP v2025.03 emissions and Melo v3.1 LULUCF.

#### Step 1: Weber corrections (RCB to allocatable budget at 2020)

|                               | co2-ffi                | co2                   |
| ----------------------------- | ---------------------- | --------------------- |
| Published RCB (total CO₂)     | 500 Gt                 | 500 Gt                |
| Fossil rebase                 | 0 (base=2020)          | 0 (base=2020)         |
| Bunker rebase                 | 0 (base=2020)          | 0 (base=2020)         |
| BM LULUCF rebase              | --                     | 0 (base=2020)         |
| LULUCF decomposition / gap    | **0** (BM sink capped) | **-90 Gt** (conv gap) |
| Bunker subtraction            | -35 Gt                 | -35 Gt                |
| **Allocatable budget (2020)** | **465 Gt**             | **375 Gt**            |

**co2-ffi:** The cumulative BM LULUCF is estimated from AR6 scenarios in the corresponding climate category (here 1.5°C 50th percentile). Each scenario's AFOLU|Direct is integrated from 2020 to its own NZ year, then the median across scenarios is taken. The result is a net sink. Under the **precautionary cap** (default), this sink is not credited to the fossil budget (capped to 0). Without the cap (`precautionary_lulucf: false`), the fossil budget would increase.

**co2:** The convention gap is -90 Gt — NGHGI reports a larger land CO₂ sink than bookkeeping models, reducing the allocatable budget. The gap is computed from NGHGI actual LULUCF and scenario BM LULUCF data (see [Convention gap decomposition](#convention-gap-decomposition)). Bunker deduction is ~35 Gt (~870 Mt/yr integrated to median NZ year ~2050). The co2 budget is lower than co2-ffi because the convention gap is a significant negative adjustment.

For [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) (`lamboll_2023`, `1.5p50`, 250 Gt from 2023):

|                               | co2-ffi                | co2                     |
| ----------------------------- | ---------------------- | ----------------------- |
| Published RCB                 | 250 Gt                 | 250 Gt                  |
| Fossil rebase (2020--2022)    | +106.6 Gt              | +106.6 Gt               |
| Bunker rebase (2020--2022)    | +2.8 Gt                | +2.8 Gt                 |
| BM LULUCF rebase (2020--2022) | --                     | -12.1 Gt                |
| LULUCF decomposition / gap    | **0** (BM sink capped) | **-90.3 Gt** (conv gap) |
| Bunker subtraction (2020--NZ) | -34.7 Gt               | -34.7 Gt                |
| **Allocatable budget (2020)** | **324.8 Gt**           | **222.4 Gt**            |

The bunker rebase and the bunker subtraction together remove the bunkers of 2023 to NZ (31.8 Gt), the years that the published budget covers.

#### Step 2: Allocation year adjustment

The allocatable budget is the budget **from 2020 onwards**. The `allocation_year` parameter shifts the starting point by adding historical emissions (before 2020) or subtracting already-used emissions (after 2020).

To regenerate these values, run `make dev-pipeline-rcbs`.

---

## See Also

- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** -- Design choices
- **[API Reference](https://setupelz.github.io/fair-shares/api/)** -- Function documentation
