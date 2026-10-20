"""A library API for computing allocation timeseries without running notebooks.

The ESABCC reproduction (notebook 601) computes, for one RCB *anchor* (a
``rcb_source`` / ``climate_assessment`` / ``quantile`` triple) and one emission
``category``:

* budget allocations of the remaining carbon budget (§4),
* each country's remaining budget after netting observed emissions (§5), and
* an annual pathway to ``pathway_end_year`` that spreads that remaining budget
  under a normative distribution grid, plus the non-CO2 and combined parts (§6).

:func:`calculate_allocation_timeseries` performs exactly that computation in
memory and returns a :class:`ResultContainer`, so downstream consumers (e.g. a
front-end data build) never have to execute the notebook or manage its output
directories. The heavy lifting still lives in the existing library functions
(``setup_data``, ``run_all_allocations``, ``distribute_remaining_budgets_pathways``);
this module holds the §5/§6 orchestration, which notebook 601 also calls, and
the historical coverage bookkeeping, and ties it together per (anchor, category).
"""

from __future__ import annotations

import json
import logging
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from fair_shares.library.allocations.coverage import ROW_KEY
from fair_shares.library.citations import (
    active_sources_from_context,
    write_citations_file,
)
from fair_shares.library.exceptions import AllocationError, ConfigurationError
from fair_shares.library.notebook_helpers import (
    load_allocation_data,
    run_all_allocations,
)
from fair_shares.library.paths import configure
from fair_shares.library.utils import setup_data
from fair_shares.library.utils.data.config import (
    is_composite_category,
    validate_data_source_config,
)
from fair_shares.library.utils.data.setup import _deprecate_project_root
from fair_shares.library.utils.math import (
    calculate_exponential_decay_pathway,
    distribute_remaining_budgets_pathways,
)

logger = logging.getLogger(__name__)

TARGET = "rcbs"  # this API is for remaining-carbon-budget allocations only

NONCO2_DEBT_MODES: tuple[str, ...] = ("report-only", "co2-debit")
"""Ways to settle past non-CO2 over-use in composite categories."""

_DEPRECATED_NONCO2_DEBT_MODES = {"free-rider": "report-only"}


def normalise_nonco2_debt_mode(mode: str) -> str:
    """Return the canonical name of a non-CO2 debt mode.

    ``"free-rider"`` is a deprecated alias of ``"report-only"`` and emits a
    ``DeprecationWarning``.

    Raises
    ------
    ValueError
        If ``mode`` is not a known mode or alias
    """
    if mode in _DEPRECATED_NONCO2_DEBT_MODES:
        new = _DEPRECATED_NONCO2_DEBT_MODES[mode]
        warnings.warn(
            f"nonco2 debt mode {mode!r} is deprecated; use {new!r}.",
            DeprecationWarning,
            stacklevel=3,
        )
        return new
    if mode not in NONCO2_DEBT_MODES:
        raise ValueError(
            f"Unknown nonco2 debt mode {mode!r}; choose one of {list(NONCO2_DEBT_MODES)}"
        )
    return mode


# Which historical gas coverages each run category needs, and the parts to sum
# to build each. The two ``combined`` baskets are the sum of their CO2 and
# non-CO2 parts (all-ghg = co2 + non-co2 from 2000; all-ghg-ex = co2-ffi +
# non-co2 from 1850). Mirrors the coverage the distributed pathways carry.
COVERAGE_PARTS: dict[str, dict[str, tuple[str, ...]]] = {
    "co2-ffi": {"co2-ffi": ("co2-ffi",)},
    "all-ghg-ex-co2-lulucf": {
        "co2-ffi": ("co2-ffi",),
        "non-co2": ("non-co2",),
        "all-ghg-ex-co2-lulucf": ("co2-ffi", "non-co2"),
    },
    "all-ghg": {
        "co2": ("co2",),
        "non-co2": ("non-co2",),
        "all-ghg": ("co2", "non-co2"),
    },
}


@dataclass
class ResultContainer:
    """The allocation timeseries for one (anchor, category), with its inputs.

    Everything common to every row is an explicit attribute; ``metadata`` is a
    fallback only for approach-specific extras that do not belong on the frame.
    """

    allocation_timeseries: pd.DataFrame
    """Distributed annual pathways. MultiIndex holds every identifying column
    (category, emission-category part, unit, source, climate-assessment,
    quantile, approach, config params, the §6 knobs shape / deviation-end-year /
    nonco2-debt-mode, iso3c); columns are the years."""

    history: pd.DataFrame
    """Observed emissions used, one row per (coverage, unit, iso3c); columns are
    the years. Includes the summed ``combined`` basket(s) for this category."""

    # --- anchor -------------------------------------------------------------
    emission_category: str
    climate_assessment: str
    quantile: float
    rcb_source: str

    # --- provenance ---------------------------------------------------------
    source_id: str
    emissions_source: str
    gdp_source: str
    population_source: str
    gini_source: str
    lulucf_source: str
    unit: str

    # --- accounting / normative choices, common to the whole run ------------
    harmonisation_year: int | None
    netting_end_year: int
    pathway_end_year: int
    base_share_floor_mt: float
    # The single §6 distribution setting used (the non-CO2 debt mode is None for
    # non-composite categories, which have no non-CO2 part).
    shape: str
    deviation_end_year: int
    convergence_year: int
    nonco2_debt_mode: str | None
    allocation_folder: str

    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# § 5 — remaining budgets after the last observed emissions year
# ---------------------------------------------------------------------------

# Columns identifying one allocation configuration (part pairing + de-dup).
_ID_COLS = [
    "iso3c",
    "source",
    "climate-assessment",
    "quantile",
    "approach",
    "emission-category",
    "unit",
    "allocation-year",
    "first-allocation-year",
    "preserve-allocation-year-shares",
    "preserve-first-allocation-year-shares",
    "pre-allocation-responsibility-weight",
    "capability-weight",
    "pre-allocation-responsibility-year",
    "pre-allocation-responsibility-per-capita",
    "capability-per-capita",
    "pre-allocation-responsibility-exponent",
    "capability-exponent",
]

# Canonical keys shared by a budget config and its non-CO2 pathway analogue.
# Both parts carry the RCB source, so each budget pairs with its own scenario set.
_PAIR_KEYS = [
    "iso3c",
    "source",
    "climate-assessment",
    "quantile",
    "family",
    "year",
    "preserve",
    "pre-allocation-responsibility-weight",
    "pre-allocation-responsibility-year",
    "pre-allocation-responsibility-per-capita",
    "pre-allocation-responsibility-exponent",
    "capability-weight",
    "capability-exponent",
]


def _country_emissions(processed_dir: Path, part: str) -> pd.DataFrame:
    return pd.read_csv(processed_dir / f"country_emissions_{part}_timeseries.csv")


