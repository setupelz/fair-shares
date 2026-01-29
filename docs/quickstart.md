---
title: Quick Start
description: Installation and first steps with fair-shares
search:
  boost: 2
---

# Quick Start

## Prerequisites

- Python 3.10+
- Git
- [uv](https://github.com/astral-sh/uv)

## Installation

```bash
git clone https://github.com/setupelz/fair-shares.git
cd fair-shares
uv sync
```

Verify:

```bash
uv run pytest tests/unit
```

## Running Notebooks

```bash
uv run jupyter lab
```

| Workflow                  | Notebook                                           |
| ------------------------- | -------------------------------------------------- |
| country-fair-shares       | `notebooks/301_custom_fair_share_allocation.ipynb` |
| iamc-regional-fair-shares | `notebooks/401_iamc_fair_share_allocation.ipynb`   |

See [User Guide]({DOCS_ROOT}/user-guide/index/) for detailed workflow documentation.
