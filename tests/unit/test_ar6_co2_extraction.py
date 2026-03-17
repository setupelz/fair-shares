"""Tests for BUG 3 fix: co2 category support in AR6 scenario extraction.

Verifies that:
1. co2 is listed in AR6 available_categories in data_sources_unified.yaml
2. The Pydantic DataSourcesConfig model accepts co2 as emission_category
"""

from __future__ import annotations

import pytest
import yaml
from pyprojroot import here

from fair_shares.library.config.models import DataSourcesConfig


class TestAR6Co2YAMLConfig:
    """Test that co2 is available in AR6 configuration."""

    @pytest.fixture(scope="class")
    def data_sources_config(self):
        """Load the unified data sources YAML config."""
        config_path = here() / "conf/data_sources/data_sources_unified.yaml"
        with open(config_path) as f:
            return yaml.safe_load(f)

    def test_co2_in_ar6_available_categories(self, data_sources_config):
        """co2 must be in AR6 scenario source available_categories."""
        ar6_categories = data_sources_config["scenarios"]["ar6"]["data_parameters"][
            "available_categories"
        ]
        assert (
            "co2" in ar6_categories
        ), f"'co2' not found in AR6 available_categories: {ar6_categories}"

    def test_co2_ffi_still_in_ar6_available_categories(self, data_sources_config):
        """co2-ffi must remain in AR6 available_categories (regression)."""
        ar6_categories = data_sources_config["scenarios"]["ar6"]["data_parameters"][
            "available_categories"
        ]
        assert "co2-ffi" in ar6_categories

    def test_all_ghg_still_in_ar6_available_categories(self, data_sources_config):
        """all-ghg must remain in AR6 available_categories (regression)."""
        ar6_categories = data_sources_config["scenarios"]["ar6"]["data_parameters"][
            "available_categories"
        ]
        assert "all-ghg" in ar6_categories

    def test_all_ghg_ex_co2_lulucf_still_in_ar6_available_categories(
        self, data_sources_config
    ):
        """all-ghg-ex-co2-lulucf must remain in AR6 available_categories (regression)."""
        ar6_categories = data_sources_config["scenarios"]["ar6"]["data_parameters"][
            "available_categories"
        ]
        assert "all-ghg-ex-co2-lulucf" in ar6_categories


class TestPydanticModelAcceptsCo2:
    """Test that Pydantic DataSourcesConfig accepts co2 as emission_category."""

    def test_co2_is_valid_emission_category_literal(self):
        """co2 must be accepted by the emission_category Literal type."""
        # Verify co2 is in the Literal type annotation
        import typing

        hints = typing.get_type_hints(DataSourcesConfig)
        emission_cat_type = hints["emission_category"]
        # Extract Literal args
        args = typing.get_args(emission_cat_type)
        assert (
            "co2" in args
        ), f"'co2' not in DataSourcesConfig.emission_category Literal: {args}"

    def test_existing_categories_still_valid(self):
        """Existing categories must remain valid (regression)."""
        import typing

        hints = typing.get_type_hints(DataSourcesConfig)
        emission_cat_type = hints["emission_category"]
        args = typing.get_args(emission_cat_type)
        for expected in ["co2-ffi", "all-ghg", "all-ghg-ex-co2-lulucf"]:
            assert (
                expected in args
            ), f"'{expected}' missing from emission_category Literal: {args}"
