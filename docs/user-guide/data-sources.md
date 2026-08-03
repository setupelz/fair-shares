---
title: Data Sources & Licensing
description: Bundled data sources, licensing terms, and attribution requirements
icon: material/database-check
---

# Data Sources & Licensing

fair-shares bundles several datasets to enable allocations without external dependencies. This page documents the sources, licenses, and citation requirements.

---

## Quick Reference

Bundled sources carry different terms. Check the per-source entry below before redistributing data or derived products:

| Data Type      | Source                 | License            | Citation Required |
| -------------- | ---------------------- | ------------------ | ----------------- |
| Emissions      | PRIMAP-hist v2.6.1     | **CC-BY-4.0**      | Yes               |
| LULUCF         | Melo et al. 2026 v3.1  | **CC-BY-4.0** (Zenodo) | Yes           |
| Population     | UN/OWID 2025           | Mixed — see below  | Yes               |
| GDP            | World Bank WDI 2025    | **CC-BY-4.0**      | Yes               |
| Gini (default) | World Bank WDI 2025 (SI.POV.GINI) | **CC-BY-4.0** | Yes    |
| Gini (opt-in)  | UNU-WIDER WIID 2025    | **CC BY-NC-SA 3.0 IGO** | Yes          |
| Regions        | regioniso3c (custom)   | **MIT**            | Optional          |
| Scenarios      | IPCC AR6 (Gidden 2023) | **CC-BY-4.0**      | Yes               |
| Carbon budgets | Lamboll et al. 2023    | Published values   | Yes               |
| Carbon budgets | Forster et al. 2024    | Published values   | Yes               |
| Bunker fuels   | Global Carbon Budget 2024 | paper **CC-BY-4.0**; data product under GCP terms | Yes |

---

## Emissions Data

### PRIMAP-hist

**Source:** Gütschow, J., Busch, D., & Pflüger, M. (2025). The PRIMAP-hist national historical emissions time series (1750-2023) v2.6.1. Zenodo.