def _cumulative_actuals(
    processed_dir: Path, part: str, start_year: int, end_year: int | None = None
) -> tuple[pd.Series, int]:
    """Actual emissions per country over the netting window, plus its last year.

    From ``start_year`` through the last observed data year (inclusive), or
    through ``end_year`` when that is earlier. Observed data only -- no
    extrapolation.
    """
    df = _country_emissions(processed_dir, part)
    year_cols = sorted(c for c in df.columns if c.isdigit())
    first_year, last_observed = int(year_cols[0]), int(year_cols[-1])
    if end_year is not None:
        last_observed = min(last_observed, end_year)
    if start_year < first_year:
        raise ValueError(
            f"{part}: data start {first_year} is after allocation year {start_year}"
        )
    window = [str(y) for y in range(start_year, last_observed + 1)]
    consumed = df[window].sum(axis=1)
    return pd.Series(consumed.values, index=df["iso3c"].values), last_observed


def _last_observed_year(processed_dir: Path, part: str) -> int:
    """Last year column of the processed country emissions for ``part``."""
    df = _country_emissions(processed_dir, part)
    return max(int(c) for c in df.columns if c.isdigit())


def compute_remaining_budgets(
    category: str, allocations_absolute: pd.DataFrame, processed_dir: Path
) -> pd.DataFrame:
    """Remaining budget per country after netting observed emissions (§5).

    Budget parts: remaining = allocated total minus actual consumption from the
    allocation year through the netting end year. Non-CO2 pathway parts:
    remaining = the forward-window allocation, with the historical deviation
    (actual minus allocated over the past window) reported separately. Every
    part nets through the last year that all parts observe (2024 for all-ghg).
    For composite categories a ``combined`` row per configuration is added (CO2
    budget part + non-CO2 pathway part), matched on the RCB source, climate
    assessment, quantile and shared equity params.

    Raises
    ------
    ValueError
        If a budget row of a composite category has no non-CO2 pathway row
    """
    ab = allocations_absolute
    year_cols = sorted(c for c in ab.columns if str(c).isdigit())

    # Every part nets through the last year that all parts observe, so a
    # composite category combines its parts over one window.
    netting_end = min(
        _last_observed_year(processed_dir, part)
        for part in ab["emission-category"].unique()
    )

    frames = []
    for part, sub in ab.groupby("emission-category"):
        sub = sub.copy()
        is_budget_part = sub["allocation-year"].notna().all()
        if is_budget_part:
            sub["year"] = sub["allocation-year"].astype(int)
            sub["allocated-total"] = [
                row[str(y)] for y, row in zip(sub["year"], sub.to_dict("records"))
            ]
            sub["preserve"] = sub["preserve-allocation-year-shares"].astype(bool)
        else:
            sub["year"] = sub["first-allocation-year"].astype(int)
            sub["allocated-total"] = sub[year_cols].sum(axis=1)
            sub["preserve"] = sub["preserve-first-allocation-year-shares"].astype(bool)

        for ay, chunk in sub.groupby("year"):
            consumed, last_observed = _cumulative_actuals(
                processed_dir, part, int(ay), netting_end
            )
            idx = chunk.index
            consumed_rows = chunk["iso3c"].map(consumed).to_numpy(dtype=float)
            # Rest of world holds the countries moved into it for this
            # allocation, so it also consumed their observed emissions.
            moved_col = chunk.get("moved-to-row", pd.Series(None, index=idx))
            for i, (iso, moved) in enumerate(zip(chunk["iso3c"], moved_col)):
                if iso == ROW_KEY and isinstance(moved, str) and moved:
                    consumed_rows[i] += (
                        consumed.reindex(moved.split(";")).fillna(0).sum()
                    )
            sub.loc[idx, "consumed-actuals"] = consumed_rows
            sub.loc[idx, "netting-end-year"] = last_observed
        frames.append(sub)

    out = pd.concat(frames, ignore_index=True)
    out["netting-end-year"] = out["netting-end-year"].astype(int)
    out["remaining-from-year"] = out["netting-end-year"] + 1

    out["remaining-budget"] = out["allocated-total"] - out["consumed-actuals"]
    out["historical-deviation"] = float("nan")
    pathway_mask = out["allocation-year"].isna()
    if pathway_mask.any():
        for ne, chunk in out[pathway_mask].groupby("netting-end-year"):
            fwd = [y for y in year_cols if int(y) > int(ne)]
            fwd_sum = out.loc[chunk.index, fwd].sum(axis=1)
            past_alloc = out.loc[chunk.index, "allocated-total"] - fwd_sum
            out.loc[chunk.index, "remaining-budget"] = fwd_sum
            out.loc[chunk.index, "historical-deviation"] = (
                out.loc[chunk.index, "consumed-actuals"] - past_alloc
            )

    out["family"] = out["approach"].str.replace("-budget", "", regex=False)
    out["category"] = category

    keep = [
        "category",
        *[c for c in _ID_COLS if c in out.columns],
        "netting-end-year",
        "remaining-from-year",
        "allocated-total",
        "consumed-actuals",
        "remaining-budget",
        "historical-deviation",
    ]
    if "moved-to-row" in out.columns:
        keep.append("moved-to-row")
    tidy = out[[*keep, "family", "year", "preserve"]].copy()

    parts = tidy["emission-category"].unique()
    if len(parts) > 1:
        if tidy["netting-end-year"].nunique() != 1:
            raise ValueError(
                f"{category}: parts have different last observed years "
                f"({sorted(tidy['netting-end-year'].unique())}) — cannot combine"
            )
        value_cols = ["allocated-total", "consumed-actuals", "remaining-budget"]
        pair_keys = [k for k in _PAIR_KEYS if k in tidy.columns]
        budget_part = tidy[tidy["emission-category"] != "non-co2"]
        pathway_part = tidy[tidy["emission-category"] == "non-co2"]
        _check_parts_moved_same_countries(budget_part, pathway_part, pair_keys)
        merged = budget_part.merge(
            pathway_part[
                pair_keys + value_cols + ["historical-deviation"]
            ].drop_duplicates(pair_keys),
            on=pair_keys,
            how="inner",
            suffixes=("", "-nonco2"),
        )
        combined = merged.copy()
        for col in value_cols:
            combined[col] = combined[col] + combined[f"{col}-nonco2"]
        combined["historical-deviation"] = combined["historical-deviation-nonco2"]
        combined["emission-category"] = "combined"
        combined = combined[tidy.columns]
        if len(combined) != len(budget_part):
            unpaired = budget_part.merge(
                combined[pair_keys], on=pair_keys, how="left", indicator=True
            )
            unpaired = unpaired[unpaired["_merge"] == "left_only"]
            labels = sorted(
                set(
                    zip(
                        unpaired["source"],
                        unpaired["climate-assessment"],
                        unpaired["quantile"],
                    )
                )
            )
            raise ValueError(
                f"{category}: {len(budget_part) - len(combined)} budget rows have "
                f"no non-CO2 pathway (source, climate-assessment, quantile): {labels}"
            )
        tidy = pd.concat([tidy, combined], ignore_index=True)

    return tidy.drop(columns=["family", "year", "preserve"])


# ---------------------------------------------------------------------------
# § 6 — distributing remaining budgets over time
# ---------------------------------------------------------------------------

