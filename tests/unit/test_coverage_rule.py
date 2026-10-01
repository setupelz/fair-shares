"""The opt-in coverage rule of an emissions source.

A source with a ``coverage`` block keeps a country in the analysis only if the
raw file records emissions before one year and population is complete from
another. A source without the block keeps the default membership.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.config.models import EmissionsDataParameters
from fair_shares.library.exceptions import DataLoadingError
from fair_shares.library.preprocessing import (
    FIRST_RECORDED_YEAR_FILENAME,
    compute_analysis_countries,
    coverage_exclusions,
    create_coverage_summary,
    source_coverage_exclusions,
)

YEARS = [str(y) for y in range(1850, 2001)]
COUNTRIES = ["AAA", "BBB", "CCC"]
ALL = set(COUNTRIES)
RULE = {"emissions_recorded_before": 1990, "population_from": 1850}
# AAA passes both tests. BBB is first recorded in 1992. CCC has population from 1950.
FIRST_RECORDED = pd.Series({"AAA": 1900, "BBB": 1992, "CCC": 1850})


def _frame(index_names: list[str], extra: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        1.0,
        index=pd.MultiIndex.from_tuples(
            [(c, *extra) for c in COUNTRIES], names=index_names
        ),
        columns=YEARS,
    )


def _population() -> pd.DataFrame:
    population = _frame(["iso3c", "unit"], ("million",))
    population.loc["CCC", [str(y) for y in range(1850, 1950)]] = None
    return population


def _inputs():
    emissions = _frame(["iso3c", "unit", "emission-category"], ("Mt", "co2-ffi"))
    gdp = _frame(["iso3c", "unit"], ("billion",))
    return {"co2-ffi": emissions}, gdp, _population()


def test_a_source_without_the_block_keeps_the_default_membership():
    assert coverage_exclusions(ALL, _population(), None, FIRST_RECORDED) == {}
    assert compute_analysis_countries(*_inputs()) == ALL


def test_each_failing_country_is_excluded_with_its_reason():
    excluded = coverage_exclusions(ALL, _population(), RULE, FIRST_RECORDED)
    assert excluded == {
        "BBB": "no emissions recorded before 1990",
        "CCC": "population incomplete from 1850",
    }
    countries = compute_analysis_countries(
        *_inputs(), coverage=RULE, first_recorded_year=FIRST_RECORDED
    )
    assert countries == {"AAA"}


def test_a_record_in_the_threshold_year_or_no_record_fails():
    first = pd.Series({"AAA": 1989, "BBB": 1990})
    rule = {"emissions_recorded_before": 1990}
    excluded = coverage_exclusions(ALL, _population(), rule, first)
    assert set(excluded) == {"BBB", "CCC"}
    with pytest.raises(DataLoadingError, match="first recorded year"):
        coverage_exclusions(ALL, _population(), rule)


def test_the_source_rule_reads_the_table_and_the_summary_names_the_reason(tmp_path):
    parameters = {"available_categories": ["co2-ffi"], "world_key": "WLD"}
    population = _population()
    assert source_coverage_exclusions(ALL, population, parameters, tmp_path) == {}

    # The rule passes through the config model that the pipeline dumps.
    parameters = EmissionsDataParameters(**parameters, coverage=RULE).model_dump()
    with pytest.raises(DataLoadingError, match="table not found"):
        source_coverage_exclusions(ALL, population, parameters, tmp_path)
    table = FIRST_RECORDED.rename("first_recorded_year").rename_axis("iso3c")
    table.reset_index().to_csv(
        tmp_path / FIRST_RECORDED_YEAR_FILENAME.format(category="co2-ffi"), index=False
    )
    excluded = source_coverage_exclusions(ALL, population, parameters, tmp_path)
    assert set(excluded) == {"BBB", "CCC"}

    emissions, gdp, population = _inputs()
    gini = pd.DataFrame(
        {"gini": [0.3]},
        index=pd.MultiIndex.from_tuples([("AAA", "unitless")], names=["iso3c", "unit"]),
    )
    mapping = pd.DataFrame({"iso3c": COUNTRIES})
    args = ({"AAA"}, emissions, gdp, population, gini, mapping, tmp_path)
    assert "coverage_rule_failed" not in create_coverage_summary(*args).columns
    summary = create_coverage_summary(*args, coverage_rule_failed=excluded)
    summary = summary.set_index("iso3c")
    assert summary["coverage_rule_failed"].to_dict() == {"AAA": "", **excluded}
    assert summary["in_row"].to_dict() == {"AAA": False, "BBB": True, "CCC": True}
