"""Tests for sector-to-top-level aggregation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.iamc_historical.aggregation import (
    aggregate_sectoral_to_top_level,
    classify_scenario_variables,
    supported_top_level_variables,
)
from fair_shares.library.iamc_historical.sources import load_historical

FIXTURES = Path(__file__).parent / "fixtures"


def _history_from_fixture() -> pd.DataFrame:
    return load_historical(FIXTURES / "tiny_history.csv")


def test_supported_top_level_list_covers_standard_gases() -> None:
    supported = set(supported_top_level_variables())
    assert "Emissions|CO2|Energy and Industrial Processes" in supported
    assert "Emissions|CH4" in supported
    assert "Emissions|N2O" in supported
    # LUC and F-gases should not be in the producible list
    assert "Emissions|CO2|AFOLU" not in supported
    assert "Emissions|HFC|HFC134a" not in supported


def test_co2_eip_excludes_agriculture_and_aircraft() -> None:
    hist = _history_from_fixture()
    out = aggregate_sectoral_to_top_level(
        hist, variables=["Emissions|CO2|Energy and Industrial Processes"]
    )
    bra_2000 = out[(out["region"] == "bra")].set_index("variable")[2000].iloc[0]
    # bra: Energy 150 + Industrial 30 + (Agriculture 5 excluded) + (Aircraft 0 excluded) = 180
    assert bra_2000 == 180
    usa_1990 = out[(out["region"] == "usa")].set_index("variable")[1990].iloc[0]
    # usa: Energy 4000 + Industrial 600 = 4600 (agriculture 20 excluded)
    assert usa_1990 == 4600


def test_ch4_includes_agriculture() -> None:
    hist = _history_from_fixture()
    out = aggregate_sectoral_to_top_level(hist, variables=["Emissions|CH4"])
    bra_1990 = out[out["region"] == "bra"].set_index("variable")[1990].iloc[0]
    # bra: Energy 2 + Agriculture 10 = 12
    assert bra_1990 == 12


def test_unsupported_variable_raises() -> None:
    hist = _history_from_fixture()
    with pytest.raises(DataProcessingError, match="Unsupported top-level variables"):
        aggregate_sectoral_to_top_level(hist, variables=["Emissions|CO2|AFOLU"])


def test_classify_sorts_buckets() -> None:
    out = classify_scenario_variables(
        [
            "Emissions|CO2|Energy and Industrial Processes",
            "Emissions|CH4",
            "Emissions|CO2|AFOLU",
            "Emissions|HFC|HFC134a",
            "Emissions|UnicornDust",
        ]
    )
    assert out["producible_ceds"] == sorted(
        ["Emissions|CO2|Energy and Industrial Processes", "Emissions|CH4"]
    )
    assert out["global_only"] == []
    # AFOLU and F-gases are not producible by this adapter; they fall into unknown.
    assert sorted(out["unknown"]) == sorted(
        [
            "Emissions|CO2|AFOLU",
            "Emissions|HFC|HFC134a",
            "Emissions|UnicornDust",
        ]
    )
    assert "producible_synthetic" not in out