_CONFIG_COLS = [
    "approach",
    "allocation-year",
    "first-allocation-year",
    "preserve-allocation-year-shares",
    "preserve-first-allocation-year-shares",
    "pre-allocation-responsibility-weight",
    "capability-weight",
    "pre-allocation-responsibility-year",
    "pre-allocation-responsibility-per-capita",
    "capability-per-capita",
    "pre-allocation-responsibility-exponent",
    "capability-exponent",
]


def _moved_sets(part: pd.DataFrame, config_keys: list[str]) -> pd.DataFrame:
    """Collect the countries moved to rest of world per configuration of one part."""
    moved = part["moved-to-row"].fillna("").astype(str)
    return (
        part.assign(_moved=moved)
        .groupby(config_keys, dropna=False)["_moved"]
        .agg(lambda v: ";".join(sorted({c for s in v for c in s.split(";") if c})))
        .reset_index()
    )


def _check_parts_moved_same_countries(
    budget_part: pd.DataFrame, pathway_part: pd.DataFrame, pair_keys: list[str]
) -> None:
    """Raise if a CO2 budget part and its non-CO2 part moved different countries.

    Their combined rest-of-world row would otherwise add two different country
    groups.
    """
    if "moved-to-row" not in budget_part.columns:
        return
    config_keys = [k for k in pair_keys if k != "iso3c"]
    paired = _moved_sets(budget_part, config_keys).merge(
        _moved_sets(pathway_part, config_keys),
        on=config_keys,
        how="inner",
        suffixes=("-co2", "-nonco2"),
    )
    differ = paired[paired["_moved-co2"] != paired["_moved-nonco2"]]
    if not differ.empty:
        row = differ.iloc[0]
        raise AllocationError(
            f"{len(differ)} configuration(s) moved different countries to rest of "
            f"world in the CO2 part ({row['_moved-co2'] or 'none'}) and the "
            f"non-CO2 part ({row['_moved-nonco2'] or 'none'}), so their combined "
            "rest-of-world row would mix two country groups."
        )


def _moved_to_row(cfg: pd.DataFrame) -> list[str]:
    """Countries moved into rest of world for this configuration."""
    if "moved-to-row" not in cfg.columns:
        return []
    values = cfg["moved-to-row"].dropna().unique()
    return sorted({c for v in values if v for c in str(v).split(";")})


def distribute_remaining_pathways(
    category: str,
    allocations_absolute: pd.DataFrame,
    remaining: pd.DataFrame,
    processed_dir: Path,
    *,
    distribution_grid: dict[str, Sequence[Any]],
    pathway_end_year: int,
    base_share_floor_mt: float,
    nonco2_debt_modes: Sequence[str],
) -> pd.DataFrame:
    """Distribute every budget configuration's remaining budget to 2100 (§6).

    Spreads each remaining budget to ``pathway_end_year`` across the
    distribution grid. For composite categories each CO2 configuration is
    distributed under every
    ``nonco2_debt_modes`` entry (``report-only`` leaves the CO2 budget as is;
    ``co2-debit`` subtracts the country's past non-CO2 over-use and retires it),
    and the allocated non-CO2 and ``combined`` rows are appended.
    """
    rem = remaining[
        (remaining["category"] == category)
        & (~remaining["emission-category"].isin(["non-co2", "combined"]))
    ].copy()
    part = rem["emission-category"].iloc[0]
    start_year = int(rem["remaining-from-year"].iloc[0])
    last_observed = str(int(rem["netting-end-year"].iloc[0]))

    emiss = _country_emissions(processed_dir, part)
    base = pd.Series(emiss[last_observed].values, index=emiss["iso3c"].values)
    n_floored = int((base <= 0).sum())
    if n_floored:
        logger.info(
            "%s: %d net-sink countries floored to %s Mt for base-year shares",
            category,
            n_floored,
            base_share_floor_mt,
        )
    base = base.clip(lower=base_share_floor_mt)

    pop = pd.read_csv(processed_dir / "country_population_timeseries.csv")

    config_cols = [c for c in _CONFIG_COLS if c in rem.columns]
    is_composite = category != "co2-ffi"

    dev_lookup = None
    if is_composite:
        dev_lookup = remaining[
            (remaining["category"] == category)
            & (remaining["emission-category"] == "combined")
        ][[*config_cols, "iso3c", "historical-deviation"]]

    out_frames = []
    for _key, cfg in rem.groupby(config_cols, dropna=False):
        budgets = pd.Series(cfg["remaining-budget"].values, index=cfg["iso3c"].values)
        regions = budgets.index
        base_cfg = base.reindex(regions)
        moved = _moved_to_row(cfg)
        if moved and ROW_KEY in base_cfg.index:
            base_cfg[ROW_KEY] += base.reindex(moved).fillna(0.0).sum()
        if base_cfg.isna().any():
            raise ValueError(
                f"{category}: missing base-year emissions for "
                f"{base_cfg[base_cfg.isna()].index.tolist()[:5]}"
            )
        modes = (
            [normalise_nonco2_debt_mode(m) for m in nonco2_debt_modes]
            if is_composite
            else [None]
        )
        for mode in modes:
            if mode == "co2-debit":
                matched = cfg[[*config_cols, "iso3c"]].merge(
                    dev_lookup, on=[*config_cols, "iso3c"], how="left"
                )
                deviation = pd.Series(
                    matched["historical-deviation"].values,
                    index=matched["iso3c"].values,
                ).reindex(regions)
                if deviation.isna().any():
                    raise ValueError(
                        f"{category}: no combined-row deviation match for "
                        "this configuration"
                    )
                debt = deviation.clip(lower=0.0)
            else:
                debt = pd.Series(0.0, index=regions)
            budgets_mode = budgets - debt
            global_pathway = calculate_exponential_decay_pathway(
                total_budget=float(budgets_mode.sum()),
                start_value=float(base_cfg.sum()),
                start_year=start_year,
                end_year=pathway_end_year,
            )
            for conv_year in distribution_grid["convergence_year"]:
                pop_all = pd.Series(
                    pop[str(conv_year)].values, index=pop["iso3c"].values
                )
                pop_cfg = pop_all.reindex(regions)
                if moved and ROW_KEY in pop_cfg.index:
                    pop_cfg[ROW_KEY] += pop_all.reindex(moved).fillna(0.0).sum()
                for shape in distribution_grid["shape"]:
                    for dev_year in distribution_grid["deviation_end_year"]:
                        paths = distribute_remaining_budgets_pathways(
                            base_year_emissions=base_cfg,
                            population=pop_cfg,
                            global_pathway=global_pathway,
                            remaining_budgets=budgets_mode,
                            convergence_year=conv_year,
                            deviation_end_year=dev_year,
                            shape=shape,
                        )
                        paths.columns = [str(c) for c in paths.columns]
                        block = cfg.drop(
                            columns=["allocated-total", "consumed-actuals"]
                        ).set_index("iso3c")
                        block = block.join(paths)
                        block["adjusted-target"] = budgets_mode
                        if mode is not None:
                            block["nonco2-debt-mode"] = mode
                            block["nonco2-debt-paid"] = debt
                        block["shape"] = shape
                        block["deviation-end-year"] = dev_year
                        block["convergence-year"] = conv_year
                        out_frames.append(block.reset_index())

    out = pd.concat(out_frames, ignore_index=True)

    if is_composite:
        nonco2 = allocations_absolute[
            allocations_absolute["emission-category"] == "non-co2"
        ].copy()
        pathway_years = [str(y) for y in range(start_year, pathway_end_year + 1)]
        nonco2["nonco2-forward"] = nonco2[pathway_years].sum(axis=1)
        nd = nonco2.assign(
            family=nonco2["approach"],
            year=nonco2["first-allocation-year"].astype(int),
            preserve=nonco2["preserve-first-allocation-year-shares"].astype(bool),
        )
        pair_cols = [
            "iso3c",
            "source",
            "family",
            "year",
            "preserve",
            "pre-allocation-responsibility-weight",
            "pre-allocation-responsibility-year",
            "pre-allocation-responsibility-per-capita",
            "pre-allocation-responsibility-exponent",
            "capability-weight",
            "capability-exponent",
        ]
        co2_part = out.assign(
            family=out["approach"].str.replace("-budget", "", regex=False),
            year=out["allocation-year"].astype(int),
            preserve=out["preserve-allocation-year-shares"].astype(bool),
        )
        merged = co2_part.merge(
            nd[pair_cols + pathway_years + ["nonco2-forward"]].drop_duplicates(
                pair_cols
            ),
            on=pair_cols,
            how="inner",
            suffixes=("", "-nonco2"),
        )
        for y in pathway_years:
            merged[y] = merged[y] + merged[f"{y}-nonco2"]
        merged["adjusted-target"] = merged["adjusted-target"] + merged["nonco2-forward"]
        combined = merged[list(out.columns)].copy()
        combined["emission-category"] = "combined"
        if len(combined) != len(out):
            logger.info(
                "%s: paired %d/%d distributed rows with a non-CO2 pathway",
                category,
                len(combined),
                len(out),
            )

        nonco2_rows = nonco2.copy()
        nonco2_rows["adjusted-target"] = nonco2_rows["nonco2-forward"]
        past_cols = [
            c for c in nonco2_rows.columns if str(c).isdigit() and int(c) < start_year
        ]
        nonco2_rows = nonco2_rows.drop(columns=["nonco2-forward", *past_cols])

        out = pd.concat([out, nonco2_rows, combined], ignore_index=True)

    out["category"] = category
    return out


