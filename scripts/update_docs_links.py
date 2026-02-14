#!/usr/bin/env python3
"""Update documentation links in notebooks and source code.

This script manages documentation links using a placeholder pattern for maintainability.

**Placeholder pattern**: {DOCS_ROOT}/path/to/page/
**Expanded URL**: https://setupelz.github.io/fair-shares/path/to/page/

When the docs URL changes, just update DOCS_BASE_URL and re-run this script.

Usage:
    python scripts/update_docs_links.py [--expand] [--dry-run]
    python scripts/update_docs_links.py [--collapse] [--dry-run]

Commands:
    --expand: Convert placeholders {DOCS_ROOT}/path/ to full URLs (for distribution)
    --collapse: Convert full URLs back to placeholders (for development)
    --dry-run: Show what would change without modifying files
"""

import argparse
import os
import re
from pathlib import Path

# Documentation base URL
# Can be overridden via FAIR_SHARES_DOCS_URL environment variable
DOCS_BASE_URL = os.environ.get(
    "FAIR_SHARES_DOCS_URL", "https://setupelz.github.io/fair-shares"
)

# Placeholder pattern for maintainable links
DOCS_PLACEHOLDER = "{DOCS_ROOT}"


def expand_placeholder_link(match: re.Match) -> str:
    """Expand a {DOCS_ROOT} placeholder to full URL.

    Args:
        match: Regex match object with groups (link_text, placeholder_path)

    Returns
    -------
        Converted markdown link with absolute URL.
    """
    link_text = match.group(1)
    placeholder_path = match.group(2)

    # Replace placeholder with actual URL
    full_url = placeholder_path.replace(DOCS_PLACEHOLDER, DOCS_BASE_URL)

    return f"[{link_text}]({full_url})"


def collapse_url_link(match: re.Match) -> str:
    """Collapse a full docs URL to {DOCS_ROOT} placeholder.

    Args:
        match: Regex match object with groups (link_text, full_url)

    Returns
    -------
        Converted markdown link with placeholder.
    """
    link_text = match.group(1)
    full_url = match.group(2)

    # Replace base URL with placeholder
    placeholder_url = full_url.replace(DOCS_BASE_URL, DOCS_PLACEHOLDER)

    return f"[{link_text}]({placeholder_url})"


def convert_relative_to_placeholder(match: re.Match) -> str:
    """Convert a relative docs link to placeholder format.

    Args:
        match: Regex match object with groups (link_text, relative_path)

    Returns
    -------
        Converted markdown link with placeholder.
    """
    link_text = match.group(1)
    relative_path = match.group(2)

    # Extract path after ../docs/
    if "../docs/" in relative_path:
        doc_path = relative_path.split("../docs/")[1]
    elif "docs/" in relative_path:
        doc_path = relative_path.split("docs/")[1]
    else:
        # Can't convert, return original
        return match.group(0)

    # Handle anchors before removing .md extension
    if "#" in doc_path:
        path_part, anchor = doc_path.split("#", 1)
        # Remove .md extension from path part
        if path_part.endswith(".md"):
            path_part = path_part[:-3]
        placeholder_url = f"{DOCS_PLACEHOLDER}/{path_part}/#{anchor}"
    else:
        # Remove .md extension (MkDocs URLs don't include it)
        if doc_path.endswith(".md"):
            doc_path = doc_path[:-3]
        placeholder_url = f"{DOCS_PLACEHOLDER}/{doc_path}/"

    return f"[{link_text}]({placeholder_url})"


def update_file(file_path: Path, mode: str, dry_run: bool = False) -> tuple[int, int]:
    """Update documentation links in a single file.

    Args:
        file_path: Path to file to update
        mode: Operation mode ('expand', 'collapse', or 'relative_to_placeholder')
        dry_run: If True, only report changes without modifying files

    Returns
    -------
        Tuple of (files_modified, links_updated)
    """
    try:
        content = file_path.read_text()
    except UnicodeDecodeError:
        # Skip binary files
        return 0, 0

    updated_content = content
    total_changes = 0

    if mode == "expand":
        # Expand {DOCS_ROOT} placeholders to full URLs
        pattern = rf"\[([^\]]+)\]\(({re.escape(DOCS_PLACEHOLDER)}[^\)]+)\)"
        updated_content = re.sub(pattern, expand_placeholder_link, content)
        total_changes = len(re.findall(pattern, content))

    elif mode == "collapse":
        # Collapse full URLs to {DOCS_ROOT} placeholders
        pattern = rf"\[([^\]]+)\]\(({re.escape(DOCS_BASE_URL)}[^\)]+)\)"
        updated_content = re.sub(pattern, collapse_url_link, content)
        total_changes = len(re.findall(pattern, content))

    elif mode == "relative_to_placeholder":
        # Convert relative paths to placeholders
        pattern = r"\[([^\]]+)\]\((\.\.\/docs\/[^\)]+|docs\/[^\)]+)\)"
        updated_content = re.sub(pattern, convert_relative_to_placeholder, content)
        total_changes = len(re.findall(pattern, content))

    if updated_content != content:
        if not dry_run:
            file_path.write_text(updated_content)
            print(f"✓ Updated {file_path}: {total_changes} links")
        else:
            print(f"  Would update {file_path}: {total_changes} links")

        return 1, total_changes

    return 0, 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Update documentation links",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert relative links to placeholders (one-time setup)
  python scripts/update_docs_links.py --to-placeholder

  # Expand placeholders to URLs (for distribution)
  python scripts/update_docs_links.py --expand

  # Collapse URLs back to placeholders (for development)
  python scripts/update_docs_links.py --collapse

  # Preview changes without modifying files
  python scripts/update_docs_links.py --collapse --dry-run
        """,
    )
    parser.add_argument(
        "--expand",
        action="store_true",
        help="Expand {DOCS_ROOT} placeholders to full URLs",
    )
    parser.add_argument(
        "--collapse",
        action="store_true",
        help="Collapse full URLs to {DOCS_ROOT} placeholders",
    )
    parser.add_argument(
        "--to-placeholder",
        action="store_true",
        help="Convert relative ../docs/ links to {DOCS_ROOT} placeholders",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    args = parser.parse_args()

    # Determine mode
    if args.expand:
        mode = "expand"
        operation = "Expanding placeholders to URLs"
    elif args.collapse:
        mode = "collapse"
        operation = "Collapsing URLs to placeholders"
    elif args.to_placeholder:
        mode = "relative_to_placeholder"
        operation = "Converting relative links to placeholders"
    else:
        parser.error("Must specify one of: --expand, --collapse, or --to-placeholder")

    project_root = Path(__file__).parent.parent

    # Files to update
    patterns = [
        "notebooks/*.py",
        "src/**/*.py",
        "README.md",
        "docs/**/*.md",
    ]

    total_files = 0
    total_links = 0

    print(f"Documentation base URL: {DOCS_BASE_URL}")
    print(f"Placeholder: {DOCS_PLACEHOLDER}")
    print(f"{'DRY RUN - ' if args.dry_run else ''}{operation}...\n")

    for pattern in patterns:
        for file_path in project_root.glob(pattern):
            if file_path.name == "update_docs_links.py":
                continue  # Skip self

            files_modified, links_updated = update_file(file_path, mode, args.dry_run)
            total_files += files_modified
            total_links += links_updated

    print(
        f"\n{'Would update' if args.dry_run else 'Updated'} {total_links} links in {total_files} files"
    )

    if args.dry_run:
        print("\nRun without --dry-run to apply changes")


if __name__ == "__main__":
    main()
