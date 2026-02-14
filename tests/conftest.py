"""
Common fixtures for pytest unit and integration tests for the fair-shares library.

"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.allocations.manager import AllocationManager
from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.utils.dataframes import ensure_string_year_columns

# Standard test constants
STANDARD_EMISSION_CATEGORY = "co2-ffi"

# Common test parameters to avoid redundancy
PATHWAY_TEST_PARAMS = {
    "first_allocation_year": 2020,
    "emission_category": STANDARD_EMISSION_CATEGORY,
}

PATHWAY_CONVERGENCE_TEST_PARAMS = {
    "first_allocation_year": 2020,
    "emission_category": STANDARD_EMISSION_CATEGORY,
    "convergence_year": 2050,
}

BUDGET_TEST_PARAMS = {
    "allocation_year": 2020,
    "emission_category": STANDARD_EMISSION_CATEGORY,
}


# Core allocation functions for testing
def get_core_allocation_functions():
    """Get core allocation function tuples (function, params) for testing."""
    from fair_shares.library.allocations.budgets import (
        equal_per_capita_budget,
        per_capita_adjusted_budget,
        per_capita_adjusted_gini_budget,
    )
    from fair_shares.library.allocations.pathways import (
        cumulative_per_capita_convergence,
        equal_per_capita,
        per_capita_adjusted,
        per_capita_adjusted_gini,
        per_capita_convergence,
    )

    return [
        # Pathway functions
        (equal_per_capita, PATHWAY_TEST_PARAMS),
        (per_capita_adjusted, PATHWAY_TEST_PARAMS),
        (per_capita_adjusted_gini, PATHWAY_TEST_PARAMS),
        (per_capita_convergence, PATHWAY_CONVERGENCE_TEST_PARAMS),
        (cumulative_per_capita_convergence, PATHWAY_TEST_PARAMS),
        # Budget functions
        (equal_per_capita_budget, BUDGET_TEST_PARAMS),
        (per_capita_adjusted_budget, BUDGET_TEST_PARAMS),
        (per_capita_adjusted_gini_budget, BUDGET_TEST_PARAMS),
    ]


def generate_simple_test_data():
    """
    Generate simple test data for allocation tests.
    Returns TimeseriesDataFrame format with proper MultiIndex structure.
    """
    countries = ["AAA", "BBB", "CCC", "DDD"]
    years = [2015, 2019, 2020, 2030, 2040, 2050]

    np.random.seed(42)  # For reproducible test data

    # Population data
    population_data = []
    for i, country in enumerate(countries):
        for year in years:
            pop = 10 + i * 5 + (year - 2020) * 0.1  # Simple growth
            population_data.append([country, "million", year, pop])

    population_df = pd.DataFrame(
        population_data, columns=["iso3c", "unit", "year", "population"]
    ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")
    population_df = ensure_string_year_columns(population_df)

    # GDP data
    gdp_data = []
    for i, country in enumerate(countries):
        for year in years:
            gdp = (100 + i * 200) * (1 + (year - 2020) * 0.02)  # Simple growth
            gdp_data.append([country, "billion", year, gdp])

    gdp_df = pd.DataFrame(
        gdp_data, columns=["iso3c", "unit", "year", "gdp"]
    ).pivot_table(index=["iso3c", "unit"], columns="year", values="gdp")
    gdp_df = ensure_string_year_columns(gdp_df)

    # Emissions data
    emissions_data = []
    category = STANDARD_EMISSION_CATEGORY  # Use single emission category

    # Calculate world totals for each year
    world_totals = {}
    for year in years:
        world_total = sum(
            10 + i * 5 + (year - 2020) * 0.05 for i in range(len(countries))
        )
        world_totals[year] = world_total

    # Add country data
    for i, country in enumerate(countries):
        for year in years:
            emissions = 10 + i * 5 + (year - 2020) * 0.05
            emissions_data.append([country, "Mt * CO2e", category, year, emissions])

    # Add World totals
    for year in years:
        emissions_data.append(
            ["World", "Mt * CO2e", category, year, world_totals[year]]
        )

    emissions_df = pd.DataFrame(
        emissions_data,
        columns=["iso3c", "unit", "emission-category", "year", "emissions"],
    ).pivot_table(
        index=["iso3c", "unit", "emission-category"], columns="year", values="emissions"
    )
    emissions_df = ensure_string_year_columns(emissions_df)

    # Gini data
    gini_data = []
    for i, country in enumerate(countries):
        gini_value = 0.3 + (i * 0.1)  # Simple variation
        gini_data.append([country, gini_value])
    gini_df = pd.DataFrame(gini_data, columns=["iso3c", "gini"])

    world_mask = emissions_df.index.get_level_values("iso3c") == "World"
    world_emissions_df = emissions_df[world_mask]

    return {
        "population": population_df,
        "gdp": gdp_df,
        "emissions": emissions_df,
        "world-emissions": world_emissions_df,
        "gini": gini_df,
        "first-allocation-year": 2020,
        "allocation-year": 2020,
    }


def generate_sample_shares_data(countries, years, emission_category):
    """
    Generate sample shares data for testing result fixtures.

    Parameters
    ----------
    countries : list
        List of country codes
    years : list
        List of years
    emission_category : str
        Emission category

    Returns
    -------
    pd.DataFrame
        TimeseriesDataFrame with equal shares across countries
    """
    shares_data = []
    for i, country in enumerate(countries):
        for year in years:
            share = 1.0 / len(countries)  # Equal shares
            shares_data.append(
                [country, "dimensionless", emission_category, year, share]
            )

    return pd.DataFrame(
        shares_data, columns=["iso3c", "unit", "emission-category", "year", "share"]
    ).pivot_table(
        index=["iso3c", "unit", "emission-category"], columns="year", values="share"
    )


# Core fixtures with session scope for performance
# Session-scoped fixtures cache expensive data generation across all tests.
# Function-scoped fixtures use deepcopy to prevent test pollution.


@pytest.fixture(scope="session")
def _shared_allocation_manager():
    """Session-cached AllocationManager (internal - do not use directly)."""
    return AllocationManager()


@pytest.fixture
def allocation_manager(_shared_allocation_manager):
    """Provide a fresh AllocationManager instance for testing.

    Each test gets a deep copy to prevent state pollution between tests.
    """
    return copy.deepcopy(_shared_allocation_manager)


@pytest.fixture(scope="session")
def _shared_test_data():
    """Session-cached test data (internal - do not use directly)."""
    return generate_simple_test_data()


@pytest.fixture
def test_data(_shared_test_data):
    """Simple test data for allocation tests.

    Each test gets a deep copy to prevent DataFrame mutation between tests.
    """
    return copy.deepcopy(_shared_test_data)


@pytest.fixture(scope="session")
def _shared_test_config():
    """Session-cached test config (internal - do not use directly)."""
    # Common emission category config for all allocation approaches
    common_allocation_config = {"emission_category": STANDARD_EMISSION_CATEGORY}

    return {
        "data_sources": {"emission_category": STANDARD_EMISSION_CATEGORY},
        "allocations": {
            "equal-per-capita": common_allocation_config,
            "per-capita-adjusted": common_allocation_config,
            "per-capita-adjusted-gini": common_allocation_config,
            "per-capita-convergence": common_allocation_config,
            "equal-per-capita-budget": common_allocation_config,
            "per-capita-adjusted-budget": common_allocation_config,
            "per-capita-adjusted-gini-budget": common_allocation_config,
        },
    }


@pytest.fixture
def test_config(_shared_test_config):
    """Basic test config for allocation functions.

    Each test gets a deep copy to prevent config mutation between tests.
    """
    return copy.deepcopy(_shared_test_config)


@pytest.fixture(scope="session")
def _shared_sample_budget_result():
    """Session-cached BudgetAllocationResult (internal - do not use directly)."""
    countries = ["AAA", "BBB", "CCC", "DDD"]
    allocation_year = 2020

    shares_df = generate_sample_shares_data(
        countries, [allocation_year], STANDARD_EMISSION_CATEGORY
    )

    return BudgetAllocationResult(
        approach="equal-per-capita-budget",
        parameters={"allocation_year": allocation_year},
        relative_shares_cumulative_emission=shares_df,
    )


@pytest.fixture
def sample_budget_result(_shared_sample_budget_result):
    """Sample BudgetAllocationResult for testing.

    Each test gets a deep copy to prevent result mutation between tests.
    """
    return copy.deepcopy(_shared_sample_budget_result)


@pytest.fixture(scope="session")
def _shared_sample_pathway_result():
    """Session-cached PathwayAllocationResult (internal - do not use directly)."""
    countries = ["AAA", "BBB", "CCC", "DDD"]
    years = [2020, 2030, 2040, 2050]

    shares_df = generate_sample_shares_data(
        countries, years, STANDARD_EMISSION_CATEGORY
    )

    return PathwayAllocationResult(
        approach="equal-per-capita",
        parameters={
            "first-allocation-year": 2020,
            "emission_category": STANDARD_EMISSION_CATEGORY,
        },
        relative_shares_pathway_emissions=shares_df,
    )


@pytest.fixture
def sample_pathway_result(_shared_sample_pathway_result):
    """Sample PathwayAllocationResult for testing.

    Each test gets a deep copy to prevent result mutation between tests.
    """
    return copy.deepcopy(_shared_sample_pathway_result)


@pytest.fixture
def limited_gdp_data(test_data):
    """Test data with limited GDP availability (only 2015, 2020)."""
    limited_data = test_data.copy()
    limited_gdp = test_data["gdp"].loc[:, ["2015", "2020"]]
    limited_data["gdp"] = ensure_string_year_columns(limited_gdp)
    return limited_data


@pytest.fixture
def mixed_units_data():
    """Test data with different units requiring conversion."""
    countries = ["AAA", "BBB", "CCC"]
    years = [2015, 2020, 2050]

    # Mixed units population data
    population_data = [
        ["AAA", "million", 2015, 0.8],
        ["AAA", "million", 2020, 1.0],
        ["AAA", "million", 2050, 2.0],
        ["BBB", "thousand", 2015, 800.0],
        ["BBB", "thousand", 2020, 1000.0],
        ["BBB", "thousand", 2050, 1000.0],
        ["CCC", "million", 2015, 0.8],
        ["CCC", "million", 2020, 1.0],
        ["CCC", "million", 2050, 0.5],
    ]

    population_df = pd.DataFrame(
        population_data, columns=["iso3c", "unit", "year", "population"]
    ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")
    population_df = ensure_string_year_columns(population_df)

    # Mixed units emissions data with world totals
    emissions_data = []
    emission_values = {
        "AAA": {"Mt * CO2e": {2015: 8.0, 2020: 10.0, 2050: 12.0}},
        "BBB": {
            "ktCO2": {2015: 4000.0, 2020: 5000.0, 2050: 6000.0}
        },  # 4, 5, 6 Mt * CO2e equiv
        "CCC": {"Mt * CO2e": {2015: 6.0, 2020: 8.0, 2050: 9.0}},
    }

    # Add country data
    for country, unit_data in emission_values.items():
        for unit, year_data in unit_data.items():
            for year, emissions in year_data.items():
                emissions_data.append(
                    [country, unit, STANDARD_EMISSION_CATEGORY, year, emissions]
                )

    # Calculate world totals (converting ktCO2 to Mt * CO2e)
    world_totals = {}
    for year in years:
        total = (
            emission_values["AAA"]["Mt * CO2e"][year]
            + emission_values["BBB"]["ktCO2"][year] / 1000.0  # Convert kt to Mt
            + emission_values["CCC"]["Mt * CO2e"][year]
        )
        world_totals[year] = total

    # Add World totals
    for year in years:
        emissions_data.append(
            ["World", "Mt * CO2e", STANDARD_EMISSION_CATEGORY, year, world_totals[year]]
        )

    emissions_df = pd.DataFrame(
        emissions_data,
        columns=["iso3c", "unit", "emission-category", "year", "emissions"],
    ).pivot_table(
        index=["iso3c", "unit", "emission-category"], columns="year", values="emissions"
    )
    emissions_df = ensure_string_year_columns(emissions_df)

    # Standard GDP data (all same units)
    gdp_data = []
    for i, country in enumerate(countries):
        for year in years:
            gdp = (100 + i * 200) * (1 + (year - 2020) * 0.02)
            gdp_data.append([country, "billion", year, gdp])

    gdp_df = pd.DataFrame(
        gdp_data, columns=["iso3c", "unit", "year", "gdp"]
    ).pivot_table(index=["iso3c", "unit"], columns="year", values="gdp")
    gdp_df = ensure_string_year_columns(gdp_df)

    gini_df = pd.DataFrame(
        [["AAA", 0.3], ["BBB", 0.4], ["CCC", 0.5]], columns=["iso3c", "gini"]
    )

    return {
        "population": population_df,
        "gdp": gdp_df,
        "emissions": emissions_df,
        "gini": gini_df,
        "first-allocation-year": 2020,
    }
