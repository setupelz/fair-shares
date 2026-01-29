"""Unit tests for IAMC data loading utilities."""

from __future__ import annotations

import pandas as pd
import pytest

try:
    import pyam

    PYAM_AVAILABLE = True
except ImportError:
    PYAM_AVAILABLE = False

from fair_shares.library.exceptions import IAMCDataError

if PYAM_AVAILABLE:
    from fair_shares.library.utils.data.iamc import (
        get_available_regions,
        get_available_variables,
        get_year_coverage,
        load_iamc_data,
    )


pytestmark = pytest.mark.skipif(not PYAM_AVAILABLE, reason="pyam not installed")


@pytest.fixture
def sample_iamc_df():
    """Create sample IAMC data for testing."""
    return pyam.IamDataFrame(
        pd.DataFrame(
            [
                {
                    "model": "TestModel",
                    "scenario": "SSP2",
                    "region": "USA",
                    "variable": "Population",
                    "unit": "million",
                    2020: 330,
                    2030: 350,
                    2040: 370,
                },
                {
                    "model": "TestModel",
                    "scenario": "SSP2",
                    "region": "CHN",
                    "variable": "Population",
                    "unit": "million",
                    2020: 1400,
                    2030: 1380,
                    2040: 1350,
                },
                {
                    "model": "TestModel",
                    "scenario": "SSP2",
                    "region": "USA",
                    "variable": "Emissions|CO2",
                    "unit": "Mt CO2/yr",
                    2020: 5000,
                    2030: 4500,
                    2040: 4000,
                },
                {
                    "model": "TestModel",
                    "scenario": "SSP2",
                    "region": "CHN",
                    "variable": "Emissions|CO2",
                    "unit": "Mt CO2/yr",
                    2020: 10000,
                    2030: 9500,
                    2040: 9000,
                },
                {
                    "model": "TestModel",
                    "scenario": "SSP2",
                    "region": "USA",
                    "variable": "GDP|PPP",
                    "unit": "billion USD_2010/yr",
                    2020: 17000,
                    2030: 20000,
                    2040: 23000,
                },
                {
                    "model": "TestModel",
                    "scenario": "SSP2",
                    "region": "CHN",
                    "variable": "GDP|PPP",
                    "unit": "billion USD_2010/yr",
                    2020: 22000,
                    2030: 28000,
                    2040: 35000,
                },
            ]
        )
    )


def test_load_iamc_basic_population(sample_iamc_df):
    """Test loading basic IAMC data with population only."""
    data = load_iamc_data(
        sample_iamc_df,
        population_variable="Population",
        regions=["USA", "CHN"],
        allocation_start_year=2020,
        budget_end_year=2040,
    )

    # Check that population data is present
    assert "population" in data
    assert "metadata" in data

    # Check MultiIndex structure
    pop = data["population"]
    assert pop.index.names == ["region", "unit"]

    # Check string year columns (fair-shares convention)
    assert list(pop.columns) == ["2020", "2030", "2040"]
    assert all(isinstance(c, str) for c in pop.columns)

    # Check regions
    assert set(pop.index.get_level_values("region")) == {"USA", "CHN"}

    # Check metadata
    assert data["metadata"]["regions"] == ["USA", "CHN"]
    assert data["metadata"]["year_range"] == (2020, 2040)
    assert "Population" in data["metadata"]["variables_loaded"]


def test_load_iamc_with_emissions(sample_iamc_df):
    """Test loading IAMC with population and emissions."""
    data = load_iamc_data(
        sample_iamc_df,
        population_variable="Population",
        emissions_variable="Emissions|CO2",
        regions=["USA", "CHN"],
        allocation_start_year=2020,
        budget_end_year=2040,
    )

    # Check both datasets are present
    assert "population" in data
    assert "emissions" in data

    # Check structure matches
    assert data["emissions"].shape == data["population"].shape
    assert data["emissions"].index.names == ["region", "unit"]
    assert list(data["emissions"].columns) == ["2020", "2030", "2040"]

    # Check metadata reflects both variables
    assert "Population" in data["metadata"]["variables_loaded"]
    assert "Emissions|CO2" in data["metadata"]["variables_loaded"]


