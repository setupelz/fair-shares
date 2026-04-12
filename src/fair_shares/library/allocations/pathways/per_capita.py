"""
Per capita pathway allocations (equal, adjusted, and Gini-adjusted).

This module implements three related per capita pathway allocation approaches:

- **equal_per_capita**: Allocates emission pathways proportional to population.
  With a past first_allocation_year, accounts for historical responsibility
  directly (past emissions consume pathway allocation).
- **per_capita_adjusted**: Extends equal per capita with optional pre-allocation
  responsibility rescaling and/or capability adjustments.
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
    pre_allocation_responsibility_weight: float = 0.0,
    capability_weight: float = 0.0,
    # Pre-allocation responsibility parameters
    pre_allocation_responsibility_year: int = 1990,
    pre_allocation_responsibility_per_capita: bool = False,
    pre_allocation_responsibility_exponent: float = 1.0,
    pre_allocation_responsibility_functional_form: str = "asinh",
    # Capability parameters
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    # Gini parameters (only used if gini_s provided)
    income_floor: float = 0.0,
    max_gini_adjustment: float = 0.8,
    # Deviation constraint
    max_deviation_sigma: float | None = None,
    # Mode
    preserve_first_allocation_year_shares: bool = False,
    # Historical emissions discounting
    historical_discount_rate: float = 0.0,
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

    Parameters
    ----------
    population_ts
        Timeseries of population for each group of interest.
    first_allocation_year
        First year that should be used for calculating the allocation.
    emission_category
        Emission category to include in the output.
    country_actual_emissions_ts
        Historical emissions data (required if pre_allocation_responsibility_weight > 0).
    gdp_ts
        GDP data (required if capability_weight > 0).
    gini_s
        DataFrame containing Gini coefficient data for each group.
    pre_allocation_responsibility_weight
        Weight for pre-allocation responsibility adjustment (0.0 to 1.0).
    capability_weight
        Weight for economic capability adjustment (0.0 to 1.0). Applies from the
        first allocation year onwards (contrast with pre-allocation responsibility,
        which covers the window prior to it).
    pre_allocation_responsibility_year
        Start year for pre-allocation responsibility calculation. Default: 1990.
    pre_allocation_responsibility_per_capita
        If True, use per capita emissions; if False, use absolute emissions.
    pre_allocation_responsibility_exponent
        Exponent for the pre-allocation responsibility adjustment function.
    pre_allocation_responsibility_functional_form
        Functional form for pre-allocation responsibility: "asinh" or "power".
    capability_per_capita
        If True, use per capita GDP; if False, use absolute GDP.
    capability_exponent
        Exponent for the capability adjustment function.
    capability_functional_form
        Functional form for capability: "asinh" or "power".
    income_floor
        Income floor for Gini adjustment (in USD PPP per capita). Default: 0.0.
    max_gini_adjustment
        Maximum reduction factor from Gini adjustment (0-1). Default: 0.8.
    max_deviation_sigma
        Maximum allowed deviation from equal per capita in standard deviations.
        If None, no constraint is applied.
    preserve_first_allocation_year_shares
        If False (default), shares are calculated at each year. If True, shares
        calculated at first_allocation_year are preserved across all periods.
    historical_discount_rate
        Discount rate for historical emissions (0.0 to <1.0). When > 0, earlier
        emissions are weighted less via (1 - rate)^(reference_year - t).
        Default: 0.0 (no discounting).
    group_level
        Level in the index which specifies group information.
    unit_level
        Level in the index which specifies the unit of each timeseries.
    ur
        The unit registry to use for calculations.

    Returns
    -------
    PathwayAllocationResult
        Relative shares over time, summing to unity each year.

    Notes
    -----
    **GDP window (capability adjustment only):** When the allocation pathway
    extends past the last year of the input GDP time series, the cumulative
    GDP per capita values from the last observed year are forward-filled to
    cover the full pathway. This preserves the cross-country capability ratios
    of the last observed year, but those ratios then get weighted against the
    full post-observation population trajectory. Users who want different
    post-observation capability dynamics (SSP2 projections, custom growth
    assumptions, or a future-extended WDI release) should extend the input
    ``gdp_ts`` time series before calling the allocation function. This note
    applies whenever ``capability_weight > 0``; ``equal_per_capita`` does not
    use GDP and is unaffected.
    """
    first_allocation_year = int(first_allocation_year)
    pre_allocation_responsibility_year = int(pre_allocation_responsibility_year)

    # Validate weights using shared function
    validate_weight_constraints(pre_allocation_responsibility_weight, capability_weight)

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
        pre_allocation_responsibility_year=pre_allocation_responsibility_year
        if pre_allocation_responsibility_weight > 0
        else None,
    )

    # Validate data requirements
    if pre_allocation_responsibility_weight > 0 and country_actual_emissions_ts is None:
        raise AllocationError(
            format_error(
                "missing_required_data",
                adjustment_type="pre-allocation responsibility",
                weight_name="pre_allocation_responsibility_weight",
                weight_value=pre_allocation_responsibility_weight,
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
    use_responsibility = pre_allocation_responsibility_weight > 0
    use_gini_adjustment = use_capability and gini_s is not None
    has_adjustments = use_responsibility or use_capability

    # Normalize weights to their sum for reporting and calculation
    total_adjustment_weight = pre_allocation_responsibility_weight + capability_weight
    if total_adjustment_weight > 0:
        normalized_pre_allocation_responsibility_weight = (
            pre_allocation_responsibility_weight / total_adjustment_weight
        )
        normalized_capability_weight = capability_weight / total_adjustment_weight
    else:
        normalized_pre_allocation_responsibility_weight = 0.0
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

    # --- Mode 1: Dynamic year-by-year ---
    if not preserve_first_allocation_year_shares:
        base_population = population_numeric.copy()

        # Compute raw capability metric (DataFrame, year-by-year)
        capability_metric_dynamic = None
        if use_capability:
            gdp_filtered = filter_time_columns(gdp_ts, first_allocation_year)
            gdp_single_unit = set_single_unit(gdp_filtered, unit_level, ur=ur)
            gdp_single_unit = convert_unit_robust(
                gdp_single_unit, "million", unit_level=unit_level, ur=ur
            )
            gdp_numeric = gdp_single_unit.droplevel(unit_level)

            common_columns = population_numeric.columns.intersection(
                gdp_numeric.columns
            )
            gdp_common = gdp_numeric[common_columns]
            pop_common = population_numeric[common_columns]

            if gini_s is not None:
                gini_lookup = create_gini_lookup_dict(gini_s)
                gdp_common = apply_gini_adjustment(
                    gdp_common, pop_common, gini_lookup,
                    income_floor, max_gini_adjustment, group_level,
                )

            if capability_per_capita:
                gdp_cumsum = gdp_common.cumsum(axis=1)
                pop_cumsum = pop_common.cumsum(axis=1)
                capability_metric_dynamic = gdp_cumsum.divide(pop_cumsum)
            else:
                capability_metric_dynamic = gdp_common.cumsum(axis=1)

            # GDP window note: when the allocation pathway extends past the
            # last year of the input GDP time series (population_ts typically
            # runs to 2100; gdp_ts often ends at the last observed year, e.g.
            # 2023 for wdi-2025), this reindex forward-fills the cumulative
            # GDP-per-capita values from the last observed year onward. The
            # cross-country capability ratios of the last observed year are
            # then held constant for every subsequent year of the pathway. The
            # capability adjustment is applied year-by-year against the
            # population trajectory, so the frozen final-observed-year snapshot
            # gets weighted by the full post-observation population. Users who
            # want different post-observation capability dynamics (SSP2 GDP
            # projections, custom growth assumptions, or a future-extended WDI
            # release) should extend the input ``gdp_ts`` time series with
            # projected data before calling this function.
            capability_metric_dynamic = capability_metric_dynamic.reindex(
                population_numeric.columns, axis=1, method="ffill"
            )

        # Compute raw pre-allocation responsibility data (Series, constant across years)
        responsibility_data = None
        if use_responsibility:
            responsibility_data = calculate_responsibility_adjustment_data(
                country_actual_emissions_ts=country_actual_emissions_ts,
                population_ts=population_ts,
                pre_allocation_responsibility_year=pre_allocation_responsibility_year,
                allocation_year=first_allocation_year,
                pre_allocation_responsibility_per_capita=pre_allocation_responsibility_per_capita,
                group_level=group_level,
                unit_level=unit_level,
                ur=ur,
                historical_discount_rate=historical_discount_rate,
            )

            responsibility_data = responsibility_data.reindex(base_population.index)

        # Multiplicative combination
        if use_capability:
            capability_adjustment = calculate_relative_adjustment(
                capability_metric_dynamic,
                functional_form=capability_functional_form,
                exponent=normalized_capability_weight * capability_exponent,
                inverse=True,
            )
            base_population = base_population * capability_adjustment

        if use_responsibility:
            responsibility_adjustment = calculate_relative_adjustment(
                responsibility_data,
                functional_form=pre_allocation_responsibility_functional_form,
                exponent=normalized_pre_allocation_responsibility_weight * pre_allocation_responsibility_exponent,
                inverse=True,
            )
            base_population = base_population.mul(responsibility_adjustment, axis=0)

        total_adjusted_population = groupby_except_robust(
            base_population, group_level
        )
        res = base_population.divide(total_adjusted_population)

        # Apply deviation constraint if provided
        if max_deviation_sigma is not None:
            res = apply_deviation_constraint(
                res, population_numeric, max_deviation_sigma, group_level
            )

    # --- Mode 2: Preserved shares (calculate at first year, broadcast) ---
    else:
        population_at_ta = population_numeric[pop_year_to_label[first_allocation_year]]
        base_population_at_ta = population_at_ta.copy()

        capability_metric_at_ta = None
        if use_capability:
            gdp_filtered = filter_time_columns(gdp_ts, first_allocation_year)
            gdp_single_unit = set_single_unit(gdp_filtered, unit_level, ur=ur)
            gdp_single_unit = convert_unit_robust(
                gdp_single_unit, "million", unit_level=unit_level, ur=ur
            )
            gdp_numeric = gdp_single_unit.droplevel(unit_level)
            gdp_year_to_label = {int(c): c for c in gdp_numeric.columns}
            gdp_at_ta = gdp_numeric[gdp_year_to_label[first_allocation_year]]

            if gini_s is not None:
                gini_lookup = create_gini_lookup_dict(gini_s)
                gdp_at_ta = apply_gini_adjustment(
                    gdp_at_ta, population_at_ta, gini_lookup,
                    income_floor, max_gini_adjustment, group_level,
                )

            if capability_per_capita:
                capability_metric_at_ta = gdp_at_ta.divide(population_at_ta)
            else:
                capability_metric_at_ta = gdp_at_ta

        responsibility_data = None
        if use_responsibility:
            responsibility_data = calculate_responsibility_adjustment_data(
                country_actual_emissions_ts=country_actual_emissions_ts,
                population_ts=population_ts,
                pre_allocation_responsibility_year=pre_allocation_responsibility_year,
                allocation_year=first_allocation_year,
                pre_allocation_responsibility_per_capita=pre_allocation_responsibility_per_capita,
                group_level=group_level,
                unit_level=unit_level,
                ur=ur,
                historical_discount_rate=historical_discount_rate,
            )

            responsibility_data = responsibility_data.reindex(
                base_population_at_ta.index
            )

        # Multiplicative combination
        if use_capability:
            capability_adjustment = calculate_relative_adjustment(
                capability_metric_at_ta,
                functional_form=capability_functional_form,
                exponent=normalized_capability_weight * capability_exponent,
                inverse=True,
            )
            base_population_at_ta = base_population_at_ta * capability_adjustment

        if use_responsibility:
            responsibility_adjustment = calculate_relative_adjustment(
                responsibility_data,
                functional_form=pre_allocation_responsibility_functional_form,
                exponent=normalized_pre_allocation_responsibility_weight * pre_allocation_responsibility_exponent,
                inverse=True,
            )
            base_population_at_ta = base_population_at_ta * responsibility_adjustment

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
        "pre_allocation_responsibility_weight": normalized_pre_allocation_responsibility_weight,
        "capability_weight": normalized_capability_weight,
        "emission_category": emission_category,
        "group_level": group_level,
        "unit_level": unit_level,
    }

    # Add pre-allocation responsibility parameters if used
    if use_responsibility:
        parameters.update(
            {
                "pre_allocation_responsibility_year": pre_allocation_responsibility_year,
                "pre_allocation_responsibility_per_capita": pre_allocation_responsibility_per_capita,
                "pre_allocation_responsibility_exponent": pre_allocation_responsibility_exponent,
                "pre_allocation_responsibility_functional_form": pre_allocation_responsibility_functional_form,
            }
        )
        if historical_discount_rate > 0.0:
            parameters["historical_discount_rate"] = historical_discount_rate

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
    pre-allocation responsibility or economic capability.

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
        See the ``allocation_year`` section in docs/science/parameter-effects.md for how this affects
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
    **Theoretical grounding:**

    The equal per capita principle treats the atmosphere as a finite shared resource
    with equal claims per person. With a past first_allocation_year, it also
    accounts for historical responsibility: emissions since that year consume
    part of each country's pathway allocation, giving less to higher-emitting
    countries.

    See docs/science/allocations.md for theoretical grounding and limitations.

    See Also
    --------
    per_capita_adjusted : With pre-allocation responsibility/capability adjustments
    per_capita_adjusted_gini : With Gini-adjusted GDP
    """
    return _per_capita_core(
        population_ts=population_ts,
        first_allocation_year=first_allocation_year,
        emission_category=emission_category,
        country_actual_emissions_ts=None,
        gdp_ts=None,
        gini_s=None,
        pre_allocation_responsibility_weight=0.0,
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
    pre_allocation_responsibility_weight: float = 0.0,
    capability_weight: float = 0.0,
    pre_allocation_responsibility_year: int = 1990,
    pre_allocation_responsibility_per_capita: bool = False,
    pre_allocation_responsibility_exponent: float = 1.0,
    pre_allocation_responsibility_functional_form: str = "asinh",
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    max_deviation_sigma: float | None = None,
    preserve_first_allocation_year_shares: bool = False,
    historical_discount_rate: float = 0.0,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Per capita pathway allocation with pre-allocation responsibility and capability adjustments.

    Extends equal per capita by incorporating:

    - Pre-allocation responsibility adjustment: Countries with higher historical
        emissions receive smaller allocations
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
    - $R(g)$: Pre-allocation responsibility adjustment factor (constant over time, equals 1.0 if not used)
    - $C(g, t)$: Capability adjustment factor (time-varying, equals 1.0 if not used)

    **Mode 2: Preserved adjusted shares (preserve_first_allocation_year_shares=True)**

    Shares calculated at first_allocation_year are broadcast across all years.

    **Pre-Allocation Responsibility Adjustment**

    The pre-allocation responsibility metric is based on cumulative historical
    emissions from pre_allocation_responsibility_year to first_allocation_year.

    For per capita pre-allocation responsibility (:code:`pre_allocation_responsibility_per_capita=True`):

    $$
    R(g) = \left(\frac{\sum_{t=t_h}^{t_a} E(g, t)}{\sum_{t=t_h}^{t_a} P(g, t)}\right)^{-w_r \times e_r}
    $$

    Where:

    - $R(g)$: Pre-allocation responsibility adjustment factor (inverse - higher emissions = lower allocation)
    - $E(g, t)$: Emissions of country $g$ in year $t$
    - $t_h$: Pre-allocation responsibility start year
    - $t_a$: First allocation year
    - $w_r$: Normalized pre-allocation responsibility weight
    - $e_r$: Pre-allocation responsibility exponent

    For absolute pre-allocation responsibility (:code:`pre_allocation_responsibility_per_capita=False`, default):

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
        Starting year for the allocation pathway. Shares are computed
        from this year onwards. See
        ``docs/science/parameter-effects.md`` §allocation_year for how
        the choice of year affects country shares.
    emission_category
        Emission category (e.g., ``'co2-ffi'``, ``'all-ghg'``).
    country_actual_emissions_ts
        **Pre-allocation responsibility.** Country emissions used to
        compute cumulative emissions in the window
        ``[pre_allocation_responsibility_year, first_allocation_year)``.
        Required when ``pre_allocation_responsibility_weight > 0``.
    gdp_ts
        **Capability.** GDP time series used from ``first_allocation_year``
        onwards. Required when ``capability_weight > 0``.
    pre_allocation_responsibility_weight
        **Pre-allocation responsibility.** Relative weight (0–1). Only the
        ratio to ``capability_weight`` matters — ``(0.5, 0.5)`` is
        identical to ``(1.0, 1.0)``. When 0, pre-allocation
        responsibility is disabled.
        See ``docs/science/parameter-effects.md`` §weights.
    capability_weight
        **Capability.** Relative weight (0–1). Applies from
        ``first_allocation_year`` onwards (contrast with pre-allocation
        responsibility, which covers the window before it). When 0,
        capability is disabled.
        See ``docs/science/parameter-effects.md`` §weights.
    pre_allocation_responsibility_year
        **Pre-allocation responsibility.** Start year of the historical
        window ``[pre_allocation_responsibility_year,
        first_allocation_year)``. Default: 1990.
    pre_allocation_responsibility_per_capita
        **Pre-allocation responsibility.** If ``True``, cumulative
        emissions are divided by cumulative population before computing
        the adjustment factor. If ``False`` (default), absolute
        cumulative emissions are used.
    pre_allocation_responsibility_exponent
        **Pre-allocation responsibility.** Exponent applied to the
        emissions metric. Higher values amplify differences between
        countries. Default: 1.0.
    pre_allocation_responsibility_functional_form
        **Pre-allocation responsibility.** Transformation applied to the
        raw metric: ``'asinh'`` (default), ``'power'``, or ``'linear'``.
        ``'asinh'`` compresses extreme values.
    capability_per_capita
        **Capability.** If ``True`` (default), GDP is divided by
        population before computing the capability factor. If ``False``,
        absolute GDP is used.
    capability_exponent
        **Capability.** Exponent applied to the GDP metric. Higher values
        amplify differences between countries. Default: 1.0.
    capability_functional_form
        **Capability.** Transformation applied to the raw GDP metric:
        ``'asinh'`` (default), ``'power'``, or ``'linear'``.
    max_deviation_sigma
        **Constraint.** Maximum allowed deviation from equal per capita
        baseline, in population-weighted standard deviations. Prevents
        extreme adjustments. ``None`` (default) means no constraint.
    preserve_first_allocation_year_shares
        **Mode.** If ``False`` (default), shares are recalculated at each
        year. If ``True``, shares from ``first_allocation_year`` are held
        constant for all subsequent years.
    historical_discount_rate
        **Pre-allocation responsibility.** Discount rate for historical
        emissions (0.0 to <1.0). Weights earlier emissions less via
        ``(1 - rate)^(reference_year - t)``. Default: 0.0
        (no discounting). Only affects the pre-allocation responsibility
        calculation.
    group_level
        Index level name for grouping. Default: ``'iso3c'``.
    unit_level
        Index level name for units. Default: ``'unit'``.
    ur
        Pint unit registry for unit conversions.

    Returns
    -------
    PathwayAllocationResult
        Relative shares over time, summing to unity each year.

    Notes
    -----
    **Theoretical grounding:**

    This approach provides explicit mechanisms for differentiating allocations:

    - **Pre-allocation Responsibility Rescaling**: Multiplicative rescaling of
      shares based on cumulative per-capita emissions in a historical window —
      an alternative to the responsibility accounting that comes from setting
      first_allocation_year in the past (where past emissions consume allocation)
    - **Capability (Ability to Pay)**: Adjusts based on economic resources
      from the first allocation year onwards — countries with greater capacity
      bear greater obligations

    CBDR-RC can be operationalized either through a past first_allocation_year
    (responsibility via consumed budget) combined with capability adjustments,
    or through pre-allocation responsibility rescaling, or both.

    Parameter choices involve normative judgments that should be made transparently:

    - Choice of start year for pre-allocation responsibility
    - Whether to use per capita or absolute metrics
    - Choice of GDP indicator (PPP vs. MER)
    - Transformation of indicators onto allocation scales

    See docs/science/allocations.md for theoretical grounding.

    **GDP window:** When the allocation pathway extends past the last year of
    the input ``gdp_ts``, the cumulative GDP per capita values from the last
    observed year are forward-filled to cover the full pathway. This preserves
    the cross-country capability ratios of the last observed year, but those
    ratios then get weighted against the full post-observation population
    trajectory. Users who want different post-observation capability dynamics
    (SSP2 projections, custom growth assumptions, or a future-extended WDI
    release) should extend the input ``gdp_ts`` time series before calling
    this function. The forward-fill is the minimum-disruption default when
    no projected GDP data is supplied.

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
        pre_allocation_responsibility_weight=pre_allocation_responsibility_weight,
        capability_weight=capability_weight,
        pre_allocation_responsibility_year=pre_allocation_responsibility_year,
        pre_allocation_responsibility_per_capita=pre_allocation_responsibility_per_capita,
        pre_allocation_responsibility_exponent=pre_allocation_responsibility_exponent,
        pre_allocation_responsibility_functional_form=pre_allocation_responsibility_functional_form,
        capability_per_capita=capability_per_capita,
        capability_exponent=capability_exponent,
        capability_functional_form=capability_functional_form,
        max_deviation_sigma=max_deviation_sigma,
        preserve_first_allocation_year_shares=preserve_first_allocation_year_shares,
        historical_discount_rate=historical_discount_rate,
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
    pre_allocation_responsibility_weight: float = 0.0,
    capability_weight: float = 0.0,
    pre_allocation_responsibility_year: int = 1990,
    pre_allocation_responsibility_per_capita: bool = False,
    pre_allocation_responsibility_exponent: float = 1.0,
    pre_allocation_responsibility_functional_form: str = "asinh",
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    income_floor: float = 7500.0,
    max_gini_adjustment: float = 0.8,
    max_deviation_sigma: float | None = None,
    preserve_first_allocation_year_shares: bool = False,
    historical_discount_rate: float = 0.0,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Per capita pathway allocation with pre-allocation responsibility, capability, and Gini adjustments.

    The most comprehensive variant, incorporating:

    - Pre-allocation responsibility adjustment: Countries with higher historical
        emissions receive smaller allocations
    - Capability adjustment: Countries with higher Gini-adjusted GDP
        (per capita or absolute) receive smaller allocations
    - Gini adjustment: GDP is adjusted for income inequality within countries

    Mathematical Foundation
    -----------------------

    Similar to :func:`per_capita_adjusted`, but capability uses Gini-adjusted GDP
    to account for income inequality within countries.

    **Gini Adjustment Process**

    GDP is adjusted using an interpretation of the Greenhouse Development
    Rights (GDR) framework's capability metric (note: GDR was designed for
    burden-sharing; fair-shares adapts its capability calculation for
    entitlement allocation). Only income above a development threshold counts
    as capability. When combined with the income floor, higher inequality
    means more national income sits above the threshold — increasing measured
    capability. See
    :func:`~fair_shares.library.utils.math.allocation.calculate_gini_adjusted_gdp`
    for the full mathematical derivation.

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

    When combined with the income floor, higher inequality means more national
    income sits above the development threshold, creating larger per-person
    excesses. Countries with high inequality and high GDP thus receive smaller
    emission allocations (higher measured capability = more ability to pay).
    See :func:`~fair_shares.library.utils.math.allocation.calculate_gini_adjusted_gdp`
    for worked examples.

    Parameters
    ----------
    population_ts
        Population time series for per capita calculations.
    first_allocation_year
        Year from which to begin the allocation pathway. See
        ``docs/science/parameter-effects.md`` §allocation_year.
    emission_category
        Emission category (e.g., ``'co2-ffi'``, ``'all-ghg'``).
    country_actual_emissions_ts
        **Pre-allocation responsibility.** Country emissions used to
        compute cumulative emissions in the window
        ``[pre_allocation_responsibility_year, first_allocation_year)``.
        Required when ``pre_allocation_responsibility_weight > 0``.
    gdp_ts
        **Capability.** GDP time series used from ``first_allocation_year``
        onwards. Required when ``capability_weight > 0`` or ``gini_s``
        is provided.
    gini_s
        **Gini.** Gini coefficients for within-country income inequality.
        Used to adjust GDP before computing the capability factor.
    pre_allocation_responsibility_weight
        **Pre-allocation responsibility.** Relative weight (0–1). Only the
        ratio to ``capability_weight`` matters. When 0, pre-allocation
        responsibility is disabled.
    capability_weight
        **Capability.** Relative weight (0–1). Applies from
        ``first_allocation_year`` onwards. When 0, capability is disabled.
    pre_allocation_responsibility_year
        **Pre-allocation responsibility.** Start year of the historical
        window ``[pre_allocation_responsibility_year,
        first_allocation_year)``. Default: 1990.
    pre_allocation_responsibility_per_capita
        **Pre-allocation responsibility.** If ``True``, uses per-capita
        cumulative emissions. If ``False`` (default), uses absolute
        cumulative emissions.
    pre_allocation_responsibility_exponent
        **Pre-allocation responsibility.** Exponent applied to the
        emissions metric. Default: 1.0.
    pre_allocation_responsibility_functional_form
        **Pre-allocation responsibility.** Transformation: ``'asinh'``
        (default), ``'power'``, or ``'linear'``.
    capability_per_capita
        **Capability.** If ``True`` (default), Gini-adjusted GDP is
        divided by population. If ``False``, absolute Gini-adjusted GDP
        is used.
    capability_exponent
        **Capability.** Exponent applied to the Gini-adjusted GDP metric.
        Default: 1.0.
    capability_functional_form
        **Capability.** Transformation: ``'asinh'`` (default), ``'power'``,
        or ``'linear'``.
    income_floor
        **Gini.** Development threshold in USD PPP per capita. Income
        below this is excluded from capability calculations, adapted from
        GDR. Default: 7500.0. See
        ``docs/science/parameter-effects.md`` §income_floor.
    max_gini_adjustment
        **Gini.** Maximum reduction factor from threshold deduction (0–1).
        Limits how much the deduction can reduce effective GDP.
        Default: 0.8.
    max_deviation_sigma
        **Constraint.** Maximum allowed deviation from equal per capita
        baseline, in population-weighted standard deviations. ``None``
        (default) means no constraint.
    preserve_first_allocation_year_shares
        **Mode.** If ``False`` (default), shares are recalculated at each
        year. If ``True``, shares from ``first_allocation_year`` are held
        constant.
    historical_discount_rate
        **Pre-allocation responsibility.** Discount rate for historical
        emissions (0.0 to <1.0), via ``(1 - rate)^(reference_year - t)``
        Default: 0.0. Only affects the pre-allocation
        responsibility calculation.
    group_level
        Index level name for grouping. Default: ``'iso3c'``.
    unit_level
        Index level name for units. Default: ``'unit'``.
    ur
        Pint unit registry for unit conversions.

    Returns
    -------
    PathwayAllocationResult
        Relative shares over time, summing to unity each year.

    Notes
    -----
    **Theoretical grounding:**

    This approach extends capability-based allocation by incorporating intra-national
    inequality via the GDR development threshold (adapted for entitlement
    allocation from GDR's burden-sharing context). Only income above the
    development threshold counts toward capability. When combined with the income
    floor, higher inequality means more national income sits above the threshold.
    See :func:`~fair_shares.library.utils.math.allocation.calculate_gini_adjusted_gdp`
    for the mathematical formulation.

    See docs/science/allocations.md for theoretical grounding.

    **GDP window:** When the allocation pathway extends past the last year of
    the input ``gdp_ts``, the cumulative (Gini-adjusted) GDP per capita values
    from the last observed year are forward-filled to cover the full pathway.
    This preserves the cross-country capability ratios of the last observed
    year, but those ratios then get weighted against the full post-observation
    population trajectory. Users who want different post-observation
    capability dynamics (SSP2 projections, custom growth assumptions, or a
    future-extended WDI release) should extend the input ``gdp_ts`` time
    series before calling this function. Gini coefficients are looked up
    per-country and are not part of this forward-fill — only the GDP series
    is extended in time.

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
        pre_allocation_responsibility_weight=pre_allocation_responsibility_weight,
        capability_weight=capability_weight,
        pre_allocation_responsibility_year=pre_allocation_responsibility_year,
        pre_allocation_responsibility_per_capita=pre_allocation_responsibility_per_capita,
        pre_allocation_responsibility_exponent=pre_allocation_responsibility_exponent,
        pre_allocation_responsibility_functional_form=pre_allocation_responsibility_functional_form,
        capability_per_capita=capability_per_capita,
        capability_exponent=capability_exponent,
        capability_functional_form=capability_functional_form,
        income_floor=income_floor,
        max_gini_adjustment=max_gini_adjustment,
        max_deviation_sigma=max_deviation_sigma,
        preserve_first_allocation_year_shares=preserve_first_allocation_year_shares,
        historical_discount_rate=historical_discount_rate,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )
