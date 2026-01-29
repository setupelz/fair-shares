"""
Approaches for allocating an emissions pathway for fair-shares library.

"""

from __future__ import annotations

from .cumulative_per_capita_convergence import (
    cumulative_per_capita_convergence,
    cumulative_per_capita_convergence_adjusted,
    cumulative_per_capita_convergence_adjusted_gini,
)
from .per_capita import (
    equal_per_capita,
    per_capita_adjusted,
    per_capita_adjusted_gini,
)
from .per_capita_convergence import per_capita_convergence

__all__ = [
    "cumulative_per_capita_convergence",
    "cumulative_per_capita_convergence_adjusted",
    "cumulative_per_capita_convergence_adjusted_gini",
    "equal_per_capita",
    "per_capita_adjusted",
    "per_capita_adjusted_gini",
    "per_capita_convergence",
]
