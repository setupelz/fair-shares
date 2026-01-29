"""
Data scenario tests for allocation functions for the fair-shares library.

"""

from __future__ import annotations

import pandas as pd
from conftest import STANDARD_EMISSION_CATEGORY

from fair_shares.library.allocations.pathways import (
    per_capita_adjusted,
)
from fair_shares.library.allocations.results import (
    PathwayAllocationResult,
)
from fair_shares.library.utils import (
    get_default_unit_registry,
)


class TestAllocationDataScenarios:
    """Test allocation functions with various data scenarios."""

    def test_limited_gdp_handling(self, limited_gdp_data):
        """Test that functions handle limited GDP data correctly."""
        population = limited_gdp_data["population"]
        gdp = limited_gdp_data["gdp"]
        first_allocation_year = limited_gdp_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test GDP-adjusted pathway function
        result = per_capita_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            ur=ur,
        )

        # Test result type
        assert isinstance(
            result, PathwayAllocationResult
        ), "Result should be PathwayAllocationResult"

        # Test approach and parameters are correctly stored
        assert result.approach == "per-capita-adjusted"
        assert result.parameters["first_allocation_year"] == first_allocation_year
        assert result.parameters["emission_category"] == STANDARD_EMISSION_CATEGORY

        # Get shares data - this should be automatically validated by the result class
        shares_df = result.relative_shares_pathway_emissions

        # Test that result has data for years beyond GDP availability
        future_years = [col for col in shares_df.columns if int(col) > 2020]
        assert (
            len(future_years) > 0
        ), "Should produce results for years beyond GDP availability"

        # Test that shares have correct MultiIndex structure
        assert isinstance(
            shares_df.index, pd.MultiIndex
        ), "Shares should have MultiIndex"
        assert shares_df.index.names == [
            "iso3c",
            "unit",
            "emission-category",
        ], f"Unexpected index names: {shares_df.index.names}"

        # Test that there is exactly one emission category
        emission_category = shares_df.index.get_level_values(
            "emission-category"
        ).unique()
        assert (
            len(emission_category) == 1
        ), f"Should have exactly one emission category, got: {emission_category}"
        assert (
            emission_category == STANDARD_EMISSION_CATEGORY
        ), f"Unexpected emission category: {emission_category}"

    def test_mixed_units_handling(self, mixed_units_data):
        """Test that functions handle different units correctly."""
        population = mixed_units_data["population"]
        gdp = mixed_units_data["gdp"]
        first_allocation_year = mixed_units_data["first-allocation-year"]
        ur = get_default_unit_registry()

        result = per_capita_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            ur=ur,
        )

        # Test result type
        assert isinstance(
            result, PathwayAllocationResult
        ), "Result should be PathwayAllocationResult"

        # Get shares data - validation is done automatically by result class
        shares_df = result.relative_shares_pathway_emissions

        # Test that no NaN values are produced
        assert not shares_df.isna().any().any(), "Produced NaN values with mixed units"

        # Test that units are properly handled in the MultiIndex
        units = shares_df.index.get_level_values("unit").unique()
        assert len(units) > 0, "Should have at least one unit"

        # Test that data structure is valid
        assert isinstance(
            shares_df.index, pd.MultiIndex
        ), "Shares should have MultiIndex"
        assert shares_df.index.names == [
            "iso3c",
            "unit",
            "emission-category",
        ], f"Unexpected index names: {shares_df.index.names}"

    def test_result_class_absolute_calculations(self, test_data):
        """Test that result classes can calculate absolute emissions correctly."""
        population = test_data["population"]
        emissions = test_data["emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        allocation_year = test_data["allocation-year"]
        ur = get_default_unit_registry()

        # Test pathway allocation absolute calculation
        from fair_shares.library.allocations.pathways import equal_per_capita

        pathway_result = equal_per_capita(
            population_ts=population,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            ur=ur,
        )

        # Filter emissions data to only include years from first_allocation_year onwards
        # This matches what the pathway allocation produces
        pathway_years = pathway_result.relative_shares_pathway_emissions.columns
        pathway_emissions = emissions[pathway_years].copy()

        # Test absolute emissions calculation using result class method
        absolute_emissions = pathway_result.get_absolute_emissions(pathway_emissions)

        assert isinstance(
            absolute_emissions, pd.DataFrame
        ), "Absolute emissions should be DataFrame"
        assert isinstance(
            absolute_emissions.index, pd.MultiIndex
        ), "Absolute emissions should have MultiIndex"

        # Test budget allocation absolute calculation
        from fair_shares.library.allocations.budgets import equal_per_capita_budget

        budget_result = equal_per_capita_budget(
            population_ts=population,
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            ur=ur,
        )

        # Create single-year budget data for testing
        single_year_emissions = emissions[[str(allocation_year)]].copy()

        # Test absolute budgets calculation using result class method
        absolute_budgets = budget_result.get_absolute_budgets(single_year_emissions)

        assert isinstance(
            absolute_budgets, pd.DataFrame
        ), "Absolute budgets should be DataFrame"
        assert isinstance(
            absolute_budgets.index, pd.MultiIndex
        ), "Absolute budgets should have MultiIndex"

        # Test that budget has only one year column
        year_cols = [col for col in absolute_budgets.columns if str(col).isdigit()]
        assert (
            len(year_cols) == 1
        ), f"Budget should have exactly one year column, got: {year_cols}"
        assert (
            int(year_cols[0]) == allocation_year
        ), f"Budget year should match allocation year {allocation_year}"
