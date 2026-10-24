---
title: Install and data
description: Install fair-shares, fetch its input data and run a first notebook
search:
  boost: 2
---

# Install and data

## Install

You need Python 3.11 or later, Git and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/setupelz/fair-shares.git
cd fair-shares
uv sync
uv run pytest tests/unit
```

`uv sync` installs the pipeline, the notebook tools and the test runner.

??? note "With conda instead of uv"

    ```bash
    conda create -n fair-shares python=3.11
    conda activate fair-shares
    pip install -e ".[pipeline,dev,docs]"
    pytest tests/unit
    ```

    The `make` targets call `uv`, so use the plain commands below in a conda environment.

To call the allocation functions from your own code, install from GitHub without the toolchain:

```bash
pip install "fair-shares @ git+https://github.com/setupelz/fair-shares"
```

The allocation functions take dataframes and read no files ([Python API](api/python-api.md)).
The higher-level entry points read processed data from disk.
Set `FAIR_SHARES_DATA_DIR` and `FAIR_SHARES_OUTPUT_DIR`, or pass `data_dir=` and `output_dir=`.
If the processed files are missing, they rebuild them with Snakemake, which needs the `pipeline` extra:

```bash
pip install "fair-shares[pipeline] @ git+https://github.com/setupelz/fair-shares"
```

## Ready-made inputs

Each release has a datapack: the processed inputs for every combination of the shipped emissions, land-use, GDP, population and Gini sources, targets and emission categories, which includes the defaults of every country notebook (301 to 303, 405, 601 to 605).
Allocation settings (approach, weights, years, income floor) are applied on top of these files, so any of them runs from the pack.
With it a run needs no raw data:

```bash
uv run fair-shares fetch-data --pack
```

The command downloads the pack of your installed version from its GitHub release, checks its hash and unpacks it into `output/`.
A folder you already have is kept; `--force` overwrites the pack's files in it and leaves your results alone.
`output/datapack-<version>/` holds the pack's README, licence and `CITATIONS.md`.

A folder is used as it is while it matches your code and configuration.
Edit either, or choose a harmonisation year other than the default and the notebooks', and that folder is rebuilt from raw inputs, which the next section covers.
The IAMC notebooks (400 to 403) read your own scenario file and need no pack.

The datapack is CC BY-NC-SA 4.0, because most of its folders derive from PRIMAP-hist v2.8, and results built on it carry the same terms.
For CC BY results, build the `primap-202503` or `gcb-2025` folders from raw inputs.
It holds pooled scenario statistics only (bunker shares, set medians and counts), never one row per scenario.

## Getting the input data

Most inputs are third-party datasets.
One command downloads them from pinned URLs and checks each file's hash:

```bash
uv run fair-shares fetch-data           # about 80 MB, everything a standard run needs
uv run fair-shares fetch-data --all     # about 165 MB more: optional sources
uv run fair-shares fetch-data --list    # source, version, size, licence, citation
uv run fair-shares fetch-data --verify  # re-hash what is present, download nothing
```

The optional sources are the AR6 scenario ensemble, CMIP7 historical, the WIID inequality data, PRIMAP-hist v2.6.1 (`primap-202503`) and the LULUCF Data Hub v3.1.1 (`melo-2026`).
A missing input also downloads the first time a run needs it.
Set `FAIR_SHARES_AUTO_FETCH=0` to turn that off for offline or CI runs.
Inside a clone the files land in `data/`. Outside a clone they go to your user data directory, or to `FAIR_SHARES_DATA_DIR`.

A file with the wrong hash stops the run, and the message names both hashes.
Re-fetch a damaged download with `--force`. If upstream re-released the file, the registry pin needs a deliberate update.
The World Bank and Our World in Data overwrite their exports without a version number. A changed hash from these two is reported as vintage drift, and `PROVENANCE.md` records the hash you got.

### Files you place yourself

This is the one list of manual inputs. `fetch-data` cannot download them.
Budget allocations need three:

- `gcb-2025-global`: the Global Carbon Budget 2025 global workbook, behind the ICOS licence page. It expresses each budget from 2020.
- `ipcc_ar6_bunkers`: world aviation and shipping CO2 of the AR6 scenarios. It feeds the bunker share.
- `ipcc_ar6_climate`: world CO2 and warming of every AR6 scenario. It gives each scenario's net-zero year and warming at net zero.

The two AR6 files come from the public AR6 Scenarios Database with one command each.
Name any manual input with `--source` for the steps, then run `--verify`:

```bash
uv run fair-shares fetch-data --source gcb-2025-global
uv run fair-shares fetch-data --source ipcc_ar6_bunkers
uv run fair-shares fetch-data --source ipcc_ar6_climate
```

A run reads the optional manual inputs only when its configuration selects them:

- `sci-2025` and `sci-2026`: the Scenario Compass ensembles. They add scenarios that report bunkers to the bunker share. Access is on request, and their embargo terms apply until Riahi et al. is published.
- `gcb-2025-luc`: Global Carbon Budget 2025 national land-use change CO2 from bookkeeping models, behind the ICOS licence page. It is the land-use source on the model basis, which notebook 405 uses by default.
- `scenariomip-cmip7`: the ScenarioMIP-CMIP7 scenarios, an alternative scenario source.
- `gcb-2024`: the Global Carbon Budget 2024 national workbook, an older source of observed bunkers.

### Licences

The default emissions source, PRIMAP-hist v2.8, is CC BY-NC-SA 4.0, so default results carry non-commercial, share-alike terms.
For CC BY results, use `primap-202503` or `gcb-2025`.
[Data & licences](user-guide/data-sources.md) gives the terms of every source.

## Run a notebook

Notebooks are stored as `.py` files in jupytext format.
Generate the `.ipynb` files after cloning or pulling, then start JupyterLab:

```bash
make sync-ipynb
uv run jupyter lab
```

The `.py` files also run directly, for example `uv run python notebooks/301_custom_fair_share_allocation.py`.
`make` is optional. Every target has a plain command in the [Makefile](https://github.com/setupelz/fair-shares/blob/main/Makefile).

[Which notebook do I start with?](user-guide/index.md) picks the notebook for your case.
IAM users start with notebook `400`.
