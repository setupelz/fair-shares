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

## See Also

- **[country-fair-shares Guide]({DOCS_ROOT}/user-guide/country-fair-shares/)**: Choose and configure allocations
- **[Developer Guide: Adding Data Sources]({DOCS_ROOT}/dev-guide/adding-data-sources/)**: Available data sources
