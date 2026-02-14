"""
Pathway generation utilities for the fair-shares library.

"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from fair_shares.library.exceptions import AllocationError


def list_pathway_generators() -> list[str]:
    """List available pathway generation methods."""
    return ["exponential-decay"]


def calculate_exponential_decay_pathway(
    total_budget: float,
    start_value: float,
    start_year: int,
    end_year: int,
    tolerance: float = 1e-6,
) -> pd.Series:
    """
    Generate an exponential decay emission pathway that sums to a total budget.

    Creates a pathway following normalized shifted exponential decay that reaches
    exactly zero at the end year:

        E(t) = start_value * (e^(-k*t) - e^(-k*T)) / (1 - e^(-k*T))

    where k is solved such that the discrete sum of annual emissions equals the
    total budget. The normalization factor (1 - e^(-k*T)) ensures:

    - E(0) = start_value (preserves initial year emissions)
    - E(T) = 0 (reaches exactly zero at end year)
    - Sum over all years equals total_budget

    This is more appropriate for RCB-derived pathways than standard exponential
    decay which asymptotically approaches (but never reaches) zero, ensuring the
    budget is fully consumed by the end year.

    Parameters
    ----------
    total_budget : float
        Total cumulative emissions budget to distribute over the pathway.
        Must be positive.
    start_value : float
        Initial emission rate at start_year (E(t_0)).
        Must be positive.
    start_year : int
        First year of the pathway (t_0).
    end_year : int
        Last year of the pathway (T), inclusive.
    tolerance : float, optional
        Relative tolerance for budget conservation verification.
        Default is 1e-6.

    Returns
    -------
    pd.Series
        Annual emissions pathway indexed by year (as strings).
        Values represent emissions for each year.

    Raises
    ------
    AllocationError
        If inputs are invalid, no solution exists, or budget constraint
        cannot be satisfied.

    Examples
    --------
    >>> pathway = calculate_exponential_decay_pathway(
    ...     total_budget=1000.0, start_value=50.0, start_year=2020, end_year=2050
    ... )
    >>> abs(pathway.sum() - 1000.0) < 0.01
    True
    """
    # Input validation
    if total_budget <= 0:
        raise AllocationError(f"total_budget must be positive, got {total_budget}")
    if start_value <= 0:
        raise AllocationError(f"start_value must be positive, got {start_value}")
    if end_year <= start_year:
        raise AllocationError(
            f"end_year ({end_year}) must be greater than start_year ({start_year})"
        )

    n_years = end_year - start_year + 1
    years = np.arange(n_years)  # 0, 1, 2, ..., n_years-1
    final_year_idx = n_years - 1  # Index of the final year

    # Check if the budget is achievable with shifted exponential
    # The maximum sum occurs when k->0 (linear decline from start_value to 0)
    # For n_years discrete points, the sum equals start_value * n_years / 2
    max_possible_sum = start_value * n_years / 2.0
    if max_possible_sum < total_budget:
        raise AllocationError(
            f"Cannot satisfy budget constraint: with shifted exponential "
            f"decay (ending at zero), maximum possible sum is approximately "
            f"{max_possible_sum:.2f}, which is less than total_budget "
            f"({total_budget:.2f}). "
            f"Consider increasing start_value or reducing total_budget."
        )

    # For the residual function fallback (when k<=0)
    constant_sum = start_value * n_years

    # Define the function to find root of shifted exponential decay
    # E(t) = start_value * (e^(-k*t) - e^(-k*T)) / (1 - e^(-k*T))
    # This ensures E(0) = start_value and E(T) = 0 exactly
    def budget_residual(k: float) -> float:
        """Calculate difference between pathway sum and target budget.

        Uses normalized shifted exponential:
        E(t) = start_value * (e^(-k*t) - e^(-k*T)) / (1 - e^(-k*T))

        This ensures:
        - E(0) = start_value (preserves initial emissions)
        - E(T) = 0 (reaches zero at end year)
        """
        if k <= 0:
            # For k=0, we'd have division by zero
            # Return a large positive value to push k higher
            return constant_sum - total_budget

        # Shifted and normalized exponential decay
        exp_values = np.exp(-k * years)
        end_value = np.exp(-k * final_year_idx)
        norm_factor = 1.0 - end_value

        # Avoid division by zero for very small k
        if norm_factor < 1e-15:
            return constant_sum - total_budget

        pathway_values = start_value * (exp_values - end_value) / norm_factor

        return pathway_values.sum() - total_budget

    # Find bounds for k
    # At k=0: sum = E0 * n_years (maximum possible sum)
    # As k -> infinity: sum -> E0 (only first year has emissions)
    k_min = 1e-10  # Small positive k
    k_max = 10.0  # Large k (very rapid decay)

    # Check that root exists in interval
    residual_at_min = budget_residual(k_min)
    residual_at_max = budget_residual(k_max)

    if residual_at_min < 0:
        raise AllocationError(
            f"Cannot satisfy budget constraint: even with minimal decay, "
            f"pathway sum (~{max_possible_sum:.2f}) is less than budget "
            f"({total_budget:.2f})."
        )

    if residual_at_max > 0:
        # Even with very rapid decay, we exceed the budget
        # This means budget < start_value (only one year of emissions)
        if total_budget < start_value:
            raise AllocationError(
                f"Cannot satisfy budget constraint: total_budget ({total_budget:.2f}) "
                f"is less than start_value ({start_value:.2f}). "
                f"The first year alone exceeds the budget."
            )
        # Extend search range
        k_max = 100.0
        residual_at_max = budget_residual(k_max)
        if residual_at_max > 0:
            raise AllocationError(
                "Cannot find decay rate k that satisfies budget constraint. "
                "Budget may be too small relative to start_value."
            )

    # Solve for k using Brent's method (robust bracketed root finding)
    try:
        k_optimal = brentq(budget_residual, k_min, k_max, xtol=1e-12)
    except ValueError as e:
        raise AllocationError(
            f"Failed to find decay rate k: {e}. "
            f"Check that budget ({total_budget}) is achievable with "
            f"start_value ({start_value}) over {n_years} years."
        ) from e

    # Generate the normalized shifted exponential pathway
    # E(t) = start_value * (e^(-k*t) - e^(-k*T)) / (1 - e^(-k*T))
    exp_values = np.exp(-k_optimal * years)
    end_value = np.exp(-k_optimal * final_year_idx)
    norm_factor = 1.0 - end_value
    pathway_values = start_value * (exp_values - end_value) / norm_factor

    # Verify the first year matches start_value (within numerical precision)
    if abs(pathway_values[0] - start_value) > 1e-6:
        raise AllocationError(
            f"Pathway first year {pathway_values[0]:.2f} does not match "
            f"start_value {start_value:.2f}"
        )

    # Verify the final year is exactly zero (within numerical precision)
    if abs(pathway_values[-1]) > 1e-10:
        raise AllocationError(
            f"Pathway does not reach zero at end year: "
            f"final value = {pathway_values[-1]:.2e}"
        )

    # Verify budget conservation
    actual_sum = pathway_values.sum()
    relative_error = abs(actual_sum - total_budget) / total_budget
    if relative_error > tolerance:
        raise AllocationError(
            f"Budget conservation failed: pathway sums to {actual_sum:.2f} "
            f"but target was {total_budget:.2f} (relative error: {relative_error:.2e})"
        )

    # Create Series with year index as strings (codebase convention)
    year_labels = [str(start_year + i) for i in range(n_years)]
    pathway = pd.Series(pathway_values, index=year_labels)

    return pathway


def generate_rcb_pathway_scenarios(
    rcbs_df: pd.DataFrame,
    world_emissions_df: pd.DataFrame,
    start_year: int,
    end_year: int,
    emission_category: str,
    generator: str = "exponential-decay",
) -> pd.DataFrame:
    """
    Generate pathway scenarios from RCB data.

    For each RCB scenario (combination of source, climate-assessment, quantile),
    generates a separate pathway starting from historical world emissions at
    start_year and summing to the RCB budget. This preserves all individual
    RCB sources rather than averaging across sources.

    Parameters
    ----------
    rcbs_df : pd.DataFrame
        Processed RCBs with columns: source, climate-assessment, quantile,
        emission-category, rcb_2020_mt.
    world_emissions_df : pd.DataFrame
        World historical emissions with MultiIndex (iso3c, unit, emission-category)
        and year columns as strings.
    start_year : int
        First year of pathways (typically 2020).
    end_year : int
        Last year of pathways (typically 2100).
    emission_category : str
        Emission category to process (e.g., "co2-ffi").
    generator : str, optional
        Name of the pathway generator to use. Default is "exponential-decay".
        Currently supported: "exponential-decay".

    Returns
    -------
    pd.DataFrame
        TimeseriesDataFrame with MultiIndex (climate-assessment, quantile, source,
        iso3c, unit, emission-category) and year columns containing
        World pathway emissions. One pathway per RCB source.

        Note: 'source' is included as an index level (after quantile) to preserve
        all individual RCB sources for allocations.

    Raises
    ------
    AllocationError
        If required data is missing, generator is unknown, or pathway
        generation fails.
    """
    # Select pathway generator function
    if generator == "exponential-decay":
        pathway_func = calculate_exponential_decay_pathway
    else:
        raise AllocationError(
            f"Unknown pathway generator: '{generator}'. "
            f"Supported generators: ['exponential-decay']"
        )

    # Filter RCBs to emission category
    rcbs_filtered = rcbs_df[rcbs_df["emission-category"] == emission_category].copy()

    if rcbs_filtered.empty:
        raise AllocationError(
            f"No RCBs found for emission category '{emission_category}'"
        )

    # Get start year emissions from world data
    start_year_str = str(start_year)
    if start_year_str not in world_emissions_df.columns:
        raise AllocationError(
            f"Start year {start_year} not found in world emissions data. "
            f"Available years: {list(world_emissions_df.columns)}"
        )

    # Extract world emissions for the emission category
    category_mask = (
        world_emissions_df.index.get_level_values("emission-category")
        == emission_category
    )
    world_category = world_emissions_df[category_mask]

    if world_category.empty:
        raise AllocationError(
            f"No world emissions found for category '{emission_category}'"
        )

    if len(world_category) != 1:
        raise AllocationError(
            f"Expected exactly one World row for category '{emission_category}', "
            f"found {len(world_category)}"
        )

    start_emissions = float(world_category[start_year_str].iloc[0])
    if np.isnan(start_emissions):
        raise AllocationError(
            f"Start year emissions for '{emission_category}' is NaN in world data"
        )

    unit = world_category.index.get_level_values("unit")[0]

    # Generate pathways for each RCB scenario (including source)
    # This preserves all individual RCB sources instead of averaging
    pathway_records = []

    for _, row in rcbs_filtered.iterrows():
        source = row["source"]
        climate_assessment = row["climate-assessment"]
        quantile = row["quantile"]
        total_budget = float(row["rcb_2020_mt"])

        # Generate pathway using the selected generator
        pathway = pathway_func(
            total_budget=total_budget,
            start_value=start_emissions,
            start_year=start_year,
            end_year=end_year,
        )

        # Create record with index values and pathway data
        record = {
            "source": source,
            "climate-assessment": climate_assessment,
            "quantile": quantile,
            "iso3c": "World",
            "unit": unit,
            "emission-category": emission_category,
        }
        record.update(pathway.to_dict())
        pathway_records.append(record)

    # Create DataFrame
    result_df = pd.DataFrame(pathway_records)

    # Set MultiIndex with source as a scenario dimension
    # Placing it after quantile but before iso3c maintains logical grouping
    index_cols = [
        "climate-assessment",
        "quantile",
        "source",  # Keep source in index for uniqueness
        "iso3c",
        "unit",
        "emission-category",
    ]
    result_df = result_df.set_index(index_cols)

    return result_df
