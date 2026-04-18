"""Tests for :mod:`fair_shares.library.iamc_historical.region_mapping`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError
from fair_shares.library.iamc_historical.region_mapping import RegionMapping

FIXTURES = Path(__file__).parent / "fixtures"


def test_from_nomenclature_yaml_resolves_iso3_lowercase() -> None:
    rm = RegionMapping.from_nomenclature_yaml(FIXTURES / "tiny_regions.yml")
    assert rm.model == "TINY 1.0"
    assert rm.regions == {
        "TINY 1.0|BRA-only": ["bra"],
        "TINY 1.0|IND-USA": ["ind", "usa"],
    }


def test_region_for_case_insensitive() -> None:
    rm = RegionMapping.from_nomenclature_yaml(FIXTURES / "tiny_regions.yml")
    assert rm.region_for("BRA") == "TINY 1.0|BRA-only"
    assert rm.region_for("usa") == "TINY 1.0|IND-USA"
    assert rm.region_for("atlantis") is None


def test_unknown_country_raises_clear_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text(
        "- BAD:\n"
        "  - BAD|X:\n"
        "      countries:\n"
        "        - Fictionland\n"
    )
    with pytest.raises(ConfigurationError, match="Could not resolve ISO3"):
        RegionMapping.from_nomenclature_yaml(bad)


def test_missing_yaml_raises() -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        RegionMapping.from_nomenclature_yaml("/no/such/file.yml")


def test_aggregate_sums_countries_to_regions() -> None:
    rm = RegionMapping.from_nomenclature_yaml(FIXTURES / "tiny_regions.yml")
    df = pd.DataFrame(
        {
            "region": ["bra", "ind", "usa"],
            "variable": ["Emissions|CO2|Energy Sector"] * 3,
            "unit": ["Mt CO2/yr"] * 3,
            1990: [100.0, 500.0, 4000.0],
            2000: [150.0, 800.0, 5000.0],
        }
    )
    out = rm.aggregate(df, country_col="region")
    out_by_region = out.set_index("region")[[1990, 2000]].sort_index()
    assert out_by_region.loc["TINY 1.0|BRA-only"].tolist() == [100.0, 150.0]
    # India + USA sum
    assert out_by_region.loc["TINY 1.0|IND-USA"].tolist() == [500.0 + 4000.0, 800.0 + 5000.0]


def test_aggregate_drops_unmapped_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    rm = RegionMapping.from_nomenclature_yaml(FIXTURES / "tiny_regions.yml")
    df = pd.DataFrame(
        {
            "region": ["bra", "atlantis"],
            "variable": ["Emissions|CO2|Energy Sector"] * 2,
            "unit": ["Mt CO2/yr"] * 2,
            1990: [100.0, 999.0],
        }
    )
    with caplog.at_level("WARNING"):
        out = rm.aggregate(df, country_col="region")
    assert "atlantis" in caplog.text.lower()
    # Atlantis row dropped, Brazil kept
    assert list(out["region"]) == ["TINY 1.0|BRA-only"]
    assert out.iloc[0][1990] == 100.0


def test_aggregate_rejects_missing_column() -> None:
    rm = RegionMapping.from_nomenclature_yaml(FIXTURES / "tiny_regions.yml")
    df = pd.DataFrame({"country": ["bra"], 1990: [1.0]})
    with pytest.raises(DataProcessingError, match="country column"):
        rm.aggregate(df, country_col="region")
