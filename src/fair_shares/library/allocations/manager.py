"""
Allocation engine: registry, parameter expansion, validation, and execution.

This module provides the central interface for calculating fair shares of emissions
budgets and pathways. It includes the approach registry (mapping names to functions),
parameter grid expansion, input validation, and result serialization.

For theoretical foundations of the equity principles underlying these approaches, see:
    docs/science/allocations.md
"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fair_shares.library.allocations.budgets.per_capita import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)
from fair_shares.library.allocations.pathways.cumulative_per_capita_convergence import (
    cumulative_per_capita_convergence,
    cumulative_per_capita_convergence_adjusted,
    cumulative_per_capita_convergence_adjusted_gini,
)
from fair_shares.library.allocations.pathways.per_capita import (
    equal_per_capita,
    per_capita_adjusted,
    per_capita_adjusted_gini,
)
from fair_shares.library.allocations.pathways.per_capita_convergence import (
    per_capita_convergence,
)
from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.allocations.results.metadata import (
    get_all_metadata_columns,
)
from fair_shares.library.allocations.results.serializers import (
    delete_existing_parquet_files as _delete_existing_parquet_files,
)
from fair_shares.library.allocations.results.serializers import (
    save_allocation_result as _save_allocation_result,
)
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils.dataframes import (
    TimeseriesDataFrame,
    filter_function_parameters,
)
from fair_shares.library.utils.io import create_param_manifest as _create_param_manifest
from fair_shares.library.utils.io import generate_readme as _generate_readme
from fair_shares.library.validation import (
    validate_allocation_parameters,
    validate_allocation_year_for_co2,
    validate_allocation_years_against_harmonisation,
    validate_function_parameters,
    validate_target_source_compatibility,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Approach registry — add new allocation approaches here
# ---------------------------------------------------------------------------


def get_allocation_functions() -> dict[str, Callable[..., Any]]:
    """Get the allocation function registry.

    Returns a dictionary mapping approach names to allocation functions.
    Budget approaches (ending in "-budget") allocate a cumulative budget at a
    single point in time. Pathway approaches allocate emissions year-by-year.
    """
    return {
        # Pathway allocations
        "equal-per-capita": equal_per_capita,
        "per-capita-adjusted": per_capita_adjusted,
        "per-capita-adjusted-gini": per_capita_adjusted_gini,
        "per-capita-convergence": per_capita_convergence,
        # NOTE (2026-04-08): Both keys route to the `_adjusted` function. The
        # bare `cumulative_per_capita_convergence` wrapper does not accept
        # responsibility/capability kwargs, so callers passing those kwargs
        # via this key were silently degenerate (kwargs filtered out by
        # `utils/dataframes.py:filter_function_parameters`). The `_adjusted`
        # function defaults `pre_allocation_responsibility_weight=0.0` and
        # `capability_weight=0.0`, so bare callers retain identical behavior.
        "cumulative-per-capita-convergence": cumulative_per_capita_convergence_adjusted,
        "cumulative-per-capita-convergence-adjusted": (
            cumulative_per_capita_convergence_adjusted
        ),
        "cumulative-per-capita-convergence-gini-adjusted": (
            cumulative_per_capita_convergence_adjusted_gini
        ),
        # Budget allocations
        "equal-per-capita-budget": equal_per_capita_budget,
        "per-capita-adjusted-budget": per_capita_adjusted_budget,
        "per-capita-adjusted-gini-budget": per_capita_adjusted_gini_budget,
    }


def get_function(approach: str) -> Callable[..., Any]:
    """Get allocation function by approach name.

    Raises AllocationError if the approach name is not recognized.
    """
    allocation_functions = get_allocation_functions()
    if approach not in allocation_functions:
        raise AllocationError(
            f"Unknown allocation approach: {approach}. "
            f"Available: {list(allocation_functions.keys())}"
        )
    return allocation_functions[approach]


def is_budget_approach(approach: str) -> bool:
    """Check if the approach is a budget allocation approach."""
    return approach.endswith("-budget")


def is_pathway_approach(approach: str) -> bool:
    """Check if the approach is a pathway allocation approach."""
    return not approach.endswith("-budget")


# Budget → pathway name mapping
_BUDGET_TO_PATHWAY: dict[str, str] = {
    "equal-per-capita-budget": "equal-per-capita",
    "per-capita-adjusted-budget": "per-capita-adjusted",
    "per-capita-adjusted-gini-budget": "per-capita-adjusted-gini",
}

_PARAM_RENAMES: dict[str, str] = {
    "allocation_year": "first_allocation_year",
    "preserve_allocation_year_shares": "preserve_first_allocation_year_shares",
}


def get_pathway_analogue(budget_approach: str) -> str:
    """Return the pathway approach name corresponding to a budget approach."""
    if budget_approach in _BUDGET_TO_PATHWAY:
        return _BUDGET_TO_PATHWAY[budget_approach]
    raise AllocationError(
        f"No pathway analogue for budget approach '{budget_approach}'. "
        f"Known mappings: {list(_BUDGET_TO_PATHWAY.keys())}"
    )


def convert_budget_config_to_pathway(config: dict) -> dict:
    """Convert a budget parameter config dict to its pathway equivalent."""
    return {_PARAM_RENAMES.get(key, key): value for key, value in config.items()}


def derive_pathway_allocations(
    budget_allocations: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    """Derive pathway approach configs from budget approach configs.

    For each budget approach with a known pathway analogue, creates the
    equivalent pathway configuration with renamed parameters.
    """
    pathway_allocs: dict[str, list[dict]] = {}
    for budget_name, configs in budget_allocations.items():
        pathway_name = get_pathway_analogue(budget_name)
        pathway_allocs[pathway_name] = [
            convert_budget_config_to_pathway(cfg) for cfg in configs
        ]
    return pathway_allocs


# ---------------------------------------------------------------------------
# Metadata and absolute emissions
# ---------------------------------------------------------------------------


def all_metadata_columns() -> list[str]:
    """Get all metadata columns in the desired order."""
    return get_all_metadata_columns()


def calculate_absolute_emissions(
    result: BudgetAllocationResult | PathwayAllocationResult,
    emissions_data: TimeseriesDataFrame,
) -> TimeseriesDataFrame:
    """
    Calculate absolute emissions from allocation result and emissions data.

    Converts relative shares (fractions summing to 1.0) into absolute emission
    quantities by applying the shares to a global emissions total. This
    separation of relative and absolute allows the same equity-based allocation
    to be applied to different emissions scenarios or budget estimates.

    Parameters
    ----------
    result : Union[BudgetAllocationResult, PathwayAllocationResult]
        The allocation result containing relative shares. These shares represent
        each country's claim to a portion of the global emissions space.
    emissions_data : TimeseriesDataFrame
        Emissions data providing the global totals to which shares are applied.
        For budget allocations, this is the total budget to distribute.
        For pathway allocations, this is the year-by-year global trajectory.

    Returns
    -------
    TimeseriesDataFrame
        Absolute emissions/budgets calculated from relative shares. Units match
        the input emissions_data (typically MtCO2eq or GtCO2eq).
    """
    if isinstance(result, BudgetAllocationResult):
        return result.get_absolute_budgets(emissions_data)
    elif isinstance(result, PathwayAllocationResult):
        return result.get_absolute_emissions(emissions_data)
    else:
        raise TypeError(
            f"Unsupported result type: {type(result).__name__}. "
            "Expected BudgetAllocationResult or PathwayAllocationResult."
        )


def run_allocation(
    approach: str,
    population_ts: TimeseriesDataFrame,
    first_allocation_year: int | None = None,
    allocation_year: int | None = None,
    gdp_ts: TimeseriesDataFrame | None = None,
    gini_s: TimeseriesDataFrame | None = None,
    country_actual_emissions_ts: TimeseriesDataFrame | None = None,
    world_scenario_emissions_ts: TimeseriesDataFrame | None = None,
    emission_category: str | None = None,
    **kwargs,
) -> BudgetAllocationResult | PathwayAllocationResult:
    """
    Run a single allocation.

    This is the main function for running allocations. It handles:

    - Parameter validation
    - Data requirement checking
    - Function execution
    - Result validation

    Parameters
    ----------
    approach : str
        The allocation approach to use
    population_ts : TimeseriesDataFrame
        Population time series data
    first_allocation_year : int, optional
        First allocation year (for pathway allocations)
    allocation_year : int, optional
        Allocation year (for budget allocations)
    gdp_ts : TimeseriesDataFrame, optional
        GDP time series data (if required by approach)
    gini_s : TimeseriesDataFrame, optional
        Gini coefficient data (if required by approach)
    country_actual_emissions_ts : TimeseriesDataFrame, optional
        Country-level actual emissions time series data (if required by approach)
    world_scenario_emissions_ts : TimeseriesDataFrame, optional
        World scenario emissions pathway (used by approaches that require it)
    emission_category : str, optional
        Emission category to allocate
    **kwargs
        Additional parameters specific to the allocation approach

    Returns
    -------
    Union[BudgetAllocationResult, PathwayAllocationResult]
        The allocation result with relative shares

    Raises
    ------
    AllocationError
        If validation fails or required data is missing
    DataProcessingError
        If other errors occur during allocation

    Examples
    --------
    Run a simple budget allocation:

    >>> from fair_shares.library.allocations import run_allocation
    >>> from fair_shares.library.utils import create_example_data
    >>>
    >>> # Create example data
    >>> data = create_example_data()
    >>>
    >>> # Run equal per capita budget allocation
    >>> result = run_allocation(  # doctest: +ELLIPSIS
    ...     approach="equal-per-capita-budget",
    ...     population_ts=data["population"],
    ...     allocation_year=2020,
    ...     emission_category="co2-ffi",
    ... )
    Converting units...
    >>>
    >>> # Check result
    >>> result.approach
    'equal-per-capita-budget'
    >>> # Shares sum to 1.0
    >>> shares_sum = result.relative_shares_cumulative_emission.sum().iloc[0]
    >>> bool(abs(shares_sum - 1.0) < 0.01)
    True

    Run a pathway allocation with adjustments:

    >>> # Run per capita adjusted pathway allocation
    >>> result = run_allocation(  # doctest: +ELLIPSIS
    ...     approach="per-capita-adjusted",
    ...     population_ts=data["population"],
    ...     gdp_ts=data["gdp"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     world_scenario_emissions_ts=data["world_emissions"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     pre_allocation_responsibility_weight=0.5,
    ...     capability_weight=0.5,
    ... )
    Converting units...
    >>>
    >>> # Check result
    >>> result.approach
    'per-capita-adjusted'
    >>> # Check that shares are calculated for all years
    >>> len(result.relative_shares_pathway_emissions.columns) == 3
    True

    Notes
    -----
    This is the main entry point for running allocations. It automatically:

    - Determines whether the approach is budget or pathway based
    - Validates all input data structures
    - Checks that required data is provided for the chosen approach
    - Filters parameters to only pass what the allocation function needs

    **When to use:** Use this function for single allocation runs. For running
    multiple parameter combinations, use :func:`run_parameter_grid` instead.

    **Budget vs Pathway:** Budget approaches (ending in "-budget") allocate a
    single year's cumulative budget. Pathway approaches allocate emissions
    over multiple years. Budget approaches use ``allocation_year``, pathway
    approaches use ``first_allocation_year``.

    **Equity considerations:** Each approach implements different equity
    principles. The equal per capita approaches treat population as the sole
    basis for claims. Adjusted approaches incorporate capability
    (ability to pay based on GDP, from the allocation year onwards) and/or
    pre-allocation responsibility (multiplicative rescaling based on
    per-capita emissions backward-looking from the allocation year),
    implementing aspects of CBDR-RC. Parameters like
    ``pre_allocation_responsibility_weight`` and ``capability_weight`` represent
    explicit normative choices about how to balance these considerations.

    **Transparency:** All parameter choices are recorded in the result
    metadata to enable replication and critical assessment.
    """
    # Get the allocation function
    allocation_func = get_function(approach)

    # Prepare all function arguments
    func_args = {
        "population_ts": population_ts,
        "emission_category": emission_category,
        "gdp_ts": gdp_ts,
        "gini_s": gini_s,
        "country_actual_emissions_ts": country_actual_emissions_ts,
        "world_scenario_emissions_ts": world_scenario_emissions_ts,
        **kwargs,
    }

    # Add year parameter based on approach type
    if is_budget_approach(approach):
        func_args["allocation_year"] = allocation_year
    else:
        func_args["first_allocation_year"] = first_allocation_year

    # Validate parameters first, then filter them
    validate_function_parameters(allocation_func, func_args)
    filtered_args = filter_function_parameters(allocation_func, func_args)
    return allocation_func(**filtered_args)


def run_parameter_grid(
    allocations_config: dict[str, list[dict[str, Any]]],
    population_ts: TimeseriesDataFrame,
    gdp_ts: TimeseriesDataFrame | None = None,
    gini_s: TimeseriesDataFrame | None = None,
    country_actual_emissions_ts: TimeseriesDataFrame | None = None,
    world_scenario_emissions_ts: TimeseriesDataFrame | None = None,
    emission_category: str | None = None,
    target_source: str | None = None,
    harmonisation_year: int | None = None,
) -> list[BudgetAllocationResult | PathwayAllocationResult]:
    """
    Run allocations for all parameter combinations in a grid.

    This function expands the configuration into all possible parameter
    combinations and runs each allocation.

    Parameters
    ----------
    allocations_config : dict[str, list[dict[str, Any]]]
        Configuration dict with approach names as keys and lists of
        parameter dicts as values. Each parameter dict defines one
        configuration to run. Parameters within each dict can be single
        values or lists for grid expansion.
    population_ts : TimeseriesDataFrame
        Population time series data
    gdp_ts : TimeseriesDataFrame, optional
        GDP time series data
    gini_s : TimeseriesDataFrame, optional
        Gini coefficient data
    country_actual_emissions_ts : TimeseriesDataFrame, optional
        Country-level actual emissions time series data
    world_scenario_emissions_ts : TimeseriesDataFrame, optional
        World scenario emissions pathway data
    emission_category : str, optional
        Emission category to allocate
    target_source : str, optional
        Target source (e.g., "rcbs", "pathway")
    harmonisation_year : int, optional
        Year at which scenarios are harmonized to historical data.
        Required for scenario-based targets (not RCBs).

    Returns
    -------
    list[Union[BudgetAllocationResult, PathwayAllocationResult]]
        list of allocation results

    Examples
    --------
    Run multiple budget allocations across different years:

    >>> from fair_shares.library.allocations import run_parameter_grid
    >>> from fair_shares.library.utils import create_example_data
    >>>
    >>> # Create example data
    >>> data = create_example_data()
    >>>
    >>> # Define configuration with multiple years for equal per capita
    >>> config = {"equal-per-capita-budget": [{"allocation-year": [2020, 2030]}]}
    >>>
    >>> # Run parameter grid
    >>> results = run_parameter_grid(  # doctest: +ELLIPSIS
    ...     allocations_config=config,
    ...     population_ts=data["population"],
    ...     emission_category="co2-ffi",
    ... )
    <BLANKLINE>
    Processing approach: equal-per-capita-budget
    ...
    >>> # Check we got 2 results (one per year)
    >>> len(results)
    2
    >>> # Both are budget results
    >>> all(r.approach == "equal-per-capita-budget" for r in results)
    True

    Run parameter grid with weight combinations for adjusted allocation:

    >>> # Define configuration with parameter grid expansion
    >>> config = {
    ...     "per-capita-adjusted-budget": [
    ...         {
    ...             "allocation-year": 2020,
    ...             "pre-allocation-responsibility-weight": 0.0,
    ...             "capability-weight": [0.25, 0.5, 0.75],
    ...         }
    ...     ]
    ... }
    >>>
    >>> # Run parameter grid (will expand to 3 combinations)
    >>> results = run_parameter_grid(  # doctest: +ELLIPSIS
    ...     allocations_config=config,
    ...     population_ts=data["population"],
    ...     gdp_ts=data["gdp"],
    ...     emission_category="co2-ffi",
    ... )
    <BLANKLINE>
    Processing approach: per-capita-adjusted-budget
    ...
    >>> # Check we got 3 results (3 capability weights)
    >>> len(results)
    3
    >>> # All are per-capita-adjusted-budget results
    >>> all(r.approach == "per-capita-adjusted-budget" for r in results)
    True

    Notes
    -----
    This function is designed for systematic parameter exploration. It:

    - Automatically expands parameter lists into all combinations
    - Validates that approaches are compatible with the target source
    - Ensures allocation years are consistent with harmonisation_year
    - Returns a list of all results for comparison

    **When to use:** Use this function when you want to run the same allocation
    approach with multiple parameter combinations to compare results. For
    single allocations, use :func:`run_allocation` instead.

    **Parameter expansion:** Any parameter value can be a list, and the function
    will create all combinations. For example, if ``allocation-year: [2020, 2030]``
    and ``capability-weight: [0.25, 0.5]``, this will run 4 allocations
    (2 years x 2 weights).

    **Configuration format:** The ``allocations_config`` parameter expects a
    nested structure where each approach maps to a list of parameter dictionaries.
    Each dictionary in the list can use either single values or lists for grid
    expansion.

    **Exploring normative choices:** The parameter grid is useful for exploring
    how different normative choices affect allocations. For example, varying
    ``pre-allocation-responsibility-weight`` and ``capability-weight`` reveals the sensitivity
    of results to how CBDR-RC principles are operationalized. Similarly, varying
    ``pre-allocation-responsibility-year`` shows how the choice of start date for
    counting historical emissions affects current allocations - a choice that
    remains debated. See docs/science/allocations.md for details.
    """
    results = []

    # Note: composite categories (all-ghg, all-ghg-ex-co2-lulucf) are valid here
    # when the target has direct scenario data (pathway mode).  Decomposition
    # into co2/non-co2 passes is only required for RCB targets and is handled
    # upstream by the Snakefile + master notebook.  No guard needed — if a
    # composite category reaches here, the upstream decided it doesn't need
    # decomposition.

    # Validate target source compatibility with allocation approaches
    if target_source:
        validate_target_source_compatibility(allocations_config, target_source)
        # Validate allocation years against harmonisation_year
        validate_allocation_years_against_harmonisation(
            allocations_config, harmonisation_year, target_source
        )

    # Validate allocation year >= 1990 for total CO2 (NGHGI data limit)
    if emission_category:
        validate_allocation_year_for_co2(allocations_config, emission_category)

    for approach, params_list in allocations_config.items():
        print(f"\nProcessing approach: {approach}")

        # Validate format
        if not isinstance(params_list, list):
            raise AllocationError(
                f"Invalid configuration for approach '{approach}': "
                f"expected list of dicts, got {type(params_list)}. "
                f"Please wrap parameter dicts in a list: "
                f"[{{'param': value}}]"
            )

        # Process each parameter configuration
        for config_idx, params in enumerate(params_list, start=1):
            if len(params_list) > 1:
                print(f"  Configuration {config_idx}/{len(params_list)}")

            # Convert kebab-case to snake_case
            params = {k.replace("-", "_"): v for k, v in params.items()}

            # Determine year parameter and validate all parameters
            is_budget_alloc = is_budget_approach(approach)
            year_param = (
                "allocation_year" if is_budget_alloc else "first_allocation_year"
            )

            # Validate parameters (checks both year and preserve shares parameters)
            validate_allocation_parameters(approach, params, is_budget_alloc)

            # Expand parameter lists
            years = _to_list(params.pop(year_param))

            param_combinations = _expand_parameters(params)

            approach_attempts = len(years) * len(param_combinations)
            print(f"  Will run {approach_attempts} parameter combinations")

            # Run allocations for each combination
            for year in years:
                for param_combo in param_combinations:
                    # Prepare arguments
                    kwargs = {year_param: year, **param_combo}
                    print(
                        f"    Running {approach} with "
                        f"{year_param}={year}, params={param_combo}"
                    )

                    result = run_allocation(
                        approach=approach,
                        population_ts=population_ts,
                        gdp_ts=gdp_ts,
                        gini_s=gini_s,
                        country_actual_emissions_ts=country_actual_emissions_ts,
                        world_scenario_emissions_ts=world_scenario_emissions_ts,
                        emission_category=emission_category,
                        **kwargs,
                    )

                    results.append(result)
                    print("      Success")

    print(f"\nCompleted {len(results)} allocations successfully")
    return results


def _to_list(value: Any) -> list[Any]:
    """Convert value to list if not already a list/tuple."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _expand_parameters(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand parameter lists into all combinations."""
    # Convert all values to lists
    param_lists: dict[str, list[Any]] = {k: _to_list(v) for k, v in params.items()}

    if not param_lists:
        return [{}]

    # Generate all combinations
    keys: list[str] = list(param_lists.keys())
    values: list[list[Any]] = list(param_lists.values())

    combinations: list[dict[str, Any]] = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))

    return combinations


