---
title: IAM model regions
description: Prepare an IAMC scenario file with notebook 400 and divide a budget or pathway between its model regions
---

# IAM model regions

Use this guide when your data is an IAMC-format scenario file and you want to divide a budget or a pathway between that model's regions.
For individual countries, use [Country fair shares](country-fair-shares.md).
For a model of one region, such as an EU-only model, see [One region of countries](#one-region-of-countries).

## 1. Prepare the scenario with notebook 400

`400_data_preprocess_scenario_for_allocation` reads your scenario, adds the history an allocation needs and writes `output/iamc/iamc_covered.xlsx`.
Notebooks 401, 402 and 403 read that file. They fail with a missing-file error if you skip notebook 400.

Set four values in the Config cell:

| Setting | What to give |
| --- | --- |
| `SCENARIO_FILE` | Your IAMC file. It points at the bundled MESSAGEix-GLOBIOM example by default, and notebook 400 runs on that example without error if you forget to change it. |
| `MODEL_NAME` | The model's name as it appears in [IAMconsortium/common-definitions](https://github.com/IAMconsortium/common-definitions), for example `MESSAGEix-GLOBIOM 2.1-R12`. The notebook reads the country-to-region mapping from there. |
| `EMISSION_CATEGORY` | `all-ghg-ex-co2-lulucf`, the only supported category. |
| `START_YEAR` | The first year of history to add, 1990 by default. It must be no later than your allocation year. |

Your file needs these variables for every model region:

- `Emissions|CO2|Energy and Industrial Processes`
- `Emissions|CH4`
- `Emissions|N2O`
- `Population`
- `GDP|PPP`

Notebook 400 adds CEDS-based regional emissions history, UN and OWID population and World Bank WDI GDP before your scenario starts.
It then builds `Emissions|Covered`: CO2 from energy and industry plus CH4 and N2O, weighted with AR6 GWP100, in Mt CO2e per year.
Land-use emissions are out of scope. F-gases exist in the historical source at World level only.
Expect a step at the join year between your model's output and the history.

**Region patches.** common-definitions can lack ISO3 codes that the CEDS history covers.
Add them to a region with `mapping.add_countries(...)`.
The example cell patches five small territories for the R12 regions. Remove or replace that cell for another model.

The output holds one model and one scenario. Notebook 400 labels every row with the first model and scenario name in your file, and interpolates all values to annual years.

## 2. Allocate

| Notebook | What it does |
| --- | --- |
| `402_example_iamc_budget_allocations` | Worked budget examples, one cumulative number per region. Runs unchanged. |
| `403_example_iamc_pathway_allocations` | Worked pathway examples, a value per region per year. Runs unchanged. |
| `401_custom_iamc_allocation` | Workspace you configure yourself, with export of a model-ready remaining budget. |

The regions are whatever your file holds. Read them from the file, because they often carry a model prefix such as `MESSAGEix-GLOBIOM 2.1-R12|Western Europe`:

```python
import pyam
from fair_shares.library.allocations.budgets.per_capita import equal_per_capita_budget
from fair_shares.library.utils.data.iamc import load_iamc_data

scenario = pyam.IamDataFrame("output/iamc/iamc_covered.xlsx")
regions = [r for r in scenario.region if r.lower() not in ("world", "global")]

data = load_iamc_data(
    data_file=scenario,
    population_variable="Population",
    gdp_variable="GDP|PPP",
    emissions_variable="Emissions|Covered",
    regions=regions,
    allocation_start_year=1990,
    budget_end_year=2100,
    expand_to_annual=True,
)

result = equal_per_capita_budget(
    population_ts=data["population"].rename_axis(index={"region": "iso3c"}),
    allocation_year=2015,
    emission_category="all-ghg-ex-co2-lulucf",
    preserve_allocation_year_shares=False,
    group_level="iso3c",
)
shares = result.relative_shares_cumulative_emission["2015"]
```

`per_capita_adjusted_budget` takes `gdp_ts=data["gdp"]` in the same way. The [Approach catalog](approach-catalog.md) lists the approaches.

`load_iamc_data` stops with an error when any region lacks a value in the start year or the end year.

## 3. Export a remaining budget for your model

Step 7 of notebook 401 turns a budget allocation into a remaining budget for a model run.
The global budget is the scenario's own cumulative `Emissions|Covered` from the allocation year to `MODEL_HORIZON_YEAR`.
Each region's remaining budget is its share of that total minus its emissions from the allocation year to the year before the first model period.
Those emissions come from `iamc_covered.xlsx`: history up to the scenario's first year, the scenario's own values after it.

IAM models label each period by its last year. In MESSAGEix with 5-year periods, timestep `2030` covers 2026 to 2030.
The remaining budget must start in the first year of the first period, so set `FIRST_MODEL_TIMESTEP` and `TIMESTEP_LENGTH`:

```
Remaining budget (from 2026) = allocation (from 2015) - emissions (2015 to 2025)
```

The notebook writes `iamc_remaining_budget_from_<year>_<approach>.csv` in Gt CO2e, for use as a cumulative emissions bound such as `bound_emission` in MESSAGEix.
Pathway allocations are already annual. Use their Step 6 export directly.

## Negative allocations

A negative remaining budget means the region's past emissions exceed its allocation.
It is an expected result for high historical emitters, for example under equal cumulative per capita from 1990 ([Negative allocation](../science/glossary.md#negative-allocation)).
In a model run it can call for a net-negative emissions target.
It does not prescribe timing or mechanism.
Keep negative values rather than clipping them to zero, so the result keeps that information [Pelz 2025a](https://doi.org/10.1073/pnas.2409316122); [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f).

## One region of countries

Notebooks 400 to 403 divide a budget between the regions of an IAMC file, so the file must cover the world.
A model of one region, such as an EU-only energy model, has no data for the rest of the world.
`405_one_region_remaining_budget` serves that case and needs no IAMC input.
It allocates the global budget between countries with the country datasets, then sums the countries of your region.

The settings are in three cells: **A. Your model** (everyone edits), **B. Budget and region** (check), **C. Advanced** (usually left as is).

### A. Your model

| Setting | What to give |
| --- | --- |
| `IAMC_MODEL`, `IAMC_REGION` | Your model's name and region name, as in its IAMC files. |
| `EMISSION_CATEGORY` | `co2` (default): a CO2 budget, cumulative to net-zero CO2, covering fossil, industry and land-use CO2. `all-ghg`: the same CO2 budget plus an annual non-CO2 pathway (CH4, N2O, F-gases; CO2-equivalent with AR6 GWP100). |
| `CO2_VARIABLE` | Your model's variable for the CO2 the budget bounds, for example `Emissions|CO2`. |
| `LAND_USE_BASIS` | `model` (default) or `inventory`; see below. |
| `FIRST_MODEL_TIMESTEP`, `TIMESTEP_LENGTH` | Your model's first period, labelled by its last year: `2030` with `5` covers 2026-2030. The budget is given from the first year of that period. |
| `NON_CO2_VARIABLE`, `NONCO2_DEBT_MODES` | `all-ghg` only, commented out by default. Your model's variable for the non-CO2 gases, and how past non-CO2 over-use is settled: `report-only` leaves the CO2 budget as it is, `co2-debit` subtracts the region's over-use (summed over the members that over-used). Each mode is its own scenario. |

**Land-use basis.** Models and national greenhouse gas inventories (NGHGI) count land-use CO2 differently: inventories count part of the natural land sink as a removal, models do not.

| `LAND_USE_BASIS` | Land-use source | The run then uses | Use it to |
| --- | --- | --- | --- |
| `model` (default) | `gcb-2025-luc`: bookkeeping models (GCB 2025 national land-use change), 1850-2024 | country history with bookkeeping land use; the global budget with no inventory correction, rebased with bookkeeping land use; scenario CO2 and Kyoto gases as reported | bound your model's own CO2 |
| `inventory` | `melo-2026-v4`: national inventories (LULUCF Data Hub v4), 2000-2024 | country history with inventory land use; the global budget corrected for the inventory-versus-model gap; NGHGI-adjusted scenario CO2 and Kyoto gases | compare with inventory-based targets, such as the EU Climate Law |

`gcb-2025-luc` is a manual download; `fair-shares fetch-data` prints the steps.

**First model period.** The budget is first netted with observed emissions through the last observed year. If the model's first period starts earlier, the region's observed emissions in the period are added back. If it starts later, the region's emissions in the years before it are subtracted; years without observed data take the last observed year's value, and the run and the output name those years.

### B. Budget and region

| Setting | What to give |
| --- | --- |
| `RCB_SOURCE`, `TEMPERATURE_LIKELIHOOD` | The published budget set and one or more (warming level, likelihood) pairs. Default `forster_2026`, `[(1.7, 0.5), (2, 0.9)]`: 748 and 848 Gt CO2 from 2020, bracketing a global budget of 800 Gt from 2020. The run prints every published budget counted from 2020, so you can match a budget fixed elsewhere, and stops with the available pairs if one is not published. |
| `REGION_NAME`, `REGION_COUNTRIES` | The region's name and its members' ISO3 codes. EU27 is preset. |

### C. Advanced

| Setting | What to give |
| --- | --- |
| `ALLOCATIONS` | Approaches and parameter grids, as in notebook 301. The non-CO2 pathway follows the same approach. The defaults cover equal per capita, responsibility since 1990, and capability. |
| `IAMC_SCENARIO_PREFIX`, `CO2_MAGNITUDE`, `OUTPUT_LABEL` | Scenario names, the CO2 budget in Gt or Mt, the output folder. |
| `active_sources` | The fair-shares default data sources. The land-use source follows `LAND_USE_BASIS`. |

### Outputs

In `output/<OUTPUT_LABEL>/`:

- `<REGION_NAME>_targets.csv`: every configuration column, the CO2 budget before and after the non-CO2 debit, the first-period adjustment, and the annual non-CO2 pathway.
- `<REGION_NAME>_targets_iamc.xlsx`: one scenario per budget, approach and debt mode. The CO2 row has unit `Gt CO2` (no `/yr`) and sits at the first year of the model's first period; the non-CO2 rows are annual, `Mt CO2e/yr`. The meta sheet records the land-use basis, the first model period, the parameters and the member countries.
- `<REGION_NAME>_targets_iamc_model_periods.xlsx`, for `all-ghg`: the same with the non-CO2 pathway as averages over the model's periods, labelled by their last year.

A member without data in the country sets is aggregated into rest of world; the run then stops and names it.
