---
title: Data & licences
description: Input data sources, their licences and what they mean for publishing results
---

# Data & licences

`uv run fair-shares fetch-data` downloads most inputs from pinned URLs. The region mapping, the carbon budget table and an example IAMC file ship with the repository.
`uv run fair-shares fetch-data --list` prints the version, licence and citation of every source, and `uv run fair-shares cite` lists what a run must cite.

## Can I publish this?

- **Results from a default run:** yes, for non-commercial use, under share-alike terms. The default emissions source, PRIMAP-hist v2.8, is CC BY-NC-SA 4.0, and its terms travel with the allocation results. Commercial use needs a licence from the dataset authors.
- **CC BY results:** set `active_emissions_source` to `primap-202503` (PRIMAP-hist v2.6.1) or `gcb-2025` (fossil CO2 only), and keep the default World Bank Gini. WIID Gini adds non-commercial, share-alike terms to any run.
- **The input data themselves:** check each source below.
    - UN WPP population: the UN Terms of Use govern the projection files; check them before republishing population data.
    - AR6 Scenarios Database: research and science communication; no redistribution of substantial parts.
    - Scenario Compass: research use only, under the Nature editorial policies and embargo rules until Riahi et al. is published.
    - ScenarioMIP-CMIP7: research use; no redistribution of substantial parts; state release v0.1 and cite its DOI.
    - CMIP7 historical (IAM regions): share-alike terms on anything derived that you redistribute.
- **Global Carbon Budget 2024 bunkers (opt-in):** the Global Carbon Project asks you to cite the original data sources and to consider co-authorship where its data are essential to a study. This is a request, not a licence condition.
- **Always:** cite fair-shares and every data source the run used. Each saved run lists them in its `CITATIONS.md`.

| Data | Source | Licence | Redistributable |
| --- | --- | --- | --- |
| Emissions (default) | PRIMAP-hist v2.8 | **CC BY-NC-SA 4.0** | No |
| Emissions (opt-in) | PRIMAP-hist v2.6.1 | CC BY 4.0 | Yes |
| Emissions (opt-in) | Global Carbon Budget 2025 (2025v15) | CC BY 4.0 | Yes |
| Land-use CO2 (default) | LULUCF Data Hub v4.0.0 | CC BY 4.0 | Yes |
| Land-use CO2 (opt-in) | LULUCF Data Hub v3.1.1 | CC BY 4.0 | Yes |
| Population | UN WPP via OWID | Mixed, see below | Check upstream |
| GDP | World Bank WDI | CC BY 4.0 | Yes |
| Gini (default) | World Bank WDI (`SI.POV.GINI`) | CC BY 4.0 | Yes |
| Gini (opt-in) | UNU-WIDER WIID | **CC BY-NC-SA 3.0 IGO** | Under its terms |
| Scenarios | AR6 reanalysis (Gidden et al. 2023) | CC BY 4.0 | Yes |
| Scenarios (bunker share, net zero) | AR6 Scenarios Database v1.1 | IIASA AR6 database licence | No |
| Scenarios (bunker share; non-CO2 opt-in) | Scenario Compass ensemble v2.0 (v1.0 selectable) | Research use; embargo until publication | No |
| Scenarios (bunker share; non-CO2 opt-in) | ScenarioMIP-CMIP7 v0.1 | Research use | No |
| IAM regional history (notebook 400) | CMIP7 ScenarioMIP historical 2025.12.07 | **CC BY-SA 4.0** | Under its terms |
| Observed global CO2 (budgets from 2020) | Global Carbon Budget 2025 global workbook | CC BY 4.0 | Yes |
| Bunkers (default) | Global Carbon Budget 2025 (2025v15) | CC BY 4.0 | Yes |
| Bunkers (opt-in) | Global Carbon Budget 2024 | Paper CC BY 4.0; data under GCP terms | Under its terms |
| Carbon budgets | Five published sources in `data/rcbs/rcbs.yaml` | Published values | Yes, cited |
| Regions | regioniso3c | MIT | Yes |

---

## Emissions

### PRIMAP-hist v2.8 (default)

Gütschow, J., & Pflüger, M. (2026). The PRIMAP-hist national historical emissions time series (1750-2025) v2.8. Zenodo. [doi:10.5281/zenodo.22876287](https://doi.org/10.5281/zenodo.22876287)

- **Licence:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), as stated on the Zenodo record. The metadata file inside the record says CC BY-NC 4.0, and fair-shares records the stricter record-level terms. PRIMAP-hist moved to a non-commercial licence with v2.8.
- **Provides:** national greenhouse gas emissions, 1750 to 2025. The dataset authors partly extrapolate the latest years. The pipeline uses the country-reported scenario (`HISTCR`).
- **Location:** `data/emissions/primap-202609/`; a plain `fetch-data` downloads it.

### PRIMAP-hist v2.6.1 (opt-in)

Gütschow, J., Busch, D., & Pflüger, M. (2025). The PRIMAP-hist national historical emissions time series (1750-2023) v2.6.1. Zenodo. [doi:10.5281/zenodo.15016289](https://doi.org/10.5281/zenodo.15016289)

- **Licence:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Provides:** national emissions, 1750 to 2023. Select it with `active_emissions_source=primap-202503` for CC BY outputs or to reproduce results built on data to 2023.
- **Location:** `data/emissions/primap-202503/`; `fetch-data --source primap-202503`.

### Global Carbon Budget 2025 (opt-in)

Andrew, R. M., & Peters, G. P. (2025). The Global Carbon Project's fossil CO2 emissions dataset (2025v15). Zenodo. [doi:10.5281/zenodo.17417124](https://doi.org/10.5281/zenodo.17417124). Paper: Friedlingstein, P., et al. (2026). Global Carbon Budget 2025. *Earth System Science Data*, 18, 3211-3288. [doi:10.5194/essd-18-3211-2026](https://doi.org/10.5194/essd-18-3211-2026)

- **Licence:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Cite both DOIs.
- **Provides:** territorial fossil CO2 (`co2-ffi` only) by country, 1850 to 2024, in Mt CO2 per year. Select it with `active_emissions_source=gcb-2025`.
- **Location:** `data/emissions/gcb-2025/`; `fetch-data --source gcb-2025`.

Its processing rules, its coverage rule and the resulting country sets are in [Global Carbon Budget processing](../science/other-operations.md#gcb-processing).

---

## Land-use CO2

A land-use source carries an accounting basis, and categories with land use (`co2`, `all-ghg`) follow it end to end.

### National inventories (NGHGI basis)

Melo, J., et al. (2026). The LULUCF Data Hub: translating global land use emissions estimates into the national GHG inventory framework. Zenodo. Both releases are [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

| Release | Key | DOI | Coverage | Location |
| --- | --- | --- | --- | --- |
| v4.0.0, 2026 NGHGI release (default) | `melo-2026-v4` | [10.5281/zenodo.22828743](https://doi.org/10.5281/zenodo.22828743) | Gap-filled, 187 countries, 2000 to 2024 | `data/lulucf/melo-2026-v4/` |
| v3.1.1, 2025 NGHGI release (opt-in) | `melo-2026` | [10.5281/zenodo.18352395](https://doi.org/10.5281/zenodo.18352395) | 185 countries, 2000 to 2023 | `data/lulucf/melo-2026/` |

On this basis the global budget is corrected for the gap between inventory and model land-use accounting ([Convention gap](../science/remaining-carbon-budgets.md#convention-gap)).

### Bookkeeping models (model basis)

Global Carbon Project (2026). Supplemental data of Global Carbon Budget 2025: National Land Use Change Carbon Emissions 2025 v1.0. ICOS Carbon Portal. [10.18160/GCP-2025](https://doi.org/10.18160/GCP-2025). Paper: Friedlingstein et al. (2026), [10.5194/essd-18-3211-2026](https://doi.org/10.5194/essd-18-3211-2026). Cite the bookkeeping-model papers named in each sheet too.

- **Key:** `gcb-2025-luc`. **Location:** `data/lulucf/gcb-2025-luc/`.
- **Provides:** net land-use change CO2 by country, 1850 to 2024, the mean of the bookkeeping models BLUE, OSCAR and LUCE; the world row is the workbook's `Global` column. This is how integrated assessment and energy-system models count land-use CO2.
- **On this basis:** no convention-gap correction of the global budget; the rebase to 2020 uses bookkeeping land use; AR6 scenario CO2 and Kyoto gases are used as reported.
- **Licence:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (ICOS data licence). ICOS asks you to cite the exact DOI or PID, to point your users to ICOS for updates, and to tell the data providers about publications that use the data; the workbook adds that co-authorship may need to be considered when the data are essential to the work.
- **Download (manual):** open the [ICOS record](https://meta.icos-cp.eu/objects/milTbWkl0G-MSpdYG3IBIfzy), click Download, tick the licence confirmation and download. Extract the zip into `data/lulucf/gcb-2025-luc/`.

---

## Population, GDP and Gini

### Population: UN WPP via Our World in Data

United Nations World Population Prospects via Our World in Data (grapher export retrieved 16 October 2026, data to 2023), and UN World Population Prospects 2024 projections. Location: `data/population/un-owid-2025/`.

**Licence: mixed.** The UN WPP bulk data files fall under the [UN Terms of Use](https://www.un.org/en/about-us/terms-of-use), which are restrictive. The CC BY 3.0 IGO grant documented for WPP covers the report's figures and tables, and not demonstrably the projection files. OWID's own charts and processing are CC BY, but OWID [does not relicense upstream data](https://ourworldindata.org/faqs); its historical series splices HYDE, Gapminder and UN WPP, each under its own terms. Check the upstream terms before redistributing.

**Coverage.** The OWID export starts Ireland in 1950, and about 16 territories after 1850: BES, BLM, BMU, CUW, CYM, GGY, GIB, IMN, MAC, MAF, MNP, NIU, SHN, SXM, VGB and WLF. An allocation that needs population before a country's first year places that country in rest of world.

### GDP: World Bank WDI

World Bank World Development Indicators, export of 8 October 2026. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Location: `data/gdp/wdi-2025/`.
It provides GDP in PPP (constant 2021 international dollars) and MER (constant 2015 US dollars), observed to 2025.
The choice between PPP and MER is a normative decision that can significantly affect allocation results [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f).
After 2025 the allocation functions forward-fill GDP per capita ([Capability timing](../science/allocations.md#capability-timing)).

### Gini: World Bank WDI (default)

World Bank, World Development Indicators, Gini index (`SI.POV.GINI`), export of 8 October 2026. The World Bank sources it from its Poverty and Inequality Platform (PIP). No DOI is issued; cite it by name. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), the World Bank's [default for its own open datasets](https://datacatalog.worldbank.org/public-licenses). Location: `data/gini/wdi-2025/`.

It gives Gini coefficients for 150 countries, each country's latest observation in 2015 to 2023 (`selection: latest-available`, `year_window: [2015, 2023]`). Survey-based Gini is sparse in any one year; a single-year rule would cover about 70 countries.

### Gini: UNU-WIDER WIID (opt-in)

UNU-WIDER World Income Inequality Database (WIID), Version 8 September 2026. [doi:10.35188/UNU-WIDER/WIID-080926](https://doi.org/10.35188/UNU-WIDER/WIID-080926). Select it with `active_gini_source=unu-wider-2025`; `fetch-data --source unu-wider-2025`. Location: `data/gini/unu-wider-2025/`.

**Licence:** [CC BY-NC-SA 3.0 IGO](https://creativecommons.org/licenses/by-nc-sa/3.0/igo/), per UNU-WIDER's [copyright terms](https://www.wider.unu.edu/about/copyright). The non-commercial and share-alike terms travel with derived Gini values, including a table of them, so a run with WIID gives no CC BY outputs on any emissions source.

It gives Gini coefficients for 194 countries, each country's latest high-quality observation, falling back to the latest of any quality (`selection: latest-high-quality`, no year window). Coverage is broader than WDI but older: 32 of the 194 values predate 2010, and four are states that no longer exist.

!!! note "Income and consumption Gini"
    PIP reports consumption-based Gini for most low- and middle-income countries and income-based Gini elsewhere; WIID pools income-based series. Consumption Gini is systematically lower for the same country-year, and the gap is large for some countries (India 0.255 vs 0.515, Côte d'Ivoire 0.353 vs 0.607, Bangladesh 0.309 vs 0.499, South Africa 0.541 vs 0.670). Higher Gini raises measured capability, so the two sources give materially different capability-based allocations. This is a choice about which welfare concept the capability measure rests on.

A country without a Gini value stays in the analysis with an imputed value ([Analysis countries](../science/other-operations.md#analysis-countries)).

---

## Scenarios {#scenario-data}

### AR6 reanalysis (Gidden et al. 2023)

Gidden, M. J., et al. (2023). AR6 Scenarios Database hosted by IIASA. [doi:10.5281/zenodo.10158920](https://doi.org/10.5281/zenodo.10158920), the v2 record that `fetch-data` downloads (concept DOI [10.5281/zenodo.8411053](https://doi.org/10.5281/zenodo.8411053) resolves to the latest version). [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Location: `data/scenarios/ipcc_ar6_gidden/`.

IPCC AR6 WGIII emission pathways in the national-inventory reanalysis, with the AR6 climate assessment in the metadata. They supply the scenario sets of every budget and the non-CO2 pathways.

### AR6 Scenarios Database (manual)

Byers, E., Krey, V., Kriegler, E., Riahi, K., et al. (2022). AR6 Scenarios Database (v1.1). IAMC and IIASA. [doi:10.5281/zenodo.5886911](https://doi.org/10.5281/zenodo.5886911)

**Terms:** the IIASA AR6 Scenarios Database licence allows use for scientific research and science communication and restricts redistribution of substantial parts. The files are never committed.
Two manual inputs come from it, each read from the public database without a login. `uv run fair-shares fetch-data --source <key>` gives the steps:

- `ipcc_ar6_bunkers` (`data/scenarios/ipcc_ar6_bunkers/ar6_bunkers_world.csv`): world aviation and maritime CO2 of every AR6 scenario that reports them. The database has no bunker variable, so bunkers are 0.6 × aviation plus maritime [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9).
- `ipcc_ar6_climate` (`data/scenarios/ipcc_ar6_climate/ar6_climate_world.csv`): world harmonised-infilled CO2, reported CO2 and the MAGICCv7.5.3 GSAT median and 67th percentile of every AR6 scenario. Notebook 104 derives each scenario's net-zero year and warming at net zero from them ([Net zero](../science/scenario-sets.md#net-zero)).

### Scenario Compass ensemble (manual)

Huppmann, D., Riahi, K., Clarke, L., Hasegawa, T., et al. (2026). Scenario Compass Initiative - Pathways Ensemble 2026 (v2.0). Zenodo. [doi:10.5281/zenodo.23232097](https://doi.org/10.5281/zenodo.23232097). Release v1.0: Huppmann, D., et al. (2026). Scenario Compass Initiative - Pathways Ensemble 2025 (v1.0). [doi:10.5281/zenodo.18598251](https://doi.org/10.5281/zenodo.18598251). Manuscript: Riahi, K., et al. (2026). Mitigation benchmarks from the 2025 community update of global emissions pathways. Research Square preprint. [doi:10.21203/rs.3.rs-8891091/v1](https://doi.org/10.21203/rs.3.rs-8891091/v1)

**Terms:** IAMC licence. The workbook states: "The data may be used for scientific research purposes. However, users must strictly adhere to the applicable Nature editorial policies and embargo rules until the manuscript has been formally published." The file is never committed or redistributed.

**Location:** `data/scenarios/sci-2026-v2.0/SCI-2026_v2.0_pathways_ensemble_global.xlsx` (`sci-2026`, download from the Scenario Compass platform with a login). Release v1.0 sits at `data/scenarios/sci-2025-v1.0/` (`sci-2025`). The `version` key of the `sci` entry in `scenario_sources.yaml` selects the release.

**Provides:** scenarios that report bunkers, for the bunker share. Its non-CO2 term serves a budget source built on it (`non_co2_basis: sci`); no shipped budget is. [Scenario sets](../science/scenario-sets.md#scenario-compass) gives what it contributes and how its warming at net zero is derived.

### ScenarioMIP-CMIP7 ensemble (manual)

Riahi, K., van Vuuren, D., et al. (2026). Scenario data of the 'Socioeconomic, Emissions and Land Use Futures - The ScenarioMIP Pathways for CMIP7' (v0.1). Zenodo. [doi:10.5281/zenodo.22296051](https://doi.org/10.5281/zenodo.22296051)

**Terms:** copyright 2026 IIASA and contributing modeling teams. Use for scientific research is allowed; redistribution of substantial parts is prohibited. Every result states release v0.1 and cites the DOI. The file is never committed or redistributed.

**Location:** `data/scenarios/scenariomip-v0.1/ScenarioMIP_v0.1_global.xlsx` (`scenariomip-cmip7`, download from the [ScenarioMIP Explorer](https://scenariomip.apps.ece.iiasa.ac.at) after registration).

**Provides:** runs with international aviation and shipping CO2, in the default bunker-share pool ([Bunker share](../science/scenario-sets.md#bunker-share)).

### CMIP7 ScenarioMIP historical (IAM regions)

Nicholls, Z., Kikstra, J., Zecchetto, M., & Hoegner, A. (2025). CMIP7 ScenarioMIP historical timeseries for harmonisation and simple climate model workflow (2025.12.07). Zenodo. [doi:10.5281/zenodo.17845154](https://doi.org/10.5281/zenodo.17845154)

**Licence:** [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The Zenodo record metadata say CC0; the dataset authors confirmed that the share-alike licence is deliberate. Its share-alike terms apply to anything you redistribute that is derived from it.
**Provides:** country-level historical emissions that notebook 400 aggregates to model regions to back-fill an IAM scenario (`src/fair_shares/conf/data_sources/iamc_data_sources.yaml`). It combines CEDS, GFED/BB4CMIP7, the Global Carbon Budget and published inversions for HFCs and ozone-depleting substances; cite those component datasets too when you report values derived from it.
**Location:** `data/emissions/cmip7-historical-2025.12.07/`; `fetch-data --all` or on first use.

---

## Budgets and bunkers

### Published carbon budgets

`data/rcbs/rcbs.yaml` holds five published sources. The budget label, temperature and likelihood of each are in [Remaining carbon budgets](../science/remaining-carbon-budgets.md#published-budgets).

| Source | 1.5 °C, 50% | Budget from | Notes |
| --- | --- | --- | --- |
| [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5) | 250 Gt CO2 | 2023 | Methodology paper for updated budget estimates |
| [Forster 2024](https://doi.org/10.5194/essd-16-2625-2024) | 200 Gt CO2 | 2024 | IGCC 2023 |
| [Forster 2026](https://doi.org/10.5194/essd-18-3889-2026) | 130 Gt CO2 | 2026 | IGCC 2025, Table 8; also 1.7 °C and 2 °C |
| [IPCC 2021 SPM](https://doi.org/10.1017/9781009157896.001) (`ar6_2020`, `ar6_wg1_2021`) | 500 Gt CO2 | 2020 | Table SPM.2; `ar6_wg1_2021` adds 1.7 °C and 2 °C |

The choice of budget (source, temperature and likelihood) is entry point 2 of the fair share quantification framework, the allocation quantity [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). Results are sensitive to it, so report all three with every result.

### Global Carbon Budget 2025 global workbook (manual)

Global Carbon Project (2026). Supplemental data of Global Carbon Budget 2025 (Version 1.1). [doi:10.18160/GCP-2025](https://doi.org/10.18160/GCP-2025), with the GCB 2025 paper above. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (ICOS CCBY4 Data Licence). Location: `data/emissions/gcb-2025/Global_Carbon_Budget_2025_v1.0.xlsx` (`gcb-2025-global`, behind the ICOS licence page).
It provides observed global net CO2 (fossil minus cement carbonation plus bookkeeping land use), which expresses each budget from the start of 2020.

### Global Carbon Budget 2024 (opt-in bunkers)

Paper: Friedlingstein, P., et al. (2025). Global Carbon Budget 2024. *Earth System Science Data*, 17, 965-1039. [doi:10.5194/essd-17-965-2025](https://doi.org/10.5194/essd-17-965-2025). Data: Global Carbon Project (2024). Supplemental data of Global Carbon Budget 2024 (Version 1.0). [doi:10.18160/GCP-2024](https://doi.org/10.18160/GCP-2024). Location: `data/bunkers/gcb-2024/`.

**Licence:** the paper is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The data product is **not** CC-licensed. It carries the Global Carbon Project's terms of use, which ask that the original data sources be cited alongside it, and note that where the data are essential to a study, co-authorship may need to be considered. That is a request from the providers, not a licence condition. Cite both DOIs; the paper DOI is not the data DOI.

Each emissions source names its bunker data (`bunkers_source` in `data_sources_unified.yaml`). The default is the [Global Carbon Budget 2025](#global-carbon-budget-2025-opt-in) file; this workbook stays available as `bunkers_source: gcb-2024` ([Bunker deduction](../science/remaining-carbon-budgets.md#bunker-deduction)).

---

## Regions

[regioniso3c](https://github.com/setupelz/regioniso3c), a custom mapping by Setu Pelz (2024), [MIT](https://opensource.org/licenses/MIT), in `data/regions/`. It maps ISO3 country codes to model regions and converts country outputs to regions.
IAMC workflows use the regions defined in your input file instead ([IAM model regions](iamc-regional-fair-shares.md)).

## Citing

Cite fair-shares ([CITATION.cff](https://github.com/setupelz/fair-shares/blob/main/CITATION.cff) is the source of truth) and every data source a run used:

```bash
uv run fair-shares cite            # as text
uv run fair-shares cite --bibtex   # as BibTeX entries
```

To add a source, see [Adding data sources](../dev-guide/adding-data-sources.md).
