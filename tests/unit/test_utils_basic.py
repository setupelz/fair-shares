"""
Basic tests for utility functions for the fair-shares library.

"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.utils import (
    TimeseriesDataFrame,
    get_default_unit_registry,
)
from fair_shares.library.utils.dataframes import get_year_columns
from fair_shares.library.validation import (
    validate_has_year_columns,
    validate_index_structure,
)


class TestUtilsBasic:
    """Basic tests for core utility functions."""

    def test_get_default_unit_registry(self):
        """Test that default unit registry can be created and has expected units."""
        ur = get_default_unit_registry()

        # Test that it's a registry
        assert hasattr(ur, "Quantity"), "Should be a unit registry with Quantity"
        assert hasattr(ur, "Unit"), "Should be a unit registry with Unit"

        # Test that it has climate-specific units we depend on
        test_units = ["dimensionless", "Mt * CO2e", "million", "thousand", "kt"]

        for unit_str in test_units:
            try:
                unit = ur.Unit(unit_str)
                assert unit is not None, f"Should be able to create unit: {unit_str}"
            except Exception as e:
                pytest.fail(f"Failed to create unit '{unit_str}': {e}")

    def test_timeseries_dataframe_type(self):
        """Test that TimeseriesDataFrame is a valid type alias."""
        # Create a simple timeseries-like DataFrame
        data = {2020: [100, 200, 300], 2021: [110, 220, 330], 2022: [120, 240, 360]}

        index_tuples = [("USA", "million"), ("CHN", "million"), ("World", "million")]
        index = pd.MultiIndex.from_tuples(index_tuples, names=["iso3c", "unit"])

        df = pd.DataFrame(data, index=index)

        # Test that it's a TimeseriesDataFrame (which is just pd.DataFrame)
        assert isinstance(df, TimeseriesDataFrame), "Should be a TimeseriesDataFrame"
        assert isinstance(df, pd.DataFrame), "TimeseriesDataFrame should be a DataFrame"

        # Test basic properties
        assert len(df) == 3, "Should have 3 rows"
        assert len(df.columns) == 3, "Should have 3 year columns"
        assert isinstance(df.index, pd.MultiIndex), "Should have MultiIndex"

    def test_validate_index_structure_basic(self):
        """Test that validate_index_structure works with valid data."""
        # Create valid timeseries data
        data = {2020: [100, 200], 2021: [110, 220]}

        index_tuples = [("USA", "million"), ("CHN", "million")]
        index = pd.MultiIndex.from_tuples(index_tuples, names=["iso3c", "unit"])
        df = pd.DataFrame(data, index=index)

        # This should not raise any exceptions
        validate_index_structure(
            df, "test data", expected_index_names=["iso3c", "unit"]
        )
        validate_has_year_columns(df, "test data")

        # Test that we can get year columns
        year_cols = get_year_columns(df)
        assert isinstance(year_cols, list), "Should return list of year columns"
        assert len(year_cols) == 2, "Should find 2 year columns"
        assert "2020" in year_cols, "Should include 2020"
        assert "2021" in year_cols, "Should include 2021"

    def test_validate_index_structure_invalid_index(self):
        """Test that validate_index_structure raises on invalid index."""
        # Create data with wrong index structure
        data = {2020: [100, 200], 2021: [110, 220]}

        # Wrong index names
        index_tuples = [("USA", "million"), ("CHN", "million")]
        index = pd.MultiIndex.from_tuples(
            index_tuples, names=["country", "unit"]
        )  # Wrong name
        df = pd.DataFrame(data, index=index)

        # This should raise DataProcessingError
        from fair_shares.library.exceptions import DataProcessingError

        with pytest.raises(DataProcessingError):
            validate_index_structure(
                df, "test data", expected_index_names=["iso3c", "unit"]
            )

    def test_validate_has_year_columns_no_year_columns(self):
        """Test that validate_has_year_columns raises when no year columns found."""
        # Create data with no numeric year columns
        data = {"country": ["USA", "CHN"], "value": [100, 200]}

        index_tuples = [("USA", "million"), ("CHN", "million")]
        index = pd.MultiIndex.from_tuples(index_tuples, names=["iso3c", "unit"])
        df = pd.DataFrame(data, index=index)

        # This should raise DataProcessingError with enhanced error message
        from fair_shares.library.exceptions import DataProcessingError

        with pytest.raises(DataProcessingError, match="Year columns not detected"):
            validate_has_year_columns(df, "test data")
