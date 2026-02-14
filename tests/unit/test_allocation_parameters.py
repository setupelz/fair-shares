"""
Parameter variation tests for allocation functions for the fair-shares library.

"""

from __future__ import annotations

from conftest import STANDARD_EMISSION_CATEGORY

from fair_shares.library.allocations.budgets import (
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)
from fair_shares.library.allocations.pathways import (
    cumulative_per_capita_convergence,
    cumulative_per_capita_convergence_adjusted,
    per_capita_adjusted,
    per_capita_adjusted_gini,
    per_capita_convergence,
)
from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.utils import (
    get_default_unit_registry,
)


class TestAllocationParameters:
    """Test parameter variations for allocation functions."""

    def test_gdp_adjusted_exponents(self, test_data):
        """Test that different exponents produce different results."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test different exponents
        results = {}
        for exponent in [0.5, 1.0, 2.0]:
            result = per_capita_adjusted(
                population_ts=population,
                gdp_ts=gdp,
                first_allocation_year=first_allocation_year,
                emission_category=STANDARD_EMISSION_CATEGORY,
                capability_weight=1.0,
                capability_exponent=exponent,
                ur=ur,
            )

            # Test result type and metadata
            assert isinstance(result, PathwayAllocationResult)
            assert result.approach == "per-capita-adjusted"
            assert result.parameters["capability_exponent"] == exponent

            results[exponent] = result.relative_shares_pathway_emissions

        # Results should be different for different exponents
        assert not results[0.5].equals(
            results[1.0]
        ), "Different exponents should produce different results"
        assert not results[1.0].equals(
            results[2.0]
        ), "Different exponents should produce different results"

    def test_gdp_adjusted_functional_forms(self, test_data):
        """Test that different functional forms work correctly."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test power function (default)
        power_result = per_capita_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_functional_form="power",
            capability_exponent=1.0,
            ur=ur,
        )

        # Test asinh function
        asinh_result = per_capita_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_functional_form="asinh",
            capability_exponent=1.0,
            ur=ur,
        )

        # Test result types and metadata
        assert isinstance(power_result, PathwayAllocationResult)
        assert isinstance(asinh_result, PathwayAllocationResult)
        assert power_result.parameters["capability_functional_form"] == "power"
        assert asinh_result.parameters["capability_functional_form"] == "asinh"

        # Both should sum to 1 (validation ensures this)
        power_shares = power_result.relative_shares_pathway_emissions
        asinh_shares = asinh_result.relative_shares_pathway_emissions

        # Results should be different
        assert not power_shares.equals(
            asinh_shares
        ), "Power and asinh functional forms should produce different results"

    def test_gini_adjusted_income_floor(self, test_data):
        """Test that different income floors work correctly."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        gini_data = test_data["gini"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test different income floors
        results = {}
        for income_floor in [0.0, 1000.0, 5000.0]:
            result = per_capita_adjusted_gini(
                population_ts=population,
                gdp_ts=gdp,
                gini_s=gini_data,
                first_allocation_year=first_allocation_year,
                emission_category=STANDARD_EMISSION_CATEGORY,
                capability_weight=1.0,
                income_floor=income_floor,
                ur=ur,
            )

            # Test result type and metadata
            assert isinstance(result, PathwayAllocationResult)
            assert result.approach == "per-capita-adjusted-gini"
            assert result.parameters["income_floor"] == income_floor

            results[income_floor] = result.relative_shares_pathway_emissions

    def test_convergence_years(self, test_data):
        """Test that different convergence years work correctly."""
        population = test_data["population"]
        emissions = test_data["emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test different convergence years
        results = {}
        for convergence_year in [2040, 2050, 2070]:
            result = per_capita_convergence(
                population_ts=population,
                country_actual_emissions_ts=emissions,
                first_allocation_year=first_allocation_year,
                emission_category=STANDARD_EMISSION_CATEGORY,
                convergence_year=convergence_year,
                ur=ur,
            )

            # Test result type and metadata
            assert isinstance(result, PathwayAllocationResult)
            assert result.approach == "per-capita-convergence"
            assert result.parameters["convergence_year"] == convergence_year

            results[convergence_year] = result.relative_shares_pathway_emissions

        # All should sum to 1 (validation ensures this)
        for convergence_year, shares_df in results.items():
            for year in shares_df.columns:
                shares_sum = shares_df[year].sum()
                assert (
                    abs(shares_sum - 1.0) < 1e-10
                ), f"Convergence year {convergence_year} shares don't sum to 1 at year {year}: {shares_sum}"

        # Results should be different for different convergence years
        assert not results[2040].equals(
            results[2050]
        ), "Different convergence years should produce different results"

    def test_budget_allocation_parameters(self, test_data):
        """Test parameter variations for budget allocation functions."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        gini_data = test_data["gini"]
        allocation_year = test_data["allocation-year"]
        ur = get_default_unit_registry()

        # Test per capita adjusted budget with different exponents
        result1 = per_capita_adjusted_budget(
            population_ts=population,
            gdp_ts=gdp,
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_exponent=0.5,
            capability_weight=1.0,
            ur=ur,
        )

        result2 = per_capita_adjusted_budget(
            population_ts=population,
            gdp_ts=gdp,
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_exponent=1.0,
            capability_weight=1.0,
            ur=ur,
        )

        # Test result types and metadata
        assert isinstance(result1, BudgetAllocationResult)
        assert isinstance(result2, BudgetAllocationResult)
        assert result1.approach == "per-capita-adjusted-budget"
        assert result2.approach == "per-capita-adjusted-budget"
        assert result1.parameters["capability_exponent"] == 0.5
        assert result2.parameters["capability_exponent"] == 1.0

        # Test Gini-adjusted budget with different functional forms
        result3 = per_capita_adjusted_gini_budget(
            population_ts=population,
            gdp_ts=gdp,
            gini_s=gini_data,
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_functional_form="power",
            ur=ur,
        )

        result4 = per_capita_adjusted_gini_budget(
            population_ts=population,
            gdp_ts=gdp,
            gini_s=gini_data,
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_functional_form="asinh",
            ur=ur,
        )

        # Test result types and metadata
        assert isinstance(result3, BudgetAllocationResult)
        assert isinstance(result4, BudgetAllocationResult)
        assert result3.approach == "per-capita-adjusted-gini-budget"
        assert result4.approach == "per-capita-adjusted-gini-budget"
        assert result3.parameters["capability_functional_form"] == "power"
        assert result4.parameters["capability_functional_form"] == "asinh"

        # Both should have valid shares (validation ensures this)
        shares3 = result3.relative_shares_cumulative_emission
        shares4 = result4.relative_shares_cumulative_emission

        for year in shares3.columns:
            sum3 = shares3[year].sum()
            sum4 = shares4[year].sum()

            assert (
                abs(sum3 - 1.0) < 1e-7
            ), f"Power form shares don't sum to 1 at year {year}: {sum3}"
            assert (
                abs(sum4 - 1.0) < 1e-7
            ), f"Asinh form shares don't sum to 1 at year {year}: {sum4}"

    def test_parameter_persistence_in_results(self, test_data):
        """Test that custom parameters are correctly stored in result objects."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test multiple parameters at once
        result = per_capita_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_exponent=0.75,
            capability_functional_form="asinh",
            ur=ur,
        )

        # Test that all parameters are stored
        assert result.parameters["capability_exponent"] == 0.75
        assert result.parameters["capability_functional_form"] == "asinh"
        assert result.parameters["first_allocation_year"] == first_allocation_year
        assert result.parameters["emission_category"] == STANDARD_EMISSION_CATEGORY

    def test_edge_case_parameters(self, test_data):
        """Test that edge case parameters are handled correctly."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        gini_data = test_data["gini"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test very small exponent
        small_exp_result = per_capita_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_exponent=0.01,
            ur=ur,
        )

        # Test very large income floor for Gini
        large_floor_result = per_capita_adjusted_gini(
            population_ts=population,
            gdp_ts=gdp,
            gini_s=gini_data,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            income_floor=100000.0,
            ur=ur,
        )

        # Both should produce valid results
        assert isinstance(small_exp_result, PathwayAllocationResult)
        assert isinstance(large_floor_result, PathwayAllocationResult)

        # Check that no NaN values are produced
        small_exp_shares = small_exp_result.relative_shares_pathway_emissions
        large_floor_shares = large_floor_result.relative_shares_pathway_emissions

        assert not small_exp_shares.isna().any().any()
        assert not large_floor_shares.isna().any().any()

        # Check that shares still sum to 1 (validation ensures this)
        for year in small_exp_shares.columns:
            assert abs(small_exp_shares[year].sum() - 1.0) < 1e-7
        for year in large_floor_shares.columns:
            assert abs(large_floor_shares[year].sum() - 1.0) < 1e-7

    def test_per_capita_adjusted_responsibility_weight(self, test_data):
        """Test that responsibility_weight parameter works for per_capita_adjusted."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        emissions = test_data["emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test with responsibility_weight = 0 (no responsibility adjustment)
        result_no_resp = per_capita_adjusted(
            population_ts=population,
            country_actual_emissions_ts=emissions,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            responsibility_weight=0.0,
            capability_weight=1.0,
            ur=ur,
        )

        # Test with responsibility_weight > 0
        result_with_resp = per_capita_adjusted(
            population_ts=population,
            country_actual_emissions_ts=emissions,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            responsibility_weight=0.3,
            capability_weight=0.7,
            ur=ur,
        )

        # Verify normalized parameters stored correctly (0.3/1.0 = 0.3, 0.7/1.0 = 0.7)
        assert result_no_resp.parameters["responsibility_weight"] == 0.0
        assert abs(result_with_resp.parameters["responsibility_weight"] - 0.3) < 1e-10
        assert abs(result_with_resp.parameters["capability_weight"] - 0.7) < 1e-10

        # Results should differ when responsibility is applied
        assert not result_no_resp.relative_shares_pathway_emissions.equals(
            result_with_resp.relative_shares_pathway_emissions
        ), "Responsibility adjustment should change allocation"

    def test_per_capita_adjusted_responsibility_per_capita(self, test_data):
        """Test responsibility_per_capita parameter for per_capita_adjusted."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        emissions = test_data["emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test with per capita responsibility
        result_per_capita = per_capita_adjusted(
            population_ts=population,
            country_actual_emissions_ts=emissions,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            responsibility_weight=0.5,
            capability_weight=0.5,
            responsibility_per_capita=True,
            ur=ur,
        )

        # Test with absolute responsibility
        result_absolute = per_capita_adjusted(
            population_ts=population,
            country_actual_emissions_ts=emissions,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            responsibility_weight=0.5,
            capability_weight=0.5,
            responsibility_per_capita=False,
            ur=ur,
        )

        # Verify parameters
        assert result_per_capita.parameters["responsibility_per_capita"] is True
        assert result_absolute.parameters["responsibility_per_capita"] is False

        # Results should differ
        assert not result_per_capita.relative_shares_pathway_emissions.equals(
            result_absolute.relative_shares_pathway_emissions
        ), "Per capita vs absolute responsibility should produce different results"

    def test_per_capita_adjusted_mixed_adjustments(self, test_data):
        """Test combining responsibility and capability adjustments."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        emissions = test_data["emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test various weight combinations
        weight_combinations = [
            (0.5, 0.5),  # Equal weights
            (0.8, 0.2),  # More responsibility
            (0.2, 0.8),  # More capability
            (1.0, 0.0),  # Only responsibility
            (0.0, 1.0),  # Only capability
        ]

        results = {}
        for resp_w, cap_w in weight_combinations:
            result = per_capita_adjusted(
                population_ts=population,
                country_actual_emissions_ts=emissions,
                gdp_ts=gdp,
                first_allocation_year=first_allocation_year,
                emission_category=STANDARD_EMISSION_CATEGORY,
                responsibility_weight=resp_w,
                capability_weight=cap_w,
                ur=ur,
            )
            results[(resp_w, cap_w)] = result

            # Verify normalized weights stored correctly
            total_w = resp_w + cap_w
            if total_w > 0:
                expected_resp = resp_w / total_w
                expected_cap = cap_w / total_w
            else:
                expected_resp = 0.0
                expected_cap = 0.0
            assert (
                abs(result.parameters["responsibility_weight"] - expected_resp) < 1e-10
            )
            assert abs(result.parameters["capability_weight"] - expected_cap) < 1e-10

        # Different weight combinations should produce different results
        assert not results[(0.5, 0.5)].relative_shares_pathway_emissions.equals(
            results[(0.8, 0.2)].relative_shares_pathway_emissions
        )
        assert not results[(0.2, 0.8)].relative_shares_pathway_emissions.equals(
            results[(1.0, 0.0)].relative_shares_pathway_emissions
        )

    def test_cumulative_per_capita_convergence_responsibility_weight(self, test_data):
        """Test that different responsibility weights produce different results."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        test_data["gini"]
        emissions = test_data["emissions"]
        world_emissions = test_data["world-emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test with no responsibility (pure cumulative per capita)
        result_no_resp = cumulative_per_capita_convergence(
            population_ts=population,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            ur=ur,
        )

        # Test with some responsibility (weight = 0.5)
        result_with_resp = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            responsibility_weight=0.5,
            ur=ur,
        )

        # Test result types and metadata
        assert isinstance(result_no_resp, PathwayAllocationResult)
        assert isinstance(result_with_resp, PathwayAllocationResult)
        assert result_no_resp.approach == "cumulative-per-capita-convergence"
        assert result_with_resp.approach == "cumulative-per-capita-convergence-adjusted"
        assert result_no_resp.parameters["responsibility_weight"] == 0.0
        # With responsibility_weight=0.5 and capability_weight=0.0 (default), normalized is 1.0
        assert abs(result_with_resp.parameters["responsibility_weight"] - 1.0) < 1e-10

        # Results should be different
        shares_no_resp = result_no_resp.relative_shares_pathway_emissions
        shares_with_resp = result_with_resp.relative_shares_pathway_emissions
        assert not shares_no_resp.equals(
            shares_with_resp
        ), "Different responsibility weights should produce different results"

    def test_cumulative_per_capita_convergence_per_capita_modes(self, test_data):
        """Test per capita vs absolute modes for responsibility and capability."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        test_data["gini"]
        emissions = test_data["emissions"]
        world_emissions = test_data["world-emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test capability per capita mode (default)
        result_cap_per_cap = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            capability_weight=0.5,
            capability_per_capita=True,
            ur=ur,
        )

        # Test capability absolute mode
        result_cap_abs = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            capability_weight=0.5,
            capability_per_capita=False,
            ur=ur,
        )

        # Test with responsibility per capita mode
        result_resp_per_cap = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            responsibility_weight=0.5,
            responsibility_per_capita=True,
            ur=ur,
        )

        # Test with responsibility absolute mode
        result_resp_abs = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            responsibility_weight=0.5,
            responsibility_per_capita=False,
            ur=ur,
        )

        # All should produce valid results
        assert isinstance(result_cap_per_cap, PathwayAllocationResult)
        assert isinstance(result_cap_abs, PathwayAllocationResult)
        assert isinstance(result_resp_per_cap, PathwayAllocationResult)
        assert isinstance(result_resp_abs, PathwayAllocationResult)

        # Check parameters are stored correctly
        assert result_cap_per_cap.parameters["capability_per_capita"] is True
        assert result_cap_abs.parameters["capability_per_capita"] is False
        assert result_resp_per_cap.parameters["responsibility_per_capita"] is True
        assert result_resp_abs.parameters["responsibility_per_capita"] is False

        # Results should be different for different modes
        assert not result_cap_per_cap.relative_shares_pathway_emissions.equals(
            result_cap_abs.relative_shares_pathway_emissions
        ), "Per capita vs absolute capability should produce different results"
        assert not result_resp_per_cap.relative_shares_pathway_emissions.equals(
            result_resp_abs.relative_shares_pathway_emissions
        ), "Per capita vs absolute responsibility should produce different results"

    def test_cumulative_per_capita_convergence_exponents(self, test_data):
        """Test that different capability and responsibility exponents work."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        test_data["gini"]
        emissions = test_data["emissions"]
        world_emissions = test_data["world-emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test different capability exponents
        result_exp_05 = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            capability_weight=0.5,
            capability_exponent=0.5,
            ur=ur,
        )

        result_exp_10 = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            capability_weight=0.5,
            capability_exponent=1.0,
            ur=ur,
        )

        result_exp_20 = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            capability_weight=0.5,
            capability_exponent=2.0,
            ur=ur,
        )

        # Test result types and metadata
        assert isinstance(result_exp_05, PathwayAllocationResult)
        assert isinstance(result_exp_10, PathwayAllocationResult)
        assert isinstance(result_exp_20, PathwayAllocationResult)
        assert result_exp_05.parameters["capability_exponent"] == 0.5
        assert result_exp_10.parameters["capability_exponent"] == 1.0
        assert result_exp_20.parameters["capability_exponent"] == 2.0

        # Results should be different
        shares_05 = result_exp_05.relative_shares_pathway_emissions
        shares_10 = result_exp_10.relative_shares_pathway_emissions
        shares_20 = result_exp_20.relative_shares_pathway_emissions

        assert not shares_05.equals(
            shares_10
        ), "Different capability exponents should produce different results"
        assert not shares_10.equals(
            shares_20
        ), "Different capability exponents should produce different results"

        # Test different responsibility exponents
        result_resp_exp_05 = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            responsibility_weight=0.5,
            responsibility_exponent=0.5,
            ur=ur,
        )

        result_resp_exp_20 = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            responsibility_weight=0.5,
            responsibility_exponent=2.0,
            ur=ur,
        )

        assert isinstance(result_resp_exp_05, PathwayAllocationResult)
        assert isinstance(result_resp_exp_20, PathwayAllocationResult)
        assert result_resp_exp_05.parameters["responsibility_exponent"] == 0.5
        assert result_resp_exp_20.parameters["responsibility_exponent"] == 2.0

        # Results should be different
        assert not result_resp_exp_05.relative_shares_pathway_emissions.equals(
            result_resp_exp_20.relative_shares_pathway_emissions
        ), "Different responsibility exponents should produce different results"

    def test_cumulative_per_capita_convergence_functional_forms(self, test_data):
        """Test that different functional forms work for capability and responsibility."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        test_data["gini"]
        emissions = test_data["emissions"]
        world_emissions = test_data["world-emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test capability functional forms
        result_power = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            capability_weight=0.5,
            capability_functional_form="power",
            ur=ur,
        )

        result_asinh = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            capability_weight=0.5,
            capability_functional_form="asinh",
            ur=ur,
        )

        assert isinstance(result_power, PathwayAllocationResult)
        assert isinstance(result_asinh, PathwayAllocationResult)
        assert result_power.parameters["capability_functional_form"] == "power"
        assert result_asinh.parameters["capability_functional_form"] == "asinh"

        # Results should be different
        assert not result_power.relative_shares_pathway_emissions.equals(
            result_asinh.relative_shares_pathway_emissions
        ), "Power and asinh capability forms should produce different results"

        # Test responsibility functional forms
        result_resp_power = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            responsibility_weight=0.5,
            responsibility_functional_form="power",
            ur=ur,
        )

        result_resp_asinh = cumulative_per_capita_convergence_adjusted(
            population_ts=population,
            gdp_ts=gdp,
            country_actual_emissions_ts=emissions,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            world_scenario_emissions_ts=world_emissions,
            responsibility_weight=0.5,
            responsibility_functional_form="asinh",
            ur=ur,
        )

        assert isinstance(result_resp_power, PathwayAllocationResult)
        assert isinstance(result_resp_asinh, PathwayAllocationResult)
        assert result_resp_power.parameters["responsibility_functional_form"] == "power"
        assert result_resp_asinh.parameters["responsibility_functional_form"] == "asinh"

        # Results should be different
        assert not result_resp_power.relative_shares_pathway_emissions.equals(
            result_resp_asinh.relative_shares_pathway_emissions
        ), "Power and asinh responsibility forms should produce different results"

    def test_per_capita_adjusted_weight_normalization_pathway(self, test_data):
        """Test that capability and responsibility weights are normalized to their sum."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        emissions = test_data["emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test various weight combinations
        test_cases = [
            (0.3, 0.7, 0.3 / 1.0, 0.7 / 1.0),  # Expected: 0.3, 0.7
            (0.5, 0.5, 0.5 / 1.0, 0.5 / 1.0),  # Expected: 0.5, 0.5
            (0.2, 0.8, 0.2 / 1.0, 0.8 / 1.0),  # Expected: 0.2, 0.8
            (0.1, 0.4, 0.1 / 0.5, 0.4 / 0.5),  # Expected: 0.2, 0.8
            (1.0, 0.0, 1.0, 0.0),  # Expected: 1.0, 0.0
            (0.0, 1.0, 0.0, 1.0),  # Expected: 0.0, 1.0
        ]

        for resp_w, cap_w, expected_resp, expected_cap in test_cases:
            result = per_capita_adjusted(
                population_ts=population,
                country_actual_emissions_ts=emissions,
                gdp_ts=gdp,
                first_allocation_year=first_allocation_year,
                emission_category=STANDARD_EMISSION_CATEGORY,
                responsibility_weight=resp_w,
                capability_weight=cap_w,
                ur=ur,
            )

            # Check normalized weights are stored correctly
            assert (
                abs(result.parameters["responsibility_weight"] - expected_resp) < 1e-10
            ), (
                f"Expected responsibility_weight={expected_resp} for inputs ({resp_w}, {cap_w}), "
                f"got {result.parameters['responsibility_weight']}"
            )
            assert abs(result.parameters["capability_weight"] - expected_cap) < 1e-10, (
                f"Expected capability_weight={expected_cap} for inputs ({resp_w}, {cap_w}), "
                f"got {result.parameters['capability_weight']}"
            )

            # When both weights are > 0, they should sum to 1.0
            if resp_w > 0 and cap_w > 0:
                weight_sum = (
                    result.parameters["responsibility_weight"]
                    + result.parameters["capability_weight"]
                )
                assert (
                    abs(weight_sum - 1.0) < 1e-10
                ), f"Normalized weights should sum to 1.0, got {weight_sum}"

    def test_per_capita_adjusted_gini_weight_normalization_pathway(self, test_data):
        """Test weight normalization for Gini-adjusted pathway allocation."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        gini_data = test_data["gini"]
        emissions = test_data["emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test weight combination
        resp_w, cap_w = 0.4, 0.6
        expected_resp = 0.4 / 1.0
        expected_cap = 0.6 / 1.0

        result = per_capita_adjusted_gini(
            population_ts=population,
            country_actual_emissions_ts=emissions,
            gdp_ts=gdp,
            gini_s=gini_data,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            responsibility_weight=resp_w,
            capability_weight=cap_w,
            ur=ur,
        )

        # Check normalized weights
        assert abs(result.parameters["responsibility_weight"] - expected_resp) < 1e-10
        assert abs(result.parameters["capability_weight"] - expected_cap) < 1e-10

        # Should sum to 1.0
        weight_sum = (
            result.parameters["responsibility_weight"]
            + result.parameters["capability_weight"]
        )
        assert abs(weight_sum - 1.0) < 1e-10

    def test_per_capita_adjusted_weight_normalization_budget(self, test_data):
        """Test that capability and responsibility weights are normalized for budget allocations."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        emissions = test_data["emissions"]
        allocation_year = test_data["allocation-year"]
        ur = get_default_unit_registry()

        # Test various weight combinations
        test_cases = [
            (0.3, 0.7, 0.3 / 1.0, 0.7 / 1.0),
            (0.5, 0.5, 0.5 / 1.0, 0.5 / 1.0),
            (0.25, 0.75, 0.25 / 1.0, 0.75 / 1.0),
        ]

        for resp_w, cap_w, expected_resp, expected_cap in test_cases:
            result = per_capita_adjusted_budget(
                population_ts=population,
                country_actual_emissions_ts=emissions,
                gdp_ts=gdp,
                allocation_year=allocation_year,
                emission_category=STANDARD_EMISSION_CATEGORY,
                responsibility_weight=resp_w,
                capability_weight=cap_w,
                ur=ur,
            )

            # Check normalized weights are stored correctly
            assert (
                abs(result.parameters["responsibility_weight"] - expected_resp) < 1e-10
            ), (
                f"Expected responsibility_weight={expected_resp}, "
                f"got {result.parameters['responsibility_weight']}"
            )
            assert abs(result.parameters["capability_weight"] - expected_cap) < 1e-10, (
                f"Expected capability_weight={expected_cap}, "
                f"got {result.parameters['capability_weight']}"
            )

            # Should sum to 1.0
            weight_sum = (
                result.parameters["responsibility_weight"]
                + result.parameters["capability_weight"]
            )
            assert abs(weight_sum - 1.0) < 1e-10

    def test_per_capita_adjusted_gini_weight_normalization_budget(self, test_data):
        """Test weight normalization for Gini-adjusted budget allocation."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        gini_data = test_data["gini"]
        emissions = test_data["emissions"]
        allocation_year = test_data["allocation-year"]
        ur = get_default_unit_registry()

        resp_w, cap_w = 0.35, 0.65
        expected_resp = 0.35 / 1.0
        expected_cap = 0.65 / 1.0

        result = per_capita_adjusted_gini_budget(
            population_ts=population,
            country_actual_emissions_ts=emissions,
            gdp_ts=gdp,
            gini_s=gini_data,
            allocation_year=allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            responsibility_weight=resp_w,
            capability_weight=cap_w,
            ur=ur,
        )

        # Check normalized weights
        assert abs(result.parameters["responsibility_weight"] - expected_resp) < 1e-10
        assert abs(result.parameters["capability_weight"] - expected_cap) < 1e-10

        # Should sum to 1.0
        weight_sum = (
            result.parameters["responsibility_weight"]
            + result.parameters["capability_weight"]
        )
        assert abs(weight_sum - 1.0) < 1e-10

    def test_cumulative_per_capita_convergence_weight_normalization(self, test_data):
        """Test weight normalization for cumulative per capita convergence."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        emissions = test_data["emissions"]
        world_emissions = test_data["world-emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test various weight combinations
        test_cases = [
            (0.3, 0.7, 0.3 / 1.0, 0.7 / 1.0),
            (0.5, 0.5, 0.5 / 1.0, 0.5 / 1.0),
            (0.1, 0.9, 0.1 / 1.0, 0.9 / 1.0),
            (0.8, 0.2, 0.8 / 1.0, 0.2 / 1.0),
        ]

        for resp_w, cap_w, expected_resp, expected_cap in test_cases:
            result = cumulative_per_capita_convergence_adjusted(
                population_ts=population,
                gdp_ts=gdp,
                country_actual_emissions_ts=emissions,
                first_allocation_year=first_allocation_year,
                emission_category=STANDARD_EMISSION_CATEGORY,
                world_scenario_emissions_ts=world_emissions,
                responsibility_weight=resp_w,
                capability_weight=cap_w,
                ur=ur,
            )

            # Check normalized weights are stored correctly
            assert (
                abs(result.parameters["responsibility_weight"] - expected_resp) < 1e-10
            ), (
                f"Expected responsibility_weight={expected_resp} for inputs ({resp_w}, {cap_w}), "
                f"got {result.parameters['responsibility_weight']}"
            )
            assert abs(result.parameters["capability_weight"] - expected_cap) < 1e-10, (
                f"Expected capability_weight={expected_cap} for inputs ({resp_w}, {cap_w}), "
                f"got {result.parameters['capability_weight']}"
            )

            # Should sum to 1.0
            weight_sum = (
                result.parameters["responsibility_weight"]
                + result.parameters["capability_weight"]
            )
            assert (
                abs(weight_sum - 1.0) < 1e-10
            ), f"Normalized weights should sum to 1.0, got {weight_sum}"

    def test_weight_normalization_zero_weights(self, test_data):
        """Test that zero weights are handled correctly in normalization."""
        population = test_data["population"]
        gdp = test_data["gdp"]
        emissions = test_data["emissions"]
        first_allocation_year = test_data["first-allocation-year"]
        ur = get_default_unit_registry()

        # Test with both weights at 0 (pure per capita)
        result = per_capita_adjusted(
            population_ts=population,
            country_actual_emissions_ts=emissions,
            gdp_ts=gdp,
            first_allocation_year=first_allocation_year,
            emission_category=STANDARD_EMISSION_CATEGORY,
            responsibility_weight=0.0,
            capability_weight=0.0,
            ur=ur,
        )

        # Both normalized weights should be 0.0
        assert result.parameters["responsibility_weight"] == 0.0
        assert result.parameters["capability_weight"] == 0.0

        # Approach should be equal-per-capita when no adjustments
        assert result.approach == "equal-per-capita"
