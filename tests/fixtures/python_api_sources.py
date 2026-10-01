"""Data sources and source-id derivation shared by the 601 fixture script and its test."""

from __future__ import annotations

from fair_shares.library.utils.data.config import build_data_config

# Must match the ``active_sources`` defaults in notebooks/601_reproduce_esabcc_2023.py.
SOURCES = {
    "emissions_source": "primap-202503",
    "gdp_source": "wdi-2025",
    "population_source": "un-owid-2025",
    "gini_source": "wdi-2025",
    "lulucf_source": "melo-2026",
}


def source_id(category: str) -> str:
    """Return the output folder id notebook 601 writes to for ``category``."""
    active_sources = {
        "target": "rcbs",
        "emissions": SOURCES["emissions_source"],
        "gdp": SOURCES["gdp_source"],
        "population": SOURCES["population_source"],
        "gini": SOURCES["gini_source"],
        "lulucf": SOURCES["lulucf_source"],
    }
    return build_data_config(category, active_sources)[1]
