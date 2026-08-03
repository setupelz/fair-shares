"""Work out what a run needs to cite, and format it.

Every allocation uses several third-party datasets, most of them requiring
attribution. Which ones depends on the run: a budget run subtracts international
bunker emissions, a pathway run uses the AR6 scenario ensemble, and the Gini
source is whichever the user chose. Rather than leave people to work that out,
:func:`citations` derives the list from the run's own settings.

Text output is the useful one. BibTeX entries put the whole formatted citation
in a ``note`` field, because the registry stores citations as finished text
rather than separate author and title fields, and splitting them up here would
mean guessing where one ends and the next begins. Anyone wanting structured
entries can import them from the DOI.

Sources with no DOI (World Bank, OWID, UN WPP) are credited by name only. That
is correct, not an omission — no identifier exists, and inventing one would put
a dead link in someone's reference list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fair_shares.library.data_registry import Registry, Source, load_registry
from fair_shares.library.exceptions import ConfigurationError

#: Keys of ``active_sources`` whose value is a registry source name.
DATA_SOURCE_KEYS = ("emissions", "gdp", "population", "gini", "lulucf")

#: Used by every run, but named in no ``active_sources`` key.
ALWAYS_USED = ("regions",)

#: Targets that subtract international bunker emissions from the budget, and so
#: use the Global Carbon Budget workbook. Confirmed against the target
#: definitions in conf/data_sources/data_sources_unified.yaml.
BUNKER_TARGETS = ("rcbs", "rcb-pathways")

#: Registry entry for the scenario ensemble. `active_sources` names it "ar6".
SCENARIO_SOURCES = {"ar6": "ipcc_ar6_gidden"}

#: `active_sources` values that name something other than a data source, so are
#: not expected to appear in the registry.
NOT_DATA_SOURCES = frozenset({"pathway", "rcbs", "rcb-pathways"})

_YEAR = re.compile(r"\((\d{4})\)")


@dataclass(frozen=True)
class RunCitations:
    """The citations for one run."""

    software: dict[str, Any]
    sources: tuple[tuple[str, Source], ...]

    @property
    def special_terms(self) -> list[tuple[str, str]]:
        """Sources whose terms ask for more than plain attribution."""
        notes = []
        for name, source in self.sources:
            note = SPECIAL_TERMS.get(name)
            if note:
                notes.append((name, note))
        return notes

    def text(self) -> str:
        """Return a plain-text block listing everything to cite."""
        return _format_text(self)

    def bibtex(self) -> str:
        """Return the same list as BibTeX entries."""
        return _format_bibtex(self)


#: Terms that go beyond "cite this". Taken from the upstream providers' own
#: statements, recorded in the registry entries for these sources.
SPECIAL_TERMS = {
    "gcb-2024": (
        "The Global Carbon Project asks that the original data sources be cited "
        "alongside this dataset, and notes that where the data are essential to "
        "a study, co-authorship may need to be considered. That is a request "
        "from the providers, not a licence condition."
    ),
    "cmip7-historical-2025.12.07": (
        "This dataset combines several others (CEDS, GFED/BB4CMIP7, the Global "
        "Carbon Budget, and published inversions for HFCs and ozone-depleting "
        "substances). Cite those component datasets as well when reporting "
        "values derived from it. Its ShareAlike licence also applies to "
        "anything you redistribute that is derived from it."
    ),
    "unu-wider-2025": (
        "WIID is licensed for non-commercial use with ShareAlike terms. Check "
        "them before redistributing anything derived from it, including a table "
        "of Gini values."
    ),
    "un-owid-2025": (
        "Our World in Data does not re-license the underlying UN figures. If "
        "you republish population data, check the UN's own terms of use."
    ),
}


def resolve_source_names(
    active_sources: dict[str, str],
    *,
    emission_category: str | None = None,
    registry: Registry | None = None,
) -> list[str]:
    """Work out which registry sources a run actually uses.

    Raises :class:`ConfigurationError` on a source name it cannot place. A
    citation list that quietly leaves something out is worse than one that
    refuses to build, because it tells the user there is nothing to attribute.

    ``emission_category`` makes the answer exact. A budget run over a composite
    category such as ``all-ghg`` splits into a CO2 part taken from budgets and a
    non-CO2 part taken from the scenario ensemble, so it uses the scenarios even
    though its target is a budget. Without the category this cannot be decided,
    and the scenario source is included, which may over-credit.
    """
    registry = registry or load_registry()
    names: list[str] = []

    for key in DATA_SOURCE_KEYS:
        value = active_sources.get(key)
        if not value:
            continue
        if value not in registry:
            raise ConfigurationError(
                f"active_sources[{key!r}] is {value!r}, which is not a known data "
                f"source. Known sources: {', '.join(sorted(registry.sources))}. "
                "Add it to the data registry so its licence and citation can be "
                "recorded."
            )
        names.append(value)

    names.extend(ALWAYS_USED)

    target = active_sources.get("target")
    if target in BUNKER_TARGETS:
        names += ["rcbs", "gcb-2024"]

    if _uses_scenarios(target, emission_category):
        scenario = active_sources.get("scenario", "ar6")
        resolved = SCENARIO_SOURCES.get(scenario, scenario)
        if resolved not in registry:
            raise ConfigurationError(
                f"scenario source {scenario!r} is not in the data registry."
            )
        names.append(resolved)

    for key, value in active_sources.items():
        if key in DATA_SOURCE_KEYS or key in {"target", "scenario"}:
            continue
        if isinstance(value, str) and value in registry and value not in names:
            names.append(value)

    unknown = [
        v
        for k, v in active_sources.items()
        if k not in DATA_SOURCE_KEYS
        and isinstance(v, str)
        and v not in registry
        and v not in NOT_DATA_SOURCES
        and k not in {"scenario", "rcb_generator"}
    ]
    if unknown:
        raise ConfigurationError(
            f"active_sources names {unknown}, which are neither registry sources "
            "nor recognised non-data settings. Citations cannot be built without "
            "knowing what these are."
        )

    seen: set[str] = set()
    return [n for n in names if not (n in seen or seen.add(n))]


#: How the run-context dicts spell the same things ``active_sources`` does.
CONTEXT_KEY_MAP = {
    "emissions-source": "emissions",
    "gdp-source": "gdp",
    "population-source": "population",
    "gini-source": "gini",
    "lulucf-source": "lulucf",
    "target-source": "target",
}

#: Placeholders meaning "no source", written by callers where one is optional.
_ABSENT = frozenset({"", "none", "None", None})


def active_sources_from_context(data_context: dict[str, Any]) -> dict[str, str]:
    """Convert a run-context dict into the ``active_sources`` form.

    The persisting code paths describe a run in two different shapes — hyphenated
    keys in one, plain keys in the other. Both come through here so the two
    ``CITATIONS.md`` files cannot end up disagreeing about the same run.
    """
    return {
        short: value
        for key, short in CONTEXT_KEY_MAP.items()
        if (value := data_context.get(key)) not in _ABSENT
    }


def _uses_scenarios(target: str | None, emission_category: str | None) -> bool:
    """Whether the run draws on the scenario ensemble."""
    if target is None:
        return True
    if target not in BUNKER_TARGETS:
        return True  # pathway targets come straight from the scenarios
    if emission_category is None:
        return True  # cannot tell; over-credit rather than miss a source

    from fair_shares.library.utils.data.setup import _enumerate_required_files

    required = _enumerate_required_files(target, emission_category)
    return any(key.startswith("world_scenarios") for key in required)


def package_citation() -> dict[str, Any]:
    """Read ``CITATION.cff`` and return its fields.

    An installed copy gets the file from inside the package, where the build
    puts it. Running from a checkout there is no copy inside the package — the
    file lives at the repository root, and is deliberately not duplicated, since
    two copies of a citation drift apart. So the root is the fallback.
    """
    import yaml

    from fair_shares.library.paths import find_repo_root, packaged_config

    try:
        raw = packaged_config("CITATION.cff").read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        repo_root = find_repo_root()
        candidate = repo_root / "CITATION.cff" if repo_root else None
        if candidate is None or not candidate.is_file():
            raise ConfigurationError(
                "CITATION.cff could not be found, so the software citation "
                "cannot be built. It should be inside the installed package; if "
                "you are working from a checkout it should be at the repository "
                "root."
            ) from None
        raw = candidate.read_text(encoding="utf-8")
    return yaml.safe_load(raw)


def citations(
    active_sources: dict[str, str],
    *,
    emission_category: str | None = None,
    registry: Registry | None = None,
) -> RunCitations:
    """Return everything a run should cite: the software and its data sources."""
    registry = registry or load_registry()
    names = resolve_source_names(
        active_sources, emission_category=emission_category, registry=registry
    )
    return RunCitations(
        software=package_citation(),
        sources=tuple((name, registry[name]) for name in names),
    )


def _authors(cff: dict[str, Any]) -> str:
    parts = []
    for author in cff.get("authors", []):
        family = author.get("family-names", "").strip()
        given = author.get("given-names", "").strip()
        initials = " ".join(f"{p[0]}." for p in given.split() if p)
        parts.append(f"{family}, {initials}".strip(", "))
    return "; ".join(parts)


def _software_line(cff: dict[str, Any]) -> str:
    year = str(cff.get("date-released", ""))[:4]
    return (
        f"{_authors(cff)} ({year}). {cff.get('title', 'fair-shares')}, "
        f"version {cff.get('version', '')}. {cff.get('url', '')}"
    )


def _format_text(run: RunCitations) -> str:
    lines = [
        "# How to cite this analysis",
        "",
        "## Software",
        "",
        _software_line(run.software),
        f"Licence: {run.software.get('license', '')}",
        "",
        "## Data sources used by this run",
        "",
        "Most of these require attribution. Cite them alongside the software in "
        "anything you publish from these results.",
        "",
    ]
    for name, source in run.sources:
        lines.append(f"### {name}")
        lines.append("")
        lines.append(" ".join(source.citation.split()))
        lines.append("")
        lines.append(f"- Version: {source.version}")
        if source.doi:
            lines.append(f"- DOI: https://doi.org/{source.doi}")
        else:
            lines.append("- DOI: none issued; cite by name as written above")
        lines.append(f"- Licence: {source.license}")
        lines.append("")

    if run.special_terms:
        lines += ["## Terms needing more than attribution", ""]
        for name, note in run.special_terms:
            lines.append(f"**{name}** — {note}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _bibtex_key(name: str) -> str:
    """Build a stable, unique BibTeX key.

    Derived from the registry name rather than author and year, which collide:
    two of these records share a lead author, and several share a year.
    """
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
    return f"fairshares-{cleaned}"


def _escape(value: str) -> str:
    return " ".join(str(value).split()).replace("{", "").replace("}", "")


def _format_bibtex(run: RunCitations) -> str:
    cff = run.software
    entries = [
        "\n".join(
            [
                "@software{fairshares-software,",
                f"  author  = {{{_escape(_authors(cff))}}},",
                f"  title   = {{{_escape(cff.get('title', 'fair-shares'))}}},",
                f"  year    = {{{str(cff.get('date-released', ''))[:4]}}},",
                f"  version = {{{_escape(cff.get('version', ''))}}},",
                f"  url     = {{{_escape(cff.get('url', ''))}}},",
                f"  note    = {{Licence: {_escape(cff.get('license', ''))}}}",
                "}",
            ]
        )
    ]

    for name, source in run.sources:
        citation = _escape(source.citation)
        fields = [f"  note    = {{{citation}}}"]
        year = _YEAR.search(source.citation)
        if year:
            fields.insert(0, f"  year    = {{{year.group(1)}}}")
        if source.doi:
            fields.insert(0, f"  doi     = {{{_escape(source.doi)}}}")
        fields.insert(0, f"  title   = {{{_escape(name)}: {_escape(source.version)}}}")
        entries.append(
            "@misc{" + _bibtex_key(name) + ",\n" + ",\n".join(fields) + "\n}"
        )

    header = (
        "% Citations for this fair-shares run.\n"
        "% The full formatted citation is in each entry's note field, because the\n"
        "% source registry stores citations as finished text rather than separate\n"
        "% author and title fields. Import from the DOI for structured entries.\n"
    )
    return header + "\n\n".join(entries) + "\n"


def write_citations_file(
    output_dir: Any,
    active_sources: dict[str, str],
    *,
    emission_category: str | None = None,
    registry: Registry | None = None,
) -> Any:
    """Write ``CITATIONS.md`` into a run's output directory.

    Called from the paths that persist a run, so the file cannot be forgotten.
    Runs kept purely in memory produce no file, because there is no directory to
    put one in.
    """
    from pathlib import Path

    run = citations(
        active_sources, emission_category=emission_category, registry=registry
    )
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    out = target / "CITATIONS.md"
    out.write_text(run.text(), encoding="utf-8")
    return out
