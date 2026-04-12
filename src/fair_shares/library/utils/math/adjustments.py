"""
Shared adjustment calculations for allocation approaches.

This module contains reusable adjustment calculations that are common across
both budget and pathway allocation approaches:
- Pre-allocation responsibility adjustments (historical emissions-based)
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
    pre_allocation_responsibility_year: int,
    allocation_year: int,
    pre_allocation_responsibility_per_capita: bool,
    group_level: str,
    unit_level: str,
    ur: pint.facets.PlainRegistry,
    historical_discount_rate: float = 0.0,
) -> pd.Series:
    """
    Calculate pre-allocation responsibility data for allocation.

    Returns cumulative emissions (or per capita emissions) from
    pre_allocation_responsibility_year up to (but not including) allocation_year.

    Pre-allocation responsibility window: [pre_allocation_responsibility_year, allocation_year - 1].

    This function is used by both budget and pathway allocations.

    Parameters
    ----------
    country_actual_emissions_ts
        Historical emissions timeseries data
    population_ts
        Population timeseries data
    pre_allocation_responsibility_year
        Start year of pre-allocation responsibility window (inclusive)
    allocation_year
        End year of pre-allocation responsibility window (exclusive).
        For budgets: the allocation year itself.
        For pathways: the first allocation year.
    pre_allocation_responsibility_per_capita
        If True, divide cumulative emissions by cumulative population
    group_level
        Index level name for country/region grouping
    unit_level
        Index level name for units
    ur
        Pint unit registry
    historical_discount_rate
        Discount rate for historical emissions (0.0 to <1.0). When > 0, earlier
        emissions are weighted less via (1 - rate)^(reference_year - t), where
        reference_year = allocation_year - 1.
        Default: 0.0 (no discounting).

    Returns
    -------
    pd.Series
        Pre-allocation responsibility metric by country/region.
        Units: emissions (or emissions per capita) depending on pre_allocation_responsibility_per_capita.

    Raises
    ------
    AllocationError
        If no years found in pre-allocation responsibility window, no country
        data found, zero population encountered (when per capita),
        pre-allocation responsibility sums to non-positive, or
        historical_discount_rate is out of range.

    See Also
    --------
    docs/science/allocations.md : Theoretical basis for historical responsibility

    """
    # Validate historical_discount_rate
    if not (0.0 <= historical_discount_rate < 1.0):
        raise AllocationError(
            f"historical_discount_rate must be >= 0.0 and < 1.0, "
            f"got {historical_discount_rate}."
        )

    # Process emissions data
    history_single_unit = set_single_unit(
        country_actual_emissions_ts, unit_level, ur=ur
    )
    history_numeric = history_single_unit.droplevel(unit_level)

    # Filter to historical period [pre_allocation_responsibility_year, allocation_year - 1]
    numeric_cols = pd.to_numeric(history_numeric.columns, errors="coerce")
    responsibility_mask = (numeric_cols >= pre_allocation_responsibility_year) & (
        numeric_cols < allocation_year
    )
    responsibility_columns = history_numeric.columns[responsibility_mask].tolist()
    if not responsibility_columns:
        raise AllocationError(
            f"No years found between {pre_allocation_responsibility_year} "
            f"and {allocation_year - 1} for pre-allocation responsibility calculation."
        )

    history_numeric = history_numeric[responsibility_columns]

    # Filter out World rows if present
    history_group_values = history_numeric.index.get_level_values(group_level)
    history_countries = history_numeric[history_group_values != "World"]
    if history_countries.empty:
        raise AllocationError(
            "No country-level emissions rows found for pre-allocation responsibility window."
        )

    # Apply historical discount weights if rate > 0
    # Weight = (1 - r_d)^(reference_year - t), where reference_year = allocation_year - 1
    if historical_discount_rate > 0.0:
        reference_year = allocation_year - 1
        years = pd.to_numeric(responsibility_columns, errors="coerce")
        discount_weights = pd.Series(
            [
                (1 - historical_discount_rate) ** (reference_year - y)
                for y in years
            ],
            index=responsibility_columns,
        )
        history_countries = history_countries.mul(discount_weights, axis=1)

    # Sum emissions across historical period
    cumulative_emissions = history_countries.sum(axis=1, min_count=1)
    responsibility_data = cumulative_emissions.groupby(level=group_level).sum()

    # If per capita, divide by cumulative population over the same period
    if pre_allocation_responsibility_per_capita:
        pop_single_unit = set_single_unit(population_ts, unit_level, ur=ur)
        pop_single_unit = convert_unit_robust(
            pop_single_unit, "million", unit_level=unit_level, ur=ur
        )
        pop_numeric = pop_single_unit.droplevel(unit_level)

        pop_cols = pd.to_numeric(pop_numeric.columns, errors="coerce")
        pop_mask = (pop_cols >= pre_allocation_responsibility_year) & (
            pop_cols < allocation_year
        )
        pop_columns = pop_numeric.columns[pop_mask].tolist()
        if not pop_columns:
            raise AllocationError("No population data found for pre-allocation responsibility window.")

        pop_numeric = pop_numeric[pop_columns]

        # Apply same discount weights to population for consistency
        if historical_discount_rate > 0.0:
            pop_years = pd.to_numeric(pop_columns, errors="coerce")
            pop_discount_weights = pd.Series(
                [
                    (1 - historical_discount_rate) ** (reference_year - y)
                    for y in pop_years
                ],
                index=pop_columns,
            )
            pop_numeric = pop_numeric.mul(pop_discount_weights, axis=1)

        cumulative_population = pop_numeric.sum(axis=1, min_count=1)
        population_totals = cumulative_population.groupby(level=group_level).sum()

        if (population_totals == 0).any():
            zero_groups = population_totals[population_totals == 0].index.tolist()
            raise AllocationError(
                f"Zero population found for groups {zero_groups} in pre-allocation responsibility window "
                f"({pre_allocation_responsibility_year}-{allocation_year}). Cannot calculate per-capita pre-allocation responsibility."
            )

        responsibility_data = responsibility_data / population_totals

    if responsibility_data.sum() <= 0:
        raise AllocationError("Pre-allocation responsibility metric sums to non-positive.")

    return responsibility_data


def calculate_responsibility_adjustment_data_convergence(
    country_actual_emissions_ts: TimeseriesDataFrame,
    population_ts: TimeseriesDataFrame,
    pre_allocation_responsibility_year: int,
    first_allocation_year: int,
    pre_allocation_responsibility_per_capita: bool,
    group_level: str,
    unit_level: str,
    ur: pint.facets.PlainRegistry,
    historical_discount_rate: float = 0.0,
) -> pd.Series:
    """
    Calculate pre-allocation responsibility data for convergence pathway allocation.

    Returns cumulative emissions (or per capita emissions) from
    pre_allocation_responsibility_year up to and including first_allocation_year.

    Pre-allocation responsibility window: [pre_allocation_responsibility_year, first_allocation_year].

    This function is used by convergence pathway allocations where the first
    allocation year is included in the pre-allocation responsibility calculation.

    Parameters
    ----------
    country_actual_emissions_ts
        Historical emissions timeseries data
    population_ts
        Population timeseries data
    pre_allocation_responsibility_year
        Start year of pre-allocation responsibility window (inclusive)
    first_allocation_year
        End year of pre-allocation responsibility window (inclusive).
    pre_allocation_responsibility_per_capita
        If True, divide cumulative emissions by cumulative population
    group_level
        Index level name for country/region grouping
    unit_level
        Index level name for units
    ur
        Pint unit registry
    historical_discount_rate
        Discount rate for historical emissions (0.0 to <1.0). When > 0, earlier
        emissions are weighted less via (1 - rate)^(reference_year - t), where
        reference_year = first_allocation_year.
        Default: 0.0 (no discounting).

    Returns
    -------
    pd.Series
        Pre-allocation responsibility metric by country/region.
        Units: emissions (or emissions per capita) depending on pre_allocation_responsibility_per_capita.

    Raises
    ------
    AllocationError
        If no years found in pre-allocation responsibility window, no country
        data found, zero population encountered (when per capita),
        pre-allocation responsibility sums to non-positive, or
        historical_discount_rate is out of range.

    See Also
    --------
    calculate_responsibility_adjustment_data : For budget allocations (exclusive end)
    docs/science/allocations.md : Theoretical basis for historical responsibility

    """
    # Validate historical_discount_rate
    if not (0.0 <= historical_discount_rate < 1.0):
        raise AllocationError(
            f"historical_discount_rate must be >= 0.0 and < 1.0, "
            f"got {historical_discount_rate}."
        )

    history_single_unit = set_single_unit(
        country_actual_emissions_ts, unit_level, ur=ur
    )
    history_numeric = history_single_unit.droplevel(unit_level)

    # Filter to historical period [pre_allocation_responsibility_year, first_allocation_year]
    # Note: inclusive on both ends (differs from budget allocation version)
    numeric_cols = pd.to_numeric(history_numeric.columns, errors="coerce")
    responsibility_mask = (numeric_cols >= pre_allocation_responsibility_year) & (
        numeric_cols <= first_allocation_year
    )
    responsibility_columns = history_numeric.columns[responsibility_mask].tolist()
    if not responsibility_columns:
        raise AllocationError(
            f"Insufficient historical data for pre-allocation responsibility.\n\n"
            f"WHAT HAPPENED:\n"
            f"  No years found between {pre_allocation_responsibility_year} and "
            f"{first_allocation_year}.\n"
            f"  Pre-allocation responsibility calculation requires historical emissions "
            f"data.\n\n"
            f"LIKELY CAUSE:\n"
            f"  The emissions dataset doesn't cover the historical period.\n\n"
            f"HOW TO FIX:\n"
            f"  1. Use a dataset with historical coverage (e.g., PRIMAP back "
            f"to 1850)\n"
            f"  2. Or adjust pre_allocation_responsibility_year to match available "
            f"data:\n"
            f"     >>> result = manager.run_allocation(\n"
            f"     ...     ...,\n"
            f"     ...     pre_allocation_responsibility_year=1990  "
            f"# Instead of 1850\n"
            f"     ... )"
        )

    history_numeric = history_numeric[responsibility_columns]
    history_group_values = history_numeric.index.get_level_values(group_level)
    history_countries = history_numeric[history_group_values != "World"]
    if history_countries.empty:
        raise AllocationError(
            "No country data for pre-allocation responsibility calculation.\n\n"
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

    # Apply historical discount weights if rate > 0
    # Weight = (1 - r_d)^(reference_year - t), where reference_year = first_allocation_year
    if historical_discount_rate > 0.0:
        reference_year = first_allocation_year
        years = pd.to_numeric(responsibility_columns, errors="coerce")
        discount_weights = pd.Series(
            [
                (1 - historical_discount_rate) ** (reference_year - y)
                for y in years
            ],
            index=responsibility_columns,
        )
        history_countries = history_countries.mul(discount_weights, axis=1)

    cumulative_emissions = history_countries.sum(axis=1, min_count=1)
    responsibility_data = cumulative_emissions.groupby(level=group_level).sum()

    if pre_allocation_responsibility_per_capita:
        pop_single_unit = set_single_unit(population_ts, unit_level, ur=ur)
        pop_single_unit = convert_unit_robust(
            pop_single_unit, "million", unit_level=unit_level, ur=ur
        )
        pop_numeric = pop_single_unit.droplevel(unit_level)

        pop_cols = pd.to_numeric(pop_numeric.columns, errors="coerce")
        pop_mask = (pop_cols >= pre_allocation_responsibility_year) & (
            pop_cols <= first_allocation_year
        )
        pop_columns = pop_numeric.columns[pop_mask].tolist()
        if not pop_columns:
            raise AllocationError(
                f"Missing population data for pre-allocation responsibility.\n\n"
                f"WHAT HAPPENED:\n"
                f"  No population data found between "
                f"{pre_allocation_responsibility_year} and "
                f"{first_allocation_year}.\n\n"
                f"LIKELY CAUSE:\n"
                f"  Population dataset doesn't cover the historical period.\n\n"
                f"HOW TO FIX:\n"
                f"  Use a population dataset with historical coverage:\n"
                f"  >>> # Most UN data starts around 1950\n"
                f"  >>> # For earlier years, use historical datasets like Maddison"
            )

        pop_numeric = pop_numeric[pop_columns]

        # Apply same discount weights to population for consistency
        if historical_discount_rate > 0.0:
            pop_years = pd.to_numeric(pop_columns, errors="coerce")
            pop_discount_weights = pd.Series(
                [
                    (1 - historical_discount_rate) ** (reference_year - y)
                    for y in pop_years
                ],
                index=pop_columns,
            )
            pop_numeric = pop_numeric.mul(pop_discount_weights, axis=1)

        cumulative_population = pop_numeric.sum(axis=1, min_count=1)
        population_totals = cumulative_population.groupby(level=group_level).sum()

        responsibility_data = responsibility_data / population_totals

    if responsibility_data.sum() <= 0:
        raise AllocationError(
            "Invalid pre-allocation responsibility calculation.\n\n"
            "WHAT HAPPENED:\n"
            "  Pre-allocation responsibility metric sums to zero or negative.\n\n"
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
    Calculate economic capability data (GDP-based proxy for the Ability to Pay Principle).

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
        Income floor for Gini adjustment (in USD PPP per capita). Income below this
        threshold is excluded from capability calculations, adapted from the
        Greenhouse Development Rights (GDR) development threshold.
        Default: 0.0
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

    Notes
    -----
    **GDP window:** The cumulative sums of GDP and population are computed
    only over the intersection of years where both data are available. There
    is no forward-fill into post-observation years. With ``gdp_ts`` typically
    ending at the last observed year (e.g. 2023 for ``wdi-2025``) and
    population running to ~2100, only the observed-GDP years contribute to
    the capability metric. Users who want post-observation GDP dynamics to
    enter the capability calculation should extend the input ``gdp_ts`` time
    series with projected data (SSP2 GDP projections, custom growth
    assumptions, or a future-extended WDI release) before calling this
    function.

    See Also
    --------
    calculate_responsibility_adjustment_data_convergence : For pre-allocation responsibility adjustments
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
