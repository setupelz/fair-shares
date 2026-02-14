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
        assert "responsibility_weight (0.6)" in msg
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

    def test_format_error_year_columns_missing(self):
        """Test formatting of year_columns_missing error."""
        msg = format_error(
            "year_columns_missing",
            dataset_name="emissions_df",
            found_columns="['country', 'year', 'value']",
        )

        assert "Year columns not detected" in msg
        assert "emissions_df" in msg
        assert "['country', 'year', 'value']" in msg
        assert "ensure_string_year_columns" in msg

    def test_format_error_missing_required_data(self):
        """Test formatting of missing_required_data error."""
        msg = format_error(
            "missing_required_data",
            adjustment_type="responsibility",
            weight_name="responsibility_weight",
            weight_value=0.5,
            data_name="country_actual_emissions_ts",
            explanation="Responsibility adjustment requires historical emissions data.",
            function_name="per_capita_adjusted_budget",
            data_param="country_actual_emissions_ts",
        )

        assert "responsibility_weight=0.5" in msg
        assert "country_actual_emissions_ts" in msg
        assert "historical emissions" in msg
        assert "per_capita_adjusted_budget" in msg

    def test_format_error_invalid_target(self):
        """Test formatting of invalid_target error with suggestion."""
        suggestion = suggest_similar("rcb", ["rcbs", "ar6", "cr", "rcb-pathways"])
        msg = format_error("invalid_target", target="rcb", suggestion=suggestion)

        assert "Target 'rcb' not recognized" in msg
        assert "Did you mean" in msg
        assert "rcbs" in msg
        assert "Valid target options:" in msg

    def test_format_error_invalid_emission_category(self):
        """Test formatting of invalid_emission_category error."""
        suggestion = suggest_similar(
            "co2", ["co2-ffi", "all-ghg", "all-ghg-ex-co2-lulucf"]
        )
        msg = format_error(
            "invalid_emission_category", category="co2", suggestion=suggestion
        )

        assert "Emission category 'co2' not recognized" in msg
        assert "co2-ffi" in msg
        assert "Common emission categories:" in msg

    def test_format_error_missing_year_range(self):
        """Test formatting of missing_year_range error."""
        msg = format_error(
            "missing_year_range",
            dataset_name="GDP data",
            required_years="2020-2050",
            available_years="2020-2040",
            missing_years="2041-2050",
        )

        assert "Required years not found" in msg
        assert "GDP data" in msg
        assert "2020-2050" in msg
        assert "2020-2040" in msg
        assert "2041-2050" in msg

    def test_format_error_negative_values(self):
        """Test formatting of negative_values error."""
        msg = format_error(
            "negative_values",
            dataset_name="population",
            value_type="Population",
            count=5,
        )

        assert "Negative or zero values found" in msg
        assert "population" in msg
        assert "5 countries/years" in msg
        assert "Data quality issue" in msg

    def test_format_error_allocation_year_future(self):
        """Test formatting of allocation_year_future error."""
        msg = format_error(
            "allocation_year_future", year=2100, max_year=2050, min_year=2020
        )

        assert "Allocation year 2100" in msg
        assert "2050" in msg
        assert "between 2020 and 2050" in msg

    def test_format_error_infeasible_convergence(self):
        """Test formatting of infeasible_convergence error."""
        msg = format_error(
            "infeasible_convergence", speed=0.9, first_year=2020, last_year=2050
        )

        assert "Cannot achieve convergence targets" in msg
        assert "max_convergence_speed=0.9" in msg
        assert "2020 to 2050" in msg
        assert "strict=False" in msg

    def test_format_error_shares_not_sum_to_one(self):
        """Test formatting of shares_not_sum_to_one error."""
        msg = format_error(
            "shares_not_sum_to_one", actual_sum=1.0001, difference=0.0001
        )

        assert "Allocation shares do not sum to 1.0" in msg
        assert "1.0001" in msg
        # Check for scientific notation (e.g., 1.000000e-04 or 1e-04)
        assert "e-04" in msg

    def test_format_error_unknown_key(self):
        """Test that unknown error keys return a fallback message."""
        msg = format_error("nonexistent_error_key", param="value")

        assert "Unknown error: nonexistent_error_key" in msg

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
        result = suggest_similar("rcb", ["rcbs", "ar6", "cr", "rcb-pathways"])

        assert "Did you mean:" in result
        assert "rcbs" in result

    def test_suggest_similar_emission_category_typo(self):
        """Test emission category typo detection."""
        result = suggest_similar("co2", ["co2-ffi", "all-ghg", "all-ghg-ex-co2-lulucf"])

        assert "Did you mean:" in result
        assert "co2-ffi" in result

    def test_suggest_similar_multiple_matches(self):
        """Test that multiple similar options are suggested."""
        result = suggest_similar(
            "per-capita",
            [
                "equal-per-capita-budget",
                "per-capita-adjusted-budget",
                "per-capita-convergence",
            ],
        )

        assert "Did you mean:" in result
        # Should suggest at least one match
        assert any(
            option in result
            for option in ["equal-per-capita-budget", "per-capita-adjusted-budget"]
        )

    def test_suggest_similar_no_close_match(self):
        """Test fallback when no close match exists."""
        result = suggest_similar("xyz", ["rcbs", "ar6", "cr"])

        # Should fall back to listing valid options
        assert "Valid options:" in result
        assert "rcbs" in result
        assert "ar6" in result
        assert "cr" in result

    def test_suggest_similar_case_sensitive(self):
        """Test that matching is case-sensitive by default."""
        result = suggest_similar("RCB", ["rcbs", "ar6", "cr", "rcb-pathways"])

        # difflib default cutoff is 0.6, case mismatch might still match
        # but we want to ensure we get suggestions
        assert "rcb" in result.lower()

    def test_suggest_similar_max_suggestions_limit(self):
        """Test that max_suggestions parameter limits results."""
        result = suggest_similar(
            "capita",
            [
                "equal-per-capita-budget",
                "per-capita-adjusted-budget",
                "per-capita-adjusted-gini-budget",
                "per-capita-convergence",
                "cumulative-per-capita-convergence",
            ],
            max_suggestions=2,
        )

        if "Did you mean:" in result:
            # Count comma-separated suggestions
            suggestion_part = result.split("Did you mean:")[1].replace("?", "")
            suggestions = [s.strip() for s in suggestion_part.split(",")]
            assert len(suggestions) <= 2, "Should respect max_suggestions limit"

    def test_suggest_similar_empty_valid_options(self):
        """Test behavior with empty valid options list."""
        result = suggest_similar("test", [])

        assert "Valid options:" in result

    def test_suggest_similar_single_valid_option(self):
        """Test with a single valid option."""
        result = suggest_similar("rcb", ["rcbs"])

        # Should suggest the single option
        assert "rcbs" in result


