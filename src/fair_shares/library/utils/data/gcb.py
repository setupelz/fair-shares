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


def gcb_bunkers(raw: pd.DataFrame, first_year: int = 1850) -> pd.DataFrame:
    """Return international shipping plus aviation as the single ``bunkers`` row."""
    wide = _wide(raw, first_year)
    bunkers = (wide.loc[SHIPPING] + wide.loc[AVIATION]).rename("bunkers")
    return bunkers.to_frame().T.rename_axis("source")
