"""Tests for :func:`backfill_population_gdp`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyam
import pytest

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.iamc_historical import (
    RegionMapping,
    backfill_population_gdp,
)

from .conftest import build_iamc_scenario

FIXTURES = Path(__file__).parent / "fixtures"

_SOCIO_VARS = (
    ("Population", "million"),
    ("GDP|PPP", "billion USD_2010/yr"),
)


def _mapping() -> RegionMapping:
    return RegionMapping.from_nomenclature_yaml(FIXTURES / "tiny_regions.yml")


def _scenario(
    *,
    start_year: int = 2015,
    end_year: int = 2020,
    regions: tuple[str, ...] = ("TINY 1.0|BRA-only", "TINY 1.0|IND-USA"),
) -> pyam.IamDataFrame:
    return build_iamc_scenario(
        variables=_SOCIO_VARS,
        regions=regions,
        start_year=start_year,
        end_year=end_year,
    )


def _pop_source(*, years: range) -> pd.DataFrame:
    """Pre-melted wide population DataFrame in the shape ``_load_population`` emits.

    Columns: region (lowercase ISO3), variable, unit, integer-year columns.
    Values are already in millions.
    """
    iso3_values = {"bra": 200.0, "ind": 1300.0, "usa": 320.0}
    rows = []
    for iso3, base in iso3_values.items():
        row: dict[str, object] = {
            "region": iso3,
            "variable": "Population",
            "unit": "million",
        }
        for offset, y in enumerate(years):
            row[y] = base + offset
        rows.append(row)
    return pd.DataFrame(rows)


def _gdp_source(*, years: range) -> pd.DataFrame:
    iso3_values = {"bra": 2000.0, "ind": 5000.0, "usa": 15000.0}
    rows = []
    for iso3, base in iso3_values.items():
        row: dict[str, object] = {
            "region": iso3,
            "variable": "GDP|PPP",
            "unit": "billion USD_2010/yr",
        }
        for offset, y in enumerate(years):
            row[y] = base + offset * 10
        rows.append(row)
    return pd.DataFrame(rows)


def test_happy_path_backfills_and_aggregates() -> None:
    scen = _scenario(start_year=2015, end_year=2020)
    years = range(1990, 2015)
    filled = backfill_population_gdp(
        scen,
        region_mapping=_mapping(),
        start_year=1990,
        population_source=_pop_source(years=years),
        gdp_source=_gdp_source(years=years),
    )
    all_years = sorted(filled.year)
    assert min(all_years) == 1990
    assert max(all_years) == 2020

    df = filled.data
    # IND-USA should sum the two countries at 1990 for Population: 1300 + 320 = 1620
    ind_usa_pop_1990 = df[
        (df["region"] == "TINY 1.0|IND-USA")
        & (df["variable"] == "Population")
        & (df["year"] == 1990)
    ]["value"].iloc[0]
    assert ind_usa_pop_1990 == pytest.approx(1620.0)

    # BRA-only GDP at 1990 = 2000 (no aggregation)
    bra_gdp_1990 = df[
        (df["region"] == "TINY 1.0|BRA-only")
        & (df["variable"] == "GDP|PPP")
        & (df["year"] == 1990)
    ]["value"].iloc[0]
    assert bra_gdp_1990 == pytest.approx(2000.0)

    # Scenario rows passthrough: 2015+ rows are the original scenario values (10.0)
    passthrough = df[(df["year"] == 2015) & (df["variable"] == "Population")]
    assert set(passthrough["value"]) == {10.0}

    # Only Population + GDP|PPP in output (no emissions)
    assert set(df["variable"]) == {"Population", "GDP|PPP"}


def test_noop_when_scenario_starts_at_start_year() -> None:
    scen = _scenario(start_year=1990, end_year=2020)
    years = range(1990, 2020)
    out = backfill_population_gdp(
        scen,
        region_mapping=_mapping(),
        start_year=1990,
        population_source=_pop_source(years=years),
        gdp_source=_gdp_source(years=years),
    )
    # Returned frame should only contain the scenario's Pop/GDP passthrough
    assert set(out.variable) == {"Population", "GDP|PPP"}
    # All values should equal the scenario sentinel 10.0 (no history mixed in)
    assert set(out.data["value"]) == {10.0}


def test_return_parts_splits_history_and_scenario() -> None:
    scen = _scenario(start_year=2015, end_year=2020)
    years = range(1990, 2015)
    hist, passthrough = backfill_population_gdp(
        scen,
        region_mapping=_mapping(),
        start_year=1990,
        population_source=_pop_source(years=years),
        gdp_source=_gdp_source(years=years),
        return_parts=True,
    )
    assert max(hist.year) == 2014
    assert min(passthrough.year) == 2015

    # History carries aggregated source values (IND+USA = 1300+320 = 1620 at 1990).
    hist_ind_usa_pop_1990 = hist.data[
        (hist.data["region"] == "TINY 1.0|IND-USA")
        & (hist.data["variable"] == "Population")
        & (hist.data["year"] == 1990)
    ]["value"].iloc[0]
    assert hist_ind_usa_pop_1990 == pytest.approx(1620.0)

    # Passthrough preserves scenario values unchanged (all 10.0).
    assert set(passthrough.data["value"]) == {10.0}
    assert set(passthrough.variable) == {"Population", "GDP|PPP"}


def test_missing_variable_raises() -> None:
    rows = [
        {
            "model": "TINY 1.0",
            "scenario": "dummy",
            "region": "TINY 1.0|BRA-only",
            "variable": "Population",
            "unit": "million",
            "year": y,
            "value": 10.0,
        }
        for y in range(2015, 2021)
    ]
    scen = pyam.IamDataFrame(pd.DataFrame(rows))
    with pytest.raises(DataProcessingError, match="GDP"):
        backfill_population_gdp(
            scen,
            region_mapping=_mapping(),
            start_year=1990,
        )
