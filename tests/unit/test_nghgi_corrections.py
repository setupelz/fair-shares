"""
Unit tests for NGHGI correction utilities (nghgi.py) and related changes to rcb.py.

Tests cover:
- Loader functions (NGHGI LULUCF, bunker timeseries, AR6 category constants)
- Cumulative emission computation
- Bunker deduction
- Scenario-to-AR6-category mapping
- process_rcb_to_2020_baseline() with Gidden Direct LULUCF shift
- NGHGI-consistent world CO2 timeseries construction
- Precautionary LULUCF cap in _resolve_adjustment_scalars
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair_shares.library.exceptions import DataLoadingError, DataProcessingError
from fair_shares.library.preprocessing.rcbs import _resolve_adjustment_scalars
from fair_shares.library.utils.data.nghgi import (
    build_nghgi_world_co2_timeseries,
    compute_bunker_deduction,
    compute_cumulative_emissions,
    load_ar6_category_constants,
    load_bunker_timeseries,
    load_world_co2_lulucf,
)
from fair_shares.library.utils.data.rcb import process_rcb_to_2020_baseline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_timeseries(
    values: dict[int, float], index_name: str = "source", row_label: str = "test"
) -> pd.DataFrame:
    """Build a single-row timeseries DataFrame with string year columns."""
    return pd.DataFrame(
        [[values[y] for y in sorted(values)]],
        columns=[str(y) for y in sorted(values)],
        index=pd.Index([row_label], name=index_name),
    )


def _make_ffi_emissions(year_values: dict[int, float]) -> pd.DataFrame:
    """Build a world CO2-FFI emissions DataFrame matching the format used in rcb.py."""
    index = pd.MultiIndex.from_tuples(
        [("World", "Mt * CO2e", "co2-ffi")],
        names=["iso3c", "unit", "emission-category"],
    )
    data = {str(y): [v] for y, v in year_values.items()}
    return pd.DataFrame(data, index=index)


# ---------------------------------------------------------------------------
# compute_cumulative_emissions
# ---------------------------------------------------------------------------


class TestComputeCumulativeEmissions:
    """Tests for compute_cumulative_emissions."""

    @pytest.fixture
    def simple_ts(self) -> pd.DataFrame:
        """Timeseries with years 2018-2025, value = year - 2000."""
        values = {y: float(y - 2000) for y in range(2018, 2026)}
        return _make_timeseries(values)

    def test_full_range_sum(self, simple_ts):
        """Sum all years 2018-2025."""
        total = compute_cumulative_emissions(simple_ts, 2018, 2025)
        expected = sum(y - 2000 for y in range(2018, 2026))
        assert total == pytest.approx(expected)

    def test_sub_range_sum(self, simple_ts):
        """Sum 2020-2022 only."""
        total = compute_cumulative_emissions(simple_ts, 2020, 2022)
        assert total == pytest.approx(20.0 + 21.0 + 22.0)

    def test_single_year(self, simple_ts):
        """Single-year range returns that year's value."""
        total = compute_cumulative_emissions(simple_ts, 2023, 2023)
        assert total == pytest.approx(23.0)

    def test_missing_years_skipped(self):
        """Years not in the timeseries are silently skipped (not interpolated)."""
        ts = _make_timeseries({2020: 10.0, 2022: 30.0})  # 2021 missing
        total = compute_cumulative_emissions(ts, 2020, 2022)
        assert total == pytest.approx(40.0)

    def test_no_data_in_range_raises(self, simple_ts):
        """Requesting a range entirely outside the data raises DataProcessingError."""
        with pytest.raises(DataProcessingError, match="No data found"):
            compute_cumulative_emissions(simple_ts, 2050, 2060)

    def test_negative_values(self):
        """Sinks (negative values) are summed correctly."""
        ts = _make_timeseries({2020: -500.0, 2021: -600.0})
        total = compute_cumulative_emissions(ts, 2020, 2021)
        assert total == pytest.approx(-1100.0)


# ---------------------------------------------------------------------------
# load_world_co2_lulucf (CSV loading)
# ---------------------------------------------------------------------------


