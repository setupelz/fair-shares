"""Loaders for country land-use (LULUCF) CO2 sources.

A LULUCF source holds country land-use CO2 on one of two accounting bases,
named by ``data_parameters.basis`` in ``data_sources_unified.yaml``:

- ``nghgi``: national greenhouse gas inventories (Melo et al., LULUCF Data
  Hub). Part of the natural land sink counts as an anthropogenic removal.
- ``bookkeeping``: bookkeeping models (Global Carbon Budget national land-use
  change), the basis integrated assessment models use.

Each loader returns the same frame: one row per ISO3 country plus a world row
under ``world_key``, string year columns, Mt CO2 per year, negative = net sink.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from fair_shares.library.exceptions import DataLoadingError, DataProcessingError
from fair_shares.library.utils.dataframes import convert_country_name_to_iso3c

LULUCF_BASES: tuple[str, ...] = ("nghgi", "bookkeeping")

# Mt CO2 per Mt C
C_TO_CO2 = 44.0 / 12.0

# Columns of the GCB national land-use change workbook that are not countries.
GCB_LUC_GLOBAL_COLUMN = "Global"
GCB_LUC_NON_COUNTRY = ("OTHER", "DISPUTED", "EU27", GCB_LUC_GLOBAL_COLUMN)


def _gcb_luc_sheet(path: Path, sheet: str, header_row: int) -> pd.DataFrame:
    """One model sheet: rows are years, columns are country names, Tg C/yr."""
    df = pd.read_excel(path, sheet_name=sheet, header=header_row, index_col=0)
    years = pd.to_numeric(df.index, errors="coerce")
    df = df[pd.notna(years)]
    df.index = years[pd.notna(years)].astype(int)
    df.columns = [str(c).strip() for c in df.columns]
    return df.apply(pd.to_numeric, errors="coerce")


def load_gcb_national_luc(
    path: str | Path,
    models: Sequence[str],
    world_key: str,
    header_row: int = 7,
) -> pd.DataFrame:
    """Load GCB national land-use change CO2, averaged over bookkeeping models.

    Reads one sheet per model (``BLUE``, ``OSCAR``, ``LUCE`` in GCB 2025), each
    in Tg C/yr with years as rows and country names as columns, and returns the
    mean over ``models`` in Mt CO2/yr. Country names are converted to ISO3; the
    workbook's ``Global`` column becomes the world row under ``world_key``.
    ``OTHER``, ``DISPUTED`` and ``EU27`` are dropped, so countries do not sum
    exactly to the world row.

    Raises
    ------
    DataLoadingError
        If the file or a model sheet is missing
    DataProcessingError
        If the model sheets disagree on countries or years, a country name has
        no ISO3 code, or two names map to one code
    """
    path = Path(path)
    if not path.exists():
        raise DataLoadingError(f"GCB national land-use change file not found: {path}")
    if not models:
        raise DataProcessingError("No bookkeeping models given")
    available = pd.ExcelFile(path).sheet_names
    lacking = [m for m in models if m not in available]
    if lacking:
        raise DataLoadingError(
            f"Model sheets {lacking} not in {path.name} (sheets: {available})"
        )

    sheets = {m: _gcb_luc_sheet(path, m, header_row) for m in models}
    first = next(iter(sheets.values()))
    for model, sheet in sheets.items():
        if list(sheet.columns) != list(first.columns) or not sheet.index.equals(
            first.index
        ):
            raise DataProcessingError(
                f"Sheet {model} differs from {models[0]} in countries or years"
            )
    if GCB_LUC_GLOBAL_COLUMN not in first.columns:
        raise DataProcessingError(f"No '{GCB_LUC_GLOBAL_COLUMN}' column in {path.name}")

    mean_tgc = sum(sheets.values()) / len(sheets)

    names = [c for c in mean_tgc.columns if c not in GCB_LUC_NON_COUNTRY]
    # A column named by its ISO3 code ("USA") converts to itself, which the
    # name helper reads as not found.
    iso = {
        n: n
        if len(n) == 3 and n.isupper()
        else convert_country_name_to_iso3c(n, world_key=world_key)
        for n in names
    }
    unmatched = sorted(n for n, code in iso.items() if code is None)
    if unmatched:
        raise DataProcessingError(f"No ISO3 code for countries: {unmatched}")
    codes = pd.Series(iso)
    duplicated = codes[codes.duplicated(keep=False)]
    if not duplicated.empty:
        raise DataProcessingError(
            f"Country names share an ISO3 code: {duplicated.to_dict()}"
        )

    countries = mean_tgc[names].rename(columns=iso)
    countries[world_key] = mean_tgc[GCB_LUC_GLOBAL_COLUMN]
    wide = (countries * C_TO_CO2).T
    wide.index.name = "iso3c"
    wide.columns = [str(y) for y in wide.columns]
    return wide


def load_nghgi_lulucf(
    path: str | Path,
    world_key: str,
    *,
    iso3_column: str,
    year_column: str,
    value_column: str,
    category_filter: str,
    gas_filter: str,
    source_world_key: str,
    exclude_regions: Sequence[str] = (),
) -> pd.DataFrame:
    """Load NGHGI LULUCF CO2 from a long-format Melo LULUCF Data Hub file.

    Keeps rows of ``category_filter`` and ``gas_filter``, drops
    ``exclude_regions``, pivots to one row per ISO3 code and renames the
    source's world row (``source_world_key``) to ``world_key``.

    Raises
    ------
    DataLoadingError
        If the file is missing
    DataProcessingError
        If the source has no world row
    """
    path = Path(path)
    if not path.exists():
        raise DataLoadingError(f"NGHGI LULUCF file not found: {path}")
    raw = pd.read_csv(path)
    rows = raw[
        (raw["Category"] == category_filter)
        & (raw["Gas"] == gas_filter)
        & (~raw[iso3_column].isin(list(exclude_regions)))
    ]
    wide = rows.pivot_table(
        index=iso3_column, columns=year_column, values=value_column, aggfunc="sum"
    )
    wide.columns = [str(int(y)) for y in wide.columns]
    if source_world_key not in wide.index:
        raise DataProcessingError(
            f"World row '{source_world_key}' not found in {path.name}"
        )
    wide = wide.rename(index={source_world_key: world_key})
    wide.index.name = "iso3c"
    return wide
