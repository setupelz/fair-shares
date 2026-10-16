---
title: Scenario sets
description: How fair-shares reads budget labels and picks the scenarios behind each scenario-derived budget term
---

# Scenario sets

Some budget terms need future emissions: the land-use term, the convention gap, the bunker deduction after the last observation and the non-CO₂ pathway.
fair-shares takes these from published scenarios.
This page explains how it reads a budget label and picks the scenarios for each term.
[Remaining carbon budgets](remaining-carbon-budgets.md) explains the terms themselves.

**In short:**

- A budget label names the warming when CO₂ reaches net zero and a likelihood. What the likelihood covers depends on the source.
- Each scenario-derived term takes the set that matches its role: a volume-matched set for land use, the convention gap and bunkers, and a temperature-matched set for the non-CO₂ pathway.
- The AR6 budgets take the matching AR6 category (C1, C3 or C4) for every term.
- The bunker share pools every scenario that reports bunkers, balanced across model families.
- Every cumulative counts full years to an interpolated net-zero crossing.

---

## What a budget label means {#what-a-budget-label-means}

A label `TpL` names a warming level $T$ and a likelihood $L$.
Each budget runs from its start year to net-zero CO₂.
$T$ is the warming when CO₂ reaches net zero. It equals peak warming when the zero-emissions commitment (ZEC) is zero.
[Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) defines $T$ as peak warming.

The likelihood of AR6 WGI and of the IGCC updates covers the uncertainty of the transient climate response to cumulative emissions (TCRE) only.
The likelihood of Lamboll et al. covers TCRE, ZEC and Earth-system feedbacks (ESF).
Every published budget assumes the median non-CO₂ warming of scenarios at $T$, for every likelihood.

| Source key     | Likelihood covers | $T$ measures        |
| -------------- | ----------------- | ------------------- |
| `ar6_2020`     | TCRE only         | Warming at net zero |
| `ar6_wg1_2021` | TCRE only         | Warming at net zero |
| `lamboll_2023` | TCRE, ZEC, ESF    | Peak warming        |
| `forster_2024` | TCRE only         | Warming at net zero |
| `forster_2026` | TCRE only         | Warming at net zero |

Each source records `likelihood_scope` and `budget_metric` in `rcbs.yaml`, and the processed budget files carry both.

`forster_2024` and `ar6_2020` publish 67% budgets under the label `2p67`.
The label `2p66` reads as `2p67` for these two sources, with a deprecation warning.
Lamboll et al. publish 66%, so `lamboll_2023` keeps `2p66`.

---

## Role-matched scenario sets {#role-matched-scenario-sets}

Each scenario-derived term of a budget takes the scenario set that matches its role.
This is the default rule, `scenario_selection: role-matched`.

