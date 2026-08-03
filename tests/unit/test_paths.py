"""Tests for the four-level data / output directory resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from fair_shares.library import paths
from fair_shares.library.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def _clear_cache():
    paths.reset_path_cache()
    yield
    paths.reset_path_cache()


@pytest.fixture
def no_platform_dirs(monkeypatch):
    """Make level 3 miss, so levels 2 and 4 are observable in isolation."""
    monkeypatch.setattr(paths, "_platform_dir", lambda kind: None)


# ---------------------------------------------------------------- precedence


def test_explicit_argument_wins_over_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "from-env"))
    assert paths.data_dir(tmp_path / "explicit") == tmp_path / "explicit"
    assert paths.output_dir(tmp_path / "explicit") == tmp_path / "explicit"


def test_environment_wins_over_platformdirs(monkeypatch, tmp_path):
    platform_dir = tmp_path / "platform"
    platform_dir.mkdir()
    monkeypatch.setattr(paths, "_platform_dir", lambda kind: platform_dir)
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "from-env"))
    assert paths.data_dir() == tmp_path / "from-env"


def test_platformdirs_used_when_it_exists(monkeypatch, tmp_path):
    platform_dir = tmp_path / "platform"
    platform_dir.mkdir()
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(paths, "_platform_dir", lambda kind: platform_dir)
    assert paths.data_dir() == platform_dir


def test_platformdirs_skipped_when_absent(monkeypatch, tmp_path):
    """A non-existent user directory must not shadow repo autodetect.

    platformdirs returns a path whether or not anything is there; without the
    existence gate level 3 would always win and level 4 would be dead code.
    """
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(paths, "_platform_dir", lambda kind: tmp_path / "missing")
    repo = _make_fake_repo(tmp_path)
    monkeypatch.chdir(repo)
    assert paths.data_dir() == repo / "data"


def test_repo_autodetect_is_the_zero_config_path(monkeypatch, tmp_path, no_platform_dirs):
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.delenv(paths.OUTPUT_DIR_ENV, raising=False)
    repo = _make_fake_repo(tmp_path)
    monkeypatch.chdir(repo / "notebooks")
    assert paths.data_dir() == repo / "data"
    assert paths.output_dir() == repo / "output"


def test_nothing_resolves_names_the_environment_variable(
    monkeypatch, tmp_path, no_platform_dirs
):
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigurationError, match=paths.DATA_DIR_ENV):
        paths.data_dir()


# ------------------------------------------------------------- repo autodetect


def _make_fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    (repo / "notebooks").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "fair-shares"\n')
    return repo


def test_find_repo_root_returns_none_outside_a_checkout(tmp_path):
    assert paths.find_repo_root(tmp_path) is None


def test_find_repo_root_ignores_unrelated_projects(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "pyproject.toml").write_text('[project]\nname = "something-else"\n')
    assert paths.find_repo_root(other) is None


def test_find_repo_root_tolerates_malformed_pyproject(tmp_path):
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "pyproject.toml").write_text("this is not = valid toml [[[")
    assert paths.find_repo_root(broken) is None


# ---------------------------------------------------------- resolve_source_path


def test_data_prefix_resolves_against_the_data_dir(tmp_path):
    resolved = paths.resolve_source_path(
        "data/gini/unu-wider-2025/WIID.xlsx", data_dir=tmp_path / "d"
    )
    assert resolved == tmp_path / "d" / "gini" / "unu-wider-2025" / "WIID.xlsx"


def test_output_prefix_resolves_against_the_output_dir(tmp_path):
    resolved = paths.resolve_source_path(
        "output/src-id/intermediate/emissions/bunkers.csv",
        data_dir=tmp_path / "d",
        output_dir=tmp_path / "o",
    )
    assert resolved == tmp_path / "o" / "src-id" / "intermediate" / "emissions" / "bunkers.csv"


def test_prefixless_relative_path_is_data_relative(tmp_path):
    assert paths.resolve_source_path("regions/map.csv", data_dir=tmp_path) == (
        tmp_path / "regions" / "map.csv"
    )


def test_absolute_path_passes_through(tmp_path):
    absolute = tmp_path / "elsewhere" / "file.csv"
    assert paths.resolve_source_path(absolute) == absolute


# -------------------------------------------------------------- packaged config


def test_packaged_config_reads_the_shipped_yaml():
    resource = paths.packaged_config("data_sources/data_sources_unified.yaml")
    assert resource.is_file()
    assert "targets:" in resource.read_text()


# ------------------------------------------------------------------- configure


def test_configure_seeds_resolution_for_deep_callers(
    monkeypatch, tmp_path, no_platform_dirs
):
    """An explicit directory must reach resolver calls it cannot be threaded to.

    Path validation and source lookup resolve directories on their own, far
    below any entry point that accepts ``data_dir=``. Without seeding they fall
    through every level and raise, which makes level 1 of the precedence inert
    for everything except the handful of call sites that pass it by hand.
    """
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.delenv(paths.OUTPUT_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigurationError):
        paths.resolve_source_path("data/regions/map.csv")

    paths.configure(data_dir=tmp_path / "d", output_dir=tmp_path / "o")
    assert paths.resolve_source_path("data/regions/map.csv") == (
        tmp_path / "d" / "regions" / "map.csv"
    )
    assert paths.resolve_source_path("output/sid/x.csv") == tmp_path / "o" / "sid" / "x.csv"


def test_configure_ignores_none(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "env"))
    paths.configure(output_dir=tmp_path / "o")
    assert paths.data_dir() == tmp_path / "env"
    assert paths.output_dir() == tmp_path / "o"


def test_reset_path_cache_lets_the_environment_change(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "first"))
    assert paths.data_dir() == tmp_path / "first"
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "second"))
    assert paths.data_dir() == tmp_path / "first", "resolution should be cached"
    paths.reset_path_cache()
    assert paths.data_dir() == tmp_path / "second"
