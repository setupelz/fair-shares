"""Tests for the RCB sources in rcbs.yaml and the scenario sets behind their deductions."""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pytest
import yaml

from fair_shares.library.config.models import AdjustmentsConfig
from fair_shares.library.exceptions import (
    ConfigurationError,
    DataLoadingError,
    DataProcessingError,
)
from fair_shares.library.preprocessing.rcbs import load_and_process_rcbs
from fair_shares.library.utils.data.nghgi import compute_bunker_deduction
from fair_shares.library.utils.data.rcb import (
    NET_ZERO_YEAR_COLUMN,
    PEAK_WARMING_COLUMN,
    build_rcb_scenario_sets,
    convention_gap_from_baseline,
    fill_rebase_years,
    missing_rebase_years,
    net_zero_year,
    parse_rcb_scenario,
    process_rcb_to_2020_baseline,
    rcb_scenario_set_key,
    select_rcb_scenario_set,
    validate_rebase_fill_max_years,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RCB_YAML = REPO_ROOT / "data" / "rcbs" / "rcbs.yaml"
GOLDEN_MASTER = REPO_ROOT / "tests" / "fixtures" / "rcb_golden_master.yaml"
AR6_METADATA = (
    REPO_ROOT / "data" / "scenarios" / "ipcc_ar6_gidden" / "metadata_ar6_gidden.xlsx"
)

# Scenario sets written by notebook 104 in a gcb-2025 pipeline run.
PIPELINE_ADJUSTMENTS = (
    REPO_ROOT
    / "output"
    / "gcb-2025_wdi-2025_un-owid-2025_wdi-2025_rcbs_co2-ffi"
    / "intermediate"
    / "scenarios"
    / "rcb_scenario_adjustments.yaml"
)

# Scenario sets written by notebook 104 in the PRIMAP run with melo-2026 LULUCF.
PIPELINE_CO2_ADJUSTMENTS = (
    REPO_ROOT
    / "output"
    / "primap-202503_wdi-2025_un-owid-2025_wdi-2025_melo-2026_rcbs_all-ghg"
    / "intermediate"
    / "scenarios"
    / "rcb_scenario_adjustments.yaml"
)

EXISTING_SOURCES = ["lamboll_2023", "forster_2024", "ar6_2020"]
LABELS = ["1.5p50", "1.5p67", "1.7p50", "1.7p67", "2p50", "2p67", "2p83"]
BAND = "peak-warming-band"


def test_new_sources_hold_the_published_budgets():
    """forster_2026 (IGCC 2025, Table 8) and ar6_wg1_2021 (AR6 WGI, Table SPM.2)."""
    sources = yaml.safe_load(RCB_YAML.read_text())["rcb_data"]

    forster = sources["forster_2026"]
    assert forster["baseline_year"] == 2026
    assert forster["unit"] == "Gt * CO2"
    assert forster["scenario_selection"] == BAND
    assert forster["scenarios"] == dict(
        zip(LABELS, [130, 80, 500, 390, 1050, 860, 690])
    )

    ar6 = sources["ar6_wg1_2021"]
    assert ar6["baseline_year"] == 2020
    assert ar6["unit"] == "Gt * CO2"
    assert ar6["scenario_selection"] == BAND
    assert ar6["scenarios"] == dict(zip(LABELS, [500, 400, 850, 700, 1350, 1150, 900]))


def test_new_labels_parse_and_share_one_band_per_temperature():
    """Each label keeps its own quantile; likelihoods of one temperature share a band."""
    assert parse_rcb_scenario("1.7p50") == ("1.7C", "0.5")
    assert parse_rcb_scenario("2p67") == ("2C", "0.67")
    assert parse_rcb_scenario("2p66") == ("2C", "0.66")

    assert rcb_scenario_set_key("forster_2026", "1.7p50", BAND) == "peak-warming-1.7C"
    assert rcb_scenario_set_key("forster_2026", "1.7p67", BAND) == "peak-warming-1.7C"
    assert rcb_scenario_set_key("forster_2026", "2p83", BAND) == "peak-warming-2C"
    assert rcb_scenario_set_key("forster_2024", "2p83", "ar6-category") == "2p83"


def test_band_is_closed_below_and_open_above():
    """The band is [T - 0.05, T + 0.05); the half-width is configurable."""
    metadata = pd.DataFrame(
        {
            "scenario": ["below", "lower_bound", "centre", "upper_bound"],
            "Category": ["C1", "C1", "C3", "C3"],
            PEAK_WARMING_COLUMN: [1.6499, 1.65, 1.7, 1.75],
            NET_ZERO_YEAR_COLUMN: [2050, 2055, 2060, 2070],
        }
    )

    selected = select_rcb_scenario_set(metadata, "forster_2026", "1.7p50", BAND)
    assert list(selected["scenario"]) == ["lower_bound", "centre"]

    # One band serves every likelihood of its temperature.
    same = select_rcb_scenario_set(metadata, "forster_2026", "1.7p67", BAND)
    assert list(same["scenario"]) == ["lower_bound", "centre"]

    wide = select_rcb_scenario_set(metadata, "forster_2026", "1.7p50", BAND, 0.1)
    assert list(wide["scenario"]) == ["below", "lower_bound", "centre", "upper_bound"]


def test_band_keeps_only_scenarios_that_reach_net_zero():
    """A budget runs to net-zero CO2, so the band drops scenarios that never reach it."""
    assert net_zero_year(pd.Series({"2040": 5.0, "2050": 0.0, "2060": -1.0})) == 2050
    assert net_zero_year(pd.Series({"2040": 5.0, "2100": 0.1})) is None

    metadata = pd.DataFrame(
        {
            "scenario": ["reaches", "never", "reaches_in_2100"],
            "Category": ["C3", "C3", "C3"],
            PEAK_WARMING_COLUMN: [2.0, 2.0, 2.0],
            NET_ZERO_YEAR_COLUMN: [2070, None, 2100],
        }
    )
    selected = select_rcb_scenario_set(metadata, "forster_2026", "2p50", BAND)
    assert list(selected["scenario"]) == ["reaches", "reaches_in_2100"]

    # The AR6 category rule keeps every scenario of the category.
    category_set = select_rcb_scenario_set(metadata, "ar6_2020", "2p66", "ar6-category")
    assert len(category_set) == 3

    never = metadata[metadata["scenario"] == "never"]
    with pytest.raises(DataProcessingError, match="net-zero CO2 year"):
        select_rcb_scenario_set(never, "forster_2026", "2p50", BAND)

    without_column = metadata.drop(columns=NET_ZERO_YEAR_COLUMN)
    with pytest.raises(ConfigurationError, match=NET_ZERO_YEAR_COLUMN):
        select_rcb_scenario_set(without_column, "forster_2026", "2p50", BAND)


def test_empty_band_raises_naming_temperature_and_band():
    metadata = pd.DataFrame(
        {
            "Category": ["C1"],
            PEAK_WARMING_COLUMN: [1.5],
            NET_ZERO_YEAR_COLUMN: [2050],
        }
    )
    with pytest.raises(DataProcessingError) as error:
        select_rcb_scenario_set(metadata, "forster_2026", "2p50", BAND)
    assert "2C band [1.95, 2.05)" in str(error.value)


def test_unmapped_label_raises_naming_source_and_label():
    """A label with no AR6 category and no band rule is an error, never a zero."""
    with pytest.raises(ConfigurationError, match="'my_source', label '1.7p50'"):
        rcb_scenario_set_key("my_source", "1.7p50", "ar6-category")
    with pytest.raises(ConfigurationError, match="unknown scenario_selection"):
        rcb_scenario_set_key("my_source", "1.7p50", "nearest-category")


def test_bands_hold_14_131_69_scenarios_and_14_111_37_reach_net_zero():
    """Band sizes at 1.5, 1.7 and 2 degrees C, before and after the net-zero filter.

    The band sizes come from the AR6 metadata file. The net-zero years come
    from the scenario time series, so the sizes after the filter are read
    from the scenario sets that notebook 104 writes.
    """
    if not AR6_METADATA.exists():
        pytest.skip("AR6 scenario metadata is not redistributable and is absent")
    metadata = pd.read_excel(AR6_METADATA)
    rcb_yaml = yaml.safe_load(RCB_YAML.read_text())

    # With a net-zero year for every scenario, each set is its whole band.
    metadata[NET_ZERO_YEAR_COLUMN] = 2100
    bands = build_rcb_scenario_sets(rcb_yaml, metadata)
    assert len(bands["peak-warming-1.5C"]) == 14
    assert len(bands["peak-warming-1.7C"]) == 131
    assert len(bands["peak-warming-2C"]) == 69

    if not PIPELINE_ADJUSTMENTS.is_file():
        pytest.skip("gcb-2025 scenario adjustments not built")
    adjustments = yaml.safe_load(PIPELINE_ADJUSTMENTS.read_text())
    assert adjustments["peak-warming-1.5C"]["n_scenarios"] == 14
    assert adjustments["peak-warming-1.7C"]["n_scenarios"] == 111
    assert adjustments["peak-warming-2C"]["n_scenarios"] == 37


def test_rebase_raises_when_emissions_end_before_the_baseline_year():
    """A partial rebase understates the budget, so a missing year is an error."""
    emissions = pd.DataFrame({str(y): [36000.0] for y in range(2020, 2024)})
    with pytest.raises(DataProcessingError) as error:
        process_rcb_to_2020_baseline(
            rcb_value=130,
            rcb_unit="Gt * CO2",
            rcb_baseline_year=2026,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=emissions,
            source_name="forster_2026",
            verbose=False,
        )
    assert "lack [2024, 2025]" in str(error.value)


def _one_row_csv(path: Path, values_by_year: dict[int, float], label: str) -> None:
    """Write a single-row timeseries CSV with a ``source`` column."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"source": label, **{str(y): v for y, v in values_by_year.items()}}
    pd.DataFrame([row]).to_csv(path, index=False)


def _world_row(values_by_year: dict[int, float], category: str) -> pd.DataFrame:
    """Build a world emissions row in the format the pipeline passes to the RCB step."""
    index = pd.MultiIndex.from_tuples(
        [("World", "Mt * CO2e", category)],
        names=["iso3c", "unit", "emission-category"],
    )
    return pd.DataFrame({str(y): [v] for y, v in values_by_year.items()}, index=index)


@pytest.mark.parametrize("emission_category", ["co2-ffi", "co2"])
def test_existing_sources_match_golden_master(tmp_path, emission_category):
    """Adjusted budgets of lamboll_2023, forster_2024 and ar6_2020.

    The rebase adds the bunkers of 2020 to the year before the baseline, so
    ar6_2020 equals its budget without that term, and lamboll_2023 and
    forster_2024 exceed theirs by exactly those bunker emissions.

    For co2 the convention gap runs from the baseline year of the source, so
    a budget exceeds the one with the gap from 2020 by the gap of 2020 to the
    year before the baseline. ar6_2020 and every co2-ffi budget stay the same.
    """
    golden = yaml.safe_load(GOLDEN_MASTER.read_text())
    inputs = golden["inputs"]

    emissions_dir = tmp_path / "golden" / "intermediate" / "emissions"
    scenarios_dir = tmp_path / "golden" / "intermediate" / "scenarios"
    _one_row_csv(emissions_dir / "bunker_timeseries.csv", inputs["bunkers_mt"], "gcb")
    _one_row_csv(
        emissions_dir / "world_co2-lulucf_timeseries.csv",
        inputs["world_co2_lulucf_mt"],
        "nghgi",
    )
    scenarios_dir.mkdir(parents=True)
    (scenarios_dir / "rcb_scenario_adjustments.yaml").write_text(
        yaml.safe_dump(inputs["scenario_adjustments"], sort_keys=False)
    )
    for key, values_by_year in inputs["lulucf_shift_median_mt"].items():
        _one_row_csv(
            scenarios_dir / f"lulucf_shift_median_{key}.csv", values_by_year, key
        )

    all_sources = yaml.safe_load(RCB_YAML.read_text())["rcb_data"]
    rcb_yaml = tmp_path / "rcbs.yaml"
    existing = {"rcb_data": {s: all_sources[s] for s in EXISTING_SOURCES}}
    rcb_yaml.write_text(yaml.safe_dump(existing, sort_keys=False))

    adjustments_config = AdjustmentsConfig.model_validate(
        {
            "lulucf_nghgi": {
                "path": "output/{source_id}/intermediate/emissions/"
                "world_co2-lulucf_timeseries.csv"
            },
            "bunkers": {
                "path": "output/{source_id}/intermediate/emissions/bunker_timeseries.csv"
            },
        }
    )
    # The inputs cover every rebase year, so a placeholder fill is an error.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = load_and_process_rcbs(
            rcb_yaml_path=rcb_yaml,
            world_fossil_emissions=_world_row(inputs["world_fossil_co2_mt"], "co2-ffi"),
            emission_category=emission_category,
            adjustments_config=adjustments_config,
            data_dir=tmp_path,
            source_id="golden",
            world_nghgi_lulucf_emissions=_world_row(
                inputs["world_co2_lulucf_mt"], "co2-lulucf"
            ),
            verbose=False,
            output_dir=tmp_path,
        )

    expected = pd.DataFrame(golden["expected"][emission_category])
    actual = result[expected.columns].reset_index(drop=True)
    actual["quantile"] = actual["quantile"].astype(float)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False)

    without_rebase = pd.DataFrame(
        golden["rcb_2020_without_bunker_rebase_mt"][emission_category]
    )
    assert list(without_rebase["source"]) == list(actual["source"])
    assert list(without_rebase["scenario"]) == list(actual["scenario"])
    increase = actual["rcb_2020_nghgi_mt"] - without_rebase["rcb_2020_nghgi_mt"]
    # The co2 budgets with the convention gap from 2020 for every source.
    if emission_category == "co2":
        gap_from_2020 = pd.DataFrame(golden["rcb_2020_with_gap_from_2020_mt"]["co2"])
        assert list(gap_from_2020["source"]) == list(actual["source"])
        assert list(gap_from_2020["scenario"]) == list(actual["scenario"])
        gap_change = actual["rcb_2020_nghgi_mt"] - gap_from_2020["rcb_2020_nghgi_mt"]
    for row, (source, label) in enumerate(zip(actual["source"], actual["scenario"])):
        baseline_year = all_sources[source]["baseline_year"]
        rebase_years = range(2020, baseline_year)
        bunkers = sum(inputs["bunkers_mt"][y] for y in rebase_years)
        assert actual["rebase_bunkers_mt"][row] == round(bunkers)

        # The gap of 2020 to the year before the baseline (negative).
        gaps = inputs["scenario_adjustments"][label]["convention_gap_median_from"]
        gap_before_baseline = gaps[2020] - gaps[baseline_year]
        if emission_category == "co2":
            assert actual["correction_lulucf_nghgi_mt"][row] == round(
                gaps[baseline_year]
            )
            assert gap_change[row] == pytest.approx(-gap_before_baseline, abs=1)
            # It is the observed NGHGI LULUCF minus the scenario BM LULUCF of
            # those years. The median of per-scenario sums differs from the sum
            # of per-year medians by up to 3%.
            nghgi_minus_bm = sum(
                inputs["world_co2_lulucf_mt"][y]
                - inputs["lulucf_shift_median_mt"][label][y]
                for y in rebase_years
            )
            assert gap_before_baseline == pytest.approx(nghgi_minus_bm, rel=0.03)
            bunkers -= gap_before_baseline
        # Each budget is rounded to 1 Mt, so the difference holds within 1 Mt.
        assert increase[row] == pytest.approx(bunkers, abs=1)
    assert (increase[actual["source"] == "ar6_2020"] == 0).all()


def test_convention_gap_starts_at_the_baseline_year():
    """Hand calculation: gap per scenario from the baseline year, then the median.

    Observed NGHGI LULUCF is -4 Mt in each year to the splice year 2023.
    Scenario A reaches net zero in 2030 with Direct 1 and Indirect -5 each year.
    Scenario B reaches net zero in 2022 with Direct 2 and Indirect -3 each year.
    """
    years = [str(y) for y in range(2020, 2031)]
    nghgi = pd.Series(-4.0, index=years[:4])
    scenarios = {
        "A": (pd.Series(1.0, index=years), pd.Series(-5.0, index=years), 2030),
        "B": (pd.Series(2.0, index=years), pd.Series(-3.0, index=years), 2022),
    }

    def gaps(baseline_year: int) -> dict[str, float]:
        return {
            name: convention_gap_from_baseline(
                nghgi, direct, indirect, baseline_year, nz_year, splice_year=2023
            )
            for name, (direct, indirect, nz_year) in scenarios.items()
        }

    # From 2020. A: 4 x (-4 - 1) + 7 x -5 = -55. B: 3 x (-4 - 2) = -18.
    assert gaps(2020) == {"A": -55.0, "B": -18.0}
    assert pd.Series(gaps(2020)).median() == -36.5
    # From 2023. A: (-4 - 1) + 7 x -5 = -40. B reaches net zero before 2023.
    assert gaps(2023) == {"A": -40.0, "B": 0.0}
    assert pd.Series(gaps(2023)).median() == -20.0
    # From 2026, after the splice year. A: Indirect only, 5 x -5 = -25.
    assert gaps(2026) == {"A": -25.0, "B": 0.0}
    # A baseline in the net-zero year keeps that one year: -4 - 2 = -6.
    assert gaps(2022)["B"] == -6.0


def test_co2_budget_needs_a_convention_gap_from_its_baseline_year(tmp_path):
    """Adjustments without a gap from the baseline year name notebook 104."""
    emissions_dir = tmp_path / "stale" / "intermediate" / "emissions"
    scenarios_dir = tmp_path / "stale" / "intermediate" / "scenarios"
    years = {y: 100.0 for y in range(2020, 2024)}
    _one_row_csv(emissions_dir / "bunker_timeseries.csv", years, "gcb")
    scenarios_dir.mkdir(parents=True)
    adjustments = {
        "1.5p50": {
            "bm_lulucf_cumulative_median": 0.0,
            "convention_gap_median_from": {2020: -50.0},
            "nz_year_median": 2030,
            "n_scenarios": 1,
        }
    }
    (scenarios_dir / "rcb_scenario_adjustments.yaml").write_text(
        yaml.safe_dump(adjustments)
    )
    _one_row_csv(scenarios_dir / "lulucf_shift_median_1.5p50.csv", years, "1.5p50")
    rcb_yaml = tmp_path / "rcbs.yaml"
    source = {"baseline_year": 2023, "unit": "Gt * CO2", "scenarios": {"1.5p50": 1}}
    rcb_yaml.write_text(yaml.safe_dump({"rcb_data": {"budget_2023": source}}))
    adjustments_config = AdjustmentsConfig.model_validate(
        {
            "lulucf_nghgi": {"path": "output/{source_id}/unused.csv"},
            "bunkers": {
                "path": "output/{source_id}/intermediate/emissions/bunker_timeseries.csv"
            },
        }
    )
    with pytest.raises(DataLoadingError) as error:
        load_and_process_rcbs(
            rcb_yaml_path=rcb_yaml,
            world_fossil_emissions=_world_row(years, "co2-ffi"),
            emission_category="co2",
            adjustments_config=adjustments_config,
            data_dir=tmp_path,
            source_id="stale",
            world_nghgi_lulucf_emissions=_world_row(years, "co2-lulucf"),
            verbose=False,
            output_dir=tmp_path,
        )
    message = str(error.value)
    assert "No convention gap from baseline year 2023 for '1.5p50'" in message
    assert "Re-run notebook 104" in message


def test_gap_from_2020_equals_the_captured_gap():
    """On the real scenario data the 2020 entry equals the captured gap from 2020."""
    if not PIPELINE_CO2_ADJUSTMENTS.is_file():
        pytest.skip("AR6 scenario adjustments with melo-2026 LULUCF not built")
    adjustments = yaml.safe_load(PIPELINE_CO2_ADJUSTMENTS.read_text())
    golden = yaml.safe_load(GOLDEN_MASTER.read_text())
    captured = golden["convention_gap_median_from_2020_captured_mt"]
    for set_key, gap in captured.items():
        assert adjustments[set_key]["convention_gap_median_from"][2020] == gap
        fixture_set = golden["inputs"]["scenario_adjustments"][set_key]
        assert fixture_set["convention_gap_median_from"][2020] == gap


@pytest.mark.parametrize("baseline_year", [2020, 2024])
def test_rebase_counts_each_bunker_year_once(baseline_year):
    """Hand calculation: two baselines of one world give one allocatable budget.

    Each year from 2020 to net zero in 2029 emits 100 Mt fossil CO2 without
    bunkers and 10 Mt bunker CO2. A published budget covers both, so it is
    1100 Mt from 2020 and 660 Mt from 2024. The budget without bunkers from
    2020 is 10 x 100 = 1000 Mt.
    """
    fossil = pd.DataFrame({str(y): [100.0] for y in range(2020, 2024)})
    bunkers = pd.DataFrame({str(y): [10.0] for y in range(2020, 2024)})
    published = {2020: 1100.0, 2024: 660.0}[baseline_year]

    # Observed 2020-2023 (40 Mt) plus the 2023 rate for 2024-2029 (60 Mt).
    deduction = compute_bunker_deduction(bunkers, start_year=2020, net_zero_year=2029)
    assert deduction == pytest.approx(100.0)

    result = process_rcb_to_2020_baseline(
        rcb_value=published,
        rcb_unit="Mt * CO2",
        rcb_baseline_year=baseline_year,
        emission_category="co2-ffi",
        world_co2_ffi_emissions=fossil,
        world_bunker_emissions=bunkers,
        bunkers_deduction_mt=deduction,
        verbose=False,
    )

    assert result["rebase_fossil_mt"] == {2020: 0, 2024: 400}[baseline_year]
    assert result["rebase_bunkers_mt"] == {2020: 0, 2024: 40}[baseline_year]
    assert result["deduction_bunkers_mt"] == -100
    assert result["rcb_2020_nghgi_mt"] == 1000


def test_rebase_with_a_bunker_deduction_needs_the_bunker_series():
    """A deduction from 2020 without the bunkers of the rebase years is an error."""
    fossil = pd.DataFrame({str(y): [100.0] for y in range(2020, 2024)})
    with pytest.raises(DataProcessingError, match="pass world_bunker_emissions"):
        process_rcb_to_2020_baseline(
            rcb_value=660.0,
            rcb_unit="Mt * CO2",
            rcb_baseline_year=2024,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=fossil,
            bunkers_deduction_mt=100.0,
            verbose=False,
        )


def test_co2_rebase_needs_the_inventory_lulucf_series():
    """A co2 budget from after 2020 raises without LULUCF; a 2020 budget runs."""
    fossil = pd.DataFrame({str(y): [100.0] for y in range(2020, 2024)})
    kwargs = {
        "rcb_unit": "Mt * CO2",
        "emission_category": "co2",
        "world_co2_ffi_emissions": fossil,
        "verbose": False,
    }
    with pytest.raises(DataProcessingError, match="pass world_nghgi_lulucf_emissions"):
        process_rcb_to_2020_baseline(rcb_value=660.0, rcb_baseline_year=2024, **kwargs)

    result = process_rcb_to_2020_baseline(
        rcb_value=1000.0, rcb_baseline_year=2020, **kwargs
    )
    assert result["rebase_lulucf_mt"] == 0
    assert result["rcb_2020_nghgi_mt"] == 1000


def test_rebase_fill_holds_the_last_observed_value():
    """Observed to 2024, baseline 2026: 2025 takes the 2024 value, with a warning.

    Hand calculation: 100 Mt fossil CO2 and 10 Mt bunker CO2 each year to net
    zero in 2029. The published budget from 2026 is 4 x 110 = 440 Mt and the
    budget without bunkers from 2020 is 1000 Mt.
    """
    fossil = pd.DataFrame({str(y): [100.0] for y in range(2020, 2025)})
    bunkers = pd.DataFrame({str(y): [10.0] for y in range(2020, 2025)})

    with pytest.warns(UserWarning) as record:
        filled_fossil = fill_rebase_years(
            fossil, 2026, 1, "world fossil CO2 emissions", "forster_2026"
        )
    message = str(record[0].message)
    assert "'forster_2026'" in message
    assert "world fossil CO2 emissions end in 2024" in message
    assert "2024 value (100.0 Mt CO2) for [2025]" in message
    assert "placeholder until observed data are published" in message
    assert filled_fossil["2025"].iloc[0] == fossil["2024"].iloc[0]
    assert "2025" not in fossil.columns

    with pytest.warns(UserWarning):
        filled_bunkers = fill_rebase_years(bunkers, 2026, 1, "bunkers", "forster_2026")
    result = process_rcb_to_2020_baseline(
        rcb_value=440.0,
        rcb_unit="Mt * CO2",
        rcb_baseline_year=2026,
        emission_category="co2-ffi",
        world_co2_ffi_emissions=filled_fossil,
        world_bunker_emissions=filled_bunkers,
        bunkers_deduction_mt=compute_bunker_deduction(bunkers, 2020, 2029),
        verbose=False,
    )
    assert result["rebase_fossil_mt"] == 600
    assert result["rebase_bunkers_mt"] == 60
    assert result["deduction_bunkers_mt"] == -100
    assert result["rcb_2020_nghgi_mt"] == 1000


def test_rebase_fill_stops_at_the_limit():
    """More missing years than the limit, or a limit of 0, leave the series as is."""
    to_2023 = pd.DataFrame({str(y): [100.0] for y in range(2020, 2024)})
    to_2024 = pd.DataFrame({str(y): [100.0] for y in range(2020, 2025)})

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert fill_rebase_years(to_2023, 2026, 1).equals(to_2023)
        assert fill_rebase_years(to_2024, 2026, 0).equals(to_2024)
        # A series that covers every rebase year needs no fill.
        assert fill_rebase_years(to_2023, 2024, 1).equals(to_2023)

    with pytest.raises(DataProcessingError, match=r"lack \[2024, 2025\]"):
        process_rcb_to_2020_baseline(
            rcb_value=440.0,
            rcb_unit="Mt * CO2",
            rcb_baseline_year=2026,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=fill_rebase_years(to_2023, 2026, 1),
            verbose=False,
        )


def test_rebase_counts_a_year_without_a_value_as_missing():
    """NaN-padded trailing years are lacking, so the rebase raises instead of summing less."""
    padded = pd.DataFrame({str(y): [100.0] for y in range(2020, 2026)})
    padded[["2023", "2024", "2025"]] = float("nan")
    assert missing_rebase_years(2026, padded) == [2023, 2024, 2025]

    with pytest.raises(DataProcessingError, match=r"lack \[2023, 2024, 2025\]"):
        process_rcb_to_2020_baseline(
            rcb_value=440.0,
            rcb_unit="Mt * CO2",
            rcb_baseline_year=2026,
            emission_category="co2-ffi",
            world_co2_ffi_emissions=padded,
            verbose=False,
        )


def test_rebase_nan_gap_beyond_the_fill_limit_is_missing():
    """A NaN gap longer than rebase_fill_max_years stays unfilled and counts as lacking."""
    gap = pd.DataFrame({str(y): [100.0] for y in range(2020, 2025)})
    gap[["2022", "2023", "2024"]] = float("nan")
    unfilled = fill_rebase_years(gap, 2026, 1)
    assert unfilled.equals(gap)
    assert missing_rebase_years(2026, unfilled) == [2022, 2023, 2024, 2025]


def test_peak_warming_label_without_a_temperature_raises_configuration_error():
    """A label such as 'abcp50' names itself in a ConfigurationError."""
    metadata = pd.DataFrame(
        {
            "scenario": ["a"],
            "Category": ["C1"],
            PEAK_WARMING_COLUMN: [1.5],
            NET_ZERO_YEAR_COLUMN: [2050],
        }
    )
    with pytest.raises(ConfigurationError, match="label 'abcp50'"):
        select_rcb_scenario_set(metadata, "forster_2026", "abcp50", BAND)


@pytest.mark.parametrize("value", [-1, 1.5, "1", None, True])
def test_rebase_fill_max_years_must_be_a_non_negative_integer(value):
    """Anything other than a count of zero or more is a configuration error."""
    with pytest.raises(ConfigurationError, match="rebase_fill_max_years"):
        validate_rebase_fill_max_years(value)
    assert validate_rebase_fill_max_years(0) == 0
    assert validate_rebase_fill_max_years(2) == 2
