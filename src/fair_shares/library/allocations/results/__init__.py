"""
Result containers for allocation calculations.

This module provides structured containers for the outputs of fair share
allocation calculations. Allocation results represent the operationalization
of equity principles into quantitative country-level shares of a global
carbon budget or emissions pathway.

The literature emphasizes that fair share analysis requires transparency
at multiple decision points: foundational principles, allocation quantity,
allocation approach, indicators, and implications for all parties.
These result containers support this transparency by:

1. **Preserving allocation metadata**: The approach name and parameters used
   to generate the allocation are stored alongside the numerical results,
   enabling reproducibility and clear documentation of normative choices.

2. **Maintaining relative shares**: Results are stored as relative shares
   (fractions of the global total) rather than absolute quantities, separating
   the equity allocation logic from the specific carbon budget being allocated.
   This allows the same allocation to be applied to different budget estimates.

3. **Enabling absolute budget/emissions calculation**: Methods are provided
   to multiply relative shares by a global budget to obtain country-level
   absolute allocations, supporting the full workflow from equity principles
   to actionable national targets.

The distinction between budget allocations (cumulative totals over a period)
and pathway allocations (year-by-year trajectories) reflects different ways
of specifying what is being allocated, each with distinct policy implications.
"""

from __future__ import annotations

from attrs import define, field
from pandas_openscm.index_manipulation import set_index_levels_func

from fair_shares.library.utils import (
    TimeseriesDataFrame,
    get_year_columns,
)
from fair_shares.library.validation import (
    validate_emission_category_match,
    validate_exactly_one_year_column,
    validate_index_structure,
    validate_world_data_present,
    validate_years_match,
)


@define
class BaseAllocationResult:
    """Base class for allocation results with common attributes.

    All allocation results contain data for exactly one emission category.

    Attributes
    ----------
    approach
        The name of the allocation approach used (e.g., "per-capita",
        "per-capita-convergence"). This documents which equity principle
        operationalization generated these results.
    parameters
        The parameter values used in the allocation calculation. The literature
        emphasizes that allocation parameters involve normative choices that
        should be documented transparently to distinguish principled assessment
        from approaches that work backward from favorable allocations.
    country_warnings
        Optional dictionary mapping country codes to warning messages about
        data quality or methodological issues affecting those countries'
        allocations. Transparency about data limitations is essential for
        credible fair share analysis.
    """

    approach: str
    parameters: dict
    country_warnings: dict[str, str] | None = field(default=None, kw_only=True)


@define
class BudgetAllocationResult(BaseAllocationResult):
    """Container for budget allocation results with validation.

    Budget allocations distribute a cumulative carbon budget among countries
    for a single allocation year and emission category. The result contains
    relative shares (fractions summing to 1.0) that represent each country's
    fair share of the global budget according to the specified equity approach.

    Cumulative budget allocations are appropriate when the policy question is
    "how much total emissions can each country emit from now until a target
    year?" This framing aligns with the scientific understanding that cumulative
    CO2 emissions determine long-term warming outcomes, as captured by the
    Transient Climate Response to Cumulative Emissions (TCRE) relationship
    (TCRE).

    The TimeseriesDataFrame structure with exactly one year column makes the
    allocation year explicit, preventing confusion when these relative shares
    are later multiplied by absolute budget estimates that may have different
    reference years.

    Attributes
    ----------
    relative_shares_cumulative_emission
        DataFrame containing each country's share of the global cumulative
        budget. Values are fractions (0.0 to 1.0) that sum to 1.0 across all
        countries. Indexed by ['iso3c', 'unit', 'emission-category'] with
        exactly one year column representing the allocation year.
    """

    relative_shares_cumulative_emission: TimeseriesDataFrame

    def __attrs_post_init__(self):
        """Initialize and validate the result."""
        self.validate()

    def validate(self) -> None:
        """Validate TimeseriesDataFrame structure and year column requirements.

        Ensures the result data meets the structural requirements for budget
        allocations: proper MultiIndex structure and exactly one year column.
        """
        # Validate TimeseriesDataFrame structure and MultiIndex
        validate_index_structure(
            self.relative_shares_cumulative_emission,
            "Cumulative emission shares",
            expected_index_names=["iso3c", "unit", "emission-category"],
        )

        # Validate that there is one year column (budget allocations are single-year)
        validate_exactly_one_year_column(
            self.relative_shares_cumulative_emission, "cumulative emission shares"
        )

    def get_absolute_budgets(
        self, remaining_budget: TimeseriesDataFrame
    ) -> TimeseriesDataFrame:
        """
        Calculate absolute budgets from relative shares and remaining budget.

        This method translates equity-based relative shares into absolute
        emissions budgets by multiplying each country's share by the global
        remaining carbon budget. The result represents each country's fair
        share of cumulative emissions from the allocation year onward.

        Note that resulting budgets may be negative for countries whose
        historical emissions have already exceeded their fair share under
        the chosen allocation approach. The literature suggests such cases
        should be addressed through transparent communication of overshoot,
        pursuit of highest domestic ambition, and international cooperation
        through transparent communication and international cooperation.

        Parameters
        ----------
        remaining_budget
            The total remaining cumulative emissions budget to distribute.
            Must contain a 'World' row with the global budget value.
            TimeseriesDataFrame must be MultiIndex
            ['iso3c', 'unit', 'emission-category'] and exactly one year
            column that matches the year in relative_shares_cumulative_emission.

        Returns
        -------
        TimeseriesDataFrame
            Absolute budgets for each country/group for the single emission
            category. Units match the input remaining_budget units.
        """
        # Validate that budget has exactly one year column and years match
        validate_exactly_one_year_column(remaining_budget, "remaining budget")
        validate_years_match(
            remaining_budget,
            self.relative_shares_cumulative_emission,
            "remaining budget",
            "cumulative emission shares",
        )

        # Extract world totals for each emission category
        validate_world_data_present(remaining_budget, "remaining budget")
        world_mask = remaining_budget.index.get_level_values("iso3c") == "World"
        world_budget = remaining_budget[world_mask]

        # Validate that relative shares and world budget have matching emission category
        validate_emission_category_match(
            self.relative_shares_cumulative_emission,
            world_budget,
            "cumulative emission shares",
            "world budget",
        )

        # Calculate absolute budgets by multiplying relative shares with world budget
        # Use the original column label type to avoid mismatches (e.g., str vs int)
        budget_year = get_year_columns(world_budget, return_type="original")[0]
        world_budget_value = world_budget.iloc[0][budget_year]  # Get the budget scalar
        result = self.relative_shares_cumulative_emission * world_budget_value

        # Update the units to match the input budget units
        budget_unit = world_budget.index.get_level_values("unit").unique()[0]
        result = set_index_levels_func(result, {"unit": budget_unit}, copy=False)

        return result


