# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags,-all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 405 — Fair-share targets for one region of countries
#
# For a model that covers one region, such as the EU, and has no data for the
# rest of the world. Notebooks 400 to 403 divide a budget between the regions of
# an IAMC file and need the whole world in that file. This notebook allocates
# the global budget between countries, using the country datasets that ship
# with fair-shares, and sums the countries of your region.
#
# You set:
#
# 1. your model's names and the gases it constrains (cell A),
# 2. the warming level and likelihood of the global budget, and the countries
#    in your region (cell B),
# 3. the allocation approaches and data sources (cell C).
#
# You get, per budget and approach, in your model's variable names, for the
# region and for each of its member countries:
#
# - a **CO2 budget**: one cumulative number, from the first year after the last
#   observed emissions (or your model's first year) to net-zero CO2;
# - with `"all-ghg"`, also a **non-CO2 pathway**: annual emissions of the
#   non-CO2 Kyoto gases, in CO2-equivalent with AR6 GWP100, to 2100;
# - with `"co2-ffi"`, also a **land-use condition**: the land-use CO2 under
#   which the fossil-only budget is a fair share.
#
# Every allocation approach is a choice between equity principles. See
# [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/)
# before choosing.

# %% [markdown]
# ---
# ## Settings
#
# | Cell | What | Who edits |
# | --- | --- | --- |
# | **A. Your model** | model, region and variable names; gases; land-use basis; first time step | **Everyone. Edit this.** |
# | **B. Budget and region** | warming level and likelihood; member countries | Check; change if your study needs other values |
# | **C. Advanced** | allocation approaches, units, data sources | Usually leave as is |
#
# Then **Run All**. Do not edit anything below "Run".

# %% [markdown]
# ### A. Your model — EDIT THIS
#
# `EMISSION_CATEGORY` picks the gases the result constrains:
#
# | `EMISSION_CATEGORY` | You get |
# | --- | --- |
# | `"co2"` (default) | a CO2 budget: fossil, industry and land-use CO2, cumulative to net zero |
# | `"co2-ffi"` | a CO2 budget of fossil and industry CO2 only, plus the land-use condition it rests on (see "Land-use condition" below) |
# | `"all-ghg"` | the CO2 budget plus an annual non-CO2 pathway (CH4, N2O, F-gases; CO2-equivalent with AR6 GWP100) |
#
# Use `"co2-ffi"` for a model without land use, such as an energy-system model.
# Its `CO2_VARIABLE` is then the model's energy and industry CO2.
#
# `LAND_USE_BASIS` picks how land-use CO2 is counted. Models and national
# greenhouse gas inventories (NGHGI) count it differently: inventories count
# part of the natural land sink as a removal, models do not.
#
# | `LAND_USE_BASIS` | Land-use CO2 counted as | Use it to |
# | --- | --- | --- |
# | `"model"` (default) | bookkeeping models (Global Carbon Budget 2025), as integrated assessment and energy-system models count it | bound your model's own CO2 |
# | `"inventory"` | national inventories (LULUCF Data Hub v4) | compare with inventory-based targets, such as the EU Climate Law |
#
# The whole run follows the choice: country history, the global budget (no
# inventory correction on the model basis) and the scenario data behind it.
# A `"co2-ffi"` budget holds no land use, so the choice does not change it.
#
# `FIRST_MODEL_TIMESTEP` and `TIMESTEP_LENGTH` describe your model's first
# period, labelled by its last year: 2030 with 5-year steps covers 2026-2030.
# The budget is given from the first year of that period. Observed emissions
# inside the period are added back; unobserved years before it are subtracted,
# each at the last observed year's value.

# %%
# ── A. YOUR MODEL — EDIT THIS ────────────────────────────────────────────────

IAMC_MODEL = "PRIMES"  # your model's name, as in its IAMC files
IAMC_REGION = "EU27"  # your model's region name, as in its IAMC files

