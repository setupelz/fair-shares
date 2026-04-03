#!/usr/bin/env python3
"""Extract and validate citations from science documentation.

This script:
1. Extracts all author-year citations from science markdown files
2. Validates them against references.md
3. Reports valid vs invalid citations
"""

import re
from pathlib import Path
from typing import Set, Tuple


def extract_citations(file_path: Path) -> Set[str]:
    """Extract all [Author YYYY] and [Author et al. YYYY] citations from a file.

    Returns set of unique citations found (normalized format).
    """
    content = file_path.read_text()

    # Pattern matches:
    # [Author YYYY] or [Author et al. YYYY] or [Author et al YYYY]
    # Also handles [e.g., Author YYYY] format
    pattern = r"\[(?:e\.g\.,\s*)?([A-Z][a-z]+(?:\s+et al\.?)?)\s+(\d{4})\]"

    matches = re.findall(pattern, content)
    citations = {f"{author} {year}" for author, year in matches}

    return citations


def load_references(refs_path: Path) -> Set[str]:
    """Load valid author-year combinations from references.md.

    Returns set of valid citations in "Author YYYY" format.
    """
    content = refs_path.read_text()
    valid = set()

    # Pattern matches the reference format:
    # **FirstAuthor LastName et al. (YYYY)** or **FirstAuthor LastName (YYYY)**
    pattern = r"\*\*([A-Z][a-z]+\s+[A-Z][^\s]+)(?:\s+et al\.)?\s+\((\d{4})\)\*\*"

    for match in re.finditer(pattern, content):
        last_name = match.group(1).split()[-1]  # Get last name
        year = match.group(2)
        valid.add(f"{last_name} {year}")
        # Also add "et al." version for multi-author papers
        if "et al" in match.group(0):
            valid.add(f"{last_name} et al. {year}")
            valid.add(f"{last_name} et al {year}")  # Without period

    return valid


def validate_citations(
    citations: Set[str], valid_refs: Set[str]
) -> Tuple[Set[str], Set[str]]:
    """Validate citations against references.

    Returns
    -------
        (valid_citations, invalid_citations)
    """
    valid = set()
    invalid = set()

    for citation in citations:
        # Normalize "et al." variations
        normalized = citation.replace("et al.", "et al").strip()
        citation_variants = [
            citation,
            normalized,
            citation.replace("et al", "et al."),
        ]

        if any(variant in valid_refs for variant in citation_variants):
            valid.add(citation)
        else:
            invalid.add(citation)

    return valid, invalid


def main():
    """Extract and validate citations from science documentation."""
    # File paths
    science_files = [
        Path("docs/science/principle-to-code.md"),
        Path("docs/science/allocations.md"),
    ]
    refs_file = Path("docs/science/references.md")

    # Extract citations from all science files
    all_citations: Set[str] = set()
    for science_file in science_files:
        if science_file.exists():
            print(f"Extracting citations from {science_file}...")
            file_citations = extract_citations(science_file)
            print(f"  Found {len(file_citations)} unique citations")
            all_citations |= file_citations
    print(f"\nTotal unique citations: {len(all_citations)}\n")

    # Load valid references
    print(f"Loading valid references from {refs_file}...")
    valid_refs = load_references(refs_file)
    print(f"Found {len(valid_refs)} valid author-year combinations\n")

    # Validate
    valid, invalid = validate_citations(all_citations, valid_refs)

    # Report results
    print("=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)

    print(f"\nVALID CITATIONS ({len(valid)}):")
    for citation in sorted(valid):
        print(f"  ✓ {citation}")

    print(f"\nINVALID CITATIONS ({len(invalid)}):")
    for citation in sorted(invalid):
        print(f"  ✗ {citation}")

    if invalid:
        print("\n" + "!" * 60)
        print("ACTION REQUIRED:")
        print(f"Fix {len(invalid)} invalid citation(s) in science docs")
        print("!" * 60)
    else:
        print("\n✓ All citations are valid!")

    return len(invalid) == 0


if __name__ == "__main__":
    import sys

    success = main()
    sys.exit(0 if success else 1)
