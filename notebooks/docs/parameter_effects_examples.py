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
# # Parameter Effects Documentation Examples
#
# Generates every number in `docs/science/parameter-effects.md`.
#
# Run from the repository root:
#
#     uv run python notebooks/docs/parameter_effects_examples.py
#
# The script prints the data sources, the fair-shares version and one markdown
# table per page section. All examples use library defaults except the
# parameter each table varies.

# %%
import warnings

import numpy as np
import pandas as pd
from pyprojroot import here

import fair_shares
from fair_shares.library.allocations.budgets import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)
from fair_shares.library.allocations.coverage import (
    find_incomplete_countries,
    move_countries_to_row,
)
from fair_shares.library.allocations.pathways import (
    cumulative_per_capita_convergence_adjusted,
)
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import (
    calculate_budget_from_rcb,
    ensure_string_year_columns,
    setup_data,
)
from fair_shares.library.utils.math.allocation import calculate_gini_adjusted_gdp
from fair_shares.library.utils.math.pathways import generate_rcb_pathway_scenarios

warnings.filterwarnings("ignore", category=DeprecationWarning)
project_root = here()

# %% [markdown]
# ## Data sources
#
# The only block to edit when the library defaults change. Keep these keys
# equal to the defaults in `src/fair_shares/conf/data_sources/`, then rerun
# the script and paste its tables into the page.

# %%
# ---- DATA SOURCES (library defaults) ---------------------------------------
active_sources = {
    "target": "rcbs",
    "emissions": "primap-202609",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "wdi-2025",
    "lulucf": "melo-2026-v4",
}
emission_category = "co2-ffi"
rcb_source, rcb_scenario = "lamboll_2023", "1.5p50"
# -----------------------------------------------------------------------------

# %%
setup_info = setup_data(
    project_root=project_root,
    active_sources=active_sources,
    emission_category=emission_category,
    verbose=False,
)
processed_dir = setup_info["paths"]["processed_dir"]


def load_ts(name: str, index: list[str]) -> pd.DataFrame:
    """Load a processed timeseries CSV with string year columns."""
    df = pd.read_csv(processed_dir / name).set_index(index)
    return ensure_string_year_columns(df)


emissions_ts = load_ts(
    f"country_emissions_{emission_category}_timeseries.csv",
    ["iso3c", "unit", "emission-category"],
)
gdp_ts = load_ts("country_gdp_timeseries.csv", ["iso3c", "unit"])
population_ts = load_ts("country_population_timeseries.csv", ["iso3c", "unit"])
gini_ts = pd.read_csv(processed_dir / "country_gini_stationary.csv").set_index(
    ["iso3c", "unit"]
)
world_emissions_df = load_ts(
    f"world_emissions_{emission_category}_timeseries.csv",
    ["iso3c", "unit", "emission-category"],
)
rcbs_df = pd.read_csv(processed_dir / f"rcbs_{emission_category}.csv")
rcb_row = rcbs_df[
    (rcbs_df["source"] == rcb_source) & (rcbs_df["scenario"] == rcb_scenario)
]
rcb_value = float(rcb_row["rcb_2020_nghgi_mt"].iloc[0])

gdp_years = [int(c) for c in gdp_ts.columns if gdp_ts[c].notna().any()]
emiss_years = [int(c) for c in emissions_ts.columns]
groups = set(population_ts.index.get_level_values("iso3c"))
n_countries = len(groups - {"ROW"})

print("## Provenance\n")
print(f"- fair-shares version: {fair_shares.__version__}")
for key, value in active_sources.items():
    print(f"- {key}: {value}")
print(f"- emission category: {emission_category}")
print(f"- countries: {n_countries}, plus rest of world: {'ROW' in groups}")
print(f"- GDP years: {min(gdp_years)}-{max(gdp_years)}")
print(f"- emissions years: {min(emiss_years)}-{max(emiss_years)}")
print(
    f"- budget: {rcb_source} {rcb_scenario}, rebased to 2020: "
    f"{rcb_value / 1e3:.1f} GtCO2"
)
print()

countries = {"USA": "USA", "IND": "India", "DEU": "Germany"}


def shares_pct(result) -> pd.Series:
    """Cumulative allocation shares in percent, indexed by iso3c."""
    shares = result.relative_shares_cumulative_emission.iloc[:, 0]
    return shares.groupby(level="iso3c").sum() * 100


def print_table(header: list[str], rows: dict[str, list[str]]) -> None:
    """Print a markdown table with a Country column."""
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join("---" for _ in header) + "|")
    for name, cells in rows.items():
        print("| " + " | ".join([name, *cells]) + " |")
    print()


# %% [markdown]
# ## Example 1: allocation_year (remaining budget from 2020)

