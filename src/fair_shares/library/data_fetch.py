"""Download the data files listed in the registry and check they are correct.

``fetch_source`` gets one source. ``verify_sources`` re-checks files already on
disk without downloading. The ``fair-shares fetch-data`` command wraps both.

A wrong checksum stops the run instead of warning. This applies to files already
on disk as well as to new downloads: a damaged file is reported rather than
quietly replaced. Use ``force=True`` to re-download on purpose.

Two exceptions to that rule:

- Some publishers rewrite their files in place with no version number (see
  ``unversioned`` in ``data_registry``). Those cannot be pinned, so a changed
  hash is reported as drift instead of failing, and the hash actually obtained
  goes into ``PROVENANCE.md``. ``--verify`` therefore exits non-zero for a fixed
  hash that does not match, but zero for drift — otherwise it would fail
  permanently the first time one of those publishers refreshed a file. To keep
  that from hiding real damage, a changed
  file is also opened and parsed; if it will not open it is reported as damaged,
  not as an update. That check has a floor: a download cut off exactly at a line
  boundary can still parse and will still be called drift.

- The three AR6 files are built from a downloaded workbook rather than saved as
  downloaded, and rebuilt spreadsheets and zips are never byte-for-byte
  identical, so they have no hash of their own — the fixed hash covers the
  workbook that was downloaded. For those, opening the file is the only check
  there is. Recording the hashes actually produced would close the gap, and is a
  decision for later.

One more thing worth knowing when comparing hashes here: ``.gitattributes`` sets
``* text=auto``, so git rewrites line endings on text files it stores. A text
file committed to this repository therefore cannot match a hash taken from a
publisher who ships Windows line endings, even though the data is identical.
Comparisons allow for that by trying both line-ending forms; which one matched
is recorded.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

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
    MissingOptionalDependencyError,
)

AUTO_FETCH_ENV = "FAIR_SHARES_AUTO_FETCH"

PROVENANCE_FILENAME = "PROVENANCE.md"

_CHUNK = 1 << 20


@dataclass(frozen=True)
class FetchResult:
    """What happened to one target path."""

    source: str
    target: Path
    #: ``fetched`` | ``present`` | ``manual`` | ``drifted``
    status: str
    sha256: str | None = None
    detail: str | None = None


def sha256_of(path: Path) -> str:
    """Return the SHA256 of a file, read in chunks so 72 MB inputs stay cheap."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_like_text(path: Path) -> bool:
    """Guess whether a file is text, by looking for a zero byte near the start.

    Only used to decide whether trying the line-ending comparison below is worth
    the effort. Getting it wrong costs a wasted read, never a wrong answer — the
    hash is still what decides.
    """
    try:
        with path.open("rb") as handle:
            return b"\x00" not in handle.read(8192)
    except OSError:  # pragma: no cover - unreadable files fail later anyway
        return False


def _newline_variant_hashes(path: Path) -> set[str]:
    """Hashes of this file with its line endings written both ways.

    Needed because git rewrites line endings. ``.gitattributes`` sets
    ``* text=auto``, so a text file committed to this repository has Unix line
    endings even when the publisher shipped Windows ones. The recorded hash is
    the publisher's, so the committed copy can never match it byte for byte,
    even though the two files hold exactly the same data.

    Converting the file on disk both ways and hashing each rebuilds the
    publisher's bytes when the only difference is line endings. If anything else
    differs, neither version matches and the file is still reported as wrong.
    """
    raw = path.read_bytes()
    unix = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    windows = unix.replace(b"\n", b"\r\n")
    return {hashlib.sha256(v).hexdigest() for v in (unix, windows)}


def check_pinned_hash(path: Path, expected: str) -> tuple[bool, str, str | None]:
    """Check a file against its recorded hash, allowing for line-ending changes.

    Returns ``(matched, hash_on_disk, how)`` where ``how`` is ``"exact"`` when
    the bytes match outright, ``"newlines"`` when they match once line endings
    are lined up, and ``None`` when the file does not match at all.
    """
    actual = sha256_of(path)
    if actual == expected:
        return True, actual, "exact"
    if _looks_like_text(path) and expected in _newline_variant_hashes(path):
        return True, actual, "newlines"
    return False, actual, None


