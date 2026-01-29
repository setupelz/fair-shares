"""
Allocation orchestration and result handling for fair-shares library.

"""

from .manager import AllocationManager
from .registry import (
    get_allocation_functions,
    get_function,
    is_budget_approach,
    is_pathway_approach,
)
from .results import BudgetAllocationResult, PathwayAllocationResult

__all__ = [
    "AllocationManager",
    "BudgetAllocationResult",
    "PathwayAllocationResult",
    "get_allocation_functions",
    "get_function",
    "is_budget_approach",
    "is_pathway_approach",
]
