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
# # 400 — Scenario preprocessing for allocation
#
# Entry point for the 400-series. Takes a raw IAM scenario (IAMC format),
# prepends CEDS-derived regional history for emissions and UN+OWID /
# World Bank WDI history for Population and GDP|PPP, and builds
# `Emissions|Covered`. Output is saved for `401`, `402`, `403` to consume.
#
# **Supported emission category**
#
# | category | components | output unit |
# |---|---|---|
# | `all-ghg-ex-co2-lulucf` | `Emissions\|CO2\|Energy and Industrial Processes` + `Emissions\|CH4` + `Emissions\|N2O` (GWP-weighted) | Mt CO2e/yr |
#
# LULUCF is out of scope. F-gases are only in the packaged historical source
# at World level (regional gap ~1 % pre-1990, ~4 % by 2020).
#
# ## Adding a new IAM
#
# You need:
#
# 1. An IAMC-format xlsx/csv with `Emissions|CO2|Energy and Industrial
#    Processes`, `Emissions|CH4`, `Emissions|N2O`, `Population`, `GDP|PPP`
#    for your model's regions.
# 2. The model's canonical name as it appears in
#    [IAMconsortium/common-definitions](https://github.com/IAMconsortium/common-definitions)
#    so `RegionMapping.from_common_definitions(MODEL_NAME)` can resolve the
#    country-to-region mapping.
# 3. If common-definitions is missing ISO3 codes that the CEDS country
#    history covers, patch them inline via `mapping.add_countries(...)`.
# 4. Expect a mismatch at the join year between raw IAM output and CEDS.

# %%
import warnings

import matplotlib.pyplot as plt
import pandas as pd
import pyam
from pyprojroot.here import here

from fair_shares.library.iamc_historical import (
    COVERED_COMPONENTS,
    RegionMapping,
    backfill_and_build_covered,
    backfill_population_gdp,
)
from fair_shares.library.utils.units import get_default_unit_registry

# %% [markdown]
# ## Config

# %%
EMISSION_CATEGORY = "all-ghg-ex-co2-lulucf"
MODEL_NAME = "MESSAGEix-GLOBIOM 2.1-R12"
START_YEAR = 1990       # back-fill to here
GWP = "AR6GWP100"       # can switch to AR4GWP100 for the older common-definitions convention

SCENARIO_FILE = here() / "data/scenarios/iamc_example/iamc_reporting_example.xlsx"
OUTPUT_FILE = here() / "output/iamc/iamc_covered.xlsx"

BLUE = "#005baa"
PLOT_MAX_REGIONS = 6

print(f"Category: {EMISSION_CATEGORY}")
print(f"Components: {COVERED_COMPONENTS[EMISSION_CATEGORY]}")

# %% [markdown]
# ## Region mapping
#
# Fetched live from `IAMconsortium/common-definitions` (CC0). For
# reproducibility in a pinned release, pass `ref="<commit-sha>"`.
#
# Common-definitions may not include every ISO3 code that the CEDS country
# history covers. If so, `mapping.add_countries(...)` patches the gaps
# inline. The block below is specific to the example model's R12 region
# set and can be removed or replaced when pointing at a different IAM.

# %%
mapping = RegionMapping.from_common_definitions(MODEL_NAME)

# Example-specific patches: five small territories missing from the R12
# common-definitions entry (<15 Mt CO2/yr combined). Remove or replace
# when swapping in your own model.
mapping.add_countries(
    f"{MODEL_NAME}|Latin America and the Caribbean", ["bes", "cuw", "sxm"]
)
mapping.add_countries(f"{MODEL_NAME}|Eastern Europe", ["kos"])
mapping.add_countries(f"{MODEL_NAME}|Sub-Saharan Africa", ["shn"])

print(
    f"Loaded {MODEL_NAME}: {len(mapping.regions)} regions, "
    f"{len(mapping.countries)} countries"
)

# %% [markdown]
# ## Load the scenario

# %%
scenario = pyam.IamDataFrame(SCENARIO_FILE)

