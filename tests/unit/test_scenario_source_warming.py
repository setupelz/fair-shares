"""Tests for derived warming at net zero and the SCI and ScenarioMIP source entries."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError
from fair_shares.library.utils.data.scenario_sets import (
    NET_ZERO_CROSSING,
    bunker_share_table,
    scenario_set_settings,
)
from fair_shares.library.utils.data.scenario_sources import (
    _duplicate_columns,
    apply_derived_net_zero,
    get_scenario_source,
    net_zero_years,
    warming_at_net_zero,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
YEARS = [str(y) for y in range(2020, 2101, 5)]


def _frame(rows: dict[str, list[float]]) -> pd.DataFrame:
    frame = pd.DataFrame.from_dict(rows, orient="index", columns=YEARS)
    frame.index = pd.MultiIndex.from_tuples(
        [("m", s) for s in frame.index], names=["Model", "Scenario"]
    )
    return frame


def test_warming_at_the_first_full_year_at_or_below_zero():
    co2 = _frame(
        {
            # Annual: 2026 3, 2027 1, 2028 -1 -> net zero in 2028.
            "crossing": [10.0, 5.0, *[-5.0] * 15],
            # Reaches exactly zero in 2025.
            "touch": [10.0, 0.0, *[-5.0] * 15],
            "never": [500.0] * 17,
        }
    )
    gsat = [1.0 + 0.04 * i for i in range(17)]  # +0.008 per year
    p67 = [g + 0.3 for g in gsat]
    result = warming_at_net_zero(
        co2,
        {
            "w50": _frame({s: gsat for s in ("crossing", "touch", "never")}),
            "w67": _frame({s: p67 for s in ("crossing", "touch", "never")}),
        },
    )
    row = result.loc[("m", "crossing")]
    assert row["net_zero_year"] == 2028
    assert row["w50"] == pytest.approx(1.0 + 0.008 * 8)  # 1.064
    assert row["w67"] == pytest.approx(1.364)
    assert result.loc[("m", "touch"), "net_zero_year"] == 2025
    assert result.loc[("m", "touch"), "w50"] == pytest.approx(1.04)
    # No net zero by 2100: no year, warming of 2100 (as the AR6 metadata).
    assert np.isnan(result.loc[("m", "never"), "net_zero_year"])
    assert result.loc[("m", "never"), "w50"] == pytest.approx(1.64)


@pytest.mark.parametrize("name", ["sci", "scenariomip"])
def test_derived_sources_declare_warming_non_co2_and_terms(name):
    source = get_scenario_source(name)
    assert set(source["terms"]) == {"bunkers", "non-co2"}
    assert set(source["derived_warming"]["gsat"]) == {"warming_median", "warming_p67"}
    assert set(source["metadata_columns"]) == {
        "net_zero_year",
        "warming_median",
        "warming_p67",
    }
    assert {"kyoto", "co2_variables"} <= set(source["non_co2"])
    registry = yaml.safe_load(
        (REPO_ROOT / "src/fair_shares/conf/data_registry.yaml").read_text()
    )
    entry = next(
        v
        for v in registry.values()
        if isinstance(v, dict) and source["registry_source"] in v
    )[source["registry_source"]]
    assert entry["tier"] == "manual" and entry["redistributable"] is False
    citation = (
        REPO_ROOT
        / Path(source["path"]).parent.as_posix().format(version=source["version"])
        / "CITATION.md"
    )
    assert citation.exists()


def test_default_pools_for_non_co2_and_the_bunker_share():
    settings = scenario_set_settings({})
    assert settings["non_co2"]["scenario_sources"] == ["ar6"]
    assert settings["bunkers"]["scenario_sources"] == ["ar6", "sci", "scenariomip"]
    rcb_yaml = yaml.safe_load((REPO_ROOT / "data/rcbs/rcbs.yaml").read_text())
    shipped = scenario_set_settings(rcb_yaml)
    assert shipped["non_co2"]["scenario_sources"] == ["ar6"]
    assert shipped["bunkers"]["scenario_sources"] == ["ar6", "sci", "scenariomip"]
    on = scenario_set_settings({"non_co2": {"scenario_sources": ["ar6", "sci"]}})
    assert on["non_co2"]["scenario_sources"] == ["ar6", "sci"]


def test_threshold_counts_as_net_zero_in_the_first_year_below_100_mt():
    """AR6 Table SPM.2 note j: harmonised or reported CO2 below 100 Mt by 2100."""
    co2 = _frame(
        {
            "crossing": [10.0, 5.0, *[-5.0] * 15],
            # Harmonised stays at 150 Mt; reported falls below 100 Mt in 2050.
            "reported": [500.0, *[150.0] * 16],
            "harmonised": [500.0, 300.0, *[90.0] * 15],
            "never": [500.0] * 17,
        }
    )
    reported = _frame(
        {"reported": [500.0, 400.0, 300.0, 200.0, 120.0, 110.0, 99.0, *[50.0] * 10]}
    )
    years = net_zero_years(co2, reported_mt=reported)
    assert years.loc[("m", "crossing")] == 2028
    assert years.loc[("m", "reported")] == 2050
    assert years.loc[("m", "harmonised")] == 2030  # 300 in 2025, 90 in 2030
    assert np.isnan(years.loc[("m", "never")])


def test_derived_columns_replace_metadata_with_ascii_matching():
    """Public-database exports write non-ASCII characters as "?"."""
    metadata = pd.DataFrame(
        {"nz": [2100.0, np.nan], "w": [2.0, 2.5]},
        index=pd.MultiIndex.from_tuples([("m", "Below 2\u00b0C"), ("m", "x")]),
    )
    derived = pd.DataFrame(
        {"nz": [2070.0, np.nan], "w": [1.8, 2.5]},
        index=pd.MultiIndex.from_tuples([("m", "Below 2?C"), ("m", "x")]),
    )
    result, changed = apply_derived_net_zero(metadata, derived)
    assert result.iloc[0].tolist() == [2070.0, 1.8]
    assert list(changed) == [("m", "Below 2\u00b0C")]
    with pytest.raises(DataProcessingError, match="No derived net-zero values"):
        apply_derived_net_zero(metadata, derived.iloc[:1])


def test_sci_releases_resolve_to_their_own_file_and_columns():
    """v2.0 is configured; v1.0 stays selectable; each names its own file."""
    v2 = get_scenario_source("sci")
    assert v2["version"] == "v2.0" and v2["registry_source"] == "sci-2026"
    assert v2["path"].endswith(
        "sci-2026-v2.0/SCI-2026_v2.0_pathways_ensemble_global.xlsx"
    )
    assert v2["vetting"] == {
        "column": "Historical Vetting [SCI 2025]",
        "keep": ["passed"],
    }
    assert "versions" not in v2
    v1 = get_scenario_source("sci", "v1.0")
    assert v1["registry_source"] == "sci-2025" and v1["vetting"]["keep"] == ["ok"]
    with pytest.raises(ConfigurationError, match="no version 'v9'"):
        get_scenario_source("sci", "v9")


def test_runs_carried_over_from_a_pooled_source_count_once():
    """SCI v2.0 flags its ScenarioMIP and AR6 runs; only pooled sources drop them."""
    sci = get_scenario_source("sci")
    assert _duplicate_columns(sci, False, ["ar6", "sci", "scenariomip"], "sci") == [
        "Scenario Ensemble|ScenarioMIP v0.1",
        "Scenario Ensemble|AR6",
    ]
    assert _duplicate_columns(sci, False, ["sci"], "sci") == []


def test_bunker_reporter_reaches_net_zero_below_100_mt():
    """Without a crossing of zero, the first full year below 100 Mt counts."""
    co2 = _frame({"low": [500.0, 300.0, *[90.0] * 15], "high": [500.0] * 17})
    bunkers = _frame({"low": [50.0] * 17, "high": [50.0] * 17})
    table = bunker_share_table({"sci": (co2, bunkers)}, family_of=lambda m: m)
    assert table["Scenario"].tolist() == ["low"]
    assert table[NET_ZERO_CROSSING].tolist() == [2030]
