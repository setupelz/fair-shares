"""End-to-end smoke test: equal per capita budget on ``gcb-2025`` emissions.

Reads the processed tree of a ``gcb-2025`` + ``co2-ffi`` + ``rcbs`` pipeline run
and skips when it has not been built::

    uv run snakemake --cores 1 --config emission_category=co2-ffi \
        active_emissions_source=gcb-2025 active_gdp_source=wdi-2025 \
        active_population_source=un-owid-2025 active_gini_source=wdi-2025 \
        active_target_source=rcbs
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
    / "output/gcb-2025_wdi-2025_un-owid-2025_wdi-2025_rcbs_co2-ffi"
    / "intermediate/processed"
)
ALLOCATION_YEAR = 1990


def _read(name: str, index: list[str]) -> pd.DataFrame:
    return ensure_string_year_columns(pd.read_csv(PROCESSED / name).set_index(index))


@pytest.mark.parametrize("rcb_source", ["forster_2026", "ar6_wg1_2021"])
def test_shares_sum_to_one_and_budgets_sum_to_the_adjusted_total(rcb_source):
    if not (PROCESSED / "rcbs_co2-ffi.csv").is_file():
        pytest.skip("gcb-2025 processed data not built")
    rcbs = pd.read_csv(PROCESSED / "rcbs_co2-ffi.csv")
    row = rcbs[(rcbs["source"] == rcb_source) & (rcbs["scenario"] == "1.7p50")]
    if row.empty:
        pytest.skip(f"{rcb_source} 1.7p50 is not in the processed budgets")

    population = _read("country_population_timeseries.csv", ["iso3c", "unit"])
    world = _read(
        "world_emissions_co2-ffi_timeseries.csv",
        ["iso3c", "unit", "emission-category"],
    )
    result = run_allocation(
        "equal-per-capita-budget",
        population_ts=population,
        allocation_year=ALLOCATION_YEAR,
        emission_category="co2-ffi",
    )
    shares = result.relative_shares_cumulative_emission[str(ALLOCATION_YEAR)]
    assert shares.sum() == pytest.approx(1.0, abs=1e-9)

    # Adjusted total = world emissions 1990-2019 + the budget rebased to 2020.
    total = calculate_budget_from_rcb(
        row["rcb_2020_nghgi_mt"].iloc[0], ALLOCATION_YEAR, world, verbose=False
    )
    budget = pd.DataFrame({str(ALLOCATION_YEAR): [total]}, index=world.index)
    absolute = result.get_absolute_budgets(budget)[str(ALLOCATION_YEAR)]
    assert absolute.sum() == pytest.approx(total, rel=1e-9)
    assert total > row["rcb_2020_nghgi_mt"].iloc[0] > 0
