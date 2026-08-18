"""Tests for the OWID population column resolution.

OWID rewrites its population export in place with no version identifier, and
has already renamed the value column once ("Population (historical
estimates)" -> "Population"). The loader must accept every known spelling and
fail with a diagnostic -- not a bare KeyError -- on an unknown one. A fresh
`fetch-data` pulls whatever OWID currently serves (the source is registered
`unversioned`), so a new user following the README is the most likely person
to hit a rename first.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.iamc_historical.socioeconomic import (
    _load_population,
    owid_population_column,
)


def _owid_csv(tmp_path, population_column: str):
    path = tmp_path / "population.csv"
    pd.DataFrame(
        {
            "Entity": ["Brazil", "Brazil", "India", "India"],
            "Code": ["BRA", "BRA", "IND", "IND"],
            "Year": [2019, 2020, 2019, 2020],
            population_column: [211e6, 213e6, 1366e6, 1380e6],
        }
    ).to_csv(path, index=False)
    return path


@pytest.mark.parametrize(
    "column", ["Population", "Population (historical estimates)"]
)
def test_both_known_owid_spellings_load(tmp_path, column) -> None:
    wide = _load_population(_owid_csv(tmp_path, column), unit="million")

    assert set(wide["region"]) == {"bra", "ind"}
    bra = wide[wide["region"] == "bra"].iloc[0]
    assert bra[2020] == pytest.approx(213.0)  # people -> million


def test_unknown_column_fails_with_diagnostic(tmp_path) -> None:
    with pytest.raises(DataProcessingError, match="Population"):
        _load_population(
            _owid_csv(tmp_path, "Population (2027 revision)"), unit="million"
        )


def test_newest_spelling_wins_when_both_present() -> None:
    columns = ["Entity", "Code", "Year", "Population (historical estimates)", "Population"]
    assert owid_population_column(columns) == "Population"
