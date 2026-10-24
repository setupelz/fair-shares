"""
Datapacks: the processed inputs of one release, ready to use.

``fair-shares fetch-data --pack`` downloads the datapack of the installed
version from its GitHub release and unpacks it into the output directory. The
pack holds a folder for every run in :func:`pack_runs`: each user-facing
notebook's defaults and every other combination of the shipped sources,
targets and categories. Those runs are then complete and current, so they run
with no raw inputs and without ``FAIR_SHARES_TRUST_CACHE``:
:func:`~fair_shares.library.utils.data.setup.setup_data` reads raw inputs only
when a folder must be rebuilt. Allocation settings (approach, weights, years)
never enter a folder, so any of them runs from the pack.

A pack holds, per folder, ``config.yaml``, the provenance stamp and
``intermediate/processed/``, and nothing else; ``output/datapack-<version>/``
holds its README, licence and citations. ``intermediate/scenarios/``
holds one row per Scenario Compass, ScenarioMIP and AR6 scenario, which their
licences do not allow us to redistribute, and the executed notebooks can show
the same rows. The processed files carry pooled values only, and
:func:`build_datapack` stops if one of them has a ``Model`` and a ``Scenario``
column.

The pack is CC BY-NC-SA 4.0, the terms of PRIMAP-hist v2.8. Its
``CITATIONS.md`` lists every source of every folder with its licence.

Each pack fits one version. The provenance stamp hashes the package version
and code, so a pack from another version is rebuilt from raw inputs on first
use, which is the safe outcome.

Maintainers build the pack at the release commit and attach both files to the
GitHub release::

    fair-shares build-datapack --out dist/datapack
    gh release upload v<version> dist/datapack/SHA256SUMS
    gh release upload v<version> dist/datapack/fair-shares-<version>-datapack.zip
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

import pandas as pd

from fair_shares.library.exceptions import ConfigurationError, DataIntegrityError

RELEASE_URL = "https://github.com/setupelz/fair-shares/releases/download"
SUMS_NAME = "SHA256SUMS"
PACK_LICENSE = "CC BY-NC-SA 4.0"
PACK_LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

#: Files of a folder that ship, relative to ``output/<source-id>/``.
_PACKED_FILES = ("config.yaml", ".provenance_stamp.json")
_PACKED_DIR = "intermediate/processed"
_PACKED_SUFFIXES = frozenset({".csv", ".yaml", ".json"})

#: Every emission category a folder can hold.
CATEGORIES = (
    "co2-ffi",
    "co2",
    "co2-lulucf",
    "non-co2",
    "all-ghg-ex-co2-lulucf",
    "all-ghg",
)

#: Sources the pack leaves out, and why. A run that selects one rebuilds its
#: folder from raw inputs. None at present: WIID (CC BY-NC-SA 3.0 IGO) is not
#: shipped in the repository, but its processed Gini may go out under the
#: pack's CC BY-NC-SA 4.0, a later version with the same licence elements.
EXCLUDED_SOURCES: dict[str, str] = {}


@dataclass(frozen=True)
class PackRun:
    """One output folder of the pack, set up as the runs that use it set it up."""

    notebooks: str
    emission_category: str
    target: str
    emissions: str
    lulucf: str | None = None
    harmonisation_year: int | None = None
    gdp: str = "wdi-2025"
    population: str = "un-owid-2025"
    gini: str = "wdi-2025"
    active_sources: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        """Assemble the run's ``active_sources``."""
        sources = {
            "gdp": self.gdp,
            "population": self.population,
            "gini": self.gini,
            "target": self.target,
            "emissions": self.emissions,
        }
        if self.lulucf:
            sources["lulucf"] = self.lulucf
        object.__setattr__(self, "active_sources", sources)


