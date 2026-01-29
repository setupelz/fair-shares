"""
Approaches for allocating a remaining emissions budget for fair-shares library.

"""

from __future__ import annotations

from .per_capita import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)

__all__ = [
    "equal_per_capita_budget",
    "per_capita_adjusted_budget",
    "per_capita_adjusted_gini_budget",
]
