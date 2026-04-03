"""
Configuration validation for fair shares allocation approaches.

Validates allocation parameters, year constraints, and target source compatibility.
See docs/science/ for theoretical foundations of validation requirements.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import AllocationError, ConfigurationError
from fair_shares.library.utils.data.config import ALL_TARGETS


def validate_allocation_parameters(
    approach: str, params: dict, is_budget: bool
) -> None:
    """
    Validate that parameters are appropriate for the allocation type.

    Budget allocations use ``allocation_year``; pathway allocations use
    ``first_allocation_year``.

    Parameters
    ----------
    approach : str
        The allocation approach name
    params : dict
        Parameter dictionary to validate
    is_budget : bool
        Whether this is a budget allocation approach (True) or pathway
        allocation approach (False)

    Raises
    ------
    AllocationError
        If parameters are incorrect for the allocation type
    """
    # Check for required year parameter
    year_param = "allocation_year" if is_budget else "first_allocation_year"
    if year_param not in params:
        # Provide helpful error message for common mistake
        wrong_param = "first_allocation_year" if is_budget else "allocation_year"
        if wrong_param in params:
            raise AllocationError(
                f"Configuration error for approach '{approach}':\n"
                f"  Found parameter: '{wrong_param}'\n"
                f"  Expected parameter: '{year_param}'\n\n"
                f"For {'budget' if is_budget else 'pathway'} allocations, "
                f"use '{year_param}' instead of '{wrong_param}'.\n"
                f"Budget allocations (ending with '-budget') use "
                f"'allocation_year'.\n"
                f"Pathway allocations use 'first_allocation_year'."
            )
        else:
            raise AllocationError(
                f"Missing required parameter '{year_param}' for approach "
                f"'{approach}'.\n"
                f"For {'budget' if is_budget else 'pathway'} allocations, "
                f"you must specify '{year_param}' in your configuration."
            )

    # Check for preserve shares parameter mismatch
    if is_budget:
        # Budget allocations should use preserve_allocation_year_shares
        wrong_param = "preserve_first_allocation_year_shares"
        correct_param = "preserve_allocation_year_shares"
    else:
        # Pathway allocations should use preserve_first_allocation_year_shares
        wrong_param = "preserve_allocation_year_shares"
        correct_param = "preserve_first_allocation_year_shares"

    if wrong_param in params:
        raise AllocationError(
            f"Configuration error for approach '{approach}':\n"
            f"  Found parameter: '{wrong_param}'\n"
            f"  Expected parameter: '{correct_param}'\n\n"
            f"You are applying a {'budget' if is_budget else 'pathway'} allocation,"
            f" use '{correct_param}' instead of '{wrong_param}' "
            "or change allocation approach.\n"
        )


# Default NGHGI min year — used only as a fallback when no metadata is available.
# The actual min year should be derived from lulucf_metadata.yaml at runtime.
_NGHGI_MIN_YEAR_DEFAULT = 2000


def _raise_nghgi_year_error(
    approach: str,
    param_name: str,
    year: int,
    emission_category: str,
    nghgi_min_year: int,
) -> None:
    """Raise AllocationError for year < nghgi_min_year in LULUCF-containing categories."""
    raise AllocationError(
        f"Configuration error for approach '{approach}':\n"
        f"  {param_name} = {year} is before {nghgi_min_year}\n\n"
        f"For emission_category='{emission_category}' (contains LULUCF), "
        f"all allocations must be NGHGI-consistent. NGHGI-consistent LULUCF "
        f"CO2 data only starts in {nghgi_min_year} — both at country level "
        f"and world level (derived from NGHGI data).\n\n"
        f"Options:\n"
        f"  1. Set {param_name} >= {nghgi_min_year}\n"
        f"  2. Use emission_category='co2-ffi' or 'all-ghg-ex-co2-lulucf' "
        f"(no LULUCF data dependency)"
    )


def validate_allocation_year_for_co2(
    allocations_config: dict[str, list[dict[str, Any]]],
    emission_category: str,
    nghgi_min_year: int | None = None,
) -> None:
    """
    Enforce year parameters >= nghgi_min_year for LULUCF-containing categories.

    The minimum year is derived from the NGHGI data (e.g., Melo v3.1 starts
    at 2000). No NGHGI/BM splicing is allowed — categories containing LULUCF
    are limited to the NGHGI data range.

    This applies to budget allocations (``allocation_year``), pathway
    allocations (``first_allocation_year``), and responsibility-adjusted
    approaches (``historical_responsibility_year``) to ensure
    methodological consistency.

    Parameters
    ----------
    allocations_config : dict[str, list[dict[str, Any]]]
        Configuration dict with approach names as keys
    emission_category : str
        Emission category (e.g. "co2-ffi", "co2", "all-ghg")
    nghgi_min_year : int or None
        Minimum year for NGHGI-consistent allocations (derived from data).
        If None, uses the default (currently 2000).

    Raises
    ------
    AllocationError
        If allocation start year or historical_responsibility_year < nghgi_min_year
        for LULUCF-containing emission categories ("co2", "all-ghg")
    """
    # Resolve NGHGI min year
    min_year = nghgi_min_year if nghgi_min_year is not None else _NGHGI_MIN_YEAR_DEFAULT

    # Categories containing LULUCF: "co2" (= co2-ffi + co2-lulucf) and
    # "all-ghg" (= co2 + non-co2, where co2 includes LULUCF).
    _LULUCF_CATEGORIES = {"co2", "all-ghg"}
    if emission_category not in _LULUCF_CATEGORIES:
        return

    for approach, params_list in allocations_config.items():
        is_budget = approach.endswith("-budget")
        year_param = "allocation_year" if is_budget else "first_allocation_year"

        for params in params_list:
            params_snake = {k.replace("-", "_"): v for k, v in params.items()}
            years = params_snake.get(year_param, [])
            if not isinstance(years, (list, tuple)):
                years = [years]

            for year in years:
                if year < min_year:
                    _raise_nghgi_year_error(
                        approach, year_param, year, emission_category, min_year
                    )

            # Check historical_responsibility_year
            hist_year = params_snake.get("historical_responsibility_year")
            if hist_year is not None:
                hist_years = (
                    hist_year if isinstance(hist_year, (list, tuple)) else [hist_year]
                )
                for hy in hist_years:
                    if hy < min_year:
                        _raise_nghgi_year_error(
                            approach,
                            "historical_responsibility_year",
                            hy,
                            emission_category,
                            min_year,
                        )


def validate_allocation_years_against_harmonisation(
    allocations_config: dict[str, list[dict[str, Any]]],
    harmonisation_year: int | None,
    target_source: str,
) -> None:
    """
    Validate that allocation years do not exceed the harmonisation year.

    Only applies to scenario-based targets (not RCBs).

    Parameters
    ----------
    allocations_config : dict[str, list[dict[str, Any]]]
        Configuration dict with approach names as keys
    harmonisation_year : int | None
        Year at which scenarios are harmonized to historical data
    target_source : str
        Target source (e.g., "rcbs", "pathway", "rcb-pathways")

    Raises
    ------
    AllocationError
        If allocation years exceed harmonisation_year for scenario-based targets
    """
    # Only validate for scenario-based targets (not RCBs-only).
    # Note: rcbs + all-ghg is also scenario-based (non-CO2 uses scenario pathways),
    # but the harmonisation check only applies when harmonisation_year is set.
    if target_source == "rcbs" or harmonisation_year is None:
        return

    for approach, params_list in allocations_config.items():
        is_budget = approach.endswith("-budget")
        year_param = "allocation_year" if is_budget else "first_allocation_year"

        for params in params_list:
            # Convert kebab-case to snake_case
            params_snake = {k.replace("-", "_"): v for k, v in params.items()}

            if year_param in params_snake:
                years = params_snake[year_param]
                # Convert to list if single value
                if not isinstance(years, (list, tuple)):
                    years = [years]

                # Check each year
                for year in years:
                    if year > harmonisation_year:
                        raise AllocationError(
                            f"Configuration error for approach '{approach}':\n"
                            f"  {year_param} = {year} exceeds "
                            f"harmonisation_year = {harmonisation_year}\n\n"
                            f"For scenario-based targets "
                            f"(target_source='{target_source}'), "
                            f"allocation years must be <= harmonisation_year because "
                            f"scenarios are harmonized to historical data up to the "
                            f"harmonisation_year.\n"
                            f"Please set {year_param} <= {harmonisation_year} or "
                            f"increase harmonisation_year in Step 1 of the notebook."
                        )


def validate_target_source_compatibility(
    allocations_config: dict[str, list[dict[str, Any]]], target_source: str
) -> None:
    """
    Validate that allocation approaches are compatible with the target source.

    RCBs require budget approaches; pathway-based targets require pathway approaches.

    Parameters
    ----------
    allocations_config : dict[str, list[dict[str, Any]]]
        Configuration dict with approach names as keys
    target_source : str
        Target source (e.g., "rcbs", "pathway", "rcb-pathways")

    Raises
    ------
    AllocationError
        If incompatible approaches are found for the target source
    """
    if target_source == "rcbs":
        # Check for pathway allocation approaches (those that don't end with '-budget')
        pathway_approaches = [
            approach
            for approach in allocations_config.keys()
            if not approach.endswith("-budget")
        ]

        if pathway_approaches:
            raise AllocationError(
                f"Configuration error: Pathway allocation approaches cannot be "
                f"used with RCBs (target_source='rcbs').\n\n"
                f"Found pathway approaches: {pathway_approaches}\n\n"
                f"RCBs (Remaining Carbon Budgets) only work with budget "
                f"allocation approaches.\n"
                f"Please use budget approaches instead, e.g.:\n"
                f"  - 'equal-per-capita-budget' instead of 'equal-per-capita'\n"
            )

    elif target_source in ALL_TARGETS - {"rcbs"}:
        # This is a temporary restriction until we determine how to properly
        # calculate allocation_year budgets from pathways that may have
        # net-negative emissions and other complexities.
        #
        # To enable budget allocations with pathway scenarios in the future:
        # 1. Implement proper budget extraction from pathways
        # 2. Handle net-negative emissions appropriately
        # 3. Remove or modify this validation check
        budget_approaches = [
            approach
            for approach in allocations_config.keys()
            if approach.endswith("-budget")
        ]

        if budget_approaches:
            target_display = {
                "pathway": "AR6 scenarios",
                "rcb-pathways": "RCB-derived pathways",
            }.get(target_source, f"{target_source} pathways")

            raise AllocationError(
                f"Configuration error: Budget allocation approaches are not "
                f"yet supported with {target_display} "
                f"(target_source='{target_source}').\n\n"
                f"Found budget approaches: {budget_approaches}\n\n"
                f"Pathway-based targets currently only work with pathway allocation "
                f"approaches.\n"
                f"Please use pathway approaches instead, e.g.:\n"
                f"  - 'equal-per-capita' instead of 'equal-per-capita-budget'\n"
                f"  - 'cumulative-per-capita-convergence' for convergence-based "
                f"allocations\n\n"
                f"Note: This is a temporary limitation. Budget allocations require "
                f"proper\n"
                f"handling of cumulative budgets from pathways with potential "
                f"net-negative\n"
                f"emissions, which is currently under development.\n"
            )


def validate_function_parameters(
    func: Callable,
    provided_params: dict[str, Any],
    required_context: dict[str, str] | None = None,
) -> None:
    """
    Validate that required data and parameters are provided for an approach.

    Parameters
    ----------
    func : Callable
        The allocation function whose parameters to validate
    provided_params : dict[str, Any]
        Parameters provided by the caller
    required_context : dict[str, str] | None
        Context for parameter requirements

    Raises
    ------
    AllocationError
        If required parameters are missing
    """
    sig = inspect.signature(func)
    func_args = {}

    # Start with provided parameters
    for k, v in provided_params.items():
        if k in sig.parameters and v is not None:
            func_args[k] = v

    # Validate required parameters
    for param_name, param in sig.parameters.items():
        if param.default == inspect.Parameter.empty and param_name not in func_args:
            # Provide error messages for common missing parameters
            error_context = (
                required_context.get(param_name, "") if required_context else ""
            )
            context_msg = f" for {error_context}" if error_context else ""

            if param_name == "first_allocation_year":
                raise AllocationError(
                    f"first_allocation_year required{context_msg} for pathway "
                    "approaches"
                )
            elif param_name == "allocation_year":
                raise AllocationError(
                    f"allocation_year required{context_msg} for budget approaches"
                )
            elif param_name == "gdp_ts":
                error_msg = format_error(
                    "missing_required_data",
                    adjustment_type="capability",
                    weight_name="capability_weight",
                    weight_value="> 0.0",
                    data_name="GDP data (gdp_ts)",
                    explanation=(
                        "Capability-based adjustments require GDP data to "
                        "calculate per-capita GDP for countries."
                    ),
                    function_name=func.__name__,
                    data_param="gdp_ts",
                )
                raise AllocationError(error_msg)
            elif param_name == "gini_s":
                error_msg = format_error(
                    "missing_required_data",
                    adjustment_type="inequality",
                    weight_name="(approach uses Gini)",
                    weight_value="",
                    data_name="Gini data (gini_s)",
                    explanation=(
                        "Gini-adjusted approaches require Gini coefficient "
                        "data to account for within-country inequality."
                    ),
                    function_name=func.__name__,
                    data_param="gini_s",
                )
                raise AllocationError(error_msg)
            elif param_name == "country_actual_emissions_ts":
                raise AllocationError(
                    f"Emissions data required{context_msg} for pathway convergence "
                    "approaches"
                )
            elif param_name == "emission_category":
                raise AllocationError(
                    f"emission_category parameter required{context_msg} for allocation "
                    "approaches"
                )
            elif param_name == "convergence_year":
                raise AllocationError(
                    f"convergence_year parameter required{context_msg} for "
                    "per-capita-convergence approach"
                )
            else:
                raise ConfigurationError(f"Missing required parameter: {param_name}")
