"""
Configuration building and validation utilities.

This module handles data source configuration management, including building
configuration objects from YAML files, validating source compatibility, and
generating source identifiers.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml

from fair_shares.library.config.models import DataSourcesConfig
from fair_shares.library.exceptions import (
    ConfigurationError,
    DataLoadingError,
)

if TYPE_CHECKING:
    pass


def build_source_id(
    *,
    emissions: str,
    gdp: str,
    population: str,
    gini: str,
    target: str,
    emission_category: str,
    rcb_generator: str | None = None,
) -> str:
    """Construct standardized source identifier used for output directories.

    Parameters are keyword-only to avoid ordering mistakes.

    For rcb-pathways targets, the generator name is appended to the target
    (e.g., "rcb-pathways-exponential-decay") to create separate output
    directories for different generators.

    Parameters
    ----------
    emissions : str
        Emissions source identifier
    gdp : str
        GDP source identifier
    population : str
        Population source identifier
    gini : str
        Gini source identifier
    target : str
        Target source (e.g., "ar6", "rcbs", "rcb-pathways")
    emission_category : str
        Emission category (e.g., "co2-ffi", "all-ghg")
    rcb_generator : str | None, optional
        RCB pathway generator name (only used for target="rcb-pathways")

    Returns
    -------
    str
        Source identifier string
    """
    # For rcb-pathways, append generator to target name (default to exponential-decay)
    if target == "rcb-pathways":
        if rcb_generator is None:
            rcb_generator = "exponential-decay"
        target_with_generator = f"{target}-{rcb_generator}"
    else:
        target_with_generator = target

    return "_".join(
        [
            emissions,
            gdp,
            population,
            gini,
            target_with_generator,
            emission_category,
        ]
    )


def build_source_id_from_config(config: dict[str, Any]) -> str:
    """Construct source_id directly from a loaded unified config dict.

    Expects keys set per build_data_config output: ``active_emissions_source``,
    ``active_gdp_source``, ``active_population_source``, ``active_gini_source``,
    ``active_target_source``, ``emission_category``, and optionally ``rcb_generator``.

    Parameters
    ----------
    config : dict[str, Any]
        Configuration dictionary with active source keys

    Returns
    -------
    str
        Source identifier string
    """
    return build_source_id(
        emissions=config["active_emissions_source"],
        gdp=config["active_gdp_source"],
        population=config["active_population_source"],
        gini=config["active_gini_source"],
        target=config["active_target_source"],
        emission_category=config["emission_category"],
        rcb_generator=config.get("rcb_generator"),
    )


def build_data_config(
    emission_category: Literal["co2-ffi", "all-ghg", "all-ghg-ex-co2-lulucf"],
    active_sources: dict[str, str],
    config_path: Path | None = None,
    harmonisation_year: int | None = None,
) -> tuple[DataSourcesConfig, str]:
    """
    Build and validate data configuration from unified config file.

    Loads the unified YAML config, filters by emission category and target,
    sets active sources, and validates with Pydantic.

    Parameters
    ----------
    emission_category : Literal["co2-ffi", "all-ghg", "all-ghg-ex-co2-lulucf"]
        Emission category to filter for
    active_sources : dict[str, str]
        Dictionary of active source names with keys:
        - "emissions": emissions source (e.g., "primap-202503")
        - "gdp": GDP source (e.g., "wdi-2025")
        - "population": population source (e.g., "un-owid-2025")
        - "gini": Gini source (e.g., "unu-wider-2025")
        - "target": target source (e.g., "ar6", "rcbs", "rcb-pathways")
        - "rcb_generator": (optional) pathway generator for rcb-pathways
          (e.g., "exponential-decay"). Only used when target="rcb-pathways".
    config_path : Path | None, optional
        Path to unified config file. If None, uses default location.
    harmonisation_year : int | None, optional
        Year for global scenario harmonisation. If None, will use value from config YAML
        if available, otherwise raise an error.

    Returns
    -------
    tuple[DataSourcesConfig, str]
        Tuple of (validated Pydantic model with filtered configuration, source_id)

    Raises
    ------
    DataLoadingError
        If config file not found or invalid
    ValueError
        If emission_category not available in selected target
    ConfigurationError
        If rcb_generator specified for non-rcb-pathways target or invalid generator
    """
    # Determine config path
    if config_path is None:
        # Default to unified config in conf/data_sources/
        from pyprojroot import here

        project_root = here()
        config_path = (
            project_root / "conf" / "data_sources" / "data_sources_unified.yaml"
        )

    # Load unified YAML
    if not config_path.exists():
        raise DataLoadingError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        full_config = yaml.safe_load(f)

    # Extract target name
    target = active_sources.get("target")
    if not target:
        raise ConfigurationError("active_sources must include 'target' key")

    # Filter targets to only the selected one
    if target not in full_config.get("targets", {}):
        available_targets = list(full_config.get("targets", {}).keys())
        raise ConfigurationError(
            f"Target '{target}' not found in config. Available: {available_targets}"
        )

    selected_target = {target: full_config["targets"][target]}

    # Validate emission category is available in selected target
    target_config = selected_target[target]
    available_categories = target_config.get("data_parameters", {}).get(
        "available_categories", []
    )
    if emission_category not in available_categories:
        raise ConfigurationError(
            f"Emission category '{emission_category}' not available "
            f"in target '{target}'. Available: {available_categories}"
        )

    # Validate and process rcb_generator parameter
    rcb_generator = active_sources.get("rcb_generator")

    if target == "rcb-pathways":
        # For rcb-pathways target, validate and default the generator
        if rcb_generator is None:
            rcb_generator = "exponential-decay"  # Default generator

        # Validate against available generators
        from fair_shares.library.utils.math.pathways import list_pathway_generators

        available_generators = list_pathway_generators()

        if rcb_generator not in available_generators:
            raise ConfigurationError(
                f"Invalid rcb_generator: '{rcb_generator}'. "
                f"Available generators: {available_generators}"
            )
    elif rcb_generator is not None:
        # rcb_generator specified but target is not rcb-pathways
        raise ConfigurationError(
            f"rcb_generator parameter is only valid for target='rcb-pathways', "
            f"but target='{target}' was specified. Remove rcb_generator or use "
            f"target='rcb-pathways'."
        )

    # Determine harmonisation_year: only needed for scenario-based targets, not for RCBs
    # Any target that isn't "rcbs" is assumed scenario-based and needs harmonisation
    final_harmonisation_year = None

    if target != "rcbs":
        # For scenario-based targets, harmonisation_year is required
        if harmonisation_year is not None:
            final_harmonisation_year = harmonisation_year
        else:
            # Try to get from config YAML
            config_harmonisation_year = full_config.get("harmonisation_year")
            if config_harmonisation_year is not None:
                final_harmonisation_year = config_harmonisation_year
            else:
                # Raise error if not provided and not in config
                raise ConfigurationError(
                    f"harmonisation_year is required for scenario-based targets "
                    f"(target='{target}'). "
                    "Please provide it in notebook 301 or in the config YAML file."
                )
    # For RCBs, harmonisation_year is not needed - leave it as None

    # Build filtered config dict
    filtered_config = {
        "emission_category": emission_category,
        "emissions": full_config.get("emissions", {}),
        "gdp": full_config.get("gdp", {}),
        "population": full_config.get("population", {}),
        "gini": full_config.get("gini", {}),
        "targets": selected_target,
        "general": full_config.get("general", {}),
        "harmonisation_year": final_harmonisation_year,
        # Set active sources
        "active_emissions_source": active_sources.get("emissions"),
        "active_gdp_source": active_sources.get("gdp"),
        "active_population_source": active_sources.get("population"),
        "active_gini_source": active_sources.get("gini"),
        "active_target_source": target,
        "rcb_generator": rcb_generator,  # Will be None for non-rcb-pathways targets
    }

    # Validate with Pydantic (this will raise ValidationError if invalid)
    validated_config = DataSourcesConfig(**filtered_config)

    # Build source_id directly from the active sources
    source_id = build_source_id(
        emissions=active_sources.get("emissions"),
        gdp=active_sources.get("gdp"),
        population=active_sources.get("population"),
        gini=active_sources.get("gini"),
        target=target,
        emission_category=emission_category,
        rcb_generator=rcb_generator,
    )

    return validated_config, source_id


def get_compatible_approaches(target: str) -> list[str]:
    """
    Return allocation approaches compatible with the given target type.

    Budget approaches (ending with "-budget") are compatible with "rcbs" target.
    Pathway approaches (not ending with "-budget") are compatible with scenario
    targets ("ar6", "rcb-pathways").

    Parameters
    ----------
    target : str
        Target source type: "rcbs", "ar6", or "rcb-pathways"

    Returns
    -------
    list[str]
        List of compatible allocation approach names

    Examples
    --------
    >>> get_compatible_approaches("rcbs")
    ['equal-per-capita-budget', 'per-capita-adjusted-budget', ...]

    >>> get_compatible_approaches("ar6")
    ['equal-per-capita', 'per-capita-adjusted', ...]
    """
    # Budget approaches - compatible with RCB targets
    budget_approaches = [
        "equal-per-capita-budget",
        "per-capita-adjusted-budget",
        "per-capita-adjusted-gini-budget",
    ]

    # Pathway approaches - compatible with scenario targets
    pathway_approaches = [
        "equal-per-capita",
        "per-capita-adjusted",
        "per-capita-adjusted-gini",
        "per-capita-convergence",
        "cumulative-per-capita-convergence",
        "cumulative-per-capita-convergence-adjusted",
        "cumulative-per-capita-convergence-gini-adjusted",
    ]

    if target == "rcbs":
        return budget_approaches
    elif target in ["ar6", "rcb-pathways"]:
        return pathway_approaches
    else:
        # Unknown target - return all approaches with a warning
        return budget_approaches + pathway_approaches


def validate_data_source_config(
    emission_category: str,
    active_sources: dict[str, str],
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Validate data source configuration before running pipeline.

    Checks that:
    1. Config file exists and loads correctly
    2. Emission category is valid for the selected target
    3. All required source keys are present
    4. Returns compatible allocation approaches

    Parameters
    ----------
    emission_category : str
        Emission category to validate (e.g., "co2-ffi", "all-ghg")
    active_sources : dict[str, str]
        Dictionary with keys: "emissions", "gdp", "population", "gini", "target"
    verbose : bool, default=True
        If True, print validation progress and results

    Returns
    -------
    dict[str, Any]
        Dictionary with keys:
        - "valid": bool - True if configuration is valid
        - "issues": list[str] - List of validation issues (empty if valid)
        - "compatible_approaches": list[str] - Approaches compatible with target
        - "target_type": str - "budget" or "pathway"

    Examples
    --------
    >>> result = validate_data_source_config(
    ...     emission_category="co2-ffi",
    ...     active_sources={
    ...         "emissions": "primap-202503",
    ...         "gdp": "wdi-2025",
    ...         "population": "un-owid-2025",
    ...         "gini": "unu-wider-2025",
    ...         "target": "rcbs",
    ...     },
    ... )
    >>> result["valid"]
    True
    >>> "equal-per-capita-budget" in result["compatible_approaches"]
    True
    """
    issues = []

    # Check required keys
    required_keys = ["emissions", "gdp", "population", "gini", "target"]
    missing_keys = [k for k in required_keys if k not in active_sources]
    if missing_keys:
        issues.append(f"Missing required keys in active_sources: {missing_keys}")

    # Try to build config to validate paths and emission category
    if not missing_keys:
        try:
            # This validates paths exist and emission category is available
            config, source_id = build_data_config(
                emission_category=emission_category,
                active_sources=active_sources,
            )
            if verbose:
                print("[OK] Configuration loaded successfully")
                print(f"  Source ID: {source_id}")
        except (DataLoadingError, ConfigurationError, ValueError) as e:
            issues.append(str(e))

    # Get compatible approaches
    target = active_sources.get("target", "")
    compatible_approaches = get_compatible_approaches(target)

    # Determine target type
    if target == "rcbs":
        target_type = "budget"
    elif target in ["ar6", "rcb-pathways"]:
        target_type = "pathway"
    else:
        target_type = "unknown"
        if target:
            issues.append(
                f"Unknown target type: '{target}'. Expected: rcbs, ar6, or rcb-pathways"
            )

    # Print summary
    if verbose and not issues:
        print(
            f"[OK] Emission category '{emission_category}' is valid for target '{target}'"
        )
        print(f"[OK] Target type: {target_type}")
        print(f"[OK] Compatible approaches: {len(compatible_approaches)} available")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "compatible_approaches": compatible_approaches,
        "target_type": target_type,
    }
