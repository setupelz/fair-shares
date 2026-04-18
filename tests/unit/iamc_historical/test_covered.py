"""Tests for Emissions|Covered construction from IAMC components."""

from __future__ import annotations

import pandas as pd
import pyam
import pytest

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.iamc_historical.covered import (
    COVERED_COMPONENTS,
    build_covered,
    covered_components,
)


def _row(region: str, year: int, variable: str, unit: str, value: float) -> dict:
    return {
        "model": "M",
        "scenario": "S",
        "region": region,
        "variable": variable,
        "unit": unit,
        "year": year,
        "value": value,
    }


def _idf_all_ghg_ex_lulucf(region: str = "R1") -> pyam.IamDataFrame:
    """Components for all-ghg-ex-co2-lulucf at a single (region, year)."""
    return pyam.IamDataFrame(
        pd.DataFrame(
            [
                _row(region, 2020,
                     "Emissions|CO2|Energy and Industrial Processes",
                     "Mt CO2/yr", 1000.0),
                _row(region, 2020, "Emissions|CH4", "Mt CH4/yr", 100.0),
                _row(region, 2020, "Emissions|N2O", "kt N2O/yr", 500.0),
            ]
        )
    )


def test_covered_components_catalog_is_usable() -> None:
    """Every registered category must expose the shape build_covered expects."""
    assert "all-ghg-ex-co2-lulucf" in COVERED_COMPONENTS
    for name, spec in COVERED_COMPONENTS.items():
        assert isinstance(spec["add"], list) and spec["add"], (
            f"{name} 'add' must be a non-empty list"
        )
        assert isinstance(spec["subtract"], list)
        assert isinstance(spec["output_unit"], str)


def test_covered_components_unknown_category_raises() -> None:
    with pytest.raises(DataProcessingError, match="Unknown emission category"):
        covered_components("not-a-thing")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("gwp", "ch4_factor", "n2o_factor"),
    [("AR6GWP100", 27.9, 273), ("AR4GWP100", 25, 298)],
)
def test_build_covered_gwp_weighted_sum(
    gwp: str, ch4_factor: float, n2o_factor: float
) -> None:
    scen = _idf_all_ghg_ex_lulucf()
    out = build_covered(scen, category="all-ghg-ex-co2-lulucf", gwp=gwp)
    covered = out.filter(variable="Emissions|Covered", region="R1", year=2020).data
    assert covered["value"].iloc[0] == pytest.approx(
        1000 + 100 * ch4_factor + 0.5 * n2o_factor
    )
    assert covered["unit"].iloc[0] == "Mt CO2e/yr"


def test_build_covered_missing_component_raises() -> None:
    scen = pyam.IamDataFrame(
        pd.DataFrame(
            [
                _row("R1", 2020,
                     "Emissions|CO2|Energy and Industrial Processes",
                     "Mt CO2/yr", 1000.0),
                _row("R1", 2020, "Emissions|CH4", "Mt CH4/yr", 100.0),
                # no N2O
            ]
        )
    )
    with pytest.raises(DataProcessingError, match="missing"):
        build_covered(scen, category="all-ghg-ex-co2-lulucf")


def test_build_covered_preserves_input_rows() -> None:
    scen = _idf_all_ghg_ex_lulucf()
    out = build_covered(scen, category="all-ghg-ex-co2-lulucf")
    for v in (
        "Emissions|CO2|Energy and Industrial Processes",
        "Emissions|CH4",
        "Emissions|N2O",
    ):
        assert v in set(out.variable)
    assert "Emissions|Covered" in set(out.variable)


def test_backfill_and_build_covered_errors_when_components_missing() -> None:
    from fair_shares.library.iamc_historical import (
        RegionMapping,
        backfill_and_build_covered,
    )

    scen = pyam.IamDataFrame(
        pd.DataFrame(
            [
                _row("R1", 2020,
                     "Emissions|CO2|Energy and Industrial Processes",
                     "Mt CO2/yr", 1000.0),
            ]
        )
    )
    mapping = RegionMapping(model="M", regions={"R1": ["bra"], "R2": ["ind"]})
    with pytest.raises(DataProcessingError, match="missing"):
        backfill_and_build_covered(
            scen,
            category="all-ghg-ex-co2-lulucf",
            region_mapping=mapping,
            start_year=1990,
        )
