"""
Per capita convergence pathway allocation.

WARNING: This is NOT an equity-based approach. Per Capita Convergence blends
grandfathering (allocating based on current emission shares) with equal per capita
and is included for comparison only. Grandfathering rewards past high emissions
and lacks ethical basis per fair shares literature.

For detailed critique of why grandfathering lacks ethical basis, see:
    docs/science/allocations.md#per-capita-convergence-pcc-why-its-not-an-equity-based-approach

This module implements the per capita convergence approach, which transitions
allocation shares from current emission shares to equal per capita shares over
a convergence period. Related to Contraction and Convergence [GCI 2003].

For allocations grounded in CBDR-RC principles, consider per_capita_adjusted
or cumulative_per_capita_convergence approaches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from pandas_openscm.index_manipulation import (
    ensure_index_is_multiindex,
    set_index_levels_func,
)

from fair_shares.library.allocations.results import PathwayAllocationResult
from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils import (
    filter_time_columns,
    get_default_unit_registry,
    groupby_except_robust,
    set_single_unit,
)
from fair_shares.library.validation import validate_single_emission_category
from fair_shares.library.validation.models import AllocationInputs, AllocationOutputs

if TYPE_CHECKING:
    import pint.facets

    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def _per_capita_convergence_core(
    population_ts: TimeseriesDataFrame,
    country_actual_emissions_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    convergence_year: int,
    emission_category: str,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    """
    Core per capita convergence pathway allocation logic without validation.

    This function implements the linear interpolation between grandfathering
    (current emission shares) and equal per capita allocation over the
    specified convergence period.

    The approach is related to Contraction and Convergence [GCI 2003], where
    global emissions contract to meet climate targets while per capita emissions
    converge to equality by a target date.

    This is the raw implementation without input/output validation.
    Use per_capita_convergence() for the validated version.
    """
    # Set first_allocation_year and convergence_year to integer
    first_allocation_year = int(first_allocation_year)
    convergence_year = int(convergence_year)

    # Determine last year from population data
    last_year = int(max(population_ts.columns, key=lambda x: int(x)))

    # Validate inputs using Pydantic model
    AllocationInputs(
        population_ts=population_ts,
        first_allocation_year=first_allocation_year,
        last_allocation_year=last_year,
        country_actual_emissions_ts=country_actual_emissions_ts,
    )

    # Validate inputs
    if first_allocation_year >= convergence_year:
        raise AllocationError(
            "first_allocation_year must be less than convergence_year"
        )

    # Validate single emission category (not covered by decorator)
    validate_single_emission_category(country_actual_emissions_ts, "emissions data")

    # Subset input data to only include years from first_allocation_year onwards
    population_filtered = filter_time_columns(population_ts, first_allocation_year)

    # Convert data to consistent units
    population_single_unit = set_single_unit(population_filtered, unit_level, ur=ur)
    emissions_single_unit = set_single_unit(
        country_actual_emissions_ts, unit_level, ur=ur
    )

    # Get population and emissions data at first_allocation_year
    # (robust to str/int labels)
    pop_year_to_label = {int(c): c for c in population_single_unit.columns}
    emis_year_to_label = {int(c): c for c in emissions_single_unit.columns}
    pop_allocation = population_single_unit[pop_year_to_label[first_allocation_year]]
    emissions_allocation = emissions_single_unit[
        emis_year_to_label[first_allocation_year]
    ]

    # Exclude aggregate rows like 'World' from emissions to align with population
    # The population input is expected to contain only country/group rows
    # while emissions may include an aggregate 'World' row used for budgets.
    if (
        isinstance(emissions_allocation.index, pd.MultiIndex)
        and group_level in emissions_allocation.index.names
    ):
        group_values = emissions_allocation.index.get_level_values(group_level)
        emissions_allocation = emissions_allocation.loc[group_values != "World"]

    # Calculate baseline shares at first_allocation_year
    pop_total_allocation = groupby_except_robust(pop_allocation, group_level)
    emissions_total_allocation = groupby_except_robust(
        emissions_allocation, group_level
    )

    gf_shares = emissions_allocation.divide(emissions_total_allocation)
    pc_shares = pop_allocation.divide(pop_total_allocation)

    # Ensure both shares have the population's index structure for alignment
    gf_shares.index = pop_allocation.index
    pc_shares.index = pop_allocation.index

    # Vectorized blending across all years
    time_ints = (
        pd.to_numeric(population_filtered.columns, errors="coerce")
        .astype(int)
        .to_numpy()
    )
    denom = float(convergence_year - first_allocation_year)
    weights = np.where(
        time_ints <= first_allocation_year,
        1.0,
        np.where(
            time_ints >= convergence_year, 0.0, (convergence_year - time_ints) / denom
        ),
    )

    # Broadcast and blend (we can't use the standard broadcast_shares_to_periods
    # function here because these change over time with blending from GF to EPC)
    gf_arr = gf_shares.to_numpy()[:, None]
    epc_arr = pc_shares.to_numpy()[:, None]
    weights_row = weights[None, :]
    res_values = gf_arr * weights_row + epc_arr * (1.0 - weights_row)
    res = pd.DataFrame(
        res_values, index=gf_shares.index, columns=population_filtered.columns
    )

    # Renormalize within each group for numerical stability
    blended_total = groupby_except_robust(res, group_level)
    res = res.divide(blended_total)

    # Set units to dimensionless
    res = ensure_index_is_multiindex(res)
    res = set_index_levels_func(res, {unit_level: "dimensionless"}, copy=False)

    # Add emission category to the index
    res = res.assign(**{"emission-category": emission_category})
    res = res.set_index("emission-category", append=True)

    # Validate outputs using Pydantic model
    AllocationOutputs(
        shares=res,
        dataset_name="per-capita-convergence pathway allocation",
        first_year=first_allocation_year,
    )

    # Create and return PathwayAllocationResult
    return PathwayAllocationResult(
        approach="per-capita-convergence",
        parameters={
            "first_allocation_year": first_allocation_year,
            "convergence_year": convergence_year,
            "emission_category": emission_category,
            "group_level": group_level,
            "unit_level": unit_level,
        },
        relative_shares_pathway_emissions=res,
    )


def per_capita_convergence(
    population_ts: TimeseriesDataFrame,
    country_actual_emissions_ts: TimeseriesDataFrame,
    first_allocation_year: int,
    convergence_year: int,
    emission_category: str,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> PathwayAllocationResult:
    r"""
    Per capita convergence pathway blending grandfathering and equal per capita.

    This approach transitions from grandfathering (GF) to equal per capita (EPC)
    from allocation time, $t_{a}$, to convergence time, $t_{conv}$, using a
    linear weight $M(t)$. It implements a variant of Contraction and Convergence
    [GCI 2003], where global emissions contract while per capita emissions
    converge to equality by a target date.

    Mathematical Foundation
    -----------------------

    **Baseline Shares at Allocation Time**

    Grandfathering and equal per capita shares at allocation time are calculated as:

    $$
    \mathrm{GF}(g) = \frac{E(g, t_{a})}{\sum_{g'} E(g', t_{a})}
    $$

    $$
    \mathrm{EPC}(g) = \frac{P(g, t_{a})}{\sum_{g'} P(g', t_{a})}
    $$

    Where:

    - $E(g, t_{a})$: Emissions of country $g$ at first allocation year $t_a$
    - $P(g, t_{a})$: Population of country $g$ at first allocation year $t_a$

    **Time-Dependent Blending Weight**

    The transition weight $M(t)$ controls the blend between grandfathering and
    equal per capita:

    - $M(t) = 1$ for $t \le t_{a}$ (full grandfathering at start)
    - $M(t) = \frac{t_{conv} - t}{t_{conv} - t_{a}}$ for $t_{a} < t < t_{conv}$
    - $M(t) = 0$ for $t \ge t_{conv}$ (full equal per capita at convergence)

    **Blended Allocation**

    The final allocation blends the two principles:

    $$
    A(g, t) = M(t) \cdot \mathrm{GF}(g) + (1 - M(t)) \cdot \mathrm{EPC}(g)
    $$

    Parameters
    ----------
    population_ts
        Timeseries of population for each group of interest.
    country_actual_emissions_ts
        Timeseries of emissions for each group of interest.
    first_allocation_year
        First year that should be used for calculating the allocation.
        This must be a column in both population and emissions.
    convergence_year
        Year by which allocations fully converge to equal per capita.
    emission_category
        Emission category to include in the output.
    group_level
        Level in index specifying group information. Default: 'iso3c'
    unit_level
        Level in index specifying units. Default: 'unit'
    ur
        The unit registry to use for calculations.

    Returns
    -------
    PathwayAllocationResult
        Container with relative shares for pathway emissions allocation.
        The TimeseriesDataFrame contains all years from first_allocation_year onwards
        with shares that sum to 1 across groups for the specified emission category.

    Notes
    -----
    WARNING: This is NOT an equity-based approach. For detailed critique, see:
        docs/science/allocations.md#per-capita-convergence-pcc-why-its-not-an-equity-based-approach

    **When to Use**

    - Academic comparison with Contraction and Convergence scenarios
    - Exploring sensitivity of allocations to transition period length
    - When a gradual transition from status quo is explicitly desired

    **Limitations**

    - Does not incorporate historical responsibility for past emissions
    - Does not incorporate capability/ability to pay
    - The grandfathering starting point lacks ethical basis (see referenced docs)

    For allocations grounded in CBDR-RC principles, consider using
    per_capita_adjusted or cumulative_per_capita_convergence approaches.

    Examples
    --------
    Calculate per capita convergence allocation transitioning from current
    emission shares to equal per capita shares over a 30-year period.

    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data(
    ...     countries=["USA", "CHN", "IND"], years=[2020, 2030, 2050]
    ... )
    >>> result = per_capita_convergence(
    ...     population_ts=data["population"],
    ...     country_actual_emissions_ts=data["emissions"],
    ...     first_allocation_year=2020,
    ...     convergence_year=2050,
    ...     emission_category="co2-ffi",
    ... )
    >>> result.approach
    'per-capita-convergence'
    >>> result.parameters["convergence_year"]
    2050
    >>> # Result contains relative shares that blend from current emissions
    >>> # (grandfathering) at 2020 to equal per capita at 2050
    >>> result.relative_shares_pathway_emissions.sum(axis=0).round(3)  # doctest: +SKIP
    2020    1.000
    2030    1.000
    2050    1.000
    dtype: float64

    See Also
    --------
    per_capita_adjusted : Equal per capita with responsibility/capability adjustments
    cumulative_per_capita_convergence : Convergence accounting for cumulative emissions
    """
    return _per_capita_convergence_core(
        population_ts=population_ts,
        country_actual_emissions_ts=country_actual_emissions_ts,
        first_allocation_year=first_allocation_year,
        convergence_year=convergence_year,
        emission_category=emission_category,
        group_level=group_level,
        unit_level=unit_level,
        ur=ur,
    )
