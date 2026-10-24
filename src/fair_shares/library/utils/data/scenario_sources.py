"""
Scenario sources behind the scenario-derived budget terms.

``fair_shares/conf/scenario_sources.yaml`` declares, per scenario source, the
world variables that notebook 104 reads, the metadata columns that the
scenario sets read (see ``fair_shares.library.utils.data.scenario_sets``) and
the bunker variables. A new scenario source plugs in as a new entry.

The AR6 bunker series come from the public AR6 Scenarios Database, read
anonymously through pyam (``fetch_ar6_bunkers``). The Scenario Compass (SCI)
and ScenarioMIP workbooks are manual downloads (``bunker_reporter_series``;
``derived_source_inputs`` for SCI's non-CO2). Their metadata carry no warming
at net zero; ``warming_at_net_zero`` derives it from their GSAT percentile
series.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fair_shares.library.exceptions import ConfigurationError, DataLoadingError

SCENARIO_SOURCES_RESOURCE = "scenario_sources.yaml"
DEFAULT_SCENARIO_SOURCE = "ar6"
# AR6 WGIII Table SPM.2, note j: a pathway counts as reaching net zero when its
# harmonised or reported CO2 falls below 100 Mt CO2/yr by 2100.
NET_ZERO_THRESHOLD_MT = 100.0

# Platform and query behind data/scenarios/ipcc_ar6_bunkers.
AR6_PUBLIC_PLATFORM = "ar6-public"
AR6_BUNKER_REGION = "World"


@lru_cache(maxsize=1)
def _load_all() -> dict[str, Any]:
    from fair_shares.library.paths import packaged_config

    raw = yaml.safe_load(
        packaged_config(SCENARIO_SOURCES_RESOURCE).read_text(encoding="utf-8")
    )
    return raw["sources"]


def get_scenario_source(
    name: str = DEFAULT_SCENARIO_SOURCE, version: str | None = None
) -> dict[str, Any]:
    """
    Return the registry entry of one scenario source.

    Parameters
    ----------
    name : str
        Key in ``scenario_sources.yaml`` (default: "ar6")
    version : str, optional
        Release of an entry with ``versions`` (default: its ``version`` key)

    Returns
    -------
    dict
        The entry as declared, merged with the fields of the selected release. Every entry has "terms", "co2_variables" and
        "bunkers"; "ar6" also has "variables", "category_column" and
        "metadata_columns"

    Raises
    ------
    ConfigurationError
        If the source is not in the registry
    """
    sources = _load_all()
    if name not in sources:
        raise ConfigurationError(
            f"Unknown scenario source '{name}'. Known sources: {sorted(sources)}."
        )
    entry = dict(sources[name])
    versions = entry.pop("versions", None)
    if versions is None:
        return entry
    version = version or entry.get("version")
    if version not in versions:
        raise ConfigurationError(
            f"Scenario source '{name}' has no version '{version}'. Known versions: "
            f"{sorted(versions)}."
        )
    return {**entry, **versions[version], "version": version}


def metadata_column_names(source: dict[str, Any]) -> list[str]:
    """List every metadata column that the scenario sets of a source read."""
    columns = [source["category_column"], *source["metadata_columns"].values()]
    return list(dict.fromkeys(columns))


def source_data_path(
    source: dict[str, Any], data_dir: str | Path | None = None
) -> Path:
    """Resolve the data file of a scenario source, filling in its version."""
    from fair_shares.library import paths

    rel = source["path"].format(version=source.get("version", ""))
    return paths._resolve("data", data_dir).joinpath(*Path(rel).parts[1:])


def load_bunker_pathways(
    path: str | Path | pd.DataFrame,
    components: dict[str, float],
    total: str | None = None,
) -> pd.DataFrame:
    """
    Return the international bunker CO2 of every scenario that reports it.

    Bunkers are the sum of the component variables, each scaled by its factor.
    A scenario counts only if it reports every component. With ``total``, a
    scenario that reports the total variable takes it instead.

    Parameters
    ----------
    path : str, Path or pd.DataFrame
        CSV written by ``fetch_ar6_bunkers``, or a frame, in IAMC wide format
    components : dict[str, float]
        Variable -> factor, from the ``bunkers`` block of the registry entry
    total : str, optional
        Variable that reports bunkers directly

    Returns
    -------
    pd.DataFrame
        One row per scenario, indexed by (Model, Scenario), string year columns,
        in Mt CO2/yr

    Raises
    ------
    DataLoadingError
        If the file is absent or holds no scenario with every component
    """
    if isinstance(path, pd.DataFrame):
        raw = path.copy()
    else:
        path = Path(path)
        if not path.exists():
            raise DataLoadingError(
                f"Scenario bunker emissions not found: {path}. Fetch them with "
                '`uv run python -c "from fair_shares.library.utils.data.'
                'scenario_sources import fetch_ar6_bunkers; fetch_ar6_bunkers()"`.'
            )
        raw = pd.read_csv(path)
    raw = raw.rename(
        columns={"model": "Model", "scenario": "Scenario", "Variable": "variable"}
    )
    years = [c for c in raw.columns if str(c).isdigit()]
    by_total = pd.DataFrame(columns=years)
    if total is not None:
        by_total = (
            raw[raw["variable"] == total]
            .groupby(["Model", "Scenario"])[years]
            .sum(min_count=1)
        )
    parts = raw[raw["variable"].isin(components)]
    complete = parts.groupby(["Model", "Scenario"])["variable"].transform("nunique")
    parts = parts[complete == len(components)]
    scaled = parts[years].mul(parts["variable"].map(components), axis=0)
    scaled[["Model", "Scenario"]] = parts[["Model", "Scenario"]]
    by_parts = scaled.groupby(["Model", "Scenario"])[years].sum(min_count=1)
    by_parts = by_parts[~by_parts.index.isin(by_total.index)]
    frames = [f for f in (by_total, by_parts) if not f.empty]
    bunkers = pd.concat(frames).astype(float) if frames else pd.DataFrame()
    if bunkers.empty:
        raise DataLoadingError(
            f"No scenario reports bunkers ({total or list(components)})."
        )
    bunkers.columns = [str(c) for c in bunkers.columns]
    return bunkers


def annual_pathways(
    wide: pd.DataFrame, first_year: int = 2020, last_year: int = 2100
) -> pd.DataFrame:
    """
    Interpolate pathways linearly to every year and keep the complete ones.

    A scenario counts only with a value in every year from ``first_year`` to
    ``last_year``.
    """
    frame = wide.copy()
    frame.columns = frame.columns.astype(int)
    frame = frame.reindex(columns=range(min(frame.columns), last_year + 1))
    frame = frame.interpolate(axis=1, limit_area="inside")
    frame.columns = frame.columns.astype(str)
    return frame[[str(y) for y in range(first_year, last_year + 1)]].dropna()


def read_workbook_sheet(
    path: str | Path,
    sheet: str,
    variables: set[str] | None = None,
    region: str = "World",
) -> pd.DataFrame:
    """
    Read one sheet of a large IAMC workbook row by row, with a parquet cache.

    With ``variables``, only rows of those variables in ``region`` are kept.
    The cache sits next to the workbook and is rebuilt when the workbook or
    the variable list changes.
    """
    import openpyxl

    path = Path(path)
    tag = hashlib.sha256(
        "|".join([sheet, region, *sorted(variables or [])]).encode()
    ).hexdigest()[:12]
    cache = path.with_name(f".{path.stem}.{sheet}.{tag}.parquet")
    if cache.exists() and cache.stat().st_mtime >= path.stat().st_mtime:
        return pd.read_parquet(cache)

    workbook = openpyxl.load_workbook(path, read_only=True)
    rows = workbook[sheet].iter_rows(values_only=True)
    header = [str(c) for c in next(rows)]
    if variables is None:
        kept = [list(r) for r in rows]
    else:
        v_at, r_at = header.index("Variable"), header.index("Region")
        kept = [list(r) for r in rows if r[v_at] in variables and r[r_at] == region]
    workbook.close()
    frame = pd.DataFrame(kept, columns=header)
    frame.columns = [str(c) for c in frame.columns]
    for column in frame.columns:
        if frame[column].dtype == object and column not in ("Model", "Scenario"):
            converted = pd.to_numeric(frame[column], errors="coerce")
            if converted.notna().sum() == frame[column].notna().sum():
                frame[column] = converted
    frame.to_parquet(cache, index=False)
    return frame


def model_family(model: str) -> str:
    """
    Return the energy-model family of a model name from ``model_families``.

    Raises
    ------
    ConfigurationError
        If the model is in no family of ``scenario_sources.yaml``
    """
    for family, models in _load_families().items():
        if model in models:
            return family
    raise ConfigurationError(
        f"Model '{model}' is in no family of `model_families` in "
        f"scenario_sources.yaml. Add it under its energy-model family."
    )


@lru_cache(maxsize=1)
def _load_families() -> dict[str, list[str]]:
    from fair_shares.library.paths import packaged_config

    raw = yaml.safe_load(
        packaged_config(SCENARIO_SOURCES_RESOURCE).read_text(encoding="utf-8")
    )
    return raw["model_families"]


def _wide(frame: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """Sum the variables per scenario; a scenario counts only with all of them."""
    frame = frame.rename(
        columns={"model": "Model", "scenario": "Scenario", "variable": "Variable"}
    )
    rows = frame[frame["Variable"].isin(variables)]
    complete = rows.groupby(["Model", "Scenario"])["Variable"].transform("nunique")
    rows = rows[complete == len(variables)]
    years = [c for c in rows.columns if str(c).isdigit()]
    wide = rows.groupby(["Model", "Scenario"])[years].sum(min_count=1).astype(float)
    wide.columns = [str(c) for c in wide.columns]
    return wide


def bunker_reporter_series(
    name: str,
    data_dir: str | Path | None = None,
    exclude_ar6_duplicates: bool = False,
    pool: list[str] | tuple[str, ...] = (),
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """
    Return the net CO2 and bunker CO2 of every bunker reporter of a source.

    Runs that the entry flags as carried over from another source of ``pool``
    (``duplicate_columns``; ``exclude_ar6_duplicates`` for AR6) count once,
    under that other source.

    No vetting applies: the bunker share needs the ratio of bunkers to net CO2
    within each model run, which historical vetting does not test. Both series
    are the model's own (``bunkers.share_co2_variables`` and the bunker
    variables of the registry entry), in Mt CO2/yr at the reported years.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame] or None
        (net CO2, bunkers), one row per reporter indexed by (Model, Scenario),
        or None when the source's data file is absent
    """
    source = get_scenario_source(name)
    block = source["bunkers"]
    co2_variables = list(block["share_co2_variables"])
    if "total" in block:
        path = source_data_path(source, data_dir)
        if not path.exists():
            warnings.warn(
                f"Scenario source workbook not found: {path}. The bunker share "
                f"leaves this source out. Registry name: "
                f"{source.get('registry_source')}.",
                stacklevel=2,
            )
            return None
        variables = {*co2_variables, *block["components"], block["total"]}
        data = read_workbook_sheet(path, "data", variables)
        data = data[~data["Model"].isin(source.get("exclude_models", []))]
        flags = _duplicate_columns(source, exclude_ar6_duplicates, pool, name)
        if flags:
            meta = read_workbook_sheet(path, "meta").set_index(["Model", "Scenario"])
            dupes = set(meta.index[meta[flags].eq(True).any(axis=1)])
            keys = list(zip(data["Model"], data["Scenario"]))
            data = data[[k not in dupes for k in keys]]
        bunkers = load_bunker_pathways(data, block["components"], block["total"])
    else:
        from fair_shares.library import paths

        data = pd.read_csv(
            paths._resolve("data", data_dir) / Path(block["path"]).relative_to("data")
        )
        bunkers = load_bunker_pathways(data, block["components"])
    co2 = _wide(data, co2_variables)
    keys = bunkers.index.intersection(co2.index)
    return co2.loc[keys], bunkers.loc[keys]


def _duplicate_columns(
    source: dict[str, Any], exclude_ar6: bool, pool, name: str
) -> list[str]:
    """Meta columns that flag runs carried over from other sources of the pool."""
    columns = dict(source.get("duplicate_columns", {}))
    if source.get("ar6_duplicate_column"):
        columns.setdefault("ar6", source["ar6_duplicate_column"])
    wanted = {o for o in pool if o != name} | ({"ar6"} if exclude_ar6 else set())
    return [column for other, column in columns.items() if other in wanted]


def _annual(frame: pd.DataFrame, last_year: int) -> pd.DataFrame:
    """Interpolate year columns linearly to every year up to ``last_year``."""
    frame = frame.astype(float)
    frame.columns = frame.columns.astype(int)
    frame = frame.reindex(columns=range(int(min(frame.columns)), last_year + 1))
    return frame.interpolate(axis=1, limit_area="inside")


def net_zero_years(
    co2_mt: pd.DataFrame,
    start: int = 2020,
    last_year: int = 2100,
    reported_mt: pd.DataFrame | None = None,
    threshold_mt: float = NET_ZERO_THRESHOLD_MT,
) -> pd.Series:
    """
    Return the net-zero CO2 year of every scenario, in the AR6 convention.

    Every series is linear between its reported years. The net-zero year is
    the first full year from ``start`` at which the harmonised CO2 is at or
    below zero. A scenario without one counts as reaching net zero when its
    harmonised or reported CO2 falls below ``threshold_mt`` by ``last_year``
    (AR6 WGIII Table SPM.2, note j), in the first such year. Other scenarios
    get NaN.

    Parameters
    ----------
    co2_mt : pd.DataFrame
        Harmonised net CO2 of the climate assessment, Mt CO2/yr, year columns
    reported_mt : pd.DataFrame, optional
        The model's own (non-harmonised) net CO2, same layout
    threshold_mt : float, optional
        Threshold of the AR6 count, Mt CO2/yr (default: 100)
    """
    co2 = _annual(co2_mt, last_year).loc[:, start:last_year]
    below = co2.lt(threshold_mt)
    if reported_mt is not None:
        reported = _annual(reported_mt, last_year).reindex(
            index=co2.index, columns=co2.columns
        )
        below |= reported.lt(threshold_mt)

    def first(mask: pd.DataFrame) -> pd.Series:
        return mask.idxmax(axis=1).where(mask.any(axis=1)).astype(float)

    return first(co2.le(0)).fillna(first(below))


def _ascii_key(key: tuple) -> tuple:
    return tuple(str(part).encode("ascii", "replace").decode() for part in key)


def warming_at_net_zero(
    co2_mt: pd.DataFrame,
    gsat: dict[str, pd.DataFrame],
    start: int = 2020,
    last_year: int = 2100,
    reported_mt: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Return the net-zero CO2 year of every scenario and the warming in that year.

    The net-zero year follows ``net_zero_years`` (AR6 convention). The warming
    is the GSAT of that year, linear between reported years. A scenario
    without net zero by ``last_year`` takes the GSAT of ``last_year``.

    Parameters
    ----------
    co2_mt : pd.DataFrame
        Harmonised net CO2 of the climate assessment, one row per scenario,
        year columns
    gsat : dict[str, pd.DataFrame]
        Output column -> GSAT series of one percentile, same layout
    start, last_year : int, optional
        First and last year searched (default: 2020, 2100)
    reported_mt : pd.DataFrame, optional
        The model's own net CO2, for the threshold count of ``net_zero_years``

    Returns
    -------
    pd.DataFrame
        One row per scenario present in every input, columns
        "net_zero_year" and the keys of ``gsat``
    """
    temperatures = {name: _annual(frame, last_year) for name, frame in gsat.items()}
    keys = co2_mt.index
    for frame in temperatures.values():
        keys = keys.intersection(frame.index)
    net_zero = net_zero_years(co2_mt.loc[keys], start, last_year, reported_mt)
    result = pd.DataFrame({"net_zero_year": net_zero}, index=keys)
    years = net_zero.fillna(last_year).astype(int)
    for name, frame in temperatures.items():
        frame = frame.loc[keys]
        result[name] = [frame.at[key, year] for key, year in zip(keys, years)]
    return result


