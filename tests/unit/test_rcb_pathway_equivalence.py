"""
Test equivalence between budget allocations (using RCBs) and pathway allocations (using RCB-Pathways).

This is a critical verification that pathway allocations match budget allocations in cumulative terms.
"""

import pandas as pd
import pytest

from fair_shares.library.allocations import AllocationManager
from fair_shares.library.utils import get_year_columns


@pytest.fixture
def allocation_manager():
    """Fresh allocation manager for each test."""
    return AllocationManager()


@pytest.fixture
def sample_population_ts():
    """Simple test population data (includes historical data from 2015)."""
    years = [str(y) for y in range(2015, 2051)]
    data = {
        "AAA": [100] * len(years),
        "BBB": [200] * len(years),
        "CCC": [300] * len(years),
        "DDD": [400] * len(years),
    }
    df = pd.DataFrame(data, index=years).T
    df.index = pd.MultiIndex.from_tuples(
        [(iso, "million") for iso in data.keys()],
        names=["iso3c", "unit"],
    )
    return df


@pytest.fixture
def sample_gdp_ts():
    """Simple test GDP data (includes historical data from 2015)."""
    years = [str(y) for y in range(2015, 2051)]
    data = {
        "AAA": [1000] * len(years),
        "BBB": [2000] * len(years),
        "CCC": [3000] * len(years),
        "DDD": [4000] * len(years),
    }
    df = pd.DataFrame(data, index=years).T
    df.index = pd.MultiIndex.from_tuples(
        [(iso, "billion") for iso in data.keys()],
        names=["iso3c", "unit"],
    )
    return df


@pytest.fixture
def sample_rcbs():
    """Sample RCB data."""
    return pd.DataFrame(
        {
            "source": ["test_source"],
            "climate-assessment": ["1.5C"],
            "quantile": [0.5],
            "rcb_2020_mt": [10000.0],
        }
    )


