---
title: Configuration Models
description: Pydantic models for validating and managing configuration
---

# Configuration Models

Pydantic models for validating and managing configuration.

## Overview

The fair-shares library uses Pydantic models to validate configuration files.
These models ensure type safety and provide clear error messages when configuration is invalid.

## Data Sources Configuration

### DataSourcesConfig

::: fair_shares.library.config.models.DataSourcesConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: true

## Individual Data Source Configurations

### EmissionsSourceConfig

::: fair_shares.library.config.models.EmissionsSourceConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### PopulationSourceConfig

::: fair_shares.library.config.models.PopulationSourceConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### GDPSourceConfig

::: fair_shares.library.config.models.GDPSourceConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### GiniSourceConfig

::: fair_shares.library.config.models.GiniSourceConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### EmissionsCoverage

::: fair_shares.library.config.models.EmissionsCoverage
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### LulucfSourceConfig

::: fair_shares.library.config.models.LulucfSourceConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### ScenarioSourceConfig

::: fair_shares.library.config.models.ScenarioSourceConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### TargetSourceConfig

::: fair_shares.library.config.models.TargetSourceConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### RegionMappingConfig

::: fair_shares.library.config.models.RegionMappingConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

## Pipeline Settings

### GeneralConfig

::: fair_shares.library.config.models.GeneralConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### AdjustmentsConfig

::: fair_shares.library.config.models.AdjustmentsConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### AllGhgScenariosConfig

::: fair_shares.library.config.models.AllGhgScenariosConfig
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

### NonCO2Overrides

::: fair_shares.library.config.models.NonCO2Overrides
    options:
        show_root_heading: true
        heading_level: 4
        show_source: false
        members: false

## See Also

- **[Country Fair Shares guide](../../user-guide/country-fair-shares.md)**: Choose and configure allocations
- **[Developer Guide: Adding Data Sources](../../dev-guide/adding-data-sources.md)**: Available data sources