EMISSION_CATEGORY = "co2"  # "co2" (default) or "all-ghg"
CO2_VARIABLE = "Emissions|CO2"  # your model's variable for the CO2 the budget bounds
LAND_USE_BASIS = "model"  # "model" (default) or "inventory"

FIRST_MODEL_TIMESTEP = 2030  # label of your model's first period (its last year)
TIMESTEP_LENGTH = 5  # years per period

# "all-ghg" only: uncomment these two lines and set them.
# NON_CO2_VARIABLE = "Emissions|Kyoto Gases (excl. CO2) (AR6-GWP100)"  # your variable
# NONCO2_DEBT_MODES = ["report-only", "co2-debit"]  # see note in cell C

# %% [markdown]
# ### B. Budget and region — CHECK
#
# `RCB_SOURCE` picks the published global budget set; each pair in
# `TEMPERATURE_LIKELIHOOD` is a warming level (°C) and the likelihood of
# staying below it. Each pair becomes its own set of scenarios.
#
# Budgets are published from different years. The run first prints the budget
# options: every published budget counted from 2020, globally on the model
# basis including international aviation and shipping, and as allocated to
# countries, with the selected ones marked. They are also saved as
# budget_options_from_2020.csv with the results.
# The default brackets a global budget of 800 Gt CO2 from 2020 (all CO2,
# including international aviation and shipping), which no published budget
# matches: `forster_2026` 1.7°C 50% is 748 Gt from 2020 and 2°C 90% is 848 Gt.
# Each runs as its own scenario set.
# The run stops and lists the available pairs if one is not published by the
# source.
#
# Sources: `forster_2026` (IGCC 2025, default), `forster_2024` (IGCC 2023),
# `ar6_wg1_2021` (AR6 WGI), `lamboll_2023` (peak warming; the others measure
# warming at net-zero CO2).

# %%
# ── B. BUDGET AND REGION — CHECK ─────────────────────────────────────────────

RCB_SOURCE = "forster_2026"
# 748 and 848 Gt CO2 from 2020 (model basis, incl. bunkers)
TEMPERATURE_LIKELIHOOD = [(1.7, 0.5), (2, 0.9)]

REGION_NAME = "EU27"
# fmt: off
REGION_COUNTRIES = [
    "AUT", "BEL", "BGR", "CYP", "CZE", "DEU", "DNK", "ESP", "EST", "FIN",
    "FRA", "GRC", "HRV", "HUN", "IRL", "ITA", "LTU", "LUX", "LVA", "MLT",
    "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "SWE",
]
# fmt: on

# %% [markdown]
# ### C. Allocation approaches and data sources
#
# The allocation approaches are equity choices: the defaults cover three
# principles and one combination. Equal cumulative per capita allocates from
# 2015 (ECPC 2015); the responsibility and capability approaches allocate from
# 2020 and count responsibility for emissions from 2015, so all four hold a
# region accountable from the same year. Responsibility is per capita
# (emissions per person since 2015): absolute responsibility divides by a
# country's total emissions, which favours small countries for their size and
# makes a region's total depend on how it splits into countries. Change
# them to test other principles; see
# [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/).
# The form is that of notebook 301: lists expand as cross-products. Vary one of
# `cumulative_end_year`, functional forms or `capability_reference_year` at a
# time; the run stops if two results cannot be told apart.
#
# `NONCO2_DEBT_MODES` (cell A, `all-ghg` only) settles past non-CO2 over-use:
# `report-only` leaves the CO2 budget as it is; `co2-debit` subtracts the
# over-use from it. Each mode is its own scenario. Equating past methane with
# future CO2 rests on GWP100, an accounting convention.

# %%
# ── C. ALLOCATION APPROACHES AND DATA SOURCES ───────────────────────────────────

