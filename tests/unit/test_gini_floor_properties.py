"""Properties of the Gini income floor and the max_gini_adjustment cap.

Capability is normalised by the median of the unadjusted indicator, so raising
the floor lowers adjusted capability without moving the reference. A country
held at the cap then keeps a constant adjustment factor (a plateau).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fair_shares.library.allocations.budgets import per_capita_adjusted_gini_budget
from fair_shares.library.utils.math.allocation import (
    calculate_gini_adjusted_gdp,
    calculate_relative_adjustment,
)

ISO = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
GDP_PC = np.array([1500.0, 2500.0, 12000.0, 20000.0, 35000.0, 60000.0])
POP = np.array([200.0, 100.0, 80.0, 60.0, 50.0, 40.0])  # million
GINI = np.array([0.40, 0.35, 0.45, 0.38, 0.33, 0.41])
FLOORS = np.linspace(0.0, 30000.0, 13)
CAP = 0.8


def _adjusted_capability(floor: float) -> np.ndarray:
    return calculate_gini_adjusted_gdp(GDP_PC * POP, GINI, floor, POP, CAP) / POP


def test_adjusted_capability_is_non_increasing_in_the_floor():
    caps = np.array([_adjusted_capability(f) for f in FLOORS])
    assert np.all(np.diff(caps, axis=0) <= 1e-9)


def test_capability_factor_rises_then_plateaus_at_the_cap():
    reference = float(np.median(GDP_PC))
    factors = np.array(
        [
            calculate_relative_adjustment(
                pd.Series(_adjusted_capability(f), index=ISO), reference=reference
            ).to_numpy()
            for f in FLOORS
        ]
    )
    assert np.all(np.diff(factors, axis=0) >= -1e-12)
    capped = np.isclose(_adjusted_capability(FLOORS[-1]), (1 - CAP) * GDP_PC)
    assert capped[:2].all()
    first_bound = np.argmax(
        np.isclose(
            np.array([_adjusted_capability(f) for f in FLOORS]), (1 - CAP) * GDP_PC
        ),
        axis=0,
    )
    for i in np.flatnonzero(capped):
        np.testing.assert_allclose(factors[first_bound[i] :, i], factors[-1, i])


def _shares(floor: float) -> pd.Series:
    index = pd.MultiIndex.from_tuples(
        [(c, "million") for c in ISO], names=["iso3c", "unit"]
    )
    population = pd.DataFrame({"2020": POP}, index=index)
    gdp = pd.DataFrame({"2020": GDP_PC * POP}, index=index)
    gini = pd.DataFrame({"iso3c": ISO, "gini": GINI})
    result = per_capita_adjusted_gini_budget(
        population_ts=population,
        gdp_ts=gdp,
        gini_s=gini,
        allocation_year=2020,
        emission_category="co2-ffi",
        capability_weight=1.0,
        income_floor=floor,
        max_gini_adjustment=CAP,
    )
    shares = result.relative_shares_cumulative_emission.iloc[:, 0]
    return shares.groupby(level="iso3c").sum()


def test_share_ratio_of_capped_countries_is_invariant_to_the_floor():
    """Two capped countries keep their share ratio as the floor rises.

    Their factors are constant only if the normalisation reference is fixed.
    A median of adjusted capability falls with the floor and moves the ratio.
    """
    floors = [f for f in FLOORS if f >= 10000.0]
    assert all(
        np.isclose(_adjusted_capability(f)[:2], (1 - CAP) * GDP_PC[:2]).all()
        for f in floors
    )
    ratios = [s["AAA"] / s["BBB"] for s in map(_shares, floors)]
    np.testing.assert_allclose(ratios, ratios[0], rtol=1e-12)


def test_gini_approach_runs_on_a_region_group_level():
    """Gini data keyed on the function's group_level, not on iso3c."""
    index = pd.MultiIndex.from_tuples(
        [(c, "million") for c in ISO], names=["region", "unit"]
    )
    result = per_capita_adjusted_gini_budget(
        population_ts=pd.DataFrame({"2020": POP}, index=index),
        gdp_ts=pd.DataFrame({"2020": GDP_PC * POP}, index=index),
        gini_s=pd.DataFrame({"region": ISO, "gini": GINI}),
        allocation_year=2020,
        emission_category="co2-ffi",
        capability_weight=1.0,
        income_floor=7500.0,
        group_level="region",
    )
    shares = result.relative_shares_cumulative_emission.iloc[:, 0]
    shares = shares.groupby(level="region").sum()
    pd.testing.assert_series_equal(
        shares.rename_axis("iso3c"), _shares(7500.0), check_names=False
    )
