---
title: How-to
description: Pick the notebook and guide for your case
---

# How-to

## Which notebook do I start with?

Two questions decide it.
**What are you dividing up?** A *budget* is one cumulative number per country. A *pathway* is a value for every year.
**Who between?** Individual *countries*, or the *model regions* of an integrated assessment model.

|                       | Countries                                     | IAM model regions                                          |
| --------------------- | --------------------------------------------- | ----------------------------------------------------------- |
| **A budget**          | `302_example_templates_budget_allocations`    | run `400` once, then `402_example_iamc_budget_allocations`   |
| **A pathway**         | `303_example_templates_pathway_allocations`   | run `400` once, then `403_example_iamc_pathway_allocations`  |
| **Your own settings** | `301_custom_fair_share_allocation`            | run `400` once, then `401_custom_iamc_allocation`            |
| **One region, model has no rest-of-world data** | | `405_one_region_remaining_budget` ([One region of countries](iamc-regional-fair-shares.md#one-region-of-countries)) |
| **Reproduce a published study** | `601`, `602`, `604` and `605` (see [Reproductions](../reproductions/index.md)) | |

The 302, 303, 402 and 403 notebooks run unchanged.
You configure 301 and 401 yourself. 401 also exports a model-ready remaining budget.

## Guides

- **[Country fair shares](country-fair-shares.md)**: the country notebooks, step by step.
- **[IAM model regions](iamc-regional-fair-shares.md)**: preparing a scenario file with notebook 400 and allocating to its regions.
- **[Updating data each year](update-data.md)**: moving to a new data release.
- **[Reproduce a published study](../reproductions/index.md)**: the 600-series notebooks.
- **[The ESABCC presets](eu-budgets.md)**: national and EU27 budgets with the settings of the ESABCC 2023 advice.

Calling the library from your own Python code? See the [Python API](../api/python-api.md).

## Choosing an approach

Decide two things.
First, do you need one cumulative number or a value for every year?
Second, which principles count: equal entitlements, historical responsibility, capability, or a combination?
[From principle to code](../science/principle-to-code.md) turns principles into settings.
The [Approach catalog](approach-catalog.md) lists every approach.

Every run records its parameters and data sources with the results ([Outputs](output-schema.md)).
Sources carry different licences ([Data & licences](data-sources.md)).
