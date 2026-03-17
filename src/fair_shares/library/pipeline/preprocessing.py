"""Orchestration logic for data preprocessing pipelines.

This module extracts the orchestration logic from notebooks to make it
reusable and testable. Notebooks should call these functions rather than
duplicating the logic.
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from pyprojroot import here

from ..exceptions import ConfigurationError, DataLoadingError
from ..preprocessing.loaders import (
    load_emissions_data as _load_emissions,
)
from ..preprocessing.loaders import (
    load_gdp_data as _load_gdp,
)
from ..preprocessing.loaders import (
    load_gini_data as _load_gini,
)
from ..preprocessing.loaders import (
    load_population_data as _load_population,
)
from ..utils import (
    add_row_timeseries,
    determine_processing_categories,
    ensure_string_year_columns,
    get_complete_iso3c_timeseries,
    get_world_totals_timeseries,
    set_post_net_zero_emissions_to_nan,
)
from ..utils.data.config import (
    get_co2_component,
    is_composite_category,
)
from ..utils.data.non_co2 import NON_CO2_CATEGORY
from ..validation import (
    validate_all_datasets_totals,
    validate_emissions_data,
    validate_gdp_data,
    validate_gini_data,
    validate_population_data,
    validate_scenarios_data,
)

logger = logging.getLogger(__name__)

# Cache project root at module level to avoid repeated filesystem traversal
_PROJECT_ROOT: Path = here()


class DataPreprocessor:
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
        self.project_root = _PROJECT_ROOT

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

        Delegates to ``preprocessing.loaders.load_emissions_data``.
        """
        return _load_emissions(self.emiss_intermediate_dir, self.final_categories)

    def load_gdp_data(self) -> pd.DataFrame:
        """Load GDP data.

        Delegates to ``preprocessing.loaders.load_gdp_data``.
        """
        return _load_gdp(self.gdp_intermediate_dir)

    def load_population_data(self) -> pd.DataFrame:
        """Load population data.

        Delegates to ``preprocessing.loaders.load_population_data``.
        """
        return _load_population(self.pop_intermediate_dir)

    def load_gini_data(self) -> pd.DataFrame:
        """Load Gini coefficient data.

        Delegates to ``preprocessing.loaders.load_gini_data``.
        """
        return _load_gini(self.gini_intermediate_dir)

    def determine_analysis_countries(
        self,
        emissions_data: dict[str, pd.DataFrame],
        gdp: pd.DataFrame,
        population: pd.DataFrame,
        gini: pd.DataFrame,
    ) -> set[str]:
        """Determine the set of analysis countries with complete data.

        Args:
            emissions_data: Dict of emission DataFrames by category
            gdp: GDP DataFrame
            population: Population DataFrame
            gini: Gini DataFrame

        Returns
        -------
            Set of iso3c country codes present in all datasets with complete data
        """
        # Get complete country list across all datasets
        # Call once per dataset and intersect results
        complete_sets = []

        for emiss_df in emissions_data.values():
            complete_sets.append(
                get_complete_iso3c_timeseries(
                    emiss_df,
                    expected_index_names=["iso3c", "unit", "emission-category"],
                )
            )

        complete_sets.append(
            get_complete_iso3c_timeseries(
                gdp,
                expected_index_names=["iso3c", "unit"],
            )
        )

        complete_sets.append(
            get_complete_iso3c_timeseries(
                population,
                expected_index_names=["iso3c", "unit"],
            )
        )

        country_iso3c = complete_sets[0].intersection(*complete_sets[1:])

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


