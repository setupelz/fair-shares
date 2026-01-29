"""
Integration tests for unit conversion functionality for the fair-shares library.

"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.utils import convert_unit_robust, get_default_unit_registry


class TestUnitConversion:
    """Tests unit conversions with AR6GWP100 context and annual transformations."""

    @pytest.fixture
    def ur(self):
        """Get the default unit registry with all contexts enabled."""
        return get_default_unit_registry()

    def test_ar6gwp100_conversions_to_mt_co2e(self, ur):
        """Test AR6GWP100 conversions to Mt CO2e for key greenhouse gases."""
        # Test CO2 (1:1 ratio) - 1000 Gg = 1 Mt
        assert ur("1000 CO2 * gigagram / a").to("Mt * CO2e").magnitude == 1.0
        assert ur("1000 CO2 * gigagram / a").to("Mt * CO2e").units == "Mt * CO2e"
        # Test CH4 (AR6 GWP100 = 27.9) - 1000 Gg * 27.9 = 27.9 Mt (Radiative forcing
        # only, AR6 Supplemental Material for WGI Chapter 7, Table 7.SM.6)
        assert abs(ur("1000 CH4 * gigagram / a").to("Mt * CO2e").magnitude - 27.9) < 0.1
        assert ur("1000 CH4 * gigagram / a").to("Mt * CO2e").units == "Mt * CO2e"
        # Test N2O (AR6 GWP100 = 273) - 1000 Gg * 273 = 273 Mt
        assert (
            abs(ur("1000 N2O * gigagram / a").to("Mt * CO2e").magnitude - 273.0) < 0.1
        )
        assert ur("1000 N2O * gigagram / a").to("Mt * CO2e").units == "Mt * CO2e"

    def test_annual_assumption_transformation(self, ur):
        """Test the annual assumption transformation for mass/time to mass."""
        # Test monthly rate to total (should convert to annual first)
        monthly_rate = ur("1 kt * CO2 / month")
        total_emissions = monthly_rate.to("kt * CO2")
        assert total_emissions.magnitude == 12.0  # 12 months = 1 year


class TestConvertUnitRobust:
    """Tests for the convert_unit_robust function."""

    @pytest.fixture
    def ur(self):
        """Get the default unit registry with all contexts enabled."""
        return get_default_unit_registry()

    def test_convert_unit_robust_needed(self, ur):
        """Test basic unit conversion when unit cleaning is needed."""
        # Test the main functionality: converting units with automatic normalization
        df = pd.DataFrame(
            [[1.0, 2.0], [3.0, 4.0]],
            columns=[2020, 2030],
            index=pd.MultiIndex.from_tuples(
                [("afg", "Mt CO2/yr"), ("aus", "kt CH4/yr")], names=["iso3c", "unit"]
            ),
        )

        result = convert_unit_robust(df, "Mt * CO2e", unit_level="unit", ur=ur)

        # Check that conversion worked
        assert result.index.get_level_values("unit").unique() == ["Mt * CO2e"]
        assert result.shape == df.shape
        assert result.index.names == df.index.names

    def test_convert_unit_robust_with_duplicate_index_fails(self, ur):
        """Test that convert_unit_robust fails gracefully with duplicate index values."""
        # Create DataFrame with duplicate index combinations
        df = pd.DataFrame(
            [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            columns=[2020, 2030],
            index=pd.MultiIndex.from_tuples(
                [("afg", "Mt CO2/yr"), ("afg", "Mt CO2/yr"), ("aus", "kt CH4/yr")],
                names=["iso3c", "unit"],
            ),
        )

        # Should raise an error due to duplicate index values
        with pytest.raises(pd.errors.InvalidIndexError):
            convert_unit_robust(df, "Mt * CO2e", unit_level="unit", ur=ur)

    def test_convert_unit_robust_not_needed(self, ur):
        """Test convert_unit_robust when no unit cleaning is needed."""
        # Create DataFrame with properly spaced units
        df = pd.DataFrame(
            [[1.0, 2.0], [3.0, 4.0]],
            columns=[2020, 2030],
            index=pd.MultiIndex.from_tuples(
                [("afg", "Mt CO2 / yr"), ("aus", "kt CH4 / yr")],
                names=["iso3c", "unit"],
            ),
        )

        result = convert_unit_robust(df, "Mt * CO2e", unit_level="unit", ur=ur)

        # Check that conversion worked
        assert result.index.get_level_values("unit").unique() == ["Mt * CO2e"]
        assert result.shape == df.shape
        assert result.index.names == df.index.names
