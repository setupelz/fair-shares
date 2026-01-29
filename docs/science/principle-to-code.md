---
title: From Principle to Code
description: Translate climate equity principles into fair-shares configurations
search:
  boost: 2
---

## Why Principles Matter

Any allocation necessarily involves ethical choices. There is no value-neutral way to divide a constrained carbon budget—every approach embeds assumptions about what matters and who should bear costs. [Dooley 2021] explains this, explicitly rejecting the framing of "neutral" approaches: "There is no ethically neutral position in the climate context. Any form of climate action necessarily imposes burdens on some while conferring benefits on others. Value-neutral presentations place a gloss over deeply contested and irreducibly normative perspectives."

**Normative transparency** means making value judgments explicit. Fair-shares helps you operationalize the principles you choose, making your value judgments as visible and replicable as possible. This enables meaningful deliberation about principles and the formulas used to represent them.

**Key insight**: Define your principles first, then select the allocation approach that operationalizes those principles.

---

## Principles-First Workflow

Based on the Pelz et al. 2025 "entry points" framework. This workflow describes process, not what to decide.

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

### Entry Points Framework

| Step                       | What Question to Ask Yourself                                                                                                        | What It Determines                                                                                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Identify Principles** | What values define fairness in this context? Should equal entitlement, historical responsibility, and/or economic capability matter? | Which normative foundations guide the allocation. Determines whether you need adjustment parameters (responsibility/capability weights) or pure equal per capita.           |
| **2. Define Quantity**     | Am I allocating a fixed carbon budget or defining emission pathways over time? What is the policy question I'm answering?            | Whether you use budget approaches (one-time allocation) or pathway approaches (annual trajectories). Budgets answer "how much total?"; pathways answer "what trajectory?"   |
| **3. Choose Approach**     | Given my principles, which formulation operationalizes them?                                                                         | The specific allocation function and its parameters. Approach names encode key features (`adjusted` = responsibility+capability, `gini-adjusted` = subsistence protection). |
| **4. Select Indicators**   | What data sources reflect my chosen principles? Which reference year for population/emissions/GDP? Do I need Gini coefficients?      | Data inputs to allocation functions. Population and emissions are foundational; GDP and Gini enable capability and subsistence adjustments.                                 |
| **5. Communicate Results** | Can someone else replicate my allocation from my stated principles and parameters? Have I made value judgments explicit?             | Transparency and reproducibility. Prevents "black box" allocations where principles are obscured by technical complexity.                                                   |

**Key insight:** Start with principles, not approaches. Working backward from favorable allocations undermines scientific legitimacy.

**Resources:** [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/), [Approach Catalog](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/), [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/), [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)

---

## Quick Reference — Navigate to Principle Sections

Use this table to jump to detailed sections on each principle. Each section explains what it means, what questions you must answer, available building blocks, and trade-offs to consider.