@define
class PathwayAllocationResult(BaseAllocationResult):
    """Container for pathway allocation results with validation.

    Pathway allocations distribute annual emissions among countries across
    multiple years, defining a trajectory of fair shares over time. Unlike
    budget allocations which specify cumulative totals, pathway allocations
    answer "how much can each country emit in each year?"

    This framing is useful for policy contexts where annual targets are more
    actionable than cumulative budgets, or where the allocation approach
    involves temporal dynamics such as convergence toward equal per capita
    emissions by a target year. The "contraction and convergence" framework,
    for example, specifies that global emissions contract to meet climate
    targets while per capita emissions converge to equality by a target
    date. See docs/science/allocations.md for theoretical foundations.

    Pathway allocations may also incorporate capability and responsibility
    adjustments that vary over time as economic circumstances and historical
    emission stocks change.

    Attributes
    ----------
    relative_shares_pathway_emissions
        DataFrame containing each country's share of global annual emissions
        for each year. Values are fractions (0.0 to 1.0) that sum to 1.0 across
        all countries for each year column. Indexed by ['iso3c', 'unit',
        'emission-category'] with year columns representing the allocation years.
    """

    relative_shares_pathway_emissions: TimeseriesDataFrame

    def __attrs_post_init__(self):
        """Initialize and validate the result."""
        self.validate()

    def validate(self) -> None:
        """Validate TimeseriesDataFrame structure and index requirements.

        Ensures the result data meets the structural requirements for pathway
        allocations: proper MultiIndex structure with country, unit, and
        emission category levels.
        """
        # Validate TimeseriesDataFrame structure and MultiIndex
        validate_index_structure(
            self.relative_shares_pathway_emissions,
            "Pathway emission shares",
            expected_index_names=["iso3c", "unit", "emission-category"],
        )

    def get_absolute_emissions(
        self, annual_emissions_budget: TimeseriesDataFrame
    ) -> TimeseriesDataFrame:
        """
        Calculate absolute emissions from relative shares and annual budgets.

        This method translates equity-based relative shares into absolute
        annual emissions by multiplying each country's share by the global
        annual emissions budget for each year. The result represents each
        country's fair share emissions pathway.

        When combined with scenario-based global pathways (such as those from
        IPCC AR6), this enables translation of equity principles into concrete
        national trajectories consistent with specific temperature targets.

        Parameters
        ----------
        annual_emissions_budget
            The total annual emissions budget to distribute for each year.
            Must contain a 'World' row with the global budget values.
            TimeseriesDataFrame must be MultiIndex
            ['iso3c', 'unit', 'emission-category'] and have years as columns
            matching those in relative_shares_pathway_emissions.

        Returns
        -------
        TimeseriesDataFrame
            Absolute emissions for each country/group for the single emission
            category across all years. Units match the input budget units.
        """
        # Extract world totals for each emission category
        validate_world_data_present(annual_emissions_budget, "annual emissions budget")
        world_mask = annual_emissions_budget.index.get_level_values("iso3c") == "World"
        world_budget = annual_emissions_budget[world_mask]

        # Validate that relative shares and world budget have matching emission category
        validate_emission_category_match(
            self.relative_shares_pathway_emissions,
            world_budget,
            "pathway emission shares",
            "world budget",
        )

        # Validate that world budget columns match pathway shares columns
        validate_years_match(
            world_budget,
            self.relative_shares_pathway_emissions,
            "world budget",
            "pathway emission shares",
        )

        # Calculate absolute emissions by multiplying relative shares with world budget
        # TimeseriesDataFrames matching ['iso3c', 'unit', 'emission-category'] indices
        # Filter world budget to only include years that exist in the allocation result
        allocation_years = self.relative_shares_pathway_emissions.columns
        world_budget_filtered = world_budget.iloc[0][allocation_years]
        result = self.relative_shares_pathway_emissions.mul(
            world_budget_filtered, axis="columns"
        )

        # Update the units to match the input world budget units
        budget_unit = world_budget.index.get_level_values("unit").unique()[0]
        result = set_index_levels_func(result, {"unit": budget_unit}, copy=False)

        return result
