---
title: Allocation Manager
description: High-level interface for running allocations with data loading and output management
---

# Allocation Manager

The `fair_shares.library.allocations.manager` module provides the high-level interface for running allocations with data loading and output management.

## Running Allocations

!!! note "`run_allocation` is not `run_all_allocations`"

    Two similarly-named functions do different jobs, and the notebooks use the second one.

    - **`allocations.manager.run_allocation`** (documented below) runs **one** allocation for **one** approach against timeseries frames you pass in, and returns a `BudgetAllocationResult` or `PathwayAllocationResult`. This is the engine.
    - **`notebook_helpers.run_all_allocations`** is the orchestrator the workflow notebooks call. It takes an `allocations` grid plus the dict returned by `notebook_helpers.load_allocation_data`, runs every parameter combination across every final category, and — unless `write=False` — persists `allocations_relative.parquet`, `allocations_absolute.parquet`, a parameter manifest and a README.

    If you are following a notebook, you want `run_all_allocations`. If you are calling the library directly with your own frames, you want `run_allocation`.

### run_allocation

::: fair_shares.library.allocations.manager.run_allocation
    options:
        show_root_heading: false
        heading_level: 4
        show_source: false

### run_parameter_grid

::: fair_shares.library.allocations.manager.run_parameter_grid
    options:
        show_root_heading: false
        heading_level: 4
        show_source: false

## Results Processing

### calculate_absolute_emissions

::: fair_shares.library.allocations.manager.calculate_absolute_emissions
    options:
        show_root_heading: false
        heading_level: 4
        show_source: false

### save_allocation_result

::: fair_shares.library.allocations.manager.save_allocation_result
    options:
        show_root_heading: false
        heading_level: 4
        show_source: false

## Output Management

### generate_readme

::: fair_shares.library.allocations.manager.generate_readme
    options:
        show_root_heading: false
        heading_level: 4
        show_source: false

### create_param_manifest

::: fair_shares.library.allocations.manager.create_param_manifest
    options:
        show_root_heading: false
        heading_level: 4
        show_source: false

## See Also

- **[Budget Allocations](https://setupelz.github.io/fair-shares/api/allocations/budgets/)**: Low-level budget allocation functions
- **[Pathway Allocations](https://setupelz.github.io/fair-shares/api/allocations/pathways/)**: Low-level pathway allocation functions
- **[Country Fair Shares guide](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/)**: Choose and configure allocations
