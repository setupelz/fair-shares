"""
Unit tests for harmonisation / pathway scaling functions for the fair-shares library.

"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fair_shares.library.utils.timeseries import (
    _apply_cumulative_preservation_scaling,
    harmonize_to_historical_with_convergence,
)


class TestApplyCumulativePreservationScaling:
    """Test the core mathematical function for cumulative preservation scaling."""

    def test_basic_functionality(self):
        """Test basic functionality with simple positive values."""
        values = np.array([10.0, 15.0, 20.0, 25.0])
        years = np.array([2020, 2021, 2022, 2023])
        first_adjustment_year = 2021
        target_cumulative = 70.0  # Sum of all values

        result = _apply_cumulative_preservation_scaling(
            values=values,
            years=years,
            first_adjustment_year=first_adjustment_year,
            target_cumulative=target_cumulative,
        )

        # Should preserve cumulative total
        assert np.isclose(np.sum(result), target_cumulative, rtol=1e-9)

        # Years before adjustment should be unchanged
        assert result[0] == 10.0

    def test_with_negative_values(self):
        """Test handling of negative values in adjustment window."""
        values = np.array([10.0, -5.0, 20.0, 25.0])
        years = np.array([2020, 2021, 2022, 2023])
        first_adjustment_year = 2021
        target_cumulative = 50.0  # Sum of all values

        result = _apply_cumulative_preservation_scaling(
            values=values,
            years=years,
            first_adjustment_year=first_adjustment_year,
            target_cumulative=target_cumulative,
        )

        # Should preserve cumulative total
        assert np.isclose(np.sum(result), target_cumulative, rtol=1e-9)

        # Negative value should be set to 0
        assert result[1] == 0.0

        # Pre-adjustment value should be unchanged
        assert result[0] == 10.0  # Before adjustment window


class TestHarmonizeToHistoricalWithConvergence:
    """Test the harmonization function with convergence."""

    def test_basic_harmonization(self):
        """Test basic harmonization functionality."""
        # Create scenario data
        scenario_data = {
            2020: [100.0, 110.0],
            2021: [105.0, 115.0],
            2022: [110.0, 120.0],
            2023: [115.0, 125.0],
        }
        scenario_index = pd.MultiIndex.from_tuples(
            [("USA", "Mt * CO2e"), ("CHN", "Mt * CO2e")], names=["iso3c", "unit"]
        )
        scenario_ts = pd.DataFrame(scenario_data, index=scenario_index)

        # Create historical data (matching anchor year 2020)
        historical_data = {
            2020: [95.0, 105.0]  # Different from scenario
        }
        historical_index = pd.MultiIndex.from_tuples(
            [("USA", "Mt * CO2e"), ("CHN", "Mt * CO2e")], names=["iso3c", "unit"]
        )
        historical_ts = pd.DataFrame(historical_data, index=historical_index)

        result = harmonize_to_historical_with_convergence(
            scenario_ts=scenario_ts,
            historical_ts=historical_ts,
            anchor_year=2020,
            convergence_year=2022,
        )

        # At anchor year, should match historical exactly
        assert result.loc[("USA", "Mt * CO2e"), 2020] == 95.0
        assert result.loc[("CHN", "Mt * CO2e"), 2020] == 105.0

        # At convergence year, should match original scenario
        assert result.loc[("USA", "Mt * CO2e"), 2022] == 110.0
        assert result.loc[("CHN", "Mt * CO2e"), 2022] == 120.0

    def test_ease_in_scaling_behavior(self):
        """Test that ease-in approach concentrates adjustments in later years."""
        values = np.array([10.0, -10.0, 20.0, 30.0])
        years = np.array([2020, 2021, 2022, 2023])
        first_adjustment_year = 2021
        target_cumulative = 50.0  # Sum of all values

        result = _apply_cumulative_preservation_scaling(
            values=values,
            years=years,
            first_adjustment_year=first_adjustment_year,
            target_cumulative=target_cumulative,
            easing_power=2.0,  # Quadratic ease-in
        )

        # Cumulative should be preserved
        assert np.isclose(np.sum(result), target_cumulative, rtol=1e-9)

        # Year 2021 negative becomes 0
        assert result[1] == 0.0

        # With ease-in, scaling factors increase over time
        # Later years get scaled down more (since we need to reduce total)
        # The scaling factor is multiplicative and weighted by time and magnitude
        # So absolute adjustment magnitude should be larger for later, larger values
        abs_adjustment_2022 = abs(result[2] - 20.0)
        abs_adjustment_2023 = abs(result[3] - 30.0)

        # 2023 should have larger absolute adjustment due to larger baseline and later time
        assert abs_adjustment_2023 > abs_adjustment_2022

    def test_harmonization_with_cumulative_preservation(self):
        """Test harmonization with preserve_cumulative_peak=True."""
        # Create scenario with peak then decline
        scenario_data = {
            2020: [100.0],
            2021: [120.0],
            2022: [110.0],  # Peak at 2021
            2023: [90.0],
            2024: [-20.0],  # Net-negative
        }
        scenario_index = pd.MultiIndex.from_tuples(
            [("World", "Mt * CO2e")], names=["iso3c", "unit"]
        )
        scenario_ts = pd.DataFrame(scenario_data, index=scenario_index)

        # Historical data different from scenario
        historical_data = {2020: [90.0]}
        historical_ts = pd.DataFrame(historical_data, index=scenario_index)

        # Harmonize WITH cumulative preservation
        result = harmonize_to_historical_with_convergence(
            scenario_ts=scenario_ts,
            historical_ts=historical_ts,
            anchor_year=2020,
            convergence_year=2022,
            preserve_cumulative_peak=True,
            max_peak_diff_percent=5.0,  # Allow 5% difference
        )

        # Should match historical at anchor
        assert result.loc[("World", "Mt * CO2e"), 2020] == 90.0

        # Peak cumulative should be close to original
        original_peak = np.max(
            np.cumsum(scenario_ts.loc[("World", "Mt * CO2e")].values)
        )
        result_peak = np.max(np.cumsum(result.loc[("World", "Mt * CO2e")].values))

        # Peak difference should be within threshold
        peak_diff_percent = abs((result_peak - original_peak) / original_peak) * 100
        assert peak_diff_percent <= 5.0

    def test_harmonization_transition_period(self):
        """Test linear interpolation in transition period."""
        scenario_data = {2020: [100.0], 2021: [105.0], 2022: [110.0], 2023: [115.0]}
        scenario_index = pd.MultiIndex.from_tuples(
            [("USA", "Mt * CO2e")], names=["iso3c", "unit"]
        )
        scenario_ts = pd.DataFrame(scenario_data, index=scenario_index)

        historical_data = {2020: [90.0]}
        historical_ts = pd.DataFrame(historical_data, index=scenario_index)

        result = harmonize_to_historical_with_convergence(
            scenario_ts=scenario_ts,
            historical_ts=historical_ts,
            anchor_year=2020,
            convergence_year=2022,
        )

        # At anchor year 2020: should match historical = 90
        assert result.loc[("USA", "Mt * CO2e"), 2020] == 90.0

        # At convergence year 2022: should match original scenario = 110
        assert result.loc[("USA", "Mt * CO2e"), 2022] == 110.0

        # 2021 is in transition (between 2020 and 2022)
        # Linear interpolation formula: hist + (1 - weight) * (scen - hist)
        # where weight = (conv_year - current_year) / (conv_year - anchor_year)
        # For 2021: weight = (2022 - 2021) / (2022 - 2020) = 1/2 = 0.5
        # Result = 90 + (1 - 0.5) * (105 - 90) = 90 + 0.5 * 15 = 97.5
        expected_2021 = 90.0 + 0.5 * (105.0 - 90.0)
        assert np.isclose(
            result.loc[("USA", "Mt * CO2e"), 2021], expected_2021, rtol=1e-6
        )
