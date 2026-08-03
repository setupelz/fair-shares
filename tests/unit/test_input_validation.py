"""
Tests for input validation functions.

Tests validation of year parameters, DataFrame structure, and data quality checks.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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


class TestGiniSelectionValidation:
    """Test Gini source parameter validation in config models."""

    def test_valid_parameters(self):
        """A selection rule with or without a year window is accepted."""
        GiniDataParameters(selection="latest-high-quality")
        GiniDataParameters(selection="latest-available", year_window=[2015, 2023])
        GiniDataParameters(selection="latest-available", year_window=[1900, 2100])

    def test_unknown_selection_rejected(self):
        """A selection rule no notebook implements must not validate."""
        with pytest.raises(ValidationError):
            GiniDataParameters(selection="single-year")

    def test_year_window_needs_two_years(self):
        with pytest.raises(ConfigurationError, match="\\[first_year, last_year\\]"):
            GiniDataParameters(selection="latest-available", year_window=[2015])

    def test_year_window_bounds(self):
        with pytest.raises(ConfigurationError, match="between 1900 and 2100"):
            GiniDataParameters(selection="latest-available", year_window=[1850, 2023])

        with pytest.raises(ConfigurationError, match="between 1900 and 2100"):
            GiniDataParameters(selection="latest-available", year_window=[2015, 2150])

    def test_year_window_order(self):
        with pytest.raises(ConfigurationError, match="out of order"):
            GiniDataParameters(selection="latest-available", year_window=[2023, 2015])
