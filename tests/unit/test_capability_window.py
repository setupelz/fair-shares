"""Cumulative-window capability (``capability_window``).

The toy follows Pelz et al. (2025, PNAS, SI Eq. 2): one capability value per
country, cumulative GDP over cumulative population in a past window, with
F(x) = 1/sqrt(x) applied to cumulative population shares.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.allocations.budgets import per_capita_adjusted_budget
from fair_shares.library.allocations.pathways import per_capita_adjusted
from fair_shares.library.exceptions import ConfigurationError

YEARS = list(range(1990, 2051))
OBSERVED = [y for y in YEARS if y <= 2022]
POP_A = np.linspace(100, 120, len(YEARS))
POP_B = np.linspace(50, 150, len(YEARS))
GDPPC_A = np.linspace(1, 4, len(YEARS))
GDPPC_B = np.full(len(YEARS), 2.0)
INDEX = pd.MultiIndex.from_tuples(
    [("AAA", "million"), ("BBB", "million")], names=["iso3c", "unit"]
)


def _frame(rows, years):
    cols = [str(y) for y in years]
    keep = [YEARS.index(y) for y in years]
    return pd.DataFrame([np.asarray(r)[keep] for r in rows], columns=cols, index=INDEX)


POPULATION = _frame([POP_A, POP_B], YEARS)
GDP = _frame([GDPPC_A * POP_A, GDPPC_B * POP_B], OBSERVED)
COMMON = dict(
    population_ts=POPULATION,
    allocation_year=1990,
    emission_category="co2-ffi",
    gdp_ts=GDP,
    capability_weight=1.0,
    capability_exponent=0.5,
    capability_functional_form="power",
    cumulative_end_year=2050,
)


def _shares(**kwargs):
    result = per_capita_adjusted_budget(**{**COMMON, **kwargs})
    return result.relative_shares_cumulative_emission.iloc[:, 0].to_numpy()


def test_pnas_toy_reproduces_eq2():
    obs = np.array([y <= 2022 for y in YEARS])
    capability = np.array(
        [
            (GDPPC_A * POP_A)[obs].sum() / POP_A[obs].sum(),
            (GDPPC_B * POP_B)[obs].sum() / POP_B[obs].sum(),
        ]
    )
    weights = capability**-0.5 * np.array([POP_A.sum(), POP_B.sum()])
    expected = weights / weights.sum()

    observed = _shares(capability_window=(1990, 2022))

    np.testing.assert_allclose(observed, expected, rtol=1e-10)
    np.testing.assert_allclose(observed, [0.536, 0.464], atol=5e-4)


@pytest.mark.parametrize("year", [1990, 2010, 2022])
def test_one_year_window_equals_snapshot(year):
    window = _shares(capability_window=(year, year))
    snapshot = _shares(capability_reference_year=year)
    np.testing.assert_allclose(window, snapshot, rtol=1e-12)

    pathway_kwargs = dict(
        population_ts=POPULATION,
        first_allocation_year=2000,
        emission_category="co2-ffi",
        gdp_ts=GDP,
        capability_weight=1.0,
        capability_exponent=0.5,
        capability_functional_form="power",
    )
    pw_window = per_capita_adjusted(**pathway_kwargs, capability_window=[year, year])
    pw_snapshot = per_capita_adjusted(**pathway_kwargs, capability_reference_year=year)
    pd.testing.assert_frame_equal(
        pw_window.relative_shares_pathway_emissions,
        pw_snapshot.relative_shares_pathway_emissions,
    )


def test_both_capability_modes_raise():
    with pytest.raises(ConfigurationError, match="mutually exclusive"):
        _shares(capability_window=(1990, 2022), capability_reference_year=2022)
