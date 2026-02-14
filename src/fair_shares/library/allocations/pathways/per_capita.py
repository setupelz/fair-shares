"""
Per capita pathway allocations (equal, adjusted, and Gini-adjusted).

This module implements three related per capita pathway allocation approaches:

- **equal_per_capita**: Allocates emission pathways proportional to population.
- **per_capita_adjusted**: Extends equal per capita with historical responsibility
  and capability adjustments, operationalizing CBDR-RC principles.
- **per_capita_adjusted_gini**: Further incorporates intra-national inequality
  through Gini adjustments.

See docs/science/allocations.md for theoretical grounding and literature review.

Unlike budget allocations (which allocate cumulative totals), pathway allocations
produce year-by-year shares that can respond dynamically to changing population
and capability over time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from pandas_openscm.index_manipulation import (
    ensure_index_is_multiindex,
    set_index_levels_func,
)

from fair_shares.library.allocations.core import validate_weight_constraints
from fair_shares.library.allocations.results import PathwayAllocationResult
from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import (
    apply_deviation_constraint,
    apply_gini_adjustment,
    broadcast_shares_to_periods,
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


def _per_capita_core(
    population_ts: TimeseriesDataFrame,
    first_allocation_year: int,
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
    preserve_first_allocation_year_shares: bool = False,
    # Common parameters
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    """
    Core per capita allocation with optional adjustments.

    The approach is determined by which adjustments are applied:
    - No adjustments (weights=0, no gdp) -> equal-per-capita
    - Any adjustments without Gini -> per-capita-adjusted
    - Adjustments with Gini -> per-capita-adjusted-gini
    """
    first_allocation_year = int(first_allocation_year)
    historical_responsibility_year = int(historical_responsibility_year)

    # Validate weights using shared function
    validate_weight_constraints(responsibility_weight, capability_weight)

    # Determine last year from population data
    last_year = int(max(population_ts.columns, key=lambda x: int(x)))

    # Validate inputs using Pydantic model
    AllocationInputs(
        population_ts=population_ts,
        first_allocation_year=first_allocation_year,
        last_allocation_year=last_year,
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
                data_name="country_actual_emissions_ts",
                explanation=(
                    "Historical emissions data is needed to calculate which "
                    "countries bear more responsibility for climate change."
                ),
                function_name="per_capita_adjusted",
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
                data_name="gdp_ts",
                explanation=(
                    "GDP data is needed to calculate which countries have "
                    "greater capacity to reduce emissions."
                ),
                function_name="per_capita_adjusted",
                data_param="gdp_ts",
            )
        )
    if gini_s is not None and gdp_ts is None:
        raise AllocationError(
            format_error(
                "missing_required_data",
                adjustment_type="Gini",
                weight_name="(via gini_s parameter)",
                weight_value="provided",
                data_name="GDP data",
                explanation=(
                    "Gini adjustment requires GDP data to apply inequality "
                    "corrections to GDP per capita calculations."
                ),
                function_name="per_capita_adjusted_gini",
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
        approach = "per-capita-adjusted-gini"
    elif has_adjustments:
        approach = "per-capita-adjusted"
    else:
        approach = "equal-per-capita"

    # Subset input data to only include years from first_allocation_year onwards
    population_filtered = filter_time_columns(population_ts, first_allocation_year)
    population_single_unit = set_single_unit(population_filtered, unit_level, ur=ur)

    # Convert to common units and drop unit level
    population_single_unit = convert_unit_robust(
        population_single_unit, "million", unit_level=unit_level, ur=ur
    )
    population_numeric = population_single_unit.droplevel(unit_level)

    # Robust mapping from integer year to existing column label
    pop_year_to_label = {int(c): c for c in population_numeric.columns}

    # Mode 1: Calculate shares at each year (dynamic allocation)
    if not preserve_first_allocation_year_shares:
        # Start with base population for each year
        base_population = population_numeric.copy()

        # Calculate capability adjustment if needed
        if use_capability:
            gdp_filtered = filter_time_columns(gdp_ts, first_allocation_year)
            gdp_single_unit = set_single_unit(gdp_filtered, unit_level, ur=ur)
            gdp_single_unit = convert_unit_robust(
                gdp_single_unit, "million", unit_level=unit_level, ur=ur
            )
            gdp_numeric = gdp_single_unit.droplevel(unit_level)

            # Find common years between population and GDP
            common_columns = population_numeric.columns.intersection(
                gdp_numeric.columns
            )
            gdp_common = gdp_numeric[common_columns]
            pop_common = population_numeric[common_columns]

            # Apply Gini adjustment if provided
            if gini_s is not None:
                gini_lookup = create_gini_lookup_dict(gini_s)
                gdp_common = apply_gini_adjustment(
                    gdp_common,
                    pop_common,
                    gini_lookup,
                    income_floor,
                    max_gini_adjustment,
                    group_level,
                )

            # Calculate capability metric based on capability_per_capita flag
            if capability_per_capita:
                # Per capita: cumulative GDP per capita
                gdp_cumsum = gdp_common.cumsum(axis=1)
                pop_cumsum = pop_common.cumsum(axis=1)
                capability_metric = gdp_cumsum.divide(pop_cumsum)
            else:
                # Absolute: cumulative GDP
                capability_metric = gdp_common.cumsum(axis=1)

            # Extend to all years in population data (forward fill)
            capability_metric = capability_metric.reindex(
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

        # Calculate responsibility adjustment if needed
        if use_responsibility:
            responsibility_data = calculate_responsibility_adjustment_data(
                country_actual_emissions_ts=country_actual_emissions_ts,
                population_ts=population_ts,
                historical_responsibility_year=historical_responsibility_year,
                allocation_year=first_allocation_year,
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

        # Calculate shares: adjusted_population / total_adjusted_population
        total_adjusted_population = groupby_except_robust(base_population, group_level)
        res = base_population.divide(total_adjusted_population)

        # Apply deviation constraint if provided
        if max_deviation_sigma is not None:
            res = apply_deviation_constraint(
                res, population_numeric, max_deviation_sigma, group_level
            )

    # Mode 2: Calculate shares at first_allocation_year and broadcast
    else:
        # Get population at first year
        population_at_ta = population_numeric[pop_year_to_label[first_allocation_year]]
        base_population_at_ta = population_at_ta.copy()

        # Calculate capability adjustment if needed
        if use_capability:
            gdp_filtered = filter_time_columns(gdp_ts, first_allocation_year)
            gdp_single_unit = set_single_unit(gdp_filtered, unit_level, ur=ur)
            gdp_single_unit = convert_unit_robust(
                gdp_single_unit, "million", unit_level=unit_level, ur=ur
            )
            gdp_numeric = gdp_single_unit.droplevel(unit_level)
            gdp_year_to_label = {int(c): c for c in gdp_numeric.columns}

            gdp_at_ta = gdp_numeric[gdp_year_to_label[first_allocation_year]]

            # Apply Gini adjustment if provided
            if gini_s is not None:
                gini_lookup = create_gini_lookup_dict(gini_s)
                gdp_at_ta = apply_gini_adjustment(
                    gdp_at_ta,
                    population_at_ta,
                    gini_lookup,
                    income_floor,
                    max_gini_adjustment,
                    group_level,
                )

            # Calculate capability metric based on capability_per_capita flag
            if capability_per_capita:
                # Per capita: GDP per capita at first year
                capability_metric = gdp_at_ta.divide(population_at_ta)
            else:
                # Absolute: GDP at first year
                capability_metric = gdp_at_ta

            # Calculate capability adjustment
            capability_adjustment = calculate_relative_adjustment(
                capability_metric,
                functional_form=capability_functional_form,
                exponent=normalized_capability_weight * capability_exponent,
                inverse=True,
            )

            base_population_at_ta = base_population_at_ta * capability_adjustment

        # Calculate responsibility adjustment if needed
        if use_responsibility:
            responsibility_data = calculate_responsibility_adjustment_data(
                country_actual_emissions_ts=country_actual_emissions_ts,
                population_ts=population_ts,
                historical_responsibility_year=historical_responsibility_year,
                allocation_year=first_allocation_year,
                responsibility_per_capita=responsibility_per_capita,
                group_level=group_level,
                unit_level=unit_level,
                ur=ur,
            )

            responsibility_data = responsibility_data.reindex(
                base_population_at_ta.index
            )

            responsibility_adjustment = calculate_relative_adjustment(
                responsibility_data,
                functional_form=responsibility_functional_form,
                exponent=normalized_responsibility_weight * responsibility_exponent,
                inverse=True,
            )

            base_population_at_ta = base_population_at_ta * responsibility_adjustment

        # Calculate shares at first year
        total_at_ta = groupby_except_robust(base_population_at_ta, group_level)
        shares_at_ta = base_population_at_ta.divide(total_at_ta)

        # Apply deviation constraint if provided
        if max_deviation_sigma is not None:
            shares_at_ta = apply_deviation_constraint(
                shares_at_ta, population_at_ta, max_deviation_sigma, group_level
            )

        # Broadcast across all time periods
        res = broadcast_shares_to_periods(shares_at_ta, population_filtered.columns)

    # Format output with proper index structure and units
    res = ensure_index_is_multiindex(res)
    res = set_index_levels_func(res, {unit_level: "dimensionless"}, copy=False)

    # Add emission category to the index
    res = res.assign(**{"emission-category": emission_category})
    res = res.set_index("emission-category", append=True)

    # Build parameters dict (always include weights for reporting)
    parameters = {
        "first_allocation_year": first_allocation_year,
        "preserve_first_allocation_year_shares": preserve_first_allocation_year_shares,
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

    # Add capability parameters if used
    if use_capability:
        parameters.update(
            {
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

    # Validate outputs using Pydantic model
    AllocationOutputs(
        shares=res,
        dataset_name=f"{approach} pathway allocation",
        first_year=first_allocation_year,
    )

    return PathwayAllocationResult(
        approach=approach,
        parameters=parameters,
        relative_shares_pathway_emissions=res,
    )


def equal_per_capita(
    population_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    emission_category: str,
    preserve_first_allocation_year_shares: bool = False,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Equal per capita pathway allocation based on population shares.

    Allocates emissions in proportion to population, with no adjustments for
    historical responsibility or economic capability.

    Mathematical Foundation
    -----------------------

    **Mode 1: Dynamic shares (preserve_first_allocation_year_shares=False, default)**

    Population shares are calculated at each year from first_allocation_year
    onwards. This accounts for changes in relative population shares over time:

    $$
    A(g, t) = \frac{P(g, t)}{\sum_{g'} P(g', t)}
    $$

    Where:

    - $A(g, t)$: Allocation share for country $g$ at year $t$
    - $P(g, t)$: Population of country $g$ at year $t$
    - $\sum_{g'} P(g', t)$: Total world population at year $t$

    **Mode 2: Preserved shares (preserve_first_allocation_year_shares=True)**

    Population shares calculated at the first_allocation_year are preserved across
    all periods. This means the relative allocation between groups remains constant:

    $$
    A(g, t) = \frac{P(g, t_a)}{\sum_{g'} P(g', t_a)} \quad \forall t \geq t_a
    $$

    Where:

    - $A(g, t)$: Allocation share for country $g$ at year $t$ (constant for all $t \geq t_a$)
    - $P(g, t_a)$: Population of country $g$ at first allocation year $t_a$
    - $\sum_{g'} P(g', t_a)$: Total world population at first allocation year

    Parameters
    ----------
    population_ts
        Population time series for each group of interest.
    first_allocation_year
        First year that should be used for calculating the allocation.
        This must be a column in population_ts.
        See docs/science/parameter-effects.md#allocation_year for how this affects
        country shares
    emission_category
        Emission category to include in the output.
    preserve_first_allocation_year_shares
        If False (default), shares are calculated at each year from
        first_allocation_year onwards. If True, shares calculated at the
        first_allocation_year are preserved across all periods.
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

    Notes
    -----
    The equal per capita principle treats the atmosphere as a finite shared resource
    with equal claims per person. It serves as a widely used baseline in climate
    equity analysis.

    **When to Use**

    - As a baseline to compare against adjusted approaches
    - When transparency and simplicity are priorities
    - As a reference point before applying responsibility or capability adjustments

    See docs/science/allocations.md for theoretical grounding and limitations.

    Examples
    --------
    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data()
    >>> result = equal_per_capita(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ... )
    Converting units...
    >>> # Check that shares sum to 1.0 at each year
    >>> shares = result.relative_shares_pathway_emissions
    >>> shares_2020 = shares["2020"]
    >>> bool(abs(shares_2020.sum() - 1.0) < 1e-10)
    True
    >>> # China and India have similar populations, so similar shares
    >>> bool(shares_2020.loc["CHN"].item() > 0.3)  # China has large population
    True
    >>> bool(shares_2020.loc["IND"].item() > 0.3)  # India has large population too
    True

    See Also
    --------
    per_capita_adjusted : With responsibility/capability adjustments
    per_capita_adjusted_gini : With Gini-adjusted GDP
    """
    return _per_capita_core(
        population_ts=population_ts,
        first_allocation_year=first_allocation_year,
        emission_category=emission_category,
        country_actual_emissions_ts=None,
        gdp_ts=None,
        gini_s=None,
        responsibility_weight=0.0,
        capability_weight=0.0,
        preserve_first_allocation_year_shares=preserve_first_allocation_year_shares,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )


