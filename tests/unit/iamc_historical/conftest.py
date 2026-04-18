"""Shared helpers for iamc_historical tests."""

from __future__ import annotations

import pandas as pd
import pyam


def build_iamc_scenario(
    *,
    variables: tuple[tuple[str, str], ...],
    regions: tuple[str, ...] = ("TINY 1.0|BRA-only", "TINY 1.0|IND-USA"),
    start_year: int = 2015,
    end_year: int = 2020,
    value: float = 10.0,
    model: str = "TINY 1.0",
    scenario: str = "dummy",
) -> pyam.IamDataFrame:
    """Build a flat IAMC IamDataFrame for test scenarios.

    ``variables`` is a tuple of ``(variable_name, unit)`` pairs. Every region
    gets every variable at every year; all values are ``value``.
    """
    rows = [
        {
            "model": model,
            "scenario": scenario,
            "region": r,
            "variable": v,
            "unit": u,
            "year": y,
            "value": value,
        }
        for r in regions
        for v, u in variables
        for y in range(start_year, end_year + 1)
    ]
    return pyam.IamDataFrame(pd.DataFrame(rows))
