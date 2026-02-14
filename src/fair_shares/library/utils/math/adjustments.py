"""
Shared adjustment calculations for allocation approaches.

This module contains reusable adjustment calculations that are common across
both budget and pathway allocation approaches:
- Responsibility adjustments (historical emissions-based)
- Capability adjustments (GDP-based)
- Gini adjustments (inequality corrections)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils.units import (
    convert_unit_robust,
    set_single_unit,
)

if TYPE_CHECKING:
    import pint.facets

    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def calculate_responsibility_adjustment_data(
    country_actual_emissions_ts: TimeseriesDataFrame,
    population_ts: TimeseriesDataFrame,
    historical_responsibility_year: int,
    allocation_year: int,
    responsibility_per_capita: bool,
    group_level: str,
    unit_level: str,
    ur: pint.facets.PlainRegistry,
) -> pd.Series:
    """
    Calculate historical responsibility data for allocation.

    Returns cumulative emissions (or per capita emissions) from
    historical_responsibility_year up to (but not including) allocation_year.

    Responsibility window: [historical_responsibility_year, allocation_year - 1].

    This function is used by both budget and pathway allocations.

    Parameters
    ----------
    country_actual_emissions_ts
        Historical emissions timeseries data
    population_ts
        Population timeseries data
    historical_responsibility_year
        Start year of responsibility window (inclusive)
    allocation_year
        End year of responsibility window (exclusive).
        For budgets: the allocation year itself.
        For pathways: the first allocation year.
    responsibility_per_capita
        If True, divide cumulative emissions by cumulative population
    group_level
        Index level name for country/region grouping
    unit_level
        Index level name for units
    ur
        Pint unit registry

    Returns
    -------
    pd.Series
        Historical responsibility metric by country/region.
        Units: emissions (or emissions per capita) depending on responsibility_per_capita.

    Raises
    ------
    AllocationError
        If no years found in responsibility window, no country data found,
        zero population encountered (when per capita), or responsibility sums to non-positive.

    See Also
    --------
    docs/science/allocations.md : Theoretical basis for historical responsibility

    """
    # Process emissions data
    history_single_unit = set_single_unit(
        country_actual_emissions_ts, unit_level, ur=ur
    )
    history_numeric = history_single_unit.droplevel(unit_level)

    # Filter to historical period [historical_responsibility_year, allocation_year - 1]
    numeric_cols = pd.to_numeric(history_numeric.columns, errors="coerce")
    responsibility_mask = (numeric_cols >= historical_responsibility_year) & (
        numeric_cols < allocation_year
    )
    responsibility_columns = history_numeric.columns[responsibility_mask].tolist()
    if not responsibility_columns:
        raise AllocationError(
            f"No years found between {historical_responsibility_year} "
            f"and {allocation_year - 1} for responsibility calculation."
        )

    history_numeric = history_numeric[responsibility_columns]

    # Filter out World rows if present
    history_group_values = history_numeric.index.get_level_values(group_level)
    history_countries = history_numeric[history_group_values != "World"]
    if history_countries.empty:
        raise AllocationError(
            "No country-level emissions rows found for responsibility window."
        )

    # Sum emissions across historical period
    cumulative_emissions = history_countries.sum(axis=1, min_count=1)
    responsibility_data = cumulative_emissions.groupby(level=group_level).sum()

    # If per capita, divide by cumulative population over the same period
    if responsibility_per_capita:
        pop_single_unit = set_single_unit(population_ts, unit_level, ur=ur)
        pop_single_unit = convert_unit_robust(
            pop_single_unit, "million", unit_level=unit_level, ur=ur
        )
        pop_numeric = pop_single_unit.droplevel(unit_level)

        pop_cols = pd.to_numeric(pop_numeric.columns, errors="coerce")
        pop_mask = (pop_cols >= historical_responsibility_year) & (
            pop_cols < allocation_year
        )
        pop_columns = pop_numeric.columns[pop_mask].tolist()
        if not pop_columns:
            raise AllocationError("No population data found for responsibility window.")

        pop_numeric = pop_numeric[pop_columns]
        cumulative_population = pop_numeric.sum(axis=1, min_count=1)
        population_totals = cumulative_population.groupby(level=group_level).sum()

        if (population_totals == 0).any():
            zero_groups = population_totals[population_totals == 0].index.tolist()
            raise AllocationError(
                f"Zero population found for groups {zero_groups} in responsibility window "
                f"({historical_responsibility_year}-{allocation_year}). Cannot calculate per-capita responsibility."
            )

        responsibility_data = responsibility_data / population_totals

    if responsibility_data.sum() <= 0:
        raise AllocationError("Responsibility metric sums to non-positive.")

    return responsibility_data


def calculate_responsibility_adjustment_data_convergence(
    country_actual_emissions_ts: TimeseriesDataFrame,
    population_ts: TimeseriesDataFrame,
    historical_responsibility_year: int,
    first_allocation_year: int,
    responsibility_per_capita: bool,
    group_level: str,
    unit_level: str,
    ur: pint.facets.PlainRegistry,
) -> pd.Series:
    """
    Calculate historical responsibility data for convergence pathway allocation.

    Returns cumulative emissions (or per capita emissions) from
    historical_responsibility_year up to and including first_allocation_year.

    Responsibility window: [historical_responsibility_year, first_allocation_year].

    This function is used by convergence pathway allocations where the first
    allocation year is included in the responsibility calculation.

    Parameters
    ----------
    country_actual_emissions_ts
        Historical emissions timeseries data
    population_ts
        Population timeseries data
    historical_responsibility_year
        Start year of responsibility window (inclusive)
    first_allocation_year
        End year of responsibility window (inclusive).
    responsibility_per_capita
        If True, divide cumulative emissions by cumulative population
    group_level
        Index level name for country/region grouping
    unit_level
        Index level name for units
    ur
        Pint unit registry

    Returns
    -------
    pd.Series
        Historical responsibility metric by country/region.
        Units: emissions (or emissions per capita) depending on responsibility_per_capita.

    Raises
    ------
    AllocationError
        If no years found in responsibility window, no country data found,
        zero population encountered (when per capita), or responsibility sums to non-positive.

    See Also
    --------
    calculate_responsibility_adjustment_data : For budget allocations (exclusive end)
    docs/science/allocations.md : Theoretical basis for historical responsibility

    """
    history_single_unit = set_single_unit(
        country_actual_emissions_ts, unit_level, ur=ur
    )
    history_numeric = history_single_unit.droplevel(unit_level)

    # Filter to historical period [historical_responsibility_year, first_allocation_year]
    # Note: inclusive on both ends (differs from budget allocation version)
    numeric_cols = pd.to_numeric(history_numeric.columns, errors="coerce")
    responsibility_mask = (numeric_cols >= historical_responsibility_year) & (
        numeric_cols <= first_allocation_year
    )
    responsibility_columns = history_numeric.columns[responsibility_mask].tolist()
    if not responsibility_columns:
        raise AllocationError(
            f"Insufficient historical data for responsibility.\n\n"
            f"WHAT HAPPENED:\n"
            f"  No years found between {historical_responsibility_year} and "
            f"{first_allocation_year}.\n"
            f"  Responsibility calculation requires historical emissions "
            f"data.\n\n"
            f"LIKELY CAUSE:\n"
            f"  The emissions dataset doesn't cover the historical period.\n\n"
            f"HOW TO FIX:\n"
            f"  1. Use a dataset with historical coverage (e.g., PRIMAP back "
            f"to 1850)\n"
            f"  2. Or adjust historical_responsibility_year to match available "
            f"data:\n"
            f"     >>> result = manager.run_allocation(\n"
            f"     ...     ...,\n"
            f"     ...     historical_responsibility_year=1990  "
            f"# Instead of 1850\n"
            f"     ... )"
        )

    history_numeric = history_numeric[responsibility_columns]
    history_group_values = history_numeric.index.get_level_values(group_level)
    history_countries = history_numeric[history_group_values != "World"]
    if history_countries.empty:
        raise AllocationError(
            "No country data for responsibility calculation.\n\n"
            "WHAT HAPPENED:\n"
            "  No country-level emissions found in the historical period.\n"
            "  All rows appear to be 'World' totals.\n\n"
            "LIKELY CAUSE:\n"
            "  The emissions data only contains global aggregates for the "
            "historical period.\n\n"
            "HOW TO FIX:\n"
            "  Use an emissions dataset with country-level historical data:\n"
            "  >>> # Verify historical coverage\n"
            "  >>> print(emissions_df[['1850', '1900', '1950']])  "
            "# Should have country rows"
        )

    cumulative_emissions = history_countries.sum(axis=1, min_count=1)
    responsibility_data = cumulative_emissions.groupby(level=group_level).sum()

    if responsibility_per_capita:
        pop_single_unit = set_single_unit(population_ts, unit_level, ur=ur)
        pop_single_unit = convert_unit_robust(
            pop_single_unit, "million", unit_level=unit_level, ur=ur
        )
        pop_numeric = pop_single_unit.droplevel(unit_level)

        pop_cols = pd.to_numeric(pop_numeric.columns, errors="coerce")
        pop_mask = (pop_cols >= historical_responsibility_year) & (
            pop_cols <= first_allocation_year
        )
        pop_columns = pop_numeric.columns[pop_mask].tolist()
        if not pop_columns:
            raise AllocationError(
                f"Missing population data for responsibility.\n\n"
                f"WHAT HAPPENED:\n"
                f"  No population data found between "
                f"{historical_responsibility_year} and "
                f"{first_allocation_year}.\n\n"
                f"LIKELY CAUSE:\n"
                f"  Population dataset doesn't cover the historical period.\n\n"
                f"HOW TO FIX:\n"
                f"  Use a population dataset with historical coverage:\n"
                f"  >>> # Most UN data starts around 1950\n"
                f"  >>> # For earlier years, use historical datasets like Maddison"
            )

        pop_numeric = pop_numeric[pop_columns]
        cumulative_population = pop_numeric.sum(axis=1, min_count=1)
        population_totals = cumulative_population.groupby(level=group_level).sum()

        responsibility_data = responsibility_data / population_totals

    if responsibility_data.sum() <= 0:
        raise AllocationError(
            "Invalid responsibility calculation.\n\n"
            "WHAT HAPPENED:\n"
            "  Responsibility metric sums to zero or negative.\n\n"
            "LIKELY CAUSE:\n"
            "  All countries have zero/negative historical emissions.\n\n"
            "HOW TO FIX:\n"
            "  Check your historical emissions data:\n"
            "  >>> print(country_actual_emissions_ts.sum(axis=1))  # Should be positive"
        )

    return responsibility_data


def calculate_capability_adjustment_data(
    population_ts: TimeseriesDataFrame,
    gdp_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    capability_per_capita: bool,
    group_level: str,
    unit_level: str,
    ur: pint.facets.PlainRegistry,
    gini_s: pd.DataFrame | None = None,
    income_floor: float = 0.0,
    max_gini_adjustment: float = 0.8,
) -> pd.Series:
    """
    Calculate capability data (cumulative GDP or GDP per capita).

    Returns the raw capability data, NOT an adjustment factor.
    The caller applies the inverse to reduce allocations for higher capability.

    Capability window: from first_allocation_year onwards.

    Parameters
    ----------
    population_ts
        Population timeseries data
    gdp_ts
        GDP timeseries data
    first_allocation_year
        First year of capability window
    capability_per_capita
        If True, divide cumulative GDP by cumulative population
    group_level
        Index level name for country/region grouping
    unit_level
        Index level name for units
    ur
        Pint unit registry
    gini_s
        Optional Gini coefficient data for inequality adjustment.
        When provided, GDP is adjusted to reflect income distribution.
    income_floor
        Income floor for Gini adjustment (in GDP units). Default: 0.0
    max_gini_adjustment
        Maximum reduction factor from Gini adjustment (0-1). Default: 0.8

    Returns
    -------
    pd.Series
        Capability metric by country/region (cumulative GDP or GDP per capita).

    Raises
    ------
    AllocationError
        If no common years between population and GDP, or capability sums to non-positive.

    See Also
    --------
    calculate_responsibility_adjustment_data_convergence : For responsibility adjustments
    docs/science/allocations.md : Theoretical basis for capability adjustment

    """
    # Import here to avoid circular imports
    from fair_shares.library.utils.data.transform import filter_time_columns
    from fair_shares.library.utils.math.allocation import (
        apply_gini_adjustment,
        create_gini_lookup_dict,
    )

    population_filtered = filter_time_columns(population_ts, first_allocation_year)
    gdp_filtered = filter_time_columns(gdp_ts, first_allocation_year)

    population_single_unit = set_single_unit(population_filtered, unit_level, ur=ur)
    gdp_single_unit = set_single_unit(gdp_filtered, unit_level, ur=ur)

    population_single_unit = convert_unit_robust(
        population_single_unit, "million", unit_level=unit_level, ur=ur
    )
    gdp_single_unit = convert_unit_robust(
        gdp_single_unit, "million", unit_level=unit_level, ur=ur
    )

    population_single_unit = population_single_unit.droplevel(unit_level)
    gdp_single_unit = gdp_single_unit.droplevel(unit_level)

    common_columns = population_single_unit.columns.intersection(
        gdp_single_unit.columns
    )
    if not common_columns.tolist():
        raise AllocationError(
            "Year range mismatch.\n\n"
            "WHAT HAPPENED:\n"
            "  No common years found between population and GDP data.\n\n"
            "LIKELY CAUSE:\n"
            "  Population and GDP datasets cover different time periods.\n\n"
            "HOW TO FIX:\n"
            "  Ensure both datasets cover overlapping years:\n"
            "  >>> pop_years = set(population_df.columns)\n"
            "  >>> gdp_years = set(gdp_df.columns)\n"
            "  >>> print(pop_years & gdp_years)  # Should show common years"
        )

    gdp_common = gdp_single_unit[common_columns]
    population_common = population_single_unit[common_columns]

    if gini_s is not None:
        gini_lookup = create_gini_lookup_dict(gini_s)
        gdp_common = apply_gini_adjustment(
            gdp_common,
            population_common,
            gini_lookup,
            income_floor,
            max_gini_adjustment,
            group_level,
        )

    gdp_cmltvsum = gdp_common.sum(axis=1)
    pop_cmltvsum = population_common.sum(axis=1)

    gdp_by_group = gdp_cmltvsum.groupby(level=group_level).sum()
    pop_by_group = pop_cmltvsum.groupby(level=group_level).sum()

    if capability_per_capita:
        capability_data = gdp_by_group / pop_by_group
    else:
        capability_data = gdp_by_group

    if capability_data.sum() <= 0:
        raise AllocationError(
            "Invalid capability calculation.\n\n"
            "WHAT HAPPENED:\n"
            "  Capability metric (GDP per capita) sums to zero or negative.\n\n"
            "LIKELY CAUSE:\n"
            "  GDP or population data contains zeros/negatives or is misaligned.\n\n"
            "HOW TO FIX:\n"
            "  Check GDP and population data:\n"
            "  >>> print(gdp_df.describe())  # Should be positive\n"
            "  >>> print(population_df.describe())  # Should be positive"
        )

    return capability_data
