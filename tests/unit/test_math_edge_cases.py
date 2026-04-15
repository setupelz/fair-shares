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
    calculate_relative_adjustment,
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


class TestRelativeAdjustmentAsinhNormalisation:
    """Test the asinh transform with median normalisation in calculate_relative_adjustment."""

    @pytest.fixture
    def positive_series(self):
        """Positive values typical of GDP per capita."""
        return pd.Series(
            [5000.0, 10000.0, 20000.0, 40000.0],
            index=pd.MultiIndex.from_tuples(
                [("A", "usd"), ("B", "usd"), ("C", "usd"), ("D", "usd")],
                names=["iso3c", "unit"],
            ),
        )

    def test_negative_values_produce_valid_results_with_asinh(self):
        """Net-sink countries (negative emissions) produce valid finite results.

        Uses exponent=1.0 because fractional exponents on negative arcsinh outputs
        produce NaN (negative base with fractional power). With exponent=1.0 the
        full real line maps cleanly through arcsinh.
        """
        values = pd.Series(
            [-500.0, 1000.0, 3000.0, 5000.0],
            index=pd.MultiIndex.from_tuples(
                [("A", "Mt"), ("B", "Mt"), ("C", "Mt"), ("D", "Mt")],
                names=["iso3c", "unit"],
            ),
        )
        result = calculate_relative_adjustment(
            values, functional_form="asinh", exponent=1.0, inverse=False
        )
        assert not np.isnan(result).any()
        assert np.all(np.isfinite(result))
        # Negative input should produce negative arcsinh output
        assert result.iloc[0] < 0

    def test_unit_invariance_with_normalisation(self, positive_series):
        """Multiplying all inputs by 1000 produces the same result when normalize=True."""
        result_base = calculate_relative_adjustment(
            positive_series,
            functional_form="asinh",
            exponent=0.5,
            inverse=True,
            normalize=True,
        )
        result_scaled = calculate_relative_adjustment(
            positive_series * 1000,
            functional_form="asinh",
            exponent=0.5,
            inverse=True,
            normalize=True,
        )
        pd.testing.assert_series_equal(result_base, result_scaled, rtol=1e-10)

    def test_normalize_false_differs_from_normalize_true(self, positive_series):
        """normalize=False gives different results than normalize=True."""
        result_norm = calculate_relative_adjustment(
            positive_series,
            functional_form="asinh",
            exponent=0.5,
            inverse=True,
            normalize=True,
        )
        result_raw = calculate_relative_adjustment(
            positive_series,
            functional_form="asinh",
            exponent=0.5,
            inverse=True,
            normalize=False,
        )
        # They should NOT be equal (unless the median happens to be 1, which it isn't)
        assert not np.allclose(result_norm.values, result_raw.values)

    def test_zero_median_guard_all_zeros(self):
        """When all values are zero (degenerate), median is zero and guard kicks in.

        Median is 0 -> replaced with NaN -> values/NaN = NaN -> fillna(0) -> all zeros.
        arcsinh(0) = 0.
        """
        values = pd.Series(
            [0.0, 0.0, 0.0],
            index=pd.MultiIndex.from_tuples(
                [("A", "x"), ("B", "x"), ("C", "x")],
                names=["iso3c", "unit"],
            ),
        )
        result = calculate_relative_adjustment(
            values, functional_form="asinh", exponent=1.0, inverse=False
        )
        assert not np.isnan(result).any()
        # arcsinh(0)^1 = 0 for all entries
        np.testing.assert_array_equal(result.values, [0.0, 0.0, 0.0])

    def test_default_functional_form_is_asinh(self, positive_series):
        """Default functional_form changed from 'power' to 'asinh'."""
        result_default = calculate_relative_adjustment(positive_series, exponent=0.5)
        result_explicit = calculate_relative_adjustment(
            positive_series, functional_form="asinh", exponent=0.5
        )
        pd.testing.assert_series_equal(result_default, result_explicit)

    def test_power_form_still_works(self, positive_series):
        """Power form with normalisation produces finite positive results."""
        result = calculate_relative_adjustment(
            positive_series,
            functional_form="power",
            exponent=0.5,
            inverse=True,
            normalize=True,
        )
        assert not np.isnan(result).any()
        assert np.all(np.isfinite(result))
        assert np.all(result > 0)
