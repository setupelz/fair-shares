"""Budget allocations from start years before the GDP series.

Population and fossil CO2 start in 1850; GDP starts in 1990. A capability
snapshot (``capability_reference_year``) needs GDP at the reference year only,
so the adjusted budget approaches run from 1850. Year-by-year capability still
needs GDP at the allocation year.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from fair_shares.library.allocations import run_parameter_grid
from fair_shares.library.allocations.budgets import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)
from fair_shares.library.exceptions import AllocationError, DataProcessingError

COUNTRIES = ["AAA", "BBB", "CCC", "DDD"]
POP_YEARS = [1850, 1900, 1950, 1990, 2000, 2015, 2020, 2023, 2050]
GDP_YEARS = [1990, 2000, 2015, 2020, 2023]
EMISSION_YEARS = [1850, 1900, 1950, 1990, 2000, 2015, 2020, 2023]
# GDP per capita in 2020 (USD): two countries below a 7500 floor, two above.
GDP_PER_CAPITA_2020 = [2000.0, 6000.0, 25000.0, 60000.0]


def _frames() -> dict[str, pd.DataFrame]:
    """Population from 1850, GDP from 1990, fossil emissions from 1850."""
    population = pd.DataFrame(
        {
            str(y): [(10.0 + 5.0 * i) * (1.0 + 0.004 * (y - 1850)) for i in range(4)]
            for y in POP_YEARS
        },
        index=pd.MultiIndex.from_product(
            [COUNTRIES, ["million"]], names=["iso3c", "unit"]
        ),
    )
    # GDP in million USD so that GDP / population (million) is USD per capita.
    gdp = pd.DataFrame(
        {
            str(y): [
                GDP_PER_CAPITA_2020[i]
                * (1.0 + 0.02 * (i + 1) * (y - 2020) / 10.0)
                * population[str(y)].iloc[i]
                for i in range(4)
            ]
            for y in GDP_YEARS
        },
        index=pd.MultiIndex.from_product(
            [COUNTRIES, ["million"]], names=["iso3c", "unit"]
        ),
    )
    emissions = pd.DataFrame(
        {
            str(y): [(1.0 + 3.0 * i) * (1.0 + 0.01 * (y - 1850)) for i in range(4)]
            for y in EMISSION_YEARS
        },
        index=pd.MultiIndex.from_product(
            [COUNTRIES, ["Mt * CO2e"], ["co2-ffi"]],
            names=["iso3c", "unit", "emission-category"],
        ),
    )
    gini = pd.DataFrame({"iso3c": COUNTRIES, "gini": [0.30, 0.45, 0.35, 0.40]})
    return {"population": population, "gdp": gdp, "emissions": emissions, "gini": gini}


def _shares(result) -> pd.Series:
    df = result.relative_shares_cumulative_emission
    return df.iloc[:, 0].droplevel(["unit", "emission-category"])


def _adjusted(f, **kwargs) -> pd.Series:
    return _shares(
        per_capita_adjusted_budget(
            population_ts=f["population"],
            gdp_ts=f["gdp"],
            emission_category="co2-ffi",
            **kwargs,
        )
    )


def _gini(f, **kwargs) -> pd.Series:
    return _shares(
        per_capita_adjusted_gini_budget(
            population_ts=f["population"],
            gdp_ts=f["gdp"],
            gini_s=f["gini"],
            emission_category="co2-ffi",
            income_floor=7500.0,
            **kwargs,
        )
    )


def test_equal_per_capita_budget_runs_from_1850():
    f = _frames()
    shares = _shares(
        equal_per_capita_budget(
            population_ts=f["population"],
            allocation_year=1850,
            emission_category="co2-ffi",
        )
    )
    cumulative_population = f["population"].sum(axis=1).droplevel("unit")
    expected = cumulative_population / cumulative_population.sum()
    np.testing.assert_allclose(shares.to_numpy(), expected.to_numpy(), rtol=1e-12)


def test_allocation_year_before_1850_raises():
    f = _frames()
    with pytest.raises(ValidationError, match="greater than or equal to 1850"):
        equal_per_capita_budget(
            population_ts=f["population"],
            allocation_year=1849,
            emission_category="co2-ffi",
        )


@pytest.mark.parametrize("allocation_year", [1850, 1990])
@pytest.mark.parametrize("run", [_adjusted, _gini])
def test_capability_snapshot_runs_from_early_start_years(run, allocation_year):
    shares = run(
        _frames(),
        allocation_year=allocation_year,
        capability_weight=1.0,
        capability_reference_year=2020,
    )
    assert shares.notna().all()
    assert shares.sum() == pytest.approx(1.0, abs=1e-12)
    # The poorest country gains over its equal per capita share.
    assert shares["AAA"] > 10.0 / 70.0


def test_snapshot_with_a_window_that_ends_before_the_gdp_series():
    shares = _adjusted(
        _frames(),
        allocation_year=1850,
        cumulative_end_year=1950,
        capability_weight=1.0,
        capability_reference_year=2020,
    )
    assert shares.sum() == pytest.approx(1.0, abs=1e-12)


def test_year_by_year_capability_before_the_gdp_series_raises():
    with pytest.raises(DataProcessingError, match="Required years not found in GDP"):
        _adjusted(_frames(), allocation_year=1850, capability_weight=1.0)


def test_reference_year_outside_the_gdp_series_raises():
    with pytest.raises(AllocationError, match="outside the GDP data range"):
        _adjusted(
            _frames(),
            allocation_year=1850,
            capability_weight=1.0,
            capability_reference_year=1950,
        )


def test_capability_only_shares_do_not_depend_on_the_weight():
    """Weights are normalised to their sum, so a lone capability weight acts as 1."""
    kwargs = dict(allocation_year=1850, capability_reference_year=2020)
    pd.testing.assert_series_equal(
        _adjusted(_frames(), capability_weight=0.3, **kwargs),
        _adjusted(_frames(), capability_weight=1.0, **kwargs),
    )


def test_responsibility_only_run_with_a_reference_year_does_not_read_gdp():
    """The grid passes GDP to every adjusted run, also when capability is off."""
    f = _frames()
    kwargs = dict(
        allocation_year=1950,
        country_actual_emissions_ts=f["emissions"],
        pre_allocation_responsibility_weight=1.0,
        pre_allocation_responsibility_year=1850,
        capability_reference_year=2020,
    )
    without_gdp = _shares(
        per_capita_adjusted_budget(
            population_ts=f["population"], emission_category="co2-ffi", **kwargs
        )
    )
    pd.testing.assert_series_equal(_adjusted(f, **kwargs), without_gdp)


# Shares from the code before the snapshot change (allocation years inside the
# GDP series), in COUNTRIES order.
PINNED = {
    "adjusted, 1990, year-by-year": (
        dict(allocation_year=1990, capability_weight=1.0),
        [
            0.5282854161360591,
            0.27415035675052307,
            0.11178139292044748,
            0.08578283419297027,
        ],
    ),
    "adjusted, 1990, snapshot 2020": (
        dict(
            allocation_year=1990, capability_weight=1.0, capability_reference_year=2020
        ),
        [
            0.5343436171274648,
            0.2728272964878631,
            0.1095039618388284,
            0.08332512454584375,
        ],
    ),
    "adjusted, 2015, snapshot 2000, responsibility from 1850": (
        dict(
            allocation_year=2015,
            capability_weight=0.5,
            capability_reference_year=2000,
            pre_allocation_responsibility_weight=0.5,
            pre_allocation_responsibility_year=1850,
        ),
        [
            0.5054500871798192,
            0.23403826224142912,
            0.1392553692665111,
            0.12125628131224056,
        ],
    ),
    "gini, 1990, year-by-year": (
        dict(allocation_year=1990),
        [
            0.6557159057156675,
            0.2719315511156184,
            0.04220255322242418,
            0.030149989946289923,
        ],
    ),
    "gini, 1990, snapshot 2020": (
        dict(allocation_year=1990, capability_reference_year=2020),
        [
            0.6677068995500234,
            0.2625082675903675,
            0.04075970083585096,
            0.029025132023758147,
        ],
    ),
    "gini, 2015, snapshot 2000": (
        dict(allocation_year=2015, capability_reference_year=2000),
        [
            0.6346141754907716,
            0.288667408408946,
            0.04466689143303458,
            0.032051524667247644,
        ],
    ),
}


@pytest.mark.parametrize("case", PINNED)
def test_results_inside_the_gdp_series_are_unchanged(case):
    kwargs, expected = PINNED[case]
    f = _frames()
    if "pre_allocation_responsibility_year" in kwargs:
        kwargs = {**kwargs, "country_actual_emissions_ts": f["emissions"]}
    run = _gini if case.startswith("gini") else _adjusted
    shares = run(f, **kwargs)
    np.testing.assert_allclose(shares.loc[COUNTRIES].to_numpy(), expected, rtol=1e-12)


RESPONSIBILITY_FROM_1850 = {
    "per-capita-adjusted-budget": [
        {
            "allocation-year": 2015,
            "pre-allocation-responsibility-weight": 1.0,
            "capability-weight": 0.0,
            "pre-allocation-responsibility-year": 1850,
        }
    ]
}


class TestResponsibilityWindowForCo2:
    """For ``co2`` the responsibility frame is fossil CO2, which starts in 1850."""

    @staticmethod
    def _co2_frame(f) -> pd.DataFrame:
        """Composite ``co2`` emissions, available from 2000 only."""
        return (
            f["emissions"]
            .loc[:, "2000":]
            .rename(index={"co2-ffi": "co2"}, level="emission-category")
        )

    def _grid_shares(self, f, responsibility_emissions_ts) -> pd.Series:
        (result,) = run_parameter_grid(
            allocations_config=RESPONSIBILITY_FROM_1850,
            population_ts=f["population"],
            country_actual_emissions_ts=self._co2_frame(f),
            responsibility_emissions_ts=responsibility_emissions_ts,
            emission_category="co2",
        )
        return _shares(result)

    def test_window_from_1850_passes_with_the_fossil_frame(self):
        f = _frames()
        base = self._grid_shares(f, f["emissions"])
        assert base.sum() == pytest.approx(1.0, abs=1e-12)

        # The window is [1850, 2015): 1850 counts, 2015 does not.
        changed_1850 = f["emissions"].copy()
        changed_1850.loc["AAA", "1850"] = 500.0
        assert (self._grid_shares(f, changed_1850) - base).abs().max() > 1e-6

        changed_2015 = f["emissions"].copy()
        changed_2015.loc["AAA", "2015"] = 500.0
        pd.testing.assert_series_equal(self._grid_shares(f, changed_2015), base)

    def test_window_before_the_frame_raises(self):
        f = _frames()
        with pytest.raises(AllocationError, match="is before 1990, the first year"):
            self._grid_shares(f, f["emissions"].loc[:, "1990":])

    def test_without_a_separate_frame_the_nghgi_floor_stands(self):
        with pytest.raises(AllocationError, match="is before 2000"):
            self._grid_shares(_frames(), None)
