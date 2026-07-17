"""Tests for the wide-CSV approach-short summarizer.

Every summarized parameter must contribute a distinct fragment to
approach_short, so runs differing only in one parameter get distinct labels
rather than colliding into one string.
"""

from __future__ import annotations

import pandas as pd

from fair_shares.library.utils.data.parquet_to_csv import (
    build_approach_short_column,
)


def _base_row(**overrides):
    row = {
        "approach": "per-capita-adjusted",
        "first-allocation-year": 2020,
        "capability-weight": 1.0,
    }
    row.update(overrides)
    return row


def test_capability_reference_year_distinguishes_runs():
    df = pd.DataFrame(
        [
            _base_row(**{"capability-reference-year": 1990}),
            _base_row(**{"capability-reference-year": 2014}),
        ]
    )
    short = build_approach_short_column(df)
    assert short.iloc[0] != short.iloc[1]
    assert "cref1990" in short.iloc[0]
    assert "cref2014" in short.iloc[1]


def test_cumulative_end_year_distinguishes_budget_runs():
    df = pd.DataFrame(
        [
            {
                "approach": "equal-per-capita-budget",
                "allocation-year": 2020,
                "cumulative-end-year": 2050,
            },
            {
                "approach": "equal-per-capita-budget",
                "allocation-year": 2020,
                "cumulative-end-year": 2100,
            },
        ]
    )
    short = build_approach_short_column(df)
    assert short.iloc[0] != short.iloc[1]
    assert "cend2050" in short.iloc[0]
    assert "cend2100" in short.iloc[1]


def test_year_params_render_without_decimal():
    df = pd.DataFrame(
        [_base_row(**{"capability-reference-year": 2014})]
    )
    short = build_approach_short_column(df)
    assert "cref2014" in short.iloc[0]
    assert "cref2014.0" not in short.iloc[0]


def test_unset_reference_year_contributes_nothing():
    df = pd.DataFrame(
        [
            _base_row(**{"capability-reference-year": 2014}),
            _base_row(**{"capability-reference-year": pd.NA}),
        ]
    )
    short = build_approach_short_column(df)
    assert "cref" in short.iloc[0]
    assert "cref" not in short.iloc[1]
