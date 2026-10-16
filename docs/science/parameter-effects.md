---
title: Parameter effects
description: How allocation parameters change country shares, with real examples
search:
  boost: 2
---

# Parameter effects

This page shows how each parameter changes the result for three countries:

- **USA**: high historical emissions, high GDP per capita
- **India**: large population, low historical emissions per capita
- **Germany**: medium population, high historical emissions and GDP per capita

**Data and version:** fair-shares 0.3.0 with the default data sources. Emissions are fossil and industry CO2 (`co2-ffi`) from PRIMAP-hist v2.8 (`primap-202609`, to 2025). Population is UN/OWID with the UN WPP 2024 median projection (`un-owid-2025`). GDP is World Bank WDI GDP PPP in constant 2021 international dollars (`wdi-2025`, to 2025). Gini is the World Bank WDI Gini index (`wdi-2025`). The budget is `lamboll_2023` 1.5°C at 50% probability, rebased to 2020: 339.2 GtCO2. The allocation covers 177 countries and one rest-of-world group.

`uv run python notebooks/docs/parameter_effects_examples.py` produces every number on this page.
[Allocation approaches](allocations.md) explains the design behind each parameter.

---

## allocation_year / first_allocation_year

An earlier allocation year counts more past emissions against each country, and high historical emitters can go negative.

`equal-per-capita-budget`, budget remaining at the start of 2020:

| Country | allocation_year=2020 | allocation_year=1990 | allocation_year=1900 |
| ------- | -------------------- | -------------------- | -------------------- |
| USA     | +13.6 GtCO2          | -118.1 GtCO2         | -324.5 GtCO2         |
| India   | +56.7 GtCO2          | +160.6 GtCO2         | +273.5 GtCO2         |
| Germany | +2.7 GtCO2           | -15.6 GtCO2          | -65.1 GtCO2          |

