---
title: From Principle to Code
description: Translate climate equity principles into fair-shares configurations
search:
  boost: 2
---

## Purpose of This Guide

This guide walks you through the **process** of translating climate equity principles into fair-shares configurations. It answers: "Given the principles I've chosen, how do I configure the tool?"

For **understanding what principles mean** and their ethical grounding, see [Climate Equity Concepts](climate-equity-concepts.md). This guide assumes you've read that page or are familiar with the concepts.

**Key insight**: Define your principles first, then select the allocation approach that operationalizes those principles.

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

## Principle-to-Code Quick Reference

Each principle maps to specific configuration choices. For conceptual background, follow the links to [Climate Equity Concepts](climate-equity-concepts.md).

| Principle                                                   | Concept Reference                                                                          | Key Questions                                 | Code Building Blocks                                               |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------- | ------------------------------------------------------------------ |
| **[Equal per capita](#equal-per-capita)**                   | [Equal Per Capita Entitlement](climate-equity-concepts.md#equal-per-capita-entitlement)    | Population year? Pure or adjusted?            | `equal_per_capita_budget()`, `equal_per_capita()`                  |
| **[Historical responsibility](#historical-responsibility)** | [Historical Responsibility](climate-equity-concepts.md#historical-responsibility)          | Start date? Weight? Subsistence exemption?    | `allocation_year`, `responsibility_weight`                         |
| **[Capability](#capability)**                               | [Ability to Pay](climate-equity-concepts.md#ability-to-pay)                                | GDP indicator? Development threshold? Weight? | `capability_weight`, `income_floor`                                |
| **[CBDR-RC](#cbdr-rc)**                                     | [CBDR-RC in Overview](climate-equity-concepts.md#overview)                                 | Balance R vs. C? Include subsistence?         | `*-adjusted` approaches, weight combinations                       |
| **[Subsistence protection](#subsistence-protection)**       | [Protection of Basic Needs](climate-equity-concepts.md#protection-of-basic-needs)          | Income floor? Gini adjustment?                | `*-gini-adjusted` approaches, `income_floor`                       |
| **[Convergence](#convergence)**                             | [Cumulative vs. Annual](climate-equity-concepts.md#cumulative-vs-annual-emissions-framing) | Budget-preserving? Pathway shape?             | `cumulative_per_capita_convergence()` vs. `per-capita-convergence` |

---

## Equal Per Capita

**Concept**: [Equal Per Capita Entitlement](climate-equity-concepts.md#equal-per-capita-entitlement)

### Questions to Answer

1. **Population year** — Which year's population determines shares? Current? Future projections?
2. **Temporal scope** — Cumulative budget (e.g., 1850-2050) or annual shares?
3. **Pure vs. adjusted** — Is equal per capita the final allocation, or a baseline for adjustments?

### Building Blocks

| Element                | Function                              | Effect                                                                            |
| ---------------------- | ------------------------------------- | --------------------------------------------------------------------------------- |
| Equal budget           | `equal_per_capita_budget()`           | Allocates fixed budget proportional to population                                 |
| Equal pathway          | `equal_per_capita()`                  | Allocates annual emissions proportional to population (immediate, no convergence) |
| Cumulative convergence | `cumulative_per_capita_convergence()` | Preserves cumulative per capita shares via gradual transition (budget-preserving) |

**Warning**: `per-capita-convergence` (without "cumulative") is NOT budget-preserving and includes grandfathering.

<!-- REFERENCE: equal_per_capita_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: equal_per_capita() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

## Historical Responsibility

**Concept**: [Historical Responsibility](climate-equity-concepts.md#historical-responsibility)

### Questions to Answer

1. **Start date** — 1750 (full history)? 1850 (data reliability)? 1990 (IPCC awareness)?
2. **Framing** — Compensation (assigning blame) or redistribution (equalizing benefits)?
3. **Exemptions** — Exclude subsistence emissions from responsibility accounting?
4. **Weight** — How much should history matter relative to other principles?

### Building Blocks

| Element                   | Parameter/Function                                             | Effect                                                |
| ------------------------- | -------------------------------------------------------------- | ----------------------------------------------------- |
| Early allocation          | `allocation_year` (budget) / `first_allocation_year` (pathway) | Earlier dates → past emissions subtracted from budget |
| Responsibility adjustment | `responsibility_weight` in `*-adjusted` approaches             | 0.0 = ignore history; 1.0 = full historical penalty   |
| Climate debt              | Matthews (2016) formula                                        | debt = Σ[actual - (world × pop fraction)]             |

!!! warning "Key insight: Remaining allocations"

    When `allocation_year` is in the past, past emissions are subtracted from the total budget before allocation. This means regions have very different **remaining** allocations depending on their historical emissions—some may already have exhausted or exceeded their fair share. For budgets, this is straightforward arithmetic. For pathways, it requires careful consideration: a region with negative remaining budget cannot follow a standard declining pathway.

**See also**: [Parameter Effects: allocation_year](parameter-effects.md#allocation_year-budget-first_allocation_year-pathway)

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

## Capability

**Concept**: [Ability to Pay](climate-equity-concepts.md#ability-to-pay)

### Questions to Answer

1. **Indicator** — GDP per capita? Income above development threshold?
2. **Threshold** — Count all income or only surplus above subsistence? GDR uses $7,500/year (2010 PPP).
3. **Weight** — 1.0 = only capability matters; 0.5 = balanced; 0.0 = ignore wealth.
4. **Reference year** — Current GDP? Historical average?

### Building Blocks

| Element               | Parameter/Function                             | Effect                          |
| --------------------- | ---------------------------------------------- | ------------------------------- |
| Capability adjustment | `capability_weight` in `*-adjusted` approaches | Higher GDP → smaller allocation |
| Income floor          | `income_floor` in `*-gini-adjusted` approaches | Exempts income below threshold  |
| GDP data              | World Bank PPP-adjusted                        | Configured via data sources     |

**See also**: [Parameter Effects: capability_weight](parameter-effects.md#capability_weight)

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

---

## CBDR-RC

**Concept**: [CBDR-RC in Overview table](climate-equity-concepts.md#overview)

CBDR-RC combines historical responsibility with capability. The question is how to balance them.

### Questions to Answer

1. **Balance** — Equal weight? Capability dominant? Responsibility dominant?
2. **National circumstances** — What beyond R&C should differentiate? (Geography, development stage, fossil dependency)
3. **Legal weight** — Reflect binding UNFCCC obligations or political feasibility?

### Building Blocks

| Configuration                                      | Meaning                        |
| -------------------------------------------------- | ------------------------------ |
| `responsibility_weight=1.0, capability_weight=0.0` | Polluter pays only             |
| `responsibility_weight=0.0, capability_weight=1.0` | Ability to pay only            |
| `responsibility_weight=0.5, capability_weight=0.5` | Balanced CBDR-RC               |
| Add `*-gini-adjusted`                              | Include subsistence protection |

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

---

## Subsistence Protection

**Concept**: [Protection of Basic Needs](climate-equity-concepts.md#protection-of-basic-needs)

### Questions to Answer

1. **Threshold** — What income defines subsistence vs. luxury? (GDR: $7,500/year 2010 PPP)
2. **What to protect** — Subsistence emissions or subsistence income?
3. **Inequality** — Account for within-country distribution (Gini)?
4. **Dynamics** — Adjust as populations move above threshold, or fix for predictability?

### Building Blocks

| Element         | Parameter/Function                  | Effect                                         |
| --------------- | ----------------------------------- | ---------------------------------------------- |
| Income floor    | `income_floor` in `*-gini-adjusted` | Exempts income below threshold from capability |
| Gini adjustment | Automatic when Gini data configured | High Gini → effective capability lower         |
| Gini pathway    | `per_capita_adjusted_gini()`        | Subsistence protection in annual allocations   |

**See also**: [Parameter Effects: income_floor](parameter-effects.md#income_floor)

<!-- REFERENCE: per_capita_adjusted_gini_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted_gini() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

## Convergence

**Concept**: [Cumulative vs. Annual Framing](climate-equity-concepts.md#cumulative-vs-annual-emissions-framing)

Convergence creates smooth transitions from current emissions to fair shares. But there are two very different types:

| Type                                 | Budget-preserving? | Fair share? | Use case                                        |
| ------------------------------------ | ------------------ | ----------- | ----------------------------------------------- |
| `cumulative-per-capita-convergence*` | Yes                | Yes         | Gradual transition preserving cumulative shares |
| `per-capita-convergence`             | **No**             | **No**      | Comparison only; includes grandfathering        |

### Questions to Answer

1. **Cumulative constraint** — Must pathway respect budget limits?
2. **Shape** — Linear? Exponential? Affects feasibility.
3. **Initial conditions** — Start from actual emissions or adjusted baseline?
4. **Historical period** — If `first_allocation_year` is in the past, past emissions are subtracted from the cumulative budget. Regions with large historical emissions may have negative remaining budgets.

### Building Blocks

| Element                       | Function                                      | Effect                                         |
| ----------------------------- | --------------------------------------------- | ---------------------------------------------- |
| Budget-preserving convergence | `cumulative_per_capita_convergence()`         | Gradual transition with cumulative constraint  |
| Immediate allocation          | `equal_per_capita()`, `per_capita_adjusted()` | Fair shares immediately, no gradual transition |
| Convergence parameters        | `first_allocation_year`, `convergence_year`   | Control transition timing                      |

!!! note "Pathways and remaining allocations"

    For pathways, `first_allocation_year` works like `allocation_year` for budgets: if set in the past, emissions from that year to present are subtracted from the cumulative budget. A region whose remaining budget is negative cannot follow a standard declining trajectory—the pathway must account for this overshoot.

**See also**: [Convergence Mechanism](allocations.md#convergence-mechanism-pathways-only)

<!-- REFERENCE: cumulative_per_capita_convergence() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->

---

## Common Principle Combinations

The following examples illustrate how principles combine in practice. Each configuration reflects specific value judgments—they are not recommendations, but transparent demonstrations of how different ethical positions translate to allocation configurations.

**Note:** The configurations below demonstrate the **logic** of combining principles, not prescriptions for which combinations you should use. Your task is to identify which principles matter for your analysis, then configure accordingly.

### Example 1: Equal Per Capita (Egalitarian)

**Value judgment:** Equal entitlement to atmospheric space is the only relevant principle. Historical emissions and economic capability do not create differential obligations—all that matters is equal per capita rights today.

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

**Distributional outcome:** Countries with high population shares (India, China) receive proportionally large allocations. All countries start with their full fair share—no historical subtraction.

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

**Distributional outcome:** Industrialized countries with high cumulative emissions (US, EU, Russia) have already consumed much of their fair share—their **remaining** allocation is very small or negative. Countries with low historical emissions retain most of their fair share.

**Underlying reasoning:** The polluter pays principle is paramount. Past emissions reduce what remains of your fair share.

---

### Example 3: Balanced CBDR-RC with Subsistence Protection

**Value judgment:** Both historical responsibility and economic capability matter for differentiation, and basic needs emissions should be protected from capability assessments. This configuration operationalizes "equity" as a multidimensional concept combining polluter-pays, ability-to-pay, and subsistence protection principles.

**Configuration:**

```python
allocations = {
    "per-capita-adjusted-gini-budget": [
        {
            "allocation_year": [2000],
            "responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "income_floor": [7500],
            "preserve_allocation_year_shares": [False]
        }
    ]
}
# Run through allocation pipeline with data sources configured in conf/
# Gini adjustment is automatic when gini data source is configured
```

**What this reflects:**

- `allocation_year=2000` → Past emissions (2000-present) subtracted; moderate historical accounting
- `responsibility_weight=0.5`, `capability_weight=0.5` → Balanced approach
- `income_floor=7500` → Income below subsistence exempt from capability (GDR threshold, 2010 PPP)
- Gini data configured → Within-country inequality reduces effective capability

**Distributional outcome:** Industrialized countries with high emissions AND high GDP have smaller remaining allocations after subtracting 2000-present emissions, further reduced by capability adjustment. Least developed countries retain most of their fair share, protected by subsistence floor.

**Underlying reasoning:** Climate equity is multidimensional. Historical harm creates obligations, current wealth determines capacity, and basic needs must be met before assessing mitigation capacity.

---

### Example 4: Immediate Pathway with Capability Adjustment

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

**Contrast with convergence:** This approach allocates fair shares immediately; convergence (Example 5) gradually transitions from current to fair shares, preserving inequality during the transition period.

<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

### Example 5: Convergence with Capability Adjustment

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

**Contrast with immediate pathways:** Cumulative per capita convergence creates gradual transitions from current emissions (preserving near-term inequality) while respecting cumulative budget constraints. Immediate pathways (Example 4) allocate fair shares from the start.

---

### Example 6: Development-First (Minimal Differentiation)

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
- `income_floor=10000` → Higher than GDR threshold (7500)—broader subsistence definition
- Gini data configured → Within-country inequality affects effective capability

**Distributional outcome:** Least developed countries retain most of their remaining allocation. High-income countries have reduced remaining allocations (from subtracting 1990-present emissions), further reduced by strong capability weighting.

**Underlying reasoning:** The right to development takes precedence. Wealthy countries should lead mitigation because they have the capacity. Subsistence protection ensures development needs are met before mitigation burdens are assessed.

<!-- REFERENCE: Configuration format matches AllocationManager in src/fair_shares/library/allocations/manager.py
     Budget approaches: src/fair_shares/library/allocations/budgets/per_capita.py
     Pathway approaches: src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py
     Usage example: notebooks/301_custom_fair_share_allocation.ipynb
-->

---

### What This Tool Cannot Tell You

Fair-shares operationalizes principles -- it cannot tell you which principles to adopt. The following questions require normative judgment, and the literature contains diverse positions on each:

1. **Which principles are morally relevant?** — Should historical responsibility matter? Should capability determine obligations? These are philosophical questions about justice.

2. **Where do thresholds come from?** — Income floors, responsibility start dates, convergence years involve value judgments about development rights and transition feasibility.

3. **What happens with negative remaining allocations?** — When `allocation_year` is in the past, high historical emitters may have already exceeded their fair share—their remaining allocation is negative (carbon debt). What this means in practice (accelerated domestic mitigation, financial transfers, CDR obligations) requires political specification.

4. **Is convergence ethically acceptable?** — Convergence embeds grandfathering, rewarding past high emissions. The tool provides pure per-capita-convergence approaches for transparency, not endorsement. This is distinct from cumulative-per-capita-convergence, which starts with current per capita emissions but converges to cumulative per capita shares over time.

5. **Which temperature target?** — Allocations depend on carbon budget, which depends on temperature target (1.5°C, 2°C) and probability threshold. These are risk tolerance decisions.

**What the tool DOES provide:**

- **Operational transparency** — Given your principles, what allocations follow?
- **Sensitivity analysis** — How do results change with different parameters?
- **Replicability** — Can others reproduce your results from your stated configuration?

**The gap between principles and policy:** Fair shares allocations are **reference points** for assessing equity, not directly implementable policy. Moving from allocation to implementation requires additional specification: domestic mitigation vs. international support, cost-effectiveness, political feasibility, and more.