def per_capita_adjusted(
    population_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    emission_category: str,
    country_actual_emissions_ts: TimeseriesDataFrame | None = None,
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
    preserve_first_allocation_year_shares: bool = False,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Per capita pathway allocation with responsibility and capability adjustments.

    Extends equal per capita by incorporating:

    - Responsibility adjustment: Countries with higher historical emissions
        receive smaller allocations
    - Capability adjustment: Countries with higher GDP (per capita or absolute)
        receive smaller allocations

    Mathematical Foundation
    -----------------------

    **Mode 1: Dynamic adjusted shares (preserve_first_allocation_year_shares=False, default)**

    Shares are computed by adjusting population at each year:

    $$
    A(g, t) = \frac{P_{\text{adj}}(g, t)}{\sum_{g'} P_{\text{adj}}(g', t)}
    $$

    Where the adjusted population is:

    $$
    P_{\text{adj}}(g, t) = P(g, t) \times R(g) \times C(g, t)
    $$

    Where:

    - $A(g, t)$: Allocation share for country $g$ at year $t$
    - $P_{\text{adj}}(g, t)$: Adjusted population of country $g$ at year $t$
    - $P(g, t)$: Actual population of country $g$ at year $t$
    - $R(g)$: Responsibility adjustment factor (constant over time, equals 1.0 if not used)
    - $C(g, t)$: Capability adjustment factor (time-varying, equals 1.0 if not used)

    **Mode 2: Preserved adjusted shares (preserve_first_allocation_year_shares=True)**

    Shares calculated at first_allocation_year are broadcast across all years.

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

    The capability metric is based on cumulative GDP per capita from
    first_allocation_year up to year :math:`t`.

    For per capita capability (:code:`capability_per_capita=True`, default):

    $$
    C(g, t) = \left(\frac{\sum_{t'=t_a}^{t} \text{GDP}(g, t')}{\sum_{t'=t_a}^{t} P(g, t')}\right)^{-w_c \times e_c}
    $$

    Where:

    - $C(g, t)$: Capability adjustment factor (inverse - higher cumulative GDP per capita = lower allocation)
    - $\text{GDP}(g, t')$: Gross domestic product of country $g$ in year $t'$
    - $w_c$: Normalized capability weight
    - $e_c$: Capability exponent

    For absolute capability (:code:`capability_per_capita=False`):

    $$
    C(g, t) = \left(\sum_{t'=t_a}^{t} \text{GDP}(g, t')\right)^{-w_c \times e_c}
    $$

    **Deviation Constraint**

    When :code:`max_deviation_sigma` is provided, shares are constrained to prevent
    extreme deviations from equal per capita. The constraint limits allocations to
    within :math:`\sigma` standard deviations of the equal per capita baseline.

    Parameters
    ----------
    population_ts
        Population time series for per capita calculations.
    first_allocation_year
        Starting year for the allocation.
        See docs/science/parameter-effects.md#allocation_year for how this affects
        country shares
    emission_category
        The emission category (e.g., 'co2-ffi', 'all-ghg').
    country_actual_emissions_ts
        Country emissions for responsibility calculation. Required if
        responsibility_weight > 0.
    gdp_ts
        GDP time series for capability adjustment. Required if capability_weight > 0.
    responsibility_weight
        Weight for responsibility adjustment (0-1). Higher historical emissions
        -> smaller allocation. Must satisfy:
        responsibility_weight + capability_weight <= 1.0
        See docs/science/parameter-effects.md#responsibility_weight for real
        allocation examples showing how this affects country shares
    capability_weight
        Weight for capability adjustment (0-1). Higher cumulative GDP per capita
        -> smaller allocation. Must satisfy:
        responsibility_weight + capability_weight <= 1.0
        See docs/science/parameter-effects.md#capability_weight for real
        allocation examples showing how this affects country shares
    historical_responsibility_year
        First year of responsibility window [historical_responsibility_year,
        first_allocation_year]. Default: 1990
    responsibility_per_capita
        If True, use per capita emissions for responsibility. Default: True
    responsibility_exponent
        Exponent for responsibility adjustment calculation. Default: 1.0
    responsibility_functional_form
        Functional form for responsibility adjustment ('asinh', 'power', 'linear').
        Default: 'asinh'
    capability_exponent
        Exponent for capability adjustment calculation. Default: 1.0
    capability_functional_form
        Functional form for capability adjustment ('asinh', 'power', 'linear').
        Default: 'power'
    max_deviation_sigma
        Maximum allowed deviation from equal per capita baseline. If None, no
        constraint is applied.
    preserve_first_allocation_year_shares
        If False (default), shares are calculated at each year. If True, shares
        calculated at first_allocation_year are preserved across all periods.
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

    Notes
    -----
    This approach operationalizes Common But Differentiated Responsibilities and
    Respective Capabilities (CBDR-RC) by combining:

    - **Historical Responsibility**: Adjusts allocations based on cumulative
      historical emissions
    - **Capability**: Adjusts based on economic resources and ability to pay

    Parameter choices involve normative judgments that should be made transparently:

    - Choice of start year for historical responsibility
    - Whether to use per capita or absolute metrics
    - Choice of GDP indicator (PPP vs. MER)
    - Transformation of indicators onto allocation scales

    See docs/science/allocations.md for theoretical grounding.

    Examples
    --------
    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data()
    >>> # Equal weights for responsibility and capability (50/50 split)
    >>> result = per_capita_adjusted(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     gdp_ts=data["gdp"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     responsibility_weight=0.5,
    ...     capability_weight=0.5,
    ... )
    Converting units...
    >>> # Check that shares sum to 1.0
    >>> shares = result.relative_shares_pathway_emissions
    >>> shares_2020 = shares["2020"]
    >>> bool(abs(shares_2020.sum() - 1.0) < 1e-10)
    True
    >>> # High emitters like USA should have smaller shares than equal per capita
    >>> equal_pc_result = equal_per_capita(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ... )
    Converting units...
    >>> equal_pc_shares = equal_pc_result.relative_shares_pathway_emissions["2020"]
    >>> # USA has lower share with adjustments due to high historical emissions + GDP
    >>> bool(shares_2020.loc["USA"].item() < equal_pc_shares.loc["USA"].item())
    True

    See Also
    --------
    equal_per_capita : Without adjustments
    per_capita_adjusted_gini : With Gini-adjusted GDP
    """
    return _per_capita_core(
        population_ts=population_ts,
        first_allocation_year=first_allocation_year,
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
        preserve_first_allocation_year_shares=preserve_first_allocation_year_shares,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )


def per_capita_adjusted_gini(
    population_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    emission_category: str,
    country_actual_emissions_ts: TimeseriesDataFrame | None = None,
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
    preserve_first_allocation_year_shares: bool = False,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Per capita pathway allocation with responsibility, capability, and Gini adjustments.

    The most comprehensive variant, incorporating:

    - Responsibility adjustment: Countries with higher historical emissions
        receive smaller allocations
    - Capability adjustment: Countries with higher Gini-adjusted GDP
        (per capita or absolute) receive smaller allocations
    - Gini adjustment: GDP is adjusted for income inequality within countries

    Mathematical Foundation
    -----------------------

    Similar to :func:`per_capita_adjusted`, but capability uses Gini-adjusted GDP
    to account for income inequality within countries.

    **Gini Adjustment Process**

    GDP is adjusted for each country at each year to reflect income inequality:

    $$
    \text{GDP}^{\text{adj}}(g, t) = \text{GDP}(g, t) \times (1 - \text{income-share-floor})
    $$

    Where:

    - $\text{GDP}^{\text{adj}}(g, t)$: Gini-adjusted GDP of country $g$ in year $t$
    - $\text{GDP}(g, t)$: Unadjusted GDP of country $g$ in year $t$
    - $\text{income-share-floor}$: Share of income below the income floor threshold

    The income share floor is calculated from:

    - $\text{Gini}(g)$: Gini coefficient for country $g$ (0 to 1, higher = more inequality)
    - $F$: Income floor parameter (income below this threshold is excluded from capability)
    - $\alpha$: Maximum Gini adjustment factor (prevents excessive reductions)

    **Capability Adjustment with Gini-Adjusted GDP**

    For per capita capability (:code:`capability_per_capita=True`, default):

    $$
    C(g, t) = \left(\frac{\sum_{t'=t_a}^{t} \text{GDP}^{\text{adj}}(g, t')}{\sum_{t'=t_a}^{t} P(g, t')}\right)^{-w_c \times e_c}
    $$

    Where:

    - $C(g, t)$: Capability adjustment factor using Gini-adjusted GDP
    - $\text{GDP}^{\text{adj}}(g, t')$: Gini-adjusted GDP in year $t'$
    - $P(g, t')$: Population in year $t'$
    - $t_a$: First allocation year
    - $w_c$: Normalized capability weight
    - $e_c$: Capability exponent

    For absolute capability (:code:`capability_per_capita=False`):

    $$
    C(g, t) = \left(\sum_{t'=t_a}^{t} \text{GDP}^{\text{adj}}(g, t')\right)^{-w_c \times e_c}
    $$

    **Gini Adjustment Effect**

    The Gini adjustment effectively reduces the GDP (and thus capability) of
    countries with high inequality, giving them larger emission allocations. This
    reflects that high-inequality countries have less capacity to pay because a
    larger share of their population has income below the capability threshold.

    For example, if country A and country B both have GDP per capita of $20,000,
    but country A has a Gini coefficient of 0.25 (low inequality) and country B
    has 0.50 (high inequality), country B's adjusted GDP will be lower, resulting
    in a larger emission allocation.

    Parameters
    ----------
    population_ts
        Population time series for per capita calculations.
    first_allocation_year
        Starting year for the allocation.
        See docs/science/parameter-effects.md#allocation_year for how this affects
        country shares
    emission_category
        The emission category (e.g., 'co2-ffi', 'all-ghg').
    country_actual_emissions_ts
        Country emissions for responsibility calculation. Required if
        responsibility_weight > 0.
    gdp_ts
        GDP time series for capability adjustment. Required if capability_weight > 0
        or gini_s provided.
    gini_s
        Gini coefficients for GDP inequality adjustment. When provided, GDP is
        adjusted to reflect income distribution within countries.
    responsibility_weight
        Weight for responsibility adjustment (0-1). Must satisfy:
        responsibility_weight + capability_weight <= 1.0
    capability_weight
        Weight for capability adjustment (0-1). Must satisfy:
        responsibility_weight + capability_weight <= 1.0
    historical_responsibility_year
        First year of responsibility window. Default: 1990
    responsibility_per_capita
        If True, use per capita emissions for responsibility. Default: True
    responsibility_exponent
        Exponent for responsibility adjustment calculation. Default: 1.0
    responsibility_functional_form
        Functional form for responsibility adjustment. Default: 'asinh'
    capability_exponent
        Exponent for capability adjustment calculation. Default: 1.0
    capability_functional_form
        Functional form for capability adjustment. Default: 'power'
    income_floor
        Income floor for Gini adjustment (in USD). Income below this threshold is
        excluded from capability calculations. Default: 7500.0
        See docs/science/parameter-effects.md#income_floor for real allocation
        examples showing how this affects country shares
    max_gini_adjustment
        Maximum reduction factor from Gini adjustment (0-1). Limits how much
        inequality can reduce effective GDP. Default: 0.8
    max_deviation_sigma
        Maximum allowed deviation from equal per capita baseline. If None, no
        constraint is applied.
    preserve_first_allocation_year_shares
        If False (default), shares are calculated at each year. If True, shares
        calculated at first_allocation_year are preserved across all periods.
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

    Notes
    -----
    This approach extends capability-based allocation by incorporating intra-national
    inequality. The Gini adjustment recognizes that GDP per capita may overstate
    the capability of high-inequality countries, where national income is
    concentrated among fewer people.

    **When to Use**

    - When capability assessment should reflect actual income distribution
    - When addressing concerns that high-inequality countries may have
      overstated capability based on GDP averages
    - For comprehensive allocation incorporating population, historical
      responsibility, and inequality-adjusted capability

    See docs/science/allocations.md for theoretical grounding.

    Examples
    --------
    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data()
    >>> # Equal weights with Gini adjustment
    >>> result = per_capita_adjusted_gini(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     gdp_ts=data["gdp"],
    ...     gini_s=data["gini"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     responsibility_weight=0.5,
    ...     capability_weight=0.5,
    ... )
    Converting units...
    >>> # Check that shares sum to 1.0
    >>> shares = result.relative_shares_pathway_emissions
    >>> shares_2020 = shares["2020"]
    >>> bool(abs(shares_2020.sum() - 1.0) < 1e-10)
    True
    >>> # Verify approach is correctly identified
    >>> result.approach
    'per-capita-adjusted-gini'
    >>> # Verify all countries have valid shares (between 0 and 1)
    >>> bool((shares_2020 >= 0).all() and (shares_2020 <= 1).all())
    True
    >>> # Compare to non-Gini version - shares will differ due to inequality adjustment
    >>> result_no_gini = per_capita_adjusted(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     gdp_ts=data["gdp"],
    ...     first_allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     responsibility_weight=0.5,
    ...     capability_weight=0.5,
    ... )
    Converting units...
    >>> shares_no_gini = result_no_gini.relative_shares_pathway_emissions["2020"]
    >>> # Gini adjustment changes the allocation pattern
    >>> bool(not shares_2020.equals(shares_no_gini))
    True

    See Also
    --------
    equal_per_capita : Without adjustments
    per_capita_adjusted : Without Gini adjustment
    """
    return _per_capita_core(
        population_ts=population_ts,
        first_allocation_year=first_allocation_year,
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
        preserve_first_allocation_year_shares=preserve_first_allocation_year_shares,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )
