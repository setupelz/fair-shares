---
title: Data Sources & Licensing
description: Bundled data sources, licensing terms, and attribution requirements
icon: material/database-check
---

# Data Sources & Licensing

fair-shares bundles several datasets to enable allocations without external dependencies. This page documents the sources, licenses, and citation requirements.

---

## Quick Reference

All bundled data permits redistribution. The licenses are permissive:

| Data Type      | Source                 | License            | Citation Required |
| -------------- | ---------------------- | ------------------ | ----------------- |
| Emissions      | PRIMAP-hist v2.6.1     | **CC-BY-4.0**      | Yes               |
| LULUCF         | Melo et al. 2026 v3.1  | **CC-BY-4.0** (Zenodo) | Yes           |
| Population     | UN/OWID 2025           | **CC-BY-4.0**      | Yes               |
| GDP            | World Bank WDI 2025    | **CC-BY-4.0**      | Yes               |
| GDP            | IMF WEO 2025           | Terms of Use       | Yes               |
| Gini           | UNU-WIDER WIID 2025    | Academic use       | Yes               |
| Gini           | WID.world 2025         | Academic use       | Yes               |
| Regions        | regioniso3c (custom)   | **MIT**            | Optional          |
| Scenarios      | IPCC AR6 (Gidden 2022) | **CC-BY-4.0**      | Yes               |
| Carbon budgets | Lamboll et al. 2023    | Published values   | Yes               |
| Bunker fuels   | Global Carbon Budget 2024 | **CC-BY-4.0**   | Yes               |

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

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

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

### IMF World Economic Outlook

**Source:** International Monetary Fund World Economic Outlook (2025).

**License:** [IMF Terms of Use](https://www.imf.org/external/terms.htm) (permits academic use with citation)

**Location:** `data/gdp/imf-2025/`

**What it provides:** GDP projections and historical estimates.

---

## Inequality Data

### UNU-WIDER WIID

**Source:** UNU-WIDER World Income Inequality Database (2025).

**License:** Academic use permitted with citation.

**Location:** `data/gini/unu-wider-2025/`

**What it provides:** Gini coefficients for income inequality.

### WID.world

**Source:** World Inequality Database (2025).

**License:** Academic use permitted with citation.

**Location:** `data/gini/wid-2025/`

**What it provides:** Alternative Gini coefficients from fiscal data. Available as a second inequality source alongside UNU-WIDER.

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

| Source              | Budget              | Temperature | Probability | Notes                                              |
| ------------------- | ------------------- | ----------- | ----------- | -------------------------------------------------- |
| Lamboll et al. 2023 | 247 GtCO2 from 2023 | 1.5°C       | 50%         | Default RCB in fair-shares bundled data            |
| IPCC AR6            | Various             | Various     | Various     | Temperature–budget relationships in WG1 Chapter 5  |

**Citation for default budget:**

> Lamboll, R. D., et al. (2023). Assessing the size and uncertainty of remaining carbon budgets. _Nature Climate Change_, 13, 1360–1367. [doi:10.1038/s41558-023-01848-5](https://doi.org/10.1038/s41558-023-01848-5)

!!! note "Budget choice is normatively significant"
The choice of carbon budget (source, temperature target, probability level) corresponds to Entry Point 2 of the fair share quantification framework — the allocation quantity [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). Results are sensitive to this choice. Always document the budget source, temperature target, and probability level when reporting allocation results.

---

## Scenario Data

### IPCC AR6 Scenarios

**Source:** Gidden, M. J., et al. (2022). AR6 Scenarios Database hosted by IIASA.

**DOI:** [10.5281/zenodo.8411053](https://doi.org/10.5281/zenodo.8411053)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

**Location:** `data/scenarios/ipcc_ar6_gidden/`

**What it provides:** IPCC AR6 WGIII emission pathways.

---

## Bunker Fuels

### Global Carbon Budget 2024

**Source:** Friedlingstein, P., et al. (2024). Global Carbon Budget 2024. *Earth System Science Data*.

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

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
