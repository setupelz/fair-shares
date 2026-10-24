"""Datapacks ship processed inputs only, check their hash and never clobber results."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from fair_shares.library import datapack
from fair_shares.library.exceptions import ConfigurationError, DataIntegrityError
from fair_shares.library.utils.data.config import build_source_id


def _folder(base: Path) -> Path:
    files = {
        "config.yaml": "a: 1\n",
        ".provenance_stamp.json": "{}\n",
        "intermediate/processed/rcbs_co2.csv": "source,rcb_2020_mt\nforster_2026,1\n",
        "intermediate/processed/meta.yaml": "x: 1\n",
        "intermediate/scenarios/bunker_share_reporters.csv": "source,Model,Scenario\n",
        "intermediate/emissions/raw_copy.csv": "iso3c,2020\n",
        "notebooks/104_scenarios.ipynb": "{}",
    }
    for rel, text in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return base


def test_only_config_stamp_and_processed_files_ship(tmp_path):
    base = _folder(tmp_path / "sid")
    shipped = {p.relative_to(base).as_posix() for p in datapack.packed_files(base)}
    assert shipped == {
        "config.yaml",
        ".provenance_stamp.json",
        "intermediate/processed/rcbs_co2.csv",
        "intermediate/processed/meta.yaml",
    }


def test_per_scenario_rows_stop_the_build(tmp_path):
    base = _folder(tmp_path / "sid")
    (base / "intermediate/processed/sets.csv").write_text("Model,Scenario,co2\nm,s,1\n")
    with pytest.raises(DataIntegrityError, match="one row per scenario"):
        datapack.packed_files(base)


def test_unknown_file_type_stops_the_build(tmp_path):
    base = _folder(tmp_path / "sid")
    (base / "intermediate/processed/series.parquet").write_bytes(b"PAR1")
    with pytest.raises(DataIntegrityError, match="Unexpected file type"):
        datapack.packed_files(base)


def test_notebook_runs_have_one_folder_each():
    ids = [
        build_source_id(
            emissions=run.emissions,
            gdp=run.gdp,
            population=run.population,
            gini=run.gini,
            target=run.target,
            emission_category=run.emission_category,
            lulucf=run.lulucf,
            harmonisation_year=run.harmonisation_year,
            default_harmonisation_year=2020,
        )
        for run in datapack.NOTEBOOK_RUNS
    ]
    assert len(ids) == len(set(ids))


def test_pack_runs_cover_the_notebooks_and_respect_exclusions(monkeypatch):
    from fair_shares.library.preprocessing.paths import LULUCF_CATEGORIES

    monkeypatch.setenv("FAIR_SHARES_AUTO_FETCH", "0")
    runs = datapack.pack_runs()
    assert runs[: len(datapack.NOTEBOOK_RUNS)] == datapack.NOTEBOOK_RUNS
    for run in runs:
        assert not set(run.active_sources.values()) & set(datapack.EXCLUDED_SOURCES)
    assert {run.gini for run in runs} == {"wdi-2025", "unu-wider-2025"}
    for run in runs[len(datapack.NOTEBOOK_RUNS) :]:
        # Grid runs: land use needs a LULUCF source, fossil-only takes none.
        # (Notebooks 405 and 601 pass one for co2-ffi; the stamp ignores it.)
        assert (run.emission_category in LULUCF_CATEGORIES) == (run.lulucf is not None)


def _zip(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return path


def test_extract_keeps_existing_folders_unless_forced(tmp_path):
    pack = _zip(
        tmp_path / "pack.zip",
        {
            "output/sid/config.yaml": "new\n",
            "output/datapack-0.7.0/README.md": "readme\n",
        },
    )
    out = tmp_path / "output"
    (out / "sid/allocations").mkdir(parents=True)
    (out / "sid/config.yaml").write_text("old\n")
    (out / "sid/allocations/result.parquet").write_text("mine\n")

    assert datapack._extract(pack, out, force=False) == [out / "datapack-0.7.0"]
    assert (out / "sid/config.yaml").read_text() == "old\n"

    datapack._extract(pack, out, force=True)
    assert (out / "sid/config.yaml").read_text() == "new\n"
    # A forced unpack overwrites the pack's files and nothing else.
    assert (out / "sid/allocations/result.parquet").read_text() == "mine\n"


def test_extract_refuses_paths_outside_the_output_dir(tmp_path):
    pack = _zip(tmp_path / "pack.zip", {"output/sid/../../evil.txt": "x"})
    with pytest.raises(DataIntegrityError, match="Unsafe path"):
        datapack._extract(pack, tmp_path / "output", force=False)


@pytest.fixture
def release(tmp_path, monkeypatch):
    """A fake GitHub release served from local files."""
    served = tmp_path / "release"
    served.mkdir()
    name = datapack.pack_name("0.7.0")
    _zip(served / name, {"output/sid/config.yaml": "a\n"})

    def fake_download(url, dest, headers):
        dest.write_bytes((served / url.rsplit("/", 1)[1]).read_bytes())
        return dest

    monkeypatch.setattr("fair_shares.library.data_fetch._download_to", fake_download)
    return served, name


def test_fetch_unpacks_a_pack_whose_hash_matches(release, tmp_path):
    from fair_shares.library.data_fetch import sha256_of

    served, name = release
    (served / "SHA256SUMS").write_text(f"{sha256_of(served / name)}  {name}\n")
    written = datapack.fetch_datapack(version="0.7.0", output_dir=tmp_path / "out")
    assert written == [tmp_path / "out" / "sid"]


def test_fetch_refuses_a_pack_whose_hash_differs(release, tmp_path):
    served, name = release
    (served / "SHA256SUMS").write_text(f"{'0' * 64}  {name}\n")
    with pytest.raises(DataIntegrityError, match="does not match"):
        datapack.fetch_datapack(version="0.7.0", output_dir=tmp_path / "out")
    assert not (tmp_path / "out" / "sid").exists()


@pytest.mark.parametrize("version", ["0.7.1.dev3", "0.7.0+g1234"])
def test_development_versions_have_no_pack(version, tmp_path):
    with pytest.raises(ConfigurationError, match="not a release"):
        datapack.fetch_datapack(version=version, output_dir=tmp_path)
