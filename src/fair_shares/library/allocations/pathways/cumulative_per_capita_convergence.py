"""
Cumulative per capita convergence pathway allocation.

This module implements allocation approaches that distribute emissions budgets
based on cumulative population shares over the full scenario time horizon,
with optional adjustments for historical responsibility and capability.

For theoretical foundations and academic context, see:
    docs/science/allocations.md#convergence-mechanism-theoretical-foundations

For CBDR-RC principles and normative considerations, see:
    docs/science/allocations.md#4-common-but-differentiated-responsibilities-cbdr-rc

**Three Allocation Variants**

- ``cumulative-per-capita-convergence``: Pure cumulative per capita shares
- ``cumulative-per-capita-convergence-adjusted``: With responsibility/capability adjustments
- ``cumulative-per-capita-convergence-gini-adjusted``: With Gini-based inequality corrections

Implementation is modular across utility packages:
- ``utils.data.convergence``: Data processing for convergence allocations
- ``utils.math.convergence``: Convergence solver and speed validation
- ``utils.math.adjustments``: Responsibility and capability adjustments
- ``validation.convergence``: Input/output validation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from fair_shares.library.allocations.results import PathwayAllocationResult
from fair_shares.library.utils import (
    calculate_relative_adjustment,
    filter_time_columns,
    get_default_unit_registry,
    set_single_unit,
)
from fair_shares.library.utils.data.convergence import (
    build_result_dataframe,
    calculate_initial_shares,
    process_emissions_data,
    process_population_data,
    process_world_scenario_data,
)
from fair_shares.library.utils.math.adjustments import (
    calculate_capability_adjustment_data,
    calculate_responsibility_adjustment_data_convergence,
)
from fair_shares.library.utils.math.convergence import find_minimum_convergence_speed
from fair_shares.library.validation.convergence import (
    validate_adjustment_data_requirements,
    validate_country_world_consistency,
    validate_share_calculation,
    validate_sufficient_time_horizon,
    validate_weights,
    validate_world_weights_aligned,
)
from fair_shares.library.validation.models import AllocationInputs, AllocationOutputs

if TYPE_CHECKING:
    import pint.facets

    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def _cumulative_per_capita_convergence_core(
    population_ts: TimeseriesDataFrame,
    country_actual_emissions_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    emission_category: str,
    world_scenario_emissions_ts: TimeseriesDataFrame,
    gdp_ts: TimeseriesDataFrame | None = None,
    gini_s: pd.DataFrame | None = None,
    responsibility_weight: float = 0.0,
    capability_weight: float = 0.0,
    historical_responsibility_year: int = 1990,
    responsibility_per_capita: bool = True,
    responsibility_exponent: float = 1.0,
    responsibility_functional_form: str = "asinh",
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    income_floor: float = 0.0,
    max_gini_adjustment: float = 0.8,
    max_deviation_sigma: float | None = 2.0,
    strict: bool = True,
    max_convergence_speed: float = 0.9,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    """
    Core allocation with cumulative per capita shares and optional adjustments.

    This function implements the cumulative per capita convergence approach,
    which allocates emissions based on cumulative population shares with
    optional adjustments for historical responsibility and capability.

    The approach is grounded in the equal per capita principle, extended to
    account for the full time dimension of emissions pathways. Adjustments
    incorporate CBDR-RC principles by reducing allocations for countries with
    higher historical emissions (responsibility) or higher economic capacity
    (capability).

    Delegates to helper modules for data processing, validation, math,
    and solving. This function orchestrates the overall workflow.
    """
    # Convert to int
    first_allocation_year = int(first_allocation_year)
    historical_responsibility_year = int(historical_responsibility_year)

    # Determine last year from world scenario data
    last_year = int(max(world_scenario_emissions_ts.columns, key=lambda x: int(x)))

    # Validate inputs using Pydantic model
    AllocationInputs(
        population_ts=population_ts,
        first_allocation_year=first_allocation_year,
        last_allocation_year=last_year,
        gdp_ts=gdp_ts,
        gini_s=gini_s,
        country_actual_emissions_ts=country_actual_emissions_ts,
        world_scenario_emissions_ts=world_scenario_emissions_ts,
        historical_responsibility_year=historical_responsibility_year
        if responsibility_weight > 0
        else None,
    )

    # Validate inputs
    validate_weights(responsibility_weight, capability_weight)
    validate_adjustment_data_requirements(capability_weight, gdp_ts, gini_s)

    # Determine approach and weight normalization
    use_capability = capability_weight > 0
    use_responsibility = responsibility_weight > 0
    use_gini_adjustment = use_capability and gini_s is not None
    has_adjustments = use_responsibility or use_capability

    total_adjustment_weight = responsibility_weight + capability_weight
    if total_adjustment_weight > 0:
        normalized_responsibility_weight = (
            responsibility_weight / total_adjustment_weight
        )
        normalized_capability_weight = capability_weight / total_adjustment_weight
    else:
        normalized_responsibility_weight = 0.0
        normalized_capability_weight = 0.0

    if use_gini_adjustment:
        approach = "cumulative-per-capita-convergence-gini-adjusted"
    elif has_adjustments:
        approach = "cumulative-per-capita-convergence-adjusted"
    else:
        approach = "cumulative-per-capita-convergence"

    # Process emissions data
    (
        emissions_full_numeric,
        emissions_countries_full,
        country_year_to_label,
        start_column,
    ) = process_emissions_data(
        country_actual_emissions_ts,
        first_allocation_year,
        emission_category,
        group_level,
        unit_level,
        ur,
    )

    # Calculate initial shares
    country_totals, country_sum = calculate_initial_shares(
        emissions_countries_full, start_column, group_level
    )

    # Process world scenario data
    (
        emissions_world,
        year_fraction_of_cumulative_emissions,
        sorted_columns,
        world_full_year_to_label,
        world_start_column,
        world_total,
    ) = process_world_scenario_data(
        world_scenario_emissions_ts,
        first_allocation_year,
        group_level,
        unit_level,
        ur,
    )

    # Validate country/world consistency
    validate_country_world_consistency(country_sum, world_total, first_allocation_year)
    initial_shares = country_totals / world_total

    # Get non-World mask for later use
    group_values_all = emissions_full_numeric.index.get_level_values(group_level)
    non_world_mask = group_values_all != "World"

    # Process population data
    cmltv_pop_by_group = process_population_data(
        population_ts, first_allocation_year, group_level, unit_level, ur
    )

    # Start with cumulative population as the base (no adjustment = equal per capita)
    adjusted_population = cmltv_pop_by_group.copy()

    # Apply responsibility adjustment: higher historical emissions -> lower allocation
    if responsibility_weight > 0:
        responsibility_data = calculate_responsibility_adjustment_data_convergence(
            country_actual_emissions_ts=country_actual_emissions_ts,
            population_ts=population_ts,
            historical_responsibility_year=historical_responsibility_year,
            first_allocation_year=first_allocation_year,
            responsibility_per_capita=responsibility_per_capita,
            group_level=group_level,
            unit_level=unit_level,
            ur=ur,
        )
        responsibility_data = responsibility_data.reindex(cmltv_pop_by_group.index)
        responsibility_adjustment = calculate_relative_adjustment(
            responsibility_data,
            functional_form=responsibility_functional_form,
            exponent=normalized_responsibility_weight * responsibility_exponent,
            inverse=True,
        )
        adjusted_population = adjusted_population * responsibility_adjustment

    # Apply capability adjustment: higher GDP -> lower allocation
    if capability_weight > 0 and gdp_ts is not None:
        capability_data = calculate_capability_adjustment_data(
            population_ts=population_ts,
            gdp_ts=gdp_ts,
            first_allocation_year=first_allocation_year,
            capability_per_capita=capability_per_capita,
            group_level=group_level,
            unit_level=unit_level,
            ur=ur,
            gini_s=gini_s,
            income_floor=income_floor,
            max_gini_adjustment=max_gini_adjustment,
        )
        capability_data = capability_data.reindex(cmltv_pop_by_group.index)
        capability_adjustment = calculate_relative_adjustment(
            capability_data,
            functional_form=capability_functional_form,
            exponent=normalized_capability_weight * capability_exponent,
            inverse=True,
        )
        adjusted_population = adjusted_population * capability_adjustment

    # Normalize to get target cumulative per capita shares
    target_cumulative_shares = adjusted_population / adjusted_population.sum()

    # Apply optional deviation constraint to cumulative target shares
    # This constrains adjusted cumulative shares to be within X sigma of equal
    # cumulative per capita (baseline), where sigma is population-weighted std dev
    if max_deviation_sigma is not None:
        # Baseline: equal cumulative per capita
        baseline_cumulative = cmltv_pop_by_group / cmltv_pop_by_group.sum()
        # Deviation from baseline
        deviation = target_cumulative_shares - baseline_cumulative
        # Population-weighted standard deviation
        weighted_std = np.sqrt(
            (deviation**2 * cmltv_pop_by_group).sum() / cmltv_pop_by_group.sum()
        )
        # Clip deviations to +/-max_deviation_sigma standard deviations
        max_dev = max_deviation_sigma * weighted_std
        constrained_deviation = np.clip(deviation, -max_dev, max_dev)
        target_cumulative_shares = baseline_cumulative + constrained_deviation
        # Renormalize to ensure shares sum to 1
        target_cumulative_shares = (
            target_cumulative_shares / target_cumulative_shares.sum()
        )

    # Determine approach name for diagnostics
    if not has_adjustments:
        approach_name = "cumulative-per-capita-convergence"
    elif use_gini_adjustment:
        approach_name = "cumulative-per-capita-convergence-gini-adjusted"
    else:
        approach_name = "cumulative-per-capita-convergence-adjusted"

    # Find convergence speed and evolve shares
    diagnostic_params = {
        "approach": approach_name,
        "first_allocation_year": first_allocation_year,
        "responsibility_weight": responsibility_weight,
        "capability_weight": capability_weight,
        "historical_responsibility_year": historical_responsibility_year,
        "max_deviation_sigma": max_deviation_sigma,
        "max_convergence_speed": max_convergence_speed,
        "use_gini_adjustment": use_gini_adjustment,
    }
    convergence_speed, long_run_shares, adjustment_warnings, adjusted_cumulative = (
        find_minimum_convergence_speed(
            sorted_columns,
            start_column,
            year_fraction_of_cumulative_emissions,
            initial_shares,
            target_cumulative_shares,
            diagnostic_params,
            strict=strict,
            max_convergence_speed=max_convergence_speed,
        )
    )

    # Use adjusted cumulative targets if fallback was used
    if adjusted_cumulative is not None:
        target_cumulative_shares = adjusted_cumulative
    long_run_shares = long_run_shares / long_run_shares.sum()

    # Validate time horizon
    validate_sufficient_time_horizon(
        sorted_columns, start_column, first_allocation_year
    )
    world_time_columns = emissions_world.columns

    # Evolve shares through convergence
    shares_df = pd.DataFrame(
        index=initial_shares.index, columns=sorted_columns, dtype=float
    )
    start_idx = sorted_columns.index(start_column)
    shares_df[start_column] = initial_shares
    current_shares = initial_shares

    for column in sorted_columns[start_idx + 1 :]:
        raw = current_shares + convergence_speed * (long_run_shares - current_shares)
        validate_share_calculation(raw, "Share evolution")
        current_shares = raw / raw.sum()
        shares_df[column] = current_shares

    shares_by_group = shares_df.reindex(columns=world_time_columns)
    validate_share_calculation(shares_by_group, "Share calculation")

    # Validate world weights alignment
    year_fraction_aligned = year_fraction_of_cumulative_emissions.reindex(
        shares_by_group.columns
    )
    validate_world_weights_aligned(year_fraction_aligned, shares_by_group.columns)

    # Build result DataFrame
    # Get emissions_countries by filtering again

    emissions_filtered = filter_time_columns(
        country_actual_emissions_ts, first_allocation_year
    )
    emissions_single_unit = set_single_unit(emissions_filtered, unit_level, ur=ur)
    emissions_numeric = emissions_single_unit.droplevel(unit_level)
    emissions_countries = emissions_numeric[non_world_mask]

    res = build_result_dataframe(
        shares_by_group,
        emissions_countries.index,
        list(world_time_columns),
        group_level,
        unit_level,
    )

    # Build parameters dict (always include normalized weights for reporting)
    parameters = {
        "first_allocation_year": first_allocation_year,
        "responsibility_weight": normalized_responsibility_weight,
        "capability_weight": normalized_capability_weight,
        "convergence_speed": convergence_speed,
        "emission_category": emission_category,
        "group_level": group_level,
        "unit_level": unit_level,
    }

    # Add responsibility parameters if used
    if responsibility_weight > 0:
        parameters.update(
            {
                "historical_responsibility_year": historical_responsibility_year,
                "responsibility_per_capita": responsibility_per_capita,
                "responsibility_exponent": responsibility_exponent,
                "responsibility_functional_form": responsibility_functional_form,
            }
        )

    # Add capability parameters if used
    if capability_weight > 0:
        parameters.update(
            {
                "capability_per_capita": capability_per_capita,
                "capability_exponent": capability_exponent,
                "capability_functional_form": capability_functional_form,
            }
        )

    # Add Gini parameters if used
    if gini_s is not None:
        parameters.update(
            {
                "income_floor": income_floor,
                "max_gini_adjustment": max_gini_adjustment,
            }
        )

    # Add deviation constraint parameter if used
    if max_deviation_sigma is not None:
        parameters["max_deviation_sigma"] = max_deviation_sigma

    # Add max convergence speed parameter
    parameters["max_convergence_speed"] = max_convergence_speed

    # Add strict parameter
    parameters["strict"] = strict

    # Format country warnings for result
    country_warnings = None
    if adjustment_warnings:
        country_warnings = {}
        for iso3c, factor in adjustment_warnings.items():
            # Round the factor to 2 decimal points
            factor_rounded = round(factor, 2)
            # Only include if it's not essentially 1.0 (no change)
            if factor_rounded != 1.00:
                country_warnings[iso3c] = f"strict=false:{factor_rounded:.2f}"

    # Validate outputs using Pydantic model
    AllocationOutputs(
        shares=res,
        dataset_name=f"{approach} pathway allocation",
        first_year=first_allocation_year,
        reference_data=world_scenario_emissions_ts,
    )

    return PathwayAllocationResult(
        approach=approach,
        parameters=parameters,
        relative_shares_pathway_emissions=res,
        country_warnings=country_warnings,
    )


def cumulative_per_capita_convergence(
    population_ts: TimeseriesDataFrame,
    country_actual_emissions_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    emission_category: str,
    world_scenario_emissions_ts: TimeseriesDataFrame,
    max_deviation_sigma: float | None = 2.0,
    max_convergence_speed: float = 0.9,
    strict: bool = True,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Pure cumulative per capita convergence allocation without adjustments.

    Allocates emissions based on cumulative population shares, converging from
    initial emission shares to cumulative per capita targets over time.

    Mathematical Foundation
    -----------------------

    **Convergence Dynamics**

    The allocation shares evolve through exponential convergence:

    $$
    A(g, t+1) = A(g, t) + \lambda \big(A^{\infty}(g) - A(g, t)\big)
    $$

    Where:

    - $A(g, t)$: Allocation share for country $g$ at year $t$
    - $A^{\infty}(g)$: Long-run target share that each year converges toward
    - $\lambda$: Convergence speed (automatically determined to be minimum feasible)

    **Initial Shares**

    Initial shares at first_allocation_year are based on actual emissions:

    $$
    A(g, t_a) = \frac{E(g, t_a)}{\sum_{g'} E(g', t_a)}
    $$

    Where:

    - $A(g, t_a)$: Initial allocation share for country $g$ at first allocation year
    - $E(g, t_a)$: Actual emissions of country $g$ at year $t_a$
    - $t_a$: First allocation year
    - $\sum_{g'} E(g', t_a)$: Total world emissions at first allocation year

    **Cumulative Target Shares**

    The cumulative target shares are based on cumulative population:

    $$
    T_{\text{cum}}(g) = \frac{\sum_{t \geq t_a} P(g, t)}{\sum_{g'} \sum_{t \geq t_a} P(g', t)}
    $$

    Where:

    - $T_{\text{cum}}(g)$: Cumulative target share for country $g$
    - $P(g, t)$: Population of country $g$ at year $t$
    - $\sum_{t \geq t_a} P(g, t)$: Cumulative population of country $g$ from allocation year onwards
    - $\sum_{g'} \sum_{t \geq t_a} P(g', t)$: Total cumulative world population from allocation year onwards

    **Convergence Speed Determination**

    The convergence speed $\lambda$ is automatically determined to be the
    minimum speed that ensures cumulative allocations match targets:

    $$
    \sum_{t \geq t_a} w(t) \, A(g, t) = T_{\text{cum}}(g)
    $$

    Where:

    - $w(t)$: Year weight for year $t$, defined as $w(t) = \frac{W(t)}{\sum_{t' \geq t_a} W(t')}$
    - $W(t)$: World emissions in year $t$ from the scenario pathway

    **Deviation Constraint**

    When :code:`max_deviation_sigma` is provided, cumulative target shares are
    constrained to prevent extreme deviations from equal cumulative per capita:

    $$
    T_{\text{equal}}(g) - \sigma \, s \leq T_{\text{cum}}(g) \leq T_{\text{equal}}(g) + \sigma \, s
    $$

    Where:

    - $T_{\text{equal}}(g)$: Equal cumulative per capita baseline share
    - $\sigma$: Maximum deviation parameter (e.g., 2.0 standard deviations)
    - $s$: Population-weighted standard deviation of unconstrained cumulative targets

    Parameters
    ----------
    population_ts
        Population time series for calculating cumulative per capita shares.
    country_actual_emissions_ts
        Country emissions for calculating initial shares at first_allocation_year.
    world_scenario_emissions_ts
        World emissions pathway defining the time horizon and year weights.
    first_allocation_year
        Starting year for the allocation.
    emission_category
        The emission category (e.g., 'co2-ffi', 'all-ghg').
    max_deviation_sigma
        Maximum allowed deviation from equal per capita baseline in terms of
        population-weighted standard deviations. If provided, constrains each
        group's share to be within +/-max_deviation_sigma standard deviations
        from the baseline equal per capita share. If None, no constraint is applied.
    group_level
        Index level name for grouping (typically 'iso3c'). Default: 'iso3c'
    unit_level
        Index level name for units. Default: 'unit'
    ur
        Pint unit registry for unit conversions.

    Returns
    -------
    PathwayAllocationResult
        Relative shares over time, summing to unity each year.

    See Also
    --------
    cumulative_per_capita_convergence_adjusted : With
        responsibility/capability adjustments
    cumulative_per_capita_convergence_adjusted_gini : With Gini-adjusted GDP

    Notes
    -----
    **Theoretical grounding:**

    For theoretical foundations, use cases, and limitations, see:
        docs/science/allocations.md#convergence-mechanism-theoretical-foundations

    For translating the egalitarian tradition (which grounds the equal per capita
    principle) into pathway allocations, see:
        docs/science/principle-to-code.md#convergence-pathway-approaches

    For CBDR-RC principles (responsibility and capability), use
    cumulative_per_capita_convergence_adjusted or
    cumulative_per_capita_convergence_adjusted_gini.

    **Convergence Speed**

    The convergence speed is automatically determined to be the minimum speed
    that ensures cumulative targets are met, creating the smoothest possible
    transition path while still achieving equity goals. The ``strict`` parameter
    controls whether an error is raised if exact targets cannot be achieved.

    Examples
    --------
    Basic usage with default parameters:

    >>> from fair_shares.library.utils import create_example_data
    >>> from fair_shares.library.allocations.pathways import (
    ...     cumulative_per_capita_convergence,
    ... )
    >>> # Create example data
    >>> data = create_example_data(
    ...     countries=["USA", "CHN", "IND"], years=[2020, 2030, 2050]
    ... )
    >>> # Run allocation with strict=False for limited time horizon
    >>> result = cumulative_per_capita_convergence(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     world_scenario_emissions_ts=data["world_emissions"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     strict=False,  # Accept approximate targets with limited data
    ... )
    Converting units...
    >>> # Check approach is correct
    >>> result.approach
    'cumulative-per-capita-convergence'
    >>> # Shares sum to 1.0 at each year
    >>> shares = result.relative_shares_pathway_emissions
    >>> bool(abs(shares["2020"].sum() - 1.0) < 1e-10)
    True

    Adjust convergence behavior with strict=False for approximate targets:

    >>> result_approx = cumulative_per_capita_convergence(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     world_scenario_emissions_ts=data["world_emissions"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     strict=False,  # Accept approximate targets
    ...     max_convergence_speed=0.5,  # Slower, smoother convergence
    ... )
    Converting units...
    >>> # Check for warnings about deviations
    >>> if result_approx.country_warnings:  # doctest: +SKIP
    ...     print("Some targets approximate:", result_approx.country_warnings)

    Remove deviation constraints for unconstrained targets:

    >>> result_unconstrained = cumulative_per_capita_convergence(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     world_scenario_emissions_ts=data["world_emissions"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     max_deviation_sigma=None,  # No constraints on target shares
    ...     strict=False,  # Needed for limited data
    ... )
    Converting units...
    """
    return _cumulative_per_capita_convergence_core(
        population_ts=population_ts,
        country_actual_emissions_ts=country_actual_emissions_ts,
        world_scenario_emissions_ts=world_scenario_emissions_ts,
        first_allocation_year=first_allocation_year,
        emission_category=emission_category,
        gdp_ts=None,
        gini_s=None,
        responsibility_weight=0.0,
        capability_weight=0.0,
        max_deviation_sigma=max_deviation_sigma,
        strict=strict,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )


