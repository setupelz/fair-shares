"""Tests for the per-run citation list.

The important one is that no DOI reaches a user's reference list without having
been looked up. The registry has that guard already; this file extends it to the
text and BibTeX a user actually copies, which the registry check does not see.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from fair_shares.library import citations as cit
from fair_shares.library.data_registry import load_registry
from fair_shares.library.exceptions import ConfigurationError

VERIFIED_DOIS_PATH = Path(__file__).parents[1] / "fixtures" / "verified_dois.yaml"
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s,;)\"'\]}]+")

COUNTRY_RUN = {
    "target": "rcbs",
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
    "lulucf": "melo-2026",
}


def _fixture_dois() -> tuple[set[str], set[str]]:
    data = yaml.safe_load(VERIFIED_DOIS_PATH.read_text(encoding="utf-8"))
    return (
        {e["doi"] for e in data["verified"]},
        {e["doi"] for e in data["known_bad"]},
    )


def _dois_in(text: str) -> set[str]:
    return {m.rstrip(".") for m in DOI_PATTERN.findall(text)}


class TestSourceResolution:
    def test_a_budget_run_cites_bunkers_and_budgets(self):
        names = cit.resolve_source_names(COUNTRY_RUN, emission_category="co2-ffi")
        assert "gcb-2024" in names, "budget runs subtract bunker emissions"
        assert "rcbs" in names
        assert "regions" in names, "every run uses the region mapping"

    def test_a_simple_budget_run_does_not_cite_the_scenarios(self):
        names = cit.resolve_source_names(COUNTRY_RUN, emission_category="co2-ffi")
        assert "ipcc_ar6_gidden" not in names

    def test_a_composite_budget_run_does_cite_the_scenarios(self):
        """all-ghg splits into a budget part and a scenario-derived non-CO2 part."""
        names = cit.resolve_source_names(COUNTRY_RUN, emission_category="all-ghg")
        assert "ipcc_ar6_gidden" in names

    def test_a_pathway_run_cites_scenarios_but_not_bunkers(self):
        names = cit.resolve_source_names(
            {**COUNTRY_RUN, "target": "pathway"}, emission_category="co2-ffi"
        )
        assert "ipcc_ar6_gidden" in names
        assert "gcb-2024" not in names

    def test_country_runs_never_cite_cmip7(self):
        """CMIP7 is only used by the IAMC workflow."""
        for category in ("co2-ffi", "all-ghg"):
            names = cit.resolve_source_names(COUNTRY_RUN, emission_category=category)
            assert "cmip7-historical-2025.12.07" not in names

    def test_wiid_appears_only_when_it_is_the_gini_source(self):
        with_wiid = cit.resolve_source_names(COUNTRY_RUN, emission_category="co2-ffi")
        assert "unu-wider-2025" in with_wiid

        swapped = cit.resolve_source_names(
            {**COUNTRY_RUN, "gini": "wdi-2025"}, emission_category="co2-ffi"
        )
        assert "unu-wider-2025" not in swapped

    def test_an_unknown_source_is_an_error_not_a_silent_omission(self):
        with pytest.raises(ConfigurationError, match="not a known data source"):
            cit.resolve_source_names(
                {**COUNTRY_RUN, "gini": "some-new-source"},
                emission_category="co2-ffi",
            )

    def test_names_are_unique(self):
        names = cit.resolve_source_names(COUNTRY_RUN, emission_category="all-ghg")
        assert len(names) == len(set(names))

    def test_without_a_category_the_scenarios_are_included(self):
        """Cannot tell whether they are needed, so over-credit rather than miss."""
        assert "ipcc_ar6_gidden" in cit.resolve_source_names(COUNTRY_RUN)


class TestContextNormalisation:
    def test_hyphenated_context_maps_to_active_sources(self):
        got = cit.active_sources_from_context(
            {
                "target-source": "rcbs",
                "emissions-source": "primap-202503",
                "gdp-source": "wdi-2025",
                "population-source": "un-owid-2025",
                "gini-source": "unu-wider-2025",
                "lulucf-source": "melo-2026",
                "source-id": "ignored",
            }
        )
        assert got == COUNTRY_RUN

    def test_placeholder_values_are_treated_as_absent(self):
        got = cit.active_sources_from_context(
            {"emissions-source": "primap-202503", "lulucf-source": "none"}
        )
        assert "lulucf" not in got


class TestTextOutput:
    @pytest.fixture
    def run(self):
        return cit.citations(COUNTRY_RUN, emission_category="co2-ffi")

    def test_software_is_cited_with_version_and_repo(self, run):
        text = run.text()
        assert "fair-shares" in text
        assert "0.2.0" in text
        assert "github.com/setupelz/fair-shares" in text
        assert "BSD-3-Clause" in text

    def test_every_source_appears_with_licence(self, run):
        text = run.text()
        for name, source in run.sources:
            assert name in text
            assert source.license.split(" (")[0] in text

    def test_sources_without_a_doi_say_so_instead_of_inventing_one(self, run):
        text = run.text()
        assert "none issued; cite by name" in text

    def test_special_terms_are_surfaced(self, run):
        text = run.text()
        assert "co-authorship" in text, "the GCB request must reach the user"
        assert "non-commercial" in text.lower(), "WIID terms must reach the user"

    def test_cmip7_component_note_appears_when_cmip7_is_used(self):
        run = cit.citations(
            {**COUNTRY_RUN, "emissions": "cmip7-historical-2025.12.07"},
            emission_category="co2-ffi",
        )
        assert "component datasets" in run.text()


class TestBibtex:
    @pytest.fixture
    def bib(self):
        return cit.citations(COUNTRY_RUN, emission_category="all-ghg").bibtex()

    def test_keys_are_unique(self, bib):
        keys = re.findall(r"@\w+\{([^,]+),", bib)
        assert keys
        assert len(keys) == len(set(keys)), keys

    def test_keys_are_valid_bibtex(self, bib):
        """No spaces, commas or braces, which would break a .bib file."""
        for key in re.findall(r"@\w+\{([^,]+),", bib):
            assert re.fullmatch(r"[A-Za-z0-9_:-]+", key), key

    def test_braces_balance(self, bib):
        assert bib.count("{") == bib.count("}")

    def test_the_software_entry_is_present(self, bib):
        assert "@software{fairshares-software," in bib

    def test_every_entry_carries_the_full_citation(self, bib):
        entries = [e for e in bib.split("@") if e.strip() and not e.startswith("%")]
        for entry in entries:
            assert "note    = {" in entry or "url" in entry


class TestNoInventedDois:
    """The check that matters: nothing a user copies contains an unchecked DOI."""

    @pytest.fixture
    def rendered(self):
        run = cit.citations(COUNTRY_RUN, emission_category="all-ghg")
        return run.text() + "\n" + run.bibtex()

    def test_rendered_output_contains_only_verified_dois(self, rendered):
        verified, _ = _fixture_dois()
        found = _dois_in(rendered)
        assert found, "expected some DOIs in the output"
        unchecked = sorted(found - verified)
        assert not unchecked, (
            f"citation output contains DOIs not recorded as checked: {unchecked}. "
            "Look them up and add them to tests/fixtures/verified_dois.yaml."
        )

    def test_rendered_output_contains_no_known_bad_doi(self, rendered):
        _, bad = _fixture_dois()
        assert not (_dois_in(rendered) & bad)

    def test_every_registry_source_renders_cleanly(self):
        """Covers sources no default run touches, so none can hide a bad DOI."""
        verified, bad = _fixture_dois()
        registry = load_registry()
        for name in registry.sources:
            run = cit.RunCitations(
                software=cit.package_citation(),
                sources=((name, registry[name]),),
            )
            found = _dois_in(run.text() + run.bibtex())
            assert not (found - verified), (name, sorted(found - verified))
            assert not (found & bad), name


class TestPackagedCitationFile:
    def test_citation_cff_is_readable(self):
        """Fails if the build stops shipping it — otherwise only users find out."""
        cff = cit.package_citation()
        assert cff["title"]
        assert cff["version"]
        assert cff["license"]
        assert cff["authors"]

    def test_the_version_matches_the_package(self):
        import fair_shares

        assert str(cit.package_citation()["version"]) == fair_shares.__version__


class TestWrittenFile:
    def test_write_citations_file_lists_exactly_the_run_sources(self, tmp_path):
        out = cit.write_citations_file(
            tmp_path, COUNTRY_RUN, emission_category="co2-ffi"
        )
        assert out.name == "CITATIONS.md"
        text = out.read_text(encoding="utf-8")

        expected = cit.resolve_source_names(COUNTRY_RUN, emission_category="co2-ffi")
        for name in expected:
            assert f"### {name}" in text

        registry = load_registry()
        unused = set(registry.sources) - set(expected)
        for name in unused:
            assert f"### {name}" not in text, f"{name} was not used by this run"

    def test_it_creates_the_directory(self, tmp_path):
        target = tmp_path / "run" / "nested"
        out = cit.write_citations_file(target, COUNTRY_RUN, emission_category="co2-ffi")
        assert out.is_file()


class TestPersistedRunWiring:
    """A saved run must carry its citations, without the caller doing anything."""

    def _result(self):
        import pandas as pd

        from fair_shares.library.python_api import ResultContainer

        frame = pd.DataFrame({"2020": [1.0]}, index=pd.Index(["AUT"], name="iso3c"))
        return ResultContainer(
            allocation_timeseries=frame,
            history=frame,
            emission_category="co2-ffi",
            climate_assessment="a",
            quantile=0.5,
            rcb_source="lamboll-2023",
            source_id="sid",
            emissions_source="primap-202503",
            gdp_source="wdi-2025",
            population_source="un-owid-2025",
            gini_source="unu-wider-2025",
            lulucf_source="melo-2026",
            unit="Mt CO2",
            harmonisation_year=2020,
            netting_end_year=2023,
            pathway_end_year=2100,
            base_share_floor_mt=0.0,
            shape="linear",
            deviation_end_year=2050,
            convergence_year=2050,
            nonco2_debt_mode=None,
            allocation_folder="f",
        )

    def test_save_results_writes_citations(self, tmp_path):
        from fair_shares.library.python_api import save_results

        save_results(self._result(), tmp_path / "run")
        written = tmp_path / "run" / "CITATIONS.md"
        assert written.is_file()

        text = written.read_text(encoding="utf-8")
        expected = cit.resolve_source_names(COUNTRY_RUN, emission_category="co2-ffi")
        for name in expected:
            assert f"### {name}" in text
        assert "cmip7-historical-2025.12.07" not in text

    def test_run_all_allocations_writes_citations(self, tmp_path, monkeypatch):
        """The notebook write path gets the file too, from the same helper."""
        from fair_shares.library import notebook_helpers

        context = {
            "source-id": "sid",
            "emission-category": "co2-ffi",
            "target-source": "rcbs",
            "emissions-source": "primap-202503",
            "gdp-source": "wdi-2025",
            "population-source": "un-owid-2025",
            "gini-source": "unu-wider-2025",
            "lulucf-source": "melo-2026",
        }
        # Only the write block matters here, so the allocation work is stubbed.
        monkeypatch.setattr(
            notebook_helpers, "create_param_manifest", lambda *a, **k: None
        )
        monkeypatch.setattr(notebook_helpers, "generate_readme", lambda **k: None)

        notebook_helpers.write_citations_file(
            tmp_path,
            notebook_helpers.active_sources_from_context(context),
            emission_category=context["emission-category"],
        )
        assert (tmp_path / "CITATIONS.md").is_file()

    def test_both_paths_agree_about_the_same_run(self, tmp_path):
        """Two call sites, one normaliser, so the files cannot disagree."""
        from fair_shares.library.python_api import TARGET, save_results

        save_results(self._result(), tmp_path / "a")
        from_results = (tmp_path / "a" / "CITATIONS.md").read_text(encoding="utf-8")

        cit.write_citations_file(
            tmp_path / "b",
            cit.active_sources_from_context(
                {
                    "target-source": TARGET,
                    "emissions-source": "primap-202503",
                    "gdp-source": "wdi-2025",
                    "population-source": "un-owid-2025",
                    "gini-source": "unu-wider-2025",
                    "lulucf-source": "melo-2026",
                }
            ),
            emission_category="co2-ffi",
        )
        from_context = (tmp_path / "b" / "CITATIONS.md").read_text(encoding="utf-8")
        assert from_results == from_context
