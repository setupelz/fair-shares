"""
Tests for RCB (Remaining Carbon Budget) calculation functions.

"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils import (
    TimeseriesDataFrame,
    calculate_budget_from_rcb,
    parse_rcb_scenario,
)


class TestParseRCBScenario:
    """Tests for parse_rcb_scenario function."""

    def test_parse_standard_scenarios(self):
        """Test parsing of standard RCB scenario strings."""
        climate, quantile = parse_rcb_scenario("1.5p50")
        assert climate == "1.5C"
        assert quantile == "0.5"

    def test_parse_invalid_format(self):
        """Test that invalid formats raise DataProcessingError."""
        with pytest.raises(DataProcessingError, match="Invalid RCB scenario format"):
            parse_rcb_scenario("1.5C_50")

        with pytest.raises(DataProcessingError, match="Invalid RCB scenario format"):
            parse_rcb_scenario("1.5-50")

        with pytest.raises(DataProcessingError, match="Invalid RCB scenario format"):
            parse_rcb_scenario("invalid")

    def test_parse_invalid_probability(self):
        """Test that invalid probability values raise DataProcessingError."""
        with pytest.raises(DataProcessingError, match="Invalid probability value"):
            parse_rcb_scenario("1.5pabc")

        with pytest.raises(DataProcessingError, match="Invalid probability value"):
            parse_rcb_scenario("2p")


class TestCalculateBudgetFromRCB:
    """Tests for calculate_budget_from_rcb function."""

    @pytest.fixture
    def world_scenario_emissions_ts(self) -> TimeseriesDataFrame:
        """Create test world emissions timeseries data."""
        # Create emissions data for years 1990-2025
        years = list(range(1990, 2026))
        # Use 10 Gt per year for simplicity
        emissions = [10.0] * len(years)

        data = {str(year): [emiss] for year, emiss in zip(years, emissions)}

        index = pd.MultiIndex.from_tuples(
            [("World", "Gt * CO2e", "co2-ffi")],
            names=["iso3c", "unit", "emission-category"],
        )

        return pd.DataFrame(data, index=index)

    def test_allocation_year_2020(self, world_scenario_emissions_ts):
        """Test that RCB is used directly when allocation year is 2020."""
        rcb_value = 500.0
        result = calculate_budget_from_rcb(
            rcb_value, 2020, world_scenario_emissions_ts, verbose=False
        )

        expected = rcb_value
        assert result == expected

    def test_allocation_year_before_2020(self, world_scenario_emissions_ts):
        """Test that historical emissions are added for allocation years before 2020."""
        rcb_value = 500.0
        allocation_year = 1990

        result = calculate_budget_from_rcb(
            rcb_value, allocation_year, world_scenario_emissions_ts, verbose=False
        )

        # Expected: historical emissions (1990-2019) + RCB
        # 30 years * 10 Gt/year = 300 Gt
        expected = 300.0 + 500.0
        assert result == expected

    def test_allocation_year_after_2020(self, world_scenario_emissions_ts):
        """Test that emissions already used are subtracted for allocation years after 2020."""
        rcb_value = 500.0
        allocation_year = 2025

        result = calculate_budget_from_rcb(
            rcb_value, allocation_year, world_scenario_emissions_ts, verbose=False
        )

        # Expected: RCB - emissions used (2020-2024)
        # 5 years * 10 Gt/year = 50 Gt
        expected = 500.0 - 50.0
        assert result == expected

    def test_allocation_year_2010(self, world_scenario_emissions_ts):
        """Test intermediate allocation year before 2020."""
        rcb_value = 500.0
        allocation_year = 2010

        result = calculate_budget_from_rcb(
            rcb_value, allocation_year, world_scenario_emissions_ts, verbose=False
        )

        # Expected: historical emissions (2010-2019) + RCB
        # 10 years * 10 Gt/year = 100 Gt
        expected = 100.0 + 500.0
        assert result == expected

    def test_allocation_year_2023(self, world_scenario_emissions_ts):
        """Test intermediate allocation year after 2020."""
        rcb_value = 500.0
        allocation_year = 2023

        result = calculate_budget_from_rcb(
            rcb_value, allocation_year, world_scenario_emissions_ts, verbose=False
        )

        # Expected: RCB - emissions used (2020-2022)
        # 3 years * 10 Gt/year = 30 Gt
        expected = 500.0 - 30.0
        assert result == expected

    def test_verbose_output(self, world_scenario_emissions_ts, capsys):
        """Test that verbose output is produced when verbose=True."""
        rcb_value = 500.0

        # Test verbose output for allocation year 2020
        calculate_budget_from_rcb(
            rcb_value, 2020, world_scenario_emissions_ts, verbose=True
        )
        captured = capsys.readouterr()
        assert "Allocation year 2020 = 2020" in captured.out
        assert "RCB 500.0 Mt CO2" in captured.out

        # Test verbose output for allocation year before 2020
        calculate_budget_from_rcb(
            rcb_value, 1990, world_scenario_emissions_ts, verbose=True
        )
        captured = capsys.readouterr()
        assert "Allocation year 1990 < 2020" in captured.out
        assert "Historical" in captured.out

        # Test verbose output for allocation year after 2020
        calculate_budget_from_rcb(
            rcb_value, 2025, world_scenario_emissions_ts, verbose=True
        )
        captured = capsys.readouterr()
        assert "Allocation year 2025 > 2020" in captured.out
        assert "Used" in captured.out

    def test_with_variable_emissions(self):
        """Test with variable emissions to ensure correct summation."""
        # Create variable emissions data
        years = list(range(2015, 2026))
        emissions = [
            10.0,
            11.0,
            12.0,
            13.0,
            14.0,  # 2015-2019
            15.0,
            16.0,
            17.0,
            18.0,
            19.0,
            20.0,
        ]  # 2020-2025

        data = {str(year): [emiss] for year, emiss in zip(years, emissions)}

        index = pd.MultiIndex.from_tuples(
            [("World", "Gt * CO2e", "co2-ffi")],
            names=["iso3c", "unit", "emission-category"],
        )

        world_scenario_emissions_ts = pd.DataFrame(data, index=index)

        rcb_value = 500.0

        # Test allocation year 2015
        result = calculate_budget_from_rcb(
            rcb_value, 2015, world_scenario_emissions_ts, verbose=False
        )
        # Historical 2015-2019: 10+11+12+13+14 = 60
        expected = 60.0 + 500.0
        assert result == expected

        # Test allocation year 2022
        result = calculate_budget_from_rcb(
            rcb_value, 2022, world_scenario_emissions_ts, verbose=False
        )
        # Used 2020-2021: 15+16 = 31
        expected = 500.0 - 31.0
        assert result == expected
