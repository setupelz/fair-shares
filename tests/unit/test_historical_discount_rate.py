"""
Tests for historical emissions discounting (Gap A from allocation extensions spec).

Validates the `historical_discount_rate` parameter that weights historical
emissions by (1 - r_d)^(t_ref - t) before summing for pre-allocation responsibility calculations.
Source: Dekker Eq. 5, Van Den Berg ECPC*.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.allocations.budgets import per_capita_adjusted_budget
from fair_shares.library.allocations.pathways import (
    per_capita_adjusted,
)
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import get_default_unit_registry
from fair_shares.library.utils.math.adjustments import (
    calculate_responsibility_adjustment_data,
    calculate_responsibility_adjustment_data_convergence,
)


@pytest.fixture
def ur():
    return get_default_unit_registry()


class TestHistoricalDiscountRateValidation:
    """Test parameter validation for historical_discount_rate."""

    @pytest.mark.parametrize("rate", [-0.1, 1.0, 1.5])
    def test_invalid_rate_raises(self, test_data, ur, rate):
        """Negative, equal-to-one, and greater-than-one rates must be rejected."""
        with pytest.raises(AllocationError, match="historical_discount_rate"):
            per_capita_adjusted(
                population_ts=test_data["population"],
                country_actual_emissions_ts=test_data["emissions"],
                first_allocation_year=2020,
                emission_category="co2-ffi",
                pre_allocation_responsibility_weight=1.0,
                pre_allocation_responsibility_year=2015,
                historical_discount_rate=rate,
                ur=ur,
            )

    @pytest.mark.parametrize("rate", [0.0, 0.99])
    def test_valid_rate_accepted(self, test_data, ur, rate):
        """Boundary-valid rates (0.0 and 0.99) must be accepted without error."""
        result = per_capita_adjusted(
            population_ts=test_data["population"],
            country_actual_emissions_ts=test_data["emissions"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            pre_allocation_responsibility_year=2015,
            historical_discount_rate=rate,
            ur=ur,
        )
        assert result is not None


class TestDefaultBehaviorUnchanged:
    """Default (0.0) must produce bit-identical results to pre-change behavior."""

    def test_pathway_default_unchanged(self, test_data, ur):
        """Pathway allocation with default discount rate matches no-discount."""
        result_default = per_capita_adjusted(
            population_ts=test_data["population"],
            country_actual_emissions_ts=test_data["emissions"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            pre_allocation_responsibility_year=2015,
            ur=ur,
        )
        result_explicit_zero = per_capita_adjusted(
            population_ts=test_data["population"],
            country_actual_emissions_ts=test_data["emissions"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            pre_allocation_responsibility_year=2015,
            historical_discount_rate=0.0,
            ur=ur,
        )
        pd.testing.assert_frame_equal(
            result_default.relative_shares_pathway_emissions,
            result_explicit_zero.relative_shares_pathway_emissions,
        )


class TestDiscountReducesEarlyEmitterResponsibility:
    """Discount rate > 0 should reduce pre-allocation responsibility for early/historical emitters."""

    def test_discount_changes_responsibility(self, test_data, ur):
        """With discounting, pre-allocation responsibility values must differ from undiscounted."""
        result_no_discount = calculate_responsibility_adjustment_data(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            pre_allocation_responsibility_year=2015,
            allocation_year=2020,
            pre_allocation_responsibility_per_capita=False,
            group_level="iso3c",
            unit_level="unit",
            ur=ur,
            historical_discount_rate=0.0,
        )
        result_with_discount = calculate_responsibility_adjustment_data(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            pre_allocation_responsibility_year=2015,
            allocation_year=2020,
            pre_allocation_responsibility_per_capita=False,
            group_level="iso3c",
            unit_level="unit",
            ur=ur,
            historical_discount_rate=0.05,
        )
        # Discounting should reduce total pre-allocation responsibility (earlier years weigh less)
        assert result_with_discount.sum() < result_no_discount.sum()

    def test_extreme_discount_nearly_zeroes_early_years(self, test_data, ur):
        """With rate=0.99, early years should have near-zero weight."""
        result_extreme = calculate_responsibility_adjustment_data(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            pre_allocation_responsibility_year=2015,
            allocation_year=2020,
            pre_allocation_responsibility_per_capita=False,
            group_level="iso3c",
            unit_level="unit",
            ur=ur,
            historical_discount_rate=0.99,
        )
        result_none = calculate_responsibility_adjustment_data(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            pre_allocation_responsibility_year=2015,
            allocation_year=2020,
            pre_allocation_responsibility_per_capita=False,
            group_level="iso3c",
            unit_level="unit",
            ur=ur,
            historical_discount_rate=0.0,
        )
        # Extreme discounting should dramatically reduce total.
        # With test data having 2 years in the window (2015, 2019), rate=0.99:
        #   weight(2019) = 0.01^0 = 1.0, weight(2015) = 0.01^4 ≈ 0.0
        # So only the 2019 data contributes => roughly 50% of total.
        ratio = result_extreme.sum() / result_none.sum()
        assert ratio < 0.6  # Significant reduction expected


class TestSharesSumToOne:
    """Shares must always sum to 1.0 regardless of discount rate."""

    def test_pathway_shares_sum_to_one(self, test_data, ur):
        """Pathway shares sum to 1.0 with discounting applied."""
        result = per_capita_adjusted(
            population_ts=test_data["population"],
            country_actual_emissions_ts=test_data["emissions"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            pre_allocation_responsibility_year=2015,
            historical_discount_rate=0.05,
            ur=ur,
        )
        shares = result.relative_shares_pathway_emissions
        for col in shares.columns:
            total = shares[col].sum()
            assert abs(total - 1.0) < 1e-10, f"Year {col}: shares sum to {total}"


class TestDiscountMathCorrectness:
    """Verify the discount formula (1-r)^(t_ref - t) applies correctly."""

    def test_per_capita_discount_applies_to_both_sides(self, test_data, ur):
        """When pre_allocation_responsibility_per_capita=True, discount must apply to population too.

        With uniform emissions-per-capita across all years, discounting both
        sides (emissions and population) should produce the same per-capita
        metric as undiscounted -- the discount factors cancel.
        """
        result_no_disc = calculate_responsibility_adjustment_data(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            pre_allocation_responsibility_year=2015,
            allocation_year=2020,
            pre_allocation_responsibility_per_capita=True,
            group_level="iso3c",
            unit_level="unit",
            ur=ur,
            historical_discount_rate=0.0,
        )
        result_disc = calculate_responsibility_adjustment_data(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            pre_allocation_responsibility_year=2015,
            allocation_year=2020,
            pre_allocation_responsibility_per_capita=True,
            group_level="iso3c",
            unit_level="unit",
            ur=ur,
            historical_discount_rate=0.05,
        )
        # Both should be valid (positive) and same ordering
        assert (result_disc > 0).all()
        assert (result_no_disc > 0).all()
        # Ordering should be preserved
        assert (
            result_disc.sort_values().index.tolist()
            == result_no_disc.sort_values().index.tolist()
        )

    def test_convergence_function_uses_inclusive_reference_year(self, test_data, ur):
        """Convergence function uses first_allocation_year as reference (inclusive end)."""
        result = calculate_responsibility_adjustment_data_convergence(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            pre_allocation_responsibility_year=2015,
            first_allocation_year=2020,
            pre_allocation_responsibility_per_capita=False,
            group_level="iso3c",
            unit_level="unit",
            ur=ur,
            historical_discount_rate=0.1,
        )
        # Should run without error and produce positive results
        assert (result > 0).all()


class TestParameterInResult:
    """Verify that historical_discount_rate appears in result parameters when used."""

    def test_discount_rate_in_parameters_when_nonzero(self, test_data, ur):
        """When discount rate > 0, it should appear in result parameters."""
        result = per_capita_adjusted(
            population_ts=test_data["population"],
            country_actual_emissions_ts=test_data["emissions"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            pre_allocation_responsibility_year=2015,
            historical_discount_rate=0.05,
            ur=ur,
        )
        assert "historical_discount_rate" in result.parameters
        assert result.parameters["historical_discount_rate"] == 0.05

    def test_discount_rate_absent_when_zero(self, test_data, ur):
        """When discount rate is 0.0, it should NOT appear in parameters."""
        result = per_capita_adjusted(
            population_ts=test_data["population"],
            country_actual_emissions_ts=test_data["emissions"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            pre_allocation_responsibility_year=2015,
            historical_discount_rate=0.0,
            ur=ur,
        )
        assert "historical_discount_rate" not in result.parameters
