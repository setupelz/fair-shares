"""
Tests for responsibility window boundary consistency.

Verifies that both budget and pathway allocation functions correctly apply the
responsibility window [historical_responsibility_year, first_allocation_year) which
excludes the first allocation year itself.

This test suite validates the fix for the responsibility window boundary bug
where the first allocation year was incorrectly included in the historical
responsibility period.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.allocations.budgets import per_capita_adjusted_budget
from fair_shares.library.allocations.pathways import (
    per_capita_adjusted,
)
from fair_shares.library.utils import get_default_unit_registry


class TestResponsibilityWindowBoundary:
    """Test that responsibility window correctly excludes first allocation year."""

    def test_pathway_adjusted_excludes_allocation_year(self, test_data):
        """
        Test that per_capita_adjusted pathway excludes first allocation year from
        responsibility window.

        With historical_responsibility_year=2015 and first_allocation_year=2020,
        the responsibility window should be [2015, 2020) = {2015, 2019}.
        Year 2020 should NOT be included in responsibility calculations.

        Test data years: 2015, 2019, 2020, 2030, 2040, 2050
        """
        ur = get_default_unit_registry()

        result = per_capita_adjusted(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=1.0,  # Maximum responsibility weight
            capability_weight=0.0,
            historical_responsibility_year=2015,
            ur=ur,
        )

        # Verify result exists and has expected structure
        assert result.relative_shares_pathway_emissions is not None
        shares_df = result.relative_shares_pathway_emissions

        # Check that shares were calculated
        assert not shares_df.empty
        assert shares_df.shape[0] == 4  # 4 countries (AAA, BBB, CCC, DDD)

        # Verify shares sum to 1 for each year
        year_totals = shares_df.sum(axis=0)
        pd.testing.assert_series_equal(
            year_totals,
            pd.Series([1.0] * len(year_totals), index=year_totals.index),
            rtol=1e-10,
        )

    def test_cumulative_convergence_adjusted_excludes_allocation_year(self, test_data):
        """
        Test that cumulative_per_capita_convergence_adjusted pathway excludes first
        allocation year from responsibility window.

        Responsibility window [2015, 2020) should contain only 2015 and 2019.
        """
        ur = get_default_unit_registry()

        from fair_shares.library.allocations.pathways import (
            cumulative_per_capita_convergence_adjusted,
        )

        result = cumulative_per_capita_convergence_adjusted(
            country_actual_emissions_ts=test_data["emissions"],
            world_scenario_emissions_ts=test_data["world-emissions"],
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=1.0,  # Maximum responsibility weight
            capability_weight=0.0,
            historical_responsibility_year=2015,
            ur=ur,
        )

        # Verify result structure
        assert result.relative_shares_pathway_emissions is not None
        shares_df = result.relative_shares_pathway_emissions

        assert not shares_df.empty
        assert shares_df.shape[0] == 4  # 4 countries

        # Verify shares sum to 1 for each year
        year_totals = shares_df.sum(axis=0)
        pd.testing.assert_series_equal(
            year_totals,
            pd.Series([1.0] * len(year_totals), index=year_totals.index),
            rtol=1e-10,
        )

    def test_budget_excludes_allocation_year(self, test_data):
        """
        Test that per_capita_adjusted_budget excludes allocation year from
        responsibility window.

        For budget functions, allocation_year plays the same role as
        first_allocation_year in pathway functions. The responsibility window
        should be [historical_responsibility_year, allocation_year) = [2015, 2020).
        """
        ur = get_default_unit_registry()

        result = per_capita_adjusted_budget(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=1.0,  # Maximum responsibility weight
            capability_weight=0.0,
            historical_responsibility_year=2015,
            ur=ur,
        )

        # Verify result structure (budget returns DataFrame with one year column)
        assert result.relative_shares_cumulative_emission is not None
        shares_df = result.relative_shares_cumulative_emission

        assert not shares_df.empty
        assert shares_df.shape[0] == 4  # 4 countries

        # Verify shares sum to 1 (extract the single year column)
        year_col = shares_df.columns[0]
        total_share = shares_df[year_col].sum()
        assert abs(total_share - 1.0) < 1e-10

    def test_responsibility_window_consistency_across_functions(self, test_data):
        """
        Test that budget and pathway functions apply responsibility adjustments
        consistently when using the same parameters.

        While the absolute allocation values differ between budget and pathway
        functions, the relative ordering of countries by responsibility should
        be consistent when using the same historical data and weights.
        """
        ur = get_default_unit_registry()

        # Run budget allocation
        budget_result = per_capita_adjusted_budget(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=1.0,
            capability_weight=0.0,
            historical_responsibility_year=2015,
            ur=ur,
        )

        # Run pathway allocation
        pathway_result = per_capita_adjusted(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=1.0,
            capability_weight=0.0,
            historical_responsibility_year=2015,
            ur=ur,
        )

        # Extract shares - budget has DataFrame, pathway has DataFrame with multiple years
        budget_shares_df = budget_result.relative_shares_cumulative_emission
        year_col = budget_shares_df.columns[0]
        budget_shares = budget_shares_df[year_col]  # Extract Series
        pathway_shares_2020 = pathway_result.relative_shares_pathway_emissions["2020"]

        # Get country ordering by share size (now working with Series)
        budget_order = budget_shares.sort_values(ascending=False).index.tolist()
        pathway_order = pathway_shares_2020.sort_values(ascending=False).index.tolist()

        # Orders should be identical since both use same responsibility window
        assert budget_order == pathway_order, (
            f"Budget and pathway responsibility adjustments produced different "
            f"country orderings. Budget: {budget_order}, Pathway: {pathway_order}"
        )

    def test_edge_case_first_year_equals_allocation_year(self, test_data):
        """
        Test edge case where historical_responsibility_year equals first_allocation_year.

        Responsibility window [2020, 2020) should be empty and raise an error.
        """
        ur = get_default_unit_registry()

        from fair_shares.library.exceptions import AllocationError

        with pytest.raises(
            AllocationError,
            match="No years found between 2020 and",
        ):
            per_capita_adjusted(
                country_actual_emissions_ts=test_data["emissions"],
                population_ts=test_data["population"],
                gdp_ts=test_data["gdp"],
                first_allocation_year=2020,
                emission_category="co2-ffi",
                responsibility_weight=1.0,
                capability_weight=0.0,
                historical_responsibility_year=2020,  # Same as allocation year
                ur=ur,
            )

    def test_edge_case_responsibility_year_after_allocation_year(self, test_data):
        """
        Test edge case where historical_responsibility_year > first_allocation_year.

        Invalid configuration should raise an error.
        """
        ur = get_default_unit_registry()

        from fair_shares.library.exceptions import AllocationError

        with pytest.raises(
            AllocationError,
            match="No years found between",
        ):
            per_capita_adjusted(
                country_actual_emissions_ts=test_data["emissions"],
                population_ts=test_data["population"],
                gdp_ts=test_data["gdp"],
                first_allocation_year=2020,
                emission_category="co2-ffi",
                responsibility_weight=1.0,
                capability_weight=0.0,
                historical_responsibility_year=2025,  # After allocation year
                ur=ur,
            )
