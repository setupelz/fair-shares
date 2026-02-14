"""
Allocation approach registry and lookup functions.

This module provides the central registry mapping approach names to allocation
functions, along with helper functions for querying the registry.
"""

from typing import Any, Callable

from fair_shares.library.allocations.budgets import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)
from fair_shares.library.allocations.pathways import (
    cumulative_per_capita_convergence,
    cumulative_per_capita_convergence_adjusted,
    cumulative_per_capita_convergence_adjusted_gini,
    equal_per_capita,
    per_capita_adjusted,
    per_capita_adjusted_gini,
    per_capita_convergence,
)
from fair_shares.library.exceptions import AllocationError


def get_allocation_functions() -> dict[str, Callable[..., Any]]:
    """
    Get the allocation function registry.

    Returns a dictionary mapping approach names to allocation functions.
    Each approach operationalizes different equity principles from the climate
    justice literature.

    Returns
    -------
    dict[str, Callable]
        Dictionary mapping approach names to allocation functions

    Notes
    -----
    Budget approaches (ending in "-budget") allocate a cumulative emissions
    budget at a single point in time, rather than allocating emissions
    year-by-year along a pathway.

    Pathway approaches allocate emissions over multiple years, producing annual
    emission shares that collectively respect a global emissions trajectory.

    The per-capita-convergence approach privileges current emission patterns
    during transition and is not considered a fair share approach.

    Cumulative approaches account for historical emissions since a reference
    year, addressing the principle that past emissions have consumed finite
    atmospheric space.
    """
    return {
        # Pathway allocations - distribute emissions over time
        "equal-per-capita": equal_per_capita,
        "per-capita-adjusted": per_capita_adjusted,
        "per-capita-adjusted-gini": per_capita_adjusted_gini,
        # Note: per-capita-convergence privileges current emission patterns
        # during transition - not considered a fair share approach
        "per-capita-convergence": per_capita_convergence,
        # Cumulative approaches account for historical emissions since a
        # reference year, addressing the principle that past emissions have
        # consumed finite atmospheric space
        "cumulative-per-capita-convergence": cumulative_per_capita_convergence,
        "cumulative-per-capita-convergence-adjusted": (
            cumulative_per_capita_convergence_adjusted
        ),
        "cumulative-per-capita-convergence-gini-adjusted": (
            cumulative_per_capita_convergence_adjusted_gini
        ),
        # Budget allocations - distribute a cumulative budget at a point in time
        "equal-per-capita-budget": equal_per_capita_budget,
        "per-capita-adjusted-budget": per_capita_adjusted_budget,
        "per-capita-adjusted-gini-budget": per_capita_adjusted_gini_budget,
    }


def get_function(approach: str) -> Callable[..., Any]:
    """
    Get allocation function by approach name.

    Parameters
    ----------
    approach : str
        Name of the allocation approach (e.g., "equal-per-capita-budget")

    Returns
    -------
    Callable
        The allocation function implementing the specified approach

    Raises
    ------
    AllocationError
        If the approach name is not recognized
    """
    allocation_functions = get_allocation_functions()
    if approach not in allocation_functions:
        raise AllocationError(
            f"Unknown allocation approach: {approach}. "
            f"Available: {list(allocation_functions.keys())}"
        )
    return allocation_functions[approach]


def is_budget_approach(approach: str) -> bool:
    """
    Check if the approach is a budget allocation approach.

    Budget approaches allocate a cumulative emissions budget (e.g., a remaining
    carbon budget) at a single point in time, rather than allocating emissions
    year-by-year along a pathway.

    Parameters
    ----------
    approach : str
        Name of the allocation approach

    Returns
    -------
    bool
        True if the approach is a budget approach, False otherwise
    """
    return approach.endswith("-budget")


def is_pathway_approach(approach: str) -> bool:
    """
    Check if the approach is a pathway allocation approach.

    Pathway approaches allocate emissions over multiple years, producing annual
    emission shares that collectively respect a global emissions trajectory.

    Parameters
    ----------
    approach : str
        Name of the allocation approach

    Returns
    -------
    bool
        True if the approach is a pathway approach, False otherwise
    """
    return not approach.endswith("-budget")
