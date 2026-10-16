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
- `make` (optional; see [Installing Make](#installing-make) below)

## Installation

```bash
git clone https://github.com/setupelz/fair-shares.git
cd fair-shares
uv sync
```

`uv sync` installs the full contributor toolchain (Snakemake, the notebook
stack and the test runner), so the pipeline and the notebooks work with no
further configuration.

Verify:

```bash
uv run pytest tests/unit
```

## Getting the input data

Most of the pipeline's inputs are third-party datasets published elsewhere.
Download them from pinned URLs, with checksums enforced:

```bash
uv run fair-shares fetch-data
```

That fetches roughly 80 MB: everything a standard country-level run needs.
Add `--all` for the optional sources, another ~165 MB: the AR6 scenario
ensemble, CMIP7 historical, the WIID inequality data, PRIMAP-hist v2.6.1
(`primap-202503`) and the LULUCF Data Hub v3.1.1 (`melo-2026`). You can skip
`--all` and let those arrive on demand. The AR6 ensemble, for instance,
downloads the first time a run needs it.

```bash
uv run fair-shares fetch-data --all     # include the optional sources
uv run fair-shares fetch-data --list    # source, version, size, licence, citation
uv run fair-shares fetch-data --verify  # re-hash what is present, download nothing
```

Inside a clone the files land in the checkout's own `data/`. From an installed
wheel outside a checkout they go to your platform's user data directory, or to
`FAIR_SHARES_DATA_DIR` if you set it. You do not have to run the command at all
if you would rather not: a missing input is fetched automatically the first time
something needs it, announcing what it is downloading. Set
`FAIR_SHARES_AUTO_FETCH=0` to disable that for offline or CI runs.

### When a checksum does not match

The run stops. It does not warn and continue, and it does not overwrite the file
in place. The message names the file and both hashes.
Either the download is damaged, in which case `--force` re-fetches it, or
upstream has re-released under the same URL, in which case the registry pin
needs updating deliberately.

Two sources are unpinnable by nature: the World Bank and Our World in Data
regenerate their exports in place without version identifiers. Those are
reported as **vintage drift** rather than failing, and the hash you actually got
is recorded in the `PROVENANCE.md` written into your data directory.

### Files you place yourself

Budget allocations need two files that `fetch-data` cannot download:

- `gcb-2025-global`: the Global Carbon Budget 2025 global workbook. It sits
  behind the ICOS licence-acceptance page. It expresses each budget from 2020.
- `ipcc_ar6_bunkers`: the world aviation and shipping CO2 of the AR6
  scenarios. One command reads it from the public AR6 Scenarios Database. It
  feeds the bunker share.

For step-by-step instructions:

```bash
uv run fair-shares fetch-data --source gcb-2025-global
uv run fair-shares fetch-data --source ipcc_ar6_bunkers
```

Follow them, then run `--verify` to confirm each file. Observed bunkers come
from the `gcb-2025` file, which `fetch-data` downloads.

The Scenario Compass ensemble (`sci-2025`) is optional. It adds bunker
reporters to the bunker share. Access is on request, and its embargo terms
apply until Riahi et al. is published. Without it, the bunker share uses the
AR6 reporters only. See [Data Sources & Licensing](user-guide/data-sources.md)
and [What Happens Where](user-guide/pipeline-map.md).

### Licences

Sources carry different terms. Several are CC BY and require attribution in
anything you derive from them. Some may not be redistributed at all.
`--list` shows the licence and citation for each, and the generated
`PROVENANCE.md` carries the same information alongside the data itself.

The default emissions source, PRIMAP-hist v2.8 (`primap-202609`), is licensed
CC BY-NC-SA 4.0. Results from a default run therefore carry non-commercial,
share-alike terms. For CC BY results, set the emissions source to
`primap-202503` or `gcb-2025`. [Data Sources & Licensing](user-guide/data-sources.md)
lists the terms of every source.

### Installing the library on its own

If you only want to call the allocation functions from your own Python code,
install the package without the authoring toolchain:

```bash
pip install fair-shares
```

That is all the allocation functions need. They take population and GDP as
pandas dataframes and return a result object. They need no files, no data
directory and no configuration. See [Python API](api/python-api.md) for a worked example.

The higher-level entry points do read files from disk. Point them at your data
with two environment variables (or pass `data_dir=` and `output_dir=`
explicitly):

```bash
export FAIR_SHARES_DATA_DIR=/path/to/data
export FAIR_SHARES_OUTPUT_DIR=/path/to/output
```

When the processed files they need are missing, they rebuild them with
Snakemake, which a plain install does not include. Either point them at a data
tree that has already been built, or install the extra:

```bash
pip install "fair-shares[pipeline]"
```

### Anaconda / Conda

If you use Anaconda or Miniconda, skip the `uv` prerequisite. Use `conda` to create the environment and `pip` to install:

```bash
conda create -n fair-shares python=3.11
conda activate fair-shares
pip install -e ".[pipeline,dev,docs]"
```

Verify:

```bash
pytest tests/unit
```

Sync notebooks (replaces `make sync-ipynb`, which requires `uv`):

```bash
jupytext --sync notebooks/*.py
jupytext --set-formats ipynb,py:percent notebooks/*.py
```

Then launch JupyterLab:

```bash
jupyter lab
```

!!! note

    `make` targets that call `uv` (e.g. `make sync-ipynb`, `make test`) will not work in a conda environment. Use the equivalent commands shown above instead.

## Notebook Format

This project uses [jupytext](https://jupytext.readthedocs.io/) to store notebooks as plain Python files (`.py`) in the `py:percent` format. This means:

- **`.py` files** are the source format: version-controlled, clean diffs, easy to edit in any IDE
- **`.ipynb` files** are generated from the `.py` files and used for interactive execution in JupyterLab

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

    The `.py` files run directly: the `.py` files directly with `uv run python notebooks/301_custom_fair_share_allocation.py`. The `.ipynb` format serves the interactive JupyterLab experience.

## Running Notebooks

```bash
uv run jupyter lab
```

### Which notebook do I start with?

The [User Guide](user-guide/index.md) has a table that picks the notebook for your case.

IAM users start with notebook `400`. It writes `output/iamc/iamc_covered.xlsx`, which notebooks `401`, `402` and `403` read.

Working from your own Python code instead of notebooks? See
[Python API](api/python-api.md).

See the [User Guide](user-guide/index.md) for detailed workflow documentation.

## Installing Make

`make` is a standard build tool used to run project commands conveniently. It is optional: every `make` target has an equivalent `uv` command shown in the [Makefile](https://github.com/setupelz/fair-shares/blob/main/Makefile).

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
