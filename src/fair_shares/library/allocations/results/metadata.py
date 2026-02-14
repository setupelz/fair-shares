"""
Column metadata and type specifications for allocation results.

This module defines the standard columns and data types used in allocation
result DataFrames. Separating this metadata from the AllocationManager improves
maintainability and makes column definitions reusable across the codebase.
"""

from __future__ import annotations

# Data context columns (from data_context parameter)
DATA_CONTEXT_COLUMNS: list[str] = [
    "source-id",  # from data_context['source-id']
    "allocation-folder",  # from data_context['allocation-folder']
    "emissions-source",  # from data_context['emissions-source']
    "gdp-source",  # from data_context['gdp-source']
    "population-source",  # from data_context['population-source']
    "gini-source",  # from data_context['gini-source']
    # from data_context['target-source']
    # (e.g., 'rcbs', 'ar6', 'cr', 'rcb-pathways')
    "target-source",
    # from data_context['rcb-generator']
    # (pathway generator for rcb-pathways, None otherwise)
    "rcb-generator",
    # from data_context['source']
    # (specific source/model/pathway within target)
    "source",
    "emission-category",  # from data_context['emission-category']
    # cumulative net-negative emissions from scenarios
    "missing-net-negative-mtco2e",
    # warnings about allocation (e.g., not-fair-share, missing data)
    "warnings",
]

# Allocation parameter columns (from result.parameters)
ALLOCATION_PARAMETER_COLUMNS: list[str] = [
    "first-allocation-year",
    "allocation-year",
    "preserve-first-allocation-year-shares",
    "preserve-allocation-year-shares",
    "convergence-year",
    "convergence-speed",
    "responsibility-weight",
    "capability-weight",
    "historical-responsibility-year",
    "responsibility-per-capita",
    "capability-per-capita",
    "responsibility-exponent",
    "capability-exponent",
    "responsibility-functional-form",
    "capability-functional-form",
    "max-deviation-sigma",
    "income-floor",
    "max-gini-adjustment",
]

# Core metadata columns (from function parameters)
CORE_METADATA_COLUMNS: list[str] = [
    "climate-assessment",
    "quantile",
    "total-budget",
    "approach",
]

# Required columns that must always be present
REQUIRED_COLUMNS: list[str] = ["iso3c", "unit"]

# Data type specifications for numeric columns
NUMERIC_COLUMN_TYPES: dict[str, str] = {
    "quantile": "float64",
    "first-allocation-year": "Int64",
    "allocation-year": "Int64",
    "convergence-year": "Int64",
    "convergence-speed": "float64",
    "total-budget": "float64",
    "missing-net-negative-mtco2e": "Int64",
    "warnings": "string",
    "responsibility-weight": "float64",
    "capability-weight": "float64",
    "historical-responsibility-year": "Int64",
    "responsibility-exponent": "float64",
    "capability-exponent": "float64",
    "max-deviation-sigma": "float64",
    "income-floor": "float64",
    "max-gini-adjustment": "float64",
}


def get_all_metadata_columns() -> list[str]:
    """
    Get all metadata columns in the desired order.

    Returns
    -------
    list[str]
        Ordered list of all metadata column names
    """
    return (
        DATA_CONTEXT_COLUMNS
        + CORE_METADATA_COLUMNS
        + REQUIRED_COLUMNS
        + ALLOCATION_PARAMETER_COLUMNS
    )
