# fair-shares

Python library for calculating shares of remaining carbon budgets and emission pathways, based on climate equity principles.
Documentation: **[setupelz.github.io/fair-shares](https://setupelz.github.io/fair-shares/)**.

## Getting started

Requires Python 3.11+, Git and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/setupelz/fair-shares.git
cd fair-shares
uv sync
uv run fair-shares fetch-data   # third-party input data, from pinned URLs
make sync-ipynb                 # generate .ipynb files from the .py sources
uv run jupyter lab
```

Budget runs also need three files that `fetch-data` cannot download.
[Install and data](https://setupelz.github.io/fair-shares/quickstart/) lists them, with download sizes, the conda route and a plain install from GitHub for the [Python API](https://setupelz.github.io/fair-shares/api/python-api/).

### Which notebook do I start with?

A *budget* is one cumulative number per country. A *pathway* is a value for every year.
*IAM model regions* are the world regions of an integrated assessment model, in IAMC-format files.

|                       | Countries                                    | IAM model regions                                     |
| --------------------- | -------------------------------------------- | ------------------------------------------------------ |
| **A budget**          | `302_example_templates_budget_allocations`   | run `400` once, then `402_example_iamc_budget_allocations`  |
| **A pathway**         | `303_example_templates_pathway_allocations`  | run `400` once, then `403_example_iamc_pathway_allocations` |
| **Your own settings** | `301_custom_fair_share_allocation`           | run `400` once, then `401_custom_iamc_allocation`          |
| **One region, model has no rest-of-world data** | | `405_one_region_remaining_budget` (no IAMC input needed) |
| **Reproduce a published study** | `601` to `605` (see [Reproductions](https://setupelz.github.io/fair-shares/reproductions/)) | |

Notebooks 401, 402 and 403 read the file that notebook 400 writes.

## Licence of results

The default emissions source, PRIMAP-hist v2.8, is CC BY-NC-SA 4.0.
Results from a default run carry its non-commercial, share-alike terms.
For CC BY results, set the emissions source to `primap-202503` or `gcb-2025`.
[Data and licences](https://setupelz.github.io/fair-shares/user-guide/data-sources/) gives the terms of every source.

## Known limitations

- Allocations with land-use CO2 (`co2`, `all-ghg`) start in 2000 or later, because national-inventory land-use data start in 2000.
- The non-CO2 pathway of each budget is the median of its temperature-matched AR6 scenarios. A custom methane pathway needs a matching budget ([Weber et al. 2026](https://doi.org/10.1038/s43247-026-03832-1)). A user-facing option is planned.

## Citation

If you use fair-shares in academic work, policy documents or legal proceedings, please cite it.
[`CITATION.cff`](CITATION.cff) is the source of truth for the software citation:

```bibtex
@software{fair_shares,
  title={fair-shares: Python package for calculating fair shares of remaining carbon budgets and emission pathways},
  author={Pelz, Setu and Holz, Ceecee and Lamboll, Robin and Weber, Konstantin and Lewis, Jared and Nicholls, Zebedee},
  year={2026},
  version={0.6.0},
  url={https://github.com/setupelz/fair-shares},
  license={BSD-3-Clause}
}
```

Also cite the data. `uv run fair-shares cite` lists the software and every data source a run uses (`--bibtex` for BibTeX).
Every saved run writes the same list to `CITATIONS.md` in its output directory.

## License

[BSD-3-Clause](LICENSE). Free to use, modify and distribute with attribution. Modified versions cannot use the fair-shares name to endorse derivative works without permission.
