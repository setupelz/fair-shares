"""
Tests for BUG 1 fix: RCB files use category-specific filenames.

Verifies that _process_and_save_rcbs() writes to rcbs_{emission_category}.csv
instead of the old rcbs.csv, so that two different emission categories produce
separate files and do not overwrite each other.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import yaml

from fair_shares.library.utils.dataframes import ensure_string_year_columns


def _make_mock_orchestrator(tmp_path: Path, emission_category: str) -> MagicMock:
    """Create a mock DataPreprocessor with the given emission_category."""
    orch = MagicMock()
    orch.emission_category = emission_category
    orch.processed_intermediate_dir = tmp_path
    orch.project_root = tmp_path
    return orch


def _make_rcb_yaml(tmp_path: Path) -> Path:
    """Create a minimal RCB YAML file in tmp_path/data/rcbs.yaml."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = data_dir / "rcbs.yaml"
    yaml_path.write_text(
        yaml.dump(
            {
                "rcb_data": {
                    "test-source": {
                        "baseline_year": 2020,
                        "unit": "Gt CO2",
                        "scenarios": {"1.5p50": 500, "2p67": 1150},
                    }
                }
            }
        )
    )
    return yaml_path


def _make_world_emissions() -> pd.DataFrame:
    """Create minimal world emissions timeseries for load_and_process_rcbs."""
    years = [str(y) for y in range(2015, 2025)]
    data = {yr: [36000.0] for yr in years}
    df = pd.DataFrame(
        data,
        index=pd.MultiIndex.from_tuples(
            [("World", "Mt * CO2e", "co2-ffi")],
            names=["iso3c", "unit", "emission-category"],
        ),
    )
    return ensure_string_year_columns(df)


def _make_mock_rcb_df(rcb_value: float) -> pd.DataFrame:
    """Create a mock DataFrame like load_and_process_rcbs returns."""
    return pd.DataFrame(
        {
            "source": ["test-source"],
            "climate-assessment": ["1.5C"],
            "quantile": [0.5],
            "rcb_2020_nghgi_mt": [rcb_value * 1000],
        }
    )


def _make_config() -> dict:
    """Create a minimal config dict with the structure _process_and_save_rcbs expects."""
    return {
        "targets": {
            "rcbs": {
                "path": "data/rcbs.yaml",
                "data_parameters": {
                    "adjustments": {},
                },
            },
        },
    }


def _call_process_and_save_rcbs(orch, config, world_fossil_emissions, mock_rcb_df):
    """Call _process_and_save_rcbs with load_and_process_rcbs and AdjustmentsConfig mocked."""
    mock_adjustments_config = MagicMock()

    with (
        patch(
            "fair_shares.library.preprocessing.rcbs.load_and_process_rcbs",
            return_value=mock_rcb_df,
        ),
        patch(
            "fair_shares.library.config.models.AdjustmentsConfig.model_validate",
            return_value=mock_adjustments_config,
        ),
    ):
        from fair_shares.library.pipeline.preprocessing import _process_and_save_rcbs

        _process_and_save_rcbs(
            orch, config, world_fossil_emissions=world_fossil_emissions
        )


class TestRCBCategorySpecificFilenames:
    """Tests that RCB output files use category-specific filenames."""

    def test_process_and_save_rcbs_writes_category_filename(self, tmp_path):
        """_process_and_save_rcbs writes to rcbs_{emission_category}.csv."""
        _make_rcb_yaml(tmp_path)

        category = "co2-ffi"
        orch = _make_mock_orchestrator(tmp_path, category)
        config = _make_config()

        _call_process_and_save_rcbs(
            orch, config, _make_world_emissions(), _make_mock_rcb_df(500)
        )

        expected_path = tmp_path / "rcbs_co2-ffi.csv"
        assert (
            expected_path.exists()
        ), f"Expected {expected_path} to exist, but it does not"

    def test_two_categories_produce_separate_files(self, tmp_path):
        """Two different emission categories produce separate RCB files (core BUG 1 fix)."""
        _make_rcb_yaml(tmp_path)
        config = _make_config()

        # Pass 1: co2-ffi
        orch_ffi = _make_mock_orchestrator(tmp_path, "co2-ffi")
        _call_process_and_save_rcbs(
            orch_ffi, config, _make_world_emissions(), _make_mock_rcb_df(500)
        )

        # Pass 2: co2
        orch_co2 = _make_mock_orchestrator(tmp_path, "co2")
        _call_process_and_save_rcbs(
            orch_co2, config, _make_world_emissions(), _make_mock_rcb_df(600)
        )

        # Both files must exist
        ffi_path = tmp_path / "rcbs_co2-ffi.csv"
        co2_path = tmp_path / "rcbs_co2.csv"
        assert ffi_path.exists(), "rcbs_co2-ffi.csv should exist after co2-ffi pass"
        assert co2_path.exists(), "rcbs_co2.csv should exist after co2 pass"

        # Files must have different content (different rcb_2020_nghgi_mt values)
        ffi_df = pd.read_csv(ffi_path)
        co2_df = pd.read_csv(co2_path)
        assert ffi_df["rcb_2020_nghgi_mt"].iloc[0] == 500000.0
        assert co2_df["rcb_2020_nghgi_mt"].iloc[0] == 600000.0

    def test_old_rcbs_csv_not_created(self, tmp_path):
        """The old undifferentiated rcbs.csv should NOT be created."""
        _make_rcb_yaml(tmp_path)
        config = _make_config()

        orch = _make_mock_orchestrator(tmp_path, "co2-ffi")
        _call_process_and_save_rcbs(
            orch, config, _make_world_emissions(), _make_mock_rcb_df(500)
        )

        old_path = tmp_path / "rcbs.csv"
        assert (
            not old_path.exists()
        ), "rcbs.csv should not be created — only rcbs_{category}.csv"
