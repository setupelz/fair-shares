---
title: Approach Catalog
description: Complete reference of all allocation approaches in fair-shares
icon: material/view-list
search:
  boost: 2
---

# Approach Catalog

All allocation approaches at a glance.

- **Which principles does each approach implement?** See [From Principle to Code](../science/principle-to-code.md)
- **How do I configure an approach for specific principles?** See [Principle to Code](../science/principle-to-code.md)
- **What's the math?** See [API Reference](../api/allocations/budgets.md)

---

## The Allocation Year Parameter

When `allocation_year` (budget) or `first_allocation_year` (pathway) is set in the past, the allocation considers cumulative population (and emissions, if using adjusted approaches) from that year onward when computing each country's share. fair-shares does not subtract past emissions natively — it computes shares of the total budget from the allocation year. If you want **remaining allocations** from the present, subtract each country's actual emissions between the allocation year and now from their allocated share as a post-processing step.

The choice of start date is normatively significant: 1850 captures the full industrial era, 1950 tracks post-war growth, and 1990 corresponds to the IPCC First Assessment Report — widely treated in the equity literature as the "excusable ignorance" threshold, beyond which responsibility for emissions harm is difficult to deny [Baer 2013](https://doi.org/10.1002/wcc.201); [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). For the philosophical origin of the excusable-ignorance defence and its rebuttal, see [Shue 2015](https://doi.org/10.1515/mopp-2013-0009) and [Caney 2010](https://doi.org/10.1080/13698230903326331).

See [Allocation Approaches](../science/allocations.md#historical-responsibility) for configuration details.

---

## Budget Approaches

Allocate a cumulative emissions budget at a single point in time.

| Approach                              | Use Case                                                                                       |
| ------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **`equal-per-capita-budget`**         | Population-proportional targets                                                                |
| **`per-capita-adjusted-budget`**      | Additional weighting by pre-allocation responsibility (per-capita emissions rescaling) and capability (GDP) |
| **`per-capita-adjusted-gini-budget`** | Accounts for within-country inequality                                                         |

---

## Pathway Approaches

Allocate emissions over multiple years, producing annual shares.

### Equal Per Capita Family

These approaches implement Equal Cumulative Per Capita (ECPC) allocation. When `allocation_year` is set in the past, cumulative population from that year determines each country's share of the total budget.

| Approach                       | Use Case                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| **`equal-per-capita`**         | Year-by-year population shares                                                                 |
| **`per-capita-adjusted`**      | Additional weighting by pre-allocation responsibility (per-capita emissions rescaling) and capability (GDP) |
| **`per-capita-adjusted-gini`** | Accounts for within-country inequality                                                         |

### Convergence Family

Gradual transition from current emissions to fair share target.

| Approach                                              | Use Case                                                                                                                                                             |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`per-capita-convergence`**                          | Comparison baseline (not a fair share approach) — convergence from current emission levels embeds implicit grandfathering during the transition period [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) |
| **`cumulative-per-capita-convergence`**               | Budget-preserving transitions                                                                                                                                        |
| **`cumulative-per-capita-convergence-adjusted`**      | Additional weighting by pre-allocation responsibility (per-capita emissions rescaling) and capability (GDP)                                                           |
| **`cumulative-per-capita-convergence-gini-adjusted`** | Accounts for within-country inequality                                                                                                                               |

---

## Choosing an Approach

| Question                                         | Answer                      |
| ------------------------------------------------ | --------------------------- |
| Single target or year-by-year?                   | Budget vs Pathway           |
| Account for history via cumulative accounting?   | Set early `allocation_year` — cumulative population from that year determines shares |
| Account for history via pre-allocation rescaling? | Use `-adjusted` variants with `pre_allocation_responsibility_weight` — multiplicative rescaling by per-capita emissions in a historical window |
| Account for capability?                          | Use `-adjusted` variants with `capability_weight` (applies from allocation year onwards) |
| Account for within-country inequality?           | Use `-gini` variants        |

See [Principle to Code](../science/principle-to-code.md) for detailed configuration.

!!! tip "Entry Points Framework"
Approach selection is one of five structured decision stages in fair share quantification [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). Before choosing an approach, make explicit decisions about (1) foundational principles, (2) allocation quantity, and (3) which indicators will operationalize your approach — these upstream choices constrain which approaches are normatively coherent. See [From Principle to Code](../science/principle-to-code.md) for the full framework.

---

## Registry Reference

All approaches are registered in [`src/fair_shares/library/allocations/manager.py`](https://github.com/setupelz/fair-shares/blob/main/src/fair_shares/library/allocations/manager.py).

```python
from fair_shares.library.allocations.manager import get_allocation_functions

approaches = get_allocation_functions()
print(list(approaches.keys()))
```

---

## Adding Approaches

See the [Developer Guide](../dev-guide/adding-approaches.md).
