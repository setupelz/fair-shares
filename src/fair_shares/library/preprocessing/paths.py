"""Path resolution for intermediate emissions files.

When a LULUCF source is active, notebook 107 writes the land-use-dependent
emission categories, built with that source's land-use CO2, to filenames
suffixed with ``_lu``. The source may be national inventories (NGHGI basis,
e.g. Melo) or bookkeeping models (model basis, e.g. GCB national land-use
change); its ``data_parameters.basis`` says which. The raw per-primitive
outputs of notebook 101 keep their base filenames. Downstream consumers use
the resolver here to pick the right variant for a given category.

Only the categories whose content depends on the choice of LULUCF source
have an ``_lu`` variant:

- ``co2-lulucf`` — the LULUCF source replaces the emissions source's land use
- ``co2`` — FFI plus the LULUCF source's land use
- ``all-ghg`` — that co2 plus non-co2

``non-co2`` and ``all-ghg-ex-co2-lulucf`` are LULUCF-independent
(non-CO2 Kyoto gases, or totals excluding LULUCF CO2), so the base
filenames are used for them even when a LULUCF source is active. This keeps
the pipeline's ``source_id`` scheme (which only appends the LULUCF tag for
LULUCF-dependent categories) aligned with the notebook 107 execution
condition (``_needs_lulucf``).

The ``co2-ffi`` category is LULUCF-independent and always uses the base
filename.
"""

from __future__ import annotations

from pathlib import Path

# Categories whose numerical content depends on the chosen LULUCF source.
# Kept in sync with ``_LULUCF_DEPENDENT`` in
# ``fair_shares.library.utils.data.config.build_source_id`` and the
# Snakefile's ``_needs_lulucf`` predicate.
LULUCF_CATEGORIES: frozenset[str] = frozenset(
    {
        "co2-lulucf",
        "co2",
        "all-ghg",
    }
)


def emissions_filename(category: str, with_lulucf: bool) -> str:
    """Return the filename for an emissions CSV, with or without a LULUCF source.

    Parameters
    ----------
    category
        Emission category (e.g. ``"co2"``, ``"co2-ffi"``).
    with_lulucf
        Whether a LULUCF source is active (return the ``_lu`` variant).

    Returns
    -------
    str
        ``"emiss_{category}_lu_timeseries.csv"`` when ``with_lulucf`` is True
        and the category is LULUCF-dependent, else
        ``"emiss_{category}_timeseries.csv"``.
    """
    if with_lulucf and category in LULUCF_CATEGORIES:
        return f"emiss_{category}_lu_timeseries.csv"
    return f"emiss_{category}_timeseries.csv"


def emissions_path(
    intermediate_dir: Path, category: str, active_lulucf_source: str | None
) -> Path:
    """Return the emissions CSV path for a category under a given config.

    Parameters
    ----------
    intermediate_dir
        Intermediate emissions directory (usually ``<run>/intermediate/emissions``).
    category
        Emission category.
    active_lulucf_source
        The configured LULUCF source; if truthy, the ``_lu`` variant is
        used for LULUCF-dependent categories.

    Returns
    -------
    Path
        Absolute (or relative, depending on ``intermediate_dir``) path
        to the appropriate CSV.
    """
    return intermediate_dir / emissions_filename(category, bool(active_lulucf_source))
