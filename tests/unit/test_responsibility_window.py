"""
Tests for pre-allocation responsibility window boundary consistency.

Verifies that allocation functions correctly apply the pre-allocation
responsibility window [pre_allocation_responsibility_year, first_allocation_year)
which excludes the first allocation year itself.
"""

from __future__ import annotations

import pytest

from fair_shares.library.allocations.budgets import per_capita_adjusted_budget
from fair_shares.library.allocations.pathways import per_capita_adjusted
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import get_default_unit_registry


class TestResponsibilityWindowBoundary:
    """Test that pre-allocation responsibility window correctly excludes first allocation year."""

    def test_window_boundary_excludes_allocation_year(self, test_data):
        """
        With pre_allocation_responsibility_year=2015 and first_allocation_year=2020,
        the window should be [2015, 2020) = {2015, 2019}. Year 2020 must not be
        included in pre-allocation responsibility calculations.
        """
        ur = get_default_unit_registry()

        result = per_capita_adjusted(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            capability_weight=0.0,
            pre_allocation_responsibility_year=2015,
            ur=ur,
        )

        shares_df = result.relative_shares_pathway_emissions
        assert not shares_df.empty
        assert shares_df.shape[0] == 4  # 4 countries (AAA, BBB, CCC, DDD)

    def test_responsibility_window_consistency_across_functions(self, test_data):
        """
        Budget and pathway functions should produce the same country ordering
        when using identical pre-allocation responsibility parameters.
        """
        ur = get_default_unit_registry()

        budget_result = per_capita_adjusted_budget(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            capability_weight=0.0,
            pre_allocation_responsibility_year=2015,
            ur=ur,
        )

        pathway_result = per_capita_adjusted(
            country_actual_emissions_ts=test_data["emissions"],
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            pre_allocation_responsibility_weight=1.0,
            capability_weight=0.0,
            pre_allocation_responsibility_year=2015,
            ur=ur,
        )

        budget_shares = budget_result.relative_shares_cumulative_emission
        year_col = budget_shares.columns[0]
        budget_order = budget_shares[year_col].sort_values(ascending=False).index.tolist()
        pathway_order = (
            pathway_result.relative_shares_pathway_emissions["2020"]
            .sort_values(ascending=False)
            .index.tolist()
        )

        assert budget_order == pathway_order, (
            f"Budget and pathway produced different country orderings. "
            f"Budget: {budget_order}, Pathway: {pathway_order}"
        )

    def test_edge_case_first_year_equals_allocation_year(self, test_data):
        """Window [2020, 2020) is empty -- should raise AllocationError."""
        ur = get_default_unit_registry()

        with pytest.raises(AllocationError, match="No years found between 2020 and"):
            per_capita_adjusted(
                country_actual_emissions_ts=test_data["emissions"],
                population_ts=test_data["population"],
                gdp_ts=test_data["gdp"],
                first_allocation_year=2020,
                emission_category="co2-ffi",
                pre_allocation_responsibility_weight=1.0,
                capability_weight=0.0,
                pre_allocation_responsibility_year=2020,
                ur=ur,
            )

    def test_edge_case_responsibility_year_after_allocation_year(self, test_data):
        """Responsibility year after allocation year is invalid -- should raise AllocationError."""
        ur = get_default_unit_registry()

        with pytest.raises(AllocationError, match="No years found between"):
            per_capita_adjusted(
                country_actual_emissions_ts=test_data["emissions"],
                population_ts=test_data["population"],
                gdp_ts=test_data["gdp"],
                first_allocation_year=2020,
                emission_category="co2-ffi",
                pre_allocation_responsibility_weight=1.0,
                capability_weight=0.0,
                pre_allocation_responsibility_year=2025,
                ur=ur,
            )
