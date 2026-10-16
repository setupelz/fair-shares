"""Check fair-shares budget allocations against the PRR2023 method (Pelz, Rogelj, Riahi 2023).

Ports the PRR2023 R allocation formulas (Zenodo 10.5281/zenodo.8035839 v1.1,
R/allocation_r11eu27_19902015.R) to Python, validates the port against the
archive's published figure tables, then feeds the same R11+EU27 inputs to
fair_shares budget functions and compares region by region. A secondary table
aggregates the notebook 601 country results to EU27.

Usage: uv run python analysis/prr2023_method_check.py <unzipped-archive-dir>
Outputs: output/_prr2023_method_check/*.csv
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from fair_shares.library.allocations.budgets.per_capita import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
)
from fair_shares.library.allocations.coverage import (
    find_incomplete_countries,
    move_countries_to_row,
)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "output" / "_prr2023_method_check"
# Notebook 601's co2-ffi output folder, from the source list shared with its fixture test.
_spec = importlib.util.spec_from_file_location(
    "python_api_sources", REPO / "tests/fixtures/python_api_sources.py"
)
_sources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sources)
SOURCE_601 = REPO / "output" / _sources.source_id("co2-ffi")
RESULTS_601 = SOURCE_601 / "allocations/601_esabcc_2023/allocations_relative.parquet"
BUDGET = {1990: 1030 + 500, 2015: 204 + 500}  # GtCO2, allocation R script
PF = {"1/x": 1.0, "1/sqrt(x)": 0.5}
REGIONS = ["EU27", "REU", "CPA", "FSU", "LAM", "MEA", "NAM", "PAS", "PAO", "SAS", "AFR"]

# indicator -> (allocation year, kind, responsibility start year, per capita)
INDICATORS = {
    "RES_emiss_1850co2_1989": (1990, "res", 1850, False),
    "RES_cmltvcapita_1850co2_1989": (1990, "res", 1850, True),
    "CAP_gdp2017pppcapita_1990": (1990, "cap", None, True),
    "CAP_capstock2017pppcapita_1990": (1990, "cap", None, True),
    "RES_emiss_1850co2_2014": (2015, "res", 1850, False),
    "RES_emiss_1990co2_2014": (2015, "res", 1990, False),
    "RES_emiss_1990co2cons_2014": (2015, "res", 1990, False),
    "RES_cmltvcapita_1850co2_2014": (2015, "res", 1850, True),
    "RES_cmltvcapita_1990co2_2014": (2015, "res", 1990, True),
    "RES_cmltvcapita_1990co2cons_2014": (2015, "res", 1990, True),
    "CAP_gdp2017pppcapita_2014": (2015, "cap", None, True),
    "CAP_capstock2017pppcapita_2014": (2015, "cap", None, True),
}
# Indicators the library can be fed from territorial CO2 + GDP (not consumption CO2 or capital stock)
LIBRARY_TESTABLE = {k for k in INDICATORS if "cons" not in k and "capstock" not in k}


def find_root(arg: str) -> Path:
    """Locate the archive root holding Data/ and Figures/."""
    hits = list(Path(arg).rglob("indicators_r11eu27.csv"))
    if not hits:
        sys.exit(f"indicators_r11eu27.csv not found under {arg}")
    return hits[0].parents[2]


def load_inputs(root: Path) -> dict:
    """Read PRR2023 regional indicators, mappings and population inputs."""
    eq = root / "Data" / "equity_data"
    ind = pd.read_csv(eq / "indicators_r11eu27.csv").set_index("r11eu27")
    mapping = pd.read_csv(eq / "indicatormapping.csv").set_index("indicator")
    isorgn = pd.read_csv(root / "Data" / "countrygrouping" / "isorgn.csv")
    popr = pd.read_csv(eq / "population" / "popr11eu271850.csv").pivot(
        index="r11eu27", columns="year", values="totalpop"
    )
    ssp = pd.read_csv(eq / "population" / "SspDb_country_data_2013-06-12.csv")
    ssp = ssp[
        (ssp.MODEL == "IIASA-WiC POP")
        & (ssp.SCENARIO == "SSP2_v9_130115")
        & (ssp.VARIABLE == "Population")
    ]
    ssp = ssp[["REGION", "2030", "2040", "2050"]].rename(columns={"REGION": "iso3c"})
    ssp = ssp.merge(isorgn[["iso3c", "r11eu27"]], on="iso3c", how="inner")
    ssp = ssp.groupby("r11eu27")[["2030", "2040", "2050"]].sum(min_count=1) * 1e6
    return {"ind": ind, "mapping": mapping, "isorgn": isorgn, "popr": popr, "ssp": ssp}


def prr_population_projection(ind: pd.DataFrame, ssp: pd.DataFrame) -> pd.DataFrame:
    """PRR2023 1990-2050 population: linear interpolation through 1990, 2015 and SSP2 2030/40/50."""
    years = np.arange(1990, 2051)
    rows = {}
    for r in ind.index:
        xp = [1990, 2015, 2030, 2040, 2050]
        fp = [ind.at[r, "EQL_capita_1990"], ind.at[r, "EQL_capita_2015"], *ssp.loc[r]]
        rows[r] = np.interp(years, xp, fp)
    return pd.DataFrame(rows, index=years).T


# ---- Independent port of PRR2023 allocation formulas ----


def prr_allocate(ind, pop_proj, year, basis, exponent) -> pd.DataFrame:
    """Regional budgets (GtCO2) per indicator, as allocationPC/allocationCPC after penalise()."""
    if basis == "EPC":
        weight = ind[f"EQL_capita_{year}"]
        eql_name = f"EQL_capita_{year}"
    else:
        weight = pop_proj.loc[:, year:2050].sum(axis=1)
        eql_name = f"EQL_cmltvcapita_{year}2050"
    out = {eql_name: weight / weight.sum() * BUDGET[year]}
    for col, (ay, *_rest) in INDICATORS.items():
        if ay != year:
            continue
        f = ind[col] ** (-exponent)
        out[col] = f * weight / (f * weight).sum() * BUDGET[year]
    return pd.DataFrame(out)


def validate_port(root, inp, pop_proj) -> pd.DataFrame:
    """Compare the port with every rcb value in the archive's published figure tables."""
    label_to_ind = {v: k for k, v in inp["mapping"]["indicatorfull"].items()}
    pub = []
    for f in sorted((root / "Figures").glob("*_bot.csv")):
        d = pd.read_csv(f, index_col=0)
        d["file"] = f.name
        pub.append(d)
    pub = pd.concat(pub).drop_duplicates(["r11eu27", "indicator", "allocation", "pf"])
    rows = []
    for _, p in pub.iterrows():
        year = 1990 if "1990" in p["allocation"] else 2015
        basis = "ECPC" if "cumulative" in p["allocation"] else "EPC"
        ours = prr_allocate(inp["ind"], pop_proj, year, basis, PF[p["pf"]])
        val = ours.at[p["r11eu27"], label_to_ind[p["indicator"]]]
        rows.append(
            {
                "file": p["file"], "region": p["r11eu27"], "indicator": p["indicator"],
                "basis": basis, "allocation_year": year, "pf": p["pf"],
                "published_gt": p["rcb"], "port_gt": val,
                "rel_diff": abs(val - p["rcb"]) / abs(p["rcb"]),
            }
        )
    return pd.DataFrame(rows)


