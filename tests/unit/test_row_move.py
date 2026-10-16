"""A country without data for a year one allocation reads joins ROW for that allocation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.allocations.budgets import per_capita_adjusted_budget
from fair_shares.library.allocations.coverage import move_countries_to_row
from fair_shares.library.allocations.manager import run_allocation
from fair_shares.library.exceptions import AllocationError

YEARS = [str(y) for y in range(1850, 2031)]


def _frames() -> dict[str, pd.DataFrame]:
    """AAA has no population before 1900; ROW holds the rest of the world."""
    pop = pd.DataFrame(
        {
            "AAA": np.full(len(YEARS), 5.0),
            "BBB": np.full(len(YEARS), 20.0),
            "ROW": np.full(len(YEARS), 30.0),
        },
        index=YEARS,
    ).T
    pop.loc["AAA", [y for y in YEARS if int(y) < 1900]] = np.nan
    pop.index = pd.MultiIndex.from_tuples(
        [(c, "million") for c in pop.index], names=["iso3c", "unit"]
    )
    emiss = pd.DataFrame(
        {"AAA": np.full(len(YEARS), 2.0), "BBB": np.full(len(YEARS), 4.0)},
        index=YEARS,
    ).T
    emiss.loc["ROW"] = 6.0
    emiss.index = pd.MultiIndex.from_tuples(
        [(c, "Mt * CO2e", "co2-ffi") for c in emiss.index],
        names=["iso3c", "unit", "emission-category"],
    )
    return {"population": pop, "emissions": emiss}


def _per_capita_responsibility(**overrides):
    data = _frames()
    args = dict(
        approach="per-capita-adjusted-budget",
        population_ts=data["population"],
        country_actual_emissions_ts=data["emissions"],
        allocation_year=2000,
        emission_category="co2-ffi",
        pre_allocation_responsibility_weight=1.0,
        capability_weight=0.0,
        pre_allocation_responsibility_year=1850,
        pre_allocation_responsibility_per_capita=True,
    )
    args.update(overrides)
    return run_allocation(**args)


def test_reading_missing_years_moves_country_to_row():
    result = _per_capita_responsibility()
    shares = result.relative_shares_cumulative_emission
    assert result.moved_to_row == ("AAA",)
    assert "AAA" not in shares.index.get_level_values("iso3c")
    assert shares.iloc[:, 0].sum() == pytest.approx(1.0)


def test_row_is_world_minus_remaining_countries():
    data = _frames()
    moved = move_countries_to_row(data["population"], ["AAA"])
    world = data["population"].fillna(0.0).sum()
    assert moved.sum().to_numpy() == pytest.approx(world.to_numpy())
    assert moved.loc[("ROW", "million")].to_numpy() == pytest.approx(
        (world - moved.loc[("BBB", "million")]).to_numpy()
    )


def test_allocation_not_reading_missing_years_keeps_country():
    data = _frames()
    result = run_allocation(
        approach="equal-per-capita-budget",
        population_ts=data["population"],
        allocation_year=2000,
        emission_category="co2-ffi",
    )
    assert result.moved_to_row == ()
    assert "AAA" in result.relative_shares_cumulative_emission.index.get_level_values(
        "iso3c"
    )


def test_direct_call_raises_naming_country_and_years():
    data = _frames()
    with pytest.raises(AllocationError, match=r"AAA \(1850-1899\)"):
        per_capita_adjusted_budget(
            population_ts=data["population"],
            country_actual_emissions_ts=data["emissions"],
            allocation_year=2000,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            capability_weight=0.0,
            pre_allocation_responsibility_year=1850,
            pre_allocation_responsibility_per_capita=True,
        )


def test_parts_that_moved_different_countries_raise():
    from fair_shares.library.python_api import _check_parts_moved_same_countries

    keys = ["iso3c", "source", "family", "year"]
    config = {"source": "ar6_2020", "family": "per-capita-adjusted", "year": 2015}
    co2 = pd.DataFrame([{"iso3c": "ROW", **config, "moved-to-row": "IRL;MAC"}])
    nonco2_same = co2.copy()
    nonco2_other = co2.assign(**{"moved-to-row": "MAC"})

    _check_parts_moved_same_countries(co2, nonco2_same, keys)
    with pytest.raises(AllocationError, match=r"IRL;MAC.*MAC"):
        _check_parts_moved_same_countries(co2, nonco2_other, keys)