| Term | Set | Rule | Why |
| ---- | --- | ---- | --- |
| Land-use term (`co2-ffi`) | Volume-matched | Reaches net-zero CO₂ by 2100; cumulative net CO₂ from 2020 to net zero within ±`volume_tolerance_gt` (50 Gt) of the budget from 2020 | The term integrates to net zero, so its scenarios spend the budget's volume |
| Convention gap (`co2`) | Volume-matched | Same | Same |
| Bunkers after the last observed year | Volume-matched, times the bunker share | Median net CO₂ of the set from the year after the last observed year to net zero, times the share $s$ | Few scenarios report bunkers and $s$ therefore pools every scenario that does ([Bunker share](#bunker-share)) |
| Non-CO₂ pathway | Temperature-matched | Net-zero year; median warming at net zero in $[T - 0.05,\; T + 0.05)$, for every likelihood | Published budgets assume the median non-CO₂ warming at $T$ |

Every set needs a net-zero year, in the AR6 convention ([Net zero](#net-zero)).

A set below `min_scenarios` (10) raises a `ConfigurationError` that names the budget.
The settings sit at the top of `rcbs.yaml`.
The selection logic is in `src/fair_shares/library/utils/data/scenario_sets.py`.

### Budget from 2020 {#budget-from-2020}

The volume-matched set compares each scenario with the budget from the start of 2020.
That is the published value plus observed global net CO₂ from 2020 to the year before the baseline.
Observed net CO₂ is fossil CO₂ (including bunkers) minus the cement carbonation sink plus bookkeeping land-use CO₂.
It comes from the Global Carbon Budget 2025 workbook (`gcb-2025-global`, [GCP 2026](https://doi.org/10.18160/GCP-2025)).
The workbook ends in 2024, so `forster_2026` takes the 2024 value for 2025 (`rebase_fill_max_years`).

??? info "Consistency record"

    `rcb_scenario_adjustments.yaml` records per budget:

    - the label as published, the likelihood scope and the metric;
    - the rule and size of each set, its median cumulative CO₂, and its median and 67th-percentile warming at net zero;
    - a check of the two sets: their overlap and the volume gap of the temperature-matched set (its median cumulative CO₂ minus the budget from 2020).

    For a p50 budget the two sets describe one budget, so a small gap supports the pairing.

---

## AR6 category pools {#ar6-category-pools}

`ar6_2020` and `ar6_wg1_2021` set `scenario_selection: ar6-category`.
Their labels with an AR6 WGIII category take that category for every term: `1.5p50` C1, `2p67` C3, `2p50` C4.

- C1 limits warming to 1.5 °C (>50%) with no or limited overshoot.
- C3 limits warming to 2 °C (>67%).
- C4 limits warming to 2 °C (>50%).

These definitions come from [IPCC 2022 Annex III](https://doi.org/10.1017/9781009157926.022), Table 14.
C2 returns warming to 1.5 °C (>50%) by 2100 after a high overshoot. Its warming peaks above 1.5 °C and a budget counts emissions to peak warming, so C2 stays outside every budget label.
The integral terms use the category members that reach net zero. The non-CO₂ pathway uses every member.
The bunker term applies the same bunker share to the net CO₂ of the category set.
The other labels of these sources use the role-matched sets.

### Net zero {#net-zero}

A scenario reaches net-zero CO₂ in the first full year from 2020 at which its harmonised climate-assessment CO₂, linear between reported years, is at or below zero.
A scenario without such a year still counts when its harmonised or reported CO₂ falls below 100 Mt CO₂/yr by 2100. Its net-zero year is the first such year.
This is the count of AR6 WGIII: "Pathways were counted when at least one of the two profiles fell below 100 MtCO2 yr–1 until 2100" ([IPCC 2022 SPM](https://doi.org/10.1017/9781009157926.001), Table SPM.2, note j).
`net_zero_years()` in `src/fair_shares/library/utils/data/scenario_sources.py` applies the rule.

The AR6 metadata give a net-zero year to the same 591 of the 914 AR6 scenarios.
For 72 of them, which reach net zero only under the 100 Mt rule, the AR6 warming at net zero holds the 2100 value.
fair-shares therefore derives the net-zero year and the warming at net zero of every AR6 scenario from the AR6 Scenarios Database series (`ipcc_ar6_climate`).
On the other 519 scenarios the derived warming matches the AR6 metadata within 0.013 °C.

---

## Scenario sets of the default budgets {#default-budget-sets}

Two readings follow from the sets of the default budgets:

- The volume-matched sets of 1.5 and 1.7 °C p67 budgets have a 67th-percentile warming at net zero 0.08 to 0.18 °C above $T$; for p83 and p90 budgets at 1.7 °C the difference is 0.00 to 0.02 °C. For 2 °C p66 and p67 the difference is within 0.02 °C. The budget likelihood covers TCRE only, and the MAGICC percentile covers more uncertainty.
- The AR6 budgets use the AR6 category pools, whose scenarios spend less than the budget to net zero: the C4 median is 1153 Gt against 1350 Gt (`2p50`), and the C3 median 834 Gt against 1150 Gt (`2p67`).

??? info "Set statistics per default budget"

    Counts from the AR6 reanalysis of Gidden et al. (2023), 914 scenarios.
    Budgets from 2020 and set statistics in Gt CO₂. Warming is MAGICCv7.5.3 at net zero.

    | Budget | From 2020 | Integral-term set | n | Median cumulative | Median / P67 warming | Non-CO₂ set n | Overlap | Volume gap | Set net CO₂ 2025 to NZ |
    | ------ | --------- | ----------------- | - | ----------------- | -------------------- | ------------- | ------- | ---------- | ---------------------- |
    | `lamboll_2023` `1.5p50` | 371 | volume | 14 | 391 | 1.52 / 1.63 | 32 | 10 | +79 | 226 |
    | `lamboll_2023` `2p50` | 1341 | volume | 21 | 1328 | 1.96 / 2.13 | 43 | 11 | +28 | 1128 |
    | `lamboll_2023` `2p66` | 1061 | volume | 41 | 1040 | 1.83 / 1.99 | 43 | 0 | +308 | 851 |
    | `lamboll_2023` `2p90` | 621 | volume | 59 | 623 | 1.64 / 1.77 | 43 | 0 | +748 | 445 |
    | `forster_2024` `1.5p50` | 363 | volume | 15 | 390 | 1.52 / 1.63 | 32 | 11 | +87 | 225 |
    | `forster_2024` `1.7p50` | 713 | volume | 64 | 719 | 1.69 / 1.83 | 156 | 43 | +49 | 530 |
    | `forster_2024` `2p50` | 1263 | volume | 23 | 1268 | 1.94 / 2.11 | 43 | 6 | +106 | 1068 |
    | `forster_2024` `2p67` | 1063 | volume | 39 | 1042 | 1.83 / 2.00 | 43 | 0 | +306 | 853 |
    | `ar6_2020` `1.5p50` | 500 | C1 | 70 | 473 | 1.55 / 1.68 | 70 | 70 | -27 | 293 |
    | `ar6_2020` `2p50` | 1350 | C4 | 100 | 1153 | 1.89 / 2.05 | 137 | 100 | -197 | 962 |
    | `ar6_2020` `2p67` | 1150 | C3 | 192 | 834 | 1.72 / 1.88 | 231 | 192 | -316 | 651 |
    | `forster_2026` `1.5p50` | 378 | volume | 19 | 403 | 1.54 / 1.67 | 32 | 10 | +72 | 234 |
    | `forster_2026` `1.7p50` | 748 | volume | 54 | 744 | 1.70 / 1.84 | 156 | 36 | +14 | 559 |
    | `forster_2026` `2p50` | 1298 | volume | 26 | 1305 | 1.93 / 2.12 | 43 | 10 | +71 | 1106 |
    | `forster_2026` `2p67` | 1108 | volume | 35 | 1130 | 1.86 / 2.02 | 43 | 0 | +261 | 932 |
    | `ar6_wg1_2021` `1.7p50` | 850 | volume | 78 | 848 | 1.75 / 1.89 | 156 | 40 | -88 | 662 |

    The adjustments file of every run holds the rows of the other labels.
    [Budgets outside the defaults](remaining-carbon-budgets.md#budgets-outside-the-defaults) lists the labels left out and why.

---

## Bunker share {#bunker-share}

Few scenarios report international aviation and shipping.
The bunker term therefore uses one share $s$ of net CO₂, taken from every scenario that reports bunkers.
[Bunker deduction](remaining-carbon-budgets.md#bunker-deduction) shows how the budget applies it.

Each scenario that reports bunkers and reaches net zero gives a ratio $r_k$: its cumulative bunkers over its own net CO₂ (the model's `Emissions|CO2`).
Both run from the year after the last observed bunker year to the scenario's net-zero crossing.
The share is family-balanced: the median of the per-family medians, $s = \text{median}_f\, \text{median}_{k \in f}\, r_k$.
A family counts only with at least `bunkers.min_runs_per_family` (3) scenarios.
A family is the energy-model stem without version or coupling: `IMAGE 3.2` and `IMAGE 3.3` are IMAGE, and `REMIND-MAgPIE 3.2-4.6` is REMIND.

With `gcb-2025` bunkers (last observed year 2024) the share runs from 2025.
The default pool is AR6, Scenario Compass v2.0 and ScenarioMIP v0.1.
156 scenarios that report bunkers reach net zero: 22 from AR6, 92 from Scenario Compass and 42 from ScenarioMIP.

| Family | Family median | Scenarios | Counts |
| ------ | ------------- | --------- | ------ |
| IMAGE | 0.072 | 57 | yes |
| REMIND | 0.071 | 46 | yes |
| MESSAGE | 0.074 | 13 | yes |
| WITCH | 0.051 | 12 | yes |
| GCAM | 0.078 | 10 | yes |
| AIM | 0.060 | 7 | yes |
| COFFEE | 0.033 | 6 | yes |
| IMACLIM | 0.106 | 5 | yes |
| GEM-E3 | 0.053 | 2 | no |
| McKinsey | 0.097 | 2 | no |
| POLES | 0.054 | 2 | no |
| LUT-ESTM | 0.191 | 1 | no |

The family-balanced share is $s = 0.072$.
The median over all 156 scenarios is 0.072 (interquartile range 0.060 to 0.081).
PROMETHEUS reports bunkers, and its runs end in 2050 without net zero.

??? info "Rules and checks"

    - The scenarios come from every source in `bunkers.scenario_sources` (default `[ar6, sci, scenariomip]`). A run carried over from another listed source counts once: Scenario Compass flags its AR6 and ScenarioMIP runs.
    - Each scenario reaches net zero by its own net CO₂, in the AR6 convention ([Net zero](#net-zero)). The climate emulator behind a source therefore does not enter the share. ScenarioMIP uses MAGICC v7.6.0a3 and AR6 uses MAGICCv7.5.3.
    - No historical vetting applies to these scenarios. Vetting tests 2010 to 2025 totals, and the share needs the ratio within each model run.
    - `model_families` in `src/fair_shares/conf/scenario_sources.yaml` lists every model. A scenario from an unlisted model is a configuration error.
    - Fewer than `bunkers.min_reporters` (10) scenarios or `bunkers.min_families` (3) families, counted after the per-family filter, raise a `ConfigurationError` that names the count per scenario source.
    - A source whose data file is absent is left out with a warning.
    - Scenarios of both sources enter with their own emissions and the same accounting.
    - The record lists the excluded families with their medians and counts.

    The function is `bunker_share()` in `src/fair_shares/library/utils/data/scenario_sets.py`.

??? info "Bunker series of each scenario source"

    **AR6.** The AR6 Scenarios Database ([Byers 2022](https://doi.org/10.5281/zenodo.5886911)) has no bunker variable.
    It reports `Emissions|CO2|Energy|Demand|Transportation|Aviation`, which covers domestic and international flights, and `...|Transportation|Maritime`.
    AR6 bunkers are 0.6 times aviation plus maritime.
    The factor 0.6 is the international share of aviation CO₂ that [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9) takes from IEA data (58% to 62%).
    Maritime counts whole as international shipping, as in Weber et al.
    The series come from the public AR6 Scenarios Database (`ipcc_ar6_bunkers`).
    39 of the 914 Gidden et al. scenarios report both variables for 2020 to 2100, all from IMAGE, and 22 of these reach net-zero CO₂ by 2100.

    **Scenario Compass.** The ensemble reports `Emissions|CO2|Energy|Demand|Bunkers` and its international aviation and shipping parts directly, so it takes no aviation share.
    A scenario takes the total where reported, else the sum of both parts.
    Of the 1,977 scenarios of v2.0, 262 report bunkers with a net CO₂ series. 194 remain once the AR6 and ScenarioMIP runs count under their own source.

    **ScenarioMIP.** The workbook reports bunkers like Scenario Compass. Its 68 model runs of 7 models all report them. The `Ensemble` envelope rows are left out.

---

## Scenario sources {#scenario-sources}

A scenario source is an entry in `src/fair_shares/conf/scenario_sources.yaml`.

### AR6 reanalysis {#ar6-reanalysis}

The default source (`ar6`) is the reanalysis of the AR6 scenarios by Gidden et al. (2023), 914 scenarios ([Gidden 2023](https://doi.org/10.5281/zenodo.10158920)).
It supplies net CO₂, the land-use fluxes (`AFOLU|Direct`, `AFOLU|Indirect`), the non-CO₂ pathways, the net-zero years and the warming at net zero (MAGICCv7.5.3).
The aviation and maritime series for the AR6 scenarios that report bunkers come from the AR6 Scenarios Database ([Byers 2022](https://doi.org/10.5281/zenodo.5886911)).

### Scenario Compass {#scenario-compass}

The Scenario Compass Initiative pathways ensemble ([Huppmann 2026b](https://doi.org/10.5281/zenodo.23232097), v2.0 of 8 October 2026; manuscript [Riahi 2026](https://doi.org/10.21203/rs.3.rs-8891091/v1)) is the scenario source `sci`.
Release v1.0 ([Huppmann 2026](https://doi.org/10.5281/zenodo.18598251)) stays selectable through the `version` key, and each release names its own file and columns.
Its terms and download are in [Data & licences](../user-guide/data-sources.md#scenario-compass-ensemble-manual).

v2.0 holds 1,977 scenarios: the 1,214 AR6 carry-overs, the 68 ScenarioMIP v0.1 runs and later submissions.
524 scenarios pass the SCI 2025 historical vetting (criteria release v2026.08.03).
The climate assessment comes in three workflows. fair-shares reads the AR6 workflow (MAGICC v7.5.3), the one behind the AR6 metadata.
The metadata carry only peak warming and warming in 2100 and fair-shares therefore derives warming at net zero itself.

??? info "Warming at net zero for Scenario Compass and ScenarioMIP"

    Their metadata hold peak and 2100 warming only.
    `warming_at_net_zero()` takes the net-zero year of [Net zero](#net-zero) from the harmonised climate-assessment CO₂ and the model's reported CO₂.
    The warming at net zero is the median and 67th-percentile GSAT in that year. Without net zero by 2100, it is the 2100 warming.
    This follows the convention of the AR6 metadata.
    On the 914 AR6 scenarios that Scenario Compass carries over, it gives the same net-zero years as the AR6 series, and the AR6 metadata warming within 0.013 °C where the AR6 metadata hold the warming at net zero.
    A source without warming at net zero in its metadata declares a `derived_warming` block in `scenario_sources.yaml`.

`non_co2.scenario_sources` in `rcbs.yaml` (default `[ar6]`) lists the sources pooled into the temperature-matched non-CO₂ set.
Scenario Compass adds its vetted scenarios that are not AR6 carry-overs: 84 in v2.0, of which 33 reach net zero.
Their non-CO₂ is the harmonised-infilled Kyoto gases minus CO₂, harmonised to the historical non-CO₂.
With a pooled source, the non-CO₂ pathway of a budget is the median of the per-scenario non-CO₂ over the set.
The AR6 category budgets keep their AR6 category pool.
The volume-matched land-use and convention-gap terms need the NGHGI reanalysis split, so they stay AR6 only.

### ScenarioMIP {#scenariomip}

ScenarioMIP-CMIP7 v0.1 ([Riahi 2026b](https://doi.org/10.5281/zenodo.22296051)) holds 68 model runs of 7 models, with the climate assessment of MAGICC v7.6.0a3.
It is the scenario source `scenariomip`, on by default for the bunker share and off for the non-CO₂ set. Its terms are in [Data & licences](../user-guide/data-sources.md#scenariomip-cmip7-ensemble-manual).

[Adding data sources](../dev-guide/adding-data-sources.md#scenario-sources-and-budgets) lists what a new budget or scenario source needs.

---

## Scenario labels {#scenario-labels}

Notebook 104 maps the categories of each scenario source to clean `climate-assessment` names and `quantile` fields.
All downstream code, including the non-CO₂ pathways, then reads one format.
AR6 categories map as:

- C1 → `climate-assessment="1.5C"`, `quantile=0.5`
- C3 → `climate-assessment="2C"`, `quantile=0.67`
- C4 → `climate-assessment="2C"`, `quantile=0.5`

C2 stays out of the map for the reason given in [AR6 category pools](#ar6-category-pools).
A new scenario source defines its own mapping into the same format.
Inside notebook 104, combined labels (e.g. "1.5p50") keep C3 and C4 apart during the median step and map to the clean format at output.
The map follows the AR6 WGIII category definitions ([AR6 category pools](#ar6-category-pools)).

---

## Full-year accounting {#accounting}

Budgets run from the start of 2020, so a cumulative counts every year in full.
A scenario series is linear between its reported years, and the value of a year is its flow over that whole year.
The net-zero year is the zero crossing of that line, interpolated between the last positive and the first non-positive point.
A cumulative to net zero sums the full years from its start to the year before the crossing and adds the fraction of the crossing year (the trapezoid of the line within that year).
The same accounting applies to the volume that selects the set, the land-use term, the convention gap and the bunker term.
The functions are `net_zero_crossing()` and `integrate()` in `src/fair_shares/library/utils/data/rcb.py`.

Each scenario integrates to its own net-zero crossing $t_{\text{nz},i}$, where its total CO₂ (`Emissions|CO2`) first reaches zero.
This keeps negative emissions after net zero out of the corrections.
`Emissions|CO2` in IAM scenario databases is fossil plus BM land-use CO₂ by convention. This is a property of how scenarios report total CO₂.
Every integral-term set holds only scenarios that reach net zero by 2100: the volume-matched set by its rule, and an AR6 category pool by keeping its members that reach net zero (192 of the 231 C3 scenarios).

??? info "Files written per budget"

    Notebook 104 keys each budget as `source:label` in `rcb_scenario_adjustments.yaml`, with the scalars and the consistency record.
    It also writes:

    - `scenario_set_{source}_{label}.csv`: the members of the integral-term set, with their net-zero crossings and net CO₂ from each possible start year;
    - `bunker_share_reporters.csv`: each scenario's cumulative bunkers and net CO₂ from every possible start year.

    The processed budget files carry `published_label`, `likelihood_scope`, `budget_metric`, `scenario_selection`, `budget_2020_gt`, the rule and size of both sets and `nz_year_median`.
    They also carry the bunker columns: `bunker_share`, `bunker_share_pooled`, the interquartile range of the ratios, the family medians and counts (`bunker_share_families`), the scenario counts by source and the set's net CO₂ after the last observed year (`bunker_set_co2_after_mt`).

The sources cited here are on the [References](references.md) page.
