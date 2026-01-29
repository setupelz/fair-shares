"""
Edge case tests for allocation functions.

Tests critical edge cases including empty DataFrames, single country allocations,
NaN propagation, non-overlapping years, and IAMC loader error cases.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.validation.inputs import (
    validate_emissions_data,
    validate_gdp_data,
    validate_gini_data,
    validate_not_empty,
    validate_population_data,
)


class TestEmptyDataFrameEdgeCases:
    """Test edge cases with empty DataFrames."""

    def test_validate_not_empty_rejects_empty_dataframe(self):
        """validate_not_empty raises clear error for empty DataFrame."""
        empty_df = pd.DataFrame()

        with pytest.raises(DataProcessingError, match="empty"):
            validate_not_empty(empty_df, "test dataset")

    def test_validate_emissions_data_rejects_empty(self):
        """validate_emissions_data raises clear error for empty DataFrame."""
        empty_emissions = pd.DataFrame()

        with pytest.raises(DataProcessingError, match="empty"):
            validate_emissions_data(empty_emissions, "emissions test")

    def test_validate_population_data_rejects_empty(self):
        """validate_population_data raises clear error for empty DataFrame."""
        empty_population = pd.DataFrame()

        with pytest.raises(DataProcessingError, match="empty"):
            validate_population_data(empty_population, "population test")

    def test_validate_gdp_data_rejects_empty(self):
        """validate_gdp_data raises clear error for empty DataFrame."""
        empty_gdp = pd.DataFrame()

        with pytest.raises(DataProcessingError, match="empty"):
            validate_gdp_data(empty_gdp, "GDP test")

    def test_validate_gini_data_rejects_empty(self):
        """validate_gini_data raises clear error for empty DataFrame."""
        empty_gini = pd.DataFrame()

        with pytest.raises(DataProcessingError, match="empty"):
            validate_gini_data(empty_gini, "Gini test")


class TestNaNPropagation:
    """Test edge cases with NaN values propagating through calculations."""

    def test_nan_in_deviation_constraint_population_raises_error(self):
        """NaN values in population during deviation constraint raise clear error."""
        from fair_shares.library.exceptions import AllocationError
        from fair_shares.library.utils.math.allocation import apply_deviation_constraint

        # Create test data with NaN in population
        shares = pd.DataFrame(
            {"2020": [0.5, 0.3, 0.2]},
            index=pd.MultiIndex.from_tuples(
                [("USA", "million"), ("CHN", "million"), ("IND", "million")],
                names=["iso3c", "unit"],
            ),
        )

        population_with_nan = pd.DataFrame(
            {"2020": [100.0, np.nan, 300.0]},  # NaN value
            index=pd.MultiIndex.from_tuples(
                [("USA", "million"), ("CHN", "million"), ("IND", "million")],
                names=["iso3c", "unit"],
            ),
        )

        with pytest.raises(AllocationError, match="NaN"):
            apply_deviation_constraint(
                shares=shares,
                population=population_with_nan,
                max_deviation_sigma=2.0,
                group_level="iso3c",
            )

    def test_nan_in_responsibility_adjustment_handles_gracefully(self):
        """NaN values in emissions during responsibility adjustment are clamped."""
        from fair_shares.library.utils.math.allocation import (
            calculate_relative_adjustment,
        )

        # Create emissions data with NaN
        emissions_with_nan = pd.DataFrame(
            {"2020": [5000.0, np.nan, 3000.0]},  # NaN value
            index=pd.MultiIndex.from_tuples(
                [("USA", "million"), ("CHN", "million"), ("IND", "million")],
                names=["iso3c", "unit"],
            ),
        )

        # calculate_relative_adjustment should handle NaN gracefully
        # by clamping NaN values to 1.0 (neutral adjustment)
        result = calculate_relative_adjustment(
            values=emissions_with_nan["2020"],
            exponent=0.5,
            inverse=True,
        )

        # Verify NaN was handled (clamped to 1.0)
        assert not np.isnan(result).any()
        # Verify NaN was replaced with 1.0 (neutral)
        assert result[1] == 1.0  # CHN is at index 1

    def test_nan_in_capability_adjustment_handles_gracefully(self):
        """NaN values in GDP during capability adjustment are clamped."""
        from fair_shares.library.utils.math.allocation import (
            calculate_relative_adjustment,
        )

        # Create GDP data with NaN
        gdp_with_nan = pd.DataFrame(
            {"2020": [20000.0, np.nan, 8000.0]},  # NaN value
            index=pd.MultiIndex.from_tuples(
                [("USA", "million"), ("CHN", "million"), ("IND", "million")],
                names=["iso3c", "unit"],
            ),
        )

        # calculate_relative_adjustment should handle NaN gracefully
        # by clamping NaN values to 1.0 (neutral adjustment)
        result = calculate_relative_adjustment(
            values=gdp_with_nan["2020"],
            exponent=0.5,
            inverse=True,
        )

        # Verify NaN was handled (clamped to 1.0)
        assert not np.isnan(result).any()
        # Verify NaN was replaced with 1.0 (neutral)
        assert result[1] == 1.0  # CHN is at index 1


class TestSingleCountryAllocation:
    """Test edge cases with single country allocations."""

    def test_equal_per_capita_budget_single_country_gets_full_allocation(self):
        """Single country in equal per capita budget receives full allocation (100%)."""
        from fair_shares.library.allocations.budgets import equal_per_capita_budget

        # Create single country population data
        single_country_pop = pd.DataFrame(
            [
                ["USA", "million", "2020", 330.0],
                ["USA", "million", "2030", 350.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

        result = equal_per_capita_budget(
            population_ts=single_country_pop,
            allocation_year=2020,
            emission_category="co2-ffi",
        )

        # Verify single country gets 100% allocation
        assert result.relative_shares_cumulative_emission.loc[
            ("USA", "dimensionless", "co2-ffi"), "2020"
        ] == pytest.approx(1.0)

    def test_per_capita_adjusted_budget_single_country_gets_full_allocation(self):
        """Single country in adjusted per capita budget receives full allocation."""
        from fair_shares.library.allocations.budgets import per_capita_adjusted_budget

        # Create single country datasets
        single_country_pop = pd.DataFrame(
            [
                ["USA", "million", "2015", 320.0],
                ["USA", "million", "2020", 330.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

        single_country_gdp = pd.DataFrame(
            [
                ["USA", "billion", "2015", 18000.0],
                ["USA", "billion", "2020", 21000.0],
            ],
            columns=["iso3c", "unit", "year", "gdp"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="gdp")

        single_country_emissions = pd.DataFrame(
            [
                ["USA", "Mt * CO2e", "co2-ffi", "2015", 5000.0],
                ["USA", "Mt * CO2e", "co2-ffi", "2020", 4800.0],
                ["World", "Mt * CO2e", "co2-ffi", "2015", 5000.0],
                ["World", "Mt * CO2e", "co2-ffi", "2020", 4800.0],
            ],
            columns=["iso3c", "unit", "emission-category", "year", "emissions"],
        ).pivot_table(
            index=["iso3c", "unit", "emission-category"],
            columns="year",
            values="emissions",
        )

        result = per_capita_adjusted_budget(
            population_ts=single_country_pop,
            allocation_year=2020,
            emission_category="co2-ffi",
            country_actual_emissions_ts=single_country_emissions,
            gdp_ts=single_country_gdp,
            responsibility_weight=0.3,
            capability_weight=0.3,
        )

        # Verify single country gets 100% allocation regardless of adjustments
        assert result.relative_shares_cumulative_emission.loc[
            ("USA", "dimensionless", "co2-ffi"), "2020"
        ] == pytest.approx(1.0)

    def test_equal_per_capita_pathway_single_country_gets_full_allocation(self):
        """Single country in equal per capita pathway receives full allocation."""
        from fair_shares.library.allocations.pathways import equal_per_capita

        # Create single country population data with multiple years
        single_country_pop = pd.DataFrame(
            [
                ["USA", "million", "2020", 330.0],
                ["USA", "million", "2030", 350.0],
                ["USA", "million", "2040", 370.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

        result = equal_per_capita(
            population_ts=single_country_pop,
            first_allocation_year=2020,
            emission_category="co2-ffi",
        )

        # Verify single country gets 100% allocation in all years
        for year in ["2020", "2030", "2040"]:
            assert result.relative_shares_pathway_emissions.loc[
                ("USA", "dimensionless", "co2-ffi"), year
            ] == pytest.approx(1.0)


class TestNonOverlappingYears:
    """Test edge cases with non-overlapping year ranges."""

    def test_budget_allocation_non_overlapping_years_raises_error(self):
        """Error when population data doesn't include allocation year."""
        from fair_shares.library.allocations.budgets import equal_per_capita_budget

        # Population data: years 2000-2020
        population_old_years = pd.DataFrame(
            [
                ["USA", "million", "2000", 280.0],
                ["USA", "million", "2010", 310.0],
                ["USA", "million", "2020", 330.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

        # Try allocation for year 2030 (not in population data)
        with pytest.raises(DataProcessingError, match="2030"):
            equal_per_capita_budget(
                population_ts=population_old_years,
                allocation_year=2030,
                emission_category="co2-ffi",
            )

    def test_pathway_allocation_non_overlapping_years_raises_error(self):
        """Error when population data doesn't include first allocation year."""
        from fair_shares.library.allocations.pathways import equal_per_capita

        # Population data: years 2030-2050
        population_future_years = pd.DataFrame(
            [
                ["USA", "million", "2030", 350.0],
                ["USA", "million", "2040", 370.0],
                ["USA", "million", "2050", 390.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

        # Try allocation starting from 2020 (not in population data)
        with pytest.raises(DataProcessingError, match="2020"):
            equal_per_capita(
                population_ts=population_future_years,
                first_allocation_year=2020,
                emission_category="co2-ffi",
            )


# Try importing pyam for IAMC tests
try:
    import pyam

    PYAM_AVAILABLE = True
except ImportError:
    PYAM_AVAILABLE = False


@pytest.mark.skipif(not PYAM_AVAILABLE, reason="pyam not installed")
class TestIAMCLoaderErrors:
    """Test error cases in IAMC data loader."""

    @pytest.fixture
    def minimal_iamc_df(self):
        """Create minimal IAMC data for error testing."""
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
                    },
                    {
                        "model": "TestModel",
                        "scenario": "SSP2",
                        "region": "CHN",
                        "variable": "Population",
                        "unit": "million",
                        2020: 1400,
                        2030: 1380,
                    },
                ]
            )
        )

    def test_iamc_missing_variable_error(self, minimal_iamc_df):
        """IAMC loader raises clear error when required variable is missing."""
        from fair_shares.library.exceptions import IAMCDataError
        from fair_shares.library.utils.data.iamc import load_iamc_data

        with pytest.raises(IAMCDataError) as exc_info:
            load_iamc_data(
                minimal_iamc_df,
                population_variable="NonexistentVariable",
                regions=["USA", "CHN"],
                allocation_start_year=2020,
                budget_end_year=2030,
            )

        # Verify error message is helpful
        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower()
        assert "NonexistentVariable" in error_msg
        assert "Available variables" in error_msg

    def test_iamc_missing_region_error(self, minimal_iamc_df):
        """IAMC loader raises clear error when required region is missing."""
        from fair_shares.library.exceptions import IAMCDataError
        from fair_shares.library.utils.data.iamc import load_iamc_data

        with pytest.raises(IAMCDataError) as exc_info:
            load_iamc_data(
                minimal_iamc_df,
                population_variable="Population",
                regions=["USA", "NONEXISTENT"],
                allocation_start_year=2020,
                budget_end_year=2030,
            )

        # Verify error message is helpful
        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower()
        assert "NONEXISTENT" in error_msg
        assert "Available regions" in error_msg

    def test_iamc_missing_year_range_error(self, minimal_iamc_df):
        """IAMC loader raises clear error when data doesn't cover required year range."""
        from fair_shares.library.exceptions import IAMCDataError
        from fair_shares.library.utils.data.iamc import load_iamc_data

        # Data only has 2020, 2030 but we request 1990-2100
        with pytest.raises(IAMCDataError) as exc_info:
            load_iamc_data(
                minimal_iamc_df,
                population_variable="Population",
                regions=["USA", "CHN"],
                allocation_start_year=1990,  # Not in data
                budget_end_year=2100,  # Not in data
            )

        # Verify error mentions missing data for required years
        error_msg = str(exc_info.value)
        assert "missing" in error_msg.lower()
        assert "year" in error_msg.lower()

    def test_iamc_pyam_not_installed_error(self, monkeypatch):
        """IAMC loader raises clear error when pyam is not installed."""
        # Mock pyam as not available
        import fair_shares.library.utils.data.iamc as iamc_module

        monkeypatch.setattr(iamc_module, "PYAM_AVAILABLE", False)

        with pytest.raises(ImportError) as exc_info:
            iamc_module._ensure_pyam()

        # Verify error message includes installation instructions
        error_msg = str(exc_info.value)
        assert "pyam" in error_msg.lower()
        assert "install" in error_msg.lower() or "pip" in error_msg.lower()
