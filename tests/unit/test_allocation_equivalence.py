"""
Mixed bag of tests for equivalence between budget and pathway allocations.

These tests verify that:
1. Budget and pathway allocations with matching names give the same cumulative
    absolute allocations when shares are preserved
2. gdp-per-capita-adjusted and gdp-per-capita-gini-adjusted give the same
    results when max_gini_adjustment=0 and income_floor=0
"""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import STANDARD_EMISSION_CATEGORY

from fair_shares.library.allocations.budgets import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)
from fair_shares.library.allocations.pathways import (
    equal_per_capita,
    per_capita_adjusted,
    per_capita_adjusted_gini,
)
from fair_shares.library.utils import (
    ensure_string_year_columns,
    get_cumulative_budget_from_timeseries,
    get_default_unit_registry,
)


class TestBudgetPathwayEquivalence:
    """Test that budget and pathway allocations give equivalent cumulative absolute allocations."""

    def _get_cumulative_pathway_allocations(self, pathway_result, world_emissions_ts):
        """Calculate cumulative absolute allocations from pathway allocation."""
        shares = pathway_result.relative_shares_pathway_emissions
        year_cols = [c for c in shares.columns if str(c).isdigit()]

        world_mask = world_emissions_ts.index.get_level_values("iso3c") == "World"
        world_row = world_emissions_ts[world_mask]

        cumulative_allocation = pd.Series(0.0, index=shares.index)
        for year in year_cols:
            if year in world_row.columns:
                world_total = float(world_row[year].iloc[0])
                cumulative_allocation += shares[year] * world_total

        return cumulative_allocation

    def _get_budget_allocations(self, budget_result, cumulative_budget):
        """Get absolute allocations from budget allocation."""
        shares = budget_result.relative_shares_cumulative_emission
        year_col = shares.columns[0]
        budget_value = float(cumulative_budget[year_col].iloc[0])
        return shares[year_col] * budget_value

    def test_equal_per_capita_equivalence(self, test_data):
        """Test that equal-per-capita-budget and equal-per-capita give same cumulative
        absolute allocations when shares are preserved."""
        ur = get_default_unit_registry()
        allocation_year = test_data["allocation-year"]
        first_allocation_year = test_data["first-allocation-year"]

        budget_result = equal_per_capita_budget(
            population_ts=test_data["population"],
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            preserve_allocation_year_shares=True,
            ur=ur,
        )

        pathway_result = equal_per_capita(
            population_ts=test_data["population"],
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            preserve_first_allocation_year_shares=True,
            ur=ur,
        )

        cumulative_budget = get_cumulative_budget_from_timeseries(
            test_data["world-emissions"],
            allocation_year,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )
        cumulative_budget = ensure_string_year_columns(cumulative_budget)

        budget_allocations = self._get_budget_allocations(
            budget_result, cumulative_budget
        )
        pathway_allocations = self._get_cumulative_pathway_allocations(
            pathway_result, test_data["world-emissions"]
        )

        pd.testing.assert_series_equal(
            budget_allocations.sort_index(),
            pathway_allocations.sort_index(),
            rtol=1e-6,
            atol=1e-10,
            check_names=False,
        )

    @pytest.mark.parametrize(
        "exponent,functional_form",
        [
            (1.0, "power"),
            (0.5, "power"),
            (2.0, "power"),
            (1.0, "asinh"),
        ],
        ids=["power_exp1", "power_exp0.5", "power_exp2", "asinh_exp1"],
    )
    def test_gdp_per_capita_adjusted_equivalence(
        self, test_data, exponent, functional_form
    ):
        """Test that gdp-per-capita-adjusted-budget and gdp-per-capita-adjusted give same
        cumulative absolute allocations when shares are preserved."""
        ur = get_default_unit_registry()
        allocation_year = test_data["allocation-year"]
        first_allocation_year = test_data["first-allocation-year"]

        budget_result = per_capita_adjusted_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            preserve_allocation_year_shares=True,
            capability_exponent=exponent,
            capability_functional_form=functional_form,
            ur=ur,
        )

        pathway_result = per_capita_adjusted(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            preserve_first_allocation_year_shares=True,
            capability_exponent=exponent,
            capability_functional_form=functional_form,
            ur=ur,
        )

        cumulative_budget = get_cumulative_budget_from_timeseries(
            test_data["world-emissions"],
            allocation_year,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )
        cumulative_budget = ensure_string_year_columns(cumulative_budget)

        budget_allocations = self._get_budget_allocations(
            budget_result, cumulative_budget
        )
        pathway_allocations = self._get_cumulative_pathway_allocations(
            pathway_result, test_data["world-emissions"]
        )

        pd.testing.assert_series_equal(
            budget_allocations.sort_index(),
            pathway_allocations.sort_index(),
            rtol=1e-5,
            atol=1e-9,
            check_names=False,
        )


