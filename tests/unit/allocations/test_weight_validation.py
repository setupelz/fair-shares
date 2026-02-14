"""
Test suite for weight validation float precision.

This test suite identifies which float combinations trigger precision issues
in validate_weight_constraints(). The function checks if
responsibility_weight + capability_weight > 1.0, which may incorrectly
reject valid combinations due to floating-point arithmetic.

Context: Phase 1 of non-coder-experience.md
Issue: Weight validation may reject valid floats (spec section 1.1.2)
"""

from __future__ import annotations

import pytest

from fair_shares.library.allocations.core import validate_weight_constraints
from fair_shares.library.exceptions import AllocationError


class TestWeightValidationPrecision:
    """Test weight validation with float precision edge cases."""

    @pytest.mark.parametrize(
        "resp,cap",
        [
            # Exact decimal sums to 1.0
            (0.7, 0.3),
            (0.5, 0.5),
            (0.1, 0.9),
            (0.4, 0.6),
            (0.25, 0.75),
            # Common fractions that should work
            (0.333, 0.667),
            (0.2, 0.8),
            (0.125, 0.875),
            # Repeating decimals - likely precision issues
            (1 / 3, 2 / 3),  # 0.333... + 0.666... = 0.999...
            (0.1, 0.2),  # Common case, sum < 1.0 so should pass
            (0.333333, 0.666667),  # Approximations
            # Edge cases near 1.0
            (0.99, 0.01),
            (0.999, 0.001),
            (0.9999, 0.0001),
            # Both zero (valid - pure per capita)
            (0.0, 0.0),
            # One zero
            (1.0, 0.0),
            (0.0, 1.0),
        ],
    )
    def test_valid_weight_combinations_accepted(self, resp: float, cap: float) -> None:
        """Weights summing to <= 1.0 should be accepted.

        This test identifies float combinations that should be valid but might
        fail due to precision issues.
        """
        # This should NOT raise - these are all valid combinations
        validate_weight_constraints(resp, cap)

    @pytest.mark.parametrize(
        "resp,cap",
        [
            # Clearly exceeds 1.0
            (0.7, 0.4),  # 1.1
            (0.6, 0.5),  # 1.1
            (1.0, 0.1),  # 1.1
            (0.5, 0.6),  # 1.1
            (0.99, 0.02),  # 1.01
        ],
    )
    def test_invalid_weights_rejected(self, resp: float, cap: float) -> None:
        """Weights clearly exceeding 1.0 should be rejected."""
        with pytest.raises(AllocationError, match="Invalid allocation weights"):
            validate_weight_constraints(resp, cap)

    @pytest.mark.parametrize(
        "resp,cap",
        [
            (-0.1, 0.5),
            (0.5, -0.1),
            (-0.1, -0.1),
        ],
    )
    def test_negative_weights_rejected(self, resp: float, cap: float) -> None:
        """Negative weights should be rejected."""
        with pytest.raises(AllocationError, match="non-negative"):
            validate_weight_constraints(resp, cap)

    def test_precision_boundary_at_exactly_one(self) -> None:
        """Test the exact boundary case: sum exactly equals 1.0.

        This is the critical case where float precision matters most.
        """
        # These should all pass - sum is exactly 1.0
        validate_weight_constraints(0.3, 0.7)
        validate_weight_constraints(0.4, 0.6)
        validate_weight_constraints(0.5, 0.5)

        # Test computed values
        resp = 0.3
        cap = 1.0 - resp
        validate_weight_constraints(resp, cap)

    def test_precision_with_thirds(self) -> None:
        """Test problematic thirds that cause precision issues.

        1/3 + 2/3 in binary float representation doesn't exactly equal 1.0.
        This test verifies how the validator handles this edge case.
        """
        # Common way users might specify thirds
        one_third = 1 / 3
        two_thirds = 2 / 3

        # Check what the actual sum is
        actual_sum = one_third + two_thirds
        print(f"\n1/3 + 2/3 = {actual_sum}")
        print(f"Representation: {actual_sum!r}")

        # This should pass - sum is less than 1.0 (0.999...)
        validate_weight_constraints(one_third, two_thirds)

    def test_precision_diagnostic_tiny_excess(self) -> None:
        """Diagnostic test: What happens with tiny floating-point excess?

        This test explores what happens when the sum exceeds 1.0 by a tiny
        amount due to float representation. We construct a case that might
        trigger precision issues.
        """
        # Start with values that sum to exactly 1.0
        resp = 0.1
        cap = 0.9

        # These should work
        validate_weight_constraints(resp, cap)

        # Now test with slightly different representation
        resp_alt = 0.7
        cap_alt = 0.3
        validate_weight_constraints(resp_alt, cap_alt)

        # Test the actual floating-point sum
        sum_value = resp_alt + cap_alt
        print(f"\n0.7 + 0.3 = {sum_value}")
        print(f"Equals 1.0? {sum_value == 1.0}")
        print(f"Representation: {sum_value!r}")

    @pytest.mark.parametrize(
        "resp,cap,expected_sum",
        [
            (0.1, 0.2, 0.3),
            (0.1, 0.1, 0.2),
            (0.2, 0.3, 0.5),
            (0.1, 0.2, 0.30000000000000004),  # Known precision issue
        ],
    )
    def test_sum_representation(
        self, resp: float, cap: float, expected_sum: float
    ) -> None:
        """Document the actual float representation of sums.

        This is a diagnostic test to understand which sums have precision
        issues in their representation.
        """
        actual_sum = resp + cap
        print(f"\n{resp} + {cap} = {actual_sum} (expected: {expected_sum})")

        # Should pass - all these sums are < 1.0
        validate_weight_constraints(resp, cap)


class TestWeightValidationCorrectness:
    """Test that weight validation correctly enforces constraints."""

    def test_zero_weights_valid(self) -> None:
        """Both weights zero is valid (pure per capita allocation)."""
        validate_weight_constraints(0.0, 0.0)

    def test_full_responsibility_valid(self) -> None:
        """Full weight to responsibility is valid."""
        validate_weight_constraints(1.0, 0.0)

    def test_full_capability_valid(self) -> None:
        """Full weight to capability is valid."""
        validate_weight_constraints(0.0, 1.0)

    def test_partial_weights_valid(self) -> None:
        """Partial weights summing to < 1.0 leave room for per capita."""
        validate_weight_constraints(0.3, 0.4)  # Sum = 0.7, leaves 0.3 for per capita
        validate_weight_constraints(0.2, 0.5)  # Sum = 0.7, leaves 0.3 for per capita

    def test_equal_split_valid(self) -> None:
        """Equal split among all three principles is valid."""
        # 1/3 each: per capita, responsibility, capability
        validate_weight_constraints(1 / 3, 1 / 3)

    def test_weight_sum_exactly_one_valid(self) -> None:
        """Sum exactly 1.0 is valid (no per capita weight)."""
        validate_weight_constraints(0.6, 0.4)
        validate_weight_constraints(0.7, 0.3)

    def test_tiny_excess_rejected(self) -> None:
        """Even tiny excess over 1.0 should be rejected (current behavior).

        This test documents the current strict behavior. If we add tolerance,
        this test will need to be updated.
        """
        # 1.0 + epsilon should fail
        with pytest.raises(AllocationError):
            validate_weight_constraints(0.6, 0.40000001)
