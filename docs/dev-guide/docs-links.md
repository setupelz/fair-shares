---
title: Documentation Links
description: How code builds links to the documentation site
---

# Documentation Links

Code that writes a link to the documentation site builds it from one module: `src/fair_shares/library/config/urls.py`.

## What `urls.py` holds

| Name            | Purpose                                                                                                   |
| --------------- | --------------------------------------------------------------------------------------------------------- |
| `DOCS_BASE_URL` | Site root. Defaults to `https://setupelz.github.io/fair-shares`; set `FAIR_SHARES_DOCS_URL` to override it. |
| `docs_url(path)` | Joins a page path to `DOCS_BASE_URL`. Drops a `.md` suffix and a leading slash, and adds a trailing slash. |
| `DOCS_URLS`     | Prebuilt URLs for common pages, grouped as `science`, `user_guide` and `api`.                              |

## Building a link in code

```python
from fair_shares.library.config.urls import DOCS_URLS, docs_url

docs_url("science/allocations")
# "https://setupelz.github.io/fair-shares/science/allocations/"

DOCS_URLS["user_guide"]["approach_catalog"]
```

`utils/io.py` uses `docs_url("user-guide/output-schema")` to point output README files at the output schema page.

## Links inside the docs

Pages in `docs/` link to each other with relative paths to the `.md` file, for example `[Allocation Approaches](../science/allocations.md)`. `uv run mkdocs build --strict` fails on a link to a missing page.

## When the site moves

Change `DOCS_BASE_URL` in `urls.py`, or set `FAIR_SHARES_DOCS_URL`. Every link built through `docs_url` follows.
