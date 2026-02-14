---
title: Quick Start
description: Installation and first steps with fair-shares
search:
  boost: 2
---

# Quick Start

## Prerequisites

- Python 3.11+
- Git
- [uv](https://github.com/astral-sh/uv)
- `make` (optional but recommended — see [Installing Make](#installing-make) below)

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

## Notebook Format

This project uses [jupytext](https://jupytext.readthedocs.io/) to store notebooks as plain Python files (`.py`) in the `py:percent` format. This means:

- **`.py` files** are the source format — version-controlled, clean diffs, easy to edit in any IDE
- **`.ipynb` files** are generated from the `.py` files — used for interactive execution in JupyterLab

After cloning (or pulling new changes), sync the `.ipynb` files:

```bash
make sync-ipynb
```

??? note "Without `make`"

    ```bash
    uv run jupytext --sync notebooks/*.py
    uv run jupytext --set-formats ipynb,py:percent notebooks/*.py
    ```

!!! tip

    You don't _need_ `.ipynb` files — you can run the `.py` files directly with `uv run python notebooks/301_custom_fair_share_allocation.py`. The `.ipynb` format is only needed if you want the interactive JupyterLab experience.

## Running Notebooks

```bash
uv run jupyter lab
```

| Workflow                  | Notebook                                           |
| ------------------------- | -------------------------------------------------- |
| country-fair-shares       | `notebooks/301_custom_fair_share_allocation.ipynb` |
| iamc-regional-fair-shares | `notebooks/401_custom_iamc_allocation.ipynb`       |

See [User Guide](https://setupelz.github.io/fair-shares/user-guide/) for detailed workflow documentation.

## Installing Make

`make` is a standard build tool used to run project commands conveniently. It is optional — every `make` target has an equivalent `uv` command shown in the [Makefile](https://github.com/setupelz/fair-shares/blob/main/Makefile).

=== "macOS"

    Already installed with Xcode Command Line Tools:
    ```bash
    xcode-select --install
    ```

=== "Linux (Debian/Ubuntu)"

    ```bash
    sudo apt install make
    ```

=== "Linux (Fedora/RHEL)"

    ```bash
    sudo dnf install make
    ```

=== "Windows"

    Install via [Chocolatey](https://chocolatey.org/install):
    ```powershell
    choco install make
    ```

    Or via [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):
    ```powershell
    winget install GnuWin32.Make
    ```
