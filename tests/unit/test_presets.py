"""The ESABCC 2023 / PRR2023 preset names its settings and runs."""

from __future__ import annotations

import numpy as np
import pytest

from fair_shares.library.allocations import run_allocation
from fair_shares.library.presets import (
    ESABCC_2023_CATEGORIES,
    esabcc_2023_allocation_list,
    esabcc_2023_allocations,
)

# Runs per category, allocation years and responsibility window starts per
# allocation year, from the notebook 601 decisions.
EXPECTED = {
    "co2-ffi": (36, {1990: {1850}, 2015: {1850, 1990}}),
    "all-ghg-ex-co2-lulucf": (22, {2015: {1850, 1990}}),
    "all-ghg": (14, {2015: {2000}}),
}
SNAPSHOT_YEAR = {1990: 1990, 2015: 2014}


@pytest.mark.parametrize("category", ESABCC_2023_CATEGORIES)
def test_preset_names_prr2023_parameters(category):
    n_runs, expected_windows = EXPECTED[category]
    runs = esabcc_2023_allocation_list(category)
    assert len(runs) == n_runs

    windows: dict[int, set[int]] = {}
    for run in runs:
        ((approach, p),) = run.items()
        ay = p["allocation_year"]
        assert ay in expected_windows
        responsibility = bool(p.get("pre_allocation_responsibility_weight"))
        if responsibility:
            assert p["pre_allocation_responsibility_functional_form"] == "power"
            assert p["pre_allocation_responsibility_exponent"] in (1.0, 0.5)
            assert "pre_allocation_responsibility_per_capita" in p
            windows.setdefault(ay, set()).add(p["pre_allocation_responsibility_year"])
        if p.get("capability_weight"):
            assert p["capability_functional_form"] == "power"
            assert p["capability_exponent"] in (1.0, 0.5)
            assert p["capability_reference_year"] == SNAPSHOT_YEAR[ay]
        # Every ECPC-base run names its 2050 window.
        if not p["preserve_allocation_year_shares"]:
            assert p["cumulative_end_year"] == 2050
    assert windows == expected_windows


def test_preset_rejects_unknown_category_and_returns_fresh_objects():
    with pytest.raises(ValueError, match="No ESABCC 2023 preset"):
        esabcc_2023_allocations("co2")
    first = esabcc_2023_allocations("co2-ffi")
    first["equal-per-capita-budget"].clear()
    assert esabcc_2023_allocations("co2-ffi")["equal-per-capita-budget"]


def test_preset_capability_ecpc_config_runs(test_data):
    (params,) = [
        p
        for r in esabcc_2023_allocation_list("co2-ffi")
        for approach, p in r.items()
        if p.get("capability_reference_year") == 2014
        and p.get("cumulative_end_year") == 2050
        and p["capability_exponent"] == 0.5
    ]
    # The fixture data start in 2015; add the 2014 snapshot year.
    pop, gdp = (test_data[k].copy() for k in ("population", "gdp"))
    for df in (pop, gdp):
        df.insert(0, "2014", df["2015"])
    result = run_allocation(
        approach="per-capita-adjusted-budget",
        population_ts=pop,
        gdp_ts=gdp,
        emission_category="co2-ffi",
        **params,
    )
    shares = result.relative_shares_cumulative_emission["2015"]
    assert np.isclose(shares.sum(), 1.0)
    assert (shares > 0).all()
