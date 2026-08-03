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
this module only ports the notebook's §5/§6 orchestration and the historical
coverage bookkeeping, and ties it together per (anchor, category).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from fair_shares.library.citations import (
    active_sources_from_context,
    write_citations_file,
)
from fair_shares.library.exceptions import ConfigurationError
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
# "source" is excluded: budget parts carry the RCB source, the non-CO2 part the
# scenario source; parts pair on climate assessment + quantile.
_PAIR_KEYS = [
    "iso3c",
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
    processed_dir: Path, part: str, start_year: int
) -> tuple[pd.Series, int]:
    """Actual emissions per country over the netting window, plus its last year.

    From ``start_year`` through the last observed data year (inclusive).
    Observed data only -- no extrapolation.
    """
    df = _country_emissions(processed_dir, part)
    year_cols = sorted(c for c in df.columns if c.isdigit())
    first_year, last_observed = int(year_cols[0]), int(year_cols[-1])
    if start_year < first_year:
        raise ValueError(
            f"{part}: data start {first_year} is after allocation year {start_year}"
        )
    window = [str(y) for y in range(start_year, last_observed + 1)]
    consumed = df[window].sum(axis=1)
    return pd.Series(consumed.values, index=df["iso3c"].values), last_observed


def compute_remaining_budgets(
    category: str, allocations_absolute: pd.DataFrame, processed_dir: Path
) -> pd.DataFrame:
    """Remaining budget per country after netting observed emissions (§5).

    Budget parts: remaining = allocated total minus actual consumption from the
    allocation year through the last observed year. Non-CO2 pathway parts:
    remaining = the forward-window allocation, with the historical deviation
    (actual minus allocated over the past window) reported separately. For
    composite categories a ``combined`` row per configuration is added (CO2
    budget part + non-CO2 pathway part), matched on the shared equity params.
    """
    ab = allocations_absolute
    year_cols = sorted(c for c in ab.columns if str(c).isdigit())

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
            consumed, last_observed = _cumulative_actuals(processed_dir, part, int(ay))
            idx = chunk.index
            sub.loc[idx, "consumed-actuals"] = chunk["iso3c"].map(consumed).values
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
            logger.info(
                "%s: paired %d/%d budget rows with a non-CO2 analogue",
                category,
                len(combined),
                len(budget_part),
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
    ``nonco2_debt_modes`` entry (``free-rider`` leaves the CO2 budget as is;
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
        if base_cfg.isna().any():
            raise ValueError(
                f"{category}: missing base-year emissions for "
                f"{base_cfg[base_cfg.isna()].index.tolist()[:5]}"
            )
        modes = list(nonco2_debt_modes) if is_composite else [None]
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
                pop_cfg = pd.Series(
                    pop[str(conv_year)].values, index=pop["iso3c"].values
                ).reindex(regions)
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
    anchor = {
        "source": rcb_source,
        "climate-assessment": climate_assessment,
        "quantile": quantile,
    }
    for cat_key, rdf in loaded_data["rcbs_data"].items():
        loaded_data["rcbs_data"][cat_key] = rdf[
            (rdf["source"] == rcb_source)
            & (rdf["climate-assessment"] == climate_assessment)
            & (rdf["quantile"] == quantile)
        ].reset_index(drop=True)
        if loaded_data["rcbs_data"][cat_key].empty:
            raise ConfigurationError(f"No RCB row matches {anchor} for {cat_key}")
    for cat_key, sdf in loaded_data["scenarios_data"].items():
        mask = (
            sdf.index.get_level_values("climate-assessment") == climate_assessment
        ) & (sdf.index.get_level_values("quantile") == quantile)
        loaded_data["scenarios_data"][cat_key] = sdf[mask]
        if loaded_data["scenarios_data"][cat_key].empty:
            raise ConfigurationError(f"No scenario rows match {anchor} for {cat_key}")


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
        The single non-CO2 debt-settlement mode (``"free-rider"`` /
        ``"co2-debit"``) for composite categories; must be ``None`` for
        ``co2-ffi`` (which has no non-CO2 part).
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
