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
| $L_{\text{NGHGI}}(a, b)$              | Cumulative observed NGHGI LULUCF CO₂ (world row of the LULUCF source, Melo et al.), years $a$ to $b$ |
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

The rebase shifts the starting point of the budget from $\text{base}$ to 2020. The published budget is in the BM convention, so a full rebase would add BM LULUCF for 2020 to $\text{base}{-}1$. The decomposition would then remove BM LULUCF for 2020 to NZ:

$$
L_{\text{BM}}(2020,\, \text{base}{-}1) - L_{\text{BM}}(2020,\, \text{NZ}) = -L_{\text{BM}}(\text{base},\, \text{NZ})
$$

The years 2020 to $\text{base}{-}1$ cancel. The formula therefore omits LULUCF from the rebase and starts the LULUCF decomposition at $\text{base}$. The pipeline holds no observed LULUCF series in the BM convention, and this form needs none.

#### Precautionary cap on BM LULUCF

A **precautionary cap** (default: on) ensures that the projected BM LULUCF sink cannot increase the fossil budget -- only sources can reduce it:

$$
L_{\text{BM}}^{\text{capped}} = \max\!\left(0,\; \underset{i}{\text{median}}\left[\sum_{t=2020}^{t_{\text{nz},i}} L_{\text{BM},i}(t)\right] - \underset{i}{\text{median}}\left[L_{\text{BM},i}(t)\right]_{t=2020}^{\text{base}-1}\right)
$$

The LULUCF decomposition extends from the baseline year to net-zero. Thus we must use AR6 scenario pathways corresponding to the same climate category as the RCB (e.g., 1.5°C 50th percentile scenarios for a 1.5p50 budget). Each scenario's cumulative AFOLU|Direct is integrated from 2020 to its own net-zero year $t_{\text{nz},i}$, then the median across scenarios is taken (integrate per scenario, then median — consistent with the convention gap computation per Weber 2026). The pre-computed median cumulative is stored as `bm_lulucf_cumulative_median` in `rcb_scenario_adjustments.yaml`. When the RCB baseline year $\text{base} > 2020$, the 2020-to-base prefix is subtracted using the per-year median timeseries (accurate because historical BM LULUCF has negligible inter-scenario spread). When the result is negative (net sink), the cap zeros it out because the sink relies on uncertain future reforestation. Configurable via `precautionary_lulucf` in the adjustments config (default: `true`; set to `false` for sensitivity analysis).

!!! note "Why `convention_gap_median_from` is 0 in CO2-FFI output"
    The `rcb_scenario_adjustments.yaml` file includes a `convention_gap_median_from` field for every scenario set, with one value per RCB baseline year. For **co2-ffi** allocations, this field is **not used** — the LULUCF adjustment comes from `bm_lulucf_cumulative_median` instead (see above). The convention gap only applies to **co2** allocations, where the budget must switch from the bookkeeping model convention to the NGHGI convention. Its presence in the YAML for co2-ffi scenarios is a storage artefact, not a computational input.

### Correction for total CO₂ budgets (co2)

For budgets covering **total CO₂** including land use, LULUCF stays in the budget but the convention must switch from BM to NGHGI. The co2 case has no LULUCF decomposition. The rebase adds observed NGHGI LULUCF for 2020 to $\text{base}{-}1$, and a convention gap converts the published budget from $\text{base}$ to NZ:

$$
\mathrm{nghgi{\_}budget}(2020) = \text{RCB}_{\text{BM}}(\text{base})
  + F_{\text{actual}}(2020,\, \text{base}{-}1)
  + B(2020,\, \text{base}{-}1)
  + L_{\text{NGHGI}}(2020,\, \text{base}{-}1)
  + \text{gap}(\text{base},\, \text{NZ})
  - B(2020,\, \text{NZ})
$$

with $\text{gap}(a, b) = \sum_{t=a}^{b} \left[L_{\text{NGHGI}}(t) - L_{\text{BM}}(t)\right]$.

The six terms are:

1. **$\text{RCB}_{\text{BM}}(\text{base})$** -- the published carbon budget, same as for co2-ffi.

