---
title: Allocation Approaches
description: Design and parameters for budget and pathway allocation approaches in fair-shares
search:
  boost: 2
---

# Allocation Approaches

Design and parameters for allocation approaches in fair-shares.

For underlying principles, see [From Principle to Code](principle-to-code.md). For mathematical formulations, see the API Reference for [budgets](https://setupelz.github.io/fair-shares/api/allocations/budgets/) and [pathways](https://setupelz.github.io/fair-shares/api/allocations/pathways/).

---

## Overview

Allocation approaches distribute emissions among countries based on equity principles. fair-shares implements two categories:

| Category    | Question Answered                                                             | Output                          |
| ----------- | ----------------------------------------------------------------------------- | ------------------------------- |
| **Budget**  | What is each country's fair share of a cumulative remaining emissions budget? | Single allocation per country   |
| **Pathway** | What is each country's fair share of emissions each future year?              | Time-varying annual allocations |

All allocation approaches ensure shares sum to 1 in each year and ensure complete global coverage.

!!! warning "Value neutrality is impossible in equity analysis"

    No allocation approach is normatively neutral. Every choice about base year, indicator, weighting, or approach inclusion reflects value judgments about fairness [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8); [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7). Research on IAM methodology and effort-sharing has repeatedly documented how "neutral" defaults systematically favour wealthy nations [Klinsky 2018](https://doi.org/10.1098/rsta.2016.0461); [Winkler 2020](https://doi.org/10.1080/14693062.2019.1680337); [Zimm 2024](https://doi.org/10.1038/s41558-023-01869-0).

    Two specific pitfalls to avoid:

    - Do not claim comprehensiveness through approach averaging. Averaging contradictory approaches (e.g., averaging grandfathering with equal per capita) does not produce a neutral result — it produces an incoherent one.
    - Do not combine contradictory principles into composite indices.

    The appropriate role of analysis is to clarify the ethical underpinnings and consequences of normative choices — not to make those choices on behalf of users [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7).

### Budget vs Pathway: Choosing Based on Your Needs

**In brief:** Both produce compatible cumulative allocations. Choose based on whether you need year-by-year breakdowns.

**Why they're compatible:** For emission pathways that never go negative (emissions always >= 0), the cumulative sum of annual allocations is consistent with the budget allocation, fair-shares ensures this cumulative consistency by design.

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
| `pathway`      | Pathway | Pathway approaches   | Allocating annual emissions following scenario pathways (e.g. AR6) | Time series of annual values                   |
| `rcb-pathways` | Hybrid  | Pathway approaches   | Using budget data but need year-by-year pathways    | Budget to global pathway to allocated annually |

### RCB-to-Pathway Conversion

The `rcb-pathways` target source converts the **global** remaining carbon budget (RCB) into a **global** annual emission pathway, which can then be allocated to countries using pathway allocation approaches. This is a two-step process:

1. **Generates a global pathway** from the remaining carbon budget using normalized shifted exponential decay (a global operation -- no country allocations at this stage)
2. **Applies pathway allocation approaches** to distribute the global pathway among countries (e.g., `equal-per-capita`, `per-capita-adjusted`)
3. **Preserves cumulative totals** -- the sum of annual pathway emissions equals the original carbon budget

The global pathway:

<!-- REFERENCE: generate_rcb_pathway_scenarios() in src/fair_shares/library/utils/math/pathways.py -->

- Starts at global historical emissions in the allocation year
- Reaches exactly zero by the end year (default 2100)
- Ensures discrete annual sums equal the budget
- The `generator` parameter is an extensibility point for alternative functional forms, provided they consume the full budget by the end year

!!! note "Country net-zero years emerge from allocation, not pathway shape"

    The global pathway shape described above does not directly prescribe when individual countries reach net-zero. Country net-zero timing emerges from the allocation step: pathway allocation approaches distribute annual emissions to countries, and countries whose allocation nears zero early in the pathway are effectively at their net-zero year. For example, under a 1.5 deg C budget with strong responsibility weighting, a high-emitting developed country might receive an allocation that reaches near-zero (or a very small % of current emissions) well before 2100 -- this can be considered their implied net-zero year in policy translation.

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

**Why this matters:** The allocation year determines how much of history counts. Setting `allocation_year=2020` means cumulative population from 2020 only determines shares -- every country starts fresh. Setting `allocation_year=1990` means cumulative population from 1990 determines shares, and when those shares are applied to a budget, high historical emitters can end up with negative remaining allocations. This is the single most consequential parameter in the framework: it operationalises the normative question of whether past emissions create present obligations. See [Historical Responsibility](#historical-responsibility) below.

### Building Blocks

| Component             | What it adds                                                | Budget Parameter                                           | Pathway Parameter                                            |
| --------------------- | ----------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------ |
| Early allocation year | Cumulative population from that year determines shares; can produce negative allocations when shares are applied to budgets | `allocation_year`                                          | `first_allocation_year`                                      |
| Pre-allocation responsibility | Multiplicative rescaling by relative per-capita emissions in [`pre_allocation_responsibility_year`, `allocation_year`); always positive (see warning below) | `pre_allocation_responsibility_weight` + `pre_allocation_responsibility_year` | Same                                                         |
| Capability weight     | GDP-based rescaling of per-capita shares from allocation year onwards | `capability_weight`                                        | Same                                                         |
| Income floor          | Protects subsistence needs in capability calculations       | `income_floor`                                             | Same                                                         |
| Gini adjustment       | Rescales GDP using Gini-modeled income distribution; income below threshold exempt | Use `*-gini-budget` allocation approach                    | Use `*-gini` or `*-gini-adjusted` allocation approach        |
| Historical discounting| Weights earlier emissions less (e.g. due to natural CO2 removal)        | `historical_discount_rate`                                 | Same                                                         |
| Deviation constraint  | Caps outlier adjustments (standard deviations from equal per capita) | `max_deviation_sigma`                                      | Same                                                         |
| Preserved shares      | Freezes population shares at allocation year                | `preserve_allocation_year_shares`                          | `preserve_first_allocation_year_shares`                      |
| Historical population entitlement | Use `equal-per-capita-budget(allocation_year=1850)` then post-process by subtracting actual emissions | N/A                                                        | Composition of budget allocation + post-processing           |
| Convergence mechanism | Exponential transition from current emission shares to cumulative per-capita targets; budget-preserving | N/A                                                        | Use `cumulative-per-capita-convergence*` allocation approach |

!!! warning "Pre-allocation responsibility scaling ≠ earlier allocation year"

    These are two **different mechanisms**, not two ways of saying the same thing.

    **Earlier allocation year** (e.g. `allocation_year=1990`): cumulative population from that year determines each country's share. When those shares are applied to a global budget, regions that emitted heavily since 1990 can end up with negative remaining allocations by 2025 — this is a mathematical consequence, not a design choice.

    **Pre-allocation responsibility scaling** (e.g. `allocation_year=2025`, `pre_allocation_responsibility_year=1990`): keeps the allocation year at 2025 (so no cumulative accounting of past emissions in the budget) but multiplicatively rescales each country's share based on relative per-capita emissions during 1990–2025. Always produces positive allocations if `allocation_year` is the present, because it adjusts *proportions*, not *levels* — but it is not a 1:1 accounting of those emissions.

**Temporal note:** Capability adjustments apply from the allocation year onwards. Pre-allocation responsibility scaling covers `pre_allocation_responsibility_year` to the allocation year — a separate, earlier window.

**GDP window beyond the last observed year:** When the allocation cumulative window extends past the last year of the input GDP time series (the default `wdi-2025` ends at 2023), the per-capita budget and pathway primitives forward-fill GDP per capita from the last observed year to cover every subsequent year of the window. The cross-country capability ratios of the last observed year are then held constant for the rest of the window. The cumulative-per-capita-convergence primitives behave differently: their per-country capability scalar is computed only over the intersection of GDP and population years, with no forward-fill at all. In both cases, users who want different post-observation capability dynamics (SSP2 GDP projections, custom growth assumptions, or a future-extended WDI release) should extend the input `gdp_ts` time series before calling the allocation function. The forward-fill is the minimum-disruption default when no projected GDP data is supplied; the library does not prescribe a projection.

**Capability snapshot mode (`capability_reference_year: int | None = None`):** By default, `per_capita_adjusted_budget` computes capability year-by-year — `pf(GDP_per_cap(g, t))` is evaluated for each country and year in the allocation window, then multiplied into that year's population and summed cumulatively. Setting `capability_reference_year` to an integer changes this: capability becomes a scalar per country, computed as `pf(GDP_per_cap(g, t_ref))` from that single reference year's data, then broadcast across all population years in the window. The reference year can be before, at, or after `allocation_year` — all three cases are handled. The two modes are algebraically equivalent only when capability is constant over the window; in practice they diverge substantially for long windows spanning periods of economic change. Emits a `UserWarning` if `capability_reference_year` exceeds the last observed GDP year.

The canonical example of `ref_year < allocation_year` is the PRR2023 lag-1 convention: PRR2023 defines capability as GDP per capita in the year immediately preceding the allocation decision, so `allocation_year=2015` paired with `capability_reference_year=2014` is the reproduction-faithful configuration. The nb601 notebook (PRR2023 reproduction) uses exactly this. More broadly: use `capability_reference_year=1990` with `allocation_year=1990` for ESABCC 2023 `CPCadjCAP` results.

**Gini caveat when `ref_year < allocation_year`:** The Gini adjustment (`gini_s` kwarg) is NOT applied to the snapshot in this case. The snapshot is sourced from the unfiltered `gdp_ts` and `population_ts` inputs, before the Gini adjustment step runs. Users who need Gini at the reference year should either (a) use a reference year inside the allocation window, or (b) pre-apply Gini to `gdp_ts` externally before calling `per_capita_adjusted_budget`.

Year-by-year integration is the more defensible forward-looking semantic — it reflects lifetime capability over the allocation window rather than a point-in-time snapshot — but snapshot is the reproduction-faithful choice for papers that defined capability as a fixed indicator at a reference instant. For full design rationale and edge-case behaviour, see the proposal spec at `specs/active/2026-04-08-capability-snapshot-mode-proposal.md`.

These can be combined. For example, CBDR-RC can be interpreted and operationalised through:

- Early allocation year (e.g. 1850) + capability weight: simplest, but capability data may be unavailable for early years
- Allocation year of 1990 + pre-allocation responsibility scaling from 1850 + capability weight: avoids data availability issues for early capability years while still differentiating by historical emissions
- (Pathways only) Convergence approach + early allocation year + capability weight: with smooth transition path

For complete parameter configurations, worked examples, and use-case-to-approach mappings, see [From Principle to Code](principle-to-code.md).

---

## Gini Adjustment

<!-- REFERENCE: per_capita_adjusted_gini_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted_gini() in src/fair_shares/library/allocations/pathways/per_capita.py -->

**Why this exists:** National GDP per capita is a crude measure of capability -- it treats every dollar equally, whether it feeds a family or buys a yacht. Within-country inequality means that two countries with identical GDP per capita can have radically different capacity to mitigate if one concentrates wealth while the other distributes it. The Gini adjustment addresses this by modeling how income is distributed within each country and counting only income above a development threshold toward capability.

Implements an interpretation of the Greenhouse Development Rights (GDR) framework's capability metric for entitlements (note: GDR was originally designed for burden-sharing, not entitlement allocation): only income **above** a development threshold counts as "ability to pay." The income floor works like a tax-free personal allowance — each person's first $7,500/year (2010 PPP, the GDR framework's standard development threshold) of income is exempt from capability calculations.

Income distribution is modelled as log-normal, parameterised by each country's Gini coefficient. When combined with the income floor, higher inequality means more national income sits above the development threshold — increasing measured capability.

See [From Principle to Code](principle-to-code.md) for conceptual context.

**Mathematical formulations:** [GDR capability calculation](https://setupelz.github.io/fair-shares/api/utils/adjustments/#calculate_gini_adjusted_gdp) | [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_gini_budget) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted_gini)

---

## Maximum Deviation Constraint

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

Parameter: `max_deviation_sigma` (default: `None` — no constraint; set to a positive float such as `2.0` to enable a ±N-σ cap)

**Why this exists:** Pre-allocation responsibility and capability adjustments are multiplicative rescaling factors applied to population. In theory, these factors are unbounded — a country with extremely high per-capita emissions and high GDP could have its allocation rescaled to near zero, while a country at the other extreme could receive a disproportionately large share. A single outlier country can therefore distort the entire distribution, making results sensitive to data quality in the tails. `max_deviation_sigma` provides an optional opt-in cap on this behaviour for users who want to dampen tail sensitivity.

`max_deviation_sigma` caps this by limiting how far any country's adjusted allocation can deviate from the equal-per-capita baseline, measured in standard deviations of the adjustment distribution. **The default is `None` (no cap)** — fair-shares does not silently clip extreme values, because most published effort-sharing frameworks (Pelz 2025, PRR2023, GDR/Baer 2009, Dekker 2025) explicitly permit and even expect extreme tails. Setting `max_deviation_sigma=2.0` reproduces the older fair-shares default behaviour, which clipped to within 2 standard deviations.

Use a numeric value (e.g. `2.0`) when you explicitly want to compress the distribution; leave it at `None` to reproduce the raw, unconstrained adjustment behaviour described in the source papers.

Only relevant when applying scaling adjustments (pre-allocation responsibility, capability, or combinations). Has no effect on pure equal-per-capita approaches.

**Implementation details:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_budget) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted)

---

## Weight Normalization

<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py -->

Combines pre-allocation responsibility scaling (over the window prior to the allocation year) and capability adjustments (from the allocation year onwards) as multiplicative factors applied to the equal per capita distribution:

```
Adjusted population = Population × responsibility_metric^(-w_r) × capability_metric^(-w_c)
```

Where `w_r` and `w_c` are the normalized pre-allocation responsibility and capability weights (divided by their sum). Only the ratio between weights affects results; `(0.3, 0.7)` and `(0.15, 0.35)` produce identical allocations because they normalize to the same values.

**Mathematical specification:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_budget) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/#per_capita_adjusted)

---

## Dynamic vs Preserved Shares

<!-- REFERENCE: equal_per_capita_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
<!-- REFERENCE: equal_per_capita() in src/fair_shares/library/allocations/pathways/per_capita.py -->

Parameter: `preserve_allocation_year_shares` (budget) / `preserve_first_allocation_year_shares` (pathway)

**Why this exists:** Equal per capita allocation rests on the principle that each person has equal entitlement to atmospheric space. But population changes over time — some countries are growing rapidly, others are shrinking. The question is: which population counts?

Dynamic mode (the default) recalculates shares as population evolves, giving growing populations proportionally more atmospheric space over the allocation horizon. This reflects a forward-looking interpretation: future people have the same entitlement as present people.

Preserved mode fixes shares at the allocation year and holds them constant. This reflects a snapshot interpretation: entitlements are determined at the moment of allocation and don't shift with subsequent demographic change. It also provides a simpler, more predictable allocation for policy planning — the shares won't move with updated population projections.

The choice between these modes is a normative judgment about whether future population growth should increase a country's atmospheric entitlement.

| Mode              | Budget                                     | Pathway                                         |
| ----------------- | ------------------------------------------ | ----------------------------------------------- |
| Dynamic (default) | Cumulative population from allocation year | Recalculated each year based on current pop/GDP |
| Preserved         | Population at allocation year only         | Fixed at first allocation year                  |

**Mathematical specifications:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/#equal_per_capita_budget) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/#equal_per_capita)

---

## Historical Responsibility

The case for historical responsibility rests on the claim that past emissions create present obligations — that cumulative contributions to the problem should shape the distribution of remaining space. The normative grounding spans harm prohibition [Shue 2015](https://doi.org/10.1515/mopp-2013-0009); [Meyer 2013](https://chicagounbound.uchicago.edu/cjil/vol13/iss2/15/), corrective justice [Caney 2010](https://doi.org/10.1080/13698230903326331), and the founding per-capita equity argument in [Agarwal 1991](https://cdn.cseindia.org/userfiles/GlobalWarming%20Book.pdf). Quantitative operationalisation is developed by [Matthews 2016](https://doi.org/10.1038/NCLIMATE2774) (cumulative carbon debt against an equal per-capita benchmark) and extended by [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122) (net-zero carbon debt as a persistent post-peak obligation).

fair-shares exposes two distinct mechanisms to operationalise this:

1. **Early allocation year:** Set `allocation_year` to 1850 or 1990 — cumulative population from that year determines each country's share (can produce negative allocations when shares are applied to a budget)
2. **Responsibility weight:** Use `pre_allocation_responsibility_weight` + `pre_allocation_responsibility_year` — multiplicative rescaling of shares based on relative per-capita historical emissions (always positive if `allocation_year` is the present)

These can be combined, but they are different mechanisms with different behavioral properties. See the [warning in Building Blocks](#building-blocks) for the full distinction.

**Mathematical details:** [Budget](https://setupelz.github.io/fair-shares/api/allocations/budgets/) | [Pathway](https://setupelz.github.io/fair-shares/api/allocations/pathways/)

### Historical Emissions Discounting

<!-- REFERENCE: calculate_responsibility_adjustment_data() in src/fair_shares/library/utils/math/adjustments.py -->

Parameter: `historical_discount_rate` (default: 0.0)

!!! warning "This is a per-capita-adjusted parameter, not an equal-per-capita parameter"

    Discounting historical emissions is not a neutral technical choice. It systematically reduces measured responsibility for early-industrialising countries and is **not** part of equal-per-capita accounting. Equal per capita treats every tonne of CO2 equivalently regardless of when it was emitted. Discounting departs from this by introducing a temporal weighting that favours early emitters.

    The parameter is available on the `per-capita-adjusted` family of functions (where `pre_allocation_responsibility_weight > 0`), not on `equal-per-capita` functions. It is also available on `cumulative-per-capita-convergence-adjusted` and `cumulative-per-capita-convergence-gini-adjusted`, which route through the same pre-allocation responsibility adjustment pipeline.

    For critiques of discounting historical responsibility, see [Meyer 2013](https://chicagounbound.uchicago.edu/cjil/vol13/iss2/15/) (why historical emissions should count at face value), [Shue 2014](references.md#shue-2014); [Shue 2015](https://doi.org/10.1515/mopp-2013-0009) (harm prohibition does not decay with time), and [Caney 2009](https://doi.org/10.1080/17449620903110300) (discounting conflates atmospheric residence with moral responsibility). For the countervailing physical argument, see [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7) and [Van Den Berg 2020](https://doi.org/10.1007/s10584-019-02368-y).

Weights earlier historical emissions less than recent ones when computing pre-allocation responsibility scaling. The discount weight for emissions in year $t$ relative to a reference year $t_{ref}$ is:

$$
w(t) = (1 - r_d)^{t_{ref} - t}
$$

where $r_d$ is the discount rate (0.0 to <1.0) and $t_{ref}$ is the year before the allocation year. When `historical_discount_rate=0.0` (default), all historical emissions are weighted equally — this is the standard approach. When per-capita pre-allocation responsibility is used, the same discount weights are applied to population for consistency.

The argument for discounting is physical: a fraction of emitted CO2 is removed from the atmosphere each year by ocean and terrestrial sinks, so older emissions contribute less to current concentrations [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7); [Van Den Berg 2020](https://doi.org/10.1007/s10584-019-02368-y). The argument against is moral: responsibility for harm does not diminish with time, and discounting produces outcomes that systematically benefit the countries most responsible for cumulative warming [Meyer 2013](https://chicagounbound.uchicago.edu/cjil/vol13/iss2/15/); [Shue 2015](https://doi.org/10.1515/mopp-2013-0009).

| Rate | Effect on 1850 emissions (ref. 2020) |
| ---- | ------------------------------------ |
| 0.0  | Full weight (1.0) — standard        |
| 0.005| ~43% weight                          |
| 0.01 | ~18% weight                          |
| 0.02 | ~3% weight                           |

Higher rates reduce the influence of early historical emissions on pre-allocation responsibility scaling. Countries with large early-industrialisation emissions (e.g., UK, Germany) benefit most from discounting. Countries whose emissions grew recently (e.g., China, India) see relatively smaller changes.

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

### Convergence Method

Parameter: `convergence_method` (default: `"minimum-speed"`)

**Why this matters:** The convergence mechanism needs a solver to find a path from each country's current emission share to its cumulative target share. The two available methods produce the same cumulative outcome (total allocations match the target budget) but differ in how they distribute emissions across years — which affects the near-term mitigation trajectory countries face.

- **`minimum-speed`** finds the slowest possible exponential convergence that still satisfies the cumulative constraint. This produces the most gradual transition, giving high-emitting countries the most time to adjust. Use this as the default — it is fully automatic and produces conservative (least-disruptive) transition paths.

- **`sine-deviation`** front-loads the adjustment, requiring larger near-term emission reductions and allowing more headroom later. This reflects an urgency argument: if cumulative emissions drive warming, earlier reductions have more value. Use this when you want to explore front-loaded pathways or when replicating [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7).

| Method             | Description                                                  | Required Parameters        |
| ------------------ | ------------------------------------------------------------ | -------------------------- |
| `minimum-speed`    | Default. Finds the minimum exponential convergence speed satisfying cumulative constraints. | None (automatic)          |
| `sine-deviation`   | Iterative sine-shaped deviation from a PCC baseline [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7). Front-loads the adjustment toward cumulative budget targets. | `convergence_year`        |

**Sine-deviation method:** Computes year-by-year allocations that deviate from a per-capita-convergence (PCC) baseline using a sine-shaped correction. Each year's allocation depends on all previous allocations (iterative). The method tracks the remaining "debt" between the target cumulative budget and actual cumulative allocations, and applies a sine-shaped correction that front-loads the adjustment.

<!-- REFERENCE: evolve_shares_sine_deviation() in src/fair_shares/library/utils/math/convergence.py -->

For country $g$ in year $t$:

$$
D(t, g) = B_{ECPC}(g) - \sum_{t_i=t_a}^{t-1} E_{alloc}(t_i, g) + E_{PCC}(t, g)
$$

$$
E_{alloc}(t, g) = \frac{D(t,g)}{t_{conv} - t} \cdot \sin\!\left(\frac{t}{t_{conv} - t_a} \cdot \pi\right) + E_{PCC}(t, g)
$$

where $t_{conv}$ is `convergence_year` and $t_a$ is `first_allocation_year`.

Parameter: `convergence_year` (required when `convergence_method="sine-deviation"`)

**Why this matters:** The sine-deviation method needs a deadline — the year by which the cumulative allocation must match the target budget. This is a policy choice: an earlier convergence year demands steeper near-term reductions (front-loading the transition), while a later year spreads the adjustment over a longer horizon. Later convergence years produce smoother transitions; earlier years produce steeper near-term adjustments.

### Maximum Convergence Speed (Convergence Only)

Parameter: `max_convergence_speed` (default: 0.9)

**Why this exists:** The convergence solver finds the exponential speed at which each country's emission share moves toward its target. Without an upper bound, the solver could produce speeds where a country's allocation swings wildly from one year to the next — technically satisfying the cumulative constraint but producing a pathway no country could actually follow.

`max_convergence_speed` caps the speed parameter at a value between 0 and 1. At 0.9 (default), a country's allocation can move up to 90% of the remaining distance to its long-run target in a single year — fast enough for aggressive transitions but smooth enough to be physically plausible. Lower values force gentler transitions but increase the chance of infeasibility (the solver may not find a path that satisfies the cumulative constraint at low speeds). Higher values allow more abrupt year-to-year changes.

If `strict=True` raises an infeasibility error and `max_convergence_speed` is below 0.9, try increasing it before relaxing other parameters.

## Strict Parameter (Convergence Only)

<!-- REFERENCE: cumulative_per_capita_convergence() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->
<!-- REFERENCE: cumulative_per_capita_convergence_adjusted() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->
<!-- REFERENCE: cumulative_per_capita_convergence_adjusted_gini() in src/fair_shares/library/allocations/pathways/cumulative_per_capita_convergence.py -->

Parameter: `strict` (default: True)

**Why this exists:** The convergence solver works backward from a cumulative target share to find a convergence speed that gets each country there. But this isn't always mathematically possible. When a country's current emissions are very far from its target share — for example, a high emitter with a small target — the solver would need a "long-run share" below 0 (i.e., negative emissions) or above 1 (i.e., more than 100% of global emissions). Neither is physically meaningful.

This happens most often under aggressive equity configurations: strong pre-allocation responsibility weighting with early allocation years, very tight carbon budgets, or combinations that push high-emitting countries toward extreme targets. The solver hits a mathematical wall — there is no exponential convergence path that satisfies the cumulative constraint within the allowed speed range.

`strict` controls what happens at that wall:

| Mode                   | Behavior                                                      | When to use |
| ---------------------- | ------------------------------------------------------------- | ----------- |
| Strict (`True`, default) | Raises an error if no feasible solution exists              | Research: you want to know immediately if your configuration produces infeasible targets |
| Permissive (`False`)     | Clips infeasible long-run shares to [0, 1], adjusts remaining countries proportionally, and reports per-country deviation ratios as warnings | Exploration: you want results for feasible countries even when some targets are unreachable |

In permissive mode, country-level warnings report the ratio of achieved-to-target cumulative shares (e.g., `strict=false:0.85` means the country achieved 85% of its target cumulative allocation). Countries whose targets were feasible are unaffected — the solver only adjusts the infeasible ones and redistributes the surplus proportionally.

!!! tip "Diagnosing infeasibilities"

    If `strict=True` raises an error, try `strict=False` first to see which countries are infeasible and by how much. Common causes: (1) very early `allocation_year` with strong pre-allocation responsibility weighting makes high-emitting countries' targets unreachable; (2) short time horizon (few years between `first_allocation_year` and end of pathway) leaves insufficient time for convergence; (3) `max_convergence_speed` is too low for the required transition.

**[Implementation details →](https://setupelz.github.io/fair-shares/api/allocations/pathways/#cumulative_per_capita_convergence)**

---

## Adjustment Shape Parameters

As described in [Building Blocks](#building-blocks), two distinct mechanisms exist for accounting for past emissions in the adjusted approaches:

- **Earlier allocation year** (`allocation_year` / `first_allocation_year`): cumulative population from that year determines each country's share. When applied to a global budget, high historical emitters can end up with negative remaining allocations — past emissions are counted directly in the budget arithmetic.
- **Pre-allocation responsibility rescaling** (`pre_allocation_responsibility_weight` + `pre_allocation_responsibility_year`): keeps the allocation year at the present, but multiplicatively rescales each country's equal-per-capita share by relative historical per-capita emissions over the responsibility window. Always produces positive allocations — it adjusts *proportions*, not *levels*.

Both are distinct from **GDP-based capability rescaling**, which reduces a country's share based on its current or cumulative wealth rather than its historical emissions. The Gini adjustment (`*-adjusted-gini` approaches) is a further refinement of the capability component only, correcting GDP for within-country income inequality.

The parameters below control the *functional shape* of these adjustments — how steeply allocations respond to differences in emissions or GDP. Both responsibility and capability adjustments share the same exponent and functional-form parameters because both implement the same underlying inversion: converting a raw metric into an allocation multiplier where a **higher raw value produces a lower entitlement**. The framework is allocating a budget or pathway, so high emitters and high-GDP countries both receive downward adjustments to their shares.

Note that this is a shape-level symmetry, not a temporal one. Pre-allocation responsibility looks **backward** from the allocation year over `[pre_allocation_responsibility_year, allocation_year)`, capturing historical emissions before the allocation begins. Capability looks **forward** from the allocation year onwards, using contemporary and future GDP. The two adjustments share functional-form parameters but act on temporally disjoint inputs.

The functional transformation achieves the inversion and as a side effect can compress the distribution — this is where the parameters matter.

These are advanced tuning parameters — the defaults are appropriate for most analyses. They are documented here for completeness; see the [API Reference](https://setupelz.github.io/fair-shares/api/allocations/budgets/#per_capita_adjusted_budget) for full mathematical details.

### Per Capita vs Absolute Mode

Parameters: `pre_allocation_responsibility_per_capita` (default: `False`), `capability_per_capita` (default: `True`)

**Why these exist:** Pre-allocation responsibility can be measured on a per-capita or absolute basis, and the choice reflects different fairness intuitions. **Absolute mode (the responsibility default)** uses total cumulative emissions regardless of population, which penalises large historical emitters in line with the polluter-pays framing of GDR (Baer 2009), Matthews (2016), and most of the historical-responsibility literature. Per-capita mode divides cumulative emissions by cumulative population before comparing countries — a high-population country with high total emissions may have low per-capita emissions, reducing its responsibility adjustment.

Capability is the inverse: per-capita mode (the default) measures individual prosperity using GDP/capita, which is the standard in the capability literature. Absolute mode uses total GDP and may be appropriate when the research question focuses on aggregate national capacity.

The historical default for responsibility was `True` (per-capita); it was flipped to `False` so that responsibility-based reproductions match the polluter-pays absolute framing the source literature actually uses. Set explicitly to `True` if your research framing genuinely calls for per-capita responsibility.

### Exponents

Parameters: `pre_allocation_responsibility_exponent` (default: 1.0), `capability_exponent` (default: 1.0)

**Why these exist:** The exponent controls how aggressively the adjustment squashes the range of allocations. With `inverse=True`, the adjustment is `1 / transform(x)^exponent`: exponent=1.0 gives `1/transform(x)`, exponent=2.0 gives `1/transform(x)²`, exponent=0.5 gives `1/√transform(x)`. Greater exponent = more squashing.

Values below 1.0 produce weaker adjustments.

### Functional Form

Parameters: `pre_allocation_responsibility_functional_form` (default: `"asinh"`), `capability_functional_form` (default: `"asinh"`)

**Why these exist:** The functional form determines how the median-normalised metric is transformed before the exponent is applied. `"asinh"` (inverse hyperbolic sine) is the default and handles zero values gracefully — it behaves like a logarithm for large values but passes through zero without blowing up. `"power"` applies a simple power function, which is undefined at zero and can produce extreme outliers when the input distribution has a long tail.

Use `"asinh"` unless you have a specific reason to prefer `"power"` (e.g., replicating a published methodology that uses power-law adjustments).

Inputs are median-normalised before transformation, making results unit-invariant. Negative values (e.g., net-sink countries) are handled natively by arcsinh; the power form clamps to a small epsilon for numerical safety.

### Maximum Gini Adjustment

Parameter: `max_gini_adjustment` (default: 0.8)

**Why this exists:** The Gini adjustment rescales GDP based on within-country income distribution: countries with high inequality have more income above the development threshold, increasing their measured capability. Without a cap, extreme Gini coefficients (>0.6, as in some Sub-Saharan African countries) could produce outsized adjustments that dominate the allocation. `max_gini_adjustment` limits the maximum proportional reduction from the Gini correction. At the default of 0.8, the Gini adjustment can reduce a country's measured GDP by at most 80%.

Available on `per-capita-adjusted-gini-budget`, `per-capita-adjusted-gini`, and `cumulative-per-capita-convergence-gini-adjusted`.

---

## Per Capita Convergence (PCC)

<!-- REFERENCE: per_capita_convergence() in src/fair_shares/library/allocations/pathways/per_capita_convergence.py -->

The `per-capita-convergence` approach linearly blends grandfathering (current emissions) with equal per capita over time. It includes grandfathering elements, critiqued as having "no support among moral and political philosophers" [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8); see [Approaches Debated in the Literature](#approaches-debated-in-the-literature) for context and [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) on how convergence framings embed grandfathering during the transition period.

**[Formulation →](https://setupelz.github.io/fair-shares/api/allocations/pathways/)**

---

## Approaches Debated in the Literature

Several approaches appear in climate policy discussions and have been subject to scholarly critique.

### Grandfathering

Allocating future emission entitlements based on current emission shares. [Caney 2009](https://doi.org/10.1080/17449620903110300) calls grandfathering "morally perverse," and [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8) documents that it has "virtually no support among moral and political philosophers." Despite this, it dominates many studies that claim to be value-neutral. Moreover grandfathering is often embedded implicitly in "blended" approaches that combine it with equity principles [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) which must be treated with caution.

The `per-capita-convergence` approach includes grandfathering elements and is available in fair-shares for comparison; see [PCC](#per-capita-convergence-pcc).

### Cascading Biases

[Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) identifies three methodological biases that compound across effort-sharing analyses and systematically favour wealthier countries: **scope bias** (including cost-effectiveness alongside equity approaches, so that "efficiency" framings dilute equity findings), **framing bias** (late base years that embed grandfathering by construction), and **aggregation bias** (averaging ethically unequal approaches as if they were interchangeable). Each bias is small in isolation; cascaded together they produce results that look neutral but are not. [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7) documents how these patterns persist in recent fair-target modelling. The practical implication for fair-shares users: choose approaches based on principled argument, not menu-inclusion, and report each configuration separately rather than aggregating across principles.

### BAU Deviation Framing

Treating deviation from business-as-usual emissions as a cost or sacrifice. [Winkler 2018](https://doi.org/10.1007/s10784-017-9381-x) establishes that fair shares must be assessed *relative to other parties*, not against a country's own BAU — BAU deviation framing violates this by making effort self-referential. [Rajamani 2021](https://doi.org/10.1080/14693062.2021.1970504) excludes self-referenced progression and grandfathering-based approaches from principled fair share assessments, finding both lack justification under international environmental law. [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f) makes the connection explicit: BAU deviation framing treats current emission levels as a baseline entitlement — a concealed form of grandfathering.

### Small Share Justification

Arguments of the form "We only emit X% of global emissions." [Winkler 2020](https://doi.org/10.1080/14693062.2019.1680337) notes this cannot be universalised (every country's share is small under a sufficiently fine partition) and conflates total with per capita emissions. [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8) catalogues it as one of several "illegitimate" fairness indicators that routinely appear in NDC justifications.

---

## See Also

- **[API Reference: Budget Allocations](https://setupelz.github.io/fair-shares/api/allocations/budgets/):** Budget mathematical formulations
- **[API Reference: Pathway Allocations](https://setupelz.github.io/fair-shares/api/allocations/pathways/):** Pathway mathematical formulations
- **[country-fair-shares Guide](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/):** When to use each approach
- **[References](https://setupelz.github.io/fair-shares/science/references/):** Complete bibliography
