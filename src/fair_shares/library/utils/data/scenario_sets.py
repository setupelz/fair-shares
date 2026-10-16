"""
Role-matched scenario sets behind the scenario-derived budget terms.

A remaining carbon budget is the cumulative net CO2 from its start year to
net-zero CO2, at a stated warming and likelihood. Each scenario-derived term
of a budget comes from the set that matches its role:

- volume-matched set (land-use deduction, convention gap, bunker window):
  scenarios that reach net-zero CO2 by 2100 and whose cumulative net CO2 from
  2020 to net zero lies within ``volume_tolerance_gt`` of the budget expressed
  from the start of 2020
- temperature-matched set (non-CO2 pathway): scenarios that reach net-zero CO2
  and whose median warming at net zero lies in [T - w, T + w), for every
  likelihood, because published budgets assume the median non-CO2 warming of
  scenarios at T
- AR6 category pool (rule "ar6-category"): the AR6 category paired with the
  label, for every term
- bunker share: bunkers after the last observed year are a share of the net
  CO2 of the volume-matched set. The share is the median, over the scenarios
  of the configured sources that report international aviation and shipping
  and reach net zero, of cumulative bunkers over cumulative net CO2 from the
  year after the last observed year to each reporter's net zero

Cumulatives follow the accounting of ``rcb.integrate``: full years from the
start year plus the fraction of the net-zero year.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import pandas as pd

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError
from fair_shares.library.utils.data.rcb import (
    AR6_CATEGORY_BY_RCB_LABEL,
    canonical_scenarios,
    cumulative_to_net_zero,
    integrate,
    label_temperature,
    net_zero_crossing,
    parse_rcb_scenario,
    resolve_scenario_selection,
)
from fair_shares.library.utils.units import get_default_unit_registry

NET_ZERO_CROSSING = "net_zero_crossing"
CUMULATIVE_CO2 = "cumulative_co2_to_net_zero_gt"
REPORTS_BUNKERS = "reports_bunkers"

DEFAULT_VOLUME_TOLERANCE_GT = 50.0
DEFAULT_MIN_SCENARIOS = 10
DEFAULT_TEMPERATURE_HALF_WIDTH = 0.05
DEFAULT_BUNKER_MIN_REPORTERS = 10
DEFAULT_BUNKER_MIN_FAMILIES = 3
DEFAULT_BUNKER_MIN_RUNS_PER_FAMILY = 3
# Start years of the bunker-share window (the year after the last observed bunker year).
SHARE_START_YEARS = tuple(range(2021, 2032))
DEFAULT_BUNKER_SOURCES = ("ar6", "sci", "scenariomip")
DEFAULT_NON_CO2_SOURCES = ("ar6",)
DEFAULT_OBSERVED_CO2_PATH = (
    "data/emissions/gcb-2025/Global_Carbon_Budget_2025_v1.0.xlsx"
)

LIKELIHOOD_SCOPES = ("tcre-only", "tcre-zec-esf")
BUDGET_METRICS = ("warming-at-net-zero", "peak-warming")


@dataclass(frozen=True)
class BudgetSpec:
    """One budget of rcbs.yaml, under its current label."""

    source: str
    label: str
    published_label: str
    baseline_year: int
    value_gt: float
    temperature: float
    likelihood: float
    likelihood_scope: str | None
    budget_metric: str | None
    rule: str

    @property
    def key(self) -> str:
        """Key of the budget in rcb_scenario_adjustments.yaml."""
        return f"{self.source}:{self.label}"

    @property
    def file_key(self) -> str:
        """Key of the budget in the names of the per-budget files."""
        return f"{self.source}_{self.label}"

    @property
    def category(self) -> str | None:
        """AR6 category of the budget, or None under the role-matched sets."""
        if self.rule == "ar6-category":
            return AR6_CATEGORY_BY_RCB_LABEL.get(self.label)
        return None


def _to_gt(value: float, unit: str) -> float:
    ureg = get_default_unit_registry()
    return float((value * ureg(unit)).to("Mt * CO2e").magnitude) / 1000.0


def _checked(source: str, field: str, value: str | None, allowed: tuple) -> str | None:
    if value is not None and value not in allowed:
        raise ConfigurationError(
            f"RCB source '{source}': {field} must be one of {list(allowed)}, "
            f"got {value!r}."
        )
    return value


def budget_specs(rcb_yaml: dict) -> list[BudgetSpec]:
    """
    Return every budget of a loaded rcbs.yaml, with renamed labels applied.

    Each source may record ``likelihood_scope`` (tcre-only, tcre-zec-esf) and
    ``budget_metric`` (warming-at-net-zero, peak-warming).
    """
    specs = []
    for source, data in rcb_yaml["rcb_data"].items():
        rule = resolve_scenario_selection(source, data.get("scenario_selection"))
        scope = _checked(
            source, "likelihood_scope", data.get("likelihood_scope"), LIKELIHOOD_SCOPES
        )
        metric = _checked(
            source, "budget_metric", data.get("budget_metric"), BUDGET_METRICS
        )
        published = list(data["scenarios"])
        current = canonical_scenarios(source, data["scenarios"])
        for published_label, (label, value) in zip(published, current.items()):
            _, quantile = parse_rcb_scenario(label)
            specs.append(
                BudgetSpec(
                    source=source,
                    label=label,
                    published_label=published_label,
                    baseline_year=int(data["baseline_year"]),
                    value_gt=_to_gt(value, data.get("unit", "Gt * CO2")),
                    temperature=label_temperature(source, label),
                    likelihood=float(quantile),
                    likelihood_scope=scope,
                    budget_metric=metric,
                    rule=rule,
                )
            )
    return specs


def scenario_set_settings(rcb_yaml: dict) -> dict:
    """
    Return the scenario-set settings of a loaded rcbs.yaml, with defaults.

    Keys: volume_tolerance_gt, min_scenarios, temperature_half_width (the
    deprecated ``band_half_width`` is read as it), bunkers (min_reporters,
    min_families, min_runs_per_family, scenario_sources), non_co2
    (scenario_sources: the sources pooled into the temperature-matched non-CO2
    set, default ["ar6"]) and observed_co2_path.

    Raises
    ------
    ConfigurationError
        If a non-CO2 source does not list "non-co2" in its registry terms
    """
    from fair_shares.library.utils.data.scenario_sources import get_scenario_source

    tolerance = float(rcb_yaml.get("volume_tolerance_gt", DEFAULT_VOLUME_TOLERANCE_GT))
    non_co2_sources = list(
        (rcb_yaml.get("non_co2") or {}).get("scenario_sources", DEFAULT_NON_CO2_SOURCES)
    )
    for name in non_co2_sources:
        if "non-co2" not in get_scenario_source(name)["terms"]:
            raise ConfigurationError(
                f"rcbs.yaml: non_co2.scenario_sources lists '{name}', whose entry "
                f"in scenario_sources.yaml does not supply the non-co2 term."
            )
    bunkers = rcb_yaml.get("bunkers") or {}
    removed = sorted(
        {"fallback", "volume_tolerance_gt", "min_scenarios"} & set(bunkers)
    )
    if removed:
        raise ConfigurationError(
            f"rcbs.yaml: bunkers.{removed[0]} was removed. Bunkers after the last "
            f"observed year are a share of the net CO2 of the volume-matched set; "
            f"bunkers.min_reporters sets the fewest reporters behind the share."
        )
    return {
        "volume_tolerance_gt": tolerance,
        "min_scenarios": int(rcb_yaml.get("min_scenarios", DEFAULT_MIN_SCENARIOS)),
        "temperature_half_width": float(
            rcb_yaml.get(
                "temperature_half_width",
                rcb_yaml.get("band_half_width", DEFAULT_TEMPERATURE_HALF_WIDTH),
            )
        ),
        "bunkers": {
            "min_reporters": int(
                bunkers.get("min_reporters", DEFAULT_BUNKER_MIN_REPORTERS)
            ),
            "min_families": int(
                bunkers.get("min_families", DEFAULT_BUNKER_MIN_FAMILIES)
            ),
            "min_runs_per_family": int(
                bunkers.get("min_runs_per_family", DEFAULT_BUNKER_MIN_RUNS_PER_FAMILY)
            ),
            "scenario_sources": list(
                bunkers.get("scenario_sources", DEFAULT_BUNKER_SOURCES)
            ),
        },
        "non_co2": {"scenario_sources": non_co2_sources},
        "observed_co2_path": rcb_yaml.get(
            "observed_co2_path", DEFAULT_OBSERVED_CO2_PATH
        ),
    }


def budget_from_2020(
    spec: BudgetSpec, observed_gt: pd.Series, max_fill_years: int = 1
) -> tuple[float, float]:
    """
    Return (budget from the start of 2020, observed emissions added), in Gt CO2.

    The budget from 2020 adds observed global net CO2 (fossil including
    bunkers, plus bookkeeping land use) of 2020 to the year before the
    baseline. Up to ``max_fill_years`` trailing years take the last observed
    value, with a warning.

    Raises
    ------
    DataProcessingError
        If the observed series lacks more years than the fill allows
    """
    years = list(range(2020, spec.baseline_year))
    observed = observed_gt.dropna()
    last = int(observed.index.max()) if len(observed) else None
    lacking = [y for y in years if y not in observed.index]
    fill = [y for y in lacking if last is not None and y > last]
    if lacking != fill or len(fill) > max_fill_years:
        raise DataProcessingError(
            f"Budget '{spec.key}': the observed global CO2 lacks {lacking} to "
            f"express the budget from 2020 (fill allows {max_fill_years} year(s))."
        )
    if fill:
        warnings.warn(
            f"Budget '{spec.key}': observed global CO2 ends in {last}; {fill} take "
            f"the {last} value ({observed[last]:.1f} Gt CO2) for the budget from 2020.",
            stacklevel=2,
        )
    added = float(sum(observed.get(y, observed[last] if last else 0.0) for y in years))
    return spec.value_gt + added, added


def scenario_accounting(
    co2_mt: pd.DataFrame, start: int = 2020, last_year: int = 2100
) -> pd.DataFrame:
    """
    Return the net-zero crossing and the cumulative CO2 to it of every scenario.

    Parameters
    ----------
    co2_mt : pd.DataFrame
        Total net CO2 in Mt per year, one row per scenario, year columns
    start : int, optional
        Start of the cumulative (default: 2020)
    last_year : int, optional
        A crossing after this year counts as no net zero (default: 2100)

    Returns
    -------
    pd.DataFrame
        Same index, columns ``NET_ZERO_CROSSING`` and ``CUMULATIVE_CO2`` (Gt);
        both empty for a scenario without net zero by ``last_year``
    """
    rows = []
    for _, row in co2_mt.iterrows():
        crossing, cumulative = cumulative_to_net_zero(row, start)
        if crossing is None or crossing > last_year:
            rows.append((None, None))
        else:
            rows.append((crossing, cumulative / 1000.0))
    return pd.DataFrame(
        rows, index=co2_mt.index, columns=[NET_ZERO_CROSSING, CUMULATIVE_CO2]
    ).astype(float)


def _require(n: int, minimum: int, message: str) -> None:
    if n < minimum:
        raise ConfigurationError(message)


def select_volume_matched(
    accounting: pd.DataFrame,
    key: str,
    budget_2020_gt: float,
    tolerance_gt: float,
    min_scenarios: int,
) -> pd.Index:
    """
    Return the scenarios whose cumulative CO2 to net zero matches the budget.

    A scenario qualifies when it reaches net zero and
    |cumulative 2020 to net zero - budget from 2020| <= tolerance.

    Raises
    ------
    ConfigurationError
        If fewer than ``min_scenarios`` qualify, naming the budget
    """
    cumulative = accounting[CUMULATIVE_CO2]
    keep = cumulative.notna() & (cumulative - budget_2020_gt).abs().le(tolerance_gt)
    selected = accounting.index[keep]
    _require(
        len(selected),
        min_scenarios,
        f"Budget '{key}': {len(selected)} scenarios reach net-zero CO2 with "
        f"cumulative net CO2 from 2020 within +-{tolerance_gt:g} Gt of "
        f"{budget_2020_gt:.0f} Gt (the budget from 2020), fewer than "
        f"min_scenarios={min_scenarios}. Remove the label from rcbs.yaml or "
        f"change volume_tolerance_gt or min_scenarios.",
    )
    return selected


def select_temperature_matched(
    metadata: pd.DataFrame,
    key: str,
    temperature: float,
    warming_column: str,
    net_zero_column: str,
    half_width: float,
    min_scenarios: int,
) -> pd.Index:
    """
    Return the scenarios whose median warming at net zero lies in [T - w, T + w).

    A scenario must have a net-zero year in ``net_zero_column``: without one,
    the at-net-zero metadata hold the 2100 value.

    Raises
    ------
    ConfigurationError
        If a column is absent or fewer than ``min_scenarios`` qualify
    """
    for column in (warming_column, net_zero_column):
        if column not in metadata.columns:
            raise ConfigurationError(
                f"Budget '{key}': the scenario metadata lack '{column}'."
            )
    # Rounding keeps the bounds exact decimals (1.7 - 0.05 gives 1.65).
    lower = round(temperature - half_width, 6)
    upper = round(temperature + half_width, 6)
    warming = metadata[warming_column]
    keep = metadata[net_zero_column].notna() & (warming >= lower) & (warming < upper)
    selected = metadata.index[keep]
    _require(
        len(selected),
        min_scenarios,
        f"Budget '{key}': {len(selected)} scenarios reach net-zero CO2 with "
        f"median warming at net zero in [{lower}, {upper}), fewer than "
        f"min_scenarios={min_scenarios}.",
    )
    return selected


def _set_summary(
    metadata: pd.DataFrame, members: pd.Index, rule: str, columns: dict
) -> dict:
    """Size and medians of one scenario set, for the provenance record."""
    rows = metadata.loc[members]

    def median(column: str | None, digits: int) -> float | None:
        if column is None or column not in rows or rows[column].dropna().empty:
            return None
        return round(float(rows[column].median()), digits)

    return {
        "rule": rule,
        "n": len(members),
        "median_cumulative_co2_gt": median(CUMULATIVE_CO2, 1),
        "median_warming_at_net_zero": median(columns.get("warming_median"), 2),
        "p67_warming_at_net_zero": median(columns.get("warming_p67"), 2),
        "net_zero_year_median": median(NET_ZERO_CROSSING, 1),
    }


def build_budget_sets(
    rcb_yaml: dict,
    metadata: pd.DataFrame,
    observed_gt: pd.Series,
    columns: dict,
    max_fill_years: int = 1,
) -> dict[str, dict]:
    """
    Select the scenario sets of every budget in a loaded rcbs.yaml.

    Parameters
    ----------
    rcb_yaml : dict
        Content of rcbs.yaml
    metadata : pd.DataFrame
        One row per scenario, indexed by (Model, Scenario), with
        ``NET_ZERO_CROSSING``, ``CUMULATIVE_CO2`` and the metadata columns
    observed_gt : pd.Series
        Observed global net CO2 in Gt per year (see ``budget_from_2020``)
    columns : dict
        Metadata column names: "category", "net_zero_year", "warming_median"
        and "warming_p67". A scenario without a net-zero year enters no
        volume-matched, temperature-matched or category terms set
    max_fill_years : int, optional
        Trailing observed years that may take the last value (default: 1)

    Returns
    -------
    dict[str, dict]
        Keyed by ``BudgetSpec.key``: "spec", "budget_2020_gt", "terms" (the
        members behind the integral terms), "non_co2" (the members behind the
        non-CO2 pathway), "category" and "record" (the provenance)
    """
    settings = scenario_set_settings(rcb_yaml)
    min_n = settings["min_scenarios"]
    # Every set needs a net-zero year (AR6 convention, see net_zero_years).
    reaches = metadata[columns["net_zero_year"]].notna()
    sets = {}
    for spec in budget_specs(rcb_yaml):
        budget_2020, observed_added = budget_from_2020(
            spec, observed_gt, max_fill_years
        )
        if spec.category is not None:
            in_category = metadata[columns["category"]] == spec.category
            non_co2 = metadata.index[in_category]
            terms = metadata.index[
                in_category & reaches & metadata[CUMULATIVE_CO2].notna()
            ]
            _require(
                len(terms),
                min_n,
                f"Budget '{spec.key}': {len(terms)} scenarios of AR6 category "
                f"{spec.category} reach net-zero CO2, fewer than "
                f"min_scenarios={min_n}.",
            )
            terms_rule = f"AR6 category {spec.category}, net zero by 2100"
            non_co2_rule = f"AR6 category {spec.category}"
        else:
            tolerance = settings["volume_tolerance_gt"]
            terms = select_volume_matched(
                metadata[reaches], spec.key, budget_2020, tolerance, min_n
            )
            half_width = settings["temperature_half_width"]
            non_co2 = select_temperature_matched(
                metadata,
                spec.key,
                spec.temperature,
                columns["warming_median"],
                columns["net_zero_year"],
                half_width,
                min_n,
            )
            terms_rule = (
                f"cumulative net CO2 2020 to net zero within +-{tolerance:g} Gt "
                f"of {budget_2020:.0f} Gt"
            )
            non_co2_rule = (
                f"median warming at net zero in [{spec.temperature - half_width:g}, "
                f"{spec.temperature + half_width:g}), net zero by 2100"
            )
        non_co2_volume = metadata.loc[non_co2, CUMULATIVE_CO2].median()
        record = {
            "source": spec.source,
            "label": spec.label,
            "published_label": spec.published_label,
            "temperature": spec.temperature,
            "likelihood": spec.likelihood,
            "likelihood_scope": spec.likelihood_scope,
            "budget_metric": spec.budget_metric,
            "scenario_selection": "ar6-category" if spec.category else "role-matched",
            "budget_published_gt": round(spec.value_gt, 1),
            "baseline_year": spec.baseline_year,
            "observed_2020_to_baseline_gt": round(observed_added, 1),
            "budget_2020_gt": round(budget_2020, 1),
            "terms_set": _set_summary(metadata, terms, terms_rule, columns),
            "non_co2_set": _set_summary(metadata, non_co2, non_co2_rule, columns),
            "consistency": {
                "overlap": len(terms.intersection(non_co2)),
                "non_co2_set_volume_gap_gt": (
                    None
                    if pd.isna(non_co2_volume)
                    else round(float(non_co2_volume) - budget_2020, 1)
                ),
            },
        }
        sets[spec.key] = {
            "spec": spec,
            "budget_2020_gt": budget_2020,
            "terms": terms,
            "non_co2": non_co2,
            "category": spec.category,
            "record": record,
        }
    return sets


def add_source_non_co2_members(
    budget_sets: dict[str, dict],
    source: str,
    metadata: pd.DataFrame,
    columns: dict,
    half_width: float,
) -> dict[str, int]:
    """
    Add the temperature-matched scenarios of another source to the non-CO2 sets.

    Applies the temperature-matched rule of ``select_temperature_matched`` to
    ``metadata`` (one row per scenario of ``source``) for every role-matched
    budget. AR6-category budgets keep their category pool. The provenance
    record of each set counts the added scenarios under "added_by_source".

    Parameters
    ----------
    budget_sets : dict[str, dict]
        Output of ``build_budget_sets``, changed in place
    source : str
        Name of the added scenario source
    metadata : pd.DataFrame
        Metadata of the source, indexed by (Model, Scenario)
    columns : dict
        Metadata column names "net_zero_year" and "warming_median"
    half_width : float
        Half-width of the temperature-matched set, in degrees C

    Returns
    -------
    dict[str, int]
        Budget key -> number of scenarios added
    """
    added_counts = {}
    for key, entry in budget_sets.items():
        if entry["category"] is not None:
            continue
        added = select_temperature_matched(
            metadata,
            key,
            entry["spec"].temperature,
            columns["warming_median"],
            columns["net_zero_year"],
            half_width,
            0,
        ).difference(entry["non_co2"])
        entry["non_co2"] = entry["non_co2"].append(added)
        record = entry["record"]["non_co2_set"]
        record["n"] = len(entry["non_co2"])
        record.setdefault("added_by_source", {})[source] = len(added)
        added_counts[key] = len(added)
    return added_counts


def bunker_share_table(
    sources: dict[str, tuple[pd.DataFrame, pd.DataFrame]],
    family_of=None,
    last_year: int = 2100,
) -> pd.DataFrame:
    """
    Return the cumulative CO2 and bunkers of every reporter that reaches net zero.

    Each reporter's net zero comes from its own net CO2, in the AR6 convention
    (``net_zero_years``): the crossing of zero, linear between reported years;
    without one, the first full year below 100 Mt CO2/yr. A window that the
    reported bunker years do not cover leaves the value empty.

    Parameters
    ----------
    sources : dict[str, tuple]
        Per scenario source: (net CO2, bunkers), one row per reporter indexed by
        (Model, Scenario), in Mt per year
    family_of : callable, optional
        Model name -> energy-model family (default: ``model_family``)
    last_year : int, optional
        A crossing after this year counts as no net zero (default: 2100)

    Returns
    -------
    pd.DataFrame
        Columns "source", "Model", "family", "Scenario", ``NET_ZERO_CROSSING``
        and, per start year Y in ``SHARE_START_YEARS``, "co2_from_Y" and
        "bunkers_from_Y" (Mt, from the start of Y to the net-zero crossing)
    """
    from fair_shares.library.utils.data.scenario_sources import (
        model_family,
        net_zero_years,
    )

    family_of = family_of or model_family
    rows = []
    for source, (co2, bunkers) in sources.items():
        threshold_years = net_zero_years(co2, last_year=last_year)
        for key in co2.index:
            crossing = net_zero_crossing(co2.loc[key])
            if crossing is None or crossing > last_year:
                crossing = threshold_years.get(key)
            if crossing is None or pd.isna(crossing):
                continue
            row = {"source": source, "Model": key[0], "family": family_of(key[0])}
            row.update({"Scenario": key[1], NET_ZERO_CROSSING: crossing})
            for year in SHARE_START_YEARS:
                for name, series in (
                    ("co2", co2.loc[key]),
                    ("bunkers", bunkers.loc[key]),
                ):
                    try:
                        row[f"{name}_from_{year}"] = integrate(series, year, crossing)
                    except DataProcessingError:
                        row[f"{name}_from_{year}"] = float("nan")
            rows.append(row)
    return pd.DataFrame(rows)


def bunker_share(
    table: pd.DataFrame,
    first_year: int,
    min_reporters: int = DEFAULT_BUNKER_MIN_REPORTERS,
    min_families: int = DEFAULT_BUNKER_MIN_FAMILIES,
    min_runs_per_family: int = DEFAULT_BUNKER_MIN_RUNS_PER_FAMILY,
) -> dict:
    """
    Return the family-balanced share of bunkers in net CO2 after ``first_year``.

    Each reporter's ratio is its cumulative bunkers over its cumulative net CO2
    from the start of ``first_year`` to its own net-zero crossing. The share is
    the median of the per-family medians, so a model family with many runs
    counts once. A family counts only with at least ``min_runs_per_family``
    reporters. Reporters with no net CO2 left in the window, or whose bunker
    years do not cover it, drop out.

    Returns
    -------
    dict
        "share" (family-balanced), "pooled", "q25" and "q75" (over every
        reporter, counted families or not), "n" and "n_by_source" (reporters of
        the counted families), "families" and "excluded_families" (family ->
        {"median", "n"})

    Raises
    ------
    ConfigurationError
        If the counted families hold fewer than ``min_reporters`` reporters or
        number fewer than ``min_families``
    DataProcessingError
        If ``first_year`` is outside ``SHARE_START_YEARS``
    """
    co2, bunkers = f"co2_from_{first_year}", f"bunkers_from_{first_year}"
    if co2 not in table:
        raise DataProcessingError(
            f"No bunker-share column for {first_year} (the year after the last "
            f"observed bunker year). Re-run notebook 104."
        )
    rows = table[(table[co2] > 0) & table[bunkers].notna()].copy()
    rows["ratio"] = rows[bunkers] / rows[co2]
    all_families = rows.groupby("family")["ratio"].agg(["median", "size"])
    counted = all_families["size"] >= min_runs_per_family
    by_family, excluded = all_families[counted], all_families[~counted]
    kept = rows[rows["family"].isin(by_family.index)]
    counts = kept["source"].value_counts().to_dict()
    message = (
        f"Bunker share from {first_year}: {len(kept)} reporters in "
        f"{len(by_family)} model families with at least {min_runs_per_family} "
        f"runs ({counts}); the share needs at least "
        f"bunkers.min_reporters={min_reporters} reporters and "
        f"bunkers.min_families={min_families} families."
    )
    _require(len(kept), min_reporters, message)
    _require(len(by_family), min_families, message)

    def _families(frame):
        return {
            f: {"median": float(r["median"]), "n": int(r["size"])}
            for f, r in frame.iterrows()
        }

    return {
        "share": float(by_family["median"].median()),
        "pooled": float(rows["ratio"].median()),
        "q25": float(rows["ratio"].quantile(0.25)),
        "q75": float(rows["ratio"].quantile(0.75)),
        "n": len(kept),
        "n_by_source": {k: int(v) for k, v in counts.items()},
        "families": _families(by_family),
        "excluded_families": _families(excluded),
    }


def median_pathways_by_budget(
    pathways: pd.DataFrame, budget_sets: dict[str, dict]
) -> pd.DataFrame:
    """
    Return the median pathway of the non-CO2 set of every budget.

    Parameters
    ----------
    pathways : pd.DataFrame
        One row per scenario, indexed by (model, scenario), with year columns
    budget_sets : dict[str, dict]
        Output of ``build_budget_sets``

    Returns
    -------
    pd.DataFrame
        One row per budget, indexed by (climate-assessment, quantile, source)

    Raises
    ------
    DataProcessingError
        If ``pathways`` holds no scenario of a set
    """
    rows = {}
    for key, entry in budget_sets.items():
        spec = entry["spec"]
        members = set(entry["non_co2"])
        selected = pathways[pathways.index.isin(members)]
        if selected.empty:
            raise DataProcessingError(
                f"Budget '{key}': no pathway of its non-CO2 set "
                f"({len(members)} scenarios)."
            )
        climate_assessment, quantile = parse_rcb_scenario(spec.label)
        rows[(climate_assessment, float(quantile), spec.source)] = selected.median(
            axis=0
        )
    result = pd.DataFrame.from_dict(rows, orient="index")
    result.index = pd.MultiIndex.from_tuples(
        result.index, names=["climate-assessment", "quantile", "source"]
    )
    return result
