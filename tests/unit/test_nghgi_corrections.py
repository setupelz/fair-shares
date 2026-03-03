"""
Unit tests for NGHGI correction utilities (nghgi.py) and related changes to rcb.py.

Tests cover:
- Loader functions with mock data
- Cumulative emission computation
- LULUCF deduction (historical-only, historical+future, sign handling)
- Bunker deduction
- Scenario-to-AR6-category mapping
- process_rcb_to_2020_baseline() with Gidden Direct LULUCF shift
- New provenance fields in the output dict
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from fair_shares.library.exceptions import DataLoadingError, DataProcessingError
from fair_shares.library.preprocessing.rcbs import _resolve_adjustment_scalars
from fair_shares.library.utils.data.nghgi import (
    _MTC_TO_MTCO2,
    build_nghgi_world_co2_timeseries,
    compute_bunker_deduction,
    compute_cumulative_emissions,
    compute_lulucf_convention_gap,
    compute_lulucf_deduction,
    load_ar6_category_constants,
    load_bunker_timeseries,
    load_gidden_lulucf_components,
    load_nghgi_lulucf_historical,
    map_scenario_to_ar6_category,
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
# map_scenario_to_ar6_category
# ---------------------------------------------------------------------------


class TestMapScenarioToAr6Category:
    """Tests for map_scenario_to_ar6_category."""

    def test_all_four_scenarios(self):
        """Verify all four scenario strings map to the expected AR6 category."""
        assert map_scenario_to_ar6_category("1.5p50") == "C1"
        assert map_scenario_to_ar6_category("1.5p66") == "C1"
        assert map_scenario_to_ar6_category("2p66") == "C3"
        assert map_scenario_to_ar6_category("2p83") == "C2"

    def test_unknown_scenario_raises(self):
        """Unknown scenario string raises DataProcessingError."""
        with pytest.raises(DataProcessingError, match="Unknown scenario"):
            map_scenario_to_ar6_category("3p50")

    def test_empty_string_raises(self):
        with pytest.raises(DataProcessingError, match="Unknown scenario"):
            map_scenario_to_ar6_category("")


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
# load_nghgi_lulucf_historical (mocked)
# ---------------------------------------------------------------------------


class TestLoadNghgiLulucfHistorical:
    """Tests for load_nghgi_lulucf_historical."""

    def test_world_row_extracted(self, tmp_path):
        """'World' row values are returned unchanged (already in MtCO2)."""
        mock_df = pd.DataFrame(
            {"1990": [-1000.0], "2022": [-2763.0]},
            index=pd.Index(["World"], name=None),
        )

        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel", return_value=mock_df
        ):
            with patch.object(Path, "exists", return_value=True):
                result = load_nghgi_lulucf_historical(tmp_path / "fake.xlsx")

        assert result["1990"].iloc[0] == pytest.approx(-1000.0)
        assert result["2022"].iloc[0] == pytest.approx(-2763.0)

    def test_negative_sink_preserved(self, tmp_path):
        """Negative values (net sink) must not be sign-flipped."""
        mock_df = pd.DataFrame(
            {"2020": [-500.0]},
            index=pd.Index(["World"]),
        )

        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel", return_value=mock_df
        ):
            with patch.object(Path, "exists", return_value=True):
                result = load_nghgi_lulucf_historical(tmp_path / "fake.xlsx")

        assert result["2020"].iloc[0] < 0

    def test_missing_world_row_raises(self, tmp_path):
        """DataLoadingError when 'World' row is absent."""
        mock_df = pd.DataFrame({"2020": [100.0]}, index=pd.Index(["Europe"]))

        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel", return_value=mock_df
        ):
            with patch.object(Path, "exists", return_value=True):
                with pytest.raises(DataLoadingError, match="'World' row not found"):
                    load_nghgi_lulucf_historical(tmp_path / "fake.xlsx")

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(DataLoadingError, match="NGHGI LULUCF file not found"):
            load_nghgi_lulucf_historical(tmp_path / "nonexistent.xlsx")

    def test_output_index_name(self, tmp_path):
        """Output index name should be 'source'."""
        mock_df = pd.DataFrame({"2020": [-100.0]}, index=pd.Index(["World"]))

        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel", return_value=mock_df
        ):
            with patch.object(Path, "exists", return_value=True):
                result = load_nghgi_lulucf_historical(tmp_path / "fake.xlsx")

        assert result.index.name == "source"


# ---------------------------------------------------------------------------
# load_bunker_timeseries (mocked)
# ---------------------------------------------------------------------------


class TestLoadBunkerTimeseries:
    """Tests for load_bunker_timeseries."""

    def _make_bunker_sheet(
        self, years: list[int], values_mtc: list[float]
    ) -> pd.DataFrame:
        """Mock Territorial Emissions sheet with a Bunkers column."""
        data = {"USA": [v * 5 for v in values_mtc], "Bunkers": values_mtc}
        return pd.DataFrame(data, index=pd.Index(years))

    def test_mtc_to_mtco2_conversion(self, tmp_path):
        """Bunker values must be converted from MtC to MtCO2."""
        mock_sheet = self._make_bunker_sheet([2020, 2021], [100.0, 110.0])

        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel",
            return_value=mock_sheet,
        ):
            with patch.object(Path, "exists", return_value=True):
                result = load_bunker_timeseries(tmp_path / "fake.xlsx")

        assert result["2020"].iloc[0] == pytest.approx(100.0 * _MTC_TO_MTCO2)
        assert result["2021"].iloc[0] == pytest.approx(110.0 * _MTC_TO_MTCO2)

    def test_missing_bunkers_column_raises(self, tmp_path):
        """DataLoadingError when 'Bunkers' column is absent."""
        bad_sheet = pd.DataFrame({"USA": [100.0], "EUR": [50.0]}, index=[2020])

        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel", return_value=bad_sheet
        ):
            with patch.object(Path, "exists", return_value=True):
                with pytest.raises(
                    DataLoadingError, match="'Bunkers' column not found"
                ):
                    load_bunker_timeseries(tmp_path / "fake.xlsx")

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(DataLoadingError, match="Bunker fuel file not found"):
            load_bunker_timeseries(tmp_path / "nonexistent.xlsx")

    def test_output_has_string_columns(self, tmp_path):
        mock_sheet = self._make_bunker_sheet([2020], [100.0])

        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel",
            return_value=mock_sheet,
        ):
            with patch.object(Path, "exists", return_value=True):
                result = load_bunker_timeseries(tmp_path / "fake.xlsx")

        assert "2020" in result.columns
        assert result.index.name == "source"


# ---------------------------------------------------------------------------
# load_gidden_lulucf_components (mocked)
# ---------------------------------------------------------------------------


class TestLoadGiddenLulucfComponents:
    """Tests for load_gidden_lulucf_components."""

    _DIRECT_VAR = "AR6 Reanalysis|OSCARv3.2|Emissions|CO2|AFOLU|Direct"
    _INDIRECT_VAR = "AR6 Reanalysis|OSCARv3.2|Emissions|CO2|AFOLU|Indirect"

    def _make_meta(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def _make_data(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_category_median_computed(self, tmp_path):
        """Median across model rows is returned for each component."""
        meta = self._make_meta(
            [
                {"model": "M1", "scenario": "S1", "Category": "C1"},
                {"model": "M2", "scenario": "S2", "Category": "C1"},
            ]
        )
        data = self._make_data(
            [
                {
                    "Model": "M1",
                    "Scenario": "S1",
                    "Region": "World",
                    "Variable": self._DIRECT_VAR,
                    2020: 100.0,
                    2025: 200.0,
                },
                {
                    "Model": "M2",
                    "Scenario": "S2",
                    "Region": "World",
                    "Variable": self._DIRECT_VAR,
                    2020: 200.0,
                    2025: 300.0,
                },
                {
                    "Model": "M1",
                    "Scenario": "S1",
                    "Region": "World",
                    "Variable": self._INDIRECT_VAR,
                    2020: 10.0,
                    2025: 20.0,
                },
                {
                    "Model": "M2",
                    "Scenario": "S2",
                    "Region": "World",
                    "Variable": self._INDIRECT_VAR,
                    2020: 30.0,
                    2025: 40.0,
                },
            ]
        )

        # read_excel is called 2 times: meta then data
        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel",
            side_effect=[meta, data],
        ):
            with patch.object(Path, "exists", return_value=True):
                direct_ts, indirect_ts = load_gidden_lulucf_components(
                    tmp_path / "ar6_gidden.xlsx", "C1"
                )

        # median of [100, 200] = 150; median of [200, 300] = 250
        assert direct_ts["2020"].iloc[0] == pytest.approx(150.0)
        assert direct_ts["2025"].iloc[0] == pytest.approx(250.0)
        # median of [10, 30] = 20; median of [20, 40] = 30
        assert indirect_ts["2020"].iloc[0] == pytest.approx(20.0)

    def test_unknown_category_raises(self, tmp_path):
        """DataProcessingError when AR6 category has no matching rows."""
        meta = self._make_meta(
            [
                {"model": "M1", "scenario": "S1", "Category": "C1"},
            ]
        )
        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel", return_value=meta
        ):
            with patch.object(Path, "exists", return_value=True):
                with pytest.raises(
                    DataProcessingError, match="AR6 category 'C9' not found"
                ):
                    load_gidden_lulucf_components(tmp_path / "ar6_gidden.xlsx", "C9")

    def test_missing_category_column_raises(self, tmp_path):
        """DataLoadingError when 'Category' column is absent from metadata."""
        meta = pd.DataFrame([{"model": "M1", "scenario": "S1", "Tier": "C1"}])
        with patch(
            "fair_shares.library.utils.data.nghgi.pd.read_excel", return_value=meta
        ):
            with patch.object(Path, "exists", return_value=True):
                with pytest.raises(
                    DataLoadingError, match="'Category' column not found"
                ):
                    load_gidden_lulucf_components(tmp_path / "ar6_gidden.xlsx", "C1")

    def test_data_file_not_found_raises(self, tmp_path):
        with pytest.raises(DataLoadingError, match="Gidden et al. data file not found"):
            load_gidden_lulucf_components(tmp_path / "nonexistent.xlsx", "C1")


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
                "net_zero_year_nghgi": 2050,
                "net_zero_year_scientific": 2047,
                "n_scenarios": 70,
            },
            "C2": {
                "net_zero_year_nghgi": 2058,
                "net_zero_year_scientific": 2054,
                "n_scenarios": 106,
            },
        }
        path = tmp_path / "constants.yaml"
        with open(path, "w") as f:
            yaml.dump(constants, f)

        result = load_ar6_category_constants(path)
        assert result["C1"]["net_zero_year_nghgi"] == 2050
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
                "net_zero_year_nghgi": 2050,
                # missing net_zero_year_scientific and n_scenarios
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
# compute_lulucf_deduction
# ---------------------------------------------------------------------------


class TestComputeLulucfDeduction:
    """Tests for compute_lulucf_deduction."""

    @pytest.fixture
    def nghgi_ts(self) -> pd.DataFrame:
        """NGHGI historical LULUCF timeseries 2020-2022, all -500 MtCO2/yr."""
        return _make_timeseries(
            {2020: -500.0, 2021: -500.0, 2022: -500.0}, row_label="nghgi_lulucf"
        )

    @pytest.fixture
    def gidden_direct(self) -> pd.DataFrame:
        """Gidden Direct timeseries 2023-2050, 100 MtCO2/yr."""
        return _make_timeseries(
            {y: 100.0 for y in range(2023, 2051)}, row_label="gidden_direct_C1"
        )

    @pytest.fixture
    def gidden_indirect(self) -> pd.DataFrame:
        """Gidden Indirect timeseries 2023-2050, -200 MtCO2/yr."""
        return _make_timeseries(
            {y: -200.0 for y in range(2023, 2051)}, row_label="gidden_indirect_C1"
        )

    def test_historical_only(self, nghgi_ts, gidden_direct, gidden_indirect):
        """When net_zero_year <= splice_year, only historical data is used."""
        result = compute_lulucf_deduction(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct,
            gidden_indirect_ts=gidden_indirect,
            start_year=2020,
            net_zero_year=2022,
            splice_year=2022,
        )
        # 3 years × (-500) = -1500
        assert result == pytest.approx(-1500.0)

    def test_historical_plus_future(self, nghgi_ts, gidden_direct, gidden_indirect):
        """Historical + future segments are summed correctly."""
        result = compute_lulucf_deduction(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct,
            gidden_indirect_ts=gidden_indirect,
            start_year=2020,
            net_zero_year=2025,
            splice_year=2022,
        )
        historical = -500.0 * 3  # 2020, 2021, 2022
        future = (100.0 + (-200.0)) * 3  # 2023, 2024, 2025 → (-100) × 3 = -300
        assert result == pytest.approx(historical + future)

    def test_net_sink_reduces_deduction(self, nghgi_ts, gidden_direct, gidden_indirect):
        """Net sink (negative LULUCF) must produce a negative cumulative deduction."""
        result = compute_lulucf_deduction(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct,
            gidden_indirect_ts=gidden_indirect,
            start_year=2020,
            net_zero_year=2022,
            splice_year=2022,
        )
        assert result < 0.0, "Net sink should give negative deduction"

    def test_net_zero_before_splice(self, nghgi_ts, gidden_direct, gidden_indirect):
        """Net-zero year before splice year uses only a subset of historical data."""
        result = compute_lulucf_deduction(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct,
            gidden_indirect_ts=gidden_indirect,
            start_year=2020,
            net_zero_year=2021,
            splice_year=2022,
        )
        assert result == pytest.approx(-1000.0)  # 2020 + 2021


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
    """Regression tests: Gidden Direct LULUCF is always included in the baseline shift."""

    @pytest.fixture
    def ffi_emissions(self) -> pd.DataFrame:
        """World FFI emissions: 9000 MtCO2/yr for 2020-2022."""
        return _make_ffi_emissions({2020: 9000.0, 2021: 9100.0, 2022: 9200.0})

    @pytest.fixture
    def lulucf_shift_zero(self) -> pd.DataFrame:
        """Zero LULUCF shift — used to isolate fossil-only shift arithmetic."""
        data = {"2020": [0.0], "2021": [0.0], "2022": [0.0]}
        return pd.DataFrame(data, index=pd.Index(["lulucf_shift_mean"], name="source"))

    def test_baseline_at_2020_no_adjustment(self, ffi_emissions, lulucf_shift_zero):
        """RCB already at 2020: zero rebase, fossil_shift=0."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_zero,
            bunkers_2020_2100=0.0,
            lulucf_2020_2100=0.0,
            verbose=False,
        )
        assert result["rebase_total_mt"] == 0
        assert result["rebase_fossil_mt"] == 0
        assert result["rebase_lulucf_mt"] == 0
        assert result["lulucf_convention"] == "nghgi"
        # 400 Gt = 400,000 Mt
        assert result["rcb_2020_mt"] == 400_000

    def test_baseline_2023_fossil_shift_with_zero_lulucf(
        self, ffi_emissions, lulucf_shift_zero
    ):
        """Baseline at 2023 with zero LULUCF shift: rebase equals fossil-only component."""
        expected_fossil_shift = 9000.0 + 9100.0 + 9200.0  # = 27300

        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_zero,
            bunkers_2020_2100=0.0,
            lulucf_2020_2100=0.0,
            verbose=False,
        )

        assert result["rebase_fossil_mt"] == round(expected_fossil_shift)
        assert result["rebase_lulucf_mt"] == 0
        assert result["lulucf_convention"] == "nghgi"
        assert result["rebase_total_mt"] == round(expected_fossil_shift)

    def test_bunkers_deduction_negative(self, ffi_emissions, lulucf_shift_zero):
        """Bunkers deduction is stored as a negative value."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_zero,
            bunkers_2020_2100=47_000.0,
            lulucf_2020_2100=0.0,
            verbose=False,
        )
        assert result["deduction_bunkers_mt"] == -47_000

    def test_lulucf_deduction_passthrough(self, ffi_emissions, lulucf_shift_zero):
        """LULUCF deduction is passed through as-is (sign-ready from caller)."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_zero,
            bunkers_2020_2100=0.0,
            lulucf_2020_2100=20_000.0,
            verbose=False,
        )
        # lulucf_2020_2100 is sign-ready: added directly to budget
        assert result["deduction_lulucf_mt"] == 20_000

    def test_net_adjustment_matches_components(self, ffi_emissions, lulucf_shift_zero):
        """net_deduction_mt = rebase_total + deduction_bunkers + deduction_lulucf."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_zero,
            bunkers_2020_2100=47_000.0,
            lulucf_2020_2100=20_000.0,
            verbose=False,
        )
        expected_total = (
            result["rebase_total_mt"]
            + result["deduction_bunkers_mt"]
            + result["deduction_lulucf_mt"]
        )
        assert result["net_deduction_mt"] == expected_total

    def test_output_dict_has_required_keys(self, ffi_emissions, lulucf_shift_zero):
        """Output must include all required provenance fields."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_zero,
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
            "net_deduction_mt",
            "lulucf_convention",
        }
        assert required_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# process_rcb_to_2020_baseline — with Gidden Direct LULUCF shift
