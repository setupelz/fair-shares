"""
Data processing utilities for cumulative per capita convergence allocation.

This module contains functions for processing input datasets (emissions, population,
GDP) into the structures needed for convergence calculations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from fair_shares.library.utils.data.transform import filter_time_columns
from fair_shares.library.utils.units import convert_unit_robust, set_single_unit
from fair_shares.library.validation.convergence import (
    validate_country_data_present,
    validate_emissions_data,
    validate_world_emissions_present,
    validate_year_in_data,
)

if TYPE_CHECKING:
    import pint.facets

    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def process_emissions_data(
    country_actual_emissions_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    emission_category: str,
    group_level: str,
    unit_level: str,
    ur: pint.facets.PlainRegistry,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[int, str | int | float], str]:
    """
    Process country emissions data and extract initial shares.

    Parameters
    ----------
    country_actual_emissions_ts : TimeseriesDataFrame
        Raw country emissions data.
    first_allocation_year : int
        Year to start allocation.
    emission_category : str
        Emission category to analyze.
    group_level : str
        Index level for grouping (e.g., 'iso3c').
    unit_level : str
        Index level for units.
    ur : pint.facets.PlainRegistry
        Unit registry.

    Returns
    -------
    tuple
        (emissions_full_numeric, emissions_countries_full, year_to_label, start_column)
    """
    # Process full emissions data
    emissions_full_single_unit = set_single_unit(
        country_actual_emissions_ts, unit_level, ur=ur
    )
    emissions_full_numeric = emissions_full_single_unit.droplevel(unit_level)

    # Validate structure
    validate_emissions_data(emissions_full_numeric, emission_category, group_level)

    # Filter out World rows to get country data
    group_values_all = emissions_full_numeric.index.get_level_values(group_level)
    non_world_mask = group_values_all != "World"
    emissions_countries_full = emissions_full_numeric[non_world_mask]
    validate_country_data_present(emissions_countries_full, group_level)

    # Build year-to-label mapping
    sorted_country_cols = sorted(emissions_countries_full.columns, key=lambda x: int(x))
    country_year_to_label: dict[int, str | int | float] = {}
    for col in sorted_country_cols:
        try:
            country_year_to_label[int(float(col))] = col
        except (TypeError, ValueError):
            continue

    # Validate first_allocation_year exists
    validate_year_in_data(
        first_allocation_year,
        country_year_to_label,
        "country emissions",
        sorted_country_cols,
    )
    start_column = country_year_to_label[first_allocation_year]

    return (
        emissions_full_numeric,
        emissions_countries_full,
        country_year_to_label,
        start_column,
    )


def calculate_initial_shares(
    emissions_countries_full: pd.DataFrame,
    start_column: str,
    group_level: str,
) -> tuple[pd.Series, float]:
    """
    Calculate initial emission shares from actual emissions at start year.

    Parameters
    ----------
    emissions_countries_full : pd.DataFrame
        Country emissions data (World rows already filtered out).
    start_column : str
        Column label for first allocation year.
    group_level : str
        Index level for grouping.

    Returns
    -------
    tuple
        (country_totals, country_sum) where country_totals is Series of emissions
        by country and country_sum is the total.
    """
    emissions_at_start = emissions_countries_full[start_column]
    country_totals = emissions_at_start.groupby(level=group_level).sum()
    country_sum = float(country_totals.sum())
    return country_totals, country_sum


def process_world_scenario_data(
    world_scenario_emissions_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    group_level: str,
    unit_level: str,
    ur: pint.facets.PlainRegistry,
) -> tuple[
    pd.DataFrame,
    pd.Series,
    list[str],
    dict[int, str | int | float],
    str,
    float,
]:
    """
    Process world scenario emissions and calculate year fractions.

    Parameters
    ----------
    world_scenario_emissions_ts : TimeseriesDataFrame
        World emissions pathway.
    first_allocation_year : int
        Year to start allocation.
    group_level : str
        Index level for grouping.
    unit_level : str
        Index level for units.
    ur : pint.facets.PlainRegistry
        Unit registry.

    Returns
    -------
    tuple
        (emissions_world, year_fraction_of_cumulative_emissions, sorted_columns,
         world_year_to_label, world_start_column, world_total)
    """
    # Process world scenario (full data for consistency check)
    world_full_single_unit = set_single_unit(
        world_scenario_emissions_ts, unit_level, ur=ur
    )
    world_full_numeric = world_full_single_unit.droplevel(unit_level)
    validate_world_emissions_present(world_full_numeric)

    # Extract World rows
    if group_level in world_full_numeric.index.names:
        world_full_values = world_full_numeric.index.get_level_values(group_level)
        world_full_rows = world_full_numeric[world_full_values == "World"]
        emissions_world_full = (
            world_full_rows if not world_full_rows.empty else world_full_numeric
        )
    else:
        emissions_world_full = world_full_numeric

    # Build year mapping for world data
    sorted_world_full_cols = sorted(emissions_world_full.columns, key=lambda x: int(x))
    world_full_year_to_label: dict[int, str | int | float] = {}
    for col in sorted_world_full_cols:
        try:
            world_full_year_to_label[int(float(col))] = col
        except (TypeError, ValueError):
            continue

    # Validate first_allocation_year exists in world data
    validate_year_in_data(
        first_allocation_year,
        world_full_year_to_label,
        "world scenario emissions",
        sorted_world_full_cols,
    )
    world_start_column = world_full_year_to_label[first_allocation_year]
    world_at_start = emissions_world_full[world_start_column]
    world_total = float(world_at_start.sum())

    # Process world scenario for allocation period only
    world_filtered = filter_time_columns(
        world_scenario_emissions_ts, first_allocation_year
    )
    world_single_unit = set_single_unit(world_filtered, unit_level, ur=ur)
    world_numeric = world_single_unit.droplevel(unit_level)

    if group_level in world_numeric.index.names:
        world_values = world_numeric.index.get_level_values(group_level)
        world_rows = world_numeric[world_values == "World"]
        emissions_world = world_rows if not world_rows.empty else world_numeric
    else:
        emissions_world = world_numeric

    # Calculate year fractions for cumulative weighting
    world_time_columns = list(emissions_world.columns)
    sorted_columns = sorted(world_time_columns, key=lambda x: int(x))

    world_series = emissions_world.sum(axis=0).reindex(world_time_columns)
    total_sum = float(world_series.sum())
    year_fraction_of_cumulative_emissions = world_series / total_sum

    return (
        emissions_world,
        year_fraction_of_cumulative_emissions,
        sorted_columns,
        world_full_year_to_label,
        world_start_column,
        world_total,
    )


def process_population_data(
    population_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    group_level: str,
    unit_level: str,
    ur: pint.facets.PlainRegistry,
) -> pd.Series:
    """
    Process population data and calculate cumulative population by group.

    Parameters
    ----------
    population_ts : TimeseriesDataFrame
        Population time series.
    first_allocation_year : int
        Year to start allocation.
    group_level : str
        Index level for grouping.
    unit_level : str
        Index level for units.
    ur : pint.facets.PlainRegistry
        Unit registry.

    Returns
    -------
    pd.Series
        Cumulative population by group.
    """
    population_filtered = filter_time_columns(population_ts, first_allocation_year)
    population_single_unit = set_single_unit(population_filtered, unit_level, ur=ur)
    population_single_unit = convert_unit_robust(
        population_single_unit, "million", unit_level=unit_level, ur=ur
    )
    population_numeric = population_single_unit.droplevel(unit_level)

    cumulative_population = population_numeric.sum(axis=1)
    cmltv_pop_by_group = cumulative_population.groupby(level=group_level).sum()

    return cmltv_pop_by_group


def build_result_dataframe(
    shares_by_group: pd.DataFrame,
    emissions_countries_index: pd.Index,
    world_time_columns: list[str],
    group_level: str,
    unit_level: str,
) -> pd.DataFrame:
    """
    Build final result DataFrame with proper index structure.

    Parameters
    ----------
    shares_by_group : pd.DataFrame
        Calculated shares indexed by group.
    emissions_countries_index : pd.Index
        Original emissions index for alignment.
    world_time_columns : list[str]
        Year columns from world scenario.
    group_level : str
        Index level for grouping.
    unit_level : str
        Index level for units.

    Returns
    -------
    pd.DataFrame
        Result DataFrame with proper multi-index structure.
    """
    group_values = emissions_countries_index.get_level_values(group_level)
    expanded = shares_by_group.reindex(group_values)
    expanded.index = emissions_countries_index
    res = expanded[world_time_columns].reset_index()
    res[unit_level] = "dimensionless"
    res = res.set_index([group_level, unit_level, "emission-category"])
    return res