ALLOCATIONS = {
    # Equal cumulative per capita from 2015 (ECPC 2015)
    "equal-per-capita-budget": [
        {"allocation_year": [2015], "preserve_allocation_year_shares": [False]},
    ],
    "per-capita-adjusted-budget": [
        # Responsibility for emissions since 2015, allocated from 2020
        {
            "allocation_year": [2020],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [2015],
            "pre_allocation_responsibility_per_capita": [True],
            "preserve_allocation_year_shares": [False],
        },
        # Capability (GDP per capita), allocated from 2020
        {
            "allocation_year": [2020],
            "capability_weight": [1.0],
            "preserve_allocation_year_shares": [False],
        },
    ],
    # Responsibility (0.4, per capita since 2015) and capability (0.6, income
    # above a development threshold of 7,500 dollars per person), from 2020
    "per-capita-adjusted-gini-budget": [
        {
            "allocation_year": [2020],
            "pre_allocation_responsibility_weight": [0.4],
            "pre_allocation_responsibility_year": [2015],
            "pre_allocation_responsibility_per_capita": [True],
            "capability_weight": [0.6],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "preserve_allocation_year_shares": [False],
        },
    ],
}

IAMC_SCENARIO_PREFIX = "effort-sharing"  # runs are named "<prefix>|<budget>|<approach>"
CO2_MAGNITUDE = "Gt"  # CO2 budget in "Gt" or "Mt"; the non-CO2 pathway is Mt/yr
OUTPUT_LABEL = "405_eu27"  # results go to output/<OUTPUT_LABEL>/

# Data sources (the fair-shares defaults). The land-use source follows
# LAND_USE_BASIS in cell A.
active_sources = {
    "target": "rcbs",
    "emissions": "primap-202609",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "wdi-2025",
}
LULUCF_SOURCES = {"model": "gcb-2025-luc", "inventory": "melo-2026-v4"}

# %% [markdown]
# ---
# ## Run — DO NOT EDIT BELOW
#
# Run All from here. Every setting is in cells A to C above.

# %%
# Check the configuration, run the data pipeline, pick the budgets
import pandas as pd
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.notebook_helpers import (
    load_allocation_data,
    run_all_allocations,
)
from fair_shares.library.python_api import (
    compute_remaining_budgets,
    filter_to_anchors,
    land_use_condition,
    member_targets,
    period_means,
    regional_observed_emissions,
    regional_targets,
    shift_to_period_start,
)
from fair_shares.library.utils import setup_data
from fair_shares.library.utils.data.config import (
    is_composite_category,
    validate_data_source_config,
)

project_root = here()
composite = is_composite_category(EMISSION_CATEGORY)

# The all-GHG settings are commented out in the configuration by default.
NON_CO2_VARIABLE = globals().get("NON_CO2_VARIABLE")
NONCO2_DEBT_MODES = globals().get("NONCO2_DEBT_MODES", [])

fossil_only = EMISSION_CATEGORY == "co2-ffi"

if EMISSION_CATEGORY not in ("co2", "co2-ffi", "all-ghg"):
    raise ConfigurationError(
        'EMISSION_CATEGORY must be "co2", "co2-ffi" or "all-ghg", '
        f"got {EMISSION_CATEGORY!r}"
    )
if LAND_USE_BASIS not in LULUCF_SOURCES:
    raise ConfigurationError(
        f'LAND_USE_BASIS must be "model" or "inventory", got {LAND_USE_BASIS!r}'
    )
active_sources["lulucf"] = LULUCF_SOURCES[LAND_USE_BASIS]
ACCOUNTING_BASIS = {
    "model": "fossil, industry and land-use CO2; land use as bookkeeping models "
    "count it (model basis, GCB 2025)",
    "inventory": "fossil, industry and land-use CO2; land use as national "
    "inventories count it (NGHGI basis, LULUCF Data Hub v4)",
}[LAND_USE_BASIS]
if fossil_only:
    ACCOUNTING_BASIS = (
        "fossil and industry CO2 only; land-use CO2 is outside the budget, "
        "under the land-use condition"
    )

PERIOD_START = FIRST_MODEL_TIMESTEP - TIMESTEP_LENGTH + 1
MODEL_YEARS = list(range(FIRST_MODEL_TIMESTEP, 2101, TIMESTEP_LENGTH))
print(
    f"First model period: {PERIOD_START}-{FIRST_MODEL_TIMESTEP}; "
    f"budget from {PERIOD_START}"
)

