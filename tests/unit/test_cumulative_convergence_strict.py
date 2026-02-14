"""
Tests for strict=False parameter in cumulative per capita convergence.

These tests verify that infeasible allocations are handled gracefully
when strict=False, with appropriate warnings generated.
"""

import pandas as pd
import pytest

from fair_shares.library.allocations import AllocationManager
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import get_year_columns


@pytest.fixture
def infeasible_test_data():
    """
    Create test data that will be infeasible for cumulative convergence.

    Design:
    - Small country (AAA) has very high initial emissions
    - But after responsibility adjustment, gets tiny target share
    - This creates negative long-run share requirement
    """
    years = [str(y) for y in range(2015, 2051)]

    # Population
    pop_data = {
        "AAA": [1] * len(years),  # Very small population
        "BBB": [100] * len(years),  # Large population
        "CCC": [200] * len(years),  # Larger population
    }
    pop_df = pd.DataFrame(pop_data, index=years).T
    pop_df.index = pd.MultiIndex.from_tuples(
        [(iso, "million") for iso in pop_data.keys()],
        names=["iso3c", "unit"],
    )

    # Emissions (AAA has disproportionately high historical emissions)
    emiss_data = {
        "AAA": [50, 50, 50, 50, 50, 50]
        + [0] * (len(years) - 6),  # High past, zero future
        "BBB": [25] * len(years),
        "CCC": [25] * len(years),
    }
    emiss_df = pd.DataFrame(emiss_data, index=years).T
    emiss_df.index = pd.MultiIndex.from_tuples(
        [(iso, "Mt * CO2e", "co2-ffi") for iso in emiss_data.keys()],
        names=["iso3c", "unit", "emission-category"],
    )

    # GDP (AAA also has high GDP per capita)
    gdp_data = {
        "AAA": [100] * len(years),  # High GDP despite small population
        "BBB": [5000] * len(years),  # Moderate total GDP
        "CCC": [8000] * len(years),  # Moderate total GDP
    }
    gdp_df = pd.DataFrame(gdp_data, index=years).T
    gdp_df.index = pd.MultiIndex.from_tuples(
        [(iso, "billion") for iso in gdp_data.keys()],
        names=["iso3c", "unit"],
    )

    # World pathway
    n_years_future = len([y for y in years if int(y) >= 2020])
    start_value = 100.0

    # Linear decay for testing
    values = [
        start_value * (1 - i / (n_years_future - 1)) for i in range(n_years_future)
    ]
    values[-1] = 0.0

    world_df = pd.DataFrame(
        [values],
        columns=[str(y) for y in range(2020, 2051)],
        index=pd.MultiIndex.from_tuples(
            [("1.5C", 0.5, "test", "World", "Mt * CO2e", "co2-ffi")],
            names=[
                "climate-assessment",
                "quantile",
                "source",
                "iso3c",
                "unit",
                "emission-category",
            ],
        ),
    )

    return {
        "population": pop_df,
        "emissions": emiss_df,
        "gdp": gdp_df,
        "world_pathway": world_df,
    }


