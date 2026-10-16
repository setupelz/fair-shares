---
title: Reproductions
description: Notebooks that reproduce published fair-share studies with the library
---

# Reproductions

Each notebook in the 600 series reproduces one published study with the library.
It extracts the study's method, maps each approach to library settings and runs it on the library's data.
Run a notebook from the repository root, for example `uv run python notebooks/602_reproduce_dekker_2025.py`.

| Notebook | Study | What it reproduces | Accuracy |
| --- | --- | --- | --- |
| [`601_reproduce_esabcc_2023`](https://github.com/setupelz/fair-shares/blob/main/notebooks/601_reproduce_esabcc_2023.py) | [ESABCC 2023](https://doi.org/10.2800/609405); [Pelz 2023](https://pure.iiasa.ac.at/18830) | Equal per capita, equal cumulative per capita, responsibility and capability budgets for the EU27, from 1990 and 2015 | EU27 shares within -0.41 to 0 pp for equal per capita and equal cumulative per capita. Responsibility differs by up to -1.76 pp, because the library allocates to countries and sums them ([details](esabcc-2023.md)) |
| [`602_reproduce_dekker_2025`](https://github.com/setupelz/fair-shares/blob/main/notebooks/602_reproduce_dekker_2025.py) | [Dekker 2025](https://doi.org/10.1038/s41558-025-02361-7) | Grandfathering, immediate per capita, per capita convergence, equal cumulative per capita, ability to pay and Greenhouse Development Rights pathways | Expressed in library terms; input differences listed in the notebook |
| [`604_reproduce_vandenberg_2020`](https://github.com/setupelz/fair-shares/blob/main/notebooks/604_reproduce_vandenberg_2020.py) | [Van den Berg 2020](https://doi.org/10.1007/s10584-019-02368-y) | Grandfathering, immediate equal per capita, per capita convergence, equal cumulative per capita, ability to pay and Greenhouse Development Rights pathways, with a cost-optimal reference | Expressed in library terms; input differences listed in the notebook |
| [`605_reproduce_matthews_2016`](https://github.com/setupelz/fair-shares/blob/main/notebooks/605_reproduce_matthews_2016.py) | [Matthews 2016](https://doi.org/10.1038/NCLIMATE2774); [Gignac 2015](https://doi.org/10.1088/1748-9326/10/7/075004) | National carbon debts and the equal per capita budget allocation | Expressed in library terms; input differences listed in the notebook |

The studies use other emissions data, scopes and population vintages than the library defaults.
Published numbers and library results therefore differ even where the method matches.
Each notebook ends with a list of these differences.

The full citations are on the [References](../science/references.md) page.
