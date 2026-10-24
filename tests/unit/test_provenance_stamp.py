"""Provenance stamps decide when setup_data reuses or rebuilds an output folder."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from fair_shares.library.utils.data import provenance
from fair_shares.library.utils.data import setup as setup_mod

CONFIG = {
    "active_target_source": "rcbs",
    "targets": {"rcbs": {"path": "data/rcbs/rcbs.yaml"}},
}


def _tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    pkg, repo, data = tmp_path / "pkg", tmp_path / "repo", tmp_path / "data"
    files = {
        pkg / "library/preprocessing/rcbs.py": "x = 1\n",
        pkg / "conf/data_sources/sources.yaml": "a: 1\n",
        repo / "Snakefile": "rule all:\n",
        repo / "notebooks/101_emiss.py": "print(1)\n",
        repo / "notebooks/301_custom.py": "print(3)\n",
        data / "rcbs/rcbs.yaml": "budgets: []\n",
    }
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return pkg, repo, data


def test_components_name_what_changed(tmp_path):
    pkg, repo, data = _tree(tmp_path)
    before = provenance.compute_components(CONFIG, repo, data, package_root=pkg)
    assert "repo:notebooks/101_emiss.py" in before
    assert "repo:notebooks/301_custom.py" not in before
    assert before["data:data/rcbs/rcbs.yaml"].startswith("file:")
    assert provenance.changed_components(before, before) == []

    (repo / "notebooks/101_emiss.py").write_text("print(2)\n")
    (pkg / "conf/data_sources/sources.yaml").write_text("a: 2\n")
    (data / "rcbs/rcbs.yaml").write_text("budgets: [1]\n")
    after = provenance.compute_components(
        {**CONFIG, "harmonisation_year": 2023}, repo, data, package_root=pkg
    )
    assert provenance.changed_components(before, after) == [
        "data:data/rcbs/rcbs.yaml",
        "library:conf/data_sources/sources.yaml",
        "repo:notebooks/101_emiss.py",
        "run_config",
    ]


def test_windows_line_endings_stamp_like_lf(tmp_path):
    pkg, repo, data = _tree(tmp_path)
    lf = provenance.compute_components(CONFIG, repo, data, package_root=pkg)
    for path in [
        *tmp_path.rglob("*.py"),
        *tmp_path.rglob("*.yaml"),
        repo / "Snakefile",
    ]:
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    crlf = provenance.compute_components(CONFIG, repo, data, package_root=pkg)
    assert provenance.changed_components(lf, crlf) == []


def test_lulucf_source_stamps_only_land_use_categories(tmp_path):
    pkg, repo, data = _tree(tmp_path)

    def stamp(category, lulucf):
        config = {
            **CONFIG,
            "emission_category": category,
            "active_lulucf_source": lulucf,
            "lulucf": {lulucf: {"path": f"data/lulucf/{lulucf}/x.csv"}},
        }
        return provenance.compute_components(config, repo, data, package_root=pkg)

    # Fossil CO2 never reads the LULUCF source, so either basis shares a stamp.
    assert stamp("co2-ffi", "gcb-2025-luc") == stamp("co2-ffi", "melo-2026-v4")
    assert stamp("co2", "gcb-2025-luc") != stamp("co2", "melo-2026-v4")


def test_binary_files_hash_byte_for_byte(tmp_path):
    blob = tmp_path / "inputs.nc"
    blob.write_bytes(b"a\nb")
    lf = provenance._sha256_file(blob)
    blob.write_bytes(b"a\r\nb")
    assert provenance._sha256_file(blob) != lf


def test_suspended_path_checks_skip_missing_raw_inputs(monkeypatch):
    from fair_shares.library.exceptions import ConfigurationError
    from fair_shares.library.utils.dataframes import validate_path_exists

    monkeypatch.delenv(provenance.TRUST_CACHE_ENV, raising=False)
    missing = "/no/such/dir/raw.nc"
    with provenance.raw_path_checks_suspended():
        assert validate_path_exists(missing) == missing
    with pytest.raises(ConfigurationError):
        validate_path_exists(missing)


def test_validate_data_source_config_checks_no_raw_inputs(monkeypatch):
    # The notebooks validate before setup_data; a ready-made folder must pass
    # without raw inputs, and validation must not fetch them.
    from fair_shares.library.utils.data import config as config_mod

    raw_checks = []

    def fake_build(**kw):
        raw_checks.append(provenance.raw_path_checks_enabled())
        return None, "sid"

    monkeypatch.setattr(config_mod, "build_data_config", fake_build)
    monkeypatch.delenv(provenance.TRUST_CACHE_ENV, raising=False)
    sources = {
        "emissions": "primap-202609",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "wdi-2025",
        "target": "rcbs",
    }
    result = config_mod.validate_data_source_config("co2-ffi", sources, verbose=False)
    assert result["valid"]
    assert raw_checks == [False]
    assert provenance.raw_path_checks_enabled()


class _Config:
    def model_dump(self, mode="json"):
        return CONFIG


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """setup_data with the build and the hashing replaced by recorders."""
    base_dir = tmp_path / "output" / "sid"
    processed = base_dir / "intermediate" / "processed"
    processed.mkdir(parents=True)
    (processed / "present.csv").write_text("x\n")
    state = {"components": {"run_config": "a"}, "builds": [], "raw_checks": []}

    def fake_resolve(**kw):
        state["raw_checks"].append(kw.get("check_raw_paths", True))
        return {
            "paths": {"base_dir": base_dir, "processed_dir": processed},
            "config": _Config(),
            "emission_category": "co2-ffi",
            "target": "rcbs",
            "verification": {
                "all_files_exist": True,
                "file_info": {"present": {"exists": True, "size_mb": 0.0}},
            },
        }

    monkeypatch.setattr(setup_mod, "resolve_data_setup", fake_resolve)
    monkeypatch.setattr(
        setup_mod,
        "build_data_setup",
        lambda info, **kw: state["builds"].append(kw["force"]) or info,
    )
    monkeypatch.setattr(
        setup_mod, "compute_components", lambda *a, **k: dict(state["components"])
    )
    monkeypatch.setattr("fair_shares.library.paths.find_repo_root", lambda: tmp_path)
    monkeypatch.delenv(provenance.TRUST_CACHE_ENV, raising=False)
    state["base_dir"] = base_dir
    return state


def _run():
    return setup_mod.setup_data(
        emission_category="co2-ffi", active_sources={"target": "rcbs"}, verbose=False
    )


def test_missing_stamp_rebuilds_then_writes_stamp(harness, caplog):
    with caplog.at_level(logging.WARNING):
        _run()
    assert harness["builds"] == [True]
    assert "no stamp" in caplog.text
    assert provenance.read_stamp(harness["base_dir"]) == {"run_config": "a"}


def test_matching_stamp_reuses(harness):
    provenance.write_stamp(harness["base_dir"], {"run_config": "a"})
    _run()
    assert harness["builds"] == []
    # A current folder is resolved once, without checking raw inputs.
    assert harness["raw_checks"] == [False]


def test_changed_component_rebuilds_and_is_named(harness, caplog):
    provenance.write_stamp(harness["base_dir"], {"run_config": "a"})
    harness["components"] = {"run_config": "a", "repo:notebooks/101_emiss.py": "b"}
    with caplog.at_level(logging.WARNING):
        _run()
    assert harness["builds"] == [True]
    assert "repo:notebooks/101_emiss.py" in caplog.text
    # The build re-resolves with raw inputs checked (and fetched).
    assert harness["raw_checks"] == [False, True]


def test_trust_cache_opt_out(harness, monkeypatch):
    monkeypatch.setenv(provenance.TRUST_CACHE_ENV, "1")
    _run()
    assert harness["builds"] == []
    assert provenance.read_stamp(harness["base_dir"]) is None
