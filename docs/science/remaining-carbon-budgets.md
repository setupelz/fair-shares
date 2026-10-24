---
title: Remaining carbon budgets
description: How fair-shares turns a published global carbon budget into the budget it allocates to countries
---

# Remaining carbon budgets

A remaining carbon budget is the net CO₂ the world can still emit from a start year until CO₂ reaches net zero.
Each budget holds warming to a stated level with a stated likelihood.
fair-shares takes a published budget and adjusts it to match what countries report in their national inventories.
The adjustments follow [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9).

**In short:**

- The library ships budgets from IPCC AR6 WGI, Lamboll et al. (2023) and the Indicators of Global Climate Change updates (Forster et al. 2024 and 2026).
- Every budget is rebased to start in 2020 with observed emissions.
- International aviation and shipping (bunkers) are deducted because national inventories report them only as memo items outside their national totals.
- For fossil CO₂ (`co2-ffi`), the land-use share of the budget is removed. A projected land sink never adds to the fossil budget.
- For total CO₂ (`co2`), land-use CO₂ switches to the national-inventory convention. This lowers the budget.

---

## Published budgets {#published-budgets}

`data/rcbs/rcbs.yaml` holds five sources.
All values are in Gt CO₂ of total anthropogenic CO₂: fossil, bunkers and land use.
A budget from the start of year $X$ has `baseline_year: X`.

