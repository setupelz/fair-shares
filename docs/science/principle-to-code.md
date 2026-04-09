---
title: From Principle to Code
description: The process of translating climate equity principles into fair-shares configurations
search:
  boost: 2
---

## Purpose

This guide describes the **process** of translating equity principles into fair-shares configurations. It does not prescribe which principles to adopt — that is a normative decision. Instead, it provides a structured framework for making those decisions explicit and mapping them to tool configuration.

For allocation approach details and parameters, see [Allocation Approaches](allocations.md).

---

## The Five Entry Points

Based on the entry points framework in [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f). Each entry point is a decision the analyst must make.

```mermaid
flowchart LR
    Start([Start]) --> Step1[1. Identify<br/>Principles]
    Step1 --> Step2[2. Define<br/>Quantity]
    Step2 --> Step3[3. Choose<br/>Approach]
    Step3 --> Step4[4. Select<br/>Indicators]
    Step4 --> Step5[5. Communicate<br/>Results]
    Step5 --> End([Complete])

    style Step1 fill:#e1f5e1
    style Step2 fill:#e1f5e1
    style Step3 fill:#e1f5e1
    style Step4 fill:#e1f5e1
    style Step5 fill:#e1f5e1
```

| Entry Point                | Your Question                                                                          | What It Determines                                                                   |
| -------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **1. Identify Principles** | What values define fairness? Equal entitlement? Historical responsibility? Capability? | Whether you need adjustment weights or pure equal per capita                         |
| **2. Define Quantity**     | Fixed budget or annual pathways?                                                       | Budget vs. pathway approaches; "how much total?" vs. "what trajectory?"              |
| **3. Choose Approach**     | Which formulation operationalizes my principles?                                       | Function and parameters (`adjusted` = R+C, `gini-adjusted` = subsistence protection) |
| **4. Select Indicators**   | Which data sources? Which reference years?                                             | Population/emissions (foundational); GDP/Gini (for adjustments)                      |
| **5. Communicate Results** | Can someone replicate this? Are value judgments explicit?                              | Transparency and reproducibility                                                     |

**Anti-pattern**: Working backward from favorable allocations undermines scientific legitimacy.

!!! note "Scholarly context"

    The entry-points framework sits within a wider conversation about how to interpret the Paris Agreement's equity provisions. For the legal interpretation of CBDR-RC in its normative environment, see [Rajamani 2024](https://doi.org/10.1093/clp/cuae011). For the ethical choices hidden inside fair-share quantifications, see [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8). On the duties of states under international climate law, see the [ICJ 2025](https://www.icj-cij.org/case/187) advisory opinion.

---

## Quick Reference

Each normative position maps to specific allocation approaches and parameters. See [Allocation Approaches](allocations.md) for full detail.