**DOI:** [10.5281/zenodo.15016289](https://doi.org/10.5281/zenodo.15016289)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

**Location:** `data/emissions/primap-202503/`

**What it provides:** National greenhouse gas emissions by country (1750-2023), including CO2 from fossil fuels, land use, and other GHGs.

---

## LULUCF Data

### Melo et al. (NGHGI LULUCF)

**Source:** Melo, J., et al. (2026). The LULUCF Data Hub: translating global land use emissions estimates into the national GHG inventory framework (Version 3.1.1, 2025 NGHGI release). Zenodo.

**DOI:** [10.5281/zenodo.18352395](https://doi.org/10.5281/zenodo.18352395)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) (Zenodo)

**Location:** `data/lulucf/melo-2026/`

**What it provides:** NGHGI-reported CO2 LULUCF fluxes for 187 countries (2000–2023). Used for all emission categories that include land use (co2, all-ghg). See [Other Operations](../science/other-operations.md) for how NGHGI LULUCF data enters the pipeline.

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

**What it provides:** GDP per capita (PPP, constant 2021 USD). Observed series; ends at 2023.

!!! note "PPP vs MER: a normative choice"
The choice between PPP and MER GDP measures is not purely technical — it is a normative decision that can significantly affect allocation results [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). See [From Principle to Code](../science/principle-to-code.md) for further discussion.

!!! note "Post-observation GDP window"
`wdi-2025` is observed data only and ends at 2023, while population data extends to ~2100. When an allocation cumulative window runs past 2023, the per-capita budget and pathway primitives forward-fill GDP per capita from 2023 to cover the rest of the window — holding the cross-country capability ratios of 2023 constant. The cumulative-per-capita-convergence primitives instead compute their per-country capability scalar only over the observed-GDP years (no forward-fill). To use projected GDP for the post-observation window (SSP2, a custom growth assumption, or a future-extended WDI release), extend the input `gdp_ts` time series before calling the allocation function. See [Building Blocks](../science/allocations.md#building-blocks) in the science docs for the full description.

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
Analysis-country membership depends on emissions, GDP and population — not on Gini. A country with no Gini value stays in the analysis and receives the analysis-country mean, the same value Rest-of-World gets, flagged as `gini_imputed` in `country_data_coverage_summary.csv`. Set `general.gini_missing_policy: strict` to stop the run instead. Under the default source, 35 of 176 analysis countries carry an imputed Gini, Saudi Arabia among them.

### UNU-WIDER WIID (opt-in)

**Source:** UNU-WIDER World Income Inequality Database (WIID), Version 29 April 2025. [doi:10.35188/UNU-WIDER/WIID-290425](https://doi.org/10.35188/UNU-WIDER/WIID-290425)

**License:** [CC BY-NC-SA 3.0 IGO](https://creativecommons.org/licenses/by-nc-sa/3.0/igo/), per UNU-WIDER's [copyright terms](https://www.wider.unu.edu/about/copyright). The NonCommercial and ShareAlike clauses travel with derived Gini values, so they are incompatible with a plain CC BY compilation.

**Location:** `data/gini/unu-wider-2025/`. Opt-in: a plain `fair-shares fetch-data` does not download it. Fetch it with `fair-shares fetch-data --source unu-wider-2025` if it is not already present.

**What it provides:** Gini coefficients for 194 countries, taking each country's latest high-quality observation and falling back to the latest of any quality (`selection: latest-high-quality`, no year window). Coverage is broader than WDI but older: 34 of the 194 values predate 2010, and four are states that no longer exist.

!!! warning "Outputs built on WIID cannot be redistributed under CC BY 4.0"
The NonCommercial and ShareAlike terms travel with the derived Gini values, including a table of them. Selecting this source puts every Gini-derived file in the run outside this project's CC BY 4.0 data deposit.

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
| Forster et al. 2024 | 200 GtCO2           | 1.5°C       | 50%         | 2024     | IGCC 2023; latest usable with PRIMAP v2.6.1 (through 2023) |
| IPCC AR6 WGI        | 500 GtCO2           | 1.5°C       | 50%         | 2020     | Original AR6 estimates from WG1 Chapter 5          |

**Citations:**

> Lamboll, R. D., et al. (2023). Assessing the size and uncertainty of remaining carbon budgets. _Nature Climate Change_, 13, 1360–1367. [doi:10.1038/s41558-023-01848-5](https://doi.org/10.1038/s41558-023-01848-5)

> Forster, P. M., et al. (2024). Indicators of Global Climate Change 2023. _Earth System Science Data_, 16, 2625–2680. [doi:10.5194/essd-16-2625-2024](https://doi.org/10.5194/essd-16-2625-2024)

!!! note "Budget choice is normatively significant"
The choice of carbon budget (source, temperature target, probability level) corresponds to Entry Point 2 of the fair share quantification framework — the allocation quantity [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). Results are sensitive to this choice. Always document the budget source, temperature target, and probability level when reporting allocation results.

---

## Scenario Data

### IPCC AR6 Scenarios

**Source:** Gidden, M. J., et al. (2023). AR6 Scenarios Database hosted by IIASA.

**DOI:** [10.5281/zenodo.10158920](https://doi.org/10.5281/zenodo.10158920) — the v2 version record bundled here (concept DOI: [10.5281/zenodo.8411053](https://doi.org/10.5281/zenodo.8411053), which always resolves to the latest version)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

**Location:** `data/scenarios/ipcc_ar6_gidden/`

**What it provides:** IPCC AR6 WGIII emission pathways.

---

## Bunker Fuels

### Global Carbon Budget 2024

**Source (paper):** Friedlingstein, P., et al. (2025). Global Carbon Budget 2024. *Earth System Science Data*, 17, 965–1039. [doi:10.5194/essd-17-965-2025](https://doi.org/10.5194/essd-17-965-2025)

**Source (data product):** Global Carbon Project (2024). Supplemental data of Global Carbon Budget 2024 (Version 1.0). [doi:10.18160/GCP-2024](https://doi.org/10.18160/GCP-2024)

**License:** The paper is [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The data product is **not** CC-licensed — it carries the Global Carbon Project's own terms of use, which condition use on citing the original data sources. Cite both DOIs; the paper DOI is not the data DOI.

**Location:** `data/bunkers/gcb-2024/`

**What it provides:** International aviation and shipping CO2 emissions, used to deduct bunker fuels from national remaining carbon budgets. See [Other Operations](../science/other-operations.md) for methodology.

---

## Attribution in Your Work

When publishing results generated with fair-shares, cite:

1. **fair-shares library** (see [CITATION.cff](https://github.com/setupelz/fair-shares/blob/main/CITATION.cff))
2. **Data sources used** (listed above)

Example citation block:

```bibtex
@software{fair_shares,
  author = {Pelz, Setu},
  title = {fair-shares: Climate mitigation burden-sharing allocations},
  year = {2026},
  url = {https://github.com/setupelz/fair-shares}
}

@dataset{primap_hist,
  author = {Gütschow, Johannes and Busch, Daniel and Pflüger, Mika},
  title = {PRIMAP-hist v2.6.1},
  year = {2025},
  doi = {10.5281/zenodo.15016289}
}
```

---

## Adding Your Own Data

See [Adding Data Sources](../dev-guide/adding-data-sources.md) for instructions on integrating additional datasets.

---

## See Also

- **[Output Schema](output-schema.md)** - How data sources are tracked in outputs
- **[User Guide](index.md)** - Workflow documentation
- **[CITATION.cff](https://github.com/setupelz/fair-shares/blob/main/CITATION.cff)** - How to cite fair-shares