def test_load_iamc_missing_variable_error(sample_iamc_df):
    """Test clear error message when variable is missing."""
    with pytest.raises(IAMCDataError) as exc_info:
        load_iamc_data(
            sample_iamc_df,
            population_variable="NonexistentVariable",
            regions=["USA"],
            allocation_start_year=2020,
            budget_end_year=2040,
        )

    # Check error message is helpful
    error_msg = str(exc_info.value)
    assert "not found" in error_msg.lower()
    assert "Available variables" in error_msg
    assert "NonexistentVariable" in error_msg


def test_load_iamc_missing_region_error(sample_iamc_df):
    """Test clear error message when region is missing."""
    with pytest.raises(IAMCDataError) as exc_info:
        load_iamc_data(
            sample_iamc_df,
            population_variable="Population",
            regions=["USA", "NONEXISTENT"],
            allocation_start_year=2020,
            budget_end_year=2040,
        )

    # Check error message is helpful
    error_msg = str(exc_info.value)
    assert "not found" in error_msg.lower()
    assert "Available regions" in error_msg
    assert "NONEXISTENT" in error_msg


def test_load_iamc_wildcard_filters(sample_iamc_df):
    """Test pyam wildcard filtering for model/scenario."""
    # Test with wildcard filters
    data = load_iamc_data(
        sample_iamc_df,
        population_variable="Population",
        model_filter="Test*",
        scenario_filter="*SSP*",
        regions=["USA", "CHN"],
        allocation_start_year=2020,
        budget_end_year=2040,
    )

    # Should successfully load data matching filters
    assert "population" in data
    assert data["metadata"]["model"] == ["TestModel"]
    assert data["metadata"]["scenario"] == ["SSP2"]


def test_iamc_to_timeseries_format(sample_iamc_df):
    """Test output format matches fair-shares expectations."""
    data = load_iamc_data(
        sample_iamc_df,
        population_variable="Population",
        regions=["USA", "CHN"],
        allocation_start_year=2020,
        budget_end_year=2040,
    )

    pop = data["population"]

    # Check MultiIndex structure
    assert isinstance(pop.index, pd.MultiIndex)
    assert "region" in pop.index.names
    assert "unit" in pop.index.names

    # Check string year columns (fair-shares convention)
    assert all(isinstance(c, str) for c in pop.columns)

    # Check data types
    assert pop.dtypes.iloc[0] in [float, int]  # Numeric data


def test_iamc_integration_with_allocation(sample_iamc_df):
    """Test IAMC data works end-to-end with allocation function."""
    from fair_shares.library.allocations.budgets.per_capita import (
        equal_per_capita_budget,
    )

    # Load data
    data = load_iamc_data(
        sample_iamc_df,
        population_variable="Population",
        regions=["USA", "CHN"],
        allocation_start_year=2020,
        budget_end_year=2040,
    )

    # Rename index level from "region" to "iso3c" to match allocation function expectations
    # This is the standard workflow when loading IAMC data for allocations
    population = data["population"].rename_axis(index={"region": "iso3c"})

    # Run allocation
    result = equal_per_capita_budget(
        population_ts=population,
        allocation_year=2020,
        emission_category="co2",
        group_level="iso3c",
    )

    # Check result is valid
    assert result is not None
    assert hasattr(result, "relative_shares_cumulative_emission")

    # Check shares sum to 1.0
    shares = result.relative_shares_cumulative_emission
    assert abs(shares.sum().sum() - 1.0) < 1e-6


def test_get_available_variables(sample_iamc_df):
    """Test variable discovery function."""
    variables = get_available_variables(sample_iamc_df)

    # Check returns sorted list
    assert isinstance(variables, list)
    assert variables == sorted(variables)

    # Check expected variables are present
    assert "Population" in variables
    assert "Emissions|CO2" in variables
    assert "GDP|PPP" in variables


def test_get_available_regions(sample_iamc_df):
    """Test region discovery function."""
    regions = get_available_regions(sample_iamc_df)

    # Check returns sorted list
    assert isinstance(regions, list)
    assert regions == sorted(regions)

    # Check expected regions are present
    assert "USA" in regions
    assert "CHN" in regions