# ---------------------------------------------------------------------------
# History (observed emissions), by coverage
# ---------------------------------------------------------------------------


def _coverage_frame(processed_dir: Path, parts: tuple[str, ...]) -> pd.DataFrame:
    frames = [_country_emissions(processed_dir, p).set_index("iso3c") for p in parts]
    year_cols = lambda f: [c for c in f.columns if str(c).isdigit()]  # noqa: E731
    unit = frames[0]["unit"].iloc[0] if "unit" in frames[0] else None
    total = frames[0][year_cols(frames[0])]
    for frame in frames[1:]:
        total = total.add(frame[year_cols(frame)])
    total.insert(0, "unit", unit)
    return total


def build_history(category: str, processed_dir: Path) -> pd.DataFrame:
    """Observed emissions for every coverage this category needs (§5 inputs).

    One frame with a (coverage, unit, iso3c) MultiIndex and year columns. The
    ``combined`` basket is the sum of its parts (NaN where either part lacks a
    year, e.g. the all-ghg basket before the NGHGI CO2 record starts).
    """
    pieces = []
    for cov, parts in COVERAGE_PARTS[category].items():
        frame = _coverage_frame(processed_dir, parts)
        frame = frame.reset_index()
        frame.insert(0, "coverage", cov)
        pieces.append(frame.set_index(["coverage", "unit", "iso3c"]))
    return pd.concat(pieces)


# ---------------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------------


def _filter_to_anchor(
    loaded_data: dict[str, Any],
    rcb_source: str,
    climate_assessment: str,
    quantile: float,
) -> None:
    """Restrict the loaded RCB rows + scenario pathways to the single anchor.

    Filters ``loaded_data`` in place (mirrors notebook 601 §4, Decision 7).
    """
    filter_to_anchors(loaded_data, rcb_source, [(climate_assessment, quantile)])


def filter_to_anchors(
    loaded_data: dict[str, Any],
    rcb_source: str,
    anchors: Sequence[tuple[str, float]],
) -> None:
    """Restrict the loaded RCB rows + scenario pathways to several anchors.

    Each anchor is a ``(climate_assessment, quantile)`` pair of ``rcb_source``,
    e.g. ``("1.7C", 0.67)``. Filters ``loaded_data`` in place.

    Raises
    ------
    ConfigurationError
        If an anchor has no RCB row, or no scenario rows, for a category part
    """
    for cat_key, rdf in loaded_data["rcbs_data"].items():
        keep = pd.Series(False, index=rdf.index)
        for climate_assessment, quantile in anchors:
            hit = (
                (rdf["source"] == rcb_source)
                & (rdf["climate-assessment"] == climate_assessment)
                & (rdf["quantile"] == quantile)
            )
            if not hit.any():
                available = sorted(
                    zip(
                        rdf.loc[rdf["source"] == rcb_source, "climate-assessment"],
                        rdf.loc[rdf["source"] == rcb_source, "quantile"],
                    )
                )
                raise ConfigurationError(
                    f"No RCB row matches source={rcb_source!r}, "
                    f"climate-assessment={climate_assessment!r}, "
                    f"quantile={quantile!r} for {cat_key}. "
                    f"{rcb_source} has: {available}"
                )
            keep |= hit
        loaded_data["rcbs_data"][cat_key] = rdf[keep].reset_index(drop=True)
    for cat_key, sdf in loaded_data["scenarios_data"].items():
        ca = sdf.index.get_level_values("climate-assessment")
        q = sdf.index.get_level_values("quantile")
        keep = pd.Series(False, index=range(len(sdf))).to_numpy()
        for climate_assessment, quantile in anchors:
            hit = (ca == climate_assessment) & (q == quantile)
            if "source" in sdf.index.names:
                hit &= sdf.index.get_level_values("source") == rcb_source
            if not hit.any():
                raise ConfigurationError(
                    f"No scenario rows match source={rcb_source!r}, "
                    f"climate-assessment={climate_assessment!r}, "
                    f"quantile={quantile!r} for {cat_key}"
                )
            keep |= hit
        loaded_data["scenarios_data"][cat_key] = sdf[keep]


# ---------------------------------------------------------------------------
# One region of countries (notebook 405)
# ---------------------------------------------------------------------------

_REMAINING_VALUE_COLS = [
    "allocated-total",
    "consumed-actuals",
    "remaining-budget",
    "historical-deviation",
]


