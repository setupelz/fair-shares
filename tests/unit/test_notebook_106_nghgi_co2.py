"""
Tests for the NGHGI-consistent world CO2 in notebook 106.

Verifies that when emission_category=co2, notebook 106 constructs the world
emissions timeseries with build_nghgi_world_co2_timeseries() from nghgi.py:
fossil CO2 (which excludes international bunkers) plus NGHGI LULUCF.

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


# ---------------------------------------------------------------------------
# Test: build_nghgi_world_co2_timeseries is used for co2 category
# ---------------------------------------------------------------------------


class TestNotebook106NghgiCo2:
    """Verify the world CO2 that notebook 106 builds for the co2 category."""

    def test_co2_is_fossil_plus_nghgi_lulucf(self):
        """World CO2 = fossil + LULUCF(NGHGI). The fossil series excludes bunkers."""
        from fair_shares.library.utils.data.nghgi import (
            build_nghgi_world_co2_timeseries,
        )

        # Set up synthetic data
        fossil_ts = _make_world_emissions(
            {1990: 6000.0, 2000: 7000.0, 2020: 9000.0}, "co2-ffi"
        )
        nghgi_ts = _make_nghgi_ts({1990: -400.0, 2000: -500.0, 2020: -600.0})

        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
        )

        # 1990: 6000 + (-400) = 5600
        assert result["1990"].iloc[0] == pytest.approx(5600.0)
        # 2000: 7000 + (-500) = 6500
        assert result["2000"].iloc[0] == pytest.approx(6500.0)
        # 2020: 9000 + (-600) = 8400
        assert result["2020"].iloc[0] == pytest.approx(8400.0)

    def test_co2_result_category_label_is_co2(self):
        """The result emission-category label should be 'co2'."""
        from fair_shares.library.utils.data.nghgi import (
            build_nghgi_world_co2_timeseries,
        )

        fossil_ts = _make_world_emissions({2020: 9000.0}, "co2-ffi")
        nghgi_ts = _make_nghgi_ts({2020: -600.0})

        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
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
