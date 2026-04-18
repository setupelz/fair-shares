"""Back-fill Population and GDP|PPP history from country-level sources.

Allocation notebooks need Population and GDP|PPP across the full history
span (typically 1990+). Scenarios usually start at the IAM's base year,
leaving a gap. This module fills it from UN+OWID (population) and World
Bank WDI (GDP PPP), aggregated country→region with the same mapping used
for emissions.

The two default CSV shapes are hard-coded here because they're the
on-disk formats that ship with the fair-shares data directory. Users
with different upstream files can point at their own CSVs or pass a
pre-melted long DataFrame via ``population_source`` / ``gdp_source``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import pyam
import pyprojroot

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError
from fair_shares.library.iamc_historical.region_mapping import RegionMapping

logger = logging.getLogger(__name__)

_ISO3_RE = re.compile(r"^[A-Z]{3}$")

# UN+OWID country-level population CSV.
_DEFAULT_POPULATION_CSV = "data/population/un-owid-2025/population.csv"
# World Bank WDI constant-PPP GDP CSV (4-row preamble, wide-format years).
_DEFAULT_GDP_CSV = "data/gdp/wdi-2025/API_NY.GDP.MKTP.PP.KD_DS2_en_csv_v2_1004.csv"

SourceLike = Path | str | pd.DataFrame | None


def backfill_population_gdp(
    scenario: pyam.IamDataFrame,
    *,
    region_mapping: RegionMapping,
    start_year: int = 1990,
    population_source: SourceLike = None,
    gdp_source: SourceLike = None,
    return_parts: bool = False,
) -> pyam.IamDataFrame | tuple[pyam.IamDataFrame, pyam.IamDataFrame]:
    """Prepend Population and GDP|PPP history to a scenario IamDataFrame.

    Takes a scenario that already carries ``Population`` and ``GDP|PPP`` rows
    at the IAM's native region resolution, fills the pre-scenario window by
    aggregating country-level UN+OWID population and World Bank WDI GDP to
    the same regions via ``region_mapping``, and returns the concatenated
    history + scenario rows for both variables.

    Values are unit-matched to the scenario's existing Population / GDP unit
    labels so downstream concatenation with other rows does not trigger a
    pyam "multiple units" error. WDI 2025 is in a newer base-year PPP than
    most example scenarios' 2010 label; allocation functions operate on
    region-year ratios, not absolute levels, so the pre/post-join ratios
    remain compatible for first-cut analyses. Swap in a deflator-corrected
    series for tighter base-year alignment.

    Parameters
    ----------
    scenario
        Scenario IamDataFrame. Must include ``Population`` and ``GDP|PPP``
        at the target regions.
    region_mapping
        Country-to-region mapping. The same instance used for emissions
        back-fill, so region coverage stays consistent.
    start_year
        Fill history from this year inclusive. Defaults to 1990.
    population_source, gdp_source
        Either a path to a CSV in the documented shape, or a pre-melted
        long DataFrame with ``region`` (lowercase ISO3), ``variable``,
        ``unit``, and year columns. Defaults resolve off ``pyprojroot.here()``
        to the packaged UN+OWID and WDI CSVs.
    return_parts
        Return ``(history_idf, scenario_idf)`` instead of a concatenated
        single IamDataFrame. If the scenario already starts at or before
        ``start_year``, no back-fill is performed and the first element of
        the tuple is an empty IamDataFrame with no rows.
    """
    if not isinstance(scenario, pyam.IamDataFrame):
        raise TypeError(
            f"scenario must be a pyam.IamDataFrame, got {type(scenario).__name__}"
        )

    missing_vars = [
        v for v in ("Population", "GDP|PPP") if v not in set(scenario.variable)
    ]
    if missing_vars:
        raise DataProcessingError(
            "Scenario is missing required variables for socio-economic "
            f"back-fill: {missing_vars}."
        )

    scen_years = sorted(scenario.year)
    first_scen_year = scen_years[0]
    scen_passthrough = scenario.filter(variable=["Population", "GDP|PPP"])

    if first_scen_year <= start_year:
        logger.info(
            "Scenario already starts at or before %d; no socio-economic "
            "back-fill needed.",
            start_year,
        )
        empty_hist = _empty_like()
        if return_parts:
            return empty_hist, scen_passthrough
        return scen_passthrough

    hist_year_range = list(range(start_year, first_scen_year))

    pop_unit = _single_unit(scenario, "Population")
    gdp_unit = _single_unit(scenario, "GDP|PPP")

    pop_wide = _load_population(population_source, unit=pop_unit)
    gdp_wide = _load_gdp(gdp_source, unit=gdp_unit)

    scen_model = sorted(scenario.model)[0]
    scen_scenario = sorted(scenario.scenario)[0]

    pop_hist = _aggregate_and_label(
        pop_wide, region_mapping, hist_year_range, scen_model, scen_scenario
    )
    gdp_hist = _aggregate_and_label(
        gdp_wide, region_mapping, hist_year_range, scen_model, scen_scenario
    )

    history_idf = pyam.IamDataFrame(
        pd.concat(
            [_melt_wide_to_long(pop_hist), _melt_wide_to_long(gdp_hist)],
            ignore_index=True,
        )
    )

    if return_parts:
        return history_idf, scen_passthrough
    return pyam.concat([history_idf, scen_passthrough])


# ----------------------------------------------------------------------
# helpers


def _empty_like() -> pyam.IamDataFrame:
    empty_df = pd.DataFrame(
        columns=["model", "scenario", "region", "variable", "unit", "year", "value"]
    )
    return pyam.IamDataFrame(empty_df)


def _single_unit(scenario: pyam.IamDataFrame, variable: str) -> str:
    units = list(scenario.filter(variable=variable).unit)
    if not units:
        raise DataProcessingError(
            f"Scenario has no rows for variable {variable!r}; cannot infer unit."
        )
    if len(set(units)) > 1:
        raise DataProcessingError(
            f"Scenario has multiple units for {variable!r}: {sorted(set(units))}. "
            "Back-fill requires a single unit per variable."
        )
    return units[0]


def _load_population(source: SourceLike, *, unit: str) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    path = _resolve_path(source, default=_DEFAULT_POPULATION_CSV)
    long = pd.read_csv(path)
    long = long[long["Code"].astype(str).str.match(_ISO3_RE, na=False)]
    wide = (
        long.rename(columns={"Code": "region", "Year": "year"})[
            ["region", "year", "Population (historical estimates)"]
        ]
        .pivot_table(
            index="region",
            columns="year",
            values="Population (historical estimates)",
            aggfunc="first",
        )
        .reset_index()
    )
    wide["region"] = wide["region"].str.lower()
    for y in [c for c in wide.columns if isinstance(c, int)]:
        wide[y] = wide[y] / 1e6  # people -> million
    return wide.assign(variable="Population", unit=unit)


def _load_gdp(source: SourceLike, *, unit: str) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    path = _resolve_path(source, default=_DEFAULT_GDP_CSV)
    wide = pd.read_csv(path, skiprows=4).rename(columns={"Country Code": "region"})
    wide = wide[wide["region"].astype(str).str.match(_ISO3_RE, na=False)]
    year_cols = [c for c in wide.columns if c.isdigit()]
    wide = wide[["region", *year_cols]].copy()
    wide.columns = ["region", *[int(c) for c in year_cols]]
    wide["region"] = wide["region"].str.lower()
    for y in [c for c in wide.columns if isinstance(c, int)]:
        wide[y] = wide[y] / 1e9  # USD -> billion
    return wide.assign(variable="GDP|PPP", unit=unit)


def _resolve_path(source: SourceLike, *, default: str) -> Path:
    if source is None:
        return pyprojroot.here() / default
    if isinstance(source, (str, Path)):
        return Path(source)
    raise ConfigurationError(
        f"Unsupported source type: {type(source).__name__}"
    )


def _aggregate_and_label(
    wide: pd.DataFrame,
    mapping: RegionMapping,
    year_range: list[int],
    model: str,
    scenario: str,
) -> pd.DataFrame:
    # mapping.aggregate relabels countries to their target region but the
    # grouping keeps per-country rows — sum within (region, variable, unit)
    # to get the regional total.
    agg = mapping.aggregate(wide, country_col="region")
    year_cols_present = [y for y in year_range if y in agg.columns]
    summed = agg.groupby(
        ["region", "variable", "unit"], as_index=False
    )[year_cols_present].sum()
    return summed.assign(model=model, scenario=scenario)


def _melt_wide_to_long(wide: pd.DataFrame) -> pd.DataFrame:
    year_cols = [c for c in wide.columns if isinstance(c, int)]
    long = wide.melt(
        id_vars=["model", "scenario", "region", "variable", "unit"],
        value_vars=year_cols,
        var_name="year",
        value_name="value",
    )
    return long[~long["value"].isna()]
