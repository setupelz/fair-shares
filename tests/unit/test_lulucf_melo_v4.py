"""The opt-in LULUCF Data Hub v4.0.0 source (``melo-2026-v4``)."""

from __future__ import annotations

import pandas as pd
import pytest
import yaml

from fair_shares.library import paths
from fair_shares.library.data_registry import load_registry, normalise_target

KEY = "melo-2026-v4"


def _config() -> dict:
    raw = yaml.safe_load(
        paths.packaged_config("data_sources/data_sources_unified.yaml").read_text(
            encoding="utf-8"
        )
    )
    return raw["lulucf"][KEY]


def test_registry_entry_is_opt_in_and_matches_config():
    source = load_registry()[KEY]
    assert source.tier == "optional"
    assert source.doi == "10.5281/zenodo.22828743"
    assert source.license == "CC-BY-4.0"
    (download,) = source.downloads
    assert len(download.sha256) == 64
    assert normalise_target(_config()["path"]) == download.target


def test_world_row_and_years_come_from_the_gap_filled_file():
    config = _config()
    params = config["data_parameters"]
    # Another test seeds the cached data directory with a temp path.
    paths.reset_path_cache()
    path = paths.resolve_source_path(config["path"])
    if not path.exists():
        pytest.skip("v4.0.0 LULUCF file not fetched")

    raw = pd.read_csv(path)
    lulucf = raw[
        (raw[params["iso3_column"]] != "EU27")
        & (raw["Category"] == params["category_filter"])
        & (raw["Gas"] == params["gas_filter"])
    ]
    wide = lulucf.pivot_table(
        index=params["iso3_column"],
        columns=params["year_column"],
        values=params["value_column"],
        aggfunc="sum",
    )
    assert list(wide.columns) == list(range(2000, 2025))
    expected = raw[
        (raw[params["iso3_column"]] == params["world_key"])
        & (raw["Category"] == "LULUCF")
    ].set_index(params["year_column"])[params["value_column"]]
    pd.testing.assert_series_equal(
        wide.loc[params["world_key"]], expected, check_names=False
    )
