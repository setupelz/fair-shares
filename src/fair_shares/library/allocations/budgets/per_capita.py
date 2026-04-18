"""
Per capita budget allocations (equal, adjusted, and Gini-adjusted).

This module implements three related per capita budget allocation approaches
grounded in fair shares literature:

- **equal_per_capita_budget**: Allocates emission budgets proportional to population.
  With a past allocation_year, accounts for historical responsibility directly
  (past emissions consume budget).
- **per_capita_adjusted_budget**: Extends equal per capita with optional pre-allocation
  responsibility rescaling and/or capability adjustments.
- **per_capita_adjusted_gini_budget**: Incorporates intra-national inequality through Gini adjustments.

See docs/science/allocations.md for theoretical grounding and academic context.
"""

from __future__ import annotations

import warnings
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
    responsibility_emissions_ts: TimeseriesDataFrame | None = None,
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
    capability_reference_year: int | None = None,
    # Gini parameters (only used if gini_s provided)
    income_floor: float = 0.0,
    max_gini_adjustment: float = 0.8,
    # Deviation constraint
    max_deviation_sigma: float | None = None,
    # Mode
    preserve_allocation_year_shares: bool = False,
    # Historical emissions discounting
    historical_discount_rate: float = 0.0,
    # Cumulative window upper bound
    cumulative_end_year: int | None = None,
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

    Parameters
    ----------
    population_ts
        Timeseries of population for each group of interest.
    allocation_year
        Year from which to start calculating allocations and budgets.
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
        allocation year onwards (contrast with pre-allocation responsibility, which
        covers the window prior to it).
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
    capability_reference_year
        Year to use as the capability snapshot. When ``None`` (default),
        capability is computed year-by-year from ``gdp_ts`` and applied to
        each population year in the allocation window. When set to an integer,
        the capability metric is taken from that single year and broadcast as
        a constant across all years in the window — equivalent to
        ``C(g, t) ≡ C(g, t_ref)`` for all ``t``. The reference year may be
        before OR after the allocation year. When
        ``capability_reference_year < allocation_year``, the snapshot is
        sourced from the full unfiltered ``gdp_ts`` and ``population_ts``
        inputs; Gini adjustment is NOT applied in that case.
        Ignored if ``capability_weight == 0.0``. Emits a ``UserWarning``
        if ``capability_reference_year`` exceeds the last observed GDP year.
    income_floor
        Income floor for Gini adjustment (in USD PPP per capita). Default: 0.0.
    max_gini_adjustment
        Maximum reduction factor from Gini adjustment (0-1). Default: 0.8.
    max_deviation_sigma
        Maximum allowed deviation from equal per capita in standard deviations.
        If None, no constraint is applied.
    preserve_allocation_year_shares
        If False (default), shares use cumulative population from allocation_year
        onwards. If True, shares calculated at allocation_year are preserved.
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
    BudgetAllocationResult
        Container with relative shares for cumulative emissions budget allocation.

    Notes
    -----
    **GDP window (capability adjustment only):** When the allocation cumulative
    window extends past the last year of the input GDP time series, the GDP per
    capita values from the last observed year are forward-filled to cover the
    full window. This preserves the cross-country capability ratios of the last
    observed year, but those ratios then get weighted against the full
    post-observation population trajectory. Users who want different
    post-observation capability dynamics (SSP2 projections, custom growth
    assumptions, or a future-extended WDI release) should extend the input
    ``gdp_ts`` time series before calling the allocation function. This note
    applies whenever ``capability_weight > 0``; ``equal_per_capita_budget``
    does not use GDP and is unaffected.
    """
    allocation_year = int(allocation_year)
    pre_allocation_responsibility_year = int(pre_allocation_responsibility_year)

    # Validate weights using shared function
    validate_weight_constraints(pre_allocation_responsibility_weight, capability_weight)

    # Validate inputs using Pydantic model
    AllocationInputs(
        population_ts=population_ts,
        first_allocation_year=allocation_year,
        last_allocation_year=allocation_year,
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
        approach = "per-capita-adjusted-gini-budget"
    elif has_adjustments:
        approach = "per-capita-adjusted-budget"
    else:
        approach = "equal-per-capita-budget"

    # Filter population to allocation_year onwards, with optional upper bound
    population_filtered = filter_time_columns(population_ts, allocation_year)
    if cumulative_end_year is not None:
        numeric_cols = pd.to_numeric(population_filtered.columns, errors="coerce")
        population_filtered = population_filtered.loc[:, numeric_cols <= cumulative_end_year]
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

    # Compute raw capability metric if needed (used by both modes)
    capability_metric = None
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

        if capability_reference_year is None:
            # Year-by-year mode (default, backward compatible).
            #
            # GDP window note: when the allocation cumulative window extends past
            # the last year of the input GDP time series (population_ts typically
            # runs to 2100; gdp_ts often ends at the last observed year, e.g. 2023
            # for wdi-2025), this reindex forward-fills the GDP per capita values
            # from the last observed year onward. The cross-country capability
            # ratios of the last observed year are then held constant for every
            # subsequent year of the cumulative window. The capability adjustment
            # is still applied year-by-year against the population trajectory, so
            # the frozen final-observed-year snapshot gets weighted by the full
            # post-observation population. Users who want different post-observation
            # capability dynamics (SSP2 GDP projections, custom growth assumptions,
            # or a future-extended WDI release) should extend the input ``gdp_ts``
            # time series with projected data before calling this function.
            capability_metric = capability_metric_common.reindex(
                population_numeric.columns, axis=1, method="ffill"
            )
        else:
            # Snapshot mode: take one column and broadcast it across the window.
            # When capability_reference_year is set, only that one GDP year is
            # used — forward-fill is irrelevant and the snapshot value is
            # broadcast across the window.
            ref_year = int(capability_reference_year)
            gdp_filtered_years = [int(c) for c in capability_metric_common.columns]

            if ref_year in gdp_filtered_years:
                # Normal case: ref_year is within the allocation window, already
                # present in capability_metric_common (which was computed from the
                # allocation_year-filtered inputs).
                ref_label = [c for c in capability_metric_common.columns
                             if int(c) == ref_year][0]
                snapshot = capability_metric_common[ref_label]
            elif ref_year > max(gdp_filtered_years):
                # User-requested ffill past end-of-series: take the last column.
                warnings.warn(
                    f"capability_reference_year={ref_year} is beyond the last "
                    f"observed GDP year ({max(gdp_filtered_years)}). Using "
                    f"{max(gdp_filtered_years)} as the snapshot year (forward-fill "
                    "consistent with year-by-year default mode).",
                    UserWarning,
                    stacklevel=2,
                )
                ref_label = capability_metric_common.columns[-1]
                snapshot = capability_metric_common[ref_label]
            else:
                # ref_year < allocation_year: the reference year was stripped by
                # filter_time_columns, so we must source the snapshot from the
                # UNFILTERED gdp_ts and population_ts inputs.
                # Apply the same unit processing used in the main capability path.
                gdp_full_single_unit = set_single_unit(gdp_ts, unit_level, ur=ur)
                gdp_full_single_unit = convert_unit_robust(
                    gdp_full_single_unit, "million", unit_level=unit_level, ur=ur
                )
                gdp_full_numeric = gdp_full_single_unit.droplevel(unit_level)

                pop_full_single_unit = set_single_unit(population_ts, unit_level, ur=ur)
                pop_full_single_unit = convert_unit_robust(
                    pop_full_single_unit, "million", unit_level=unit_level, ur=ur
                )
                pop_full_numeric = pop_full_single_unit.droplevel(unit_level)

                gdp_all_years = [int(c) for c in gdp_full_numeric.columns]
                pop_all_years = [int(c) for c in pop_full_numeric.columns]
                if ref_year not in gdp_all_years:
                    raise AllocationError(
                        f"capability_reference_year={ref_year} is outside the GDP "
                        f"data range [{min(gdp_all_years)}, {max(gdp_all_years)}]. "
                        "Extend gdp_ts or choose a year inside the observed range."
                    )
                if ref_year not in pop_all_years:
                    raise AllocationError(
                        f"capability_reference_year={ref_year} is outside the "
                        f"population data range [{min(pop_all_years)}, "
                        f"{max(pop_all_years)}]."
                    )
                gdp_ref_label = [c for c in gdp_full_numeric.columns
                                 if int(c) == ref_year][0]
                pop_ref_label = [c for c in pop_full_numeric.columns
                                 if int(c) == ref_year][0]

                if capability_per_capita:
                    snapshot = gdp_full_numeric[gdp_ref_label].divide(
                        pop_full_numeric[pop_ref_label]
                    )
                else:
                    snapshot = gdp_full_numeric[gdp_ref_label]

                # Note: Gini adjustment is NOT applied in the pre-allocation-window
                # branch. When ref_year < allocation_year, the snapshot is sourced
                # from the raw (non-Gini-adjusted) inputs. If Gini correction at
                # the reference year is needed, choose a ref_year within the
                # allocation window (ref_year >= allocation_year).

            # Broadcast the scalar-per-region series across every column in the
            # population window. The downstream adjustment and cumulative sum then
            # apply pf(snapshot) * P(g,t) per cell and sum over t, which is
            # algebraically identical to pf(snapshot) * sum_t P(g,t).
            capability_metric = pd.DataFrame(
                {c: snapshot for c in population_numeric.columns},
                index=population_numeric.index,
            )

    # Compute raw pre-allocation responsibility data if needed (used by both modes)
    responsibility_input = (
        responsibility_emissions_ts
        if responsibility_emissions_ts is not None
        else country_actual_emissions_ts
    )
    responsibility_data = None
    if use_responsibility:
        responsibility_data = calculate_responsibility_adjustment_data(
            country_actual_emissions_ts=responsibility_input,
            population_ts=population_ts,
            pre_allocation_responsibility_year=pre_allocation_responsibility_year,
            allocation_year=allocation_year,
            pre_allocation_responsibility_per_capita=pre_allocation_responsibility_per_capita,
            group_level=group_level,
            unit_level=unit_level,
            ur=ur,
            historical_discount_rate=historical_discount_rate,
        )

        # Reindex to match population index
        responsibility_data = responsibility_data.reindex(base_population.index)

    # Apply capability adjustment multiplicatively
    if use_capability:
        capability_adjustment = calculate_relative_adjustment(
            capability_metric,
            functional_form=capability_functional_form,
            exponent=normalized_capability_weight * capability_exponent,
            inverse=True,
        )
        base_population = base_population * capability_adjustment

    # Apply pre-allocation responsibility adjustment multiplicatively
    if use_responsibility:
        responsibility_adjustment = calculate_relative_adjustment(
            responsibility_data,
            functional_form=pre_allocation_responsibility_functional_form,
            exponent=normalized_pre_allocation_responsibility_weight * pre_allocation_responsibility_exponent,
            inverse=True,
        )
        base_population = base_population.mul(responsibility_adjustment, axis=0)

    # Calculate shares from adjusted population
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

    # Build parameters dict (always include normalized weights for reporting)
    parameters = {
        "allocation_year": allocation_year,
        "preserve_allocation_year_shares": preserve_allocation_year_shares,
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
    if use_capability:
        parameters.update(
            {
                "capability_exponent": capability_exponent,
                "capability_functional_form": capability_functional_form,
                "capability_reference_year": capability_reference_year,
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
    cumulative_end_year: int | None = None,
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
        Population time series for each group of interest.
    allocation_year
        Year from which to calculate budget shares. See
        ``docs/science/parameter-effects.md`` §allocation_year for how
        the choice of year affects country shares.
    emission_category
        Emission category (e.g., ``'co2-ffi'``, ``'all-ghg'``).
    preserve_allocation_year_shares
        **Mode.** If ``False`` (default), shares are calculated using
        cumulative population from ``allocation_year`` onwards. If
        ``True``, shares from ``allocation_year`` only are used.
    cumulative_end_year
        Upper bound of the cumulative population window. ``None``
        (default) uses the last year in the population data.
    group_level
        Index level name for grouping. Default: ``'iso3c'``.
    unit_level
        Index level name for units. Default: ``'unit'``.
    ur
        Pint unit registry for unit conversions.

    Returns
    -------
    BudgetAllocationResult
        Relative shares for cumulative emissions budget allocation,
        summing to 1 across groups.

    Notes
    -----
    See ``docs/science/allocations.md`` for mathematical formulation.
    See ``docs/science/principle-to-code.md`` for implementation examples.

    See Also
    --------
    per_capita_adjusted_budget : With pre-allocation responsibility and/or capability adjustments
    per_capita_adjusted_gini_budget : With Gini-adjusted GDP capability weighting
    """
    return _per_capita_budget_core(
        population_ts=population_ts,
        allocation_year=allocation_year,
        emission_category=emission_category,
        pre_allocation_responsibility_weight=0.0,
        capability_weight=0.0,
        preserve_allocation_year_shares=preserve_allocation_year_shares,
        cumulative_end_year=cumulative_end_year,
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
    responsibility_emissions_ts: TimeseriesDataFrame | None = None,
    gdp_ts: TimeseriesDataFrame | None = None,
    # Adjustment weights
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
    capability_reference_year: int | None = None,
    # Deviation constraint
    max_deviation_sigma: float | None = None,
    # Mode
    preserve_allocation_year_shares: bool = False,
    # Historical emissions discounting
    historical_discount_rate: float = 0.0,
    # Cumulative window upper bound
    cumulative_end_year: int | None = None,
    # Common parameters
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:
    r"""
    Per capita budget allocation with pre-allocation responsibility and capability adjustments.

    This function generates cumulative shares for the allocation year based
    on adjusted per capita principles, incorporating pre-allocation responsibility
    and economic capability adjustments (but without Gini correction).

    Mathematical Foundation
    -----------------------

    The per capita adjusted budget allocation adjusts for pre-allocation responsibility
    and economic capability using the following approach.

    **Core Allocation Formula**

    For budget allocation with dynamic shares (default mode):

    $$
    A(g) = \frac{\sum_{t \geq t_a} R(g) \times C(g, t) \times P(g, t)}{\sum_g \sum_{t \geq t_a} R(g) \times C(g, t) \times P(g, t)}
    $$

    Where:

    - $A(g)$: Budget share allocated to country $g$
    - $R(g)$: Pre-allocation responsibility adjustment factor for country $g$ (constant over time, equals 1.0 if not used)
    - $C(g, t)$: Capability adjustment factor for country $g$ in year $t$ (equals 1.0 if not used)
    - $P(g, t)$: Population of country $g$ in year $t$
    - $t_a$: Allocation year

    **Pre-Allocation Responsibility Adjustment**

    Historical emissions reduce future allocation rights.

    For per capita pre-allocation responsibility (:code:`pre_allocation_responsibility_per_capita=True`):

    $$
    R(g) = \left(\frac{\sum_{t=t_h}^{t_a-1} E(g, t)}{\sum_{t=t_h}^{t_a-1} P(g, t)}\right)^{-w_r \times e_r}
    $$

    Where:

    - $R(g)$: Pre-allocation responsibility adjustment factor (inverse - higher emissions = lower allocation)
    - $E(g, t)$: Emissions of country $g$ in year $t$
    - $t_h$: Pre-allocation responsibility start year
    - $t_a$: Allocation year
    - $w_r$: Normalized pre-allocation responsibility weight
    - $e_r$: Pre-allocation responsibility exponent

    For absolute pre-allocation responsibility (:code:`pre_allocation_responsibility_per_capita=False`, default):

    $$
    R(g) = \left(\sum_{t=t_h}^{t_a-1} E(g, t)\right)^{-w_r \times e_r}
    $$

    **Capability Adjustment**

    Economic capacity reduces allocation rights for wealthier countries.

    By default (``capability_reference_year=None``), the capability term
    $C(g, t)$ is computed year-by-year from ``gdp_ts``, integrating lifetime
    capability over the full allocation window. When ``capability_reference_year``
    is set to an integer $t_{\text{ref}}$, the capability is frozen at that
    year: $C(g, t) \equiv C(g, t_{\text{ref}})$ for all $t$ in the cumulative
    window. When ``capability_reference_year`` is before ``allocation_year``,
    the snapshot is sourced from the full unfiltered ``gdp_ts``. When
    ``capability_reference_year`` exceeds the last observed GDP year, the last
    observed column is used as the snapshot (forward-fill fallback, consistent
    with year-by-year default mode), and a ``UserWarning`` is emitted.

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
        Population time series for each group of interest.
    allocation_year
        Year from which to calculate budget shares. See
        ``docs/science/parameter-effects.md`` §allocation_year for how
        the choice of year affects country shares.
    emission_category
        Emission category (e.g., ``'co2-ffi'``, ``'all-ghg'``).
    country_actual_emissions_ts
        **Pre-allocation responsibility.** Historical emissions data.
        Required when ``pre_allocation_responsibility_weight > 0``.
    gdp_ts
        **Capability.** GDP data used from ``allocation_year`` onwards.
        Required when ``capability_weight > 0``.
    pre_allocation_responsibility_weight
        **Pre-allocation responsibility.** Relative weight (0–1). Only the
        ratio to ``capability_weight`` matters. When 0, pre-allocation
        responsibility is disabled.
        See ``docs/science/parameter-effects.md`` §weights.
    capability_weight
        **Capability.** Relative weight (0–1). Applies from
        ``allocation_year`` onwards (contrast with pre-allocation
        responsibility, which covers the window before it). When 0,
        capability is disabled.
        See ``docs/science/parameter-effects.md`` §weights.
    pre_allocation_responsibility_year
        **Pre-allocation responsibility.** Start year of the historical
        window ``[pre_allocation_responsibility_year,
        allocation_year)``. Default: 1990.
    pre_allocation_responsibility_per_capita
        **Pre-allocation responsibility.** If ``True``, uses per-capita
        cumulative emissions. If ``False`` (default), uses absolute
        cumulative emissions.
    pre_allocation_responsibility_exponent
        **Pre-allocation responsibility.** Exponent applied to the
        emissions metric. Default: 1.0.
    pre_allocation_responsibility_functional_form
        **Pre-allocation responsibility.** Transformation: ``'asinh'``
        (default) or ``'power'``.
    capability_per_capita
        **Capability.** If ``True`` (default), GDP is divided by
        population. If ``False``, absolute GDP is used.
    capability_exponent
        **Capability.** Exponent applied to the GDP metric. Default: 1.0.
    capability_functional_form
        **Capability.** Transformation: ``'asinh'`` (default) or
        ``'power'``.
    capability_reference_year
        **Capability.** When ``None`` (default), capability is computed
        year-by-year. When set to an integer, GDP from that single year
        is broadcast across the allocation window. May be before or
        after ``allocation_year``.
        When before, Gini adjustment is NOT applied to the snapshot.
        Ignored when ``capability_weight == 0``.
    max_deviation_sigma
        **Constraint.** Maximum allowed deviation from equal per capita,
        in standard deviations. ``None`` (default) means no constraint.
    preserve_allocation_year_shares
        **Mode.** If ``False`` (default), uses cumulative adjusted
        population from ``allocation_year`` onwards. If ``True``, uses
        population at ``allocation_year`` only.
    historical_discount_rate
        **Pre-allocation responsibility.** Discount rate for historical
        emissions (0.0 to <1.0), via ``(1 - rate)^(reference_year - t)``
        Default: 0.0. Only affects the pre-allocation
        responsibility calculation.
    cumulative_end_year
        Upper bound of the cumulative window. ``None`` (default) uses the
        last year in the population data.
    group_level
        Index level name for grouping. Default: ``'iso3c'``.
    unit_level
        Index level name for units. Default: ``'unit'``.
    ur
        Pint unit registry for unit conversions.

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

    See docs/science/allocations.md#historical-responsibility for CBDR-RC
    alignment and parameter considerations. For implementation examples
    combining pre-allocation responsibility and capability adjustments,
    see docs/science/principle-to-code.md.

    **GDP window:** When the allocation cumulative window extends past the last
    year of the input ``gdp_ts``, the GDP per capita values from the last
    observed year are forward-filled to cover the full window. This preserves
    the cross-country capability ratios of the last observed year, but those
    ratios then get weighted against the full post-observation population
    trajectory. Users who want different post-observation capability dynamics
    (SSP2 projections, custom growth assumptions, or a future-extended WDI
    release) should extend the input ``gdp_ts`` time series before calling
    this function. The forward-fill is the minimum-disruption default when
    no projected GDP data is supplied.

    See Also
    --------
    equal_per_capita_budget : Without responsibility or capability adjustments
    per_capita_adjusted_gini_budget : With Gini-adjusted GDP capability weighting

    """
    return _per_capita_budget_core(
        population_ts=population_ts,
        allocation_year=allocation_year,
        emission_category=emission_category,
        country_actual_emissions_ts=country_actual_emissions_ts,
        responsibility_emissions_ts=responsibility_emissions_ts,
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
        capability_reference_year=capability_reference_year,
        max_deviation_sigma=max_deviation_sigma,
        preserve_allocation_year_shares=preserve_allocation_year_shares,
        historical_discount_rate=historical_discount_rate,
        cumulative_end_year=cumulative_end_year,
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
    responsibility_emissions_ts: TimeseriesDataFrame | None = None,
    # Adjustment weights
    pre_allocation_responsibility_weight: float = 0.0,
    capability_weight: float = 1.0,
    # Pre-allocation responsibility parameters
    pre_allocation_responsibility_year: int = 1990,
    pre_allocation_responsibility_per_capita: bool = False,
    pre_allocation_responsibility_exponent: float = 1.0,
    pre_allocation_responsibility_functional_form: str = "asinh",
    # Capability parameters
    capability_per_capita: bool = True,
    capability_exponent: float = 1.0,
    capability_functional_form: str = "asinh",
    capability_reference_year: int | None = None,
    # Gini parameters
    income_floor: float = 0.0,
    max_gini_adjustment: float = 0.8,
    # Deviation constraint
    max_deviation_sigma: float | None = None,
    # Mode
    preserve_allocation_year_shares: bool = False,
    # Historical emissions discounting
    historical_discount_rate: float = 0.0,
    # Cumulative window upper bound
    cumulative_end_year: int | None = None,
    # Common parameters
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:
    r"""
    Per capita budget allocation with pre-allocation responsibility, capability, and Gini adjustments.

    This function generates cumulative shares for the allocation year based
    on adjusted per capita principles, incorporating pre-allocation responsibility,
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
    - $R(g)$: Pre-allocation responsibility adjustment factor (equals 1.0 if not used)
    - $C_{\text{Gini}}(g, t)$: Gini-adjusted capability factor (equals 1.0 if not used)
    - $P(g, t)$: Population of country $g$ in year $t$
    - $t_a$: Allocation year

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

    **Pre-Allocation Responsibility Adjustment**

    Identical to per capita adjusted budget (see that function for details).

    For per capita pre-allocation responsibility (:code:`pre_allocation_responsibility_per_capita=True`):

    $$
    R(g) = \left(\frac{\sum_{t=t_h}^{t_a-1} E(g, t)}{\sum_{t=t_h}^{t_a-1} P(g, t)}\right)^{-w_r \times e_r}
    $$

    Where:

    - $E(g, t)$: Emissions of country $g$ in year $t$
    - $t_h$: Pre-allocation responsibility start year
    - $t_a$: Allocation year
    - $w_r$: Normalized pre-allocation responsibility weight
    - $e_r$: Pre-allocation responsibility exponent

    **Capability Adjustment with Gini-Adjusted GDP**

    For per capita capability (:code:`capability_per_capita=True`, default):

    $$
    C_{\text{Gini}}(g, t) = \left(\frac{\text{GDP}^{\text{adj}}(g, t)}{P(g, t)}\right)^{-w_c \times e_c}
    $$

    Where:

    - $C_{\text{Gini}}(g, t)$: Gini-adjusted capability factor (inverse - higher adjusted GDP = lower allocation)
    - $\text{GDP}^{\text{adj}}(g, t)$: Gini-adjusted GDP (see :func:`~fair_shares.library.utils.math.allocation.calculate_gini_adjusted_gdp`)
    - $w_c$: Normalized capability weight
    - $e_c$: Capability exponent

    When combined with the income floor, higher inequality means more income
    above the development threshold, giving high-inequality countries smaller
    emission allocations than unadjusted GDP would suggest.

    By default (``capability_reference_year=None``), $C_{\text{Gini}}(g, t)$
    is computed year-by-year. Setting ``capability_reference_year`` to an
    integer freezes capability at that year: $C_{\text{Gini}}(g, t) \equiv
    C_{\text{Gini}}(g, t_{\text{ref}})$ for all $t$ in the window. Note that
    when ``capability_reference_year < allocation_year``, the Gini adjustment
    is NOT applied to the snapshot (see ``capability_reference_year`` in the
    Parameters section and ``_per_capita_budget_core`` for the implementation
    detail).

    Two allocation modes are supported based on
    :code:`preserve_allocation_year_shares`:

    - **False** (default): Uses cumulative adjusted population from
      allocation_year onwards
    - **True**: Uses adjusted population at allocation_year only

    Parameters
    ----------
    population_ts
        Population time series for each group of interest.
    gdp_ts
        **Capability.** GDP time series (required). Used from
        ``allocation_year`` onwards for capability calculations.
    gini_s
        **Gini.** Gini coefficients for within-country income inequality
        (required). Used to adjust GDP before computing the capability
        factor.
    allocation_year
        Year from which to calculate budget shares. See
        ``docs/science/parameter-effects.md`` §allocation_year.
    emission_category
        Emission category (e.g., ``'co2-ffi'``, ``'all-ghg'``).
    country_actual_emissions_ts
        **Pre-allocation responsibility.** Historical emissions data.
        Required when ``pre_allocation_responsibility_weight > 0``.
    pre_allocation_responsibility_weight
        **Pre-allocation responsibility.** Relative weight (0–1). Only the
        ratio to ``capability_weight`` matters. When 0, pre-allocation
        responsibility is disabled.
        See ``docs/science/parameter-effects.md`` §weights.
    capability_weight
        **Capability.** Relative weight (0–1, default 1.0). Applies from
        ``allocation_year`` onwards. When 0, capability is disabled.
    pre_allocation_responsibility_year
        **Pre-allocation responsibility.** Start year of the historical
        window. Default: 1990.
    pre_allocation_responsibility_per_capita
        **Pre-allocation responsibility.** If ``True``, uses per-capita
        cumulative emissions. If ``False`` (default), uses absolute
        cumulative emissions.
    pre_allocation_responsibility_exponent
        **Pre-allocation responsibility.** Exponent applied to the
        emissions metric. Default: 1.0.
    pre_allocation_responsibility_functional_form
        **Pre-allocation responsibility.** Transformation: ``'asinh'``
        (default) or ``'power'``.
    capability_per_capita
        **Capability.** If ``True`` (default), Gini-adjusted GDP is
        divided by population. If ``False``, absolute Gini-adjusted GDP
        is used.
    capability_exponent
        **Capability.** Exponent applied to the Gini-adjusted GDP metric.
        Default: 1.0.
    capability_functional_form
        **Capability.** Transformation: ``'asinh'`` (default) or
        ``'power'``.
    capability_reference_year
        **Capability.** When ``None`` (default), capability is computed
        year-by-year. When set to an integer, GDP from that single year
        is broadcast across the allocation window. When before
        ``allocation_year``, Gini
        adjustment is NOT applied to the snapshot.
        Ignored when ``capability_weight == 0``.
    income_floor
        **Gini.** Development threshold in USD PPP per capita. Income
        below this is excluded from capability calculations, adapted from
        GDR. Default: 0.0. See
        ``docs/science/parameter-effects.md`` §income_floor.
    max_gini_adjustment
        **Gini.** Maximum reduction factor from threshold deduction (0–1).
        Default: 0.8.
    max_deviation_sigma
        **Constraint.** Maximum allowed deviation from equal per capita,
        in standard deviations. ``None`` (default) means no constraint.
    preserve_allocation_year_shares
        **Mode.** If ``False`` (default), uses cumulative adjusted
        population from ``allocation_year`` onwards. If ``True``, uses
        population at ``allocation_year`` only.
    historical_discount_rate
        **Pre-allocation responsibility.** Discount rate for historical
        emissions (0.0 to <1.0), via ``(1 - rate)^(reference_year - t)``
        Default: 0.0. Only affects the pre-allocation
        responsibility calculation.
    cumulative_end_year
        Upper bound of the cumulative window. ``None`` (default) uses the
        last year in the population data.
    group_level
        Index level name for grouping. Default: ``'iso3c'``.
    unit_level
        Index level name for units. Default: ``'unit'``.
    ur
        Pint unit registry for unit conversions.

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

    See docs/science/allocations.md#gini-adjustment for intra-national equity
    considerations. For implementation examples combining capability with
    subsistence protection, see docs/science/principle-to-code.md.

    **GDP window:** When the allocation cumulative window extends past the last
    year of the input ``gdp_ts``, the (Gini-adjusted) GDP per capita values
    from the last observed year are forward-filled to cover the full window.
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
    equal_per_capita_budget : Without responsibility or capability adjustments
    per_capita_adjusted_budget : Without Gini adjustment to capability weighting

    """
    return _per_capita_budget_core(
        population_ts=population_ts,
        allocation_year=allocation_year,
        emission_category=emission_category,
        country_actual_emissions_ts=country_actual_emissions_ts,
        responsibility_emissions_ts=responsibility_emissions_ts,
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
        capability_reference_year=capability_reference_year,
        income_floor=income_floor,
        max_gini_adjustment=max_gini_adjustment,
        max_deviation_sigma=max_deviation_sigma,
        preserve_allocation_year_shares=preserve_allocation_year_shares,
        historical_discount_rate=historical_discount_rate,
        cumulative_end_year=cumulative_end_year,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )
