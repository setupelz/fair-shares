# fair-shares

Python library for calculating shares of remaining carbon budgets and emission pathways, based on climate equity principles.
Documentation: **[setupelz.github.io/fair-shares](https://setupelz.github.io/fair-shares/)**.

## Getting started

Requires Python 3.11+, Git and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/setupelz/fair-shares.git
cd fair-shares
uv sync
uv run fair-shares fetch-data --pack   # this release's processed inputs, ready to run
make sync-ipynb                        # generate .ipynb files from the .py sources
uv run jupyter lab
```

The datapack covers every combination of the shipped data sources, targets and emission categories, so any allocation setting runs from it. It is CC BY-NC-SA 4.0.
To edit the pipeline, fetch the raw inputs instead with `uv run fair-shares fetch-data`; budget runs also need three files it cannot download.
[Install and data](https://setupelz.github.io/fair-shares/quickstart/) covers both routes, with download sizes, the conda route and a plain install from GitHub for the [Python API](https://setupelz.github.io/fair-shares/api/python-api/).

### Which notebook do I start with?

A *budget* is one cumulative number per country. A *pathway* is a value for every year.
*IAM model regions* are the world regions of an integrated assessment model, in IAMC-format files.

|                       | Countries                                    | IAM model regions                                     |
| --------------------- | -------------------------------------------- | ------------------------------------------------------ |
| **A budget**          | `302_example_templates_budget_allocations`   | run `400` once, then `402_example_iamc_budget_allocations`  |
| **A pathway**         | `303_example_templates_pathway_allocations`  | run `400` once, then `403_example_iamc_pathway_allocations` |
| **Your own settings** | `301_custom_fair_share_allocation`           | run `400` once, then `401_custom_iamc_allocation`          |
| **One region, model has no rest-of-world data** | | `405_one_region_remaining_budget` (no IAMC input needed) |
| **Reproduce a published study** | `601`, `602`, `604` and `605` (see [Reproductions](https://setupelz.github.io/fair-shares/reproductions/)) | |

Notebooks 401, 402 and 403 read the file that notebook 400 writes.

An allocation run writes to `output/<source-id>/allocations/<allocation_folder>/`: the results as parquet, `param_manifest.csv` with every parameter combination, `columns.csv` with the meaning and unit of every column, and `CITATIONS.md`.
Notebook 405 writes to `output/<OUTPUT_LABEL>/`, with the same `columns.csv` and a `columns` sheet in its IAMC files.
[Outputs](https://setupelz.github.io/fair-shares/user-guide/output-schema/) lists every file.

## Non-CO2 gases

A multi-gas result (`all-ghg`, `all-ghg-ex-co2-lulucf`) is a CO2 budget plus an annual non-CO2 pathway.
A budget depends on the methane pathway it assumes ([Weber et al. 2026](https://doi.org/10.1038/s43247-026-03832-1)), so each budget takes the median non-CO2 pathway of its temperature-matched set: the scenarios whose median warming at net zero lies within 0.05 °C of the budget's own temperature.
The set comes from the scenario database the budget was built on (`non_co2_basis` in `data/rcbs/rcbs.yaml`), which is AR6 for every shipped budget.
[Scenario sets](https://setupelz.github.io/fair-shares/science/scenario-sets/#scenario-sources) gives the scenario source of every term and why.

## Licence of results

The default emissions source, PRIMAP-hist v2.8, is CC BY-NC-SA 4.0.
Results from a default run are under its non-commercial, share-alike terms.
For CC BY results, set the emissions source to `primap-202503` or `gcb-2025`.
[Data and licences](https://setupelz.github.io/fair-shares/user-guide/data-sources/) gives the terms of every source.

## Known limitations

- With the default land-use source, the national-inventory LULUCF Data Hub (`melo-2026-v4`, from 2000), allocations with land-use CO2 (`co2`, `all-ghg`) start in 2000 or later. The bookkeeping source `gcb-2025-luc` (manual download, 1850 to 2024) allows earlier start years, on the model basis rather than the inventory basis.

## Citation

If you use fair-shares in academic work, policy documents or legal proceedings, please cite it.
[`CITATION.cff`](CITATION.cff) is the source of truth for the software citation:

```bibtex
@software{fair_shares,
  title={fair-shares: Python package for calculating fair shares of remaining carbon budgets and emission pathways},
  author={Pelz, Setu and Holz, Ceecee and Lamboll, Robin and Weber, Konstantin and Lewis, Jared and Nicholls, Zebedee},
  year={2026},
  version={0.7.0},
  url={https://github.com/setupelz/fair-shares},
  license={BSD-3-Clause}
}
```

Also cite the data. `uv run fair-shares cite` lists the software and every data source a run uses (`--bibtex` for BibTeX).
Every saved run writes the same list to `CITATIONS.md` in its output directory.

## License

[BSD-3-Clause](LICENSE). Free to use, modify and distribute with attribution. Modified versions cannot use the fair-shares name to endorse derivative works without permission.
