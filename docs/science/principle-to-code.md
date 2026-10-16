---
title: From principle to code
description: The process of translating climate equity principles into fair-shares configurations
search:
  boost: 2
---

# From principle to code

This page describes how to turn equity principles into settings.
It does not prescribe which principles to adopt. That is a normative decision.
[Allocation approaches](allocations.md) explains each approach and parameter.

## The five entry points

Based on the entry points framework in [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). Each entry point is a decision the analyst must make.

| Entry Point                | Your Question                                                                          | What It Determines                                                                   |
| -------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **1. Identify Principles** | What values define fairness? Equal entitlement? Historical responsibility? Capability? | Whether you need adjustment weights or pure equal per capita                         |
| **2. Define Quantity**     | Fixed budget or annual pathways?                                                       | Budget vs. pathway approaches; "how much total?" vs. "what trajectory?"              |
| **3. Choose Approach**     | Which formulation operationalizes my principles?                                       | Function and parameters (`adjusted` = R+C, `gini-adjusted` = subsistence protection) |
| **4. Select Indicators**   | Which data sources? Which reference years?                                             | Population/emissions (foundational); GDP/Gini (for adjustments)                      |
| **5. Communicate Results** | Can someone replicate this? Are value judgments explicit?                              | Transparency and reproducibility                                                     |

Work forward from the principles. Choosing settings to reach a preferred allocation removes the scientific basis of the result.

!!! note "Scholarly context"

    The entry-points framework sits within a wider conversation about how to interpret the Paris Agreement's equity provisions. For the legal interpretation of CBDR-RC in its normative environment, see [Rajamani 2024](https://doi.org/10.1093/clp/cuae011). For the ethical choices hidden inside fair-share quantifications, see [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8). On the duties of states under international climate law, see the [ICJ 2025](https://www.icj-cij.org/case/187) advisory opinion.

---

## Quick reference