def _sum_members(
    df: pd.DataFrame,
    countries: Sequence[str],
    region: str,
    group_cols: list[str],
    value_cols: list[str],
) -> pd.DataFrame:
    """Sum ``value_cols`` over the member rows of ``df``, per ``group_cols``.

    Raises
    ------
    ValueError
        If a member has no row, a member was moved into the rest of world (ROW)
        for some configuration, two rows of one member share every grouping
        column, or a configuration lacks some members
    """
    countries = list(dict.fromkeys(countries))
    present = set(df["iso3c"])
    missing = [c for c in countries if c not in present]
    if missing:
        raise ValueError(
            f"{region}: no allocation rows for {missing}. Check the ISO3 codes; "
            "a country without data is aggregated into ROW."
        )
    if "moved-to-row" in df.columns:
        moved = set()
        for entry in df["moved-to-row"].dropna():
            if isinstance(entry, str) and entry:
                moved.update(entry.split(";"))
        clash = sorted(moved.intersection(countries))
        if clash:
            raise ValueError(
                f"{region}: {clash} were moved into ROW for some configuration, "
                "so their allocation is not in their own row."
            )

    members = df[df["iso3c"].isin(countries)]
    # compute_remaining_budgets keeps a fixed set of identifying columns, so
    # two configurations that differ only in a parameter outside it (e.g.
    # cumulative_end_year, a functional form) share every column here and
    # would be summed together.
    dupes = members.duplicated([*group_cols, "iso3c"], keep=False)
    if dupes.any():
        raise ValueError(
            f"{region}: {int(dupes.sum())} rows share every identifying column "
            "with another row. The allocation grid varies a parameter that "
            "compute_remaining_budgets does not keep (e.g. cumulative_end_year, "
            "a functional form, capability_reference_year); run one value of "
            "that parameter at a time."
        )
    grouped = members.groupby(group_cols, dropna=False)
    out = grouped[value_cols].sum(min_count=1)
    out["n-countries"] = grouped["iso3c"].nunique()
    out = out.reset_index()
    incomplete = out[out["n-countries"] != len(countries)]
    if not incomplete.empty:
        raise ValueError(
            f"{region}: {len(incomplete)} configurations lack some members' rows"
        )
    out.insert(out.columns.get_loc(group_cols[0]) + 1, "iso3c", region)
    return out


def regional_remaining_budgets(
    remaining: pd.DataFrame, countries: Sequence[str], region: str
) -> pd.DataFrame:
    """Sum the remaining budgets of ``countries`` into one ``region`` row.

    ``remaining`` is the output of :func:`compute_remaining_budgets`. One row
    is returned per configuration (anchor, approach, parameters, emission
    part), with ``iso3c`` set to ``region`` and ``n-countries`` the number of
    members summed.

    Raises
    ------
    ValueError
        As :func:`_sum_members`; a member moved into ROW has its allocation
        inside ROW, so the region sum would miss it
    """
    value_cols = [c for c in _REMAINING_VALUE_COLS if c in remaining.columns]
    group_cols = [
        c for c in remaining.columns if c not in (*value_cols, "iso3c", "moved-to-row")
    ]
    return _sum_members(remaining, countries, region, group_cols, value_cols)


def _pair_frame(df: pd.DataFrame, *, budget: bool) -> pd.DataFrame:
    """Add the columns that pair a CO2 budget with its non-CO2 pathway.

    The columns are ``family``, ``year`` and ``preserve``.
    """
    if budget:
        return df.assign(
            family=df["approach"].str.replace("-budget", "", regex=False),
            year=df["allocation-year"].astype(int),
            preserve=df["preserve-allocation-year-shares"].astype(bool),
        )
    return df.assign(
        family=df["approach"],
        year=df["first-allocation-year"].astype(int),
        preserve=df["preserve-first-allocation-year-shares"].astype(bool),
    )


def regional_targets(
    remaining: pd.DataFrame,
    allocations_absolute: pd.DataFrame,
    countries: Sequence[str],
    region: str,
    nonco2_debt_modes: Sequence[str] = NONCO2_DEBT_MODES,
) -> pd.DataFrame:
    """Return the CO2 budget and non-CO2 pathway of one region, per configuration.

    One row per configuration (and, for composite categories, per non-CO2 debt
    mode). ``remaining-budget`` is the region's CO2 budget after observed
    emissions (the CO2 part of :func:`compute_remaining_budgets`, summed over
    ``countries``). For composite categories the row also carries:

    * ``nonco2-overuse``: the members' past non-CO2 over-use, summed over the
      members that over-used (under-use earns nothing, as in
      :func:`distribute_remaining_pathways`);
    * ``nonco2-debt-mode`` and ``nonco2-debt-paid``: ``co2-debit`` charges the
      over-use against ``co2-budget``; ``report-only`` charges nothing;
    * year columns: the region's annual non-CO2 allocation (the members' sum),
      for every allocated year; :func:`shift_to_period_start` trims them to
      the model's first period.

    ``co2-budget`` is ``remaining-budget`` minus ``nonco2-debt-paid``.

    Raises
    ------
    ValueError
        As :func:`regional_remaining_budgets`, or if a CO2 configuration has no
        single non-CO2 pathway
    """
    co2 = remaining[~remaining["emission-category"].isin(["non-co2", "combined"])]
    budgets = regional_remaining_budgets(co2, countries, region)
    if not (remaining["emission-category"] == "combined").any():
        budgets["nonco2-debt-mode"] = None
        budgets["nonco2-debt-paid"] = 0.0
        budgets["co2-budget"] = budgets["remaining-budget"]
        return budgets

    # Over-use per member: the combined rows carry each member's non-CO2
    # deviation, clipped before summing so one member's under-use does not
    # offset another's over-use.
    combined = remaining[remaining["emission-category"] == "combined"].copy()
    combined["historical-deviation"] = combined["historical-deviation"].clip(lower=0)
    overuse = regional_remaining_budgets(combined, countries, region)
    key = [
        c
        for c in budgets.columns
        if c not in (*_REMAINING_VALUE_COLS, "n-countries", "emission-category")
    ]
    budgets = budgets.drop(columns="historical-deviation").merge(
        overuse[[*key, "historical-deviation"]].rename(
            columns={"historical-deviation": "nonco2-overuse"}
        ),
        on=key,
        how="left",
        validate="one_to_one",
    )

    # Region's non-CO2 pathway per configuration, paired to its CO2 budget.
    nonco2 = allocations_absolute[
        allocations_absolute["emission-category"] == "non-co2"
    ]
    year_cols = [c for c in nonco2.columns if str(c).isdigit()]
    id_cols = [c for c in _ID_COLS if c in nonco2.columns and c != "iso3c"]
    nonco2_region = _sum_members(nonco2, countries, region, id_cols, year_cols)
    budgets_p = _pair_frame(budgets, budget=True)
    nonco2_p = _pair_frame(nonco2_region, budget=False)
    pair_keys = [
        k
        for k in _PAIR_KEYS
        if k != "iso3c" and k in budgets_p.columns and k in nonco2_p.columns
    ]
    paired = budgets_p.merge(
        nonco2_p[[*pair_keys, *year_cols]],
        on=pair_keys,
        how="left",
        validate="one_to_one",
    )
    if paired[year_cols].isna().all(axis=1).any():
        raise ValueError(f"{region}: a CO2 configuration has no non-CO2 pathway")
    keep_years = list(year_cols)
    paired = paired.drop(columns=["family", "year", "preserve"])

    frames = []
    for mode in nonco2_debt_modes:
        mode = normalise_nonco2_debt_mode(mode)
        block = paired.copy()
        block["nonco2-debt-mode"] = mode
        block["nonco2-debt-paid"] = (
            block["nonco2-overuse"] if mode == "co2-debit" else 0.0
        )
        frames.append(block)
    out = pd.concat(frames, ignore_index=True)
    out["co2-budget"] = out["remaining-budget"] - out["nonco2-debt-paid"]
    lead = [c for c in out.columns if not str(c).isdigit()]
    return out[[*lead, *keep_years]]