def save_allocation_result(
    result: BudgetAllocationResult | PathwayAllocationResult,
    output_dir: Path,
    absolute_emissions: TimeseriesDataFrame | None = None,
    climate_assessment: str | None = None,
    quantile: float | None = None,
    data_context: dict | None = None,
    **metadata,
) -> dict[str, Path]:
    """
    Save allocation results to parquet files.

    Persists allocation results with comprehensive metadata to enable
    transparent, replicable analysis. Following the transparency principles
    recommended for transparency, all parameter choices and data sources
    are recorded to allow critical assessment of the normative choices embedded
    in each allocation.

    Parameters
    ----------
    result : Union[BudgetAllocationResult, PathwayAllocationResult]
        The allocation result to save
    output_dir : Path
        Directory to save results
    absolute_emissions : TimeseriesDataFrame, optional
        Absolute emissions data (if None, only relative shares are saved)
    climate_assessment : str, optional
        Climate assessment name (e.g., "AR6")
    quantile : float, optional
        Quantile value for scenario (e.g., 0.5 for median)
    data_context : dict, optional
        Context about data sources and processing. Should include sources for
        population, GDP, emissions, and other input data to enable verification.
    **metadata
        Additional metadata to include

    Returns
    -------
    dict[str, Path]
        Paths to saved parquet files

    Raises
    ------
    DataProcessingError
        If data preparation fails
    IOError
        If file writing fails

    Notes
    -----
    The output includes a ``warnings`` column that flags allocations requiring
    attention, such as:

    - ``not-fair-share``: Approaches like per-capita-convergence that privilege
      current emission patterns during transition
    - ``missing-net-negative``: Scenarios where negative emissions were excluded
    """
    return _save_allocation_result(
        result=result,
        output_dir=output_dir,
        absolute_emissions=absolute_emissions,
        climate_assessment=climate_assessment,
        quantile=quantile,
        data_context=data_context,
        **metadata,
    )