2. **$F_{\text{actual}}(2020,\, \text{base}{-}1)$** -- the fossil rebase, identical to co2-ffi.

3. **$B(2020,\, \text{base}{-}1)$** -- the bunker rebase, identical to co2-ffi.

4. **$L_{\text{NGHGI}}(2020,\, \text{base}{-}1)$** -- the NGHGI LULUCF rebase. Observed LULUCF CO₂ in the national-inventory convention is added for 2020 to $\text{base}{-}1$. The source is the world row of the active LULUCF source (Melo et al.), which notebook 107 writes. The pipeline holds no observed LULUCF series in the BM convention. When $\text{base} = 2020$, this term is zero. The output column is `rebase_lulucf_mt`.

5. **$\text{gap}(\text{base},\, \text{NZ})$** -- the BM-to-NGHGI convention gap. It covers the years that the published budget covers, from $\text{base}$ to NZ, and replaces BM LULUCF with NGHGI LULUCF for those years. [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) (Methods, Eqs. 2--3) uses the same split: the correction term starts at the reference year of the budget, and earlier years take observed NGHGI LULUCF. This quantity is negative (NGHGI reports a larger land sink than BM), so it reduces the allocatable budget. It is computed per scenario from observed NGHGI LULUCF and scenario AFOLU data (see [Convention gap decomposition](#convention-gap-decomposition)). Notebook 104 stores one median per baseline year in `convention_gap_median_from`. The output column is `correction_lulucf_nghgi_mt`.

6. **$B(2020,\, \text{NZ})$** -- the bunker deduction, same as for co2-ffi.

#### Why the co2 rebase adds NGHGI LULUCF

The target quantity is cumulative fossil CO₂ plus NGHGI LULUCF from 2020 to NZ. The published budget holds fossil CO₂, bunkers and BM LULUCF from $\text{base}$ to NZ.

For 2020 to $\text{base}{-}1$ the rebase adds the observed quantities in the target convention: fossil CO₂, bunkers and NGHGI LULUCF. For $\text{base}$ to NZ the convention gap converts the LULUCF share of the published budget from BM to NGHGI. Each year from 2020 to NZ is converted once. The gap starts at $\text{base}$ because the rebase LULUCF of the earlier years is already in the NGHGI convention.

### Design principle: actual data for the rebase, scenario data for the future

The formulas enforce a strict separation:

| Quantity                                                | Data type                       | Rationale                                                             |
| ------------------------------------------------------- | ------------------------------- | --------------------------------------------------------------------- |
| Fossil rebase ($F_{\text{actual}}$)                     | Actual (e.g. PRIMAP)            | Observed emissions -- no projection uncertainty                       |
| Bunker rebase ($B$, 2020 to $\text{base}{-}1$)          | Actual (GCB bunker series)      | Same rationale                                                        |
| NGHGI LULUCF rebase ($L_{\text{NGHGI}}$, co2 only)      | Actual (Melo et al. world row)  | Same rationale                                                        |
| BM LULUCF decomposition ($L_{\text{BM}}$, co2-ffi only) | Scenario median (AFOLU\|Direct) | Requires future pathway to NZ; no observational data exists           |
| Convention gap ($\text{gap}$, co2 only)                 | Observed NGHGI + scenario data  | Forward-looking NGHGI--BM difference requires modeled indirect fluxes |
| Net-zero year ($\text{NZ}$)                             | Scenario data                   | By definition a future quantity                                       |
| Bunker deduction ($B$)                                  | Observational + extrapolation   | Historical data extended at last observed rate to NZ                  |

This means that adding a new RCB source (e.g., Lamboll et al. with baseline 2023) only requires actual fossil, bunker and, for co2, NGHGI LULUCF data through 2022 for the rebase. The LULUCF decomposition (co2-ffi) and the convention gap (co2) start at $\text{base}$. The bunker deduction covers 2020 to NZ.

The rebase needs a value for every year from 2020 to $\text{base}{-}1$ in each series it adds: fossil emissions, bunkers and, for co2, LULUCF.

#### Placeholder for unobserved rebase years

A series can end before $\text{base}{-}1$. Each later year then takes the last observed value of that series. This fill is a placeholder until observed data are published. `rebase_fill_max_years` in `rcbs.yaml` sets the largest number of years that one series may take this way (default 1; 0 turns the fill off). Every fill raises a warning that names the source, the series, the filled years and the value.

A source that needs more years than the limit is left out of the processed budgets. The pipeline prints one warning that lists the sources left out and their missing years. `forster_2026` (baseline 2026) needs values through 2025. With `gcb-2025` emissions and bunkers (observed to 2024) the rebase fills 2025 with the 2024 values. With PRIMAP (observed to 2023) two years are missing and the source is left out. For `co2`, `forster_2026` also needs NGHGI LULUCF through 2025. With `melo-2026` (ends 2023) two years are missing and the source is left out. With `melo-2026-v4` (ends 2024) the rebase fills 2025 with the 2024 value. `lamboll_2023` and `forster_2024` need no fill with either emissions source.

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

The LULUCF decomposition and the convention gap are integrated per scenario from their start year to the **scenario-specific net-zero year** $t_{\text{nz},i}$, the first year when that scenario's total CO₂ emissions (`Emissions|CO2`) reach zero. This prevents post-net-zero negative emissions from inflating the corrections. The bunker deduction is integrated to the median net-zero year of the scenario set.

Note that `Emissions|CO2` in IAM scenario databases is fossil + BM LULUCF by convention — this is a property of how scenarios report total CO₂, not a methodological choice by fair-shares.

Per-scenario net-zero years are computed from scenario data (e.g. Gidden et al. AR6 reanalysis). Scenario-level summary statistics (median, quartiles) are stored in `rcb_scenario_adjustments.yaml` in the pipeline output directory, keyed by scenario set (e.g., `1.5p50` or `peak-warming-1.7C`; see [RCB sources and scenario sets](#rcb-sources-and-scenario-sets)). The scenario-level median NZ year is used for the bunker integration endpoint (which is observational, not scenario-dependent).

Scenarios that never reach net-zero total CO₂ by 2100 are assigned 2100 as a conservative upper integration bound. This applies to the AR6 category sets (38 of 231 scenarios in C3). The peak-warming band sets hold no such scenario.

### Convention gap decomposition

The per-scenario convention gap $\text{Gap}_i$ runs from the baseline year $\text{base}$ of the RCB source to the net-zero year of the scenario. It decomposes into two temporal segments:

**Observed** ($\text{base} \leq t \leq \mathrm{splice{\_}year}$): NGHGI actual LULUCF (reported values, same for all scenarios) minus BM LULUCF for scenario $i$ (the bookkeeping proxy from scenario data). The splice year is the last year of the NGHGI data (2023 for `melo-2026`, 2024 for `melo-2026-v4`):

$$
\text{Gap}_{i,\text{obs}} = \sum_{t=\text{base}}^{\min(\text{splice},\, t_{\text{nz},i})} \left[\text{NGHGI}_{\text{actual}}(t) - \text{BM}_{\text{Direct},i}(t)\right]
$$

Currently, NGHGI actual LULUCF is sourced from Melo et al. and BM LULUCF from the Gidden et al. AR6 reanalysis (AFOLU|Direct). These are the current data sources for these roles — alternatives providing the same quantities could be substituted.

**Future** ($t > \mathrm{splice{\_}year}$): Only the NGHGI-consistent indirect component for scenario $i$ (CO₂ fertilization and other passive fluxes), because the direct components cancel in the gap:

$$
\text{Gap}_{i,\text{future}} = \sum_{t=\max(\text{base},\, \text{splice}+1)}^{t_{\text{nz},i}} \text{Indirect}_{i}(t)
$$

Currently sourced from the Gidden et al. AR6 reanalysis (AFOLU|Indirect).

A baseline year after the splice year leaves the observed segment empty, and the gap is the indirect component from $\text{base}$. A scenario that reaches net zero before $\text{base}$ has a gap of zero. The years 2020 to $\text{base}{-}1$ are outside the gap: the rebase adds observed NGHGI LULUCF for them ([Weber 2026](https://doi.org/10.1038/s41467-026-69078-9), Methods, Eqs. 2--3).

The total per-scenario gap is $\text{Gap}_i = \text{Gap}_{i,\text{obs}} + \text{Gap}_{i,\text{future}}$, and the median is taken across all scenarios $i$ in the scenario set. Each scenario's integration ends at its own $t_{\text{nz},i}$. Notebook 104 computes one median for each baseline year in `rcbs.yaml` (`convention_gap_median_from` in `rcb_scenario_adjustments.yaml`), and a budget takes the median of its own baseline year. The per-scenario function is `convention_gap_from_baseline()` in `src/fair_shares/library/utils/data/rcb.py`.

**Why per-scenario data for the BM side?** The convention gap is a per-scenario quantity — each scenario has its own AFOLU|Direct pathway, NZ year, and Indirect fluxes. Global Carbon Budget multi-model averages cannot be substituted here because they would collapse the per-scenario variation into a single number, breaking the integrate-per-scenario-then-median methodology. For actual historical emissions (the RCB rebase from baseline to 2020), observational data is used — no scenario data is involved in that step.

**Convention choice for the BM side.** The BM side of the convention gap is the scenario `AFOLU|Direct` flux from the Gidden et al. 2023 reanalysis, also for the observed years from $\text{base}$ to the splice year. An observed mean of bookkeeping models is an alternative for those years. [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) adjusts the Gidden et al. values with the difference between the Global Carbon Budget mean of bookkeeping models and NGHGI-reported values for 2020 to 2023 (Methods, "Calculating a NGHGI-consistent global RCB"). The package holds no observed BM series and makes no such adjustment. Weber et al. also take the mean across scenarios, and the package takes the median.

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
| Observed NGHGI LULUCF      | co2 rebase                             | World row of the LULUCF source, Melo et al. (already in pipeline) |
| Per-year BM LULUCF pathway | co2-ffi LULUCF decomposition           | Scenario data (AFOLU\|Direct median)    |
| Net-zero year              | Integration limit for bunkers + LULUCF | Scenario data                           |
| Convention gap             | co2 BM-to-NGHGI adjustment             | NGHGI + scenario Indirect AFOLU         |
| Bunker fuel timeseries     | Bunker rebase and bunker deduction     | GCB (already in pipeline)               |

The RCB value comes from the publication. Fossil CO₂, NGHGI LULUCF and the bunker timeseries are observational and already in the pipeline. The bunker deduction extends the last observed bunker rate to the median net-zero year. The BM LULUCF pathway, the net-zero year and the convention gap need scenario data for the scenario set of the new source.

### Data sources

| Component          | Source                                        | Coverage                                 |
| ------------------ | --------------------------------------------- | ---------------------------------------- |
| Fossil CO₂         | PRIMAP-hist v2.6.1                            | 1750--present                            |
| NGHGI LULUCF       | Melo et al. (2026) NGHGI LULUCF: v3.1.1 (`melo-2026`, default) or v4.0.0 (`melo-2026-v4`) | 2000--2023, 185 countries + world (v3.1.1); 2000--2024, 187 countries + world (v4.0.0) |
| BM LULUCF proxy    | Gidden et al. AR6 reanalysis, AFOLU\|Direct   | 2015--2100, per scenario within category |
| Passive flux       | Gidden et al. AR6 reanalysis, AFOLU\|Indirect | 2015--2100, per scenario within category |
| Net-zero years     | Gidden et al. AR6 reanalysis, Emissions\|CO2  | Per scenario (first year total CO₂ ≤ 0)  |
| Bunker fuels       | GCB historical + rate extrapolation           | Observed to the last year of the data, then that rate to median NZ |

**[API Reference →](https://setupelz.github.io/fair-shares/api/utils/data/#nghgi-corrections)** | `src/fair_shares/library/utils/data/nghgi.py`

### Worked example: AR6 WG1 1.5C 50% (1.5p50)

Using `ar6_2020` source: 500 GtCO₂ total from 2020, scenario `1.5p50` (70 C1 scenarios, median NZ year ~2050). Values from two pipeline runs with PRIMAP v2025.03 emissions, `gcb-2024` bunkers and Melo v3.1.1 LULUCF (`melo-2026`): `rcbs_co2-ffi.csv` of `primap-202503_wdi-2025_un-owid-2025_wdi-2025_rcbs_co2-ffi` and `rcbs_co2.csv` of `primap-202503_wdi-2025_un-owid-2025_wdi-2025_melo-2026_rcbs_all-ghg`. Each row is rounded, and the totals use unrounded values.

#### Step 1: Weber corrections (RCB to allocatable budget at 2020)

|                               | co2-ffi                | co2                   |
| ----------------------------- | ---------------------- | --------------------- |
| Published RCB (total CO₂)     | 500 Gt                 | 500 Gt                |
| Fossil rebase                 | 0 (base=2020)          | 0 (base=2020)         |
| Bunker rebase                 | 0 (base=2020)          | 0 (base=2020)         |
| NGHGI LULUCF rebase           | --                     | 0 (base=2020)         |
| LULUCF decomposition / gap    | **0** (BM sink capped) | **-90 Gt** (conv gap, 2020--NZ) |
| Bunker subtraction            | -35 Gt                 | -35 Gt                |
| **Allocatable budget (2020)** | **465 Gt**             | **375 Gt**            |

**co2-ffi:** The cumulative BM LULUCF is estimated from AR6 scenarios in the corresponding climate category (here 1.5°C 50th percentile). Each scenario's AFOLU|Direct is integrated from 2020 to its own NZ year, then the median across scenarios is taken. The result is a net sink. Under the **precautionary cap** (default), this sink is not credited to the fossil budget (capped to 0). Without the cap (`precautionary_lulucf: false`), the fossil budget would increase.

**co2:** The convention gap from 2020 to NZ is -90 Gt (`1.5p50` median, -90.3 Gt). NGHGI reports a larger land CO₂ sink than bookkeeping models, which reduces the allocatable budget. The gap is computed from NGHGI actual LULUCF and scenario AFOLU data (see [Convention gap decomposition](#convention-gap-decomposition)). Bunker deduction is ~35 Gt (~870 Mt/yr integrated to median NZ year ~2050). The co2 budget is lower than co2-ffi because the convention gap is a significant negative adjustment.

For [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) (`lamboll_2023`, `1.5p50`, 250 Gt from 2023):

|                               | co2-ffi                | co2                     |
| ----------------------------- | ---------------------- | ----------------------- |
| Published RCB                 | 250 Gt                 | 250 Gt                  |
| Fossil rebase (2020--2022)    | +106.6 Gt              | +106.6 Gt               |
| Bunker rebase (2020--2022)    | +2.8 Gt                | +2.8 Gt                 |
| NGHGI LULUCF rebase (2020--2022) | --                  | -12.1 Gt                |
| LULUCF decomposition / gap    | **0** (BM sink capped) | **-71.2 Gt** (conv gap, 2023--NZ) |
| Bunker subtraction (2020--NZ) | -34.7 Gt               | -34.7 Gt                |
| **Allocatable budget (2020)** | **324.8 Gt**           | **241.5 Gt**            |

The bunker rebase and the bunker subtraction together remove the bunkers of 2023 to NZ (31.8 Gt), the years that the published budget covers. For co2, the rebase adds observed NGHGI LULUCF for 2020 to 2022 (Melo et al. world row, -12.1 Gt), and the convention gap covers 2023 to NZ (`1.5p50` median from 2023, -71.2 Gt).

#### Step 2: Allocation year adjustment

The allocatable budget is the budget **from 2020 onwards**. The `allocation_year` parameter shifts the starting point by adding historical emissions (before 2020) or subtracting already-used emissions (after 2020).

`make dev-pipeline-rcbs` regenerates the co2-ffi values. The co2 values come from a pipeline run with `emission_category=all-ghg` and `active_lulucf_source=melo-2026`.

---

## See Also

- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** -- Design choices
- **[API Reference](https://setupelz.github.io/fair-shares/api/)** -- Function documentation