class TestLoadNghgiLulucfWorld:
    """Tests for load_world_co2_lulucf (CSV-based loader returning tuple)."""

    def _write_csv(self, tmp_path, source: str, year_values: dict[int, float]) -> Path:
        """Write a mock NGHGI LULUCF world CSV and return its path."""
        cols = ["source"] + [str(y) for y in sorted(year_values)]
        vals = [source] + [year_values[y] for y in sorted(year_values)]
        df = pd.DataFrame([vals], columns=cols)
        csv_path = tmp_path / "world_co2-lulucf_timeseries.csv"
        df.to_csv(csv_path, index=False)
        return csv_path

    def test_values_returned_unchanged(self, tmp_path):
        """Values are returned unchanged (already in MtCO2)."""
        csv_path = self._write_csv(
            tmp_path, "nghgi_lulucf", {1990: -1000.0, 2022: -2763.0}
        )
        result, splice_year = load_world_co2_lulucf(csv_path)

        assert result["1990"].iloc[0] == pytest.approx(-1000.0)
        assert result["2022"].iloc[0] == pytest.approx(-2763.0)

    def test_splice_year_derived_from_data(self, tmp_path):
        """Splice year is the max year column in the CSV."""
        csv_path = self._write_csv(
            tmp_path, "nghgi_lulucf", {1990: -1000.0, 2020: -2000.0, 2022: -2763.0}
        )
        _, splice_year = load_world_co2_lulucf(csv_path)
        assert splice_year == 2022

    def test_negative_sink_preserved(self, tmp_path):
        """Negative values (net sink) must not be sign-flipped."""
        csv_path = self._write_csv(tmp_path, "nghgi_lulucf", {2020: -500.0})
        result, _ = load_world_co2_lulucf(csv_path)
        assert result["2020"].iloc[0] < 0

    def test_missing_source_column_raises(self, tmp_path):
        """DataLoadingError when 'source' column is absent."""
        csv_path = tmp_path / "bad.csv"
        pd.DataFrame({"year": [2020], "value": [100.0]}).to_csv(csv_path, index=False)
        with pytest.raises(DataLoadingError, match="'source' column not found"):
            load_world_co2_lulucf(csv_path)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(
            DataLoadingError, match="NGHGI LULUCF world timeseries not found"
        ):
            load_world_co2_lulucf(tmp_path / "nonexistent.csv")

    def test_output_index_name(self, tmp_path):
        """Output index name should be 'source'."""
        csv_path = self._write_csv(tmp_path, "nghgi_lulucf", {2020: -100.0})
        result, _ = load_world_co2_lulucf(csv_path)
        assert result.index.name == "source"

    def test_returns_tuple(self, tmp_path):
        """Return type is (DataFrame, int) tuple."""
        csv_path = self._write_csv(
            tmp_path, "nghgi_lulucf", {2020: -100.0, 2022: -200.0}
        )
        out = load_world_co2_lulucf(csv_path)
        assert isinstance(out, tuple)
        assert len(out) == 2
        assert isinstance(out[0], pd.DataFrame)
        assert isinstance(out[1], int)


# ---------------------------------------------------------------------------
# load_bunker_timeseries (mocked)
# ---------------------------------------------------------------------------


