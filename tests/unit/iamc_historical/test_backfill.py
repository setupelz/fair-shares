"""Tests for the public :func:`backfill` entry point."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyam
import pytest

from fair_shares.library.exceptions import (
    ConfigurationError,
    DataProcessingError,
)
from fair_shares.library.iamc_historical import RegionMapping, backfill

from .conftest import build_iamc_scenario

FIXTURES = Path(__file__).parent / "fixtures"

_DEFAULT_EMISSIONS_VARS = (
    ("Emissions|CO2|Energy and Industrial Processes", "Mt CO2/yr"),
    ("Emissions|CH4", "Mt CH4/yr"),
)


def _mapping() -> RegionMapping:
    return RegionMapping.from_nomenclature_yaml(FIXTURES / "tiny_regions.yml")


def _scenario(
    *,
    start_year: int = 2010,
    end_year: int = 2020,
    regions: tuple[str, ...] = ("TINY 1.0|BRA-only", "TINY 1.0|IND-USA"),
    variables: tuple[tuple[str, str], ...] = _DEFAULT_EMISSIONS_VARS,
    value: float = 99.0,
) -> pyam.IamDataFrame:
    return build_iamc_scenario(
        variables=variables,
        regions=regions,
        start_year=start_year,
        end_year=end_year,
        value=value,
    )


def test_happy_path_concatenates_history_before_scenario() -> None:
    scen = _scenario(start_year=2010, end_year=2020)
    filled = backfill(
        scen,
        region_mapping=_mapping(),
        start_year=1990,
        history_path=FIXTURES / "tiny_history.csv",
        check_continuity=False,
    )
    years = sorted(filled.year)
    assert min(years) == 1990
    assert max(years) == 2020
    # Pre-join years exist only in history, post-join only in scenario
    df = filled.data
    pre_join_models = set(df[df["year"] < 2010]["model"])
    assert len(pre_join_models) == 1
    pre_label = next(iter(pre_join_models))
    assert "2025.12.07" in pre_label
    assert set(df[df["year"] >= 2010]["model"]) == {"TINY 1.0"}
    # The Brazil CO2 EIP value at 2000 should be Energy 150 + Industrial 30 = 180
    bra_co2_2000 = df[
        (df["region"] == "TINY 1.0|BRA-only")
        & (df["variable"] == "Emissions|CO2|Energy and Industrial Processes")
        & (df["year"] == 2000)
    ]["value"].iloc[0]
    assert bra_co2_2000 == 180.0


def test_noop_when_scenario_starts_at_start_year(
    caplog: pytest.LogCaptureFixture,
) -> None:
    scen = _scenario(start_year=1990, end_year=2020)
    with caplog.at_level("INFO"):
        filled = backfill(
            scen,
            region_mapping=_mapping(),
            start_year=1990,
            history_path=FIXTURES / "tiny_history.csv",
        )
    assert sorted(filled.year) == sorted(scen.year)
    assert "nothing to back-fill" in caplog.text.lower()


def test_unsupported_variable_passes_through(
    caplog: pytest.LogCaptureFixture,
) -> None:
    scen = _scenario(
        variables=(
            ("Emissions|CO2|Energy and Industrial Processes", "Mt CO2/yr"),
            ("Emissions|UnicornDust", "Mt Unicorn/yr"),
        ),
    )
    with caplog.at_level("WARNING"):
        filled = backfill(
            scen,
            region_mapping=_mapping(),
            start_year=1990,
            history_path=FIXTURES / "tiny_history.csv",
            check_continuity=False,
        )
    # Unicorn variable present in scenario years unchanged, not in history
    df = filled.data
    unicorn = df[df["variable"] == "Emissions|UnicornDust"]
    assert set(unicorn["year"]) == set(range(2010, 2021))
    assert "UnicornDust" in caplog.text


def test_return_parts_tuple_contract() -> None:
    scen = _scenario(start_year=2010, end_year=2015)
    history_idf, scenario_idf = backfill(
        scen,
        region_mapping=_mapping(),
        start_year=1990,
        history_path=FIXTURES / "tiny_history.csv",
        check_continuity=False,
        return_parts=True,
    )
    assert isinstance(history_idf, pyam.IamDataFrame)
    assert isinstance(scenario_idf, pyam.IamDataFrame)
    assert max(history_idf.year) <= 2009
    assert min(scenario_idf.year) == 2010


def test_missing_mapping_raises_with_guidance() -> None:
    scen = _scenario()
    with pytest.raises(ConfigurationError, match="region_mapping"):
        backfill(
            scen,
            model="Bogus Model 9.9",
            start_year=1990,
            history_path=FIXTURES / "tiny_history.csv",
        )


def test_missing_region_above_threshold_raises() -> None:
    # Scenario has a region (Atlantis) not in mapping, carrying all of the
    # emissions at the join year. Threshold default 5%, so this must raise.
    rows = [
        {
            "model": "TINY 1.0",
            "scenario": "dummy",
            "region": "TINY 1.0|Atlantis",
            "variable": "Emissions|CO2|Energy and Industrial Processes",
            "unit": "Mt CO2/yr",
            "year": y,
            "value": 100.0,
        }
        for y in range(2010, 2016)
    ]
    scen = pyam.IamDataFrame(pd.DataFrame(rows))
    with pytest.raises(DataProcessingError, match="missing from mapping"):
        backfill(
            scen,
            region_mapping=_mapping(),
            start_year=1990,
            history_path=FIXTURES / "tiny_history.csv",
            check_continuity=False,
        )


def test_continuity_warning_fires_on_big_disagreement(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # The history puts Brazil CO2 EIP at 200 in 2010. Scenario says 50 —
    # that's a 75% delta, well above the 10% default.
    scen = _scenario(
        start_year=2010,
        end_year=2015,
        regions=("TINY 1.0|BRA-only",),
        variables=(("Emissions|CO2|Energy and Industrial Processes", "Mt CO2/yr"),),
        value=50.0,
    )
    with caplog.at_level("WARNING"):
        backfill(
            scen,
            region_mapping=_mapping(),
            start_year=1990,
            history_path=FIXTURES / "tiny_history.csv",
            check_continuity=True,
        )
    assert "Continuity" in caplog.text
    assert "BRA-only" in caplog.text
