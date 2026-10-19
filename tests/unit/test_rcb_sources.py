"""Tests for the RCB sources in rcbs.yaml and the scenario sets behind their terms."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from fair_shares.library.config.models import AdjustmentsConfig
from fair_shares.library.exceptions import (
    ConfigurationError,
    DataProcessingError,
)
from fair_shares.library.preprocessing.rcbs import load_and_process_rcbs
from fair_shares.library.utils.data.nghgi import (
    bunker_deduction_from_share,
    compute_bunker_deduction,
)
from fair_shares.library.utils.data.rcb import (
    AR6_CATEGORY_BY_RCB_LABEL,
    canonical_label,
    convention_gap_from_baseline,
    cumulative_to_net_zero,
    fill_rebase_years,
    integrate,
    missing_rebase_years,
    net_zero_crossing,
    process_rcb_to_2020_baseline,
    resolve_scenario_selection,
    validate_rebase_fill_max_years,
)
from fair_shares.library.utils.data.scenario_sets import (
    CUMULATIVE_CO2,
    NET_ZERO_CROSSING,
    add_source_non_co2_members,
    budget_from_2020,
    budget_specs,
    build_budget_sets,
    bunker_share,
    median_pathways_by_budget,
    scenario_accounting,
    scenario_set_settings,
    select_temperature_matched,
    select_volume_matched,
)
from fair_shares.library.utils.data.scenario_sources import (
    apply_derived_net_zero,
    ar6_at_net_zero,
    load_bunker_pathways,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RCB_YAML = REPO_ROOT / "data" / "rcbs" / "rcbs.yaml"
GOLDEN_MASTER = REPO_ROOT / "tests" / "fixtures" / "rcb_golden_master.yaml"
AR6_METADATA = (
    REPO_ROOT / "data" / "scenarios" / "ipcc_ar6_gidden" / "metadata_ar6_gidden.xlsx"
)

AR6_CLIMATE = REPO_ROOT / "data/scenarios/ipcc_ar6_climate/ar6_climate_world.csv"

# Toy metadata columns, as in scenario_sources.yaml.
COLUMNS = {
    "category": "Category",
    "net_zero_year": "nz_year",
    "warming_median": "w50",
    "warming_p67": "w67",
}
OBSERVED = pd.Series({2020: 40.0, 2021: 41.0, 2022: 42.0})


def _metadata(rows: dict[str, tuple]) -> pd.DataFrame:
    """Toy metadata: name -> (category, cumulative Gt, median warming at NZ, NZ year)."""
    frame = pd.DataFrame.from_dict(
        rows, orient="index", columns=["Category", CUMULATIVE_CO2, "w50", "nz_year"]
    )
    frame.index = pd.MultiIndex.from_tuples(
        [("m", name) for name in frame.index], names=["Model", "Scenario"]
    )
    frame["w67"] = frame["w50"] + 0.1
    frame[NET_ZERO_CROSSING] = frame["nz_year"]
    return frame


def test_defaults_hold_the_published_budgets_and_label_semantics():
    """Published values (Lamboll 2023 p.1366; IGCC 2023 and 2025 Table 8; AR6 SPM.2)."""
    rcb_yaml = yaml.safe_load(RCB_YAML.read_text())
    sources = rcb_yaml["rcb_data"]
    assert sources["lamboll_2023"]["scenarios"] == {
        "1.5p50": 250,
        "2p50": 1220,
        "2p66": 940,
        "2p90": 500,
    }
    assert {k: sources[k]["scenarios"]["2p50"] for k in sources} == {
        "lamboll_2023": 1220,
        "forster_2024": 1100,
        "ar6_2020": 1350,
        "forster_2026": 1050,
        "ar6_wg1_2021": 1350,
    }
    assert sources["lamboll_2023"]["likelihood_scope"] == "tcre-zec-esf"
    assert sources["lamboll_2023"]["budget_metric"] == "peak-warming"
    assert sources["forster_2024"]["scenarios"]["2p67"] == 900
    assert sources["ar6_2020"]["scenarios"]["2p67"] == 1150
    assert sources["forster_2026"]["scenarios"]["2p67"] == 860
    assert sources["ar6_wg1_2021"]["scenarios"]["2p83"] == 900
    for name in ("forster_2024", "forster_2026", "ar6_2020", "ar6_wg1_2021"):
        assert sources[name]["likelihood_scope"] == "tcre-only"
        assert sources[name]["budget_metric"] == "warming-at-net-zero"
    assert all(
        "2p66" not in s["scenarios"] for k, s in sources.items() if k != "lamboll_2023"
    )
    settings = scenario_set_settings(rcb_yaml)
    assert (settings["volume_tolerance_gt"], settings["min_scenarios"]) == (50.0, 10)
    assert settings["bunkers"]["scenario_sources"] == ["ar6", "sci", "scenariomip"]


def test_full_years_to_the_interpolated_net_zero_year():
    """Hand calculation on 40 (2020), 20 (2030), -20 (2040).

    The line crosses zero halfway between 2030 and 2040: 2035. The cumulative
    sums the full years 2020-2034: 40, 38, ..., 22 (310) and 20, 16, ..., 4
    (60) = 370. 2025-2029: 30 + 28 + 26 + 24 + 22 = 130. A crossing in 2034.5
    adds half of the year 2034 as a trapezoid: 366 + (4 + 2) / 2 x 0.5.
    """
    series = pd.Series({"2020": 40.0, "2030": 20.0, "2040": -20.0})
    assert net_zero_crossing(series) == 2035.0
    assert cumulative_to_net_zero(series) == (2035.0, 370.0)
    assert integrate(series, 2025, 2030) == pytest.approx(130.0)
    assert integrate(series, 2020, 2034.5) == pytest.approx(367.5)
    assert net_zero_crossing(pd.Series({"2020": 5.0, "2100": 0.1})) is None
    with pytest.raises(DataProcessingError, match="needs 2020-2041"):
        integrate(series, 2020, 2041)

    co2_mt = pd.DataFrame(
        {
            "2020": [40e3, 40e3, 40e3],
            "2030": [20e3, 20e3, 20e3],
            "2040": [-20e3, 1e3, -20e3],
        },
        index=pd.MultiIndex.from_tuples([("m", "a"), ("m", "b"), ("m", "c")]),
    )
    accounts = scenario_accounting(co2_mt, last_year=2100)
    assert accounts.loc[("m", "a")].tolist() == [2035.0, 370.0]
    assert accounts.loc[("m", "b")].isna().all()
    assert scenario_accounting(co2_mt, last_year=2030).isna().all().all()


def test_volume_matched_set_edges_and_minimum():
    """Within +-50 Gt of 400 Gt, edges included; scenarios without net zero out."""
    accounts = _metadata(
        {
            "a": ("C1", 349.9, 1.5, 2050),
            "b": ("C1", 350.0, 1.5, 2050),
            "c": ("C1", 400.0, 1.5, 2050),
            "d": ("C1", 450.0, 1.5, 2050),
            "e": ("C1", 450.1, 1.5, 2050),
            "f": ("C1", np.nan, 1.5, None),
        }
    )
    selected = select_volume_matched(accounts, "src:1.5p50", 400.0, 50.0, 3)
    assert [s for _, s in selected] == ["b", "c", "d"]
    with pytest.raises(ConfigurationError, match="Budget 'src:1.5p50': 3 scenarios"):
        select_volume_matched(accounts, "src:1.5p50", 400.0, 50.0, 4)


def test_budget_from_2020_adds_observed_emissions():
    """250 Gt from 2023 plus 40 + 41 + 42 observed = 373 Gt from 2020."""
    rcb_yaml = {
        "rcb_data": {
            "s23": {
                "baseline_year": 2023,
                "unit": "Gt * CO2",
                "scenarios": {"1.5p50": 250},
            },
            "s24": {
                "baseline_year": 2024,
                "unit": "Gt * CO2",
                "scenarios": {"1.5p50": 250},
            },
            "s25": {
                "baseline_year": 2025,
                "unit": "Gt * CO2",
                "scenarios": {"1.5p50": 250},
            },
        }
    }
    s23, s24, s25 = budget_specs(rcb_yaml)
    assert budget_from_2020(s23, OBSERVED) == (373.0, 123.0)
    with pytest.warns(UserWarning, match="2022 value"):
        assert budget_from_2020(s24, OBSERVED)[0] == 415.0
    with pytest.raises(DataProcessingError, match=r"lacks \[2023, 2024\]"):
        budget_from_2020(s25, OBSERVED)


def test_temperature_matched_set_needs_net_zero_and_reads_the_median():
    """[1.45, 1.55) on median warming at net zero; a scenario without net zero is out."""
    metadata = _metadata(
        {
            "a": ("C1", 300.0, 1.4499, 2050),
            "b": ("C1", 300.0, 1.45, 2050),
            "c": ("C1", 300.0, 1.5, None),
            "d": ("C1", 300.0, 1.5499, 2050),
            "e": ("C1", 300.0, 1.55, 2050),
        }
    )
    selected = select_temperature_matched(metadata, "k", 1.5, "w50", "nz_year", 0.05, 2)
    assert [s for _, s in selected] == ["b", "d"]
    with pytest.raises(ConfigurationError, match="2 scenarios .* min_scenarios=3"):
        select_temperature_matched(metadata, "k", 1.5, "w50", "nz_year", 0.05, 3)


def test_role_matched_and_category_sets_of_each_budget():
    """Volume set for the terms, median-T set for non-CO2 at every likelihood.

    Budgets from 2020 (baseline 2020): 1.5p50 at 300 Gt and 1.5p67 at 200 Gt
    share the temperature set {b, c}. The AR6 source pairs 1.5p50 with C1:
    terms = C1 members that reach net zero {a, b}, non-CO2 = all of C1.
    """
    metadata = _metadata(
        {
            "a": ("C1", 300.0, 1.40, 2045),
            "b": ("C1", 210.0, 1.50, 2040),
            "c": ("C3", 290.0, 1.52, 2050),
            "d": ("C1", np.nan, 1.60, None),
        }
    )
    rcb_yaml = {
        "min_scenarios": 1,
        "volume_tolerance_gt": 20,
        "rcb_data": {
            "band": {
                "baseline_year": 2020,
                "scenarios": {"1.5p50": 300, "1.5p67": 200},
            },
            "ar6": {
                "baseline_year": 2020,
                "scenario_selection": "ar6-category",
                "scenarios": {"1.5p50": 500},
            },
        },
    }
    sets = build_budget_sets(rcb_yaml, metadata, OBSERVED, COLUMNS)
    names = {
        k: {key: sorted(s for _, s in v[key]) for key in ("terms", "non_co2")}
        for k, v in sets.items()
    }
    assert names == {
        "band:1.5p50": {"terms": ["a", "c"], "non_co2": ["b", "c"]},
        "band:1.5p67": {"terms": ["b"], "non_co2": ["b", "c"]},
        "ar6:1.5p50": {"terms": ["a", "b"], "non_co2": ["a", "b", "d"]},
    }
    record = sets["band:1.5p50"]["record"]
    assert record["consistency"] == {"overlap": 1, "non_co2_set_volume_gap_gt": -50.0}
    assert record["terms_set"]["median_warming_at_net_zero"] == 1.46

    index = pd.MultiIndex.from_tuples([("m", s) for s in "abcd"])
    ghg = pd.DataFrame({"2030": [50.0, 60.0, 90.0, 70.0]}, index=index)
    assert median_pathways_by_budget(ghg, sets)["2030"].to_dict() == {
        ("1.5C", 0.5, "band"): 75.0,
        ("1.5C", 0.67, "band"): 75.0,
        ("1.5C", 0.5, "ar6"): 60.0,
    }


def test_other_sources_join_the_non_co2_set_of_role_matched_budgets():
    """SCI scenarios at T with net zero join role-matched non-CO2 sets only."""
    metadata = _metadata(
        {"a": ("C1", 300.0, 1.50, 2045), "b": ("C1", 300.0, 1.40, 2045)}
    )
    rcb_yaml = {
        "min_scenarios": 1,
        "rcb_data": {
            "band": {"baseline_year": 2020, "scenarios": {"1.5p50": 300}},
            "ar6": {
                "baseline_year": 2020,
                "scenario_selection": "ar6-category",
                "scenarios": {"1.5p50": 300},
            },
        },
    }
    sets = build_budget_sets(rcb_yaml, metadata, OBSERVED, COLUMNS)
    sci = pd.DataFrame(
        {"nz_year": [2050, None, 2050], "w50": [1.52, 1.50, 1.70]},
        index=pd.MultiIndex.from_tuples([("s", "in"), ("s", "no-nz"), ("s", "warm")]),
    )
    added = add_source_non_co2_members(sets, "sci", sci, COLUMNS, 0.05)
    assert added == {"band:1.5p50": 1}
    assert sorted(sets["band:1.5p50"]["non_co2"]) == [("m", "a"), ("s", "in")]
    assert sets["band:1.5p50"]["record"]["non_co2_set"]["n"] == 2
    assert list(sets["ar6:1.5p50"]["non_co2"]) == [("m", "a"), ("m", "b")]


def test_corrected_ar6_category_map_and_removed_rules():
    """C1 holds the 1.5 C p50 budget, C3 >67% below 2 C, C4 >50% below 2 C."""
    assert AR6_CATEGORY_BY_RCB_LABEL == {"1.5p50": "C1", "2p67": "C3", "2p50": "C4"}
    assert resolve_scenario_selection("s", None) == "role-matched"
    with pytest.raises(ConfigurationError, match="'peak-warming' was removed"):
        resolve_scenario_selection("s", "peak-warming")
    for removed in ("fallback", "volume_tolerance_gt"):
        with pytest.raises(ConfigurationError, match=f"bunkers.{removed} was removed"):
            scenario_set_settings({"bunkers": {removed: 1}})


def test_family_balanced_bunker_share_and_the_deduction():
    """Bunkers over net CO2 from 2025; the share is the median of family medians.

    IMAGE ratios 0.05, 0.06, 0.07 (median 0.06), WITCH 0.08, 0.09, 0.10 (0.09)
    and REMIND 0.10, 0.11, 0.12 (0.11) count; LUT-ESTM has one run (0.30) and
    stays out. The share is the median of 0.06, 0.09 and 0.11 = 0.09. The pooled
    median of all ten ratios is 0.095. A reporter at net zero before 2025 has
    no net CO2 left and drops out. The deduction counts observed bunkers
    2020-2024 (5 x 1000) plus 0.09 x 200,000 Mt of set CO2.
    """
    ratios = [
        ("ar6", "IMAGE", 50.0),
        ("ar6", "IMAGE", 60.0),
        ("sci", "IMAGE", 70.0),
        ("sci", "WITCH", 80.0),
        ("sci", "WITCH", 90.0),
        ("sci", "WITCH", 100.0),
        ("sci", "REMIND", 100.0),
        ("sci", "REMIND", 110.0),
        ("sci", "REMIND", 120.0),
        ("ar6", "LUT-ESTM", 300.0),
    ]
    rows = [
        {
            "source": src,
            "Model": fam,
            "family": fam,
            "Scenario": f"s{i}",
            "co2_from_2025": 1000.0,
            "bunkers_from_2025": bunkers,
        }
        for i, (src, fam, bunkers) in enumerate(ratios)
    ]
    rows.append(
        {
            "source": "ar6",
            "Model": "IMAGE",
            "family": "IMAGE",
            "Scenario": "done",
            "co2_from_2025": 0.0,
            "bunkers_from_2025": 0.0,
        }
    )
    table = pd.DataFrame(rows)
    share = bunker_share(table, 2025, 9, 3, 3)
    assert share["share"] == pytest.approx(0.09)
    assert share["pooled"] == pytest.approx(0.095)
    assert share["families"]["IMAGE"] == {"median": pytest.approx(0.06), "n": 3}
    assert share["excluded_families"] == {
        "LUT-ESTM": {"median": pytest.approx(0.3), "n": 1}
    }
    assert (share["n"], share["n_by_source"]) == (9, {"sci": 7, "ar6": 2})
    with pytest.raises(ConfigurationError, match="9 reporters in 3 model families"):
        bunker_share(table, 2025, 10, 3, 3)
    with pytest.raises(ConfigurationError, match="min_families=4"):
        bunker_share(table, 2025, 9, 4, 3)
    with pytest.raises(DataProcessingError, match="2026"):
        bunker_share(table, 2026, 1, 1, 1)

    observed = pd.DataFrame({str(y): [1000.0] for y in range(2020, 2025)})
    deduction, last = bunker_deduction_from_share(observed, 0.09, 200_000.0)
    assert (deduction, last) == (pytest.approx(5000.0 + 18_000.0), 2024)


def test_bunker_pathways_aviation_share_and_direct_totals():
    """AR6: 0.6 x Aviation + Maritime. SCI: the total, else the two components."""
    ar6 = pd.DataFrame(
        {
            "model": ["m", "m", "m"],
            "scenario": ["x", "x", "y"],
            "variable": ["Aviation", "Maritime", "Aviation"],
            "2020": [100.0, 50.0, 100.0],
        }
    )
    bunkers = load_bunker_pathways(ar6, {"Aviation": 0.6, "Maritime": 1.0})
    assert bunkers["2020"].to_dict() == {("m", "x"): 110.0}

    sci = pd.DataFrame(
        {
            "Model": ["m"] * 5,
            "Scenario": ["p", "p", "p", "q", "q"],
            "Variable": ["Total", "Air", "Sea", "Air", "Sea"],
            "2020": [70.0, 30.0, 30.0, 30.0, 20.0],
        }
    )
    bunkers = load_bunker_pathways(sci, {"Air": 1.0, "Sea": 1.0}, total="Total")
    assert bunkers["2020"].to_dict() == {("m", "p"): 70.0, ("m", "q"): 50.0}


def test_67_percent_labels_replace_2p66_with_a_deprecation_warning():
    with pytest.warns(DeprecationWarning, match="'2p66' is deprecated"):
        assert canonical_label("forster_2024", "2p66") == "2p67"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert canonical_label("lamboll_2023", "2p66") == "2p66"
    rcb_yaml = {
        "rcb_data": {"ar6_2020": {"baseline_year": 2020, "scenarios": {"2p66": 1150}}}
    }
    with pytest.warns(DeprecationWarning):
        (spec,) = budget_specs(rcb_yaml)
    assert (spec.label, spec.published_label, spec.likelihood) == ("2p67", "2p66", 0.67)


def test_temperature_sets_on_the_ar6_metadata():
    """Median warming at net zero within 0.05 C, harmonised-infilled net zero."""
    if not AR6_METADATA.exists():
        pytest.skip("AR6 scenario metadata is not redistributable and is absent")
    if not AR6_CLIMATE.exists():
        pytest.skip("AR6 climate series extract is absent")
    metadata = pd.read_excel(AR6_METADATA).set_index(["model", "scenario"])
    column = "Median warming at year of netzero Emissions|CO2 (MAGICCv7.5.3)"
    nz = "Year of netzero CO2 emissions (Harm-Infilled) table"
    derived, changed = apply_derived_net_zero(metadata, ar6_at_net_zero("ar6"))
    # Same scenarios reach net zero; years differ only where AR6 used 2100 warming.
    assert derived[nz].notna().equals(metadata[nz].notna())
    assert len(changed) == 48
    metadata = derived
    sizes = {
        t: len(select_temperature_matched(metadata, "k", t, column, nz, 0.05, 10))
        for t in (1.5, 1.7, 2.0)
    }
    assert sizes == {1.5: 32, 1.7: 156, 2.0: 43}


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


# Golden-master sets by label; forster_2024 and ar6_2020 publish 2p67.
GOLDEN_SOURCES = {
    "lamboll_2023": (2023, {"1.5p50": 250, "2p66": 940}),
    "forster_2024": (2024, {"1.5p50": 200, "2p67": 900, "2p83": 750}),
    "ar6_2020": (2020, {"1.5p50": 500, "2p67": 1150, "2p83": 900}),
}
GOLDEN_SET = {"1.5p50": "1.5p50", "2p66": "2p66", "2p67": "2p66", "2p83": "2p83"}


@pytest.mark.parametrize("emission_category", ["co2-ffi", "co2"])
def test_existing_sources_match_golden_master(tmp_path, emission_category):
    """Adjusted budgets of lamboll_2023, forster_2024 and ar6_2020.

    Each budget takes the scalars of its golden set. The BM LULUCF term from a
    baseline year is the 2020 term minus the median of the years before it.
    The bunker term counts observed bunkers 2020-2023, then a share of 0.05 of
    the set's net CO2 from 2024 (400, 700 and 600 Gt for the 1.5p50, 2p66 and
    2p83 sets). The rebase adds the bunkers of 2020 to the year before the
    baseline, and for co2 the convention gap runs from the baseline.
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
    set_co2 = {"1.5p50": 400e3, "2p66": 700e3, "2p83": 600e3}
    reporters = pd.DataFrame(
        {
            "source": "ar6",
            "Model": "IMAGE 3.2",
            "family": ["IMAGE", "REMIND", "WITCH"] * 3 + ["IMAGE"],  # 3+ runs each
            "Scenario": [f"r{i}" for i in range(10)],
            "co2_from_2024": 1000.0,
            "bunkers_from_2024": 50.0,
        }
    )
    reporters.to_csv(scenarios_dir / "bunker_share_reporters.csv", index=False)
    adjustments = {}
    for source, (baseline_year, budgets) in GOLDEN_SOURCES.items():
        for label in budgets:
            adjustment = inputs["scenario_adjustments"][GOLDEN_SET[label]]
            shift = inputs["lulucf_shift_median_mt"][GOLDEN_SET[label]]
            prefix = sum(shift[y] for y in range(2020, baseline_year))
            adjustments[f"{source}:{label}"] = {
                "bm_lulucf_median_from": {
                    baseline_year: adjustment["bm_lulucf_cumulative_median"] - prefix
                },
                "convention_gap_median_from": adjustment["convention_gap_median_from"],
            }
            pd.DataFrame({"co2_from_2024": [set_co2[GOLDEN_SET[label]]]}).to_csv(
                scenarios_dir / f"scenario_set_{source}_{label}.csv", index=False
            )
    (scenarios_dir / "rcb_scenario_adjustments.yaml").write_text(
        yaml.safe_dump(adjustments, sort_keys=False)
    )

    sources = {
        source: {"baseline_year": year, "unit": "Gt * CO2", "scenarios": budgets}
        for source, (year, budgets) in GOLDEN_SOURCES.items()
    }
    rcb_yaml = tmp_path / "rcbs.yaml"
    rcb_yaml.write_text(yaml.safe_dump({"rcb_data": sources}, sort_keys=False))
    adjustments_config = AdjustmentsConfig.model_validate(
        {
            "lulucf_world": {
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
            world_lulucf_emissions=_world_row(
                inputs["world_co2_lulucf_mt"], "co2-lulucf"
            ),
            verbose=False,
            output_dir=tmp_path,
        )

    expected = pd.DataFrame(golden["expected"][emission_category])
    actual = result[expected.columns].reset_index(drop=True)
    actual["quantile"] = actual["quantile"].astype(float)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
    for row, (source, label) in enumerate(zip(actual["source"], actual["scenario"])):
        baseline_year = sources[source]["baseline_year"]
        bunkers = sum(inputs["bunkers_mt"][y] for y in range(2020, baseline_year))
        assert actual["rebase_bunkers_mt"][row] == round(bunkers)
        observed = sum(inputs["bunkers_mt"].values())
        assert actual["deduction_bunkers_mt"][row] == -round(
            observed + 0.05 * set_co2[GOLDEN_SET[label]]
        )
        if emission_category == "co2":
            gaps = inputs["scenario_adjustments"][GOLDEN_SET[label]]
            assert actual["correction_lulucf_convention_mt"][row] == round(
                gaps["convention_gap_median_from"][baseline_year]
            )


def test_convention_gap_starts_at_the_baseline_year():
    """Hand calculation: full years of the gap series from the baseline year.

    Observed NGHGI LULUCF is -4 Mt in each year to the splice year 2023.
    Scenario A: Direct 1, Indirect -5, so the gap is -5 in every year.
    Scenario B: Direct 2, Indirect -3: -6 to 2023, then -3.
    """
    years = [str(y) for y in range(2020, 2032)]
    nghgi = pd.Series(-4.0, index=years[:4])
    a = (pd.Series(1.0, index=years), pd.Series(-5.0, index=years))
    b = (pd.Series(2.0, index=years), pd.Series(-3.0, index=years))

    def gap(scenario, baseline_year, nz_year):
        direct, indirect = scenario
        return convention_gap_from_baseline(
            nghgi, direct, indirect, baseline_year, nz_year, splice_year=2023
        )

    assert gap(a, 2020, 2030) == pytest.approx(-50.0)
    assert gap(a, 2023, 2030.5) == pytest.approx(-37.5)
    assert gap(a, 2026, 2030) == pytest.approx(-20.0)
    # B: four years at -6 (2020-2023), then 2024 at -3: -27.
    assert gap(b, 2020, 2025) == pytest.approx(-27.0)
    assert gap(b, 2020, 2022) == pytest.approx(-12.0)
    # Net zero at or before the baseline year: no gap.
    assert gap(b, 2023, 2022) == 0.0


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

    # Net zero at the end of 2029: the crossing is 2030. Observed 2020-2023,
    # then the 2023 rate: 10 x 10 Mt.
    deduction = compute_bunker_deduction(bunkers, start_year=2020, net_zero_year=2030)
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
    assert result["rcb_2020_mt"] == 1000


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
    with pytest.raises(DataProcessingError, match="pass world_lulucf_emissions"):
        process_rcb_to_2020_baseline(rcb_value=660.0, rcb_baseline_year=2024, **kwargs)

    result = process_rcb_to_2020_baseline(
        rcb_value=1000.0, rcb_baseline_year=2020, **kwargs
    )
    assert result["rebase_lulucf_mt"] == 0
    assert result["rcb_2020_mt"] == 1000


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
        bunkers_deduction_mt=compute_bunker_deduction(bunkers, 2020, 2030),
        verbose=False,
    )
    assert result["rebase_fossil_mt"] == 600
    assert result["rebase_bunkers_mt"] == 60
    assert result["deduction_bunkers_mt"] == -100
    assert result["rcb_2020_mt"] == 1000


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


@pytest.mark.parametrize("value", [-1, 1.5, "1", None, True])
def test_rebase_fill_max_years_must_be_a_non_negative_integer(value):
    """Anything other than a count of zero or more is a configuration error."""
    with pytest.raises(ConfigurationError, match="rebase_fill_max_years"):
        validate_rebase_fill_max_years(value)
    assert validate_rebase_fill_max_years(0) == 0
    assert validate_rebase_fill_max_years(2) == 2
