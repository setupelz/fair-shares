"""
Edge case tests for math utility functions in allocation module.

Tests critical numerical safety issues including division by zero
and NaN validation in allocation math operations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils.math.allocation import (
    apply_deviation_constraint,
    calculate_gini_adjusted_gdp,
)


class TestGiniAdjustmentEdgeCases:
    """Test edge cases in Gini-adjusted GDP calculation."""

    def test_zero_population_raises_error(self):
        """Test that zero population raises AllocationError before division."""
        total_gdps = np.array([1000.0, 2000.0, 3000.0])
        gini_coefficients = np.array([0.3, 0.4, 0.5])
        income_floor = 1000.0
        total_populations = np.array([100.0, 0.0, 200.0])  # Zero population

        with pytest.raises(
            AllocationError,
            match="Zero population found.*Cannot calculate mean income per capita",
        ):
            calculate_gini_adjusted_gdp(
                total_gdps=total_gdps,
                gini_coefficients=gini_coefficients,
                income_floor=income_floor,
                total_populations=total_populations,
            )

    def test_all_zero_population_raises_error(self):
        """Test that all zero populations raises AllocationError."""
        total_gdps = np.array([1000.0, 2000.0, 3000.0])
        gini_coefficients = np.array([0.3, 0.4, 0.5])
        income_floor = 1000.0
        total_populations = np.array([0.0, 0.0, 0.0])  # All zero

        with pytest.raises(
            AllocationError,
            match="Zero population found.*Cannot calculate mean income per capita",
        ):
            calculate_gini_adjusted_gdp(
                total_gdps=total_gdps,
                gini_coefficients=gini_coefficients,
                income_floor=income_floor,
                total_populations=total_populations,
            )

    def test_valid_populations_no_error(self):
        """Test that valid populations do not raise errors."""
        total_gdps = np.array([1000.0, 2000.0, 3000.0])
        gini_coefficients = np.array([0.3, 0.4, 0.5])
        income_floor = 1000.0
        total_populations = np.array([100.0, 200.0, 300.0])  # All valid

        # Should not raise
        result = calculate_gini_adjusted_gdp(
            total_gdps=total_gdps,
            gini_coefficients=gini_coefficients,
            income_floor=income_floor,
            total_populations=total_populations,
        )

        assert result is not None
        assert len(result) == 3
        assert np.all(result >= 0)  # Adjusted GDP should be non-negative


class TestDeviationConstraintEdgeCases:
    """Test edge cases in deviation constraint application."""

    def test_nan_population_raises_error(self):
        """Test that NaN population raises AllocationError before division."""
        # Create test data with NaN in population
        data_shares = {"2020": [0.5, 0.3, 0.2], "2021": [0.4, 0.4, 0.2]}
        data_pop = {"2020": [100.0, np.nan, 300.0], "2021": [110.0, 220.0, 330.0]}

        index_tuples = [("USA", "million"), ("CHN", "million"), ("IND", "million")]
        index = pd.MultiIndex.from_tuples(index_tuples, names=["iso3c", "unit"])

        shares = pd.DataFrame(data_shares, index=index)
        population = pd.DataFrame(data_pop, index=index)

        with pytest.raises(
            AllocationError,
            match="Population data contains NaN values.*Check data quality",
        ):
            apply_deviation_constraint(
                shares=shares,
                population=population,
                max_deviation_sigma=2.0,
                group_level="iso3c",
            )

    def test_all_nan_population_raises_error(self):
        """Test that all NaN populations raises AllocationError."""
        # Create test data with all NaN in population
        data_shares = {"2020": [0.5, 0.3, 0.2], "2021": [0.4, 0.4, 0.2]}
        data_pop = {"2020": [np.nan, np.nan, np.nan], "2021": [np.nan, np.nan, np.nan]}

        index_tuples = [("USA", "million"), ("CHN", "million"), ("IND", "million")]
        index = pd.MultiIndex.from_tuples(index_tuples, names=["iso3c", "unit"])

        shares = pd.DataFrame(data_shares, index=index)
        population = pd.DataFrame(data_pop, index=index)

        with pytest.raises(
            AllocationError,
            match="Population data contains NaN values.*Check data quality",
        ):
            apply_deviation_constraint(
                shares=shares,
                population=population,
                max_deviation_sigma=2.0,
                group_level="iso3c",
            )

    def test_valid_population_no_error(self):
        """Test that valid populations do not raise errors."""
        # Create test data with valid population
        data_shares = {"2020": [0.5, 0.3, 0.2], "2021": [0.4, 0.4, 0.2]}
        data_pop = {"2020": [100.0, 200.0, 300.0], "2021": [110.0, 220.0, 330.0]}

        index_tuples = [("USA", "million"), ("CHN", "million"), ("IND", "million")]
        index = pd.MultiIndex.from_tuples(index_tuples, names=["iso3c", "unit"])

        shares = pd.DataFrame(data_shares, index=index)
        population = pd.DataFrame(data_pop, index=index)

        # Should not raise
        result = apply_deviation_constraint(
            shares=shares,
            population=population,
            max_deviation_sigma=2.0,
            group_level="iso3c",
        )

        assert result is not None
        assert result.shape == shares.shape
        # Shares should sum to approximately 1 for each year
        assert np.allclose(result.sum(axis=0), 1.0, rtol=1e-5)
