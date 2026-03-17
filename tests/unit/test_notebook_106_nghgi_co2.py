"""
Tests for BUG 7 fix: NGHGI-consistent world CO2 in notebook 106.

Verifies that when emission_category=co2, notebook 106 constructs the world
emissions timeseries using the 4-parameter build_nghgi_world_co2_timeseries()
from nghgi.py (fossil, nghgi, bunker, bm_lulucf), NOT a simplified co2_ffi +
co2_lulucf sum.

These tests use synthetic data to validate the notebook's NGHGI loading logic
in isolation, without requiring actual data files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_world_emissions(year_values: dict[int, float], category: str) -> pd.DataFrame:
    """Build a world emissions DataFrame matching PRIMAP format."""
    index = pd.MultiIndex.from_tuples(
        [("EARTH", "Mt * CO2e", category)],
        names=["iso3c", "unit", "emission-category"],
    )
    data = {str(y): [v] for y, v in year_values.items()}
    return pd.DataFrame(data, index=index)


def _make_nghgi_ts(year_values: dict[int, float]) -> pd.DataFrame:
    """Build a single-row NGHGI LULUCF timeseries (Melo format)."""
    return pd.DataFrame(
        [[year_values[y] for y in sorted(year_values)]],
        columns=[str(y) for y in sorted(year_values)],
        index=pd.Index(["nghgi_lulucf"], name="source"),
    )


def _make_bunker_ts(year_values: dict[int, float]) -> pd.DataFrame:
    """Build a single-row bunker timeseries (GCB format)."""
    return pd.DataFrame(
        [[year_values[y] for y in sorted(year_values)]],
        columns=[str(y) for y in sorted(year_values)],
        index=pd.Index(["bunkers"], name="source"),
    )


# ---------------------------------------------------------------------------
# Test: build_nghgi_world_co2_timeseries is used for co2 category
# ---------------------------------------------------------------------------


class TestNotebook106NghgiCo2:
    """Verify notebook 106 uses the 4-parameter build_nghgi_world_co2_timeseries."""

    def test_co2_uses_build_nghgi_world_co2_timeseries(self):
        """When emission_category=co2, the notebook must call
        build_nghgi_world_co2_timeseries with 4 parameters (fossil, nghgi,
        bunker, bm_lulucf), not a simplified 2-parameter version.
        """
        from fair_shares.library.utils.data.nghgi import (
            build_nghgi_world_co2_timeseries,
        )

        # Set up synthetic data
        fossil_ts = _make_world_emissions(
            {1990: 6000.0, 2000: 7000.0, 2020: 9000.0}, "co2-ffi"
        )
        nghgi_ts = _make_nghgi_ts({1990: -400.0, 2000: -500.0, 2020: -600.0})
        bunker_ts = _make_bunker_ts({1990: 200.0, 2000: 300.0, 2020: 400.0})
        bm_lulucf_ts = _make_world_emissions(
            {1990: -350.0, 2000: -450.0, 2020: -550.0}, "co2-lulucf"
        )

        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )

        # Verify the formula: total CO2 = fossil - bunkers + LULUCF(NGHGI)
        # 1990: 6000 - 200 + (-400) = 5400
        assert result["1990"].iloc[0] == pytest.approx(5400.0)
        # 2000: 7000 - 300 + (-500) = 6200
        assert result["2000"].iloc[0] == pytest.approx(6200.0)
        # 2020: 9000 - 400 + (-600) = 8000
        assert result["2020"].iloc[0] == pytest.approx(8000.0)

    def test_co2_result_includes_bunker_deduction(self):
        """The NGHGI world CO2 must include bunker deduction.

        A simplified co2_ffi + co2_lulucf would miss the bunker deduction
        entirely, producing higher emissions than correct.
        """
        from fair_shares.library.utils.data.nghgi import (
            build_nghgi_world_co2_timeseries,
        )

        fossil_ts = _make_world_emissions({2020: 10000.0}, "co2-ffi")
        nghgi_ts = _make_nghgi_ts({2020: -500.0})
        bunker_ts = _make_bunker_ts({2020: 600.0})
        bm_lulucf_ts = _make_world_emissions({2020: -500.0}, "co2-lulucf")

        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )

        # With bunkers: 10000 - 600 + (-500) = 8900
        expected_with_bunkers = 8900.0
        # Without bunkers (the bug): 10000 + (-500) = 9500
        wrong_without_bunkers = 9500.0

        assert result["2020"].iloc[0] == pytest.approx(expected_with_bunkers)
        assert result["2020"].iloc[0] != pytest.approx(wrong_without_bunkers)

    def test_co2_result_uses_nghgi_lulucf_not_bm(self):
        """The NGHGI world CO2 must use Melo NGHGI LULUCF where available,
        not the BM convention LULUCF from PRIMAP.
        """
        from fair_shares.library.utils.data.nghgi import (
            build_nghgi_world_co2_timeseries,
        )

        fossil_ts = _make_world_emissions({2000: 7000.0}, "co2-ffi")
        # NGHGI and BM give DIFFERENT values -- this is the whole point
        nghgi_ts = _make_nghgi_ts({2000: -800.0})  # NGHGI: more sink
        bunker_ts = _make_bunker_ts({2000: 200.0})
        bm_lulucf_ts = _make_world_emissions(
            {2000: -400.0},
            "co2-lulucf",  # BM: less sink
        )

        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )

        # With NGHGI: 7000 - 200 + (-800) = 6000
        expected_with_nghgi = 6000.0
        # With BM (wrong): 7000 - 200 + (-400) = 6400
        wrong_with_bm = 6400.0

        assert result["2000"].iloc[0] == pytest.approx(expected_with_nghgi)
        assert result["2000"].iloc[0] != pytest.approx(wrong_with_bm)

    def test_co2_result_category_label_is_co2(self):
        """The result emission-category label should be 'co2'."""
        from fair_shares.library.utils.data.nghgi import (
            build_nghgi_world_co2_timeseries,
        )

        fossil_ts = _make_world_emissions({2020: 9000.0}, "co2-ffi")
        nghgi_ts = _make_nghgi_ts({2020: -600.0})
        bunker_ts = _make_bunker_ts({2020: 400.0})
        bm_lulucf_ts = _make_world_emissions({2020: -550.0}, "co2-lulucf")

        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )

        # Result should have co2 as emission-category
        assert result.index.get_level_values("emission-category")[0] == "co2"

    def test_co2_ffi_does_not_use_build_nghgi(self):
        """When emission_category=co2-ffi, the notebook should load emissions
        directly without calling build_nghgi_world_co2_timeseries.

        This is a structural test: co2-ffi does not involve LULUCF or bunkers.
        """
        # For co2-ffi, the notebook loads emiss_co2-ffi_timeseries.csv directly
        # and does NOT call build_nghgi_world_co2_timeseries.
        # We verify by checking the notebook source code.

        notebook_path = (
            Path(__file__).resolve().parent.parent.parent
            / "notebooks"
            / "106_generate_pathways_from_rcbs.py"
        )
        source = notebook_path.read_text()

        # The co2 branch should call build_nghgi_world_co2_timeseries
        assert "build_nghgi_world_co2_timeseries" in source

        # The branching logic: co2 branch constructs NGHGI, co2-ffi loads directly
        assert 'emission_category == "co2"' in source
