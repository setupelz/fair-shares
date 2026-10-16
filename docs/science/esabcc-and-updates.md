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
Section 5 subtracts observed emissions through the last observed year of every part of the category. That is 2025 for `co2-ffi` and `all-ghg-ex-co2-lulucf` (remaining from 2026) and 2024 for `all-ghg` (remaining from 2025), because its land-use data end in 2024.
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

The named preset holds these settings, and notebook 601 builds its grid from it ([Presets](../api/python-api.md#presets)):

```python
from fair_shares.library.presets import esabcc_2023_allocations

allocations = esabcc_2023_allocations("co2-ffi")  # the PRR2023 matrix, 36 runs
```

## 3. Differences from PRR2023

Each row gives the difference, its effect, and the setting that controls it.

| Topic | PRR2023 | fair-shares (notebook 601) | Effect | Controlled by |
| --- | --- | --- | --- | --- |
| National fossil emissions | GCB 2022 | PRIMAP-hist v2.8 (`primap-202609`, the library default, licence CC BY-NC-SA 4.0). PRIMAP-hist v2.6.1 (`primap-202503`, CC BY 4.0) and GCB 2025 (`gcb-2025`) are available | Changes responsibility indicators and the emissions subtracted in section 5. Results on the default source carry the non-commercial, share-alike terms | `active_sources["emissions"]` |
| Global budget from 1990 and 2015 | Adds total CO2 for the years before 2020. The size of the 1030 Gt and 204 Gt additions matches fossil plus land-use CO2 | Adds the fossil CO2 series that the shares use, without international bunkers: 857 Gt (1990 to 2019) and 177 Gt (2015 to 2019) | Global budget 1327 Gt from 1990 (PRR2023: 1530 Gt, about 13% lower) and 647 Gt from 2015 (PRR2023: 704 Gt, about 8% lower). Every national share of the global budget falls by the same proportion | Rebase in `library/utils/data/rcb.py` |
| International aviation and shipping | Kept inside the 500 Gt | Deducted from the budget, 2020 to net zero: observed bunkers 2020 to 2024 (GCB 2025, 5 Gt) plus the bunker share of the scenario set's net CO2 after 2024. The share is 0.088, the median of the model-family medians of IMAGE, REMIND and IMACLIM over 59 AR6 and Scenario Compass scenarios. At 1.5°C 50% the deduction is 31 Gt and the 500 Gt becomes 469 Gt | Lowers every national budget. Bunkers belong to no country, so no country should receive them | `bunkers` block in `data/rcbs/rcbs.yaml`; bunker reporters in `conf/scenario_sources.yaml` |
| Future land-use CO2 in a fossil budget | Not separated | The median land-use CO2 of the AR6 C1 scenarios from 2020 to net zero is removed from the budget. It is a net sink at 1.5°C, and the precautionary cap sets it to 0 | No effect at 1.5°C 50% with the cap on. Turning the cap off raises the fossil budget | `precautionary_lulucf` |
| Population | WiC SSP2 projections (2013 vintage), OWID history | UN WPP 2024 projections with UN and OWID history (`un-owid-2025`) | Changes ECPC shares through the 2015 to 2050 population window | `active_sources["population"]` |
| GDP | WDI `NY.GDP.MKTP.PP.KD` in constant 2017 PPP dollars | The same WDI indicator, now rebased by the World Bank to constant 2021 PPP dollars (2025 vintage) | Changes capability shares through relative price levels between countries | `active_sources["gdp"]` |
| Spatial unit | 11 regions plus EU27 | Countries plus rest of world: 177 analysis countries for `co2-ffi` and `all-ghg-ex-co2-lulucf`, 167 for `all-ghg` | EPC and ECPC are linear, so the two give the same totals for the same grouping. The 1/x and 1/√x penalties are non-linear, so country-level and region-level results differ | Library design |
| Consumption CO2, capital stock | Used | Not available | These indicators are absent from 601 | No data source |

The two budget rows explain most of the difference in the global budget: what is added for the years before 2020, and the bunker deduction.
The choice of national emissions source changes the shares between countries.

### Budgets published after the IPCC AR6 report

The library holds later budget estimates next to the AR6 budget used by PRR2023:
`lamboll_2023`, `forster_2024`, `forster_2026` (IGCC 2025) and `ar6_wg1_2021`.
A budget with a baseline year after 2020 is first rebased to 2020 from observed emissions.
Budgets for total CO2 (`co2`) are then converted to the national-inventory convention, following [Weber et al. (2026)](https://doi.org/10.1038/s41467-026-69078-9).
[Other Operations](other-operations.md#weber-rcb-corrections) gives the equations and a worked example.

### Which scenarios each budget uses

Every published budget runs from its start year to net-zero CO2.
Its temperature is the warming at net zero, and its likelihood covers the uncertainty in the warming response to cumulative CO2 (for Lamboll et al. 2023 also the zero-emissions commitment and Earth-system feedbacks).
Every budget assumes the median non-CO2 warming for its temperature, whatever its likelihood.

The scenario-derived terms therefore come from scenario sets matched to their role:

| Term | Scenario set |
| --- | --- |
| Land-use deduction, national-inventory convention gap, bunker deduction | Scenarios whose cumulative net CO2 from 2020 to net zero lies within 50 Gt of the budget |
| Non-CO2 pathway | Scenarios whose median warming at net zero lies within 0.05°C of the budget temperature |

The AR6 budgets (`ar6_2020`, `ar6_wg1_2021`) use the AR6 WGIII categories that WGIII itself pairs with them: C1 for 1.5°C at 50%, C3 for 2°C at 67%, C4 for 2°C at 50%.
Notebook 601 therefore takes every scenario term from the C1 category.
[Other Operations](other-operations.md) lists the rules, the budgets outside the defaults and the reasons.

## 4. Gases: fossil CO2, land-use CO2 and the other greenhouse gases

The allocation approaches follow Pelz et al. ([2025a](https://doi.org/10.1073/pnas.2409316122), [2025b](https://doi.org/10.1088/1748-9326/ada45f)).
The conversion of the budget to the national-inventory convention for land-use CO2 follows [Weber et al. (2026)](https://doi.org/10.1038/s41467-026-69078-9).
The pairing of the CO2 budget with a methane pathway follows [Weber et al. (2026b)](https://doi.org/10.1038/s43247-026-03832-1).
A remaining carbon budget limits CO2 only.
The library therefore treats CO2 as a budget and the other gases as annual pathways.

A remaining carbon budget also assumes a methane pathway.
Weber et al. (2026b) find that an additional sustained linear 10% cut in methane emissions to 2050 raises the 2°C (50%) budget by about 165 Gt CO2 [checked: abstract].
The library therefore takes the non-CO2 pathway from scenarios at the budget's temperature (the AR6 category for AR6 budgets).
A different methane pathway needs a matching budget.

| Category | Contents | How it is allocated |
| --- | --- | --- |
| `co2-ffi` | Fossil and industry CO2 | One budget. This is the PRR2023 and ESABCC scope |
| `co2` | `co2-ffi` plus land-use CO2 as national inventories report it (NGHGI) | One budget, converted to the national-inventory convention. At 1.5°C 50% the budget from 2020 is 378 Gt (469 Gt minus a 91 Gt convention gap) |
| `all-ghg` | `co2` plus the non-CO2 Kyoto gases | The `co2` budget plus a non-CO2 pathway |
| `all-ghg-ex-co2-lulucf` | `co2-ffi` plus the non-CO2 Kyoto gases, without any land-use emissions | The `co2-ffi` budget plus a non-CO2 pathway |

The non-CO2 pathway comes from the budget's temperature-matched scenario set (the C1 category for notebook 601).
Each scenario is harmonised to observed emissions, and the median is taken.
The non-CO2 world pathway is the median all-GHG pathway minus the median CO2 pathway.
The same equity approach and parameters then divide the non-CO2 pathway between countries, year by year.
Gases are added with AR6 GWP100 values.

Three points matter when a result is described as a "greenhouse gas budget":

- **No single GHG budget number exists in the library.** An all-GHG result is the CO2 budget plus the sum of the non-CO2 pathway over the same years. Both parts are reported separately and also added together (notebook 601, section 5).
- **Past non-CO2 deviation has two settlement options.** Section 5 reports each country's actual minus allocated non-CO2 emissions since the allocation year (`historical-deviation`). In `free-rider` mode the deviation is reported only. In `co2-debit` mode a country's past non-CO2 overuse is subtracted from its remaining CO2 budget. This uses GWP100, so a different metric gives different numbers.
- **The earliest allocation year depends on the category.** `co2` and `all-ghg` start in 2000 at the earliest, because national-inventory land-use data begin in 2000; the library raises an error for earlier years. `all-ghg-ex-co2-lulucf` has no such limit. Notebook 601 runs both all-GHG categories from 2015, so they compare like for like. For `all-ghg` the responsibility window starts in 2000.

The name `all-ghg-ex-co2-lulucf` describes less than the category excludes.
It uses the PRIMAP-hist category `M.0.EL`, which excludes all land-use emissions: CO2, CH4 and N2O.
Agriculture stays in.
The historical non-CO2 series therefore excludes land-use CH4 and N2O, while the AR6 scenario non-CO2 includes them.
Harmonisation to the 2020 historical value removes the difference in level at 2020.
The name stays unchanged for compatibility.

Methane pathways different from the AR6 medians are possible in the library design, each with its matching budget from Weber et al. (2026b).
A user-facing option for custom methane pathways is planned; the README lists it under Known Limitations.

## 5. What is checked, and what remains to check

| Check | Status |
| --- | --- |
| Notebook 601 and the Python API give the same numbers | Tested (`tests/integration/test_python_api_reproduces_notebook.py`, tolerance 1e-6) |
| Each budget correction | Unit-tested; the worked example in [Other Operations](other-operations.md#worked-example-ar6-wg1-15c-50-15p50) uses pipeline output |
| Allocation formulas against PRR2023 | Done (`analysis/prr2023_method_check.py`). An independent port of the PRR2023 R code reproduces its 336 published regional values (max relative difference 5e-15). On the same regional inputs the library matches the port for all 40 approach, indicator and penalty combinations (max relative difference 1e-15) |
| Notebook 601 against PRR2023 for the EU27 | Done (same script). See below |

The EU27 share of the global budget, in per cent, splits into a data gap and a granularity gap.
The data gap is the library on the PRR2023 regions with current data, minus PRR2023.
The granularity gap is notebook 601 (country level, then summed), minus the regional result.

| Approach | PRR2023 | Notebook 601 | Data gap (pp) | Granularity gap (pp) |
| --- | --- | --- | --- | --- |
| EPC 1990 | 7.88 | 7.87 | -0.003 | 0 |
| ECPC 1990 | 5.93 | 5.65 | -0.28 | 0 |
| EPC 2015 | 5.96 | 5.96 | -0.001 | 0 |
| ECPC 2015 | 5.47 | 5.06 | -0.41 | 0 |
| Capability (all indicators) | | | -0.17 to +0.05 | -0.21 to 0 |
| Responsibility (all indicators) | | | -0.41 to +0.03 | -1.61 to +0.44 |

The ECPC data gap comes from the population projections.
The granularity gap appears only for the non-linear 1/x and 1/√x penalties, and it is largest for responsibility based on total emissions.
Allocating to countries and summing gives a different EU27 share from allocating to the EU27 as one region; this is a choice of allocation unit.

## References

- European Scientific Advisory Board on Climate Change (2023). *Scientific advice for the determination of an EU-wide 2040 climate target and a greenhouse gas budget for 2030–2050.* [doi:10.2800/609405](https://doi.org/10.2800/609405)
- Pelz, S., Rogelj, J., Riahi, K. (2023). *Evaluating equity in European climate change mitigation pathways for the EU Scientific Advisory Board on Climate Change.* IIASA, Laxenburg. [pure.iiasa.ac.at/18830](https://pure.iiasa.ac.at/18830). Replication code: [doi:10.5281/zenodo.8035839](https://doi.org/10.5281/zenodo.8035839)
- Friedlingstein, P. et al. (2022). Global Carbon Budget 2021. *Earth System Science Data* 14, 1917–2005. [doi:10.5194/essd-14-1917-2022](https://doi.org/10.5194/essd-14-1917-2022)
- Weber, K., Brunner, C., Knutti, R. (2026). Tracking country-level mitigation progress using NGHGI-consistent carbon budgets. *Nature Communications*. [doi:10.1038/s41467-026-69078-9](https://doi.org/10.1038/s41467-026-69078-9)
- Weber, K., Knutti, R., Brun, L., Brunner, C. (2026b). Limiting warming by CO2 and methane mitigation in an expanded scenario space. *Communications Earth & Environment*. [doi:10.1038/s43247-026-03832-1](https://doi.org/10.1038/s43247-026-03832-1)
- Pelz, S. et al. (2025). Entry points for assessing "fair shares" in national mitigation contributions. *Environmental Research Letters*. [doi:10.1088/1748-9326/ada45f](https://doi.org/10.1088/1748-9326/ada45f)
- Huppmann, D. (2026). Scenario Compass Initiative - Pathways Ensemble 2025 (v1.0). Zenodo. [doi:10.5281/zenodo.18598251](https://doi.org/10.5281/zenodo.18598251)
- Byers, E. et al. (2022). AR6 Scenarios Database (v1.1). IIASA and IAMC. [doi:10.5281/zenodo.5886911](https://doi.org/10.5281/zenodo.5886911)
- Pelz, S. et al. (2025). Using net-zero carbon debt to track climate overshoot responsibility. *PNAS*. [doi:10.1073/pnas.2409316122](https://doi.org/10.1073/pnas.2409316122)

The full list is on the [References](references.md) page.