validation = validate_data_source_config(EMISSION_CATEGORY, active_sources)
if not validation["valid"]:
    raise ConfigurationError(
        "Configuration errors:\n" + "\n".join(f"  - {i}" for i in validation["issues"])
    )
if not CO2_VARIABLE:
    raise ConfigurationError("Set CO2_VARIABLE")
if composite and not NON_CO2_VARIABLE:
    raise ConfigurationError(
        f"{EMISSION_CATEGORY} has a non-CO2 pathway: uncomment and set NON_CO2_VARIABLE"
    )
if composite and not NONCO2_DEBT_MODES:
    raise ConfigurationError("List at least one of NONCO2_DEBT_MODES")

anchors = [(f"{t:g}C", float(p)) for t, p in TEMPERATURE_LIKELIHOOD]

setup_info = setup_data(
    project_root=project_root,
    emission_category=EMISSION_CATEGORY,
    active_sources=active_sources,
    harmonisation_year=2020 if composite else None,
    verbose=False,
)
processed_dir = setup_info["paths"]["processed_dir"]
final_categories = setup_info["final_categories"]
co2_part = final_categories[0]

loaded_data = load_allocation_data(
    processed_dir=processed_dir,
    target="rcbs",
    final_categories=final_categories,
    emission_category=setup_info["emission_category"],
)
# Budget options: every published budget of this run's CO2 category, counted
# from 2020, so a budget fixed elsewhere (e.g. a protocol's "800 Gt from 2020")
# can be matched to a label. Two columns from 2020:
# - global, model basis, incl. bunkers: the published budget plus observed
#   global net CO2 from 2020 to its baseline (Global Carbon Budget 2025: fossil
#   CO2, bookkeeping land use, international aviation and shipping). This is
#   the total a global model's cumulative CO2 constraint covers.
# - allocated to countries: this run's budget for the country allocation,
#   without international aviation and shipping and on this run's land-use
#   basis.
all_budgets = next(iter(loaded_data["rcbs_data"].values()))
GLOBAL_COL = "global from 2020, model basis, incl. bunkers (Gt)"
ALLOCATED_COL = (
    "allocated to countries from 2020, fossil only (Gt)"
    if fossil_only
    else f"allocated to countries from 2020, {LAND_USE_BASIS} basis (Gt)"
)
budget_options = pd.DataFrame(
    {
        "source": all_budgets["source"],
        "budget": [
            f"{c} {q:.0%}"
            for c, q in zip(all_budgets["climate-assessment"], all_budgets["quantile"])
        ],
        "published (Gt)": all_budgets["rcb_original_value"],
        "published from": all_budgets["baseline_year"],
        GLOBAL_COL: all_budgets["budget_2020_gt"].round(0).astype(int),
        ALLOCATED_COL: (all_budgets["rcb_2020_mt"] / 1000).round(0).astype(int),
        "selected": [
            "<<" if s == RCB_SOURCE and (c, float(q)) in anchors else ""
            for s, c, q in zip(
                all_budgets["source"],
                all_budgets["climate-assessment"],
                all_budgets["quantile"],
            )
        ],
    }
).sort_values(["source", GLOBAL_COL])
print("Budget options (global CO2 budgets, Gt CO2, counted from the start of 2020)\n")
print(budget_options.to_string(index=False))
print()

filter_to_anchors(loaded_data, RCB_SOURCE, anchors)
print(f"\nCO2 budget covers {ACCOUNTING_BASIS}")
print(f"CO2 budget -> {CO2_VARIABLE}")
if composite:
    print(f"Non-CO2 pathway (AR6 GWP100) -> {NON_CO2_VARIABLE}")

