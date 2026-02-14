"""
Per capita budget allocations (equal, adjusted, and Gini-adjusted).

This module implements three related per capita budget allocation approaches
grounded in fair shares literature:

- **equal_per_capita_budget**: Allocates emission budgets proportional to population.
- **per_capita_adjusted_budget**: Extends equal per capita with historical responsibility and capability adjustments.
- **per_capita_adjusted_gini_budget**: Incorporates intra-national inequality through Gini adjustments.

See docs/science/allocations.md for theoretical grounding and academic context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from pandas_openscm.index_manipulation import (
    ensure_index_is_multiindex,
    set_index_levels_func,
)

from fair_shares.library.allocations.core import validate_weight_constraints
from fair_shares.library.allocations.results import BudgetAllocationResult
from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import (
    apply_deviation_constraint,
    apply_gini_adjustment,
    calculate_relative_adjustment,
    create_gini_lookup_dict,
    filter_time_columns,
    get_default_unit_registry,
    groupby_except_robust,
    set_single_unit,
)
from fair_shares.library.utils.math.adjustments import (
    calculate_responsibility_adjustment_data,
)
from fair_shares.library.utils.units import convert_unit_robust
from fair_shares.library.validation.models import AllocationInputs, AllocationOutputs

if TYPE_CHECKING:
    import pint.facets

    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def _per_capita_budget_core(
    population_ts: TimeseriesDataFrame,
    allocation_year: int,
    emission_category: str,
    # Optional data for adjustments
    country_actual_emissions_ts: TimeseriesDataFrame | None = None,
    gdp_ts: TimeseriesDataFrame | None = None,
    gini_s: pd.DataFrame | None = None,
    # Explicit weights (must sum to <= 1.0)
    responsibility_weight: float = 0.0,
    capability_weight: float = 0.0,
    # Responsibility parameters
    historical_responsibility_year: int = 1990,
    responsibility_per_capita: bool = True,
    responsibility_exponent: float = 1.0,
    responsibility_functional_form: str = "asinh",
    # Capability parameters
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    # Gini parameters (only used if gini_s provided)
    income_floor: float = 0.0,
    max_gini_adjustment: float = 0.8,
    # Deviation constraint
    max_deviation_sigma: float | None = 2.0,
    # Mode
    preserve_allocation_year_shares: bool = False,
    # Common parameters
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:
    """
    Core per capita budget allocation with optional adjustments.

    The approach is determined by which adjustments are applied:
    - No adjustments (weights=0, no gdp) -> equal-per-capita-budget
    - Any adjustments without Gini -> per-capita-adjusted-budget
    - Adjustments with Gini -> per-capita-adjusted-gini-budget
    """
    allocation_year = int(allocation_year)
    historical_responsibility_year = int(historical_responsibility_year)

    # Validate weights using shared function
    validate_weight_constraints(responsibility_weight, capability_weight)

    # Validate inputs using Pydantic model
    AllocationInputs(
        population_ts=population_ts,
        first_allocation_year=allocation_year,
        last_allocation_year=allocation_year,
        gdp_ts=gdp_ts,
        gini_s=gini_s,
        country_actual_emissions_ts=country_actual_emissions_ts,
        historical_responsibility_year=historical_responsibility_year
        if responsibility_weight > 0
        else None,
    )

    # Validate data requirements
    if responsibility_weight > 0 and country_actual_emissions_ts is None:
        raise AllocationError(
            format_error(
                "missing_required_data",
                adjustment_type="responsibility",
                weight_name="responsibility_weight",
                weight_value=responsibility_weight,
                data_name="historical emissions data",
                explanation=(
                    "Responsibility adjustment uses historical emissions "
                    "to reduce future allocation for countries with "
                    "higher past emissions."
                ),
                function_name="per_capita_adjusted_budget",
                data_param="country_actual_emissions_ts",
            )
        )
    if capability_weight > 0 and gdp_ts is None:
        raise AllocationError(
            format_error(
                "missing_required_data",
                adjustment_type="capability",
                weight_name="capability_weight",
                weight_value=capability_weight,
                data_name="GDP data",
                explanation=(
                    "Capability adjustment uses GDP per capita to reduce "
                    "allocation for countries with higher economic capacity."
                ),
                function_name="per_capita_adjusted_budget",
                data_param="gdp_ts",
            )
        )
    if gini_s is not None and gdp_ts is None:
        raise AllocationError(
            format_error(
                "missing_required_data",
                adjustment_type="Gini",
                weight_name="gini_s",
                weight_value="provided",
                data_name="GDP data",
                explanation=(
                    "Gini adjustment requires GDP data to calculate "
                    "inequality-corrected economic capacity."
                ),
                function_name="per_capita_adjusted_gini_budget",
                data_param="gdp_ts",
            )
        )

    # Determine approach based on inputs
    use_capability = capability_weight > 0
    use_responsibility = responsibility_weight > 0
    use_gini_adjustment = use_capability and gini_s is not None
    has_adjustments = use_responsibility or use_capability

    # Normalize weights to their sum for reporting and calculation
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
        approach = "per-capita-adjusted-gini-budget"
    elif has_adjustments:
        approach = "per-capita-adjusted-budget"
    else:
        approach = "equal-per-capita-budget"

    # Filter population to allocation_year onwards
    population_filtered = filter_time_columns(population_ts, allocation_year)
    population_single_unit = set_single_unit(population_filtered, unit_level, ur=ur)

    # Map integer year to actual column label
    year_to_label = {int(c): c for c in population_single_unit.columns}

    # Convert to common units and drop unit level for calculations
    population_single_unit = convert_unit_robust(
        population_single_unit, "million", unit_level=unit_level, ur=ur
    )
    population_numeric = population_single_unit.droplevel(unit_level)

    # Start with base population
    base_population = population_numeric.copy()

    # Apply capability adjustment if needed
    if use_capability:
        gdp_filtered = filter_time_columns(gdp_ts, allocation_year)
        gdp_single_unit = set_single_unit(gdp_filtered, unit_level, ur=ur)
        gdp_single_unit = convert_unit_robust(
            gdp_single_unit, "million", unit_level=unit_level, ur=ur
        )
        gdp_numeric = gdp_single_unit.droplevel(unit_level)

        # Find common years between GDP and population
        common_columns = population_numeric.columns.intersection(gdp_numeric.columns)
        gdp_common = gdp_numeric[common_columns]
        population_common = population_numeric[common_columns]

        # Apply Gini adjustment if provided
        if gini_s is not None:
            gini_lookup = create_gini_lookup_dict(gini_s)
            gdp_common = apply_gini_adjustment(
                gdp_data=gdp_common,
                population_data=population_common,
                gini_lookup=gini_lookup,
                income_floor=income_floor,
                max_gini_adjustment=max_gini_adjustment,
                group_level=group_level,
            )

        # Calculate capability metric based on capability_per_capita flag
        if capability_per_capita:
            # Per capita: GDP per capita
            capability_metric_common = gdp_common.divide(population_common)
        else:
            # Absolute: GDP
            capability_metric_common = gdp_common

        # Extend to all years
        capability_metric = capability_metric_common.reindex(
            population_numeric.columns, axis=1, method="ffill"
        )

        # Calculate capability adjustment (inverse of capability metric)
        capability_adjustment = calculate_relative_adjustment(
            capability_metric,
            functional_form=capability_functional_form,
            exponent=normalized_capability_weight * capability_exponent,
            inverse=True,
        )

        # Apply adjustment to population
        base_population = base_population * capability_adjustment

    # Apply responsibility adjustment if needed
    if use_responsibility:
        responsibility_data = calculate_responsibility_adjustment_data(
            country_actual_emissions_ts=country_actual_emissions_ts,
            population_ts=population_ts,
            historical_responsibility_year=historical_responsibility_year,
            allocation_year=allocation_year,
            responsibility_per_capita=responsibility_per_capita,
            group_level=group_level,
            unit_level=unit_level,
            ur=ur,
        )

        # Reindex to match population index
        responsibility_data = responsibility_data.reindex(base_population.index)

        # Calculate adjustment (inverse - higher emissions = lower allocation)
        responsibility_adjustment = calculate_relative_adjustment(
            responsibility_data,
            functional_form=responsibility_functional_form,
            exponent=normalized_responsibility_weight * responsibility_exponent,
            inverse=True,
        )

        # Broadcast adjustment across all years (constant over time)
        base_population = base_population.mul(responsibility_adjustment, axis=0)

    # Mode 1: Calculate shares using cumulative adjusted population
    # from allocation_year onwards
    if not preserve_allocation_year_shares:
        # Sum each group's adjusted population across all years
        # from allocation_year onwards
        group_totals = base_population.sum(axis=1)

        # Calculate world total using groupby_except_robust
        world_totals = groupby_except_robust(group_totals, group_level)

        # Calculate share of world adjusted population
        shares = group_totals / world_totals

        # Apply deviation constraint if specified (to cumulative shares)
        if max_deviation_sigma is not None:
            # Need population summed across years for deviation constraint
            cumulative_population = population_numeric.sum(axis=1)
            shares = apply_deviation_constraint(
                shares=pd.DataFrame({year_to_label[allocation_year]: shares}),
                population=pd.DataFrame(
                    {year_to_label[allocation_year]: cumulative_population}
                ),
                max_deviation_sigma=max_deviation_sigma,
                group_level=group_level,
            )[year_to_label[allocation_year]]

    # Mode 2: Calculate shares using adjusted population at allocation_year
    else:
        adjusted_pop_at_ay = base_population[year_to_label[allocation_year]]
        world_totals = groupby_except_robust(adjusted_pop_at_ay, group_level)
        shares = adjusted_pop_at_ay / world_totals

        # Apply deviation constraint if specified (to shares at allocation_year)
        if max_deviation_sigma is not None:
            population_at_ay = population_numeric[year_to_label[allocation_year]]
            shares = apply_deviation_constraint(
                shares=pd.DataFrame({year_to_label[allocation_year]: shares}),
                population=pd.DataFrame(
                    {year_to_label[allocation_year]: population_at_ay}
                ),
                max_deviation_sigma=max_deviation_sigma,
                group_level=group_level,
            )[year_to_label[allocation_year]]

    # Create DataFrame with only allocation_year column
    shares_df = pd.DataFrame({year_to_label[allocation_year]: shares})

    # Set units to dimensionless
    shares_df = ensure_index_is_multiindex(shares_df)
    shares_df = set_index_levels_func(
        shares_df, {unit_level: "dimensionless"}, copy=False
    )

    # Add emission category to the index
    shares_df = shares_df.assign(**{"emission-category": emission_category})
    shares_df = shares_df.set_index("emission-category", append=True)

    # Build parameters dict
    # Build parameters dict (always include normalized weights for reporting)
    parameters = {
        "allocation_year": allocation_year,
        "preserve_allocation_year_shares": preserve_allocation_year_shares,
        "responsibility_weight": normalized_responsibility_weight,
        "capability_weight": normalized_capability_weight,
        "emission_category": emission_category,
        "group_level": group_level,
        "unit_level": unit_level,
    }

    # Add responsibility parameters if used
    if use_responsibility:
        parameters.update(
            {
                "historical_responsibility_year": historical_responsibility_year,
                "responsibility_per_capita": responsibility_per_capita,
                "responsibility_exponent": responsibility_exponent,
                "responsibility_functional_form": responsibility_functional_form,
            }
        )
    if use_capability:
        parameters.update(
            {
                "capability_exponent": capability_exponent,
                "capability_functional_form": capability_functional_form,
            }
        )
    if use_gini_adjustment:
        parameters.update(
            {
                "income_floor": income_floor,
                "max_gini_adjustment": max_gini_adjustment,
            }
        )
    if max_deviation_sigma is not None:
        parameters["max_deviation_sigma"] = max_deviation_sigma

    # Validate outputs using Pydantic model
    AllocationOutputs(
        shares=shares_df,
        dataset_name=f"{approach} budget allocation",
        first_year=allocation_year,
    )

    # Create and return BudgetAllocationResult
    return BudgetAllocationResult(
        approach=approach,
        parameters=parameters,
        relative_shares_cumulative_emission=shares_df,
    )


def equal_per_capita_budget(
    population_ts: TimeseriesDataFrame,
    allocation_year: int,
    emission_category: str,
    preserve_allocation_year_shares: bool = False,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:
    r"""
    Equal per capita budget allocation for cumulative emissions.

    This function generates cumulative shares for the allocation year based
    on equal per capita principles.

    Mathematical Foundation
    -----------------------

    Two allocation modes are supported:

    **Mode 1: Dynamic shares (preserve_allocation_year_shares=False, default)**

    Population shares are calculated using cumulative population from
    allocation_year onwards. This accounts for changes in relative
    population shares over time:

    $$
    A(g) = \frac{\sum_{t \geq t_a} P(g, t)}{\sum_{g} \sum_{t \geq t_a} P(g, t)}
    $$

    Where:

    - $A(g)$: Budget share allocated to country $g$
    - $P(g, t)$: Population of country $g$ in year $t$
    - $t_a$: Allocation year
    - $\sum_{t \geq t_a} P(g, t)$: Cumulative population of country $g$ from allocation year onwards
    - $\sum_{g} \sum_{t \geq t_a} P(g, t)$: Total cumulative population across all countries from allocation year onwards

    **Mode 2: Preserved shares (preserve_allocation_year_shares=True)**

    Population shares calculated at the allocation year are preserved.
    This means the relative allocation between groups remains constant:

    $$
    A(g) = \frac{P(g, t_a)}{\sum_{g} P(g, t_a)}
    $$

    Where:

    - $A(g)$: Budget share allocated to country $g$
    - $P(g, t_a)$: Population of country $g$ at allocation year $t_a$
    - $\sum_{g} P(g, t_a)$: Total world population at allocation year

    Parameters
    ----------
    population_ts
        Timeseries of population for each group of interest
    allocation_year
        Year from which to start calculating allocations and budgets.
        See docs/science/parameter-effects.md#allocation_year for how this affects
        country shares
    emission_category
        Emission category to include in the output
    preserve_allocation_year_shares
        If False (default), shares are calculated using cumulative population
        from allocation_year onwards. If True, shares calculated at
        allocation_year are preserved
    group_level
        Level in the index which specifies group information
    unit_level
        Level in the index which specifies the unit of each timeseries
    ur
        The unit registry to use for calculations

    Returns
    -------
    BudgetAllocationResult
        Container with relative shares for cumulative emissions budget allocation.
        The TimeseriesDataFrame contains only the allocation_year column with
        population shares that sum to 1 across groups for the specified
        emission category.

    Notes
    -----
    **Theoretical grounding:**

    See docs/science/allocations.md#equal-per-capita for detailed mathematical
    formulation, limitations, and when to use this approach.

    For translating the egalitarian tradition (which grounds the equal per capita
    principle) into code, see docs/science/principle-to-code.md#egalitarianism
    for implementation guidance.

    Examples
    --------
    Calculate equal per capita budget allocation for 2020:

    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data()
    >>> result = equal_per_capita_budget(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     allocation_year=2020,
    ...     emission_category="co2-ffi",
    ... )
    Converting units...
    >>> result.approach
    'equal-per-capita-budget'
    >>> # Shares are proportional to population
    >>> shares = result.relative_shares_cumulative_emission
    >>> bool(abs(shares["2020"].sum() - 1.0) < 1e-10)  # Should sum to 1.0
    True

    Using preserve_allocation_year_shares to fix shares at allocation year:

    >>> result_preserved = equal_per_capita_budget(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     preserve_allocation_year_shares=True,
    ... )
    Converting units...
    >>> # Shares are based only on 2020 population, not cumulative from 2020 onwards
    >>> result_preserved.parameters["preserve_allocation_year_shares"]
    True
    """
    return _per_capita_budget_core(
        population_ts=population_ts,
        allocation_year=allocation_year,
        emission_category=emission_category,
        responsibility_weight=0.0,
        capability_weight=0.0,
        preserve_allocation_year_shares=preserve_allocation_year_shares,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )


def per_capita_adjusted_budget(
    population_ts: TimeseriesDataFrame,
    allocation_year: int,
    emission_category: str,
    # Optional adjustment data
    country_actual_emissions_ts: TimeseriesDataFrame | None = None,
    gdp_ts: TimeseriesDataFrame | None = None,
    # Adjustment weights
    responsibility_weight: float = 0.0,
    capability_weight: float = 0.0,
    # Responsibility parameters
    historical_responsibility_year: int = 1990,
    responsibility_per_capita: bool = True,
    responsibility_exponent: float = 1.0,
    responsibility_functional_form: str = "asinh",
    # Capability parameters
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    # Deviation constraint
    max_deviation_sigma: float | None = 2.0,
    # Mode
    preserve_allocation_year_shares: bool = False,
    # Common parameters
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:
    r"""
    Per capita budget allocation with responsibility and capability adjustments.

    This function generates cumulative shares for the allocation year based
    on adjusted per capita principles, incorporating historical responsibility
    and economic capability adjustments (but without Gini correction).

    Mathematical Foundation
    -----------------------

    The per capita adjusted budget allocation adjusts for historical responsibility
    and economic capability using the following approach.

    **Core Allocation Formula**

    For budget allocation with dynamic shares (default mode):

    $$
    A(g) = \frac{\sum_{t \geq t_a} R(g) \times C(g, t) \times P(g, t)}{\sum_g \sum_{t \geq t_a} R(g) \times C(g, t) \times P(g, t)}
    $$

    Where:

    - $A(g)$: Budget share allocated to country $g$
    - $R(g)$: Responsibility adjustment factor for country $g$ (constant over time, equals 1.0 if not used)
    - $C(g, t)$: Capability adjustment factor for country $g$ in year $t$ (equals 1.0 if not used)
    - $P(g, t)$: Population of country $g$ in year $t$
    - $t_a$: Allocation year

    **Responsibility Adjustment**

    Historical emissions reduce future allocation rights.

    For per capita responsibility (:code:`responsibility_per_capita=True`, default):

    $$
    R(g) = \left(\frac{\sum_{t=t_h}^{t_a-1} E(g, t)}{\sum_{t=t_h}^{t_a-1} P(g, t)}\right)^{-w_r \times e_r}
    $$

    Where:

    - $R(g)$: Responsibility adjustment factor (inverse - higher emissions = lower allocation)
    - $E(g, t)$: Emissions of country $g$ in year $t$
    - $t_h$: Historical responsibility start year
    - $t_a$: Allocation year
    - $w_r$: Normalized responsibility weight
    - $e_r$: Responsibility exponent

    For absolute responsibility (:code:`responsibility_per_capita=False`):

    $$
    R(g) = \left(\sum_{t=t_h}^{t_a-1} E(g, t)\right)^{-w_r \times e_r}
    $$

    **Capability Adjustment**

    Economic capacity reduces allocation rights for wealthier countries.

    For per capita capability (:code:`capability_per_capita=True`, default):

    $$
    C(g, t) = \left(\frac{\text{GDP}(g, t)}{P(g, t)}\right)^{-w_c \times e_c}
    $$

    Where:

    - $C(g, t)$: Capability adjustment factor (inverse - higher GDP per capita = lower allocation)
    - $\text{GDP}(g, t)$: Gross domestic product of country $g$ in year $t$
    - $w_c$: Normalized capability weight
    - $e_c$: Capability exponent

    For absolute capability (:code:`capability_per_capita=False`):

    $$
    C(g, t) = \text{GDP}(g, t)^{-w_c \times e_c}
    $$

    Two allocation modes are supported based on
    :code:`preserve_allocation_year_shares`:

    - **False** (default): Uses cumulative adjusted population from
      allocation_year onwards
    - **True**: Uses adjusted population at allocation_year only

    Parameters
    ----------
    population_ts
        Timeseries of population for each group of interest
    allocation_year
        Year from which to start calculating allocations and budgets.
        See docs/science/parameter-effects.md#allocation_year for how this affects
        country shares
    emission_category
        Emission category to include in the output
    country_actual_emissions_ts
        Historical emissions data (required if responsibility_weight > 0)
    gdp_ts
        GDP data (required if capability_weight > 0)
    responsibility_weight
        Weight for historical responsibility adjustment (0.0 to 1.0).
        See docs/science/parameter-effects.md#responsibility_weight for real
        allocation examples showing how this affects country shares
    capability_weight
        Weight for economic capability adjustment (0.0 to 1.0).
        See docs/science/parameter-effects.md#capability_weight for real
        allocation examples showing how this affects country shares
    historical_responsibility_year
        Start year for calculating historical responsibility (default: 1990)
    responsibility_per_capita
        If True, use per capita emissions; if False, use absolute emissions
    responsibility_exponent
        Exponent for the responsibility adjustment function
    responsibility_functional_form
        Functional form for responsibility: "asinh" or "power"
    capability_exponent
        Exponent for the capability adjustment function
    capability_functional_form
        Functional form for capability: "asinh" or "power"
    max_deviation_sigma
        Maximum allowed deviation from equal per capita in standard deviations.
        If None, no constraint is applied
    preserve_allocation_year_shares
        If False (default), shares are calculated using cumulative adjusted
        population from allocation_year onwards. If True, shares calculated at
        allocation_year are preserved
    group_level
        Level in the index which specifies group information
    unit_level
        Level in the index which specifies the unit of each timeseries
    ur
        The unit registry to use for calculations

    Returns
    -------
    BudgetAllocationResult
        Container with relative shares for cumulative emissions budget
        allocation. The TimeseriesDataFrame contains only the allocation_year
        column with adjusted population shares that sum to 1 across groups for
        the specified emission category.

    Notes
    -----
    **Theoretical grounding:**

    See docs/science/allocations.md#per-capita-adjusted for detailed mathematical
    formulation, parameter considerations, and CBDR-RC alignment.

    For translating equity principles into code, see:

    - docs/science/principle-to-code.md#historical-responsibility-polluter-pays
      for responsibility weight implementation
    - docs/science/principle-to-code.md#capability-ability-to-pay for capability
      weight implementation
    - docs/science/principle-to-code.md#cbdr-rc for combining both principles

    Examples
    --------
    Calculate allocation with both responsibility and capability adjustments:

    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data()
    >>> result = per_capita_adjusted_budget(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     allocation_year=2030,
    ...     emission_category="co2-ffi",
    ...     country_actual_emissions_ts=data["emissions"],
    ...     gdp_ts=data["gdp"],
    ...     responsibility_weight=0.5,
    ...     capability_weight=0.5,
    ...     historical_responsibility_year=2020,
    ... )
    Converting units...
    >>> result.approach
    'per-capita-adjusted-budget'
    >>> # Shares sum to 1.0
    >>> shares = result.relative_shares_cumulative_emission
    >>> bool(abs(shares["2030"].sum() - 1.0) < 1e-10)
    True
    >>> # Parameters include normalized weights
    >>> result.parameters["responsibility_weight"]  # doctest: +ELLIPSIS
    0.5...
    >>> result.parameters["capability_weight"]  # doctest: +ELLIPSIS
    0.5...

    Using only responsibility adjustment (no capability):

    >>> result_resp_only = per_capita_adjusted_budget(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     allocation_year=2030,
    ...     emission_category="co2-ffi",
    ...     country_actual_emissions_ts=data["emissions"],
    ...     responsibility_weight=1.0,
    ...     capability_weight=0.0,
    ...     historical_responsibility_year=2020,
    ... )
    Converting units...
    >>> # Countries with higher historical emissions get lower allocations
    >>> result_resp_only.approach
    'per-capita-adjusted-budget'
    >>> result_resp_only.parameters["responsibility_weight"]  # doctest: +ELLIPSIS
    1.0...
    >>> result_resp_only.parameters["capability_weight"]  # doctest: +ELLIPSIS
    0.0...
    """
    return _per_capita_budget_core(
        population_ts=population_ts,
        allocation_year=allocation_year,
        emission_category=emission_category,
        country_actual_emissions_ts=country_actual_emissions_ts,
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
        preserve_allocation_year_shares=preserve_allocation_year_shares,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )


def per_capita_adjusted_gini_budget(
    population_ts: TimeseriesDataFrame,
    gdp_ts: TimeseriesDataFrame,
    gini_s: pd.DataFrame,
    allocation_year: int,
    emission_category: str,
    # Optional adjustment data
    country_actual_emissions_ts: TimeseriesDataFrame | None = None,
    # Adjustment weights
    responsibility_weight: float = 0.0,
    capability_weight: float = 1.0,
    # Responsibility parameters
    historical_responsibility_year: int = 1990,
    responsibility_per_capita: bool = True,
    responsibility_exponent: float = 1.0,
    responsibility_functional_form: str = "asinh",
    # Capability parameters
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    # Gini parameters
    income_floor: float = 0.0,
    max_gini_adjustment: float = 0.8,
    # Deviation constraint
    max_deviation_sigma: float | None = 2.0,
    # Mode
    preserve_allocation_year_shares: bool = False,
    # Common parameters
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:
    r"""
    Per capita budget allocation with responsibility, capability, and Gini adjustments.

    This function generates cumulative shares for the allocation year based
    on adjusted per capita principles, incorporating historical responsibility,
    Gini-corrected GDP capability adjustments, and inequality considerations.

    Mathematical Foundation
    -----------------------

    The Gini-adjusted budget allocation extends the per capita adjusted approach
    by incorporating income inequality within countries.

    **Core Allocation Formula**

    For budget allocation with dynamic shares (default mode):

    $$
    A(g) = \frac{\sum_{t \geq t_a} R(g) \times C_{\text{Gini}}(g, t) \times P(g, t)}{\sum_g \sum_{t \geq t_a} R(g) \times C_{\text{Gini}}(g, t) \times P(g, t)}
    $$

    Where:

    - $A(g)$: Budget share allocated to country $g$
    - $R(g)$: Responsibility adjustment factor (equals 1.0 if not used)
    - $C_{\text{Gini}}(g, t)$: Gini-adjusted capability factor (equals 1.0 if not used)
    - $P(g, t)$: Population of country $g$ in year $t$
    - $t_a$: Allocation year

    **Gini Adjustment Process**

    GDP is adjusted for within-country income inequality using the Gini coefficient.
    This process modifies the GDP values used in capability calculations:

    $$
    \text{GDP}^{\text{adj}}(g, t) = \text{GDP}(g, t) \times (1 - \text{income-share-floor})
    $$

    Where the income share floor is calculated from the Gini coefficient and income floor
    parameters. The adjustment reduces GDP for high-inequality countries, reflecting that
    their wealth is concentrated among fewer people.

    **Responsibility Adjustment**

    Identical to per capita adjusted budget (see that function for details).

    For per capita responsibility (:code:`responsibility_per_capita=True`, default):

    $$
    R(g) = \left(\frac{\sum_{t=t_h}^{t_a-1} E(g, t)}{\sum_{t=t_h}^{t_a-1} P(g, t)}\right)^{-w_r \times e_r}
    $$

    Where:

    - $E(g, t)$: Emissions of country $g$ in year $t$
    - $t_h$: Historical responsibility start year
    - $t_a$: Allocation year
    - $w_r$: Normalized responsibility weight
    - $e_r$: Responsibility exponent

    **Capability Adjustment with Gini-Adjusted GDP**

    For per capita capability (:code:`capability_per_capita=True`, default):

    $$
    C_{\text{Gini}}(g, t) = \left(\frac{\text{GDP}^{\text{adj}}(g, t)}{P(g, t)}\right)^{-w_c \times e_c}
    $$

    Where:

    - $C_{\text{Gini}}(g, t)$: Gini-adjusted capability factor (inverse - higher adjusted GDP = lower allocation)
    - $\text{GDP}^{\text{adj}}(g, t)$: Gini-adjusted GDP (reduced for high-inequality countries)
    - $w_c$: Normalized capability weight
    - $e_c$: Capability exponent

    The Gini adjustment effectively reduces capability for high-inequality countries,
    giving them larger emission allocations than unadjusted GDP would suggest.

    Two allocation modes are supported based on
    :code:`preserve_allocation_year_shares`:

    - **False** (default): Uses cumulative adjusted population from
      allocation_year onwards
    - **True**: Uses adjusted population at allocation_year only

    Parameters
    ----------
    population_ts
        Timeseries of population for each group of interest
    gdp_ts
        Timeseries of GDP for each group of interest (required)
    gini_s
        DataFrame containing Gini coefficient data for each group (required)
    allocation_year
        Year from which to start calculating allocations and budgets.
        See docs/science/parameter-effects.md#allocation_year for how this affects
        country shares
    emission_category
        Emission category to include in the output
    country_actual_emissions_ts
        Historical emissions data (required if responsibility_weight > 0)
    responsibility_weight
        Weight for historical responsibility adjustment (0.0 to 1.0).
        See docs/science/parameter-effects.md#responsibility_weight for real
        allocation examples showing how this affects country shares
    capability_weight
        Weight for economic capability adjustment (0.0 to 1.0, default 1.0)
    historical_responsibility_year
        Start year for calculating historical responsibility (default: 1990)
    responsibility_per_capita
        If True, use per capita emissions; if False, use absolute emissions
    responsibility_exponent
        Exponent for the responsibility adjustment function
    responsibility_functional_form
        Functional form for responsibility: "asinh" or "power"
    capability_exponent
        Exponent for the capability adjustment function
    capability_functional_form
        Functional form for capability: "asinh" or "power"
    income_floor
        Minimum income floor for Gini adjustment calculations.
        See docs/science/parameter-effects.md#income_floor for real allocation
        examples showing how this affects country shares
    max_gini_adjustment
        Maximum allowed Gini adjustment factor
    max_deviation_sigma
        Maximum allowed deviation from equal per capita in standard deviations.
        If None, no constraint is applied
    preserve_allocation_year_shares
        If False (default), shares are calculated using cumulative adjusted
        population from allocation_year onwards. If True, shares calculated at
        allocation_year are preserved
    group_level
        Level in the index which specifies group information
    unit_level
        Level in the index which specifies the unit of each timeseries
    ur
        The unit registry to use for calculations

    Returns
    -------
    BudgetAllocationResult
        Container with relative shares for cumulative emissions budget
        allocation. The TimeseriesDataFrame contains only the allocation_year
        column with Gini-adjusted capability-weighted population shares that
        sum to 1 across groups for the specified emission category.

    Notes
    -----
    **Theoretical grounding:**

    See docs/science/allocations.md#gini-adjusted for detailed mathematical
    formulation, intra-national equity considerations, and when to use this approach.

    For translating equity principles into code, see:

    - docs/science/principle-to-code.md#subsistence-protection for income floor
      and Gini adjustment implementation
    - docs/science/principle-to-code.md#cbdr-rc for combining with responsibility
      and capability

    Examples
    --------
    Calculate allocation with Gini-adjusted capability (no responsibility):

    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data()
    >>> result = per_capita_adjusted_gini_budget(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     gdp_ts=data["gdp"],
    ...     gini_s=data["gini"],
    ...     allocation_year=2030,
    ...     emission_category="co2-ffi",
    ...     responsibility_weight=0.0,
    ...     capability_weight=1.0,
    ... )
    Converting units...
    >>> result.approach
    'per-capita-adjusted-gini-budget'
    >>> # Shares are adjusted for inequality in addition to GDP
    >>> shares = result.relative_shares_cumulative_emission
    >>> bool(abs(shares["2030"].sum() - 1.0) < 1e-10)  # Should sum to 1.0
    True
    >>> # Gini parameters are stored in result
    >>> result.parameters["income_floor"]  # doctest: +ELLIPSIS
    0.0...
    >>> result.parameters["max_gini_adjustment"]  # doctest: +ELLIPSIS
    0.8...

    Calculate allocation with both responsibility and Gini-adjusted capability:

    >>> result_full = per_capita_adjusted_gini_budget(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     gdp_ts=data["gdp"],
    ...     gini_s=data["gini"],
    ...     allocation_year=2030,
    ...     emission_category="co2-ffi",
    ...     country_actual_emissions_ts=data["emissions"],
    ...     responsibility_weight=0.5,
    ...     capability_weight=0.5,
    ...     historical_responsibility_year=2020,
    ... )
    Converting units...
    >>> result_full.approach
    'per-capita-adjusted-gini-budget'
    >>> # Both adjustments are reflected in parameters
    >>> result_full.parameters["responsibility_weight"]  # doctest: +ELLIPSIS
    0.5...
    >>> result_full.parameters["capability_weight"]  # doctest: +ELLIPSIS
    0.5...
    >>> # High inequality countries get higher allocations than GDP alone suggests
    >>> shares_full = result_full.relative_shares_cumulative_emission
    >>> bool(abs(shares_full["2030"].sum() - 1.0) < 1e-10)
    True
    """
    return _per_capita_budget_core(
        population_ts=population_ts,
        allocation_year=allocation_year,
        emission_category=emission_category,
        country_actual_emissions_ts=country_actual_emissions_ts,
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
        preserve_allocation_year_shares=preserve_allocation_year_shares,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )
