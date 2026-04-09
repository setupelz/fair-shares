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
from fair_shares.library.utils.math.allocation import calculate_relative_adjustment
from fair_shares.library.validation.inputs import (
    validate_emissions_data,
    validate_gdp_data,
    validate_gini_data,
    validate_not_empty,
    validate_population_data,
)


class TestEmptyDataFrameEdgeCases:
    """Test edge cases with empty DataFrames."""

    @pytest.mark.parametrize(
        "validator,name",
        [
            (validate_not_empty, "test dataset"),
            (validate_emissions_data, "emissions test"),
            (validate_population_data, "population test"),
            (validate_gdp_data, "GDP test"),
            (validate_gini_data, "Gini test"),
        ],
    )
    def test_validator_rejects_empty_dataframe(self, validator, name):
        with pytest.raises(DataProcessingError, match="empty"):
            validator(pd.DataFrame(), name)


class TestNaNPropagation:
    """Test edge cases with NaN values propagating through calculations."""

    def test_nan_in_deviation_constraint_population_raises_error(self):
        """NaN values in population during deviation constraint raise clear error."""
        from fair_shares.library.exceptions import AllocationError
        from fair_shares.library.utils.math.allocation import apply_deviation_constraint

        shares = pd.DataFrame(
            {"2020": [0.5, 0.3, 0.2]},
            index=pd.MultiIndex.from_tuples(
                [("USA", "million"), ("CHN", "million"), ("IND", "million")],
                names=["iso3c", "unit"],
            ),
        )

        population_with_nan = pd.DataFrame(
            {"2020": [100.0, np.nan, 300.0]},
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

    @pytest.mark.parametrize("label", ["responsibility", "capability"])
    def test_nan_in_relative_adjustment_handles_gracefully(self, label):
        """NaN values in adjustment input are clamped to neutral (1.0)."""
        values_with_nan = pd.DataFrame(
            {"2020": [5000.0, np.nan, 3000.0]},
            index=pd.MultiIndex.from_tuples(
                [("USA", "million"), ("CHN", "million"), ("IND", "million")],
                names=["iso3c", "unit"],
            ),
        )

        result = calculate_relative_adjustment(
            values=values_with_nan["2020"],
            exponent=0.5,
            inverse=True,
        )

        assert not np.isnan(result).any()
        assert result[1] == 1.0  # CHN (NaN) clamped to neutral


class TestSingleCountryAllocation:
    """Test edge cases with single country allocations."""

    @pytest.mark.parametrize(
        "alloc_func,kwargs",
        [
            pytest.param(
                "fair_shares.library.allocations.budgets.equal_per_capita_budget",
                dict(allocation_year=2020, emission_category="co2-ffi"),
                id="equal_per_capita_budget",
            ),
            pytest.param(
                "fair_shares.library.allocations.budgets.per_capita_adjusted_budget",
                dict(
                    allocation_year=2020,
                    emission_category="co2-ffi",
                    pre_allocation_responsibility_weight=0.3,
                    capability_weight=0.3,
                ),
                id="per_capita_adjusted_budget",
            ),
        ],
    )
    def test_single_country_budget_gets_full_allocation(self, alloc_func, kwargs):
        """Single country in any budget allocation receives 100%."""
        import importlib

        module_path, func_name = alloc_func.rsplit(".", 1)
        func = getattr(importlib.import_module(module_path), func_name)

        pop = pd.DataFrame(
            [
                ["USA", "million", "2015", 320.0],
                ["USA", "million", "2020", 330.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

        call_kwargs = dict(population_ts=pop, **kwargs)

        # per_capita_adjusted_budget needs extra data
        if "per_capita_adjusted" in alloc_func:
            call_kwargs["gdp_ts"] = pd.DataFrame(
                [
                    ["USA", "billion", "2015", 18000.0],
                    ["USA", "billion", "2020", 21000.0],
                ],
                columns=["iso3c", "unit", "year", "gdp"],
            ).pivot_table(index=["iso3c", "unit"], columns="year", values="gdp")

            call_kwargs["country_actual_emissions_ts"] = pd.DataFrame(
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

        result = func(**call_kwargs)
        assert result.relative_shares_cumulative_emission.loc[
            ("USA", "dimensionless", "co2-ffi"), "2020"
        ] == pytest.approx(1.0)

    def test_single_country_pathway_gets_full_allocation(self):
        """Single country in equal per capita pathway receives 100% in all years."""
        from fair_shares.library.allocations.pathways import equal_per_capita

        pop = pd.DataFrame(
            [
                ["USA", "million", "2020", 330.0],
                ["USA", "million", "2030", 350.0],
                ["USA", "million", "2040", 370.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

        result = equal_per_capita(
            population_ts=pop,
            first_allocation_year=2020,
            emission_category="co2-ffi",
        )

        for year in ["2020", "2030", "2040"]:
            assert result.relative_shares_pathway_emissions.loc[
                ("USA", "dimensionless", "co2-ffi"), year
            ] == pytest.approx(1.0)


class TestNonOverlappingYears:
    """Test edge cases with non-overlapping year ranges."""

    def test_budget_allocation_non_overlapping_years_raises_error(self):
        """Error when population data doesn't include allocation year."""
        from fair_shares.library.allocations.budgets import equal_per_capita_budget

        population_old_years = pd.DataFrame(
            [
                ["USA", "million", "2000", 280.0],
                ["USA", "million", "2010", 310.0],
                ["USA", "million", "2020", 330.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

        with pytest.raises(DataProcessingError, match="2030"):
            equal_per_capita_budget(
                population_ts=population_old_years,
                allocation_year=2030,
                emission_category="co2-ffi",
            )

    def test_pathway_allocation_non_overlapping_years_raises_error(self):
        """Error when population data doesn't include first allocation year."""
        from fair_shares.library.allocations.pathways import equal_per_capita

        population_future_years = pd.DataFrame(
            [
                ["USA", "million", "2030", 350.0],
                ["USA", "million", "2040", 370.0],
                ["USA", "million", "2050", 390.0],
            ],
            columns=["iso3c", "unit", "year", "population"],
        ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")

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

        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower()
        assert "NONEXISTENT" in error_msg
        assert "Available regions" in error_msg

    def test_iamc_missing_year_range_error(self, minimal_iamc_df):
        """IAMC loader raises clear error when data doesn't cover required year range."""
        from fair_shares.library.exceptions import IAMCDataError
        from fair_shares.library.utils.data.iamc import load_iamc_data

        with pytest.raises(IAMCDataError) as exc_info:
            load_iamc_data(
                minimal_iamc_df,
                population_variable="Population",
                regions=["USA", "CHN"],
                allocation_start_year=1990,
                budget_end_year=2100,
            )

        error_msg = str(exc_info.value)
        assert "missing" in error_msg.lower()
        assert "year" in error_msg.lower()

    def test_iamc_pyam_not_installed_error(self, monkeypatch):
        """IAMC loader raises clear error when pyam is not installed."""
        import fair_shares.library.utils.data.iamc as iamc_module

        monkeypatch.setattr(iamc_module, "PYAM_AVAILABLE", False)

        with pytest.raises(ImportError) as exc_info:
            iamc_module._ensure_pyam()

        error_msg = str(exc_info.value)
        assert "pyam" in error_msg.lower()
        assert "install" in error_msg.lower() or "pip" in error_msg.lower()