class TestLoadBunkerTimeseries:
    """Tests for load_bunker_timeseries (reads intermediate CSV)."""

    @staticmethod
    def _write_bunker_csv(
        path: Path, years: list[int], values_mtco2: list[float]
    ) -> Path:
        """Write a standard bunker timeseries CSV."""
        df = pd.DataFrame(
            [values_mtco2],
            columns=[str(y) for y in years],
            index=pd.Index(["bunkers"], name="source"),
        )
        df.reset_index().to_csv(path, index=False)
        return path

    def test_reads_csv_correctly(self, tmp_path):
        """Values from the CSV are returned unchanged (already MtCO2)."""
        csv_path = self._write_bunker_csv(
            tmp_path / "bunker_timeseries.csv", [2020, 2021], [366.4, 402.0]
        )
        result = load_bunker_timeseries(csv_path)

        assert result["2020"].iloc[0] == pytest.approx(366.4)
        assert result["2021"].iloc[0] == pytest.approx(402.0)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(DataLoadingError, match="Bunker timeseries CSV not found"):
            load_bunker_timeseries(tmp_path / "nonexistent.csv")

    def test_output_has_string_columns(self, tmp_path):
        csv_path = self._write_bunker_csv(
            tmp_path / "bunker_timeseries.csv", [2020], [100.0]
        )
        result = load_bunker_timeseries(csv_path)

        assert "2020" in result.columns
        assert result.index.name == "source"

    def test_missing_source_column_raises(self, tmp_path):
        """DataLoadingError when 'source' column is absent."""
        bad_csv = tmp_path / "bad_bunker.csv"
        pd.DataFrame({"2020": [100.0]}).to_csv(bad_csv, index=False)

        with pytest.raises(DataLoadingError, match="'source' column not found"):
            load_bunker_timeseries(bad_csv)


# ---------------------------------------------------------------------------
# load_ar6_category_constants
# ---------------------------------------------------------------------------


class TestLoadAr6CategoryConstants:
    """Tests for load_ar6_category_constants."""

    def test_valid_file(self, tmp_path):
        """Valid YAML with all required keys is loaded correctly."""
        import yaml

        constants = {
            "C1": {
                "nz_year_median": 2050,
                "nz_year_min": 2035,
                "nz_year_q25": 2045,
                "nz_year_q75": 2055,
                "nz_year_max": 2070,
                "n_scenarios": 70,
                "n_reaching_nz": 68,
            },
            "C2": {
                "nz_year_median": 2058,
                "nz_year_min": 2040,
                "nz_year_q25": 2052,
                "nz_year_q75": 2065,
                "nz_year_max": 2100,
                "n_scenarios": 106,
                "n_reaching_nz": 95,
            },
        }
        path = tmp_path / "constants.yaml"
        with open(path, "w") as f:
            yaml.dump(constants, f)

        result = load_ar6_category_constants(path)
        assert result["C1"]["nz_year_median"] == 2050
        assert result["C2"]["n_scenarios"] == 106

    def test_missing_file_raises(self, tmp_path):
        """DataLoadingError when file does not exist."""
        with pytest.raises(DataLoadingError, match="not found"):
            load_ar6_category_constants(tmp_path / "nonexistent.yaml")

    def test_missing_required_key_raises(self, tmp_path):
        """DataProcessingError when a category is missing required keys."""
        import yaml

        constants = {
            "C1": {
                "nz_year_min": 2035,
                # missing nz_year_median and n_scenarios
            },
        }
        path = tmp_path / "constants.yaml"
        with open(path, "w") as f:
            yaml.dump(constants, f)

        with pytest.raises(DataProcessingError, match="missing keys"):
            load_ar6_category_constants(path)

    def test_non_mapping_raises(self, tmp_path):
        """DataProcessingError when file content is not a mapping."""
        path = tmp_path / "constants.yaml"
        path.write_text("- item1\n- item2\n")

        with pytest.raises(DataProcessingError, match="does not contain a mapping"):
            load_ar6_category_constants(path)


# ---------------------------------------------------------------------------
# compute_bunker_deduction
# ---------------------------------------------------------------------------


