"""Tests for the country land-use CO2 loaders (utils/data/lulucf.py)."""

import pandas as pd
import pytest

from fair_shares.library.exceptions import DataLoadingError, DataProcessingError
from fair_shares.library.utils.data.lulucf import (
    C_TO_CO2,
    load_gcb_national_luc,
    load_nghgi_lulucf,
)

HEADER_ROW = 7


def _write_gcb_workbook(path, sheets):
    """Write a GCB-style workbook: 7 note rows, then years x names in Tg C."""
    with pd.ExcelWriter(path) as writer:
        for name, frame in sheets.items():
            notes = pd.DataFrame([[f"note {i}"] for i in range(HEADER_ROW)])
            notes.to_excel(writer, sheet_name=name, header=False, index=False)
            frame.index.name = "unit: Tg C/year"
            frame.to_excel(writer, sheet_name=name, startrow=HEADER_ROW)


def _sheet(brazil, usa):
    return pd.DataFrame(
        {
            "Brazil": brazil,
            "USA": usa,
            "OTHER": [1.0, 1.0],
            "Global": [100.0, 90.0],
            "EU27": [-5.0, -5.0],
        },
        index=[2023, 2024],
    )


@pytest.fixture
def workbook(tmp_path):
    path = tmp_path / "luc.xlsx"
    _write_gcb_workbook(
        path,
        {
            "BLUE": _sheet([10.0, 20.0], [2.0, 4.0]),
            "OSCAR": _sheet([30.0, 40.0], [6.0, 8.0]),
        },
    )
    return path


def test_gcb_luc_is_model_mean_in_mt_co2(workbook):
    out = load_gcb_national_luc(workbook, ["BLUE", "OSCAR"], "EARTH")
    assert out.loc["BRA", "2023"] == pytest.approx(20.0 * C_TO_CO2)
    assert out.loc["USA", "2024"] == pytest.approx(6.0 * C_TO_CO2)
    assert list(out.columns) == ["2023", "2024"]


def test_gcb_luc_world_row_is_global_column_and_aggregates_are_dropped(workbook):
    out = load_gcb_national_luc(workbook, ["BLUE", "OSCAR"], "EARTH")
    assert out.loc["EARTH", "2024"] == pytest.approx(90.0 * C_TO_CO2)
    assert set(out.index) == {"BRA", "USA", "EARTH"}


def test_gcb_luc_single_model(workbook):
    out = load_gcb_national_luc(workbook, ["OSCAR"], "EARTH")
    assert out.loc["BRA", "2023"] == pytest.approx(30.0 * C_TO_CO2)


def test_gcb_luc_rejects_missing_model_sheet(workbook):
    with pytest.raises(DataLoadingError, match="LUCE"):
        load_gcb_national_luc(workbook, ["BLUE", "LUCE"], "EARTH")


def test_gcb_luc_rejects_unknown_country_name(tmp_path):
    path = tmp_path / "luc.xlsx"
    frame = _sheet([1.0, 1.0], [1.0, 1.0]).rename(columns={"Brazil": "Atlantis"})
    _write_gcb_workbook(path, {"BLUE": frame})
    with pytest.raises(DataProcessingError, match="Atlantis"):
        load_gcb_national_luc(path, ["BLUE"], "EARTH")


def test_nghgi_loader_pivots_and_renames_world(tmp_path):
    path = tmp_path / "melo.csv"
    pd.DataFrame(
        {
            "ISO3": ["BRA", "BRA", "WRD", "EU27", "BRA"],
            "Gas": ["CO2", "CO2", "CO2", "CO2", "CO2"],
            "Year": [2023, 2024, 2024, 2024, 2024],
            "Category": ["LULUCF", "LULUCF", "LULUCF", "LULUCF", "FOREST"],
            "CFluxes_yr": [5.0, 6.0, -100.0, -300.0, 99.0],
        }
    ).to_csv(path, index=False)
    out = load_nghgi_lulucf(
        path,
        "EARTH",
        iso3_column="ISO3",
        year_column="Year",
        value_column="CFluxes_yr",
        category_filter="LULUCF",
        gas_filter="CO2",
        source_world_key="WRD",
        exclude_regions=["EU27"],
    )
    assert out.loc["BRA", "2024"] == 6.0
    assert out.loc["EARTH", "2024"] == -100.0
    assert "EU27" not in out.index


def test_lulucf_parameters_require_fields_of_their_basis():
    from pydantic import ValidationError

    from fair_shares.library.config.models import LulucfDataParameters

    ok = LulucfDataParameters(
        basis="bookkeeping", world_key="Global", format="gcb-luc", models=["BLUE"]
    )
    assert ok.basis == "bookkeeping"
    with pytest.raises(ValidationError, match="models"):
        LulucfDataParameters(basis="bookkeeping", world_key="Global", format="gcb-luc")
    with pytest.raises(ValidationError, match="category_filter"):
        LulucfDataParameters(world_key="WRD", format="long")


def test_config_validates_only_the_active_lulucf_source():
    """A missing file of an inactive LULUCF source must not block a run."""
    from fair_shares.library.utils.data import config as config_mod

    sources = {
        "target": "rcbs",
        "emissions": "primap-202609",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "wdi-2025",
        "lulucf": "melo-2026-v4",
    }
    cfg, _ = config_mod.build_data_config("co2", sources)
    assert list(cfg.lulucf) == ["melo-2026-v4"]


def test_unknown_lulucf_source_names_the_options():
    from fair_shares.library.exceptions import ConfigurationError
    from fair_shares.library.utils.data.config import build_data_config

    with pytest.raises(ConfigurationError, match="Did you mean"):
        build_data_config(
            "co2",
            {
                "target": "rcbs",
                "emissions": "primap-202609",
                "gdp": "wdi-2025",
                "population": "un-owid-2025",
                "gini": "wdi-2025",
                "lulucf": "melo-2026-v5",
            },
        )


def test_trusted_cache_skips_raw_path_checks(monkeypatch):
    from fair_shares.library.utils.dataframes import validate_path_exists

    monkeypatch.setenv("FAIR_SHARES_TRUST_CACHE", "1")
    assert (
        validate_path_exists("data/nowhere/missing.csv") == "data/nowhere/missing.csv"
    )
