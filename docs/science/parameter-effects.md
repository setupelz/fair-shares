---
title: Parameter Effects Reference
description: How allocation parameters affect country shares with real examples
icon: material/tune-variant
search:
  boost: 2
---

# Parameter Effects Reference

This guide shows how key parameters affect allocation outcomes using real data for representative countries:

- **USA**: High historical emissions, high GDP per capita
- **India**: Large population, lower historical emissions per capita
- **Germany**: Medium population, high historical emissions and GDP per capita

**Data and version:** fair-shares 0.3.0 with the default data sources. Emissions are fossil and industry CO2 (`co2-ffi`) from PRIMAP-hist v2.8 (`primap-202609`, to 2025). Population is UN/OWID with the UN WPP 2024 median projection (`un-owid-2025`). GDP is World Bank WDI GDP PPP in constant 2021 international dollars (`wdi-2025`, to 2025). Gini is the World Bank WDI Gini index (`wdi-2025`). The budget is `lamboll_2023` 1.5°C at 50% probability, rebased to 2020: 335.6 GtCO2. The allocation covers 177 countries and one rest-of-world group.

**Reproducing examples:** `notebooks/docs/parameter_effects_examples.py` produces every number on this page. Run `uv run python notebooks/docs/parameter_effects_examples.py` from the repository root.

---

## allocation_year (Budget) / first_allocation_year (Pathway)

**Effect:** Earlier allocation years account for more historical emissions in the cumulative budget calculation, dramatically reducing the remaining allocation for high historical emitters.

**Direction:**

- Earlier years → More cumulative emissions accounted for → High emitters may go negative
- Later years → Less history considered → Allocations closer to current population shares

**Example:** `equal-per-capita-budget` with varying `allocation_year`, showing remaining budget from 2020

| Country | allocation_year=2020 | allocation_year=1990 | allocation_year=1900 |
| ------- | -------------------- | -------------------- | -------------------- |
| USA     | +13.5 GtCO2          | -118.2 GtCO2         | -324.6 GtCO2         |
| India   | +56.1 GtCO2          | +160.2 GtCO2         | +274.7 GtCO2         |
| Germany | +2.7 GtCO2           | -15.6 GtCO2          | -65.2 GtCO2          |

_Example uses the `lamboll_2023` 1.5°C budget (50% probability). Remaining budget = (cumulative population share × global budget from allocation_year) minus actual emissions from allocation_year to 2020._

**Key insight:** The `allocation_year` is a highly consequential normative choice. With `allocation_year=2020`, the calculation counts no historical emissions and all three countries have positive remaining budgets. With `allocation_year=1990`, the USA and Germany have already used more than their equal per capita share and their remaining budgets are negative. Moving the start to 1900 widens the gap: the USA falls to -324.6 GtCO2 and India rises to +274.7 GtCO2.

<!-- REFERENCE: equal_per_capita_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

