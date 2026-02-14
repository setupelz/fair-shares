"""
Tests for input validation functions.

Tests validation of year parameters, DataFrame structure, and data quality checks.
"""

from __future__ import annotations

import pytest

from fair_shares.library.config.models import GiniDataParameters
from fair_shares.library.exceptions import AllocationError, ConfigurationError
from fair_shares.library.validation.inputs import validate_year_parameter


class TestYearParameterValidation:
    """Test year parameter type validation."""

    def test_valid_year_integer(self):
        """Valid integer year should not raise."""
        validate_year_parameter(2020, "test_year")
        validate_year_parameter(1990, "historical_year")
        validate_year_parameter(2100, "future_year")

    def test_year_as_string_raises(self):
        """String year should raise AllocationError."""
        with pytest.raises(AllocationError, match="must be an integer.*str.*2020"):
            validate_year_parameter("2020", "test_year")

    def test_year_as_float_raises(self):
        """Float year should raise AllocationError."""
        with pytest.raises(AllocationError, match="must be an integer.*float.*2020"):
            validate_year_parameter(2020.0, "test_year")

    def test_year_as_none_raises(self):
        """None year should raise AllocationError."""
        with pytest.raises(AllocationError, match="must be an integer.*NoneType"):
            validate_year_parameter(None, "test_year")

    def test_error_message_includes_parameter_name(self):
        """Error message should include the parameter name."""
        with pytest.raises(AllocationError, match="first_allocation_year"):
            validate_year_parameter("2020", "first_allocation_year")


class TestGiniYearBoundsValidation:
    """Test gini_year bounds validation in config models."""

    def test_valid_gini_year(self):
        """Valid gini_year within bounds should not raise."""
        # Boundary values
        GiniDataParameters(world_key="WORLD", gini_year=1900)
        GiniDataParameters(world_key="WORLD", gini_year=2100)

        # Middle values
        GiniDataParameters(world_key="WORLD", gini_year=2000)
        GiniDataParameters(world_key="WORLD", gini_year=2015)

    def test_gini_year_below_1900_raises(self):
        """gini_year below 1900 should raise ConfigurationError."""
        with pytest.raises(
            ConfigurationError, match="gini_year must be between 1900 and 2100"
        ):
            GiniDataParameters(world_key="WORLD", gini_year=1899)

        with pytest.raises(
            ConfigurationError, match="gini_year must be between 1900 and 2100"
        ):
            GiniDataParameters(world_key="WORLD", gini_year=1800)

    def test_gini_year_above_2100_raises(self):
        """gini_year above 2100 should raise ConfigurationError."""
        with pytest.raises(
            ConfigurationError, match="gini_year must be between 1900 and 2100"
        ):
            GiniDataParameters(world_key="WORLD", gini_year=2101)

        with pytest.raises(
            ConfigurationError, match="gini_year must be between 1900 and 2100"
        ):
            GiniDataParameters(world_key="WORLD", gini_year=2200)

    def test_error_message_includes_value(self):
        """Error message should include the invalid year value."""
        with pytest.raises(ConfigurationError, match="got 1850"):
            GiniDataParameters(world_key="WORLD", gini_year=1850)

        with pytest.raises(ConfigurationError, match="got 2150"):
            GiniDataParameters(world_key="WORLD", gini_year=2150)
