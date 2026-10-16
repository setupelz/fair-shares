---
title: Docs conventions
description: How to write and check fair-shares documentation, docstrings and links
---

# Docs conventions

**Documentation must match the code.** When they conflict, the code is correct and the docs are wrong.

## Where each fact lives

| Layer | Location | Source of truth for |
| --- | --- | --- |
| Docstrings | `src/fair_shares/library/` | What the code does: maths, parameters, return types |
| Science docs | `docs/science/` | Why it works this way: equity principles, citations, design rationale |
| How-to and reference | `docs/user-guide/`, `docs/reproductions/` | How to use it: workflows, examples, file and column reference |
| API docs | `docs/api/` | Generated from docstrings by mkdocstrings |

How-to pages may simplify, but only when the simplification stays accurate. If an API page is wrong, fix the docstring.
State each fact once and link to it from elsewhere.

## Writing style

- Short sentences, one idea each, active voice and plain words.
- No em-dashes and no icons.
- State what is true now. Leave revision history and provenance notes to the changelog and commits.
- Name every source with a verified citation.

## Before merging a docs change

1. **Ground every technical claim.** A claim about behaviour, formulas or parameter effects must trace to a docstring, a science page or a test. A science page may name the function in an HTML comment:

    ```markdown
    <!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py -->
    ```

2. **Run every code example** and check that its output and comments match the text.
3. **Build strictly:** `uv run mkdocs build --strict` fails on broken links and missing pages. `uv run mkdocs serve` previews the site.

| Change | Update |
| --- | --- |
| New parameter | Docstring, `docs/science/allocations.md` if the maths changes, the how-to pages if users set it |
| Bug fix | Code, then the docstring if behaviour changed, then the examples it affects |
| Clearer docs | Read the docstring and science page first, and check your version against them |

## Links

Pages in `docs/` link to each other with relative paths to the `.md` file, for example `[Allocation approaches](../science/allocations.md)`.

Code that links to the site builds the URL in one module, `src/fair_shares/library/config/urls.py`:

| Name | Purpose |
| --- | --- |
| `DOCS_BASE_URL` | Site root. Defaults to `https://setupelz.github.io/fair-shares`; `FAIR_SHARES_DOCS_URL` overrides it |
| `docs_url(path)` | Joins a page path to `DOCS_BASE_URL`. Drops a `.md` suffix and a leading slash, and adds a trailing slash |
| `DOCS_URLS` | Prebuilt URLs for common pages, grouped as `science`, `user_guide` and `api` |

```python
from fair_shares.library.config.urls import DOCS_URLS, docs_url

docs_url("science/allocations")
# "https://setupelz.github.io/fair-shares/science/allocations/"

DOCS_URLS["user_guide"]["approach_catalog"]
```

`utils/io.py` uses `docs_url("user-guide/output-schema")` to point output README files at the Outputs page.
When the site moves, change `DOCS_BASE_URL` or set `FAIR_SHARES_DOCS_URL`, and every link built through `docs_url` follows.
A page that renames a heading keeps the old anchor with `{#old-anchor}`, because docstrings and error messages link to anchors.

## Docstrings for allocation approaches

Docstrings follow the numpy convention and need four sections: a one-line summary, the mathematical foundation in LaTeX, every parameter, and the return value.
The approaches in `allocations/budgets/per_capita.py` are the models.

```python
def my_new_allocation(
    population_ts: TimeseriesDataFrame,
    allocation_year: int,
    emission_category: str,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:
    r"""
    Short one-line summary of what this approach does.

    Longer description providing context on when to use this approach.

    Mathematical Foundation
    -----------------------

    The allocation is calculated as:

    $$
    A(g) = \frac{P(g, t_a)}{\sum_{g'} P(g', t_a)}
    $$

    Where:

    - $A(g)$: Budget share allocated to country $g$
    - $P(g, t_a)$: Population of country $g$ at allocation year $t_a$

    Parameters
    ----------
    population_ts
        Timeseries of population for each group
    allocation_year
        Year from which to start calculating allocations
    emission_category
        Emission category to include in the output
    group_level
        Level in the index which specifies group information
    unit_level
        Level in the index which specifies the unit of each timeseries
    ur
        The unit registry to use for calculations

    Returns
    -------
    BudgetAllocationResult
        Container with relative shares for cumulative emissions budget allocation.

    See Also
    --------
    `From Principle to Code <https://setupelz.github.io/fair-shares/science/principle-to-code/>`_
        Normative foundations and equity principles underlying allocation approaches.
    """
```

- Use a raw string (`r"""`) for LaTeX, and define every variable in an equation. Break a complex calculation into steps.
- For key parameters, link to the matching section of the Parameter effects page. For adjustment weights, state the direction of the effect. Give valid ranges and defaults.
- Check that the LaTeX renders with `uv run mkdocs serve`, and that parameter types match the signature.