# %%
# Country allocations, remaining budgets, and the region's targets
data_context = {
    "source-id": setup_info["source_id"],
    "allocation-folder": OUTPUT_LABEL,
    "emission-category": setup_info["emission_category"],
    "target-source": "rcbs",
    "emissions-source": active_sources["emissions"],
    "gdp-source": active_sources["gdp"],
    "population-source": active_sources["population"],
    "gini-source": active_sources["gini"],
    "lulucf-source": active_sources.get("lulucf", "none"),
}
_manifest, allocations_absolute = run_all_allocations(
    allocations=ALLOCATIONS,
    loaded_data=loaded_data,
    output_dir=None,
    data_context=data_context,
    target="rcbs",
    final_categories=final_categories,
    harmonisation_year=setup_info["config"].harmonisation_year,
    write=False,
    return_allocations=True,
)
remaining = compute_remaining_budgets(
    EMISSION_CATEGORY, allocations_absolute, processed_dir
)
print(
    f"\nObserved emissions netted through {remaining['netting-end-year'].max()}; "
    f"budgets run from {remaining['remaining-from-year'].min()}."
)

targets = regional_targets(
    remaining,
    allocations_absolute,
    REGION_COUNTRIES,
    REGION_NAME,
    nonco2_debt_modes=NONCO2_DEBT_MODES if composite else (),
)
observed = regional_observed_emissions(processed_dir, co2_part, REGION_COUNTRIES)
targets = shift_to_period_start(targets, PERIOD_START, observed)
members = member_targets(
    remaining,
    allocations_absolute,
    REGION_COUNTRIES,
    processed_dir,
    co2_part,
    PERIOD_START,
    nonco2_debt_modes=NONCO2_DEBT_MODES if composite else (),
)
from_year = int(targets["remaining-from-year"].iloc[0])
adjustment = targets["start-adjustment"].iloc[0]
estimated = targets["start-adjustment-estimated-years"].iloc[0]
if adjustment > 0:
    print(
        f"Added the region's observed CO2 for {PERIOD_START}-"
        f"{remaining['remaining-from-year'].min() - 1}: {adjustment:,.0f} Mt"
    )
elif adjustment < 0:
    print(
        f"Subtracted the region's CO2 before {PERIOD_START}: {-adjustment:,.0f} Mt"
        + (
            f"; years {estimated.replace(';', ', ')} not observed, held at "
            f"{int(observed.index.max())} ({observed.iloc[-1]:,.0f} Mt/yr)"
            if estimated
            else ""
        )
    )
year_cols = [c for c in targets.columns if str(c).isdigit()]

# %%
# Labels and summary tables
PARAM_PREFIXES = {
    "allocation-year": "ay",
    "pre-allocation-responsibility-weight": "rw",
    "pre-allocation-responsibility-year": "hr",
    "capability-weight": "cw",
    "pre-allocation-responsibility-exponent": "re",
    "capability-exponent": "ce",
}


def _budget_label(row):
    return f"{RCB_SOURCE} {row['climate-assessment']} {row['quantile']:.0%}"


def _approach_label(row):
    params = [
        f"{prefix}{row[col]:g}"
        if isinstance(row[col], float)
        else f"{prefix}{row[col]}"
        for col, prefix in PARAM_PREFIXES.items()
        if col in row and pd.notna(row[col]) and row[col] != 0
    ]
    per_capita = row.get("pre-allocation-responsibility-per-capita")
    if pd.notna(per_capita) and bool(per_capita):
        params.append("rpc")
    return " ".join([row["approach"].removesuffix("-budget"), *params])


co2_scale = {"Gt": 1e-3, "Mt": 1.0}[CO2_MAGNITUDE]
co2_unit = f"{CO2_MAGNITUDE} CO2"


def _label(df):
    df = df.copy()
    df["budget"] = df.apply(_budget_label, axis=1)
    df["allocation"] = df.apply(_approach_label, axis=1)
    df["scenario"] = [
        "|".join([IAMC_SCENARIO_PREFIX, b, a, *([m] if composite else [])])
        for b, a, m in zip(df["budget"], df["allocation"], df["nonco2-debt-mode"])
    ]
    df["co2-budget-out"] = df["co2-budget"] * co2_scale
    return df


