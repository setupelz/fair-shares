"""The ``fair-shares`` command line entry point.

Currently one subcommand, ``fetch-data``, which is the supported way to obtain
the pipeline's inputs::

    fair-shares fetch-data                 # everything a standard run needs
    fair-shares fetch-data --all           # plus the large optional sources
    fair-shares fetch-data --source wiid   # one source
    fair-shares fetch-data --list          # what exists, and under what licence
    fair-shares fetch-data --verify        # re-hash what is present, fetch nothing

If you script against this, the exit codes matter: ``--verify`` exits non-zero
when a file fails its fixed checksum, and zero when a file from an unversioned
publisher has simply been updated. ``data_fetch`` explains why.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from fair_shares.library.citations import citations
from fair_shares.library.data_fetch import (
    fetch_source,
    verify_sources,
    write_provenance,
)
from fair_shares.library.data_registry import ALL_TIERS, DEFAULT_TIERS, load_registry
from fair_shares.library.exceptions import (
    ConfigurationError,
    DataIntegrityError,
    ManualFetchRequired,
)


def _human_bytes(value: int) -> str:
    if not value:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover - unreachable


def _cmd_list(data_dir: str | None) -> int:
    from fair_shares.library import paths

    registry = load_registry()
    resolved = paths.data_dir_for_write(data_dir)
    print(f"Data directory: {resolved}\n")

    header = f"{'SOURCE':<30} {'TIER':<9} {'SIZE':>9}  {'FILES':>7}  LICENCE"
    print(header)
    print("-" * len(header))
    for name in sorted(registry.sources):
        source = registry.sources[name]
        targets = source.targets
        present = sum(1 for t in targets if (resolved / t).exists())
        print(
            f"{name:<30} {source.tier:<9} "
            f"{_human_bytes(source.total_bytes):>9}  "
            f"{present}/{len(targets):<5}  {source.license}"
        )
    print("\nVersions and citations:")
    for name in sorted(registry.sources):
        source = registry.sources[name]
        print(f"\n  {name} — {source.version}")
        if source.doi:
            print(f"    DOI:  https://doi.org/{source.doi}")
        print(f"    Cite: {' '.join(source.citation.split())}")
    return 0


def _cmd_verify(data_dir: str | None, names: list[str] | None) -> int:
    failures, drift = verify_sources(names=names, data_dir=data_dir)

    for result in drift:
        print(
            f"DRIFT   {result.target}\n"
            f"        got      {result.sha256}\n"
            f"        {result.detail}\n"
            "        This publisher updates the file in place with no version "
            "number, so a changed hash is\n"
            "        expected over time. The file still opens, which is why this "
            "is not reported as damage —\n"
            "        but that check cannot rule out a download cut off at a line "
            "boundary. If you did not\n"
            "        expect a new version, re-download with --force and compare.\n"
            "        Either way, results will not reproduce the published numbers "
            "exactly."
        )
    for result in failures:
        print(
            f"CORRUPT {result.target}\n"
            f"        got      {result.sha256}\n"
            f"        {result.detail}",
            file=sys.stderr,
        )

    if failures:
        print(
            f"\n{len(failures)} file(s) do not match their pinned checksum.",
            file=sys.stderr,
        )
        return 1
    if drift:
        print(
            f"\nAll pinned checksums match. {len(drift)} unversioned file(s) drifted."
        )
    else:
        print("All present files match their recorded checksums.")
    return 0


def _cmd_fetch(
    data_dir: str | None,
    source: str | None,
    all_tiers: bool,
    force: bool,
) -> int:
    from fair_shares.library import paths

    registry = load_registry()
    resolved = paths.data_dir_for_write(data_dir)

    if source is not None:
        planned = [source] if source in registry else []
        if not planned:
            raise ConfigurationError(
                f"Unknown data source {source!r}. Known sources: "
                f"{', '.join(sorted(registry.sources))}"
            )
    else:
        planned = registry.names_for_tiers(ALL_TIERS if all_tiers else DEFAULT_TIERS)

    total = sum(registry[n].total_bytes for n in planned)
    print(f"Fetching {len(planned)} source(s) into {resolved}")
    print(f"Approximate download size: {_human_bytes(total)}\n")

    results = []
    for name in planned:
        try:
            results.extend(
                fetch_source(name, data_dir=resolved, force=force, registry=registry)
            )
        except ManualFetchRequired as exc:
            # Only reachable for an explicit --source: manual sources are in no
            # tier, so a tier fetch never plans one.
            print(str(exc))
            return 2

    for result in results:
        mark = {
            "fetched": "fetched ",
            "present": "present ",
            "drifted": "DRIFTED ",
            "manual": "MISSING ",
        }.get(result.status, result.status)
        try:
            shown = result.target.relative_to(resolved)
        except ValueError:  # pragma: no cover - defensive
            shown = result.target
        print(f"  {mark} {shown}")
        if result.detail and result.status != "present":
            print(f"           {result.detail}")

    if results:
        provenance = write_provenance(results, resolved, registry=registry)
        print(f"\nWrote {provenance}")

    # Manual sources are in no tier, so a plain fetch would never mention them
    # and you would only find out when a run failed halfway through.
    manual = [
        n
        for n in sorted(registry.sources)
        if registry[n].tier == "manual"
        and not all((resolved / t).exists() for t in registry[n].targets)
    ]
    if manual and source is None:
        print(
            "\nNot fetched — these need a manual download through a licence gate.\n"
            "Run `fair-shares fetch-data --source <name>` for step-by-step "
            "instructions:"
        )
        for name in manual:
            print(f"  {name}")
    return 0


#: What a standard country-level run uses, matching the configured defaults.
DEFAULT_ACTIVE_SOURCES = {
    "target": "rcbs",
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "wdi-2025",
    "lulucf": "melo-2026",
}


def _cmd_cite(
    sources: str | None, as_bibtex: bool, emission_category: str | None
) -> int:
    if sources:
        # "key=value,key=value", so a user can describe their own run.
        active = dict(DEFAULT_ACTIVE_SOURCES)
        for pair in sources.split(","):
            if "=" not in pair:
                raise ConfigurationError(
                    f"--sources expects key=value pairs separated by commas; got {pair!r}"
                )
            key, value = pair.split("=", 1)
            active[key.strip()] = value.strip()
    else:
        active = dict(DEFAULT_ACTIVE_SOURCES)

    run = citations(active, emission_category=emission_category)
    print(run.bibtex() if as_bibtex else run.text())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the ``fair-shares`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="fair-shares",
        description="Utilities for the fair-shares allocation pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser(
        "fetch-data",
        help="Download the pipeline's input data.",
        description=(
            "Download the pipeline's input data from pinned URLs, verifying "
            "checksums. A mismatch is a hard error."
        ),
    )
    fetch.add_argument(
        "--data-dir",
        default=None,
        help=(
            "Where to write. Defaults to the checkout's data/ when run inside a "
            "clone, otherwise the platformdirs user data location."
        ),
    )
    fetch.add_argument("--source", default=None, help="Fetch one source by name.")
    fetch.add_argument(
        "--all",
        action="store_true",
        dest="all_tiers",
        help="Also fetch the large optional sources.",
    )
    fetch.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when targets are present and match.",
    )
    fetch.add_argument(
        "--list",
        action="store_true",
        help="List sources with version, size, licence and citation.",
    )
    fetch.add_argument(
        "--verify",
        action="store_true",
        help="Re-hash present files without downloading.",
    )

    cite = subparsers.add_parser(
        "cite",
        help="Print what to cite for a run.",
        description=(
            "Print the software citation and the citation, DOI and licence of "
            "every data source a run uses."
        ),
    )
    cite.add_argument(
        "--sources",
        default=None,
        help=(
            "Override the default sources, as comma-separated key=value pairs, "
            "e.g. --sources gini=wdi-2025,target=pathway"
        ),
    )
    cite.add_argument(
        "--emission-category",
        default=None,
        help=(
            "Emission category of the run. Given, the source list is exact; "
            "without it the scenario ensemble is included in case the run needs it."
        ),
    )
    cite.add_argument(
        "--bibtex", action="store_true", help="Print BibTeX entries instead of text."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code."""
    args = build_parser().parse_args(argv)

    try:
        if args.command == "cite":
            return _cmd_cite(args.sources, args.bibtex, args.emission_category)
        if args.list:
            return _cmd_list(args.data_dir)
        if args.verify:
            return _cmd_verify(args.data_dir, [args.source] if args.source else None)
        return _cmd_fetch(args.data_dir, args.source, args.all_tiers, args.force)
    except DataIntegrityError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except ManualFetchRequired as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 2
    except ConfigurationError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
