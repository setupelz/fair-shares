"""
Tests for NGHGI year validation in CO2 allocations.

Validates that allocation_year, first_allocation_year, and
historical_responsibility_year are all >= 2000 when emission_category='co2'.
"""

from __future__ import annotations

import pytest

from fair_shares.library.exceptions import AllocationError
from fair_shares.library.validation.config import validate_allocation_year_for_co2


class TestValidateAllocationYearForCo2:
    """Test NGHGI minimum year enforcement for co2 emission category."""

    # --- allocation_year (budget approaches) ---

    def test_budget_allocation_year_below_2000_raises(self):
        """allocation_year < 2000 with co2 should raise AllocationError."""
        config = {
            "equal-per-capita-budget": [{"allocation_year": 1850}],
        }
        with pytest.raises(
            AllocationError, match="allocation_year = 1850 is before 2000"
        ):
            validate_allocation_year_for_co2(config, "co2")

    def test_budget_allocation_year_at_2000_passes(self):
        """allocation_year = 2000 with co2 should pass."""
        config = {
            "equal-per-capita-budget": [{"allocation_year": 2000}],
        }
        validate_allocation_year_for_co2(config, "co2")

    def test_budget_allocation_year_above_1990_passes(self):
        """allocation_year > 2000 with co2 should pass."""
        config = {
            "equal-per-capita-budget": [{"allocation_year": 2020}],
        }
        validate_allocation_year_for_co2(config, "co2")

    # --- first_allocation_year (pathway approaches) ---

    def test_pathway_first_allocation_year_below_2000_raises(self):
        """first_allocation_year < 2000 with co2 should raise AllocationError."""
        config = {
            "equal-per-capita": [{"first_allocation_year": 1980}],
        }
        with pytest.raises(
            AllocationError, match="first_allocation_year = 1980 is before 2000"
        ):
            validate_allocation_year_for_co2(config, "co2")

    def test_pathway_first_allocation_year_at_2000_passes(self):
        """first_allocation_year = 2000 with co2 should pass."""
        config = {
            "equal-per-capita": [{"first_allocation_year": 2000}],
        }
        validate_allocation_year_for_co2(config, "co2")

    # --- historical_responsibility_year ---

    def test_historical_responsibility_year_below_2000_raises(self):
        """historical_responsibility_year < 2000 with co2 should raise AllocationError."""
        config = {
            "per-capita-adjusted": [
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 1850,
                }
            ],
        }
        with pytest.raises(
            AllocationError,
            match="historical_responsibility_year = 1850 is before 2000",
        ):
            validate_allocation_year_for_co2(config, "co2")

    def test_historical_responsibility_year_at_2000_passes(self):
        """historical_responsibility_year = 2000 with co2 should pass."""
        config = {
            "per-capita-adjusted": [
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 2000,
                }
            ],
        }
        validate_allocation_year_for_co2(config, "co2")

    def test_historical_responsibility_year_above_1990_passes(self):
        """historical_responsibility_year > 2000 with co2 should pass."""
        config = {
            "per-capita-adjusted": [
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 2000,
                }
            ],
        }
        validate_allocation_year_for_co2(config, "co2")

    def test_historical_responsibility_year_absent_passes(self):
        """Missing historical_responsibility_year should pass (default is 2000)."""
        config = {
            "per-capita-adjusted": [{"first_allocation_year": 2020}],
        }
        validate_allocation_year_for_co2(config, "co2")

    # --- kebab-case parameter names ---

    def test_historical_responsibility_year_kebab_case_below_2000_raises(self):
        """Kebab-case historical-responsibility-year < 2000 with co2 should raise."""
        config = {
            "per-capita-adjusted": [
                {
                    "first-allocation-year": 2020,
                    "historical-responsibility-year": 1850,
                }
            ],
        }
        with pytest.raises(
            AllocationError,
            match="historical_responsibility_year = 1850 is before 2000",
        ):
            validate_allocation_year_for_co2(config, "co2")

    def test_historical_responsibility_year_kebab_case_at_2000_passes(self):
        """Kebab-case historical-responsibility-year = 2000 with co2 should pass."""
        config = {
            "per-capita-adjusted": [
                {
                    "first-allocation-year": 2020,
                    "historical-responsibility-year": 2000,
                }
            ],
        }
        validate_allocation_year_for_co2(config, "co2")

    # --- co2-ffi (no NGHGI constraint) ---

    def test_co2_ffi_allows_historical_responsibility_year_before_1990(self):
        """co2-ffi has no NGHGI constraint — early years should pass."""
        config = {
            "per-capita-adjusted": [
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 1850,
                }
            ],
        }
        validate_allocation_year_for_co2(config, "co2-ffi")

    def test_co2_ffi_allows_allocation_year_before_1990(self):
        """co2-ffi has no NGHGI constraint — early allocation_year should pass."""
        config = {
            "equal-per-capita-budget": [{"allocation_year": 1850}],
        }
        validate_allocation_year_for_co2(config, "co2-ffi")

    # --- all-ghg-ex-co2-lulucf (no NGHGI constraint) ---

    def test_all_ghg_ex_co2_lulucf_allows_early_years(self):
        """all-ghg-ex-co2-lulucf has no NGHGI constraint."""
        config = {
            "per-capita-adjusted": [
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 1850,
                }
            ],
        }
        validate_allocation_year_for_co2(config, "all-ghg-ex-co2-lulucf")

    # --- budget approaches with historical_responsibility_year ---

    def test_budget_historical_responsibility_year_below_2000_raises(self):
        """Budget approach with historical_responsibility_year < 2000 and co2 should raise."""
        config = {
            "per-capita-adjusted-budget": [
                {
                    "allocation_year": 2020,
                    "historical_responsibility_year": 1850,
                }
            ],
        }
        with pytest.raises(
            AllocationError,
            match="historical_responsibility_year = 1850 is before 2000",
        ):
            validate_allocation_year_for_co2(config, "co2")

    # --- multiple param sets ---

    def test_second_param_set_with_early_historical_year_raises(self):
        """Second param set with historical_responsibility_year < 2000 should raise."""
        config = {
            "per-capita-adjusted": [
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 2000,
                },
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 1850,
                },
            ],
        }
        with pytest.raises(
            AllocationError,
            match="historical_responsibility_year = 1850 is before 2000",
        ):
            validate_allocation_year_for_co2(config, "co2")

    # --- error message content ---

    def test_error_message_mentions_nghgi(self):
        """Error message should explain the NGHGI rationale."""
        config = {
            "per-capita-adjusted": [
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 1850,
                }
            ],
        }
        with pytest.raises(AllocationError, match="NGHGI-consistent"):
            validate_allocation_year_for_co2(config, "co2")

    def test_error_message_suggests_co2_ffi_alternative(self):
        """Error message should suggest co2-ffi as an alternative."""
        config = {
            "per-capita-adjusted": [
                {
                    "first_allocation_year": 2020,
                    "historical_responsibility_year": 1850,
                }
            ],
        }
        with pytest.raises(AllocationError, match="co2-ffi"):
            validate_allocation_year_for_co2(config, "co2")
