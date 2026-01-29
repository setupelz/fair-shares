"""
Example data generation for documentation and testing.

This module provides helper functions to generate minimal example datasets
that can be used in docstring examples and for quick testing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fair_shares.library.utils.dataframes import ensure_string_year_columns


def create_example_data(
    countries: list[str] | None = None,
    years: list[int] | None = None,
    emission_category: str = "co2-ffi",
) -> dict[str, pd.DataFrame]:
    """
    Create minimal example data for documentation and testing.

    This function generates realistic example datasets with proper index
    structures and magnitudes suitable for use in docstring examples and
    quick testing.

    Parameters
    ----------
    countries : list[str], optional
        List of ISO3C country codes to include. Defaults to ["USA", "CHN", "IND"].
    years : list[int], optional
        List of years to include. Defaults to [2020, 2030, 2050].
    emission_category : str, default="co2-ffi"
        The emission category to use for emissions data.

    Returns
    -------
    dict[str, pd.DataFrame]
        Dictionary with keys:
        - 'population': Population DataFrame with MultiIndex ['iso3c', 'unit']
        - 'gdp': GDP DataFrame with MultiIndex ['iso3c', 'unit']
        - 'emissions': Emissions DataFrame with MultiIndex
          ['iso3c', 'unit', 'emission-category']
        - 'world_emissions': World emissions pathway (subset of emissions DataFrame)
        - 'gini': Gini coefficients DataFrame with columns ['iso3c', 'gini']

    Notes
    -----
    All TimeseriesDataFrames (population, gdp, emissions) use string year columns
    (e.g., "2020") following the codebase convention. The emissions DataFrame
    includes a "World" row with global totals.

    The data magnitudes are realistic:
    - Population: millions of people
    - GDP: billions (of USD, PPP-adjusted)
    - Emissions: Mt CO2e (megatonnes of CO2 equivalent)
    - Gini: unitless coefficient between 0 and 1

    Examples
    --------
    >>> data = create_example_data()
    >>> data["population"].head()  # doctest: +SKIP
    >>> # Population data for USA, CHN, IND for years 2020, 2030, 2050

    >>> # Custom countries and years
    >>> data = create_example_data(
    ...     countries=["DEU", "FRA", "GBR"], years=[2025, 2035, 2045]
    ... )
    """
    # Default arguments
    if countries is None:
        countries = ["USA", "CHN", "IND"]
    if years is None:
        years = [2020, 2030, 2050]

    # Set seed for reproducibility
    np.random.seed(42)

    # Realistic base values (approximate real-world magnitudes)
    base_population = {
        "USA": 330,
        "CHN": 1400,
        "IND": 1400,
        "DEU": 83,
        "FRA": 67,
        "GBR": 67,
    }
    base_gdp = {
        "USA": 21000,
        "CHN": 14000,
        "IND": 2900,
        "DEU": 3800,
        "FRA": 2700,
        "GBR": 2800,
    }
    base_emissions = {
        "USA": 5000,
        "CHN": 10000,
        "IND": 2500,
        "DEU": 700,
        "FRA": 300,
        "GBR": 400,
    }
    base_gini = {
        "USA": 0.41,
        "CHN": 0.47,
        "IND": 0.36,
        "DEU": 0.29,
        "FRA": 0.29,
        "GBR": 0.35,
    }

    # Default values for unknown countries
    default_population = 100
    default_gdp = 1000
    default_emissions = 500
    default_gini = 0.35

    # Generate population data
    population_data = []
    for country in countries:
        base_pop = base_population.get(country, default_population)
        for year in years:
            # Simple growth model: 0.5% per year
            pop = base_pop * (1 + 0.005) ** (year - 2020)
            population_data.append([country, "million", year, pop])

    population_df = pd.DataFrame(
        population_data, columns=["iso3c", "unit", "year", "population"]
    ).pivot_table(index=["iso3c", "unit"], columns="year", values="population")
    population_df = ensure_string_year_columns(population_df)

    # Generate GDP data
    gdp_data = []
    for country in countries:
        base_val = base_gdp.get(country, default_gdp)
        for year in years:
            # Growth model: 2% per year
            gdp = base_val * (1 + 0.02) ** (year - 2020)
            gdp_data.append([country, "billion", year, gdp])

    gdp_df = pd.DataFrame(
        gdp_data, columns=["iso3c", "unit", "year", "gdp"]
    ).pivot_table(index=["iso3c", "unit"], columns="year", values="gdp")
    gdp_df = ensure_string_year_columns(gdp_df)

    # Generate emissions data
    emissions_data = []

    # Calculate world totals for each year (declining pathway)
    world_totals = {}
    for year in years:
        # Declining emissions: -2% per year from 2020 baseline
        world_base = sum(base_emissions.get(c, default_emissions) for c in countries)
        world_totals[year] = world_base * (1 - 0.02) ** (year - 2020)

    # Add country emissions data
    for country in countries:
        base_val = base_emissions.get(country, default_emissions)
        for year in years:
            # Declining emissions: -2% per year
            emissions = base_val * (1 - 0.02) ** (year - 2020)
            emissions_data.append(
                [country, "Mt CO2e", emission_category, year, emissions]
            )

    # Add World row
    for year in years:
        emissions_data.append(
            ["World", "Mt CO2e", emission_category, year, world_totals[year]]
        )

    emissions_df = pd.DataFrame(
        emissions_data,
        columns=["iso3c", "unit", "emission-category", "year", "emissions"],
    ).pivot_table(
        index=["iso3c", "unit", "emission-category"], columns="year", values="emissions"
    )
    emissions_df = ensure_string_year_columns(emissions_df)

    # Generate Gini data (single year, not time series)
    gini_data = []
    for country in countries:
        gini_value = base_gini.get(country, default_gini)
        gini_data.append([country, "unitless", gini_value])

    gini_df = pd.DataFrame(gini_data, columns=["iso3c", "unit", "gini"])
    gini_df = gini_df.set_index(["iso3c", "unit"])

    # Extract world emissions as separate DataFrame
    world_mask = emissions_df.index.get_level_values("iso3c") == "World"
    world_emissions_df = emissions_df[world_mask]

    return {
        "population": population_df,
        "gdp": gdp_df,
        "emissions": emissions_df,
        "world_emissions": world_emissions_df,
        "gini": gini_df,
    }