def regional_observed_emissions(
    processed_dir: Path, part: str, countries: Sequence[str]
) -> pd.Series:
    """Observed emissions of ``part`` summed over ``countries``, by year.

    Read from the processed country emissions of the run (Mt per year).

    Raises
    ------
    ValueError
        If a member has no row
    """
    df = _country_emissions(processed_dir, part).set_index("iso3c")
    missing = [c for c in countries if c not in df.index]
    if missing:
        raise ValueError(f"No observed {part} emissions for {missing}")
    years = [c for c in df.columns if str(c).isdigit()]
    series = df.loc[list(countries), years].astype(float).sum(min_count=1)
    series.index = series.index.astype(int)
    return series.dropna()


def shift_to_period_start(
    regional: pd.DataFrame,
    period_start: int,
    observed: pd.Series,
) -> pd.DataFrame:
    """Express a region's CO2 budget from the first year of a model period.

    :func:`compute_remaining_budgets` nets observed emissions through the last
    observed year, so the budget runs from the year after it
    (``remaining-from-year``). A model's first period may start elsewhere:

    * earlier: the region's observed emissions from ``period_start`` up to
      ``remaining-from-year`` fall inside the model's first period, so they are
      added back;
    * later: the region's emissions from ``remaining-from-year`` up to
      ``period_start`` fall before the model, so they are subtracted. They are
      not observed; each takes the last observed year's value.

    ``observed`` is the region's emissions of the budget's part by year
    (:func:`regional_observed_emissions`). The change applies to
    ``remaining-budget`` and, when present, ``co2-budget``, and is recorded in
    ``start-adjustment`` (Mt, positive = added) and
    ``start-adjustment-estimated-years`` (the years held at the last observed
    value). Year columns (a non-CO2 pathway) before ``period_start`` are
    dropped. ``remaining-from-year`` becomes ``period_start``.

    Raises
    ------
    ValueError
        If ``observed`` lacks a year that must be added back
    """
    out = regional.copy()
    budget_cols = [c for c in ("remaining-budget", "co2-budget") if c in out.columns]
    observed = observed.copy()
    observed.index = observed.index.astype(int)
    last_year = int(observed.index.max())
    out["start-adjustment"] = 0.0
    out["start-adjustment-estimated-years"] = ""
    for from_year, idx in out.groupby("remaining-from-year").groups.items():
        from_year = int(from_year)
        if period_start < from_year:
            years = list(range(period_start, from_year))
            lacking = [y for y in years if y not in observed.index]
            if lacking:
                raise ValueError(f"No observed regional emissions for {lacking}")
            adjustment = float(observed.loc[years].sum())
            estimated = []
        else:
            years = list(range(from_year, period_start))
            estimated = [y for y in years if y > last_year]
            values = [
                observed.loc[y] if y <= last_year else observed.loc[last_year]
                for y in years
            ]
            adjustment = -float(sum(values))
        out.loc[idx, "start-adjustment"] = adjustment
        out.loc[idx, "start-adjustment-estimated-years"] = ";".join(
            str(y) for y in estimated
        )
        for col in budget_cols:
            out.loc[idx, col] = out.loc[idx, col] + adjustment
        out.loc[idx, "remaining-from-year"] = period_start
    early = [c for c in out.columns if str(c).isdigit() and int(c) < period_start]
    return out.drop(columns=early)


def period_means(
    annual: pd.DataFrame, model_years: Sequence[int], first_year: int
) -> pd.DataFrame:
    """Average annual year columns over a model's periods.

    Each period is labelled by its last year, as IAM timesteps are: label
    ``model_years[i]`` covers the years after ``model_years[i-1]`` through
    itself, and the first label covers ``first_year`` through itself. Columns
    that are not years are kept.

    Raises
    ------
    ValueError
        If the labels are not increasing, the first label is before
        ``first_year``, or a period year has no column
    """
    model_years = [int(y) for y in model_years]
    if model_years != sorted(set(model_years)):
        raise ValueError(f"model_years must be increasing: {model_years}")
    if model_years[0] < first_year:
        raise ValueError(
            f"First model year {model_years[0]} is before the pathway start "
            f"{first_year}"
        )
    lead = [c for c in annual.columns if not str(c).isdigit()]
    out = annual[lead].copy()
    starts = [first_year, *[y + 1 for y in model_years[:-1]]]
    for start, label in zip(starts, model_years):
        cols = [str(y) for y in range(start, label + 1)]
        lacking = [c for c in cols if c not in annual.columns]
        if lacking:
            raise ValueError(f"Period ending {label} lacks years {lacking}")
        out[str(label)] = annual[cols].mean(axis=1)
    return out


def member_targets(
    remaining: pd.DataFrame,
    allocations_absolute: pd.DataFrame,
    countries: Sequence[str],
    processed_dir: Path,
    part: str,
    period_start: int,
    nonco2_debt_modes: Sequence[str] = NONCO2_DEBT_MODES,
) -> pd.DataFrame:
    """Return the targets of each member of a region, from ``period_start``.

    Each member is a region of one country: :func:`regional_targets` and
    :func:`shift_to_period_start` run per member, with the member's own
    observed emissions of ``part``, so the members sum to the region. ``iso3c``
    is the member's code.

    Raises
    ------
    ValueError
        As :func:`regional_targets` and :func:`shift_to_period_start`
    """
    frames = []
    for iso in countries:
        targets = regional_targets(
            remaining, allocations_absolute, [iso], iso, nonco2_debt_modes
        )
        observed = regional_observed_emissions(processed_dir, part, [iso])
        frames.append(shift_to_period_start(targets, period_start, observed))
    return pd.concat(frames, ignore_index=True)


LAND_USE_OBSERVED_YEARS: tuple[int, int] = (2020, 2024)
"""First and last year of the observed land-use CO2 in :func:`land_use_condition`."""


def _observed_stats(series: pd.Series, prefix: str) -> dict[str, float]:
    return {
        f"{prefix}-median": float(series.median()),
        f"{prefix}-min": float(series.min()),
        f"{prefix}-max": float(series.max()),
    }


