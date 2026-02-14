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

| Data Type  | Source                 | License       | Citation Required |
| ---------- | ---------------------- | ------------- | ----------------- |
| Emissions  | PRIMAP-hist v2.6.1     | **CC-BY-4.0** | Yes               |
| Population | UN/OWID 2025           | **CC-BY-4.0** | Yes               |
| GDP        | World Bank WDI 2025    | **CC-BY-4.0** | Yes               |
| GDP        | IMF WEO 2025           | Terms of Use  | Yes               |
| Gini       | UNU-WIDER WIID 2025    | Academic use  | Yes               |
| Regions    | regioniso3c (custom)   | **MIT**       | Optional          |
| Scenarios  | IPCC AR6 (Gidden 2022) | **CC-BY-4.0** | Yes               |

---

## Emissions Data

### PRIMAP-hist

**Source:** Gütschow, J., Busch, D., & Pflüger, M. (2025). The PRIMAP-hist national historical emissions time series (1750-2023) v2.6.1. Zenodo.

**DOI:** [10.5281/zenodo.15016289](https://doi.org/10.5281/zenodo.15016289)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

**Location:** `data/emissions/primap-202503/`

**What it provides:** National greenhouse gas emissions by country (1750-2023), including CO2 from fossil fuels, land use, and other GHGs.

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

**What it provides:** GDP per capita (PPP, constant 2021 USD).

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

## Scenario Data

### IPCC AR6 Scenarios

**Source:** Gidden, M. J., et al. (2022). AR6 Scenarios Database hosted by IIASA.

**DOI:** [10.5281/zenodo.5886911](https://doi.org/10.5281/zenodo.5886911)

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

**Location:** `data/scenarios/ipcc_ar6_gidden/`

**What it provides:** IPCC AR6 WGIII emission pathways.

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
