"""Global Carbon Budget fossil CO2: flat CSV to the pipeline's timeseries layout.

The Andrew and Peters flat file is long format, MtCO2 per year, one row per
entity and year. Besides countries it holds four rows that belong to no country:
the global total (``WLD``), international shipping (``XIS``), international
aviation (``XIA``) and the 1991 Kuwaiti oil fires. The global total equals the
sum of every other row.

Rules applied here:

- Every blank year counts as zero. A blank means the file reports those
  emissions under another entity (Ireland under the United Kingdom until 1923)
  or reports none, and the global total already treats it as zero.
- The world row is the global total minus shipping, aviation and the oil fires.
  The three series are returned separately so the split stays auditable.
- A country row is an ISO3 code in ``countries``. Every other row stays in the
  world row and so lands in rest-of-world: codes outside the region mapping
  (Kosovo, Antarctica) and the two rows without a code ("Pacific Islands
  (Palau)", "Ryukyu Islands"), which the official GCB workbook also keeps in
  the world total and in no country column.
"""

from __future__ import annotations

import pandas as pd

from fair_shares.library.exceptions import DataLoadingError

ISO, NAME, YEAR, VALUE = "ISO 3166-1 alpha-3", "Country", "Year", "Total"
GLOBAL = "WLD"
SHIPPING = "XIS"
AVIATION = "XIA"
OIL_FIRES = "Kuwaiti Oil Fires"
UNIT = "Mt * CO2e"


def _wide(raw: pd.DataFrame, first_year: int) -> pd.DataFrame:
    """Pivot the long file to one row per entity, with blanks as zero."""
    missing = {ISO, NAME, YEAR, VALUE} - set(raw.columns)
    if missing:
        raise DataLoadingError(f"GCB file lacks expected columns: {sorted(missing)}")
    raw = raw[raw[YEAR] >= first_year]
    # Rows without an ISO code are keyed by their name.
    wide = raw.assign(key=raw[ISO].fillna(raw[NAME])).pivot(
        index="key", columns=YEAR, values=VALUE
    )
    wide.columns = wide.columns.astype(str).rename(None)
    return wide.fillna(0.0)


def gcb_fossil_co2(
    raw: pd.DataFrame, countries: set[str], world_key: str, first_year: int = 1850
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return GCB fossil CO2 as (emissions, excluded), both in MtCO2 per year.

    ``emissions`` holds one row per code in ``countries`` plus the world row,
    indexed by (iso3c, unit, emission-category). ``excluded`` holds shipping,
    aviation and the oil fires, indexed by source. For every year,
    world row + excluded rows = GCB global total.
    """
    wide = _wide(raw, first_year)
    excluded = wide.loc[[SHIPPING, AVIATION, OIL_FIRES]].rename_axis("source")
    world = (wide.loc[GLOBAL] - excluded.sum()).rename(world_key)

    emissions = pd.concat([wide[wide.index.isin(countries)], world.to_frame().T])
    emissions.index = pd.MultiIndex.from_tuples(
        [(iso3c, UNIT, "co2-ffi") for iso3c in emissions.index],
        names=["iso3c", "unit", "emission-category"],
    )
    return emissions, excluded


def gcb_first_recorded_year(
    raw: pd.DataFrame, countries: set[str], first_year: int = 1850
) -> pd.Series:
    """Return the first year from ``first_year`` with a value in the raw file.

    One entry per code in ``countries`` that has a record, indexed by iso3c.
    A blank is not a record, and a reported zero is. After the zero-fill the
    two look the same, so the coverage rule reads this table.
    """
    recorded = raw[(raw[YEAR] >= first_year) & raw[VALUE].notna()]
    recorded = recorded[recorded[ISO].isin(countries)]
    first = recorded.groupby(ISO)[YEAR].min()
    return first.rename("first_recorded_year").rename_axis("iso3c")


def gcb_bunkers(raw: pd.DataFrame, first_year: int = 1850) -> pd.DataFrame:
    """Return international shipping plus aviation as the single ``bunkers`` row."""
    wide = _wide(raw, first_year)
    bunkers = (wide.loc[SHIPPING] + wide.loc[AVIATION]).rename("bunkers")
    return bunkers.to_frame().T.rename_axis("source")


# Sheet and columns of the Global Carbon Budget workbook (GtC per year).
GLOBAL_BUDGET_SHEET = "Global Carbon Budget"
GLOBAL_FOSSIL = "fossil emissions excluding carbonation"
GLOBAL_CARBONATION = "cement carbonation sink"
GLOBAL_LAND_USE = "land-use change emissions"
GTC_TO_GTCO2 = 3.664


def gcb_global_net_co2(path) -> pd.Series:
    """Return observed global net CO2 emissions in Gt CO2 per year.

    Net emissions are fossil emissions minus the cement carbonation sink plus
    bookkeeping land-use change emissions, from the "Global Carbon Budget"
    sheet of the Global Carbon Budget workbook. The sheet reports GtC; the
    workbook's own factor 3.664 converts to Gt CO2. Fossil emissions are
    global, so they include international bunkers.

    Parameters
    ----------
    path : str or Path
        The workbook, e.g. Global_Carbon_Budget_2025_v1.0.xlsx

    Returns
    -------
    pd.Series
        Indexed by year (int), one value per year with all three components

    Raises
    ------
    DataLoadingError
        If the sheet lacks the year row or a component column
    """
    raw = pd.read_excel(path, sheet_name=GLOBAL_BUDGET_SHEET, header=None)
    header_rows = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "Year"]
    if header_rows.empty:
        raise DataLoadingError(f"{path}: no 'Year' header in '{GLOBAL_BUDGET_SHEET}'.")
    table = raw.iloc[header_rows[0] + 1 :].copy()
    table.columns = [str(c).strip() for c in raw.iloc[header_rows[0]]]
    missing = {GLOBAL_FOSSIL, GLOBAL_CARBONATION, GLOBAL_LAND_USE} - set(table.columns)
    if missing:
        raise DataLoadingError(
            f"{path}: '{GLOBAL_BUDGET_SHEET}' lacks {sorted(missing)}."
        )
    table = table[pd.to_numeric(table["Year"], errors="coerce").notna()]
    table.index = table["Year"].astype(int)
    values = table[[GLOBAL_FOSSIL, GLOBAL_CARBONATION, GLOBAL_LAND_USE]].astype(float)
    net = values[GLOBAL_FOSSIL] - values[GLOBAL_CARBONATION] + values[GLOBAL_LAND_USE]
    return (net.dropna() * GTC_TO_GTCO2).rename("net_co2_gt").rename_axis("year")
