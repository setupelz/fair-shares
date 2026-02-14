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

| Workflow                  | Notebook                                 |
| ------------------------- | ---------------------------------------- |
| country-fair-shares       | `301_custom_fair_share_allocation.ipynb` |
| iamc-regional-fair-shares | `401_custom_iamc_allocation.ipynb`       |

Start with country-fair-shares unless you're working with integrated assessment models.

## Documentation

**[setupelz.github.io/fair-shares](https://setupelz.github.io/fair-shares/)**

- [Quick Start](https://setupelz.github.io/fair-shares/quickstart/) -- install and run your first allocation
- [Approach Catalog](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/) -- all 10 approaches at a glance
- [Science](https://setupelz.github.io/fair-shares/science/) -- equity concepts, allocation design, references
- [Developer Guide](https://setupelz.github.io/fair-shares/dev-guide/) -- architecture, adding approaches, contributing

## Citation

If you use fair-shares in academic work, policy documents, or legal proceedings, please cite it:

```bibtex
@software{fair_shares,
  title={fair-shares: Python package for calculating fair shares of remaining carbon budgets and emission pathways},
  author={Pelz, Setu and Holz, Ceecee and Lewis, Jared and Nicholls, Zebedee},
  year={2025},
  url={https://github.com/setupelz/fair-shares},
  license={BSD-3-Clause}
}
```

## License

[BSD-3-Clause](LICENSE). Free to use, modify, and distribute with attribution. Modified versions cannot use the fair-shares name to endorse derivative works without permission.
