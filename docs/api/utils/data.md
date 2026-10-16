---
title: Data Processing Utilities
description: API reference for data processing utilities including convergence data preparation, NGHGI corrections, RCB processing and scenario sets
---

# Data Processing Utilities

Functions for processing and transforming input datasets: convergence pathway data preparation, NGHGI-consistent RCB corrections, RCB processing, and the scenario sets and scenario sources behind the budget terms.

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

Functions for converting IPCC RCBs to NGHGI-consistent values following Weber et al. (2026). See [Scientific Documentation](../../science/other-operations.md#weber-rcb-corrections) for methodology.

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

### bunker_deduction_from_share

::: fair_shares.library.utils.data.nghgi.bunker_deduction_from_share
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

Functions that parse RCB labels, integrate scenario series to net zero, and rebase budgets to 2020.

### parse_rcb_scenario

::: fair_shares.library.utils.data.rcb.parse_rcb_scenario
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### canonical_label

::: fair_shares.library.utils.data.rcb.canonical_label
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### canonical_scenarios

::: fair_shares.library.utils.data.rcb.canonical_scenarios
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### label_temperature

::: fair_shares.library.utils.data.rcb.label_temperature
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### resolve_scenario_selection

::: fair_shares.library.utils.data.rcb.resolve_scenario_selection
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### net_zero_crossing

::: fair_shares.library.utils.data.rcb.net_zero_crossing
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### integrate

::: fair_shares.library.utils.data.rcb.integrate
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### cumulative_to_net_zero

::: fair_shares.library.utils.data.rcb.cumulative_to_net_zero
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### convention_gap_from_baseline

::: fair_shares.library.utils.data.rcb.convention_gap_from_baseline
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

### fill_rebase_years

::: fair_shares.library.utils.data.rcb.fill_rebase_years
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## Scenario Sets

Role-matched scenario sets behind the scenario-derived budget terms: the volume-matched set (land-use deduction, convention gap, bunker window), the temperature-matched set (non-CO2 pathway) and the AR6 category pool. See [Other Operations](../../science/other-operations.md) for the method.

### BudgetSpec

::: fair_shares.library.utils.data.scenario_sets.BudgetSpec
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### budget_specs

::: fair_shares.library.utils.data.scenario_sets.budget_specs
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### scenario_set_settings

::: fair_shares.library.utils.data.scenario_sets.scenario_set_settings
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### budget_from_2020

::: fair_shares.library.utils.data.scenario_sets.budget_from_2020
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### scenario_accounting

::: fair_shares.library.utils.data.scenario_sets.scenario_accounting
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### select_volume_matched

::: fair_shares.library.utils.data.scenario_sets.select_volume_matched
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### select_temperature_matched

::: fair_shares.library.utils.data.scenario_sets.select_temperature_matched
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### build_budget_sets

::: fair_shares.library.utils.data.scenario_sets.build_budget_sets
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### bunker_share_table

::: fair_shares.library.utils.data.scenario_sets.bunker_share_table
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### bunker_share

::: fair_shares.library.utils.data.scenario_sets.bunker_share
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### median_pathways_by_budget

::: fair_shares.library.utils.data.scenario_sets.median_pathways_by_budget
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## Scenario Sources

The registry `fair_shares/conf/scenario_sources.yaml` declares each scenario source: its variables, metadata columns and bunker variables. See [Data Sources](../../user-guide/data-sources.md) for downloads and licences.

### get_scenario_source

::: fair_shares.library.utils.data.scenario_sources.get_scenario_source
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### load_bunker_pathways

::: fair_shares.library.utils.data.scenario_sources.load_bunker_pathways
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### annual_pathways

::: fair_shares.library.utils.data.scenario_sources.annual_pathways
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### read_workbook_sheet

::: fair_shares.library.utils.data.scenario_sources.read_workbook_sheet
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### model_family

::: fair_shares.library.utils.data.scenario_sources.model_family
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### bunker_reporter_series

::: fair_shares.library.utils.data.scenario_sources.bunker_reporter_series
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

### fetch_ar6_bunkers

::: fair_shares.library.utils.data.scenario_sources.fetch_ar6_bunkers
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## Global Carbon Budget

### gcb_global_net_co2

::: fair_shares.library.utils.data.gcb.gcb_global_net_co2
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false

## See Also

- **[Core Utilities](core.md)**: General data manipulation functions
- **[Math Utilities](math.md)**: Convergence solver and adjustments
- **[NGHGI Corrections (Science)](../../science/other-operations.md#weber-rcb-corrections)**: Scientific methodology
