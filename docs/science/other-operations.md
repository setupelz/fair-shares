---
title: Data processing
description: Harmonisation, pathway generation, interpolation, unit conversion, validation and the analysis-country set
---

# Data processing

These operations prepare the data that the allocations read.
They carry no equity choice of their own.

**In short:**

- Scenario pathways are harmonised to historical data at an anchor year and then converge back to the scenario.
- A global budget can become a global annual pathway that reaches zero in 2100 and sums exactly to the budget.
- Gaps in timeseries are interpolated, and units are standardised.
- Validation checks the structure of every dataset and that analysis countries plus rest of world equal the world total.
- A country enters the analysis when its data are complete. Every other country joins rest of world.

---

## Scenario harmonisation {#scenario-harmonisation}

Harmonisation aligns emission pathways with historical data at an anchor year, then converges back to the original scenario trajectory:

1. Years up to the anchor year take the historical values.
2. Years between the anchor year and the convergence year are linearly interpolated.
3. Years from the convergence year onward keep the original scenario values.

With `preserve_cumulative_peak=True`, a time-varying scaling keeps the peak cumulative emissions of the scenario.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/timeseries.py`

### Global pathways after net zero {#post-net-zero}

Some AR6 global pathways go net-negative: the world as a whole removes more CO₂ than it emits.
Negative global emissions have no meaningful split across countries.
Years after the global pathway crosses zero are therefore set to NaN and reported.
Years before net zero stay unchanged.
This step runs on global scenario pathways before allocation.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/dataframes.py::set_post_net_zero_emissions_to_nan`

---

## RCB pathway generation {#rcb-pathway-generation}

The `rcb-pathways` target turns the **global** remaining carbon budget into a **global** annual pathway.
Pathway approaches (e.g. `equal-per-capita`, `per-capita-adjusted`) then allocate that pathway among countries.

1. The inputs are the global budget (Mt CO₂) and current global emissions.
2. A normalised shifted exponential decay gives one global pathway.
3. The pathway starts at current global emissions and reaches exactly zero at the end year (default 2100).
4. The discrete annual sum equals the budget by construction.

The pathway shape sets no country net-zero years.
Those emerge from the allocation step.
A country whose allocated share nears zero reaches its implied net-zero year, which can be well before 2100.

??? info "Other pathway shapes"

    The default and only generator is `exponential-decay` (shifted exponential).
    The `generator` parameter accepts other functional forms (e.g. linear, sigmoid) without changes to the allocation pipeline.
    Each must satisfy the same constraint: the discrete annual sum equals the input budget by the end year.

