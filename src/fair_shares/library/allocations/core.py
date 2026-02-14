"""
Core allocation logic shared between budget and pathway allocations.

This module provides foundational functions used by both budget and pathway
allocation approaches: weight validation and population-based share calculation.

For theoretical foundations of equity principles, see:
    docs/science/allocations.md#equity-principles-framework
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import (
    get_default_unit_registry,
    groupby_except_robust,
    set_single_unit,
)
from fair_shares.library.utils.units import convert_unit_robust

if TYPE_CHECKING:
    import pint.facets

    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def validate_weight_constraints(
    responsibility_weight: float,
    capability_weight: float,
) -> None:
    """
    Validate that allocation weights satisfy mathematical constraints.

    Many allocation approaches in fair shares literature combine multiple
    principles--equal per capita, historical responsibility, and capability--
    using explicit weights. The Greenhouse Development Rights framework, for
    example, uses weighted combinations of responsibility and capability indices
    (e.g., Greenhouse Development Rights). This function ensures that
    user-specified weights are valid for such weighted allocation approaches.

    The weight constraints are:

    - Both weights must be non-negative (principles cannot be applied negatively)
    - Sum of weights cannot exceed 1.0 (the remaining weight is implicitly
      assigned to the equal per capita baseline)

    When both weights are zero, the allocation reduces to pure equal per capita.
    When weights sum to 1.0, no weight remains for the equal per capita baseline.

    The literature emphasizes that weighting between equity principles involves
    normative choices that should be documented transparently, as different
    weightings can substantially affect resulting allocations.

    Parameters
    ----------
    responsibility_weight
        Weight for historical responsibility adjustment (must be >= 0).
        Higher values give more weight to cumulative past emissions when
        adjusting allocations.
    capability_weight
        Weight for economic capability adjustment (must be >= 0).
        Higher values give more weight to ability to pay (typically GDP-based)
        when adjusting allocations.

    Raises
    ------
    AllocationError
        If weights are negative or sum exceeds 1.0.
    """
    if responsibility_weight < 0:
        raise AllocationError("responsibility_weight must be non-negative.")
    if capability_weight < 0:
        raise AllocationError("capability_weight must be non-negative.")
    if responsibility_weight + capability_weight > 1.0:
        raise AllocationError(
            format_error(
                "weights_exceed_limit",
                resp=responsibility_weight,
                cap=capability_weight,
                total=responsibility_weight + capability_weight,
            )
        )


def calculate_base_shares(
    population: TimeseriesDataFrame,
    year: int | None = None,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> pd.Series | pd.DataFrame:
    """
    Calculate population-based shares implementing equal per capita allocation.

    This function computes each group's share of world population, implementing
    the equal per capita principle that is foundational to fair shares
    allocation. The equal per capita principle holds that each person globally
    has equal entitlement to atmospheric space, meaning allocation shares should
    be proportional to population.

    For theoretical foundations, see:
        docs/science/allocations.md#1-equal-per-capita-principle

    Parameters
    ----------
    population
        Population timeseries data indexed by group (e.g., iso3c).
    year
        Specific year to calculate shares for. If None, calculates shares
        for all years in the population data. The year must correspond to
        a column label in the population data.
    group_level
        Index level name for grouping (default: "iso3c").
    unit_level
        Index level name for units (default: "unit").
    ur
        Unit registry for unit conversions (default: default registry).

    Returns
    -------
    pd.Series or pd.DataFrame
        Population shares that sum to 1.0 across groups.

        - If year is specified: returns Series with shares for that year
        - If year is None: returns DataFrame with shares for all years

    Notes
    -----
    The calculation:

    1. Converts population to millions for consistency
    2. Drops the unit level from the index
    3. Calculates group totals and world totals
    4. Returns shares = group_total / world_total

    Examples
    --------
    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data()
    >>> # Calculate shares for a specific year
    >>> shares_2020 = calculate_base_shares(  # doctest: +ELLIPSIS
    ...     population=data["population"], year=2020
    ... )
    Converting units...
    >>> bool(abs(shares_2020.sum() - 1.0) < 1e-10)  # Should sum to 1.0
    True
    >>> # Calculate shares for all years
    >>> all_shares = calculate_base_shares(  # doctest: +ELLIPSIS
    ...     population=data["population"]
    ... )
    Converting units...
    >>> # Each year should sum to 1.0
    >>> sums_to_one = all(
    ...     abs(all_shares[col].sum() - 1.0) < 1e-10 for col in all_shares.columns
    ... )
    >>> bool(sums_to_one)
    True
    """
    # Convert to single unit (millions)
    population_single_unit = set_single_unit(population, unit_level, ur=ur)
    population_single_unit = convert_unit_robust(
        population_single_unit, "million", unit_level=unit_level, ur=ur
    )

    # Drop unit level for calculations
    population_numeric = population_single_unit.droplevel(unit_level)

    # Filter to specific year if requested
    if year is not None:
        # Map integer year to actual column label
        year_to_label = {int(c): c for c in population_numeric.columns}
        if year not in year_to_label:
            available_years = sorted(year_to_label.keys())
            raise AllocationError(
                f"Year {year} not found in population data. "
                f"Available years: {available_years}"
            )
        population_numeric = population_numeric[[year_to_label[year]]]

    # Calculate world totals for each year
    world_totals = groupby_except_robust(population_numeric, group_level)

    # Calculate shares
    shares = population_numeric.divide(world_totals)

    # Return Series if single year, DataFrame if multiple years
    if year is not None:
        return shares.iloc[:, 0]  # Return as Series
    return shares
