---
title: Allocation approaches
description: Design and parameters for budget and pathway allocation approaches in fair-shares
search:
  boost: 2
---

# Allocation approaches

An allocation approach turns an equity principle into each country's share.
This page explains the design and parameters of every approach.
[From principle to code](principle-to-code.md) maps principles to settings, and the API reference gives the maths for [budgets](../api/allocations/budgets.md) and [pathways](../api/allocations/pathways.md).

| Category | Question answered | Output |
| --- | --- | --- |
| **Budget** | What is each country's fair share of a cumulative remaining budget? | One value per country |
| **Pathway** | What is each country's fair share of emissions in each future year? | One value per country and year |

Shares sum to 1 in every year and cover the whole world.
For pathways that never go negative, the cumulative sum of annual allocations matches the budget allocation.
Global pathways that go net-negative are cut at net zero before allocation ([Global pathways after net zero](other-operations.md#post-net-zero)).
The `rcb-pathways` target turns a budget into a global pathway first ([RCB pathway generation](other-operations.md#rcb-pathway-generation)).

!!! note "No allocation approach is value-neutral"

    Every choice of base year, indicator, weighting or included approach reflects a judgement about fairness [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8); [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7). Studies of IAM methodology and effort-sharing document that defaults presented as neutral systematically favour wealthy nations [Klinsky 2018](https://doi.org/10.1098/rsta.2016.0461); [Winkler 2020](https://doi.org/10.1080/14693062.2019.1680337); [Zimm 2024](https://doi.org/10.1038/s41558-023-01869-0).

    Two consequences follow:

    - Averaging contradictory approaches, for example grandfathering and equal per capita, does not give a neutral or comprehensive result. It gives one that follows no single principle.
    - A composite index of contradictory principles has the same problem.

    Analysis clarifies the ethical basis and consequences of normative choices, and leaves the choices to the user [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7).

[Parameter effects](parameter-effects.md) shows how each parameter changes the shares of real countries.

---

## Allocation year

`allocation_year` (budget) or `first_allocation_year` (pathway) sets how much of history counts.
With `allocation_year=2020`, cumulative population from 2020 sets the shares, and every country starts fresh.
With `allocation_year=1990`, cumulative population from 1990 sets the shares. Once observed emissions since 1990 are subtracted, high historical emitters can have negative remaining budgets.
This is the most consequential parameter in the library. It answers the normative question of whether past emissions create present obligations ([Historical responsibility](#historical-responsibility)).

## Building blocks

| Component | What it adds | Budget parameter | Pathway parameter |
| --- | --- | --- | --- |
| Early allocation year | Cumulative population from that year sets shares; remaining budgets can be negative | `allocation_year` | `first_allocation_year` |
| Pre-allocation responsibility | Multiplicative rescaling by emissions in [`pre_allocation_responsibility_year`, `allocation_year`) (see warning below) | `pre_allocation_responsibility_weight` + `pre_allocation_responsibility_year` | Same |
| Capability weight | GDP-based rescaling: year by year from the allocation year, a snapshot year or a cumulative window | `capability_weight` (+ `capability_reference_year` or `capability_window`) | Same |
| Income floor | Exempts income below a development threshold from capability | `income_floor` | Same |
| Gini adjustment | Models the income distribution within each country | `*-gini-budget` approach | `*-gini` or `*-gini-adjusted` approach |
| Historical discounting | Weights earlier emissions less | `historical_discount_rate` | Same |
| Deviation constraint | Caps outlier adjustments | `max_deviation_sigma` | Same |
| Preserved shares | Freezes population shares at the allocation year | `preserve_allocation_year_shares` | `preserve_first_allocation_year_shares` |
| Historical population entitlement | `equal-per-capita-budget(allocation_year=1850)`; the library then subtracts observed emissions ([`compute_remaining_budgets`](../api/python-api.md#compute_remaining_budgets)) | N/A | Budget allocation, then remaining budget |
| Convergence | Exponential transition from current emission shares to cumulative per-capita targets; budget-preserving | N/A | `cumulative-per-capita-convergence*` approach |

!!! warning "Pre-allocation responsibility scaling ≠ earlier allocation year"

    These are two **different mechanisms**, not two ways of saying the same thing.

    **Earlier allocation year** (e.g. `allocation_year=1990`): cumulative population from that year determines each country's share. When those shares are applied to a global budget, regions that emitted heavily since 1990 can end up with negative remaining allocations by 2025. This is a mathematical consequence, not a design choice.

    **Pre-allocation responsibility scaling** (e.g. `allocation_year=2025`, `pre_allocation_responsibility_year=1990`): keeps the allocation year at 2025 (so no cumulative accounting of past emissions in the budget) but multiplicatively rescales each country's share based on relative per-capita emissions during 1990–2025. Always produces positive allocations if `allocation_year` is the present, because it adjusts *proportions*, not *levels*, but it is not a 1:1 accounting of those emissions.

The mechanisms combine. For example, common but differentiated responsibilities and respective capabilities (CBDR-RC) can be put into practice as:

- an early allocation year (e.g. 1850) plus a capability weight. Capability data may be missing for early years;
- an allocation year of 1990, responsibility scaling from 1850 and a capability weight. This avoids the early capability data while still differentiating by historical emissions;
- for pathways, a convergence approach with an early allocation year and a capability weight, for a smooth transition.

[From principle to code](principle-to-code.md) gives complete configurations.

## Capability timing

Responsibility always reads the window before the allocation year.
Capability has three modes, and each reproduces a different definition:

| Mode | Setting | Capability is | Reproduces |
| --- | --- | --- | --- |
| Year by year (default) | none | GDP per capita in each year of the allocation window | |
| Snapshot | `capability_reference_year` | GDP per capita in one year, held across the window | PRR2023 and ESABCC 2023 ([Pelz 2023](references.md)) |
| Cumulative window | `capability_window=(start, end)` | Cumulative GDP over cumulative population for an inclusive window, held across the allocation window | [Pelz 2025a](references.md) (SI Eq. 2) and [Weber 2026](references.md) (Eq. 18), with `capability_functional_form="power"` and `capability_exponent=0.5` |

The snapshot year and the window can lie before the allocation year.
In a grid configuration, `[1990, 2019]` is one window and `[[1990, 2019], [2000, 2019]]` is two.
Snapshot and window modes are exclusive. Both are available on `per_capita_adjusted_budget`, `per_capita_adjusted_gini_budget`, `per_capita_adjusted` and `per_capita_adjusted_gini`, and not on the convergence family.
The functional form, exponent and median normalisation apply to the snapshot or window value as in the default mode.
On the Gini approaches the Gini adjustment applies to each year's GDP before a window sum. A one-year window gives the snapshot result for that year.
On the budget approaches a snapshot needs GDP at the reference year only, so `allocation_year` can precede the first GDP year (down to 1850). The pathway approaches still need GDP at `first_allocation_year`.
Year-by-year and snapshot modes agree only when capability is constant over the window. Over long windows of economic change they diverge substantially ([capability_reference_year](parameter-effects.md#capability_reference_year)).

Notebook 601 pairs `allocation_year=1990` with `capability_reference_year=1990`, and `allocation_year=2015` with 2014. The all-GHG categories allocate from 2015 only, so they use 2014. The preset `esabcc_2023_allocations()` holds this grid.

**After the last observed GDP year.** The allocation window can run past the end of the GDP series (2025 for the default `wdi-2025`).
The per-capita budget and pathway approaches then forward-fill GDP per capita from the last observed year, holding that year's cross-country ratios.
The convergence approaches compute capability only over years with both GDP and population, and do not forward-fill.
For other dynamics, such as SSP2 projections, extend `gdp_ts` before calling the allocation function. The library does not prescribe a projection.

---

## Gini adjustment

National GDP per capita counts all income the same, whether it meets basic needs or not.
Two countries with the same GDP per capita can differ widely in capacity to mitigate if one concentrates income and the other spreads it.
The Gini adjustment models income within each country as log-normal, parameterised by its Gini coefficient, and counts only income above a development threshold, `income_floor`, toward capability.
The floor works like a tax-free personal allowance: each person's income up to the threshold is exempt.
Higher inequality puts more national income above the threshold, so it raises measured capability.

This adapts the capability metric of the Greenhouse Development Rights (GDR) framework, which was designed for burden-sharing, to entitlement allocation.
[Baer 2013](https://doi.org/10.1002/wcc.201) sets the GDR threshold at 7,500 dollars per person per year on a 2005 price base and 8,500 on a 2010 base.
Give the floor in the price base of the GDP series. The default GDP source is in constant 2021 international dollars.

The adjusted capability is normalised by the median of the unadjusted indicator, GDP per capita or GDP before the floor applies. This reference does not move with the floor.
Raising the floor lowers each country's capability, so each country's capability factor rises or stays flat.
At `income_floor=0` the reference equals the usual median, and results match the approaches without the Gini adjustment.

### Maximum Gini adjustment

`max_gini_adjustment` (default 0.8) caps the reduction from the Gini correction. At 0.8, capability stays at no less than 20% of GDP.
Without a cap, capability in low-income countries falls toward zero as the floor rises, and the inverse capability factor behaves like `median / capability`. A few of the poorest countries would then take most of the allocation.

The cap binds for low-income countries, not for high-inequality ones. Once a country reaches the cap, its capability and its factor stay constant at every higher floor. Its share can still fall slowly, because the floor keeps lowering other countries' capability.
On the default data for 2025 (177 countries and rest-of-world), the 0.8 cap binds for 8 of these 178 at a floor of 2,500, 43 at 7,500, 54 at 10,000, 69 at 15,000 and 86 at 20,000.

The cap level is a values choice, and above a floor of about 5,000 it decides the results.
With capability weight 1.0 and a floor of 10,000, India's budget share is 14.0% at 0.8, 10.1% at 0.9, 5.9% at 0.95 and 0.5% with no cap ([Parameter effects](parameter-effects.md#income_floor)).
Set `max_gini_adjustment=0` to switch the Gini correction off.
It is available on `per-capita-adjusted-gini-budget`, `per-capita-adjusted-gini` and `cumulative-per-capita-convergence-gini-adjusted`.

**Maths:** [GDR capability](../api/utils/adjustments.md#calculate_gini_adjusted_gdp) | [Budget](../api/allocations/budgets.md#per_capita_adjusted_gini_budget) | [Pathway](../api/allocations/pathways.md#per_capita_adjusted_gini)

---

## Combining the adjustments {#weight-normalization}

Responsibility and capability act as multiplicative factors on the equal per capita distribution:

```
Adjusted population = Population × responsibility_metric^(-w_r) × capability_metric^(-w_c)
```

`w_r` and `w_c` are the two weights divided by their sum. Only their ratio matters: `(0.3, 0.7)` and `(0.15, 0.35)` give identical allocations. The two weights may sum to at most 1.0; a larger sum raises an error.

### Shape parameters {#adjustment-shape-parameters}

Both adjustments invert a raw metric: a higher value gives a lower entitlement. They therefore share the same shape parameters.
These are advanced settings. The defaults suit most analyses.

- **Per capita or absolute.** `pre_allocation_responsibility_per_capita` defaults to `False`: total cumulative emissions, which penalise large historical emitters in line with the polluter-pays framing of GDR (Baer 2009), Matthews (2016) and most of the historical-responsibility literature. Greenhouse Development Rights count only income and emissions above a development threshold, using the distribution within each country ([Baer 2008](https://doi.org/10.1080/09557570802453050)). `True` divides by cumulative population, so a populous country with high total emissions may get a smaller adjustment. `capability_per_capita` defaults to `True`, GDP per capita, the standard in the capability literature. `False` uses total GDP, for questions about aggregate national capacity.
- **Exponents.** `pre_allocation_responsibility_exponent` and `capability_exponent` (default 1.0) set how strongly the adjustment compresses the range. The adjustment is `1 / transform(x)^exponent`, so 2.0 compresses more and 0.5 less.
- **Functional form.** `pre_allocation_responsibility_functional_form` and `capability_functional_form` default to `"asinh"`. It behaves like a logarithm for large values and passes through zero and negative values (net-sink countries). `"power"` is undefined at zero, clamps to a small epsilon and can give extreme outliers in a long-tailed distribution. Use it to replicate a study that uses power-law adjustments.

Inputs are divided by the cross-country median before the transform, so results do not depend on units. The median also sets where the asinh curve bends from linear to logarithmic. The Gini approaches use the median of the unadjusted indicator ([Gini adjustment](#gini-adjustment)).
A missing capability or responsibility value raises an `AllocationError` that names the countries. Fill or drop them before allocating.

### Maximum deviation {#maximum-deviation-constraint}

`max_deviation_sigma` (default `None`) caps how far any country's adjusted allocation can move from equal per capita, in standard deviations of the adjustment distribution.
The factors are unbounded, so one outlier can distort the distribution and make results sensitive to data quality in the tails.
The library does not clip by default, because most published effort-sharing frameworks (Pelz 2025, PRR2023, GDR/Baer 2009, Dekker 2025) permit and even expect extreme tails.
Set a value such as `2.0` to compress the distribution. It has no effect on equal per capita approaches.

**Maths:** [Budget](../api/allocations/budgets.md#per_capita_adjusted_budget) | [Pathway](../api/allocations/pathways.md#per_capita_adjusted)

---

## Dynamic and preserved shares {#dynamic-vs-preserved-shares}

Equal per capita gives each person an equal entitlement. Populations change, so which population counts is a choice.

| Mode | Budget | Pathway | Interpretation |
| --- | --- | --- | --- |
| Dynamic (default) | Cumulative population from the allocation year | Recalculated each year | Future people have the same entitlement as present people |
| Preserved | Population at the allocation year only | Fixed at the first allocation year | Entitlements are set at the moment of allocation. Shares do not move with new population projections |

Set `preserve_allocation_year_shares` (budget) or `preserve_first_allocation_year_shares` (pathway).
The choice is a normative judgement about whether future population growth should increase a country's entitlement.

**Maths:** [Budget](../api/allocations/budgets.md#equal_per_capita_budget) | [Pathway](../api/allocations/pathways.md#equal_per_capita)

---

## Historical responsibility

The case for historical responsibility rests on the claim that past emissions create present obligations: that cumulative contributions to the problem should shape the distribution of remaining space. The normative grounding spans harm prohibition [Shue 2015](https://doi.org/10.1515/mopp-2013-0009); [Meyer 2013](https://chicagounbound.uchicago.edu/cjil/vol13/iss2/15/), corrective justice [Caney 2010](https://doi.org/10.1080/13698230903326331), and the founding per-capita equity argument in [Agarwal 1991](https://cdn.cseindia.org/userfiles/GlobalWarming%20Book.pdf). Quantitative operationalisation is developed by [Matthews 2016](https://doi.org/10.1038/NCLIMATE2774) (cumulative carbon debt against an equal per-capita benchmark) and extended by [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122) (net-zero carbon debt as a persistent post-peak obligation).

The library offers the two mechanisms of [Building blocks](#building-blocks): an early allocation year, and the responsibility weight.

### Historical emissions discounting

`historical_discount_rate` (default 0.0) weights earlier emissions less in the responsibility adjustment.

!!! note "A parameter of the per-capita-adjusted family, not of equal per capita"

    Discounting is a normative choice, not a neutral technical one. It lowers measured responsibility for early-industrialising countries. Equal per capita accounting counts every tonne of CO2 the same whatever the year it was emitted, and discounting departs from that with a weighting over time that favours early emitters.

    The parameter is available on the `per-capita-adjusted` family of functions (where `pre_allocation_responsibility_weight > 0`), not on `equal-per-capita` functions. It is also available on `cumulative-per-capita-convergence-adjusted` and `cumulative-per-capita-convergence-gini-adjusted`, which route through the same pre-allocation responsibility adjustment pipeline.

    For critiques of discounting historical responsibility, see [Meyer 2013](https://chicagounbound.uchicago.edu/cjil/vol13/iss2/15/) (why historical emissions should count at face value), [Shue 2014](references.md#shue-2014); [Shue 2015](https://doi.org/10.1515/mopp-2013-0009) (harm prohibition does not decay with time), and [Caney 2009](https://doi.org/10.1080/17449620903110300) (discounting conflates atmospheric residence with moral responsibility). For the countervailing physical argument, see [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7) and [Van Den Berg 2020](https://doi.org/10.1007/s10584-019-02368-y).

The weight for emissions in year $t$ is

$$
w(t) = (1 - r_d)^{t_{ref} - t}
$$

where $r_d$ is the rate (0.0 to below 1.0) and $t_{ref}$ is the year before the allocation year.
At 0.0 every year counts equally. With per-capita responsibility, population takes the same weights.

The argument for discounting is physical: ocean and land sinks remove part of emitted CO2 each year, so older emissions contribute less to current concentrations [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7); [Van Den Berg 2020](https://doi.org/10.1007/s10584-019-02368-y). The argument against is moral: responsibility for harm does not diminish with time, and discounting favours the countries most responsible for cumulative warming [Meyer 2013](https://chicagounbound.uchicago.edu/cjil/vol13/iss2/15/); [Shue 2015](https://doi.org/10.1515/mopp-2013-0009).

| Rate | Weight of 1850 emissions (ref. 2020) |
| --- | --- |
| 0.0 | 1.0 |
| 0.005 | about 43% |
| 0.01 | about 18% |
| 0.02 | about 3% |

Countries with large early-industrial emissions (e.g. UK, Germany) gain most from discounting. Countries whose emissions grew recently (e.g. China, India) change less.

---

## Convergence (pathways only) {#convergence-mechanism-pathways-only}

The `cumulative-per-capita-convergence*` approaches move each country from its current emission share to its cumulative per capita target share.
The path is smooth, and its total over the horizon equals the target share.

`convergence_method` chooses the solver. Both methods reach the same cumulative total and differ in timing:

| Method | What it does | Needs |
| --- | --- | --- |
| `minimum-speed` (default) | The slowest exponential convergence that meets the cumulative target. The most gradual transition, giving high emitters the most time | nothing |
| `sine-deviation` | A sine-shaped deviation from a per capita convergence baseline that front-loads the adjustment ([Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7)). Reflects the urgency argument that earlier reductions are worth more | `convergence_year` |

??? note "Sine-deviation equations"

    For country $g$ in year $t$, with $t_{conv}$ the `convergence_year` and $t_a$ the `first_allocation_year`:

    $$
    D(t, g) = B_{ECPC}(g) - \sum_{t_i=t_a}^{t-1} E_{alloc}(t_i, g) + E_{PCC}(t, g)
    $$

    $$
    E_{alloc}(t, g) = \frac{D(t,g)}{t_{conv} - t} \cdot \sin\!\left(\frac{t}{t_{conv} - t_a} \cdot \pi\right) + E_{PCC}(t, g)
    $$

    Each year's allocation depends on all earlier ones. An earlier `convergence_year` demands steeper near-term reductions; a later one spreads the adjustment.

`max_convergence_speed` (default 0.9) caps the speed. At 0.9 an allocation can move up to 90% of the remaining distance to its long-run target in one year. Lower values give gentler paths but can make the target unreachable.

`strict` (default `True`) decides what happens when no path exists.
A high emitter with a small target can need a long-run share below 0 or above 1. This happens most under strong responsibility weighting with early allocation years, tight budgets, or short horizons.

| Mode | Behaviour | Use for |
| --- | --- | --- |
| `strict=True` | Raises an error | Research: you learn at once that the configuration is infeasible |
| `strict=False` | Clips infeasible long-run shares to [0, 1], rescales the other countries, and reports each country's achieved-to-target ratio as a warning, e.g. `strict=false:0.85` | Exploration: results for the feasible countries |

To diagnose an error, run with `strict=False` to see which countries fail and by how much, then raise `max_convergence_speed` if it is below 0.9, before relaxing other parameters.

**Maths:** [Convergence](../api/allocations/pathways.md#cumulative_per_capita_convergence)

### Per capita convergence (PCC)

`per-capita-convergence` blends current emissions (grandfathering) linearly into equal per capita over time.
It is available for comparison only. Grandfathering has "no support among moral and political philosophers" [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8), and convergence framings embed it during the transition [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7). See [Approaches debated in the literature](#approaches-debated-in-the-literature).

---

## Approaches debated in the literature

??? note "Grandfathering, cascading biases, BAU deviation and small-share arguments"

    Several approaches appear in climate policy discussions and have been subject to scholarly critique.

    **Grandfathering.** Allocating future emission entitlements by current emission shares. [Caney 2009](https://doi.org/10.1080/17449620903110300) calls grandfathering "morally perverse," and [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8) finds "virtually no support among moral and political philosophers" for it. It still underlies many studies presented as value-neutral, often implicitly in "blended" approaches that combine it with equity principles [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7). The `per-capita-convergence` approach includes grandfathering elements and is available for comparison; see [PCC](#per-capita-convergence-pcc).

    **Cascading biases.** [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7) identifies three methodological biases that compound across effort-sharing analyses and systematically favour wealthier countries: **scope bias** (including cost-effectiveness alongside equity approaches, so that "efficiency" framings dilute equity findings), **framing bias** (late base years that embed grandfathering by construction), and **aggregation bias** (averaging ethically unequal approaches as if they were interchangeable). Each bias is small alone. Together they give results that look neutral but are not. [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7) documents these patterns in recent fair-target modelling. In practice: choose approaches by their stated principles rather than by inclusion in a menu, and report each configuration separately rather than averaging across principles.

    **BAU deviation framing.** Treating deviation from business-as-usual emissions as a cost or sacrifice. [Winkler 2018](https://doi.org/10.1007/s10784-017-9381-x) establishes that fair shares must be assessed *relative to other parties*, not against a country's own BAU. BAU deviation framing makes effort self-referential, which conflicts with this. [Rajamani 2021](https://doi.org/10.1080/14693062.2021.1970504) excludes self-referenced progression and grandfathering-based approaches from principled fair share assessments, finding both lack justification under international environmental law. [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f) makes the connection explicit: BAU deviation framing treats current emission levels as a baseline entitlement, an implicit form of grandfathering.

    **Small share justification.** Arguments of the form "We only emit X% of global emissions." [Winkler 2020](https://doi.org/10.1080/14693062.2019.1680337) notes this cannot be universalised (every country's share is small under a sufficiently fine partition) and conflates total with per capita emissions. [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8) catalogues it as one of several "illegitimate" fairness indicators that routinely appear in NDC justifications.
