"""
Manager for orchestrating allocation calculations.

This module provides the central interface for calculating fair shares of emissions
budgets and pathways. Supports budget allocations (single point in time) and pathway
allocations (annual shares over time).

For theoretical foundations of the equity principles underlying these approaches, see:
    docs/science/allocations.md
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from attrs import define

logger = logging.getLogger(__name__)

from fair_shares.library.allocations.registry import (
    get_function,
    is_budget_approach,
    is_pathway_approach,  # noqa: F401 - exported for backward compatibility
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
    validate_allocation_years_against_harmonisation,
    validate_function_parameters,
    validate_target_source_compatibility,
)


@define
class AllocationManager:
    """
    Manager for allocation operations with validation and result handling.

    This class provides a high-level interface for running allocations and managing
    the results, including validation, absolute calculations, and file output.

    The manager orchestrates the application of different allocation approaches, each
    of which operationalizes particular equity principles. Users should be aware that
    every approach embeds normative choices about how to weight competing claims to
    atmospheric space. This tool aims to make these choices explicit rather than
    hidden in default parameters. See docs/science/ for theoretical foundations.

    Supported Approaches
    --------------------
    Budget approaches (single-year cumulative budget allocation):

    - ``equal-per-capita-budget``: Allocates budget proportional to population
    - ``per-capita-adjusted-budget``: Adjusts for capability and/or responsibility
    - ``per-capita-adjusted-gini-budget``: Further adjusts for within-country inequality

    Pathway approaches (multi-year emissions trajectory allocation):

    - ``equal-per-capita``: Annual shares proportional to population
    - ``per-capita-adjusted``: Adjusted for capability/responsibility
    - ``per-capita-adjusted-gini``: Further adjusted for inequality
    - ``per-capita-convergence``: Transitions to equal per capita (not a fair share)
    - ``cumulative-per-capita-convergence``: Equal cumulative per capita from reference year
    - ``cumulative-per-capita-convergence-adjusted``: With capability/responsibility
    - ``cumulative-per-capita-convergence-gini-adjusted``: With inequality adjustment

    Notes
    -----
    The distinction between budget and pathway approaches matters for interpretation:

    - Budget approaches answer: "What share of a remaining carbon budget does each
      country have a claim to?"

    - Pathway approaches answer: "What emissions trajectory should each country follow
      to collectively achieve a global target while respecting equity principles?"

    Both require explicit choices about which equity principles to apply and how to
    weight them. The manager validates inputs and tracks these choices in output
    metadata to enable transparent, replicable analysis.
    """

    @property
    def all_metadata_columns(self) -> list[str]:
        """Get all metadata columns in the desired order."""
        return get_all_metadata_columns()

    def calculate_absolute_emissions(
        self,
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

    def run_allocation(
        self,
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

        This is the main method for running allocations. It handles:

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

        >>> from fair_shares.library.allocations import AllocationManager
        >>> from fair_shares.library.utils import create_example_data
        >>>
        >>> # Create example data
        >>> data = create_example_data()
        >>>
        >>> # Initialize manager
        >>> manager = AllocationManager()
        >>>
        >>> # Run equal per capita budget allocation
        >>> result = manager.run_allocation(  # doctest: +ELLIPSIS
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
        >>> result = manager.run_allocation(  # doctest: +ELLIPSIS
        ...     approach="per-capita-adjusted",
        ...     population_ts=data["population"],
        ...     gdp_ts=data["gdp"],
        ...     country_actual_emissions_ts=data["emissions"],
        ...     world_scenario_emissions_ts=data["world_emissions"],
        ...     first_allocation_year=2020,
        ...     emission_category="co2-ffi",
        ...     responsibility_weight=0.5,
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

        **When to use:** Use this method for single allocation runs. For running
        multiple parameter combinations, use :meth:`run_parameter_grid` instead.

        **Budget vs Pathway:** Budget approaches (ending in "-budget") allocate a
        single year's cumulative budget. Pathway approaches allocate emissions
        over multiple years. Budget approaches use ``allocation_year``, pathway
        approaches use ``first_allocation_year``.

        **Equity considerations:** Each approach implements different equity
        principles. The equal per capita approaches treat population as the sole
        basis for claims. Adjusted approaches incorporate capability
        (ability to pay based on GDP) and/or historical responsibility, implementing
        aspects of CBDR-RC. Parameters like ``responsibility_weight`` and
        ``capability_weight`` represent explicit normative choices about how to
        balance these considerations.

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
        self,
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

        This method expands the configuration into all possible parameter
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
            Target source (e.g., "rcbs", "ar6")
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

        >>> from fair_shares.library.allocations import AllocationManager
        >>> from fair_shares.library.utils import create_example_data
        >>>
        >>> # Create example data
        >>> data = create_example_data()
        >>>
        >>> # Initialize manager
        >>> manager = AllocationManager()
        >>>
        >>> # Define configuration with multiple years for equal per capita
        >>> config = {"equal-per-capita-budget": [{"allocation-year": [2020, 2030]}]}
        >>>
        >>> # Run parameter grid
        >>> results = manager.run_parameter_grid(  # doctest: +ELLIPSIS
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
        ...             "responsibility-weight": 0.0,
        ...             "capability-weight": [0.25, 0.5, 0.75],
        ...         }
        ...     ]
        ... }
        >>>
        >>> # Run parameter grid (will expand to 3 combinations)
        >>> results = manager.run_parameter_grid(  # doctest: +ELLIPSIS
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
        This method is designed for systematic parameter exploration. It:

        - Automatically expands parameter lists into all combinations
        - Validates that approaches are compatible with the target source
        - Ensures allocation years are consistent with harmonisation_year
        - Returns a list of all results for comparison

        **When to use:** Use this method when you want to run the same allocation
        approach with multiple parameter combinations to compare results. For
        single allocations, use :meth:`run_allocation` instead.

        **Parameter expansion:** Any parameter value can be a list, and the method
        will create all combinations. For example, if ``allocation-year: [2020, 2030]``
        and ``capability-weight: [0.25, 0.5]``, this will run 4 allocations
        (2 years x 2 weights).

        **Configuration format:** The ``allocations_config`` parameter expects a
        nested structure where each approach maps to a list of parameter dictionaries.
        Each dictionary in the list can use either single values or lists for grid
        expansion.

        **Exploring normative choices:** The parameter grid is useful for exploring
        how different normative choices affect allocations. For example, varying
        ``responsibility-weight`` and ``capability-weight`` reveals the sensitivity
        of results to how CBDR-RC principles are operationalized. Similarly, varying
        ``historical-responsibility-year`` shows how the choice of start date for
        counting historical emissions affects current allocations - a choice that
        remains debated. See docs/science/allocations.md for details.
        """
        results = []

        # Validate target source compatibility with allocation approaches
        if target_source:
            validate_target_source_compatibility(allocations_config, target_source)
            # Validate allocation years against harmonisation_year
            validate_allocation_years_against_harmonisation(
                allocations_config, harmonisation_year, target_source
            )

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
                years = self._to_list(params.pop(year_param))

                param_combinations = self._expand_parameters(params)

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

                        result = self.run_allocation(
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

    def _to_list(self, value: Any) -> list[Any]:
        """Convert value to list if not already a list/tuple."""
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    def _expand_parameters(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Expand parameter lists into all combinations."""
        import itertools

        # Convert all values to lists
        param_lists: dict[str, list[Any]] = {
            k: self._to_list(v) for k, v in params.items()
        }

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
        self,
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

    def generate_readme(
        self, output_dir: Path, data_context: dict | None = None
    ) -> None:
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
        self, param_manifest_rows: list[dict[str, Any]], output_dir: Path
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

    def _delete_existing_parquet_files(self, output_dir: Path) -> None:
        """
        Delete existing parquet files in the output directory.

        .. deprecated::
            Use :func:`~fair_shares.library.allocations.results.serializers.delete_existing_parquet_files` instead.
        """
        _delete_existing_parquet_files(output_dir)
