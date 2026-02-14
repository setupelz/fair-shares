---
title: Approach Catalog
description: Complete reference of all allocation approaches in fair-shares
icon: material/view-list
search:
  boost: 2
---

# Approach Catalog

All allocation approaches at a glance.

- **Which principles does each approach implement?** See [Climate Equity Concepts](../science/climate-equity-concepts.md)
- **How do I configure an approach for specific principles?** See [Principle to Code](../science/principle-to-code.md)
- **What's the math?** See [API Reference](../api/allocations/budgets.md)

---

## The Allocation Year Parameter

When `allocation_year` (budget) or `first_allocation_year` (pathway) is set in the past, past emissions are subtracted from the budget before allocation. Countries have different **remaining allocations** depending on historical emissions.

See [Principle to Code](../science/principle-to-code.md#historical-responsibility) for configuration details.

---

## Budget Approaches

Allocate a cumulative emissions budget at a single point in time.

| Approach                              | Use Case                                          |
| ------------------------------------- | ------------------------------------------------- |
| **`equal-per-capita-budget`**         | Population-proportional targets                   |
| **`per-capita-adjusted-budget`**      | Additional weighting by emissions history and GDP |
| **`per-capita-adjusted-gini-budget`** | Accounts for within-country inequality            |

---

## Pathway Approaches

Allocate emissions over multiple years, producing annual shares.

### Equal Per Capita Family

| Approach                       | Use Case                                          |
| ------------------------------ | ------------------------------------------------- |
| **`equal-per-capita`**         | Year-by-year population shares                    |
| **`per-capita-adjusted`**      | Additional weighting by emissions history and GDP |
| **`per-capita-adjusted-gini`** | Accounts for within-country inequality            |

### Convergence Family

Gradual transition from current emissions to fair share target.

| Approach                                              | Use Case                                          |
| ----------------------------------------------------- | ------------------------------------------------- |
| **`per-capita-convergence`**                          | Comparison baseline (not a fair share approach)   |
| **`cumulative-per-capita-convergence`**               | Budget-preserving transitions                     |
| **`cumulative-per-capita-convergence-adjusted`**      | Additional weighting by emissions history and GDP |
| **`cumulative-per-capita-convergence-gini-adjusted`** | Accounts for within-country inequality            |

---

## Choosing an Approach

| Question                               | Answer                      |
| -------------------------------------- | --------------------------- |
| Single target or year-by-year?         | Budget vs Pathway           |
| Account for history?                   | Set early `allocation_year` |
| Account for capability?                | Use `-adjusted` variants    |
| Account for within-country inequality? | Use `-gini` variants        |

See [Principle to Code](../science/principle-to-code.md) for detailed configuration.

---

## Registry Reference

All approaches are registered in [`src/fair_shares/library/allocations/registry.py`](https://github.com/setupelz/fair-shares/blob/main/src/fair_shares/library/allocations/registry.py).

```python
from fair_shares.library.allocations.registry import get_allocation_functions

approaches = get_allocation_functions()
print(list(approaches.keys()))
```

---

## Adding Approaches

See the [Developer Guide](../dev-guide/adding-approaches.md).
