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

Based on the Pelz et al. 2025 framework. Each entry point is a decision you must make.

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

---

## Quick Reference

Each normative position maps to specific allocation approaches and parameters. See [Allocation Approaches](allocations.md) for full detail.

| Normative Position                                | Operationalized By                                                             | Detail                                                                                 |
| ------------------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| Equal entitlement to atmospheric space            | `equal-per-capita-*` approaches                                                | [Allocation Approaches](allocations.md)                                                |
| Past emissions count against remaining budget     | Early `allocation_year` (past emissions subtracted directly)                   | [Historical Responsibility](allocations.md#historical-responsibility)                  |
| Historical per-capita emissions scale allocation  | `responsibility_weight` in `*-adjusted` approaches                             | [Historical Responsibility](allocations.md#historical-responsibility)                  |
| Wealthier countries should do more                | `*-adjusted` approaches (GDP scales per-capita shares)                         | [Allocation Approaches](allocations.md)                                                |
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

- No responsibility/capability weights → Historical emissions and wealth don't affect allocation
- `allocation_year=2020` → Forward-looking; no past emissions subtracted (allocation starts from 2020)
- `preserve_allocation_year_shares=False` → Shares adjust with population changes

**Distributional outcome:** Countries with high population shares (India, China) receive proportionally large allocations. All countries start with their full fair share — no historical subtraction.

**Underlying reasoning:** The atmosphere is treated as a global commons to be shared equally among all living persons, without regard to past emissions.

---

### Example 2: Strong CBDR-RC (Responsibility Dominant)

**Value judgment:** Historical responsibility is the primary basis for differentiation. Countries that caused the climate problem through cumulative emissions should bear proportionally greater mitigation burdens. Equal per capita provides the baseline, but historical excess emissions strongly reduce allocation.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [1990],
            "responsibility_weight": [1.0],
            "capability_weight": [0.0],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
```

**What this reflects:**

- `allocation_year=1990` → Past emissions (1990-present) are subtracted from total budget before allocation
- `responsibility_weight=1.0` → Full reduction in allocation for historical excess
- `capability_weight=0.0` → GDP does not affect allocation

**Distributional outcome:** Industrialized countries with high cumulative emissions (US, EU, Russia) have already consumed much of their fair share — their **remaining** allocation is very small or negative. Countries with low historical emissions retain most of their fair share.

**Underlying reasoning:** The polluter pays principle is paramount. Past emissions reduce what remains of your fair share.

---

### Example 3: Capability Adjustment

**Value judgment:** Wealthier countries have greater capacity to mitigate and should bear proportionally more of the burden. GDP scales per-capita shares so high-income countries receive smaller allocations.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [2020],
            "responsibility_weight": [0.0],
            "capability_weight": [1.0],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
```

**What this reflects:**

- `allocation_year=2020` → Forward-looking; no past emissions subtracted
- `capability_weight=1.0` → GDP fully scales per-capita shares
- `responsibility_weight=0.0` → Historical emissions do not affect allocation

**Distributional outcome:** High-GDP countries (US, Germany) receive smaller allocations than pure equal per capita would give them. Low-GDP countries receive larger allocations. The adjustment is based on current economic capacity, not historical emissions.

**Underlying reasoning:** The ability-to-pay principle. Countries with greater economic resources should lead mitigation because they can afford to.

---

### Example 4: Historical Responsibility via Rescaling

**Value judgment:** Countries with high historical per-capita emissions should receive smaller allocations. Rather than subtracting past emissions from the budget (as an early `allocation_year` does), historical per-capita emissions rescale the allocation — a multiplicative adjustment rather than an arithmetic one.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-budget": [
        {
            "allocation_year": [2020],
            "responsibility_weight": [1.0],
            "capability_weight": [0.0],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
```

**What this reflects:**

- `allocation_year=2020` → No past emissions subtracted from the budget
- `responsibility_weight=1.0` → Historical per-capita emissions rescale allocation
- `capability_weight=0.0` → GDP does not affect allocation

**Distributional outcome:** Countries with high historical per-capita emissions (US, EU) receive smaller allocations. Unlike early `allocation_year` (Example 2), no country starts with a negative remaining allocation — the rescaling reduces shares proportionally rather than subtracting a fixed quantity.

**Underlying reasoning:** Historical emissions create differential obligations, but the mechanism is proportional rescaling rather than direct subtraction. This avoids negative allocations while still differentiating based on historical responsibility.

**Contrast with early allocation year:** Example 2 uses `allocation_year=1990` to subtract 1990-present emissions directly — some countries end up with negative remaining budgets. This example achieves historical differentiation without negative allocations.

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
            "responsibility_weight": [0.5]
        }
    ]
}
# Run through allocation pipeline with AR6 scenario data configured in conf/
# This creates annual pathway allocations, NOT gradual convergence
```

**What this reflects:**

- `first_allocation_year=2025` → Start pathway allocations from 2025
- `capability_weight=0.5`, `responsibility_weight=0.5` → Balanced CBDR-RC in each year
- No convergence → Countries immediately receive fair shares in 2025, adjusted each year
- Immediate allocation → No grandfathering, high emitters get reduced shares immediately

**Distributional outcome:** High-GDP, high-historical-emission countries (US, EU) face immediate strong reductions from current emissions. Low-income countries receive allocations above current emissions immediately. Year-by-year adjustments track population and GDP changes dynamically.

**Underlying reasoning:** Fair shares should apply immediately, not phased in over time. Annual allocations respect both historical responsibility and current capacity without rewarding past excess through convergence.

**Contrast with convergence:** This approach allocates fair shares immediately; convergence (Example 6) gradually transitions from current to fair shares, preserving inequality during the transition period.

<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

### Example 6: Convergence with Capability Adjustment

**Value judgment:** Immediate transition to equal per capita is economically disruptive and politically infeasible. A gradual pathway that converges to fair shares over time is necessary for transition planning, but economic capability should determine how fast countries converge and how much they pay for international support.

**Configuration:**

```python
allocations = {
    "cumulative-per-capita-convergence-adjusted": [
        {
            "first_allocation_year": [2025],
            "capability_weight": [0.3],
            "responsibility_weight": [0.0]
        }
    ]
}
# Run through allocation pipeline with AR6 scenario data configured in conf/
# Note: Use cumulative-per-capita-convergence-adjusted (not base convergence)
# for capability/responsibility weighting
```

**What this reflects:**

- `first_allocation_year=2025` → Begin convergence pathway from 2025
- `capability_weight=0.3` → Wealth moderately reduces allocation
- `responsibility_weight=0.0` → Historical emissions don't affect pathway
- Cumulative constraint → Total pathway emissions respect global budget

**Distributional outcome:** Countries transition from current emissions toward cumulative per capita targets while preserving cumulative shares. High-emission countries have downward trajectories; low-emission countries have upward trajectories. Starting from current emissions means high emitters receive higher near-term allocations, but cumulative totals are budget-preserving (unlike `per-capita-convergence` which is NOT budget-preserving).

**Underlying reasoning:** Cumulative per capita shares are the fair target, but immediate redistribution is impractical. Transition pathways balance long-term equity with near-term feasibility while preserving cumulative budgets.

**Contrast with immediate pathways:** Cumulative per capita convergence creates gradual transitions from current emissions (preserving near-term inequality) while respecting cumulative budget constraints. Immediate pathways (Example 5) allocate fair shares from the start.

---

### Example 7: Development-First (Minimal Differentiation)

**Value judgment:** Development rights are paramount. Countries should be allowed to reach development thresholds before facing mitigation burdens. Only income above subsistence counts toward capability, and historical emissions before widespread scientific consensus (1990) should not create obligations.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-gini-budget": [
        {
            "allocation_year": [1990],
            "responsibility_weight": [0.2],
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

- `allocation_year=1990` → Past emissions (1990-present) subtracted from budget
- `responsibility_weight=0.2`, `capability_weight=0.8` → Capability matters more than historical excess
- `income_floor=10000` → Higher than GDR threshold ($7,500/year 2010 PPP) — broader subsistence definition
- Gini data configured → Within-country inequality affects effective capability

**Distributional outcome:** Least developed countries retain most of their remaining allocation. High-income countries have reduced remaining allocations (from subtracting 1990-present emissions), further reduced by strong capability weighting.

**Underlying reasoning:** The right to development takes precedence. Wealthy countries should lead mitigation because they have the capacity. Subsistence protection ensures development needs are met before mitigation burdens are assessed.

<!-- REFERENCE: Configuration format matches AllocationManager in src/fair_shares/library/allocations/manager.py
     Budget approaches: src/fair_shares/library/allocations/budgets/per_capita.py
     Pathway approaches: src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py
     Usage example: notebooks/301_custom_fair_share_allocation.ipynb
-->

---

## What This Tool Cannot Tell You

Fair-shares operationalizes principles -- it cannot tell you which principles to adopt. The following questions require normative judgment, and the literature contains diverse positions on each:

1. **Which principles are morally relevant?** — Should historical responsibility matter? Should capability determine obligations? These are philosophical questions about justice.

2. **Where do thresholds come from?** — Income floors, responsibility start dates, convergence years involve value judgments about development rights and transition feasibility.

3. **What happens with negative remaining allocations?** — When `allocation_year` is in the past, high historical emitters may have already exceeded their fair share — their remaining allocation is negative (carbon debt). Negative allocations communicate the scale of exceedance and create a signal for what is required. They imply the need for highest possible domestic ambition, negative emissions targets (carbon dioxide removal), and international support for others. The priority is to minimize the duration and magnitude of overshoot [Pelz 2025b; Pelz 2025a]. What specific obligations follow (accelerated domestic mitigation, financial transfers, CDR investments) requires political specification, but the tool transparently surfaces the normative implication.

4. **Is convergence ethically acceptable?** — Convergence embeds grandfathering, rewarding past high emissions. The tool provides pure per-capita-convergence approaches for transparency, not endorsement. This is distinct from cumulative-per-capita-convergence, which starts with current per capita emissions but converges to cumulative per capita shares over time.

5. **Which temperature target?** — Allocations depend on carbon budget, which depends on temperature target (1.5°C, 2°C) and probability threshold. These are risk tolerance decisions.

**What the tool DOES provide:**

- **Operational transparency** — Given your principles, what allocations follow?
- **Sensitivity analysis** — How do results change with different parameters?
- **Replicability** — Can others reproduce your results from your stated configuration?

**The gap between principles and policy:** Fair shares allocations are **reference points** for assessing equity, not directly implementable policy. Moving from allocation to implementation requires additional specification: domestic mitigation vs. international support, cost-effectiveness, political feasibility, and more.
