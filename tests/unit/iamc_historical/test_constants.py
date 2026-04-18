"""Tests for YAML-driven data-source configuration."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from fair_shares.library.iamc_historical import constants


def test_active_release_resolves_to_known_entry() -> None:
    """The ``active_iamc_historical`` tag must name a real release entry."""
    assert (
        constants.LATEST_IAMC_HISTORICAL_RELEASE in constants.IAMC_HISTORICAL_RELEASES
    )


def test_release_entries_expose_required_keys() -> None:
    for tag, rec in constants.IAMC_HISTORICAL_RELEASES.items():
        assert "package_dir" in rec, f"{tag} missing package_dir"
        assert "files" in rec, f"{tag} missing files"
        assert "country_feather" in rec["files"], f"{tag} files missing country_feather"


def test_reload_picks_up_new_release_added_to_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_yaml = tmp_path / "iamc_data_sources.yaml"
    fake_yaml.write_text(
        dedent(
            """
            active_iamc_historical: "2099.01.01"

            iamc_historical:
              "2099.01.01":
                package_dir: "data/emissions/future-historical-2099.01.01"
                concept_doi: "10.5281/zenodo.99999999"
                licence: "CC-BY-4.0"
                files:
                  country_feather: "country-history.feather"
                  global_csv: "global-workflow-history.csv"
            """
        ).strip()
    )
    monkeypatch.setattr(constants, "_CONFIG_PATH", fake_yaml)
    constants.reload_releases()
    assert constants.LATEST_IAMC_HISTORICAL_RELEASE == "2099.01.01"
    assert "2099.01.01" in constants.IAMC_HISTORICAL_RELEASES