@pytest.fixture
def sample_world_pathway():
    """
    Sample world pathway generated from RCB.

    This should represent a pathway that starts at 500 Mt in 2020
    and decays to exactly 0 by 2050, with cumulative = 10000 Mt.
    """
    # Create a simple linear decay for testing
    years = list(range(2020, 2051))
    n_years = len(years)

    # Linear decay: starts at start_value, ends at 0
    # For cumulative to equal budget, we need: budget = average * n_years
    # average = (start_value + 0) / 2
    # So: start_value = 2 * budget / n_years
    budget = 10000.0
    start_value = 2 * budget / n_years

    values = [start_value * (1 - i / (n_years - 1)) for i in range(n_years)]
    values[-1] = 0.0  # Ensure exactly zero at end

    df = pd.DataFrame(
        [values],
        columns=[str(y) for y in years],
        index=pd.MultiIndex.from_tuples(
            [("1.5C", 0.5, "test_source", "World", "Mt * CO2e", "co2-ffi")],
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
    return df


@pytest.fixture
def sample_country_emissions():
    """Sample country historical emissions."""
    years = [str(y) for y in range(2015, 2021)]
    data = {
        "AAA": [10, 10, 10, 10, 10, 10],
        "BBB": [20, 20, 20, 20, 20, 20],
        "CCC": [30, 30, 30, 30, 30, 30],
        "DDD": [40, 40, 40, 40, 40, 40],
    }
    df = pd.DataFrame(data, index=years).T
    df.index = pd.MultiIndex.from_tuples(
        [(iso, "Mt * CO2e", "co2-ffi") for iso in data.keys()],
        names=["iso3c", "unit", "emission-category"],
    )
    return df


class TestRCBPathwayEquivalence:
    """Test that pathway allocations match budget allocations in cumulative terms."""

    def test_equal_per_capita_equivalence(
        self,
        allocation_manager,
        sample_population_ts,
        sample_rcbs,
        sample_world_pathway,
    ):
        """
        Test that equal-per-capita (pathway) matches equal-per-capita-budget (RCB) cumulatively.
        """
        # 1. Run budget allocation with RCB
        budget_result = allocation_manager.run_allocation(
            approach="equal-per-capita-budget",
            population_ts=sample_population_ts,
            allocation_year=2020,
            emission_category="co2-ffi",
            rcbs=sample_rcbs,
        )

        # Extract budget shares (single year column from TimeseriesDataFrame)
        year_col = get_year_columns(budget_result.relative_shares_cumulative_emission)[
            0
        ]
        budget_shares = budget_result.relative_shares_cumulative_emission[year_col]

        # 2. Run pathway allocation with RCB-Pathway
        pathway_result = allocation_manager.run_allocation(
            approach="equal-per-capita",
            population_ts=sample_population_ts,
            world_scenario_emissions_ts=sample_world_pathway,
            first_allocation_year=2020,
            emission_category="co2-ffi",
        )

        pathway_shares = pathway_result.relative_shares_pathway_emissions

        # 3. Calculate cumulative pathway shares
        year_cols = get_year_columns(pathway_shares)
        cumulative_pathway_shares = pathway_shares[year_cols].sum(axis=1)

        # Normalize to get relative shares
        cumulative_pathway_shares = (
            cumulative_pathway_shares / cumulative_pathway_shares.sum()
        )

        # 4. Assert equivalence (within 0.1% tolerance)
        pd.testing.assert_series_equal(
            budget_shares.sort_index(),
            cumulative_pathway_shares.sort_index(),
            check_names=False,
            rtol=0.001,  # 0.1% relative tolerance
            atol=1e-6,  # Absolute tolerance for small values
        )

    def test_per_capita_adjusted_equivalence(
        self,
        allocation_manager,
        sample_population_ts,
        sample_gdp_ts,
        sample_rcbs,
        sample_world_pathway,
        sample_country_emissions,
    ):
        """
        Test that per-capita-adjusted (pathway) matches per-capita-adjusted-budget (RCB) cumulatively.
        """
        # 1. Run budget allocation with RCB
        budget_result = allocation_manager.run_allocation(
            approach="per-capita-adjusted-budget",
            population_ts=sample_population_ts,
            gdp_ts=sample_gdp_ts,
            country_actual_emissions_ts=sample_country_emissions,
            allocation_year=2020,
            emission_category="co2-ffi",
            rcbs=sample_rcbs,
            responsibility_weight=0.5,
            capability_weight=0.5,
            historical_responsibility_year=2015,
        )

        # Extract budget shares (single year column from TimeseriesDataFrame)
        year_col = get_year_columns(budget_result.relative_shares_cumulative_emission)[
            0
        ]
        budget_shares = budget_result.relative_shares_cumulative_emission[year_col]

        # 2. Run pathway allocation with RCB-Pathway
        pathway_result = allocation_manager.run_allocation(
            approach="per-capita-adjusted",
            population_ts=sample_population_ts,
            gdp_ts=sample_gdp_ts,
            country_actual_emissions_ts=sample_country_emissions,
            world_scenario_emissions_ts=sample_world_pathway,
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=0.5,
            capability_weight=0.5,
            historical_responsibility_year=2015,
        )

        pathway_shares = pathway_result.relative_shares_pathway_emissions

        # 3. Calculate cumulative pathway shares
        year_cols = get_year_columns(pathway_shares)
        cumulative_pathway_shares = pathway_shares[year_cols].sum(axis=1)

        # Normalize to get relative shares
        cumulative_pathway_shares = (
            cumulative_pathway_shares / cumulative_pathway_shares.sum()
        )

        # 4. Assert equivalence (within 0.1% tolerance)
        pd.testing.assert_series_equal(
            budget_shares.sort_index(),
            cumulative_pathway_shares.sort_index(),
            check_names=False,
            rtol=0.001,  # 0.1% relative tolerance
            atol=1e-6,  # Absolute tolerance for small values
        )

    def test_cumulative_conservation(
        self, allocation_manager, sample_population_ts, sample_world_pathway
    ):
        """
        Test that pathway allocations conserve the total budget.

        The sum of all RELATIVE shares across countries should equal 1.0 for each year.
        """
        # Run pathway allocation
        result = allocation_manager.run_allocation(
            approach="equal-per-capita",
            population_ts=sample_population_ts,
            world_scenario_emissions_ts=sample_world_pathway,
            first_allocation_year=2020,
            emission_category="co2-ffi",
        )

        # Check that relative shares sum to 1.0 for each year
        year_cols = get_year_columns(result.relative_shares_pathway_emissions)
        for year in year_cols:
            year_sum = result.relative_shares_pathway_emissions[year].sum()
            assert abs(year_sum - 1.0) < 1e-10, (
                f"Year {year} shares sum to {year_sum}, not 1.0"
            )

    @pytest.mark.parametrize(
        "responsibility_weight,capability_weight",
        [
            (0.0, 0.0),  # Pure equal per capita
            (0.5, 0.5),  # Balanced
            (1.0, 0.0),  # Pure responsibility
            (0.0, 1.0),  # Pure capability
        ],
    )
    def test_per_capita_adjusted_equivalence_parametric(
        self,
        allocation_manager,
        sample_population_ts,
        sample_gdp_ts,
        sample_rcbs,
        sample_world_pathway,
        sample_country_emissions,
        responsibility_weight,
        capability_weight,
    ):
        """
        Test equivalence with different responsibility/capability weights.
        """
        # 1. Run budget allocation
        budget_result = allocation_manager.run_allocation(
            approach="per-capita-adjusted-budget",
            population_ts=sample_population_ts,
            gdp_ts=sample_gdp_ts,
            country_actual_emissions_ts=sample_country_emissions,
            allocation_year=2020,
            emission_category="co2-ffi",
            rcbs=sample_rcbs,
            responsibility_weight=responsibility_weight,
            capability_weight=capability_weight,
            historical_responsibility_year=2015,
        )

        # Extract budget shares (single year column from TimeseriesDataFrame)
        year_col = get_year_columns(budget_result.relative_shares_cumulative_emission)[
            0
        ]
        budget_shares = budget_result.relative_shares_cumulative_emission[year_col]

        # 2. Run pathway allocation
        pathway_result = allocation_manager.run_allocation(
            approach="per-capita-adjusted",
            population_ts=sample_population_ts,
            gdp_ts=sample_gdp_ts,
            country_actual_emissions_ts=sample_country_emissions,
            world_scenario_emissions_ts=sample_world_pathway,
            first_allocation_year=2020,
            emission_category="co2-ffi",
            responsibility_weight=responsibility_weight,
            capability_weight=capability_weight,
            historical_responsibility_year=2015,
        )

        # 3. Calculate cumulative pathway shares
        year_cols = get_year_columns(pathway_result.relative_shares_pathway_emissions)
        cumulative_pathway_shares = pathway_result.relative_shares_pathway_emissions[
            year_cols
        ].sum(axis=1)
        cumulative_pathway_shares = (
            cumulative_pathway_shares / cumulative_pathway_shares.sum()
        )

        # 4. Assert equivalence
        pd.testing.assert_series_equal(
            budget_shares.sort_index(),
            cumulative_pathway_shares.sort_index(),
            check_names=False,
            rtol=0.001,
            atol=1e-6,
        )