class TestComputeBunkerDeduction:
    """Tests for compute_bunker_deduction."""

    @pytest.fixture
    def bunker_ts(self) -> pd.DataFrame:
        """Bunker timeseries 2020-2023, 1000 MtCO2/yr each year."""
        return _make_timeseries(
            {y: 1000.0 for y in range(2020, 2024)}, row_label="bunkers"
        )

    def test_historical_only(self, bunker_ts):
        """When net_zero_year <= historical_end_year, only historical values used."""
        result = compute_bunker_deduction(
            bunker_ts=bunker_ts,
            start_year=2020,
            net_zero_year=2022,
            historical_end_year=2023,
        )
        assert result == pytest.approx(3000.0)  # 3 × 1000

    def test_historical_plus_extrapolation(self, bunker_ts):
        """When net_zero_year > historical_end_year, last rate is extrapolated."""
        result = compute_bunker_deduction(
            bunker_ts=bunker_ts,
            start_year=2020,
            net_zero_year=2050,
            historical_end_year=2023,
        )
        historical = 4 * 1000.0  # 2020, 2021, 2022, 2023
        future = 1000.0 * (2050 - 2023)  # last rate × 27 years
        assert result == pytest.approx(historical + future)

    def test_full_historical_window(self, bunker_ts):
        """Historical segment respects both start_year and historical_end_year."""
        result = compute_bunker_deduction(
            bunker_ts=bunker_ts,
            start_year=2021,
            net_zero_year=2023,
        )
        assert result == pytest.approx(3000.0)  # 2021, 2022, 2023

    def test_single_year(self, bunker_ts):
        """Single-year range returns that year's value only."""
        result = compute_bunker_deduction(
            bunker_ts=bunker_ts,
            start_year=2020,
            net_zero_year=2020,
        )
        assert result == pytest.approx(1000.0)  # 2020 only

    def test_shorter_nz_year_smaller_deduction(self, bunker_ts):
        """Using a shorter net-zero year reduces the total deduction."""
        result_short = compute_bunker_deduction(
            bunker_ts=bunker_ts,
            start_year=2020,
            net_zero_year=2050,
            historical_end_year=2023,
        )
        result_long = compute_bunker_deduction(
            bunker_ts=bunker_ts,
            start_year=2020,
            net_zero_year=2100,
            historical_end_year=2023,
        )
        assert result_short < result_long


# ---------------------------------------------------------------------------
# process_rcb_to_2020_baseline — regression (no BM LULUCF)
# ---------------------------------------------------------------------------


