"""
Tests for error message formatting and typo detection.

These tests ensure that:
1. Error message templates format correctly with parameters
2. The suggest_similar function properly detects typos
3. All error messages follow the WHAT/CAUSE/FIX structure
"""

from __future__ import annotations

from fair_shares.library.error_messages import (
    ERROR_MESSAGES,
    format_error,
    suggest_similar,
)


class TestErrorMessageFormatting:
    """Test error message template formatting."""

    def test_format_error_weights_exceed_limit(self):
        """Test formatting of weights_exceed_limit error."""
        msg = format_error("weights_exceed_limit", resp=0.6, cap=0.5, total=1.1)

        # Check key components are present
        assert "WHAT HAPPENED:" in msg
        assert "pre_allocation_responsibility_weight (0.6)" in msg
        assert "capability_weight (0.5)" in msg
        assert "1.1" in msg
        assert "VALID EXAMPLES:" in msg

    def test_format_error_index_structure_mismatch(self):
        """Test formatting of index_structure_mismatch error."""
        msg = format_error(
            "index_structure_mismatch",
            dataset_name="population_ts",
            expected="['iso3c', 'unit']",
            actual="['country', 'unit']",
        )

        # Check WHAT/CAUSE/FIX structure
        assert "WHAT HAPPENED:" in msg
        assert "LIKELY CAUSE:" in msg
        assert "HOW TO FIX:" in msg

        # Check specifics
        assert "population_ts" in msg
        assert "['iso3c', 'unit']" in msg
        assert "['country', 'unit']" in msg
        assert "set_index" in msg

    def test_all_error_messages_have_structure(self):
        """Test that all error messages follow WHAT/CAUSE/FIX or similar structure."""
        # Some errors use different but valid structures
        alternative_keywords = ["WHY:", "VALID EXAMPLES:", "LIKELY CAUSE:"]

        for key, template in ERROR_MESSAGES.items():
            # Every error should have at least some structure keywords
            has_structure = any(
                keyword in template
                for keyword in [
                    "WHAT HAPPENED:",
                    "HOW TO FIX:",
                    "WHY:",
                    *alternative_keywords,
                ]
            )
            assert has_structure, f"Error '{key}' missing structural keywords"


class TestSuggestSimilar:
    """Test typo detection and suggestion functionality."""

    def test_suggest_similar_exact_typo_rcb_to_rcbs(self):
        """Test the canonical typo case: rcb -> rcbs."""
        result = suggest_similar("rcb", ["rcbs", "pathway", "cr", "rcb-pathways"])

        assert "Did you mean:" in result
        assert "rcbs" in result

    def test_suggest_similar_no_close_match(self):
        """Test fallback when no close match exists."""
        result = suggest_similar("xyz", ["rcbs", "pathway", "cr"])

        # Should fall back to listing valid options
        assert "Valid options:" in result
        assert "rcbs" in result
        assert "pathway" in result
        assert "cr" in result

    def test_suggest_similar_empty_valid_options(self):
        """Test behavior with empty valid options list."""
        result = suggest_similar("test", [])

        assert "Valid options:" in result
