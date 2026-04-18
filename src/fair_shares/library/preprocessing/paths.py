"""Path resolution for intermediate emissions files.

When an NGHGI LULUCF source is active (e.g. Melo), notebook 107 writes
NGHGI-consistent emission categories to filenames suffixed with
``_nghgi``. The PRIMAP (or equivalent) raw per-primitive outputs from
notebook 101 keep their base filenames. Downstream consumers use the
resolver here to pick the right variant for a given category.

Only the categories whose content genuinely depends on the choice of
LULUCF source require an NGHGI variant in the downstream pipeline:

- ``co2-lulucf`` — Melo NGHGI replaces PRIMAP bookkeeping LULUCF
- ``co2`` — FFI + Melo NGHGI, not PRIMAP total
- ``all-ghg`` — NGHGI co2 plus non-co2

``non-co2`` and ``all-ghg-ex-co2-lulucf`` are LULUCF-independent
(non-CO2 Kyoto gases, or PRIMAP totals excluding LULUCF CO2), so the
base PRIMAP filenames are used for them even when an NGHGI source is
active. This keeps the pipeline's ``source_id`` scheme (which only
appends the LULUCF tag for LULUCF-dependent categories) aligned with
the notebook 107 execution condition (``_needs_lulucf``).

The ``co2-ffi`` category is LULUCF-independent and always uses the
PRIMAP filename.
"""

from __future__ import annotations

from pathlib import Path

# Categories whose numerical content depends on the chosen LULUCF source.
# Kept in sync with ``_LULUCF_DEPENDENT`` in
# ``fair_shares.library.utils.data.config.build_source_id`` and the
# Snakefile's ``_needs_lulucf`` predicate.
NGHGI_CORRECTED_CATEGORIES: frozenset[str] = frozenset(
    {
        "co2-lulucf",
        "co2",
        "all-ghg",
    }
)


def emissions_filename(category: str, nghgi: bool) -> str:
    """Return the filename for an emissions CSV at the given NGHGI level.

    Parameters
    ----------
    category
        Emission category (e.g. ``"co2"``, ``"co2-ffi"``).
    nghgi
        Whether to return the NGHGI-consistent variant.

    Returns
    -------
    str
        ``"emiss_{category}_nghgi_timeseries.csv"`` when ``nghgi`` is True
        and the category is NGHGI-affected, else
        ``"emiss_{category}_timeseries.csv"``.
    """
    if nghgi and category in NGHGI_CORRECTED_CATEGORIES:
        return f"emiss_{category}_nghgi_timeseries.csv"
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
        The configured LULUCF source; if truthy, NGHGI correction is in
        effect and the NGHGI variant is preferred for affected categories.

    Returns
    -------
    Path
        Absolute (or relative, depending on ``intermediate_dir``) path
        to the appropriate CSV.
    """
    nghgi = bool(active_lulucf_source)
    return intermediate_dir / emissions_filename(category, nghgi)
