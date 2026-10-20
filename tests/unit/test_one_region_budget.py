"""Tests for the one-region helpers behind notebook 405."""

import pandas as pd
import pytest

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.python_api import (
    filter_to_anchors,
    land_use_condition,
    member_targets,
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


# --- member_targets and land_use_condition -----------------------------------


def _write_country_series(directory, part, values):
    """Processed country series of ``part``: ``values`` maps ISO3 to {year: Mt}."""
    directory.mkdir(parents=True, exist_ok=True)
    rows = [
        {"iso3c": iso, **{str(y): v for y, v in s.items()}} for iso, s in values.items()
    ]
    pd.DataFrame(rows).to_csv(
        directory / f"country_emissions_{part}_timeseries.csv", index=False
    )


def test_members_sum_to_region_from_the_period_start(remaining, tmp_path):
    flat = {y: 5.0 for y in range(2015, 2025)}
    _write_country_series(tmp_path, "co2", {"AAA": flat, "BBB": flat})
    region = shift_to_period_start(
        regional_targets(remaining, pd.DataFrame(), ["AAA", "BBB"], "REG"),
        2020,
        pd.Series({y: 10.0 for y in range(2015, 2025)}),
    )
    members = member_targets(
        remaining, pd.DataFrame(), ["AAA", "BBB"], tmp_path, "co2", 2020
    )
    assert sorted(members["iso3c"].unique()) == ["AAA", "BBB"]
    # Each member adds back its own 2020-2024 emissions (25)
    assert (members["start-adjustment"] == 25.0).all()
    summed = members.groupby("allocation-year")["co2-budget"].sum()
    assert summed.tolist() == region.set_index("allocation-year")["co2-budget"].tolist()


_RCBS = pd.DataFrame(
    {
        "source": ["forster_2026"],
        "climate-assessment": ["1.7C"],
        "quantile": [0.67],
        "baseline_year": [2026],
        "nz_year_median": [2061.0],
        "deduction_lulucf_future_mt": [-1050.0],
    }
)


@pytest.fixture
def land_dirs(tmp_path):
    years = range(2020, 2025)
    bookkeeping = {
        "AAA": {y: v for y, v in zip(years, [1.0, 2.0, 3.0, 4.0, 5.0])},
        "BBB": {y: 0.0 for y in years},
    }
    inventory = {
        "AAA": {y: v for y, v in zip(years, [-9.0, -8.0, -7.0, -6.0, -5.0])},
        "BBB": {y: -10.0 for y in years},
    }
    _write_country_series(tmp_path / "bm", "co2-lulucf", bookkeeping)
    _write_country_series(tmp_path / "inv", "co2-lulucf", inventory)
    return tmp_path / "bm", tmp_path / "inv"


def _condition(remaining, land_dirs, rcbs=_RCBS):
    region = regional_targets(remaining, pd.DataFrame(), ["AAA", "BBB"], "REG")
    member = regional_targets(remaining, pd.DataFrame(), ["AAA"], "AAA")
    return land_use_condition(
        pd.concat([region, member], ignore_index=True),
        remaining,
        rcbs,
        {"REG": ["AAA", "BBB"], "AAA": ["AAA"]},
        bookkeeping_dir=land_dirs[0],
        inventory_dir=land_dirs[1],
    ).set_index(["iso3c", "allocation-year"])


def test_land_allowance_is_the_share_of_the_removed_global_term(remaining, land_dirs):
    out = _condition(remaining, land_dirs)
    # World allocation 1050; the region holds 150, AAA 100
    assert out.loc[("REG", 2015), "land-allowance-mt"] == pytest.approx(150.0)
    assert out.loc[("AAA", 2015), "land-allowance-mt"] == pytest.approx(100.0)
    assert out.loc[("REG", 2015), "land-allowance-mt-per-yr"] == pytest.approx(
        150.0 / 35
    )
    assert out.loc[("REG", 2015), "land-from-year"] == 2026


def test_land_allowance_is_zero_when_the_cap_removes_nothing(remaining, land_dirs):
    capped = _RCBS.assign(deduction_lulucf_future_mt=-0.0)
    out = _condition(remaining, land_dirs, capped)
    assert (out["land-allowance-mt"] == 0).all()
    # The inventory equivalent is then the indirect gap alone
    pd.testing.assert_series_equal(
        out["inventory-equivalent-median"],
        out["indirect-gap-median"],
        check_names=False,
    )


def test_land_observed_stats_and_indirect_gap_per_area(remaining, land_dirs):
    out = _condition(remaining, land_dirs).xs(2015, level="allocation-year")
    assert out.loc["AAA", "bookkeeping-observed-median"] == 3.0
    assert out.loc["AAA", "bookkeeping-observed-min"] == 1.0
    assert out.loc["AAA", "bookkeeping-observed-max"] == 5.0
    # Region: bookkeeping 1..5, inventory -19..-15; gap -20 every year
    assert out.loc["REG", "indirect-gap-median"] == -20.0
    assert out.loc["REG", "indirect-gap-min"] == -20.0
    assert out.loc["REG", "inventory-observed-median"] == -17.0


def test_land_condition_needs_every_observed_year(remaining, land_dirs, tmp_path):
    short = {"AAA": {2020: 1.0}, "BBB": {2020: 0.0}}
    _write_country_series(tmp_path / "short", "co2-lulucf", short)
    with pytest.raises(ValueError, match="bookkeeping land-use CO2 for REG"):
        _condition(remaining, (tmp_path / "short", land_dirs[1]))


def test_land_condition_matches_targets_shifted_to_a_period_start(remaining, land_dirs):
    region = shift_to_period_start(
        regional_targets(remaining, pd.DataFrame(), ["AAA", "BBB"], "REG"),
        2020,
        _OBSERVED,
    )
    out = land_use_condition(
        region,
        remaining,
        _RCBS,
        {"REG": ["AAA", "BBB"]},
        bookkeeping_dir=land_dirs[0],
        inventory_dir=land_dirs[1],
    )
    assert out["land-allowance-mt"].tolist() == pytest.approx([150.0, 150.0])