def test_get_year_coverage(sample_iamc_df):
    """Test year coverage function."""
    min_year, max_year = get_year_coverage(sample_iamc_df)

    # Check correct years
    assert min_year == 2020
    assert max_year == 2040

    # Check types
    assert isinstance(min_year, int)
    assert isinstance(max_year, int)


def test_load_iamc_all_variables(sample_iamc_df):
    """Test loading with all variables (population, emissions, GDP)."""
    data = load_iamc_data(
        sample_iamc_df,
        population_variable="Population",
        emissions_variable="Emissions|CO2",
        gdp_variable="GDP|PPP",
        regions=["USA", "CHN"],
        allocation_start_year=2020,
        budget_end_year=2040,
    )

    # Check all datasets are present
    assert "population" in data
    assert "emissions" in data
    assert "gdp" in data
    assert "metadata" in data

    # Check all have same structure
    assert data["population"].shape == data["emissions"].shape == data["gdp"].shape

    # Check metadata
    assert len(data["metadata"]["variables_loaded"]) == 3
    assert "Population" in data["metadata"]["variables_loaded"]
    assert "Emissions|CO2" in data["metadata"]["variables_loaded"]
    assert "GDP|PPP" in data["metadata"]["variables_loaded"]


def test_load_iamc_auto_exclude_world(sample_iamc_df):
    """Test that 'World' region is auto-excluded when regions=None."""
    # Add World region to sample data (in long format to match as_pandas output)
    world_data = pd.DataFrame(
        [
            {
                "model": "TestModel",
                "scenario": "SSP2",
                "region": "World",
                "variable": "Population",
                "unit": "million",
                "year": year,
                "value": value,
            }
            for year, value in [(2020, 7800), (2030, 8500), (2040, 9100)]
        ]
    )
    df_with_world = pyam.IamDataFrame(
        pd.concat([sample_iamc_df.as_pandas(), world_data], ignore_index=True)
    )

    # Load with regions=None (should auto-exclude World)
    data = load_iamc_data(
        df_with_world,
        population_variable="Population",
        regions=None,  # Auto-detect, should exclude World
        allocation_start_year=2020,
        budget_end_year=2040,
    )

    # Check World is not in the data
    regions = set(data["population"].index.get_level_values("region"))
    assert "World" not in regions
    assert "USA" in regions
    assert "CHN" in regions


# Integration test with example Excel file
EXAMPLE_FILE_PATH = "data/scenarios/iamc_example/iamc_reporting_example.xlsx"


@pytest.fixture
def example_iamc_file():
    """Path to example IAMC Excel file for integration testing."""
    from pathlib import Path

    # Navigate from tests/unit/utils/data to project root
    project_root = Path(__file__).parent.parent.parent.parent.parent
    file_path = project_root / EXAMPLE_FILE_PATH
    if not file_path.exists():
        pytest.skip(f"Example file not found: {file_path}")
    return str(file_path)


@pytest.mark.integration
def test_iamc_example_file_allocation_integration(example_iamc_file):
    """
    Integration test: verify IAMC loader + allocation reproduces expected values.

    The example file contains pre-calculated ECPC (Equal Cumulative Per Capita)
    allocations. This test verifies that loading the file and running
    equal_per_capita_budget() reproduces those values.
    """

    # Load regions from file (excluding World)
    df = pd.read_excel(example_iamc_file)
    all_regions = [r for r in df["region"].unique() if r != "World"]

    # Load population data using IAMC loader
    data = load_iamc_data(
        data_file=example_iamc_file,
        population_variable="Population",
        regions=all_regions,
        allocation_start_year=2015,
        budget_end_year=2100,
    )

    assert "population" in data
    population = data["population"]

    # Check we got all expected regions
    loaded_regions = set(population.index.get_level_values("region"))
    assert len(loaded_regions) == 12  # 12 regions in the example file

    # Verify IAMC format was loaded correctly
    assert all(isinstance(c, str) for c in population.columns)
    assert "2015" in population.columns
    assert population.index.names == ["region", "unit"]