def cumulative_per_capita_convergence_adjusted(
    population_ts: TimeseriesDataFrame,
    country_actual_emissions_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    emission_category: str,
    world_scenario_emissions_ts: TimeseriesDataFrame,
    gdp_ts: TimeseriesDataFrame | None = None,
    responsibility_weight: float = 0.0,
    capability_weight: float = 0.0,
    historical_responsibility_year: int = 1990,
    responsibility_per_capita: bool = True,
    responsibility_exponent: float = 1.0,
    responsibility_functional_form: str = "asinh",
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    max_deviation_sigma: float | None = 2.0,
    max_convergence_speed: float = 0.9,
    strict: bool = True,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Cumulative per capita convergence with responsibility and capability adjustments.

    Extends cumulative per capita convergence by incorporating:

    - Responsibility adjustment: Countries with higher historical emissions
        receive smaller allocations
    - Capability adjustment: Countries with higher GDP receive smaller allocations

    Mathematical Foundation
    -----------------------

    **Convergence Dynamics**

    The allocation shares evolve through exponential convergence (same as base approach):

    $$
    A(g, t+1) = A(g, t) + \lambda \big(A^{\infty}(g) - A(g, t)\big)
    $$

    Where:

    - $A(g, t)$: Allocation share for country $g$ at year $t$
    - $A^{\infty}(g)$: Long-run target share
    - $\lambda$: Convergence speed (automatically determined)

    Initial shares at first_allocation_year are based on actual emissions.

    **Cumulative Target Shares with Adjustments**

    Target shares are computed by adjusting cumulative population for
    historical responsibility and economic capability:

    $$
    T_{\text{cum}}(g) = \frac{P_{\text{adj}}(g)}{\sum_{g'} P_{\text{adj}}(g')}
    $$

    Where the adjusted population is:

    $$
    P_{\text{adj}}(g) = P_{\text{cum}}(g) \times R(g) \times C(g)
    $$

    Where:

    - $T_{\text{cum}}(g)$: Cumulative target share for country $g$
    - $P_{\text{adj}}(g)$: Adjusted cumulative population
    - $P_{\text{cum}}(g) = \sum_{t \geq t_a} P(g, t)$: Cumulative population from allocation year onwards
    - $R(g)$: Responsibility adjustment factor (equals 1.0 if not used)
    - $C(g)$: Capability adjustment factor (equals 1.0 if not used)

    **Responsibility Adjustment**

    The responsibility metric is based on cumulative historical emissions
    from historical_responsibility_year to first_allocation_year.

    For per capita responsibility (:code:`responsibility_per_capita=True`, default):

    $$
    R(g) = \left(\frac{\sum_{t=t_h}^{t_a} E(g, t)}{\sum_{t=t_h}^{t_a} P(g, t)}\right)^{-w_r \times e_r}
    $$

    Where:

    - $R(g)$: Responsibility adjustment factor (inverse - higher emissions = lower allocation)
    - $E(g, t)$: Emissions of country $g$ in year $t$
    - $t_h$: Historical responsibility start year
    - $t_a$: First allocation year
    - $w_r$: Normalized responsibility weight
    - $e_r$: Responsibility exponent

    For absolute responsibility (:code:`responsibility_per_capita=False`):

    $$
    R(g) = \left(\sum_{t=t_h}^{t_a} E(g, t)\right)^{-w_r \times e_r}
    $$

    **Capability Adjustment**

    The capability metric is based on cumulative GDP from first_allocation_year onwards.

    For per capita capability (:code:`capability_per_capita=True`, default):

    $$
    C(g) = \left(\frac{\sum_{t \geq t_a} \text{GDP}(g, t)}{\sum_{t \geq t_a} P(g, t)}\right)^{-w_c \times e_c}
    $$

    Where:

    - $C(g)$: Capability adjustment factor (inverse - higher cumulative GDP per capita = lower allocation)
    - $\text{GDP}(g, t)$: Gross domestic product of country $g$ in year $t$
    - $w_c$: Normalized capability weight
    - $e_c$: Capability exponent

    For absolute capability (:code:`capability_per_capita=False`):

    $$
    C(g) = \left(\sum_{t \geq t_a} \text{GDP}(g, t)\right)^{-w_c \times e_c}
    $$

    **Deviation Constraint**

    When :code:`max_deviation_sigma` is provided, adjusted cumulative target shares
    are constrained to prevent extreme deviations from equal cumulative per capita.

    Parameters
    ----------
    population_ts
        Population time series for per capita calculations and responsibility
        adjustment.
    country_actual_emissions_ts
        Country emissions for initial shares and responsibility calculation.
    world_scenario_emissions_ts
        World emissions pathway defining time horizon and year weights.
    first_allocation_year
        Starting year for the allocation.
    emission_category
        The emission category (e.g., 'co2-ffi', 'all-ghg').
    gdp_ts
        GDP time series for capability adjustment. Required if capability_weight > 0.
    responsibility_weight
        Weight for responsibility adjustment (0-1). Higher historical emissions
        -> smaller allocation. Must satisfy: responsibility_weight +
        capability_weight <= 1.0
    capability_weight
        Weight for capability adjustment (0-1). Higher GDP -> smaller allocation.
        Requires gdp_ts. Must satisfy: responsibility_weight + capability_weight <= 1.0
    historical_responsibility_year
        First year of responsibility window
        [historical_responsibility_year, first_allocation_year].
        Default: 1990
    responsibility_per_capita
        If True, use per capita emissions for responsibility. Default: True
    responsibility_exponent
        Exponent for responsibility adjustment calculation. Default: 1.0
    responsibility_functional_form
        Functional form for responsibility adjustment ('asinh', 'power',
        'linear'). Default: 'asinh'
    capability_per_capita
        If True, use per capita GDP for capability. Default: True
    capability_exponent
        Exponent for capability adjustment calculation. Default: 1.0
    capability_functional_form
        Functional form for capability adjustment ('asinh', 'power',
        'linear'). Default: 'asinh'
    max_deviation_sigma
        Maximum allowed deviation from equal per capita baseline in terms of
        population-weighted standard deviations. If None, no constraint is applied.
    max_convergence_speed
        Maximum allowed convergence speed (0 to 1.0). Lower values create smoother
        pathways but may become infeasible. Default: 0.9
    strict
        If True (default), raise error for infeasible convergence.
        If False, use nearest feasible solution with warnings.
    group_level
        Index level name for grouping (typically 'iso3c'). Default: 'iso3c'
    unit_level
        Index level name for units. Default: 'unit'
    ur
        Pint unit registry for unit conversions.

    Returns
    -------
    PathwayAllocationResult
        Relative shares over time, summing to unity each year.

    See Also
    --------
    cumulative_per_capita_convergence : Without adjustments
    cumulative_per_capita_convergence_adjusted_gini : With Gini-adjusted GDP

    Notes
    -----
    **Theoretical grounding:**

    For theoretical foundations and CBDR-RC principles, see:
        docs/science/allocations.md#convergence-mechanism-theoretical-foundations
        docs/science/allocations.md#4-common-but-differentiated-responsibilities-cbdr-rc

    For translating equity principles into pathway allocations, see:
        docs/science/principle-to-code.md#convergence-pathway-approaches
        docs/science/principle-to-code.md#cbdr-rc

    This approach incorporates historical responsibility and capability adjustments
    to operationalize Common But Differentiated Responsibilities and Respective
    Capabilities (CBDR-RC). Higher past emissions and higher GDP -> smaller allocation.

    Examples
    --------
    Basic usage with equal responsibility and capability weights:

    >>> from fair_shares.library.utils import create_example_data
    >>> from fair_shares.library.allocations.pathways import (
    ...     cumulative_per_capita_convergence_adjusted,
    ... )
    >>> # Create example data
    >>> data = create_example_data(
    ...     countries=["USA", "CHN", "IND"], years=[2020, 2030, 2050]
    ... )
    >>> # Run allocation with adjustments and strict=False for limited data
    >>> result = cumulative_per_capita_convergence_adjusted(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     world_scenario_emissions_ts=data["world_emissions"],
    ...     gdp_ts=data["gdp"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     responsibility_weight=0.5,  # 50% adjustment for historical emissions
    ...     capability_weight=0.5,  # 50% adjustment for GDP
    ...     strict=False,  # Accept approximate targets with limited data
    ... )
    Converting units...
    >>> # Check results - high emitters get less than pure per-capita
    >>> result.approach
    'cumulative-per-capita-convergence-adjusted'
    >>> # Shares sum to 1.0 at each year
    >>> shares = result.relative_shares_pathway_emissions
    >>> bool(abs(shares["2020"].sum() - 1.0) < 1e-10)
    True

    Adjust convergence speed for smoother pathways:

    >>> result_smooth = cumulative_per_capita_convergence_adjusted(
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     world_scenario_emissions_ts=data["world_emissions"],
    ...     gdp_ts=data["gdp"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     responsibility_weight=0.3,
    ...     capability_weight=0.3,
    ...     max_convergence_speed=0.5,
    ...     strict=False,
    ... )  # doctest: +ELLIPSIS
    Converting units...
    >>> # Check for warnings if targets couldn't be met exactly
    >>> if result_smooth.country_warnings:  # doctest: +SKIP
    ...     print("Approximate targets:", result_smooth.country_warnings)

    Emphasize responsibility over capability:

    >>> result_responsibility = cumulative_per_capita_convergence_adjusted(
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     world_scenario_emissions_ts=data["world_emissions"],
    ...     gdp_ts=data["gdp"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     responsibility_weight=0.7,
    ...     capability_weight=0.3,
    ...     strict=False,
    ... )  # doctest: +ELLIPSIS
    Converting units...
    >>> # Historical emitters penalized more than in equal-weight case
    >>> result_responsibility.parameters["responsibility_weight"]
    0.7
    """
    return _cumulative_per_capita_convergence_core(
        population_ts=population_ts,
        country_actual_emissions_ts=country_actual_emissions_ts,
        world_scenario_emissions_ts=world_scenario_emissions_ts,
        first_allocation_year=first_allocation_year,
        emission_category=emission_category,
        gdp_ts=gdp_ts,
        gini_s=None,
        responsibility_weight=responsibility_weight,
        capability_weight=capability_weight,
        historical_responsibility_year=historical_responsibility_year,
        responsibility_per_capita=responsibility_per_capita,
        responsibility_exponent=responsibility_exponent,
        responsibility_functional_form=responsibility_functional_form,
        capability_per_capita=capability_per_capita,
        capability_exponent=capability_exponent,
        capability_functional_form=capability_functional_form,
        max_deviation_sigma=max_deviation_sigma,
        max_convergence_speed=max_convergence_speed,
        strict=strict,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )


def cumulative_per_capita_convergence_adjusted_gini(
    population_ts: TimeseriesDataFrame,
    country_actual_emissions_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    emission_category: str,
    world_scenario_emissions_ts: TimeseriesDataFrame,
    gdp_ts: TimeseriesDataFrame | None = None,
    gini_s: pd.DataFrame | None = None,
    responsibility_weight: float = 0.0,
    capability_weight: float = 0.0,
    historical_responsibility_year: int = 1990,
    responsibility_per_capita: bool = True,
    responsibility_exponent: float = 1.0,
    responsibility_functional_form: str = "asinh",
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    income_floor: float = 7500.0,
    max_gini_adjustment: float = 0.8,
    max_deviation_sigma: float | None = 2.0,
    max_convergence_speed: float = 0.9,
    strict: bool = True,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Cumulative per capita convergence with Gini-adjusted GDP and full adjustments.

    The most comprehensive variant, incorporating:

    - Responsibility adjustment: Countries with higher historical emissions
      receive smaller allocations
    - Capability adjustment: Countries with higher GDP receive smaller allocations
    - Gini adjustment: GDP is adjusted for income inequality within countries

    Mathematical Foundation
    -----------------------

    **Convergence Dynamics**

    The allocation shares evolve through exponential convergence (same as base approach):

    $$
    A(g, t+1) = A(g, t) + \lambda \big(A^{\infty}(g) - A(g, t)\big)
    $$

    Where:

    - $A(g, t)$: Allocation share for country $g$ at year $t$
    - $A^{\infty}(g)$: Long-run target share
    - $\lambda$: Convergence speed (automatically determined)

    Initial shares at first_allocation_year are based on actual emissions.

    **Cumulative Target Shares with Adjustments**

    Target shares are computed by adjusting cumulative population for
    historical responsibility and Gini-adjusted economic capability:

    $$
    T_{\text{cum}}(g) = \frac{P_{\text{adj}}(g)}{\sum_{g'} P_{\text{adj}}(g')}
    $$

    Where the adjusted population is:

    $$
    P_{\text{adj}}(g) = P_{\text{cum}}(g) \times R(g) \times C_{\text{Gini}}(g)
    $$

    Where:

    - $T_{\text{cum}}(g)$: Cumulative target share for country $g$
    - $P_{\text{adj}}(g)$: Adjusted cumulative population
    - $P_{\text{cum}}(g) = \sum_{t \geq t_a} P(g, t)$: Cumulative population from allocation year onwards
    - $R(g)$: Responsibility adjustment factor (equals 1.0 if not used)
    - $C_{\text{Gini}}(g)$: Gini-adjusted capability factor (equals 1.0 if not used)

    **Gini Adjustment Process**

    GDP is adjusted for within-country income inequality:

    $$
    \text{GDP}^{\text{adj}}(g, t) = \text{GDP}(g, t) \times (1 - \text{income-share-floor})
    $$

    Where the income share floor is calculated from the Gini coefficient and income floor
    parameters. The adjustment reduces GDP for high-inequality countries, reflecting that
    their wealth is concentrated among fewer people.

    **Responsibility Adjustment**

    Identical to adjusted convergence (see that function for details).

    For per capita responsibility (:code:`responsibility_per_capita=True`, default):

    $$
    R(g) = \left(\frac{\sum_{t=t_h}^{t_a} E(g, t)}{\sum_{t=t_h}^{t_a} P(g, t)}\right)^{-w_r \times e_r}
    $$

    Where:

    - $E(g, t)$: Emissions of country $g$ in year $t$
    - $t_h$: Historical responsibility start year
    - $t_a$: First allocation year
    - $w_r$: Normalized responsibility weight
    - $e_r$: Responsibility exponent

    **Capability Adjustment with Gini-Adjusted GDP**

    The capability metric uses Gini-adjusted GDP to account for income inequality.

    For per capita capability (:code:`capability_per_capita=True`, default):

    $$
    C_{\text{Gini}}(g) = \left(\frac{\sum_{t \geq t_a} \text{GDP}^{\text{adj}}(g, t)}{\sum_{t \geq t_a} P(g, t)}\right)^{-w_c \times e_c}
    $$

    Where:

    - $C_{\text{Gini}}(g)$: Gini-adjusted capability factor (inverse - higher adjusted GDP = lower allocation)
    - $\text{GDP}^{\text{adj}}(g, t)$: Gini-adjusted GDP in year $t$
    - $w_c$: Normalized capability weight
    - $e_c$: Capability exponent

    For absolute capability (:code:`capability_per_capita=False`):

    $$
    C_{\text{Gini}}(g) = \left(\sum_{t \geq t_a} \text{GDP}^{\text{adj}}(g, t)\right)^{-w_c \times e_c}
    $$

    **Gini Adjustment Effect**

    The Gini adjustment effectively reduces the GDP (and thus capability) of
    countries with high inequality, giving them larger emission allocations. This
    reflects that high-inequality countries have less capacity to pay because a
    larger share of their population has income below the capability threshold.

    For example, if country A and country B both have cumulative GDP per capita
    of $500,000, but country A has a Gini coefficient of 0.25 (low inequality)
    and country B has 0.50 (high inequality), country B's adjusted GDP will be
    lower, resulting in a larger emission allocation.

    **Deviation Constraint**

    When :code:`max_deviation_sigma` is provided, adjusted cumulative target shares
    are constrained to prevent extreme deviations from equal cumulative per capita.

    Parameters
    ----------
    population_ts
        Population time series for per capita calculations and responsibility
        adjustment.
    country_actual_emissions_ts
        Country emissions for initial shares and responsibility calculation.
    world_scenario_emissions_ts
        World emissions pathway defining time horizon and year weights.
    first_allocation_year
        Starting year for the allocation.
    emission_category
        The emission category (e.g., 'co2-ffi', 'all-ghg').
    gdp_ts
        GDP time series for capability adjustment. Required if
        capability_weight > 0 or gini_s provided.
    gini_s
        Gini coefficients for GDP inequality adjustment. When provided, GDP is adjusted
        to reflect income distribution within countries.
    responsibility_weight
        Weight for responsibility adjustment (0-1). Higher historical emissions
        -> smaller allocation. Must satisfy: responsibility_weight +
        capability_weight <= 1.0
    capability_weight
        Weight for capability adjustment (0-1). Higher GDP -> smaller allocation.
        Requires gdp_ts. Must satisfy: responsibility_weight + capability_weight <= 1.0
    historical_responsibility_year
        First year of responsibility window
        [historical_responsibility_year, first_allocation_year].
        Default: 1990
    responsibility_per_capita
        If True, use per capita emissions for responsibility. Default: True
    responsibility_exponent
        Exponent for responsibility adjustment calculation. Default: 1.0
    responsibility_functional_form
        Functional form for responsibility adjustment ('asinh', 'power',
        'linear'). Default: 'asinh'
    capability_per_capita
        If True, use per capita GDP for capability. Default: True
    capability_exponent
        Exponent for capability adjustment calculation. Default: 1.0
    capability_functional_form
        Functional form for capability adjustment ('asinh', 'power',
        'linear'). Default: 'asinh'
    income_floor
        Income floor for Gini adjustment (in USD). Income below this threshold
        is excluded
        from capability calculations. Default: 7500.0
    max_gini_adjustment
        Maximum reduction factor from Gini adjustment (0-1). Limits how much inequality
        can reduce effective GDP. Default: 0.8
    max_deviation_sigma
        Maximum allowed deviation from equal per capita baseline in terms of
        population-weighted standard deviations. If None, no constraint is applied.
    max_convergence_speed
        Maximum allowed convergence speed (0 to 1.0). Lower values create smoother
        pathways but may become infeasible. Default: 0.9
    strict
        If True (default), raise error for infeasible convergence.
        If False, use nearest feasible solution with warnings.
    group_level
        Index level name for grouping (typically 'iso3c'). Default: 'iso3c'
    unit_level
        Index level name for units. Default: 'unit'
    ur
        Pint unit registry for unit conversions.

    Returns
    -------
    PathwayAllocationResult
        Relative shares over time, summing to unity each year.

    See Also
    --------
    cumulative_per_capita_convergence : Without adjustments
    cumulative_per_capita_convergence_adjusted : Without Gini adjustment

    Notes
    -----
    **Theoretical grounding:**

    For theoretical foundations, intra-national equity, and Gini adjustment rationale, see:
        docs/science/allocations.md#convergence-mechanism-theoretical-foundations
        docs/science/allocations.md#gini-adjustment-for-within-country-inequality

    For translating equity principles into pathway allocations, see:
        docs/science/principle-to-code.md#convergence-pathway-approaches
        docs/science/principle-to-code.md#subsistence-protection

    This approach extends the adjusted convergence method by incorporating
    Gini-adjusted GDP to account for income inequality within countries. The
    ``income_floor`` parameter implements the subsistence vs. luxury emissions
    distinction. High-inequality countries have reduced effective capability.

    Examples
    --------
    Basic usage with Gini-adjusted GDP:

    >>> from fair_shares.library.utils import create_example_data
    >>> from fair_shares.library.allocations.pathways import (
    ...     cumulative_per_capita_convergence_adjusted_gini,
    ... )
    >>> # Create example data
    >>> data = create_example_data(
    ...     countries=["USA", "CHN", "BRA"], years=[2020, 2030, 2050]
    ... )
    >>> # Run allocation with Gini adjustment
    >>> result = cumulative_per_capita_convergence_adjusted_gini(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     world_scenario_emissions_ts=data["world_emissions"],
    ...     gdp_ts=data["gdp"],
    ...     gini_s=data["gini"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     responsibility_weight=0.5,  # 50% adjustment for historical emissions
    ...     capability_weight=0.5,  # 50% adjustment for Gini-adjusted GDP
    ... )
    Converting units...
    >>> # Check results - Gini adjustment included
    >>> result.approach
    'cumulative-per-capita-convergence-gini-adjusted'

    Adjust Gini parameters to control inequality weighting:

    >>> # Custom Gini parameters
    >>> result_custom_gini = (  # doctest: +ELLIPSIS
    ...     cumulative_per_capita_convergence_adjusted_gini(
    ...         population_ts=data["population"],
    ...         country_actual_emissions_ts=data["emissions"],
    ...         world_scenario_emissions_ts=data["world_emissions"],
    ...         gdp_ts=data["gdp"],
    ...         gini_s=data["gini"],
    ...         first_allocation_year=2020,
    ...         emission_category="co2-ffi",
    ...         responsibility_weight=0.3,
    ...         capability_weight=0.3,
    ...         income_floor=5000.0,  # Lower income floor
    ...         max_gini_adjustment=0.9,  # Allow stronger inequality adjustment
    ...         max_convergence_speed=0.5,  # Slower convergence
    ...         strict=False,  # Accept approximate targets if exact infeasible
    ...     )
    ... )
    Converting units...
    >>> # Countries with high inequality get more generous allocations
    >>> result_custom_gini.approach
    'cumulative-per-capita-convergence-gini-adjusted'
    """
    return _cumulative_per_capita_convergence_core(
        population_ts=population_ts,
        country_actual_emissions_ts=country_actual_emissions_ts,
        world_scenario_emissions_ts=world_scenario_emissions_ts,
        first_allocation_year=first_allocation_year,
        emission_category=emission_category,
        gdp_ts=gdp_ts,
        gini_s=gini_s,
        responsibility_weight=responsibility_weight,
        capability_weight=capability_weight,
        historical_responsibility_year=historical_responsibility_year,
        responsibility_per_capita=responsibility_per_capita,
        responsibility_exponent=responsibility_exponent,
        responsibility_functional_form=responsibility_functional_form,
        capability_per_capita=capability_per_capita,
        capability_exponent=capability_exponent,
        capability_functional_form=capability_functional_form,
        income_floor=income_floor,
        max_gini_adjustment=max_gini_adjustment,
        max_deviation_sigma=max_deviation_sigma,
        max_convergence_speed=max_convergence_speed,
        strict=strict,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )
