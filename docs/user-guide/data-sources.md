---
title: Data Sources & Licensing
description: Input data sources, licensing terms, and attribution requirements
icon: material/database-check
---

# Data Sources & Licensing

fair-shares downloads most of its input datasets from pinned URLs with `uv run fair-shares fetch-data`. A few small inputs ship with the repository: the region mapping, the carbon budget table and an example IAMC scenario file. This page documents the sources, licenses, and citation requirements.

---

## Quick Reference

Sources carry different terms. Check the per-source entry below before redistributing data or derived products:

| Data Type      | Source                 | License            | Citation Required |
| -------------- | ---------------------- | ------------------ | ----------------- |
| Emissions (default) | PRIMAP-hist v2.8  | **CC BY-NC-SA 4.0** | Yes              |
| Emissions (opt-in) | PRIMAP-hist v2.6.1 | **CC-BY-4.0**      | Yes               |
| Emissions (opt-in) | Global Carbon Budget 2025 (2025v15) | **CC-BY-4.0** | Yes   |
| LULUCF (default) | LULUCF Data Hub v4.0.0 | **CC-BY-4.0** (Zenodo) | Yes         |
| LULUCF (opt-in) | LULUCF Data Hub v3.1.1 | **CC-BY-4.0** (Zenodo) | Yes          |
| Population     | UN/OWID 2025           | Mixed — see below  | Yes               |
| GDP            | World Bank WDI 2025    | **CC-BY-4.0**      | Yes               |
| Gini (default) | World Bank WDI 2025 (SI.POV.GINI) | **CC-BY-4.0** | Yes    |
| Gini (opt-in)  | UNU-WIDER WIID 2025    | **CC BY-NC-SA 3.0 IGO** | Yes          |
| Regions        | regioniso3c (custom)   | **MIT**            | Optional          |
| Scenarios      | IPCC AR6 (Gidden 2023) | **CC-BY-4.0**      | Yes               |
| Scenarios (bunker share) | AR6 Scenarios Database v1.1, aviation and maritime CO2 | IIASA AR6 database licence; not redistributable | Yes |
| Scenarios (bunker share, optional) | Scenario Compass ensemble v1.0 | Research use; embargo terms until publication | Yes |
| Observed global CO2 (budgets from 2020) | Global Carbon Budget 2025 global workbook | **CC-BY-4.0** | Yes |
| Carbon budgets | Five sources in `data/rcbs/rcbs.yaml`: Lamboll et al. 2023, Forster et al. 2024, Forster et al. 2026, IPCC AR6 WGI (`ar6_2020`, `ar6_wg1_2021`). See [Carbon Budget Provenance](#carbon-budget-provenance) | Published values | Yes |
| Bunker fuels (default) | Global Carbon Budget 2025 (2025v15) | **CC-BY-4.0** | Yes |
| Bunker fuels (opt-in) | Global Carbon Budget 2024 | paper **CC-BY-4.0**; data product under GCP terms | Yes |

!!! warning "Outputs from the default sources carry non-commercial, share-alike terms"
    The default emissions source is PRIMAP-hist v2.8 (`primap-202609`). Its licence is CC BY-NC-SA 4.0. Allocation results from a default run include these data, so they carry the same terms: non-commercial use, and share-alike terms on anything you redistribute. Commercial use needs a licence from the dataset authors. For outputs under CC BY terms, set `active_emissions_source` to `primap-202503` (PRIMAP-hist v2.6.1) or `gcb-2025` (fossil CO2 only). `fair-shares cite` lists the terms for the sources of your run.

---

## Emissions Data

### PRIMAP-hist v2.8 (default)

**Source:** Gütschow, J., & Pflüger, M. (2026). The PRIMAP-hist national historical emissions time series (1750-2025) v2.8. Zenodo.

**DOI:** [10.5281/zenodo.22876287](https://doi.org/10.5281/zenodo.22876287)

**License:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), as stated on the Zenodo record. The metadata file inside the record says CC BY-NC 4.0. fair-shares records the stricter record-level terms. PRIMAP-hist moved to a non-commercial licence with v2.8.

**Location:** `data/emissions/primap-202609/`. A plain `fair-shares fetch-data` downloads it.

**What it provides:** National greenhouse gas emissions by country (1750-2025), including CO2 from fossil fuels, land use, and other GHGs. The latest years are partly extrapolated by the dataset authors. The pipeline uses the country-reported scenario (`HISTCR`), as for v2.6.1.

### PRIMAP-hist v2.6.1 (opt-in)

**Source:** Gütschow, J., Busch, D., & Pflüger, M. (2025). The PRIMAP-hist national historical emissions time series (1750-2023) v2.6.1. Zenodo.

**DOI:** [10.5281/zenodo.15016289](https://doi.org/10.5281/zenodo.15016289)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

**Location:** `data/emissions/primap-202503/`. Opt-in: fetch it with `fair-shares fetch-data --source primap-202503`.

**What it provides:** National greenhouse gas emissions by country (1750-2023). Select it with `active_emissions_source=primap-202503` for outputs under CC BY terms or to reproduce results built on data to 2023.

### Global Carbon Budget 2025 (opt-in)

**Source (data product):** Andrew, R. M., & Peters, G. P. (2025). The Global Carbon Project's fossil CO2 emissions dataset (2025v15). Zenodo. [doi:10.5281/zenodo.17417124](https://doi.org/10.5281/zenodo.17417124)

**Source (paper):** Friedlingstein, P., et al. (2026). Global Carbon Budget 2025. *Earth System Science Data*, 18, 3211-3288. [doi:10.5194/essd-18-3211-2026](https://doi.org/10.5194/essd-18-3211-2026)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Cite both DOIs.

**Location:** `data/emissions/gcb-2025/`. Opt-in: a plain `fair-shares fetch-data` does not download it. Fetch it with `fair-shares fetch-data --source gcb-2025`.

**What it provides:** Territorial fossil CO2 (`co2-ffi`) by country, 1850 to 2024, in MtCO2 per year. Select it with `active_emissions_source=gcb-2025`. The default is `primap-202609`. The source declares `co2-ffi` only, and the pipeline asks it for no other category.

**Processing rules** (`notebooks/101_data_preprocess_emiss_gcb-2025.py`):

- **Blank years count as zero.** The file leaves a year blank where it reports those emissions under another entity or reports none. Most blanks precede a country's first record. The GCB global total treats every blank as zero.
- **The world row excludes bunkers and the oil fires.** World row = GCB global total minus international shipping, international aviation and the 1991 Kuwaiti oil fires (478 MtCO2). These three belong to no country. The run saves them to `emiss_co2-ffi_excluded_timeseries.csv`, so that world row + excluded rows = GCB global total for every year.
- **Rows outside the region mapping go to rest-of-world.** Kosovo and Antarctica have ISO codes that the region mapping lacks. "Pacific Islands (Palau)" (1955 to 1991, 4.43 MtCO2 in total) and "Ryukyu Islands" (1965 to 1972, 0.82 MtCO2 in total) have no ISO code. The official GCB workbook keeps both in its World column and in no country column, and this source does the same.
- **Bunkers come from the same file.** Every run deducts observed international shipping plus aviation from this file (`gcb-2025` is the default `bunkers_source`). Notebook `108_data_preprocess_bunkers_gcb-2025` extracts them.
- **Coverage rule.** An analysis country needs an emissions record before 1990 and population data for every year from 1850 (`coverage` in `data_sources_unified.yaml`). A blank in the raw file is not a record. The run saves each country's first recorded year to `emiss_co2-ffi_first_recorded_year.csv`. Eight countries have their first record in 1990 or later: Andorra, Lesotho and Tuvalu (1990), Namibia (1991), Micronesia, the Marshall Islands and Palau (1992) and Timor-Leste (1994). Their zero-filled values for 1850 to 1989 are all zero, and a responsibility adjustment over those years divides by zero. Macao has population data from 1950. These nine countries join rest-of-world in every allocation, so the country set is the same for every start year from 1850. Rest-of-world is the world row minus the analysis countries, so it takes their emissions, population and GDP. The column `coverage_rule_failed` in `country_data_coverage_summary.csv` names the failed test for each country. Runs on the PRIMAP sources have no coverage rule and keep their country set.

With the default GDP and population sources, a `co2-ffi` run holds 168 analysis countries plus rest-of-world: the 177 of a PRIMAP v2.6.1 run minus these nine. A `co2` run with `melo-2026-v4` holds 160, because that LULUCF source has no series for eight more countries (Egypt, Hong Kong, Kiribati, Libya, the Maldives, Nauru, Qatar and Sierra Leone). World `co2-ffi` in 2020 is 34,319 MtCO2 (PRIMAP v2.6.1: 34,343).

---

## LULUCF Data

### Melo et al. (NGHGI LULUCF), v3.1.1 (opt-in)

**Source:** Melo, J., et al. (2026). The LULUCF Data Hub: translating global land use emissions estimates into the national GHG inventory framework (Version 3.1.1, 2025 NGHGI release). Zenodo.

**DOI:** [10.5281/zenodo.18352395](https://doi.org/10.5281/zenodo.18352395)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) (Zenodo)

**Location:** `data/lulucf/melo-2026/`

**What it provides:** NGHGI-reported CO2 LULUCF fluxes for 185 countries (2000–2023). Select it with `active_lulucf_source=melo-2026`. Fetch it with `fair-shares fetch-data --source melo-2026`. See [Other Operations](../science/other-operations.md) for how NGHGI LULUCF data enters the pipeline.

### Melo et al. (NGHGI LULUCF), v4.0.0 (default)

**Source:** Melo, J., et al. (2026). The LULUCF Data Hub: translating global land use emissions estimates into the national GHG inventory framework (Version 4.0.0, 2026 NGHGI release). Zenodo.

**DOI:** [10.5281/zenodo.22828743](https://doi.org/10.5281/zenodo.22828743)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) (Zenodo)

**Location:** `data/lulucf/melo-2026-v4/`

**What it provides:** The gap-filled NGHGI CO2 LULUCF file for 187 countries (2000–2024). Used for all emission categories that include land use (co2, all-ghg). A plain `fair-shares fetch-data` downloads it. See [Other Operations](../science/other-operations.md) for how NGHGI LULUCF data enters the pipeline.

---

## Population Data

### UN/OWID

**Source:** United Nations World Population Prospects via Our World in Data (2025).

**License:** Mixed. The UN WPP bulk data files are governed by the [UN Terms of Use](https://www.un.org/en/about-us/terms-of-use), which are restrictive; the CC BY 3.0 IGO grant documented for WPP is stated for the report's figures and tables, not demonstrably for the projection files. OWID's own charts and processing are CC BY, but OWID [does not relicense upstream data](https://ourworldindata.org/faqs) — the historical series splices HYDE, Gapminder and UN WPP, each under its own terms. Check the upstream terms before redistributing.

**Location:** `data/population/un-owid-2025/`

**What it provides:** National population time series (historical and projections).

---

## Economic Data

### World Bank WDI

**Source:** World Bank World Development Indicators (2025).

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

**Location:** `data/gdp/wdi-2025/`

**What it provides:** GDP per capita (PPP, constant 2021 USD). Observed series; ends at 2025.

!!! note "PPP vs MER: a normative choice"
    The choice between PPP and MER GDP measures is not purely technical — it is a normative decision that can significantly affect allocation results [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). See [From Principle to Code](../science/principle-to-code.md) for further discussion.

!!! note "Post-observation GDP window"
    `wdi-2025` is observed data only and ends at 2025, while population data extends to ~2100. When an allocation cumulative window runs past 2025, the per-capita budget and pathway primitives forward-fill GDP per capita from 2025 to cover the rest of the window. This holds the cross-country capability ratios of 2025 constant. The cumulative-per-capita-convergence primitives instead compute their per-country capability scalar only over the observed-GDP years (no forward-fill). To use projected GDP for the post-observation window (SSP2, a custom growth assumption, or a future-extended WDI release), extend the input `gdp_ts` time series before calling the allocation function. See [Building Blocks](../science/allocations.md#building-blocks) in the science docs for the full description.

---

## Inequality Data

Two Gini sources are configured. `wdi-2025` is the default; `unu-wider-2025`
(WIID) still works and is selected with `active_gini_source=unu-wider-2025`.

### World Bank WDI Gini index (default)

**Source:** World Bank, World Development Indicators, Gini index (`SI.POV.GINI`), 2025 export. The World Bank sources this indicator from its own Poverty and Inequality Platform (PIP). No DOI is issued; cite by name.

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), the World Bank's [default for its own open datasets](https://datacatalog.worldbank.org/public-licenses).

**Location:** `data/gini/wdi-2025/`

**What it provides:** Gini coefficients for 150 countries, taking each country's latest observation in 2015–2023 (`selection: latest-available`, `year_window: [2015, 2023]`). Survey-based Gini is sparse in any single year — a single-year rule would cover about 70 countries.

!!! note "Income vs consumption Gini"
    PIP reports consumption-based Gini for most low- and middle-income countries and income-based Gini elsewhere; WIID pools income-based series. Consumption Gini is systematically lower for the same country-year, and the gap is large for some countries (India 0.255 vs 0.515, Côte d'Ivoire 0.353 vs 0.607, Bangladesh 0.309 vs 0.499, South Africa 0.541 vs 0.670). Because higher Gini raises measured capability, the two sources give materially different capability-based allocations. This is a choice about which welfare concept the capability measure rests on, not a data-plumbing detail.

!!! note "Countries without a Gini value"
    Analysis-country membership depends on emissions, GDP and population — not on Gini. A country with no Gini value stays in the analysis and receives the analysis-country mean, the same value Rest-of-World gets, flagged as `gini_imputed` in `country_data_coverage_summary.csv`. Set `general.gini_missing_policy: strict` to stop the run instead. Under the default Gini source, 35 of 177 analysis countries in a PRIMAP v2.6.1 `co2-ffi` run carry an imputed Gini, Saudi Arabia among them.

### UNU-WIDER WIID (opt-in)

**Source:** UNU-WIDER World Income Inequality Database (WIID), Version 29 April 2025. [doi:10.35188/UNU-WIDER/WIID-290425](https://doi.org/10.35188/UNU-WIDER/WIID-290425)

**License:** [CC BY-NC-SA 3.0 IGO](https://creativecommons.org/licenses/by-nc-sa/3.0/igo/), per UNU-WIDER's [copyright terms](https://www.wider.unu.edu/about/copyright). The NonCommercial and ShareAlike clauses travel with derived Gini values, so they are incompatible with a plain CC BY compilation.

**Location:** `data/gini/unu-wider-2025/`. Opt-in: a plain `fair-shares fetch-data` does not download it. Fetch it with `fair-shares fetch-data --source unu-wider-2025` if it is not already present.

**What it provides:** Gini coefficients for 194 countries, taking each country's latest high-quality observation and falling back to the latest of any quality (`selection: latest-high-quality`, no year window). Coverage is broader than WDI but older: 34 of the 194 values predate 2010, and four are states that no longer exist.

!!! warning "Outputs built on WIID carry its NonCommercial and ShareAlike terms"
    The NonCommercial and ShareAlike terms travel with the derived Gini values, including a table of them. A run on `primap-202503` or `gcb-2025` with WIID Gini therefore gives no CC BY outputs.

---

## Regional Mappings

### regioniso3c

**Source:** Custom mapping by Setu Pelz (2024).

**GitHub:** [setupelz/regioniso3c](https://github.com/setupelz/regioniso3c)

**License:** [MIT](https://opensource.org/licenses/MIT)

**Location:** `data/regions/`

**What it provides:** Consistent mapping between ISO3C country codes and model region definitions.

!!! note "IAMC regional data"
    When working with IAMC-format files, the library uses **the regions defined in your input file**, not fixed mappings. The bundled regional mapping is only for converting country-level outputs to model regions.

---

## Carbon Budget Provenance

The global remaining carbon budget (RCB) is a key input for budget-based allocations. Different sources, temperature targets, and probability levels produce substantially different budgets. The table below documents the primary sources used and referenced in fair-shares:

| Source              | Budget              | Temperature | Probability | Baseline | Notes                                              |
| ------------------- | ------------------- | ----------- | ----------- | -------- | -------------------------------------------------- |
| Lamboll et al. 2023 | 250 GtCO2           | 1.5°C       | 50%         | 2023     | Methodology paper for updated RCB estimates        |
| Forster et al. 2024 | 200 GtCO2           | 1.5°C       | 50%         | 2024     | IGCC 2023                                          |
| IPCC AR6 WGI        | 500 GtCO2           | 1.5°C       | 50%         | 2020     | Original AR6 estimates from WG1 Chapter 5          |
| Forster et al. 2026 | 130 GtCO2           | 1.5°C       | 50%         | 2026     | IGCC 2025, Table 8; also 1.7°C and 2°C. Needs emissions through 2025; one missing year takes the last observed value |
| IPCC AR6 WGI (SPM)  | 500 GtCO2           | 1.5°C       | 50%         | 2020     | Table SPM.2; also 1.7°C and 2°C (`ar6_wg1_2021`)   |

Each source carries several labels (`rcbs.yaml` lists them). The scenario-derived terms of every budget come from role-matched scenario sets. See [RCB sources and scenario sets](../science/other-operations.md#rcb-sources-and-scenario-sets).

**Citations:**

> Lamboll, R. D., et al. (2023). Assessing the size and uncertainty of remaining carbon budgets. _Nature Climate Change_, 13, 1360–1367. [doi:10.1038/s41558-023-01848-5](https://doi.org/10.1038/s41558-023-01848-5)

> Forster, P. M., et al. (2024). Indicators of Global Climate Change 2023. _Earth System Science Data_, 16, 2625–2658. [doi:10.5194/essd-16-2625-2024](https://doi.org/10.5194/essd-16-2625-2024)

> Forster, P. M., et al. (2026). Indicators of Global Climate Change 2025. _Earth System Science Data_, 18, 3889–3933. [doi:10.5194/essd-18-3889-2026](https://doi.org/10.5194/essd-18-3889-2026)

> IPCC (2021). Summary for Policymakers. In _Climate Change 2021: The Physical Science Basis_. Cambridge University Press. [doi:10.1017/9781009157896.001](https://doi.org/10.1017/9781009157896.001)

!!! note "Budget choice is normatively significant"
    The choice of carbon budget (source, temperature target, probability level) corresponds to Entry Point 2 of the fair share quantification framework — the allocation quantity [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). Results are sensitive to this choice. Always document the budget source, temperature target, and probability level when reporting allocation results.

---

## Scenario Data

### IPCC AR6 Scenarios

**Source:** Gidden, M. J., et al. (2023). AR6 Scenarios Database hosted by IIASA.

**DOI:** [10.5281/zenodo.10158920](https://doi.org/10.5281/zenodo.10158920) — the v2 version record that `fetch-data` downloads (concept DOI: [10.5281/zenodo.8411053](https://doi.org/10.5281/zenodo.8411053), which always resolves to the latest version)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

**Location:** `data/scenarios/ipcc_ar6_gidden/`

**What it provides:** IPCC AR6 WGIII emission pathways in the NGHGI reanalysis, with the AR6 climate assessment in the metadata. They supply the scenario sets of every budget and the non-CO2 pathways.

### AR6 Scenarios Database (bunker components)

**Source:** Byers, E., Krey, V., Kriegler, E., Riahi, K., et al. (2022). AR6 Scenarios Database (v1.1). IAMC and IIASA. [doi:10.5281/zenodo.5886911](https://doi.org/10.5281/zenodo.5886911)

**Terms:** the IIASA AR6 Scenarios Database licence. It allows use for scientific research and science communication and restricts redistribution of substantial parts. The file is never committed.

**Location:** `data/scenarios/ipcc_ar6_bunkers/ar6_bunkers_world.csv` (registry name `ipcc_ar6_bunkers`, manual tier). Write it with `uv run python -c "from fair_shares.library.utils.data.scenario_sources import fetch_ar6_bunkers; fetch_ar6_bunkers()"`. The function reads the public database through pyam without a login and writes a provenance file next to the CSV.

**What it provides:** world aviation and maritime CO₂ of every AR6 scenario that reports them. The database has no bunker variable, so bunkers are 0.6 × aviation plus maritime [Weber 2026](https://doi.org/10.1038/s41467-026-69078-9).

### Scenario Compass ensemble (optional, bunker share)

**Source (data):** Huppmann, D., et al. (2026). Scenario Compass Initiative - Pathways Ensemble 2025 (v1.0). Zenodo. [doi:10.5281/zenodo.18598251](https://doi.org/10.5281/zenodo.18598251)

**Source (manuscript):** Riahi, K., et al. (2026). Mitigation benchmarks from the 2025 community update of global emissions pathways. Research Square preprint. [doi:10.21203/rs.3.rs-8891091/v1](https://doi.org/10.21203/rs.3.rs-8891091/v1)

**Terms:** The workbook states: "The data may be used for scientific research purposes. However, users must strictly adhere to the applicable Nature editorial policies and embargo rules until the manuscript has been formally published." The file is never committed or redistributed.

**Location:** `data/scenarios/sci-2025-v1.0/` (registry name `sci-2025`; download from the Scenario Compass platform). The version in `scenario_sources.yaml` selects the file.

**What it provides:** scenarios that report international aviation and shipping CO₂. Those that reach net zero enter the bunker share of net CO₂ that the bunker term applies to every budget. See [Bunker term](../science/other-operations.md#bunker-term) for the method.

**Versions:** fair-shares reads v1.0. Later releases exist (v1.1, v1.2, and v2.0 at [doi:10.5281/zenodo.23232097](https://doi.org/10.5281/zenodo.23232097)). fair-shares does not read v2.0.

### Global Carbon Budget 2025 global workbook

**Source:** Global Carbon Project (2026). Supplemental data of Global Carbon Budget 2025 (Version 1.1). [doi:10.18160/GCP-2025](https://doi.org/10.18160/GCP-2025), with the GCB 2025 paper above.

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) (ICOS CCBY4 Data Licence).

**Location:** `data/emissions/gcb-2025/Global_Carbon_Budget_2025_v1.0.xlsx` (registry name `gcb-2025-global`, manual download behind the ICOS licence page).

**What it provides:** observed global net CO₂ (fossil minus cement carbonation plus bookkeeping land use), which expresses each budget from the start of 2020 for its volume-matched scenario set.

---

## Bunker Fuels

### Global Carbon Budget 2024

**Source (paper):** Friedlingstein, P., et al. (2025). Global Carbon Budget 2024. *Earth System Science Data*, 17, 965–1039. [doi:10.5194/essd-17-965-2025](https://doi.org/10.5194/essd-17-965-2025)

**Source (data product):** Global Carbon Project (2024). Supplemental data of Global Carbon Budget 2024 (Version 1.0). [doi:10.18160/GCP-2024](https://doi.org/10.18160/GCP-2024)

**License:** The paper is [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The data product is **not** CC-licensed — it carries the Global Carbon Project's own terms of use, which condition use on citing the original data sources. Cite both DOIs; the paper DOI is not the data DOI.

**Location:** `data/bunkers/gcb-2024/`

**What it provides:** International aviation and shipping CO2 emissions, used to deduct bunker fuels from national remaining carbon budgets. See [Other Operations](../science/other-operations.md) for methodology.

Each emissions source names its bunker data (`bunkers_source` in `data_sources_unified.yaml`). The default is the [Global Carbon Budget 2025](#global-carbon-budget-2025-opt-in) file (`gcb-2025`). This 2024 workbook stays available as `bunkers_source: gcb-2024`.

---

## Attribution in Your Work

When publishing results generated with fair-shares, cite:

1. **fair-shares library** (see [CITATION.cff](https://github.com/setupelz/fair-shares/blob/main/CITATION.cff))
2. **Data sources used** (listed above)

`CITATION.cff` is the source of truth for the software citation. To print the software citation plus every data source a run uses:

```bash
uv run fair-shares cite            # as text
uv run fair-shares cite --bibtex   # as BibTeX entries
```

---

## Adding Your Own Data

See [Adding Data Sources](../dev-guide/adding-data-sources.md) for instructions on integrating additional datasets.

---

## See Also

- **[Output Schema](output-schema.md)** - How data sources are tracked in outputs
- **[User Guide](index.md)** - Workflow documentation
- **[CITATION.cff](https://github.com/setupelz/fair-shares/blob/main/CITATION.cff)** - How to cite fair-shares
