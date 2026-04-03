"""Tests for harmonise-then-median pipeline and calculate_emission_difference."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.preprocessing.scenarios import (
    harmonise_and_median_ar6_pathways,
)
from fair_shares.library.utils.data.emissions import calculate_emission_difference

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pathway_long(
    n_pathways: int = 3,
    years: list[int] | None = None,
    emission_category: str = "co2-ffi",
    base_value: float = 100.0,
    climate_assessment: str = "C1",
) -> pd.DataFrame:
    """Build a minimal long-format pathway DataFrame for testing."""
    if years is None:
        years = [2020, 2025, 2030, 2035, 2040]

    rows = []
    for i in range(n_pathways):
        for year in years:
            rows.append(
                {
                    "climate-assessment": climate_assessment,
                    "model": f"MODEL_{i}",
                    "scenario": f"SCEN_{i}",
                    "iso3c": "World",
                    "unit": "Mt * CO2e",
                    "year": year,
                    emission_category: base_value * (1 + 0.05 * i),
                }
            )
    return pd.DataFrame(rows)


def _make_historical(
    anchor_year: int = 2020,
    value: float = 95.0,
    extra_years: list[int] | None = None,
) -> pd.DataFrame:
    """Build a wide historical DataFrame with a single row, indexed like MultiIndex."""
    if extra_years is None:
        extra_years = list(range(2010, anchor_year + 1))

    years = sorted(set(extra_years + [anchor_year]))
    data = {str(y): [value] for y in years}
    df = pd.DataFrame(data)
    # Minimal single-row index (no MultiIndex needed for harmonization helper)
    return df


# ---------------------------------------------------------------------------
# calculate_emission_difference
# ---------------------------------------------------------------------------


class TestCalculateEmissionDifference:
    """Tests for calculate_emission_difference()."""

    def _make_df(
        self,
        year_cols: list[str],
        values: list[float],
        n_rows: int = 2,
        model_prefix: str = "M",
    ) -> pd.DataFrame:
        rows = []
        for i in range(n_rows):
            row = {
                "climate-assessment": "C1",
                "Model": f"{model_prefix}{i}",
                "Scenario": f"S{i}",
                "Region": "World",
            }
            for j, col in enumerate(year_cols):
                row[col] = values[j] + i
            rows.append(row)
        return pd.DataFrame(rows)

    def test_basic_difference(self):
        """Difference df1 - df2 for simple known inputs."""
        id_vars = ["climate-assessment", "Model", "Scenario", "Region"]
        year_cols = ["2020", "2025", "2030"]

        df1 = self._make_df(year_cols, [100.0, 110.0, 120.0])
        df2 = self._make_df(year_cols, [10.0, 15.0, 20.0])

        merged, year_data = calculate_emission_difference(
            df1, df2, id_vars, year_cols, "co2", "afolu"
        )

        assert set(year_data.keys()) == set(year_cols)
        # Row 0: 100 - 10 = 90; Row 1: 101 - 11 = 90
        assert (year_data["2020"] == 90.0).all()
        assert (year_data["2025"] == 95.0).all()
        assert (year_data["2030"] == 100.0).all()

    def test_returns_merged_and_year_data(self):
        """Returns both merged DataFrame and year_data dict."""
        id_vars = ["Model"]
        year_cols = ["2020"]
        df1 = pd.DataFrame({"Model": ["A"], "2020": [50.0]})
        df2 = pd.DataFrame({"Model": ["A"], "2020": [30.0]})

        merged, year_data = calculate_emission_difference(
            df1, df2, id_vars, year_cols, "x", "y"
        )

        assert isinstance(merged, pd.DataFrame)
        assert isinstance(year_data, dict)
        assert "2020" in year_data
        assert year_data["2020"].iloc[0] == pytest.approx(20.0)

    def test_no_match_raises_error(self):
        """DataProcessingError raised when no rows match on id_vars."""
        id_vars = ["Model"]
        year_cols = ["2020"]
        df1 = pd.DataFrame({"Model": ["A"], "2020": [50.0]})
        df2 = pd.DataFrame({"Model": ["B"], "2020": [30.0]})  # Different model

        with pytest.raises(DataProcessingError, match="No matching rows"):
            calculate_emission_difference(df1, df2, id_vars, year_cols, "x", "y")

    def test_string_stripping_enables_match(self):
        """Whitespace in id columns is stripped before merging."""
        id_vars = ["Model"]
        year_cols = ["2020"]
        df1 = pd.DataFrame({"Model": ["  A  "], "2020": [50.0]})
        df2 = pd.DataFrame({"Model": ["A"], "2020": [30.0]})

        _, year_data = calculate_emission_difference(
            df1, df2, id_vars, year_cols, "x", "y"
        )
        assert year_data["2020"].iloc[0] == pytest.approx(20.0)

    def test_negative_difference(self):
        """Handles negative differences without error."""
        id_vars = ["Model"]
        year_cols = ["2020"]
        df1 = pd.DataFrame({"Model": ["A"], "2020": [10.0]})
        df2 = pd.DataFrame({"Model": ["A"], "2020": [50.0]})

        _, year_data = calculate_emission_difference(
            df1, df2, id_vars, year_cols, "x", "y"
        )
        assert year_data["2020"].iloc[0] == pytest.approx(-40.0)


# ---------------------------------------------------------------------------
# harmonise_and_median_ar6_pathways
# ---------------------------------------------------------------------------


class TestHarmoniseAndMedianAr6Pathways:
    """Tests for harmonise_and_median_ar6_pathways()."""

    _PATHWAY_INDEX_COLS = [
        "climate-assessment",
        "model",
        "scenario",
        "iso3c",
        "unit",
        "year",
    ]

    def test_median_of_three_pathways_correct(self):
        """Median across 3 pathways with known values matches expected median."""
        emission_category = "co2-ffi"
        years = [2020, 2025, 2030]

        # Three pathways with values 100, 110, 120 at year 2020
        rows = []
        values_by_pathway = [100.0, 110.0, 120.0]
        for i, base in enumerate(values_by_pathway):
            for year in years:
                rows.append(
                    {
                        "climate-assessment": "C1",
                        "model": f"MODEL_{i}",
                        "scenario": f"SCEN_{i}",
                        "iso3c": "World",
                        "unit": "Mt * CO2e",
                        "year": year,
                        emission_category: base,
                    }
                )
        var_long = pd.DataFrame(rows)

        result = harmonise_and_median_ar6_pathways(
            var_long=var_long,
            emission_category=emission_category,
            historical_data=None,  # Skip harmonisation
            anchor_year=2020,
            convergence_year=2030,
            interpolation_method="linear",
            pathway_index_cols=self._PATHWAY_INDEX_COLS,
            source_name="ar6",
        )

        assert isinstance(result, pd.DataFrame)
        assert result.index.names == [
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ]
        # Median of 100, 110, 120 = 110
        # Year 2020 after interpolation should be 110
        assert "2020" in result.columns
        quantile_row = result.xs(
            ("C1", "ar6", "World", "Mt * CO2e", "co2-ffi"),
            level=[
                "climate-assessment",
                "source",
                "iso3c",
                "unit",
                "emission-category",
            ],
        )
        quantile_row = quantile_row[
            quantile_row.index.get_level_values("quantile") == 0.5
        ]
        assert quantile_row["2020"].iloc[0] == pytest.approx(110.0)

    def test_output_multiindex_structure(self):
        """Output has correct 6-level MultiIndex and string year columns."""
        emission_category = "co2-ffi"
        var_long = _make_pathway_long(emission_category=emission_category)

        result = harmonise_and_median_ar6_pathways(
            var_long=var_long,
            emission_category=emission_category,
            historical_data=None,
            anchor_year=2020,
            convergence_year=2030,
            interpolation_method="linear",
            pathway_index_cols=self._PATHWAY_INDEX_COLS,
            source_name="ar6",
        )

        assert result.index.names == [
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ]
        # All columns should be string year labels
        for col in result.columns:
            assert isinstance(col, str), f"Column {col!r} is not a string"
            assert col.isdigit(), f"Column {col!r} is not a year"

    def test_single_pathway(self):
        """Single pathway returns itself as its own median without error."""
        emission_category = "co2-ffi"
        var_long = _make_pathway_long(n_pathways=1, emission_category=emission_category)

        result = harmonise_and_median_ar6_pathways(
            var_long=var_long,
            emission_category=emission_category,
            historical_data=None,
            anchor_year=2020,
            convergence_year=2030,
            interpolation_method="linear",
            pathway_index_cols=self._PATHWAY_INDEX_COLS,
            source_name="ar6",
        )

        assert len(result) >= 1
        assert result.index.names[0] == "climate-assessment"

    def test_with_harmonisation(self):
        """Pipeline works end-to-end when historical_data is provided."""
        emission_category = "co2-ffi"
        anchor_year = 2020
        convergence_year = 2030

        var_long = _make_pathway_long(
            n_pathways=3,
            years=[2020, 2025, 2030, 2035, 2040],
            emission_category=emission_category,
            base_value=100.0,
        )

        # Historical value at anchor year differs from pathway values
        hist = _make_historical(anchor_year=anchor_year, value=80.0)

        result = harmonise_and_median_ar6_pathways(
            var_long=var_long,
            emission_category=emission_category,
            historical_data=hist,
            anchor_year=anchor_year,
            convergence_year=convergence_year,
            interpolation_method="linear",
            pathway_index_cols=self._PATHWAY_INDEX_COLS,
            source_name="ar6",
        )

        assert isinstance(result, pd.DataFrame)
        # After harmonisation the anchor year value should match historical (80)
        anchor_slice = result.xs(
            ("C1", "ar6", "World", "Mt * CO2e", "co2-ffi"),
            level=[
                "climate-assessment",
                "source",
                "iso3c",
                "unit",
                "emission-category",
            ],
        )
        anchor_slice = anchor_slice[
            anchor_slice.index.get_level_values("quantile") == 0.5
        ]
        anchor_val = anchor_slice[str(anchor_year)].iloc[0]
        assert anchor_val == pytest.approx(80.0, rel=1e-4)

    def test_empty_input_raises_error(self):
        """DataProcessingError raised for empty input DataFrame."""
        emission_category = "co2-ffi"
        var_long = pd.DataFrame(
            columns=[
                "climate-assessment",
                "model",
                "scenario",
                "iso3c",
                "unit",
                "year",
                emission_category,
            ]
        )

        with pytest.raises(DataProcessingError, match="empty"):
            harmonise_and_median_ar6_pathways(
                var_long=var_long,
                emission_category=emission_category,
                historical_data=None,
                anchor_year=2020,
                convergence_year=2030,
                interpolation_method="linear",
                pathway_index_cols=self._PATHWAY_INDEX_COLS,
                source_name="ar6",
            )

    def test_all_nan_pathway_handled(self):
        """Pathway with all-NaN values is excluded from median gracefully."""
        emission_category = "co2-ffi"
        years = [2020, 2025, 2030]

        rows = []
        # Pathway 0: valid values
        for year in years:
            rows.append(
                {
                    "climate-assessment": "C1",
                    "model": "MODEL_0",
                    "scenario": "SCEN_0",
                    "iso3c": "World",
                    "unit": "Mt * CO2e",
                    "year": year,
                    emission_category: 100.0,
                }
            )
        # Pathway 1: NaN values
        for year in years:
            rows.append(
                {
                    "climate-assessment": "C1",
                    "model": "MODEL_1",
                    "scenario": "SCEN_1",
                    "iso3c": "World",
                    "unit": "Mt * CO2e",
                    "year": year,
                    emission_category: np.nan,
                }
            )

        var_long = pd.DataFrame(rows)

        # Should not raise; median of [100, NaN] = 100
        result = harmonise_and_median_ar6_pathways(
            var_long=var_long,
            emission_category=emission_category,
            historical_data=None,
            anchor_year=2020,
            convergence_year=2030,
            interpolation_method="linear",
            pathway_index_cols=self._PATHWAY_INDEX_COLS,
            source_name="ar6",
        )

        # The median of [100, NaN] should be 100 (pandas median skips NaN)
        nan_slice = result.xs(
            ("C1", "ar6", "World", "Mt * CO2e", "co2-ffi"),
            level=[
                "climate-assessment",
                "source",
                "iso3c",
                "unit",
                "emission-category",
            ],
        )
        nan_slice = nan_slice[nan_slice.index.get_level_values("quantile") == 0.5]
        val = nan_slice["2020"].iloc[0]
        assert val == pytest.approx(100.0)

    def test_source_name_propagated(self):
        """source_name appears correctly in output MultiIndex."""
        emission_category = "co2-ffi"
        var_long = _make_pathway_long(emission_category=emission_category)

        result = harmonise_and_median_ar6_pathways(
            var_long=var_long,
            emission_category=emission_category,
            historical_data=None,
            anchor_year=2020,
            convergence_year=2030,
            interpolation_method="linear",
            pathway_index_cols=self._PATHWAY_INDEX_COLS,
            source_name="my-source",
        )

        sources = result.index.get_level_values("source").unique()
        assert list(sources) == ["my-source"]

    def test_emission_category_propagated(self):
        """emission-category index level matches the input emission_category."""
        emission_category = "all-ghg-ex-co2-lulucf"
        var_long = _make_pathway_long(emission_category=emission_category)

        result = harmonise_and_median_ar6_pathways(
            var_long=var_long,
            emission_category=emission_category,
            historical_data=None,
            anchor_year=2020,
            convergence_year=2030,
            interpolation_method="linear",
            pathway_index_cols=self._PATHWAY_INDEX_COLS,
            source_name="ar6",
        )

        cats = result.index.get_level_values("emission-category").unique()
        assert list(cats) == [emission_category]
