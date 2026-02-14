#!/usr/bin/env python3
"""Build docs/science/references.md from rubric JSON files.

This script extracts citation metadata from all rubric JSON files in
data/rubrics/climate-equity/ and generates a properly formatted references.md
file with all 29 sources.
"""

import json
from pathlib import Path
from typing import Any


def format_authors(authors: list[str]) -> str:
    """Format author list for citation.

    Args:
        authors: List of author names in "Last, First" format

    Returns
    -------
        Formatted string: "Last, F. et al." or "Last, F. and Last2, F."
    """
    if not authors:
        return ""

    # Get first author's last name and first initial
    first_author = authors[0]
    if ", " in first_author:
        last, first = first_author.split(", ", 1)
        first_initial = first[0] if first else ""
    else:
        # Handle cases where author is just a last name
        last = first_author
        first_initial = ""

    first_author_formatted = f"{last}, {first_initial}." if first_initial else last

    # If multiple authors, add "et al."
    if len(authors) > 1:
        return f"{first_author_formatted} et al."

    return first_author_formatted


def format_reference(rubric: dict[str, Any]) -> str:
    """Format a single rubric as a reference entry.

    Args:
        rubric: Dictionary containing title, authors, year, journal, doi

    Returns
    -------
        Formatted markdown reference entry
    """
    authors_str = format_authors(rubric.get("authors", []))
    year = rubric.get("year", "n.d.")
    title = rubric.get("title", "Untitled")
    journal = rubric.get("journal")
    doi = rubric.get("doi")

    # Build reference string
    ref = f'**{authors_str} ({year})**. "{title}."'

    if journal:
        ref += f" _{journal}_."

    if doi:
        ref += f" DOI: {doi}"

    return ref


def extract_rubric_metadata(rubric_dir: Path) -> list[tuple[str, str]]:
    """Extract metadata from all rubric JSON files.

    Args:
        rubric_dir: Path to directory containing rubric JSON files

    Returns
    -------
        List of (sort_key, formatted_reference) tuples
    """
    references = []

    for json_file in sorted(rubric_dir.glob("*.json")):
        with open(json_file, encoding="utf-8") as f:
            rubric = json.load(f)

        # Format the reference
        formatted_ref = format_reference(rubric)

        # Create sort key from first author's last name
        authors = rubric.get("authors", [])
        if authors:
            first_author = authors[0]
            # Extract last name for sorting
            if ", " in first_author:
                sort_key = first_author.split(", ")[0]
            else:
                sort_key = first_author
        else:
            sort_key = "zzz"  # Put entries without authors at the end

        # Add year to sort key for secondary sorting
        year = rubric.get("year", 9999)
        sort_key_full = f"{sort_key.lower()}_{year}"

        references.append((sort_key_full, formatted_ref))

    return references


def generate_references_md(references: list[tuple[str, str]]) -> str:
    """Generate the complete references.md content.

    Args:
        references: List of (sort_key, formatted_reference) tuples

    Returns
    -------
        Complete markdown content for references.md
    """
    # Sort references alphabetically by sort key
    references.sort(key=lambda x: x[0])

    # Build the markdown content
    content = """# References

Complete bibliography for the fair-shares project. All citations are drawn from curated
rubrics reviewed for climate equity scholarship.

For context on how these inform allocation approaches, see:
- [Climate Equity Concepts](climate-equity-concepts.md)
- [Allocation Approaches](allocations.md)
- [Other Operations](other-operations.md)

> **Citation style in docs/science/**: Inline citations use `[e.g., Author YYYY]` format to signal
> these are illustrative examples from a broader literature. This list represents the reviewed
> sources; inline citations are selective.

---

"""

    # Add all references
    for _, ref in references:
        content += f"{ref}\n\n"

    return content.rstrip() + "\n"


def main() -> None:
    """Main entry point."""
    # Define paths
    rubric_dir = Path("/Users/setupelz/Documents/monorepo/data/rubrics/climate-equity")
    output_file = Path(__file__).parent.parent / "docs" / "science" / "references.md"

    # Extract metadata
    print(f"Extracting metadata from {rubric_dir}...")
    references = extract_rubric_metadata(rubric_dir)
    print(f"Found {len(references)} rubric files")

    # Generate references.md
    print(f"Generating {output_file}...")
    content = generate_references_md(references)

    # Write output
    output_file.write_text(content, encoding="utf-8")
    print(f"✓ Generated {output_file}")
    print(f"✓ Total references: {len(references)}")


if __name__ == "__main__":
    main()
