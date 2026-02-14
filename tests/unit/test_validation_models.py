"""Tests for Pydantic validation models (AllocationInputs, AllocationOutputs)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from fair_shares.library.exceptions import AllocationError, DataProcessingError
from fair_shares.library.validation.models import AllocationOutputs


class TestAllocationOutputs:
    """Tests for AllocationOutputs Pydantic model."""

    def test_valid_shares_pass_validation(self):
        """Test that valid shares (sum to 1.0) pass validation."""
        shares = pd.DataFrame(
            {
                "2020": [0.3, 0.5, 0.2],
                "2025": [0.4, 0.3, 0.3],
            },
            index=pd.Index(["USA", "CHN", "IND"], name="iso3c"),
        )

        # Should not raise
        outputs = AllocationOutputs(
            shares=shares,
            dataset_name="Test Shares",
        )
        assert outputs.shares.equals(shares)

    def test_shares_not_sum_to_one_fails(self):
        """Test that shares not summing to 1.0 fail validation."""
        shares = pd.DataFrame(
            {
                "2020": [0.3, 0.5, 0.3],  # Sums to 1.1
            },
            index=pd.Index(["USA", "CHN", "IND"], name="iso3c"),
        )

        with pytest.raises(AllocationError, match="shares for year 2020"):
            AllocationOutputs(
                shares=shares,
                dataset_name="Test Shares",
            )

    def test_shares_with_nulls_fail_without_reference(self):
        """Test that shares with NaN values fail validation without reference data."""
        shares = pd.DataFrame(
            {
                "2020": [0.5, 0.5, np.nan],
            },
            index=pd.Index(["USA", "CHN", "IND"], name="iso3c"),
        )

        with pytest.raises(DataProcessingError, match="Found 1 null values"):
            AllocationOutputs(
                shares=shares,
                dataset_name="Test Shares",
            )

    def test_shares_with_nulls_pass_with_reference(self):
        """Test that shares with NaN pass when reference data has matching NaN."""
        shares = pd.DataFrame(
            {
                "2020": [0.5, 0.5, 0.0],
                "2050": [np.nan, np.nan, np.nan],  # Post-net-zero
            },
            index=pd.Index(["USA", "CHN", "IND"], name="iso3c"),
        )

        reference = pd.DataFrame(
            {
                "2020": [100.0],
                "2050": [np.nan],  # World emissions are NaN post-net-zero
            },
            index=pd.Index(["WORLD"], name="iso3c"),
        )

        # Should not raise - NaN in 2050 is expected based on reference
        outputs = AllocationOutputs(
            shares=shares,
            dataset_name="Test Shares",
            first_year=2020,
            reference_data=reference,
        )
        assert outputs.shares.equals(shares)

    def test_tolerance_parameter(self):
        """Test that tolerance parameter controls floating point precision."""
        # Shares sum to 1.0001 - fails with default tolerance
        shares = pd.DataFrame(
            {
                "2020": [0.33334, 0.33333, 0.33334],  # Sums to 1.00001
            },
            index=pd.Index(["USA", "CHN", "IND"], name="iso3c"),
        )

        # Should fail with default tolerance (1e-6)
        with pytest.raises(AllocationError):
            AllocationOutputs(shares=shares, dataset_name="Test")

        # Should pass with larger tolerance
        outputs = AllocationOutputs(
            shares=shares,
            dataset_name="Test",
            tolerance=1e-4,
        )
        assert outputs.tolerance == 1e-4

    def test_tolerance_bounds_validation(self):
        """Test that tolerance must be within valid bounds."""
        shares = pd.DataFrame(
            {"2020": [1.0]},
            index=pd.Index(["USA"], name="iso3c"),
        )

        # Tolerance too large should fail
        with pytest.raises(ValidationError):
            AllocationOutputs(
                shares=shares,
                dataset_name="Test",
                tolerance=0.01,  # > 1e-3
            )

        # Negative tolerance should fail
        with pytest.raises(ValidationError):
            AllocationOutputs(
                shares=shares,
                dataset_name="Test",
                tolerance=-1e-6,
            )

    def test_dataset_name_in_error_messages(self):
        """Test that dataset_name appears in error messages for debugging."""
        shares = pd.DataFrame(
            {
                "2020": [0.3, 0.3, 0.3],  # Sums to 0.9
            },
            index=pd.Index(["USA", "CHN", "IND"], name="iso3c"),
        )

        with pytest.raises(
            AllocationError, match="My Custom Dataset Name shares for year 2020"
        ):
            AllocationOutputs(
                shares=shares,
                dataset_name="My Custom Dataset Name",
            )

    def test_nan_years_skipped_in_sum_validation(self):
        """Test that years with any NaN are skipped in sum validation."""
        shares = pd.DataFrame(
            {
                "2020": [0.5, 0.5, 0.0],  # Valid - sums to 1.0
                "2050": [np.nan, 0.5, 0.5],  # Has NaN - should be skipped
            },
            index=pd.Index(["USA", "CHN", "IND"], name="iso3c"),
        )

        reference = pd.DataFrame(
            {
                "2020": [100.0],
                "2050": [np.nan],  # World emissions are NaN
            },
            index=pd.Index(["WORLD"], name="iso3c"),
        )

        # Should not raise - year 2050 skipped due to NaN
        outputs = AllocationOutputs(
            shares=shares,
            dataset_name="Test Shares",
            first_year=2020,
            reference_data=reference,
        )
        assert outputs.shares.equals(shares)