# %%
allocation_years = [2020, 1990, 1900]
remaining = {c: [] for c in countries}
moved_by_year = {}
for year in allocation_years:
    year_budget = calculate_budget_from_rcb(
        rcb_value=rcb_value,
        allocation_year=year,
        world_scenario_emissions_ts=world_emissions_df,
        verbose=False,
    )
    # As in run_allocation: a country without population from the year joins ROW.
    moved = list(
        find_incomplete_countries(
            {"population": population_ts}, [("population", year, None)]
        )
    )
    moved_by_year[year] = moved
    shares = shares_pct(
        equal_per_capita_budget(
            population_ts=move_countries_to_row(population_ts, moved),
            allocation_year=year,
            emission_category=emission_category,
        )
    )
    emiss_cols = [str(y) for y in range(year, 2020)]
    for c in countries:
        actual = (
            float(emissions_ts.loc[c][emiss_cols].sum(axis=1).iloc[0])
            if emiss_cols
            else 0.0
        )
        remaining[c].append((shares[c] / 100 * year_budget - actual) / 1e3)

print("## allocation_year\n")
print(f"Moved to rest of world: {moved_by_year}\n")
print_table(
    ["Country", *[f"allocation_year={y}" for y in allocation_years]],
    {countries[c]: [f"{v:+.1f} GtCO2" for v in remaining[c]] for c in countries},
)

# %% [markdown]
# ## Example 2: each adjustment in isolation

# %%


def adjusted(rw: float, cw: float, **kwargs) -> pd.Series:
    """Shares of per-capita-adjusted-budget at allocation_year=2020."""
    return shares_pct(
        per_capita_adjusted_budget(
            population_ts=population_ts,
            country_actual_emissions_ts=emissions_ts,
            gdp_ts=gdp_ts,
            allocation_year=2020,
            emission_category=emission_category,
            pre_allocation_responsibility_weight=rw,
            capability_weight=cw,
            pre_allocation_responsibility_year=1990,
            **kwargs,
        )
    )


base = adjusted(0.0, 0.0)
resp_abs = adjusted(1.0, 0.0)
resp_pc = adjusted(1.0, 0.0, pre_allocation_responsibility_per_capita=True)
cap = adjusted(0.0, 1.0)

print("## Pre-allocation responsibility only\n")
print_table(
    [
        "Country",
        "No adjustment (both=0)",
        "Responsibility only (default: absolute)",
        "Responsibility only (per capita)",
    ],
    {
        countries[c]: [f"{base[c]:.1f}%", f"{resp_abs[c]:.1f}%", f"{resp_pc[c]:.1f}%"]
        for c in countries
    },
)

print("## Capability only\n")
print_table(
    ["Country", "No adjustment (both=0)", "Capability only"],
    {countries[c]: [f"{base[c]:.1f}%", f"{cap[c]:.1f}%"] for c in countries},
)

# %% [markdown]
# ## Example 3: weight ratio

# %%
ratios = [(1.0, 0.0), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.0, 1.0)]
ratio_shares = [adjusted(rw, cw) for rw, cw in ratios]
print("## Weight ratio (responsibility:capability)\n")
print_table(
    ["Country", *[f"{rw:.1f}:{cw:.1f}" for rw, cw in ratios]],
    {countries[c]: [f"{s[c]:.1f}%" for s in ratio_shares] for c in countries},
)

# %% [markdown]
# ## Example 4: income_floor

# %%
income_floors = [0, 2500, 5000, 7500, 10000, 15000, 20000]


def gini_shares(floor: float, max_gini_adjustment: float = 0.8) -> pd.Series:
    """Shares of per-capita-adjusted-gini-budget, capability only, from 2020."""
    return shares_pct(
        per_capita_adjusted_gini_budget(
            population_ts=population_ts,
            country_actual_emissions_ts=emissions_ts,
            gdp_ts=gdp_ts,
            gini_s=gini_ts,
            allocation_year=2020,
            emission_category=emission_category,
            pre_allocation_responsibility_weight=0.0,
            capability_weight=1.0,
            income_floor=floor,
            max_gini_adjustment=max_gini_adjustment,
        )
    )


floor_shares = [gini_shares(floor) for floor in income_floors]
print("## income_floor\n")
print_table(
    ["Country", *[f"floor={f}" for f in income_floors]],
    {countries[c]: [f"{s[c]:.1f}%" for s in floor_shares] for c in countries},
)

