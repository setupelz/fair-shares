---
title: Developer Guide
description: Architecture overview and extension guide for the fair-shares library
icon: material/code-braces
---

# Developer Guide

This guide explains the fair-shares architecture and how to extend the library.

---

## Architecture Overview

> **For a detailed end-to-end walkthrough with worked examples**, see the [Architecture Walkthrough](architecture-walkthrough.md).

```mermaid
graph TB
    subgraph Input
        DS[Data Sources<br/>conf/data_sources/]
        RAW[Raw Data<br/>data/]
    end

    subgraph Pipeline
        PP[Preprocessing<br/>notebooks/1xx]
        SM[Snakemake<br/>Snakefile]
    end

    subgraph Library
        AL[Allocations<br/>allocations/]
        UT[Utilities<br/>utils/]
        CF[Config<br/>config/]
    end

    subgraph Output
        RES[Results<br/>output/]
    end

    DS --> PP
    RAW --> PP
    PP --> SM
    SM --> AL
    AL --> RES
    UT --> AL
    CF --> AL
```

---

## Key Modules

| Module            | Location                               | Responsibility                 |
| ----------------- | -------------------------------------- | ------------------------------ |
| **Allocations**   | `src/fair_shares/library/allocations/` | Core allocation functions      |
| **Utilities**     | `src/fair_shares/library/utils/`       | Data manipulation, adjustments |
| **Config**        | `src/fair_shares/library/config/`      | Pydantic models                |
| **Preprocessing** | `notebooks/1xx_*.py`                   | Data pipeline notebooks        |

---

## Allocations Module

### Structure

```
allocations/
├── __init__.py
├── budgets/
│   ├── __init__.py
│   └── per_capita.py      # Budget allocation functions
├── pathways/
│   ├── __init__.py
│   ├── per_capita.py      # Pathway allocation functions
│   ├── per_capita_convergence.py
│   └── cumulative_per_capita_convergence.py
├── results/               # Result dataclasses
├── core.py               # Shared logic
├── manager.py            # Orchestration + approach name → function registry
└── runner.py             # Category-level allocation runner
```

### Entry Points

**Direct function calls:**

```python
from fair_shares.library.allocations.budgets import equal_per_capita_budget

result = equal_per_capita_budget(
    population_ts=population_df,
    allocation_year=2020,
    emission_category="co2-ffi",
)
```

**Manager functions (high-level):**

```python
from fair_shares.library.allocations import run_parameter_grid

results = run_parameter_grid(
    allocations_config=config,
    population_ts=population_df,
    # ...
)
```

### Result Types

| Type                      | Module                | Description                     |
| ------------------------- | --------------------- | ------------------------------- |
| `BudgetAllocationResult`  | `allocations.results` | Single cumulative allocation    |
| `PathwayAllocationResult` | `allocations.results` | Time-varying annual allocations |

`BudgetAllocationResult` contains `relative_shares_cumulative_emission`; `PathwayAllocationResult` contains `relative_shares_pathway_emissions`. Both sum to 1.0 and provide methods to compute absolute emissions.

---

## Adding New Functionality

All allocation approaches in this library can be linked to specific (sets of) equity principles. Before contributing new approaches, review the [From Principle to Code](../science/principle-to-code.md) documentation to understand the normative foundations.

Use the **Entry Points Framework** when considering any new approach: (1) foundational principles, (2) allocation quantity, (3) allocation approach, (4) indicators, (5) implications for all others [Pelz 2025b].

In particular, avoid:

- **Claiming value neutrality** — all allocation choices embed normative judgments [Dooley 2021; Kartha 2018]
- **Including grandfathering** — it has no philosophical support and contradicts equity purposes [Dooley 2021; Kartha 2018]
- **Combining contradictory principles** — produces incoherent results [Dooley 2021]

- **[Adding Allocation Approaches](https://setupelz.github.io/fair-shares/dev-guide/adding-approaches/)** - New equity principles
- **[Adding Data Sources](https://setupelz.github.io/fair-shares/dev-guide/adding-data-sources/)** - New datasets

---

## Conventions

### Year Columns as Strings

**Critical:** Year columns must be strings, not integers.

```python
# Correct
df["2020"]

# Incorrect
df[2020]
```

Always call `ensure_string_year_columns(df)` after loading data.

### Kebab vs Snake Case

| Context               | Style      | Example                   |
| --------------------- | ---------- | ------------------------- |
| Config/approach names | kebab-case | `equal-per-capita-budget` |
| Python identifiers    | snake_case | `equal_per_capita_budget` |

### Index Structure

DataFrames use MultiIndex with standard levels:

| Data Type      | Index Levels                         |
| -------------- | ------------------------------------ |
| Emissions      | `iso3c`, `unit`, `emission-category` |
| GDP/Population | `iso3c`, `unit`                      |
| Gini           | `iso3c`, `unit`                      |

---

## Testing

```bash
# Run all tests
uv run pytest tests/

# Run specific test module
uv run pytest tests/unit/allocations/

# Run with coverage
uv run pytest --cov=fair_shares tests/
```

---

## Code Quality

```bash
# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/
```

---

## Documentation Workflow

### Checking Documentation Consistency

Use `tools/docs-sync-check.py` to validate documentation is in sync with code:

```bash
# Run all validation checks
uv run python tools/docs-sync-check.py

# Suppress warnings (only show errors)
uv run python tools/docs-sync-check.py --quiet

# Show progress for each check
uv run python tools/docs-sync-check.py --verbose
```

**What it checks:**

| Check                     | Purpose                                                           |
| ------------------------- | ----------------------------------------------------------------- |
| **Registry coverage**     | All approaches in `manager.py` have API docs and catalog entries  |
| **Example syntax**        | Python code blocks in docs parse without syntax errors            |
| **Parameter consistency** | Parameters in code match those documented in `allocations.md`     |
| **Cross-references**      | Internal markdown links resolve to existing files and anchors     |

**Exit codes:**

- `0` - No errors (warnings may be present)
- `1` - One or more errors found
- `2` - Invalid command-line arguments

**Best practices:**

- Run before committing documentation changes
- Address errors immediately (broken links, invalid syntax)
- Review warnings to identify documentation gaps

**False positives:** The script automatically skips:

- Documentation examples with GOOD/BAD or CORRECT/WRONG markers (intentionally incomplete)
- Docstring section examples (showing docstring structure)
- DataFrame representations and tabular data
- Code blocks with ellipsis (`...`) or `TODO` comments

---

## See Also

- **[Architecture Walkthrough](architecture-walkthrough.md)** - End-to-end code path walkthrough with worked examples
- **[API Reference](https://setupelz.github.io/fair-shares/api/)** - Function documentation
- **[Scientific Documentation](https://setupelz.github.io/fair-shares/science/allocations/)** - Theoretical foundations
