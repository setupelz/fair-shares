---
title: Allocation Approaches
description: Design and parameters for budget and pathway allocation approaches in fair-shares
search:
  boost: 2
---

# Allocation Approaches

Design and parameters for allocation approaches in fair-shares.

For underlying principles, see [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/). For mathematical formulations, see the API Reference for [budgets](https://setupelz.github.io/fair-shares/api/allocations/budgets/) and [pathways](https://setupelz.github.io/fair-shares/api/allocations/pathways/).

---

## Overview

Allocation approaches distribute emissions among countries based on equity principles. fair-shares implements two categories:

| Category    | Question Answered                                                             | Output                          |
| ----------- | ----------------------------------------------------------------------------- | ------------------------------- |
| **Budget**  | What is each country's fair share of a cumulative remaining emissions budget? | Single allocation per country   |
| **Pathway** | What is each country's fair share of emissions each future year?              | Time-varying annual allocations |

All allocation approaches ensure shares sum to 1 in each year and ensure complete global coverage.

### Budget vs Pathway: Choosing Based on Your Needs

**In brief:** Both produce the same cumulative allocations. Choose based on whether you need year-by-year breakdowns.

**Why they're equivalent:** For emission pathways that never go negative (emissions always ≥0), the cumulative sum of annual allocations equals the budget allocation. fair-shares ensures this by design.

??? note "Technical note: The net-negative emissions exception"

    The equivalence holds only for pathways with positive-only emissions. IPCC AR6 overshoot scenarios include net-negative emissions in later decades (CO2 removal). This creates a challenge:

    - **AR6 budgets** work fine — they capture cumulative totals that already account for net-negative emissions
    - **AR6 pathways** present ambiguity — how to allocate negative values while maintaining proportional fairness?

    fair-shares does not alter AR6 pathways. Instead, it sets post-net-zero emissions to NaN and reports unallocated quantities as a warning. Users must decide how to handle net-negative portions separately.

    **Converting RCBs to pathways:** Use `generate_rcb_pathway_scenarios()` to convert any budget to a temporal breakdown (e.g., exponential decay over years). See [Other Operations: RCB Pathway Generation](https://setupelz.github.io/fair-shares/science/other-operations/#rcb-pathway-generation).

    <!-- REFERENCE: generate_rcb_pathway_scenarios() in src/fair_shares/library/utils/math/pathways.py -->

---

## Target Source Options

fair-shares currently supports three target sources for allocation calculations:

| Target         | Type    | Allocation Functions | Use When                                            | Output                                         |
| -------------- | ------- | -------------------- | --------------------------------------------------- | ---------------------------------------------- |
| `rcbs`         | Budget  | Budget approaches    | Calculating cumulative national budget allocations  | Single value per country                       |
| `ar6`          | Pathway | Pathway approaches   | Allocating annual emissions following AR6 scenarios | Time series of annual values                   |
| `rcb-pathways` | Hybrid  | Pathway approaches   | Using budget data but need year-by-year pathways    | Budget to global pathway to allocated annually |

### RCB-to-Pathway Conversion

The `rcb-pathways` target source converts the global remaining carbon budget (RCB) into an annual emission pathway, which can then be allocated using pathway allocation approaches. This approach:

1. **Generates a global pathway** from the remaining carbon budget using normalized shifted exponential decay
2. **Applies pathway allocation approaches** to distribute the global pathway among countries (e.g., `equal-per-capita`, `per-capita-adjusted`)
3. **Preserves cumulative totals** — the sum of annual pathway emissions equals the original carbon budget

**Why use this?** You want to start from a global carbon budget but need year-by-year emission trajectories for:

- Integration with IAMs (Integrated Assessment Models)
- Policy roadmaps requiring annual targets
- Comparison with AR6 scenario pathways

**Mathematical approach:** Uses `generate_rcb_pathway_scenarios()` which creates an exponential decay curve that:

<!-- REFERENCE: generate_rcb_pathway_scenarios() in src/fair_shares/library/utils/math/pathways.py -->

- Starts at historical emissions in the allocation year
- Reaches exactly zero by the end year
- Ensures discrete annual sums equal the budget

**Configuration:** Set `target: "rcb-pathways"` in your data source config. See [User Guide: Configuration](https://setupelz.github.io/fair-shares/user-guide/#rcb-pathway-generation) for setup details.

**Technical details:** [RCB Pathway Generation](https://setupelz.github.io/fair-shares/science/other-operations/#rcb-pathway-generation)

---

## Parameters

For real-world examples showing how these parameters affect allocation outcomes for different countries, see [Parameter Effects Reference](https://setupelz.github.io/fair-shares/science/parameter-effects/).

### Allocation Year

Reference year for calculating cumulative per capita allocations.

| Category | Parameter Name          |
| -------- | ----------------------- |
| Budget   | `allocation_year`       |
| Pathway  | `first_allocation_year` |

Earlier allocation years account for historical emissions in the cumulative calculation. See [Polluter Pays](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#polluter-pays-historical-responsibility).

### Building Blocks

| Component             | What it adds                                                | Budget Parameter                                           | Pathway Parameter                                            |
| --------------------- | ----------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------ |
| Early allocation year | Accounts for emissions since that year                      | `allocation_year`                                          | `first_allocation_year`                                      |
| Responsibility weight | Rescales by emissions from `historical_responsibility_year` | `responsibility_weight` + `historical_responsibility_year` | Same                                                         |
| Capability weight     | Adjustment by capacity from allocation year onwards         | `capability_weight`                                        | Same                                                         |
| Income floor          | Protects subsistence needs in capability calculations       | `income_floor`                                             | Same                                                         |
| Gini adjustment       | Within-country inequality correction                        | Use `*-gini-budget` allocation approach                    | Use `*-gini` or `*-gini-adjusted` allocation approach        |
| Convergence mechanism | Transition from current to target cumulative shares         | N/A                                                        | Use `cumulative-per-capita-convergence*` allocation approach |

**Temporal note:** Capability adjustments apply from the allocation year onwards, while responsibility weight rescaling uses emissions from `historical_responsibility_year` to the allocation year. This allows separating the periods for capability and responsibility accounting.

These can be combined. For example, CBDR-RC can be interpreted and operationalised through:

- Early allocation year (e.g. 1850) + capability weight: simplest, but capability data may be unavailable for early years
- Allocation year of 1990 + responsibility weight from 1850 + capability weight: uses responsibility rescaling for 1850-1990 emissions while applying capability adjustments from 1990 onwards (when data is available)
- (Pathways only) Convergence approach + early allocation year + capability weight: with smooth transition path

### Example Configurations: Budget

<!-- REFERENCE: equal_per_capita_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted_gini_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

| Use Case                     | Approach                          | Key Parameters                                |
| ---------------------------- | --------------------------------- | --------------------------------------------- |
| Forward-looking egalitarian  | `equal-per-capita-budget`         | Recent `allocation_year`                      |
| Egalitarian + historical     | `equal-per-capita-budget`         | Early `allocation_year` (e.g. 1850, 1990)     |
| CBDR-RC (simplest)           | `per-capita-adjusted-budget`      | Early `allocation_year` + `capability_weight` |
| CBDR-RC (via rescaling)      | `per-capita-adjusted-budget`      | `responsibility_weight` + `capability_weight` |
| Inequality-sensitive CBDR-RC | `per-capita-adjusted-gini-budget` | Early `allocation_year` + `capability_weight` |

### Example Configurations: Pathway

<!-- REFERENCE: equal_per_capita() in src/fair_shares/library/allocations/pathways/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted_gini() in src/fair_shares/library/allocations/pathways/per_capita.py -->
<!-- REFERENCE: cumulative_per_capita_convergence_adjusted() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->

| Use Case                     | Approach                                     | Key Parameters                                      |
| ---------------------------- | -------------------------------------------- | --------------------------------------------------- |
| Forward-looking egalitarian  | `equal-per-capita`                           | Recent `first_allocation_year`                      |
| Egalitarian + historical     | `equal-per-capita`                           | Early `first_allocation_year` (e.g. 1850, 1990)     |
| CBDR-RC (simplest)           | `per-capita-adjusted`                        | Early `first_allocation_year` + `capability_weight` |
| CBDR-RC (via rescaling)      | `per-capita-adjusted`                        | `responsibility_weight` + `capability_weight`       |
| CBDR-RC with convergence     | `cumulative-per-capita-convergence-adjusted` | Early `first_allocation_year` + `capability_weight` |
| Inequality-sensitive CBDR-RC | `*-gini-adjusted`                            | Early `first_allocation_year` + `capability_weight` |

---

## Gini Adjustment

<!-- REFERENCE: per_capita_adjusted_gini_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted_gini() in src/fair_shares/library/allocations/pathways/per_capita.py -->

Models national income distribution as log-normal and applies an income floor, excluding income below threshold when calculating capability. Higher Gini coefficients reduce the effective capability metric.

See [Subsistence vs. Luxury Emissions](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#subsistence-vs-luxury-emissions) for conceptual context.

**Mathematical formulations:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_gini_budget) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted_gini)

---

## Maximum Deviation Constraint

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

Limits how far any country's allocation can deviate from equal per capita. Default: ±2 standard deviations.

Parameter: `max_deviation_sigma`

**Implementation details:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_budget) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted)

---

## Weight Normalization

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

Combines responsibility and capability adjustments as multiplicative factors applied to the equal-per-capita baseline:

```
Adjusted population = Population × responsibility_metric^(-w_r) × capability_metric^(-w_c)
```

Where `w_r` and `w_c` are the normalized responsibility and capability weights (divided by their sum). Only the ratio between weights affects results; `(0.3, 0.7)` and `(0.15, 0.35)` produce identical allocations because they normalize to the same values.

**Mathematical specification:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_budget) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted)

---

## Dynamic vs Preserved Shares

<!-- REFERENCE: equal_per_capita_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: equal_per_capita() in src/fair_shares/library/allocations/pathways/per_capita.py -->

Parameter: `preserve_allocation_year_shares` (budget) / `preserve_first_allocation_year_shares` (pathway)

| Mode              | Budget                                     | Pathway                                         |
| ----------------- | ------------------------------------------ | ----------------------------------------------- |
| Dynamic (default) | Cumulative population from allocation year | Recalculated each year based on current pop/GDP |
| Preserved         | Population at allocation year only         | Fixed at first allocation year                  |

**Mathematical specifications:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/#equal_per_capita_budget) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/#equal_per_capita)

---

## Historical Responsibility

Two mechanisms:

1. **Early allocation year:** Set `allocation_year` to 1850 or 1990 (calculates cumulative per capita since that year)
2. **Responsibility weight:** Use `responsibility_weight` + `historical_responsibility_year` (multiplicative adjustment based on per-capita historical emissions)

These can be combined. See [Polluter Pays](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#polluter-pays-historical-responsibility) for conceptual foundations.

**Mathematical details:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/)

---

## Convergence Mechanism (Pathways Only)

<!-- REFERENCE: cumulative_per_capita_convergence() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->
<!-- REFERENCE: cumulative_per_capita_convergence_adjusted() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->
<!-- REFERENCE: cumulative_per_capita_convergence_adjusted_gini() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->

Cumulative per capita convergence approaches provide exponential transition from current emissions to cumulative per capita targets.

Properties:

- Smooth (continuous and differentiable)
- Cumulative-constrained: total over horizon equals target share
- Automatic speed: minimum speed satisfying cumulative constraints

**[Mathematical derivation →](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence)**

---

## Strict Parameter (Convergence Only)

<!-- REFERENCE: cumulative_per_capita_convergence() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->
<!-- REFERENCE: cumulative_per_capita_convergence_adjusted() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->
<!-- REFERENCE: cumulative_per_capita_convergence_adjusted_gini() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->

Parameter: `strict` (default: True)

| Mode       | Behavior                                                      |
| ---------- | ------------------------------------------------------------- |
| Strict     | Raise error if no feasible convergence solution exists        |
| Permissive | Accept approximate solutions, document deviations in warnings |

**[Implementation details →](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence)**

---

## Per Capita Convergence (PCC)

<!-- REFERENCE: per_capita_convergence() in src/fair_shares/library/allocations/pathways/per_capita_convergence.py -->

The `per-capita-convergence` approach linearly blends grandfathering (current emissions) with equal per capita over time. It includes grandfathering elements, which are critiqued in the literature; see [Approaches Debated in the Literature](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#approaches-debated-in-the-literature) for context.

**[Formulation →](https://setupelz.github.io/fair-shares/api/allocations/pathways/)**

---

## See Also

- **[Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/):** Theoretical foundations and principles
- **[API Reference: Budget Allocations](https://setupelz.github.io/fair-shares/api/allocations/budgets/):** Budget mathematical formulations
- **[API Reference: Pathway Allocations](https://setupelz.github.io/fair-shares/api/allocations/pathways/):** Pathway mathematical formulations
- **[country-fair-shares Guide](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/):** When to use each approach
- **[References](https://setupelz.github.io/fair-shares/science/references/):** Complete bibliography
