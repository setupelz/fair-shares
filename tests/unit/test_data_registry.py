"""Tests for the registry table, the file transforms, and fetch/verify.

No test here touches the network. Checking that the real URLs work was done by
hand and written up separately: a test suite that downloads 130 MB is one people
skip.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

from fair_shares.library import data_fetch, paths
from fair_shares.library.data_registry import (
    Download,
    Registry,
    Source,
    load_registry,
    normalise_target,
)
from fair_shares.library.exceptions import (
    DataIntegrityError,
    ManualFetchRequired,
)

CONFIG_PATH_KEYS = ("path", "path_ppp", "path_mer", "path_historical", "path_projected")

VERIFIED_DOIS_PATH = Path(__file__).parents[1] / "fixtures" / "verified_dois.yaml"

# Matches a DOI anywhere in a block of text. Trailing punctuation is stripped by
# the caller, since a DOI at the end of a sentence picks up the full stop.
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s,;)\"'\]]+")


def _verified_dois() -> dict:
    return yaml.safe_load(VERIFIED_DOIS_PATH.read_text(encoding="utf-8"))


def _registry_dois(registry) -> set[tuple[str, str]]:
    """Every DOI the registry asserts, as ``(source name, doi)``.

    Covers DOIs written into citation text as well as the ``doi`` field. A made
    up DOI in a citation reaches a user's reference list just as easily as one
    in a field.
    """
    found: set[tuple[str, str]] = set()
    for name, source in registry.sources.items():
        if source.doi:
            found.add((name, source.doi))
        for match in DOI_PATTERN.findall(source.citation):
            found.add((name, match.rstrip(".")))
    return found


# Drift means "the publisher released a new version", so these have to be files
# that still open. A file that will not parse is damage, not an update.
OLD_CSV = b"iso3c,value\nAUT,1\nDEU,2\n"
NEW_CSV = b"iso3c,value\nAUT,9\nDEU,8\n"


@pytest.fixture
def registry():
    return load_registry()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stub_download(monkeypatch, payload: bytes):
    """Replace the network with fixed bytes, recording the headers used."""
    seen: dict[str, object] = {}

    def fake(url: str, dest: Path, headers: dict[str, str]) -> Path:
        seen["url"] = url
        seen["headers"] = headers
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        return dest

    monkeypatch.setattr(data_fetch, "_download_to", fake)
    return seen


class TestRegistryIntegrity:
    def test_every_source_validates(self, registry):
        assert registry.version == 1
        assert registry.sources

    def test_every_source_has_licence_and_citation(self, registry):
        for name, source in registry.sources.items():
            assert source.license.strip(), f"{name} has no licence"
            assert source.citation.strip(), f"{name} has no citation"

    def test_no_doi_is_invented(self, registry):
        """DOIs must be real identifiers, not placeholders or URLs."""
        for name, source in registry.sources.items():
            if source.doi is None:
                continue
            assert source.doi.startswith("10."), f"{name} DOI is not a DOI"
            assert " " not in source.doi, f"{name} DOI contains whitespace"
            assert not source.doi.startswith("http"), f"{name} DOI is a URL"

    def test_every_doi_has_been_looked_up(self, registry):
        """The registry may only claim DOIs recorded as checked.

        The list lives in ``tests/fixtures/verified_dois.yaml``, in the
        repository, so this runs everywhere including CI and needs no network.

        It is a separate file on purpose. Because the registry and the list are
        edited independently, a DOI typed into the registry without being looked
        up first has nowhere to hide.
        """
        verified = {entry["doi"] for entry in _verified_dois()["verified"]}
        missing = sorted(
            f"{name}: {doi}"
            for name, doi in _registry_dois(registry)
            if doi not in verified
        )
        assert not missing, (
            f"DOIs claimed by the registry but not recorded as checked: {missing}. "
            "Look each one up at DataCite, Crossref or doi.org and add it to "
            "tests/fixtures/verified_dois.yaml with the evidence — never just add "
            "it to the list to make this pass."
        )

    def test_no_known_bad_doi_is_used(self, registry):
        """A DOI already found to be wrong must not come back."""
        bad = {
            entry["doi"]: entry["evidence"] for entry in _verified_dois()["known_bad"]
        }
        offenders = [
            f"{name}: {doi} — {' '.join(bad[doi].split())}"
            for name, doi in _registry_dois(registry)
            if doi in bad
        ]
        assert not offenders, offenders

    def test_the_corrected_gcb_doi_is_the_one_used(self, registry):
        assert "10.5194/essd-16-5567-2024" not in registry["gcb-2024"].citation
        assert "10.5194/essd-17-965-2025" in registry["gcb-2024"].citation

    def test_the_verified_list_itself_is_well_formed(self):
        data = _verified_dois()
        seen = set()
        for section in ("verified", "known_bad"):
            for entry in data[section]:
                doi = entry["doi"]
                assert doi.startswith("10."), doi
                assert doi not in seen, f"{doi} listed twice"
                seen.add(doi)
                assert entry["evidence"].strip(), f"{doi} has no evidence note"
                assert entry["verified"], f"{doi} has no verification date"
        overlap = {e["doi"] for e in data["verified"]} & {
            e["doi"] for e in data["known_bad"]
        }
        assert not overlap, f"listed as both good and bad: {overlap}"

    def test_urls_are_https(self, registry):
        for name, source in registry.sources.items():
            for download in source.downloads:
                if download.url:
                    assert download.url.startswith("https://"), name

    def test_targets_are_unique_across_sources(self, registry):
        seen: dict[str, str] = {}
        for name, source in registry.sources.items():
            for target in source.targets:
                key = normalise_target(target)
                assert key not in seen, f"{key} claimed by {seen.get(key)} and {name}"
                seen[key] = name

    def test_only_wiid_sends_a_custom_user_agent(self, registry):
        """The WAF workaround stays visible where it applies."""
        with_headers = {
            name
            for name, source in registry.sources.items()
            for download in source.downloads
            if download.headers
        }
        assert with_headers == {"unu-wider-2025"}

    def test_manual_sources_name_a_destination(self, registry):
        for name, source in registry.sources.items():
            if source.tier != "manual":
                continue
            assert "<data_dir>" in (source.manual_instructions or ""), name

    def test_default_tier_covers_a_standard_run(self, registry):
        assert set(registry.names_for_tiers(("default",))) == {
            "primap-202503",
            "melo-2026",
            "wdi-2025",
            "un-owid-2025",
        }


class TestConfigCrossReference:
    """Every data path in the config must match a registry entry.

    The registry and the config write the same paths differently (one with a
    ``data/`` in front, one without). If they are not lined up, automatic
    downloading never happens and every other test still passes, so this walks
    the real config file instead of assuming.
    """

    def _config_paths(self) -> list[str]:
        raw = yaml.safe_load(
            paths.packaged_config("data_sources/data_sources_unified.yaml").read_text(
                encoding="utf-8"
            )
        )
        found: list[str] = []

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in CONFIG_PATH_KEYS and isinstance(value, str):
                        found.append(value)
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(raw)
        return found

    def test_config_declares_data_paths(self):
        assert any(p.startswith("data/") for p in self._config_paths())

    def test_every_configured_data_path_is_registered(self, registry):
        index = registry.target_index()
        unregistered = [
            p
            for p in self._config_paths()
            if p.startswith("data/") and normalise_target(p) not in index
        ]
        assert not unregistered, (
            f"configured data paths absent from the registry: {unregistered}. "
            "Auto-fetch cannot fire for these, and removing them from the repo "
            "would break a fresh clone."
        )

    def test_normalise_target_strips_the_data_prefix(self):
        assert normalise_target("data/gdp/wdi-2025/x.csv") == "gdp/wdi-2025/x.csv"
        assert normalise_target("gdp/wdi-2025/x.csv") == "gdp/wdi-2025/x.csv"
        assert normalise_target("data\\gdp\\x.csv") == "gdp/x.csv"


class TestSchemaContract:
    def test_versioned_download_requires_a_pin(self):
        with pytest.raises(ValueError, match="must carry a pinned"):
            Download(url="https://x/y", target="a/b.csv")

    def test_unversioned_download_rejects_a_pin(self):
        with pytest.raises(ValueError, match="cannot carry a pinned"):
            Download(
                url="https://x/y",
                target="a/b.csv",
                unversioned=True,
                sha256="a" * 64,
                reference_sha256="b" * 64,
            )

    def test_unversioned_download_requires_a_reference(self):
        with pytest.raises(ValueError, match="must carry `reference_sha256`"):
            Download(url="https://x/y", target="a/b.csv", unversioned=True)

    def test_unzip_member_requires_a_pattern(self):
        with pytest.raises(ValueError, match="member_pattern"):
            Download(
                url="https://x/y",
                target="a/b.csv",
                transform="unzip-member",
                unversioned=True,
                reference_sha256="b" * 64,
            )

    def test_ar6_split_requires_outputs(self):
        with pytest.raises(ValueError, match="`outputs`"):
            Download(url="https://x/y", transform="ar6-split", sha256="a" * 64)

    def test_manual_source_requires_instructions(self):
        with pytest.raises(ValueError, match="manual_instructions"):
            Source(
                tier="manual",
                version="1",
                license="x",
                citation="y",
                redistributable=False,
            )

    def test_short_hashes_are_rejected(self):
        with pytest.raises(ValueError, match="64-character"):
            Download(url="https://x/y", target="a/b.csv", sha256="abc")


class TestFetching:
    def _registry(self, download: Download, tier: str = "default") -> Registry:
        return Registry(
            version=1,
            sources={
                "demo": Source(
                    tier=tier,
                    version="v1",
                    license="CC-BY-4.0",
                    citation="Someone (2026). Demo.",
                    redistributable=True,
                    downloads=(download,),
                )
            },
        )

    def test_fetch_writes_the_target(self, tmp_path, monkeypatch):
        payload = b"hello,world\n"
        seen = _stub_download(monkeypatch, payload)
        reg = self._registry(
            Download(url="https://x/y", target="a/b.csv", sha256=_sha256(payload))
        )

        results = data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)

        assert (tmp_path / "a" / "b.csv").read_bytes() == payload
        assert [r.status for r in results] == ["fetched"]
        assert seen["url"] == "https://x/y"

    def test_download_checksum_mismatch_raises(self, tmp_path, monkeypatch):
        _stub_download(monkeypatch, b"corrupted")
        reg = self._registry(
            Download(url="https://x/y", target="a/b.csv", sha256=_sha256(b"expected"))
        )

        with pytest.raises(DataIntegrityError) as excinfo:
            data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)

        message = str(excinfo.value)
        assert "b.csv" in message
        assert _sha256(b"expected") in message
        assert _sha256(b"corrupted") in message
        assert not (tmp_path / "a" / "b.csv").exists(), "corrupt bytes must not land"

    def test_present_and_matching_is_not_redownloaded(self, tmp_path, monkeypatch):
        payload = b"hello,world\n"
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(payload)

        def explode(*args, **kwargs):  # pragma: no cover - must not be reached
            raise AssertionError("re-downloaded a file that already matched")

        monkeypatch.setattr(data_fetch, "_download_to", explode)
        reg = self._registry(
            Download(url="https://x/y", target="a/b.csv", sha256=_sha256(payload))
        )

        results = data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)
        assert [r.status for r in results] == ["present"]

    def test_present_but_corrupt_raises_rather_than_overwriting(
        self, tmp_path, monkeypatch
    ):
        """A corrupt file is reported, not silently repaired."""
        payload = b"hello,world\n"
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(payload[:-1])

        monkeypatch.setattr(data_fetch, "_download_to", lambda *a, **k: 1 / 0)
        reg = self._registry(
            Download(url="https://x/y", target="a/b.csv", sha256=_sha256(payload))
        )

        with pytest.raises(DataIntegrityError):
            data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)
        assert target.read_bytes() == payload[:-1], "must not overwrite"

    def test_force_redownloads_over_a_corrupt_file(self, tmp_path, monkeypatch):
        payload = b"hello,world\n"
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"junk")
        _stub_download(monkeypatch, payload)
        reg = self._registry(
            Download(url="https://x/y", target="a/b.csv", sha256=_sha256(payload))
        )

        data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg, force=True)
        assert target.read_bytes() == payload

    def test_registry_headers_are_handed_to_the_downloader(self, tmp_path, monkeypatch):
        """The browser header WIID needs must actually reach the request.

        Checks the header that gets passed on, rather than making a real request
        to see it rejected. What matters is that we send it, not what a third
        party's server happens to do today.
        """
        payload = b"x"
        seen = _stub_download(monkeypatch, payload)
        agent = "Mozilla/5.0 (Macintosh)"
        reg = self._registry(
            Download(
                url="https://x/y",
                target="a/b.xlsx",
                sha256=_sha256(payload),
                headers={"User-Agent": agent},
            )
        )

        data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)
        assert seen["headers"] == {"User-Agent": agent}

    def test_real_wiid_entry_carries_a_browser_user_agent(self, registry):
        header = registry["unu-wider-2025"].downloads[0].headers["User-Agent"]
        assert "Mozilla/5.0" in header

    def test_manual_source_raises_with_actionable_instructions(self, tmp_path):
        reg = load_registry()
        with pytest.raises(ManualFetchRequired) as excinfo:
            data_fetch.fetch_source("gcb-2024", data_dir=tmp_path, registry=reg)

        message = str(excinfo.value)
        assert "meta.icos-cp.eu/objects/mNRkixV0ZZViLvv5ADVGQCtx" in message
        assert "National_Fossil_Carbon_Emissions_2024v1.0.xlsx" in message
        assert str(tmp_path) in message, "the destination path must be concrete"

    def test_unversioned_drift_is_reported_not_raised(self, tmp_path, monkeypatch):
        _stub_download(monkeypatch, NEW_CSV)
        reg = self._registry(
            Download(
                url="https://x/y",
                target="a/b.csv",
                unversioned=True,
                reference_sha256=_sha256(OLD_CSV),
            )
        )

        results = data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)
        assert [r.status for r in results] == ["drifted"]
        assert (tmp_path / "a" / "b.csv").exists()


class TestTransforms:
    def test_unzip_member_extracts_the_matching_file(self, tmp_path, monkeypatch):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("Metadata_API_X_DS2_en_csv_v2_99.csv", "meta")
            archive.writestr("API_X_DS2_en_csv_v2_99.csv", "real,data\n")
        _stub_download(monkeypatch, buffer.getvalue())

        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            transform="unzip-member",
                            member_pattern="API_X_DS2_en_csv_v2_*.csv",
                            target="gdp/API_X_DS2_en_csv_v2_1004.csv",
                            unversioned=True,
                            reference_sha256=_sha256(b"real,data\n"),
                        ),
                    ),
                )
            },
        )

        data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)
        out = tmp_path / "gdp" / "API_X_DS2_en_csv_v2_1004.csv"
        assert out.read_bytes() == b"real,data\n"

    def test_unzip_member_reports_a_changed_layout(self, tmp_path, monkeypatch):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("something_else.csv", "x")
        _stub_download(monkeypatch, buffer.getvalue())

        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            transform="unzip-member",
                            member_pattern="API_X_*.csv",
                            target="gdp/out.csv",
                            unversioned=True,
                            reference_sha256="a" * 64,
                        ),
                    ),
                )
            },
        )

        with pytest.raises(DataIntegrityError, match="member_pattern"):
            data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)

    def _ar6_workbook(self) -> bytes:
        buffer = io.BytesIO()
        data = pd.DataFrame(
            {"Model": ["m"], "Scenario": ["s"], "Variable": ["v"], 2020: [1.0]}
        )
        meta = pd.DataFrame({"model": ["m"], "scenario": ["s"], "Category": ["C1"]})
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            data.to_excel(writer, sheet_name="data", index=False)
            meta.to_excel(writer, sheet_name="meta", index=False)
        return buffer.getvalue()

    def _ar6_registry(self, payload: bytes) -> Registry:
        return Registry(
            version=1,
            sources={
                "ar6": Source(
                    tier="optional",
                    version="v2",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=False,
                    downloads=(
                        Download(
                            url="https://x/y",
                            transform="ar6-split",
                            sha256=_sha256(payload),
                            outputs=(
                                "scenarios/ipcc_ar6_gidden/ar6_gidden.xlsx",
                                "scenarios/ipcc_ar6_gidden/metadata_ar6_gidden.xlsx",
                                "scenarios/ipcc_ar6_gidden/ar6_gidden.zip",
                            ),
                        ),
                    ),
                )
            },
        )

    def test_ar6_split_produces_both_workbooks_and_the_zip(self, tmp_path, monkeypatch):
        payload = self._ar6_workbook()
        _stub_download(monkeypatch, payload)

        data_fetch.fetch_source(
            "ar6", data_dir=tmp_path, registry=self._ar6_registry(payload)
        )

        base = tmp_path / "scenarios" / "ipcc_ar6_gidden"
        assert (base / "ar6_gidden.xlsx").exists()
        assert (base / "metadata_ar6_gidden.xlsx").exists()

        # Each split workbook carries one sheet, because process_iamc_zip reads
        # sheet 0 of every member.
        assert pd.ExcelFile(base / "ar6_gidden.xlsx").sheet_names == ["data"]
        assert pd.ExcelFile(base / "metadata_ar6_gidden.xlsx").sheet_names == ["meta"]

        with zipfile.ZipFile(base / "ar6_gidden.zip") as archive:
            assert sorted(archive.namelist()) == [
                "ar6_gidden.xlsx",
                "metadata_ar6_gidden.xlsx",
            ]

    def test_ar6_split_round_trips_the_values(self, tmp_path, monkeypatch):
        payload = self._ar6_workbook()
        _stub_download(monkeypatch, payload)
        data_fetch.fetch_source(
            "ar6", data_dir=tmp_path, registry=self._ar6_registry(payload)
        )

        base = tmp_path / "scenarios" / "ipcc_ar6_gidden"
        produced = pd.read_excel(base / "ar6_gidden.xlsx")
        expected = pd.read_excel(io.BytesIO(payload), sheet_name="data")
        pd.testing.assert_frame_equal(produced, expected)

    def test_ar6_split_rejects_an_unexpected_layout(self, tmp_path, monkeypatch):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame({"a": [1]}).to_excel(writer, sheet_name="unexpected")
        payload = buffer.getvalue()
        _stub_download(monkeypatch, payload)

        with pytest.raises(DataIntegrityError, match="sheets"):
            data_fetch.fetch_source(
                "ar6", data_dir=tmp_path, registry=self._ar6_registry(payload)
            )


class TestVerify:
    def test_intact_tree_reports_nothing(self, tmp_path):
        payload = b"hello\n"
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(payload)
        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="a/b.csv",
                            sha256=_sha256(payload),
                        ),
                    ),
                )
            },
        )
        failures, drift = data_fetch.verify_sources(data_dir=tmp_path, registry=reg)
        assert failures == [] and drift == []

    def test_modified_pinned_file_is_a_failure(self, tmp_path):
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"tampered")
        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="a/b.csv",
                            sha256=_sha256(b"original"),
                        ),
                    ),
                )
            },
        )
        failures, drift = data_fetch.verify_sources(data_dir=tmp_path, registry=reg)
        assert [f.target for f in failures] == [target]
        assert drift == []

    def test_unversioned_drift_is_drift_not_failure(self, tmp_path):
        """An updated file must not make --verify fail forever."""
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(NEW_CSV)
        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="a/b.csv",
                            unversioned=True,
                            reference_sha256=_sha256(OLD_CSV),
                        ),
                    ),
                )
            },
        )
        failures, drift = data_fetch.verify_sources(data_dir=tmp_path, registry=reg)
        assert failures == []
        assert [d.target for d in drift] == [target]

    def test_absent_files_are_neither(self, tmp_path, registry):
        failures, drift = data_fetch.verify_sources(
            data_dir=tmp_path / "empty", registry=registry
        )
        assert failures == [] and drift == []


class TestProvenance:
    def test_provenance_carries_licence_and_citation(self, tmp_path, monkeypatch):
        payload = b"hello\n"
        _stub_download(monkeypatch, payload)
        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v9",
                    license="CC-BY-4.0",
                    citation="Someone (2026). A dataset. Zenodo.",
                    redistributable=True,
                    doi="10.5281/zenodo.1",
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="a/b.csv",
                            sha256=_sha256(payload),
                        ),
                    ),
                )
            },
        )
        results = data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)
        out = data_fetch.write_provenance(results, tmp_path, registry=reg)

        text = out.read_text(encoding="utf-8")
        assert out.name == "PROVENANCE.md"
        assert "CC-BY-4.0" in text
        assert "Someone (2026). A dataset. Zenodo." in text
        assert "10.5281/zenodo.1" in text
        assert _sha256(payload) in text, "record the hash actually obtained"

    def test_provenance_flags_drift(self, tmp_path, monkeypatch):
        _stub_download(monkeypatch, NEW_CSV)
        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v9",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="a/b.csv",
                            unversioned=True,
                            reference_sha256=_sha256(OLD_CSV),
                        ),
                    ),
                )
            },
        )
        results = data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)
        text = data_fetch.write_provenance(results, tmp_path, registry=reg).read_text(
            encoding="utf-8"
        )
        assert "Vintage drift" in text

    def test_provenance_describes_the_directory_not_just_this_run(self, tmp_path):
        """A second download must not erase the record of the first.

        People usually download in several goes. Rebuilding the file from just
        one command's results would leave files on disk with no licence
        recorded anywhere.
        """
        reg = Registry(
            version=1,
            sources={
                "alpha": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="Alpha citation.",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/a",
                            target="a/one.csv",
                            sha256=_sha256(b"one"),
                        ),
                    ),
                ),
                "beta": Source(
                    tier="optional",
                    version="v2",
                    license="CC-BY-SA-4.0",
                    citation="Beta citation.",
                    redistributable=False,
                    downloads=(
                        Download(
                            url="https://x/b",
                            target="b/two.csv",
                            sha256=_sha256(b"two"),
                        ),
                    ),
                ),
            },
        )
        for rel, payload in (("a/one.csv", b"one"), ("b/two.csv", b"two")):
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        # Results from fetching only beta, as a later `--source beta` would give.
        only_beta = [
            data_fetch.FetchResult("beta", tmp_path / "b/two.csv", "fetched", None)
        ]
        text = data_fetch.write_provenance(only_beta, tmp_path, registry=reg).read_text(
            encoding="utf-8"
        )

        assert "Alpha citation." in text, "alpha is on disk and must stay documented"
        assert "Beta citation." in text
        assert _sha256(b"one") in text

    def test_provenance_rederives_drift_for_files_it_did_not_fetch(self, tmp_path):
        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="a/b.csv",
                            unversioned=True,
                            reference_sha256=_sha256(OLD_CSV),
                        ),
                    ),
                )
            },
        )
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(NEW_CSV)

        text = data_fetch.write_provenance([], tmp_path, registry=reg).read_text(
            encoding="utf-8"
        )
        assert "Vintage drift" in text


class TestCommittedDataTree:
    """The registry's hashes must match the data files actually in this repo.

    This is the check that would have caught the line-ending problem before a
    user hit it. `.gitattributes` sets `* text=auto`, so git rewrites line
    endings on text files it stores, and a hash taken from a publisher who ships
    Windows line endings can never match the committed copy byte for byte.

    Skips cleanly once the data files leave the repository, so it keeps working
    through that change rather than having to be deleted.
    """

    def _repo_data_dir(self):
        candidate = Path(__file__).parents[2] / "data"
        if not candidate.is_dir():
            pytest.skip("no data directory in this checkout")
        return candidate

    def test_committed_files_match_their_recorded_hashes(self, registry):
        data_dir = self._repo_data_dir()
        problems = []
        for name in sorted(registry.sources):
            for download in registry[name].downloads:
                if not data_fetch.has_recorded_hash(download):
                    continue
                for rel in download.targets:
                    target = data_dir / rel
                    if not target.exists():
                        continue
                    result = data_fetch.classify_target(download, name, target)
                    if result.status == "corrupt":
                        problems.append(f"{rel}: {result.detail}")
        assert not problems, (
            "registry hashes disagree with the data files committed to this "
            f"repository: {problems}. A fresh clone would fail `fair-shares "
            "fetch-data` before touching the network."
        )

    def test_clean_checkout_verifies(self, registry):
        """`fetch-data --verify` on an untouched checkout must exit 0."""
        failures, _drift = data_fetch.verify_sources(
            data_dir=self._repo_data_dir(), registry=registry
        )
        assert not failures, [(f.target.name, f.detail) for f in failures]


class TestNewlineTolerance:
    def test_windows_pin_matches_a_unix_copy(self, tmp_path):
        """The case git creates: publisher ships CRLF, repo stores LF."""
        unix = tmp_path / "unix.csv"
        unix.write_bytes(b"a,b\n1,2\n")
        windows_hash = _sha256(b"a,b\r\n1,2\r\n")

        matched, _digest, how = data_fetch.check_pinned_hash(unix, windows_hash)
        assert matched and how == "newlines"

    def test_exact_match_is_reported_as_exact(self, tmp_path):
        target = tmp_path / "x.csv"
        target.write_bytes(b"a,b\n1,2\n")
        matched, _digest, how = data_fetch.check_pinned_hash(
            target, _sha256(b"a,b\n1,2\n")
        )
        assert matched and how == "exact"

    def test_real_content_differences_still_fail(self, tmp_path):
        """Line-ending tolerance must not excuse a genuinely different file."""
        target = tmp_path / "x.csv"
        target.write_bytes(b"a,b\n1,2\n")
        matched, _digest, how = data_fetch.check_pinned_hash(
            target, _sha256(b"a,b\n9,9\n")
        )
        assert not matched and how is None

    def test_binary_files_are_not_newline_mangled(self, tmp_path):
        """A zero byte marks the file binary, so no conversion is attempted."""
        target = tmp_path / "x.nc"
        target.write_bytes(b"\x00\r\n\x00")
        matched, _digest, _how = data_fetch.check_pinned_hash(
            target, _sha256(b"\x00\n\x00")
        )
        assert not matched


class TestPartialWriteRecovery:
    def test_writes_go_via_a_temporary_name(self, tmp_path, monkeypatch):
        """The final name must never hold a half-written file."""
        seen = []

        real_replace = data_fetch._replace_atomically

        def spy(source, target):
            seen.append((source.name, target.name))
            real_replace(source, target)

        monkeypatch.setattr(data_fetch, "_replace_atomically", spy)
        payload = b"iso3c,value\nAUT,1\nDEU,2\n"
        _stub_download(monkeypatch, payload)
        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="a/b.csv",
                            sha256=_sha256(payload),
                        ),
                    ),
                )
            },
        )
        data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)
        assert seen == [(".b.csv.partial", "b.csv")]

    def test_a_killed_run_leaves_no_usable_wreckage(self, tmp_path):
        """A staging file left behind is not mistaken for the real thing."""
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        data_fetch._staging_path(target).write_bytes(b"half writ")
        assert not target.exists()

    def test_damaged_derived_output_is_rebuilt_not_dead_ended(
        self, tmp_path, monkeypatch
    ):
        """A broken built file has no hash to protect, so it is rebuilt."""
        payload = TestTransforms()._ar6_workbook()
        _stub_download(monkeypatch, payload)
        reg = TestTransforms()._ar6_registry(payload)

        base = tmp_path / "scenarios" / "ipcc_ar6_gidden"
        base.mkdir(parents=True)
        for name in ("ar6_gidden.xlsx", "metadata_ar6_gidden.xlsx", "ar6_gidden.zip"):
            (base / name).write_bytes(b"truncated wreckage")

        results = data_fetch.fetch_source("ar6", data_dir=tmp_path, registry=reg)

        assert {r.status for r in results} == {"fetched"}
        with zipfile.ZipFile(base / "ar6_gidden.zip") as archive:
            assert sorted(archive.namelist()) == [
                "ar6_gidden.xlsx",
                "metadata_ar6_gidden.xlsx",
            ]

    def test_damaged_pinned_input_raises_instead_of_rebuilding(
        self, tmp_path, monkeypatch
    ):
        """A recorded hash means a mismatch is ambiguous, so it must not self-heal."""
        payload = b"iso3c,value\nAUT,1\n"
        target = tmp_path / "a" / "b.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"\x00\x00 not the file at all")
        monkeypatch.setattr(
            data_fetch,
            "_download_to",
            lambda *a, **k: pytest.fail("must not silently re-download"),
        )
        reg = Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="a/b.csv",
                            sha256=_sha256(payload),
                        ),
                    ),
                )
            },
        )
        with pytest.raises(DataIntegrityError):
            data_fetch.fetch_source("demo", data_dir=tmp_path, registry=reg)


class TestDamageVersusUpdate:
    def _wdi_registry(self, reference: bytes) -> Registry:
        return Registry(
            version=1,
            sources={
                "demo": Source(
                    tier="default",
                    version="v1",
                    license="CC-BY-4.0",
                    citation="c",
                    redistributable=True,
                    downloads=(
                        Download(
                            url="https://x/y",
                            target="gdp/x.csv",
                            unversioned=True,
                            reference_sha256=_sha256(reference),
                        ),
                    ),
                )
            },
        )

    def test_a_truncated_unversioned_file_is_damage_not_an_update(self, tmp_path):
        """Exit non-zero: a hash alone cannot tell these apart, but parsing can."""
        target = tmp_path / "gdp" / "x.csv"
        target.parent.mkdir(parents=True)
        target.write_text("truncated garbage\n")

        failures, drift = data_fetch.verify_sources(
            data_dir=tmp_path, registry=self._wdi_registry(OLD_CSV)
        )
        assert [f.target for f in failures] == [target]
        assert drift == []

    def test_a_readable_new_version_is_still_reported_as_drift(self, tmp_path):
        target = tmp_path / "gdp" / "x.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(NEW_CSV)

        failures, drift = data_fetch.verify_sources(
            data_dir=tmp_path, registry=self._wdi_registry(OLD_CSV)
        )
        assert failures == []
        assert [d.target for d in drift] == [target]