# ---- Same inputs through fair_shares ----


def ts(df: pd.DataFrame, unit: str, extra: dict | None = None) -> pd.DataFrame:
    """Wrap a region x year frame as a fair_shares TimeseriesDataFrame."""
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    df.index.name = "iso3c"  # input validation requires this level name; values are R11+EU27 codes
    df = df.assign(unit=unit, **(extra or {})).set_index(["unit", *(extra or {})], append=True)
    return df


def library_inputs(inp, pop_proj, year):
    """Build library inputs: PRR historical population before `year`, PRR projection from it."""
    ind = inp["ind"]
    pop = pd.concat([inp["popr"].loc[:, 1850 : year - 1], pop_proj.loc[:, year:2050]], axis=1)
    emis = pd.DataFrame(0.0, index=ind.index, columns=range(1850, 2051))  # validation needs the allocation year present
    emis[1850] = ind["RES_emiss_1850co2_1989"] * 1e3  # lump sums: only window totals matter
    emis[1990] = ind["RES_emiss_1990co2_2014"] * 1e3
    gdp = pd.DataFrame(
        {y: ind[f"CAP_gdp2017pppcapita_{y}"] * pop[y] / 1e6 for y in (1990, 2014)}
    )
    return (
        ts(pop / 1e6, "million"),
        ts(emis, "Mt * CO2", {"emission-category": "co2-ffi"}),
        ts(gdp, "million"),
    )


