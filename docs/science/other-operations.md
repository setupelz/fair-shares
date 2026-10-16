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

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/timeseries.py`

### Cumulative Peak Preservation

Preserves the peak cumulative emissions using time-varying scaling when `preserve_cumulative_peak=True`.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/timeseries.py`

### Post-Net-Zero Handling in Global Pathways

Some AR6 scenario pathways have the **global** emission trajectory going net-negative (i.e., the world as a whole achieves net-negative emissions). The allocation framework cannot meaningfully distribute negative global emissions across countries, so years after the global pathway crosses zero are set to NaN and reported.

This is a preprocessing step applied to global scenario pathways before allocation. Pre-net-zero years are preserved unchanged.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/dataframes.py::set_post_net_zero_emissions_to_nan`

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

**[API Reference →](../api/utils/math.md#rcb-pathway-generation)**

---

## Data Preprocessing

### Interpolation

Fills missing values using linear or stepwise interpolation.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/timeseries.py::interpolate_scenarios_data`

### Unit Conversion

Standardizes units (emissions: kt/Mt/Gt CO2e, population: million).

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/units.py`

---

## Data Validation

### TimeseriesDataFrame Validation

Validates structure (MultiIndex format) and content (non-negative values, complete time series).

**[Implementation →](../api/utils/validation.md)** | `src/fair_shares/library/validation/pipeline_validation.py`

### Cross-Dataset Validation

Verifies analysis countries + ROW = world totals, and ensures temporal/spatial alignment.

**[Implementation →](../api/utils/validation.md)** | `src/fair_shares/library/validation/pipeline_validation.py`

---

## Data Completeness

### Analysis Country Selection

Selects the analysis countries and computes Rest of World (ROW) totals for the remaining countries. A country is an analysis country if it passes two tests:

1. **Completeness.** Each emissions category, GDP and population hold a value for the country in every year from 1990 to the last year of that dataset.
2. **Coverage rule (opt-in).** An emissions source can carry a `coverage` block in `data_sources_unified.yaml`. Only `gcb-2025` sets one: the country needs an emissions record before 1990 and population from 1850. A source without the block applies no extra test.

Gini does not decide membership. An analysis country without a Gini value gets the analysis-country mean under the default `general.gini_missing_policy: fallback-mean`, and `country_data_coverage_summary.csv` records it as imputed. The `strict` policy stops the run instead. Countries that fail a test join ROW, whose rows are the world row minus the analysis countries.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/data/completeness.py`, `src/fair_shares/library/preprocessing/coverage.py`, `src/fair_shares/library/preprocessing/gini.py`

### World Total Extraction

