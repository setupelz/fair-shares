"""Compare the two Gini sources, and the effect of decoupling, in one place.

Run:

    uv run python analysis/gini_source_comparison.py

Writes CSVs and a summary to ``output/_gini_source_comparison/``. Four questions:

1. Which countries does each Gini source cover?
2. Which countries does the swap gain and lose, and how old is the WIID value
   for the ones lost?
3. How far apart are the two sources where both have a value?
4. How many analysis countries end up with an imputed Gini?

Reading WIID needs the file fetched first:
``fair-shares fetch-data --source unu-wider-2025``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from pyprojroot import here

from fair_shares.library.utils import get_complete_iso3c_timeseries, last_year_column
from fair_shares.library.utils.dataframes import ensure_string_year_columns

ROOT = here()
OUT = ROOT / "output" / "_gini_source_comparison"

WDI_PATH = ROOT / "data/gini/wdi-2025/API_SI.POV.GINI_DS2_en_csv_v2.csv"
WIID_PATH = ROOT / "data/gini/unu-wider-2025/WIID-29APR2025.xlsx"
REGIONS_PATH = ROOT / "data/regions/iso3c_region_mapping_20240319.csv"
YEAR_WINDOW = (2015, 2023)

# The two runs compared: same emissions, GDP and population, different Gini.
WIID_RUN = "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_rcbs_co2-ffi"
WDI_RUN = "primap-202503_wdi-2025_un-owid-2025_wdi-2025_rcbs_co2-ffi"


def wdi_selection() -> pd.DataFrame:
    """Latest available Gini per country within the year window."""
    raw = pd.read_csv(WDI_PATH, skiprows=4)
    years = [c for c in raw.columns if c.isdigit()]
    long = raw.melt(
        id_vars=["Country Name", "Country Code"],
        value_vars=years,
        var_name="year",
        value_name="gini",
    ).rename(columns={"Country Code": "iso3c"})
    long["year"] = long["year"].astype(int)
    long = long.dropna(subset=["gini"])
    countries = set(pd.read_csv(REGIONS_PATH)["iso3c"])
    long = long[long["iso3c"].isin(countries)]
    first, last = YEAR_WINDOW
    long = long[(long["year"] >= first) & (long["year"] <= last)]
    selected = long.sort_values(["iso3c", "year"]).groupby("iso3c").tail(1)
    selected = selected[["iso3c", "year", "gini"]].copy()
    selected["gini"] = selected["gini"] / 100.0
    return selected.set_index("iso3c")


def wiid_selection() -> pd.DataFrame:
    """Latest high-quality Gini per country, falling back to latest of any quality.

    Mirrors notebook 105 exactly, including that the row is picked before
    missing values are dropped: a country whose latest observation has no Gini
    value is dropped rather than falling back to an earlier one. Checked
    against the WIID run's own ``gini_stationary.csv`` below.
    """
    raw = pd.read_excel(WIID_PATH)[["c3", "year", "gini", "quality"]]
    raw = raw.rename(columns={"c3": "iso3c"})

    def pick(group: pd.DataFrame) -> pd.Series:
        high = group[group["quality"] == "High"]
        pool = high if len(high) else group
        return pool.loc[pool["year"].idxmax()]

    selected = raw.groupby("iso3c").apply(pick, include_groups=False)
    selected = selected.reset_index()[["iso3c", "year", "gini", "quality"]].dropna()
    selected["gini"] = selected["gini"] / 100.0
    selected = selected.set_index("iso3c")

    produced = ROOT / "output" / WIID_RUN / "intermediate/gini/gini_stationary.csv"
    if produced.is_file():
        expected = set(pd.read_csv(produced)["iso3c"])
        if set(selected.index) != expected:
            raise SystemExit(
                "WIID selection here does not match the one the pipeline produced "
                f"({len(selected)} vs {len(expected)} countries). The comparison "
                "would be against a set nothing ever ran on."
            )
    return selected


def analysis_countries(source_id: str, *, gate_on_gini: bool) -> set[str]:
    """Recompute a run's analysis set from its own intermediates.

    Cheaper and more exact than rebuilding: the inputs are already on disk.
    """
    base = ROOT / "output" / source_id / "intermediate"

    def load(path: Path, index: list[str]) -> pd.DataFrame:
        return ensure_string_year_columns(pd.read_csv(path).set_index(index))

    gdp = load(base / "gdp/gdp_timeseries.csv", ["iso3c", "unit"])
    pop = load(base / "population/population_timeseries.csv", ["iso3c", "unit"])
    sets = [
        get_complete_iso3c_timeseries(
            frame,
            expected_index_names=["iso3c", "unit"],
            start=1990,
            end=last_year_column(frame),
        )
        for frame in (gdp, pop)
    ]

    processed = sorted((base / "processed").glob("country_emissions_*_timeseries.csv"))
    categories = [
        p.name.replace("country_emissions_", "").replace("_timeseries.csv", "")
        for p in processed
    ]
    for category in categories:
        frame = load(
            base / "emissions" / f"emiss_{category}_timeseries.csv",
            ["iso3c", "unit", "emission-category"],
        )
        sets.append(
            get_complete_iso3c_timeseries(
                frame,
                expected_index_names=["iso3c", "unit", "emission-category"],
                start=1990,
                end=last_year_column(frame),
            )
        )

    countries = sets[0].intersection(*sets[1:])
    if gate_on_gini:
        gini = pd.read_csv(base / "gini/gini_stationary.csv")
        countries &= set(gini["iso3c"])
    return countries


def main() -> int:
    """Write the comparison and print its headline numbers."""
    OUT.mkdir(parents=True, exist_ok=True)

    wdi = wdi_selection()
    wiid = wiid_selection()

    gained = sorted(set(wdi.index) - set(wiid.index))
    lost = sorted(set(wiid.index) - set(wdi.index))
    overlap = sorted(set(wdi.index) & set(wiid.index))

    lost_table = wiid.loc[lost, ["year", "gini", "quality"]].copy()
    lost_table = lost_table.rename(
        columns={"year": "wiid_observation_year", "gini": "wiid_gini"}
    )
    lost_table["vintage"] = pd.cut(
        lost_table["wiid_observation_year"],
        bins=[0, 2009, 2014, 9999],
        labels=["pre-2010", "2010-2014", "2015 or later"],
    )
    lost_table.sort_values("wiid_observation_year", ascending=False).to_csv(
        OUT / "countries_lost.csv"
    )

    wdi.loc[gained].to_csv(OUT / "countries_gained.csv")

    diff = pd.DataFrame(
        {
            "wdi_gini": wdi.loc[overlap, "gini"],
            "wdi_year": wdi.loc[overlap, "year"],
            "wiid_gini": wiid.loc[overlap, "gini"],
            "wiid_year": wiid.loc[overlap, "year"],
        }
    )
    diff["difference"] = diff["wdi_gini"] - diff["wiid_gini"]
    diff.sort_values("difference").to_csv(OUT / "overlap_differences.csv")

    # Decoupling: same run, membership with and without the Gini gate.
    gated = analysis_countries(WIID_RUN, gate_on_gini=True)
    decoupled = analysis_countries(WIID_RUN, gate_on_gini=False)

    lines = [
        "# Gini source comparison",
        "",
        f"WDI window: {YEAR_WINDOW[0]}-{YEAR_WINDOW[1]}, latest available per country.",
        "WIID: latest high-quality observation, any year.",
        "",
        "## Coverage",
        "",
        f"- WIID countries: {len(wiid)}",
        f"- WDI countries: {len(wdi)}",
        f"- Overlap: {len(overlap)}",
        f"- Gained by the swap: {len(gained)} {gained}",
        f"- Lost by the swap: {len(lost)}",
        "",
        "### Vintage of the countries lost",
        "",
    ]
    counts = lost_table["vintage"].value_counts()
    for label in ["2015 or later", "2010-2014", "pre-2010"]:
        members = sorted(lost_table.index[lost_table["vintage"] == label])
        lines.append(f"- {label}: {counts.get(label, 0)} {members}")

    lines += [
        "",
        "## Value differences on the overlap (WDI - WIID)",
        "",
        f"- median: {diff['difference'].median():.3f}",
        f"- IQR: {diff['difference'].quantile(0.25):.3f} to "
        f"{diff['difference'].quantile(0.75):.3f}",
        f"- median absolute difference: {diff['difference'].abs().median():.3f}",
        "",
        "Ten largest downward movers (WDI lower than WIID):",
        "",
    ]
    for iso3c, row in diff.nsmallest(10, "difference").iterrows():
        lines.append(
            f"- {iso3c}: WDI {row['wdi_gini']:.3f} ({int(row['wdi_year'])}) vs "
            f"WIID {row['wiid_gini']:.3f} ({int(row['wiid_year'])})"
        )
    lines += ["", "Ten largest upward movers:", ""]
    for iso3c, row in diff.nlargest(10, "difference").iterrows():
        lines.append(
            f"- {iso3c}: WDI {row['wdi_gini']:.3f} ({int(row['wdi_year'])}) vs "
            f"WIID {row['wiid_gini']:.3f} ({int(row['wiid_year'])})"
        )

    lines += [
        "",
        "## Decoupling: analysis-country membership",
        "",
        f"Run compared: {WIID_RUN}",
        f"- Gini-gated (before): {len(gated)}",
        f"- Decoupled (after): {len(decoupled)}",
        f"- Gained: {sorted(decoupled - gated)}",
        f"- Lost: {sorted(gated - decoupled)} (must be empty)",
        "",
        "## Imputation under fallback-mean",
        "",
    ]
    for label, gini_countries in (("WIID", set(wiid.index)), ("WDI", set(wdi.index))):
        imputed = sorted(decoupled - gini_countries)
        lines.append(
            f"- {label}: {len(imputed)} of {len(decoupled)} analysis countries "
            f"imputed {imputed}"
        )

    report = "\n".join(lines) + "\n"
    (OUT / "summary.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"Written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
