"""Tests for non-CO2 GHG infrastructure.

Covers:
- NonCO2Overrides Pydantic model validation
- Country-level non-CO2 timeseries derivation
- Edge cases: mismatched country sets, NaN handling
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.config.models import NonCO2Overrides
from fair_shares.library.utils.data.non_co2 import (
    NON_CO2_CATEGORY,
    derive_non_co2_country_timeseries,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_primap_df(
    countries: list[str],
    years: list[str],
    values: dict[str, list[float]],
    category: str,
    unit: str = "Mt * CO2e",
) -> pd.DataFrame:
    """Build a PRIMAP-style timeseries DataFrame.

    MultiIndex: (iso3c, unit, emission-category)
    Columns: year strings
    """
    rows = []
    for country in countries:
        row_values = values[country]
        rows.append((country, unit, category, *row_values))

    columns = ["iso3c", "unit", "emission-category"] + years
    df = pd.DataFrame(rows, columns=columns)
    df = df.set_index(["iso3c", "unit", "emission-category"])
    return df


# ---------------------------------------------------------------------------
# NonCO2Overrides model tests
# ---------------------------------------------------------------------------


class TestNonCO2Overrides:
    def test_default_all_none(self):
        overrides = NonCO2Overrides()
        assert overrides.convergence_year is None
        assert overrides.responsibility_weight is None
        assert overrides.capability_weight is None

    def test_partial_override(self):
        overrides = NonCO2Overrides(convergence_year=2060)
        assert overrides.convergence_year == 2060
        assert overrides.responsibility_weight is None
        assert overrides.capability_weight is None

    def test_full_override(self):
        overrides = NonCO2Overrides(
            convergence_year=2055,
            responsibility_weight=0.5,
            capability_weight=0.5,
        )
        assert overrides.convergence_year == 2055
        assert overrides.responsibility_weight == 0.5
        assert overrides.capability_weight == 0.5

    def test_merge_with_empty_base(self):
        overrides = NonCO2Overrides(convergence_year=2060)
        result = overrides.merge_with({})
        assert result == {"convergence_year": 2060}

    def test_merge_overrides_base_value(self):
        overrides = NonCO2Overrides(convergence_year=2060)
        base = {"convergence_year": 2050, "responsibility_weight": 0.3}
        result = overrides.merge_with(base)
        assert result["convergence_year"] == 2060
        assert result["responsibility_weight"] == 0.3

    def test_merge_none_fields_do_not_override(self):
        overrides = NonCO2Overrides(responsibility_weight=0.7)
        base = {
            "convergence_year": 2050,
            "responsibility_weight": 0.3,
            "capability_weight": 0.4,
        }
        result = overrides.merge_with(base)
        assert result["convergence_year"] == 2050  # not overridden
        assert result["responsibility_weight"] == 0.7  # overridden
        assert result["capability_weight"] == 0.4  # not overridden

    def test_merge_does_not_mutate_base(self):
        overrides = NonCO2Overrides(convergence_year=2060)
        base = {"convergence_year": 2050}
        result = overrides.merge_with(base)
        assert base["convergence_year"] == 2050  # unchanged
        assert result["convergence_year"] == 2060


# ---------------------------------------------------------------------------
# derive_non_co2_country_timeseries tests
# ---------------------------------------------------------------------------


class TestDeriveNonCO2CountryTimeseries:
    def test_basic_subtraction(self):
        """non_co2 = all_ghg_ex_co2_lulucf - co2_ffi for matching countries."""
        countries = ["AAA", "BBB", "CCC"]
        years = ["2000", "2010", "2020"]

        ghg = _make_primap_df(
            countries,
            years,
            {
                "AAA": [20.0, 25.0, 30.0],
                "BBB": [10.0, 12.0, 14.0],
                "CCC": [5.0, 6.0, 7.0],
            },
            category="all-ghg-ex-co2-lulucf",
        )
        ffi = _make_primap_df(
            countries,
            years,
            {"AAA": [15.0, 18.0, 22.0], "BBB": [7.0, 8.0, 9.0], "CCC": [3.0, 3.5, 4.0]},
            category="co2-ffi",
        )

        result = derive_non_co2_country_timeseries(ghg, ffi)

        assert result.index.names == ["iso3c", "unit", "emission-category"]
        assert all(
            result.index.get_level_values("emission-category") == NON_CO2_CATEGORY
        )

        # Check values
        aaa = result.xs("AAA", level="iso3c")
        assert aaa.loc[("Mt * CO2e", NON_CO2_CATEGORY), "2000"] == pytest.approx(5.0)
        assert aaa.loc[("Mt * CO2e", NON_CO2_CATEGORY), "2010"] == pytest.approx(7.0)
        assert aaa.loc[("Mt * CO2e", NON_CO2_CATEGORY), "2020"] == pytest.approx(8.0)

    def test_result_emission_category_label(self):
        """Result emission-category level must be NON_CO2_CATEGORY."""
        countries = ["AAA"]
        years = ["2000", "2010"]

        ghg = _make_primap_df(
            countries, years, {"AAA": [10.0, 12.0]}, "all-ghg-ex-co2-lulucf"
        )
        ffi = _make_primap_df(countries, years, {"AAA": [6.0, 7.0]}, "co2-ffi")

        result = derive_non_co2_country_timeseries(ghg, ffi)
        categories = (
            result.index.get_level_values("emission-category").unique().tolist()
        )
        assert categories == [NON_CO2_CATEGORY]

    def test_mismatched_country_sets(self):
        """Countries in only one input receive NaN for missing counterpart."""
        years = ["2000", "2010"]

        ghg = _make_primap_df(
            ["AAA", "BBB"],
            years,
            {"AAA": [20.0, 25.0], "BBB": [10.0, 12.0]},
            "all-ghg-ex-co2-lulucf",
        )
        # CCC present in FFI but not in GHG
        ffi = _make_primap_df(
            ["AAA", "CCC"],
            years,
            {"AAA": [15.0, 18.0], "CCC": [3.0, 4.0]},
            "co2-ffi",
        )

        result = derive_non_co2_country_timeseries(ghg, ffi)

        # AAA: fully defined — should be numeric
        aaa_val = result.xs("AAA", level="iso3c").iloc[0]["2000"]
        assert not np.isnan(aaa_val)
        assert aaa_val == pytest.approx(5.0)

        # BBB: only in GHG — result should be NaN
        bbb_val = result.xs("BBB", level="iso3c").iloc[0]["2000"]
        assert np.isnan(bbb_val)

        # CCC: only in FFI — result should be NaN
        ccc_val = result.xs("CCC", level="iso3c").iloc[0]["2000"]
        assert np.isnan(ccc_val)

    def test_nan_in_input_propagates(self):
        """NaN in either input propagates to output."""
        years = ["2000", "2010"]

        ghg_data = _make_primap_df(
            ["AAA"], years, {"AAA": [np.nan, 25.0]}, "all-ghg-ex-co2-lulucf"
        )
        ffi_data = _make_primap_df(["AAA"], years, {"AAA": [15.0, 18.0]}, "co2-ffi")

        result = derive_non_co2_country_timeseries(ghg_data, ffi_data)

        val_2000 = result.xs("AAA", level="iso3c").iloc[0]["2000"]
        val_2010 = result.xs("AAA", level="iso3c").iloc[0]["2010"]

        assert np.isnan(val_2000)  # NaN propagated
        assert val_2010 == pytest.approx(7.0)  # 25 - 18

    def test_year_intersection(self):
        """Only overlapping year columns are kept in the result."""
        ghg = _make_primap_df(
            ["AAA"],
            ["2000", "2010", "2020"],
            {"AAA": [20.0, 25.0, 30.0]},
            "all-ghg-ex-co2-lulucf",
        )
        ffi = _make_primap_df(
            ["AAA"],
            ["2010", "2020", "2030"],
            {"AAA": [12.0, 18.0, 20.0]},
            "co2-ffi",
        )

        result = derive_non_co2_country_timeseries(ghg, ffi)

        assert "2000" not in result.columns
        assert "2030" not in result.columns
        assert "2010" in result.columns
        assert "2020" in result.columns

    def test_single_country_single_year(self):
        """Minimal case: one country, one year."""
        ghg = _make_primap_df(
            ["ZZZ"], ["2015"], {"ZZZ": [100.0]}, "all-ghg-ex-co2-lulucf"
        )
        ffi = _make_primap_df(["ZZZ"], ["2015"], {"ZZZ": [60.0]}, "co2-ffi")

        result = derive_non_co2_country_timeseries(ghg, ffi)

        val = result.xs("ZZZ", level="iso3c").iloc[0]["2015"]
        assert val == pytest.approx(40.0)

    def test_index_structure(self):
        """Result always has three-level MultiIndex with correct names."""
        countries = ["AAA", "BBB"]
        years = ["2000", "2010"]

        ghg = _make_primap_df(
            countries,
            years,
            {"AAA": [10.0, 12.0], "BBB": [5.0, 6.0]},
            "all-ghg-ex-co2-lulucf",
        )
        ffi = _make_primap_df(
            countries, years, {"AAA": [7.0, 8.0], "BBB": [3.0, 4.0]}, "co2-ffi"
        )

        result = derive_non_co2_country_timeseries(ghg, ffi)

        assert isinstance(result.index, pd.MultiIndex)
        assert list(result.index.names) == ["iso3c", "unit", "emission-category"]
        assert result.index.nlevels == 3