| Normative Position                                | Operationalized By                                                             | Detail                                                                                 |
| ------------------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| Equal entitlement to atmospheric space            | `equal-per-capita-*` approaches                                                | [Allocation Approaches](allocations.md)                                                |
| Past emissions count against remaining budget     | Early `allocation_year` (cumulative accounting from that year; can produce negative allocations)    | [Historical Responsibility](allocations.md#historical-responsibility)                  |
| Historical per-capita emissions scale allocation  | `pre_allocation_responsibility_weight` in `*-adjusted` approaches (multiplicative rescaling; always positive) | [Historical Responsibility](allocations.md#historical-responsibility)                  |
| Wealthier countries should do more                | `capability_weight` in `*-adjusted` approaches (GDP-based rescaling from allocation year onwards) | [Allocation Approaches](allocations.md)                                                |
| Protect basic development needs                   | `income_floor`, `*-gini-*` approaches                                          | [Gini Adjustment](allocations.md#gini-adjustment)                                      |
| Gradual transition to fair shares                 | `cumulative-per-capita-convergence-*` approaches                               | [Convergence Mechanism](allocations.md#convergence-mechanism-pathways-only)             |

---

## Example Configurations

The following examples illustrate how principles combine in practice. Each configuration reflects specific value judgments — they are not recommendations, but transparent demonstrations of how different ethical positions translate to allocation configurations.

**Note:** The configurations below demonstrate the **logic** of combining principles, not prescriptions for which combinations you should use. Your task is to identify which principles matter for your analysis, then configure accordingly.

### Example 1: Equal Per Capita (Egalitarian)

**Value judgment:** Equal entitlement to atmospheric space is the only relevant principle. Historical emissions and economic capability do not create differential obligations — all that matters is equal per capita rights today.

**Configuration:**

```python
allocations = {
    "equal-per-capita-budget": [
        {
            "allocation_year": [2020],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
```

**What this reflects:**

- No pre-allocation responsibility/capability weights → Historical emissions and wealth don't affect allocation
- `allocation_year=2020` → Forward-looking; no cumulative accounting of past emissions in the budget
- `preserve_allocation_year_shares=False` → Shares adjust with population changes

**Distributional outcome:** Countries with high population shares (India, China) receive proportionally large allocations. All countries start with their full fair share — no cumulative accounting of past emissions.

**Underlying reasoning:** The atmosphere is treated as a global commons to be shared equally among all living persons, without regard to past emissions.

---

### Example 2: Both Responsibility Mechanisms (Cumulative Accounting + Rescaling)

**Value judgment:** Historical responsibility is the primary basis for differentiation. Countries that caused the climate problem through cumulative emissions should bear proportionally greater mitigation burdens. Equal per capita provides the baseline, but historical excess emissions strongly reduce allocation.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [1990],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [1950],
            "capability_weight": [0.0],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
```

**What this reflects:**

- `allocation_year=1990` → Cumulative population from 1990 determines each country's share of the total budget
- `pre_allocation_responsibility_weight=1.0` + `pre_allocation_responsibility_year=1950` → Per-capita emissions from 1950-1989 fully rescale shares — high historical per-capita emitters get proportionally less (relative mechanism)
- `capability_weight=0.0` → GDP does not affect allocation
- Both mechanisms are active: cumulative accounting via early allocation year AND relative rescaling via pre-allocation responsibility weight. These behave differently: the early allocation year determines shares from cumulative population, and negative allocations are a mathematical consequence when those shares are applied to a budget. The rescaling is a multiplicative adjustment that always produces positive allocations if `allocation_year` is the present.

**Distributional outcome:** Both mechanisms apply to industrialized countries: cumulative population from 1990 determines their share (via early allocation_year), and 1950-1989 per-capita emissions rescale their proportional share of what remains (via pre_allocation_responsibility_weight=1.0). Countries with low historical emissions retain most of their per-capita allocation.

**Underlying reasoning:** The polluter pays principle is paramount. An early `allocation_year` means cumulative population from that year determines shares; `pre_allocation_responsibility_weight` additionally rescales shares based on pre-1990 per-capita emissions.

---

### Example 3: Capability Adjustment

**Value judgment:** Wealthier countries have greater capacity to mitigate and should bear proportionally more of the burden. GDP from the allocation year onwards scales per-capita shares so high-income countries receive smaller allocations.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [2020],
            "pre_allocation_responsibility_weight": [0.0],
            "capability_weight": [1.0],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
```

**What this reflects:**

- `allocation_year=2020` → Forward-looking; no cumulative accounting of past emissions in the budget
- `capability_weight=1.0` → GDP fully scales per-capita shares (from allocation year onwards)
- `pre_allocation_responsibility_weight=0.0` → Historical emissions do not affect allocation

**Distributional outcome:** High-GDP countries (US, Germany) receive smaller allocations than pure equal per capita would give them. Low-GDP countries receive larger allocations. The adjustment is based on economic capacity from the allocation year onwards, not historical emissions.

**Underlying reasoning:** The ability-to-pay principle. Countries with greater economic resources should lead mitigation because they can afford to.

**GDP window:** When the cumulative window extends past the last observed GDP year (`wdi-2025` ends at 2023), GDP per capita is forward-filled from the last observed year so that every subsequent year of the window uses the same cross-country capability ratios. To plug in projected GDP (SSP2, a custom growth assumption, or an updated WDI release), extend the input `gdp_ts` time series before calling the allocation function.

---

### Example 4: Historical Responsibility via Rescaling

**Value judgment:** Countries with high historical per-capita emissions should receive smaller allocations. Rather than accounting for cumulative past emissions in the budget (as an early `allocation_year` does), historical per-capita emissions rescale the allocation — a multiplicative adjustment rather than cumulative accounting.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [2020],
            "pre_allocation_responsibility_weight": [1.0],
            "capability_weight": [0.0],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
```

**What this reflects:**

- `allocation_year=2020` → No cumulative accounting of past emissions in the budget
- `pre_allocation_responsibility_weight=1.0` → Historical per-capita emissions rescale allocation
- `capability_weight=0.0` → GDP does not affect allocation

**Distributional outcome:** Countries with high historical per-capita emissions (US, EU) receive smaller allocations. Unlike early `allocation_year` (Example 2), no country receives a negative allocation — the rescaling always produces positive allocations when `allocation_year` is the present, reducing shares proportionally.

**Underlying reasoning:** Historical emissions create differential obligations, but the mechanism is proportional rescaling rather than cumulative budget accounting. This avoids negative allocations while still differentiating based on historical responsibility.

**Contrast with early allocation year:** Example 2 uses `allocation_year=1990`, where cumulative population from 1990 determines shares — some countries end up with negative allocations when those shares are applied to a budget. This example achieves historical differentiation without negative allocations.

---

### Example 5: Immediate Pathway with Capability Adjustment

**Value judgment:** Annual emissions should reflect fair shares immediately, not gradually converge. Economic capability should reduce allocations in each year, creating differentiated annual trajectories without grandfathering. This is a pathway approach (year-by-year allocations) but NOT a convergence approach (no gradual transition from current emissions).

**Configuration:**

```python
allocations = {
    "per-capita-adjusted": [
        {
            "first_allocation_year": [2025],
            "capability_weight": [0.5],
            "pre_allocation_responsibility_weight": [0.5]
        }
    ]
}
# Run through allocation pipeline with AR6 scenario data configured in conf/
# This creates annual pathway allocations, NOT gradual convergence
```

**What this reflects:**

- `first_allocation_year=2025` → Start pathway allocations from 2025
- `capability_weight=0.5`, `pre_allocation_responsibility_weight=0.5` → Balanced CBDR-RC in each year. Capability adjustments apply from the first allocation year onwards; pre-allocation responsibility looks backward from it — this temporal asymmetry is inherent to CBDR-RC.
- No convergence → Countries immediately receive fair shares in 2025, adjusted each year
- Immediate allocation → No grandfathering, high emitters get reduced shares immediately

**Distributional outcome:** High-GDP, high-historical-emission countries (US, EU) receive allocations below current emissions from 2025 onward. Low-income countries receive allocations above current emissions from 2025 onward. Year-by-year adjustments track population and GDP changes dynamically.

**Underlying reasoning:** Fair shares should apply immediately, not phased in over time. Annual allocations respect both historical responsibility and current capacity without rewarding past excess through convergence.

**Contrast with convergence:** This approach allocates fair shares immediately; convergence (Example 6) gradually transitions from current to fair shares, preserving inequality during the transition period.

<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

### Example 6: Convergence with Capability Adjustment

**Value judgment:** Immediate transition to equal per capita is economically disruptive and politically infeasible. A gradual pathway that converges to fair shares over time is necessary for transition planning, but economic capability should determine how fast countries converge and how much they pay for international support. Furthermore, cumulative per-capita entitlements should reflect historical population patterns — countries that had large populations during the period of industrialisation had more people with a claim to equal atmospheric space.

**Configuration:**

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
# Run through allocation pipeline with AR6 scenario data configured in conf/
# Note: Use cumulative-per-capita-convergence-adjusted (not base convergence)
# for pre-allocation responsibility/capability weighting
```

**What this reflects:**

- `first_allocation_year=2025` → Begin convergence pathway from 2025
- `capability_weight=0.5`, `pre_allocation_responsibility_weight=0.5` → Equal weighting of capability (GDP, from first allocation year onwards) and historical responsibility (per-capita emissions, looking backward from it). These weights are relative — only the ratio matters. `(0.5, 0.5)` is identical to `(0.3, 0.3)` or `(1.0, 1.0)`. If one weight is 0, the other becomes the sole adjustment regardless of its value.
- `pre_allocation_responsibility_year=1990` → Responsibility rescaling window covers 1990–2025
- `strict=False` → Accept approximate solutions if some countries' targets are mathematically infeasible. The solver reports per-country deviation ratios as warnings rather than raising an error. Use `strict=True` (default) when you need exact results and want to know immediately if a configuration is infeasible.
- Cumulative constraint → Total pathway emissions respect global budget

**Distributional outcome:** Countries transition from current emissions toward cumulative per capita targets while preserving cumulative shares. The balanced responsibility/capability weighting means both historical per-capita emissions (1990–2025) and GDP per capita reduce allocations for developed countries. Starting from current emissions means high emitters receive higher near-term allocations, but cumulative totals are budget-preserving (unlike `per-capita-convergence` which is NOT budget-preserving).

**Underlying reasoning:** Cumulative per capita shares are the fair target, but immediate redistribution is impractical. Transition pathways balance long-term equity with near-term feasibility while preserving cumulative budgets. The balanced CBDR-RC weighting differentiates by both who emitted most and who can afford to act.

**Contrast with immediate pathways:** Cumulative per capita convergence creates gradual transitions from current emissions (preserving near-term inequality) while respecting cumulative budget constraints. Immediate pathways (Example 5) allocate fair shares from the start.

**Note on historical accounting:** To replicate Dekker's ECPC (Eqs. 5-6) with historical population entitlements, use `equal-per-capita-budget(allocation_year=1850)` to compute per-country entitlements from a historical year, then post-process by subtracting actual historical emissions. The convergence pathway should only run over the future window. See [Allocations](allocations.md) for details.

---

### Example 7: Development-First (Minimal Differentiation)

**Value judgment:** Development rights are paramount. Countries should be allowed to reach development thresholds before facing mitigation burdens. Only income above subsistence counts toward capability, and historical emissions before widespread scientific consensus (1990) should not create obligations.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-gini-budget": [
        {
            "allocation_year": [1990],
            "pre_allocation_responsibility_weight": [0.2],
            "pre_allocation_responsibility_year": [1950],
            "capability_weight": [0.8],
            "income_floor": [10000],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
# Gini adjustment is automatic when gini data source is configured
```

**What this reflects:**

- `allocation_year=1990` → Cumulative population from 1990 determines each country's share of the total budget
- `pre_allocation_responsibility_weight=0.2` + `pre_allocation_responsibility_year=1950` → Per-capita emissions from 1950-1989 rescale allocations (relative mechanism)
- `capability_weight=0.8` → GDP-based capability dominates the adjustment (applies from allocation year onwards)
- `income_floor=10000` → Higher than GDR threshold ($7,500/year 2010 PPP) — broader subsistence definition (GDR was designed for burden-sharing; fair-shares adapts its capability metric for entitlement allocation)
- Gini data configured → Within-country inequality affects effective capability

**Distributional outcome:** Least developed countries retain most of their remaining allocation. High-income countries have reduced remaining allocations (from cumulative budget accounting since 1990), further reduced by capability_weight=0.8. The pre_allocation_responsibility_weight=0.2 additionally rescales shares based on 1950-1989 per-capita emissions (this rescaling always produces positive allocations if `allocation_year` is the present — it is a multiplicative adjustment, not cumulative accounting).

**Underlying reasoning:** The right to development takes precedence. Wealthy countries should lead mitigation because they have the capacity. Subsistence protection ensures development needs are met before mitigation burdens are assessed. Pre-allocation responsibility plays a supporting role, not the primary one.

<!-- REFERENCE: Configuration format matches AllocationManager in src/fair_shares/library/allocations/manager.py
     Budget approaches: src/fair_shares/library/allocations/budgets/per_capita.py
     Pathway approaches: src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py
     Usage example: notebooks/301_custom_fair_share_allocation.ipynb
-->

---

## What This Tool Cannot Tell You

Fair-shares operationalizes principles -- it cannot tell you which principles to adopt. The following questions require normative judgment, and the literature contains diverse positions on each:

1. **Which principles are morally relevant?** — Should historical responsibility matter? Should capability determine obligations? These are philosophical questions about justice. For a concise overview of the competing ethical traditions (utilitarian, egalitarian, capabilities, cosmopolitan, Rawlsian), see [Caney 2021](https://plato.stanford.edu/entries/justice-climate/) in the Stanford Encyclopedia of Philosophy, and [Shue 2014](references.md#shue-2014) for the subsistence/luxury-emissions distinction that underpins most development-rights framings.

2. **Where do thresholds come from?** — Income floors, pre-allocation responsibility start dates, convergence years involve value judgments about development rights and transition feasibility. The $7,500 PPP development threshold used in fair-shares originates in the Greenhouse Development Rights framework ([Baer 2013](https://doi.org/10.1002/wcc.201)); other thresholds require their own defence.

3. **What happens with negative remaining allocations?** — When `allocation_year` is in the past, high historical emitters may have already exceeded their fair share — their remaining allocation is negative (carbon debt). Negative allocations communicate the scale of exceedance and create a signal for what is required. They imply the need for highest possible domestic ambition, negative emissions targets (carbon dioxide removal), and international support for others. The priority is to minimize the duration and magnitude of overshoot [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f); [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122); see also [Matthews 2016](https://doi.org/10.1038/NCLIMATE2774) for the earlier carbon-debt formulation. What specific obligations follow (accelerated domestic mitigation, financial transfers, CDR investments) requires political specification, but the tool transparently surfaces the normative implication.

4. **Is convergence ethically acceptable?** — Convergence embeds grandfathering, rewarding past high emissions. [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) catalogues the resulting distributional bias; [Caney 2009](https://doi.org/10.1080/17449620903110300) makes the ethical case against it. The tool provides pure per-capita-convergence approaches for transparency, not endorsement. This is distinct from cumulative-per-capita-convergence, which starts with current per capita emissions but converges to cumulative per capita shares over time.

5. **Which temperature target?** — Allocations depend on carbon budget, which depends on temperature target (1.5°C, 2°C) and probability threshold [Lamboll 2023](https://doi.org/10.1038/s41558-023-01848-5). These are risk tolerance decisions.

**What the tool DOES provide:**

- **Operational transparency** — Given your principles, what allocations follow?
- **Sensitivity analysis** — How do results change with different parameters?
- **Replicability** — Can others reproduce your results from your stated configuration?

**The gap between principles and policy:** Fair shares allocations are **reference points** for assessing equity, not directly implementable policy. Moving from allocation to implementation requires additional specification: domestic mitigation vs. international support, cost-effectiveness, political feasibility, and more.
