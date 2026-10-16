---
title: ESABCC 2023 reproduction
description: How notebook 601 reproduces the ESABCC 2023 fair-share approaches, and how its numbers differ from the underlying IIASA study
---

# ESABCC 2023 reproduction

The fair-share numbers in the ESABCC advice on the EU 2040 target ([ESABCC 2023](https://doi.org/10.2800/609405)) come from an IIASA study, Pelz, Rogelj and Riahi (2023), here PRR2023 ([report](https://pure.iiasa.ac.at/18830), [replication code](https://doi.org/10.5281/zenodo.8035839)).
Notebook `601_reproduce_esabcc_2023` runs the same approaches with the library and current data.

**In short:**

- Notebook 601 uses the PRR2023 settings through a preset, `esabcc_2023_allocations()`. The library defaults differ.
- The global budget is smaller than in PRR2023: 1331 Gt from 1990 (PRR2023: 1530 Gt) and 651 Gt from 2015 (PRR2023: 704 Gt). Two choices cause most of this: the years before 2020 are added as fossil CO2 only, and international aviation and shipping are deducted.
- The EU27 shares match PRR2023 closely; see [Reproduction accuracy](#reproduction-accuracy).
- Notebook 601 also extends PRR2023 to land-use CO2 and the other greenhouse gases, and to budgets remaining from today.

The details follow in the boxes below. [Remaining carbon budgets](../science/remaining-carbon-budgets.md), [Scenario sets](../science/scenario-sets.md) and [Greenhouse gases](../science/greenhouse-gases.md) explain the budget corrections, the scenario sets and the gas treatment for every run.

??? info "What PRR2023 computed"

    | Element | PRR2023 |
    | --- | --- |
    | Emissions in scope | Fossil and industry CO2 (`co2-ffi`) |
    | Global budget | IPCC AR6 WGI, 1.5°C at 50%: 500 Gt CO2 from 2020 |
    | Allocation years | 1990 and 2015. The year 1850 enters only as the start of a responsibility window |
    | Budget from the allocation year | 1530 Gt from 1990 and 704 Gt from 2015: 500 Gt plus 1030 Gt and 204 Gt from Global Carbon Budget 2021 ([Friedlingstein 2022](https://doi.org/10.5194/essd-14-1917-2022)) |
    | National emissions | Global Carbon Budget 2022, national fossil emissions |
    | Approaches | Equal per capita (EPC), equal cumulative per capita (ECPC), responsibility, capability. The responsibility-capability-need composite stays unquantified |
    | Responsibility windows | Fossil CO2 1850 to 1989 (allocation year 1990); 1850 to 2014 and 1990 to 2014 (allocation year 2015); total and per capita |
    | Capability | GDP per capita in 1990 or 2014 |
    | Penalty functions | 1/x and 1/√x |
    | Spatial unit | 11 world regions plus EU27 |

??? info "Settings in notebook 601 and the preset"

    | PRR2023 approach | fair-shares approach | Settings |
    | --- | --- | --- |
    | EPC | `equal-per-capita-budget` | `allocation_year` 1990 or 2015, `preserve_allocation_year_shares=True` |
    | ECPC | `equal-per-capita-budget` | `allocation_year` 1990 or 2015, `preserve_allocation_year_shares=False`, `cumulative_end_year=2050` |
    | Responsibility | `per-capita-adjusted-budget` | functional form `"power"`, exponent 1.0 (1/x) or 0.5 (1/√x), window start 1850 or 1990, total or per capita, on both bases |
    | Capability | `per-capita-adjusted-budget` | functional form `"power"`, exponent 1.0 or 0.5, `capability_reference_year` 1990 (allocation year 1990) or 2014 (allocation year 2015), on both bases |

    The library defaults differ: functional form `"asinh"`, no 2050 population window, GDP year by year.
    A tool that presents the PRR2023 approaches takes its settings from the preset ([Presets](../api/python-api.md#presets)):

    ```python
    from fair_shares.library.presets import esabcc_2023_allocations

    allocations = esabcc_2023_allocations("co2-ffi")  # the PRR2023 matrix, 36 runs
    ```

    Notebook 601 uses one budget, `ar6_2020` at 1.5°C and 50%.
    Its section 5 subtracts observed emissions and reports the budget remaining from 2026 (from 2025 for `all-ghg`, whose land-use data end in 2024).
    Its section 6 spreads each remaining budget into an annual pathway to 2100.

??? info "Differences from PRR2023 and their effect"

    | Topic | PRR2023 | Notebook 601 | Effect |
    | --- | --- | --- | --- |
    | National emissions | GCB 2022 | PRIMAP-hist v2.8, the library default (CC BY-NC-SA 4.0) | Changes responsibility indicators |
    | Budget from 1990 and 2015 | Adds total CO2 for 1990 to 2019 (1030 Gt) and 2015 to 2019 (204 Gt) | Adds fossil CO2 without bunkers: 857 Gt and 177 Gt | 1331 Gt from 1990 and 651 Gt from 2015, about 13% and 7% below PRR2023. Every national budget falls by the same proportion |
    | International aviation and shipping | Inside the 500 Gt | Deducted, 2020 to net zero: 26 Gt, so 500 Gt becomes 474 Gt | Lowers every national budget |
    | Future land-use CO2 | Not separated | Median of the AR6 C1 scenarios, a net sink, set to 0 by the precautionary cap | No effect at 1.5°C |
    | Population | WiC SSP2 (2013), OWID history | UN WPP 2024 with UN and OWID history | Changes ECPC shares |
    | GDP | WDI PPP, constant 2017 dollars | Same indicator, rebased to constant 2021 dollars | Changes capability shares |
    | Spatial unit | 11 regions plus EU27 | 177 countries plus rest of world | Changes responsibility and capability shares (see the check below) |
    | Consumption CO2, capital stock | Used | No data source | Indicators absent |

## Reproduction accuracy

Notebook 601 reproduces PRR2023 closely.
The table compares the EU27 share of the global budget, in per cent.

| Approach | PRR2023 | fair-shares | Difference (pp) |
| --- | --- | --- | --- |
| Equal per capita, from 1990 | 7.88 | 7.88 | +0.01 |
| Equal per capita, from 2015 | 5.96 | 5.94 | -0.02 |
| Equal cumulative per capita, from 1990 | 5.93 | 5.65 | -0.28 |
| Equal cumulative per capita, from 2015 | 5.47 | 5.06 | -0.41 |
| Capability, all variants | | | -0.36 to +0.04 |
| Responsibility, all variants | | | -1.77 to +0.31 |

The cumulative per capita rows differ through the newer population projections.
The responsibility rows differ most because fair-shares allocates to countries and sums them, while PRR2023 allocates to the EU27 as one region.
With the same regional inputs, the library reproduces the PRR2023 results exactly.

??? info "Extensions beyond PRR2023: land-use CO2 and other gases"

    Notebook 601 also runs `co2` (with land-use CO2 as national inventories report it), `all-ghg-ex-co2-lulucf` and `all-ghg`.
    A remaining carbon budget limits CO2 only, so the CO2 part is a budget and the non-CO2 part is an annual pathway; the library holds no single greenhouse-gas budget number.
    At 1.5°C and 50% the `co2` budget from 2020 is 383 Gt (474 Gt minus a 91 Gt national-inventory convention gap).
    The all-GHG categories start in 2015 in notebook 601; `all-ghg` cannot start before 2000, the first year of national-inventory land-use data.
    [Greenhouse gases](../science/greenhouse-gases.md#decomposition-rules) explains the method and the sources behind it.

The sources cited here are on the [References](../science/references.md) page.