class TestProcessRcbTo2020BaselineRegression:
    """Regression tests for process_rcb_to_2020_baseline with co2-ffi category."""

    @pytest.fixture
    def ffi_emissions(self) -> pd.DataFrame:
        """World FFI emissions: 9000 MtCO2/yr for 2020-2022."""
        return _make_ffi_emissions({2020: 9000.0, 2021: 9100.0, 2022: 9200.0})

    def test_baseline_at_2020_no_adjustment(self, ffi_emissions):
        """RCB already at 2020: zero rebase, fossil_shift=0."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            bunkers_deduction_mt=0.0,
            lulucf_deduction_mt=0.0,
            verbose=False,
        )
        assert result["rebase_total_mt"] == 0
        assert result["rebase_fossil_mt"] == 0
        assert result["rebase_lulucf_mt"] == 0
        # 400 Gt = 400,000 Mt
        assert result["rcb_2020_mt"] == 400_000

    def test_baseline_2023_fossil_shift_co2ffi(self, ffi_emissions):
        """Baseline at 2023 with co2-ffi: rebase equals fossil-only component."""
        expected_fossil_shift = 9000.0 + 9100.0 + 9200.0  # = 27300

        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            bunkers_deduction_mt=0.0,
            lulucf_deduction_mt=0.0,
            verbose=False,
        )

        assert result["rebase_fossil_mt"] == round(expected_fossil_shift)
        assert result["rebase_lulucf_mt"] == 0
        assert result["rebase_total_mt"] == round(expected_fossil_shift)

    def test_bunkers_deduction_negative(self, ffi_emissions):
        """Bunkers deduction is stored as a negative value."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            bunkers_deduction_mt=47_000.0,
            lulucf_deduction_mt=0.0,
            verbose=False,
        )
        assert result["deduction_bunkers_mt"] == -47_000

    def test_lulucf_deduction_passthrough(self, ffi_emissions):
        """LULUCF deduction is passed through as-is (sign-ready from caller)."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            bunkers_deduction_mt=0.0,
            lulucf_deduction_mt=20_000.0,
            verbose=False,
        )
        # lulucf_deduction_mt is sign-ready: added directly to budget
        assert result["deduction_lulucf_mt"] == 20_000

    def test_net_adjustment_matches_components(self, ffi_emissions):
        """net_adjustment_mt = rebase_total + deduction_bunkers + deduction_lulucf."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            bunkers_deduction_mt=47_000.0,
            lulucf_deduction_mt=20_000.0,
            verbose=False,
        )
        expected_total = (
            result["rebase_total_mt"]
            + result["deduction_bunkers_mt"]
            + result["deduction_lulucf_mt"]
        )
        assert result["net_adjustment_mt"] == expected_total

    def test_output_dict_has_required_keys(self, ffi_emissions):
        """Output must include all required provenance fields."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            verbose=False,
        )
        required_keys = {
            "rcb_2020_mt",
            "rcb_original_value",
            "rcb_original_unit",
            "baseline_year",
            "rebase_total_mt",
            "rebase_fossil_mt",
            "rebase_lulucf_mt",
            "deduction_bunkers_mt",
            "deduction_lulucf_mt",
            "net_adjustment_mt",
        }
        assert required_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# process_rcb_to_2020_baseline — co2 category with actual BM LULUCF rebase
# ---------------------------------------------------------------------------


class TestProcessRcbTo2020BaselineWithCo2Rebase:
    """Tests for co2 emission category including actual BM LULUCF in rebase."""

    @pytest.fixture
    def ffi_emissions(self) -> pd.DataFrame:
        return _make_ffi_emissions({2020: 9000.0, 2021: 9100.0, 2022: 9200.0})

    @pytest.fixture
    def actual_bm_lulucf(self) -> pd.DataFrame:
        """Actual BM LULUCF emissions: 3000 MtCO2/yr for 2020-2022."""
        index = pd.MultiIndex.from_tuples(
            [("World", "Mt * CO2e", "co2-lulucf")],
            names=["iso3c", "unit", "emission-category"],
        )
        data = {"2020": [3000.0], "2021": [3100.0], "2022": [3200.0]}
        return pd.DataFrame(data, index=index)

    def test_co2_rebase_includes_bm_lulucf(self, ffi_emissions, actual_bm_lulucf):
        """co2 rebase includes fossil + actual BM LULUCF."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2",
            world_co2_ffi_emissions=ffi_emissions,
            actual_bm_lulucf_emissions=actual_bm_lulucf,
            bunkers_deduction_mt=0.0,
            lulucf_deduction_mt=0.0,
            verbose=False,
        )
        expected_fossil = 9000.0 + 9100.0 + 9200.0
        expected_lulucf = 3000.0 + 3100.0 + 3200.0
        expected_total_shift = expected_fossil + expected_lulucf

        assert result["rebase_fossil_mt"] == round(expected_fossil)
        assert result["rebase_lulucf_mt"] == round(expected_lulucf)
        assert result["rebase_total_mt"] == round(expected_total_shift)

    def test_co2ffi_rebase_excludes_bm_lulucf(self, ffi_emissions, actual_bm_lulucf):
        """co2-ffi rebase uses fossil only, even when actual BM LULUCF is provided."""
        result_ffi = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            actual_bm_lulucf_emissions=actual_bm_lulucf,
            verbose=False,
        )
        assert result_ffi["rebase_lulucf_mt"] == 0
        expected_fossil = 9000.0 + 9100.0 + 9200.0
        assert result_ffi["rebase_fossil_mt"] == round(expected_fossil)
        assert result_ffi["rebase_total_mt"] == round(expected_fossil)

    def test_co2_rebase_larger_than_ffi_only(self, ffi_emissions, actual_bm_lulucf):
        """co2 rebase (fossil + LULUCF) produces larger rcb_2020_mt than co2-ffi."""
        result_ffi = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            verbose=False,
        )
        result_co2 = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2",
            world_co2_ffi_emissions=ffi_emissions,
            actual_bm_lulucf_emissions=actual_bm_lulucf,
            verbose=False,
        )
        assert result_co2["rcb_2020_mt"] > result_ffi["rcb_2020_mt"]

    def test_baseline_2020_no_rebase_regardless_of_category(
        self, ffi_emissions, actual_bm_lulucf
    ):
        """When baseline == 2020, no rebase needed regardless of emission category."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            emission_category="co2",
            world_co2_ffi_emissions=ffi_emissions,
            actual_bm_lulucf_emissions=actual_bm_lulucf,
            verbose=False,
        )
        assert result["rebase_fossil_mt"] == 0
        assert result["rebase_lulucf_mt"] == 0
        assert result["rebase_total_mt"] == 0

    def test_provenance_fields_present(self, ffi_emissions, actual_bm_lulucf):
        """All provenance fields must be present in output."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2",
            world_co2_ffi_emissions=ffi_emissions,
            actual_bm_lulucf_emissions=actual_bm_lulucf,
            verbose=False,
        )
        assert "rebase_fossil_mt" in result
        assert "rebase_lulucf_mt" in result


