"""The ``gcb-2025`` coverage rule on a real pipeline run, with start years from 1850.

``gcb-2025`` keeps a country in the analysis only if the raw file records
emissions before 1990 and population is complete from 1850. Reads the tree of
a ``gcb-2025`` + ``co2-ffi`` + ``rcbs`` pipeline run and skips when it has not
been built (command in ``test_gcb_2025_smoke.py``).
"""

from __future__ import annotations

import pandas as pd
import pytest
import yaml
from pyprojroot import here

from fair_shares.library.allocations.budgets.per_capita import (
    equal_per_capita_budget,
    per_capita_adjusted_budget,
)
from fair_shares.library.notebook_helpers import load_allocation_data
from fair_shares.library.utils import ensure_string_year_columns

RUN = here() / "output/gcb-2025_wdi-2025_un-owid-2025_wdi-2025_rcbs_co2-ffi"
PROCESSED = RUN / "intermediate/processed"
NO_RECORD_BEFORE_1990 = {"AND", "FSM", "LSO", "MHL", "NAM", "PLW", "TLS", "TUV"}
NO_POPULATION_FROM_1850 = {"MAC"}


@pytest.fixture(scope="module")
def data() -> dict:
    if not (PROCESSED / "rcbs_co2-ffi.csv").is_file():
        pytest.skip("gcb-2025 processed data not built")
    return load_allocation_data(PROCESSED, "rcbs", ["co2-ffi"], "co2-ffi")


def _world_row(folder: str, name: str, world_key: str) -> pd.Series:
    frame = pd.read_csv(RUN / "intermediate" / folder / name).set_index("iso3c")
    frame = ensure_string_year_columns(frame)
    return frame.loc[world_key]


def test_the_nine_countries_are_in_rest_of_world_and_totals_close(data):
    summary = pd.read_csv(PROCESSED / "country_data_coverage_summary.csv")
    summary = summary.set_index("iso3c").fillna({"coverage_rule_failed": ""})
    # A country that the rule alone moves has complete data under the default check.
    complete = summary["has_emissions"] & summary["has_gdp"] & summary["has_population"]
    moved = summary[complete & (summary["coverage_rule_failed"] != "")]
    assert set(moved.index) == NO_RECORD_BEFORE_1990 | NO_POPULATION_FROM_1850
    assert moved["in_row"].all()
    reasons = moved["coverage_rule_failed"]
    assert set(reasons[sorted(NO_RECORD_BEFORE_1990)]) == {
        "no emissions recorded before 1990"
    }
    assert reasons["MAC"] == "population incomplete from 1850"
    assert summary["in_analysis"].sum() == 168

    emissions = data["emissions_data"]["co2-ffi"]
    population = data["country_population_df"]
    gdp = data["country_gdp_df"]
    analysis = set(summary.index[summary["in_analysis"]]) | {"ROW"}
    for frame in (emissions, population, gdp):
        assert set(frame.index.get_level_values("iso3c")) == analysis
        assert not frame.isna().any().any()

    # Countries + rest-of-world = world row, for every year of each dataset.
    with open(RUN / "config.yaml") as f:
        config = yaml.safe_load(f)
    gdp_key = config["gdp"]["wdi-2025"]["data_parameters"]["world_key"]
    population_key = config["population"]["un-owid-2025"]["data_parameters"][
        "historical_world_key"
    ]
    world_emissions = data["world_emissions_data"]["co2-ffi"].iloc[0]
    world_population = _world_row(
        "population", "population_timeseries.csv", population_key
    )
    world_gdp = _world_row("gdp", "gdp_timeseries.csv", gdp_key)
    for frame, world in (
        (emissions, world_emissions),
        (population, world_population),
        (gdp, world_gdp),
    ):
        total = frame.sum()
        assert total.to_numpy() == pytest.approx(
            world[total.index].to_numpy(dtype=float), rel=1e-9
        )


@pytest.mark.parametrize("per_capita", [False, True])
def test_responsibility_from_1850_gives_complete_shares(data, per_capita):
    result = per_capita_adjusted_budget(
        population_ts=data["country_population_df"],
        country_actual_emissions_ts=data["emissions_data"]["co2-ffi"],
        allocation_year=1990,
        emission_category="co2-ffi",
        pre_allocation_responsibility_weight=1.0,
        capability_weight=0.0,
        pre_allocation_responsibility_year=1850,
        pre_allocation_responsibility_per_capita=per_capita,
    )
    shares = result.relative_shares_cumulative_emission["1990"]
    assert len(shares) == 169
    assert not shares.isna().any()
    assert shares.sum() == pytest.approx(1.0, abs=1e-9)


def test_fixed_1850_population_shares_are_complete(data):
    result = equal_per_capita_budget(
        population_ts=data["country_population_df"],
        allocation_year=1850,
        emission_category="co2-ffi",
        preserve_allocation_year_shares=True,
    )
    shares = result.relative_shares_cumulative_emission["1850"]
    assert len(shares) == 169
    assert not shares.isna().any()
    assert shares.sum() == pytest.approx(1.0, abs=1e-9)
