# Contributing to fair-shares

Bug reports, allocation approaches, data sources, documentation fixes, and reproductions of published studies are all welcome. Documentation-editing conventions live in [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## Reporting issues

Open an issue at [github.com/setupelz/fair-shares/issues](https://github.com/setupelz/fair-shares/issues) with: what you ran (notebook, API call, or `snakemake` invocation, with source/target parameters), what you expected, what happened (full traceback), Python version and install method. For wrong-looking numbers, name the approach, emission category, and affected countries/years.

## Setup

Requires Python 3.11+, Git, and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/<your-username>/fair-shares.git
cd fair-shares
uv sync --extra dev
uv run pre-commit install
```

Notebooks are jupytext `.py` files. Edit the `.py`, never the `.ipynb`; regenerate with `make sync-ipynb`.

## Making a change

1. Fork, branch from `main` (`fix/lulucf-year-bounds`).
2. Change code and tests together — allocation logic needs a test pinning the expected numbers.
3. `make test` and `make lint` pass (`make lint-fix` auto-fixes; pre-commit runs ruff + 80% docstring coverage).
4. Open a PR describing what changed and why. If allocation results change, say which approaches and categories.

Docstrings (numpy convention) are the authoritative behaviour description — the API docs are generated from them. Behaviour change = docstring change, same commit.

## Adding approaches and data sources

- [Adding an allocation approach](https://setupelz.github.io/fair-shares/dev-guide/adding-approaches/)
- [Adding a data source](https://setupelz.github.io/fair-shares/dev-guide/adding-data-sources/)

A new data source needs a `CITATION.md` with the full citation, DOI, and licence. Never assert a DOI or licence you have not verified upstream; no DOI → name-only credit.

## Getting help

Open an issue. Check first: [Quick Start](https://setupelz.github.io/fair-shares/quickstart/), [Approach Catalog](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/), [Science docs](https://setupelz.github.io/fair-shares/science/).

## Licence

Contributions are licensed under the project's [BSD-3-Clause](LICENSE) licence.
