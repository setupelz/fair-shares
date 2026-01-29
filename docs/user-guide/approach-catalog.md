---
title: Approach Catalog
description: Complete reference of all allocation approaches in fair-shares
icon: material/view-list
search:
  boost: 2
---

# Approach Catalog

This page provides a quick-reference overview of all 10 allocation approaches available in fair-shares. Each approach operationalizes different equity principles from the climate justice literature.

For detailed mathematical formulations, see the [API Reference](https://setupelz.github.io/fair-shares/api/index/). For theoretical grounding, see [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/) and [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/).

---

## The `allocation_year` Parameter

The `allocation_year` parameter applies to **all approaches** (except `per-capita-convergence`) and represents a fundamental debate in climate equity literature: **when do allocations begin?**

- **Early allocation_year (e.g., 1850, 1990)**: Operationalizes historical responsibility by starting the "equal entitlement clock" earlier. Historical over-emitters have already consumed their fair share from that date forward.
- **Recent allocation_year (e.g., 2015, 2020)**: Focuses on current/future population without accounting for historical emissions through this mechanism.

This is distinct from (and complementary to) other responsibility mechanisms like `responsibility_weight` or cumulative accounting. The choice of allocation year is a normative parameter—there is no neutral default.

---

## Budget Approaches

<!-- Source: src/fair_shares/library/allocations/registry.py -->
<!-- Descriptions: src/fair_shares/library/allocations/budgets/ -->

Budget approaches allocate a cumulative emissions budget (e.g., a remaining carbon budget compatible with 1.5°C) at a single point in time, rather than allocating emissions year-by-year along a pathway.

**Use when:** You need national targets for cumulative emissions (e.g., "What share of the remaining carbon budget should each country get?")

| Approach                              | Operationalizes                         | Best For                                                                        | Links                                                                                                       |
| ------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **`equal-per-capita-budget`**         | Equal per capita                        | National targets based on population shares                                     | [API](https://setupelz.github.io/fair-shares/api/allocations/budgets/#equal_per_capita_budget) · [Science](https://setupelz.github.io/fair-shares/science/allocations/)         |
| **`per-capita-adjusted-budget`**      | CBDR-RC, Capability                     | Differentiated responsibility with historical emissions and GDP adjustments     | [API](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_budget) · [Science](https://setupelz.github.io/fair-shares/science/allocations/)      |
| **`per-capita-adjusted-gini-budget`** | CBDR-RC, Capability, Sufficientarianism | Adjusted allocation accounting for intra-national inequality (Gini coefficient) | [API](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_gini_budget) · [Science](https://setupelz.github.io/fair-shares/science/allocations/) |

All budget approaches support Historical Responsibility via `allocation_year` (see above).

---

## Pathway Approaches

<!-- Source: src/fair_shares/library/allocations/registry.py -->
<!-- Descriptions: src/fair_shares/library/allocations/pathways/ -->

Pathway approaches allocate emissions over multiple years, producing annual emission shares that collectively respect a global emissions trajectory.

**Use when:** You need year-by-year emissions guidance (e.g., "What emissions pathway should each country follow to 2050?")

### Equal Per Capita Family

| Approach                       | Operationalizes                         | Best For                                                   | Links                                                                                                 |
| ------------------------------ | --------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **`equal-per-capita`**         | Equal per capita                        | Pathways based on population shares                        | [API](https://setupelz.github.io/fair-shares/api/allocations/pathways/#equal_per_capita) · [Science](https://setupelz.github.io/fair-shares/science/allocations/)         |
| **`per-capita-adjusted`**      | CBDR-RC, Capability                     | Pathways with historical emissions and GDP adjustments     | [API](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted) · [Science](https://setupelz.github.io/fair-shares/science/allocations/)      |
| **`per-capita-adjusted-gini`** | CBDR-RC, Capability, Sufficientarianism | Adjusted pathways accounting for intra-national inequality | [API](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted_gini) · [Science](https://setupelz.github.io/fair-shares/science/allocations/) |

All Equal Per Capita approaches support Historical Responsibility via `allocation_year` (see above).

### Convergence Family

Convergence approaches allow countries to gradually transition from current emissions to their fair share target.

| Approach                                              | Operationalizes                                                | Best For                                                              | Links                                                                                                                        |
| ----------------------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **`per-capita-convergence`**                          | Transition mechanism (not equity-based)\*                      | Comparing against grandfathering baselines                            | [API](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_convergence) · [Science](https://setupelz.github.io/fair-shares/science/allocations/)                          |
| **`cumulative-per-capita-convergence`**               | CBDR-RC, Cumulative accounting                                 | Transition pathways that account for cumulative historical emissions  | [API](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence) · [Science](https://setupelz.github.io/fair-shares/science/allocations/)               |
| **`cumulative-per-capita-convergence-adjusted`**      | CBDR-RC, Capability, Cumulative accounting                     | Cumulative convergence with responsibility and capability adjustments | [API](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence_adjusted) · [Science](https://setupelz.github.io/fair-shares/science/allocations/)      |
| **`cumulative-per-capita-convergence-gini-adjusted`** | CBDR-RC, Capability, Sufficientarianism, Cumulative accounting | Cumulative convergence accounting for intra-national inequality       | [API](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence_adjusted_gini) · [Science](https://setupelz.github.io/fair-shares/science/allocations/) |

All Convergence approaches (except `per-capita-convergence`) support Historical Responsibility via `allocation_year` (see above). The cumulative approaches additionally account for historical emissions through cumulative per-capita accounting.

**Note on `per-capita-convergence`:** This approach privileges current emission patterns during the transition period (grandfathering). It is **not considered a fair share approach** because it allocates more to currently high-emitting countries without equity-based justification. It is included for comparison purposes only.

---

## Choosing an Approach

Not sure which approach to use? See the [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/) guide for guidance on translating your ethical framework to code. See [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/) for the principle-to-code mapping guide.

**Quick decision guide:**

1. **Budget vs Pathway?** → Do you need a single cumulative target or year-by-year guidance?
2. **Account for history?** → Set early `allocation_year` (all approaches), and/or use cumulative approaches, and/or use `responsibility_weight`
3. **Account for capability?** → Use `-adjusted` variants with `responsibility_weight` and `capability_weight`
4. **Account for inequality within countries?** → Use `-gini` variants with Gini coefficient data

---

## Registry Reference

<!-- This section links to the authoritative registry in the codebase -->

All approaches are registered in [`src/fair_shares/library/allocations/registry.py`](https://github.com/setupelz/fair-shares/blob/main/src/fair_shares/library/allocations/registry.py). The registry maps approach names (kebab-case) to implementation functions.

To get a list of all available approaches programmatically:

```python
from fair_shares.library.allocations.registry import get_allocation_functions

approaches = get_allocation_functions()
print(list(approaches.keys()))
```

---

## Implementation Details

For implementation patterns and adding new approaches, see the [Developer Guide](https://setupelz.github.io/fair-shares/dev-guide/adding-approaches/).

For common use cases and worked examples, see:

- [Country Fair Shares](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/)
- [IAMC Regional Fair Shares](https://setupelz.github.io/fair-shares/user-guide/iamc-regional-fair-shares/)
