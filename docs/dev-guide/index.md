---
title: Contributing
description: How to report issues, set up a development checkout and contribute to fair-shares
---

# Contributing

Bug reports, allocation approaches, data sources, documentation fixes and reproductions of published studies are all welcome.

## Reporting issues

Open an issue at [github.com/setupelz/fair-shares/issues](https://github.com/setupelz/fair-shares/issues).
Say what you ran (notebook, API call or `snakemake` invocation, with its sources and target), what you expected, what happened (the full traceback), and your Python version and install method.
For numbers that look wrong, name the approach, the emission category and the affected countries and years.

## Setup

```bash
git clone https://github.com/<your-username>/fair-shares.git
cd fair-shares
uv sync --extra dev
uv run pre-commit install
```

Notebooks are jupytext `.py` files. Edit the `.py`, never the `.ipynb`, and regenerate with `make sync-ipynb`.

## Making a change

1. Fork, and branch from `main` (for example `fix/lulucf-year-bounds`).
2. Change code and tests together. Allocation logic needs a test that pins the expected numbers.
3. Run `make test` and `make lint` (`make lint-fix` fixes what it can). Pre-commit runs ruff and checks 80% docstring coverage.
4. For docs changes, run `uv run mkdocs build --strict` ([Docs conventions](docs-conventions.md)).
5. Open a pull request that says what changed and why. If allocation results change, name the approaches and categories.

Docstrings follow the numpy convention and are the authoritative description of behaviour, because the API pages are generated from them. A behaviour change changes the docstring in the same commit.

## Conventions

- **Year columns are strings:** `df["2020"]`, never `df[2020]`. Call `ensure_string_year_columns(df)` after loading data.
- **Kebab-case for configuration, snake_case for Python:** `equal-per-capita-budget` names the approach, `equal_per_capita_budget` the function.
- **Index levels:** emissions use `iso3c`, `unit`, `emission-category`. GDP, population and Gini use `iso3c`, `unit`.

## Where the code lives

| Module            | Location                                  | Responsibility                                                    |
| ----------------- | ----------------------------------------- | ----------------------------------------------------------------- |
| **Allocations**   | `src/fair_shares/library/allocations/`    | Core allocation functions                                         |
| **Utilities**     | `src/fair_shares/library/utils/`          | Data manipulation, adjustments                                    |
| **Config**        | `src/fair_shares/library/config/`         | Pydantic models                                                   |
| **Preprocessing** | `src/fair_shares/library/preprocessing/`  | Reusable logic for the 100-series preprocessing notebooks         |
| **Pipeline**      | `src/fair_shares/library/pipeline/`       | Composite, RCB, pathway and non-CO2 preprocessing runners         |
| **IAMC history**  | `src/fair_shares/library/iamc_historical/` | Back-fills IAM scenarios with IAMC-consistent historical emissions |
| **Python API**    | `src/fair_shares/library/python_api.py`   | Computes allocation timeseries in memory, without notebooks       |
| **Presets**       | `src/fair_shares/library/presets/`        | Parameter grids of published studies (ESABCC 2023 / PRR2023)      |
| **Data fetch**    | `src/fair_shares/library/data_fetch.py`   | Downloads registry files and checks their checksums               |
| **Citations**     | `src/fair_shares/library/citations.py`    | Derives and formats the citations a run needs                     |
| **Data registry** | `src/fair_shares/library/data_registry.py` | Reads and checks `conf/data_registry.yaml` (source, licence, citation) |
| **Notebooks**     | `notebooks/1xx_*.py`                      | Data pipeline notebooks                                           |

[Architecture](architecture-walkthrough.md) follows one budget run and one pathway run through this code.

## New approaches and data sources

Every allocation approach expresses a set of equity principles. Before you add one, read [From principle to code](../science/principle-to-code.md) and work through the five entry points of [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f).

Three points from the literature apply to every new approach:

- **No approach is value-neutral.** Every allocation choice embeds normative judgements [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8); [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7).
- **Grandfathering has no philosophical support** and conflicts with the purpose of equity analysis [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8); [Kartha 2018](https://doi.org/10.1038/s41558-018-0152-7).
- **Contradictory principles do not combine** into a coherent result [Dooley 2021](https://doi.org/10.1038/s41558-021-01015-8).

Then follow [Adding approaches](adding-approaches.md) or [Adding data sources](adding-data-sources.md). A new data source needs a registry entry, a verified DOI record and a `CITATION.md` ([Registering the source](adding-data-sources.md#registering-the-source)).