def land_use_condition(
    targets: pd.DataFrame,
    remaining: pd.DataFrame,
    rcbs: pd.DataFrame,
    areas: dict[str, Sequence[str]],
    bookkeeping_dir: Path,
    inventory_dir: Path,
    observed_years: tuple[int, int] = LAND_USE_OBSERVED_YEARS,
) -> pd.DataFrame:
    """Return the land-use CO2 under which a fossil-only budget is a fair share.

    A ``co2-ffi`` budget removes the projected global land-use CO2 from the
    budget's baseline year to net zero (bookkeeping basis; 0 when the
    precautionary cap sets a projected sink to zero). An area's fossil budget
    holds only if its own land-use CO2 over those years nets to at most its
    share of that term (``land-allowance-mt``): its share of the global
    allocation times the term. A net source above the allowance comes off the
    fossil budget; a sink beyond it is not counted.

    One row per row of ``targets`` (``iso3c`` names the area, a key of
    ``areas``). Columns:

    * ``land-term-removed-mt``: the global term the budget removed (Mt);
    * ``land-share`` and ``land-allowance-mt``: the area's share of the global
      allocation and its allowance, cumulative from ``land-from-year`` to
      ``land-to-year`` (the set's median net-zero year), and per year;
    * observed land-use CO2 over ``observed_years`` (Mt/yr, median, min, max)
      on the bookkeeping basis (``bookkeeping_dir``), the inventory basis
      (``inventory_dir``), and their difference ``indirect-gap`` (inventory
      minus bookkeeping: mostly indirect uptake, which the global budget
      counts as part of the climate response);
    * ``inventory-equivalent``: the allowance per year plus the indirect gap,
      the inventory land-use CO2 (Mt/yr) that meets the allowance.

    ``bookkeeping_dir`` and ``inventory_dir`` are processed directories of two
    ``co2`` runs, with country ``co2-lulucf`` series on each basis.

    Raises
    ------
    ValueError
        If a budget of ``targets`` has no row in ``rcbs``, a configuration has
        no global allocation, or a member has no observed land-use CO2 in a
        year of ``observed_years``
    """
    co2 = remaining[~remaining["emission-category"].isin(["non-co2", "combined"])]
    value_cols = [c for c in _REMAINING_VALUE_COLS if c in co2.columns]
    # remaining-from-year is left out: shift_to_period_start rewrites it
    group_cols = [
        c
        for c in co2.columns
        if c not in (*value_cols, "iso3c", "moved-to-row", "remaining-from-year")
        and c in targets.columns
    ]
    world = (
        co2.groupby(group_cols, dropna=False)["allocated-total"]
        .sum()
        .rename("world-allocated-total")
        .reset_index()
    )
    out = targets.merge(world, on=group_cols, how="left", validate="many_to_one")
    if out["world-allocated-total"].isna().any():
        raise ValueError("A configuration of targets has no global allocation")

    budget_keys = ["source", "climate-assessment", "quantile"]
    budget_terms = rcbs[[*budget_keys, "baseline_year", "nz_year_median"]].assign(
        **{"land-term-removed-mt": -rcbs["deduction_lulucf_future_mt"]}
    )
    out = out.merge(budget_terms, on=budget_keys, how="left", validate="many_to_one")
    if out["baseline_year"].isna().any():
        raise ValueError("A budget of targets has no row in rcbs")

    out["land-share"] = out["allocated-total"] / out["world-allocated-total"]
    out["land-allowance-mt"] = out["land-share"] * out["land-term-removed-mt"]
    out["land-from-year"] = out["baseline_year"].astype(int)
    out["land-to-year"] = out["nz_year_median"]
    years = out["land-to-year"] - out["land-from-year"]
    out["land-allowance-mt-per-yr"] = out["land-allowance-mt"] / years

    first, last = observed_years
    window = list(range(first, last + 1))
    stats = {}
    for area, countries in areas.items():
        bases = {}
        for name, processed_dir in (
            ("bookkeeping", bookkeeping_dir),
            ("inventory", inventory_dir),
        ):
            series = regional_observed_emissions(processed_dir, "co2-lulucf", countries)
            lacking = [y for y in window if y not in series.index]
            if lacking:
                raise ValueError(
                    f"No observed {name} land-use CO2 for {area} in {lacking}"
                )
            bases[name] = series.loc[window]
        gap = bases["inventory"] - bases["bookkeeping"]
        stats[area] = {
            **_observed_stats(bases["bookkeeping"], "bookkeeping-observed"),
            **_observed_stats(bases["inventory"], "inventory-observed"),
            **_observed_stats(gap, "indirect-gap"),
        }
    observed = pd.DataFrame.from_dict(stats, orient="index")
    out = out.join(observed, on="iso3c")
    for stat in ("median", "min", "max"):
        out[f"inventory-equivalent-{stat}"] = (
            out["land-allowance-mt-per-yr"] + out[f"indirect-gap-{stat}"]
        )
    out["land-observed-years"] = f"{first}-{last}"
    return out.drop(
        columns=["world-allocated-total", "baseline_year", "nz_year_median"]
    )


