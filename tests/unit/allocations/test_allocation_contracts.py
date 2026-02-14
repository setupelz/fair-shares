from __future__ import annotations

import inspect

import pytest

from fair_shares.library.allocations.manager import AllocationManager
from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)

STANDARD_EMISSION_CATEGORY = "co2-ffi"


@pytest.mark.unit
def test_allocation_contracts(test_data):
    """
    Ensure every registered allocation function runs with shared synthetic data.
    """
    from fair_shares.library.allocations import get_allocation_functions

    manager = AllocationManager()
    allocation_functions = get_allocation_functions()
    first_allocation_year = test_data["first-allocation-year"]
    allocation_year = test_data["allocation-year"]

    shared_inputs = {
        "population_ts": test_data["population"],
        "gdp_ts": test_data["gdp"],
        "gini_s": test_data["gini"],
        "country_actual_emissions_ts": test_data["emissions"],
        "world_scenario_emissions_ts": test_data["world-emissions"],
        "emission_category": STANDARD_EMISSION_CATEGORY,
        "first_allocation_year": first_allocation_year,
        "allocation_year": allocation_year,
    }

    approach_overrides = {
        "per-capita-convergence": {"convergence_year": first_allocation_year + 30},
        # Unified function: variant determined by inputs (gdp_ts, gini_s, weights)
        "cumulative-per-capita-convergence": {
            "historical_responsibility_year": 1990,
            "responsibility_weight": 0.3,
            "capability_weight": 0.3,
        },
    }

    for approach, func in allocation_functions.items():
        overrides = approach_overrides.get(approach, {})
        sig = inspect.signature(func)
        kwargs = {}

        for name in sig.parameters:
            if name in overrides:
                kwargs[name] = overrides[name]
            elif name in shared_inputs:
                kwargs[name] = shared_inputs[name]

        missing_required = [
            name
            for name, param in sig.parameters.items()
            if param.default is inspect._empty and name not in kwargs
        ]
        if missing_required:
            pytest.skip(
                f"Skipping {approach} due to missing parameters: {missing_required}",
            )

        result = func(**kwargs)

        if approach.endswith("-budget"):
            assert isinstance(result, BudgetAllocationResult)
        else:
            assert isinstance(result, PathwayAllocationResult)