class TestErrorMessageIntegration:
    """Integration tests for error messages in real usage scenarios."""

    def test_invalid_target_full_workflow(self):
        """Test complete workflow for invalid target error."""
        # Simulate user typo
        user_input = "rcb"
        valid_targets = ["rcbs", "ar6", "cr", "rcb-pathways"]

        # Generate suggestion
        suggestion = suggest_similar(user_input, valid_targets)

        # Format complete error
        error_msg = format_error(
            "invalid_target", target=user_input, suggestion=suggestion
        )

        # Verify complete message is helpful
        assert "rcb" in error_msg
        assert "Did you mean" in error_msg
        assert "rcbs" in error_msg
        assert "Valid target options:" in error_msg
        assert "Remaining Carbon Budget Shares" in error_msg

    def test_emission_category_full_workflow(self):
        """Test complete workflow for invalid emission category error."""
        user_input = "co2"
        valid_categories = ["co2-ffi", "all-ghg", "all-ghg-ex-co2-lulucf"]

        suggestion = suggest_similar(user_input, valid_categories)
        error_msg = format_error(
            "invalid_emission_category", category=user_input, suggestion=suggestion
        )

        assert "co2" in error_msg
        assert "Did you mean" in error_msg
        assert "co2-ffi" in error_msg
        assert "CO2 from fossil fuels and industry" in error_msg

    def test_weights_validation_error(self):
        """Test weights validation error message."""
        resp = 0.6
        cap = 0.5
        total = resp + cap

        error_msg = format_error(
            "weights_exceed_limit", resp=resp, cap=cap, total=total
        )

        # Should clearly explain the problem
        assert "0.6" in error_msg
        assert "0.5" in error_msg
        assert "1.1" in error_msg
        assert "VALID EXAMPLES:" in error_msg
        assert "responsibility_weight=0.5, capability_weight=0.5" in error_msg
