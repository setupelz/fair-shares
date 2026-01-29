# fair-shares

A Python package for calculating country-level fair shares of remaining carbon budgets and emission pathways based on climate equity principles.

## What It Does

Imagine countries need to allocate remaining global carbon budgets. How should they be shared? If divided equally per person? If accounting for historical emissions? If adjusted by economic capacity? fair-shares calculates these allocations using different equity-grounded approaches, making value judgments transparent rather than hidden.

The tool supports **budget allocations** (cumulative emission budgets) and **pathway allocations** (annual emission trajectories over time). It's designed for researchers, policy analysts, and modelers exploring how climate mitigation can be distributed equitably.

## Workflows

fair-shares is used through Jupyter notebooks. **Choose based on your data:**

| You have...                | Use this workflow         | Notebook                                 |
| -------------------------- | ------------------------- | ---------------------------------------- |
| Individual country targets | country-fair-shares       | `301_custom_fair_share_allocation.ipynb` |
| IAMC scenario data         | iamc-regional-fair-shares | `401_iamc_fair_share_allocation.ipynb`   |

**Start with country-fair-shares** unless you're working with integrated assessment models.

## Overview

fair-shares distributes global emissions budgets and pathways among countries using allocation approaches grounded in climate equity principles, including equal per capita entitlements, historical responsibility, and capability-based differentiation. For theoretical foundations, see [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/).

### Allocation Approaches

Approaches operationalize climate equity principles—equal rights to atmosphere, historical responsibility, economic capacity—through different parameter configurations. All approaches ensure global allocations sum to 100%.

**Budget Allocations** (for remaining carbon budget targets):

- `equal-per-capita-budget` — Each person globally gets equal share
- `per-capita-adjusted-budget` — Adjusted for historical emissions and/or economic capacity
- `per-capita-adjusted-gini-budget` — Further adjusted for within-country inequality

**Pathway Allocations** (for scenario-based targets):

- `equal-per-capita` — Equal share per person per year
- `per-capita-adjusted` — Adjusted for responsibility and capacity
- `cumulative-per-capita-convergence` — Smooth transition to equal per capita over time

See [Allocation Approaches](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/) for theoretical foundations and when to use each approach.

## Documentation

Full documentation is available at [https://setupelz.github.io/fair-shares/](https://setupelz.github.io/fair-shares/)

### User Resources

- [Quick Start](https://setupelz.github.io/fair-shares/quickstart/)
- [User Guide](https://setupelz.github.io/fair-shares/user-guide/)
- [Approach Catalog](https://setupelz.github.io/fair-shares/user-guide/approach-catalog/)

### Scientific Documentation

- [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)
- [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/)
- [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/)

### Development Resources

- [Developer Guide](https://setupelz.github.io/fair-shares/dev-guide/)
- [Adding Data Sources](https://setupelz.github.io/fair-shares/dev-guide/adding-data-sources/)
- [Adding Approaches](https://setupelz.github.io/fair-shares/dev-guide/adding-approaches/)
- [Contributing Guide](https://setupelz.github.io/fair-shares/CONTRIBUTING/)

## License

fair-shares is licensed under the [BSD-3-Clause License](LICENSE).

**Key points:**

- ✅ Free to use, modify, and distribute
- ✅ Attribution required (keep copyright notice and license)
- ✅ Modified versions cannot use the fair-shares name to endorse derivative works without permission
- ✅ Contributors retain copyright on their contributions

See [LICENSE](LICENSE) for full details. Contributors are acknowledged in CITATION.cff and release notes.

## Citation

**If you use fair-shares in legal proceedings, policy documents, or academic work, please cite it.**

GitHub will automatically format the citation for you using the "Cite this repository" button, or use:

```bibtex
@software{fair_shares,
  title={fair-shares: Python package for calculating fair shares of remaining carbon budgets and emission pathways},
  author={Pelz, Setu and Holz, Ceecee and Lewis, Jared and Nicholls, Zebedee},
  year={2025},
  url={https://github.com/setupelz/fair-shares},
  license={BSD-3-Clause}
}
```

**Important for derivative works:** If you modify fair-shares to add allocation approaches not in the original, you must clearly state that your version is modified and is not endorsed by the original fair-shares contributors (see BSD-3-Clause License, Clause 3).
