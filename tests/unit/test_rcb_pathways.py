"""
Tests for RCB pathway generation functions.

"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import (
    calculate_exponential_decay_pathway,
    generate_rcb_pathway_scenarios,
)


class TestCalculateExponentialDecayPathway:
    """Tests for calculate_exponential_decay_pathway function."""

    def test_conservation_basic(self):
        """Test that pathway sums to total budget."""
        # With shifted exponential (ending at 0), max sum is ~start_value * n_years / 2
        # For 31 years and start_value=50: max ~= 775
        total_budget = 700.0  # Achievable budget
        start_value = 50.0
        start_year = 2020
        end_year = 2050

        pathway = calculate_exponential_decay_pathway(
            total_budget=total_budget,
            start_value=start_value,
            start_year=start_year,
            end_year=end_year,
        )

        # Check conservation within tolerance
        relative_error = abs(pathway.sum() - total_budget) / total_budget
        assert relative_error < 1e-6, (
            f"Pathway sum {pathway.sum():.2f} differs from budget {total_budget:.2f} "
            f"by {relative_error:.2e}"
        )

    def test_conservation_various_budgets(self):
        """Test conservation with various budget sizes."""
        start_value = 36000.0  # Realistic world emissions (Mt CO2)
        start_year = 2020
        end_year = 2100

        # Test with different budget sizes
        budgets = [100000, 300000, 500000, 1000000]

        for budget in budgets:
            pathway = calculate_exponential_decay_pathway(
                total_budget=budget,
                start_value=start_value,
                start_year=start_year,
                end_year=end_year,
            )

            relative_error = abs(pathway.sum() - budget) / budget
            assert (
                relative_error < 1e-6
            ), f"Budget {budget}: sum {pathway.sum():.2f}, error {relative_error:.2e}"

    def test_start_value_preserved(self):
        """Test that first year emission matches start_value."""
        start_value = 36000.0
        start_year = 2020
        end_year = 2100
        total_budget = 500000.0

        pathway = calculate_exponential_decay_pathway(
            total_budget=total_budget,
            start_value=start_value,
            start_year=start_year,
            end_year=end_year,
        )

        first_year = str(start_year)
        assert abs(pathway[first_year] - start_value) < 1e-6, (
            f"First year value {pathway[first_year]:.2f} differs from "
            f"start_value {start_value:.2f}"
        )

    def test_monotonically_decreasing(self):
        """Test that pathway is strictly decreasing."""
        pathway = calculate_exponential_decay_pathway(
            total_budget=500000.0,
            start_value=36000.0,
            start_year=2020,
            end_year=2100,
        )

        values = pathway.values
        for i in range(len(values) - 1):
            assert values[i] > values[i + 1], (
                f"Pathway not decreasing at year {2020 + i}: "
                f"{values[i]:.2f} -> {values[i + 1]:.2f}"
            )

    def test_all_positive(self):
        """Test that all pathway values are non-negative (final year is zero)."""
        pathway = calculate_exponential_decay_pathway(
            total_budget=500000.0,
            start_value=36000.0,
            start_year=2020,
            end_year=2100,
        )

        # All values should be >= 0 (final year is exactly zero)
        assert (pathway >= 0).all(), "Pathway contains negative values"
        # All values except the last should be positive
        assert (
            pathway[:-1] > 0
        ).all(), "Pathway contains non-positive values before final year"
        # Final year should be zero
        assert abs(pathway.iloc[-1]) < 1e-10, f"Final year not zero: {pathway.iloc[-1]}"

    def test_final_year_is_zero(self):
        """Test that final year emissions are exactly zero."""
        pathway = calculate_exponential_decay_pathway(
            total_budget=500000.0,
            start_value=36000.0,
            start_year=2020,
            end_year=2100,
        )

        assert (
            abs(pathway.iloc[-1]) < 1e-10
        ), f"Final year emissions should be zero, got {pathway.iloc[-1]:.2e}"
        assert pathway.index[-1] == "2100", "Final year index incorrect"

    def test_year_index_as_strings(self):
        """Test that year index values are strings (codebase convention)."""
        # Use budget that can be achieved with given start_value
        # 11 years with start_value=50 can sum to ~200-500 depending on decay
        pathway = calculate_exponential_decay_pathway(
            total_budget=200.0,
            start_value=50.0,
            start_year=2020,
            end_year=2030,
        )

        assert all(
            isinstance(idx, str) for idx in pathway.index
        ), "Year indices should be strings"
        assert pathway.index[0] == "2020"
        assert pathway.index[-1] == "2030"

    def test_correct_number_of_years(self):
        """Test that pathway has correct number of years."""
        start_year = 2020
        end_year = 2050

        pathway = calculate_exponential_decay_pathway(
            total_budget=500.0,
            start_value=50.0,
            start_year=start_year,
            end_year=end_year,
        )

        expected_years = end_year - start_year + 1
        assert (
            len(pathway) == expected_years
        ), f"Expected {expected_years} years, got {len(pathway)}"

    def test_invalid_negative_budget(self):
        """Test that negative budget raises AllocationError."""
        with pytest.raises(AllocationError, match="total_budget must be positive"):
            calculate_exponential_decay_pathway(
                total_budget=-100.0,
                start_value=50.0,
                start_year=2020,
                end_year=2050,
            )

    def test_invalid_zero_budget(self):
        """Test that zero budget raises AllocationError."""
        with pytest.raises(AllocationError, match="total_budget must be positive"):
            calculate_exponential_decay_pathway(
                total_budget=0.0,
                start_value=50.0,
                start_year=2020,
                end_year=2050,
            )

    def test_invalid_negative_start_value(self):
        """Test that negative start_value raises AllocationError."""
        with pytest.raises(AllocationError, match="start_value must be positive"):
            calculate_exponential_decay_pathway(
                total_budget=1000.0,
                start_value=-50.0,
                start_year=2020,
                end_year=2050,
            )

    def test_invalid_year_order(self):
        """Test that end_year <= start_year raises AllocationError."""
        with pytest.raises(AllocationError, match="end_year.*must be greater"):
            calculate_exponential_decay_pathway(
                total_budget=1000.0,
                start_value=50.0,
                start_year=2050,
                end_year=2020,
            )

        with pytest.raises(AllocationError, match="end_year.*must be greater"):
            calculate_exponential_decay_pathway(
                total_budget=1000.0,
                start_value=50.0,
                start_year=2020,
                end_year=2020,
            )

    def test_budget_too_large_for_start_value(self):
        """Test error when budget cannot be achieved with given start_value."""
        # With start_value=10 and 31 years, max possible sum is 310
        # Budget of 1000 is impossible
        with pytest.raises(AllocationError, match="Cannot satisfy budget constraint"):
            calculate_exponential_decay_pathway(
                total_budget=1000.0,
                start_value=10.0,
                start_year=2020,
                end_year=2050,
            )

    def test_budget_smaller_than_start_value(self):
        """Test error when budget is smaller than first year emissions."""
        with pytest.raises(AllocationError, match="first year alone exceeds"):
            calculate_exponential_decay_pathway(
                total_budget=10.0,
                start_value=50.0,
                start_year=2020,
                end_year=2050,
            )

    def test_realistic_rcb_scenario(self):
        """Test with realistic RCB values (1.5C, 50% scenario)."""
        # Realistic values: ~306,640 Mt CO2 budget (1.5p50 from 2020)
        # World emissions ~36,000 Mt CO2/year in 2020
        total_budget = 306640.0
        start_value = 36000.0
        start_year = 2020
        end_year = 2100

        pathway = calculate_exponential_decay_pathway(
            total_budget=total_budget,
            start_value=start_value,
            start_year=start_year,
            end_year=end_year,
        )

        # Verify conservation
        relative_error = abs(pathway.sum() - total_budget) / total_budget
        assert relative_error < 1e-6

        # First year should match start value
        assert abs(pathway["2020"] - start_value) < 1e-6

        # Should be all non-negative (final year is zero) and decreasing
        assert (pathway >= 0).all()
        # Final year should be zero
        assert abs(pathway.iloc[-1]) < 1e-10
        # All years before final should be positive
        assert (pathway[:-1] > 0).all()
        # Values should be monotonically decreasing
        values = pathway.values
        assert all(values[i] > values[i + 1] for i in range(len(values) - 1))


class TestGenerateRCBPathwayScenarios:
    """Tests for generate_rcb_pathway_scenarios function."""

    @pytest.fixture
    def sample_rcbs_df(self) -> pd.DataFrame:
        """Create sample RCBs DataFrame.

        Note: With shifted exponential (ending at 0), the maximum achievable budget
        for start_emissions=36500 and 31 years is approximately 36500*31/2 = 565,750 Mt.
        So RCB values must be < 565,750 to be achievable.
        """
        return pd.DataFrame(
            {
                "source": ["lamboll_2023", "lamboll_2023", "ar6_2020", "ar6_2020"],
                "climate-assessment": ["1.5C", "2C", "1.5C", "2C"],
                "quantile": ["0.5", "0.5", "0.5", "0.5"],
                "emission-category": ["co2-ffi"] * 4,
                "rcb_2020_mt": [306640, 500000, 350000, 450000],  # Achievable budgets
            }
        )

    @pytest.fixture
    def sample_world_emissions(self) -> pd.DataFrame:
        """Create sample world emissions DataFrame."""
        years = [str(y) for y in range(2015, 2025)]
        emissions = [34000 + i * 500 for i in range(len(years))]

        data = {year: [emiss] for year, emiss in zip(years, emissions)}

        index = pd.MultiIndex.from_tuples(
            [("World", "Mt * CO2e", "co2-ffi")],
            names=["iso3c", "unit", "emission-category"],
        )

        return pd.DataFrame(data, index=index)

    def test_generates_correct_scenarios(self, sample_rcbs_df, sample_world_emissions):
        """Test that correct number of scenarios are generated."""
        result = generate_rcb_pathway_scenarios(
            rcbs_df=sample_rcbs_df,
            world_emissions_df=sample_world_emissions,
            start_year=2020,
            end_year=2050,
            emission_category="co2-ffi",
        )

        # Should have one pathway per RCB (4 rows in sample_rcbs_df)
        # Each source gets its own pathway
        assert len(result) == 4

    def test_output_index_structure(self, sample_rcbs_df, sample_world_emissions):
        """Test that output has correct MultiIndex structure."""
        result = generate_rcb_pathway_scenarios(
            rcbs_df=sample_rcbs_df,
            world_emissions_df=sample_world_emissions,
            start_year=2020,
            end_year=2050,
            emission_category="co2-ffi",
        )

        expected_names = [
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ]
        assert list(result.index.names) == expected_names

    def test_output_columns_are_years(self, sample_rcbs_df, sample_world_emissions):
        """Test that columns are year strings."""
        result = generate_rcb_pathway_scenarios(
            rcbs_df=sample_rcbs_df,
            world_emissions_df=sample_world_emissions,
            start_year=2020,
            end_year=2050,
            emission_category="co2-ffi",
        )

        assert result.columns[0] == "2020"
        assert result.columns[-1] == "2050"
        assert len(result.columns) == 31  # 2020 to 2050 inclusive

    def test_iso3c_is_world(self, sample_rcbs_df, sample_world_emissions):
        """Test that all rows have iso3c='World'."""
        result = generate_rcb_pathway_scenarios(
            rcbs_df=sample_rcbs_df,
            world_emissions_df=sample_world_emissions,
            start_year=2020,
            end_year=2050,
            emission_category="co2-ffi",
        )

        iso3c_values = result.index.get_level_values("iso3c").unique()
        assert list(iso3c_values) == ["World"]

    def test_conservation_for_each_scenario(
        self, sample_rcbs_df, sample_world_emissions
    ):
        """Test that each scenario conserves its budget."""
        result = generate_rcb_pathway_scenarios(
            rcbs_df=sample_rcbs_df,
            world_emissions_df=sample_world_emissions,
            start_year=2020,
            end_year=2050,
            emission_category="co2-ffi",
        )

        # Get expected budgets (one per row, including source)
        expected_budgets = sample_rcbs_df.set_index(
            ["climate-assessment", "quantile", "source"]
        )["rcb_2020_mt"]

        for idx in result.index:
            climate_assessment = idx[0]
            quantile = idx[1]
            source = idx[2]
            expected_budget = expected_budgets.loc[
                (climate_assessment, quantile, source)
            ]

            pathway_sum = result.loc[idx].sum()
            relative_error = abs(pathway_sum - expected_budget) / expected_budget

            assert relative_error < 1e-6, (
                f"Scenario {climate_assessment}/{quantile}/{source}: "
                f"sum {pathway_sum:.2f} vs expected {expected_budget:.2f}"
            )

    def test_missing_emission_category_raises(
        self, sample_rcbs_df, sample_world_emissions
    ):
        """Test error when emission category not in RCBs."""
        with pytest.raises(AllocationError, match="No RCBs found"):
            generate_rcb_pathway_scenarios(
                rcbs_df=sample_rcbs_df,
                world_emissions_df=sample_world_emissions,
                start_year=2020,
                end_year=2050,
                emission_category="all-ghg",
            )

    def test_missing_start_year_raises(self, sample_rcbs_df, sample_world_emissions):
        """Test error when start year not in world emissions."""
        with pytest.raises(AllocationError, match="Start year 2000 not found"):
            generate_rcb_pathway_scenarios(
                rcbs_df=sample_rcbs_df,
                world_emissions_df=sample_world_emissions,
                start_year=2000,
                end_year=2050,
                emission_category="co2-ffi",
            )