def _run_common_preprocessing(
    config: dict[str, Any],
    source_id: str,
    active_sources: dict[str, str],
    emission_category: str,
) -> tuple[
    DataPreprocessor,
    dict[str, pd.DataFrame],
    dict[str, pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Run the preprocessing steps shared by RCB and pathway pipelines.

    Initializes the orchestrator, loads and validates all core datasets
    (emissions, GDP, population, Gini), determines analysis countries,
    filters each dataset to those countries, adds Rest-of-World rows,
    validates totals, and returns everything needed for mode-specific
    final steps.

    Parameters
    ----------
    config : dict[str, Any]
        Configuration dictionary from ``build_data_config``.
    source_id : str
        Source identifier string.
    active_sources : dict[str, str]
        Active source names dict.
    emission_category : str
        Emission category (e.g. ``"co2-ffi"``).

    Returns
    -------
    tuple
        ``(orch, emissions_complete, world_emiss, gdp_complete,
        population_complete, gini_complete)`` where *world_emiss* maps
        each emission category to its world-total DataFrame.
    """
    # Initialize orchestrator
    orch = DataPreprocessor(config, source_id, active_sources, emission_category)

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

    country_iso3c = orch.determine_analysis_countries(
        emissions_data, gdp, population, gini
    )

    # Filter emissions to analysis countries and add ROW
    emissions_complete: dict[str, pd.DataFrame] = {}
    world_emiss: dict[str, pd.DataFrame] = {}

    for category, emiss_df in emissions_data.items():
        world_df = get_world_totals_timeseries(
            emiss_df,
            world_key=orch.emissions_world_key,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )
        world_emiss[category] = world_df

        country_df = emiss_df.loc[
            emiss_df.index.get_level_values("iso3c").isin(country_iso3c)
        ]
        row_df = add_row_timeseries(
            country_df,
            country_iso3c,
            world_df,
            expected_index_names=["iso3c", "unit", "emission-category"],
        )
        emissions_complete[category] = row_df

    # Filter GDP
    gdp_world = get_world_totals_timeseries(
        gdp,
        world_key=orch.gdp_world_key,
        expected_index_names=["iso3c", "unit"],
    )
    gdp_country = gdp.loc[gdp.index.get_level_values("iso3c").isin(country_iso3c)]
    gdp_complete = add_row_timeseries(
        gdp_country,
        country_iso3c,
        gdp_world,
        expected_index_names=["iso3c", "unit"],
    )

    # Filter population
    pop_world_historical = get_world_totals_timeseries(
        population,
        world_key=orch.population_historical_world_key,
        expected_index_names=["iso3c", "unit"],
    )
    pop_country = population.loc[
        population.index.get_level_values("iso3c").isin(country_iso3c)
    ]
    population_complete = add_row_timeseries(
        pop_country,
        country_iso3c,
        pop_world_historical,
        expected_index_names=["iso3c", "unit"],
    )

    # Filter Gini
    gini_complete = gini.loc[gini.index.get_level_values("iso3c").isin(country_iso3c)]

    # Validate totals
    validate_all_datasets_totals(
        emissions_complete, gdp_complete, population_complete, gini_complete
    )

    return (
        orch,
        emissions_complete,
        world_emiss,
        gdp_complete,
        population_complete,
        gini_complete,
    )


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
    if emission_category not in ("co2-ffi", "co2"):
        raise ConfigurationError(
            f"RCB-based budget allocations only support 'co2-ffi' and 'co2' emission "
            f"categories. Got: {emission_category}. Please use target: 'pathway' "
            f"in your configuration for other emission categories."
        )

    (
        orch,
        emissions_complete,
        world_emiss,
        gdp_complete,
        population_complete,
        gini_complete,
    ) = _run_common_preprocessing(config, source_id, active_sources, emission_category)

    # For total CO2, construct NGHGI-consistent world timeseries
    if emission_category == "co2":
        # Build AdjustmentsConfig for loading shared timeseries
        from ..config.models import AdjustmentsConfig
        from ..preprocessing.rcbs import _load_shared_timeseries
        from ..utils.data.nghgi import build_nghgi_world_co2_timeseries

        rcb_config = config["targets"]["rcbs"]
        rcb_data_params = rcb_config.get("data_parameters", {})
        rcb_adjustments_raw = rcb_data_params.get("adjustments", {})
        adjustments_config = AdjustmentsConfig.model_validate(rcb_adjustments_raw)

        nghgi_ts, bunker_ts, _splice_year = _load_shared_timeseries(
            adjustments_config, orch.project_root, source_id=source_id, verbose=True
        )

        if "co2-lulucf" not in world_emiss:
            raise DataLoadingError(
                "LULUCF world emissions ('co2-lulucf') required for total CO2 "
                "NGHGI-consistent budgets but not found in emissions data."
            )

        world_emiss["co2"] = build_nghgi_world_co2_timeseries(
            fossil_ts=world_emiss["co2-ffi"],
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=world_emiss["co2-lulucf"],
        )

    # Save processed data
    orch.save_processed_data(
        emissions_complete,
        gdp_complete,
        population_complete,
        gini_complete,
        world_emiss,
    )

    # Process and save RCB data — always pass PRIMAP fossil (co2-ffi);
    # for total CO2, also pass BM LULUCF for rebase inside load_and_process_rcbs
    _process_and_save_rcbs(
        orch,
        config,
        world_fossil_emissions=world_emiss["co2-ffi"],
        actual_bm_lulucf_emissions=world_emiss.get("co2-lulucf"),
    )


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
    (
        orch,
        emissions_complete,
        _world_emiss,
        gdp_complete,
        population_complete,
        gini_complete,
    ) = _run_common_preprocessing(config, source_id, active_sources, emission_category)

    # Load and validate scenario data (pathway-specific)
    scenarios = _load_scenario_data(orch, emission_category)
    validate_scenarios_data(scenarios)

    # Save processed data (no world emissions for pathway mode)
    orch.save_processed_data(
        emissions_complete, gdp_complete, population_complete, gini_complete
    )

    # Process and save scenario data
    _process_and_save_scenarios(orch, scenarios, orch.processed_intermediate_dir)


def _process_and_save_rcbs(
    orch: DataPreprocessor,
    config: dict[str, Any],
    world_fossil_emissions: pd.DataFrame,
    actual_bm_lulucf_emissions: pd.DataFrame | None = None,
) -> None:
    """Process RCB data and save to CSV.

    Delegates to load_and_process_rcbs() which handles both legacy scalar
    constants and timeseries-based NGHGI-consistent adjustments.

    Args:
        orch: Orchestrator instance
        config: Configuration dict
        world_fossil_emissions: PRIMAP fossil world emissions (co2-ffi)
        actual_bm_lulucf_emissions: BM LULUCF world emissions for co2 rebase
    """
    from ..config.models import AdjustmentsConfig
    from ..preprocessing.rcbs import load_and_process_rcbs

    # Get RCB config
    rcb_config = config["targets"]["rcbs"]
    rcb_yaml_path = orch.project_root / rcb_config.get("path")

    # Build AdjustmentsConfig from the YAML config dict
    rcb_data_params = rcb_config.get("data_parameters", {})
    rcb_adjustments_raw = rcb_data_params.get("adjustments", {})
    adjustments_config = AdjustmentsConfig.model_validate(rcb_adjustments_raw)

    rcb_df = load_and_process_rcbs(
        rcb_yaml_path=rcb_yaml_path,
        world_fossil_emissions=world_fossil_emissions,
        emission_category=orch.emission_category,
        adjustments_config=adjustments_config,
        project_root=orch.project_root,
        source_id=orch.source_id,
        actual_bm_lulucf_emissions=actual_bm_lulucf_emissions,
        verbose=False,
    )

    # Save to CSV
    rcb_output_path = (
        orch.processed_intermediate_dir / f"rcbs_{orch.emission_category}.csv"
    )
    rcb_df.to_csv(rcb_output_path, index=False)


def _load_scenario_data(orch: DataPreprocessor, emission_category: str) -> pd.DataFrame:
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

    try:
        scenarios = pd.read_csv(scenario_path)
    except FileNotFoundError:
        raise DataLoadingError(
            f"Scenario file not found: {scenario_path}. "
            "Ensure the scenario preprocessing notebook has been run successfully."
        ) from None
    scenarios = scenarios.set_index(["Model", "Scenario", "Region", "Variable", "Unit"])
    scenarios = ensure_string_year_columns(scenarios)

    return scenarios


def _process_and_save_scenarios(
    orch: DataPreprocessor,
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
    scenarios_processed, _ = set_post_net_zero_emissions_to_nan(
        scenarios, orch.emission_category
    )

    # Save processed scenarios
    scenario_output_path = output_dir / f"scenarios_{orch.emission_category}.csv"
    scenarios_processed = ensure_string_year_columns(scenarios_processed)
    scenarios_processed.reset_index().to_csv(scenario_output_path, index=False)


def get_allocation_output_dir(
    base_output_dir: Path,
    target_source: str,
    gas: str,
    emission_category: str = "co2-ffi",
) -> Path:
    """Return the appropriate output subdirectory for a given target and gas.

    For all-GHG runs (``emission_category="all-ghg"``), results are split into
    ``co2/`` and ``non-co2/`` subdirectories to keep the two gases separate.
    For all other runs the base directory is returned unchanged.

    Parameters
    ----------
    base_output_dir : Path
        Root allocations folder, e.g. ``output/<source_id>/allocations/<folder>/``.
    target_source : str
        Active target source (e.g. ``"pathway"``, ``"rcbs"``).
    gas : str
        Which gas subdirectory to return: ``"co2"`` or ``"non-co2"``.
    emission_category : str, default "co2-ffi"
        Original emission category. When "all-ghg", subdirectory split is used.

    Returns
    -------
    Path
        Output directory.  Created if it does not exist.

    Raises
    ------
    ValueError
        If ``gas`` is not ``"co2"`` or ``"non-co2"``.
    """
    _valid_gases = {"co2", NON_CO2_CATEGORY}
    if gas not in _valid_gases:
        raise ValueError(f"gas must be one of {_valid_gases}, got '{gas}'")

    if is_composite_category(emission_category):
        out_dir = base_output_dir / gas
    else:
        # Backward-compatible: single gas, no subdirectory split
        out_dir = base_output_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def run_non_co2_preprocessing(
    config: dict[str, Any],
    source_id: str,
    active_sources: dict[str, str],
    emission_category: str,
) -> None:
    """Derive non-CO2 emissions and scenarios by subtraction, then preprocess.

    non-CO2 = all-ghg-ex-co2-lulucf - co2-ffi

    Both historical (PRIMAP) and scenario (AR6) data are derived by subtraction
    from their respective parent categories.  The derived data is saved as
    intermediate files so that ``run_pathway_preprocessing("non-co2")`` can
    load and process it through the standard pipeline.

    Parameters
    ----------
    config : dict[str, Any]
        Configuration dictionary from ``build_data_config``.
    source_id : str
        Source identifier string.
    active_sources : dict[str, str]
        Active source names dict.
    emission_category : str
        The composite emission category (``"all-ghg"`` or
        ``"all-ghg-ex-co2-lulucf"``).  Used to locate the parent data files.
    """
    from ..utils.data.non_co2 import derive_non_co2_country_timeseries
    from ..utils.dataframes import get_year_columns

    project_root = _PROJECT_ROOT
    base_dir = project_root / f"output/{source_id}/intermediate"
    emiss_dir = base_dir / "emissions"

    # ------------------------------------------------------------------
    # Step 1: Derive non-CO2 historical emissions
    # ------------------------------------------------------------------
    co2_ffi = pd.read_csv(emiss_dir / "emiss_co2-ffi_timeseries.csv")
    co2_ffi = co2_ffi.set_index(["iso3c", "unit", "emission-category"])
    co2_ffi = ensure_string_year_columns(co2_ffi)

    allghg_ex = pd.read_csv(emiss_dir / "emiss_all-ghg-ex-co2-lulucf_timeseries.csv")
    allghg_ex = allghg_ex.set_index(["iso3c", "unit", "emission-category"])
    allghg_ex = ensure_string_year_columns(allghg_ex)

    non_co2 = derive_non_co2_country_timeseries(allghg_ex, co2_ffi)
    non_co2.reset_index().to_csv(
        emiss_dir / "emiss_non-co2_timeseries.csv", index=False
    )

    # ------------------------------------------------------------------
    # Step 2: Derive non-CO2 scenarios from AR6
    #
    # Load AR6 scenario files for co2-ffi and all-ghg-ex-co2-lulucf,
    # subtract to get non-CO2 scenarios, and save for the pathway pipeline.
    # ------------------------------------------------------------------
    scenario_dir = base_dir  # scenarios_{cat}.csv lives directly under intermediate/
    co2_ffi_scenario_path = scenario_dir / "scenarios_co2-ffi.csv"
    allghg_ex_scenario_path = scenario_dir / "scenarios_all-ghg-ex-co2-lulucf.csv"

    if co2_ffi_scenario_path.exists() and allghg_ex_scenario_path.exists():
        scenario_index_cols = [
            "Model",
            "Scenario",
            "Region",
            "Variable",
            "Unit",
        ]

        co2_ffi_scenarios = pd.read_csv(co2_ffi_scenario_path)
        co2_ffi_scenarios = co2_ffi_scenarios.set_index(scenario_index_cols)
        co2_ffi_scenarios = ensure_string_year_columns(co2_ffi_scenarios)

        allghg_ex_scenarios = pd.read_csv(allghg_ex_scenario_path)
        allghg_ex_scenarios = allghg_ex_scenarios.set_index(scenario_index_cols)
        allghg_ex_scenarios = ensure_string_year_columns(allghg_ex_scenarios)

        # Align on shared index rows and year columns
        shared_idx = allghg_ex_scenarios.index.intersection(co2_ffi_scenarios.index)
        shared_years = sorted(
            set(get_year_columns(allghg_ex_scenarios))
            & set(get_year_columns(co2_ffi_scenarios))
        )

        non_co2_scenarios = (
            allghg_ex_scenarios.loc[shared_idx, shared_years]
            - co2_ffi_scenarios.loc[shared_idx, shared_years]
        )

        # Update the Variable level to reflect non-co2
        new_index = pd.MultiIndex.from_tuples(
            [
                (model, scenario, region, NON_CO2_CATEGORY, unit)
                for model, scenario, region, _var, unit in non_co2_scenarios.index
            ],
            names=scenario_index_cols,
        )
        non_co2_scenarios.index = new_index

        non_co2_scenarios.reset_index().to_csv(
            scenario_dir / "scenarios_non-co2.csv", index=False
        )
    else:
        missing = [
            p
            for p in (co2_ffi_scenario_path, allghg_ex_scenario_path)
            if not p.exists()
        ]
        logger.warning(
            "Skipping non-CO2 scenario derivation: missing %s",
            ", ".join(str(p) for p in missing),
        )

    # ------------------------------------------------------------------
    # Step 3: Run pathway preprocessing on derived non-CO2 data
    # ------------------------------------------------------------------
    run_pathway_preprocessing(config, source_id, active_sources, NON_CO2_CATEGORY)


def run_composite_preprocessing(
    config: dict[str, Any],
    source_id: str,
    active_sources: dict[str, str],
    emission_category: str = "all-ghg",
) -> None:
    """Run preprocessing for composite emission categories.

    Handles both ``"all-ghg"`` and ``"all-ghg-ex-co2-lulucf"`` by decomposing
    them into a CO2 component (target-specific) and a non-CO2 component
    (always AR6 pathway-based).

    Preprocessing strategy depends on the target:

    - **pathway**: single pass — ``run_pathway_preprocessing(emission_category)``
      (pathway target has direct data for composite categories).

    - **RCBs**: 2 passes:
      1. ``run_rcb_preprocessing(co2_component)`` for the CO2 budget
      2. ``run_non_co2_preprocessing(emission_category)`` for non-CO2

    - **rcb-pathways**: 2 passes:
      1. ``run_pathway_preprocessing(co2_component)`` for CO2 pathways
      2. ``run_non_co2_preprocessing(emission_category)`` for non-CO2

    Parameters
    ----------
    config : dict[str, Any]
        Configuration dictionary from ``build_data_config``.
    source_id : str
        Source identifier string.
    active_sources : dict[str, str]
        Active source names dict (must include ``"target"``).
    emission_category : str, default "all-ghg"
        Must be a composite category (``"all-ghg"`` or
        ``"all-ghg-ex-co2-lulucf"``).

    Raises
    ------
    ConfigurationError
        If emission_category is not a composite category.
    DataLoadingError
        If required input files are missing.
    """
    if not is_composite_category(emission_category):
        raise ConfigurationError(
            f"run_composite_preprocessing() requires a composite emission category "
            f"('all-ghg' or 'all-ghg-ex-co2-lulucf'). "
            f"Got emission_category='{emission_category}'. "
            f"Use run_pathway_preprocessing() or run_rcb_preprocessing() instead."
        )

    target_source = active_sources.get("target", "")

    if target_source == "pathway":
        # pathway target has direct data for composite categories — single pass
        run_pathway_preprocessing(config, source_id, active_sources, emission_category)
        return

    # RCB or rcb-pathways: decompose into CO2 + non-CO2
    co2_component = get_co2_component(emission_category)

    # Pass 1: CO2 component — target-specific
    if target_source == "rcbs":
        run_rcb_preprocessing(config, source_id, active_sources, co2_component)
    else:
        # rcb-pathways: pathway preprocessing for CO2
        run_pathway_preprocessing(config, source_id, active_sources, co2_component)

    # Pass 2: Non-CO2 — derived by subtraction, then pathway-processed
    run_non_co2_preprocessing(config, source_id, active_sources, emission_category)