| Source key     | Publication | Budget from |
| -------------- | ----------- | ----------- |
| `ar6_2020`     | [IPCC 2021 SPM](https://doi.org/10.1017/9781009157896.001), Table SPM.2 | Start of 2020 |
| `ar6_wg1_2021` | [IPCC 2021 SPM](https://doi.org/10.1017/9781009157896.001), Table SPM.2 | Start of 2020 |
| `lamboll_2023` | [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) | Start of 2023 |
| `forster_2024` | [Forster 2024](https://doi.org/10.5194/essd-16-2625-2024), IGCC 2023, Table 8 | Start of 2024 |
| `forster_2026` | [Forster 2026](https://doi.org/10.5194/essd-18-3889-2026), IGCC 2025, Table 8 | Start of 2026 |

A label such as `1.5p50` names a warming level (1.5 °C) and a likelihood (50%).
What the warming level measures and what the likelihood covers differ between sources.
[What a budget label means](scenario-sets.md#what-a-budget-label-means) explains both.

??? info "Labels and published values (Gt CO₂)"

    | Source key     | Labels and values |
    | -------------- | ----------------- |
    | `ar6_2020`     | `1.5p50` 500, `2p67` 1150, `2p83` 900 |
    | `ar6_wg1_2021` | `1.5p50` 500, `1.5p67` 400, `1.7p50` 850, `1.7p67` 700, `1.7p83` 550, `2p67` 1150, `2p83` 900 |
    | `lamboll_2023` | `1.5p50` 250, `2p66` 940, `2p90` 500 |
    | `forster_2024` | `1.5p50` 200, `1.7p50` 550, `1.7p67` 450, `1.7p83` 350, `2p67` 900, `2p83` 750 |
    | `forster_2026` | `1.5p50` 130, `1.5p67` 80, `1.7p50` 500, `1.7p67` 390, `1.7p83` 300, `1.7p90` 250, `2p67` 860, `2p83` 690, `2p90` 600 |

---

## From published budget to allocatable budget {#allocatable-budget}

A published budget counts total CO₂ from its own baseline year.
Its land-use CO₂ follows the bookkeeping-model (BM) convention.
National inventories count land use differently and leave out bunkers.
Three adjustments close these gaps:

1. **Rebase to 2020.** Observed emissions fill the years from 2020 to the baseline year.
2. **Bunker deduction.** Bunker CO₂ from 2020 to net zero leaves the budget.
3. **Land-use term.** For `co2-ffi`, the land-use share of the budget leaves the budget. For `co2`, land-use CO₂ switches from the BM convention to the national-inventory (NGHGI) convention.


??? note "Equations"

    | Symbol | Definition |
    | ------ | ---------- |
    | $\text{RCB}_{\text{BM}}(\text{base})$ | Published budget from the baseline year, in BM convention |
    | $F_{\text{actual}}(a, b)$ | Cumulative observed fossil CO₂ without international bunkers, years $a$ to $b$ (e.g. PRIMAP) |
    | $L_{\text{BM}}(a, b)$ | Cumulative BM land-use CO₂ from the scenario median (AFOLU\|Direct), years $a$ to $b$ |
    | $L_{\text{NGHGI}}(a, b)$ | Cumulative observed NGHGI land-use CO₂ (world row of the LULUCF source, Melo et al.), years $a$ to $b$ |
    | $B(a, b)$ | Cumulative international bunker CO₂, years $a$ to $b$ |
    | $\text{gap}(a, b)$ | Cumulative NGHGI minus BM convention gap for CO₂, years $a$ to $b$ |
    | $\text{NZ}$ | Net-zero year (from scenario data) |
    | $\text{base}$ | Baseline year of the budget (e.g. 2023 for Lamboll, 2020 for AR6 WGI) |

    Fossil-only budget (`co2-ffi`):

    $$
    \mathrm{fossil{\_}budget}(2020) = \text{RCB}_{\text{BM}}(\text{base})
      + F_{\text{actual}}(2020,\, \text{base}{-}1)
      + B(2020,\, \text{base}{-}1)
      - L_{\text{BM}}(\text{base},\, \text{NZ})
      - B(2020,\, \text{NZ})
    $$

    Total CO₂ budget (`co2`):

    $$
    \mathrm{nghgi{\_}budget}(2020) = \text{RCB}_{\text{BM}}(\text{base})
      + F_{\text{actual}}(2020,\, \text{base}{-}1)
      + B(2020,\, \text{base}{-}1)
      + L_{\text{NGHGI}}(2020,\, \text{base}{-}1)
      + \text{gap}(\text{base},\, \text{NZ})
      - B(2020,\, \text{NZ})
    $$

    with $\text{gap}(a, b) = \int_{a}^{b} \left[L_{\text{NGHGI}}(t) - L_{\text{BM}}(t)\right] dt$.

    The `co2` case has no land-use decomposition. Its land use stays in the budget and changes convention.

??? info "Which data feed each term"

    The past uses observed data. Scenario data enter only for future quantities.

    | Term | Data | Coverage |
    | ---- | ---- | -------- |
    | Fossil rebase ($F_{\text{actual}}$) | PRIMAP-hist v2.8 (`primap-202609`, default), v2.6.1 (`primap-202503`) or GCB 2025 (`gcb-2025`, `co2-ffi` only) | 1850 to 2025 (v2.8); 1850 to 2023 (v2.6.1); 1850 to 2024 (GCB) |
    | Bunker rebase and observed bunkers ($B$) | GCB 2025 (`gcb-2025`) | to 2024 |
    | NGHGI land-use rebase ($L_{\text{NGHGI}}$, `co2` only) | Melo et al. (2026) world row: v4.0.0 (`melo-2026-v4`, default) or v3.1.1 (`melo-2026`) | 2000 to 2024, 187 countries (v4.0.0); 2000 to 2023, 185 countries (v3.1.1) |
    | BM land-use term ($L_{\text{BM}}$, `co2-ffi` only) | Gidden et al. AR6 reanalysis, scenario median of AFOLU\|Direct | 2015 to 2100 |
    | Convention gap (`co2` only) | Observed NGHGI, then AFOLU\|Indirect from the same reanalysis | 2015 to 2100 |
    | Net-zero crossing (NZ) | The same reanalysis, Emissions\|CO2 | Interpolated per scenario |
    | Future bunkers | A bunker share of the set's median net CO₂ (AR6, Scenario Compass and ScenarioMIP scenarios that report bunkers) | From 2025 to net zero |
    | Budget from 2020 | Global Carbon Budget 2025 global workbook (`gcb-2025-global`) | 1959 to 2024; 2025 takes the 2024 value |

    **[API Reference →](../api/utils/data.md#nghgi-corrections)** | `src/fair_shares/library/utils/data/nghgi.py`, `src/fair_shares/library/utils/data/rcb.py`

### Rebase to 2020 {#rebase-to-2020}

The rebase moves the start of every budget to 2020.
A budget published from a later year gets back the observed emissions of 2020 to the year before its baseline:

- **Fossil CO₂.** The world fossil series leaves out international bunkers. The PRIMAP world total equals the sum of its countries. The `gcb-2025` world row is the GCB global total minus bunkers.
- **Bunkers.** The published budget holds bunkers, and the fossil series does not. The output column is `rebase_bunkers_mt`.
- **Land-use CO₂ (`co2` only).** Observed land-use CO₂ in the NGHGI convention, from the world row of the active LULUCF source (Melo et al.), which notebook 107 writes. The output column is `rebase_lulucf_mt`.

For a budget from 2020 every rebase term is zero.

??? note "Why the `co2-ffi` rebase adds no land-use CO₂"

    The published budget is in the BM convention, so a full rebase would add BM land-use CO₂ for 2020 to $\text{base}{-}1$.
    The decomposition would then remove BM land-use CO₂ for 2020 to NZ:

    $$
    L_{\text{BM}}(2020,\, \text{base}{-}1) - L_{\text{BM}}(2020,\, \text{NZ}) = -L_{\text{BM}}(\text{base},\, \text{NZ})
    $$

    The years 2020 to $\text{base}{-}1$ cancel.
    The formula therefore omits land use from the rebase and starts the decomposition at $\text{base}$.
    This form suits the pipeline because it needs no observed land-use series in the BM convention.

??? note "Why the `co2` rebase adds NGHGI land-use CO₂"

    The target quantity is cumulative fossil CO₂ plus NGHGI land-use CO₂ from 2020 to NZ.
    The published budget holds fossil CO₂, bunkers and BM land-use CO₂ from $\text{base}$ to NZ.

    For 2020 to $\text{base}{-}1$ the rebase adds the observed quantities in the target convention: fossil CO₂, bunkers and NGHGI land-use CO₂.
    For $\text{base}$ to NZ the convention gap converts the land-use share of the published budget from BM to NGHGI.
    Each year from 2020 to NZ is converted once.

??? info "Years without observed data"

    The rebase needs a value for every year from 2020 to $\text{base}{-}1$ in each series it adds.
    When a series ends earlier, each later year takes its last observed value, with a warning that names the source, series, years and value.
    This fill is a placeholder until observed data are published.
    `rebase_fill_max_years` in `rcbs.yaml` caps the filled years per series (default 1; 0 turns the fill off). A source that needs more is left out of the processed budgets, with one warning listing it.

    | Budget | Emissions or land-use source | Fill |
    | ------ | ---------------------------- | ---- |
    | `forster_2026` (baseline 2026) | `primap-202609` (to 2025) | none |
    | `forster_2026` | `gcb-2025` emissions and bunkers (to 2024) | 2025 takes the 2024 value |
    | `forster_2026` | `primap-202503` (to 2023) | two years missing: left out |
    | `forster_2026`, `co2` | `melo-2026-v4` (to 2024) | 2025 takes the 2024 value |
    | `forster_2026`, `co2` | `melo-2026` (to 2023) | two years missing: left out |
    | `lamboll_2023`, `forster_2024` | any | none |

    After the last observed year the bunker deduction uses the bunker share, while a filled rebase year holds the last observed value. The two can count that year differently: 2025 for `forster_2026` with `gcb-2025` bunkers.

### Bunker deduction {#bunker-deduction}

International aviation and shipping count towards global emission totals but national inventories report them only as memo items outside their national totals.
The deduction removes them from 2020 to net zero, for every baseline year.

Observed bunkers count from 2020 to the last observed year $L$ (`gcb-2025` by default, $L = 2024$).
After $L$, bunkers are a share $s$ of the median net CO₂ of the budget's scenario set.
The share comes from every scenario that reports bunkers, balanced across model families ([Bunker share](scenario-sets.md#bunker-share)).
With the default sources $s = 0.072$.
The 1.5 °C (50%) budgets thus deduct 4.96 Gt of observed bunkers (2020 to 2024) plus 0.072 times 225 to 293 Gt of set net CO₂.
A set with more net CO₂ after $L$ takes more bunkers.

??? note "Equation and why the rebase adds bunkers"

    $$
    B(2020,\, \text{NZ}) = \sum_{t=2020}^{L} B_{\text{obs}}(t) + s \cdot \underset{i \in \text{set}}{\text{median}}\; C_i(L{+}1,\, t_{\text{nz},i})
    $$

    $C_i$ is the cumulative net CO₂ of scenario $i$ of the budget's volume-matched set (or AR6 category) from the start of $L{+}1$ to its net-zero crossing.

    The two bunker terms count each bunker year once.
    The bunker rebase restores the published budget to a total-CO₂ budget from 2020.
    The deduction then removes every bunker year from 2020 to NZ:

    $$
    B(2020,\, \text{base}{-}1) - B(2020,\, \text{NZ}) = -B(\text{base},\, \text{NZ})
    $$

    The years 2020 to $\text{base}{-}1$ cancel, and the net deduction covers the years that the published budget holds.
    The result is the budget from 2020 without any bunker emissions, for every baseline year.

    The function is `bunker_deduction_from_share()` in `src/fair_shares/library/utils/data/nghgi.py`.

### Land-use term for fossil CO₂ {#land-use-term}

A published budget includes land-use CO₂.
A fossil-only budget removes the land-use share from the baseline year to net zero.
No observation covers these future years, so the term comes from scenarios.
Each scenario of the budget's volume-matched set ([Role-matched scenario sets](scenario-sets.md#role-matched-scenario-sets)) gives its cumulative `AFOLU|Direct` flux from the baseline year to its own net-zero crossing.
The term is the median across these scenarios.
Notebook 104 stores one median per baseline year as `bm_lulucf_median_from` in `rcb_scenario_adjustments.yaml`.

A **precautionary cap** (default on) keeps a projected land sink from adding to the fossil budget.
A net land source still reduces it.
The sink relies on uncertain future reforestation, so the cap sets a net sink to zero.
`precautionary_lulucf: false` in the adjustments config turns the cap off for sensitivity analysis.

??? note "Equation"

    $$
    L_{\text{BM}}^{\text{capped}} = \max\!\left(0,\; \underset{i}{\text{median}}\int_{\text{base}}^{t_{\text{nz},i}} L_{\text{BM},i}(t)\,dt\right)
    $$

    The structure follows [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) (Methods, Eqs. 2 and 3).
    [Differences from Weber et al. (2026)](#differences-from-weber) lists where the package departs from it.

`rcb_scenario_adjustments.yaml` also holds `convention_gap_median_from` for every budget. Only `co2` allocations read it.

### National-inventory convention gap for total CO₂ {#convention-gap}

Bookkeeping models (e.g. BLUE, OSCAR) estimate only **direct** human-caused land-use fluxes: deforestation, afforestation and land management.
National inventories (NGHGIs) also count **indirect** effects, such as CO₂ fertilisation of managed forests and climate-driven changes in soil carbon.
NGHGI land-use CO₂ is therefore a larger net sink than the BM estimate.
The global difference is 5 to 7 Gt CO₂ per year, mainly from CO₂ fertilisation on managed land ([Weber 2026](https://doi.org/10.1038/s41467-026-69078-9)).

A total CO₂ budget keeps land use and switches it to the NGHGI convention.
The convention gap covers the years of the published budget, from the baseline year to net zero.
[Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) (Methods, Eqs. 2 and 3) uses the same split: the correction starts at the reference year of the budget, and earlier years take observed NGHGI land-use CO₂.
The gap is negative, so it reduces the allocatable budget.
Notebook 104 stores one median per baseline year in `convention_gap_median_from`.
The output column is `correction_lulucf_convention_mt`.

??? note "How the gap is computed per scenario"

    The per-scenario gap $\text{Gap}_i$ runs from the baseline year $\text{base}$ to the net-zero crossing of the scenario. It has two segments.

    **Observed** ($\text{base} \leq t \leq \mathrm{splice{\_}year}$): observed NGHGI land-use CO₂ (the same for all scenarios) minus the BM flux of scenario $i$.
    The splice year is the last year of the NGHGI data (2023 for `melo-2026`, 2024 for `melo-2026-v4`).
    NGHGI data come from Melo et al. and the BM flux from the Gidden et al. AR6 reanalysis (`AFOLU|Direct`). Other sources of the same quantities can take these roles.

    $$
    \text{Gap}_{i,\text{obs}} = \int_{\text{base}}^{\min(\text{splice},\, t_{\text{nz},i})} \left[\text{NGHGI}_{\text{actual}}(t) - \text{BM}_{\text{Direct},i}(t)\right] dt
    $$

    **Future** ($t > \mathrm{splice{\_}year}$): only the indirect component of scenario $i$ (CO₂ fertilisation and other passive fluxes), because the direct components cancel. It comes from the Gidden et al. AR6 reanalysis (`AFOLU|Indirect`).

    $$
    \text{Gap}_{i,\text{future}} = \int_{\max(\text{base},\, \text{splice})}^{t_{\text{nz},i}} \text{Indirect}_{i}(t)\, dt
    $$

    The total is $\text{Gap}_i = \text{Gap}_{i,\text{obs}} + \text{Gap}_{i,\text{future}}$.
    The median runs over the volume-matched set or the AR6 category of the budget, and a budget takes the median of its own baseline year.
    Each year counts in full, and the net-zero year adds its fraction ([Full-year accounting](scenario-sets.md#accounting)).

    Edge cases:

    - A baseline year after the splice year leaves the observed segment empty. The gap is then the indirect component from $\text{base}$.
    - A scenario that reaches net zero before $\text{base}$ has a gap of zero.
    - The years 2020 to $\text{base}{-}1$ sit outside the gap. The rebase adds observed NGHGI land-use CO₂ for them.

    The per-scenario function is `convention_gap_from_baseline()` in `src/fair_shares/library/utils/data/rcb.py`.

---

## Differences from Weber et al. (2026) {#differences-from-weber}

The package follows the structure of [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) (Methods, Eqs. 2 and 3), with five differences.

??? info "The five differences"

    1. **Scenario sets.** Weber et al. use AR6 C1 scenarios for 1.5 °C (50%) and C3 for 2 °C (66%). The package uses these categories for the AR6 sources and role-matched sets for the other sources.
    2. **Statistic.** Weber et al. take the mean across scenarios for the land-use and bunker terms. The package takes the median.
    3. **BM side.** Weber et al. adjust the Gidden et al. values with the difference between the Global Carbon Budget mean of bookkeeping models and NGHGI-reported values for 2020 to 2023 (Methods, "Calculating a NGHGI-consistent global RCB"). The package uses the scenario `AFOLU|Direct` flux, also for the observed years from the baseline year to the splice year, and holds no observed BM series. The gap is a per-scenario quantity: each scenario has its own `AFOLU|Direct` pathway, net-zero year and indirect flux. One multi-model average would collapse this variation and break the integrate-then-median method.
    4. **Bunker term.** Weber et al. take the bunker pathways of the C1 or C3 scenarios that report aviation and maritime (8 and 9 scenarios). The package applies a family-balanced bunker share of net CO₂ to the scenario set of every budget, AR6 categories included.
    5. **Accounting.** The package counts full years to an interpolated net-zero crossing for every term.

---

## Allocation years other than 2020 {#allocation-year}

The allocatable budget runs from 2020.
The `allocation_year` parameter moves the start.
An earlier year adds the world's historical emissions before 2020.
A later year subtracts the emissions already used.

The world series matches the adjusted budget.
It holds fossil CO₂ without bunkers and, for total CO₂, NGHGI land-use CO₂:

$$
E_{\text{world}}(t) = E_{\text{fossil}}(t) + \text{LULUCF}(t)
$$

NGHGI land-use data start in 2000: LULUCF Data Hub v4.0.0 (`melo-2026-v4`, default, 2000 to 2024) or v3.1.1 (`melo-2026`, opt-in, 2000 to 2023).
On this basis categories with land-use CO₂ start in 2000 or later. The bookkeeping source `gcb-2025-luc` (model basis, 1850 to 2024) allows earlier years ([Start-year limits](greenhouse-gases.md#start-year-limits)).
An allocation year before the first year of the world series raises an error that names the first available year.
`calculate_budget_from_rcb` then works the same way for `co2-ffi` and `co2`.
`build_world_co2_timeseries()` and the preprocessing notebooks build the same series.

??? info "Why land-use CO₂ starts in 2000"

    The official NGHGI land-use data begin in 2000.
    Earlier NGHGI estimates exist, such as historical extensions of Melo et al.
    Extending to 1990 would splice heterogeneous datasets, and the BM-to-NGHGI transition around 1990 shows a large jump.
    The package performs no NGHGI/BM splicing.
    We plan to extend coverage when validated pre-2000 NGHGI land-use data become available.

---

## Budgets outside the defaults {#budgets-outside-the-defaults}

Some published labels stay out of the default `rcbs.yaml`, because their scenario sets are too thin:

- **1.5 °C budgets with high likelihoods** (`forster_2024`, `forster_2026`, `ar6_wg1_2021`). Fewer than 10 volume-matched scenarios.

To run one, add its label and published value to [`data/rcbs/rcbs.yaml`](https://github.com/setupelz/fair-shares/blob/main/data/rcbs/rcbs.yaml).
Each of its scenario sets must hold at least `min_scenarios` scenarios.

??? info "Labels left out, with published values and counts"

    | Source | Label | Published (Gt) | Reason |
    | ------ | ----- | -------------- | ------ |
    | `forster_2024` | `1.5p67`, `1.5p83` | 150, 100 | 6 and 3 volume-matched scenarios |
    | `forster_2026` | `1.5p67`, `1.5p83`, `1.5p90` | 80, 30, 10 | 8, 5 and 3 volume-matched scenarios |
    | `ar6_wg1_2021` | `1.5p83` | 300 | 6 volume-matched scenarios |

---

## Worked example {#worked-example}

The two boxes trace one budget from 2020 and one from 2023 through every adjustment, with values from pipeline runs on the default sources.

??? info "A budget from 2020: IPCC AR6 WGI, 1.5 °C at 50%"

    IPCC AR6 WGI, 1.5 °C at 50% (`ar6_2020`, `1.5p50`): 500 Gt CO₂ from 2020.
    It takes AR6 category C1: 70 scenarios, all reaching net zero.
    Values come from pipeline runs on the default sources: PRIMAP-hist v2.8 (`primap-202609`), LULUCF Data Hub v4.0.0 (`melo-2026-v4`) and `gcb-2025` bunkers.
    Each row is rounded, and the totals use unrounded values.

    |                               | `co2-ffi`              | `co2`                 |
    | ----------------------------- | ---------------------- | --------------------- |
    | Published budget (total CO₂)  | 500 Gt                 | 500 Gt                |
    | Rebase (fossil, bunkers, land use) | 0 (base = 2020)   | 0 (base = 2020)       |
    | Land-use term / convention gap | **0** (BM sink capped) | **-91.4 Gt** (gap, 2020 to NZ) |
    | Bunker deduction              | -26.0 Gt               | -26.0 Gt              |
    | **Allocatable budget (2020)** | **474.0 Gt**           | **382.6 Gt**          |

    - **`co2-ffi`.** The median `AFOLU|Direct` flux of the 70 scenarios from 2020 to net zero is -48.4 Gt, a net sink. The precautionary cap sets it to 0. Without the cap (`precautionary_lulucf: false`) the fossil budget would increase.
    - **`co2`.** The convention gap from 2020 to net zero is -91.4 Gt (median of the category).
    - **Bunkers.** Observed bunkers for 2020 to 2024 (5.0 Gt), plus the bunker share 0.072 times the median net CO₂ of C1 from 2025 to net zero (292.9 Gt).

??? info "A budget from 2023: Lamboll et al., 1.5 °C at 50%"

    `lamboll_2023`, `1.5p50`: 250 Gt from 2023.
    The budget from 2020 is 371 Gt: 250 Gt plus 121 Gt of observed global net CO₂ in 2020 to 2022.
    Its volume-matched set holds 14 scenarios with cumulative net CO₂ from 2020 to net zero within 321 to 421 Gt (median crossing 2046.2) and 225.6 Gt of median net CO₂ from 2025 to net zero.

    |                               | `co2-ffi`              | `co2`                   |
    | ----------------------------- | ---------------------- | ----------------------- |
    | Published budget              | 250 Gt                 | 250 Gt                  |
    | Fossil rebase (2020 to 2022)  | +107.6 Gt              | +107.6 Gt               |
    | Bunker rebase (2020 to 2022)  | +2.7 Gt                | +2.7 Gt                 |
    | NGHGI land-use rebase (2020 to 2022) | n/a             | -13.1 Gt                |
    | Land-use term / convention gap | **0** (BM sink capped) | **-57.7 Gt** (gap, 2023 to NZ) |
    | Bunker deduction (2020 to NZ) | -21.1 Gt               | -21.1 Gt                |
    | **Allocatable budget (2020)** | **339.2 Gt**           | **268.4 Gt**            |

    The bunker rebase and the bunker deduction together remove the bunkers of 2023 to net zero (18.4 Gt), the years that the published budget covers.
    For `co2`, the rebase adds observed NGHGI land-use CO₂ for 2020 to 2022 (LULUCF Data Hub world row, -13.1 Gt), and the convention gap covers 2023 to net zero (median from 2023, -57.7 Gt).

??? info "Runs behind the numbers"

    The `co2-ffi` values come from a budget run of `co2-ffi` on the default sources, with PRIMAP-hist v2.8 emissions.
    The `co2` values come from a budget run of `all-ghg` on the same sources, with land-use CO₂ from the LULUCF Data Hub (`melo-2026-v4`).

The sources cited here are on the [References](references.md) page.