Extracts world totals for validation. Supports keys: "EARTH", "WLD", "World".

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/data/completeness.py`

---

## All-GHG Allocations with RCBs

Remaining carbon budgets constrain **CO₂ only** — they are derived from the
near-linear relationship between cumulative CO₂ emissions and global warming
([IPCC 2021](https://doi.org/10.1017/9781009157896), AR6 WG1; see also
[Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) on budget size and
uncertainty). Each published budget assumes a pathway for the non-CO₂
greenhouse gases (CH₄, N₂O, F-gases). The budget itself covers CO₂ only.

The allocation approaches follow [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122)
and [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). The land-use CO₂
convention follows [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9), and
the pairing with a methane pathway follows
[Weber 2026b](https://doi.org/10.1038/s43247-026-03832-1). The budget depends on
the methane pathway it assumes: an additional sustained linear 10% cut in methane
emissions to 2050 raises the 2°C (50%) budget by about 165 Gt CO₂
([Weber 2026b](https://doi.org/10.1038/s43247-026-03832-1)). The library therefore
takes the non-CO₂ pathway from scenarios of the same climate target as the budget.
A different methane pathway needs a matching budget.

When users request an all-GHG allocation (e.g. `all-ghg` or `all-ghg-ex-co2-lulucf`) but use RCBs as the target source, a problem arises: RCBs constrain CO₂ only and say nothing about non-CO₂ gases. To produce all-GHG results, the system **decomposes** the problem into two components — allocating CO₂ via the budget approach and non-CO₂ via scenario pathways:

| Component | Gas scope          | Allocation method                | Data source              |
| --------- | ------------------ | -------------------------------- | ------------------------ |
| CO₂       | `co2` or `co2-ffi` | Budget approach (RCBs)           | Remaining carbon budgets |
| Non-CO₂   | `non-co2`          | Pathway approach (e.g. AR6 scenarios) | Median pathway of the budget's temperature-matched set |

!!! note "Each budget takes non-CO₂ from its temperature-matched set"

    The non-CO₂ pathway of a budget comes from the scenarios whose median warming at net-zero CO₂ matches the budget temperature, or from its AR6 category (see [RCB sources and scenario sets](#rcb-sources-and-scenario-sets)). Every label in `rcbs.yaml` therefore gets a non-CO₂ pathway. A set below `min_scenarios` raises an error.

### Decomposition rules

The CO₂ component depends on the requested emission category:

- **`all-ghg`** → CO₂ component is `co2` (total CO₂ including LULUCF,
  NGHGI-corrected)
- **`all-ghg-ex-co2-lulucf`** → CO₂ component is `co2-ffi` (fossil only,
  no NGHGI corrections needed)

### Non-CO₂ derivation

Non-CO₂ emissions are not a native category. They are derived by subtraction.
History and scenarios use different inputs.

**Historical emissions (e.g. PRIMAP).** The pipeline subtracts country by
country (`derive_non_co2_country_timeseries()` in
`src/fair_shares/library/utils/data/non_co2.py`):

$$
\text{non-CO}_2 = \text{all-ghg-ex-co2-lulucf} - \text{co2-ffi}
$$

PRIMAP category `M.0.EL` excludes all LULUCF emissions: CO₂, CH₄ and N₂O.
Agriculture (`M.AG`) stays in. So `all-ghg-ex-co2-lulucf` also excludes
LULUCF CH₄ and N₂O. The name is kept for compatibility. The historical
non-CO₂ series therefore holds no LULUCF CH₄ or N₂O.

**AR6 scenarios.** Notebook 104 harmonises each pathway to history and takes
the median of each category over the non-CO₂ set of every budget. It then
subtracts the medians:

$$
\text{non-CO}_2 = \text{median}(\text{all-ghg}) - \text{median}(\text{co2})
$$

The result is a difference of medians. In a decomposition run the two medians
are those of `all-ghg-ex-co2-lulucf` and `co2-ffi`. Notebook 104 writes them
per budget to `scenarios_{category}_by_budget_timeseries.csv`
(`median_pathways_by_budget()` in `src/fair_shares/library/utils/data/scenario_sets.py`).
Each budget gets the median of its own non-CO₂ set (see
[RCB sources and scenario sets](#rcb-sources-and-scenario-sets)). The AR6 non-CO₂ series includes AFOLU
CH₄ and N₂O. Harmonisation to the 2020 historical value removes the level
difference to the historical series at the harmonisation year.

### Scenario labels

Scenario source categories are mapped to clean `climate-assessment` names and `quantile` fields during preprocessing (notebook 104). This normalisation ensures that all downstream code — including non-CO₂ pathways — works with a consistent format regardless of the upstream scenario source. For example, AR6 categories map as:

- C1 → `climate-assessment="1.5C"`, `quantile=0.5`
- C3 → `climate-assessment="2C"`, `quantile=0.67`
- C4 → `climate-assessment="2C"`, `quantile=0.5`

New scenario sources would define their own mapping into the same clean format. Any new data processing notebook that introduces a scenario source must output data in this normalised schema.

Internally, notebook 104 uses combined labels (e.g., "1.5p50") during
median calculation to keep C3 and C4 distinct, then remaps to the clean
format at output. The map follows the AR6 WGIII category definitions (see
[AR6 category pools](#ar6-category-pools)).

The non-CO₂ pathways of a budget target hold one row per budget. Each row
carries the label of the budget as `climate-assessment` and `quantile`, and the
RCB source key as `source`. A budget part pairs with the non-CO₂ part on
`source`, `climate-assessment` and `quantile`. A budget row without a non-CO₂
partner raises an error.

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
`capability_reference_year` and `capability_window`, which pathway approaches
support with the same semantics as budgets. A derived config therefore names exactly the
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

5. **$B(2020,\, \text{NZ})$** -- the bunker deduction. Removes international aviation and shipping emissions that appear in global totals but are excluded from national inventories. Integrated from 2020 to NZ regardless of baseline year. Observed values run to the last year of the bunker data. Later years take a share of the net CO₂ of the budget's scenario set (see [Bunker term](#bunker-term)).

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
L_{\text{BM}}^{\text{capped}} = \max\!\left(0,\; \underset{i}{\text{median}}\int_{\text{base}}^{t_{\text{nz},i}} L_{\text{BM},i}(t)\,dt\right)
$$

The LULUCF decomposition extends from the baseline year to net-zero. Thus we must use the scenario pathways of the volume-matched set of the budget (see [Role-matched scenario sets](#role-matched-scenario-sets)). Each scenario's AFOLU|Direct is integrated from the baseline year to its own net-zero crossing $t_{\text{nz},i}$, then the median across scenarios is taken. The package follows the structure of [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) (Methods, Eqs. 2--3) and differs in two ways: it takes the median across scenarios, and it uses the scenario Direct flux as the bookkeeping side. The paragraph "Convention choice for the BM side" under [Convention gap decomposition](#convention-gap-decomposition) states both. Notebook 104 stores one median per RCB baseline year as `bm_lulucf_median_from` in `rcb_scenario_adjustments.yaml`. When the result is negative (net sink), the cap zeros it out because the sink relies on uncertain future reforestation. Configurable via `precautionary_lulucf` in the adjustments config (default: `true`; set to `false` for sensitivity analysis).

!!! note "Why `convention_gap_median_from` is 0 in CO2-FFI output"
    The `rcb_scenario_adjustments.yaml` file includes a `convention_gap_median_from` field for every budget, with one value per RCB baseline year. For **co2-ffi** allocations, this field is **not used** — the LULUCF adjustment comes from `bm_lulucf_median_from` instead (see above). The convention gap only applies to **co2** allocations, where the budget must switch from the bookkeeping model convention to the NGHGI convention. Its presence in the YAML for co2-ffi scenarios is a storage artefact, not a computational input.

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

with $\text{gap}(a, b) = \int_{a}^{b} \left[L_{\text{NGHGI}}(t) - L_{\text{BM}}(t)\right] dt$.

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
| Net-zero crossing ($\text{NZ}$)                         | Scenario data                   | By definition a future quantity                                       |
| Bunker deduction ($B$)                                  | Observed + bunker share of set CO₂ | Observed to the last year, then a share of the set's net CO₂ to NZ |

This means that adding a new RCB source (e.g., Lamboll et al. with baseline 2023) only requires actual fossil, bunker and, for co2, NGHGI LULUCF data through 2022 for the rebase. The LULUCF decomposition (co2-ffi) and the convention gap (co2) start at $\text{base}$. The bunker deduction covers 2020 to NZ.

The rebase needs a value for every year from 2020 to $\text{base}{-}1$ in each series it adds: fossil emissions, bunkers and, for co2, LULUCF.

#### Placeholder for unobserved rebase years

A series can end before $\text{base}{-}1$. Each later year then takes the last observed value of that series. This fill is a placeholder until observed data are published. `rebase_fill_max_years` in `rcbs.yaml` sets the largest number of years that one series may take this way (default 1; 0 turns the fill off). Every fill raises a warning that names the source, the series, the filled years and the value.

A source that needs more years than the limit is left out of the processed budgets. The pipeline prints one warning that lists the sources left out and their missing years. `forster_2026` (baseline 2026) needs values through 2025. PRIMAP-hist v2.8 (`primap-202609`, observed to 2025) needs no fill. `gcb-2025` emissions and bunkers (observed to 2024) take the 2024 value for 2025. With PRIMAP-hist v2.6.1 (`primap-202503`, observed to 2023) two years are missing and the source is left out. For `co2`, `forster_2026` also needs NGHGI LULUCF through 2025. With `melo-2026-v4` (ends 2024) the rebase fills 2025 with the 2024 value. With `melo-2026` (ends 2023) two years are missing and the source is left out. `lamboll_2023` and `forster_2024` need no fill with any emissions source.

After the last observed year, the bunker deduction takes the bunker share of the set's net CO₂ (see [Bunker term](#bunker-term)). A filled bunker year in the rebase holds the last observed value. The rebase and the deduction can therefore count that year differently. For `forster_2026` with `gcb-2025` bunkers this is the year 2025.

### RCB sources and scenario sets

`data/rcbs/rcbs.yaml` holds five sources. A budget from the start of year $X$ has `baseline_year: X`. All values are in Gt CO₂ of total anthropogenic CO₂.

| Source key     | Publication                                                                          | Budget from   | Likelihood scope | Metric of $T$       | Labels and values |
| -------------- | ------------------------------------------------------------------------------------ | ------------- | ---------------- | ------------------- | ----------------- |
| `lamboll_2023` | [Lamboll et al. 2023](https://doi.org/10.1038/s41558-023-01848-5)                    | Start of 2023 | TCRE, ZEC, ESF   | Peak warming        | `1.5p50` 250, `2p66` 940, `2p90` 500 |
| `forster_2024` | [Forster et al. 2024](https://doi.org/10.5194/essd-16-2625-2024), IGCC 2023, Table 8 | Start of 2024 | TCRE only        | Warming at net zero | `1.5p50` 200, `1.7p50` 550, `1.7p67` 450, `1.7p83` 350, `2p67` 900, `2p83` 750 |
| `ar6_2020`     | IPCC AR6 WGI, Table SPM.2                                                            | Start of 2020 | TCRE only        | Warming at net zero | `1.5p50` 500, `2p67` 1150, `2p83` 900 |
| `forster_2026` | [Forster et al. 2026](https://doi.org/10.5194/essd-18-3889-2026), IGCC 2025, Table 8 | Start of 2026 | TCRE only        | Warming at net zero | `1.5p50` 130, `1.5p67` 80, `1.7p50` 500, `1.7p67` 390, `1.7p83` 300, `1.7p90` 250, `2p67` 860, `2p83` 690, `2p90` 600 |
| `ar6_wg1_2021` | [IPCC AR6 WGI, Table SPM.2](https://doi.org/10.1017/9781009157896.001)               | Start of 2020 | TCRE only        | Warming at net zero | `1.5p50` 500, `1.5p67` 400, `1.7p50` 850, `1.7p67` 700, `1.7p83` 550, `2p67` 1150, `2p83` 900 |

#### What a budget label means

A label `TpL` names a warming level $T$ and a likelihood $L$. Each budget runs from its start year to net-zero CO₂. $T$ is the warming when CO₂ reaches net zero. It equals peak warming when the zero-emissions commitment (ZEC) is zero. [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) defines $T$ as peak warming. The likelihood of AR6 WGI and of the IGCC updates covers the uncertainty of the transient climate response to cumulative emissions (TCRE) only. The likelihood of Lamboll et al. covers TCRE, ZEC and Earth-system feedbacks (ESF). Every published budget assumes the median non-CO₂ warming of scenarios at $T$, for every likelihood. Each source records `likelihood_scope` and `budget_metric` in `rcbs.yaml`, and the processed budget files carry both.

`forster_2024` and `ar6_2020` publish 67% budgets under the label `2p67`. The label `2p66` reads as `2p67` for these two sources with a deprecation warning. Lamboll et al. publish 66%, so `lamboll_2023` keeps `2p66`.

#### Role-matched scenario sets

Each scenario-derived term of a budget takes the scenario set that matches its role:

| Term | Set | Rule | Why |
| ---- | --- | ---- | --- |
| BM LULUCF decomposition (`co2-ffi`) | Volume-matched | Reaches net-zero CO₂ by 2100; cumulative net CO₂ from 2020 to net zero within ±`volume_tolerance_gt` (50 Gt) of the budget from 2020 | The term integrates to net zero, so its scenarios spend the budget's volume |
| Convention gap (`co2`) | Volume-matched | Same | Same |
| Bunkers after the last observed year | Volume-matched, times the bunker share | Median net CO₂ of the set from the year after the last observed year to net zero, times the share $s$ | Few scenarios report bunkers, so $s$ pools every reporter (see [Bunker term](#bunker-term)) |
| Non-CO₂ pathway | Temperature-matched | Harmonised-infilled net-zero year; median warming at net zero in $[T - 0.05,\; T + 0.05)$, for every likelihood | Published budgets assume the median non-CO₂ warming at $T$ |

The temperature-matched set needs a net-zero year because the AR6 at-net-zero columns hold the 2100 value for a scenario that never reaches net zero. A set below `min_scenarios` (10) raises a `ConfigurationError` that names the budget. Fewer than `bunkers.min_reporters` (10) bunker reporters raise one that names the count per scenario source. The settings sit at the top of `rcbs.yaml`. The selection logic is in `src/fair_shares/library/utils/data/scenario_sets.py`.

**Budget from 2020.** The volume-matched set compares each scenario with the budget from the start of 2020: the published value plus observed global net CO₂ from 2020 to the year before the baseline. Observed net CO₂ is fossil CO₂ (including bunkers) minus the cement carbonation sink plus bookkeeping land-use CO₂, from the Global Carbon Budget 2025 workbook (`gcb-2025-global`). The workbook ends in 2024, so `forster_2026` takes the 2024 value for 2025 (`rebase_fill_max_years`).

**Accounting.** Budgets run from the start of 2020, so a cumulative counts every year in full. A scenario series is linear between its reported years, and the value of a year is its flow over that whole year. The net-zero year is the zero crossing of that line, interpolated between the last positive and the first non-positive point. A cumulative to net zero sums the full years from its start to the year before the crossing and adds the fraction of the crossing year (the trapezoid of the line within that year). The same accounting applies to the volume that selects the set, the BM LULUCF term, the convention gap and the bunker term. The functions are `net_zero_crossing()` and `integrate()` in `src/fair_shares/library/utils/data/rcb.py`.

**Consistency record.** `rcb_scenario_adjustments.yaml` records per budget the label as published, the likelihood scope and metric, the rule and size of each set, its median cumulative CO₂ and its median and 67th-percentile warming at net zero, and a check of the two sets: their overlap and the volume gap of the temperature-matched set (its median cumulative CO₂ minus the budget from 2020). For a p50 budget the two sets describe one budget, so a small gap supports the pairing.

#### AR6 category pools

`ar6_2020` and `ar6_wg1_2021` set `scenario_selection: ar6-category`. Their labels with an AR6 WGIII category take the category for every term: `1.5p50` C1, `2p67` C3, `2p50` C4. C1 limits warming to 1.5°C (>50%) with no or limited overshoot, C3 limits warming to 2°C (>67%), and C4 limits warming to 2°C (>50%) ([IPCC AR6 WGIII, Annex III, Table 14](https://doi.org/10.1017/9781009157926.022)). C2 returns warming to 1.5°C after a high overshoot and pairs with no label. The integral terms use the category members that reach net zero, and the non-CO₂ pathway uses every member. The bunker term applies the same bunker share to the net CO₂ of the category set. The other labels of these sources use the role-matched sets.

#### Scenario sets of the default budgets

Counts from the AR6 reanalysis of Gidden et al. (2023), 914 scenarios. Budgets from 2020 and set statistics in Gt CO₂; warming is MAGICCv7.5.3 at net zero.

| Budget | From 2020 | Integral-term set | n | Median cumulative | Median / P67 warming | Non-CO₂ set n | Overlap | Volume gap | Set net CO₂ 2025--NZ |
| ------ | --------- | ----------------- | - | ----------------- | -------------------- | ------------- | ------- | ---------- | -------------------- |
| `lamboll_2023` `1.5p50` | 371 | volume | 14 | 391 | 1.53 / 1.65 | 38 | 10 | +79 | 226 |
| `lamboll_2023` `2p66` | 1061 | volume | 42 | 1040 | 1.82 / 1.99 | 41 | 0 | +339 | 852 |
| `lamboll_2023` `2p90` | 621 | volume | 59 | 623 | 1.64 / 1.77 | 41 | 0 | +779 | 445 |
| `forster_2024` `1.5p50` | 363 | volume | 15 | 390 | 1.53 / 1.63 | 38 | 11 | +87 | 225 |
| `forster_2024` `1.7p50` | 713 | volume | 64 | 719 | 1.68 / 1.82 | 151 | 40 | +57 | 530 |
| `forster_2024` `2p67` | 1063 | volume | 40 | 1041 | 1.82 / 2.01 | 41 | 0 | +337 | 854 |
| `ar6_2020` `1.5p50` | 500 | C1 | 70 | 473 | 1.55 / 1.68 | 70 | 70 | -27 | 293 |
| `ar6_2020` `2p67` | 1150 | C3 | 193 | 834 | 1.72 / 1.88 | 231 | 193 | -316 | 652 |
| `forster_2026` `1.5p50` | 378 | volume | 19 | 403 | 1.54 / 1.67 | 38 | 10 | +72 | 234 |
| `forster_2026` `1.7p50` | 748 | volume | 54 | 744 | 1.70 / 1.84 | 151 | 34 | +22 | 559 |
| `forster_2026` `2p67` | 1108 | volume | 36 | 1134 | 1.86 / 2.02 | 41 | 0 | +292 | 933 |
| `ar6_wg1_2021` `1.7p50` | 850 | volume | 79 | 848 | 1.74 / 1.89 | 151 | 39 | -80 | 662 |

The adjustments file of every run holds the rows of the other labels. Two readings follow from the table. The volume-matched sets of 1.5 and 1.7°C p67 budgets have a 67th-percentile warming at net zero 0.07 to 0.18°C above $T$ (2°C p66 and p67: within 0.02°C of $T$), because the budget likelihood covers TCRE only and the MAGICC percentile covers more uncertainty. C3 scenarios reach net zero with 834 Gt from 2020, well below the 1150 Gt of the AR6 2°C (67%) budget.

Labels left out of the defaults, with their published values and counts:

| Source | Label | Published (Gt) | Reason |
| ------ | ----- | -------------- | ------ |
| `lamboll_2023` | `2p50` | 1220 | No scenario that reaches net zero at that volume reports bunkers |
| `forster_2024` | `1.5p67`, `1.5p83` | 150, 100 | 6 and 3 volume-matched scenarios |
| `forster_2024` | `2p50` | 1100 | No scenario that reaches net zero at that volume reports bunkers |
| `forster_2026` | `1.5p67`, `1.5p83`, `1.5p90` | 80, 30, 10 | 8, 5 and 3 volume-matched scenarios |
| `forster_2026` | `2p50` | 1050 | No scenario that reaches net zero at that volume reports bunkers |
| `ar6_wg1_2021` | `1.5p83` | 300 | 6 volume-matched scenarios |
| `ar6_wg1_2021` | `2p50` | 1350 | AR6 category C4 holds no scenario that reports bunkers |

The 2°C (50%) budgets (1266 to 1344 Gt from 2020) are left out because no scenario that reaches net zero with that much net CO₂ reports bunkers (the reporters reach net zero with at most 1037 Gt from 2020), so the bunker share would rest on scenarios of a different volume.

Notebook 104 keys each budget as `source:label` in `rcb_scenario_adjustments.yaml`, with the scalars and the record. It also writes `scenario_set_{source}_{label}.csv` (the members of the integral-term set with their net-zero crossings and net CO₂ from each possible start year) and `bunker_share_reporters.csv`. The processed budget files carry `published_label`, `likelihood_scope`, `budget_metric`, `scenario_selection`, `budget_2020_gt`, the rule and size of both sets, `nz_year_median` and the bunker-share columns.

#### Bunker term

The deduction counts observed bunkers from 2020 to the last observed year $L$ (`gcb-2025` by default, $L = 2024$). After $L$, bunkers are a share $s$ of net CO₂:

$$
B(2020,\, \text{NZ}) = \sum_{t=2020}^{L} B_{\text{obs}}(t) + s \cdot \underset{i \in \text{set}}{\text{median}}\; C_i(L{+}1,\, t_{\text{nz},i})
$$

$C_i$ is the cumulative net CO₂ of scenario $i$ of the budget's volume-matched set (or AR6 category) from the start of $L{+}1$ to its net-zero crossing. Every scenario of `bunkers.scenario_sources` (default `[ar6, sci]`) that reports international aviation and shipping and reaches net zero gives a ratio $r_k$: its cumulative bunkers over its own net CO₂ (the model's `Emissions|CO2`), both from the start of $L{+}1$ to its net-zero crossing. No historical vetting applies to these reporters: vetting tests 2010--2025 totals, and the share needs the ratio within each model run. The share is family-balanced, the median of the per-family medians: $s = \text{median}_f\, \text{median}_{k \in f}\, r_k$. A family counts only with at least `bunkers.min_runs_per_family` (3) reporters; the record lists the excluded families with their medians and counts. A family is the energy-model stem without version or coupling (`IMAGE 3.2` and `IMAGE 3.3` are IMAGE, `REMIND-MAgPIE 3.2-4.6` is REMIND); `model_families` in `src/fair_shares/conf/scenario_sources.yaml` lists every model, and an unlisted reporter model is a configuration error. Fewer than `bunkers.min_reporters` (10) reporters or `bunkers.min_families` (3) families, counted after the per-family filter, raise a `ConfigurationError`. The functions are `bunker_share()` in `src/fair_shares/library/utils/data/scenario_sets.py` and `bunker_deduction_from_share()` in `src/fair_shares/library/utils/data/nghgi.py`.

The AR6 Scenarios Database has no bunker variable. It reports `Emissions|CO2|Energy|Demand|Transportation|Aviation`, which covers domestic and international flights, and `...|Transportation|Maritime`. AR6 bunkers are 0.6 times aviation plus maritime. The factor 0.6 is the international share of aviation CO₂ that [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) takes from IEA data (58% to 62%). Maritime counts whole as international shipping, as in Weber et al. The series come from the public AR6 Scenarios Database (`ipcc_ar6_bunkers`). 39 of the 914 Gidden et al. scenarios report both variables for 2020 to 2100, all from IMAGE, and 22 of these reach net-zero CO₂ by 2100.

The Scenario Compass ensemble (`sci`, see [Scenario Compass](#scenario-compass)) reports `Emissions|CO2|Energy|Demand|Bunkers` and its international aviation and shipping parts directly, so it takes no aviation share. A scenario takes the total where reported, else the sum of both parts. 116 SCI scenarios report bunkers with a net CO₂ series. Scenarios carried over from AR6 count once.

With `gcb-2025` bunkers ($L = 2024$) the share runs from 2025. 64 reporters reach net zero, 25 AR6 and 39 SCI. Three families have at least 3 runs and count: IMAGE 0.073 (n = 37), REMIND 0.088 (17) and IMACLIM 0.106 (5). Three families stay out: WITCH 0.076 (2), McKinsey 0.097 (2) and LUT-ESTM 0.191 (1). The family-balanced share is $s = 0.088$; the median over all 64 reporters is 0.077 (interquartile range 0.072 to 0.095). PROMETHEUS reports bunkers but its runs end in 2050 without net zero. The 1.5°C (50%) budgets thus deduct 4.96 Gt of observed bunkers (2020--2024) plus 0.088 times 225 to 293 Gt of set net CO₂.

The share ties the bunker term to the volume of the budget: a set with more net CO₂ after $L$ takes more bunkers. Reporters of both sources enter with their own emissions and the same accounting. A source whose data file is absent is left out with a warning. `bunker_share_reporters.csv` holds each reporter's cumulative bunkers and net CO₂ from every possible start year, and the processed budget files carry `bunker_share`, `bunker_share_pooled`, the interquartile range of the ratios, the family medians and counts (`bunker_share_families`), the reporter counts by source and the set's net CO₂ after $L$ (`bunker_set_co2_after_mt`).

#### Scenario Compass

The Scenario Compass Initiative pathways ensemble ([Huppmann et al. 2026](https://doi.org/10.5281/zenodo.18598251), v1.0; manuscript [Riahi et al. 2026](https://doi.org/10.21203/rs.3.rs-8891091/v1)) is a registered scenario source (`sci` in `scenario_sources.yaml`, `sci-2025` in the data registry). The workbook states that the data "may be used for scientific research purposes. However, users must strictly adhere to the applicable Nature editorial policies and embargo rules until the manuscript has been formally published." The file is a manual download, never committed, and the version in `scenario_sources.yaml` selects it (`data/scenarios/sci-2025-v1.0/`).

v1.0 holds 1,599 scenarios with global timeseries, 347 of them pass the SCI 2025 vetting. Its metadata carry peak warming and warming in 2100 (33rd, 50th and 67th percentiles), exceedance probabilities, AR6 and SCI categories and the net-zero year, and no warming at net zero. The source therefore supplies bunker reporters only, without the vetting filter. Scenarios carried over from AR6 count once when `ar6` is also a bunker source.

#### Deviations from Weber et al. (2026)

The package follows the structure of [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) (Methods, Eqs. 2--3). The remaining deviations are:

1. Scenario sets. Weber et al. use AR6 C1 scenarios for 1.5°C (50%) and C3 for 2°C (66%). The package uses these categories for the AR6 sources and role-matched sets for the other sources.
2. Statistic. Weber et al. take the mean across scenarios for the LULUCF and bunker terms. The package takes the median.
3. LULUCF bookkeeping side. Weber et al. adjust the Gidden et al. values with the difference between the Global Carbon Budget bookkeeping mean and NGHGI-reported values for 2020 to 2023. The package uses the scenario `AFOLU|Direct` flux without that adjustment.
4. Bunker term. Weber et al. take the bunker pathways of the C1 or C3 scenarios that report aviation and maritime (8 and 9 scenarios). The package applies a family-balanced bunker share of net CO₂ to the scenario set of every budget, AR6 categories included.
5. Accounting. The package counts full years to an interpolated net-zero crossing for every term.

### Why two LULUCF conventions matter

Bookkeeping models (e.g., BLUE, OSCAR) estimate only **direct human-caused** land-use fluxes -- deforestation, afforestation, land management. NGHGIs additionally include **indirect effects** such as CO₂ fertilization of managed forests and climate-driven changes in soil carbon. The NGHGI total is therefore systematically different from the bookkeeping total, even for the same physical land area.

The global difference is substantial: NGHGI-reported LULUCF is a larger net sink than BM estimates, creating a 5--7 GtCO₂/yr discrepancy primarily because CO₂ fertilization enhances carbon uptake on managed land [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9).

### Per-scenario net-zero years as integration bounds

The LULUCF decomposition, the convention gap and the bunker deduction are integrated per scenario from their start year to the **scenario-specific net-zero crossing** $t_{\text{nz},i}$, where that scenario's total CO₂ emissions (`Emissions|CO2`) first reach zero. The crossing is interpolated linearly between the reported years. This prevents post-net-zero negative emissions from inflating the corrections.

Note that `Emissions|CO2` in IAM scenario databases is fossil + BM LULUCF by convention — this is a property of how scenarios report total CO₂, not a methodological choice by fair-shares.

Per-scenario net-zero crossings are computed from the CO₂ series of the scenario source (the Gidden et al. AR6 reanalysis for `ar6`). Notebook 104 writes them per budget to `scenario_set_{source}_{label}.csv`. Every integral-term set holds only scenarios that reach net zero by 2100: the volume-matched set by its rule, and an AR6 category pool by keeping its members that reach net zero for the integral terms (193 of the 231 C3 scenarios).

### Convention gap decomposition

The per-scenario convention gap $\text{Gap}_i$ runs from the baseline year $\text{base}$ of the RCB source to the net-zero year of the scenario. It decomposes into two temporal segments:

**Observed** ($\text{base} \leq t \leq \mathrm{splice{\_}year}$): NGHGI actual LULUCF (reported values, same for all scenarios) minus BM LULUCF for scenario $i$ (the bookkeeping proxy from scenario data). The splice year is the last year of the NGHGI data (2023 for `melo-2026`, 2024 for `melo-2026-v4`):

$$
\text{Gap}_{i,\text{obs}} = \int_{\text{base}}^{\min(\text{splice},\, t_{\text{nz},i})} \left[\text{NGHGI}_{\text{actual}}(t) - \text{BM}_{\text{Direct},i}(t)\right] dt
$$

Currently, NGHGI actual LULUCF is sourced from Melo et al. and BM LULUCF from the Gidden et al. AR6 reanalysis (AFOLU|Direct). These are the current data sources for these roles — alternatives providing the same quantities could be substituted.

**Future** ($t > \mathrm{splice{\_}year}$): Only the NGHGI-consistent indirect component for scenario $i$ (CO₂ fertilization and other passive fluxes), because the direct components cancel in the gap:

$$
\text{Gap}_{i,\text{future}} = \int_{\max(\text{base},\, \text{splice})}^{t_{\text{nz},i}} \text{Indirect}_{i}(t)\, dt
$$

Each year counts in full, and the net-zero year adds its fraction (see the accounting under [Role-matched scenario sets](#role-matched-scenario-sets)).

Currently sourced from the Gidden et al. AR6 reanalysis (AFOLU|Indirect).

A baseline year after the splice year leaves the observed segment empty, and the gap is the indirect component from $\text{base}$. A scenario that reaches net zero before $\text{base}$ has a gap of zero. The years 2020 to $\text{base}{-}1$ are outside the gap: the rebase adds observed NGHGI LULUCF for them ([Weber 2026](https://doi.org/10.1038/s41467-026-69078-9), Methods, Eqs. 2--3).

The total per-scenario gap is $\text{Gap}_i = \text{Gap}_{i,\text{obs}} + \text{Gap}_{i,\text{future}}$, and the median is taken across all scenarios $i$ in the volume-matched set or AR6 category of the budget. Each scenario's integration ends at its own $t_{\text{nz},i}$. Notebook 104 computes one median for each baseline year in `rcbs.yaml` (`convention_gap_median_from` in `rcb_scenario_adjustments.yaml`), and a budget takes the median of its own baseline year. The per-scenario function is `convention_gap_from_baseline()` in `src/fair_shares/library/utils/data/rcb.py`.

**Why per-scenario data for the BM side?** The convention gap is a per-scenario quantity — each scenario has its own AFOLU|Direct pathway, NZ year, and Indirect fluxes. Global Carbon Budget multi-model averages cannot be substituted here because they would collapse the per-scenario variation into a single number, breaking the integrate-per-scenario-then-median methodology. For actual historical emissions (the RCB rebase from baseline to 2020), observational data is used — no scenario data is involved in that step.

**Convention choice for the BM side.** The BM side of the convention gap is the scenario `AFOLU|Direct` flux from the Gidden et al. 2023 reanalysis, also for the observed years from $\text{base}$ to the splice year. An observed mean of bookkeeping models is an alternative for those years. [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) adjusts the Gidden et al. values with the difference between the Global Carbon Budget mean of bookkeeping models and NGHGI-reported values for 2020 to 2023 (Methods, "Calculating a NGHGI-consistent global RCB"). The package holds no observed BM series and makes no such adjustment. Weber et al. also take the mean across scenarios, and the package takes the median.

### World CO₂ timeseries for backward extension

When the allocation year is before 2020, historical emissions must be added back to the RCB (see [RCB Pathway Generation](#rcb-pathway-generation) above). For total CO₂, the per-year world emissions use the NGHGI convention:

$$
E_{\text{world}}(t) = E_{\text{fossil}}(t) + \text{LULUCF}(t)
$$

$E_{\text{fossil}}$ is the world fossil series, which excludes international bunkers. The series therefore matches the adjusted budget, which holds no bunker emissions. `build_nghgi_world_co2_timeseries()` and the preprocessing notebooks build the same series.

Where LULUCF uses:

- **2000 onwards**: NGHGI LULUCF, nationally aggregated inventory data: LULUCF Data Hub v4.0.0 (`melo-2026-v4`, default, 2000--2024) or v3.1.1 (`melo-2026`, opt-in, 2000--2023)
- **Pre-2000**: Not available in NGHGI convention. Categories including LULUCF are limited to the NGHGI data range (2000+). No NGHGI/BM splicing is performed. While earlier NGHGI LULUCF estimates may exist (e.g., historical extensions of Melo), the official NGHGI data begins in 2000. Extending to 1990 would require splicing heterogeneous datasets, which risks introducing artefacts (the BM-to-NGHGI transition around 1990 shows a large jump). We plan to extend coverage when validated pre-2000 NGHGI LULUCF data becomes available.

This ensures the world timeseries passed to `calculate_budget_from_rcb` is NGHGI-consistent, and that function works identically for both `co2-ffi` and `co2` categories. An allocation year before the first year of the world series raises an error that names the first available year.

### Data requirements for new scenario sources

When adding a new RCB source (e.g., a new publication with a different baseline year or scenario set), the following data are needed:

| Data needed                | Used for                               | Source                                  |
| -------------------------- | -------------------------------------- | --------------------------------------- |
| RCB value + baseline year  | Starting point                         | Published literature                    |
| Actual fossil CO₂          | Rebase                                 | e.g. PRIMAP (already in pipeline)       |
| Observed NGHGI LULUCF      | co2 rebase                             | World row of the LULUCF source, Melo et al. (already in pipeline) |
| Per-scenario BM LULUCF     | co2-ffi LULUCF decomposition           | Scenario data (AFOLU\|Direct)           |
| Net-zero crossing          | Integration limit for bunkers + LULUCF | Scenario data                           |
| Observed global net CO₂    | Budget from 2020 for the volume match  | Global Carbon Budget 2025 workbook      |
| Convention gap             | co2 BM-to-NGHGI adjustment             | NGHGI + scenario Indirect AFOLU         |
| Bunker fuel timeseries     | Bunker rebase and bunker deduction     | GCB (already in pipeline)               |
| Scenario bunker pathways   | Bunker share of net CO₂ after the last observed year | Scenario data (aviation and shipping CO₂) |
| Median warming at net zero | Temperature-matched non-CO₂ set        | Scenario metadata                       |

The RCB value comes from the publication. Fossil CO₂, NGHGI LULUCF and the bunker timeseries are observational and already in the pipeline. The BM LULUCF term, the net-zero crossing, the convention gap and the set net CO₂ behind the bunker term need scenario data for the sets of the new budget.

A new scenario source is an entry in `src/fair_shares/conf/scenario_sources.yaml`. The entry names the world variables for CO₂, AFOLU Direct and Indirect, Kyoto gases (with the NGHGI variants), the CO₂ series of the volume match, the bunker variables, the metadata columns (net-zero year, median and 67th-percentile warming at net zero, category) and the terms it supplies. Scenario Compass plugs in this way for the bunker share; the public ScenarioMIP (CMIP7) set can follow.

### Data sources

| Component          | Source                                        | Coverage                                 |
| ------------------ | --------------------------------------------- | ---------------------------------------- |
| Fossil CO₂         | PRIMAP-hist v2.8 (`primap-202609`, default), PRIMAP-hist v2.6.1 (`primap-202503`, opt-in) or GCB 2025 fossil CO₂ (`gcb-2025`, opt-in, `co2-ffi` only) | 1850--2025 (PRIMAP v2.8, as processed); 1850--2023 (PRIMAP v2.6.1); 1850--2024 (GCB) |
| NGHGI LULUCF       | Melo et al. (2026) NGHGI LULUCF: v4.0.0 (`melo-2026-v4`, default) or v3.1.1 (`melo-2026`, opt-in) | 2000--2023, 185 countries + world (v3.1.1); 2000--2024, 187 countries + world (v4.0.0) |
| BM LULUCF proxy    | Gidden et al. AR6 reanalysis, AFOLU\|Direct   | 2015--2100, per scenario of the set      |
| Passive flux       | Gidden et al. AR6 reanalysis, AFOLU\|Indirect | 2015--2100, per scenario of the set      |
| Net-zero crossings | Gidden et al. AR6 reanalysis, Emissions\|CO2  | Per scenario, interpolated zero crossing |
| Budget from 2020   | Global Carbon Budget 2025 global workbook (`gcb-2025-global`) | 1959--2024; 2025 takes the 2024 value |
| Bunker fuels       | GCB 2025 (`gcb-2025`), then a bunker share of the set's net CO₂ (AR6 and Scenario Compass reporters) | Observed to 2024, then the share times the set's median net CO₂ from 2025 to NZ |

**[API Reference →](../api/utils/data.md#nghgi-corrections)** | `src/fair_shares/library/utils/data/nghgi.py`

### Worked example: AR6 WG1 1.5C 50% (1.5p50)

Using `ar6_2020` source: 500 GtCO₂ total from 2020, label `1.5p50`. It takes AR6 category C1: 70 scenarios, all reaching net zero. Values from two pipeline runs on the default sources, PRIMAP-hist v2.8 (`primap-202609`), LULUCF Data Hub v4.0.0 (`melo-2026-v4`) and `gcb-2025` bunkers: `rcbs_co2-ffi.csv` of `primap-202609_wdi-2025_un-owid-2025_wdi-2025_rcbs_co2-ffi` and `rcbs_co2.csv` of `primap-202609_wdi-2025_un-owid-2025_wdi-2025_melo-2026-v4_rcbs_all-ghg`, both run on 2026-10-16. Each row is rounded, and the totals use unrounded values.

#### Step 1: Weber corrections (RCB to allocatable budget at 2020)

|                               | co2-ffi                | co2                   |
| ----------------------------- | ---------------------- | --------------------- |
| Published RCB (total CO₂)     | 500 Gt                 | 500 Gt                |
| Fossil rebase                 | 0 (base=2020)          | 0 (base=2020)         |
| Bunker rebase                 | 0 (base=2020)          | 0 (base=2020)         |
| NGHGI LULUCF rebase           | --                     | 0 (base=2020)         |
| LULUCF decomposition / gap    | **0** (BM sink capped) | **-91.4 Gt** (conv gap, 2020--NZ) |
| Bunker subtraction            | -30.7 Gt               | -30.7 Gt              |
| **Allocatable budget (2020)** | **469.3 Gt**           | **377.9 Gt**          |

**co2-ffi:** Each scenario's AFOLU|Direct is cumulated from 2020 to its own net-zero crossing, then the median across the 70 scenarios is taken (-48.4 Gt). The result is a net sink. Under the **precautionary cap** (default), this sink is not credited to the fossil budget (capped to 0). Without the cap (`precautionary_lulucf: false`), the fossil budget would increase.

**co2:** The convention gap from 2020 to NZ is -91.4 Gt (median of the category). NGHGI reports a larger land CO₂ sink than bookkeeping models, which reduces the allocatable budget. The gap is computed from NGHGI actual LULUCF and scenario AFOLU data (see [Convention gap decomposition](#convention-gap-decomposition)). The bunker deduction is 30.7 Gt: observed bunkers for 2020 to 2024 (5.0 Gt), plus the family-balanced bunker share 0.088 times the median net CO₂ of C1 from 2025 to net zero (292.9 Gt).

For [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) (`lamboll_2023`, `1.5p50`, 250 Gt from 2023). The budget from 2020 is 371 Gt (250 Gt plus 121 Gt of observed global net CO₂ in 2020--2022). Its volume-matched set holds 14 scenarios with cumulative net CO₂ from 2020 to net zero within 321--421 Gt (median crossing 2046.2) and 225.6 Gt of median net CO₂ from 2025 to net zero.

|                               | co2-ffi                | co2                     |
| ----------------------------- | ---------------------- | ----------------------- |
| Published RCB                 | 250 Gt                 | 250 Gt                  |
| Fossil rebase (2020--2022)    | +107.6 Gt              | +107.6 Gt               |
| Bunker rebase (2020--2022)    | +2.7 Gt                | +2.7 Gt                 |
| NGHGI LULUCF rebase (2020--2022) | --                  | -13.1 Gt                |
| LULUCF decomposition / gap    | **0** (BM sink capped) | **-57.7 Gt** (conv gap, 2023--NZ) |
| Bunker subtraction (2020--NZ) | -24.7 Gt               | -24.7 Gt                |
| **Allocatable budget (2020)** | **335.6 Gt**           | **264.8 Gt**            |

The bunker rebase and the bunker subtraction together remove the bunkers of 2023 to NZ (22.0 Gt), the years that the published budget covers. For co2, the rebase adds observed NGHGI LULUCF for 2020 to 2022 (LULUCF Data Hub world row, -13.1 Gt), and the convention gap covers 2023 to NZ (median from 2023, -57.7 Gt).

#### Step 2: Allocation year adjustment

The allocatable budget is the budget **from 2020 onwards**. The `allocation_year` parameter shifts the starting point by adding historical emissions (before 2020) or subtracting already-used emissions (after 2020).

The co2-ffi values come from a pipeline run with `emission_category=co2-ffi`, `active_emissions_source=primap-202609` and `active_target_source=rcbs`. The co2 values come from a run with `emission_category=all-ghg` and `active_lulucf_source=melo-2026-v4`.

---

## See Also

- **[Allocation Approaches](allocations.md)** -- Design choices
- **[API Reference](../api/index.md)** -- Function documentation
