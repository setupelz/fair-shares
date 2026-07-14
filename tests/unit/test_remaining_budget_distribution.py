"""Tests for distribute_remaining_budgets_pathways (negative-budget pathway distribution)."""

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils.math import distribute_remaining_budgets_pathways

YEARS = np.arange(2026, 2101)


@pytest.fixture
def global_pathway():
    """Linear decline from 50 to 0 over 2026-2100; sums to 1875 (positive)."""
    values = np.linspace(50.0, 0.0, len(YEARS))
    return pd.Series(values, index=[str(y) for y in YEARS])


@pytest.fixture
def regions():
    return {
        "base_year_emissions": pd.Series(
            {"DEBTOR": 15.0, "CREDITOR": 8.0, "ROW": 27.0}
        ),
        "population": pd.Series({"DEBTOR": 0.4, "CREDITOR": 4.5, "ROW": 5.1}),
    }


@pytest.fixture
def remaining_budgets(global_pathway):
    """Large negative, large positive, and normal share of the global total.

    Sums exactly to the global pathway total (1875), so the regional pathways
    must also sum to the global pathway in every year.
    """
    total = global_pathway.sum()
    return pd.Series(
        {"DEBTOR": -500.0, "CREDITOR": 1575.0, "ROW": total - 1575.0 + 500.0}
    )


def test_budgets_match_exactly_including_negative(
    global_pathway, regions, remaining_budgets
):
    result = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
    )
    pd.testing.assert_series_equal(
        result.sum(axis=1), remaining_budgets, check_names=False, atol=1e-9, rtol=0
    )


def test_pathways_sum_to_global_in_every_year(
    global_pathway, regions, remaining_budgets
):
    result = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
    )
    np.testing.assert_allclose(
        result.sum(axis=0).to_numpy(), global_pathway.to_numpy(), atol=1e-9
    )


def test_first_year_equals_base_year_emissions(
    global_pathway, regions, remaining_budgets
):
    result = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
    )
    np.testing.assert_allclose(
        result["2026"].to_numpy(),
        regions["base_year_emissions"].to_numpy(),
        rtol=1e-12,
    )


def test_shapes_match_budget_signs(global_pathway, regions, remaining_budgets):
    result = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
    )
    debtor = result.loc["DEBTOR"]
    creditor = result.loc["CREDITOR"]
    # Large negative budget: starts positive, goes net-negative mid-horizon.
    assert debtor.iloc[0] > 0
    assert debtor.min() < 0
    # Large positive budget: rises above its starting level, never negative.
    assert creditor.max() > creditor.iloc[0]
    assert creditor.min() >= -1e-9


def test_later_deviation_end_gives_shallower_dip(
    global_pathway, regions, remaining_budgets
):
    dips = {}
    for end_year in (2050, 2100):
        result = distribute_remaining_budgets_pathways(
            **regions,
            global_pathway=global_pathway,
            remaining_budgets=remaining_budgets,
            deviation_end_year=end_year,
        )
        dips[end_year] = result.loc["DEBTOR"].min()
        np.testing.assert_allclose(result.loc["DEBTOR"].sum(), -500.0, atol=1e-9)
    assert dips[2100] > dips[2050]


def test_missing_region_raises(global_pathway, regions):
    budgets = pd.Series({"DEBTOR": -500.0, "CREDITOR": 1575.0})  # ROW missing
    with pytest.raises(AllocationError, match="remaining_budgets"):
        distribute_remaining_budgets_pathways(
            **regions, global_pathway=global_pathway, remaining_budgets=budgets
        )


def test_invalid_deviation_end_year_raises(
    global_pathway, regions, remaining_budgets
):
    for bad_year in (2026, 2150):
        with pytest.raises(AllocationError, match="deviation_end_year"):
            distribute_remaining_budgets_pathways(
                **regions,
                global_pathway=global_pathway,
                remaining_budgets=remaining_budgets,
                deviation_end_year=bad_year,
            )


# --- Exponential shape ---------------------------------------------------
# Opt-in shape="exponential": a saturating rise instead of the half-sine hump,
# so debtor regions stay net-negative through the horizon rather than
# recovering to their per-capita baseline.


def test_exponential_budgets_match_exactly_including_negative(
    global_pathway, regions, remaining_budgets
):
    result = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
        shape="exponential",
    )
    pd.testing.assert_series_equal(
        result.sum(axis=1), remaining_budgets, check_names=False, atol=1e-9, rtol=0
    )


def test_exponential_pathways_sum_to_global_every_year(
    global_pathway, regions, remaining_budgets
):
    result = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
        shape="exponential",
    )
    np.testing.assert_allclose(
        result.sum(axis=0).to_numpy(), global_pathway.to_numpy(), atol=1e-9
    )


def test_exponential_first_year_equals_base_year_emissions(
    global_pathway, regions, remaining_budgets
):
    result = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
        shape="exponential",
    )
    np.testing.assert_allclose(
        result["2026"].to_numpy(),
        regions["base_year_emissions"].to_numpy(),
        rtol=1e-12,
    )


def test_exponential_debtor_stays_net_negative(
    global_pathway, regions, remaining_budgets
):
    result = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
        shape="exponential",
    )
    debtor = result.loc["DEBTOR"]
    # Persists: the most net-negative point is the final year, not a mid-horizon
    # trough that recovers.
    assert debtor.iloc[-1] < 0
    assert debtor.iloc[-1] == pytest.approx(debtor.min())


def test_exponential_does_not_recover_but_half_sine_does(
    global_pathway, regions, remaining_budgets
):
    """The distinguishing property: half-sine debtor recovers, exponential stays down."""
    exp = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
        shape="exponential",
    ).loc["DEBTOR"]
    sine = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
        shape="half-sine",
    ).loc["DEBTOR"]
    # Half-sine: trough is interior, recovers to ~baseline by the end.
    assert sine.iloc[-1] > sine.min() + 1e-6
    # Exponential: no recovery — final year is the trough.
    assert exp.iloc[-1] == pytest.approx(exp.min())


def test_invalid_shape_raises(global_pathway, regions, remaining_budgets):
    with pytest.raises(AllocationError, match="shape"):
        distribute_remaining_budgets_pathways(
            **regions,
            global_pathway=global_pathway,
            remaining_budgets=remaining_budgets,
            shape="triangle",
        )


def test_default_shape_matches_half_sine(global_pathway, regions, remaining_budgets):
    default = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
    )
    explicit = distribute_remaining_budgets_pathways(
        **regions,
        global_pathway=global_pathway,
        remaining_budgets=remaining_budgets,
        shape="half-sine",
    )
    pd.testing.assert_frame_equal(default, explicit)


def test_exponential_deviation_end_year_controls_final_dip(
    global_pathway, regions, remaining_budgets
):
    finals = {}
    for end_year in (2050, 2100):
        result = distribute_remaining_budgets_pathways(
            **regions,
            global_pathway=global_pathway,
            remaining_budgets=remaining_budgets,
            shape="exponential",
            deviation_end_year=end_year,
        )
        np.testing.assert_allclose(result.loc["DEBTOR"].sum(), -500.0, atol=1e-9)
        finals[end_year] = result.loc["DEBTOR"].iloc[-1]
    # The transition-timescale knob changes the final-year depth (deepen vs plateau).
    assert finals[2050] != pytest.approx(finals[2100])
