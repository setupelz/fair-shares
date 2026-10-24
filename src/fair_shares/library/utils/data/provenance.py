"""
Provenance stamps for preprocessed output folders.

Each ``output/<source-id>/`` folder carries a ``.provenance_stamp.json`` that
records one hash per input that shapes its contents: the package version, the
composed run config, every preprocessing notebook, the library modules and
packaged config files preprocessing uses, ``data/rcbs/rcbs.yaml`` and the
registry checksums of the run's input data files.

:func:`~fair_shares.library.utils.data.setup.setup_data` compares the stored
stamp with a fresh one. A missing or different stamp forces Snakemake to
rebuild the folder, and the log line names the components that changed. Set
``FAIR_SHARES_TRUST_CACHE=1`` (or pass ``trust_cache=True``) to reuse a folder
without the check.

Text files hash with CRLF line endings read as LF, so a Windows checkout
(``* text=auto``) stamps the same as a macOS or Linux one and a folder built on
one platform stays current on the other.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

STAMP_FILENAME = ".provenance_stamp.json"
TRUST_CACHE_ENV = "FAIR_SHARES_TRUST_CACHE"
STAMP_VERSION = 1

#: Files hashed with CRLF normalised to LF. Git rewrites their line endings on
#: a Windows checkout; binary inputs (.nc, .xlsx, .zip) are left byte for byte.
TEXT_SUFFIXES: frozenset[str] = frozenset(
    {".py", ".yaml", ".yml", ".csv", ".json", ".md", ".txt"}
)
TEXT_FILENAMES: frozenset[str] = frozenset({"Snakefile"})

_RAW_PATH_CHECKS: ContextVar[bool] = ContextVar(
    "fair_shares_raw_path_checks", default=True
)

# Package-relative globs for code and config that preprocessing imports.
LIBRARY_GLOBS: tuple[str, ...] = (
    "library/pipeline/**/*.py",
    "library/preprocessing/**/*.py",
    "library/utils/data/**/*.py",
    "library/iamc_historical/**/*.py",
    "library/utils/*.py",
    "library/config/*.py",
    "library/paths.py",
    "library/validation/pipeline_validation.py",
    "conf/**/*.yaml",
)
# Repo-relative globs, present only in a checkout.
CHECKOUT_GLOBS: tuple[str, ...] = ("Snakefile", "notebooks/1[0-9][0-9]_*.py")

_ACTIVE_SECTIONS: tuple[tuple[str, str], ...] = (
    ("emissions", "active_emissions_source"),
    ("gdp", "active_gdp_source"),
    ("population", "active_population_source"),
    ("gini", "active_gini_source"),
    ("lulucf", "active_lulucf_source"),
    ("targets", "active_target_source"),
    ("scenarios", "active_scenario_source"),
)
# Unregistered files above this size are stamped by size, not content.
_CONTENT_HASH_MAX_BYTES = 50 * 1024 * 1024
_RCBS_YAML = "data/rcbs/rcbs.yaml"


def trust_cache_enabled(trust_cache: bool | None = None) -> bool:
    """Return whether the provenance check is switched off.

    An explicit argument wins; otherwise ``FAIR_SHARES_TRUST_CACHE`` set to
    ``1``, ``true`` or ``yes`` switches it off.
    """
    if trust_cache is not None:
        return bool(trust_cache)
    value = os.environ.get(TRUST_CACHE_ENV, "").strip().lower()
    return value in {"1", "true", "yes"}


@contextmanager
def raw_path_checks_suspended() -> Iterator[None]:
    """Build a config without checking, or fetching, its raw input paths.

    :func:`~fair_shares.library.utils.data.setup.setup_data` resolves a run this
    way first, so a folder whose processed files are complete and current needs
    no raw inputs at all. Raw inputs are checked once a build has to run.
    """
    token = _RAW_PATH_CHECKS.set(False)
    try:
        yield
    finally:
        _RAW_PATH_CHECKS.reset(token)


def raw_path_checks_enabled() -> bool:
    """Whether configured raw input paths must exist (and may be fetched)."""
    return _RAW_PATH_CHECKS.get() and not trust_cache_enabled()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_FILENAMES


def _sha256_file(path: Path) -> str:
    if _is_text(path):
        return _sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_globs(root: Path, globs: tuple[str, ...], prefix: str) -> dict[str, str]:
    components: dict[str, str] = {}
    for pattern in globs:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and "__pycache__" not in path.parts:
                rel = path.relative_to(root).as_posix()
                components[f"{prefix}:{rel}"] = _sha256_file(path)
    return components


def _collect_data_paths(node: Any, found: set[str]) -> None:
    if isinstance(node, str):
        if node.replace("\\", "/").startswith("data/"):
            found.add(node.replace("\\", "/"))
    elif isinstance(node, dict):
        for value in node.values():
            _collect_data_paths(value, found)
    elif isinstance(node, list | tuple):
        for value in node:
            _collect_data_paths(value, found)


def stamped_config(config_dump: dict[str, Any]) -> dict[str, Any]:
    """Return the part of a composed config that shapes the output folder.

    A category without land-use CO₂ never reads the LULUCF source: the
    Snakefile skips the land-use step and :func:`build_source_id` leaves the
    source out of the folder name. The stamp leaves it out too, so the runs
    that share such a folder (notebook 405 on either land-use basis, notebook
    601) do not rebuild it for one another.
    """
    from fair_shares.library.preprocessing.paths import LULUCF_CATEGORIES

    if config_dump.get("emission_category") in LULUCF_CATEGORIES:
        return config_dump
    return {
        key: value
        for key, value in config_dump.items()
        if key not in ("lulucf", "active_lulucf_source")
    }


def active_data_paths(config_dump: dict[str, Any]) -> list[str]:
    """Return the ``data/`` paths of the active sources in a composed config."""
    found: set[str] = set()
    for section, active_key in _ACTIVE_SECTIONS:
        active = config_dump.get(active_key)
        if active:
            _collect_data_paths(config_dump.get(section, {}).get(active), found)
    _collect_data_paths(config_dump.get("general"), found)
    found.add(_RCBS_YAML)
    return sorted(found)


def _data_file_hash(rel: str, data_root: Path | None, registry: Any) -> str:
    from fair_shares.library.data_registry import normalise_target

    key = normalise_target(rel)
    entry = registry.target_index().get(key)
    if entry is not None and registry[entry[0]].tier != "bundled":
        download = entry[1]
        pinned = download.sha256 or download.reference_sha256
        if pinned:
            return f"registry:{pinned}"
    # Bundled files can be edited in place, so hash their contents.
    if data_root is None:
        return "unresolved"
    path = data_root / key
    if not path.is_file():
        return "absent"
    size = path.stat().st_size
    if size > _CONTENT_HASH_MAX_BYTES:
        return f"size:{size}"
    return f"file:{_sha256_file(path)}"


def compute_components(
    config_dump: dict[str, Any],
    repo_root: Path | None,
    data_root: Path | None,
    package_root: Path | None = None,
) -> dict[str, str]:
    """Hash every input that shapes a preprocessed output folder.

    Parameters
    ----------
    config_dump : dict
        The composed run config, as ``model_dump(mode="json")`` gives it.
    repo_root : Path | None
        The checkout holding ``Snakefile`` and ``notebooks/``. ``None`` skips
        those components.
    data_root : Path | None
        The resolved input data directory, for files without a registry hash.
    package_root : Path | None
        The ``fair_shares`` package directory. Defaults to the installed one.

    Returns
    -------
    dict[str, str]
        Component name to hash, e.g. ``{"notebook:notebooks/101_...py": ...}``.
    """
    import fair_shares
    from fair_shares.library.data_registry import load_registry

    if package_root is None:
        package_root = Path(fair_shares.__file__).parent

    config_dump = stamped_config(config_dump)
    components: dict[str, str] = {
        "package_version": str(getattr(fair_shares, "__version__", "unknown")),
        "run_config": _sha256_bytes(
            json.dumps(config_dump, sort_keys=True, default=str).encode()
        ),
    }
    components.update(_hash_globs(package_root, LIBRARY_GLOBS, "library"))
    if repo_root is not None:
        components.update(_hash_globs(Path(repo_root), CHECKOUT_GLOBS, "repo"))

    registry = load_registry()
    for rel in active_data_paths(config_dump):
        components[f"data:{rel}"] = _data_file_hash(rel, data_root, registry)
    return components


def stamp_path(base_dir: Path) -> Path:
    """Return the stamp location for an ``output/<source-id>/`` folder."""
    return Path(base_dir) / STAMP_FILENAME


def read_stamp(base_dir: Path) -> dict[str, str] | None:
    """Return the stored components, or ``None`` when absent or unreadable."""
    path = stamp_path(base_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    components = payload.get("components") if isinstance(payload, dict) else None
    return components if isinstance(components, dict) else None


def write_stamp(base_dir: Path, components: dict[str, str]) -> Path:
    """Write the stamp atomically and return its path."""
    path = stamp_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stamp_version": STAMP_VERSION,
        "components": dict(sorted(components.items())),
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def clear_stamp(base_dir: Path) -> None:
    """Remove the stamp, so a failed rebuild never inherits a matching one."""
    stamp_path(base_dir).unlink(missing_ok=True)


def changed_components(
    stored: dict[str, str] | None, current: dict[str, str]
) -> list[str]:
    """Name the components that differ; ``["no stamp"]`` when none is stored."""
    if stored is None:
        return ["no stamp"]
    names = set(stored) | set(current)
    return sorted(n for n in names if stored.get(n) != current.get(n))


def describe_changes(changed: list[str], limit: int = 5) -> str:
    """Join changed component names into one short phrase."""
    shown = ", ".join(changed[:limit])
    extra = len(changed) - limit
    return f"{shown}, +{extra} more" if extra > 0 else shown