def apply_derived_net_zero(
    metadata: pd.DataFrame, derived: pd.DataFrame
) -> tuple[pd.DataFrame, pd.Index]:
    """
    Replace the at-net-zero columns of the metadata with derived values.

    Keys match after non-ASCII characters become "?", as in exports of the
    public AR6 database.

    Parameters
    ----------
    metadata : pd.DataFrame
        One row per scenario, indexed by (Model, Scenario)
    derived : pd.DataFrame
        Output of ``ar6_at_net_zero``: the same column names, one row per
        scenario

    Returns
    -------
    tuple[pd.DataFrame, pd.Index]
        The metadata with the derived columns, and the scenarios whose
        net-zero year changed

    Raises
    ------
    DataProcessingError
        If a scenario of the metadata has no derived row
    """
    from fair_shares.library.exceptions import DataProcessingError

    by_ascii = {_ascii_key(k): row for k, row in derived.iterrows()}
    missing = [k for k in metadata.index if _ascii_key(k) not in by_ascii]
    if missing:
        raise DataProcessingError(
            f"No derived net-zero values for {len(missing)} scenarios, e.g. "
            f"{missing[:3]}. Fetch the AR6 climate series again."
        )
    rows = pd.DataFrame(
        [by_ascii[_ascii_key(k)] for k in metadata.index], index=metadata.index
    )
    result = metadata.copy()
    year = derived.columns[0]
    old = result[year]
    changed = metadata.index[~((old == rows[year]) | (old.isna() & rows[year].isna()))]
    result[derived.columns] = rows[derived.columns]
    return result, changed


