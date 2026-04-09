"""Tests for weight validation in validate_weight_constraints()."""

from __future__ import annotations

import pytest

from fair_shares.library.allocations.core import validate_weight_constraints
from fair_shares.library.exceptions import AllocationError


class TestWeightValidation:
    """Weight validation: valid, invalid, and negative cases."""

    @pytest.mark.parametrize(
        "resp,cap",
        [
            (0.0, 0.0),
            (1.0, 0.0),
            (0.0, 1.0),
            (0.5, 0.5),
            (0.7, 0.3),
            (0.1, 0.9),
            (0.25, 0.75),
            (1 / 3, 2 / 3),
            (1 / 3, 1 / 3),
            (0.333, 0.667),
            (0.99, 0.01),
            (0.9999, 0.0001),
            (0.3, 0.4),
        ],
    )
    def test_valid_weight_combinations_accepted(self, resp: float, cap: float) -> None:
        """Weights summing to <= 1.0 should be accepted."""
        validate_weight_constraints(resp, cap)

    @pytest.mark.parametrize(
        "resp,cap",
        [
            (0.7, 0.4),
            (0.6, 0.5),
            (1.0, 0.1),
            (0.5, 0.6),
            (0.99, 0.02),
            (0.6, 0.40000001),
        ],
    )
    def test_invalid_weights_rejected(self, resp: float, cap: float) -> None:
        """Weights exceeding 1.0 should be rejected."""
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
