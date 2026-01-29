"""Data loading functions for preprocessing notebooks."""

from pathlib import Path

import pandas as pd

from fair_shares.library.exceptions import DataLoadingError
from fair_shares.library.utils import ensure_string_year_columns


def load_emissions_data(
    emiss_intermediate_dir: Path,
    final_categories: list[str],
) -> dict[str, pd.DataFrame]:
    """Load emissions data for specified categories.

    Args:
        emiss_intermediate_dir: Path to emissions intermediate directory
        final_categories: List of emission categories to load

    Returns
    -------
        Dictionary mapping category names to emissions DataFrames
    """
    emissions_data = {}
    for category in final_categories:
        emiss_path = emiss_intermediate_dir / f"emiss_{category}_timeseries.csv"
        if emiss_path.exists():
            emiss_df = pd.read_csv(emiss_path)
            emiss_df = emiss_df.set_index(["iso3c", "unit", "emission-category"])
            emiss_df = ensure_string_year_columns(emiss_df)
            emissions_data[category] = emiss_df
        else:
            raise DataLoadingError(
                f"Emissions file not found for requested category {category}: {emiss_path}"
            )
    return emissions_data


def load_gdp_data(gdp_intermediate_dir: Path) -> pd.DataFrame:
    """Load GDP data.

    Args:
        gdp_intermediate_dir: Path to GDP intermediate directory

    Returns
    -------
        GDP DataFrame with multi-index
    """
    gdp_path = gdp_intermediate_dir / "gdp_timeseries.csv"
    if not gdp_path.exists():
        raise DataLoadingError(
            f"GDP file not found: {gdp_path}. "
            "Ensure the GDP preprocessing notebook has been run successfully."
        )
    gdp = pd.read_csv(gdp_path)
    gdp = gdp.set_index(["iso3c", "unit"])
    gdp = ensure_string_year_columns(gdp)
    return gdp


def load_population_data(pop_intermediate_dir: Path) -> pd.DataFrame:
    """Load population data.

    Args:
        pop_intermediate_dir: Path to population intermediate directory

    Returns
    -------
        Population DataFrame with multi-index
    """
    population_path = pop_intermediate_dir / "population_timeseries.csv"
    if not population_path.exists():
        raise DataLoadingError(
            f"Population file not found: {population_path}. "
            "Ensure the population preprocessing notebook has been run successfully."
        )
    population = pd.read_csv(population_path)
    population = population.set_index(["iso3c", "unit"])
    population = ensure_string_year_columns(population)
    return population


def load_gini_data(gini_intermediate_dir: Path) -> pd.DataFrame:
    """Load Gini coefficient data.

    Args:
        gini_intermediate_dir: Path to Gini intermediate directory

    Returns
    -------
        Gini DataFrame with multi-index
    """
    gini_path = gini_intermediate_dir / "gini_stationary.csv"
    if not gini_path.exists():
        raise DataLoadingError(
            f"Gini file not found: {gini_path}. "
            "Ensure the Gini preprocessing notebook has been run successfully."
        )
    gini = pd.read_csv(gini_path)
    gini = gini.set_index(["iso3c", "unit"])
    return gini


def load_scenarios_data(
    scenario_intermediate_dir: Path,
    final_categories: list[str],
) -> dict[str, pd.DataFrame]:
    """Load scenario data for specified emission categories.

    Args:
        scenario_intermediate_dir: Path to scenarios intermediate directory
        final_categories: List of emission categories to load

    Returns
    -------
        Dictionary mapping category names to scenario DataFrames
    """
    scenarios_data = {}
    for category in final_categories:
        scenarios_path = (
            scenario_intermediate_dir / f"scenarios_{category}_timeseries.csv"
        )
        if scenarios_path.exists():
            scenarios_df = pd.read_csv(scenarios_path)
            scenarios_df = scenarios_df.set_index(
                [
                    "climate-assessment",
                    "quantile",
                    "source",
                    "iso3c",
                    "unit",
                    "emission-category",
                ]
            )
            scenarios_df = ensure_string_year_columns(scenarios_df)
            scenarios_data[category] = scenarios_df
            print(f"  Loaded scenarios for {category}: {scenarios_path.name}")
        elif category == "all-other":
            # all-other is a derived category - scenarios may not exist for it
            print(
                f"  Skipping scenarios for {category} (derived category, no scenario file)"
            )
        else:
            # Primary categories should always have scenarios
            raise DataLoadingError(
                f"Scenarios file not found for category {category}: {scenarios_path}"
            )
    return scenarios_data