targets = _label(targets)
members = _label(members)
member_sum = members.groupby("scenario")["co2-budget"].sum()
mismatch = (member_sum - targets.set_index("scenario")["co2-budget"]).abs().max()
if mismatch > 1e-6:
    raise ValueError(f"Members do not sum to {REGION_NAME}: off by {mismatch} Mt")

columns = ["budget", "nonco2-debt-mode"] if composite else "budget"
print(
    f"{REGION_NAME} CO2 budget from {from_year} to net-zero CO2, {co2_unit} "
    "(negative = allocation already used up):\n"
)
print(
    targets.pivot_table(
        index="allocation", columns=columns, values="co2-budget-out", aggfunc="first"
    )
    .round(1 if CO2_MAGNITUDE == "Gt" else 0)
    .to_string()
)
for budget, rows in members.groupby("budget"):
    if composite:
        rows = rows[rows["nonco2-debt-mode"] == rows["nonco2-debt-mode"].iloc[0]]
    print(f"\nMember states, CO2 budget from {from_year}, {co2_unit}, {budget}:\n")
    print(
        rows.pivot_table(
            index="iso3c",
            columns="allocation",
            values="co2-budget-out",
            aggfunc="first",
        )
        .round(2 if CO2_MAGNITUDE == "Gt" else 0)
        .to_string()
    )
if composite:
    one_mode = targets[
        targets["nonco2-debt-mode"] == targets["nonco2-debt-mode"].iloc[0]
    ]
    show = [y for y in ("2030", "2040", "2050") if y in year_cols]
    print(
        f"\n{REGION_NAME} non-CO2 pathway, Mt CO2e/yr (AR6 GWP100), "
        f"and past over-use charged under co2-debit, Mt CO2e:\n"
    )
    print(
        one_mode.set_index(["budget", "allocation"])[[*show, "nonco2-overuse"]]
        .round(0)
        .to_string()
    )

# %%
# Charts: CO2 budget per allocation; non-CO2 pathways
import matplotlib.pyplot as plt

co2_table = targets.pivot_table(
    index="allocation", columns=columns, values="co2-budget-out", aggfunc="first"
)
ax = co2_table.plot.barh(figsize=(9, 1.2 + 0.6 * len(co2_table)), width=0.8)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_xlabel(f"{REGION_NAME} CO2 budget from {from_year} ({co2_unit})")
ax.set_ylabel("")
plt.tight_layout()
plt.show()

if composite:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for _, row in one_mode.iterrows():
        ax.plot(
            [int(y) for y in year_cols],
            row[year_cols].astype(float),
            label=f"{row['budget']} | {row['allocation']}",
        )
    ax.set_ylabel("Mt CO2e/yr (AR6 GWP100)")
    ax.set_title(f"{REGION_NAME} non-CO2 pathway")
    ax.legend(fontsize=7, loc="upper right")
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ### Land-use condition (`"co2-ffi"` only)
#
# A published budget covers all CO2, land use included. The fossil-only budget
# removes the projected global land-use CO2 from the budget's first year to
# net zero, counted as bookkeeping models count it. When the scenarios project
# a net sink, the precautionary cap counts it as zero, so the world's fossil
# budget takes no credit for future land sinks.
#
# The fossil budget of a region or member is therefore a fair share only if
# its own land-use CO2, on the bookkeeping basis, nets to at most its
# **allowance** over those years: its share of the global allocation times the
# removed term, so zero under the cap. A net source above the allowance must
# come off the fossil budget; a sink beyond it is not counted.
#
# The condition asks for a real net sink in four cases:
#
# 1. **Inventory accounting.** National inventories also count indirect uptake
#    on managed land, mostly CO2 fertilisation, which the global budget counts
#    as part of the climate response. Meeting the allowance on the bookkeeping
#    basis means holding an inventory sink of about the indirect gap (column
#    "inventory equivalent"). An inventory sink is not spare fossil budget.
# 2. **Residual fossil CO2 at net zero.** The budget runs to net-zero CO2. A
#    model whose energy and industry CO2 stays above zero at that point, netted
#    against land, needs a bookkeeping land sink of that size on top.
# 3. **No precautionary cap.** With the cap off, the global fossil budget gains
#    the projected sink, and each area's allowance becomes its share of that
#    sink: a negative allowance, a net sink the area must deliver.
# 4. **A fair share already used up.** When the budget is negative, keeping to
#    it needs net-negative emissions. On a fossil-only budget a land sink
#    cannot supply them; use `"co2"`, where land use counts.
#
# Members' sources and sinks offset each other in the region's total, so check
# the members as well as the region. Observed land-use CO2 on both bases comes
# from the two `"co2"` runs (Global Carbon Budget 2025 bookkeeping, LULUCF Data
# Hub v4 inventories).

