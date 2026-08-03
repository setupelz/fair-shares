# fair-shares

Python library for calculating shares of remaining carbon budgets and emission pathways, based on climate equity principles. See [Approach Catalog](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/) for the available approaches.

## Getting Started

Requires Python 3.11+, Git, and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/setupelz/fair-shares.git
cd fair-shares
uv sync
make sync-ipynb   # generate .ipynb files from .py sources (requires make)
uv run jupyter lab
```

> **No `make`?** Run the commands directly: `uv run jupytext --sync notebooks/*.py && uv run jupytext --set-formats ipynb,py:percent notebooks/*.py`

Notebooks are stored as plain `.py` files (jupytext format) for clean version control. The `sync-ipynb` step generates the `.ipynb` files for interactive use in JupyterLab. You can also run the `.py` files directly.

### Which notebook do I start with?

**What are you dividing up?** A *budget* is one cumulative number per country —
"how much may this country emit in total from now on". A *pathway* is a value
for every year — "how much may it emit in 2030, in 2031, and so on".

**Who are you dividing it between?** Individual *countries*, or the *model
regions* used by an integrated assessment model (a handful of world regions such
as "Western Europe", in IAMC-format files).

|                       | Countries                                    | IAM model regions                                     |
| --------------------- | -------------------------------------------- | ------------------------------------------------------ |
| **A budget**          | `302_example_templates_budget_allocations`   | run `400` once, then `402_example_iamc_budget_allocations`  |
| **A pathway**         | `303_example_templates_pathway_allocations`  | run `400` once, then `403_example_iamc_pathway_allocations` |
| **Your own settings** | `301_custom_fair_share_allocation`           | run `400` once, then `401_custom_iamc_allocation`          |

The 302/303/402/403 notebooks are worked examples you can run unchanged. The 301
and 401 notebooks are the blank workspaces you configure yourself; 401 also
exports a model-ready remaining budget.

**IAM users: notebook 400 is the starting point.** It reads a raw scenario file, adds
the historical emissions, population and GDP that the allocation needs, and
writes `output/iamc/iamc_covered.xlsx`. Notebooks 401, 402 and 403 all read that
file and will fail with a missing-file error if you have not run 400 first.

Only want to call the allocation functions from your own Python code, with your
own data? You do not need the notebooks at all — see
[Python API](https://setupelz.github.io/fair-shares/api/python-api/).

### Input data

Most inputs are third-party datasets obtained from their original publishers
rather than authored here. We provide a command that downloads them from pinned URLs:

```bash
uv run fair-shares fetch-data          # everything a standard run needs (~70 MB)
uv run fair-shares fetch-data --all    # plus the large optional sources (~90 MB more)
uv run fair-shares fetch-data --list   # every source: version, size, licence, citation
uv run fair-shares fetch-data --verify # re-hash what is present, download nothing
```

Run inside a clone, files land in the checkout's own `data/`. Run from an
installed wheel outside a checkout, they land in your platform's user data
directory instead — or wherever `FAIR_SHARES_DATA_DIR` points. A missing input
is also fetched automatically the first time something needs it; set
`FAIR_SHARES_AUTO_FETCH=0` to turn that off for offline or CI runs.

A checksum mismatch stops the run instead of warning. Two
sources are exceptions by nature: the World Bank and Our World in Data
regenerate their exports in place with no version identifier, so those are
reported as vintage drift instead of failing, and the hash you actually got is
recorded in the generated `PROVENANCE.md`.

**Global Carbon Budget bunkers data must be downloaded by hand** — it sits
behind a licence-acceptance page that cannot be automated. Run
`uv run fair-shares fetch-data --source gcb-2024` for step-by-step instructions,
then `--verify` to confirm the file you dropped in is the right one.

Every source's licence, version and citation lives in
`src/fair_shares/conf/data_registry.yaml` and is written into `PROVENANCE.md`
after a fetch. Several inputs are CC BY and require attribution in anything
derived from them; some are not redistributable at all. Check `--list` before
republishing any of it.

### Using the library without the notebooks

`uv sync` above installs the full contributor toolchain — Snakemake, JupyterLab
and the test runner. A plain install gets none of that:

```bash
pip install fair-shares
```

That is enough for the allocation functions themselves. They take population and
GDP as pandas dataframes and hand back a result object, so they touch no files
and need no data directory — see
[Python API](https://setupelz.github.io/fair-shares/api/python-api/) for a
worked example.

The higher-level entry points do read files. Point them at your data with two
environment variables, or pass `data_dir=` and `output_dir=` directly:

```bash
export FAIR_SHARES_DATA_DIR=/path/to/data
export FAIR_SHARES_OUTPUT_DIR=/path/to/output
```

If the processed data they want is not there yet, they rebuild it with Snakemake,
which is not in a plain install. Either point them at a data tree somebody has
already built, or add the extra: `pip install "fair-shares[pipeline]"`.

## Documentation

**[setupelz.github.io/fair-shares](https://setupelz.github.io/fair-shares/)**

- [Quick Start](https://setupelz.github.io/fair-shares/quickstart/) -- install and run your first allocation
- [Approach Catalog](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/) -- all 10 approaches at a glance
- [Science](https://setupelz.github.io/fair-shares/science/) -- equity concepts, allocation design, references
- [Developer Guide](https://setupelz.github.io/fair-shares/dev-guide/) -- architecture, adding approaches, contributing

## Known Limitations

- **Pre-2000 LULUCF data**: Allocations that include LULUCF (emission category `co2`) are currently restricted to start years of 2000 or later. NGHGI-reported LULUCF data (Melo et al. v3.1) is only available from 2000. We are working with scientific collaborators to assess the quality of pre-2000 estimates and expect to extend coverage in a future release.
- **Non-CO₂ pathways**: The all-GHG allocation currently derives non-CO₂ pathways from AR6 scenario medians. Custom CH₄ mitigation pathways (e.g., for different CH₄ reduction targets) are architecturally supported but not yet available as a user-facing option - this is also being actively pursued.

## Citation

If you use fair-shares in academic work, policy documents, or legal proceedings, please cite it:

```bibtex
@software{fair_shares,
  title={fair-shares: Python package for calculating fair shares of remaining carbon budgets and emission pathways},
  author={Pelz, Setu and Holz, Ceecee and Lamboll, Robin and Weber, Konstantin and Lewis, Jared and Nicholls, Zebedee},
  year={2025},
  url={https://github.com/setupelz/fair-shares},
  license={BSD-3-Clause}
}
```

**Also cite the data.** Most inputs are third-party datasets that require
attribution, and which ones a run uses depends on its settings. To see the list:

```bash
uv run fair-shares cite            # software plus every data source, as text
uv run fair-shares cite --bibtex   # the same as BibTeX entries
```

Every saved run also writes a `CITATIONS.md` into its output directory, listing
the software and exactly the sources that run used, with DOIs, licences, and any
terms that ask for more than attribution.

## License

[BSD-3-Clause](LICENSE). Free to use, modify, and distribute with attribution. Modified versions cannot use the fair-shares name to endorse derivative works without permission.
