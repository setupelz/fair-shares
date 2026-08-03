"""The Gini adjustment applies wherever the capability snapshot comes from.

``capability_reference_year`` can name a year before the allocation window, in
which case the snapshot is read from the unfiltered GDP and population inputs
rather than the window-filtered ones. That path used to skip the Gini
adjustment entirely, so a Gini-adjusted approach silently produced
Gini-independent results — including for the common
``allocation_year=2015, capability_reference_year=2014`` pairing. These tests
fail on that behaviour.
"""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import STANDARD_EMISSION_CATEGORY

from fair_shares.library.allocations.budgets import per_capita_adjusted_gini_budget
from fair_shares.library.allocations.pathways import per_capita_adjusted_gini

# capability_reference_year 2019 is in the fixture's year set but before the
# allocation year, so it exercises the unfiltered-input branch.
PRE_WINDOW_YEAR = 2019
ALLOCATION_YEAR = 2020

COMMON = dict(
    emission_category=STANDARD_EMISSION_CATEGORY,
    capability_weight=1.0,
    capability_functional_form="power",
    capability_exponent=1.0,
    capability_per_capita=True,
    capability_reference_year=PRE_WINDOW_YEAR,
    income_floor=7500.0,
    max_gini_adjustment=0.8,
)


def _flat_gini(gini_df: pd.DataFrame, value: float) -> pd.DataFrame:
    """The same countries, every Gini set to one value."""
    flat = gini_df.copy()
    flat["gini"] = value
    return flat


def _budget_shares(test_data, gini_df):
    result = per_capita_adjusted_gini_budget(
        population_ts=test_data["population"],
        gdp_ts=test_data["gdp"],
        gini_s=gini_df,
        allocation_year=ALLOCATION_YEAR,
        preserve_allocation_year_shares=True,
        **COMMON,
    )
    return result.relative_shares_cumulative_emission[str(ALLOCATION_YEAR)].droplevel(
        ["unit", "emission-category"]
    )


def _pathway_shares(test_data, gini_df):
    result = per_capita_adjusted_gini(
        population_ts=test_data["population"],
        gdp_ts=test_data["gdp"],
        gini_s=gini_df,
        first_allocation_year=ALLOCATION_YEAR,
        preserve_first_allocation_year_shares=True,
        **COMMON,
    )
    return result.relative_shares_pathway_emissions[str(ALLOCATION_YEAR)].droplevel(
        ["unit", "emission-category"]
    )


class TestPreWindowSnapshotUsesGini:
    def test_budget_shares_respond_to_gini(self, test_data):
        observed = _budget_shares(test_data, test_data["gini"])
        flattened = _budget_shares(test_data, _flat_gini(test_data["gini"], 0.9))
        assert (observed - flattened).abs().max() > 1e-6, (
            "changing every Gini value left the allocation untouched, so the "
            "pre-window capability snapshot ignored the Gini adjustment"
        )

    def test_pathway_shares_respond_to_gini(self, test_data):
        observed = _pathway_shares(test_data, test_data["gini"])
        flattened = _pathway_shares(test_data, _flat_gini(test_data["gini"], 0.9))
        assert (observed - flattened).abs().max() > 1e-6

    def test_budget_and_pathway_agree_on_the_pre_window_snapshot(self, test_data):
        """Both sides read the snapshot the same way, Gini adjustment included."""
        pd.testing.assert_series_equal(
            _pathway_shares(test_data, test_data["gini"]).sort_index(),
            _budget_shares(test_data, test_data["gini"]).sort_index(),
            check_names=False,
        )

    def test_income_floor_still_matters_at_a_pre_window_reference_year(self, test_data):
        """With no floor, capability is Gini-independent by construction.

        So a floor of zero is not evidence the adjustment ran — this checks the
        floor changes the answer on this branch, which it can only do through
        the Gini-adjusted capability.
        """
        without_floor = per_capita_adjusted_gini_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            allocation_year=ALLOCATION_YEAR,
            preserve_allocation_year_shares=True,
            **{**COMMON, "income_floor": 0.0},
        ).relative_shares_cumulative_emission[str(ALLOCATION_YEAR)]

        with_floor = _budget_shares(test_data, test_data["gini"])
        difference = abs(with_floor.to_numpy() - without_floor.to_numpy()).max()
        assert difference > 1e-6

    def test_an_in_window_reference_year_is_unaffected(self, test_data):
        """Guard against the fix disturbing the branch that already worked."""
        in_window = {**COMMON, "capability_reference_year": ALLOCATION_YEAR}
        result = per_capita_adjusted_gini_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            allocation_year=ALLOCATION_YEAR,
            preserve_allocation_year_shares=True,
            **in_window,
        )
        shares = result.relative_shares_cumulative_emission[str(ALLOCATION_YEAR)]
        assert shares.sum() == pytest.approx(1.0)