def ar6_at_net_zero(
    name: str = DEFAULT_SCENARIO_SOURCE, data_dir: str | Path | None = None
) -> pd.DataFrame | None:
    """
    Derive the at-net-zero columns of a source from its climate series, or None.

    Reads the ``climate_series`` block of the registry entry (AR6: the
    harmonised-infilled CO2, the reported CO2 and the GSAT percentiles of the
    AR6 climate assessment, fetched with ``fetch_ar6_climate_series``) and
    applies ``warming_at_net_zero``. None when the entry has no such block.

    Returns
    -------
    pd.DataFrame or None
        One row per scenario, columns named as in ``metadata_columns``
        (net-zero year first)

    Raises
    ------
    DataLoadingError
        If the entry declares the block and the file is absent
    """
    from fair_shares.library import paths

    source = get_scenario_source(name)
    block = source.get("climate_series")
    if block is None:
        return None
    path = paths._resolve("data", data_dir) / Path(block["path"]).relative_to("data")
    if not path.exists():
        raise DataLoadingError(
            f"AR6 climate series not found: {path}. Fetch them with "
            '`uv run python -c "from fair_shares.library.utils.data.'
            "scenario_sources import fetch_ar6_climate_series; "
            'fetch_ar6_climate_series()"`.'
        )
    data = pd.read_csv(path)
    columns = source["metadata_columns"]
    derived = warming_at_net_zero(
        _wide(data, [block["co2"]]),
        {columns[role]: _wide(data, [v]) for role, v in block["gsat"].items()},
        reported_mt=_wide(data, [block["co2_reported"]]),
    )
    return derived.rename(columns={"net_zero_year": columns["net_zero_year"]})