| Normative Position                                | Operationalized By                                                             | Detail                                                                                 |
| ------------------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| Equal entitlement to atmospheric space            | `equal-per-capita-*` approaches                                                | [Allocation Approaches](allocations.md)                                                |
| Past emissions count against remaining budget     | Early `allocation_year` (cumulative accounting from that year; can produce negative allocations)    | [Historical Responsibility](allocations.md#historical-responsibility)                  |
| Historical emissions rescale allocation           | `pre_allocation_responsibility_weight` in `*-adjusted` approaches (multiplicative rescaling) | [Historical Responsibility](allocations.md#historical-responsibility)                  |
| Wealthier countries should do more                | `capability_weight` in `*-adjusted` approaches (GDP-based rescaling; by default from the allocation year onwards, or a snapshot year or past window) | [Allocation Approaches](allocations.md)                                                |
| Protect basic development needs                   | `income_floor`, `*-gini-*` approaches                                          | [Gini Adjustment](allocations.md#gini-adjustment)                                      |
| Gradual transition to fair shares                 | `cumulative-per-capita-convergence-*` approaches                               | [Convergence Mechanism](allocations.md#convergence-mechanism-pathways-only)             |

---

## Example configurations

Each example states a value judgement and the configuration that expresses it.
They show how principles become settings. They are not recommendations.
Pass the `allocations` dictionary to a country notebook ([Country fair shares](../user-guide/country-fair-shares.md#2-choose-the-approaches)).

### 1. Equal per capita

**Value judgement:** Equal entitlement to atmospheric space is the only relevant principle. Past emissions and wealth create no differential obligations.

```python
allocations = {
    "equal-per-capita-budget": [
        {"allocation_year": [2020], "preserve_allocation_year_shares": [False]}
    ]
}
```

There are no adjustment weights, and the allocation year counts no past emissions. Shares follow population as it changes.
Populous countries such as India and China receive large allocations, and every country starts with its full share.
The atmosphere is treated as a global commons shared equally among all living persons.

### 2. Both responsibility mechanisms

**Value judgement:** Historical responsibility is the main basis for differentiation. Countries that caused the problem should bear more of the burden.

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [1990],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [1950],
            "capability_weight": [0.0],
            "preserve_allocation_year_shares": [False],
        }
    ]
}
```

Cumulative population from 1990 sets the shares, so emissions since 1990 count in full and remaining budgets can be negative.
Emissions from 1950 to 1989 then rescale the shares, absolute by default. High historical emitters get proportionally less.
This is the polluter-pays principle through [both mechanisms](allocations.md#building-blocks).

### 3. Capability

**Value judgement:** Wealthier countries have more capacity to mitigate and should bear more of the burden.

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [2020],
            "pre_allocation_responsibility_weight": [0.0],
            "capability_weight": [1.0],
            "preserve_allocation_year_shares": [False],
        }
    ]
}
```

GDP per capita from 2020 onwards scales the shares, and past emissions do not count.
High-GDP countries such as the USA and Germany receive less than equal per capita, and low-GDP countries more.
This is the ability-to-pay principle.

### 4. Responsibility by rescaling only

**Value judgement:** High historical emitters should receive less, through proportional rescaling rather than budget accounting.

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [2020],
            "pre_allocation_responsibility_weight": [1.0],
            "capability_weight": [0.0],
            "preserve_allocation_year_shares": [False],
        }
    ]
}
```

Past emissions rescale the shares, and the allocation year stays at 2020.
Unlike example 2, no country receives a negative allocation, while countries are still differentiated by historical responsibility.

### 5. Immediate pathway with capability and responsibility

**Value judgement:** Annual emissions should reflect fair shares at once, without a gradual transition from current emissions.

```python
allocations = {
    "per-capita-adjusted": [
        {
            "first_allocation_year": [2025],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_weight": [0.5],
        }
    ]
}
```

This is a pathway approach, not a convergence approach.
Responsibility uses each country's total cumulative emissions from 1990 (the default `pre_allocation_responsibility_year`) to 2024, absolute by default. Capability uses GDP per capita year by year from 2025. This split between past and present is inherent to CBDR-RC.
High-GDP, high-emission countries receive allocations below their current emissions from 2025, and low-income countries above. Shares track population and GDP year by year.
Annual allocations reflect responsibility and capacity from the first year, with no transition from current emissions.

### 6. Convergence with capability and responsibility

**Value judgement:** An immediate move to fair shares is disruptive and politically infeasible. A gradual transition is needed, with capability and responsibility differentiating the targets.

```python
allocations = {
    "cumulative-per-capita-convergence-adjusted": [
        {
            "first_allocation_year": [2025],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_weight": [0.5],
            "pre_allocation_responsibility_year": [1990],
            "strict": [False],
        }
    ]
}
```

Countries move from current emissions toward cumulative per capita targets, and the cumulative totals match the budget.
Responsibility uses each country's total cumulative emissions from 1990 to 2024, and capability GDP per capita from 2025.
Only the ratio of the two weights matters: `(0.5, 0.5)` equals `(0.3, 0.3)`. Their sum may not exceed 1.0.
`strict=False` accepts approximate solutions and reports each country's deviation as a warning ([Convergence](allocations.md#convergence-mechanism-pathways-only)).
Starting from current emissions gives high emitters more in the near term. Unlike `per-capita-convergence`, the totals are budget-preserving.
To replicate the ECPC of Dekker et al. (Eqs. 5-6) with historical population entitlements, compute entitlements with `equal-per-capita-budget(allocation_year=1850)`, let the library subtract observed emissions ([`compute_remaining_budgets`](../api/python-api.md#compute_remaining_budgets)), and run the convergence over the future window only.

### 7. Development first

**Value judgement:** Development rights come first. Only income above subsistence counts toward capability, and emissions before the scientific consensus of 1990 count only lightly.

```python
allocations = {
    "per-capita-adjusted-gini-budget": [
        {
            "allocation_year": [1990],
            "pre_allocation_responsibility_weight": [0.2],
            "pre_allocation_responsibility_year": [1950],
            "capability_weight": [0.8],
            "income_floor": [10000],
            "preserve_allocation_year_shares": [False],
        }
    ]
}
```

Cumulative population from 1990 sets the shares. Each country's total cumulative emissions from 1950 to 1989 rescale them with a small weight (absolute, because `pre_allocation_responsibility_per_capita` defaults to `False`). Gini-adjusted GDP per capita from 1990 onwards rescales them with a large weight.
The floor of 10,000 is above the GDR threshold of 7,500 dollars on a 2005 price base, a broader subsistence definition. The Gini source configured for the run adds inequality within countries.
At this floor the default `max_gini_adjustment=0.8` holds 54 of 178 rows (177 countries and rest-of-world) at 20% of GDP, so the cap shapes the result as much as the floor does.
Least developed countries keep most of their allocation. High-income countries lose budget to accounting since 1990 and to capability.

---

## What This Tool Cannot Tell You

The library puts principles into practice. It cannot tell you which principles to adopt. The following questions require normative judgment, and the literature contains diverse positions on each:

1. **Which principles are morally relevant?** Should historical responsibility matter? Should capability determine obligations? These are philosophical questions about justice. For a concise overview of the competing ethical traditions (utilitarian, egalitarian, capabilities, cosmopolitan, Rawlsian), see [Caney 2021](https://plato.stanford.edu/entries/justice-climate/) in the Stanford Encyclopedia of Philosophy, and [Shue 2014](references.md#shue-2014) for the subsistence/luxury-emissions distinction that underpins most development-rights framings.

2. **Where do thresholds come from?** Income floors, pre-allocation responsibility start dates, convergence years involve value judgments about development rights and transition feasibility. The $7,500 PPP development threshold used in fair-shares originates in the Greenhouse Development Rights framework ([Baer 2013](https://doi.org/10.1002/wcc.201)); other thresholds require their own defence.

3. **What follows from a negative remaining allocation?** When `allocation_year` is in the past, high historical emitters can have emitted more than their allocation, so their remaining allocation is negative (carbon debt). The value shows the size of the exceedance. [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f) and [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122) read it as calling for the highest possible domestic ambition, net-negative targets through carbon dioxide removal, and international support for others, with priority on minimising the duration and magnitude of overshoot. [Matthews 2016](https://doi.org/10.1038/NCLIMATE2774) gives the earlier carbon-debt formulation. Which obligations follow (domestic mitigation, financial transfers, investment in carbon dioxide removal) needs political specification. The library reports the value and leaves that specification to the user.

4. **Is convergence ethically acceptable?** Convergence embeds grandfathering: shares during the transition follow current emissions. [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) catalogues the resulting distributional bias, and [Caney 2009](https://doi.org/10.1080/17449620903110300) makes the ethical case against it. The library offers `per-capita-convergence` for comparison. This is distinct from cumulative-per-capita-convergence, which starts with current per capita emissions but converges to cumulative per capita shares over time.

5. **Which temperature target?** Allocations depend on carbon budget, which depends on temperature target (1.5°C, 2°C) and probability threshold [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5). These are risk tolerance decisions.

**What the library provides:**

- **Operational transparency**: Given your principles, what allocations follow?
- **Sensitivity analysis**: How do results change with different parameters?
- **Replicability**: Can others reproduce your results from your stated configuration?

**The gap between principles and policy:** Fair shares allocations are **reference points** for assessing equity, not directly implementable policy. Moving from allocation to implementation requires additional specification: domestic mitigation vs. international support, cost-effectiveness, political feasibility, and more.
