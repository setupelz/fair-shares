"""
Per-allocation data coverage.

An analysis country has complete data from 1990, but an allocation can read
earlier years: cumulative population from an early allocation year, a
responsibility window, or a capability snapshot or window. A country without a
value in a year that one allocation reads joins rest of world (ROW) for that
allocation only. ROW is the world total minus the analysis countries, so the
country's rows are added to the ROW rows and dropped.

:func:`years_read` lists the years each input is read for one allocation,
:func:`find_incomplete_countries` names the countries with a gap in those
years, and :func:`move_countries_to_row` rebuilds the input frames.
"""

from __future__ import annotations

import pandas as pd

from fair_shares.library.utils import TimeseriesDataFrame

ROW_KEY = "ROW"

#: One read window: (input name, first year, last year or ``None`` for the
#: last column of the frame). Input names: "population", "gdp",
#: "emissions" (country history) and "responsibility-emissions".
YearWindow = tuple[str, int, int | None]


def years_read(
    approach: str,
    params: dict,
    allocation_year: int | None = None,
    first_allocation_year: int | None = None,
) -> list[YearWindow]:
    """List the years each input frame is read for one allocation.

    Parameters
    ----------
    approach
        Approach name, e.g. ``"per-capita-adjusted-budget"``.
    params
        The allocation's parameters with the function defaults filled in
        (snake_case keys).
    allocation_year, first_allocation_year
        The allocation year of a budget or pathway approach.

    Returns
    -------
    list[YearWindow]
        Inclusive year windows per input.
    """
    is_budget = approach.endswith("-budget")
    year = allocation_year if is_budget else first_allocation_year
    if year is None:
        return []
    year = int(year)
    windows: list[YearWindow] = []

    cumulative_end_year = params.get("cumulative_end_year")
    windows.append(
        ("population", year, int(cumulative_end_year) if cumulative_end_year else None)
    )

    is_cumulative_convergence = approach.startswith("cumulative-per-capita-convergence")
    if is_cumulative_convergence or approach == "per-capita-convergence":
        # Current emission shares at the first allocation year.
        windows.append(("emissions", year, year))

    if (params.get("pre_allocation_responsibility_weight") or 0) > 0:
        start = params.get("pre_allocation_responsibility_year")
        if start is not None:
            # The convergence family includes the first allocation year.
            end = year if is_cumulative_convergence else year - 1
            windows.append(("responsibility-emissions", int(start), end))
            if params.get("pre_allocation_responsibility_per_capita"):
                windows.append(("population", int(start), end))

    if (params.get("capability_weight") or 0) > 0:
        window = params.get("capability_window")
        reference_year = params.get("capability_reference_year")
        if window is not None:
            start, end = (int(y) for y in window)
            windows += [("gdp", start, end), ("population", start, end)]
        elif reference_year is not None:
            reference_year = int(reference_year)
            windows += [
                ("gdp", reference_year, reference_year),
                ("population", reference_year, reference_year),
            ]
        else:
            windows.append(("gdp", year, None))

    return windows


def _missing_years(
    df: TimeseriesDataFrame, start: int, end: int | None, group_level: str
) -> dict[str, list[int]]:
    """Years in [start, end] without a value, per country (ROW and World excluded)."""
    years = {int(c): c for c in df.columns if str(c).isdigit()}
    selected = [
        label for y, label in years.items() if y >= start and (end is None or y <= end)
    ]
    if not selected:
        return {}
    groups = df.index.get_level_values(group_level)
    countries = df[~groups.isin([ROW_KEY, "World"])][selected]
    gaps = countries.isna()
    position = (
        countries.index.names.index(group_level)
        if isinstance(countries.index, pd.MultiIndex)
        else None
    )
    out: dict[str, list[int]] = {}
    for idx, row in gaps[gaps.any(axis=1)].iterrows():
        country = idx[position] if position is not None else idx
        out.setdefault(country, [])
        out[country] += [int(c) for c in row.index[row.to_numpy()]]
    return {c: sorted(set(y)) for c, y in out.items()}


def find_incomplete_countries(
    frames: dict[str, TimeseriesDataFrame | None],
    windows: list[YearWindow],
    group_level: str = "iso3c",
) -> dict[str, str]:
    """Name the countries without a value in a year an allocation reads.

    Parameters
    ----------
    frames
        Input frames by name ("population", "gdp", "emissions",
        "responsibility-emissions"). A missing frame is skipped.
    windows
        The output of :func:`years_read`.
    group_level
        Index level of the country codes.

    Returns
    -------
    dict[str, str]
        Country code mapped to a description of its gaps, e.g.
        ``"population 1850-1949"``.
    """
    found: dict[str, list[str]] = {}
    for name, start, end in windows:
        df = frames.get(name)
        if df is None:
            continue
        for country, years in _missing_years(df, start, end, group_level).items():
            span = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
            found.setdefault(country, []).append(f"{name} {span}")
    return {c: ", ".join(sorted(set(d))) for c, d in sorted(found.items())}


def has_row(df: TimeseriesDataFrame | None, group_level: str = "iso3c") -> bool:
    """Whether a frame holds rest-of-world rows."""
    return df is not None and ROW_KEY in df.index.get_level_values(group_level)


def move_countries_to_row(
    df: TimeseriesDataFrame | None,
    countries: list[str],
    group_level: str = "iso3c",
    add_values: bool = True,
) -> TimeseriesDataFrame | None:
    """Move countries into the rest-of-world rows of one frame.

    The countries' rows are dropped. With ``add_values`` their values are added
    to the ROW row with the same other index levels (unit, category), so ROW
    stays the world total minus the remaining analysis countries; a missing
    value of a moved country counts as zero, because the world total already
    holds it. Without ``add_values`` (a per-country value such as Gini) the
    rows are only dropped.
    """
    if df is None or not countries:
        return df
    groups = df.index.get_level_values(group_level)
    moved_mask = groups.isin(countries)
    if not moved_mask.any():
        return df
    kept = df[~moved_mask].copy()
    if not add_values:
        return kept

    other_levels = [n for n in df.index.names if n != group_level]
    moved = df[moved_mask].fillna(0.0)
    row_mask = kept.index.get_level_values(group_level) == ROW_KEY
    row = kept[row_mask]
    if other_levels:
        moved_sum = moved.groupby(level=other_levels).sum()
        row_keys = row.droplevel(group_level).index
        addition = moved_sum.reindex(row_keys).fillna(0.0).to_numpy()
    else:
        addition = moved.sum().to_numpy()
    kept.loc[row_mask] = row.to_numpy() + addition
    return kept