print(
    f"Scenario: {len(list(scenario.region))} regions × "
    f"{len(list(scenario.variable))} vars × "
    f"{len(list(scenario.year))} years "
    f"({min(scenario.year)}–{max(scenario.year)})"
)

# %% [markdown]
# ## Back-fill emissions and build `Emissions|Covered`

# %%
out = backfill_and_build_covered(
    scenario,
    category=EMISSION_CATEGORY,
    region_mapping=mapping,
    start_year=START_YEAR,
    gwp=GWP,
    check_continuity=False,
)
print(f"Output years: {min(out.year)}–{max(out.year)}")
print(f"Output variables: {sorted(out.variable)}")
print(f"Output models: {sorted(out.model)}")

# %% [markdown]
# ## Back-fill Population and GDP|PPP
#
# Allocation notebooks need the full history span. The scenario typically 
# starts at the IAM's base year; UN+OWID population and World Bank WDI GDP 
# cover 1970+ at country level and aggregate up to the same regions via `mapping`.

# %%
socio = backfill_population_gdp(
    scenario,
    region_mapping=mapping,
    start_year=START_YEAR,
)
print(f"Socio-economic years: {min(socio.year)}–{max(socio.year)}")
print(f"Socio-economic variables: {sorted(socio.variable)}")

# %% [markdown]
# ## Visual check: join continuity and aggregation
#
# 1. **Join continuity** — each component (CO2|EIP, CH4, N2O) and
#    `Emissions|Covered` are plotted with history dashed, scenario solid.
#    Expect a step at the join year on the order of 5-25 %
# 2. **Aggregation consistency** — `Emissions|Covered` should equal an
#    independently-recomputed GWP-weighted sum of its components. Lines
#    must overlap.

# %%
PLOT_REGIONS = sorted(r for r in out.region if r != "World")[:PLOT_MAX_REGIONS]
scen_first_year = min(scenario.year)
spec = COVERED_COMPONENTS[EMISSION_CATEGORY]
plot_variables = list(spec["add"]) + list(spec["subtract"]) + ["Emissions|Covered"]

_ur = get_default_unit_registry()
_output_unit = str(spec["output_unit"])
with _ur.context(GWP):
    _unit_factor = {
        unit: float((1.0 * _ur(unit)).to(_output_unit).magnitude)
        for unit in set(out.data["unit"])
    }

fig, axes = plt.subplots(
    len(PLOT_REGIONS), 1, figsize=(10, 2.4 * len(PLOT_REGIONS)), sharex=True
)
if len(PLOT_REGIONS) == 1:
    axes = [axes]

for ax, region in zip(axes, PLOT_REGIONS, strict=True):
    for variable in plot_variables:
        series = out.filter(region=region, variable=variable).data.sort_values("year")
        if series.empty:
            continue
        series = series.assign(
            value_co2e=series["value"] * series["unit"].map(_unit_factor)
        )
        hist_part = series[series["year"] < scen_first_year]
        scen_part = series[series["year"] >= scen_first_year]
        (line,) = ax.plot(
            hist_part["year"], hist_part["value_co2e"], linestyle="--", alpha=0.7
        )
        ax.plot(
            scen_part["year"], scen_part["value_co2e"],
            linestyle="-", color=line.get_color(), label=variable,
        )
    ax.axvline(scen_first_year, color="grey", linewidth=0.6, alpha=0.5)
    ax.axhline(0, color="black", linewidth=0.4, alpha=0.4)
    ax.set_title(region.split("|", 1)[1], fontsize=10)
    ax.set_ylabel("Mt CO2e/yr")
    ax.grid(alpha=0.3)
axes[0].legend(loc="upper left", fontsize=8, frameon=False)
axes[-1].set_xlabel("Year")
fig.suptitle(
    f"Components and Covered for {EMISSION_CATEGORY}  —  "
    f"dashed=history, solid=scenario, grey line=join year ({scen_first_year})",
    fontsize=10,
)
fig.tight_layout()
plt.show()

# %% [markdown]
# ### Aggregation check

