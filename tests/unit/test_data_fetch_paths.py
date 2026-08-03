"""Where downloads are written, and when a missing file triggers a download.

Kept separate from ``test_data_registry.py`` because these are about working out
paths rather than about the source table. The checkout-versus-per-user-directory
rule is the easiest thing here to get wrong: if it is wrong, the first download
anyone runs quietly changes where the code looks for data from then on.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from fair_shares.library import data_fetch, paths
from fair_shares.library.data_registry import Download, Registry, Source
from fair_shares.library.exceptions import ManualFetchRequired


@pytest.fixture(autouse=True)
def _clear_cache():
    paths.reset_path_cache()
    yield
    paths.reset_path_cache()


def _make_fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    (repo / "notebooks").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "fair-shares"\n')
    return repo


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _demo_registry(payload: bytes, tier: str = "default") -> Registry:
    return Registry(
        version=1,
        sources={
            "demo": Source(
                tier=tier,
                version="v1",
                license="CC-BY-4.0",
                citation="Someone (2026). Demo.",
                redistributable=True,
                downloads=(
                    Download(
                        url="https://x/y",
                        target="regions/map.csv",
                        sha256=_sha256(payload),
                    ),
                ),
            )
        },
    )


class TestWriteDestination:
    """`data_dir_for_write` decides where downloads land."""

    def test_explicit_argument_wins(self, tmp_path):
        assert paths.data_dir_for_write(tmp_path / "x") == tmp_path / "x"

    def test_environment_variable_is_honoured(self, monkeypatch, tmp_path):
        monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "env"))
        assert paths.data_dir_for_write() == tmp_path / "env"

    def test_inside_a_checkout_it_is_the_checkouts_own_data_dir(
        self, monkeypatch, tmp_path
    ):
        """The rule that stops a download rewiring an existing clone.

        Reading only uses the per-user directory if it already exists, so
        creating it would make it beat the checkout from then on, even from
        inside the checkout. Downloading into the checkout prevents that.
        """
        monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
        user_dir = tmp_path / "user-data"
        monkeypatch.setattr(paths, "_platform_dir", lambda kind: user_dir)
        repo = _make_fake_repo(tmp_path)
        monkeypatch.chdir(repo / "notebooks")

        assert paths.data_dir_for_write() == repo / "data"
        assert not user_dir.exists(), "must not create the user data directory"

    def test_outside_a_checkout_it_is_the_user_directory(self, monkeypatch, tmp_path):
        """The other branch: an installed wheel run from anywhere."""
        monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
        user_dir = tmp_path / "user-data"
        monkeypatch.setattr(paths, "_platform_dir", lambda kind: user_dir)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        assert paths.data_dir_for_write() == user_dir

    def test_an_existing_user_directory_still_wins_over_a_checkout(
        self, monkeypatch, tmp_path
    ):
        """Deliberate opt-in: once it exists, it is the configured location."""
        monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
        user_dir = tmp_path / "user-data"
        user_dir.mkdir()
        monkeypatch.setattr(paths, "_platform_dir", lambda kind: user_dir)
        repo = _make_fake_repo(tmp_path)
        monkeypatch.chdir(repo)

        assert paths.data_dir_for_write() == user_dir


class TestFetchDestination:
    def test_fetch_inside_a_checkout_writes_into_the_checkout(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
        user_dir = tmp_path / "user-data"
        monkeypatch.setattr(paths, "_platform_dir", lambda kind: user_dir)
        repo = _make_fake_repo(tmp_path)
        monkeypatch.chdir(repo)

        payload = b"iso3c,region\n"

        def fake(url, dest, headers):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            return dest

        monkeypatch.setattr(data_fetch, "_download_to", fake)
        data_fetch.fetch_source("demo", registry=_demo_registry(payload))

        assert (repo / "data" / "regions" / "map.csv").read_bytes() == payload
        assert not user_dir.exists()

    def test_fetch_seeds_process_wide_resolution(self, monkeypatch, tmp_path):
        """An explicit data_dir must reach the deep resolver calls too."""
        monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
        monkeypatch.setattr(paths, "_platform_dir", lambda kind: None)
        monkeypatch.chdir(tmp_path)
        payload = b"x"

        monkeypatch.setattr(
            data_fetch,
            "_download_to",
            lambda url, dest, headers: (
                dest.parent.mkdir(parents=True, exist_ok=True),
                dest.write_bytes(payload),
                dest,
            )[-1],
        )
        target = tmp_path / "chosen"
        data_fetch.fetch_source(
            "demo", data_dir=target, registry=_demo_registry(payload)
        )
        assert paths.data_dir() == target


class TestAutoFetch:
    def test_disabled_by_environment(self, monkeypatch):
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "0")
        assert not data_fetch.auto_fetch_enabled()
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "1")
        assert data_fetch.auto_fetch_enabled()

    def test_on_by_default(self, monkeypatch):
        monkeypatch.delenv(data_fetch.AUTO_FETCH_ENV, raising=False)
        assert data_fetch.auto_fetch_enabled()

    def test_missing_registered_file_is_fetched(self, monkeypatch, tmp_path):
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "1")
        payload = b"iso3c,region\n"
        calls: list[str] = []

        def fake(url, dest, headers):
            calls.append(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            return dest

        monkeypatch.setattr(data_fetch, "_download_to", fake)
        monkeypatch.setattr(
            data_fetch, "load_registry", lambda **kw: _demo_registry(payload)
        )
        paths.configure(data_dir=tmp_path)

        resolved = paths.resolve_source_path("data/regions/map.csv")
        assert calls == ["https://x/y"]
        assert resolved.read_bytes() == payload

    def test_unregistered_missing_file_is_left_alone(self, monkeypatch, tmp_path):
        """Resolution of an unknown path must stay a pure path operation."""
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "1")
        monkeypatch.setattr(
            data_fetch, "load_registry", lambda **kw: _demo_registry(b"x")
        )
        monkeypatch.setattr(
            data_fetch,
            "_download_to",
            lambda *a, **k: pytest.fail("fetched an unregistered path"),
        )
        paths.configure(data_dir=tmp_path)

        resolved = paths.resolve_source_path("data/not/in/registry.csv")
        assert not resolved.exists()

    def test_output_paths_are_never_fetched(self, monkeypatch, tmp_path):
        """The pipeline writes output/; nothing there is in the registry."""
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "1")
        monkeypatch.setattr(
            data_fetch,
            "_download_to",
            lambda *a, **k: pytest.fail("fetched an output path"),
        )
        paths.configure(data_dir=tmp_path / "d", output_dir=tmp_path / "o")
        paths.resolve_source_path("output/sid/intermediate/x.csv")

    def test_existing_file_is_not_refetched(self, monkeypatch, tmp_path):
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "1")
        target = tmp_path / "regions" / "map.csv"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"already here\n")
        monkeypatch.setattr(
            data_fetch,
            "_download_to",
            lambda *a, **k: pytest.fail("re-fetched an existing file"),
        )
        paths.configure(data_dir=tmp_path)
        paths.resolve_source_path("data/regions/map.csv")

    def test_disabled_auto_fetch_leaves_the_path_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "0")
        monkeypatch.setattr(
            data_fetch,
            "_download_to",
            lambda *a, **k: pytest.fail("fetched with auto-fetch disabled"),
        )
        paths.configure(data_dir=tmp_path)
        resolved = paths.resolve_source_path("data/regions/map.csv")
        assert not resolved.exists()

    def test_manual_source_raises_with_instructions(self, monkeypatch, tmp_path):
        """A bunkers-dependent step must say how to get the file."""
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "1")
        paths.configure(data_dir=tmp_path)

        with pytest.raises(ManualFetchRequired) as excinfo:
            paths.resolve_source_path(
                "data/bunkers/gcb-2024/National_Fossil_Carbon_Emissions_2024v1.0.xlsx"
            )

        message = str(excinfo.value)
        assert "meta.icos-cp.eu/objects/mNRkixV0ZZViLvv5ADVGQCtx" in message
        assert "National_Fossil_Carbon_Emissions_2024v1.0.xlsx" in message

        # The instructions already include the sub-path, so anything worked out
        # from the file's own location doubles it up and tells the user to save
        # the file at <data_dir>/bunkers/bunkers/...
        assert str(tmp_path / "bunkers" / "gcb-2024") in message
        assert "bunkers/bunkers" not in message


class TestConfigureReset:
    """Passing None must clear, not be ignored.

    Otherwise one call with an explicit directory silently repoints every later
    call in the same session, which is the opposite of what the entry-point
    docstrings promise.
    """

    def test_none_clears_a_previously_set_directory(self, monkeypatch, tmp_path):
        monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
        scratch = tmp_path / "scratch"
        paths.configure(data_dir=scratch)
        assert paths.data_dir() == scratch

        paths.configure(data_dir=None)
        monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "env"))
        assert paths.data_dir() == tmp_path / "env"

    def test_none_leaves_the_other_directory_alone(self, monkeypatch, tmp_path):
        paths.configure(data_dir=tmp_path / "d", output_dir=tmp_path / "o")
        paths.configure(data_dir=None)
        assert paths.output_dir() == tmp_path / "o"

    def test_a_bare_entry_point_call_undoes_an_earlier_explicit_one(
        self, monkeypatch, tmp_path
    ):
        """The behaviour the python_api docstrings promise."""
        monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
        monkeypatch.setattr(paths, "_platform_dir", lambda kind: None)
        repo = _make_fake_repo(tmp_path)
        monkeypatch.chdir(repo)

        paths.configure(data_dir=tmp_path / "alt")
        assert paths.data_dir() == tmp_path / "alt"

        # An entry point called without a directory passes None through.
        paths.configure(data_dir=None, output_dir=None)
        assert paths.data_dir() == repo / "data"

    def test_fetch_source_still_sets_the_directory_it_used(self, monkeypatch, tmp_path):
        """fetch_source deliberately keeps its directory for later reads."""
        monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
        monkeypatch.setattr(paths, "_platform_dir", lambda kind: None)
        monkeypatch.chdir(tmp_path)
        payload = b"iso3c,region\nAUT,EU\n"
        monkeypatch.setattr(
            data_fetch,
            "_download_to",
            lambda url, dest, headers: (
                dest.parent.mkdir(parents=True, exist_ok=True),
                dest.write_bytes(payload),
                dest,
            )[-1],
        )
        chosen = tmp_path / "chosen"
        data_fetch.fetch_source(
            "demo", data_dir=chosen, registry=_demo_registry(payload)
        )
        assert paths.data_dir() == chosen


class TestAutoFetchDestination:
    def test_explicit_data_dir_reaches_the_download(self, monkeypatch, tmp_path):
        """A read with an explicit directory must download into that directory.

        If it downloaded somewhere else, the read that triggered it would still
        find nothing there.
        """
        monkeypatch.setenv(data_fetch.AUTO_FETCH_ENV, "1")
        payload = b"iso3c,region\nAUT,EU\n"
        seen: list = []

        def fake(url, dest, headers):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            return dest

        monkeypatch.setattr(data_fetch, "_download_to", fake)
        monkeypatch.setattr(
            data_fetch, "load_registry", lambda **kw: _demo_registry(payload)
        )
        real = data_fetch.fetch_source

        def spy(name, **kw):
            seen.append(kw.get("data_dir"))
            return real(name, **kw)

        monkeypatch.setattr(data_fetch, "fetch_source", spy)

        elsewhere = tmp_path / "elsewhere"
        resolved = paths.resolve_source_path("data/regions/map.csv", data_dir=elsewhere)
        assert seen == [elsewhere]
        assert resolved.read_bytes() == payload