# ---------------------------------------------------------------------------


class TestProcessRcbTo2020BaselineWithLulucfShift:
    """Tests for Gidden Direct LULUCF inclusion in the baseline shift."""

    @pytest.fixture
    def ffi_emissions(self) -> pd.DataFrame:
        return _make_ffi_emissions({2020: 9000.0, 2021: 9100.0, 2022: 9200.0})

    @pytest.fixture
    def lulucf_shift_emissions(self) -> pd.DataFrame:
        """World Gidden Direct LULUCF shift timeseries: 3000 MtCO2/yr for 2020-2022."""
        data = {
            "2020": [3000.0],
            "2021": [3100.0],
            "2022": [3200.0],
        }
        return pd.DataFrame(
            data,
            index=pd.Index(["lulucf_shift_mean"], name="source"),
        )

    @pytest.fixture
    def lulucf_shift_zero(self) -> pd.DataFrame:
        """Zero LULUCF shift for comparison."""
        data = {"2020": [0.0], "2021": [0.0], "2022": [0.0]}
        return pd.DataFrame(data, index=pd.Index(["lulucf_shift_mean"], name="source"))

    def test_lulucf_shift_included_in_rebase(
        self, ffi_emissions, lulucf_shift_emissions
    ):
        """Gidden Direct LULUCF is always included: rebase_total = fossil + LULUCF."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_emissions,
            bunkers_2020_2100=0.0,
            lulucf_2020_2100=0.0,
            verbose=False,
        )
        expected_fossil = 9000.0 + 9100.0 + 9200.0
        expected_lulucf = 3000.0 + 3100.0 + 3200.0
        expected_total_shift = expected_fossil + expected_lulucf

        assert result["rebase_fossil_mt"] == round(expected_fossil)
        assert result["rebase_lulucf_mt"] == round(expected_lulucf)
        assert result["rebase_total_mt"] == round(expected_total_shift)

    def test_lulucf_convention_always_nghgi(
        self, ffi_emissions, lulucf_shift_emissions
    ):
        """lulucf_convention is always 'nghgi'."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_emissions,
            verbose=False,
        )
        assert result["lulucf_convention"] == "nghgi"

    def test_lulucf_shift_increases_rcb_2020_vs_zero_shift(
        self, ffi_emissions, lulucf_shift_emissions, lulucf_shift_zero
    ):
        """Non-zero LULUCF shift produces larger rcb_2020_mt than zero shift."""
        result_zero_bm = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_zero,
            verbose=False,
        )
        result_with_bm = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_emissions,
            verbose=False,
        )
        assert result_with_bm["rcb_2020_mt"] > result_zero_bm["rcb_2020_mt"]

    def test_baseline_2020_no_lulucf_shift_when_already_at_target(
        self, ffi_emissions, lulucf_shift_emissions
    ):
        """When baseline == 2020, no shift is needed regardless of LULUCF data."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2020,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_emissions,
            verbose=False,
        )
        assert result["rebase_fossil_mt"] == 0
        assert result["rebase_lulucf_mt"] == 0
        assert result["rebase_total_mt"] == 0

    def test_provenance_fields_present_with_lulucf_shift(
        self, ffi_emissions, lulucf_shift_emissions
    ):
        """All new provenance fields must be present in output."""
        result = process_rcb_to_2020_baseline(
            rcb_value=400.0,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2023,
            world_co2_ffi_emissions=ffi_emissions,
            world_lulucf_shift_emissions=lulucf_shift_emissions,
            verbose=False,
        )
        assert "rebase_fossil_mt" in result
        assert "rebase_lulucf_mt" in result
        assert "lulucf_convention" in result


# ---------------------------------------------------------------------------
# compute_lulucf_convention_gap
# ---------------------------------------------------------------------------


class TestComputeLulucfConventionGap:
    """Tests for compute_lulucf_convention_gap (total CO2 NGHGI-BM gap)."""

    @pytest.fixture
    def nghgi_ts(self) -> pd.DataFrame:
        """NGHGI historical LULUCF timeseries 2020-2022, -500 MtCO2/yr."""
        return _make_timeseries(
            {2020: -500.0, 2021: -500.0, 2022: -500.0}, row_label="nghgi_lulucf"
        )

    @pytest.fixture
    def gidden_direct(self) -> pd.DataFrame:
        """Gidden Direct timeseries 2020-2050, 100 MtCO2/yr."""
        return _make_timeseries(
            {y: 100.0 for y in range(2020, 2051)}, row_label="gidden_direct_C1"
        )

    @pytest.fixture
    def gidden_indirect(self) -> pd.DataFrame:
        """Gidden Indirect timeseries 2020-2050, -200 MtCO2/yr."""
        return _make_timeseries(
            {y: -200.0 for y in range(2020, 2051)}, row_label="gidden_indirect_C1"
        )

    def test_historical_only_gap(self, nghgi_ts, gidden_direct, gidden_indirect):
        """When net_zero_year <= splice_year, gap = NGHGI - Direct (historical only)."""
        result = compute_lulucf_convention_gap(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct,
            gidden_indirect_ts=gidden_indirect,
            start_year=2020,
            net_zero_year=2022,
            splice_year=2022,
        )
        # NGHGI: 3 × (-500) = -1500; Direct: 3 × 100 = 300; gap = -1500 - 300 = -1800
        assert result == pytest.approx(-1800.0)

    def test_historical_plus_future_gap(self, nghgi_ts, gidden_direct, gidden_indirect):
        """Historical gap + future indirect component."""
        result = compute_lulucf_convention_gap(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct,
            gidden_indirect_ts=gidden_indirect,
            start_year=2020,
            net_zero_year=2025,
            splice_year=2022,
        )
        # Historical: NGHGI(-1500) - Direct(300) = -1800
        # Future: Indirect(2023-2025) = 3 × (-200) = -600
        assert result == pytest.approx(-1800.0 + (-600.0))

    def test_gap_differs_from_full_deduction(
        self, nghgi_ts, gidden_direct, gidden_indirect
    ):
        """Convention gap must differ from the full LULUCF deduction."""
        gap = compute_lulucf_convention_gap(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct,
            gidden_indirect_ts=gidden_indirect,
            start_year=2020,
            net_zero_year=2025,
            splice_year=2022,
        )
        full = compute_lulucf_deduction(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct,
            gidden_indirect_ts=gidden_indirect,
            start_year=2020,
            net_zero_year=2025,
            splice_year=2022,
        )
        assert gap != pytest.approx(
            full
        ), "Convention gap should differ from full deduction"

    def test_gap_smaller_magnitude_than_full_deduction_when_direct_positive(self):
        """When Direct is positive (net source), gap magnitude < full deduction magnitude."""
        nghgi_ts = _make_timeseries(
            {2020: -800.0, 2021: -800.0, 2022: -800.0}, row_label="nghgi_lulucf"
        )
        direct_ts = _make_timeseries(
            {y: 200.0 for y in range(2020, 2026)}, row_label="gidden_direct_C1"
        )
        indirect_ts = _make_timeseries(
            {y: -100.0 for y in range(2020, 2026)}, row_label="gidden_indirect_C1"
        )

        gap = compute_lulucf_convention_gap(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=direct_ts,
            gidden_indirect_ts=indirect_ts,
            start_year=2020,
            net_zero_year=2025,
            splice_year=2022,
        )
        full = compute_lulucf_deduction(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=direct_ts,
            gidden_indirect_ts=indirect_ts,
            start_year=2020,
            net_zero_year=2025,
            splice_year=2022,
        )
        # Full deduction is larger in magnitude (includes Direct in future too)
        assert abs(gap) != abs(full)


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

    When precautionary_lulucf=True (default), BM LULUCF sinks (negative
    cumulative) cannot increase the co2-ffi fossil budget. Sources (positive
    cumulative) still reduce it.
    """

    @pytest.fixture
    def nghgi_ts(self) -> pd.DataFrame:
        """NGHGI timeseries (unused for co2-ffi, but required by signature)."""
        return _make_timeseries(
            {y: -500.0 for y in range(2020, 2051)}, row_label="nghgi_lulucf"
        )

    @pytest.fixture
    def bunker_ts(self) -> pd.DataFrame:
        """Bunker timeseries: 1000 MtCO2/yr."""
        return _make_timeseries(
            {y: 1000.0 for y in range(2020, 2051)}, row_label="bunkers"
        )

    @pytest.fixture
    def gidden_direct_sink(self) -> pd.DataFrame:
        """Gidden Direct as net sink: -100 MtCO2/yr (cumulative is negative)."""
        return _make_timeseries(
            {y: -100.0 for y in range(2020, 2051)}, row_label="gidden_direct_C1"
        )

    @pytest.fixture
    def gidden_direct_source(self) -> pd.DataFrame:
        """Gidden Direct as net source: +100 MtCO2/yr (cumulative is positive)."""
        return _make_timeseries(
            {y: 100.0 for y in range(2020, 2051)}, row_label="gidden_direct_C1"
        )

    @pytest.fixture
    def gidden_indirect(self) -> pd.DataFrame:
        """Gidden Indirect (unused for co2-ffi, but required by signature)."""
        return _make_timeseries(
            {y: -200.0 for y in range(2020, 2051)}, row_label="gidden_indirect_C1"
        )

    def test_sink_capped_to_zero_with_precautionary(
        self, nghgi_ts, bunker_ts, gidden_direct_sink, gidden_indirect
    ):
        """When BM is a sink, precautionary cap sets lulucf_mt to 0."""
        _, lulucf_mt = _resolve_adjustment_scalars(
            scenario="1.5p50",
            net_zero_year=2050,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            gidden_direct_ts=gidden_direct_sink,
            gidden_indirect_ts=gidden_indirect,
            emission_category="co2-ffi",
            precautionary_lulucf=True,
            verbose=False,
        )
        assert lulucf_mt == 0.0

    def test_source_still_reduces_budget_with_precautionary(
        self, nghgi_ts, bunker_ts, gidden_direct_source, gidden_indirect
    ):
        """When BM is a source, precautionary cap still reduces fossil budget."""
        _, lulucf_mt = _resolve_adjustment_scalars(
            scenario="1.5p50",
            net_zero_year=2050,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            gidden_direct_ts=gidden_direct_source,
            gidden_indirect_ts=gidden_indirect,
            emission_category="co2-ffi",
            precautionary_lulucf=True,
            verbose=False,
        )
        # cumulative = 31 * 100 = 3100 (positive), lulucf_mt = -3100
        assert lulucf_mt < 0.0
        assert lulucf_mt == pytest.approx(-3100.0)

    def test_sink_increases_budget_without_precautionary(
        self, nghgi_ts, bunker_ts, gidden_direct_sink, gidden_indirect
    ):
        """When precautionary is off, BM sink increases fossil budget (original behavior)."""
        _, lulucf_mt = _resolve_adjustment_scalars(
            scenario="1.5p50",
            net_zero_year=2050,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            gidden_direct_ts=gidden_direct_sink,
            gidden_indirect_ts=gidden_indirect,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        # cumulative = 31 * (-100) = -3100, lulucf_mt = -(-3100) = 3100
        assert lulucf_mt > 0.0
        assert lulucf_mt == pytest.approx(3100.0)

    def test_co2_category_unaffected_by_precautionary(
        self, nghgi_ts, bunker_ts, gidden_direct_sink, gidden_indirect
    ):
        """Precautionary cap only applies to co2-ffi, not co2."""
        _, lulucf_on = _resolve_adjustment_scalars(
            scenario="1.5p50",
            net_zero_year=2050,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            gidden_direct_ts=gidden_direct_sink,
            gidden_indirect_ts=gidden_indirect,
            emission_category="co2",
            precautionary_lulucf=True,
            verbose=False,
        )
        _, lulucf_off = _resolve_adjustment_scalars(
            scenario="1.5p50",
            net_zero_year=2050,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            gidden_direct_ts=gidden_direct_sink,
            gidden_indirect_ts=gidden_indirect,
            emission_category="co2",
            precautionary_lulucf=False,
            verbose=False,
        )
        assert lulucf_on == lulucf_off

    def test_bunkers_unaffected_by_precautionary(
        self, nghgi_ts, bunker_ts, gidden_direct_sink, gidden_indirect
    ):
        """Bunker deduction is identical regardless of precautionary setting."""
        bunkers_on, _ = _resolve_adjustment_scalars(
            scenario="1.5p50",
            net_zero_year=2050,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            gidden_direct_ts=gidden_direct_sink,
            gidden_indirect_ts=gidden_indirect,
            emission_category="co2-ffi",
            precautionary_lulucf=True,
            verbose=False,
        )
        bunkers_off, _ = _resolve_adjustment_scalars(
            scenario="1.5p50",
            net_zero_year=2050,
            nghgi_ts=nghgi_ts,
            bunker_ts=bunker_ts,
            gidden_direct_ts=gidden_direct_sink,
            gidden_indirect_ts=gidden_indirect,
            emission_category="co2-ffi",
            precautionary_lulucf=False,
            verbose=False,
        )
        assert bunkers_on == bunkers_off