def derived_source_inputs(
    name: str,
    data_dir: str | Path | None = None,
    exclude_ar6_duplicates: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """
    Return the metadata and non-CO2 pathways of a source with derived warming.

    For a registry entry with a ``derived_warming`` block that supplies the
    non-co2 term (SCI): keeps the scenarios that pass its ``vetting`` and are
    not in ``exclude_models``, derives the at-net-zero columns with
    ``warming_at_net_zero`` and takes non-CO2 as Kyoto gases minus CO2 of its
    ``non_co2`` block.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame] or None
        (metadata, non-CO2 in Mt CO2e/yr at the reported years), both indexed
        by (Model, Scenario). The metadata hold the columns named in
        ``metadata_columns`` and ``category_column``. None when the workbook
        is absent.

    Raises
    ------
    ConfigurationError
        If the entry has no ``derived_warming`` block or no non-co2 term
    """
    source = get_scenario_source(name)
    derived = source.get("derived_warming")
    if derived is None:
        raise ConfigurationError(
            f"Scenario source '{name}' declares no derived_warming block."
        )
    if "non-co2" not in source["terms"]:
        raise ConfigurationError(
            f"Scenario source '{name}' does not supply the non-co2 term."
        )
    path = source_data_path(source, data_dir)
    if not path.exists():
        warnings.warn(
            f"Scenario source workbook not found: {path}. Registry name: "
            f"{source.get('registry_source')}.",
            stacklevel=2,
        )
        return None
    block = source["non_co2"]
    reported = derived.get("co2_reported")
    variables = {
        *source["co2_variables"],
        *([reported] if reported else []),
        *derived["gsat"].values(),
        block["kyoto"],
        *block["co2_variables"],
    }
    data = read_workbook_sheet(path, "data", variables)
    meta = read_workbook_sheet(path, "meta").set_index(["Model", "Scenario"])
    keep = ~meta.index.get_level_values("Model").isin(source.get("exclude_models", []))
    if "vetting" in source:
        keep &= meta[source["vetting"]["column"]].isin(source["vetting"]["keep"])
    if exclude_ar6_duplicates and source.get("ar6_duplicate_column"):
        keep &= ~meta[source["ar6_duplicate_column"]].eq(True)
    meta = meta[keep]

    columns = source["metadata_columns"]
    derived_frame = warming_at_net_zero(
        _wide(data, list(source["co2_variables"])),
        {
            columns[role]: _wide(data, [variable])
            for role, variable in derived["gsat"].items()
        },
        reported_mt=_wide(data, [reported]) if reported else None,
    ).rename(columns={"net_zero_year": columns["net_zero_year"]})
    keys = meta.index.intersection(derived_frame.index)
    metadata = derived_frame.loc[keys]
    category = source.get("category_column")
    if category:
        metadata[category] = meta.loc[keys, category]
    non_co2 = (
        _wide(data, [block["kyoto"]])
        .sub(_wide(data, list(block["co2_variables"])))
        .dropna(how="all")
    )
    return metadata, non_co2.loc[non_co2.index.intersection(keys)]


def fetch_ar6_bunkers(
    data_dir: str | Path | None = None,
    source: str = DEFAULT_SCENARIO_SOURCE,
) -> Path:
    """
    Download the world bunker components of every AR6 scenario.

    Reads the public AR6 Scenarios Database (platform "ar6-public") anonymously
    through pyam, keeps the World region and the component variables of the
    registry entry, and writes them with a provenance file next to them.

    Parameters
    ----------
    data_dir : str or Path, optional
        Data directory (default: the resolved data directory)
    source : str
        Scenario source key (default: "ar6")

    Returns
    -------
    Path
        The written CSV
    """
    import pyam

    from fair_shares.library import paths

    entry = get_scenario_source(source)["bunkers"]
    variables = list(entry["components"])
    share_co2 = list(entry.get("share_co2_variables", []))
    target = paths.data_dir_for_write(data_dir) / Path(entry["path"]).relative_to(
        "data"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    df = pyam.read_iiasa(
        AR6_PUBLIC_PLATFORM, variable=variables, region=AR6_BUNKER_REGION, meta=False
    )
    table = df.timeseries().reset_index()
    if share_co2:
        # Net CO2 of the same scenarios, for the bunker share.
        co2 = (
            pyam.read_iiasa(
                AR6_PUBLIC_PLATFORM,
                variable=share_co2,
                region=AR6_BUNKER_REGION,
                meta=False,
            )
            .timeseries()
            .reset_index()
        )
        reporters = set(zip(table["model"], table["scenario"]))
        co2 = co2[[k in reporters for k in zip(co2["model"], co2["scenario"])]]
        table = pd.concat([table, co2], ignore_index=True)
        variables = variables + share_co2
    return _write_with_provenance(table, target, variables)


def _write_with_provenance(
    table: pd.DataFrame, target: Path, variables: list[str]
) -> Path:
    """Write an ar6-public extract and its provenance file next to it."""
    import pyam

    table.to_csv(target, index=False)
    provenance = {
        "platform": AR6_PUBLIC_PLATFORM,
        "query": {"variable": variables, "region": AR6_BUNKER_REGION},
        "retrieved": _dt.date.today().isoformat(),
        "pyam_version": pyam.__version__,
        "n_scenarios": int(table[["model", "scenario"]].drop_duplicates().shape[0]),
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    target.with_suffix(".provenance.yaml").write_text(
        yaml.safe_dump(provenance, sort_keys=False)
    )
    return target


def fetch_ar6_climate_series(
    data_dir: str | Path | None = None,
    source: str = DEFAULT_SCENARIO_SOURCE,
) -> Path:
    """
    Download the world climate series behind the AR6 at-net-zero columns.

    Reads the variables of the ``climate_series`` block of the registry entry
    (harmonised-infilled CO2, reported CO2, GSAT percentiles) from the public
    AR6 Scenarios Database (platform "ar6-public") anonymously through pyam
    and writes them with a provenance file next to them.

    Returns
    -------
    Path
        The written CSV
    """
    import pyam

    from fair_shares.library import paths

    block = get_scenario_source(source)["climate_series"]
    variables = [block["co2"], block["co2_reported"], *block["gsat"].values()]
    target = paths.data_dir_for_write(data_dir) / Path(block["path"]).relative_to(
        "data"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    table = (
        pyam.read_iiasa(
            AR6_PUBLIC_PLATFORM,
            variable=variables,
            region=AR6_BUNKER_REGION,
            meta=False,
        )
        .timeseries()
        .reset_index()
    )
    return _write_with_provenance(table, target, variables)
