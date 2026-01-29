"""
Core mathematical properties tests for allocation functions for the fair-shares library.

"""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import get_core_allocation_functions

from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.utils import (
    get_default_unit_registry,
)


class TestAllocationMathProperties:
    """Test core mathematical properties that all allocation functions must satisfy."""

    def _prepare_function_kwargs(self, allocation_function, test_data, call_kwargs):
        """Prepare arguments for allocation function calls."""
        population = test_data["population"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        is_budget_function = allocation_function.__name__.endswith("_budget")

        if is_budget_function:
            func_kwargs = {
                "population_ts": population,
                "allocation_year": first_allocation_year,
                "emission_category": call_kwargs.get("emission_category"),
                "ur": ur,
            }
        else:
            func_kwargs = {
                "population_ts": population,
                "first_allocation_year": first_allocation_year,
                "emission_category": call_kwargs.get("emission_category"),
                "ur": ur,
            }

        func_kwargs.update(call_kwargs)

        # Add GDP data for GDP-adjusted functions (including per_capita variants)
        if (
            "gdp" in allocation_function.__name__
            or "per_capita_adjusted" in allocation_function.__name__
        ):
            func_kwargs["gdp_ts"] = test_data["gdp"]

        # Add Gini data for Gini-adjusted functions
        if "gini" in allocation_function.__name__:
            func_kwargs["gini_s"] = test_data["gini"]
            # Gini functions also need GDP
            func_kwargs["gdp_ts"] = test_data["gdp"]

        # Add emissions data for convergence functions
        if "convergence" in allocation_function.__name__:
            func_kwargs["country_actual_emissions_ts"] = test_data["emissions"]
            # Add world scenario emissions for cumulative convergence functions
            if "cumulative" in allocation_function.__name__:
                func_kwargs["world_scenario_emissions_ts"] = test_data[
                    "world-emissions"
                ]

        return func_kwargs, is_budget_function

    @pytest.mark.parametrize(
        "allocation_function,call_kwargs", get_core_allocation_functions()
    )
    def test_shares_bounded(self, test_data, allocation_function, call_kwargs):
        """Test that shares are bounded between 0 and 1."""
        func_kwargs, is_budget_function = self._prepare_function_kwargs(
            allocation_function, test_data, call_kwargs
        )

        result = allocation_function(**func_kwargs)

        # Get shares DataFrame
        if is_budget_function:
            shares_df = result.relative_shares_cumulative_emission
        else:
            shares_df = result.relative_shares_pathway_emissions

        # Check bounds
        max_share = shares_df.max().max()
        min_share = shares_df.min().min()

        assert (
            min_share >= 0
        ), f"{allocation_function.__name__} produced shares < 0: {min_share}"
        assert (
            max_share <= 1
        ), f"{allocation_function.__name__} produced shares > 1: {max_share}"

    @pytest.mark.parametrize(
        "allocation_function,call_kwargs", get_core_allocation_functions()
    )
    def test_shares_sum_to_one(self, test_data, allocation_function, call_kwargs):
        """Test that shares sum to 1 for all years."""
        func_kwargs, is_budget_function = self._prepare_function_kwargs(
            allocation_function, test_data, call_kwargs
        )

        result = allocation_function(**func_kwargs)

        # Get shares DataFrame
        if is_budget_function:
            shares_df = result.relative_shares_cumulative_emission
        else:
            shares_df = result.relative_shares_pathway_emissions

        # Check that shares sum to 1 for each year
        for year in shares_df.columns:
            if str(year).isdigit():  # Only check numeric year columns
                shares_sum = shares_df[year].sum()
                assert (
                    abs(shares_sum - 1.0) < 1e-10
                ), f"{allocation_function.__name__} shares don't sum to 1 at year {year}: {shares_sum}"

    @pytest.mark.parametrize(
        "allocation_function,call_kwargs", get_core_allocation_functions()
    )
    def test_output_structure(self, test_data, allocation_function, call_kwargs):
        """Test that output has correct structure and types."""
        func_kwargs, is_budget_function = self._prepare_function_kwargs(
            allocation_function, test_data, call_kwargs
        )

        result = allocation_function(**func_kwargs)

        # Test result type
        if is_budget_function:
            assert isinstance(
                result, BudgetAllocationResult
            ), f"{allocation_function.__name__} should return BudgetAllocationResult"
            shares_df = result.relative_shares_cumulative_emission
        else:
            assert isinstance(
                result, PathwayAllocationResult
            ), f"{allocation_function.__name__} should return PathwayAllocationResult"
            shares_df = result.relative_shares_pathway_emissions

        # Test DataFrame structure
        assert isinstance(
            shares_df, pd.DataFrame
        ), f"{allocation_function.__name__} should return DataFrame"

        # Test MultiIndex structure
        assert isinstance(
            shares_df.index, pd.MultiIndex
        ), f"{allocation_function.__name__} should have MultiIndex"

        expected_index_names = ["iso3c", "unit", "emission-category"]
        assert shares_df.index.names == expected_index_names, (
            f"{allocation_function.__name__} should have index levels {expected_index_names}, "
            f"got {shares_df.index.names}"
        )

        # Test number of countries
        num_countries = len(shares_df.index.get_level_values("iso3c").unique())
        expected_countries = len(
            test_data["population"].index.get_level_values("iso3c").unique()
        )
        assert (
            num_countries == expected_countries
        ), f"{allocation_function.__name__} should have same number of countries as input"

        # Test emission category
        emission_category = shares_df.index.get_level_values(
            "emission-category"
        ).unique()
        assert (
            len(emission_category) == 1
        ), f"{allocation_function.__name__} should have exactly one emission category"
        assert emission_category == call_kwargs.get(
            "emission_category"
        ), f"{allocation_function.__name__} should have correct emission category"

        # Test units
        units = shares_df.index.get_level_values("unit").unique()
        assert (
            len(units) == 1
        ), f"{allocation_function.__name__} should have exactly one unit"
        assert (
            units[0] == "dimensionless"
        ), f"{allocation_function.__name__} should have dimensionless units"

    @pytest.mark.parametrize(
        "allocation_function,call_kwargs", get_core_allocation_functions()
    )
    def test_result_metadata(self, test_data, allocation_function, call_kwargs):
        """Test that result objects contain correct metadata."""
        func_kwargs, is_budget_function = self._prepare_function_kwargs(
            allocation_function, test_data, call_kwargs
        )

        result = allocation_function(**func_kwargs)

        # Test that approach is correctly set
        assert hasattr(
            result, "approach"
        ), f"{allocation_function.__name__} result missing approach attribute"
        assert isinstance(
            result.approach, str
        ), f"{allocation_function.__name__} approach should be string"

        # Test that parameters are correctly set
        assert hasattr(
            result, "parameters"
        ), f"{allocation_function.__name__} result missing parameters attribute"
        assert isinstance(
            result.parameters, dict
        ), f"{allocation_function.__name__} parameters should be dict"

        # Test specific parameter requirements
        if is_budget_function:
            assert (
                "allocation_year" in result.parameters
            ), f"{allocation_function.__name__} should have allocation_year in parameters"
        else:
            assert (
                "first_allocation_year" in result.parameters
            ), f"{allocation_function.__name__} should have first_allocation_year in parameters"

        # Test emission category is in parameters
        assert (
            "emission_category" in result.parameters
        ), f"{allocation_function.__name__} should have emission_category in parameters"

    @pytest.mark.parametrize(
        "allocation_function,call_kwargs", get_core_allocation_functions()
    )
    def test_result_validation(self, test_data, allocation_function, call_kwargs):
        """Test that result objects are automatically validated."""
        func_kwargs, is_budget_function = self._prepare_function_kwargs(
            allocation_function, test_data, call_kwargs
        )

        # This should not raise any validation errors because the result class
        # automatically validates in __attrs_post_init__
        result = allocation_function(**func_kwargs)

        # The fact that we get a result object means validation passed
        if is_budget_function:
            assert isinstance(result, BudgetAllocationResult)
            shares_df = result.relative_shares_cumulative_emission
            # Budget allocations should have exactly one year column
            year_cols = [col for col in shares_df.columns if str(col).isdigit()]
            assert (
                len(year_cols) == 1
            ), f"{allocation_function.__name__} budget should have exactly one year column"
        else:
            assert isinstance(result, PathwayAllocationResult)
            shares_df = result.relative_shares_pathway_emissions
            # Pathway allocations should have multiple year columns
            year_cols = [col for col in shares_df.columns if str(col).isdigit()]
            assert (
                len(year_cols) > 1
            ), f"{allocation_function.__name__} pathway should have multiple year columns"

    def test_result_absolute_calculation_methods(self, test_data):
        """Test that result objects can calculate absolute values."""
        from fair_shares.library.allocations.budgets import equal_per_capita_budget
        from fair_shares.library.allocations.pathways import equal_per_capita

        ur = get_default_unit_registry()

        # Test pathway result absolute emissions calculation
        pathway_result = equal_per_capita(
            population_ts=test_data["population"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            ur=ur,
        )

        # Test with emissions data - filter to only include years that pathway allocation produces
        pathway_years = pathway_result.relative_shares_pathway_emissions.columns
        emissions_subset = test_data["emissions"][pathway_years]
        absolute_emissions = pathway_result.get_absolute_emissions(
            annual_emissions_budget=emissions_subset
        )

        # Test that absolute emissions are calculated correctly
        assert isinstance(absolute_emissions, pd.DataFrame)
        assert not absolute_emissions.isna().any().any()

        # Test budget result absolute budget calculation
        budget_result = equal_per_capita_budget(
            population_ts=test_data["population"],
            allocation_year=2020,
            emission_category="co2-ffi",
            ur=ur,
        )

        # Test with budget data - use only the allocation year
        budget_result_year = budget_result.relative_shares_cumulative_emission.columns[
            0
        ]
        budget_subset = test_data["emissions"][[budget_result_year]]
        absolute_budgets = budget_result.get_absolute_budgets(
            remaining_budget=budget_subset  # Using emissions as budget for test
        )

        # Test that absolute budgets are calculated correctly
        assert isinstance(absolute_budgets, pd.DataFrame)
        assert not absolute_budgets.isna().any().any()

    def test_column_dtype_mismatch_regression(self, test_data):
        """Test for column dtype mismatch in get_absolute_budgets.

        This tests the specific bug where relative shares have string columns
        but cumulative budget has integer columns, causing pandas multiplication
        to return NaN values.
        """
        from fair_shares.library.allocations.budgets import equal_per_capita_budget
        from fair_shares.library.utils import (
            ensure_string_year_columns,
            get_cumulative_budget_from_timeseries,
        )

        ur = get_default_unit_registry()
        allocation_year = 2020

        # Create budget allocation result (has string columns)
        budget_result = equal_per_capita_budget(
            population_ts=test_data["population"],
            allocation_year=allocation_year,
            emission_category="co2-ffi",
            ur=ur,
        )

        # Simulate production scenario where cumulative budget comes from
        # get_cumulative_budget_from_timeseries (creates integer columns)
        world_emissions = test_data["emissions"]
        cumulative_budget = get_cumulative_budget_from_timeseries(
            world_emissions,
            allocation_year,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )
        cumulative_budget = ensure_string_year_columns(cumulative_budget)

        # This should work despite the column dtype mismatch
        absolute_budgets = budget_result.get_absolute_budgets(cumulative_budget)

        # Verify results are not NaN
        assert isinstance(absolute_budgets, pd.DataFrame)
        assert (
            not absolute_budgets.isna().any().any()
        ), "get_absolute_budgets should not return NaN values due to column dtype mismatch"
        assert (
            absolute_budgets.sum().sum() > 0
        ), "Absolute budgets should have positive values"

    def test_cumulative_per_capita_equal_allocation_per_person(self, test_data):
        """Test base cumulative-per-capita-convergence gives equal cumulative per-capita

        With no adjustments (responsibility_weight=0, capability_weight=0), each
        country's cumulative allocation divided by cumulative population should
        be identical across all countries. This is the core fairness property:
        everyone gets the same emissions per person over the allocation period.
        """
        from fair_shares.library.allocations.pathways import (
            cumulative_per_capita_convergence,
        )

        ur = get_default_unit_registry()
        first_allocation_year = test_data["first-allocation-year"]

        # Run base function with NO adjustments
        result = cumulative_per_capita_convergence(
            population_ts=test_data["population"],
            country_actual_emissions_ts=test_data["emissions"],
            world_scenario_emissions_ts=test_data["world-emissions"],
            first_allocation_year=first_allocation_year,
            emission_category="co2-ffi",
            ur=ur,
        )

        shares = result.relative_shares_pathway_emissions
        year_cols = [c for c in shares.columns if str(c).isdigit()]

        # Get world emissions for each year
        world_emissions = test_data["world-emissions"]
        world_mask = world_emissions.index.get_level_values("iso3c") == "World"
        world_row = world_emissions[world_mask]

        # Calculate cumulative allocation for each country:
        # sum over years of (share * world_emissions)
        cumulative_allocation = pd.Series(0.0, index=shares.index)
        for year in year_cols:
            if year in world_row.columns:
                world_total = float(world_row[year].iloc[0])
                cumulative_allocation += shares[year] * world_total

        # Calculate cumulative population for each country
        population = test_data["population"]
        pop_year_cols = [c for c in year_cols if c in population.columns]
        cumulative_population = population[pop_year_cols].sum(axis=1)

        # Align indices: shares has [iso3c, unit='dimensionless', emission-category],
        # population has [iso3c, unit='million']. Match only by iso3c.
        shares_iso3c = shares.index.get_level_values("iso3c")
        # Group population by iso3c (sum across units if multiple)
        pop_by_country = cumulative_population.groupby(level="iso3c").sum()
        # Map each share row to its population value by iso3c only
        cum_pop_aligned = [pop_by_country.loc[iso3c] for iso3c in shares_iso3c]

        # Calculate per-capita allocation for each country
        per_capita = cumulative_allocation.values / pd.Series(cum_pop_aligned).values

        # Check for NaN values (indicates alignment issue)
        assert not pd.isna(per_capita).any(), (
            "Per-capita calculation produced NaN values. "
            "Check index alignment between shares and population."
        )

        # All countries should have the same per-capita allocation (within numerical precision)
        # Allow up to 0.1% variation due to clipping/renormalization of long_run_shares
        assert per_capita.std() / per_capita.mean() < 0.001, (
            f"Per-capita allocations should be equal across countries, "
            f"but got std/mean = {per_capita.std() / per_capita.mean():.2e}, "
            f"values = {per_capita}"
        )
