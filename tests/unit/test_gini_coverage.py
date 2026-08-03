"""Analysis-country membership does not depend on Gini, and missing Gini is explicit.

A country without a Gini value used to be dropped from every allocation, not
just the inequality-adjusted ones. These tests hold the two halves of the fix in
place: Gini is out of the membership intersection, and a country without a value
is named and marked as imputed rather than disappearing.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError
from fair_shares.library.preprocessing import (
    complete_gini,
    compute_analysis_countries,
    create_coverage_summary,
    gini_missing_policy,
)

YEARS = [str(y) for y in range(1990, 2024)]
COUNTRIES = ["AUT", "DEU", "SAU"]


def _timeseries(countries, unit="billion"):
    return pd.DataFrame(
        [[1.0] * len(YEARS) for _ in countries],
        index=pd.MultiIndex.from_tuples(
            [(c, unit) for c in countries], names=["iso3c", "unit"]
        ),
        columns=YEARS,
    )


def _emissions(countries):
    return pd.DataFrame(
        [[1.0] * len(YEARS) for _ in countries],
        index=pd.MultiIndex.from_tuples(
            [(c, "MtCO2", "co2-ffi") for c in countries],
            names=["iso3c", "unit", "emission-category"],
        ),
        columns=YEARS,
    )


def _gini(values: dict[str, float]):
    return pd.DataFrame(
        {"gini": list(values.values())},
        index=pd.MultiIndex.from_tuples(
            [(c, "unitless") for c in values], names=["iso3c", "unit"]
        ),
    )


class TestAnalysisCountriesIgnoreGini:
    def test_a_country_without_gini_stays_in_the_analysis(self):
        countries = compute_analysis_countries(
            {"co2-ffi": _emissions(COUNTRIES)},
            _timeseries(COUNTRIES),
            _timeseries(COUNTRIES, unit="million"),
            _gini({"AUT": 0.3, "DEU": 0.32}),
        )
        assert countries == set(COUNTRIES)

    def test_the_country_set_does_not_change_with_the_gini_source(self):
        args = (
            {"co2-ffi": _emissions(COUNTRIES)},
            _timeseries(COUNTRIES),
            _timeseries(COUNTRIES, unit="million"),
        )
        wiid = compute_analysis_countries(*args, _gini({"AUT": 0.3, "SAU": 0.45}))
        wdi = compute_analysis_countries(*args, _gini({"AUT": 0.29, "DEU": 0.31}))
        assert wiid == wdi == set(COUNTRIES)

    def test_missing_gdp_still_removes_a_country(self):
        countries = compute_analysis_countries(
            {"co2-ffi": _emissions(COUNTRIES)},
            _timeseries(["AUT", "DEU"]),
            _timeseries(COUNTRIES, unit="million"),
            _gini({c: 0.3 for c in COUNTRIES}),
        )
        assert countries == {"AUT", "DEU"}


class TestCompleteGini:
    def test_fallback_mean_names_every_country_and_reports_imputation(self):
        gini_complete, imputed = complete_gini(
            _gini({"AUT": 0.30, "DEU": 0.34}), set(COUNTRIES)
        )
        assert imputed == {"SAU"}
        assert set(gini_complete.index.get_level_values("iso3c")) == {
            *COUNTRIES,
            "ROW",
        }
        assert gini_complete.loc[("SAU", "unitless"), "gini"] == pytest.approx(0.32)
        assert gini_complete.loc[("ROW", "unitless"), "gini"] == pytest.approx(0.32)

    def test_the_mean_uses_analysis_countries_only(self):
        gini_complete, _ = complete_gini(
            _gini({"AUT": 0.30, "DEU": 0.34, "BRA": 0.90}), {"AUT", "DEU", "SAU"}
        )
        assert gini_complete.loc[("SAU", "unitless"), "gini"] == pytest.approx(0.32)

    def test_nothing_changes_when_every_country_has_a_value(self):
        values = {"AUT": 0.30, "DEU": 0.34, "SAU": 0.45}
        gini_complete, imputed = complete_gini(_gini(values), set(COUNTRIES))
        assert imputed == set()
        for iso3c, value in values.items():
            assert gini_complete.loc[(iso3c, "unitless"), "gini"] == value
        assert gini_complete.loc[("ROW", "unitless"), "gini"] == pytest.approx(
            sum(values.values()) / 3
        )

    def test_strict_refuses_to_impute(self):
        with pytest.raises(DataProcessingError, match="SAU"):
            complete_gini(
                _gini({"AUT": 0.30, "DEU": 0.34}), set(COUNTRIES), policy="strict"
            )

    def test_strict_is_fine_when_nothing_is_missing(self):
        gini_complete, imputed = complete_gini(
            _gini({c: 0.3 for c in COUNTRIES}), set(COUNTRIES), policy="strict"
        )
        assert imputed == set()
        assert ("ROW", "unitless") in gini_complete.index

    def test_no_gini_at_all_is_an_error(self):
        with pytest.raises(DataProcessingError, match="No Gini coefficient data"):
            complete_gini(_gini({"BRA": 0.5}), set(COUNTRIES))

    def test_an_unknown_policy_is_rejected(self):
        with pytest.raises(ConfigurationError, match="Unknown Gini missing-value"):
            complete_gini(_gini({"AUT": 0.3}), {"AUT"}, policy="guess")


class TestPolicyFromConfig:
    def test_the_default_applies_when_the_config_predates_the_setting(self):
        assert gini_missing_policy({"general": {}}) == "fallback-mean"
        assert gini_missing_policy({}) == "fallback-mean"

    def test_a_configured_policy_is_used(self):
        assert (
            gini_missing_policy({"general": {"gini_missing_policy": "strict"}})
            == "strict"
        )


class TestCoverageSummary:
    def test_gini_imputed_marks_analysis_countries_without_a_value(self, tmp_path):
        summary = create_coverage_summary(
            analysis_countries=set(COUNTRIES),
            emissions_data={"co2-ffi": _emissions(COUNTRIES)},
            gdp=_timeseries(COUNTRIES),
            population=_timeseries(COUNTRIES, unit="million"),
            gini=_gini({"AUT": 0.30, "DEU": 0.34}),
            region_mapping=pd.DataFrame({"iso3c": [*COUNTRIES, "BRA"]}),
            output_dir=tmp_path,
        )
        by_country = summary.set_index("iso3c")
        assert by_country.loc["SAU", "gini_imputed"]
        assert not by_country.loc["AUT", "gini_imputed"]
        # Outside the analysis, so it is in ROW rather than imputed.
        assert not by_country.loc["BRA", "gini_imputed"]
