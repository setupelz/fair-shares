---
title: Data Processing Utilities
description: API reference for data processing utilities including convergence data preparation, NGHGI corrections, and RCB processing
---

# Data Processing Utilities

Functions for processing and transforming input datasets: convergence pathway data preparation, NGHGI-consistent RCB corrections, and RCB scenario processing.

## Convergence Data Processing

### process_emissions_data

::: fair_shares.library.utils.data.convergence.process_emissions_data
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### calculate_initial_shares

::: fair_shares.library.utils.data.convergence.calculate_initial_shares
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### process_world_scenario_data

::: fair_shares.library.utils.data.convergence.process_world_scenario_data
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### process_population_data

::: fair_shares.library.utils.data.convergence.process_population_data
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### build_result_dataframe

::: fair_shares.library.utils.data.convergence.build_result_dataframe
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## NGHGI Corrections

Functions for converting IPCC RCBs to NGHGI-consistent values following Weber et al. (2026). See [Scientific Documentation](https://setupelz.github.io/fair-shares/science/other-operations/#nghgi-consistent-rcb-corrections) for methodology.

### load_world_co2_lulucf

::: fair_shares.library.utils.data.nghgi.load_world_co2_lulucf
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### load_bunker_timeseries

::: fair_shares.library.utils.data.nghgi.load_bunker_timeseries
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### compute_bunker_deduction

::: fair_shares.library.utils.data.nghgi.compute_bunker_deduction
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### build_nghgi_world_co2_timeseries

::: fair_shares.library.utils.data.nghgi.build_nghgi_world_co2_timeseries
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### compute_cumulative_emissions

::: fair_shares.library.utils.data.nghgi.compute_cumulative_emissions
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false


## RCB Processing

Functions for parsing RCB scenarios and converting to allocation-ready budgets.

### parse_rcb_scenario

::: fair_shares.library.utils.data.rcb.parse_rcb_scenario
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### calculate_budget_from_rcb

::: fair_shares.library.utils.data.rcb.calculate_budget_from_rcb
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### process_rcb_to_2020_baseline

::: fair_shares.library.utils.data.rcb.process_rcb_to_2020_baseline
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## See Also

- **[Core Utilities](https://setupelz.github.io/fair-shares/api/utils/core/)**: General data manipulation functions
- **[Math Utilities](https://setupelz.github.io/fair-shares/api/utils/math/)**: Convergence solver and adjustments
- **[NGHGI Corrections (Science)](https://setupelz.github.io/fair-shares/science/other-operations/#nghgi-consistent-rcb-corrections)**: Scientific methodology