# Capability per person, as share of GDP, against the median of unadjusted GDP
# per capita, and countries held at the max_gini_adjustment cap (default 0.8:
# capability >= 20% of GDP), last GDP year.
last = str(max(gdp_years))
gdp_last = gdp_ts[last].droplevel("unit") * 1e3  # billion -> million
pop_last = population_ts[last].droplevel("unit")
gini_last = gini_ts["gini"].droplevel("unit")
idx = gdp_last.dropna().index.intersection(pop_last.index).intersection(gini_last.index)
median_pc = (gdp_last[idx] / pop_last[idx]).median()
cap_rows = {}
for floor in income_floors:
    adj = calculate_gini_adjusted_gdp(
        gdp_last[idx].to_numpy(),
        gini_last[idx].to_numpy(),
        floor,
        pop_last[idx].to_numpy(),
        0.8,
    )
    adj_s = pd.Series(adj, index=idx)
    at_cap = int(np.sum(np.isclose(adj, 0.2 * gdp_last[idx].to_numpy())))
    if floor == 0:
        at_cap = 0
    india_frac = adj_s["IND"] / gdp_last["IND"]
    india_rel = adj_s["IND"] / pop_last["IND"] / median_pc
    cap_rows[f"floor={floor}"] = [
        f"{india_frac:.0%}",
        f"{median_pc:,.0f}",
        f"{india_rel:.2f}",
        f"{at_cap} of {len(idx)}",
    ]
print(f"## income_floor diagnostics ({last})\n")
print_table(
    [
        "Floor",
        "India capability as share of GDP",
        "Median GDP per person (unadjusted)",
        "India capability per person / median",
        "Countries and groups held at the cap",
    ],
    cap_rows,
)

# The cap level at a 10,000 floor (1.0: no cap).
cap_levels = [0.8, 0.9, 0.95, 1.0]
cap_shares = [gini_shares(10000, level) for level in cap_levels]
print("## max_gini_adjustment at income_floor=10000\n")
print_table(
    ["Country", *[f"max_gini_adjustment={level}" for level in cap_levels]],
    {countries[c]: [f"{s[c]:.1f}%" for s in cap_shares] for c in countries},
)

# %% [markdown]
# ## Example 5: strict (convergence pathways)

# %%
strict_configs = [
    ("1.5p50", 0.0, 0.0),
    ("2p66", 0.5, 0.5),
    ("1.5p50", 0.5, 0.5),
]
print("## strict\n")
print(
    "| Budget | Weights (responsibility:capability) | strict=True "
    "| strict=False: USA | India | Germany | Countries above target "
    "| Countries below target |"
)
print("|---|---|---|---|---|---|---|---|")
for scen, rw, cw in strict_configs:
    rcb_sel = rcbs_df[(rcbs_df["source"] == rcb_source) & (rcbs_df["scenario"] == scen)]
    pathway = generate_rcb_pathway_scenarios(
        rcb_sel, world_emissions_df, 2020, 2100, emission_category
    ).droplevel(["climate-assessment", "quantile", "source"])
    kwargs = dict(
        population_ts=population_ts,
        country_actual_emissions_ts=emissions_ts,
        gdp_ts=gdp_ts,
        first_allocation_year=2020,
        emission_category=emission_category,
        world_scenario_emissions_ts=pathway,
        pre_allocation_responsibility_weight=rw,
        capability_weight=cw,
    )
    try:
        cumulative_per_capita_convergence_adjusted(strict=True, **kwargs)
        strict_true = "feasible"
    except AllocationError:
        strict_true = "raises AllocationError"
    result = cumulative_per_capita_convergence_adjusted(strict=False, **kwargs)
    warns = result.country_warnings or {}
    values = {k: float(v.split(":")[1]) for k, v in warns.items()}
    ratio = {c: values.get(c, 1.0) for c in countries}
    above = sum(v > 1.0 for v in values.values())
    below = sum(v < 1.0 for v in values.values())
    print(
        f"| {rcb_source} {scen} | {rw:.1f}:{cw:.1f} | {strict_true} | "
        f"{ratio['USA']:.2f} | {ratio['IND']:.2f} | {ratio['DEU']:.2f} | "
        f"{above} | {below} |"
    )
print()

# %% [markdown]
# ## Example 6: historical_discount_rate weights

# %%
print("## historical_discount_rate (allocation_year=2020, reference year 2019)\n")
for rate in [0.005, 0.01]:
    print(
        f"- rate={rate}: weight of 1850 emissions = {(1 - rate) ** (2019 - 1850):.0%}"
    )
print()

# %% [markdown]
# ## Sensitivity summary

# %%
print("## Largest change for USA, India, Germany (percentage points)\n")
summary = {
    "pre_allocation_responsibility_weight (0 to 1)": resp_abs - base,
    "capability_weight (0 to 1)": cap - base,
    "income_floor (0 to 7500)": floor_shares[income_floors.index(7500)]
    - floor_shares[0],
    "income_floor (0 to 15000)": floor_shares[income_floors.index(15000)]
    - floor_shares[0],
}
for name, diff in summary.items():
    d = diff[list(countries)]
    print(f"- {name}: " + ", ".join(f"{countries[c]} {d[c]:+.1f}" for c in countries))
print()
