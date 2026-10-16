---
title: ESABCC 2023 and what changed since
description: How fair-shares reproduces the ESABCC 2023 fair-share approaches, every method and data difference from the underlying IIASA study, and how CO2, land-use CO2 and non-CO2 gases are combined
---

# ESABCC 2023 and what changed since

The European Scientific Advisory Board on Climate Change (ESABCC) assessed national fair shares in its advice on the EU 2040 target ([ESABCC 2023](https://doi.org/10.2800/609405)).
The fair-share numbers in that report come from an IIASA study, Pelz, Rogelj and Riahi (2023), here called PRR2023 ([report](https://pure.iiasa.ac.at/18830), [replication code](https://doi.org/10.5281/zenodo.8035839)).

This page answers three questions:

1. How does fair-shares reproduce the PRR2023 approaches?
2. Where do the current methods and data differ from PRR2023, and what does each difference do to the numbers?
3. How are fossil CO2, land-use CO2 and the other greenhouse gases combined?

The reproduction lives in notebook `601_reproduce_esabcc_2023`.
Statements about PRR2023 on this page are checked against its published replication code (v1.1).

## 1. What PRR2023 computed

| Element | PRR2023 |
| --- | --- |
| Emissions in scope | Fossil and industry CO2 (`co2-ffi`) |
| Global budget | IPCC AR6 WGI, 1.5°C at 50%: 500 Gt CO2 from 2020 |
| Allocation years | 1990 and 2015 |
| Global budget from the allocation year | 1530 Gt from 1990, 704 Gt from 2015. PRR2023 adds 1030 Gt (1990 to 2019) and 204 Gt (2015 to 2019) to the 500 Gt, taken from Global Carbon Budget 2021 ([Friedlingstein 2022](https://doi.org/10.5194/essd-14-1917-2022)) |
| National emissions | Global Carbon Budget 2022, national fossil emissions v1.0 |
| Approaches | Equal per capita (EPC), equal cumulative per capita (ECPC), responsibility-adjusted, capability-adjusted. The responsibility-capability-need composite is described and left unquantified |
| Responsibility windows | Cumulative fossil CO2 1850 to 1989 (allocation year 1990); 1850 to 2014 and 1990 to 2014 (allocation year 2015); total and per capita. Consumption CO2 1990 to 2014 |
| Capability indicators | GDP per capita in 1990 and 2014 (one snapshot year). Capital stock per capita |
| Penalty functions | 1/x and 1/√x |
| Spatial unit | 11 world regions plus EU27 |

The year 1850 enters PRR2023 only as the start of a responsibility window.
The allocation itself starts in 1990 or in 2015.

## 2. How notebook 601 reproduces it

| PRR2023 approach | fair-shares approach | Settings |
| --- | --- | --- |
| EPC | `equal-per-capita-budget` | `allocation_year` 1990 or 2015, `preserve_allocation_year_shares=True` |
| ECPC | `equal-per-capita-budget` | `allocation_year` 1990 or 2015, `preserve_allocation_year_shares=False`, `cumulative_end_year=2050` |
| Responsibility, 1/x or 1/√x | `per-capita-adjusted-budget` | `pre_allocation_responsibility_weight=1.0`, `..._functional_form="power"`, `..._exponent` 1.0 or 0.5, `..._year` 1850 or 1990, `..._per_capita` True or False, on both the EPC and ECPC basis |
| Capability, 1/x or 1/√x | `per-capita-adjusted-budget` | `capability_weight=1.0`, `capability_functional_form="power"`, `capability_exponent` 1.0 or 0.5, `capability_reference_year` 1990 (allocation year 1990) or 2014 (allocation year 2015), on both bases |

Notebook 601 uses one budget for every run: `ar6_2020`, 1.5°C, quantile 0.5 (`RCB_ANCHOR` in its section 3).
It also goes two steps beyond PRR2023.
Section 5 subtracts observed emissions through 2023 and reports the budget remaining from 2024.
Section 6 spreads each remaining budget into an annual pathway to 2100.
The [Python API](../api/python-api.md) runs both steps without the notebook.

### Library defaults differ from the PRR2023 settings

A run that relies on the library defaults gives different numbers from PRR2023.
Any tool that presents PRR2023 approaches must pass these settings explicitly, as notebook 601 does.

| Parameter | PRR2023 setting | Library default |
| --- | --- | --- |
| `pre_allocation_responsibility_functional_form`, `capability_functional_form` | `"power"` | `"asinh"` |
| `cumulative_end_year` (ECPC) | 2050 | none (the population window runs to the end of the population series) |
| `capability_reference_year` | 1990 or 2014 (one snapshot year) | none (GDP year by year) |
| `pre_allocation_responsibility_year` | 1850 or 1990 | 1990 |

## 3. Differences from PRR2023

Each row gives the difference, its effect, and the setting that controls it.

| Topic | PRR2023 | fair-shares (notebook 601) | Effect | Controlled by |
| --- | --- | --- | --- | --- |
| National fossil emissions | GCB 2022 | PRIMAP-hist v2.6.1. GCB 2025 is available as `gcb-2025` | Changes responsibility indicators and the emissions subtracted in section 5 | `active_sources["emissions"]` |
| Global budget from 1990 and 2015 | Adds total CO2 for the years before 2020. The size of the 1030 Gt and 204 Gt additions matches fossil plus land-use CO2 | Adds the fossil CO2 series that the shares use, without international bunkers: 857 Gt (1990 to 2019) and 177 Gt (2015 to 2019) | Global budget 1322 Gt from 1990 (PRR2023: 1530 Gt, about 14% lower) and 642 Gt from 2015 (PRR2023: 704 Gt, about 9% lower). Every national share of the global budget falls by the same proportion | Rebase in `library/utils/data/rcb.py` |
| International aviation and shipping | Kept inside the 500 Gt | Deducted from the budget, 2020 to net zero: 35 Gt at 1.5°C 50%. The 500 Gt becomes 465 Gt | Lowers every national budget. Bunkers belong to no country, so no country should receive them | `bunkers` entry of the `rcbs` target in `data_sources_unified.yaml` |
| Future land-use CO2 in a fossil budget | Not separated | The AR6 scenario median for land-use CO2 from 2020 to net zero is removed from the budget. It is a net sink at 1.5°C, and the precautionary cap sets it to 0 | No effect at 1.5°C 50% with the cap on. Turning the cap off raises the fossil budget | `precautionary_lulucf` |
| Population | WiC SSP2 projections (2013 vintage), OWID history | UN WPP 2024 projections with UN and OWID history (`un-owid-2025`) | Changes ECPC shares through the 2015 to 2050 population window | `active_sources["population"]` |
| GDP | Constant 2017 PPP | Same convention, World Bank WDI 2025 vintage | Small changes to capability shares | `active_sources["gdp"]` |
| Spatial unit | 11 regions plus EU27 | Countries (177 with the default sources) plus rest of world | EPC and ECPC are linear, so the two give the same totals for the same grouping. The 1/x and 1/√x penalties are non-linear, so country-level and region-level results differ | Library design |
| Consumption CO2, capital stock | Used | Not available | These indicators are absent from 601 | No data source |

The two budget rows explain most of the difference in the global budget: what is added for the years before 2020, and the bunker deduction.
The choice of national emissions source changes the shares between countries.

### Budgets published after the IPCC AR6 report

The library holds later budget estimates next to the AR6 budget used by PRR2023:
`lamboll_2023`, `forster_2024`, `forster_2026` (IGCC 2025) and `ar6_wg1_2021`.
A budget with a baseline year after 2020 is first rebased to 2020 from observed emissions.
Budgets for total CO2 (`co2`) are then converted to the national-inventory convention, following [Weber et al. (2026)](https://doi.org/10.1038/s41467-026-69078-9).
[Other Operations](other-operations.md#weber-rcb-corrections) gives the equations and a worked example.

## 4. Gases: fossil CO2, land-use CO2 and the other greenhouse gases

A remaining carbon budget limits CO2 only.
The library therefore treats CO2 as a budget and the other gases as annual pathways.

| Category | Contents | How it is allocated |
| --- | --- | --- |
| `co2-ffi` | Fossil and industry CO2 | One budget. This is the PRR2023 and ESABCC scope |
| `co2` | `co2-ffi` plus land-use CO2 as national inventories report it (NGHGI) | One budget, converted to the national-inventory convention. At 1.5°C 50% the budget from 2020 is 375 Gt (465 Gt minus a 90 Gt convention gap) |
| `all-ghg` | `co2` plus the non-CO2 Kyoto gases | The `co2` budget plus a non-CO2 pathway |
| `all-ghg-ex-co2-lulucf` | `co2-ffi` plus the non-CO2 Kyoto gases, without any land-use emissions | The `co2-ffi` budget plus a non-CO2 pathway |

The non-CO2 pathway comes from AR6 scenarios of the same climate target.
Each scenario is harmonised to observed emissions, and the median is taken.
The non-CO2 world pathway is the median all-GHG pathway minus the median CO2 pathway.
The same equity approach and parameters then divide the non-CO2 pathway between countries, year by year.
Gases are added with AR6 GWP100 values.

Three points matter when a result is described as a "greenhouse gas budget":

- **No single GHG budget number exists in the library.** An all-GHG result is the CO2 budget plus the sum of the non-CO2 pathway over the same years. Both parts are reported separately and also added together (notebook 601, section 5).
- **Past non-CO2 deviation has two settlement options.** Section 5 reports each country's actual minus allocated non-CO2 emissions since the allocation year (`historical-deviation`). In `free-rider` mode the deviation is reported only. In `co2-debit` mode a country's past non-CO2 overuse is subtracted from its remaining CO2 budget. This uses GWP100, so a different metric gives different numbers.
- **The all-GHG categories start in 2015.** National-inventory land-use data start in 2000, and the AR6 non-CO2 pathways start in 2015. For `all-ghg` the responsibility window starts in 2000.

The name `all-ghg-ex-co2-lulucf` describes less than the category excludes.
It uses the PRIMAP-hist category `M.0.EL`, which excludes all land-use emissions: CO2, CH4 and N2O.
Agriculture stays in.
The historical non-CO2 series therefore excludes land-use CH4 and N2O, while the AR6 scenario non-CO2 includes them.
Harmonisation to the 2020 historical value removes the difference in level at 2020.
The name stays unchanged for compatibility.

Methane pathways different from the AR6 medians are possible in the library design.
[Weber et al. (2026)](https://doi.org/10.1038/s43247-026-03832-1) map peak warming across combinations of the CO2 net-zero year and the change in methane emissions [checked: abstract].
A user-facing option for custom methane pathways is planned; the README lists it under Known Limitations.

## 5. What is checked, and what remains to check

| Check | Status |
| --- | --- |
| Notebook 601 and the Python API give the same numbers | Tested (`tests/integration/test_python_api_reproduces_notebook.py`, tolerance 1e-6) |
| Each budget correction | Unit-tested; the worked example in [Other Operations](other-operations.md#worked-example-ar6-wg1-15c-50-15p50) uses pipeline output |
| Notebook 601 against the published PRR2023 regional figures | Open. Aggregate the country results to the PRR2023 regions first, with `Data/countrygrouping/isorgn.csv` from the PRR2023 replication archive |

## References

- European Scientific Advisory Board on Climate Change (2023). *Scientific advice for the determination of an EU-wide 2040 climate target and a greenhouse gas budget for 2030–2050.* [doi:10.2800/609405](https://doi.org/10.2800/609405)
- Pelz, S., Rogelj, J., Riahi, K. (2023). *Evaluating equity in European climate change mitigation pathways for the EU Scientific Advisory Board on Climate Change.* IIASA, Laxenburg. [pure.iiasa.ac.at/18830](https://pure.iiasa.ac.at/18830). Replication code: [doi:10.5281/zenodo.8035839](https://doi.org/10.5281/zenodo.8035839)
- Friedlingstein, P. et al. (2022). Global Carbon Budget 2021. *Earth System Science Data* 14, 1917–2005. [doi:10.5194/essd-14-1917-2022](https://doi.org/10.5194/essd-14-1917-2022)
- Weber, K., Brunner, L., Knutti, R. (2026). Tracking country-level mitigation progress using NGHGI-consistent carbon budgets. *Nature Communications*. [doi:10.1038/s41467-026-69078-9](https://doi.org/10.1038/s41467-026-69078-9)
- Weber, K., Knutti, R., Brun, P., Brunner, L. (2026). Limiting warming by CO2 and methane mitigation in an expanded scenario space. *Communications Earth & Environment*. [doi:10.1038/s43247-026-03832-1](https://doi.org/10.1038/s43247-026-03832-1)
- Pelz, S. et al. (2025). Entry points for assessing "fair shares" in national mitigation contributions. *Environmental Research Letters*. [doi:10.1088/1748-9326/ada45f](https://doi.org/10.1088/1748-9326/ada45f)
- Pelz, S. et al. (2025). Using net-zero carbon debt to track climate overshoot responsibility. *PNAS*. [doi:10.1073/pnas.2409316122](https://doi.org/10.1073/pnas.2409316122)

The full list is on the [References](references.md) page.
