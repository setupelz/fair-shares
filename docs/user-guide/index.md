---
title: User Guide
description: Guides for calculating fair share allocations using country-level or IAMC-regional workflows
icon: material/book-open-page-variant
---

# User Guide

<!-- REFERENCE: Workflows are entry points to different allocation pipelines
     country-fair-shares: Implemented via manager in src/fair_shares/library/allocations/manager.py
     iamc-regional-fair-shares: Uses direct function calls from src/fair_shares/library/utils/data/iamc.py
-->

## Workflows

| Workflow                                                                                                      | Notebook                                 | Description                             |
| ------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | --------------------------------------- |
| **[country-fair-shares](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/)**             | `301_custom_fair_share_allocation.ipynb` | Country-level allocations with pipeline |
| **[iamc-regional-fair-shares](https://setupelz.github.io/fair-shares/user-guide/iamc-regional-fair-shares/)** | `401_custom_iamc_allocation.ipynb`       | IAMC model region allocations           |

Both workflows produce relative shares (0-1) and absolute emissions (Mt CO2e).

---

## Outputs & Provenance

All outputs include **full parameter provenance** for reproducibility:

| Output Type        | Description                                   | Format       |
| ------------------ | --------------------------------------------- | ------------ |
| Relative shares    | Country fractions summing to 1.0              | Parquet, CSV |
| Absolute emissions | Shares x global target in physical units      | Parquet, CSV |
| Comparison tables  | Results across multiple approaches/parameters | CSV (wide)   |
| Parameter manifest | All parameter combinations used               | CSV          |

**Parquet files contain complete metadata:**

- Every parameter value (weights, years, functional forms)
- Data source identifiers (`emissions-source`, `gdp-source`, `population-source`, etc.)
- Approach names and configuration

This enables exact reproduction and comparison of results. See **[Output Schema](output-schema.md)** for full column documentation.

---

## Configuration

Data sources are configured in `conf/data_sources/`.

| Data Type  | Options                       |
| ---------- | ----------------------------- |
| Target     | `rcbs`, `pathway`, `rcb-pathways` |
| Emissions  | e.g. PRIMAP-hist              |
| Population | UN/OWID                       |
| GDP        | World Bank WDI                |
| Gini       | UNU-WIDER                     |

All bundled data is permissively licensed (CC-BY-4.0 or similar). See **[Data Sources & Licensing](data-sources.md)** for attribution requirements.

### Target Sources

fair-shares currently supports three target sources:

| Target         | Type    | Allocation Functions | Use When                                            | Output                                         |
| -------------- | ------- | -------------------- | --------------------------------------------------- | ---------------------------------------------- |
| `rcbs`         | Budget  | Budget approaches    | Calculating cumulative national budget allocations  | Single value per country                       |
| `pathway`      | Pathway | Pathway approaches   | Allocating annual emissions following scenario pathways (e.g. AR6) | Time series of annual values                   |
| `rcb-pathways` | Hybrid  | Pathway approaches   | Using budget data but need year-by-year pathways    | Budget to global pathway to allocated annually |

**`rcb-pathways` workflow:** First converts a global remaining carbon budget into a global annual emission pathway (using exponential decay), then allocates that pathway among countries using pathway allocation functions. See [Other Operations](https://setupelz.github.io/fair-shares/science/other-operations/#rcb-pathway-generation) for details on pathway generation.

---

## Choosing an Approach

Two questions:

1. **Budget or pathway?** Do you need a single cumulative target or year-by-year emissions?
2. **Which principles?** Equal entitlements, historical differentiation (via early `allocation_year` for cumulative accounting and/or `pre_allocation_responsibility_weight` for per-capita emissions rescaling), capability (ability to pay, from the allocation year onwards) -- or some combination? Note: "subsistence protection" as a live approach choice has diminished operational value — [Shue 2014](../science/references.md#shue-2014) later acknowledged that what the poor need is energy, not emissions rights. The more relevant operational concept is the GDR development threshold [Baer 2013](https://doi.org/10.1002/wcc.201) (note: GDR was designed for burden-sharing; fair-shares adapts its capability metric for entitlement allocation), which exempts individuals below a development income threshold (~$7,500 PPP) from capability calculations.

Then:

- **[Approach Catalog](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/)** -- all 10 approaches at a glance
- **[Principle-to-Code](https://setupelz.github.io/fair-shares/science/principle-to-code/)** -- how principles map to parameters
- **[Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)** -- design and parameter details