| Principle                                                                                  | What It Addresses                                  |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| [Egalitarianism](#egalitarianism)                                                          | Ethical tradition grounding equal per capita       |
| [Historical Responsibility](#historical-responsibility-polluter-pays)                      | Past emissions create obligations                  |
| [Capability](#capability-ability-to-pay)                                                   | Economic capacity determines mitigation effort     |
| [CBDR-RC](#cbdr-rc-common-but-differentiated-responsibilities-and-respective-capabilities) | Differentiated obligations under UNFCCC            |
| [Subsistence Protection](#subsistence-protection)                                          | Basic needs emissions should be protected          |
| [Convergence](#convergence)                                                                | Smooth transition from current to fair share state |

**For implementation details:** See [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/) for parameter specifications and function signatures.

---

## Egalitarianism

**Egalitarianism** is the ethical tradition grounding the principle of **equal rights to the atmosphere** (also called "equal per capita").

### What It Means

The egalitarian tradition holds that each person globally has equal entitlement to atmospheric space. The atmosphere is a global commons that should be shared equally among all people. This principle of equal per capita distribution is the foundation of all approaches in fair-shares.

1. **Population reference year** - Which year's population should determine allocation? Current population? Future projections?
2. **Temporal scope** - Are you allocating a fixed cumulative budget (e.g., 1850-2050) or defining annual equal shares?
3. **Pure egalitarianism vs. adjustments** - Should equal shares be the final allocation, or should they be adjusted for other principles (responsibility, capability, subsistence)?

### Building Blocks Available

- **Equal per capita budgets** - `equal_per_capita_budget()` allocates fixed carbon budgets proportional to population share
- **Equal per capita pathways** - `equal_per_capita()` allocates annual emissions proportional to population share in each year (immediate equal shares, no convergence)
- **Cumulative per capita convergence pathways** - `cumulative_per_capita_convergence()` creates pathways that preserve cumulative per capita shares by distributing them from current emissions over time. This is budget-preserving (same cumulative total as equal per capita budget) but can lead to steep curves when starting from current emissions. **Not to be confused with `per-capita-convergence`**, which is NOT budget-preserving and includes grandfathering elements.

**See:** [Equal Rights to Atmosphere](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#equal-rights-to-atmosphere) for theory, [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/) for implementation.

<!-- REFERENCE: equal_per_capita_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: equal_per_capita() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

## Historical Responsibility (Polluter Pays)

### What It Means

Countries bear responsibility proportional to cumulative historical emissions. Those who caused the climate problem through past emissions should bear greater costs of addressing it. This principle operationalizes UNFCCC's "differentiated responsibilities" and is grounded in both corrective justice (reparations for harm) and distributive justice (equalizing undeserved benefits from fossil-fueled development).

1. **Start date** - When does responsibility begin? 1750 (full industrial history)? 1850 (data reliability)? 1990 (established scientific awareness via IPCC FAR)?
2. **Excusable ignorance** - Should pre-1990 emissions count if scientific awareness was limited? Or does the beneficiary-pays framing (equalizing undeserved benefits) avoid the ignorance objection?
3. **Subsistence exemption** - Should emissions needed for basic living standards be excluded from responsibility accounting?
4. **Compensation vs. redistribution** - Are you assigning blame for wrongful emissions (compensation) or equalizing undeserved benefits (redistribution)?
5. **Responsibility weight** - How much should historical emissions matter relative to other principles?

### Building Blocks Available

- **Allocation year / first allocation year** - Earlier years give greater weight to historical emissions by shrinking remaining budget for current/future emissions
- **Responsibility weight (`responsibility_weight`)** - In `*-adjusted` approaches (both budget and pathway), controls how much cumulative emissions reduce allocation
- **Adjusted pathways** - `per_capita_adjusted()` applies responsibility weighting to annual pathway allocations (immediate adjustment, no convergence)
- **Climate debt accounting** - Matthews (2016) methodology: debt = Σ [actual emissions - (world emissions × population fraction)]

**See:** [Polluter Pays](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#polluter-pays-historical-responsibility) for theory, [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/#allocation_year-budget-first_allocation_year-pathway) for examples.

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

## Capability (Ability to Pay)

### What It Means

Mitigation effort should be allocated according to economic capability. Those with greater resources can contribute more without threatening basic well-being. GDP-based adjustments create an inverse relationship: higher economic capacity results in smaller emission allocations (or greater mitigation obligations). This is a forward-looking principle—unlike historical responsibility, it does not depend on past actions.

1. **Capability indicator** - GDP per capita (aggregate economic capacity)? Income above development threshold (only surplus capacity counts)?
2. **Development threshold** - Should capability only count income above subsistence levels? GDR framework uses $7,500/year (2010 PPP); other thresholds possible depending on definition of "basic needs."
3. **Capability weight** - How much should economic capacity matter relative to other principles? Weight of 1.0 means only capability matters; 0.5 balances capability with responsibility; 0.0 treats all countries equally regardless of wealth.
4. **Temporal reference** - Which year's GDP determines capability? Current GDP reflects present capacity but changes annually. Historical average? Future projections?
5. **Purchasing power vs. market exchange rates** - PPP-adjusted GDP (purchasing power) or market exchange rate GDP? PPP better reflects domestic capacity; market rates better reflect international finance capacity.

### Building Blocks Available

- **Capability weight (`capability_weight`)** - In `*-adjusted` approaches (both budget and pathway), controls how much GDP reduces emission allocation
- **Adjusted pathways** - `per_capita_adjusted()` applies capability weighting to annual pathway allocations (immediate adjustment, no convergence)
- **Income floor (`income_floor`)** - In `*-gini-adjusted` approaches, exempts income below threshold from capability accounting
- **GDP per capita indicators** - World Bank data with PPP adjustment available through fair-shares data sources

**See:** [Ability to Pay](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#ability-to-pay-capability) for theory, [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/#capability_weight) for examples.

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

## CBDR-RC (Common But Differentiated Responsibilities and Respective Capabilities)

### What It Means

A cornerstone principle of the UNFCCC (1992). "Common" responsibilities acknowledge that all countries must act on climate, but these responsibilities are "differentiated" based on historical contribution to the problem and current economic capacity to address it. The Paris Agreement maintained this framework while adding "in light of different national circumstances." The ICJ Advisory Opinion (2025) confirmed these are _erga omnes_ obligations—duties owed to the international community as a whole.

1. **Balance between responsibility and capability** - How should historical emissions and economic capacity be weighted relative to each other? Equal weight? Capability dominant? Responsibility dominant?
2. **Operationalization of "circumstances"** - What national circumstances beyond R&C should differentiate obligations? Geography (climate vulnerability, renewable potential)? Development stage? Fossil fuel dependency for export revenue?
3. **Common baseline** - What does "common" responsibility mean operationally? That all start from equal per capita? That all share same temperature goal? That all commit to domestic action regardless of allocation?
4. **Legal vs. political interpretation** - CBDR-RC is legally binding under UNFCCC. How much should fair shares analysis reflect legal obligations vs. political feasibility?

### Building Blocks Available

- **`*-adjusted` approaches** - Combine responsibility and capability through weighted adjustments to per capita baseline
- **Responsibility weight + capability weight** - Independently control how much each dimension matters
- **`*-gini-adjusted` approaches** - Add subsistence protection through income floors and within-country inequality accounting
- **UNFCCC classification** - Annex I vs. Non-Annex I countries as rough proxy for differentiation (though increasingly outdated)

**See:** [CBDR-RC](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#cbdr-rc) for theory, [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/) for implementation.

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py
     Legal basis: ICJ Advisory Opinion 2025 -->

---

## Subsistence Protection

### What It Means

Not all emissions are morally equivalent. Emissions required for meeting basic needs (survival emissions) should be protected from mitigation burdens, while luxury emissions from high consumption can be restricted. Income below development thresholds should not count toward mitigation capacity. This principle has moral priority across multiple philosophical traditions—rights-based, utilitarian, contractarian, and egalitarian—yet is often excluded from quantified approaches despite being foundational to UNFCCC's right to development.

1. **Development threshold** - What income level defines subsistence vs. luxury? GDR framework uses $7,500/year (2010 PPP).
2. **Emissions vs. income protection** - Should you exempt subsistence emissions (energy for cooking, heating, basic mobility) or subsistence income (capacity to purchase any goods, including mitigation)?
3. **Within-country inequality** - Should capability account for income distribution within countries?
4. **Temporal dynamics** - As countries develop and incomes rise, subsistence protection decreases. Should allocation adjust dynamically as populations move above threshold? Or fix threshold year for predictability?

### Building Blocks Available

- **Income floor (`income_floor`)** - In `*-gini-adjusted` approaches (both budget and pathway), exempts income below threshold from capability calculations
- **Gini coefficient adjustments** - Accounts for within-country inequality in capability assessments. High Gini → effective capability lower than GDP per capita suggests.
- **Gini-adjusted pathways** - `per_capita_adjusted_gini()` applies subsistence protection to annual pathway allocations (immediate adjustment, no convergence)
- **Subsistence emissions accounting** - Can be implemented through emission floors (not currently in core library but conceptually straightforward)

**See:** [Subsistence vs. Luxury](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/#subsistence-vs-luxury-emissions) for theory, [Parameter Effects](https://setupelz.github.io/fair-shares/science/parameter-effects/#income_floor) for examples.

<!-- REFERENCE: per_capita_adjusted_gini_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted_gini() in src/fair_shares/library/allocations/pathways/per_capita.py -->

---

## Convergence

### What It Means

Convergence creates smooth pathways that gradually transition from current emissions toward fair share targets over time. This is ONE type of pathway approach—pathways can also allocate immediately to fair shares without convergence (using functions like `equal_per_capita()`, `per_capita_adjusted()`, or `per_capita_adjusted_gini()`).

**Important distinction:** fair-shares includes two types of convergence:

1. **Cumulative per capita convergence** (`cumulative-per-capita-convergence*`) - Budget-preserving fair share approaches that distribute equal cumulative per capita shares from current emissions. These are constrained to preserve cumulative totals and are considered fair share approaches.

2. **Per capita convergence** (`per-capita-convergence`) - NOT budget-preserving, incorporates grandfathering elements by privileging current emission patterns. This is NOT considered a fair share approach and is included for comparison only.

**Key questions when using convergence approaches:**

1. **Pathway shape** - Linear convergence? Exponential decline? Smooth vs. sharp transitions affect economic and political feasibility.
2. **Cumulative constraint** - Should the pathway respect cumulative budget limits (i.e. reflect a fair share)?
3. **Initial conditions** - Should pathway start from current actual emissions, or from an adjusted baseline?

### Building Blocks Available

- **Convergence pathways** - `cumulative_per_capita_convergence()` creates gradual transition pathways with cumulative budget constraints
- **Immediate pathways (non-convergence)** - `equal_per_capita()`, `per_capita_adjusted()`, `per_capita_adjusted_gini()` allocate to fair shares immediately in each year without gradual transition
- **Convergence parameters** - `first_allocation_year`, `convergence_year`, adjustment weights control convergence trajectory
- **Adjusted convergence variants** - `*-adjusted` and `*-gini-adjusted` versions available for convergence pathways, applying responsibility/capability logic to transition trajectories

**See:** [Convergence Mechanism](https://setupelz.github.io/fair-shares/science/allocations/#convergence-mechanism-pathways-only) for details.

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
- `allocation_year=2020` → Allocation based on 2020 population shares
- `preserve_allocation_year_shares=False` → Shares adjust with population changes

**Distributional outcome:** Countries with high population shares (India, China) receive proportionally large allocations. Historical emissions and GDP do not affect shares.

**Ethical stance:** The atmosphere is a global commons to be shared equally among all living persons.

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

- `allocation_year=1990` → Cumulative emissions from 1990-2020 count heavily
- `responsibility_weight=1.0` → Full reduction in allocation for historical excess
- `capability_weight=0.0` → GDP does not affect allocation

**Distributional outcome:** Industrialized countries with high cumulative emissions (US, EU, Russia) receive very small or negative allocations. Countries with low historical emissions receive allocations above current emissions.

**Ethical stance:** The polluter pays principle is paramount. Those who benefited from fossil-fueled development owe restitution through reduced future allocations.

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

- `allocation_year=2000` → Moderate historical accounting (post-Kyoto)
- `responsibility_weight=0.5`, `capability_weight=0.5` → Balanced approach
- `income_floor=7500` → Income below subsistence exempt from capability (GDR threshold, 2010 PPP)
- Gini data configured → Within-country inequality reduces effective capability

**Distributional outcome:** Industrialized countries with high emissions AND high GDP (US, EU) face strong reductions. Least developed countries receive allocations above current emissions, protected by subsistence floor.

**Ethical stance:** Climate equity is multidimensional. Historical harm creates obligations, current wealth determines capacity, and basic needs must be met before assessing mitigation capacity.

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

**Ethical stance:** Fair shares should apply immediately, not phased in over time. Annual allocations respect both historical responsibility and current capacity without rewarding past excess through convergence.

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

**Ethical stance:** Cumulative per capita shares are the fair target, but immediate redistribution is impractical. Transition pathways balance long-term equity with near-term feasibility while preserving cumulative budgets.

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

- `allocation_year=1990` → Responsibility only for post-IPCC emissions
- `responsibility_weight=0.2`, `capability_weight=0.8` → Capability matters more than history
- `income_floor=10000` → Higher than GDR threshold (7500)—broader subsistence definition
- Gini data configured → Within-country inequality affects effective capability

**Distributional outcome:** Least developed countries receive allocations well above current emissions. High-income countries face strong capability reductions but light responsibility penalties.

**Ethical stance:** The right to development takes precedence. Wealthy countries should lead mitigation because they have the capacity. Subsistence protection ensures development needs are met before mitigation burdens are assessed.

<!-- REFERENCE: Configuration format matches AllocationManager in src/fair_shares/library/allocations/manager.py
     Budget approaches: src/fair_shares/library/allocations/budgets/per_capita.py
     Pathway approaches: src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py
     Usage example: notebooks/301_custom_fair_share_allocation.ipynb
-->

---

### What This Tool Cannot Tell You

Fair-shares operationalizes principles—it cannot tell you which principles matter. The following questions require normative judgment:

1. **Which principles are morally relevant?** — Should historical responsibility matter? Should capability determine obligations? These are philosophical questions about justice.

2. **Where do thresholds come from?** — Income floors, responsibility start dates, convergence years involve value judgments about development rights and transition feasibility.

3. **What happens with negative allocations?** — Many configurations result in soon-to-be negative allocations (carbon debts) for high historical emitters. Implementation mechanism (domestic mitigation vs. financial transfers) requires political specification.

4. **Is convergence ethically acceptable?** — Convergence embeds grandfathering, rewarding past high emissions. The tool provides pure per-capita-convergence approaches for transparency, not endorsement. This is distinct from cumulative-per-capita-convergence, which starts with current per capita emissions but converges to cumulative per capita shares over time.

5. **Which temperature target?** — Allocations depend on carbon budget, which depends on temperature target (1.5°C, 2°C) and probability threshold. These are risk tolerance decisions.

**What the tool DOES provide:**

- **Operational transparency** — Given your principles, what allocations follow?
- **Sensitivity analysis** — How do results change with different parameters?
- **Replicability** — Can others reproduce your results from your stated configuration?

**The gap between principles and policy:** Fair shares allocations are **reference points** for assessing equity, not directly implementable policy. Moving from allocation to implementation requires additional specification: domestic mitigation vs. international support, cost-effectiveness, political feasibility, and more.
