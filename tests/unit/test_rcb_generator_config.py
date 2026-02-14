"""
Tests for rcb_generator parameter in configuration and source_id generation.

"""

from __future__ import annotations

import pytest

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.utils.data.config import (
    build_data_config,
    build_source_id,
)


class TestRcbGeneratorConfig:
    """Tests for rcb_generator parameter handling in build_data_config."""

    def test_rcb_pathways_default_generator(self):
        """Test that rcb-pathways target defaults to exponential-decay generator."""
        active_sources = {
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "unu-wider-2025",
            "target": "rcb-pathways",
        }

        config, source_id = build_data_config("co2-ffi", active_sources)

        # Check that default generator was set
        assert config.rcb_generator == "exponential-decay"
        assert "rcb_generator" in config.model_dump()

    def test_rcb_pathways_explicit_generator(self):
        """Test that explicit rcb_generator is accepted for rcb-pathways."""
        active_sources = {
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "unu-wider-2025",
            "target": "rcb-pathways",
            "rcb_generator": "exponential-decay",
        }

        config, source_id = build_data_config("co2-ffi", active_sources)

        assert config.rcb_generator == "exponential-decay"

    def test_rcb_pathways_invalid_generator(self):
        """Test that invalid generator raises ConfigurationError."""
        active_sources = {
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "unu-wider-2025",
            "target": "rcb-pathways",
            "rcb_generator": "invalid-generator",
        }

        with pytest.raises(ConfigurationError, match="Invalid rcb_generator"):
            build_data_config("co2-ffi", active_sources)

    def test_non_rcb_pathways_with_generator_raises_error(self):
        """Test that rcb_generator with non-rcb-pathways target raises error."""
        # Test with ar6 target
        active_sources_ar6 = {
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "unu-wider-2025",
            "target": "ar6",
            "rcb_generator": "exponential-decay",
        }

        with pytest.raises(
            ConfigurationError,
            match="rcb_generator parameter is only valid for target='rcb-pathways'",
        ):
            build_data_config("co2-ffi", active_sources_ar6)

        # Test with rcbs target
        active_sources_rcbs = {
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "unu-wider-2025",
            "target": "rcbs",
            "rcb_generator": "exponential-decay",
        }

        with pytest.raises(
            ConfigurationError,
            match="rcb_generator parameter is only valid for target='rcb-pathways'",
        ):
            build_data_config("co2-ffi", active_sources_rcbs)

    def test_non_rcb_pathways_without_generator(self):
        """Test that non-rcb-pathways targets work without generator."""
        active_sources = {
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "unu-wider-2025",
            "target": "rcbs",
        }

        config, source_id = build_data_config("co2-ffi", active_sources)

        # rcb_generator should be None for non-rcb-pathways
        assert config.rcb_generator is None


class TestSourceIdWithGenerator:
    """Tests for source_id generation with rcb_generator parameter."""

    def test_source_id_with_rcb_pathways_and_generator(self):
        """Test that source_id includes generator for rcb-pathways."""
        source_id = build_source_id(
            emissions="primap-202503",
            gdp="wdi-2025",
            population="un-owid-2025",
            gini="unu-wider-2025",
            target="rcb-pathways",
            emission_category="co2-ffi",
            rcb_generator="exponential-decay",
        )

        expected = (
            "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_"
            "rcb-pathways-exponential-decay_co2-ffi"
        )
        assert source_id == expected

    def test_source_id_rcb_pathways_without_generator(self):
        """Test that source_id defaults to exponential-decay for rcb-pathways."""
        source_id = build_source_id(
            emissions="primap-202503",
            gdp="wdi-2025",
            population="un-owid-2025",
            gini="unu-wider-2025",
            target="rcb-pathways",
            emission_category="co2-ffi",
            rcb_generator=None,
        )

        # rcb-pathways now defaults to exponential-decay when no generator specified
        expected = (
            "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_"
            "rcb-pathways-exponential-decay_co2-ffi"
        )
        assert source_id == expected

    def test_source_id_non_rcb_pathways_with_generator(self):
        """Test that generator is ignored for non-rcb-pathways targets."""
        # For ar6
        source_id_ar6 = build_source_id(
            emissions="primap-202503",
            gdp="wdi-2025",
            population="un-owid-2025",
            gini="unu-wider-2025",
            target="ar6",
            emission_category="co2-ffi",
            rcb_generator="exponential-decay",
        )

        expected_ar6 = "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_ar6_co2-ffi"
        assert source_id_ar6 == expected_ar6

        # For rcbs
        source_id_rcbs = build_source_id(
            emissions="primap-202503",
            gdp="wdi-2025",
            population="un-owid-2025",
            gini="unu-wider-2025",
            target="rcbs",
            emission_category="co2-ffi",
            rcb_generator="exponential-decay",
        )

        expected_rcbs = (
            "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_rcbs_co2-ffi"
        )
        assert source_id_rcbs == expected_rcbs

    def test_source_id_non_rcb_pathways_without_generator(self):
        """Test source_id for non-rcb-pathways targets without generator."""
        source_id = build_source_id(
            emissions="primap-202503",
            gdp="wdi-2025",
            population="un-owid-2025",
            gini="unu-wider-2025",
            target="ar6",
            emission_category="all-ghg",
        )

        expected = "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_ar6_all-ghg"
        assert source_id == expected

    def test_integration_config_and_source_id(self):
        """Test that build_data_config generates correct source_id with generator."""
        active_sources = {
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "unu-wider-2025",
            "target": "rcb-pathways",
            "rcb_generator": "exponential-decay",
        }

        config, source_id = build_data_config("co2-ffi", active_sources)

        # Check config has generator
        assert config.rcb_generator == "exponential-decay"

        # Check source_id includes generator
        expected_source_id = (
            "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_"
            "rcb-pathways-exponential-decay_co2-ffi"
        )
        assert source_id == expected_source_id