# %%
def _recompute_covered_per_region(idf, category: str, region: str) -> pd.DataFrame:
    """GWP-weighted independent recompute, mirroring build_covered."""
    spec = COVERED_COMPONENTS[category]
    output_unit = spec["output_unit"]
    long = idf.filter(region=region).data
    ur = get_default_unit_registry()
    with ur.context(GWP):
        factors = {
            variable: float((1.0 * ur(unit)).to(output_unit).magnitude)
            for variable, unit in (
                long.drop_duplicates(subset=["variable", "unit"])
                .set_index("variable")["unit"]
                .to_dict()
                .items()
            )
            if variable in (spec["add"] + spec["subtract"])
        }
    converted = long[long["variable"].isin(spec["add"] + spec["subtract"])].copy()
    converted["value"] = converted["value"] * converted["variable"].map(factors)
    wide = converted.pivot_table(
        index="year", columns="variable", values="value", aggfunc="first"
    )
    total = wide[spec["add"]].sum(axis=1)
    if spec["subtract"]:
        total = total - wide[spec["subtract"]].sum(axis=1)
    return total.reset_index(name="recomputed")


fig2, axes2 = plt.subplots(
    len(PLOT_REGIONS), 1, figsize=(10, 1.8 * len(PLOT_REGIONS)), sharex=True
)
if len(PLOT_REGIONS) == 1:
    axes2 = [axes2]
for ax, region in zip(axes2, PLOT_REGIONS, strict=True):
    recomputed = _recompute_covered_per_region(out, EMISSION_CATEGORY, region)
    covered = (
        out.filter(region=region, variable="Emissions|Covered")
        .data[["year", "value"]]
        .rename(columns={"value": "adapter"})
    )
    merged = covered.merge(recomputed, on="year")
    ax.plot(merged["year"], merged["adapter"], color=BLUE, linewidth=2,
            label="adapter Emissions|Covered")
    ax.plot(merged["year"], merged["recomputed"],
            linewidth=1, linestyle=":", label="independent recompute")
    ax.set_title(region.split("|", 1)[1], fontsize=10)
    ax.set_ylabel("Mt CO2e/yr")
    ax.grid(alpha=0.3)
    max_abs_diff = (merged["adapter"] - merged["recomputed"]).abs().max()
    ax.text(
        0.98, 0.05, f"max |Δ| = {max_abs_diff:.2e}", transform=ax.transAxes,
        ha="right", va="bottom", fontsize=8, alpha=0.6,
    )
axes2[0].legend(loc="upper left", fontsize=8, frameon=False)
axes2[-1].set_xlabel("Year")
fig2.suptitle(
    "Aggregation sanity: adapter Covered vs independent recompute "
    "(lines should overlap, max |Δ| → 0)",
    fontsize=10,
)
fig2.tight_layout()
plt.show()

# %% [markdown]
# ## Concatenate, interpolate to annual, and save for 401 / 402 / 403
#
# Output is written at annual resolution, linearly interpolated across the
# scenario's native cadence. 401/402/403 load this file and expect
# Population, GDP|PPP, the three component emissions, and
# `Emissions|Covered` across history and scenario years.

# %%
combined = pyam.concat([out, socio])

# Unify model and scenario labels across history and scenario rows so the
# output is a single (model, scenario) combination — what the 401/402/403
# loader expects. Historical provenance is preserved implicitly in the
# variable-level data; downstream we just need consistent keys on the
# regional time-series.
scen_model = sorted(scenario.model)[0]
scen_scenario = sorted(scenario.scenario)[0]
combined_df = combined.data.assign(model=scen_model, scenario=scen_scenario)
combined = pyam.IamDataFrame(combined_df)

annual_years = list(range(START_YEAR, int(max(combined.year)) + 1))
# pyam.interpolate inserts year columns one at a time and trips pandas'
# fragmentation warning ~120 times. Cosmetic; suppress locally.
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
    combined.interpolate(time=annual_years, inplace=True)
combined = combined.filter(year=annual_years)

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
combined.to_excel(OUTPUT_FILE)
print(
    f"Wrote {OUTPUT_FILE}  (model={scen_model!r}, scenario={scen_scenario!r}, "
    f"years={annual_years[0]}-{annual_years[-1]}, annual)"
)

# %%