**Mathematical detail:** See [equal_per_capita_budget API](../api/allocations/budgets.md#equal_per_capita_budget)

**Theoretical basis:** See [Allocation Approaches](allocations.md) · [Historical Responsibility](allocations.md#historical-responsibility)

---

## pre_allocation_responsibility_weight and capability_weight

**Effect:** These two weights jointly control CBDR-RC adjustments. They are **relative**: only their ratio matters, not their individual values. `(0.5, 0.5)` is identical to `(1.0, 1.0)` or `(0.3, 0.3)`. When one weight is 0, the other becomes the sole adjustment regardless of its value: `(0.0, 0.3)` is identical to `(0.0, 1.0)`. When both are 0, no adjustment is applied (pure equal per capita). See [Weight Normalization](allocations.md#weight-normalization).

`pre_allocation_responsibility_weight` activates per-capita rescaling based on cumulative emissions in [`pre_allocation_responsibility_year`, `allocation_year`). By default the metric is absolute cumulative emissions; `pre_allocation_responsibility_per_capita=True` divides them by cumulative population. This is a **separate mechanism** from setting an early `allocation_year`: rescaling is multiplicative and always produces positive allocations if `allocation_year` is the present, whereas cumulative accounting can produce negative allocations (see [comparison table](#if-you-want-x-set-y-guide) below).

`capability_weight` activates capability (ability to pay) adjustments based on GDP per capita from the allocation year onwards. Without `capability_reference_year`, capability data before the allocation year is not used; with it, a single snapshot year is used, and that year may precede or follow the allocation year. When the allocation window extends past the last observed GDP year (default `wdi-2025` ends at 2025), the per-capita budget and pathway primitives forward-fill GDP per capita from the last observed year to cover the rest of the window, holding the cross-country capability ratios of that last year constant for every subsequent year. To use different post-observation capability dynamics (SSP2 projections, custom growth assumptions, or a future-extended WDI release), extend the input `gdp_ts` time series before calling the allocation function.

**Direction:**

- Both weights `0.0` → No adjustment (equal per capita)
- One weight `> 0`, other `= 0` → That adjustment is the sole factor (the specific non-zero value is irrelevant)
- Both non-zero → Balanced by their ratio (e.g., 0.7:0.3 = 70% pre-allocation responsibility, 30% capability)

### Each adjustment in isolation

**Pre-allocation responsibility only** (`per-capita-adjusted-budget`, `capability_weight=0.0`):

| Country | No adjustment (both=0) | Responsibility only, absolute (default) | Responsibility only, per capita |
| ------- | ---------------------- | --------------------------------------- | ------------------------------- |
| USA     | 4.0%                   | 0.5%                                    | 0.3%                            |
| India   | 16.7%                  | 2.7%                                    | 6.5%                            |
| Germany | 0.8%                   | 0.1%                                    | 0.1%                            |

_Uses `allocation_year=2020`, `pre_allocation_responsibility_year=1990`. The last column sets `pre_allocation_responsibility_per_capita=True`._

On the default absolute metric, the responsibility adjustment cuts all three shares sharply: USA 4.0% to 0.5%, India 16.7% to 2.7%, Germany 0.8% to 0.1%. India loses the most percentage points because the absolute metric compares total 1990-2019 emissions and India's total is large. The per-capita metric divides by population, so India keeps 6.5% and the USA falls further to 0.3%. In both modes the freed share goes to countries with low cumulative emissions outside this three-country excerpt. The choice between absolute and per-capita responsibility is a normative choice; see [Per Capita vs Absolute Mode](allocations.md#per-capita-vs-absolute-mode).

**Capability only** (`per-capita-adjusted-budget`, `pre_allocation_responsibility_weight=0.0`):

| Country | No adjustment (both=0) | Capability only |
| ------- | ---------------------- | --------------- |
| USA     | 4.0%                   | 0.8%            |
| India   | 16.7%                  | 12.6%           |
| Germany | 0.8%                   | 0.2%            |

_Uses `allocation_year=2020`._

The capability adjustment alone is almost as strong as the responsibility adjustment for high-income countries. It cuts the USA from 4.0% to 0.8% and Germany from 0.8% to 0.2%. India also falls, from 16.7% to 12.6%: its GDP per capita is below the median, but the adjustment moves share to the lowest-income countries.

### Varying the ratio (both weights non-zero)

The ratio only matters when both weights are non-zero. Here the specific values matter because they determine how much each adjustment contributes:

| Country | 100% pre-alloc resp. (1.0:0.0) | 70:30 | 50:50 | 30:70 | 100% capability (0.0:1.0) |
| ------- | ------------------------------ | ----- | ----- | ----- | ------------------------- |
| USA     | 0.5%                           | 0.7%  | 0.7%  | 0.8%  | 0.8%                      |
| India   | 2.7%                           | 4.9%  | 6.8%  | 8.9%  | 12.6%                     |
| Germany | 0.1%                           | 0.2%  | 0.2%  | 0.2%  | 0.2%                      |

_Uses `allocation_year=2020`, `pre_allocation_responsibility_year=1990`, absolute responsibility._

The ratio blends smoothly between the two pure cases. For the USA and Germany both adjustments give similar shares, so the ratio changes little. For India the ratio decides the result: its share rises from 2.7% to 12.6% as the weight moves from responsibility to capability.

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

**Mathematical detail:** See [per_capita_adjusted_budget API](../api/allocations/budgets.md#per_capita_adjusted_budget)

**Theoretical basis:** See [Historical Responsibility](allocations.md#historical-responsibility) · [Weight Normalization](allocations.md#weight-normalization)

---

## capability_reference_year

**Effect:** Freezes the capability metric at a single year's GDP (per capita)
snapshot instead of computing it across the allocation window. Available on
budget and pathway approaches with identical semantics.

- **Unset (default):** budget approaches compute capability year-by-year
  across the cumulative window; pathway approaches use the cumulative
  lifetime GDP-per-capita metric in dynamic mode and the first-allocation-year
  value in preserved mode. Values past the last observed GDP year are
  forward-filled.
- **Set:** the snapshot year's metric is broadcast across the window. A year
  before the allocation window is sourced from the unfiltered inputs; a year
  beyond the last observed GDP year falls back to the last observed column
  with a warning; a year outside the data range raises. On the Gini-adjusted
  approaches the Gini adjustment applies in all three cases; which input the
  snapshot is read from does not change the capability definition.
- **Start years before the GDP series:** with a reference year set, the budget
  approaches need GDP at that year only. `allocation_year` can then be earlier
  than the first GDP year, down to 1850. With no reference year, an allocation
  year before the GDP series raises an error.

**When to use:** replicating studies that fix capability at a reference year
(e.g. a single-year GDP-per-capita indicator), or holding the capability
ranking constant across the allocation horizon. Year-by-year capability
responds to projected convergence in GDP; a snapshot does not.

**Interaction with auto-derivation:** composite (all-GHG) runs derive the
non-CO₂ pathway configs from the budget configs; `capability_reference_year`
passes through, so both gas components apply the same snapshot.

---

## income_floor

**Effect:** Sets a development threshold for capability calculations, adapted from the Greenhouse Development Rights framework ([Baer 2009](https://doi.org/10.1080/13668790903195495); [Baer 2013](https://doi.org/10.1002/wcc.201)). Note that GDR was designed for burden-sharing; fair-shares uses its capability metric in an entitlement allocation context. For every person, only their income **above** this threshold counts towards "capability" or "ability to pay". Income up to the threshold is considered necessary for basic human development.

**Default:** `0.0` on every Gini-adjusted approach (budget and pathway alike): all income counts toward capability unless a threshold is chosen explicitly. Applying the GDR threshold is a normative decision, so it is passed rather than assumed.

**Direction:**

- `floor=0` → All income counts toward capability (no development protection)
- `floor=7500` → 7,500 per person per year, in the units of the GDP series. [Baer 2013](https://doi.org/10.1002/wcc.201) used this value as the GDR development threshold on a 2005 price base and raised it to 8,500 on a 2010 base.
- `floor=15000` → 15,000 per person per year, in the units of the GDP series, a higher subsistence threshold

The floor must be expressed in the price base of the GDP series passed in. The default GDP source is in constant 2021 international dollars, so a threshold from another price year needs converting first.

A floor lowers measured capability in every country. Shares depend on capability relative to other countries, so the floor moves share toward countries where most people earn below the threshold. The Gini coefficient sets how much income lies above the floor; at `floor=0` the Gini adjustment has no effect. Capability never falls below 20% of GDP, because `max_gini_adjustment` defaults to 0.8 ([Maximum Gini Adjustment](allocations.md#maximum-gini-adjustment)).

**Example:** `per-capita-adjusted-gini-budget` varying `income_floor` (with `capability_weight=1.0`, `pre_allocation_responsibility_weight=0.0`: capability is the sole adjustment, so its specific value is arbitrary; 1.0 is used for clarity)

| Country | floor=0 | floor=7500 | floor=15000 |
| ------- | ------- | ---------- | ----------- |
| USA     | 0.8%    | 0.3%       | 0.4%        |
| India   | 12.6%   | 9.9%       | 13.3%       |
| Germany | 0.2%    | 0.1%       | 0.1%        |

_Example uses `allocation_year=2020`, Gini-adjusted capability calculation, default `max_gini_adjustment=0.8`. The `floor=0` column equals the capability-only column above._

The capability metric behind the table, for the last GDP year (2025):

| Floor       | India capability as share of GDP | Median capability per person | India capability per person / median | Countries and groups held at the 20% cap |
| ----------- | -------------------------------- | ---------------------------- | ------------------------------------ | ---------------------------------------- |
| floor=0     | 100%                             | 17,255                       | 0.58                                 | 0 of 178                                 |
| floor=7500  | 32%                              | 10,188                       | 0.31                                 | 43 of 178                                |
| floor=15000 | 20%                              | 5,277                        | 0.38                                 | 69 of 178                                |

**Key insight:** The income floor has a large effect, and India's share falls and then rises as the floor increases. A floor of 7,500 cuts the USA from 0.8% to 0.3% and India from 12.6% to 9.9%, because share moves to the lowest-income countries. At 15,000 the 20% cap holds 69 of 178 countries and groups, India among them, while the median capability keeps falling. India's capability relative to the median rises from 0.31 to 0.38, and its share returns to 13.3%. Results with a high floor therefore depend on `max_gini_adjustment` as much as on the floor itself. Report both parameters together.

<!-- REFERENCE: per_capita_adjusted_gini_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

**Mathematical detail:** See [per_capita_adjusted_gini_budget API](../api/allocations/budgets.md#per_capita_adjusted_gini_budget)

**Theoretical basis:** See [Gini Adjustment](allocations.md#gini-adjustment)

---

## historical_discount_rate

<!-- REFERENCE: calculate_responsibility_adjustment_data() in src/fair_shares/library/utils/math/adjustments.py -->

**Effect:** Weights earlier historical emissions less than recent ones when computing pre-allocation responsibility adjustments. Available on all `*-adjusted` families -- `per-capita-adjusted`, `per-capita-adjusted-gini`, `cumulative-per-capita-convergence-adjusted`, and `cumulative-per-capita-convergence-gini-adjusted` (where `pre_allocation_responsibility_weight > 0`) -- not part of equal-per-capita accounting.

**Direction:**

- `rate=0.0` (default) → All historical emissions weighted equally (standard approach)
- `rate=0.005` → 1850 emissions at ~43% weight relative to 2020
- `rate=0.01` → Stronger discounting; 1850 emissions at ~18% weight

Higher rates reduce the influence of early-industrialisation emissions. Countries that industrialised early (UK, Germany, USA) benefit most from discounting. Countries whose emissions grew recently (China, India) see relatively smaller changes because their emission mass is concentrated in recent decades where discount weights are near 1.0.

**Key insight:** This parameter is contested in the literature. The physical argument: natural carbon sinks remove CO2 over time, so older emissions contribute less to current concentrations [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7); [Van Den Berg 2020](https://doi.org/10.1007/s10584-019-02368-y). The moral counterargument: responsibility for harm does not decay with time, and discounting systematically benefits the countries most responsible for cumulative warming [Meyer 2013](https://chicagounbound.uchicago.edu/cjil/vol13/iss2/15/); [Shue 2015](https://doi.org/10.1515/mopp-2013-0009); [Caney 2009](https://doi.org/10.1080/17449620903110300). The choice of any rate above 0.0 is a normative decision, not a technical one.

**Mathematical detail:** See [Historical Emissions Discounting](allocations.md#historical-emissions-discounting)

**Theoretical basis:** See [Allocation Approaches](allocations.md) · [Historical Responsibility](allocations.md#historical-responsibility)

---

## strict (Convergence Only)

<!-- REFERENCE: find_minimum_convergence_speed() in src/fair_shares/library/utils/math/convergence.py -->

**Effect:** Controls whether infeasible convergence targets raise an error or produce approximate results with warnings. Infeasibility occurs when a country's current emissions are so far from its target share that no valid convergence path exists within the allowed speed range: the solver would need negative or >100% long-run shares, which are physically meaningless.

**Direction:**

- `strict=True` (default) → Error on infeasibility. Use during research to catch impossible configurations early.
- `strict=False` → Clips infeasible long-run shares to [0, 1], redistributes proportionally, reports per-country deviation ratios. Use during exploration to get results even when some targets are unreachable.

**When infeasibility happens:**

Aggressive equity configurations are the usual trigger. The more you push high-emitting countries toward small targets, via strong pre-allocation responsibility weighting, early allocation years, tight budgets, or combinations, the more likely the solver hits a mathematical wall. Short time horizons (few years between `first_allocation_year` and end of pathway) and low `max_convergence_speed` values also increase the chance.

**Example:** `cumulative-per-capita-convergence-adjusted` from 2020, with `lamboll_2023` budgets turned into world pathways by the default exponential-decay generator

| Budget | Weights (resp.:cap.) | `strict=True` | `strict=False` ratio: USA | India | Germany | Countries above target | Countries below target |
| ------ | -------------------- | ------------- | ------------------------- | ----- | ------- | ---------------------- | ---------------------- |
| 1.5°C, 50% | 0.0:0.0 | feasible | 1.00 | 1.00 | 1.00 | 0 | 0 |
| 2°C, 66%   | 0.5:0.5 | feasible | 1.00 | 1.00 | 1.00 | 0 | 0 |
| 1.5°C, 50% | 0.5:0.5 | raises `AllocationError` | 1.90 | 0.98 | 1.10 | 14 | 163 |

_Ratios show achieved/target cumulative share. Countries above 1.0 keep more than their target because their current emissions cannot fall fast enough; every other country is scaled down to keep the world total._

**Key insight:** Equity adjustments on a tight budget are the usual trigger. The 1.5°C budget is feasible without adjustments and the 0.5:0.5 weights are feasible on the 2°C budget, but the same weights on the 1.5°C budget are infeasible. With `strict=False`, 14 high emitters overshoot their targets (the USA reaches 1.90 times its target, Germany 1.10) and 163 countries and groups receive 2% less than their targets. Treat `strict=False` as a diagnostic. Ratios well above 1.0 show that the configuration asks for a faster transition than the convergence mechanism can deliver; relax the weights, use a larger budget, or extend the time horizon.

**Mathematical detail:** See [Strict Parameter](allocations.md#strict-parameter-convergence-only)

---

## max_deviation_sigma

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

**Effect:** Limits how far any country's adjusted allocation can deviate from equal per capita, measured in standard deviations. Only relevant when applying scaling adjustments (pre-allocation responsibility, capability, or combinations). Without this constraint, extreme adjustment values can produce outlier allocations.

**Direction:**

- `None` (default) → No constraint; adjustments applied without limit
- `2.0` → Allocations clipped to within ±2 standard deviations of equal per capita
- Lower values → Tighter constraint, allocations closer to equal per capita

**Key insight:** This is an opt-in tail-compression lever. The default is `None` (no constraint applied). When you set a value, allocations for countries in the tails of the distribution are clipped inward -- disclose the choice explicitly, since it materially affects results for the most and least adjusted countries.

**Practical guidance:**

| sigma | Effect | Use when |
|-------|--------|----------|
| 1.0 | Tight -- allocations stay close to equal per capita | Testing sensitivity, or when equity adjustments should be modest |
| 2.0 | Moderate -- allows substantial deviation but compresses extremes | General use when you want a safety net against outlier adjustments |
| 3.0 | Loose -- nearly unconstrained for most distributions | Only catching truly extreme outliers |
| None | No constraint (default) | When you trust the adjustment parameters to produce reasonable results |

Examples and tests use `max_deviation_sigma=2.0` for illustration; the default is `None` (unconstrained).

**Mathematical detail:** See [Maximum Deviation Constraint](allocations.md#maximum-deviation-constraint)

---

## preserve_allocation_year_shares / preserve_first_allocation_year_shares

<!-- REFERENCE: equal_per_capita_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: equal_per_capita() in src/fair_shares/library/allocations/pathways/per_capita.py -->

**Effect:** Controls whether population (and adjustment) shares are recalculated dynamically over time or frozen at the allocation year. Budget approaches use `preserve_allocation_year_shares`; pathway approaches use `preserve_first_allocation_year_shares`.

**Direction:**

- `False` (default) → Dynamic: shares update with changing population and GDP over time
- `True` → Preserved: shares fixed at allocation year values, constant across all periods

**Key insight:** The default (dynamic) accounts for demographic change: countries with growing populations receive increasing shares over time. Preserved mode treats the allocation year as a snapshot: useful when you want to isolate the effect of equity parameters from demographic projections, or when population projections are uncertain. For budget approaches, dynamic mode uses cumulative population from the allocation year; preserved mode uses the single-year population at the allocation year.

**Mathematical detail:** See [Dynamic vs Preserved Shares](allocations.md#dynamic-vs-preserved-shares)

---

## convergence_method (Convergence Only)

<!-- REFERENCE: cumulative_per_capita_convergence() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->

**Effect:** Selects the solver for computing convergence pathways. Two methods produce different transition dynamics while respecting the same cumulative budget constraints.

**Direction:**

- `"minimum-speed"` (default) → Finds the minimum exponential convergence speed that satisfies cumulative constraints. Produces the smoothest feasible transition.
- `"sine-deviation"` → Iterative sine-shaped deviation from a per-capita-convergence baseline [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7). Front-loads the adjustment toward cumulative budget targets. Requires `convergence_year`.

**Key insight:** `minimum-speed` is the workhorse: it requires no additional parameters and finds the least disruptive transition path. `sine-deviation` is more aggressive near-term: it front-loads adjustments using a sine-shaped correction, producing steeper initial changes but converging by `convergence_year`. Use `sine-deviation` when the policy question is specifically about accelerated near-term transitions.

**Mathematical detail:** See [Convergence Method](allocations.md#convergence-method)

---

## max_convergence_speed (Convergence Only)

<!-- REFERENCE: cumulative_per_capita_convergence() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->

**Effect:** Upper bound on the exponential convergence speed parameter. Controls how fast allocations can transition from current emission shares to target shares in a single year.

**Direction:**

- `0.9` (default) → Allows up to 90% of the remaining gap to close per year
- Lower values → Forces slower, more gradual transitions but increases the risk of infeasibility
- Higher values (approaching 1.0) → Allows near-instantaneous convergence

**Key insight:** This parameter is rarely tuned directly. The default of 0.9 permits fast transitions when needed while keeping the convergence mathematically stable. Lowering it constrains the solver: if the cumulative target requires rapid transition and `max_convergence_speed` is too low, the solver cannot find a feasible path. When `strict=True`, this manifests as an error; when `strict=False`, as achieved/target ratios away from 1.0.

**Mathematical detail:** See [Convergence Mechanism](allocations.md#convergence-mechanism-pathways-only)

---

## Understanding Weights vs Exponents

Two distinct parameter types control adjustments. They are often confused:

| Parameter                 | Default | Meaning of default               | What it controls                                           |
| ------------------------- | ------- | -------------------------------- | ---------------------------------------------------------- |
| `pre_allocation_responsibility_weight`   | 0.0     | Both at 0.0 → no adjustments     | Relative importance of responsibility vs capability        |
| `capability_weight`       | 0.0     | Both at 0.0 → no adjustments     | Relative importance of capability vs responsibility        |
| `pre_allocation_responsibility_exponent` | 1.0     | **Standard** proportional effect | Shape of the responsibility function (1=linear, 2=squared) |
| `capability_exponent`     | 1.0     | **Standard** proportional effect | Shape of the capability function (1=linear, 2=squared)     |

**Key distinction:** Weights are **relative**: only the ratio between `pre_allocation_responsibility_weight` and `capability_weight` matters. Setting either to any non-zero value (with the other at zero) gives that adjustment 100% of the weighting. Exponents control the functional _shape_ of each adjustment independently.

**Why exponents matter:** At 1.0 (default), the adjustment factor is `1 / asinh(x / median(x))` for the metric `x`. At values above 1.0, the adjustment becomes convex: high emitters or wealthy countries are penalised disproportionately more, operationalising the argument that marginal emissions or income matter more at higher levels. The default of 1.0 is the most transparent choice; deviations require explicit normative justification. See [Adjustment Shape Parameters](allocations.md#adjustment-shape-parameters) for details on exponents, functional forms, and per-capita vs absolute modes.

### "If you want X, set Y" guide

Two **independent** mechanisms for historical responsibility exist. They can be used separately or together:

| Mechanism | Parameter | How it works |
| --------- | --------- | ------------ |
| **Cumulative accounting** | Early `allocation_year` (e.g. 1990, 1850) | Cumulative population from that year determines shares; negative allocations are a mathematical consequence when shares are applied to budgets |
| **Relative rescaling** | `pre_allocation_responsibility_weight` + `pre_allocation_responsibility_year` | Multiplicative rescaling of per-capita shares over [`pre_allocation_responsibility_year`, `allocation_year`); always produces positive allocations if `allocation_year` is the present |

The rescaling mechanism requires `pre_allocation_responsibility_year < allocation_year`: when they are equal, the window is empty and the weight has no effect.

| Goal                                   | Parameters                                               |
| -------------------------------------- | -------------------------------------------------------- |
| Pure equal per capita (no adjustments) | `pre_allocation_responsibility_weight=0.0, capability_weight=0.0`       |
| Historical responsibility via cumulative accounting | Early `allocation_year` (e.g. 1990), no weight needed |
| Historical responsibility via rescaling | `pre_allocation_responsibility_weight=1.0`, `pre_allocation_responsibility_year` < `allocation_year` |
| Both mechanisms combined               | Early `allocation_year` + `pre_allocation_responsibility_weight > 0` + `pre_allocation_responsibility_year` < `allocation_year` |
| Balanced CBDR-RC (rescaling + capability) | `pre_allocation_responsibility_weight=0.5, capability_weight=0.5`       |
| CBDR-RC with 0.7:0.3 responsibility-to-capability ratio | `pre_allocation_responsibility_weight=0.7, capability_weight=0.3`       |
| Ability to pay only                    | `pre_allocation_responsibility_weight=0.0, capability_weight=1.0`       |
| Stronger-than-linear rescaling         | `pre_allocation_responsibility_weight=1.0, pre_allocation_responsibility_exponent=2.0` |

---

## Combining Parameters

Real allocation approaches combine multiple principles. Common patterns:

### Pre-Allocation Responsibility Scaling + Capability

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

```python
per_capita_adjusted_budget(
    allocation_year=2020,
    pre_allocation_responsibility_weight=0.5,
    capability_weight=0.5,
    pre_allocation_responsibility_year=1990,  # window: [1990, 2020)
)
```

Rescales per-capita shares using both 1990-2019 cumulative emissions (absolute by default) and GDP per capita from 2020 onwards, weighted equally (0.5:0.5 ratio, identical to 1.0:1.0). No cumulative accounting of past emissions in the budget (allocation starts at 2020). Note the temporal asymmetry: pre-allocation responsibility covers the window prior to the allocation year, capability applies from it onwards.

### Both Responsibility Mechanisms (Cumulative Accounting + Rescaling)

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

```python
per_capita_adjusted_budget(
    allocation_year=1990,
    pre_allocation_responsibility_weight=1.0,
    capability_weight=0.0,
    pre_allocation_responsibility_year=1850,  # window: [1850, 1990)
)
```

Cumulative population from 1990 determines shares (via `allocation_year=1990`). Cumulative emissions from 1850-1989 (absolute by default) rescale those shares (via `pre_allocation_responsibility_weight=1.0`). Remaining budgets are computed as a post-processing step by the analyst.

### Capability with Development Threshold

<!-- REFERENCE: per_capita_adjusted_gini_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->

```python
per_capita_adjusted_gini_budget(
    pre_allocation_responsibility_weight=0.0,
    capability_weight=1.0,
    income_floor=7500,  # ~$20/day
)
```

Adjusts for wealth while protecting subsistence needs.

---

## Understanding Parameter Interactions

### Parameter Sensitivity Ranking

Based on the examples (USA, India, Germany, `allocation_year=2020`):

1. **`allocation_year`** (largest absolute effect): cumulative accounting moves remaining budgets by hundreds of GtCO2 and turns them negative (USA: +13.5 to -324.6 GtCO2).
2. **`pre_allocation_responsibility_weight`**: switching it on changes shares by 0.7 to 14.0 percentage points (Germany -0.7, USA -3.5, India -14.0). The absolute or per-capita metric decides how much India loses.
3. **`capability_weight`**: switching it on changes shares by 0.6 to 4.1 percentage points (Germany -0.6, USA -3.2, India -4.1).
4. **`income_floor`**: up to 2.7 percentage points (India -2.7 at 7,500, +0.7 at 15,000). The direction depends on `max_gini_adjustment`.

### Multi-Parameter Trade-offs

When combining adjustments:

- High pre-allocation responsibility weight + high capability weight → Very low allocations for developed countries
- Capability-dominant weighting (e.g., 0.2:0.8) → Allocations shift primarily by GDP per capita
- Pre-allocation responsibility alone → "Polluter pays" framing
- Capability alone → "Common but differentiated" without historical accountability

---

## See Also

- [Principle to Code](principle-to-code.md) - How equity principles map to parameters
- [Approach Catalog](../user-guide/approach-catalog.md) - Pre-configured combinations for common scenarios
- [API Documentation](../api/allocations/budgets.md) - Mathematical definitions and validation rules