def calculate_allocation_timeseries(
    *,
    emission_category: str,
    climate_assessment: str,
    quantile: float,
    rcb_source: str,
    allocation: dict[str, dict[str, Any]],
    shape: str,
    deviation_end_year: int,
    convergence_year: int,
    nonco2_debt_mode: str | None,
    pathway_end_year: int,
    base_share_floor_mt: float,
    desired_harmonisation_year: int,
    emissions_source: str,
    gdp_source: str,
    population_source: str,
    gini_source: str,
    lulucf_source: str,
    allocation_folder: str,
    project_root: Path | None = None,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> ResultContainer:
    """Compute the distributed allocation timeseries for one (anchor, category).

    Runs §4 (budget allocation, in memory), §5 (remaining budget) and §6 (time
    distribution) for a *single* fully-specified allocation, under the single
    RCB anchor ``(rcb_source, climate_assessment, quantile)``. Loop over
    allocations / distributions / debt modes around this function to build a
    fuller set. No files are written and no notebook is executed; every input is
    explicit (wrap this with your own defaults if desired).

    Parameters
    ----------
    allocation
        One approach mapped to its scalar parameters, e.g.
        ``{"equal-per-capita-budget": {"allocation_year": 2015,
        "preserve_allocation_year_shares": True}}``.
    shape, deviation_end_year, convergence_year
        The single §6 distribution setting (debt-redress envelope shape, the
        year it closes, and the per-capita convergence year).
    nonco2_debt_mode
        The single non-CO2 debt-settlement mode (``"report-only"`` /
        ``"co2-debit"``) for composite categories; must be ``None`` for
        ``co2-ffi`` (which has no non-CO2 part). ``"free-rider"`` is a
        deprecated alias of ``"report-only"``.
    project_root
        Deprecated. Superseded by ``data_dir`` and ``output_dir``, onto which
        it maps as ``project_root/"data"`` and ``project_root/"output"``.
    data_dir, output_dir
        Input and product directories. Both default to the resolved
        directories — see :mod:`fair_shares.library.paths`.
    """
    if project_root is not None:
        data_dir, output_dir = _deprecate_project_root(
            project_root, data_dir, output_dir, "calculate_allocation_timeseries"
        )
    # Seed before the first validation call — config validation resolves the
    # config's relative data paths, well below anywhere these can be threaded.
    configure(data_dir=data_dir, output_dir=output_dir)
    is_composite = is_composite_category(emission_category)
    if is_composite and nonco2_debt_mode is None:
        raise ValueError(
            f"nonco2_debt_mode is required for composite category {emission_category!r}"
        )
    if not is_composite and nonco2_debt_mode is not None:
        raise ValueError(
            f"nonco2_debt_mode must be None for non-composite category "
            f"{emission_category!r} (got {nonco2_debt_mode!r})"
        )
    if nonco2_debt_mode is not None:
        nonco2_debt_mode = normalise_nonco2_debt_mode(nonco2_debt_mode)
    if len(allocation) != 1:
        raise ValueError(
            f"allocation must specify exactly one approach, got {list(allocation)}"
        )
    ((approach, params),) = allocation.items()
    # Expand the single allocation / distribution to the grid forms the run and
    # distribution helpers expect; each expands to exactly one combination.
    allocations_grid = {approach: [{k: [v] for k, v in params.items()}]}
    distribution_grid = {
        "shape": [shape],
        "deviation_end_year": [deviation_end_year],
        "convergence_year": [convergence_year],
    }
    nonco2_debt_modes = [nonco2_debt_mode]

    active_sources = {
        "target": TARGET,
        "emissions": emissions_source,
        "gdp": gdp_source,
        "population": population_source,
        "gini": gini_source,
        "lulucf": lulucf_source,
    }

    validation = validate_data_source_config(emission_category, active_sources)
    if not validation["valid"]:
        raise ConfigurationError(
            "Configuration errors:\n"
            + "\n".join(f"  - {i}" for i in validation["issues"])
        )

    harmonisation_year = desired_harmonisation_year if is_composite else None

    setup_info = setup_data(
        emission_category=emission_category,
        active_sources=active_sources,
        harmonisation_year=harmonisation_year,
        verbose=False,
        data_dir=data_dir,
        output_dir=output_dir,
    )
    source_id = setup_info["source_id"]
    processed_dir = setup_info["paths"]["processed_dir"]
    final_categories = setup_info["final_categories"]
    resolved_category = setup_info["emission_category"]

    loaded_data = load_allocation_data(
        processed_dir=processed_dir,
        target=TARGET,
        final_categories=final_categories,
        emission_category=resolved_category,
    )
    _filter_to_anchor(loaded_data, rcb_source, climate_assessment, quantile)

    data_context = {
        "source-id": source_id,
        "allocation-folder": allocation_folder,
        "emission-category": resolved_category,
        "target-source": TARGET,
        "emissions-source": emissions_source,
        "gdp-source": gdp_source,
        "population-source": population_source,
        "gini-source": gini_source,
        "lulucf-source": lulucf_source,
    }

    _manifest, allocations_absolute = run_all_allocations(
        allocations=allocations_grid,
        loaded_data=loaded_data,
        output_dir=None,
        data_context=data_context,
        target=TARGET,
        final_categories=final_categories,
        harmonisation_year=setup_info["config"].harmonisation_year,
        write=False,
        return_allocations=True,
    )

    remaining = compute_remaining_budgets(
        emission_category, allocations_absolute, processed_dir
    )
    distributed = distribute_remaining_pathways(
        emission_category,
        allocations_absolute,
        remaining,
        processed_dir,
        distribution_grid=distribution_grid,
        pathway_end_year=pathway_end_year,
        base_share_floor_mt=base_share_floor_mt,
        nonco2_debt_modes=nonco2_debt_modes,
    )
    history = build_history(emission_category, processed_dir)

    netting_end_year = int(remaining["netting-end-year"].iloc[0])
    units = sorted({str(u) for u in distributed["unit"].dropna().unique()})
    if len(units) != 1:
        raise ConfigurationError(f"expected one unit, got {units}")

    index_cols = [c for c in distributed.columns if not str(c).isdigit()]
    allocation_timeseries = distributed.set_index(index_cols)

    return ResultContainer(
        allocation_timeseries=allocation_timeseries,
        history=history,
        emission_category=resolved_category,
        climate_assessment=climate_assessment,
        quantile=quantile,
        rcb_source=rcb_source,
        source_id=source_id,
        emissions_source=emissions_source,
        gdp_source=gdp_source,
        population_source=population_source,
        gini_source=gini_source,
        lulucf_source=lulucf_source,
        unit=units[0],
        harmonisation_year=setup_info["config"].harmonisation_year,
        netting_end_year=netting_end_year,
        pathway_end_year=pathway_end_year,
        base_share_floor_mt=base_share_floor_mt,
        shape=shape,
        deviation_end_year=deviation_end_year,
        convergence_year=convergence_year,
        nonco2_debt_mode=nonco2_debt_mode,
        allocation_folder=allocation_folder,
        metadata={},
    )


def save_results(results: ResultContainer, outpath: Path) -> Path:
    """Persist a :class:`ResultContainer` under ``outpath`` (created if needed).

    Writes ``allocation_timeseries.parquet``, ``history.parquet``, a
    ``metadata.json`` of every scalar attribute, and ``CITATIONS.md`` listing
    the software and the data sources this run used. Returns ``outpath``.
    """
    outpath = Path(outpath)
    outpath.mkdir(parents=True, exist_ok=True)
    results.allocation_timeseries.to_parquet(outpath / "allocation_timeseries.parquet")
    results.history.to_parquet(outpath / "history.parquet")

    scalar_meta = {
        "emission-category": results.emission_category,
        "climate-assessment": results.climate_assessment,
        "quantile": results.quantile,
        "rcb-source": results.rcb_source,
        "source-id": results.source_id,
        "emissions-source": results.emissions_source,
        "gdp-source": results.gdp_source,
        "population-source": results.population_source,
        "gini-source": results.gini_source,
        "lulucf-source": results.lulucf_source,
        "unit": results.unit,
        "harmonisation-year": results.harmonisation_year,
        "netting-end-year": results.netting_end_year,
        "pathway-end-year": results.pathway_end_year,
        "base-share-floor-mt": results.base_share_floor_mt,
        "shape": results.shape,
        "deviation-end-year": results.deviation_end_year,
        "convergence-year": results.convergence_year,
        "nonco2-debt-mode": results.nonco2_debt_mode,
        "allocation-folder": results.allocation_folder,
        **results.metadata,
    }
    (outpath / "metadata.json").write_text(json.dumps(scalar_meta, indent=2) + "\n")

    # Written alongside the results so a saved run always says what to cite.
    write_citations_file(
        outpath,
        active_sources_from_context(
            {
                "target-source": TARGET,
                "emissions-source": results.emissions_source,
                "gdp-source": results.gdp_source,
                "population-source": results.population_source,
                "gini-source": results.gini_source,
                "lulucf-source": results.lulucf_source,
            }
        ),
        emission_category=results.emission_category,
    )
    return outpath