#: The folders the user-facing notebooks set up with their default settings.
#: Arguments match each notebook's ``setup_data`` call, so the stamps match.
# fmt: off
NOTEBOOK_RUNS: tuple[PackRun, ...] = (
    PackRun("301, 302, 405 (inventory), 601", "all-ghg", "rcbs", "primap-202609", "melo-2026-v4", 2020),
    PackRun("601", "all-ghg-ex-co2-lulucf", "rcbs", "primap-202609", "melo-2026-v4", 2020),
    PackRun("405, 601", "co2-ffi", "rcbs", "primap-202609", "melo-2026-v4"),
    PackRun("405 (inventory)", "co2", "rcbs", "primap-202609", "melo-2026-v4"),
    PackRun("405 (model)", "co2", "rcbs", "primap-202609", "gcb-2025-luc"),
    PackRun("405 (model)", "all-ghg", "rcbs", "primap-202609", "gcb-2025-luc", 2020),
    PackRun("303", "all-ghg", "rcb-pathways", "primap-202609", "melo-2026-v4", 2020),
    PackRun("602", "co2-ffi", "rcb-pathways", "primap-202503", "melo-2026", 2021),
    PackRun("604", "co2-ffi", "rcb-pathways", "primap-202503", None, 2020),
    PackRun("605", "co2-ffi", "rcbs", "primap-202503", "melo-2026"),
)
# fmt: on


def pack_runs() -> tuple[PackRun, ...]:
    """Return every run of the pack, one per output folder.

    The notebooks' own runs come first, so their labels stay. Then the grid:
    every emissions, GDP, population, Gini, LULUCF, target and category option
    of the unified config, less :data:`EXCLUDED_SOURCES`, at the configured
    harmonisation year. A combination the config rejects is not a run anyone
    can make and is left out, as is a land-use category without a LULUCF source
    (the Snakefile refuses it) or a fossil-only category with one (the source
    does not enter its folder).
    """
    import itertools

    import yaml

    from fair_shares.library.preprocessing.paths import LULUCF_CATEGORIES
    from fair_shares.library.utils.data.config import unified_config_path
    from fair_shares.library.utils.data.setup import resolve_data_setup

    with unified_config_path().open() as f:
        config = yaml.safe_load(f)

    def options(section: str) -> list[str]:
        return [name for name in config[section] if name not in EXCLUDED_SOURCES]

    grid = [
        PackRun("", category, target, emissions, lulucf, None, gdp, population, gini)
        for emissions, gdp, population, gini, target, category, lulucf in (
            itertools.product(
                options("emissions"),
                options("gdp"),
                options("population"),
                options("gini"),
                list(config["targets"]),
                CATEGORIES,
                [None, *options("lulucf")],
            )
        )
        if (category in LULUCF_CATEGORIES) == (lulucf is not None)
    ]

    runs: dict[str, PackRun] = {}
    for run in (*NOTEBOOK_RUNS, *grid):
        try:
            info = resolve_data_setup(
                emission_category=run.emission_category,
                active_sources=run.active_sources,
                harmonisation_year=run.harmonisation_year,
                verbose=False,
                check_raw_paths=False,
            )
        except (ConfigurationError, ValueError):
            continue
        runs.setdefault(info["source_id"], run)
    return tuple(runs.values())


def pack_name(version: str) -> str:
    """Return the zip file name of a version's pack."""
    return f"fair-shares-{version}-datapack.zip"


def docs_folder(version: str) -> str:
    """Return the output subfolder holding a pack's README, licence and citations.

    Under ``output/`` rather than the zip's root, so unzipping the pack into a
    checkout cannot overwrite the repository's own README or licence.
    """
    return f"datapack-{version}"


def packed_files(base_dir: Path) -> list[Path]:
    """Return the files of one output folder that go into a pack."""
    files = [base_dir / name for name in _PACKED_FILES]
    missing = [f.name for f in files if not f.is_file()]
    if missing:
        raise DataIntegrityError(
            f"{base_dir} lacks {', '.join(missing)}; rebuild it from a checkout "
            "so it carries a provenance stamp."
        )
    processed = base_dir / _PACKED_DIR
    for path in sorted(processed.iterdir()):
        if path.suffix not in _PACKED_SUFFIXES:
            raise DataIntegrityError(
                f"Unexpected file type in {processed}: {path.name}. Add its suffix "
                "to the pack's allowlist only after checking its contents."
            )
        if path.suffix == ".csv":
            _refuse_scenario_rows(path)
        files.append(path)
    return files