# %%
# Land-use condition of the fossil-only budget, per region and member
land = None
if fossil_only:
    land_dirs = {
        basis: setup_data(
            project_root=project_root,
            emission_category="co2",
            active_sources={**active_sources, "lulucf": LULUCF_SOURCES[basis]},
            verbose=False,
        )["paths"]["processed_dir"]
        for basis in ("model", "inventory")
    }
    areas = {REGION_NAME: REGION_COUNTRIES, **{c: [c] for c in REGION_COUNTRIES}}
    land = land_use_condition(
        pd.concat([targets, members], ignore_index=True),
        remaining,
        next(iter(loaded_data["rcbs_data"].values())),
        areas,
        bookkeeping_dir=land_dirs["model"],
        inventory_dir=land_dirs["inventory"],
    )

    def _range(row, stat):
        return (
            f"{row[f'{stat}-median']:,.0f} ({row[f'{stat}-min']:,.0f} to "
            f"{row[f'{stat}-max']:,.0f})"
        )

    for budget, rows in land.groupby("budget"):
        first = rows.iloc[0]
        print(
            f"\n{budget}: global land-use CO2 removed from the budget, "
            f"{first['land-from-year']}-{first['land-to-year']:.0f}: "
            f"{first['land-term-removed-mt'] / 1000:,.1f} Gt"
            + (
                " (the scenarios project a net sink; the precautionary cap "
                "counts it as zero)"
                if first["land-term-removed-mt"] == 0
                else ""
            )
        )
        allowance = rows.pivot_table(
            index="iso3c",
            columns="allocation",
            values="land-allowance-mt-per-yr",
            aggfunc="first",
        ).reindex(list(areas))
        if (allowance == 0).all().all():
            print("Allowance: 0 Mt/yr for every area and approach.")
        else:
            print("Allowance, bookkeeping land-use CO2, Mt/yr:\n")
            print(allowance.round(0).to_string())
    observed_table = (
        land.drop_duplicates("iso3c")
        .set_index("iso3c")
        .reindex(list(areas))
        .apply(
            lambda row: pd.Series(
                {
                    "bookkeeping": _range(row, "bookkeeping-observed"),
                    "inventory": _range(row, "inventory-observed"),
                    "indirect gap": _range(row, "indirect-gap"),
                }
            ),
            axis=1,
        )
    )
    print(
        f"\nObserved land-use CO2, {land['land-observed-years'].iloc[0]}, Mt/yr, "
        "median (min to max). Inventory equivalent of the allowance = "
        "allowance + indirect gap:\n"
    )
    print(observed_table.to_string())

# %%
# Export: tidy CSV with every column, IAMC files in your model's names
import pyam

out_dir = project_root / "output" / OUTPUT_LABEL
out_dir.mkdir(parents=True, exist_ok=True)

budget_options_path = out_dir / "budget_options_from_2020.csv"
budget_options.to_csv(budget_options_path, index=False)

# The region under IAMC_REGION, each member under its ISO3 code
all_targets = pd.concat(
    [targets.assign(region=IAMC_REGION), members.assign(region=members["iso3c"])],
    ignore_index=True,
)
csv_path = out_dir / f"{REGION_NAME}_targets.csv"
all_targets.drop(columns=["co2-budget-out"]).to_csv(csv_path, index=False)
if land is not None:
    land_path = out_dir / f"{REGION_NAME}_land_use_condition.csv"
    land.drop(columns=["co2-budget-out"]).to_csv(land_path, index=False)