**[API Reference →](../api/utils/math.md#rcb-pathway-generation)**

---

## Interpolation and units {#interpolation-and-units}

Interpolation fills missing values, linearly or stepwise.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/timeseries.py::interpolate_scenarios_data`

Unit conversion standardises units: emissions in kt, Mt or Gt CO₂e, population in millions.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/units.py`

---

## Data validation {#data-validation}

- **Timeseries validation** checks the structure (MultiIndex format) and the content (non-negative values, complete time series) of every dataset.
- **Cross-dataset validation** checks that analysis countries plus rest of world equal the world totals, and that the datasets align in time and space.

**[Implementation →](../api/utils/validation.md)** | `src/fair_shares/library/validation/pipeline_validation.py`

---

## Analysis countries and rest of world {#analysis-countries}

A country is an analysis country if it passes two tests:

1. **Completeness.** Each emissions category, GDP and population hold a value for the country in every year from 1990 to the last year of that dataset.
2. **Coverage rule (opt-in).** An emissions source can carry a `coverage` block in `data_sources_unified.yaml`. Only `gcb-2025` sets one: the country needs an emissions record before 1990 and population from 1850. A source without the block applies no extra test.

Countries that fail a test join rest of world (ROW).
The ROW rows are the world row minus the analysis countries.

The completeness test covers the years from 1990. An allocation can read earlier years: cumulative population from an early allocation year, a responsibility window or a capability snapshot or window.
An analysis country without a value in a year that one allocation reads joins ROW for that allocation only, and ROW is recomputed as the world total minus the remaining analysis countries.
The allocation records the moved countries in the `moved-to-row` column, and the log names each one with its missing years.
For example, the default population data start Ireland in 1950, so an allocation with per-capita responsibility from 1850 places Ireland in ROW.
An allocation function called directly, without ROW rows, raises an error that names the countries and years instead.

Gini does not decide membership.
An analysis country without a Gini value gets the analysis-country mean under the default `general.gini_missing_policy: fallback-mean`, and `country_data_coverage_summary.csv` records it as imputed.
The `strict` policy stops the run instead.

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/data/completeness.py`, `src/fair_shares/library/preprocessing/coverage.py`, `src/fair_shares/library/preprocessing/gini.py`

Under the default Gini source, 35 of 177 analysis countries in a PRIMAP v2.6.1 `co2-ffi` run carry an imputed Gini, Saudi Arabia among them.

### Global Carbon Budget processing {#gcb-processing}

The opt-in emissions source `gcb-2025` ([Data & licences](../user-guide/data-sources.md#global-carbon-budget-2025-opt-in)) follows these rules in `notebooks/101_data_preprocess_emiss_gcb-2025.py`:

- **Blank years count as zero.** The file leaves a year blank where it reports those emissions under another entity or reports none. Most blanks precede a country's first record. The GCB global total treats every blank as zero.
- **The world row excludes bunkers and the oil fires.** World row = GCB global total minus international shipping, international aviation and the 1991 Kuwaiti oil fires (478 Mt CO2). These three belong to no country. The run saves them to `emiss_co2-ffi_excluded_timeseries.csv`, so world row plus excluded rows equals the GCB global total in every year.
- **Rows outside the region mapping go to rest-of-world.** Kosovo and Antarctica have ISO codes that the region mapping lacks. "Pacific Islands (Palau)" (1955 to 1991, 4.43 Mt CO2 in total) and "Ryukyu Islands" (1965 to 1972, 0.82 Mt CO2 in total) have no ISO code. The official GCB workbook keeps both in its World column and in no country column, and this source does the same.
- **Bunkers come from the same file.** Every run deducts observed international shipping and aviation from this file (`gcb-2025` is the default `bunkers_source`). Notebook `108_data_preprocess_bunkers_gcb-2025` extracts them.
- **Coverage rule.** An analysis country needs an emissions record before 1990 and population for every year from 1850 (`coverage` in `data_sources_unified.yaml`). A blank in the raw file is not a record. The run saves each country's first recorded year to `emiss_co2-ffi_first_recorded_year.csv`. Eight countries have their first record in 1990 or later: Andorra, Lesotho and Tuvalu (1990), Namibia (1991), Micronesia, the Marshall Islands and Palau (1992) and Timor-Leste (1994). Their zero-filled values for 1850 to 1989 are all zero, and a responsibility adjustment over those years divides by zero. Macao has population data from 1950. These nine countries join rest-of-world in every allocation, so the country set is the same for every start year from 1850. Rest-of-world is the world row minus the analysis countries, so it takes their emissions, population and GDP. The column `coverage_rule_failed` in `country_data_coverage_summary.csv` names the failed test. Runs on the PRIMAP sources have no coverage rule and keep their country set.

With the default GDP and population sources, a `co2-ffi` run holds 168 analysis countries plus rest-of-world: the 177 of a PRIMAP v2.6.1 run minus these nine. A `co2` run with `melo-2026-v4` holds 160, because that land-use source has no series for eight more countries (Egypt, Hong Kong, Kiribati, Libya, the Maldives, Nauru, Qatar and Sierra Leone). World `co2-ffi` in 2020 is 34,319 Mt CO2 (PRIMAP v2.6.1: 34,343).

### World totals {#world-totals}

World totals feed the validation. The extraction accepts the keys "EARTH", "WLD" and "World".

**[Implementation →](../api/utils/core.md)** | `src/fair_shares/library/utils/data/completeness.py`

---

## See also

- **[Method overview](index.md)**: the full chain from published budget to national results
- **[API Reference](../api/index.md)**: function documentation