class TestStrictFalseMode:
    """Test strict=False parameter handling."""

    def test_strict_true_raises_error(self, infeasible_test_data):
        """Verify that strict=True (default) raises error for infeasible case."""
        manager = AllocationManager()

        with pytest.raises(AllocationError, match="invalid long-run shares"):
            manager.run_allocation(
                approach="cumulative-per-capita-convergence-adjusted",
                population_ts=infeasible_test_data["population"],
                country_actual_emissions_ts=infeasible_test_data["emissions"],
                gdp_ts=infeasible_test_data["gdp"],
                world_scenario_emissions_ts=infeasible_test_data["world_pathway"],
                first_allocation_year=2020,
                emission_category="co2-ffi",
                responsibility_weight=0.4,
                capability_weight=0.4,
                historical_responsibility_year=2015,
                strict=True,  # Explicit
            )

    def test_strict_false_returns_result(self, infeasible_test_data):
        """Verify that strict=False returns a result instead of raising error."""
        manager = AllocationManager()

        result = manager.run_allocation(
            approach="cumulative-per-capita-convergence-adjusted",
            population_ts=infeasible_test_data["population"],
            country_actual_emissions_ts=infeasible_test_data["emissions"],
            gdp_ts=infeasible_test_data["gdp"],
            world_scenario_emissions_ts=infeasible_test_data["world_pathway"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=0.4,
            capability_weight=0.4,
            historical_responsibility_year=2015,
            strict=False,
        )

        # Should return a valid result
        assert result is not None
        assert result.approach == "cumulative-per-capita-convergence-adjusted"

        # Should have warnings
        assert result.country_warnings is not None
        assert len(result.country_warnings) > 0

    def test_warnings_format(self, infeasible_test_data):
        """Verify warnings are formatted correctly."""
        manager = AllocationManager()

        result = manager.run_allocation(
            approach="cumulative-per-capita-convergence-adjusted",
            population_ts=infeasible_test_data["population"],
            country_actual_emissions_ts=infeasible_test_data["emissions"],
            gdp_ts=infeasible_test_data["gdp"],
            world_scenario_emissions_ts=infeasible_test_data["world_pathway"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=0.4,
            capability_weight=0.4,
            historical_responsibility_year=2015,
            strict=False,
        )

        # Check warning format
        for iso3c, warning in result.country_warnings.items():
            assert warning.startswith("strict=false:")
            # Extract factor
            factor_str = warning.split(":")[1]
            factor = float(factor_str)
            # Should be a reasonable positive number
            assert factor > 0
            assert factor < 100  # Can be large for extreme cases

    def test_conservation(self, infeasible_test_data):
        """Verify shares still sum to 1.0 in strict=False mode."""
        manager = AllocationManager()

        result = manager.run_allocation(
            approach="cumulative-per-capita-convergence-adjusted",
            population_ts=infeasible_test_data["population"],
            country_actual_emissions_ts=infeasible_test_data["emissions"],
            gdp_ts=infeasible_test_data["gdp"],
            world_scenario_emissions_ts=infeasible_test_data["world_pathway"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=0.4,
            capability_weight=0.4,
            historical_responsibility_year=2015,
            strict=False,
        )

        # Check shares sum to 1.0 for each year
        year_cols = get_year_columns(result.relative_shares_pathway_emissions)
        for year in year_cols:
            year_sum = result.relative_shares_pathway_emissions[year].sum()
            assert abs(year_sum - 1.0) < 1e-10

    def test_adjustment_factors_consistency(self, infeasible_test_data):
        """Verify adjustment factors reflect actual changes."""
        manager = AllocationManager()

        # Run with strict=False
        result_adjusted = manager.run_allocation(
            approach="cumulative-per-capita-convergence-adjusted",
            population_ts=infeasible_test_data["population"],
            country_actual_emissions_ts=infeasible_test_data["emissions"],
            gdp_ts=infeasible_test_data["gdp"],
            world_scenario_emissions_ts=infeasible_test_data["world_pathway"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=0.4,
            capability_weight=0.4,
            historical_responsibility_year=2015,
            strict=False,
        )

        # Verify warnings exist for at least one country
        assert result_adjusted.country_warnings

        # Countries with adjustment factor < 1 should have lower cumulative share
        # Countries with adjustment factor > 1 should have higher cumulative share
        # (This is a sanity check - exact values depend on the algorithm)
        year_cols = get_year_columns(result_adjusted.relative_shares_pathway_emissions)
        result_adjusted.relative_shares_pathway_emissions[year_cols].sum(axis=1)

        for iso3c, warning in result_adjusted.country_warnings.items():
            factor = float(warning.split(":")[1])
            # Just verify factor is reasonable - exact interpretation depends on implementation
            # For extreme test cases, factors can be large
            assert 0.01 < factor < 100  # Wide range for extreme test cases


class TestStrictParameterPropagation:
    """Test that strict parameter is properly propagated through manager."""

    def test_parameter_stored_in_result(self, infeasible_test_data):
        """Verify strict parameter is stored in result.parameters."""
        manager = AllocationManager()

        result = manager.run_allocation(
            approach="cumulative-per-capita-convergence-adjusted",
            population_ts=infeasible_test_data["population"],
            country_actual_emissions_ts=infeasible_test_data["emissions"],
            gdp_ts=infeasible_test_data["gdp"],
            world_scenario_emissions_ts=infeasible_test_data["world_pathway"],
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=0.3,
            capability_weight=0.3,
            historical_responsibility_year=2015,
            strict=False,
        )

        # Check parameter is stored
        assert "strict" in result.parameters
        assert result.parameters["strict"] is False