def _refuse_scenario_rows(path: Path) -> None:
    columns = {str(c).strip().lower() for c in pd.read_csv(path, nrows=0).columns}
    if {"model", "scenario"} <= columns:
        raise DataIntegrityError(
            f"{path} has one row per scenario (Model and Scenario columns). "
            "Scenario Compass, ScenarioMIP and AR6 data cannot be redistributed "
            "row by row, so the pack holds pooled values only."
        )


def build_datapack(
    dest: Path | str,
    *,
    runs: tuple[PackRun, ...] | None = None,
) -> Path:
    """Build every folder in ``runs`` and write the pack and ``SHA256SUMS``.

    Run it from a checkout at the release commit, with every raw input present:
    each folder is built, or reused if current, with
    :func:`~fair_shares.library.utils.data.setup.setup_data`, in the checkout's
    own output directory (Snakemake writes there whatever ``output_dir`` says).
    A failed build stops the pack; built folders stay current, so a rerun
    resumes where it stopped.

    Parameters
    ----------
    dest
        Directory for the zip and ``SHA256SUMS``.
    runs
        Defaults to :func:`pack_runs`.

    Returns
    -------
    Path
        The zip file.
    """
    import fair_shares
    from fair_shares.library.citations import RunCitations, citations, package_citation
    from fair_shares.library.data_fetch import sha256_of
    from fair_shares.library.utils.data.setup import setup_data

    version = fair_shares.__version__
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    runs = pack_runs() if runs is None else runs

    folders: dict[str, tuple[Path, PackRun]] = {}
    sources: dict[str, object] = {}
    for number, run in enumerate(runs, start=1):
        print(
            f"[{number}/{len(runs)}] {run.emission_category} {run.target} "
            f"{run.emissions} {run.lulucf or ''}",
            flush=True,
        )
        info = setup_data(
            emission_category=run.emission_category,
            active_sources=run.active_sources,
            harmonisation_year=run.harmonisation_year,
            verbose=False,
        )
        folders[info["source_id"]] = (Path(info["paths"]["base_dir"]), run)
        for name, source in citations(
            run.active_sources, emission_category=run.emission_category
        ).sources:
            sources.setdefault(name, source)

    zip_path = dest / pack_name(version)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source_id, (base_dir, _run) in sorted(folders.items()):
            for path in packed_files(base_dir):
                arcname = PurePosixPath(
                    "output", source_id, *path.relative_to(base_dir).parts
                )
                archive.write(path, str(arcname))
        docs = PurePosixPath("output", docs_folder(version))
        run_citations = RunCitations(
            software=package_citation(), sources=tuple(sorted(sources.items()))
        )
        archive.writestr(str(docs / "README.md"), _readme(version, folders))
        archive.writestr(str(docs / "LICENSE.txt"), _license_text())
        archive.writestr(str(docs / "CITATIONS.md"), run_citations.text())

    (dest / SUMS_NAME).write_text(f"{sha256_of(zip_path)}  {zip_path.name}\n")
    return zip_path


def _readme(version: str, folders: dict[str, tuple[Path, PackRun]]) -> str:
    rows = "\n".join(
        f"| `{source_id}` | {run.notebooks} |"
        for source_id, (_base, run) in sorted(folders.items())
    )
    return f"""# fair-shares {version} datapack

The processed inputs of fair-shares {version}: one folder for every combination
of the shipped emissions, land-use, GDP, population and Gini sources, targets
and emission categories, including each notebook's defaults (named below).
With them a run needs no raw data, whatever its allocation settings: approach,
weights and years are applied on top of these files.

Install from a checkout of the same version:

    fair-shares fetch-data --pack

or unzip the pack into the repository root, so the folders land in `output/`.
A folder is used as it is while it matches the installed code; a change to the
code, the configuration or the sources rebuilds it from raw inputs.

| Folder | Notebooks |
| --- | --- |
{rows}

Licence: {PACK_LICENSE} ({PACK_LICENSE_URL}) for the whole pack, because most
folders derive from PRIMAP-hist v2.8 or the WIID Gini. Results built on these
files are under their non-commercial, share-alike terms. For CC BY results, build
the `primap-202503` or `gcb-2025` folders with the WDI Gini from raw inputs
instead. `CITATIONS.md` lists every source
with its own licence; cite them as well as fair-shares.

Scenario-derived values are pooled statistics only (bunker shares, set
medians and counts). Scenario Compass data are used under its terms, which
apply Nature's editorial and embargo policy until Riahi et al. is published.
"""


