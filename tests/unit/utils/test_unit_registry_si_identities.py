"""SI-consistency characterisation tests for the default unit registry.

These tests lock in the SI / IAMC / climate-science convention:

    1 kt = 10**6 kg = 1 Gg
    1 Mt = 10**9 kg = 1 Tg
    1 Gt = 10**12 kg = 1 Pg

They will fail on any registry that redefines the tonne-prefixed units
as 10**3, 10**6, 10**9 kg (the off-by-1000 bug that previously lived in
`get_default_unit_registry`).
"""

from __future__ import annotations

import openscm_units
import pytest

from fair_shares.library.utils.units import get_default_unit_registry


REL = 1e-12


def test_kt_equals_one_million_kg() -> None:
    ur = get_default_unit_registry()
    assert (1 * ur("kt")).to("kg").magnitude == pytest.approx(1_000_000.0, rel=REL)


def test_Mt_equals_one_billion_kg() -> None:
    ur = get_default_unit_registry()
    assert (1 * ur("Mt")).to("kg").magnitude == pytest.approx(1_000_000_000.0, rel=REL)


def test_Gt_equals_one_trillion_kg() -> None:
    ur = get_default_unit_registry()
    assert (1 * ur("Gt")).to("kg").magnitude == pytest.approx(
        1_000_000_000_000.0, rel=REL
    )


def test_Mt_equals_Tg_si_identity() -> None:
    ur = get_default_unit_registry()
    assert (1 * ur("Mt")).to("Tg").magnitude == pytest.approx(1.0, rel=REL)


def test_kt_equals_Gg_si_identity() -> None:
    ur = get_default_unit_registry()
    assert (1 * ur("kt")).to("Gg").magnitude == pytest.approx(1.0, rel=REL)


def test_Gt_equals_Pg_si_identity() -> None:
    ur = get_default_unit_registry()
    assert (1 * ur("Gt")).to("Pg").magnitude == pytest.approx(1.0, rel=REL)


@pytest.mark.parametrize(
    "unit", ["g", "kg", "t", "kt", "Mt", "Gt", "Gg", "Tg", "Pg"]
)
def test_cross_registry_consistency_with_openscm(unit: str) -> None:
    """The fair-shares registry must agree with stock openscm-units on every
    mass unit on the SI / tonne ladder."""
    ur = get_default_unit_registry()
    ref = openscm_units.unit_registry
    ours = (1 * ur(unit)).to("kg").magnitude
    theirs = (1 * ref(unit)).to("kg").magnitude
    assert ours == pytest.approx(theirs, rel=REL)


def test_iamc_global_fossil_co2_mt_to_gt() -> None:
    """5000 Mt CO2/yr is a plausible global fossil CO2 figure; in Gt it's 5."""
    ur = get_default_unit_registry()
    result = (5000 * ur("Mt CO2 / yr")).to("Gt CO2 / yr").magnitude
    assert result == pytest.approx(5.0, rel=REL)


def test_gcb_luc_tg_c_to_mt_co2() -> None:
    """1000 Tg C/yr converts to 1000 * 44/12 Mt CO2/yr by molar mass."""
    ur = get_default_unit_registry()
    result = (1000 * ur("Tg C / yr")).to("Mt CO2 / yr").magnitude
    assert result == pytest.approx(1000.0 * 44.0 / 12.0, rel=REL)


def test_gt_to_mt_within_family() -> None:
    """Sanity: 1 Gt CO2/yr = 1000 Mt CO2/yr under the fixed definitions."""
    ur = get_default_unit_registry()
    result = (1 * ur("Gt CO2 / yr")).to("Mt CO2 / yr").magnitude
    assert result == pytest.approx(1000.0, rel=REL)
