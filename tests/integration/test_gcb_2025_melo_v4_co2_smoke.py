"""End-to-end smoke test: equal per capita ``co2`` budget on ``gcb-2025`` + ``melo-2026-v4``.

``co2`` is ``gcb-2025`` fossil CO2 plus national-inventory LULUCF from the LULUCF
Data Hub v4.0.0. Reads the processed tree of that pipeline run and skips when it
has not been built::

    uv run snakemake --cores 1 --config emission_category=co2 \
        active_emissions_source=gcb-2025 active_gdp_source=wdi-2025 \
        active_population_source=un-owid-2025 active_gini_source=wdi-2025 \
        active_lulucf_source=melo-2026-v4 active_target_source=rcbs
"""

from __future__ import annotations

import pandas as pd
import pytest
from pyprojroot import here

from fair_shares.library.allocations.manager import run_allocation
from fair_shares.library.utils import ensure_string_year_columns
from fair_shares.library.utils.data.rcb import calculate_budget_from_rcb

PROCESSED = (
    here()
    / "output/gcb-2025_wdi-2025_un-owid-2025_wdi-2025_melo-2026-v4_rcbs_co2"
    / "intermediate/processed"
)
# The inventory LULUCF series starts in 2000, and so does world co2.
ALLOCATION_YEAR = 2000
EMISSIONS_INDEX = ["iso3c", "unit", "emission-category"]


def _read(name: str, index: list[str]) -> pd.DataFrame:
    return ensure_string_year_columns(pd.read_csv(PROCESSED / name).set_index(index))


@pytest.mark.parametrize("rcb_source", ["forster_2026", "ar6_wg1_2021"])
def test_shares_sum_to_one_and_budgets_sum_to_the_adjusted_total(rcb_source):
    if not (PROCESSED / "rcbs_co2.csv").is_file():
        pytest.skip("gcb-2025 + melo-2026-v4 co2 processed data not built")
    rcbs = pd.read_csv(PROCESSED / "rcbs_co2.csv")
    row = rcbs[(rcbs["source"] == rcb_source) & (rcbs["scenario"] == "1.7p50")]
    if row.empty:
        pytest.skip(f"{rcb_source} 1.7p50 is not in the processed budgets")

    population = _read("country_population_timeseries.csv", ["iso3c", "unit"])
    world = _read("world_emissions_co2_timeseries.csv", EMISSIONS_INDEX)
    fossil = _read("world_emissions_co2-ffi_timeseries.csv", EMISSIONS_INDEX)
    lulucf = _read("world_emissions_co2-lulucf_timeseries.csv", EMISSIONS_INDEX)

    # World co2 is fossil CO2 plus inventory LULUCF in every year it covers.
    years = list(world.columns)
    assert years[0] == str(ALLOCATION_YEAR)
    assert world[years].to_numpy() == pytest.approx(
        fossil[years].to_numpy() + lulucf[years].to_numpy()
    )

    result = run_allocation(
        "equal-per-capita-budget",
        population_ts=population,
        allocation_year=ALLOCATION_YEAR,
        emission_category="co2",
    )
    shares = result.relative_shares_cumulative_emission[str(ALLOCATION_YEAR)]
    assert shares.sum() == pytest.approx(1.0, abs=1e-9)

    # Adjusted total = world co2 2000-2019 + the budget rebased to 2020.
    budget_2020 = row["rcb_2020_nghgi_mt"].iloc[0]
    total = calculate_budget_from_rcb(
        budget_2020, ALLOCATION_YEAR, world, verbose=False
    )
    budget = pd.DataFrame({str(ALLOCATION_YEAR): [total]}, index=world.index)
    absolute = result.get_absolute_budgets(budget)[str(ALLOCATION_YEAR)]
    assert absolute.sum() == pytest.approx(total, rel=1e-9)
    assert total > budget_2020 > 0
    # A post-2020 baseline carries the observed inventory LULUCF of the rebase years.
    if row["baseline_year"].iloc[0] > 2020:
        assert row["rebase_lulucf_mt"].iloc[0] != 0
