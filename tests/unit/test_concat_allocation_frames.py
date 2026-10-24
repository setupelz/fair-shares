"""Stacking allocation frames whose approaches fill different columns."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from fair_shares.library.notebook_helpers import concat_allocation_frames


def test_columns_one_approach_leaves_empty_keep_their_dtype():
    with_weight = pd.DataFrame(
        {"approach": ["a"], "weight": [0.5], "note": [None], "2030": [1.0]}
    )
    without_weight = pd.DataFrame(
        {"approach": ["b"], "weight": [None], "note": [None], "2030": [2.0]}
    )
    assert without_weight["weight"].dtype == object

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = concat_allocation_frames([with_weight, without_weight])

    assert list(result.columns) == ["approach", "weight", "note", "2030"]
    assert result["weight"].dtype == np.float64
    assert result["weight"].isna().tolist() == [False, True]
    assert result["note"].isna().all()
    assert result["2030"].tolist() == [1.0, 2.0]


def test_empty_frames_are_left_out():
    filled = pd.DataFrame({"approach": ["a"], "2030": [1.0]})
    empty = pd.DataFrame({"approach": pd.Series([], dtype=object), "extra": []})

    result = concat_allocation_frames([empty, filled])

    assert list(result.columns) == ["approach", "extra", "2030"]
    assert result["approach"].tolist() == ["a"]
