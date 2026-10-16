"""The non-CO2 debt mode names and the deprecated ``free-rider`` alias."""

import pytest

from fair_shares.library.python_api import (
    NONCO2_DEBT_MODES,
    normalise_nonco2_debt_mode,
)


@pytest.mark.parametrize("mode", NONCO2_DEBT_MODES)
def test_canonical_modes_pass_through(mode):
    assert normalise_nonco2_debt_mode(mode) == mode


def test_free_rider_maps_to_report_only_with_warning():
    with pytest.warns(DeprecationWarning, match="report-only"):
        assert normalise_nonco2_debt_mode("free-rider") == "report-only"


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="Unknown nonco2 debt mode"):
        normalise_nonco2_debt_mode("forgive")
