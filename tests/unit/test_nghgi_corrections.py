"""
Unit tests for NGHGI correction utilities (nghgi.py) and related changes to rcb.py.

Tests cover:
- Loader functions (NGHGI LULUCF, bunker timeseries, AR6 category constants)
- Cumulative emission computation
- Bunker deduction
- Scenario-to-AR6-category mapping
- process_rcb_to_2020_baseline() with BM Direct LULUCF shift
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

    def test_full_years_to_the_net_zero_crossing(self, bunker_ts):
        """Hand calculation: full years from the start year to the crossing.

        1000 Mt each year: 2020 to 2022 gives 2 x 1000, 2021 to 2023 gives
        2 x 1000, and a crossing at the start year gives 0. After the last
        observed year (2023) the rate holds: 2020 to 2050 gives 30 x 1000.
        """
        assert compute_bunker_deduction(bunker_ts, 2020, 2022) == pytest.approx(2000)
        assert compute_bunker_deduction(bunker_ts, 2021, 2023) == pytest.approx(2000)
        assert compute_bunker_deduction(bunker_ts, 2020, 2020) == 0.0
        assert compute_bunker_deduction(bunker_ts, 2020, 2050) == pytest.approx(30000)

    def test_end_year_comes_from_the_data(self):
        """Observed 800 to 1200 Mt in 2020-2024, then the 2024 rate.

        2020-2024: 5000; 2025-2029 at the 2024 rate: 5 x 1200. A crossing in
        2024.5 sums 2020-2023 (3800) and half of 2024: 3800 + 600.
        """
        observed_to_2024 = _make_timeseries(
            {2020: 800.0, 2021: 900.0, 2022: 1000.0, 2023: 1100.0, 2024: 1200.0},
            row_label="bunkers",
        )
        result = compute_bunker_deduction(observed_to_2024, 2020, 2030)
        assert result == pytest.approx(5000.0 + 6000.0)
        assert compute_bunker_deduction(
            observed_to_2024, 2020, 2024.5
        ) == pytest.approx(4400.0)

    def test_scenario_pathway_after_observed_then_median_over_nz_years(self, bunker_ts):
        """Observed 2020-2023 at 1000, then the scenario pathway at 500.

        2020-2023: 4000, then 500 a year: net zero in 2025, 2030.5 and 2040
        gives 4500, 7250 and 12000. The median is 7250.
        """
        pathway = pd.Series({str(y): 500.0 for y in range(2020, 2101)})
        result = compute_bunker_deduction(
            bunker_ts=bunker_ts,
            start_year=2020,
            net_zero_year=[2025, 2030.5, 2040],
            scenario_pathway=pathway,
        )
        assert result == pytest.approx(7250.0)
        with pytest.raises(DataProcessingError, match="lacks 2031-2040"):
            compute_bunker_deduction(
                bunker_ts, 2020, [2040], scenario_pathway=pathway[:"2030"]
            )

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
            lulucf_future_deduction_mt=0.0,
            verbose=False,
        )
        assert result["rebase_total_mt"] == 0
        assert result["rebase_fossil_mt"] == 0
        assert result["rebase_lulucf_mt"] == 0
        # 400 Gt = 400,000 Mt
        assert result["rcb_2020_nghgi_mt"] == 400_000

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
            lulucf_future_deduction_mt=0.0,
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
            lulucf_future_deduction_mt=0.0,
            verbose=False,
        )
        assert result["deduction_bunkers_mt"] == -47_000

    def test_lulucf_future_deduction_passthrough(self, ffi_emissions):
        """LULUCF future deduction is passed through as-is (sign-ready)."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            bunkers_deduction_mt=0.0,
            lulucf_future_deduction_mt=20_000.0,
            verbose=False,
        )
        assert result["deduction_lulucf_future_mt"] == 20_000
        assert result["correction_lulucf_nghgi_mt"] == 0

    def test_net_adjustment_matches_components(self, ffi_emissions):
        """net_adjustment_mt = rebase + bunkers + future + nghgi_correction."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            world_bunker_emissions=_make_timeseries(
                {2020: 800.0, 2021: 900.0, 2022: 1000.0}
            ),
            bunkers_deduction_mt=47_000.0,
            lulucf_future_deduction_mt=20_000.0,
            verbose=False,
        )
        assert result["rebase_bunkers_mt"] == 2_700
        assert result["rebase_total_mt"] == 27_300 + 2_700
        expected_total = (
            result["rebase_total_mt"]
            + result["deduction_bunkers_mt"]
            + result["deduction_lulucf_future_mt"]
            + result["correction_lulucf_nghgi_mt"]
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
            "rcb_2020_nghgi_mt",
            "rcb_original_value",
            "rcb_original_unit",
            "baseline_year",
            "rebase_total_mt",
            "rebase_fossil_mt",
            "rebase_bunkers_mt",
            "rebase_lulucf_mt",
            "deduction_bunkers_mt",
            "deduction_lulucf_future_mt",
            "correction_lulucf_nghgi_mt",
            "net_adjustment_mt",
        }
        assert required_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# process_rcb_to_2020_baseline — co2 category with NGHGI LULUCF rebase
# ---------------------------------------------------------------------------


class TestProcessRcbTo2020BaselineWithCo2Rebase:
    """Tests for co2 emission category including observed NGHGI LULUCF in rebase."""

    @pytest.fixture
    def ffi_emissions(self) -> pd.DataFrame:
        return _make_ffi_emissions({2020: 9000.0, 2021: 9100.0, 2022: 9200.0})

    @pytest.fixture
    def nghgi_lulucf(self) -> pd.DataFrame:
        """Observed NGHGI LULUCF emissions: 3000 to 3200 MtCO2/yr for 2020-2022."""
        index = pd.MultiIndex.from_tuples(
            [("World", "Mt * CO2e", "co2-lulucf")],
            names=["iso3c", "unit", "emission-category"],
        )
        data = {"2020": [3000.0], "2021": [3100.0], "2022": [3200.0]}
        return pd.DataFrame(data, index=index)

    def test_co2_rebase_includes_nghgi_lulucf(self, ffi_emissions, nghgi_lulucf):
        """co2 rebase includes fossil + observed NGHGI LULUCF."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2",
            world_co2_ffi_emissions=ffi_emissions,
            world_nghgi_lulucf_emissions=nghgi_lulucf,
            bunkers_deduction_mt=0.0,
            lulucf_future_deduction_mt=0.0,
            verbose=False,
        )
        expected_fossil = 9000.0 + 9100.0 + 9200.0
        expected_lulucf = 3000.0 + 3100.0 + 3200.0
        expected_total_shift = expected_fossil + expected_lulucf

        assert result["rebase_fossil_mt"] == round(expected_fossil)
        assert result["rebase_lulucf_mt"] == round(expected_lulucf)
        assert result["rebase_total_mt"] == round(expected_total_shift)

    def test_co2ffi_rebase_excludes_nghgi_lulucf(self, ffi_emissions, nghgi_lulucf):
        """co2-ffi rebase uses fossil only, even when NGHGI LULUCF is provided."""
        result_ffi = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=ffi_emissions,
            world_nghgi_lulucf_emissions=nghgi_lulucf,
            verbose=False,
        )
        assert result_ffi["rebase_lulucf_mt"] == 0
        expected_fossil = 9000.0 + 9100.0 + 9200.0
        assert result_ffi["rebase_fossil_mt"] == round(expected_fossil)
        assert result_ffi["rebase_total_mt"] == round(expected_fossil)

    def test_co2_rebase_larger_than_ffi_only(self, ffi_emissions, nghgi_lulucf):
        """co2 rebase (fossil + LULUCF) produces larger rcb_2020_nghgi_mt than co2-ffi."""
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
            world_nghgi_lulucf_emissions=nghgi_lulucf,
            verbose=False,
        )
        assert result_co2["rcb_2020_nghgi_mt"] > result_ffi["rcb_2020_nghgi_mt"]

    def test_baseline_2020_no_rebase_regardless_of_category(
        self, ffi_emissions, nghgi_lulucf
    ):
        """When baseline == 2020, no rebase needed regardless of emission category."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            emission_category="co2",
            world_co2_ffi_emissions=ffi_emissions,
            world_nghgi_lulucf_emissions=nghgi_lulucf,
            verbose=False,
        )
        assert result["rebase_fossil_mt"] == 0
        assert result["rebase_lulucf_mt"] == 0
        assert result["rebase_total_mt"] == 0

    def test_provenance_fields_present(self, ffi_emissions, nghgi_lulucf):
        """All provenance fields must be present in output."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            emission_category="co2",
            world_co2_ffi_emissions=ffi_emissions,
            world_nghgi_lulucf_emissions=nghgi_lulucf,
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

    def test_pre_nghgi_years_are_nan(self, fossil_ts, nghgi_ts):
        """Years outside NGHGI coverage should be NaN (no BM fallback)."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
        )
        # 1980: no NGHGI data -> NaN
        assert pd.isna(result["1980"].iloc[0])

    def test_world_co2_is_fossil_plus_nghgi_lulucf(self, fossil_ts, nghgi_ts):
        """World CO2 = fossil + NGHGI LULUCF. The fossil series excludes bunkers."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
        )
        # 1990: fossil(6000) + NGHGI(-400) = 5600
        assert result["1990"].iloc[0] == pytest.approx(5600.0)
        # 2000: fossil(7000) + NGHGI(-500) = 6500
        assert result["2000"].iloc[0] == pytest.approx(6500.0)
        # 2020: fossil(9000) + NGHGI(-600) = 8400
        assert result["2020"].iloc[0] == pytest.approx(8400.0)

    def test_emission_category_label_is_co2(self, fossil_ts, nghgi_ts):
        """Output emission-category label should be 'co2'."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
        )
        assert result.index.get_level_values("emission-category")[0] == "co2"

    def test_index_structure_matches_fossil_ts(self, fossil_ts, nghgi_ts):
        """Output index structure matches fossil_ts (same names, same iso3c/unit)."""
        result = build_nghgi_world_co2_timeseries(
            fossil_ts=fossil_ts,
            nghgi_ts=nghgi_ts,
        )
        assert result.index.names == fossil_ts.index.names
        assert result.index.get_level_values("iso3c")[0] == "World"
        assert result.index.get_level_values("unit")[0] == "Mt * CO2e"


# ---------------------------------------------------------------------------
# _resolve_adjustment_scalars — precautionary LULUCF cap, per-baseline terms
# ---------------------------------------------------------------------------


class TestResolveAdjustmentScalars:
    """The LULUCF term of a budget is read for its baseline year and capped.

    co2-ffi: ``bm_lulucf_median_from[baseline]`` is the median BM LULUCF from
    the baseline year to net zero. With the precautionary cap a sink cannot
    raise the fossil budget; a source still lowers it. co2 reads
    ``convention_gap_median_from[baseline]`` and ignores the cap.
    """

    @staticmethod
    def _resolve(bm_from, category, precautionary, baseline=2020):
        adjustments = {
            "b:1.5p50": {
                "bm_lulucf_median_from": bm_from,
                "convention_gap_median_from": {2020: -5000.0, 2023: -4000.0},
            }
        }
        return _resolve_adjustment_scalars(
            budget_key="b:1.5p50",
            baseline_year=baseline,
            rcb_adjustments=adjustments,
            emission_category=category,
            precautionary_lulucf=precautionary,
            verbose=False,
        )

    @pytest.mark.parametrize(
        ("bm", "precautionary", "expected"),
        [(-3100.0, True, 0.0), (3100.0, True, -3100.0), (-3100.0, False, 3100.0)],
    )
    def test_precautionary_cap(self, bm, precautionary, expected):
        future, gap = self._resolve({2020: bm}, "co2-ffi", precautionary)
        assert future == pytest.approx(expected)
        assert gap == 0.0

    def test_terms_are_read_for_the_baseline_year(self):
        bm_from = {2020: 500.0, 2023: 200.0}
        assert self._resolve(bm_from, "co2-ffi", True, 2023)[0] == -200.0
        assert self._resolve(bm_from, "co2", True, 2023)[1] == -4000.0
        assert self._resolve(bm_from, "co2", False, 2023)[1] == -4000.0
        with pytest.raises(DataLoadingError, match="baseline year 2024"):
            self._resolve(bm_from, "co2-ffi", True, 2024)