def library_allocate(pop, emis, gdp, year, basis, exponent) -> pd.DataFrame:
    """Run fair_shares budget functions for every testable indicator; return GtCO2."""
    common = dict(
        population_ts=pop, allocation_year=year, emission_category="co2-ffi",
        group_level="iso3c",
        preserve_allocation_year_shares=(basis == "EPC"),
        cumulative_end_year=None if basis == "EPC" else 2050,
    )
    eql = equal_per_capita_budget(**common)
    out = {
        ("EQL_capita_" if basis == "EPC" else "EQL_cmltvcapita_")
        + (f"{year}" if basis == "EPC" else f"{year}2050"): eql
    }
    for col, (ay, kind, start, per_cap) in INDICATORS.items():
        if ay != year or col not in LIBRARY_TESTABLE:
            continue
        if kind == "res":
            # As in run_allocation: a country without population in the window joins ROW.
            window = [("population", start, ay - 1)] if per_cap else []
            moved = list(find_incomplete_countries({"population": pop}, window))
            out[col] = per_capita_adjusted_budget(
                **{**common, "population_ts": move_countries_to_row(pop, moved)},
                country_actual_emissions_ts=move_countries_to_row(emis, moved),
                pre_allocation_responsibility_weight=1.0,
                pre_allocation_responsibility_year=start,
                pre_allocation_responsibility_per_capita=per_cap,
                pre_allocation_responsibility_functional_form="power",
                pre_allocation_responsibility_exponent=exponent,
            )
        else:
            out[col] = per_capita_adjusted_budget(
                **common, gdp_ts=gdp, capability_weight=1.0,
                capability_functional_form="power", capability_exponent=exponent,
                capability_per_capita=True,
                capability_reference_year=1990 if year == 1990 else 2014,
            )
    shares = {
        k: r.relative_shares_cumulative_emission.iloc[:, 0].droplevel(
            ["unit", "emission-category"]
        )
        for k, r in out.items()
    }
    return pd.DataFrame(shares) * BUDGET[year]


def method_fidelity(inp, pop_proj) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare library and port region by region on identical inputs."""
    detail = []
    for year in (1990, 2015):
        for basis in ("EPC", "ECPC"):
            for pf, e in PF.items():
                port = prr_allocate(inp["ind"], pop_proj, year, basis, e)
                with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
                    warnings.simplefilter("ignore")
                    lib = library_allocate(*library_inputs(inp, pop_proj, year), year, basis, e)
                for col in lib.columns:
                    for r in REGIONS:
                        a, b = port.at[r, col], lib.at[r, col]
                        detail.append(
                            {
                                "allocation_year": year, "basis": basis, "pf": pf,
                                "indicator": col, "region": r, "port_gt": a,
                                "library_gt": b, "rel_diff": abs(b - a) / abs(a),
                            }
                        )
    detail = pd.DataFrame(detail)
    summary = (
        detail.groupby(["allocation_year", "basis", "indicator", "pf"], sort=False)
        .agg(max_rel_diff=("rel_diff", "max"))
        .reset_index()
    )
    return detail, summary


# ---- Data-gap view: notebook 601 country results aggregated to EU27 ----


def library_data_by_region(isorgn, aggregate: bool = True) -> tuple:
    """Load the 601 run's processed inputs, summed to R11+EU27 if `aggregate` (ROW kept)."""
    proc = SOURCE_601 / "intermediate" / "processed"
    region = isorgn.set_index("iso3c")["r11eu27"]

    def agg(name, keys):
        d = pd.read_csv(proc / name)
        if aggregate:
            d["iso3c"] = d["iso3c"].map(lambda c: region.get(c, c))
        return d.groupby(keys).sum(min_count=1)

    return (
        agg("country_population_timeseries.csv", ["iso3c", "unit"]),
        agg("country_emissions_co2-ffi_timeseries.csv", ["iso3c", "unit", "emission-category"]),
        agg("country_gdp_timeseries.csv", ["iso3c", "unit"]),
    )


