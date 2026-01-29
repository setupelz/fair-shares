"""
Integration tests for AllocationManager for the fair-shares library.

"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from conftest import STANDARD_EMISSION_CATEGORY

from fair_shares.library.allocations.manager import AllocationManager


class TestAllocationManagerIntegration:
    """Additional integration tests for AllocationManager (grid, IO, absolute calcs)."""

    def test_run_parameter_grid_basic(
        self, allocation_manager: AllocationManager, test_data
    ):
        """Ensure grid expansion runs and shares sum to 1 for each year."""
        allocations_cfg = {
            "equal-per-capita": [
                {
                    "first-allocation-year": [2020],
                }
            ],
            "per-capita-adjusted": [
                {
                    "first-allocation-year": [2020],
                    "exponent": [1.0, 2.0],
                }
            ],
        }

        results = allocation_manager.run_parameter_grid(
            allocations_config=allocations_cfg,
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Expect 1 + 2 parameter combinations
        assert len(results) == 3

        for res in results:
            shares_df = (
                res.relative_shares_pathway_emissions
                if hasattr(res, "relative_shares_pathway_emissions")
                else res.relative_shares_cumulative_emission
            )
            # Sum of shares across iso3c should be 1.0 for every year
            totals = shares_df.sum(axis=0)
            # Allow small floating error
            assert all(abs(t - 1.0) < 1e-6 for t in totals), "Shares must sum to 1"

    def test_save_allocation_result_appends(
        self, allocation_manager: AllocationManager, test_data, tmp_path: Path
    ):
        """First write creates file, second write appends rows (row count doubles)."""
        # Run a single allocation to get a PathwayAllocationResult
        result = allocation_manager.run_allocation(
            approach="equal-per-capita",
            population_ts=test_data["population"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # First save
        paths1 = allocation_manager.save_allocation_result(
            result=result, output_dir=tmp_path
        )
        relative_file = paths1["relative"]
        rows_after_first = pd.read_parquet(relative_file).shape[0]
        assert rows_after_first > 0

        # Second save - should append
        allocation_manager.save_allocation_result(result=result, output_dir=tmp_path)
        rows_after_second = pd.read_parquet(relative_file).shape[0]
        assert rows_after_second == 2 * rows_after_first

    def test_calculate_absolute_emissions_matches_world_total(
        self, allocation_manager: AllocationManager, test_data
    ):
        """Absolute emissions should add up to the World total for each year."""
        result = allocation_manager.run_allocation(
            approach="equal-per-capita",
            population_ts=test_data["population"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        absolute_df = allocation_manager.calculate_absolute_emissions(
            result, test_data["emissions"]
        )

        # Get world totals from the emissions data (index level iso3c == 'World')
        world_totals = test_data["emissions"].xs("World", level="iso3c").sum(axis=0)

        # Sum absolute emissions across countries for each year
        abs_totals = absolute_df.sum(axis=0)

        # Compare each year within small tolerance
        # Only compare years that exist in both datasets
        common_years = abs_totals.index.intersection(world_totals.index)
        for year in common_years:
            assert pytest.approx(abs_totals[year], abs=1e-6) == world_totals[year]
