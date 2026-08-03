"""Where every input file comes from, and what its licence and citation are.

The list itself is ``fair_shares/conf/data_registry.yaml``, shipped inside the
package so it is available after a plain install. This module reads and checks
that file; ``data_fetch`` is what acts on it.

Two things to know when reading an entry.

**A hash means different things depending on the publisher.** ``sha256`` is a
fixed value for the downloaded file and a mismatch stops the run. But the World
Bank and Our World in Data rewrite their files in place with no version number,
so a fixed value there would flag a newer file rather than a broken one, and
would break every fresh clone within months. Those entries are marked
``unversioned: true`` and carry ``reference_sha256`` instead, which is reported
but not enforced. This is a property of the entry, not a special case in the
fetcher.

**What is downloaded is not always what the pipeline reads.** ``transform`` says
how to get from one to the other: ``copy`` saves the download as-is,
``unzip-member`` pulls one file out of a zip, and ``ar6-split`` divides a
workbook into the two files the pipeline wants. When files are built rather than
saved as downloaded, only the download can carry a fixed hash — rebuilt
spreadsheets and zips are never byte-for-byte identical — so the built files are
checked by their structure when written instead.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fair_shares.library.exceptions import ConfigurationError

REGISTRY_RESOURCE = "data_registry.yaml"

#: Tiers that a bare ``fair-shares fetch-data`` will download.
DEFAULT_TIERS = ("default",)
#: Tiers that ``--all`` adds on top of :data:`DEFAULT_TIERS`.
ALL_TIERS = ("default", "optional")

Tier = Literal["default", "optional", "manual", "bundled"]
Transform = Literal["copy", "unzip-member", "ar6-split"]


class Download(BaseModel):
    """One file to obtain, and what to do with it once obtained."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str | None = None
    transform: Transform = "copy"
    target: str | None = None
    outputs: tuple[str, ...] = ()
    member_pattern: str | None = None
    sha256: str | None = None
    reference_sha256: str | None = None
    upstream_hash: str | None = None
    size_bytes: int | None = None
    unversioned: bool = False
    headers: dict[str, str] = Field(default_factory=dict)

    @property
    def targets(self) -> tuple[str, ...]:
        """Every data-relative path this download produces."""
        return self.outputs if self.transform == "ar6-split" else (self.target or "",)

    @model_validator(mode="after")
    def _check_shape(self) -> Download:
        if self.transform == "ar6-split":
            if not self.outputs:
                raise ValueError("ar6-split downloads must declare `outputs`")
            if self.target is not None:
                raise ValueError("ar6-split downloads use `outputs`, not `target`")
        else:
            if not self.target:
                raise ValueError(f"{self.transform} downloads must declare `target`")
            if self.outputs:
                raise ValueError("`outputs` is only meaningful for ar6-split")

        if self.transform == "unzip-member" and not self.member_pattern:
            raise ValueError("unzip-member downloads must declare `member_pattern`")

        # Enforced on the entry rather than in the fetcher.
        if self.unversioned:
            if self.sha256 is not None:
                raise ValueError(
                    "an unversioned download cannot carry a pinned `sha256`; use "
                    "`reference_sha256` to record the vintage in hand"
                )
            if not self.reference_sha256:
                raise ValueError(
                    "an unversioned download must carry `reference_sha256` so "
                    "drift can be reported against a known vintage"
                )
        elif not self.sha256:
            raise ValueError(
                "a versioned download must carry a pinned `sha256`; set "
                "`unversioned: true` if upstream publishes no stable vintage"
            )

        for value in (self.sha256, self.reference_sha256):
            if value is not None and len(value) != 64:
                raise ValueError(f"expected a 64-character SHA256, got {value!r}")
        return self


class Source(BaseModel):
    """One upstream dataset: its rights, its citation, and its files."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tier: Tier
    version: str
    license: str
    citation: str
    redistributable: bool
    doi: str | None = None
    notes: str | None = None
    manual_instructions: str | None = None
    downloads: tuple[Download, ...] = ()

    @property
    def targets(self) -> tuple[str, ...]:
        """Every data-relative path this source produces."""
        return tuple(t for d in self.downloads for t in d.targets)

    @property
    def total_bytes(self) -> int:
        """Sum of known download sizes; 0 where upstream reports none."""
        return sum(d.size_bytes or 0 for d in self.downloads)

    @model_validator(mode="after")
    def _check_shape(self) -> Source:
        if self.tier == "manual" and not self.manual_instructions:
            raise ValueError(
                "a manual-tier source must carry `manual_instructions`"
            )
        if self.tier == "bundled":
            urls = [d.url for d in self.downloads if d.url]
            if urls:
                raise ValueError("bundled sources ship with the repo and have no URL")
        return self


class Registry(BaseModel):
    """The whole source table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    sources: dict[str, Source]

    def __getitem__(self, name: str) -> Source:
        """Look up a source, naming the alternatives when the key is wrong."""
        try:
            return self.sources[name]
        except KeyError:
            raise ConfigurationError(
                f"Unknown data source {name!r}. Known sources: "
                f"{', '.join(sorted(self.sources))}"
            ) from None

    def __contains__(self, name: str) -> bool:
        """Whether ``name`` is a registered source."""
        return name in self.sources

    def names_for_tiers(self, tiers: tuple[str, ...]) -> list[str]:
        """Source names in the given tiers, alphabetically."""
        return sorted(n for n, s in self.sources.items() if s.tier in tiers)

    def target_index(self) -> dict[str, tuple[str, Download]]:
        """Map each file path to the source and download that produces it.

        Lets automatic downloading start from a missing file and work back to
        what would create it.
        """
        index: dict[str, tuple[str, Download]] = {}
        for name, source in self.sources.items():
            for download in source.downloads:
                for target in download.targets:
                    index[normalise_target(target)] = (name, download)
        return index


def normalise_target(path: str) -> str:
    """Put a path into the one form the registry uses as a key.

    The registry writes paths relative to the data directory
    (``emissions/primap-202503/…``), while the data-source config files write
    the same paths with a ``data/`` in front. Both have to end up as the same
    key, or automatic downloading quietly never happens. A test walks every path
    in the config and checks it against the registry, rather than assuming.
    """
    cleaned = str(path).replace("\\", "/").strip("/")
    if cleaned.startswith("data/"):
        cleaned = cleaned[len("data/") :]
    return cleaned


_cache: Registry | None = None


def load_registry(*, refresh: bool = False) -> Registry:
    """Load and validate the packaged source table.

    Cached after the first call, since it is read on every path resolution that
    misses. Pass ``refresh=True`` in tests that patch the packaged resource.
    """
    global _cache
    if _cache is not None and not refresh:
        return _cache

    import yaml

    from fair_shares.library.paths import packaged_config

    resource = packaged_config(REGISTRY_RESOURCE)
    try:
        raw: Any = yaml.safe_load(resource.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read the packaged data registry ({REGISTRY_RESOURCE}): {exc}"
        ) from exc

    try:
        registry = Registry.model_validate(raw)
    except Exception as exc:
        raise ConfigurationError(f"The data registry is invalid: {exc}") from exc

    _cache = registry
    return registry


def reset_registry_cache() -> None:
    """Drop the cached registry. Tests that patch the table must call this."""
    global _cache
    _cache = None