def eu27_data_gap(inp, pop_proj) -> pd.DataFrame:
    """Split the EU27 share gap into data (region-level) and granularity (country-level) parts."""
    if not RESULTS_601.exists():
        return pd.DataFrame()
    d = pd.read_parquet(RESULTS_601)
    d = d[d["quantile"].astype(float) == 0.5].copy()
    d["region"] = d["iso3c"].map(inp["isorgn"].set_index("iso3c")["r11eu27"])
    d["share"] = np.where(d["allocation-year"].astype(int) == 1990, d["1990"], d["2015"])
    reg_inputs = library_data_by_region(inp["isorgn"])
    cty_inputs = library_data_by_region(inp["isorgn"], aggregate=False)
    eu_iso = inp["isorgn"].loc[inp["isorgn"]["r11eu27"] == "EU27", "iso3c"]
    rows = []
    for year, basis in [(y, b) for y in (1990, 2015) for b in ("EPC", "ECPC")]:
        sub = d[
            (d["allocation-year"].astype(int) == year)
            & (d["preserve-allocation-year-shares"].astype(str) == str(basis == "EPC"))
        ]
        for pf, e in PF.items():
            port = prr_allocate(inp["ind"], pop_proj, year, basis, e) / BUDGET[year]
            with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
                warnings.simplefilter("ignore")
                reg = library_allocate(*reg_inputs, year, basis, e) / BUDGET[year]
                cty = library_allocate(*cty_inputs, year, basis, e) / BUDGET[year]
            for col in port.columns:
                spec = INDICATORS.get(col)
                if spec is None:
                    m = sub[sub["approach"] == "equal-per-capita-budget"]
                    if pf != "1/x":
                        continue
                elif col not in LIBRARY_TESTABLE:
                    continue
                elif spec[1] == "res":
                    m = sub[
                        (sub["pre-allocation-responsibility-weight"].astype(float) == 1.0)
                        & (sub["pre-allocation-responsibility-year"].astype(float) == spec[2])
                        & (sub["pre-allocation-responsibility-per-capita"].astype(str) == str(spec[3]))
                        & (sub["pre-allocation-responsibility-exponent"].astype(float) == e)
                    ]
                else:
                    m = sub[
                        (sub["capability-weight"].astype(float) == 1.0)
                        & (sub["capability-exponent"].astype(float) == e)
                    ]
                if m.empty:
                    continue
                world = m["share"].sum()
                eu = m.loc[m["region"] == "EU27", "share"].sum() / world
                eu_rerun = cty.loc[cty.index.isin(eu_iso), col].sum()
                rows.append(
                    {
                        "allocation_year": year, "basis": basis, "indicator": col,
                        "pf": pf if spec else "-", "prr2023_eu27_share": port.at["EU27", col],
                        "fair_shares_region_level_eu27_share": reg.at["EU27", col],
                        "fair_shares_601_eu27_share": eu,
                        "data_gap_pp": 100 * (reg.at["EU27", col] - port.at["EU27", col]),
                        "granularity_gap_pp": 100 * (eu - reg.at["EU27", col]),
                        "total_diff_pp": 100 * (eu - port.at["EU27", col]),
                        "rerun_minus_601_pp": 100 * (eu_rerun - eu),
                        "row_group_share": m.loc[m["iso3c"] == "ROW", "share"].sum() / world,
                        "n_countries": int(m["iso3c"].nunique()),
                    }
                )
    return pd.DataFrame(rows)


def main(arg: str) -> None:
    """Write all comparison tables."""
    root = find_root(arg)
    inp = load_inputs(root)
    pop_proj = prr_population_projection(inp["ind"], inp["ssp"])
    OUT.mkdir(parents=True, exist_ok=True)

    port_val = validate_port(root, inp, pop_proj)
    port_val.to_csv(OUT / "port_validation.csv", index=False)
    detail, summary = method_fidelity(inp, pop_proj)
    detail.to_csv(OUT / "method_fidelity_detail.csv", index=False)
    summary.to_csv(OUT / "method_fidelity_summary.csv", index=False)
    gap = eu27_data_gap(inp, pop_proj)
    gap.to_csv(OUT / "eu27_data_gap.csv", index=False)

    print(f"Port vs published: {len(port_val)} values, max rel diff {port_val.rel_diff.max():.2e}")
    print(f"Library vs port: {len(detail)} values, max rel diff {detail.rel_diff.max():.2e}")
    print(summary.to_string(index=False))
    if not gap.empty:
        print(gap.round(4).to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
