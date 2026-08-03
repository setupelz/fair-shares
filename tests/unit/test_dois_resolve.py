"""Check the recorded DOIs still resolve at the registrars.

Not part of the normal test run. These tests need the network and depend on
DataCite, Crossref and doi.org being up, so a failure here often means a service
is having a bad day rather than that anything in this repository is wrong.

Run them on purpose, occasionally — before a release, or when adding entries to
``tests/fixtures/verified_dois.yaml``::

    uv run pytest -m network -v

The everyday check is in ``test_data_registry.py``: the registry may only claim
DOIs recorded in that fixture. This is what confirms the fixture is still true.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

VERIFIED_DOIS_PATH = Path(__file__).parents[1] / "fixtures" / "verified_dois.yaml"
TIMEOUT = 30


def _entries(section: str) -> list[dict]:
    data = yaml.safe_load(VERIFIED_DOIS_PATH.read_text(encoding="utf-8"))
    return data[section]


def _resolve(doi: str) -> int:
    """Ask doi.org for the record, returning the HTTP status.

    Content negotiation is used rather than a registrar's own API because it
    works whichever registrar issued the DOI, and these come from three.
    """
    requests = pytest.importorskip("requests")
    response = requests.get(
        f"https://doi.org/{doi}",
        headers={
            "Accept": "application/vnd.citationstyles.csl+json",
            "User-Agent": "fair-shares-doi-check",
        },
        timeout=TIMEOUT,
    )
    return response.status_code


@pytest.mark.network
@pytest.mark.parametrize(
    "entry", _entries("verified"), ids=lambda e: e["doi"].replace("/", "_")
)
def test_verified_doi_still_resolves(entry):
    status = _resolve(entry["doi"])
    assert status == 200, (
        f"{entry['doi']} (used by {entry['used_by']}) returned HTTP {status}. "
        "If the DOI has genuinely been withdrawn, correct the registry and move "
        "this entry to known_bad with the evidence. If a registrar is simply "
        "down, try again later — do not delete the entry."
    )


@pytest.mark.network
@pytest.mark.parametrize(
    "entry",
    [e for e in _entries("known_bad") if "essd-16-5567" in e["doi"]],
    ids=lambda e: e["doi"].replace("/", "_"),
)
def test_the_broken_gcb_doi_still_does_not_resolve(entry):
    """Confirms the DOI recorded as non-existent really is.

    Only the fabricated one is checked. The other known_bad entry is the
    restricted AR6 database, which resolves perfectly well — it is listed for
    rights reasons, not because it is broken.
    """
    assert _resolve(entry["doi"]) != 200, (
        f"{entry['doi']} now resolves. It was recorded as non-existent. Re-check "
        "it and, if it is real, move it out of known_bad with fresh evidence."
    )