def parses_cleanly(path: Path, *, min_csv_rows: int = 2) -> str | None:
    """Check a file can actually be opened. Returns a reason if it cannot.

    A hash alone cannot tell a file that the publisher has updated from one that
    downloaded half way, since both simply have the wrong hash. Whether the file
    still opens can tell them apart: a genuine new version parses, a truncated
    one usually does not.

    This is a floor, not a guarantee — a download cut off at a line boundary can
    still parse. It catches the common case.
    """
    suffix = path.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    return "the archive contains a damaged entry"
                if not archive.namelist():
                    return "the archive is empty"
        elif suffix in {".xlsx", ".xlsm"}:
            # An xlsx is a zip; a truncated one fails to open as one.
            with zipfile.ZipFile(path) as archive:
                if "[Content_Types].xml" not in archive.namelist():
                    return "not a readable spreadsheet"
        elif suffix == ".csv":
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                lines = 0
                header = handle.readline()
                if "," not in header and ";" not in header:
                    return "no readable header row"
                for _ in handle:
                    lines += 1
                    if lines >= min_csv_rows:
                        break
                if lines < min_csv_rows:
                    return f"fewer than {min_csv_rows} data rows"
    except (OSError, zipfile.BadZipFile, UnicodeError) as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _replace_atomically(source: Path, target: Path) -> None:
    """Move ``source`` onto ``target`` in one step.

    Writing straight to the final name means a run killed part way through
    leaves a half-written file that later runs treat as complete. Writing beside
    it and then renaming means the final name only ever holds a finished file.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)


def _staging_path(target: Path) -> Path:
    return target.with_name(f".{target.name}.partial")


def _integrity_error(
    *,
    path: Path,
    expected: str,
    actual: str,
    source: str,
    url: str | None,
    extra: str | None = None,
) -> DataIntegrityError:
    where = f"\n  Downloaded from: {url}" if url else ""
    note = f"\n  Note:     {extra}" if extra else ""
    return DataIntegrityError(
        f"Checksum mismatch for {path}\n"
        f"  Source:   {source}\n"
        f"  Expected: {expected}\n"
        f"  Actual:   {actual}{note}{where}\n\n"
        "The bytes on disk are not the bytes this analysis was pinned to. Either "
        "the file is damaged or truncated, or upstream re-released under the same "
        "URL and the registry pin is stale. Nothing has been overwritten and "
        "nothing will be retried automatically.\n\n"
        "If the file is damaged, delete it and re-run the fetch (or pass --force). "
        "If upstream re-released, the registry entry needs updating deliberately — "
        "a new vintage changes results."
    )


def _require_pooch() -> object:
    try:
        import pooch
    except ImportError as exc:  # pragma: no cover - pooch is a runtime dep
        raise MissingOptionalDependencyError("fetch_source", "pooch") from exc
    return pooch


def _download_to(url: str, dest: Path, headers: dict[str, str]) -> Path:
    """Download ``url`` to ``dest``, showing a progress bar.

    pooch writes via a temporary file, so an interrupted download does not leave
    a half-finished file that looks complete. It cannot resume a part-finished
    download — an interrupted transfer starts again from the beginning.
    """
    pooch = _require_pooch()
    downloader = pooch.HTTPDownloader(  # type: ignore[attr-defined]
        progressbar=True,
        headers=headers or None,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    downloader(url, str(dest), None)
    return dest


def _apply_copy(downloaded: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = _staging_path(target)
    shutil.copyfile(downloaded, staged)
    _replace_atomically(staged, target)


def _apply_unzip_member(downloaded: Path, target: Path, pattern: str) -> None:
    """Extract the single zip member matching ``pattern`` to ``target``."""
    with zipfile.ZipFile(downloaded) as archive:
        matches = [n for n in archive.namelist() if fnmatch.fnmatch(n, pattern)]
        if not matches:
            raise DataIntegrityError(
                f"No member matching {pattern!r} in the archive downloaded for "
                f"{target.name}. The archive contains: {', '.join(archive.namelist())}. "
                "Upstream has probably changed its export layout; the registry's "
                "member_pattern needs updating."
            )
        if len(matches) > 1:
            raise DataIntegrityError(
                f"{len(matches)} members match {pattern!r} in the archive for "
                f"{target.name}: {', '.join(matches)}. The pattern must select "
                "exactly one file."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        staged = _staging_path(target)
        with archive.open(matches[0]) as src, staged.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        _replace_atomically(staged, target)


#: Which sheet of the downloaded AR6 workbook goes into which file. The pipeline
#: reads the first sheet of each file, so each gets exactly one sheet.
_AR6_SHEETS = {
    "data": "ar6_gidden.xlsx",
    "meta": "metadata_ar6_gidden.xlsx",
}
_AR6_ARCHIVE = "ar6_gidden.zip"


def _apply_ar6_split(downloaded: Path, outputs: Sequence[Path]) -> None:
    """Split the downloaded AR6 workbook into the files the pipeline reads.

    Zenodo record 10158920 publishes one workbook with two sheets, ``data`` and
    ``meta``. The pipeline instead reads a zip holding ``ar6_gidden.xlsx`` and
    ``metadata_ar6_gidden.xlsx``, so this writes those two files and zips them.

    Checked on 2026-08-03 that the copies in the repository are exactly these two
    sheets saved separately: same size, same columns, same missing values, same
    text. 137 numbers out of 5.8 million differ in their last decimal place,
    which is what saving a spreadsheet again does — not different data.
    """
    import pandas as pd

    by_name = {path.name: path for path in outputs}
    required = set(_AR6_SHEETS.values()) | {_AR6_ARCHIVE}
    missing = required - set(by_name)
    if missing:
        raise DataIntegrityError(
            f"The AR6 registry entry must declare outputs named {sorted(required)}; "
            f"got {sorted(by_name)} (missing {sorted(missing)})."
        )

    workbook = pd.ExcelFile(downloaded, engine="calamine")
    expected_sheets = set(_AR6_SHEETS)
    if not expected_sheets <= set(workbook.sheet_names):
        raise DataIntegrityError(
            f"The downloaded AR6 workbook has sheets {workbook.sheet_names}, but "
            f"the split expects {sorted(expected_sheets)}. Upstream has changed "
            "its layout; the transform needs revisiting."
        )

    # Everything is written beside its final name and renamed at the end, so a
    # run killed part way through cannot leave a half-written spreadsheet or zip
    # that the next run mistakes for a finished one.
    staged = {name: _staging_path(path) for name, path in by_name.items()}

    for sheet, filename in _AR6_SHEETS.items():
        frame = pd.read_excel(workbook, sheet_name=sheet)
        if frame.empty:
            raise DataIntegrityError(
                f"Sheet {sheet!r} of the downloaded AR6 workbook is empty."
            )
        out = staged[filename]
        out.parent.mkdir(parents=True, exist_ok=True)
        # Sheet name kept so each file says what it holds. The pipeline reads
        # the first sheet, and each file has only one.
        frame.to_excel(out, sheet_name=sheet, index=False)

    archive = staged[_AR6_ARCHIVE]
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # metadata first, matching the archive that shipped in the repository
        for filename in (_AR6_SHEETS["meta"], _AR6_SHEETS["data"]):
            zf.write(staged[filename], arcname=filename)

    for name, path in by_name.items():
        _replace_atomically(staged[name], path)


def _resolve_targets(download: Download, data_dir: Path) -> list[Path]:
    return [data_dir / Path(t) for t in download.targets]


def classify_target(download: Download, source_name: str, target: Path) -> FetchResult:
    """Decide whether a file on disk is fine, updated, or damaged.

    Status is one of:

    ``present``  the file is what it should be.
    ``drifted``  the hash differs but the file still opens, so the publisher has
                 most likely released a new version. Only possible for sources
                 marked ``unversioned``.
    ``corrupt``  the hash is wrong and the file will not open, or a fixed hash
                 does not match.

    Both callers go through here so the download path and ``--verify`` can never
    disagree about the same file.
    """
    if download.sha256 and download.transform == "copy":
        matched, digest, how = check_pinned_hash(target, download.sha256)
        if matched:
            detail = None if how == "exact" else "matches once line endings agree"
            return FetchResult(source_name, target, "present", digest, detail)
        return FetchResult(
            source_name, target, "corrupt", digest, f"expected {download.sha256}"
        )

    if download.unversioned and download.reference_sha256:
        matched, digest, _ = check_pinned_hash(target, download.reference_sha256)
        if matched:
            return FetchResult(source_name, target, "present", digest)
        # A different hash on its own cannot say whether the publisher updated
        # the file or the download was cut short. Whether it still opens can.
        broken = parses_cleanly(target)
        if broken:
            return FetchResult(
                source_name,
                target,
                "corrupt",
                digest,
                f"does not match the recorded version and will not open: {broken}",
            )
        return FetchResult(
            source_name,
            target,
            "drifted",
            digest,
            "upstream has re-generated this file since the version the analysis "
            f"was built on ({download.reference_sha256})",
        )

    # Files built from a download rather than saved as downloaded: no hash of
    # their own exists, so all we can check is that they open.
    digest = sha256_of(target)
    broken = parses_cleanly(target)
    if broken:
        return FetchResult(
            source_name, target, "corrupt", digest, f"will not open: {broken}"
        )
    return FetchResult(source_name, target, "present", digest)


def has_recorded_hash(download: Download) -> bool:
    """Whether the file on disk has a hash of its own to be checked against."""
    if download.sha256 and download.transform == "copy":
        return True
    return bool(download.unversioned and download.reference_sha256)


def _check_existing(
    download: Download, source_name: str, targets: Sequence[Path]
) -> list[FetchResult] | None:
    """Return results if every target is already there and usable.

    ``None`` means "go and download".

    A damaged file is handled one of two ways, depending on whether there is a
    hash recorded for it:

    - **A hash is recorded.** Raise. A mismatch might mean the file is damaged,
      but it might also mean the publisher released something new, and quietly
      overwriting would hide either. The message says to use ``--force``.
    - **No hash is recorded** (files built from a download). Rebuild them. There
      is no recorded hash to protect and no ambiguity to preserve: the file is
      simply unusable, and it can be rebuilt from a download that *is* pinned.
    """
    if not all(t.exists() for t in targets):
        return None

    results = [classify_target(download, source_name, t) for t in targets]
    damaged = [r for r in results if r.status == "corrupt"]
    if not damaged:
        return results

    if has_recorded_hash(download):
        first = damaged[0]
        raise _integrity_error(
            path=first.target,
            expected=download.sha256 or download.reference_sha256 or "(no hash)",
            actual=first.sha256 or "(unreadable)",
            source=source_name,
            url=download.url,
            extra=first.detail,
        )

    for result in damaged:
        print(
            f"[fair-shares] {result.target.name} is damaged ({result.detail}); "
            "rebuilding it."
        )
    return None


def _fetch_download(
    download: Download,
    source_name: str,
    data_dir: Path,
    *,
    force: bool,
) -> list[FetchResult]:
    targets = _resolve_targets(download, data_dir)

    if not force:
        existing = _check_existing(download, source_name, targets)
        if existing is not None:
            return existing

    if not download.url:
        raise ManualFetchRequired(
            f"{source_name} has no download URL and must be provided by hand at "
            f"{targets[0]}."
        )

    with TemporaryDirectory(prefix="fair-shares-fetch-") as tmp:
        staged = Path(tmp) / "download"
        _download_to(download.url, staged, download.headers)
        actual = sha256_of(staged)

        if download.sha256 and actual != download.sha256:
            raise _integrity_error(
                path=Path(download.targets[0]),
                expected=download.sha256,
                actual=actual,
                source=source_name,
                url=download.url,
            )

        if download.transform == "copy":
            _apply_copy(staged, targets[0])
        elif download.transform == "unzip-member":
            assert download.member_pattern is not None  # schema-enforced
            _apply_unzip_member(staged, targets[0], download.member_pattern)
        else:
            _apply_ar6_split(staged, targets)

    results: list[FetchResult] = []
    for target in targets:
        checked = classify_target(download, source_name, target)
        if checked.status == "corrupt":
            raise _integrity_error(
                path=target,
                expected=download.sha256 or download.reference_sha256 or "(no hash)",
                actual=checked.sha256 or "(unreadable)",
                source=source_name,
                url=download.url,
                extra=checked.detail,
            )
        status = "fetched" if checked.status == "present" else checked.status
        results.append(
            FetchResult(source_name, target, status, checked.sha256, checked.detail)
        )
    return results


def fetch_source(
    name: str,
    *,
    data_dir: Path | str | None = None,
    force: bool = False,
    registry: Registry | None = None,
) -> list[FetchResult]:
    """Fetch every file belonging to one registered source.

    Parameters
    ----------
    name
        Registry key, e.g. ``"primap-202503"``.
    data_dir
        Where to write. Defaults to
        :func:`fair_shares.library.paths.data_dir_for_write`.
        **Whatever is used is then set for the rest of the process**, so later
        reads look in the same place as the download just went. Call
        ``paths.configure(data_dir=None)`` or ``paths.reset_path_cache()`` to
        undo that.
    force
        Re-download even when the targets are present and match.

    Raises
    ------
    DataIntegrityError
        A pinned checksum did not match, on disk or after download.
    ManualFetchRequired
        The source is behind a click-through gate; the message carries the
        landing URL, the expected filename and the destination path.
    """
    from fair_shares.library import paths

    registry = registry or load_registry()
    source = registry[name]
    resolved = paths.data_dir_for_write(data_dir)
    # Deep resolver calls (config validation, source lookup) read process-wide
    # state, so an explicit directory only reaches them through configure().
    paths.configure(data_dir=resolved)

    if source.tier == "manual":
        raise ManualFetchRequired(_manual_message(name, source, resolved))

    if source.tier == "bundled":
        return [
            FetchResult(
                name,
                resolved / Path(target),
                "present" if (resolved / Path(target)).exists() else "manual",
                None,
                "ships with the repository; never fetched",
            )
            for target in source.targets
        ]

    results: list[FetchResult] = []
    for download in source.downloads:
        results.extend(_fetch_download(download, name, resolved, force=force))
    return results


def _manual_message(name: str, source: Source, data_dir: Path) -> str:
    instructions = (source.manual_instructions or "").replace(
        "<data_dir>", str(data_dir)
    )
    return (
        f"{name} cannot be downloaded automatically.\n\n"
        f"{instructions}\n\n"
        f"Licence: {source.license}\n"
        f"Cite: {source.citation}"
    )


def verify_sources(
    *,
    names: Iterable[str] | None = None,
    data_dir: Path | str | None = None,
    registry: Registry | None = None,
) -> tuple[list[FetchResult], list[FetchResult]]:
    """Re-check every file already on disk, without downloading anything.

    Returns ``(failures, drift)``. Failures are files that are damaged or do not
    match a fixed hash, and are what a caller should exit non-zero on. Drift is a
    file from an unversioned publisher that has changed but still opens, which is
    worth reporting but expected over time. Missing files are neither — they
    simply have not been downloaded yet.

    Files built from a download have no hash of their own, so for those this only
    checks that they open. See the module docstring.
    """
    from fair_shares.library import paths

    registry = registry or load_registry()
    resolved = paths.data_dir_for_write(data_dir)
    selected = sorted(names) if names is not None else sorted(registry.sources)

    failures: list[FetchResult] = []
    drift: list[FetchResult] = []
    for name in selected:
        source = registry[name]
        for download in source.downloads:
            for target in _resolve_targets(download, resolved):
                if not target.exists():
                    continue
                result = classify_target(download, name, target)
                if result.status == "corrupt":
                    failures.append(result)
                elif result.status == "drifted":
                    drift.append(result)
    return failures, drift


def auto_fetch_enabled() -> bool:
    """Whether a missing registered file may be fetched on demand."""
    return os.environ.get(AUTO_FETCH_ENV, "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def ensure_target_present(path: Path, *, rel: str) -> None:
    """Download ``rel`` if it is a known source, is missing, and fetching is on.

    Called from ``resolve_source_path``. Does nothing if the file is already
    there or is not in the registry, so it stays cheap on the many path lookups
    the pipeline makes.
    """
    if path.exists() or not auto_fetch_enabled():
        return

    try:
        registry = load_registry()
    except Exception:  # pragma: no cover - a broken registry must not break reads
        return

    key = normalise_target(rel)
    entry = registry.target_index().get(key)
    if entry is None:
        return
    name, _download = entry
    source = registry[name]

    # Work the data directory back out of the path we were given, by removing
    # the part of it that came from the registry. This keeps the download in the
    # same directory the caller was reading from, even when that came from an
    # explicit argument rather than the usual resolution.
    depth = len(PurePosixPath(key).parts)
    target_dir = path
    for _ in range(depth):
        target_dir = target_dir.parent

    if source.tier == "manual":
        # The data directory itself, not the file's own folder: the instructions
        # already include the sub-path, so passing the file's folder would tell
        # the user to save it at <data_dir>/bunkers/bunkers/gcb-2024/.
        raise ManualFetchRequired(_manual_message(name, source, target_dir))
    if source.tier == "bundled":
        return

    print(
        f"[fair-shares] {path.name} is missing; downloading {name} "
        f"({source.version}) — {source.license}."
    )
    fetch_source(name, data_dir=target_dir, registry=registry)


def write_provenance(
    results: Sequence[FetchResult],
    data_dir: Path,
    *,
    registry: Registry | None = None,
) -> Path:
    """Write ``PROVENANCE.md``: what is in the data directory and who owns it.

    Written next to the data rather than in a README, and built from the
    registry, so the licence and citation for each file stay with the file.

    It lists everything currently in the directory, not only what this command
    just fetched. People usually fetch in several goes, and rewriting the file
    from one command's results would wipe the record of the earlier ones,
    leaving files on disk with no licence recorded anywhere.
    """
    registry = registry or load_registry()
    by_target = {r.target: r for r in results}

    # Everything the registry knows about that is actually on disk. Status is
    # worked out again here rather than carried over, so a file that changed
    # during an earlier command is still reported by a later one.
    for name in sorted(registry.sources):
        for download in registry[name].downloads:
            for target in _resolve_targets(download, data_dir):
                if not target.exists() or target in by_target:
                    continue
                by_target[target] = classify_target(download, name, target)

    results = sorted(by_target.values(), key=lambda r: (r.source, str(r.target)))
    fetched = sorted({r.source for r in results})
    hashes = by_target

    lines = [
        "# Data provenance",
        "",
        f"Generated by `fair-shares fetch-data` on "
        f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}.",
        "",
        "This file is generated. It records the upstream source, version, licence "
        "and citation of every input in this directory, and the SHA256 actually "
        "obtained for each file.",
        "",
        "Attribution obligations travel with the data: several sources below are "
        "CC BY and require attribution in anything derived from them. Sources "
        "marked not redistributable must not be republished — cite and link them "
        "instead.",
        "",
    ]

    for name in fetched:
        source = registry[name]
        lines += [
            f"## {name}",
            "",
            f"- **Version:** {source.version}",
            f"- **Licence:** {source.license}",
            f"- **Redistributable:** {'yes' if source.redistributable else 'no'}",
        ]
        if source.doi:
            lines.append(f"- **DOI:** https://doi.org/{source.doi}")
        lines += [
            f"- **Cite:** {source.citation}",
            "",
            "| File | SHA256 | Status |",
            "| --- | --- | --- |",
        ]
        for result in [r for r in results if r.source == name]:
            digest = hashes[result.target].sha256 or "—"
            note = result.status
            if result.detail:
                note = f"{result.status} ({result.detail})"
            try:
                shown = result.target.relative_to(data_dir)
            except ValueError:  # pragma: no cover - defensive
                shown = result.target
            lines.append(f"| `{shown}` | `{digest}` | {note} |")
        lines.append("")

    drifted = [r for r in results if r.status == "drifted"]
    if drifted:
        lines += [
            "## Vintage drift",
            "",
            "These files come from sources that upstream regenerates in place "
            "without a version identifier, and the copies obtained differ from "
            "the vintage the published analysis was built on. Results computed "
            "from them will not reproduce the published numbers exactly.",
            "",
        ]
        lines += [f"- `{r.target.name}` — {r.detail}" for r in drifted]
        lines.append("")

    data_dir.mkdir(parents=True, exist_ok=True)
    out = data_dir / PROVENANCE_FILENAME
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
