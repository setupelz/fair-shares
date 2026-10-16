"""Validation follows the allocation's group_level and reads only the years it uses."""

from __future__ import annotations

import inspect

import pandas as pd
import pytest
from conftest import get_core_allocation_functions

from fair_shares.library.allocations.budgets import per_capita_adjusted_budget
from fair_shares.library.allocations.manager import (
    convert_budget_config_to_pathway,
    derive_pathway_allocations,
)
from fair_shares.library.allocations.pathways import per_capita_convergence
from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils import get_default_unit_registry

REGION = "r11eu27"
ADJUSTED = {
    "pre_allocation_responsibility_weight": 0.5,
    "capability_weight": 0.5,
    "pre_allocation_responsibility_year": 2015,
}


def _shares(result) -> pd.DataFrame:
    if hasattr(result, "relative_shares_cumulative_emission"):
        return result.relative_shares_cumulative_emission
    return result.relative_shares_pathway_emissions


def _run(func, params, data, group_level):
    ren = {"iso3c": group_level}
    inputs = {
        "population_ts": data["population"].rename_axis(index=ren),
        "gdp_ts": data["gdp"].rename_axis(index=ren),
        "gini_s": data["gini"].rename(columns=ren),
        "country_actual_emissions_ts": data["emissions"].rename_axis(index=ren),
        "world_scenario_emissions_ts": data["world-emissions"].rename_axis(index=ren),
        "group_level": group_level,
        "ur": get_default_unit_registry(),
        **params,
        **ADJUSTED,
    }
    accepted = inspect.signature(func).parameters
    return _shares(func(**{k: v for k, v in inputs.items() if k in accepted}))


@pytest.mark.parametrize(
    "func,params",
    get_core_allocation_functions(),
    ids=lambda x: getattr(x, "__name__", ""),
)
def test_region_group_level_matches_iso3c(func, params, test_data):
    by_iso = _run(func, params, test_data, "iso3c")
    by_region = _run(func, params, test_data, REGION)
    assert by_region.index.names[0] == REGION
    pd.testing.assert_frame_equal(
        by_region.rename_axis(index={REGION: "iso3c"}), by_iso
    )


def _budget(emissions, test_data, **kwargs):
    return per_capita_adjusted_budget(
        country_actual_emissions_ts=emissions,
        population_ts=test_data["population"],
        gdp_ts=test_data["gdp"],
        allocation_year=2020,
        emission_category="co2-ffi",
        pre_allocation_responsibility_weight=1.0,
        capability_weight=0.0,
        ur=get_default_unit_registry(),
        **kwargs,
    ).relative_shares_cumulative_emission


def test_responsibility_needs_no_allocation_year_emissions(test_data):
    full = _budget(
        test_data["emissions"], test_data, pre_allocation_responsibility_year=2015
    )
    trimmed = _budget(
        test_data["emissions"].drop(columns=["2020"]),
        test_data,
        pre_allocation_responsibility_year=2015,
    )
    pd.testing.assert_frame_equal(full, trimmed)


def test_empty_responsibility_window_names_missing_years(test_data):
    late = test_data["emissions"].drop(columns=["2015", "2019"])
    with pytest.raises(DataProcessingError, match="2015-2019"):
        _budget(late, test_data, pre_allocation_responsibility_year=2015)


def test_convergence_still_requires_first_year_emissions(test_data):
    with pytest.raises(DataProcessingError, match="Missing: 2020"):
        per_capita_convergence(
            country_actual_emissions_ts=test_data["emissions"].drop(columns=["2020"]),
            population_ts=test_data["population"],
            first_allocation_year=2020,
            convergence_year=2050,
            emission_category="co2-ffi",
            ur=get_default_unit_registry(),
        )


def test_kebab_budget_config_converts_like_snake():
    kebab = {
        "allocation-year": 2015,
        "cumulative-end-year": 2050,
        "preserve-allocation-year-shares": False,
        "capability-window": [2010, 2019],
        "capability-reference-year": None,
    }
    snake = {k.replace("-", "_"): v for k, v in kebab.items()}
    expected = {
        "first_allocation_year": 2015,
        "preserve_first_allocation_year_shares": False,
        "capability_window": [2010, 2019],
        "capability_reference_year": None,
    }
    assert convert_budget_config_to_pathway(kebab) == expected
    assert convert_budget_config_to_pathway(snake) == expected
    derived = derive_pathway_allocations({"per-capita-adjusted-budget": [kebab]})
    assert derived == {"per-capita-adjusted": [expected]}


def test_window_cut_short_by_data_coverage_names_missing_years(test_data):
    """A window from 1850 over data from 1990 raises, naming 1850-1989."""
    with pytest.raises(DataProcessingError, match="Missing: 1850-1989"):
        _budget(
            test_data["emissions"], test_data, pre_allocation_responsibility_year=1850
        )