@pytest.mark.integration
def test_iamc_allocation_reproduces_expected_values(example_iamc_file):
    """
    Verify that equal_per_capita_budget() reproduces the pre-calculated allocations.

    The example file contains allocations calculated using ECPC (Equal Cumulative
    Per Capita) from 2015-2100 with period weighting:
    - 2015 x 1 (first year)
    - 2020-2060 x 5 (5-year intervals)
    - 2070-2100 x 10 (10-year intervals)

    Using expand_to_annual=True with bfill correctly accounts for the period
    weighting by expanding non-annual data to annual values.
    """
    from fair_shares.library.allocations.budgets.per_capita import (
        equal_per_capita_budget,
    )

    # Load the raw file
    df = pd.read_excel(example_iamc_file)
    all_regions = [r for r in df["region"].unique() if r != "World"]

    # Extract expected allocations from file
    expected_alloc = df[df["variable"] == "Emissions|Allocation|Starting"]
    expected_by_region = expected_alloc.set_index("region")["2015"]
    total_budget = expected_by_region.sum()  # ~1981.52 Gt

    # Load population data using IAMC loader WITH annual expansion
    data = load_iamc_data(
        data_file=example_iamc_file,
        population_variable="Population",
        regions=all_regions,
        allocation_start_year=2015,
        budget_end_year=2100,
        expand_to_annual=True,  # Expand to annual for period weighting
        interpolation_method="bfill",  # Each value fills preceding interval
    )

    # Rename index from "region" to "iso3c" to match allocation function expectations
    population = data["population"].rename_axis(index={"region": "iso3c"})

    # Run equal per capita allocation (dynamic shares, not preserved)
    result = equal_per_capita_budget(
        population_ts=population,
        allocation_year=2015,
        emission_category="co2",
        preserve_allocation_year_shares=False,  # Dynamic shares (ECPC)
        group_level="iso3c",
    )

    # Get the relative shares and calculate absolute allocations
    # shares has MultiIndex (iso3c, unit, emission-category) and column "2015"
    shares = result.relative_shares_cumulative_emission["2015"]

    # Calculate absolute allocations by multiplying shares by total budget
    calculated_alloc = shares * total_budget

    # Compare to expected values
    tolerance = 0.01  # 0.01 Gt = 10 Mt tolerance

    for region in all_regions:
        expected = expected_by_region[region]
        # Extract calculated value for this region (any unit/emission-category)
        calc_value = calculated_alloc.xs(region, level="iso3c").iloc[0]
        diff = abs(expected - calc_value)
        assert diff < tolerance, (
            f"Region {region}: expected {expected:.4f}, "
            f"got {calc_value:.4f}, diff {diff:.4f}"
        )


@pytest.mark.integration
def test_iamc_example_file_variable_loading(example_iamc_file):
    """Test loading multiple variables from the example IAMC file."""
    df = pd.read_excel(example_iamc_file)
    all_regions = [r for r in df["region"].unique() if r != "World"]

    # Load all variables from the file
    data = load_iamc_data(
        data_file=example_iamc_file,
        population_variable="Population",
        gdp_variable="GDP|PPP",
        regions=all_regions,
        allocation_start_year=2015,
        budget_end_year=2100,
    )

    assert "population" in data
    assert "gdp" in data
    assert data["population"].shape == data["gdp"].shape


@pytest.mark.integration
def test_iamc_example_file_helpers(example_iamc_file):
    """Test helper functions with the example IAMC file."""
    iamc_df = pyam.IamDataFrame(example_iamc_file)

    # Test get_available_variables
    variables = get_available_variables(iamc_df)
    assert "Population" in variables
    assert "GDP|PPP" in variables
    assert "Emissions|Allocation|Starting" in variables

    # Test get_available_regions
    regions = get_available_regions(iamc_df)
    assert "AFR" in regions
    assert "CHN" in regions
    assert len(regions) >= 12  # 12 regions + World

    # Test get_year_coverage
    min_year, max_year = get_year_coverage(iamc_df)
    assert min_year == 1990
    assert max_year == 2100
