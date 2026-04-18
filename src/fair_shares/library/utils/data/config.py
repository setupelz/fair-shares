"""
Configuration building and validation utilities.

This module handles data source configuration management, including building
configuration objects from YAML files, validating source compatibility, and
generating source identifiers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from fair_shares.library.config.models import DataSourcesConfig
from fair_shares.library.exceptions import (
    ConfigurationError,
    DataLoadingError,
)

# All valid target types.
ALL_TARGETS: frozenset[str] = frozenset({"pathway", "rcbs", "rcb-pathways"})

# Composite categories that contain non-CO2 components.
COMPOSITE_CATEGORIES: frozenset[str] = frozenset({"all-ghg", "all-ghg-ex-co2-lulucf"})

# CO2 categories (both use budget/RCB-based allocations; non-CO2 uses scenario pathways).
ALL_GHG_CO2_CATEGORIES: tuple[str, str] = ("co2-ffi", "co2")


def is_composite_category(emission_category: str) -> bool:
    """Return True if emission_category contains non-CO2 components.

    Composite categories (all-ghg, all-ghg-ex-co2-lulucf) need decomposition
    into CO2 + non-CO2 when used with RCB targets, because RCBs only constrain CO2.
    """
    return emission_category in COMPOSITE_CATEGORIES


def needs_decomposition(target: str, emission_category: str) -> bool:
    """Return True if this target + category needs 2-pass decomposition.

    RCB targets can only constrain CO2, so composite categories (all-ghg,
    all-ghg-ex-co2-lulucf) must be decomposed into CO2 (from RCBs) + non-CO2
    (from scenario pathways, e.g. AR6).  Pathway targets have direct data for all categories.

    The non-CO2 pass requires scenario pathway data matching the RCBs'
    climate assessments in the active data source configuration.
    ``build_data_config`` validates this and raises ``ConfigurationError``
    when no scenario source is configured.
    """
    return target != "pathway" and is_composite_category(emission_category)


def get_co2_component(emission_category: str) -> str:
    """Return the CO2 sub-category for a composite emission category.

    all-ghg             → co2     (includes LULUCF)
    all-ghg-ex-co2-lulucf → co2-ffi (excludes LULUCF)
    """
    if emission_category == "all-ghg":
        return "co2"
    elif emission_category == "all-ghg-ex-co2-lulucf":
        return "co2-ffi"
    return emission_category


def is_budget_target(target: str, category: str) -> bool:
    """Return True if this target + category uses budget (RCB) allocation."""
    return target == "rcbs" and category in ALL_GHG_CO2_CATEGORIES


def get_final_categories(target: str, emission_category: str) -> tuple[str, ...]:
    """Return the emission categories that the allocation loop iterates over.

    pathway target has direct pathways for all categories — no expansion needed.
    RCB targets need decomposition for categories containing non-CO2:
      all-ghg               → (co2, non-co2)
      all-ghg-ex-co2-lulucf → (co2-ffi, non-co2)
    Pure CO2 categories pass through unchanged.
    """
    if target == "pathway":
        return (emission_category,)

    if emission_category == "all-ghg":
        return ("co2", "non-co2")
    elif emission_category == "all-ghg-ex-co2-lulucf":
        return ("co2-ffi", "non-co2")
    else:
        return (emission_category,)


def get_emission_preprocessing_categories(
    target: str, emission_category: str
) -> tuple[str, ...]:
    """Return emission categories needed for emissions preprocessing.

    These are the categories that the emissions notebook (101) must extract
    from the emissions source (e.g. PRIMAP).  Notebook 107 (LULUCF) always needs co2-ffi, co2-lulucf,
    and all-ghg-ex-co2-lulucf as primitives for computing derived categories,
    so those are always included.

    ``non-co2`` is NEVER a direct 101 output — it is always derived by
    subtraction (``all-ghg-ex-co2-lulucf − co2-ffi``) in the derive_non_co2
    pipeline rule.  When ``non-co2`` is the main category, we return its
    ingredients instead.
    """
    # Base primitives always needed by notebook 107 (LULUCF → derived categories)
    _LULUCF_PRIMITIVES = {"co2-ffi", "co2-lulucf", "all-ghg-ex-co2-lulucf"}

    if not is_composite_category(emission_category):
        if emission_category == "co2":
            needed = {"co2", "co2-ffi", "co2-lulucf", "all-ghg-ex-co2-lulucf"}
        elif emission_category == "non-co2":
            # non-co2 is derived by subtraction, not extracted by 101
            needed = _LULUCF_PRIMITIVES.copy()
        else:
            needed = {emission_category} | _LULUCF_PRIMITIVES
        return tuple(sorted(needed))

    if target == "pathway":
        # pathway target has direct data, but notebook 107 still needs primitives
        needed = {emission_category} | _LULUCF_PRIMITIVES
        return tuple(sorted(needed))

    # RCB targets: need source categories for non-co2 derivation + LULUCF primitives
    if emission_category == "all-ghg":
        return ("all-ghg-ex-co2-lulucf", "co2", "co2-ffi", "co2-lulucf")
    else:  # all-ghg-ex-co2-lulucf
        return ("all-ghg-ex-co2-lulucf", "co2-ffi", "co2-lulucf")


def build_source_id(
    *,
    emissions: str,
    gdp: str,
    population: str,
    gini: str,
    target: str,
    emission_category: str,
    lulucf: str | None = None,
    rcb_generator: str | None = None,
) -> str:
    """Construct standardized source identifier used for output directories.

    Parameters are keyword-only to avoid ordering mistakes.

    For rcb-pathways targets, the generator name is appended to the target
    (e.g., "rcb-pathways-exponential-decay") to create separate output
    directories for different generators.

    The emission_category is always included in the source_id to ensure
    unique output directories for different emission scopes.

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
        Target source type. One of: "rcbs", "pathway", "rcb-pathways".
    emission_category : str
        Emission category. Available categories are defined per target in
        ``conf/data_sources/data_sources_unified.yaml``.
    lulucf : str | None, optional
        LULUCF source identifier (e.g., "melo-2026")
    rcb_generator : str | None, optional
        RCB pathway generator name (only used for target="rcb-pathways")

    Returns
    -------
    str
        Source identifier string
    """
    # For rcb-pathways, append generator to target name (default to exponential-decay).
    if target == "rcb-pathways":
        if rcb_generator is None:
            rcb_generator = "exponential-decay"
        target_with_generator = f"{target}-{rcb_generator}"
    else:
        target_with_generator = target

    # LULUCF only affects categories whose content depends on the LULUCF
    # source: co2-lulucf (IS LULUCF), co2 (FFI + LULUCF), all-ghg (includes
    # LULUCF).  all-ghg-ex-co2-lulucf and non-co2 are LULUCF-independent.
    # Kept in sync with ``NGHGI_CORRECTED_CATEGORIES`` in
    # ``fair_shares.library.preprocessing.paths`` and Snakefile's
    # ``_needs_lulucf``.
    _LULUCF_DEPENDENT = {"co2", "co2-lulucf", "all-ghg"}

    parts = [emissions, gdp, population, gini]
    if lulucf and emission_category in _LULUCF_DEPENDENT:
        parts.append(lulucf)
    parts.extend([target_with_generator, emission_category])
    return "_".join(parts)


def build_data_config(
    emission_category: Literal[
        "co2-ffi", "co2-lulucf", "co2", "non-co2", "all-ghg", "all-ghg-ex-co2-lulucf"
    ],
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
    emission_category : Literal[...]
        Emission category to filter for. Options:
        - "co2-ffi": CO2 from fossil fuels and industry
        - "co2-lulucf": LULUCF CO2 (NGHGI convention)
        - "co2": Total CO2 (fossil + LULUCF, NGHGI-consistent)
        - "non-co2": CH4 + N2O + F-gases (all Kyoto excl CO2)
        - "all-ghg": All greenhouse gases including LULUCF (GWP100 AR6)
        - "all-ghg-ex-co2-lulucf": All GHGs excluding CO2 from land use
    active_sources : dict[str, str]
        Dictionary of active source names with keys:
        - "emissions": emissions source (e.g., "primap-202503")
        - "gdp": GDP source (e.g., "wdi-2025")
        - "population": population source (e.g., "un-owid-2025")
        - "gini": Gini source (e.g., "unu-wider-2025")
        - "target": target source (e.g., "pathway", "rcbs", "rcb-pathways")
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

    # Validate emission category is available.
    # For pathway-mode targets, categories come from the scenario source.
    target_config = selected_target[target]
    available_categories = target_config.get("data_parameters", {}).get(
        "available_categories", []
    )
    if not available_categories:
        # Fall back to scenario source categories
        _scenario_key = target_config.get("scenario_source") or full_config.get(
            "active_scenario_source"
        )
        if _scenario_key:
            _scenario_cfg = full_config.get("scenarios", {}).get(_scenario_key, {})
            available_categories = _scenario_cfg.get("data_parameters", {}).get(
                "available_categories", []
            )
    if emission_category not in available_categories:
        raise ConfigurationError(
            f"Emission category '{emission_category}' not available "
            f"in target '{target}'. Available: {available_categories}"
        )

    # For composite categories with budget/rcb-pathway targets, validate that
    # a scenario source exists (non-CO2 pass needs scenario pathways).
    _is_composite = is_composite_category(emission_category)
    # Infer allocation mode early for validation
    _tc = target_config
    if _tc.get("allocation_mode"):
        _alloc_mode = _tc["allocation_mode"]
    elif not _tc.get("path"):
        _alloc_mode = "pathway"
    elif _tc.get("generator"):
        _alloc_mode = "rcb-pathway"
    else:
        _alloc_mode = "budget"
    if _is_composite and _alloc_mode != "pathway":
        _sc_key = _tc.get("scenario_source") or full_config.get(
            "active_scenario_source"
        )
        if _sc_key is None:
            raise ConfigurationError(
                f"Target '{target}' (allocation_mode={_alloc_mode}) requires "
                f"'scenario_source' when emission_category='{emission_category}'. "
                f"Non-CO2 pathways need a scenario source for decomposition."
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

    # Determine harmonisation_year: always include when available, since upstream
    # notebooks (e.g., 104 scenario preprocessing) need it regardless of target.
    if harmonisation_year is not None:
        final_harmonisation_year = harmonisation_year
    else:
        final_harmonisation_year = full_config.get("harmonisation_year")

    # Scenario-based targets require it — error if missing
    if final_harmonisation_year is None and (target != "rcbs" or _is_composite):
        raise ConfigurationError(
            f"harmonisation_year is required for scenario-based targets "
            f"(target='{target}'). "
            "Please provide it in notebook 301 or in the config YAML file."
        )

    # Resolve scenario source: per-target override → global default → None
    active_target_cfg = full_config["targets"][target]
    scenario_source_key = active_target_cfg.get("scenario_source") or full_config.get(
        "active_scenario_source"
    )
    all_scenarios = full_config.get("scenarios", {})
    if scenario_source_key and scenario_source_key in all_scenarios:
        filtered_scenarios = {scenario_source_key: all_scenarios[scenario_source_key]}
    else:
        filtered_scenarios = {}

    # Infer allocation_mode from target structure if not explicit
    _alloc_mode = active_target_cfg.get("allocation_mode")
    if not _alloc_mode:
        if not active_target_cfg.get("path"):
            _alloc_mode = "pathway"
        elif active_target_cfg.get("generator"):
            _alloc_mode = "rcb-pathway"
        else:
            _alloc_mode = "budget"

    # Build filtered config dict
    filtered_config = {
        "emission_category": emission_category,
        "emissions": full_config.get("emissions", {}),
        "gdp": full_config.get("gdp", {}),
        "population": full_config.get("population", {}),
        "gini": full_config.get("gini", {}),
        "lulucf": full_config.get("lulucf", {}),
        "scenarios": filtered_scenarios,
        "targets": selected_target,
        "general": full_config.get("general", {}),
        "harmonisation_year": final_harmonisation_year,
        # Set active sources
        "active_emissions_source": active_sources.get("emissions"),
        "active_gdp_source": active_sources.get("gdp"),
        "active_population_source": active_sources.get("population"),
        "active_gini_source": active_sources.get("gini"),
        "active_lulucf_source": active_sources.get("lulucf"),
        "active_target_source": target,
        "active_scenario_source": scenario_source_key,
        "rcb_generator": rcb_generator,  # Will be None for non-rcb-pathways targets
    }

    # Validate with Pydantic (this will raise ValidationError if invalid)
    validated_config = DataSourcesConfig(**filtered_config)

    source_id = build_source_id(
        emissions=active_sources.get("emissions"),
        gdp=active_sources.get("gdp"),
        population=active_sources.get("population"),
        gini=active_sources.get("gini"),
        lulucf=active_sources.get("lulucf"),
        target=target,
        emission_category=emission_category,
        rcb_generator=rcb_generator,
    )

    return validated_config, source_id


def get_compatible_approaches(
    target: str, emission_category: str = "co2-ffi"
) -> list[str]:
    """
    Return allocation approaches compatible with the given target type.

    Budget approaches (ending with "-budget") are compatible with "rcbs" target
    when not running all-GHG.  When ``emission_category="all-ghg"`` and
    ``target="rcbs"``, both budget and pathway approaches are returned because
    CO2 uses budget allocation and non-CO2 uses pathway allocation.

    Parameters
    ----------
    target : str
        Target source type: "rcbs", "pathway", or "rcb-pathways".
    emission_category : str, default "co2-ffi"
        Emission category. When "all-ghg", rcbs returns both budget and pathway
        approaches.

    Returns
    -------
    list[str]
        List of compatible allocation approach names

    Examples
    --------
    >>> get_compatible_approaches("rcbs")
    ['equal-per-capita-budget', 'per-capita-adjusted-budget', ...]

    >>> get_compatible_approaches("pathway")
    ['equal-per-capita', 'per-capita-adjusted', ...]

    >>> get_compatible_approaches("rcbs", emission_category="all-ghg")
    ['equal-per-capita-budget', ..., 'equal-per-capita', ...]
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
        if needs_decomposition(target, emission_category):
            return (
                budget_approaches + pathway_approaches
            )  # CO2 budgets + non-CO2 pathways
        return budget_approaches
    elif target in ALL_TARGETS:
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
        Emission category to validate. One of: "co2-ffi", "all-ghg",
        "all-ghg-ex-co2-lulucf".
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
    compatible_approaches = get_compatible_approaches(target, emission_category)

    # Determine target type
    if is_composite_category(emission_category):
        target_type = "composite"
    elif target == "rcbs":
        target_type = "budget"
    elif target in ALL_TARGETS:
        target_type = "pathway"
    else:
        target_type = "unknown"
        if target:
            issues.append(
                f"Unknown target type: '{target}'. "
                f"Expected one of: {sorted(ALL_TARGETS)}"
            )

    # Print summary
    if verbose and not issues:
        print(
            f"[OK] Emission category '{emission_category}' is valid for target '{target}'"
        )
        print(f"[OK] Target type: {target_type}")
        if target_type == "composite":
            print(
                f"[OK] Composite run: {get_final_categories(target, emission_category)}"
            )
        print(f"[OK] Compatible approaches: {len(compatible_approaches)} available")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "compatible_approaches": compatible_approaches,
        "target_type": target_type,
    }
