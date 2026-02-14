"""
Tests for the AllocationManager class for the fair-shares library.

"""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import STANDARD_EMISSION_CATEGORY

from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import (
    ensure_string_year_columns,
)


class TestAllocationManager:
    """Test AllocationManager functionality."""

    def test_get_function(self, allocation_manager):
        """Test that get_function returns correct functions for each approach."""
        from fair_shares.library.allocations import (
            get_allocation_functions,
            get_function,
        )

        allocation_functions = get_allocation_functions()
        for approach in allocation_functions.keys():
            func = get_function(approach)
            assert callable(func), f"Function for {approach} is not callable"
            assert func.__name__ in str(func), f"Function for {approach} has no name"

    def test_get_function_invalid(self, allocation_manager):
        """Test that get_function raises error for invalid approaches."""
        from fair_shares.library.allocations import get_function

        with pytest.raises(AllocationError, match="Unknown allocation approach"):
            get_function("invalid-approach")

    def test_is_budget_approach(self, allocation_manager):
        """Test identification of budget approaches."""
        from fair_shares.library.allocations import is_budget_approach

        budget_approaches = [
            "equal-per-capita-budget",
            "per-capita-adjusted-budget",
            "per-capita-adjusted-gini-budget",
        ]
        pathway_approaches = [
            "equal-per-capita",
            "per-capita-adjusted",
            "per-capita-adjusted-gini",
            "per-capita-convergence",
        ]

        for approach in budget_approaches:
            assert is_budget_approach(approach), f"{approach} should be budget approach"

        for approach in pathway_approaches:
            assert not is_budget_approach(
                approach
            ), f"{approach} should not be budget approach"

    def test_is_pathway_approach(self, allocation_manager):
        """Test identification of pathway approaches."""
        from fair_shares.library.allocations import is_pathway_approach

        budget_approaches = [
            "equal-per-capita-budget",
            "per-capita-adjusted-budget",
            "per-capita-adjusted-gini-budget",
        ]
        pathway_approaches = [
            "equal-per-capita",
            "per-capita-adjusted",
            "per-capita-adjusted-gini",
            "per-capita-convergence",
        ]

        for approach in pathway_approaches:
            assert is_pathway_approach(
                approach
            ), f"{approach} should be pathway approach"

        for approach in budget_approaches:
            assert not is_pathway_approach(
                approach
            ), f"{approach} should not be pathway approach"

    @pytest.mark.parametrize(
        "approach",
        [
            "equal-per-capita",
            "per-capita-adjusted",
            "per-capita-adjusted-gini",
            "per-capita-convergence",
        ],
    )
    def test_pathway_allocations(
        self, allocation_manager, test_config, test_data, approach
    ):
        """Test that manager can run pathway allocation approaches."""
        result = allocation_manager.run_allocation(
            approach=approach,
            config=test_config,
            population_ts=test_data["population"],
            first_allocation_year=2020,
            country_actual_emissions_ts=(
                test_data["emissions"] if "convergence" in approach else None
            ),
            emission_category=STANDARD_EMISSION_CATEGORY,
            convergence_year=2050 if "convergence" in approach else None,
            gdp_ts=test_data["gdp"] if "adjusted" in approach else None,
            gini_s=test_data["gini"] if "gini" in approach else None,
            capability_weight=1.0 if "adjusted" in approach else 0.0,
        )

        # Test result type and basic properties
        assert isinstance(result, PathwayAllocationResult)
        assert result.approach == approach
        assert result.parameters["first_allocation_year"] == 2020

        # Test that result is not empty
        shares_df = result.relative_shares_pathway_emissions
        assert isinstance(shares_df, pd.DataFrame)
        assert len(shares_df) > 0
        assert len(shares_df.columns) > 0

        # Test that emission category matches
        emission_cat = shares_df.index.get_level_values("emission-category").unique()
        assert len(emission_cat) == 1
        assert emission_cat == STANDARD_EMISSION_CATEGORY

    @pytest.mark.parametrize(
        "inputs,expected_approach,approach_name,expected_normalized",
        [
            # Base: no adjustments
            (
                {"capability_weight": 0.0, "responsibility_weight": 0.0},
                "cumulative-per-capita-convergence",
                "cumulative-per-capita-convergence",
                {"capability_weight": 0.0, "responsibility_weight": 0.0},
            ),
            # Adjusted: capability only (0.5/0.5 = 1.0, 0.0/0.5 = 0.0)
            (
                {"capability_weight": 0.5, "responsibility_weight": 0.0},
                "cumulative-per-capita-convergence-adjusted",
                "cumulative-per-capita-convergence-adjusted",
                {"capability_weight": 1.0, "responsibility_weight": 0.0},
            ),
            # Adjusted: responsibility only (0.0/0.5 = 0.0, 0.5/0.5 = 1.0)
            (
                {"capability_weight": 0.0, "responsibility_weight": 0.5},
                "cumulative-per-capita-convergence-adjusted",
                "cumulative-per-capita-convergence-adjusted",
                {"capability_weight": 0.0, "responsibility_weight": 1.0},
            ),
            # Adjusted: both (0.3/0.6 = 0.5, 0.3/0.6 = 0.5)
            (
                {"capability_weight": 0.3, "responsibility_weight": 0.3},
                "cumulative-per-capita-convergence-adjusted",
                "cumulative-per-capita-convergence-adjusted",
                {"capability_weight": 0.5, "responsibility_weight": 0.5},
            ),
        ],
    )
    def test_cumulative_per_capita_convergence_variants(
        self,
        allocation_manager,
        test_config,
        test_data,
        inputs,
        expected_approach,
        approach_name,
        expected_normalized,
    ):
        """Test cumulative per capita convergence variants with different approaches."""
        result = allocation_manager.run_allocation(
            approach=approach_name,
            config=test_config,
            population_ts=test_data["population"],
            first_allocation_year=2020,
            country_actual_emissions_ts=test_data["emissions"],
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=test_data["world-emissions"],
            gdp_ts=test_data["gdp"] if inputs.get("capability_weight", 0) > 0 else None,
            **inputs,
        )

        assert isinstance(result, PathwayAllocationResult)
        assert result.approach == expected_approach
        assert result.parameters["first_allocation_year"] == 2020
        # Check normalized weights are stored
        assert (
            abs(
                result.parameters["capability_weight"]
                - expected_normalized["capability_weight"]
            )
            < 1e-10
        )
        assert (
            abs(
                result.parameters["responsibility_weight"]
                - expected_normalized["responsibility_weight"]
            )
            < 1e-10
        )

    def test_cumulative_per_capita_convergence_gini_variant(
        self, allocation_manager, test_config, test_data
    ):
        """Test gini-adjusted variant by calling the specific approach."""
        result = allocation_manager.run_allocation(
            approach="cumulative-per-capita-convergence-gini-adjusted",
            config=test_config,
            population_ts=test_data["population"],
            first_allocation_year=2020,
            country_actual_emissions_ts=test_data["emissions"],
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=test_data["world-emissions"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            capability_weight=0.5,
        )

        assert isinstance(result, PathwayAllocationResult)
        assert result.approach == "cumulative-per-capita-convergence-gini-adjusted"

    @pytest.mark.parametrize(
        "approach",
        [
            "equal-per-capita-budget",
            "per-capita-adjusted-budget",
            "per-capita-adjusted-gini-budget",
        ],
    )
    def test_budget_allocations(
        self, allocation_manager, test_config, test_data, approach
    ):
        """Test that manager can run budget allocation approaches."""
        result = allocation_manager.run_allocation(
            approach=approach,
            config=test_config,
            population_ts=test_data["population"],
            allocation_year=2020,
            gdp_ts=test_data["gdp"] if "adjusted" in approach else None,
            gini_s=test_data["gini"] if "gini" in approach else None,
            capability_weight=1.0 if "adjusted" in approach else 0.0,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Test result type and basic properties
        assert isinstance(result, BudgetAllocationResult)
        assert result.approach == approach
        assert result.parameters["allocation_year"] == 2020

        # Test that result is not empty
        shares_df = result.relative_shares_cumulative_emission
        assert isinstance(shares_df, pd.DataFrame)
        assert len(shares_df) > 0
        assert len(shares_df.columns) > 0

        # Test emission category
        emission_category = shares_df.index.get_level_values(
            "emission-category"
        ).unique()
        assert len(emission_category) == 1
        assert emission_category == STANDARD_EMISSION_CATEGORY

    def test_parameter_validation(self, allocation_manager, test_config, test_data):
        """Test that manager properly validates required parameters."""

        # Test missing first_allocation_year for pathway approaches
        with pytest.raises(AllocationError, match="first_allocation_year required"):
            allocation_manager.run_allocation(
                approach="equal-per-capita",
                config=test_config,
                population_ts=test_data["population"],
                emission_category=STANDARD_EMISSION_CATEGORY,
            )

        # Test missing allocation_year for budget approaches
        with pytest.raises(AllocationError, match="allocation_year required"):
            allocation_manager.run_allocation(
                approach="equal-per-capita-budget",
                config=test_config,
                population_ts=test_data["population"],
                emission_category=STANDARD_EMISSION_CATEGORY,
            )

        # Test missing GDP data for GDP-adjusted approaches (when capability_weight > 0)
        with pytest.raises(
            AllocationError, match="Missing required data for capability adjustment"
        ):
            allocation_manager.run_allocation(
                approach="per-capita-adjusted",
                config=test_config,
                population_ts=test_data["population"],
                first_allocation_year=2020,
                capability_weight=1.0,
                emission_category=STANDARD_EMISSION_CATEGORY,
            )

        # Test missing GDP data for Gini-adjusted approaches
        with pytest.raises(AllocationError, match="Missing required data"):
            allocation_manager.run_allocation(
                approach="per-capita-adjusted-gini",
                config=test_config,
                population_ts=test_data["population"],
                first_allocation_year=2020,
                gini_s=test_data["gini"],
                emission_category=STANDARD_EMISSION_CATEGORY,
            )

        # Test missing emissions data for convergence approaches
        with pytest.raises(AllocationError, match="Emissions data required"):
            allocation_manager.run_allocation(
                approach="per-capita-convergence",
                config=test_config,
                population_ts=test_data["population"],
                first_allocation_year=2020,
                emission_category=STANDARD_EMISSION_CATEGORY,
            )

    def test_calculate_absolute_emissions_pathway(
        self, allocation_manager, test_config, test_data
    ):
        """Test calculate_absolute_emissions for pathway allocations."""
        result = allocation_manager.run_allocation(
            approach="equal-per-capita",
            config=test_config,
            population_ts=test_data["population"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Filter emissions data to match pathway shares years (from first_allocation_year onwards)
        pathway_years = result.relative_shares_pathway_emissions.columns
        emissions_data = test_data["emissions"][pathway_years].copy()

        absolute = allocation_manager.calculate_absolute_emissions(
            result=result,
            emissions_data=emissions_data,
        )

        assert isinstance(absolute, pd.DataFrame)
        assert len(absolute) > 0
        assert len(absolute.columns) > 0

        # Test that absolute emissions have correct structure
        assert isinstance(absolute.index, pd.MultiIndex)
        assert absolute.index.names == ["iso3c", "unit", "emission-category"]

        # Test that no NaN values are produced
        assert not absolute.isna().any().any()

    def test_calculate_absolute_emissions_budget_single_year(
        self, allocation_manager, test_config, test_data
    ):
        """Test calculate_absolute_emissions for budget allocations with single year."""
        result = allocation_manager.run_allocation(
            approach="equal-per-capita-budget",
            config=test_config,
            population_ts=test_data["population"],
            allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Create single-year emissions data for testing
        emissions_data = ensure_string_year_columns(
            test_data["emissions"][["2020"]].copy()
        )

        absolute = allocation_manager.calculate_absolute_emissions(
            result=result,
            emissions_data=emissions_data,
        )

        assert isinstance(absolute, pd.DataFrame)
        assert len(absolute) > 0
        assert len(absolute.columns) > 0

        # Test that absolute budgets have correct structure
        assert isinstance(absolute.index, pd.MultiIndex)
        assert absolute.index.names == ["iso3c", "unit", "emission-category"]

        # Test that no NaN values are produced
        assert not absolute.isna().any().any()

        # Test that budget has only one year column
        year_cols = [col for col in absolute.columns if str(col).isdigit()]
        assert len(year_cols) == 1
        assert int(year_cols[0]) == 2020

    def test_calculate_absolute_emissions_budget_multiple_years(
        self, allocation_manager, test_config, test_data
    ):
        """Test calculate_absolute_emissions for budget allocations with multiple years."""
        result = allocation_manager.run_allocation(
            approach="equal-per-capita-budget",
            config=test_config,
            population_ts=test_data["population"],
            allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Create single-year emissions data for testing (budget allocations use only allocation_year)
        emissions_data = ensure_string_year_columns(
            test_data["emissions"][["2020"]].copy()
        )

        absolute = allocation_manager.calculate_absolute_emissions(
            result=result,
            emissions_data=emissions_data,
        )

        assert isinstance(absolute, pd.DataFrame)
        assert len(absolute) > 0
        assert len(absolute.columns) > 0

        # Test that absolute budgets have correct structure
        assert isinstance(absolute.index, pd.MultiIndex)
        assert absolute.index.names == ["iso3c", "unit", "emission-category"]

        # Test that no NaN values are produced
        assert not absolute.isna().any().any()

        # Test that budget has only one year column (allocation_year)
        year_cols = [col for col in absolute.columns if str(col).isdigit()]
        assert len(year_cols) == 1
        assert int(year_cols[0]) == 2020

        # Verify that allocated budgets sum to the world total for the allocation year
        world_emissions_sum = emissions_data.loc[
            ("World", "Mt * CO2e", STANDARD_EMISSION_CATEGORY), "2020"
        ]
        allocated_sum = absolute["2020"].sum()
        assert abs(allocated_sum - world_emissions_sum) < 1e-10

    def test_calculate_absolute_emissions_multiple_categories_error(
        self, allocation_manager, test_config, test_data
    ):
        """Test that calculate_absolute_emissions raises error for multiple emission categories."""
        result = allocation_manager.run_allocation(
            approach="equal-per-capita-budget",
            config=test_config,
            population_ts=test_data["population"],
            allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Add a second emission category (but keep only one year for budget allocation)
        multi_category_data = []
        countries = ["AAA", "BBB", "CCC", "DDD", "World"]
        year = 2020  # Only one year for budget allocation
        categories = [STANDARD_EMISSION_CATEGORY, "co2-lulucf"]

        for country in countries:
            for category in categories:
                emissions = 10
                if country == "World":
                    emissions *= len(countries) - 1  # World total
                multi_category_data.append(
                    [country, "Mt * CO2e", category, year, emissions]
                )

        multi_category_df = pd.DataFrame(
            multi_category_data,
            columns=["iso3c", "unit", "emission-category", "year", "emissions"],
        ).pivot_table(
            index=["iso3c", "unit", "emission-category"],
            columns="year",
            values="emissions",
        )
        multi_category_df = ensure_string_year_columns(multi_category_df)

        # Test that it raises the correct error
        from fair_shares.library.exceptions import AllocationError

        with pytest.raises(
            AllocationError, match="must contain exactly one emission category, found:"
        ):
            allocation_manager.calculate_absolute_emissions(
                result=result,
                emissions_data=multi_category_df,
            )

    def test_calculate_absolute_emissions_single_year_mismatch(
        self, allocation_manager, test_config, test_data
    ):
        """Test that calculate_absolute_emissions raises error when single year doesn't match allocation_year."""
        result = allocation_manager.run_allocation(
            approach="equal-per-capita-budget",
            config=test_config,
            population_ts=test_data["population"],
            allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Create single-year emissions data with wrong year
        emissions_data = ensure_string_year_columns(
            test_data["emissions"][["2030"]].copy()
        )

        # Test that it raises the correct error
        with pytest.raises(
            AllocationError,
            match="remaining budget year 2030 does not match cumulative emission shares year 2020",
        ):
            allocation_manager.calculate_absolute_emissions(
                result=result,
                emissions_data=emissions_data,
            )

    def test_calculate_absolute_emissions_no_world_data(
        self, allocation_manager, test_config, test_data
    ):
        """Test that calculate_absolute_emissions raises error when no World data is present."""
        result = allocation_manager.run_allocation(
            approach="equal-per-capita-budget",
            config=test_config,
            population_ts=test_data["population"],
            allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Create emissions data with only the allocation year and without World totals
        emissions_data = ensure_string_year_columns(
            test_data["emissions"][["2020"]].drop(
                ("World", "Mt * CO2e", STANDARD_EMISSION_CATEGORY)
            )
        )

        # Test that it raises the correct error
        with pytest.raises(
            AllocationError, match="No 'World' data found in remaining budget"
        ):
            allocation_manager.calculate_absolute_emissions(
                result=result,
                emissions_data=emissions_data,
            )

    def test_calculate_absolute_emissions_empty_data(
        self, allocation_manager, test_config, test_data
    ):
        """Test that calculate_absolute_emissions raises error when emissions data is empty."""
        result = allocation_manager.run_allocation(
            approach="equal-per-capita-budget",
            config=test_config,
            population_ts=test_data["population"],
            allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Create empty emissions data
        empty_emissions = pd.DataFrame(columns=["2020"])
        empty_emissions.index = pd.MultiIndex.from_tuples(
            [], names=["iso3c", "unit", "emission-category"]
        )

        # Test that it raises the correct error
        with pytest.raises(
            AllocationError, match="No 'World' data found in remaining budget"
        ):
            allocation_manager.calculate_absolute_emissions(
                result=result,
                emissions_data=empty_emissions,
            )

    def test_extended_parameters(self, allocation_manager, test_config, test_data):
        """Test that manager handles extended parameters correctly."""

        # Test GDP-adjusted with capability_exponent parameter
        result = allocation_manager.run_allocation(
            approach="per-capita-adjusted",
            config=test_config,
            population_ts=test_data["population"],
            first_allocation_year=2020,
            gdp_ts=test_data["gdp"],
            capability_weight=1.0,
            capability_exponent=0.5,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )
        assert result.parameters["capability_exponent"] == 0.5

        # Test GDP-adjusted with capability_functional_form parameter
        result = allocation_manager.run_allocation(
            approach="per-capita-adjusted",
            config=test_config,
            population_ts=test_data["population"],
            first_allocation_year=2020,
            gdp_ts=test_data["gdp"],
            capability_weight=1.0,
            capability_functional_form="asinh",
            emission_category=STANDARD_EMISSION_CATEGORY,
        )
        assert result.parameters["capability_functional_form"] == "asinh"

        # Test convergence with convergence_year parameter
        result = allocation_manager.run_allocation(
            approach="per-capita-convergence",
            config=test_config,
            population_ts=test_data["population"],
            first_allocation_year=2020,
            country_actual_emissions_ts=test_data["emissions"],
            convergence_year=2050,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )
        assert result.parameters["convergence_year"] == 2050

    def test_result_validation_through_manager(
        self, allocation_manager, test_config, test_data
    ):
        """Test that results created through manager pass validation automatically."""

        # Test pathway result validation
        pathway_result = allocation_manager.run_allocation(
            approach="equal-per-capita",
            config=test_config,
            population_ts=test_data["population"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Result should already be validated due to result class __attrs_post_init__
        assert isinstance(pathway_result, PathwayAllocationResult)

        # Test budget result validation
        budget_result = allocation_manager.run_allocation(
            approach="equal-per-capita-budget",
            config=test_config,
            population_ts=test_data["population"],
            allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Result should already be validated due to result class __attrs_post_init__
        assert isinstance(budget_result, BudgetAllocationResult)