_Remaining budget = cumulative population share × global budget from the allocation year, minus actual emissions from the allocation year to 2019. Notebook 601 and the Python API net observed emissions through the last observed year instead, so their budgets remain from 2026 ([remaining budgets](../user-guide/pipeline-map.md#4-remaining-budgets-and-annual-pathways-notebook-601-and-the-python-api))._

From 2020 no past emissions count, and all three countries have positive budgets.
From 1990 the USA and Germany have already used more than their equal per capita share.
From 1900 the gap widens: the USA falls to -324.5 GtCO2 and India rises to +273.5 GtCO2.
The allocation year is the most consequential normative choice in the library.

---

## pre_allocation_responsibility_weight and capability_weight

The two weights set the responsibility and capability adjustments. Only their ratio matters: `(0.5, 0.5)` equals `(0.3, 0.3)`. Their sum may not exceed 1.0, or the allocation raises an error.
When one weight is 0, the other is the sole adjustment whatever its value. When both are 0, the result is equal per capita ([Combining the adjustments](allocations.md#weight-normalization)).

The responsibility weight rescales shares by emissions in [`pre_allocation_responsibility_year`, `allocation_year`). The metric is absolute cumulative emissions by default; `pre_allocation_responsibility_per_capita=True` divides them by cumulative population.
This rescaling is multiplicative, whereas an early allocation year can produce negative allocations ([the two mechanisms](allocations.md#building-blocks); [comparison table](#if-you-want-x-set-y-guide)).
The capability weight rescales shares by GDP per capita, year by year from the allocation year unless a snapshot or window is set ([Capability timing](allocations.md#capability-timing)).

### Each adjustment alone

**Responsibility only** (`per-capita-adjusted-budget`, `capability_weight=0.0`, `allocation_year=2020`, `pre_allocation_responsibility_year=1990`):

| Country | No adjustment | Responsibility, absolute (default) | Responsibility, per capita |
| ------- | ------------- | ---------------------------------- | -------------------------- |
| USA     | 4.0%          | 0.5%                               | 0.3%                       |
| India   | 16.7%         | 2.7%                               | 6.4%                       |
| Germany | 0.8%          | 0.1%                               | 0.1%                       |

The absolute metric cuts all three shares sharply. India loses the most percentage points, because its total 1990-2019 emissions are large.
The per-capita metric divides by population, so India keeps 6.4% and the USA falls further to 0.3%.
In both modes the freed share goes to countries with low cumulative emissions outside this excerpt.
The choice between the two metrics is normative ([Shape parameters](allocations.md#adjustment-shape-parameters)).

**Capability only** (`pre_allocation_responsibility_weight=0.0`, `allocation_year=2020`):

| Country | No adjustment | Capability only |
| ------- | ------------- | --------------- |
| USA     | 4.0%          | 0.8%            |
| India   | 16.7%         | 12.6%           |
| Germany | 0.8%          | 0.2%            |

For high-income countries capability alone is almost as strong as responsibility.
India also falls: its GDP per capita is below the median, but the adjustment moves share to the lowest-income countries.

### Varying the ratio

| Country | 1.0:0.0 (responsibility) | 70:30 | 50:50 | 30:70 | 0.0:1.0 (capability) |
| ------- | ------------------------ | ----- | ----- | ----- | -------------------- |
| USA     | 0.5%                     | 0.7%  | 0.7%  | 0.8%  | 0.8%                 |
| India   | 2.7%                     | 4.9%  | 6.8%  | 8.9%  | 12.6%                |
| Germany | 0.1%                     | 0.2%  | 0.2%  | 0.2%  | 0.2%                 |

_Same settings, absolute responsibility._

The ratio blends smoothly between the two pure cases. For the USA and Germany both give similar shares. For India the ratio decides the result: 2.7% to 12.6%.

---

## capability_reference_year

Freezes capability at one year's GDP per capita instead of computing it across the allocation window. Budget and pathway approaches treat it the same way.

- **Unset (default):** budget approaches compute capability year by year across the window. Pathway approaches use the cumulative GDP-per-capita metric in dynamic mode and the first-allocation-year value in preserved mode. Years past the last observed GDP year are forward-filled.
- **Set:** the snapshot year's value holds across the window. A year before the window is read from the unfiltered inputs. A year past the last observed GDP year falls back to the last observed year with a warning. A year outside the data raises an error. The Gini adjustment applies in every case.
- **Start years before the GDP series:** with a reference year, the budget approaches need GDP at that year only, so `allocation_year` can go back to 1850. Without one, an allocation year before the GDP series raises an error.

Use it to replicate studies that fix capability at one year, or to hold the capability ranking constant. Year-by-year capability responds to projected convergence in GDP; a snapshot does not.
All-GHG runs derive the non-CO₂ pathway settings from the budget settings, and `capability_reference_year` passes through, so both gas parts use the same snapshot.

---

## income_floor

Only income **above** the floor counts toward capability. Income up to it is treated as necessary for basic human development.
The idea comes from the Greenhouse Development Rights framework ([Baer 2009](https://doi.org/10.1080/13668790903195495); [Baer 2013](https://doi.org/10.1002/wcc.201)), which was designed for burden-sharing. fair-shares uses its capability metric for entitlements.

**Default:** `income_floor=0.0` on every Gini-adjusted approach: all income counts. Applying the GDR threshold is a normative decision, so you pass it rather than the library assuming it.

[Baer 2013](https://doi.org/10.1002/wcc.201) used 7,500 per person per year on a 2005 price base and 8,500 on a 2010 base.
Give the floor in the price base of the GDP series. The default is constant 2021 international dollars, so convert a threshold from another price year first.

The Gini coefficient sets how much income lies above the floor; at a floor of 0 it has no effect.
Capability never falls below 20% of GDP, because `max_gini_adjustment` defaults to 0.8 ([Maximum Gini adjustment](allocations.md#maximum-gini-adjustment)).

`per-capita-adjusted-gini-budget`, capability only, `allocation_year=2020`:

| Country | floor=0 | floor=2500 | floor=5000 | floor=7500 | floor=10000 | floor=15000 | floor=20000 |
| ------- | ------- | ---------- | ---------- | ---------- | ----------- | ----------- | ----------- |
| USA     | 0.8%    | 0.3%       | 0.2%       | 0.2%       | 0.2%        | 0.2%        | 0.2%        |
| India   | 12.6%   | 6.1%       | 7.0%       | 10.3%      | 14.0%       | 13.4%       | 13.1%       |
| Germany | 0.2%    | 0.1%       | 0.0%       | 0.0%       | 0.0%        | 0.0%        | 0.0%        |

The capability metric behind the table, for the last GDP year (2025):

| Floor       | India capability as share of GDP | Median GDP per person (unadjusted) | India / median | Rows at the 20% cap (177 countries and rest-of-world) |
| ----------- | -------------------------------- | ---------------------------------- | -------------- | ------------------------------------------------------ |
| floor=0     | 100%                             | 17,255                             | 0.58           | 0 of 178                                               |
| floor=2500  | 75%                              | 17,255                             | 0.44           | 8 of 178                                               |
| floor=5000  | 51%                              | 17,255                             | 0.30           | 30 of 178                                              |
| floor=7500  | 30%                              | 17,255                             | 0.18           | 43 of 178                                              |
| floor=10000 | 20%                              | 17,255                             | 0.12           | 54 of 178                                              |
| floor=15000 | 20%                              | 17,255                             | 0.12           | 69 of 178                                              |
| floor=20000 | 20%                              | 17,255                             | 0.12           | 86 of 178                                              |

Capability is divided by the median of unadjusted GDP per capita, so raising the floor lowers each country's capability against a fixed yardstick.
Each country's capability factor rises with the floor until the `max_gini_adjustment` cap binds (capability at 20% of GDP at the default 0.8), and then stays constant.
Shares are not monotonic: at low floors the poorest countries reach the cap first and their factors jump, so India's share falls; it then rises as its own capability falls, and drifts once it is capped while other countries' capability keeps falling.
Above about a 5,000 floor the cap level decides the result.

At a floor of 10,000:

| Country | max_gini_adjustment=0.8 (default) | 0.9  | 0.95 | no cap (1.0) |
| ------- | --------------------------------- | ---- | ---- | ------------ |
| USA     | 0.2%                              | 0.1% | 0.1% | 0.0%         |
| India   | 14.0%                             | 10.1% | 5.9% | 0.5%        |
| Germany | 0.0%                              | 0.0% | 0.0% | 0.0%         |

Results with a high floor depend on `max_gini_adjustment` as much as on the floor. Report both.

---

## historical_discount_rate

Weights earlier emissions less in the responsibility adjustment. Available on every `*-adjusted` family where `pre_allocation_responsibility_weight > 0`; not part of equal per capita accounting.

- `0.0` (default): every year counts equally
- `0.005`: 1850 emissions at about 43% weight relative to 2020
- `0.01`: 1850 emissions at about 18% weight

Early industrialisers (UK, Germany, USA) gain most. Countries whose emissions grew recently (China, India) change less, because their emissions sit in recent decades where the weights are near 1.0.

This parameter is contested. The physical argument: natural sinks remove CO2 over time, so older emissions contribute less to current concentrations [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7); [Van Den Berg 2020](https://doi.org/10.1007/s10584-019-02368-y). The moral counterargument: responsibility for harm does not decay with time, and discounting favours the countries most responsible for cumulative warming [Meyer 2013](https://chicagounbound.uchicago.edu/cjil/vol13/iss2/15/); [Shue 2015](https://doi.org/10.1515/mopp-2013-0009); [Caney 2009](https://doi.org/10.1080/17449620903110300). Any rate above 0.0 is a normative decision, not a technical one ([Historical emissions discounting](allocations.md#historical-emissions-discounting)).

---

## strict (convergence only)

Decides whether an infeasible convergence target raises an error (`True`, default) or gives an approximate result with warnings (`False`).
Infeasibility means no valid path exists within the allowed speed: the solver would need a long-run share below 0 or above 1.

`cumulative-per-capita-convergence-adjusted` from 2020, with `lamboll_2023` budgets turned into world pathways by the default generator:

| Budget | Weights (resp.:cap.) | `strict=True` | `strict=False` ratio: USA | India | Germany | Countries above target | Countries below target |
| ------ | -------------------- | ------------- | ------------------------- | ----- | ------- | ---------------------- | ---------------------- |
| 1.5°C, 50% | 0.0:0.0 | feasible | 1.00 | 1.00 | 1.00 | 0 | 0 |
| 2°C, 66%   | 0.5:0.5 | feasible | 1.00 | 1.00 | 1.00 | 0 | 0 |
| 1.5°C, 50% | 0.5:0.5 | raises `AllocationError` | 1.88 | 0.98 | 1.09 | 13 | 165 |

_Ratios are achieved over target cumulative share. Countries above 1.0 keep more than their target because their emissions cannot fall fast enough; every other country is scaled down to keep the world total._

Equity adjustments on a tight budget are the usual trigger. Strong responsibility weights, early allocation years, short horizons and a low `max_convergence_speed` add to it.
With `strict=False`, 13 high emitters overshoot (the USA reaches 1.88 times its target) and 165 countries and groups receive 2% less.
Treat `strict=False` as a diagnostic. Ratios well above 1.0 mean the configuration asks for a faster transition than convergence can deliver. Relax the weights, use a larger budget, or extend the horizon.

---

## Other parameters

<a id="max_deviation_sigma"></a><a id="preserve_allocation_year_shares-preserve_first_allocation_year_shares"></a><a id="convergence_method-convergence-only"></a><a id="max_convergence_speed-convergence-only"></a>

| Parameter | Default | Effect |
| --- | --- | --- |
| `max_deviation_sigma` | `None` | Clips adjusted allocations to within this many standard deviations of equal per capita. 1.0 is tight, 2.0 compresses extremes, 3.0 catches only extreme outliers. It materially affects the most and least adjusted countries, so disclose it. Examples and tests use 2.0 for illustration |
| `preserve_allocation_year_shares` / `preserve_first_allocation_year_shares` | `False` | `False` updates shares with population and GDP; growing populations gain share. `True` fixes them at the allocation year, which isolates the equity parameters from demographic projections. For budgets, `False` uses cumulative population from the allocation year and `True` the single-year population |
| `convergence_method` | `"minimum-speed"` | `minimum-speed` needs no other parameter and finds the least disruptive path. `sine-deviation` front-loads the adjustment and needs `convergence_year`; use it for questions about accelerated near-term transitions |
| `max_convergence_speed` | 0.9 | Up to 90% of the remaining gap can close in a year. Rarely tuned. A lower value can make targets infeasible: an error with `strict=True`, ratios away from 1.0 with `strict=False` |

---

## Weights and exponents

| Parameter | Default | Controls |
| --- | --- | --- |
| `pre_allocation_responsibility_weight` | 0.0 | Relative importance of responsibility. Both weights at 0.0: no adjustment |
| `capability_weight` | 0.0 | Relative importance of capability |
| `pre_allocation_responsibility_exponent` | 1.0 | Shape of the responsibility adjustment |
| `capability_exponent` | 1.0 | Shape of the capability adjustment |

Weights are relative, while each exponent shapes its own adjustment.
At 1.0 the adjustment factor is `1 / asinh(x / median(x))`. Above 1.0 it becomes convex: high emitters or wealthy countries are penalised disproportionately more, which puts into practice the argument that marginal emissions or income matter more at higher levels.
The default of 1.0 is the most transparent choice, and other values need explicit normative justification ([Shape parameters](allocations.md#adjustment-shape-parameters)).

### "If you want X, set Y" guide

| Goal | Parameters |
| --- | --- |
| Pure equal per capita | `pre_allocation_responsibility_weight=0.0, capability_weight=0.0` |
| Responsibility through cumulative accounting | Early `allocation_year` (e.g. 1990), no weight needed |
| Responsibility through rescaling | `pre_allocation_responsibility_weight=1.0`, `pre_allocation_responsibility_year` < `allocation_year` |
| Both mechanisms | Early `allocation_year` + `pre_allocation_responsibility_weight > 0` + `pre_allocation_responsibility_year` < `allocation_year` |
| Balanced CBDR-RC | `pre_allocation_responsibility_weight=0.5, capability_weight=0.5` |
| CBDR-RC at 0.7:0.3 | `pre_allocation_responsibility_weight=0.7, capability_weight=0.3` |
| Ability to pay only | `pre_allocation_responsibility_weight=0.0, capability_weight=1.0` |
| Stronger-than-linear rescaling | `pre_allocation_responsibility_weight=1.0, pre_allocation_responsibility_exponent=2.0` |

Rescaling needs `pre_allocation_responsibility_year < allocation_year`. When they are equal the window is empty and the weight has no effect.

Responsibility alone gives a polluter-pays framing. Capability alone gives common but differentiated responsibilities without historical accountability. High weights on both give very low allocations for developed countries.

---

## Sensitivity ranking

From the examples above (USA, India, Germany, `allocation_year=2020`):

1. **`allocation_year`**: moves remaining budgets by hundreds of GtCO2 and turns them negative (USA: +13.5 to -324.6 GtCO2).
2. **`pre_allocation_responsibility_weight`**: switching it on changes shares by 0.7 to 14.0 percentage points (Germany -0.7, USA -3.5, India -14.0). The absolute or per-capita metric decides how much India loses.
3. **`capability_weight`**: switching it on changes shares by 0.6 to 4.1 percentage points (Germany -0.6, USA -3.2, India -4.1).
4. **`income_floor`**: up to 6.5 percentage points (India -6.5 at 2,500, +1.4 at 10,000). The direction depends on `max_gini_adjustment`.
