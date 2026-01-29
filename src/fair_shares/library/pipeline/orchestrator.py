"""Orchestration logic for data preprocessing pipelines.

This module extracts the orchestration logic from notebooks to make it
reusable and testable. Notebooks should call these functions rather than
duplicating the logic.
"""

from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from pyprojroot import here

from ..exceptions import ConfigurationError, DataLoadingError
from ..utils import (
    add_row_timeseries,
    determine_processing_categories,
    ensure_string_year_columns,
    get_complete_iso3c_timeseries,
    get_world_totals_timeseries,
    process_rcb_to_2020_baseline,
    set_post_net_zero_emissions_to_nan,
)
from ..validation import (
    validate_all_datasets_totals,
    validate_emissions_data,
    validate_gdp_data,
    validate_gini_data,
    validate_population_data,
    validate_scenarios_data,
)


class PreprocessingOrchestrator:
    """Orchestrates data preprocessing for RCB or pathway-based allocations.

    This class encapsulates the common orchestration logic from the
    100_data_preprocess_*.py notebooks, making it reusable and testable.
    """

    def __init__(
        self,
        config: dict[str, Any],
        source_id: str,
        active_sources: dict[str, str],
        emission_category: str,
    ):
        """Initialize the orchestrator.

        Args:
            config: Configuration dictionary from build_data_config
            source_id: Source identifier string
            active_sources: Dict mapping source types to source names
            emission_category: Emission category (e.g., 'co2-ffi')
        """
        self.config = config
        self.source_id = source_id
        self.active_sources = active_sources
        self.emission_category = emission_category
        self.project_root = here()

        # Extract active source names
        self.active_emissions_source = active_sources["emissions"]
        self.active_gdp_source = active_sources["gdp"]
        self.active_population_source = active_sources["population"]
        self.active_gini_source = active_sources["gini"]
        self.active_target_source = active_sources["target"]

        # Setup paths
        self._setup_paths()

        # Extract config parameters
        self._extract_config_parameters()

    def _setup_paths(self) -> None:
        """Setup intermediate directory paths."""
        base = self.project_root / f"output/{self.source_id}/intermediate"

        self.emiss_intermediate_dir = base / "emissions"
        self.gdp_intermediate_dir = base / "gdp"
        self.pop_intermediate_dir = base / "population"
        self.gini_intermediate_dir = base / "gini"
        self.processed_intermediate_dir = base / "processed"

        # Create directories
        for dir_path in [
            self.emiss_intermediate_dir,
            self.gdp_intermediate_dir,
            self.pop_intermediate_dir,
            self.gini_intermediate_dir,
            self.processed_intermediate_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _extract_config_parameters(self) -> None:
        """Extract parameters from config dictionary."""
        # Emissions parameters
        emissions_params = self.config["emissions"][self.active_emissions_source][
            "data_parameters"
        ]
        self.available_categories = emissions_params.get("available_categories")
        self.emissions_world_key = emissions_params.get("world_key")
        self.emissions_scenario = emissions_params.get("scenario")

        # Determine processing categories
        processing_info = determine_processing_categories(
            self.emission_category, self.available_categories
        )
        self.final_categories = processing_info["final"]

        # GDP parameters
        gdp_params = self.config["gdp"][self.active_gdp_source]["data_parameters"]
        self.gdp_variant = gdp_params.get("gdp_variant")
        self.gdp_world_key = gdp_params.get("world_key")

        # Population parameters
        pop_params = self.config["population"][self.active_population_source][
            "data_parameters"
        ]
        self.population_projection = pop_params.get("projected_variant")
        self.population_historical_world_key = pop_params.get("historical_world_key")
        self.population_projected_world_key = pop_params.get("projected_world_key")

        # Region mapping
        self.region_mapping_path = self.config["general"]["region_mapping"]["path"]

    def load_emissions_data(self) -> dict[str, pd.DataFrame]:
        """Load emissions data for all categories.

        Returns
        -------
            Dictionary mapping category names to DataFrames

        Raises
        ------
            DataLoadingError: If emissions file not found
        """
        emissions_data = {}

        for category in self.final_categories:
            emiss_path = (
                self.emiss_intermediate_dir / f"emiss_{category}_timeseries.csv"
            )
            if not emiss_path.exists():
                raise DataLoadingError(
                    f"Emissions file not found for category {category}: {emiss_path}. "
                    "Ensure the emissions preprocessing notebook has been run successfully."
                )

            emiss_df = pd.read_csv(emiss_path)
            emiss_df = emiss_df.set_index(["iso3c", "unit", "emission-category"])
            emiss_df = ensure_string_year_columns(emiss_df)
            emissions_data[category] = emiss_df

        return emissions_data

    def load_gdp_data(self) -> pd.DataFrame:
        """Load GDP data.

        Returns
        -------
            GDP DataFrame with iso3c and unit index

        Raises
        ------
            DataLoadingError: If GDP file not found
        """
        gdp_path = self.gdp_intermediate_dir / "gdp_timeseries.csv"
        if not gdp_path.exists():
            raise DataLoadingError(
                f"GDP file not found: {gdp_path}. "
                "Ensure the GDP preprocessing notebook has been run successfully."
            )

        gdp = pd.read_csv(gdp_path)
        gdp = gdp.set_index(["iso3c", "unit"])
        gdp = ensure_string_year_columns(gdp)

        return gdp

    def load_population_data(self) -> pd.DataFrame:
        """Load population data.

        Returns
        -------
            Population DataFrame with iso3c and unit index

        Raises
        ------
            DataLoadingError: If population file not found
        """
        pop_path = self.pop_intermediate_dir / "population_timeseries.csv"
        if not pop_path.exists():
            raise DataLoadingError(
                f"Population file not found: {pop_path}. "
                "Ensure the population preprocessing notebook has been run successfully."
            )

        population = pd.read_csv(pop_path)
        population = population.set_index(["iso3c", "unit"])
        population = ensure_string_year_columns(population)

        return population

    def load_gini_data(self) -> pd.DataFrame:
        """Load Gini coefficient data.

        Returns
        -------
            Gini DataFrame with iso3c and year index

        Raises
        ------
            DataLoadingError: If Gini file not found
        """
        gini_path = self.gini_intermediate_dir / "gini_stationary.csv"
        if not gini_path.exists():
            raise DataLoadingError(
                f"Gini file not found: {gini_path}. "
                "Ensure the Gini preprocessing notebook has been run successfully."
            )

        gini = pd.read_csv(gini_path)
        gini = gini.set_index(["iso3c", "year"])

        return gini

    def determine_analysis_countries(
        self,
        emissions_data: dict[str, pd.DataFrame],
        gdp: pd.DataFrame,
        population: pd.DataFrame,
        gini: pd.DataFrame,
    ) -> tuple[list[str], pd.DataFrame]:
        """Determine the set of analysis countries with complete data.

        Args:
            emissions_data: Dict of emission DataFrames by category
            gdp: GDP DataFrame
            population: Population DataFrame
            gini: Gini DataFrame

        Returns
        -------
            Tuple of (country_list, missing_countries_df)
        """
        # Get complete country list across all datasets
        analysis_years = [str(y) for y in range(1990, 2020)]  # 1990-2019

        country_iso3c = get_complete_iso3c_timeseries(
            emissions_data=emissions_data,
            gdp_data=gdp,
            population_data=population,
            gini_data=gini,
            years=analysis_years,
        )

        return country_iso3c

    def save_processed_data(
        self,
        emissions_complete: dict[str, pd.DataFrame],
        gdp_complete: pd.DataFrame,
        population_complete: pd.DataFrame,
        gini_complete: pd.DataFrame,
        world_emiss: dict[str, pd.DataFrame] | None = None,
    ) -> None:
        """Save processed data to CSV files.

        Args:
            emissions_complete: Dict of complete emission DataFrames
            gdp_complete: Complete GDP DataFrame
            population_complete: Complete population DataFrame
            gini_complete: Complete Gini DataFrame
            world_emiss: Optional dict of world emission DataFrames (historical only)
        """
        # Save country data
        for category, emiss_df in emissions_complete.items():
            emiss_output_path = (
                self.processed_intermediate_dir
                / f"country_emissions_{category}_timeseries.csv"
            )
            emiss_df = ensure_string_year_columns(emiss_df)
            emiss_df.reset_index().to_csv(emiss_output_path, index=False)

        gdp_output_path = self.processed_intermediate_dir / "country_gdp_timeseries.csv"
        gdp_complete = ensure_string_year_columns(gdp_complete)
        gdp_complete.reset_index().to_csv(gdp_output_path, index=False)

        pop_output_path = (
            self.processed_intermediate_dir / "country_population_timeseries.csv"
        )
        population_complete = ensure_string_year_columns(population_complete)
        population_complete.reset_index().to_csv(pop_output_path, index=False)

        gini_output_path = (
            self.processed_intermediate_dir / "country_gini_stationary.csv"
        )
        gini_complete.reset_index().to_csv(gini_output_path, index=False)

        # Save world emissions if provided (RCB mode only)
        if world_emiss:
            for category, world_df in world_emiss.items():
                world_output_path = (
                    self.processed_intermediate_dir
                    / f"world_emissions_{category}_timeseries.csv"
                )
                # Reconstruct multi-index
                world_category_df = world_df.copy()
                world_category_df.index = pd.MultiIndex.from_tuples(
                    [("World", unit, cat) for _, unit, cat in world_df.index],
                    names=["iso3c", "unit", "emission-category"],
                )
                world_category_df = ensure_string_year_columns(world_category_df)
                world_category_df.reset_index().to_csv(world_output_path, index=False)


def run_rcb_preprocessing(
    config: dict[str, Any],
    source_id: str,
    active_sources: dict[str, str],
    emission_category: str,
) -> None:
    """Run RCB-based preprocessing pipeline.

    This function encapsulates the orchestration logic from
    notebooks/100_data_preprocess_rcbs.py.

    Args:
        config: Configuration dictionary
        source_id: Source identifier
        active_sources: Active source names
        emission_category: Emission category

    Raises
    ------
        ConfigurationError: If RCB config invalid
        DataLoadingError: If required data files missing
    """
    # Validate emission category for RCBs
    if emission_category != "co2-ffi":
        raise ConfigurationError(
            f"RCB-based budget allocations only support 'co2-ffi' emission category. "
            f"Got: {emission_category}. Please use target: 'ar6' or 'cr' "
            f"in your configuration for other emission categories."
        )

    # Initialize orchestrator
    orch = PreprocessingOrchestrator(
        config, source_id, active_sources, emission_category
    )

    # Load data
    emissions_data = orch.load_emissions_data()
    gdp = orch.load_gdp_data()
    population = orch.load_population_data()
    gini = orch.load_gini_data()

    # Validate loaded data
    for category, emiss_df in emissions_data.items():
        validate_emissions_data(emiss_df)
    validate_gdp_data(gdp)
    validate_population_data(population)
    validate_gini_data(gini)

    # Determine analysis countries
    analysis_years = [str(y) for y in range(1990, 2020)]
    country_iso3c = get_complete_iso3c_timeseries(
        emissions_data=emissions_data,
        gdp_data=gdp,
        population_data=population,
        gini_data=gini,
        years=analysis_years,
    )

    # Filter to analysis countries and add ROW
    emissions_complete = {}
    world_emiss = {}

    for category, emiss_df in emissions_data.items():
        # Get world totals (historical only for RCB mode)
        world_df = get_world_totals_timeseries(
            emiss_df, world_key=orch.emissions_world_key
        )
        world_emiss[category] = world_df

        # Filter to analysis countries
        country_df = emiss_df.loc[
            emiss_df.index.get_level_values("iso3c").isin(country_iso3c)
        ]

        # Add ROW
        row_df = add_row_timeseries(country_df, world_df)
        emissions_complete[category] = row_df

    # Filter GDP
    gdp_world = get_world_totals_timeseries(gdp, world_key=orch.gdp_world_key)
    gdp_country = gdp.loc[gdp.index.get_level_values("iso3c").isin(country_iso3c)]
    gdp_complete = add_row_timeseries(gdp_country, gdp_world)

    # Filter population
    pop_world_historical = get_world_totals_timeseries(
        population, world_key=orch.population_historical_world_key
    )
    pop_country = population.loc[
        population.index.get_level_values("iso3c").isin(country_iso3c)
    ]
    population_complete = add_row_timeseries(pop_country, pop_world_historical)

    # Filter Gini
    gini_complete = gini.loc[gini.index.get_level_values("iso3c").isin(country_iso3c)]

    # Validate totals
    validate_all_datasets_totals(
        emissions_complete, gdp_complete, population_complete, gini_complete
    )

    # Save processed data
    orch.save_processed_data(
        emissions_complete,
        gdp_complete,
        population_complete,
        gini_complete,
        world_emiss,
    )

    # Process and save RCB data
    _process_and_save_rcbs(orch, config, world_emiss[emission_category])


def run_pathway_preprocessing(
    config: dict[str, Any],
    source_id: str,
    active_sources: dict[str, str],
    emission_category: str,
) -> None:
    """Run pathway-based preprocessing pipeline.

    This function encapsulates the orchestration logic from
    notebooks/100_data_preprocess_pathways.py.

    Args:
        config: Configuration dictionary
        source_id: Source identifier
        active_sources: Active source names
        emission_category: Emission category

    Raises
    ------
        DataLoadingError: If required data files missing
    """
    # Initialize orchestrator
    orch = PreprocessingOrchestrator(
        config, source_id, active_sources, emission_category
    )

    # Load data
    emissions_data = orch.load_emissions_data()
    gdp = orch.load_gdp_data()
    population = orch.load_population_data()
    gini = orch.load_gini_data()

    # Load scenario data
    scenarios = _load_scenario_data(orch, emission_category)

    # Validate loaded data
    for category, emiss_df in emissions_data.items():
        validate_emissions_data(emiss_df)
    validate_gdp_data(gdp)
    validate_population_data(population)
    validate_gini_data(gini)
    validate_scenarios_data(scenarios)

    # Determine analysis countries
    analysis_years = [str(y) for y in range(1990, 2020)]
    country_iso3c = get_complete_iso3c_timeseries(
        emissions_data=emissions_data,
        gdp_data=gdp,
        population_data=population,
        gini_data=gini,
        years=analysis_years,
    )

    # Filter and add ROW (similar to RCB mode)
    emissions_complete = {}

    for category, emiss_df in emissions_data.items():
        world_df = get_world_totals_timeseries(
            emiss_df, world_key=orch.emissions_world_key
        )
        country_df = emiss_df.loc[
            emiss_df.index.get_level_values("iso3c").isin(country_iso3c)
        ]
        row_df = add_row_timeseries(country_df, world_df)
        emissions_complete[category] = row_df

    gdp_world = get_world_totals_timeseries(gdp, world_key=orch.gdp_world_key)
    gdp_country = gdp.loc[gdp.index.get_level_values("iso3c").isin(country_iso3c)]
    gdp_complete = add_row_timeseries(gdp_country, gdp_world)

    pop_world_historical = get_world_totals_timeseries(
        population, world_key=orch.population_historical_world_key
    )
    pop_country = population.loc[
        population.index.get_level_values("iso3c").isin(country_iso3c)
    ]
    population_complete = add_row_timeseries(pop_country, pop_world_historical)

    gini_complete = gini.loc[gini.index.get_level_values("iso3c").isin(country_iso3c)]

    # Validate totals
    validate_all_datasets_totals(
        emissions_complete, gdp_complete, population_complete, gini_complete
    )

    # Save processed data (no world emissions for pathway mode)
    orch.save_processed_data(
        emissions_complete, gdp_complete, population_complete, gini_complete
    )

    # Process and save scenario data
    _process_and_save_scenarios(orch, scenarios, orch.processed_intermediate_dir)


def _process_and_save_rcbs(
    orch: PreprocessingOrchestrator,
    config: dict[str, Any],
    world_emissions: pd.DataFrame,
) -> None:
    """Process RCB data and save to CSV.

    Args:
        orch: Orchestrator instance
        config: Configuration dict
        world_emissions: World emissions DataFrame for baseline
    """
    # Get RCB config
    rcb_config = config["targets"]["rcbs"]
    rcb_yaml_path = orch.project_root / rcb_config.get("path")

    if not rcb_yaml_path.exists():
        raise DataLoadingError(f"RCB YAML file not found: {rcb_yaml_path}")

    with open(rcb_yaml_path) as f:
        rcb_data = yaml.safe_load(f)

    # Get adjustment parameters
    rcb_data_params = rcb_config.get("data_parameters", {})
    rcb_adjustments = rcb_data_params.get("adjustments", {})
    bunkers_2020_2100 = rcb_adjustments.get("bunkers_2020_2100")
    lulucf_2020_2100 = rcb_adjustments.get("lulucf_2020_2100")

    # Ensure string year columns
    world_emissions = ensure_string_year_columns(world_emissions)

    # Process each RCB source
    rcb_records = []

    for source_key, source_data in rcb_data["rcb_data"].items():
        baseline_year = source_data.get("baseline_year")
        unit = source_data.get("unit", "Gt CO2")
        scenarios = source_data.get("scenarios", {})

        # Validate required fields
        if baseline_year is None:
            raise ConfigurationError(
                f"RCB source '{source_key}' missing required field 'baseline_year'"
            )
        if not scenarios:
            raise ConfigurationError(
                f"RCB source '{source_key}' has no scenarios defined"
            )

        # Process each scenario
        for scenario, rcb_value in scenarios.items():
            # Parse scenario format (e.g., "1.5p50")
            parts = scenario.split("p")
            if len(parts) != 2:
                raise ValueError(f"Invalid RCB scenario format: {scenario}")

            temperature = parts[0]
            probability = parts[1]
            climate_assessment = f"{temperature}C"
            quantile = str(int(probability) / 100)

            # Process to 2020 baseline
            result = process_rcb_to_2020_baseline(
                rcb_value=rcb_value,
                rcb_unit=unit,
                rcb_baseline_year=baseline_year,
                world_co2_ffi_emissions=world_emissions,
                bunkers_2020_2100=bunkers_2020_2100,
                lulucf_2020_2100=lulucf_2020_2100,
                target_baseline_year=2020,
                source_name=source_key,
                scenario=scenario,
                verbose=False,
            )

            # Create record
            record = {
                "source": source_key,
                "scenario": scenario,
                "climate-assessment": climate_assessment,
                "quantile": quantile,
                "emission-category": orch.emission_category,
                "baseline_year": baseline_year,
                "rcb_original_value": result["rcb_original_value"],
                "rcb_original_unit": result["rcb_original_unit"],
                "rcb_2020_mt": result["rcb_2020_mt"],
                "emissions_adjustment_mt": result["emissions_adjustment_mt"],
                "bunkers_adjustment_mt": result["bunkers_adjustment_mt"],
                "lulucf_adjustment_mt": result["lulucf_adjustment_mt"],
                "total_adjustment_mt": result["total_adjustment_mt"],
            }

            rcb_records.append(record)

    # Save to CSV
    rcb_df = pd.DataFrame(rcb_records)
    rcb_output_path = orch.processed_intermediate_dir / "rcbs.csv"
    rcb_df.to_csv(rcb_output_path, index=False)


def _load_scenario_data(
    orch: PreprocessingOrchestrator, emission_category: str
) -> pd.DataFrame:
    """Load scenario data from intermediate directory.

    Args:
        orch: Orchestrator instance
        emission_category: Emission category

    Returns
    -------
        Scenario DataFrame

    Raises
    ------
        DataLoadingError: If scenario file not found
    """
    scenario_path = (
        orch.processed_intermediate_dir.parent / f"scenarios_{emission_category}.csv"
    )

    if not scenario_path.exists():
        raise DataLoadingError(
            f"Scenario file not found: {scenario_path}. "
            "Ensure the scenario preprocessing notebook has been run successfully."
        )

    scenarios = pd.read_csv(scenario_path)
    scenarios = scenarios.set_index(["Model", "Scenario", "Region", "Variable", "Unit"])
    scenarios = ensure_string_year_columns(scenarios)

    return scenarios


def _process_and_save_scenarios(
    orch: PreprocessingOrchestrator,
    scenarios: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Process scenario data and save to CSV.

    Args:
        orch: Orchestrator instance
        scenarios: Scenario DataFrame
        output_dir: Output directory path
    """
    # Set post-net-zero emissions to NaN
    scenarios_processed = set_post_net_zero_emissions_to_nan(scenarios)

    # Save processed scenarios
    scenario_output_path = output_dir / f"scenarios_{orch.emission_category}.csv"
    scenarios_processed = ensure_string_year_columns(scenarios_processed)
    scenarios_processed.reset_index().to_csv(scenario_output_path, index=False)
