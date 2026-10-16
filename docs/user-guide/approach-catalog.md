---
title: Approach catalog
description: Complete reference of all allocation approaches in fair-shares
search:
  boost: 2
---

# Approach catalog

All allocation approaches at a glance.
[From principle to code](../science/principle-to-code.md) maps principles to settings, and the [API reference](../api/allocations/budgets.md) gives the maths.

---

## The Allocation Year Parameter

When `allocation_year` (budget) or `first_allocation_year` (pathway) is set in the past, the allocation considers cumulative population (and emissions, if using adjusted approaches) from that year onward when computing each country's share. The allocation itself is each country's share of the total budget from the allocation year. The library then subtracts each country's observed emissions from the allocation year to the last observed year, which gives its **remaining budget**. Notebook 601 and the Python API do this step ([Remaining budgets and annual pathways](pipeline-map.md#4-remaining-budgets-and-annual-pathways-notebook-601-and-the-python-api)).

The choice of start date is normatively significant: 1850 captures the full industrial era, 1950 tracks post-war growth, and 1990 corresponds to the IPCC First Assessment Report, widely treated in the equity literature as the "excusable ignorance" threshold, beyond which responsibility for emissions harm is difficult to deny [Baer 2013](https://doi.org/10.1002/wcc.201); [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). For the philosophical origin of the excusable-ignorance defence and its rebuttal, see [Shue 2015](https://doi.org/10.1515/mopp-2013-0009) and [Caney 2010](https://doi.org/10.1080/13698230903326331).

See [Allocation Approaches](../science/allocations.md#historical-responsibility) for configuration details.

---

## Budget Approaches

Allocate a cumulative emissions budget at a single point in time.

| Approach                              | Use Case                                                                                       |
| ------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **`equal-per-capita-budget`**         | Population-proportional targets                                                                |
| **`per-capita-adjusted-budget`**      | Additional weighting by pre-allocation responsibility (historical emissions) and capability (GDP) |
| **`per-capita-adjusted-gini-budget`** | Accounts for within-country inequality                                                         |

---

## Pathway Approaches

Allocate emissions over multiple years, producing annual shares.

### Equal Per Capita Family

These approaches implement Equal Cumulative Per Capita (ECPC) allocation. When `allocation_year` is set in the past, cumulative population from that year determines each country's share of the total budget.

| Approach                       | Use Case                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| **`equal-per-capita`**         | Year-by-year population shares                                                                 |
| **`per-capita-adjusted`**      | Additional weighting by pre-allocation responsibility (historical emissions) and capability (GDP) |
| **`per-capita-adjusted-gini`** | Accounts for within-country inequality                                                         |

### Convergence Family

Gradual transition from current emissions to fair share target.

| Approach                                              | Use Case                                                                                                                                                             |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`per-capita-convergence`**                          | Comparison baseline (not a fair share approach): convergence from current emission levels embeds implicit grandfathering during the transition period [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) |
| **`cumulative-per-capita-convergence`**               | Budget-preserving transitions                                                                                                                                        |
| **`cumulative-per-capita-convergence-adjusted`**      | Additional weighting by pre-allocation responsibility (historical emissions) and capability (GDP)                                                           |
| **`cumulative-per-capita-convergence-gini-adjusted`** | Accounts for within-country inequality                                                                                                                               |

---

## Choosing an Approach

| Question                                         | Answer                      |
| ------------------------------------------------ | --------------------------- |
| Single target or year-by-year?                   | Budget vs Pathway           |
| Account for history via cumulative accounting?   | Set early `allocation_year`: cumulative population from that year determines shares |
| Account for history via pre-allocation rescaling? | Use `-adjusted` variants with `pre_allocation_responsibility_weight`: multiplicative rescaling by emissions in a historical window (absolute by default) |
| Account for capability?                          | Use `-adjusted` variants with `capability_weight`: year by year from the allocation year, a snapshot (`capability_reference_year`) or a cumulative window (`capability_window`) |
| Account for within-country inequality?           | Use `-gini` variants        |

See [Principle to Code](../science/principle-to-code.md) for detailed configuration.

!!! note "Which inequality dataset the `-gini` approaches use"

    The default Gini source is the World Bank's Gini index (`SI.POV.GINI`),
    which `fair-shares fetch-data` brings down with everything else. WIID is
    still available with `active_gini_source=unu-wider-2025`. It is
    licensed CC BY-NC-SA 3.0 IGO, and those terms travel with every
    Gini-derived output. The two sources give materially different
    capability-based allocations; see
    [Data Sources & Licensing](data-sources.md).

---

## Registry Reference

All approaches are registered in [`src/fair_shares/library/allocations/manager.py`](https://github.com/setupelz/fair-shares/blob/main/src/fair_shares/library/allocations/manager.py).

```python
from fair_shares.library.allocations.manager import get_allocation_functions

approaches = get_allocation_functions()
print(list(approaches.keys()))
```

To add an approach, see [Adding approaches](../dev-guide/adding-approaches.md).
