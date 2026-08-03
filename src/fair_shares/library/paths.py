"""Resolution of the data and output directories, and of packaged config files.

Two directories are resolved independently: the *data* directory holding
inputs (``data/`` in a checkout) and the *output* directory holding pipeline
products (``output/`` in a checkout). A common deployment pairs a read-only
shared data directory with a per-user writable output directory, so they are
never derived from one another.

Both are worked out the same way, highest priority first:

1. an argument passed straight to the call,
2. **whatever was worked out earlier in this process** — either seeded by
   :func:`configure` or remembered from the first lookup,
3. the ``FAIR_SHARES_DATA_DIR`` / ``FAIR_SHARES_OUTPUT_DIR`` environment
   variable,
4. the per-user location, **only if it already exists**,
5. the surrounding checkout, if the working directory is inside one.

Level 2 is the per-process cache: results are remembered, because every
level touches the filesystem and the pipeline asks many times. So the first
lookup in a process fixes the answer, and setting the environment variable after
that has no effect until :func:`reset_path_cache` or a fresh
:func:`configure` call. Tests that change ``FAIR_SHARES_*`` or the working
directory must reset between cases.

Level 4 checks the directory exists on purpose. The per-user location is
returned whether or not anything is in it, so using it unconditionally would
hide level 5 and turn "there is no data anywhere" into a missing-file
error rather than a :class:`ConfigurationError` naming the environment variable.

Level 5 is why a checkout needs no configuration at all. It returns ``None``
rather than raising when there is no checkout, which lets the caller give an
error naming the environment variable, and lets an installed copy run from any
directory.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from fair_shares.library.exceptions import ConfigurationError

DATA_DIR_ENV = "FAIR_SHARES_DATA_DIR"
OUTPUT_DIR_ENV = "FAIR_SHARES_OUTPUT_DIR"

_APP_NAME = "fair-shares"

_cache: dict[str, Path | None] = {}


class _Unset:
    """Marks an argument that was not supplied at all.

    Needed because ``None`` is a meaningful value here: it means "clear this
    directory". Without a separate marker there would be no way to tell
    ``configure(data_dir=x)`` from ``configure(data_dir=x, output_dir=None)``.
    """


_UNSET = _Unset()


def configure(
    *,
    data_dir: Path | str | None | _Unset = _UNSET,
    output_dir: Path | str | None | _Unset = _UNSET,
) -> None:
    """Set the directories for the rest of this process.

    Entry points that take ``data_dir`` / ``output_dir`` call this so the
    argument reaches the lookups deep inside the call tree (path checking,
    source lookup), not just the few places it can be passed by hand.

    **Passing ``None`` clears that directory** and puts it back to normal
    lookup. That is what stops one call with ``data_dir="/scratch/alt"`` from
    silently repointing every later call in the same session: an entry point
    called without a directory passes ``None`` down, which resets it.

    Leaving an argument out is different from passing ``None`` — it leaves that
    directory untouched. So ``configure(data_dir=x)`` does not disturb the
    output directory.
    """
    for kind, value in (("data", data_dir), ("output", output_dir)):
        if isinstance(value, _Unset):
            continue
        if value is None:
            _cache.pop(kind, None)
        else:
            _cache[kind] = Path(value)


def reset_path_cache() -> None:
    """Clear the per-process resolution cache.

    Resolution is cached because it touches the filesystem on every level.
    Tests that manipulate ``FAIR_SHARES_*`` or the working directory must call
    this between cases.
    """
    _cache.clear()


def find_repo_root(start: Path | None = None) -> Path | None:
    """Return the fair-shares checkout containing ``start``, or ``None``.

    Walks upward looking for a ``pyproject.toml`` whose ``[project].name`` is
    ``fair-shares``. Returns ``None`` rather than raising when there is none —
    an installed wheel run from an arbitrary directory is a supported case,
    not an error.
    """
    current = Path(start) if start is not None else Path.cwd()
    try:
        current = current.resolve()
    except OSError:
        return None
    for candidate in (current, *current.parents):
        pyproject = candidate / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            with pyproject.open("rb") as handle:
                parsed = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if parsed.get("project", {}).get("name") == _APP_NAME:
            return candidate
    return None


def _platform_dir(kind: str) -> Path | None:
    try:
        import platformdirs
    except ImportError:  # pragma: no cover - platformdirs is a runtime dep
        return None
    if kind == "data":
        return Path(platformdirs.user_data_dir(_APP_NAME)) / "data"
    return Path(platformdirs.user_cache_dir(_APP_NAME)) / "output"


def _resolve(kind: str, explicit: Path | str | None) -> Path:
    if explicit is not None:
        return Path(explicit)

    if kind in _cache:
        cached = _cache[kind]
        if cached is not None:
            return cached

    env_var = DATA_DIR_ENV if kind == "data" else OUTPUT_DIR_ENV
    resolved: Path | None = None

    from_env = os.environ.get(env_var)
    if from_env:
        resolved = Path(from_env)
    else:
        platform_candidate = _platform_dir(kind)
        if platform_candidate is not None and platform_candidate.is_dir():
            resolved = platform_candidate
        else:
            repo_root = find_repo_root()
            if repo_root is not None:
                resolved = repo_root / ("data" if kind == "data" else "output")

    if resolved is None:
        raise ConfigurationError(
            f"Could not resolve the fair-shares {kind} directory. Set "
            f"{env_var} to the directory holding your "
            f"{'input data' if kind == 'data' else 'pipeline output'}, pass it "
            f"explicitly, or run from inside a fair-shares checkout."
        )

    _cache[kind] = resolved
    return resolved


def data_dir(explicit: Path | str | None = None) -> Path:
    """Return the directory holding input data (``data/`` in a checkout)."""
    return _resolve("data", explicit)


def data_dir_for_write(explicit: Path | str | None = None) -> Path:
    """Return where newly downloaded data files should be written.

    Same as :func:`data_dir` except at the very last step: where reading gives up
    with a :class:`ConfigurationError` because nothing exists anywhere yet,
    writing falls back to the per-user location, which the caller may create.

    In a fresh checkout with no per-user directory this gives the checkout's own
    ``data/``, and that order matters. Reading only uses the per-user location if
    it already exists, so the moment anything creates it, it beats the checkout
    from then on — even from inside the checkout. If downloading defaulted to the
    per-user location, the first download anyone ran would quietly change where
    the repository looks for its own data.

    Note this follows the per-user location rather than overriding it: **once
    that directory exists it wins, even inside a checkout.** That is deliberate —
    creating it is how you opt in to a shared data directory — but it does mean
    this is not an unconditional "always the checkout" rule.
    """
    if explicit is not None:
        return Path(explicit)

    try:
        # Must use the same logic reads use. If this worked it out separately, a
        # download triggered by a read could land in a different directory from
        # the one the read is looking in, and the file would still seem missing.
        return _resolve("data", None)
    except ConfigurationError:
        platform_candidate = _platform_dir("data")
        if platform_candidate is None:
            raise
        # Remembered like any other answer, so reads later in this process agree
        # with where the download just went instead of raising.
        _cache["data"] = platform_candidate
        return platform_candidate


def output_dir(explicit: Path | str | None = None) -> Path:
    """Return the directory holding pipeline products (``output/`` in a checkout)."""
    return _resolve("output", explicit)


def resolve_source_path(
    rel: str | Path,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Resolve a repo-relative config path against the resolved directories.

    Data-source configs store repo-relative strings such as
    ``data/gini/unu-wider-2025/WIID-29APR2025.xlsx`` or
    ``output/{source_id}/intermediate/emissions/bunker_timeseries.csv``. The
    leading segment selects the directory: ``data/`` resolves against the data
    directory and ``output/`` against the output directory, both with the
    prefix stripped. Anything else relative is treated as data-relative.
    Absolute paths pass through untouched.

    If a data path is missing but names a known source, it is downloaded, so a
    fresh clone says what it is downloading instead of just "file not found".
    Set ``FAIR_SHARES_AUTO_FETCH=0`` to turn that off; the test suite does, so a
    missing test file fails loudly rather than hitting the network. Output paths
    are never downloaded — the pipeline writes those itself.
    """
    candidate = Path(rel)
    if candidate.is_absolute():
        return candidate

    parts = PurePosixPath(str(rel).replace(os.sep, "/")).parts
    if parts and parts[0] == "output":
        return _resolve("output", output_dir).joinpath(*parts[1:])
    if parts and parts[0] == "data":
        resolved = _resolve("data", data_dir).joinpath(*parts[1:])
    else:
        resolved = _resolve("data", data_dir) / candidate

    _maybe_auto_fetch(resolved, str(rel))
    return resolved


def _maybe_auto_fetch(resolved: Path, rel: str) -> None:
    """Hand a missing data path to the fetcher, if it is a registered source."""
    if resolved.exists():
        return
    try:
        from fair_shares.library.data_fetch import ensure_target_present
    except ImportError:  # pragma: no cover - fetch deps are runtime deps
        return
    ensure_target_present(resolved, rel=rel)


def packaged_config(name: str) -> Any:
    """Return a :mod:`importlib.resources` handle on a packaged config file.

    ``name`` is a POSIX-style path relative to ``fair_shares/conf``, e.g.
    ``"data_sources/iamc_data_sources.yaml"``.
    """
    from importlib.resources import files

    resource = files("fair_shares.conf")
    for part in PurePosixPath(name).parts:
        resource = resource / part
    return resource