def _iamc(values: pd.DataFrame) -> pyam.IamDataFrame:
    """CO2 budget rows plus non-CO2 rows (year columns of ``values``)."""
    co2_rows = pd.DataFrame(
        {
            "model": IAMC_MODEL,
            "scenario": values["scenario"],
            "region": values["region"],
            "variable": CO2_VARIABLE,
            "unit": co2_unit,
            "year": from_year,
            "value": values["co2-budget-out"],
        }
    )
    frames = [co2_rows]
    nonco2_years = [c for c in values.columns if str(c).isdigit()]
    if composite:
        long = values[["scenario", "region", *nonco2_years]].melt(
            id_vars=["scenario", "region"], var_name="year", value_name="value"
        )
        long["year"] = long["year"].astype(int)
        frames.append(
            long.assign(
                model=IAMC_MODEL,
                variable=NON_CO2_VARIABLE,
                unit="Mt CO2e/yr",
            )
        )
    df = pyam.IamDataFrame(pd.concat(frames, ignore_index=True))

    meta_cols = [
        "source",
        "climate-assessment",
        "quantile",
        "approach",
        *[c for c in PARAM_PREFIXES if c in targets.columns],
        "netting-end-year",
        "remaining-from-year",
        "start-adjustment",
        "start-adjustment-estimated-years",
        "n-countries",
    ]
    if composite:
        meta_cols += ["nonco2-debt-mode", "nonco2-overuse", "nonco2-debt-paid"]
    meta = targets[meta_cols].copy()
    meta.index = pd.MultiIndex.from_arrays(
        [[IAMC_MODEL] * len(targets), targets["scenario"]], names=["model", "scenario"]
    )
    meta["co2-budget"] = (
        f"{CO2_VARIABLE}: cumulative {co2_unit} from the start of {from_year} to "
        "net-zero CO2"
    )
    meta["co2-accounting"] = ACCOUNTING_BASIS
    if fossil_only:
        meta["land-use-condition"] = (
            "each area's bookkeeping land-use CO2 nets to at most its allowance "
            f"(see {REGION_NAME}_land_use_condition.csv); a net source above it "
            "comes off the fossil budget"
        )
    meta["regions"] = f"{IAMC_REGION} and its members by ISO3 code"
    meta["first-model-period"] = f"{PERIOD_START}-{FIRST_MODEL_TIMESTEP}"
    if composite:
        meta["non-co2-pathway"] = f"{NON_CO2_VARIABLE}: annual Mt CO2e/yr (AR6 GWP100)"
    meta["countries"] = ";".join(REGION_COUNTRIES)
    meta["emission-category"] = EMISSION_CATEGORY
    for key, value in active_sources.items():
        meta[f"{key}-source"] = value
    for col in meta.columns:
        df.set_meta(meta[col], name=col)
    return df


annual_path = out_dir / f"{REGION_NAME}_targets_iamc.xlsx"
_iamc(all_targets).to_excel(annual_path)
print(f"Budget options:      {budget_options_path}")
print(f"Tidy table:          {csv_path}")
if land is not None:
    print(f"Land-use condition:  {land_path}")
print(f"IAMC, annual:        {annual_path}")

if composite:
    periods = period_means(
        all_targets[["scenario", "region", "co2-budget-out", *year_cols]],
        MODEL_YEARS,
        from_year,
    )
    period_path = out_dir / f"{REGION_NAME}_targets_iamc_model_periods.xlsx"
    _iamc(periods).to_excel(period_path)
    print(f"IAMC, model periods: {period_path}")

print(
    f"\nThe CO2 row ({co2_unit}, no '/yr') is cumulative from the start of "
    f"{from_year} to net-zero CO2, written at year {from_year}."
)
if composite:
    print("The non-CO2 rows are annual, Mt CO2e/yr with AR6 GWP100.")

# %%
