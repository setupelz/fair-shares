"""Rest of World (ROW) data completion logic."""

import pandas as pd

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils import add_row_timeseries, get_world_totals_timeseries


def add_row_to_datasets(
    emissions_data: dict[str, pd.DataFrame],
    gdp: pd.DataFrame,
    population: pd.DataFrame,
    gini: pd.DataFrame,
    analysis_countries: set[str],
    emissions_world_key: str,
    gdp_world_key: str,
    population_world_key: str,
) -> tuple[
    dict[str, pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, pd.DataFrame],
]:
    """Add Rest of World (ROW) aggregates to all datasets.

    ROW represents countries that are missing from the analysis dataset, computed as
    the difference between world totals and the sum of complete countries.

    Args:
        emissions_data: Dictionary of emission category DataFrames
        gdp: GDP DataFrame
        population: Population DataFrame
        gini: Gini coefficient DataFrame
        analysis_countries: Set of countries with complete data
        emissions_world_key: Key for world totals in emissions data
        gdp_world_key: Key for world totals in GDP data
        population_world_key: Key for world totals in population data

    Returns
    -------
        Tuple of (emissions_complete, gdp_complete, population_complete, gini_complete, world_emissions)
    """
    # Get world totals for each dataset
    world_emiss = {}
    for category, emiss_df in emissions_data.items():
        world_emiss[category] = get_world_totals_timeseries(
            emiss_df,
            emissions_world_key,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )

    world_gdp = get_world_totals_timeseries(
        gdp, gdp_world_key, expected_index_names=["iso3c", "unit"]
    )

    world_population = get_world_totals_timeseries(
        population, population_world_key, expected_index_names=["iso3c", "unit"]
    )

    # Add ROW to each dataset
    emiss_complete = {}
    for category, emiss_df in emissions_data.items():
        emiss_complete[category] = add_row_timeseries(
            emiss_df,
            analysis_countries,
            world_emiss[category],
            expected_index_names=["iso3c", "unit", "emission-category"],
        )

    gdp_complete = add_row_timeseries(
        gdp, analysis_countries, world_gdp, expected_index_names=["iso3c", "unit"]
    )
    population_complete = add_row_timeseries(
        population,
        analysis_countries,
        world_population,
        expected_index_names=["iso3c", "unit"],
    )

    # Handle Gini separately - use average of analysis countries for ROW
    gini_analysis = gini[
        gini.index.get_level_values("iso3c").isin(analysis_countries)
    ].copy()

    if gini_analysis.empty:
        raise DataProcessingError(
            "No Gini coefficient data found for analysis countries. "
            "Cannot calculate ROW average without data."
        )

    gini_analysis_average = gini_analysis["gini"].mean()
    gini_row = pd.DataFrame(
        {"gini": [gini_analysis_average]},
        index=pd.MultiIndex.from_tuples([("ROW", "unitless")], names=["iso3c", "unit"]),
    )
    gini_complete = pd.concat([gini_analysis, gini_row])

    return emiss_complete, gdp_complete, population_complete, gini_complete, world_emiss