def generate_readme(output_dir: Path, data_context: dict | None = None) -> None:
    """
    Generate README files for relative and absolute parquet files.

    Creates human-readable documentation of the allocation outputs,
    including column descriptions and data sources. This supports
    the transparency goal of enabling users to understand and
    critically assess the choices embedded in each allocation.

    Parameters
    ----------
    output_dir : Path
        Directory containing parquet files
    data_context : dict, optional
        Context about data sources and processing
    """
    _generate_readme(output_dir=output_dir, data_context=data_context)


def create_param_manifest(
    param_manifest_rows: list[dict[str, Any]], output_dir: Path
) -> None:
    """
    Create param_manifest.csv with proper kebab-case column names.

    The parameter manifest provides a summary of all allocation configurations
    run in a batch, enabling quick comparison of different normative choices.
    This supports transparent reporting of how different parameter combinations
    affect allocation results.

    Parameters
    ----------
    param_manifest_rows : list[dict[str, Any]]
        List of parameter manifest rows, where each row contains parameters
        in snake_case format
    output_dir : Path
        Directory where param_manifest.csv will be saved
    """
    _create_param_manifest(
        param_manifest_rows=param_manifest_rows, output_dir=output_dir
    )


def delete_existing_parquet_files(output_dir: Path) -> None:
    """
    Delete existing parquet files in the output directory.

    Parameters
    ----------
    output_dir : Path
        Directory containing parquet files to delete.
    """
    _delete_existing_parquet_files(output_dir)
