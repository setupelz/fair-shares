"""Documentation URL configuration for fair-shares.

This module provides centralized configuration for documentation URLs,
making it easy to update links when documentation moves.
"""

import os

# Documentation base URL
# Can be overridden via FAIR_SHARES_DOCS_URL environment variable
DOCS_BASE_URL = os.environ.get(
    "FAIR_SHARES_DOCS_URL", "https://setupelz.github.io/fair-shares"
)


def docs_url(path: str) -> str:
    """Generate a documentation URL from a relative path.

    Args:
        path: Relative path within docs (e.g., 'science/allocations' or 'science/allocations.md')

    Returns
    -------
        Full URL to the documentation page.

    Examples
    --------
        >>> docs_url("science/allocations")
        'https://setupelz.github.io/fair-shares/science/allocations/'
        >>> docs_url("user-guide/country-fair-shares")
        'https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/'
    """
    # Remove .md extension if present (MkDocs URLs don't include it)
    if path.endswith(".md"):
        path = path[:-3]

    # Remove leading slash if present
    path = path.lstrip("/")

    # Ensure trailing slash for clean URLs
    if not path.endswith("/"):
        path = path + "/"

    return f"{DOCS_BASE_URL}/{path}"


# Common documentation URLs for quick reference
DOCS_URLS = {
    "science": {
        "allocations": docs_url("science/allocations"),
        "climate_equity_concepts": docs_url("science/climate-equity-concepts"),
        "principle_to_code": docs_url("science/principle-to-code"),
        "glossary": docs_url("science/glossary"),
        "references": docs_url("science/references"),
    },
    "user_guide": {
        "country_fair_shares": docs_url("user-guide/country-fair-shares"),
        "iamc_regional_fair_shares": docs_url("user-guide/iamc-regional-fair-shares"),
        "approach_catalog": docs_url("user-guide/approach-catalog"),
    },
    "api": {
        "budgets": docs_url("api/allocations/budgets"),
        "pathways": docs_url("api/allocations/pathways"),
    },
}
