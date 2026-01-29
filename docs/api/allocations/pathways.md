---
title: Pathway Allocation Functions
description: API reference for pathway allocation functions that generate annual emission allocation shares over time using per capita and convergence-based approaches
---

# Pathway Allocation Functions

Pathway allocation functions generate annual emission allocation shares over time.

## Overview

All pathway allocation approaches return a `PathwayAllocationResult` containing:

- `approach`: Name of the allocation approach used
- `parameters`: Dictionary of parameters used in the calculation
- `relative_shares_pathway_emissions`: DataFrame of annual shares (sum to 1.0 each year)

## Per Capita Pathways

### equal_per_capita

::: fair_shares.library.allocations.pathways.per_capita.equal_per_capita
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### per_capita_adjusted

::: fair_shares.library.allocations.pathways.per_capita.per_capita_adjusted
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### per_capita_adjusted_gini

::: fair_shares.library.allocations.pathways.per_capita.per_capita_adjusted_gini
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

## Convergence Pathways

### per_capita_convergence

::: fair_shares.library.allocations.pathways.per_capita_convergence.per_capita_convergence
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### cumulative_per_capita_convergence

::: fair_shares.library.allocations.pathways.cumulative_per_capita_convergence.cumulative_per_capita_convergence
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### cumulative_per_capita_convergence_adjusted

::: fair_shares.library.allocations.pathways.cumulative_per_capita_convergence.cumulative_per_capita_convergence_adjusted
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### cumulative_per_capita_convergence_adjusted_gini

::: fair_shares.library.allocations.pathways.cumulative_per_capita_convergence.cumulative_per_capita_convergence_adjusted_gini
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

## See Also

- **[Budget Allocations]({DOCS_ROOT}/api/budgets/)**: Fixed cumulative budgets
- **[Scientific Documentation: Allocation Approaches]({DOCS_ROOT}/science/allocations/)**: Theoretical foundations
- **[country-fair-shares Guide]({DOCS_ROOT}/user-guide/country-fair-shares/)**: Conceptual overview
