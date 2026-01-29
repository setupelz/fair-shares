---
title: Budget Allocation Functions
description: API reference for budget allocation functions that distribute fixed cumulative emission budgets among countries using per capita and equity-based approaches
---

# Budget Allocation Functions

Budget allocation functions distribute a fixed cumulative emission budget among countries in a given allocation year.

## Overview

All budget allocation approaches return a `BudgetAllocationResult` containing:

- `approach`: Name of the allocation approach used
- `parameters`: Dictionary of parameters used in the calculation
- `relative_shares_cumulative_emission`: DataFrame of budget shares (sum to 1.0)

## Per Capita Budgets

### equal_per_capita_budget

::: fair_shares.library.allocations.budgets.per_capita.equal_per_capita_budget
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### per_capita_adjusted_budget

::: fair_shares.library.allocations.budgets.per_capita.per_capita_adjusted_budget
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### per_capita_adjusted_gini_budget

::: fair_shares.library.allocations.budgets.per_capita.per_capita_adjusted_gini_budget
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

## See Also

- **[Pathway Allocations](https://setupelz.github.io/fair-shares/api/pathways/)**: Annual emission pathways
- **[Scientific Documentation: Budget Allocations](https://setupelz.github.io/fair-shares/science/allocations/)**: Theoretical foundations
- **[country-fair-shares Guide](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/)**: Conceptual overview