# ---------------------------------------------------------------------------
# build_nghgi_world_co2_timeseries
# ---------------------------------------------------------------------------


class TestBuildNghgiWorldCo2Timeseries:
    """Tests for build_nghgi_world_co2_timeseries."""

    def _make_world_ts(
        self, year_values: dict[int, float], category: str
    ) -> pd.DataFrame:
        """Build a world emissions DataFrame with MultiIndex."""
        index = pd.MultiIndex.from_tuples(
            [("World", "Mt * CO2e", category)],
            names=["iso3c", "unit", "emission-category"],
        )
        data = {str(y): [v] for y, v in year_values.items()}
        return pd.DataFrame(data, index=index)

    @pytest.fixture
    def fossil_ts(self) -> pd.DataFrame:
        return self._make_world_ts(
            {1980: 5000.0, 1990: 6000.0, 2000: 7000.0, 2020: 9000.0}, "co2-ffi"
        )

    @pytest.fixture
    def nghgi_ts(self) -> pd.DataFrame:
        """NGHGI available from 1990 only."""
        return _make_timeseries(
            {1990: -400.0, 2000: -500.0, 2020: -600.0}, row_label="nghgi_lulucf"
        )

    @pytest.fixture
    def bunker_ts(self) -> pd.DataFrame:
        return _make_timeseries(
            {1980: 100.0, 1990: 200.0, 2000: 300.0, 2020: 400.0}, row_label="bunkers"
        )

    @pytest.fixture
    def bm_lulucf_ts(self) -> pd.DataFrame:
        return self._make_world_ts(
            {1980: -300.0, 1990: -350.0, 2000: -450.0, 2020: -550.0}, "co2-lulucf"
        )

    def test_pre_1990_uses_bm_fallback(
        self, fossil_ts, nghgi_ts, bunker_ts, bm_lulucf_ts
    ):
        """Pre-1990 years should use BM LULUCF (no NGHGI data)."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )
        # 1980: fossil(5000) + BM_LULUCF(-300) - bunkers(100) = 4600
        assert result["1980"].iloc[0] == pytest.approx(4600.0)

    def test_1990_plus_uses_nghgi(self, fossil_ts, nghgi_ts, bunker_ts, bm_lulucf_ts):
        """1990+ years should use NGHGI LULUCF instead of BM."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )
        # 1990: fossil(6000) + NGHGI(-400) - bunkers(200) = 5400
        assert result["1990"].iloc[0] == pytest.approx(5400.0)
        # 2000: fossil(7000) + NGHGI(-500) - bunkers(300) = 6200
        assert result["2000"].iloc[0] == pytest.approx(6200.0)

    def test_bunkers_subtracted(self, fossil_ts, nghgi_ts, bunker_ts, bm_lulucf_ts):
        """Bunker emissions are subtracted in all years."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )
        # All result values should be less than fossil alone
        for y in ["1980", "1990", "2000", "2020"]:
            assert result[y].iloc[0] < fossil_ts[y].iloc[0]

    def test_emission_category_label_is_co2(
        self, fossil_ts, nghgi_ts, bunker_ts, bm_lulucf_ts
    ):
        """Output emission-category label should be 'co2'."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )
        assert result.index.get_level_values("emission-category")[0] == "co2"

    def test_index_structure_matches_fossil_ts(
        self, fossil_ts, nghgi_ts, bunker_ts, bm_lulucf_ts
    ):
        """Output index structure matches fossil_ts (same names, same iso3c/unit)."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            bm_lulucf_ts=bm_lulucf_ts,
        )
        assert result.index.names == fossil_ts.index.names
        assert result.index.get_level_values("iso3c")[0] == "World"
        assert result.index.get_level_values("unit")[0] == "Mt * CO2e"


# ---------------------------------------------------------------------------
# _resolve_adjustment_scalars — precautionary LULUCF cap
# ---------------------------------------------------------------------------


class TestPrecautionaryLulucfCap:
    """Tests for the precautionary_lulucf cap in _resolve_adjustment_scalars.

    For co2-ffi: integrates per-year BM LULUCF timeseries from baseline_year
    to net_zero_year. When precautionary_lulucf=True (default), net sinks
    (negative cumulative) cannot increase the fossil budget. Net sources
    (positive cumulative) still reduce it.

    For co2: uses pre-computed convention gap from rcb_adjustments dict.
    """

    @pytest.fixture
    def bunker_ts(self) -> pd.DataFrame:
        """Bunker timeseries: 1000 MtCO2/yr."""
        return _make_timeseries(
            {y: 1000.0 for y in range(2020, 2051)}, row_label="bunkers"
        )

    @pytest.fixture
    def lulucf_shift_sink(self) -> pd.DataFrame:
        """Per-year BM LULUCF median: net sink (-100 MtCO2/yr for 2020-2050)."""
        values = {y: -100.0 for y in range(2020, 2051)}
        return _make_timeseries(values, row_label="lulucf_shift_median")

    @pytest.fixture
    def lulucf_shift_source(self) -> pd.DataFrame:
        """Per-year BM LULUCF median: net source (+100 MtCO2/yr for 2020-2050)."""
        values = {y: 100.0 for y in range(2020, 2051)}
        return _make_timeseries(values, row_label="lulucf_shift_median")

    @pytest.fixture
    def rcb_adj(self) -> dict[str, dict]:
        """Pre-computed adjustments (convention gap used for co2 only)."""
        return {
            "1.5p50": {
                "bm_lulucf_cumulative_median": -3100.0,
                "convention_gap_median": -5000.0,
                "nz_year_median": 2050,
                "n_scenarios": 10,
            }
        }

    def test_sink_capped_to_zero_with_precautionary(
        self, bunker_ts, lulucf_shift_sink, rcb_adj
    ):
        """When BM is a sink, precautionary cap sets lulucf_mt to 0."""
        _, lulucf_mt = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_sink,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=True,
            verbose=False,
        )
        assert lulucf_mt == 0.0

    def test_source_still_reduces_budget_with_precautionary(
        self, bunker_ts, lulucf_shift_source, rcb_adj
    ):
        """When BM is a source, precautionary cap still reduces fossil budget."""
        _, lulucf_mt = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_source,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=True,
            verbose=False,
        )
        assert lulucf_mt < 0.0
        # 31 years (2020-2050 inclusive) * 100 = 3100
        assert lulucf_mt == pytest.approx(-3100.0)

    def test_sink_increases_budget_without_precautionary(
        self, bunker_ts, lulucf_shift_sink, rcb_adj
    ):
        """When precautionary is off, BM sink increases fossil budget."""
        _, lulucf_mt = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_sink,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        # bm_lulucf_mt = sum(-100 * 31) = -3100, lulucf_mt = -(-3100) = 3100
        assert lulucf_mt > 0.0
        assert lulucf_mt == pytest.approx(3100.0)

    def test_co2_category_unaffected_by_precautionary(
        self, bunker_ts, lulucf_shift_sink, rcb_adj
    ):
        """Precautionary cap only applies to co2-ffi, not co2."""
        _, lulucf_on = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_sink,
            rcb_adjustments=rcb_adj,
            emission_category="co2",
            precautionary_lulucf=True,
            verbose=False,
        )
        _, lulucf_off = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_sink,
            rcb_adjustments=rcb_adj,
            emission_category="co2",
            precautionary_lulucf=False,
            verbose=False,
        )
        assert lulucf_on == lulucf_off

    def test_bunkers_unaffected_by_precautionary(
        self, bunker_ts, lulucf_shift_sink, rcb_adj
    ):
        """Bunker deduction is identical regardless of precautionary setting."""
        bunkers_on, _ = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_sink,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=True,
            verbose=False,
        )
        bunkers_off, _ = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_sink,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        assert bunkers_on == bunkers_off


# ---------------------------------------------------------------------------
# _resolve_adjustment_scalars — baseline-aware LULUCF integration
# ---------------------------------------------------------------------------


class TestBaselineAwareLulucfIntegration:
    """Tests that LULUCF integration in _resolve_adjustment_scalars is
    baseline-aware: starting from baseline_year, not always 2020.

    When baseline_year > 2020, the years before baseline_year are excluded
    from the LULUCF integration, resulting in a different deduction.
    """

    @pytest.fixture
    def bunker_ts(self) -> pd.DataFrame:
        """Bunker timeseries: 1000 MtCO2/yr."""
        return _make_timeseries(
            {y: 1000.0 for y in range(2020, 2061)}, row_label="bunkers"
        )

    @pytest.fixture
    def lulucf_shift_ts(self) -> pd.DataFrame:
        """Per-year BM LULUCF median with varying values 2020-2060.

        Values increase linearly: year 2020 = 100, 2021 = 110, ..., so
        different baseline years give different cumulative sums.
        """
        values = {y: 100.0 + 10.0 * (y - 2020) for y in range(2020, 2061)}
        return _make_timeseries(values, row_label="lulucf_shift_median")

    @pytest.fixture
    def rcb_adj(self) -> dict[str, dict]:
        """Pre-computed adjustments (only convention_gap used for co2)."""
        return {
            "1.5p50": {
                "bm_lulucf_cumulative_median": -5000.0,
                "convention_gap_median": -2000.0,
                "nz_year_median": 2050,
                "n_scenarios": 10,
            }
        }

    def test_baseline_2023_excludes_early_years(
        self, bunker_ts, lulucf_shift_ts, rcb_adj
    ):
        """baseline_year=2023 excludes 2020-2022 from LULUCF integration."""
        _, lulucf_2020 = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_ts,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        _, lulucf_2023 = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2023,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_ts,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        # Both should be negative (negated positive source)
        # The 2023 baseline excludes 2020(100), 2021(110), 2022(120) = 330 Mt
        # so the cumulative from 2023 is smaller, and the negated result differs
        assert lulucf_2020 != lulucf_2023

    def test_baseline_2020_vs_2023_magnitude(self, bunker_ts, lulucf_shift_ts, rcb_adj):
        """baseline_year=2020 integrates more years, so abs(lulucf) is larger."""
        _, lulucf_2020 = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2020,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_ts,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        _, lulucf_2023 = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2023,
            net_zero_year=2050,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_ts,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        # All per-year values are positive, so cumulative is positive,
        # and negated lulucf is negative. More years = more negative.
        assert abs(lulucf_2020) > abs(lulucf_2023)

    def test_exact_integration_from_baseline(self, bunker_ts, lulucf_shift_ts, rcb_adj):
        """Verify exact LULUCF value from baseline_year=2023 to NZ=2025."""
        _, lulucf_mt = _resolve_adjustment_scalars(
            scenario="1.5p50",
            baseline_year=2023,
            net_zero_year=2025,
            bunker_ts=bunker_ts,
            lulucf_shift_ts=lulucf_shift_ts,
            rcb_adjustments=rcb_adj,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        # Years 2023, 2024, 2025:
        #   2023 = 100 + 10*3 = 130
        #   2024 = 100 + 10*4 = 140
        #   2025 = 100 + 10*5 = 150
        # Sum = 420, negated = -420
        expected_sum = 130.0 + 140.0 + 150.0
        assert lulucf_mt == pytest.approx(-expected_sum)
