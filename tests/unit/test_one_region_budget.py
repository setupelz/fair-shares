"""Tests for the one-region helpers behind notebook 405."""

import pandas as pd
import pytest

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.python_api import (
    filter_to_anchors,
    period_means,
    regional_remaining_budgets,
    regional_targets,
    shift_to_period_start,
)


def _remaining(rows):
    base = {
        "category": "co2",
        "source": "forster_2026",
        "climate-assessment": "1.7C",
        "quantile": 0.67,
        "approach": "equal-per-capita-budget",
        "emission-category": "co2",
        "unit": "Mt * CO2",
        "allocation-year": 2015,
        "capability-weight": None,
        "netting-end-year": 2024,
        "remaining-from-year": 2025,
        "historical-deviation": float("nan"),
        "moved-to-row": None,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


@pytest.fixture
def remaining():
    rows = []
    for ay in (1990, 2015):
        for iso, alloc, used in (
            ("AAA", 100.0, 40.0),
            ("BBB", 50.0, 70.0),
            ("CCC", 900.0, 10.0),
        ):
            rows.append(
                {
                    "iso3c": iso,
                    "allocation-year": ay,
                    "allocated-total": alloc,
                    "consumed-actuals": used,
                    "remaining-budget": alloc - used,
                }
            )
    return _remaining(rows)


def test_region_sums_members_per_configuration(remaining):
    out = regional_remaining_budgets(remaining, ["AAA", "BBB"], "REG")
    assert len(out) == 2
    assert (out["iso3c"] == "REG").all()
    assert (out["n-countries"] == 2).all()
    assert out["allocated-total"].tolist() == [150.0, 150.0]
    assert out["remaining-budget"].tolist() == [40.0, 40.0]
    # All-NaN deviation stays NaN rather than becoming 0
    assert out["historical-deviation"].isna().all()


def test_region_rejects_unknown_member(remaining):
    with pytest.raises(ValueError, match="ZZZ"):
        regional_remaining_budgets(remaining, ["AAA", "ZZZ"], "REG")


def test_region_rejects_member_moved_into_row(remaining):
    remaining.loc[remaining["iso3c"] == "CCC", "moved-to-row"] = "BBB;DDD"
    with pytest.raises(ValueError, match="moved into ROW"):
        regional_remaining_budgets(remaining, ["AAA", "BBB"], "REG")


def test_region_rejects_configurations_it_cannot_tell_apart(remaining):
    # Same identifying columns twice, as when a grid varies cumulative_end_year
    doubled = pd.concat([remaining, remaining], ignore_index=True)
    with pytest.raises(ValueError, match="share every identifying column"):
        regional_remaining_budgets(doubled, ["AAA", "BBB"], "REG")


# Observed regional emissions: 10 per year to 2024
_OBSERVED = pd.Series({y: 10.0 for y in range(2015, 2025)})


def test_shift_later_start_subtracts_held_last_observed_value(remaining):
    reg = regional_remaining_budgets(remaining, ["AAA", "BBB"], "REG")
    # Budget runs from 2025; a period starting 2027 skips 2025 and 2026
    out = shift_to_period_start(reg, 2027, _OBSERVED)
    assert out["remaining-budget"].tolist() == [20.0, 20.0]
    assert (out["start-adjustment"] == -20.0).all()
    assert (out["start-adjustment-estimated-years"] == "2025;2026").all()
    assert (out["remaining-from-year"] == 2027).all()


def test_shift_earlier_start_adds_back_observed_years(remaining):
    reg = regional_remaining_budgets(remaining, ["AAA", "BBB"], "REG")
    # A period starting 2021 includes the observed years 2021-2024
    out = shift_to_period_start(reg, 2021, _OBSERVED)
    assert out["remaining-budget"].tolist() == [80.0, 80.0]
    assert (out["start-adjustment"] == 40.0).all()
    assert (out["start-adjustment-estimated-years"] == "").all()


def test_shift_same_start_changes_nothing(remaining):
    reg = regional_remaining_budgets(remaining, ["AAA"], "REG")
    out = shift_to_period_start(reg, 2025, _OBSERVED)
    pd.testing.assert_series_equal(out["remaining-budget"], reg["remaining-budget"])
    assert (out["start-adjustment"] == 0).all()


def test_shift_needs_observed_years_to_add_back(remaining):
    reg = regional_remaining_budgets(remaining, ["AAA"], "REG")
    with pytest.raises(ValueError, match="2014"):
        shift_to_period_start(reg, 2014, _OBSERVED)


def _loaded():
    rcbs = pd.DataFrame(
        {
            "source": ["s", "s", "s", "t"],
            "climate-assessment": ["1.5C", "1.7C", "2C", "1.7C"],
            "quantile": [0.5, 0.67, 0.67, 0.67],
        }
    )
    idx = pd.MultiIndex.from_tuples(
        [("1.5C", 0.5, "s"), ("1.7C", 0.67, "s"), ("1.7C", 0.67, "t")],
        names=["climate-assessment", "quantile", "source"],
    )
    scen = pd.DataFrame({"2030": [1.0, 2.0, 3.0]}, index=idx)
    return {"rcbs_data": {"co2": rcbs}, "scenarios_data": {"non-co2": scen}}


def test_filter_to_anchors_keeps_each_requested_anchor():
    data = _loaded()
    filter_to_anchors(data, "s", [("1.5C", 0.5), ("1.7C", 0.67)])
    kept = data["rcbs_data"]["co2"]
    assert sorted(kept["climate-assessment"]) == ["1.5C", "1.7C"]
    assert (kept["source"] == "s").all()
    assert data["scenarios_data"]["non-co2"]["2030"].tolist() == [1.0, 2.0]


def test_filter_to_anchors_names_available_labels_on_miss():
    with pytest.raises(ConfigurationError, match="1.7C"):
        filter_to_anchors(_loaded(), "s", [("1.6C", 0.5)])


# --- regional_targets: CO2 budget plus non-CO2 pathway -----------------------

_YEARS = [str(y) for y in range(2015, 2031)]


def _composite():
    """all-ghg-like inputs: CO2 budget rows, combined rows, non-CO2 pathways.

    AAA over-used non-CO2 by 6, BBB under-used by 4, CCC is outside the region.
    """
    cfg = {
        "category": "all-ghg",
        "source": "s",
        "climate-assessment": "1.7C",
        "quantile": 0.67,
        "unit": "Mt * CO2e",
        "capability-weight": 0.0,
        "netting-end-year": 2024,
        "remaining-from-year": 2025,
    }
    budget_cfg = {
        **cfg,
        "approach": "equal-per-capita-budget",
        "allocation-year": 2015,
        "preserve-allocation-year-shares": False,
    }
    rows = []
    for iso, rem, dev in (("AAA", 10.0, 6.0), ("BBB", 20.0, -4.0), ("CCC", 99.0, 1.0)):
        rows.append(
            {
                **budget_cfg,
                "iso3c": iso,
                "emission-category": "co2",
                "remaining-budget": rem,
                "historical-deviation": float("nan"),
            }
        )
        rows.append(
            {
                **budget_cfg,
                "iso3c": iso,
                "emission-category": "combined",
                "remaining-budget": rem + 100,
                "historical-deviation": dev,
            }
        )
    remaining = pd.DataFrame(rows)
    remaining["allocated-total"] = 0.0
    remaining["consumed-actuals"] = 0.0

    nonco2 = []
    for iso, level in (("AAA", 1.0), ("BBB", 2.0), ("CCC", 50.0)):
        nonco2.append(
            {
                **cfg,
                "iso3c": iso,
                "emission-category": "non-co2",
                "approach": "equal-per-capita",
                "first-allocation-year": 2015,
                "preserve-first-allocation-year-shares": False,
                **{y: level for y in _YEARS},
            }
        )
    return remaining, pd.DataFrame(nonco2)


def test_targets_charge_only_member_overuse_under_co2_debit():
    remaining, ab = _composite()
    out = regional_targets(remaining, ab, ["AAA", "BBB"], "REG").set_index(
        "nonco2-debt-mode"
    )
    assert out.loc["report-only", "co2-budget"] == 30.0
    # AAA's over-use of 6 is charged; BBB's under-use does not offset it
    assert out.loc["co2-debit", "nonco2-overuse"] == 6.0
    assert out.loc["co2-debit", "co2-budget"] == 24.0


def test_targets_carry_regional_nonco2_pathway_for_every_year():
    remaining, ab = _composite()
    out = regional_targets(remaining, ab, ["AAA", "BBB"], "REG")
    years = [c for c in out.columns if str(c).isdigit()]
    assert years[0] == "2015" and years[-1] == "2030"
    assert (out[years] == 3.0).all().all()


def test_targets_without_nonco2_part_return_budget_only(remaining):
    out = regional_targets(remaining, pd.DataFrame(), ["AAA", "BBB"], "REG")
    assert out["co2-budget"].tolist() == out["remaining-budget"].tolist()
    assert not any(str(c).isdigit() for c in out.columns)


def test_shift_moves_co2_budget_and_drops_pathway_years_before_start():
    remaining, ab = _composite()
    out = regional_targets(remaining, ab, ["AAA", "BBB"], "REG")
    shifted = shift_to_period_start(out, 2027, _OBSERVED)
    assert shifted["co2-budget"].tolist() == (out["co2-budget"] - 20.0).tolist()
    years = [c for c in shifted.columns if str(c).isdigit()]
    assert years[0] == "2027"


def test_period_means_label_each_period_by_its_last_year():
    annual = pd.DataFrame(
        {"k": ["a"], **{str(y): [float(y - 2025)] for y in range(2025, 2036)}}
    )
    out = period_means(annual, [2030, 2035], first_year=2026)
    # 2026-2030 -> mean(1..5) = 3; 2031-2035 -> mean(6..10) = 8
    assert out["2030"].iloc[0] == 3.0
    assert out["2035"].iloc[0] == 8.0
    assert out["k"].iloc[0] == "a"


def test_period_means_reject_label_before_start():
    annual = pd.DataFrame({str(y): [1.0] for y in range(2025, 2031)})
    with pytest.raises(ValueError, match="before the pathway start"):
        period_means(annual, [2025, 2030], first_year=2026)
