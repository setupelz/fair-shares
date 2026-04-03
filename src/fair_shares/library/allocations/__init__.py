"""
Allocation engine and result handling for fair-shares library.

"""

from .manager import (
    all_metadata_columns,
    calculate_absolute_emissions,
    convert_budget_config_to_pathway,
    create_param_manifest,
    delete_existing_parquet_files,
    derive_pathway_allocations,
    generate_readme,
    get_allocation_functions,
    get_function,
    get_pathway_analogue,
    is_budget_approach,
    is_pathway_approach,
    run_allocation,
    run_parameter_grid,
    save_allocation_result,
)
from .results import BudgetAllocationResult, PathwayAllocationResult

__all__ = [
    "BudgetAllocationResult",
    "PathwayAllocationResult",
    "all_metadata_columns",
    "calculate_absolute_emissions",
    "convert_budget_config_to_pathway",
    "create_param_manifest",
    "delete_existing_parquet_files",
    "derive_pathway_allocations",
    "generate_readme",
    "get_allocation_functions",
    "get_function",
    "get_pathway_analogue",
    "is_budget_approach",
    "is_pathway_approach",
    "run_allocation",
    "run_parameter_grid",
    "save_allocation_result",
]