def _license_text() -> str:
    return f"""This datapack is licensed under the Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International licence ({PACK_LICENSE}).
Licence text: {PACK_LICENSE_URL}legalcode

It is adapted material derived from the sources listed in CITATIONS.md, each of
which keeps its own licence. The most restrictive of them, PRIMAP-hist v2.8
(CC BY-NC-SA 4.0) and UNU-WIDER WIID (CC BY-NC-SA 3.0 IGO, whose adaptations
may go out under a later version with the same licence elements), set the
licence of the pack.

The fair-shares software is BSD-3-Clause; that licence does not cover this data.
"""


def fetch_datapack(
    *,
    version: str | None = None,
    output_dir: Path | str | None = None,
    force: bool = False,
    base_url: str = RELEASE_URL,
) -> list[Path]:
    """Download a version's pack, check its hash and unpack it.

    A folder that already exists is left alone unless ``force`` is set, in
    which case the pack's files overwrite their copies and every other file in
    the folder (allocation results, for example) stays.

    Returns
    -------
    list[Path]
        The folders written.
    """
    import fair_shares
    from fair_shares.library import paths
    from fair_shares.library.data_fetch import _download_to, sha256_of

    installed = fair_shares.__version__
    version = version or installed
    if not version[0].isdigit() or any(tag in version for tag in ("dev", "+")):
        raise ConfigurationError(
            f"fair-shares {version} is not a release, so it has no datapack. "
            "Pass --pack-version with a released version; its folders are used "
            "only if they match your code."
        )

    target = paths.output_dir(output_dir)
    name = pack_name(version)
    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        sums = _download_to(
            f"{base_url}/v{version}/{SUMS_NAME}", tmp_dir / SUMS_NAME, {}
        )
        expected = _expected_hash(sums.read_text(), name)
        archive_path = _download_to(f"{base_url}/v{version}/{name}", tmp_dir / name, {})
        got = sha256_of(archive_path)
        if got != expected:
            raise DataIntegrityError(
                f"{name} does not match {SUMS_NAME}: expected {expected}, got {got}. "
                "Download again; if it persists, report it."
            )
        return _extract(archive_path, target, force=force)


def _expected_hash(sums: str, name: str) -> str:
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return parts[0]
    raise DataIntegrityError(f"{SUMS_NAME} has no entry for {name}.")


def _extract(archive_path: Path, target: Path, *, force: bool) -> list[Path]:
    written: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        by_folder: dict[str, list[zipfile.ZipInfo]] = {}
        for member in archive.infolist():
            parts = PurePosixPath(member.filename).parts
            if member.is_dir() or len(parts) < 3 or parts[0] != "output":
                continue
            if (
                any(part in ("..", "") for part in parts)
                or PurePosixPath(member.filename).is_absolute()
            ):
                raise DataIntegrityError(f"Unsafe path in pack: {member.filename}")
            by_folder.setdefault(parts[1], []).append(member)

        for source_id, members in sorted(by_folder.items()):
            folder = target / source_id
            if folder.exists() and not force:
                print(
                    f"  present  {source_id} (kept; --force overwrites the pack's files)"
                )
                continue
            for member in members:
                dest = target.joinpath(*PurePosixPath(member.filename).parts[1:])
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, dest.open("wb") as out:
                    shutil.copyfileobj(src, out)
            print(f"  unpacked {source_id}")
            written.append(folder)
    return written