class TestGiniAdjustedEquivalence:
    """Test that gini-adjusted allocations match non-gini when max_gini_adjustment=0."""

    def _get_budget_allocations(self, budget_result, cumulative_budget):
        """Get absolute allocations from budget allocation."""
        shares = budget_result.relative_shares_cumulative_emission
        year_col = shares.columns[0]
        budget_value = float(cumulative_budget[year_col].iloc[0])
        return shares[year_col] * budget_value

    def _get_pathway_allocations(self, pathway_result, world_emissions_ts):
        """Get absolute allocations per year from pathway allocation."""
        shares = pathway_result.relative_shares_pathway_emissions
        year_cols = [c for c in shares.columns if str(c).isdigit()]

        world_mask = world_emissions_ts.index.get_level_values("iso3c") == "World"
        world_row = world_emissions_ts[world_mask]

        allocations_dict = {}
        for year in year_cols:
            if year in world_row.columns:
                world_total = float(world_row[year].iloc[0])
                allocations_dict[year] = shares[year] * world_total

        return allocations_dict

    @pytest.mark.parametrize(
        "exponent,functional_form,preserve_shares",
        [
            (1.0, "power", False),
            (1.0, "power", True),
            (0.5, "power", False),
            (2.0, "power", False),
            (1.0, "asinh", False),
        ],
        ids=[
            "power_exp1_dynamic",
            "power_exp1_preserved",
            "power_exp0.5_dynamic",
            "power_exp2_dynamic",
            "asinh_exp1_dynamic",
        ],
    )
    def test_gdp_per_capita_gini_adjusted_equivalence_budget(
        self, test_data, exponent, functional_form, preserve_shares
    ):
        """Test that gdp-per-capita-adjusted-budget and gdp-per-capita-gini-adjusted-budget
        give same absolute allocations when max_gini_adjustment=0 and income_floor=0."""
        ur = get_default_unit_registry()
        allocation_year = test_data["allocation-year"]

        non_gini_result = per_capita_adjusted_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            preserve_allocation_year_shares=preserve_shares,
            capability_exponent=exponent,
            capability_functional_form=functional_form,
            ur=ur,
        )

        gini_result = per_capita_adjusted_gini_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            preserve_allocation_year_shares=preserve_shares,
            capability_exponent=exponent,
            capability_functional_form=functional_form,
            income_floor=0.0,
            max_gini_adjustment=0.0,
            ur=ur,
        )

        cumulative_budget = get_cumulative_budget_from_timeseries(
            test_data["world-emissions"],
            allocation_year,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )
        cumulative_budget = ensure_string_year_columns(cumulative_budget)

        non_gini_allocations = self._get_budget_allocations(
            non_gini_result, cumulative_budget
        )
        gini_allocations = self._get_budget_allocations(gini_result, cumulative_budget)

        pd.testing.assert_series_equal(
            non_gini_allocations.sort_index(),
            gini_allocations.sort_index(),
            rtol=1e-10,
            atol=1e-12,
            check_names=False,
        )

    @pytest.mark.parametrize(
        "exponent,functional_form,preserve_shares",
        [
            (1.0, "power", False),
            (1.0, "power", True),
            (0.5, "power", False),
            (2.0, "power", False),
            (1.0, "asinh", False),
        ],
        ids=[
            "power_exp1_dynamic",
            "power_exp1_preserved",
            "power_exp0.5_dynamic",
            "power_exp2_dynamic",
            "asinh_exp1_dynamic",
        ],
    )
    def test_gdp_per_capita_gini_adjusted_equivalence_pathway(
        self, test_data, exponent, functional_form, preserve_shares
    ):
        """Test that gdp-per-capita-adjusted and gdp-per-capita-gini-adjusted
        give same absolute allocations when max_gini_adjustment=0 and income_floor=0."""
        ur = get_default_unit_registry()
        first_allocation_year = test_data["first-allocation-year"]

        non_gini_result = per_capita_adjusted(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            preserve_first_allocation_year_shares=preserve_shares,
            capability_weight=1.0,
            capability_exponent=exponent,
            capability_functional_form=functional_form,
            ur=ur,
        )

        gini_result = per_capita_adjusted_gini(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            preserve_first_allocation_year_shares=preserve_shares,
            capability_weight=1.0,
            capability_exponent=exponent,
            capability_functional_form=functional_form,
            income_floor=0.0,
            max_gini_adjustment=0.0,
            ur=ur,
        )

        non_gini_allocations = self._get_pathway_allocations(
            non_gini_result, test_data["world-emissions"]
        )
        gini_allocations = self._get_pathway_allocations(
            gini_result, test_data["world-emissions"]
        )

        for year in non_gini_allocations.keys():
            pd.testing.assert_series_equal(
                non_gini_allocations[year].sort_index(),
                gini_allocations[year].sort_index(),
                rtol=1e-10,
                atol=1e-12,
                check_names=False,
            )

    @pytest.mark.parametrize(
        "max_gini_adjustment,income_floor",
        [
            (0.0, 0.0),
            (0.0, 1000.0),
        ],
        ids=["both_zero", "max_adj_zero_floor_nonzero"],
    )
    def test_gini_adjustment_disabled_cases(
        self, test_data, max_gini_adjustment, income_floor
    ):
        """Test that gini-adjusted allocations match non-gini when max_gini_adjustment=0,
        regardless of income_floor value."""
        ur = get_default_unit_registry()
        allocation_year = test_data["allocation-year"]
        first_allocation_year = test_data["first-allocation-year"]

        non_gini_budget = per_capita_adjusted_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_exponent=1.0,
            capability_functional_form="power",
            ur=ur,
        )

        non_gini_pathway = per_capita_adjusted(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_exponent=1.0,
            capability_functional_form="power",
            ur=ur,
        )

        gini_budget = per_capita_adjusted_gini_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_exponent=1.0,
            capability_functional_form="power",
            income_floor=income_floor,
            max_gini_adjustment=max_gini_adjustment,
            ur=ur,
        )

        gini_pathway = per_capita_adjusted_gini(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_exponent=1.0,
            capability_functional_form="power",
            income_floor=income_floor,
            max_gini_adjustment=max_gini_adjustment,
            ur=ur,
        )

        cumulative_budget = get_cumulative_budget_from_timeseries(
            test_data["world-emissions"],
            allocation_year,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )
        cumulative_budget = ensure_string_year_columns(cumulative_budget)

        non_gini_budget_allocations = self._get_budget_allocations(
            non_gini_budget, cumulative_budget
        )
        gini_budget_allocations = self._get_budget_allocations(
            gini_budget, cumulative_budget
        )
        pd.testing.assert_series_equal(
            non_gini_budget_allocations.sort_index(),
            gini_budget_allocations.sort_index(),
            rtol=1e-10,
            atol=1e-12,
            check_names=False,
        )

        non_gini_pathway_allocations = self._get_pathway_allocations(
            non_gini_pathway, test_data["world-emissions"]
        )
        gini_pathway_allocations = self._get_pathway_allocations(
            gini_pathway, test_data["world-emissions"]
        )
        for year in non_gini_pathway_allocations.keys():
            pd.testing.assert_series_equal(
                non_gini_pathway_allocations[year].sort_index(),
                gini_pathway_allocations[year].sort_index(),
                rtol=1e-10,
                atol=1e-12,
                check_names=False,
            )
