"""Configuration loading for preprocessing notebooks."""

from pathlib import Path
from typing import Any

import yaml
from pyprojroot import here

from fair_shares.library.utils import build_source_id
from fair_shares.library.utils.data.config import build_data_config


def load_preprocessing_config(
    emission_category: str | None,
    active_target_source: str | None,
    active_emissions_source: str | None,
    active_gdp_source: str | None,
    active_population_source: str | None,
    active_gini_source: str | None,
) -> tuple[dict[str, Any], str, Path]:
    """Load preprocessing configuration from Papermill parameters or interactive defaults.

    Args:
        emission_category: Emission category (e.g., "co2-ffi", "all-ghg-ex-co2-lulucf")
        active_target_source: Target source (e.g., "rcbs", "ar6")
        active_emissions_source: Emissions source (e.g., "primap-202503")
        active_gdp_source: GDP source (e.g., "wdi-2025")
        active_population_source: Population source (e.g., "un-owid-2025")
        active_gini_source: Gini source (e.g., "unu-wider-2025")

    Returns
    -------
        Tuple of (config dict, source_id string, project_root Path)
    """
    project_root = here()

    if emission_category is not None:
        # Running via Papermill - load composed config
        print("Running via Papermill")

        source_id = build_source_id(
            emissions=active_emissions_source,
            gdp=active_gdp_source,
            population=active_population_source,
            gini=active_gini_source,
            target=active_target_source,
            emission_category=emission_category,
        )

        config_path = project_root / f"output/{source_id}/config.yaml"
        print(f"Loading config from: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

    else:
        # Running interactively - build config programmatically
        print("Running interactively - build desired config")

        # Default interactive configuration
        emission_category = "co2-ffi"
        active_sources = {
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "unu-wider-2025",
            "target": "rcbs",
        }

        config, source_id = build_data_config(emission_category, active_sources)
        # Convert Pydantic model to dict for consistency with pipeline
        config = config.model_dump()

    return config, source_id, project_root
