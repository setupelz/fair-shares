"""Allocation result visualization.

Handles both budget allocations (single cumulative value per country) and
pathway allocations (annual time series) correctly.  Budget data is shown
as bar charts, pathway data as time series.  When a composite run produces
both types (e.g. CO2 budgets + non-CO2 pathways), the plots are separated
into distinct sections.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Consistent color palette — budget variants (e.g. "equal-per-capita-budget")
# resolve to the same color as their pathway counterpart via _get_approach_color.
_APPROACH_COLORS = {
    "equal-per-capita": "#3498db",
    "per-capita-adjusted": "#e74c3c",
    "per-capita-adjusted-gini": "#2ecc71",
    "cumulative-per-capita-convergence": "#9b59b6",
    "cumulative-per-capita-convergence-adjusted": "#f39c12",
    "cumulative-per-capita-convergence-gini-adjusted": "#1abc9c",
}

_FALLBACK_COLORS = plt.cm.Set2(np.linspace(0, 1, 8))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_absolute_df(output_dir: Path) -> pd.DataFrame:
    """Load allocations_absolute.parquet from output_dir."""
    path = output_dir / "allocations_absolute.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No allocation results at {path}")
    return pd.read_parquet(path)


def _get_year_cols(df: pd.DataFrame, start_year: int = 0) -> list[str]:
    """Extract year columns >= start_year, in order."""
    return sorted(
        [c for c in df.columns if c.isdigit() and int(c) >= start_year],
        key=int,
    )


def _build_param_label(row: pd.Series, approach: str) -> str:
    """Build a human-readable label for a parameter combination."""
    parts = []
    param_keys = [
        ("responsibility-weight", "rw"),
        ("capability-weight", "cw"),
        ("historical-responsibility-year", "hr"),
        ("allocation-year", "ay"),
        ("first-allocation-year", "y"),
        ("income-floor", "floor"),
        ("max-gini-adjustment", "gini"),
        ("convergence-year", "cy"),
    ]
    for col, abbrev in param_keys:
        if col in row.index:
            val = row[col]
            if pd.notna(val) and val != "":
                if isinstance(val, float) and val == int(val):
                    val = int(val)
                parts.append(f"{abbrev}={val}")
    if not parts:
        return approach
    return ", ".join(parts)


@lru_cache(maxsize=16)
def _load_historical_cached(
    hist_path: str,
    country: str,
    category: str,
    start_year: int,
) -> tuple[list[int], list[float]] | None:
    """Load historical emissions for a country. Cached by path + args."""
    p = Path(hist_path)
    if not p.exists():
        return None
    try:
        hist_df = pd.read_csv(p, index_col=[0, 1, 2])
        mask = (hist_df.index.get_level_values("iso3c") == country) & (
            hist_df.index.get_level_values("emission-category") == category
        )
        country_hist = hist_df[mask]
        if country_hist.empty:
            return None
        yr_cols = [
            c for c in country_hist.columns if str(c).isdigit() and int(c) >= start_year
        ]
        if not yr_cols:
            return None
        years = [int(c) for c in yr_cols]
        values = country_hist[yr_cols].iloc[0].values.astype(float).tolist()
        return years, values
    except Exception:
        logger.debug("Failed to load historical data for %s/%s", country, category)
        return None


def _load_historical(
    processed_dir: Path,
    category: str,
    country: str,
    start_year: int,
) -> tuple[list[int], np.ndarray] | None:
    """Load historical emissions for a country. Returns (years, values) or None."""
    hist_path = processed_dir / f"country_emissions_{category}_timeseries.csv"
    result = _load_historical_cached(str(hist_path), country, category, start_year)
    if result is None:
        return None
    return result[0], np.array(result[1])


def _split_budget_pathway(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a DataFrame into budget rows and pathway rows.

    Budget rows have data in at most 1 year column; pathway rows have data
    in multiple year columns.  Returns views (not copies) — callers must
    copy explicitly if they need to mutate.
    """
    yr_cols = _get_year_cols(df)
    if not yr_cols:
        return df, pd.DataFrame(columns=df.columns)

    non_null_counts = df[yr_cols].notna().sum(axis=1)
    budget_mask = non_null_counts <= 1
    return df[budget_mask], df[~budget_mask]


def _get_approach_color(approach: str) -> str:
    """Get color for approach, falling back to a palette.

    Normalizes budget variant names (strips "-budget" suffix) so
    ``equal-per-capita-budget`` gets the same color as ``equal-per-capita``.
    """
    normalized = approach.removesuffix("-budget")
    if normalized in _APPROACH_COLORS:
        return _APPROACH_COLORS[normalized]
    # Stable fallback: hash the name so the same approach always gets the same color
    return _FALLBACK_COLORS[hash(approach) % len(_FALLBACK_COLORS)]


def _scenario_label(ca: str, q, src: str | None = None) -> str:
    """Format a scenario label."""
    base = f"{ca} {q}"
    return f"{src}: {base}" if src else base


def _get_scenario_groups(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], bool]:
    """Extract unique scenario groups from allocation data.

    Returns (groups_df, group_cols, has_source).
    """
    group_cols = ["climate-assessment", "quantile"]
    has_source = "source" in df.columns and df["source"].notna().any()
    if has_source:
        group_cols.append("source")
    groups = df.groupby(group_cols).size().reset_index()[group_cols]
    return groups, group_cols, has_source


def _filter_scenario(
    df: pd.DataFrame, ca: str, q, src: str | None, has_source: bool
) -> pd.DataFrame:
    """Filter DataFrame to a single scenario."""
    mask = (df["climate-assessment"] == ca) & (df["quantile"] == q)
    if has_source and src is not None:
        mask = mask & (df["source"] == src)
    return df[mask]


def _show_empty_panel(ax: plt.Axes, message: str) -> None:
    """Render a 'no data' message on an axes."""
    ax.text(
        0.5,
        0.5,
        message,
        ha="center",
        va="center",
        transform=ax.transAxes,
        fontsize=10,
        color="gray",
    )


def _render_budget_bars(
    ax: plt.Axes,
    sc_data: pd.DataFrame,
    budget_approaches: list[str],
    val_col: str,
    *,
    label_fontsize: int = 8,
    xlabel_fontsize: int = 10,
) -> None:
    """Render horizontal budget bars on a single axes."""
    labels, values, colors = [], [], []
    for approach in budget_approaches:
        app_data = sc_data[sc_data["approach"] == approach]
        color = _get_approach_color(approach)
        for _, row in app_data.iterrows():
            val = row[val_col]
            if pd.isna(val):
                continue
            labels.append(_build_param_label(row, approach))
            values.append(float(val))
            colors.append(color)

    if not values:
        return

    y_pos = np.arange(len(labels))
    ax.barh(y_pos, values, color=colors, alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=label_fontsize)
    ax.set_xlabel("Cumulative Budget (Mt CO₂)", fontsize=xlabel_fontsize)
    ax.axvline(x=0, color="black", linewidth=0.8, alpha=0.4)
    ax.grid(axis="x", alpha=0.3)


def _render_pathway_lines(
    ax: plt.Axes,
    app_data: pd.DataFrame,
    approach: str,
    yr_cols: list[str],
    years: list[int],
) -> None:
    """Render pathway time-series lines on a single axes."""
    n_lines = len(app_data)
    colors = plt.cm.Set2(np.linspace(0, 1, max(n_lines, 3)))

    for idx, (_, row) in enumerate(app_data.iterrows()):
        label = _build_param_label(row, approach) if n_lines > 1 else approach
        vals = row[yr_cols].values.astype(float)
        ax.plot(years, vals, linewidth=1.8, color=colors[idx], alpha=0.85, label=label)


def _overlay_historical(
    ax: plt.Axes,
    processed_dir: Path | None,
    category: str,
    country: str,
    start_year: int,
) -> None:
    """Overlay historical emissions on a pathway panel if data is available."""
    if processed_dir is None:
        return
    hist = _load_historical(processed_dir, category, country, start_year)
    if hist is not None:
        ax.plot(
            hist[0],
            hist[1],
            color="black",
            linewidth=2.5,
            alpha=0.85,
            label="Historical",
            zorder=5,
        )


def _format_pathway_panel(
    ax: plt.Axes,
    approach: str,
    ca: str,
    q,
    src: str | None = None,
) -> None:
    """Apply consistent formatting to a pathway panel."""
    ax.set_title(
        f"{approach}\n{_scenario_label(ca, q, src)}", fontsize=10, fontweight="bold"
    )
    ax.set_xlabel("Year", fontsize=9)
    ax.set_ylabel("Emissions (Mt CO₂e)", fontsize=9)


# ---------------------------------------------------------------------------
# Main comparison plot
# ---------------------------------------------------------------------------


def plot_allocation_comparison(
    output_dir: Path,
    test_country: str = "AUS",
    plot_start_year: int = 2015,
    approaches: list[str] | None = None,
    processed_dir: Path | None = None,
    emission_category: str | None = None,
    final_categories: list[str] | None = None,
    figsize_per_panel: tuple[float, float] = (6, 5),
    absolute_df: pd.DataFrame | None = None,
) -> plt.Figure:
    """Compare allocation results for a single country.

    Automatically detects budget vs pathway data and uses appropriate
    chart types:

    * **Budget approaches** → grouped bar chart (one bar per param combo,
      grouped by scenario)
    * **Pathway approaches** → time-series grid (rows = scenarios,
      cols = approaches) with historical overlay

    When a composite run produces both types, returns a figure with
    separate sections.

    Parameters
    ----------
    output_dir : Path
        Directory containing allocation parquet files.
    test_country : str
        ISO 3166-1 alpha-3 country code.
    plot_start_year : int
        First year to display (pathway plots only).
    approaches : list[str] | None
        Approaches to plot.  None = all found in data.
    processed_dir : Path | None
        Directory with processed data (for historical overlay).
    emission_category : str | None
        Original emission category (for historical overlay lookup).
    final_categories : list[str] | None
        Categories produced by decomposition (e.g. ``["co2", "non-co2"]``).
    figsize_per_panel : tuple
        Size per subplot panel.
    absolute_df : pd.DataFrame | None
        Pre-loaded absolute allocations.  If None, reads from output_dir.

    Returns
    -------
    matplotlib.figure.Figure
    """
    if absolute_df is None:
        absolute_df = _load_absolute_df(output_dir)
    country_data = absolute_df[absolute_df["iso3c"] == test_country]
    if country_data.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            f"No data for {test_country}",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=14,
        )
        ax.set_title(f"Allocation Results — {test_country}")
        return fig

    # Filter approaches
    available = country_data["approach"].unique()
    if approaches is not None:
        plot_approaches = [a for a in approaches if a in available]
    else:
        plot_approaches = sorted(available)

    if not plot_approaches:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "No matching approaches found",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=14,
        )
        return fig

    country_data = country_data[country_data["approach"].isin(plot_approaches)]
    budget_df, pathway_df = _split_budget_pathway(country_data)

    budget_approaches = (
        sorted(budget_df["approach"].unique()) if not budget_df.empty else []
    )
    pathway_approaches = (
        sorted(pathway_df["approach"].unique()) if not pathway_df.empty else []
    )

    has_budget = len(budget_approaches) > 0
    has_pathway = len(pathway_approaches) > 0

    # Determine layout
    if has_budget and has_pathway:
        fig = _plot_mixed_comparison(
            budget_df,
            pathway_df,
            budget_approaches,
            pathway_approaches,
            test_country,
            plot_start_year,
            processed_dir,
            emission_category,
            final_categories,
            figsize_per_panel,
        )
    elif has_budget:
        fig = _plot_budget_comparison(
            budget_df,
            budget_approaches,
            test_country,
            figsize_per_panel,
        )
    else:
        fig = _plot_pathway_comparison(
            pathway_df,
            pathway_approaches,
            test_country,
            plot_start_year,
            processed_dir,
            emission_category,
            final_categories,
            figsize_per_panel,
        )

    return fig


def _plot_budget_comparison(
    budget_df: pd.DataFrame,
    budget_approaches: list[str],
    test_country: str,
    figsize_per_panel: tuple[float, float],
) -> plt.Figure:
    """Bar chart comparing budget allocations across approaches and scenarios."""
    scenario_groups, _, has_source = _get_scenario_groups(budget_df)
    n_scenarios = len(scenario_groups)

    fig, axes = plt.subplots(
        1,
        n_scenarios,
        figsize=(figsize_per_panel[0] * n_scenarios, figsize_per_panel[1]),
        squeeze=False,
    )

    for i, (_, scenario) in enumerate(scenario_groups.iterrows()):
        ax = axes[0, i]
        ca, q = scenario["climate-assessment"], scenario["quantile"]
        src = scenario.get("source")

        sc_data = _filter_scenario(budget_df, ca, q, src, has_source)
        yr_col = _get_year_cols(sc_data)
        if not yr_col:
            continue

        _render_budget_bars(ax, sc_data, budget_approaches, yr_col[0])
        ax.set_title(_scenario_label(ca, q, src), fontsize=11, fontweight="bold")

    fig.suptitle(
        f"CO₂ Budget Allocations — {test_country}",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    return fig


def _resolve_hist_category(
    emission_category: str | None,
    final_categories: list[str] | None,
    *,
    force_non_co2: bool = False,
) -> str | None:
    """Determine the category to use for the historical overlay."""
    if force_non_co2:
        if final_categories and "non-co2" in final_categories:
            return "non-co2"
        return None
    if emission_category is not None:
        if final_categories and len(final_categories) > 1:
            return "non-co2" if "non-co2" in final_categories else final_categories[-1]
        return emission_category
    return None


def _plot_pathway_comparison(
    pathway_df: pd.DataFrame,
    pathway_approaches: list[str],
    test_country: str,
    plot_start_year: int,
    processed_dir: Path | None,
    emission_category: str | None,
    final_categories: list[str] | None,
    figsize_per_panel: tuple[float, float],
) -> plt.Figure:
    """Time-series grid for pathway allocations."""
    scenario_groups, _, has_source = _get_scenario_groups(pathway_df)
    n_scenarios = len(scenario_groups)
    n_approaches = len(pathway_approaches)

    fig, axes = plt.subplots(
        n_scenarios,
        n_approaches,
        figsize=(
            figsize_per_panel[0] * n_approaches,
            figsize_per_panel[1] * n_scenarios,
        ),
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    hist_cat = _resolve_hist_category(emission_category, final_categories)

    for i, (_, scenario) in enumerate(scenario_groups.iterrows()):
        ca, q = scenario["climate-assessment"], scenario["quantile"]
        src = scenario.get("source")
        sc_data = _filter_scenario(pathway_df, ca, q, src, has_source)

        for j, approach in enumerate(pathway_approaches):
            ax = axes[i, j]
            app_data = sc_data[sc_data["approach"] == approach]

            if app_data.empty:
                _show_empty_panel(ax, f"No data for\n{approach}")
                _format_pathway_panel(ax, approach, ca, q, src)
                continue

            yr_cols = _get_year_cols(app_data, plot_start_year)
            years = [int(c) for c in yr_cols]

            _render_pathway_lines(ax, app_data, approach, yr_cols, years)

            if hist_cat is not None:
                _overlay_historical(
                    ax, processed_dir, hist_cat, test_country, plot_start_year
                )

            ax.axhline(y=0, color="black", linestyle="--", linewidth=0.8, alpha=0.4)
            _format_pathway_panel(ax, approach, ca, q, src)

            if i == 0 and j == 0:
                ax.legend(loc="upper right", fontsize=7, framealpha=0.8)

    fig.suptitle(
        f"Pathway Allocations — {test_country}",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    return fig


def _plot_mixed_comparison(
    budget_df: pd.DataFrame,
    pathway_df: pd.DataFrame,
    budget_approaches: list[str],
    pathway_approaches: list[str],
    test_country: str,
    plot_start_year: int,
    processed_dir: Path | None,
    emission_category: str | None,
    final_categories: list[str] | None,
    figsize_per_panel: tuple[float, float],
) -> plt.Figure:
    """Two-section figure: budget bars (top) + pathway time series (bottom)."""
    budget_scenarios, _, budget_has_source = _get_scenario_groups(budget_df)
    n_budget_cols = len(budget_scenarios)

    pathway_scenarios, _, pathway_has_source = _get_scenario_groups(pathway_df)
    n_pathway_scenarios = len(pathway_scenarios)
    n_pathway_approaches = len(pathway_approaches)

    # Layout: top row = budget scenarios, bottom rows = pathway grid
    n_cols = max(n_budget_cols, n_pathway_approaches)
    n_rows = 1 + n_pathway_scenarios

    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(figsize_per_panel[0] * n_cols, figsize_per_panel[1] * n_rows),
        squeeze=False,
    )

    # --- Top row: budget bar charts ---
    for i, (_, scenario) in enumerate(budget_scenarios.iterrows()):
        if i >= n_cols:
            break
        ax = axes[0, i]
        ca, q = scenario["climate-assessment"], scenario["quantile"]
        src = scenario.get("source")

        sc_data = _filter_scenario(budget_df, ca, q, src, budget_has_source)
        yr_col = _get_year_cols(sc_data)
        if not yr_col:
            continue

        _render_budget_bars(
            ax,
            sc_data,
            budget_approaches,
            yr_col[0],
            label_fontsize=7,
            xlabel_fontsize=9,
        )
        ax.set_title(
            f"CO₂ Budget — {_scenario_label(ca, q, src)}",
            fontsize=10,
            fontweight="bold",
        )

    # Hide unused budget columns
    for i in range(n_budget_cols, n_cols):
        axes[0, i].set_visible(False)

    # --- Bottom rows: pathway time series ---
    hist_cat = _resolve_hist_category(
        emission_category, final_categories, force_non_co2=True
    )

    for i, (_, scenario) in enumerate(pathway_scenarios.iterrows()):
        ca, q = scenario["climate-assessment"], scenario["quantile"]
        src = scenario.get("source")
        sc_data = _filter_scenario(pathway_df, ca, q, src, pathway_has_source)

        for j, approach in enumerate(pathway_approaches):
            if j >= n_cols:
                break
            ax = axes[1 + i, j]
            app_data = sc_data[sc_data["approach"] == approach]

            if app_data.empty:
                _show_empty_panel(ax, f"No data for\n{approach}")
                _format_pathway_panel(ax, approach, ca, q, src)
                continue

            yr_cols = _get_year_cols(app_data, plot_start_year)
            years = [int(c) for c in yr_cols]

            _render_pathway_lines(ax, app_data, approach, yr_cols, years)

            if hist_cat is not None:
                _overlay_historical(
                    ax, processed_dir, hist_cat, test_country, plot_start_year
                )

            ax.axhline(y=0, color="black", linestyle="--", linewidth=0.8, alpha=0.4)
            _format_pathway_panel(ax, approach, ca, q, src)

            if i == 0 and j == 0:
                ax.legend(loc="upper right", fontsize=7, framealpha=0.8)

        # Hide unused pathway columns
        for j in range(n_pathway_approaches, n_cols):
            axes[1 + i, j].set_visible(False)

    fig.suptitle(
        f"Emission Allocations — {test_country}",
        fontsize=16,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Decomposition summary
# ---------------------------------------------------------------------------


def plot_decomposition_summary(
    output_dir: Path,
    test_country: str = "AUS",
    plot_start_year: int = 2015,
    processed_dir: Path | None = None,
    final_categories: list[str] | None = None,
    approach: str | None = None,
    absolute_df: pd.DataFrame | None = None,
) -> plt.Figure | None:
    """Summary of CO₂ budget + non-CO₂ pathway for a composite run.

    Shows a two-panel layout: left = CO₂ budget bar per scenario,
    right = non-CO₂ pathway time series.  This replaces the previous
    stacked area which broke when mixing cumulative budget with annual flow.

    Returns None if not a decomposed run.
    """
    if final_categories is None or len(final_categories) <= 1:
        return None

    if absolute_df is None:
        absolute_df = _load_absolute_df(output_dir)
    country_data = absolute_df[absolute_df["iso3c"] == test_country]
    if country_data.empty:
        return None

    budget_df, pathway_df = _split_budget_pathway(country_data)

    # Pick first budget approach if not specified
    if approach is None:
        if not budget_df.empty:
            approach = budget_df["approach"].iloc[0]
        elif not pathway_df.empty:
            approach = pathway_df["approach"].iloc[0]
        else:
            return None

    # Find paired approach names
    budget_approach = approach if approach.endswith("-budget") else f"{approach}-budget"
    pathway_approach = (
        approach.replace("-budget", "") if approach.endswith("-budget") else approach
    )

    co2_data = budget_df[budget_df["approach"] == budget_approach]
    nc_data = pathway_df[pathway_df["approach"] == pathway_approach]

    if co2_data.empty and nc_data.empty:
        return None

    fig, axes = plt.subplots(
        1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1, 2]}
    )

    # --- Left panel: CO₂ budget bars per scenario ---
    ax_budget = axes[0]
    if not co2_data.empty:
        yr_col = _get_year_cols(co2_data)
        if yr_col:
            val_col = yr_col[0]
            labels, values = [], []
            for _, row in co2_data.iterrows():
                val = row[val_col]
                if pd.isna(val):
                    continue
                ca = row.get("climate-assessment", "")
                q = row.get("quantile", "")
                params = _build_param_label(row, "")
                label = f"{ca} {q}"
                if params:
                    label += f"\n{params}"
                labels.append(label)
                values.append(float(val))

            if values:
                y_pos = np.arange(len(labels))
                ax_budget.barh(
                    y_pos,
                    values,
                    color="#3498db",
                    alpha=0.85,
                    edgecolor="white",
                    linewidth=0.5,
                )
                ax_budget.set_yticks(y_pos)
                ax_budget.set_yticklabels(labels, fontsize=8)
                ax_budget.set_xlabel("Cumulative CO₂ Budget (Mt)", fontsize=10)
                ax_budget.axvline(x=0, color="black", linewidth=0.8, alpha=0.4)
                ax_budget.grid(axis="x", alpha=0.3)
    ax_budget.set_title(
        f"CO₂ Budget\n{budget_approach}", fontsize=11, fontweight="bold"
    )

    # --- Right panel: non-CO₂ pathway time series ---
    ax_pathway = axes[1]
    if not nc_data.empty:
        yr_cols = _get_year_cols(nc_data, plot_start_year)
        years = [int(c) for c in yr_cols]

        n_lines = len(nc_data)
        colors = plt.cm.Set2(np.linspace(0, 1, max(n_lines, 3)))

        for idx, (_, row) in enumerate(nc_data.iterrows()):
            ca = row.get("climate-assessment", "")
            q = row.get("quantile", "")
            label = f"{ca} {q}"
            vals = row[yr_cols].values.astype(float)
            ax_pathway.plot(
                years, vals, linewidth=1.8, color=colors[idx], alpha=0.85, label=label
            )

        # Historical overlay for non-CO2
        if processed_dir is not None and "non-co2" in final_categories:
            hist = _load_historical(
                processed_dir, "non-co2", test_country, plot_start_year
            )
            if hist is not None:
                ax_pathway.plot(
                    hist[0],
                    hist[1],
                    color="black",
                    linewidth=2.5,
                    linestyle="--",
                    alpha=0.7,
                    label="Historical",
                )

        ax_pathway.legend(loc="upper right", fontsize=8)
        ax_pathway.grid(alpha=0.3)

    ax_pathway.axhline(y=0, color="black", linestyle="--", linewidth=0.8, alpha=0.4)
    ax_pathway.set_xlabel("Year", fontsize=10)
    ax_pathway.set_ylabel("Non-CO₂ Emissions (Mt CO₂e)", fontsize=10)
    ax_pathway.set_title(
        f"Non-CO₂ Pathway\n{pathway_approach}", fontsize=11, fontweight="bold"
    )

    fig.suptitle(
        f"Emission Decomposition — {test_country}",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Multi-country comparison
# ---------------------------------------------------------------------------


def plot_multi_country_comparison(
    output_dir: Path,
    countries: list[str] | None = None,
    plot_start_year: int = 2015,
    approaches: list[str] | None = None,
    absolute_df: pd.DataFrame | None = None,
) -> plt.Figure:
    """One panel per approach, comparing countries.

    Budget approaches → horizontal bar chart.
    Pathway approaches → time-series lines per country.
    Uses the first scenario group found for each type.

    Parameters
    ----------
    output_dir : Path
        Directory containing allocation parquet files.
    countries : list[str] | None
        Countries to compare.  None defaults to top 10 by share.
    approaches : list[str] | None
        Approaches to include.  None = all.
    plot_start_year : int
        First year displayed (pathway plots only).
    absolute_df : pd.DataFrame | None
        Pre-loaded absolute allocations.  If None, reads from output_dir.

    Returns
    -------
    matplotlib.figure.Figure
    """
    if absolute_df is None:
        absolute_df = _load_absolute_df(output_dir)

    available = absolute_df["approach"].unique()
    if approaches is not None:
        plot_approaches = [a for a in approaches if a in available]
    else:
        plot_approaches = sorted(available)

    if not plot_approaches:
        fig, ax = plt.subplots()
        ax.text(
            0.5,
            0.5,
            "No approaches found",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return fig

    # Split into budget and pathway
    budget_df, pathway_df = _split_budget_pathway(absolute_df)
    budget_approaches = (
        [a for a in plot_approaches if a in budget_df["approach"].unique()]
        if not budget_df.empty
        else []
    )
    pathway_approaches = (
        [a for a in plot_approaches if a in pathway_df["approach"].unique()]
        if not pathway_df.empty
        else []
    )

    n_budget = len(budget_approaches)
    n_pathway = len(pathway_approaches)
    n_total = n_budget + n_pathway

    if n_total == 0:
        fig, ax = plt.subplots()
        ax.text(
            0.5,
            0.5,
            "No approaches found",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return fig

    fig, axes = plt.subplots(1, n_total, figsize=(6 * n_total, 6), squeeze=False)

    # --- Auto-select countries ---
    if countries is None:
        ref_df = budget_df if not budget_df.empty else pathway_df
        yr_cols = _get_year_cols(ref_df)
        if yr_cols:
            ref_approach = (budget_approaches or pathway_approaches)[0]
            ref_app_df = ref_df[ref_df["approach"] == ref_approach]
            if not ref_app_df.empty:
                sums = ref_app_df.groupby("iso3c")[yr_cols[0]].sum().abs()
                sums = sums[sums.index != "World"]
                countries = sums.nlargest(10).index.tolist()
            else:
                countries = sorted(ref_df["iso3c"].unique())[:10]
        else:
            countries = sorted(absolute_df["iso3c"].unique())[:10]

    country_colors = plt.cm.tab10(np.linspace(0, 1, len(countries)))

    # Helper: pick first scenario for a subset
    def _first_scenario(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
        groups, group_cols, has_source = _get_scenario_groups(df)
        first = df.groupby(group_cols).size().index[0]
        if isinstance(first, str):
            first = (first,)
        mask = pd.Series(True, index=df.index)
        for col, val in zip(group_cols, first):
            mask = mask & (df[col] == val)
        return df[mask], " / ".join(str(v) for v in first)

    scenario_label = ""

    # --- Budget approaches: bar charts ---
    for j, approach in enumerate(budget_approaches):
        ax = axes[0, j]
        app_df = budget_df[
            (budget_df["approach"] == approach) & (budget_df["iso3c"].isin(countries))
        ]
        if app_df.empty:
            _show_empty_panel(ax, f"No data for\n{approach}")
            ax.set_title(approach, fontsize=11, fontweight="bold")
            continue

        sc_df, scenario_label = _first_scenario(app_df)
        yr_col = _get_year_cols(sc_df)
        if not yr_col:
            continue
        val_col = yr_col[0]

        bar_data = sc_df.groupby("iso3c")[val_col].first()
        bar_data = bar_data.reindex(countries).dropna()
        sorted_c = bar_data.sort_values(ascending=True).index

        ax.barh(
            range(len(sorted_c)),
            bar_data[sorted_c].values,
            color=[country_colors[countries.index(c)] for c in sorted_c],
            alpha=0.85,
            edgecolor="white",
            linewidth=0.5,
        )
        ax.set_yticks(range(len(sorted_c)))
        ax.set_yticklabels(sorted_c, fontsize=9)
        ax.set_xlabel("Cumulative Budget (Mt CO₂)", fontsize=10)
        ax.axvline(x=0, color="black", linewidth=0.8, alpha=0.4)
        ax.set_title(approach, fontsize=11, fontweight="bold")
        ax.grid(axis="x", alpha=0.3)

    # --- Pathway approaches: time series ---
    for j, approach in enumerate(pathway_approaches):
        ax = axes[0, n_budget + j]
        app_df = pathway_df[
            (pathway_df["approach"] == approach) & (pathway_df["iso3c"].isin(countries))
        ]
        if app_df.empty:
            _show_empty_panel(ax, f"No data for\n{approach}")
            ax.set_title(approach, fontsize=11, fontweight="bold")
            continue

        sc_df, sc_label = _first_scenario(app_df)
        if not scenario_label:
            scenario_label = sc_label

        yr_cols = _get_year_cols(sc_df, plot_start_year)
        years = [int(c) for c in yr_cols]

        for ci, country in enumerate(countries):
            c_data = sc_df[sc_df["iso3c"] == country]
            if c_data.empty:
                continue
            vals = c_data.iloc[0][yr_cols].values.astype(float)
            ax.plot(
                years,
                vals,
                linewidth=1.8,
                color=country_colors[ci],
                label=country,
                alpha=0.85,
            )

        ax.set_xlabel("Year", fontsize=10)
        ax.set_ylabel("Emissions (Mt CO₂e)", fontsize=10)
        ax.set_title(approach, fontsize=11, fontweight="bold")
        ax.axhline(y=0, color="black", linestyle="--", linewidth=0.8, alpha=0.4)
        ax.grid(alpha=0.3)

        if j == n_pathway - 1:
            ax.legend(loc="center left", bbox_to_anchor=(1, 0.5), fontsize=8)

    fig.suptitle(
        f"Country Comparison — {scenario_label}",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Quick-check example plot
# ---------------------------------------------------------------------------

DEFAULT_EXAMPLE_COUNTRIES = ["USA", "CHN", "IND", "DEU", "BRA"]


def _first_scenario_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the first scenario group in a DataFrame."""
    if df.empty:
        return df
    groups, _, has_source = _get_scenario_groups(df)
    first = groups.iloc[0]
    ca, q = first["climate-assessment"], first["quantile"]
    src = first.get("source")
    return _filter_scenario(df, ca, q, src, has_source)


def _first_scenario_label(df: pd.DataFrame) -> str:
    """Human-readable scenario label for quick-check plots."""
    if df.empty:
        return ""
    groups, _, _ = _get_scenario_groups(df)
    first = groups.iloc[0]
    ca, q = first["climate-assessment"], first["quantile"]
    try:
        pct = int(float(q) * 100)
        return f"{ca}, {pct}th percentile"
    except (ValueError, TypeError):
        return str(ca)


def plot_example_result(
    output_dir: Path,
    countries: list[str] | None = None,
    plot_start_year: int = 2015,
    approach: str | None = None,
    processed_dir: Path | None = None,
    emission_category: str | None = None,
    final_categories: list[str] | None = None,
) -> plt.Figure:
    """Quick-check plot: one approach, a few key countries.

    Demonstrates that the allocation pipeline produced sensible results.
    For composite categories (e.g. all-ghg), shows both the CO₂ and
    non-CO₂ components side by side.

    Parameters
    ----------
    output_dir : Path
        Directory containing allocation parquet files.
    countries : list[str] | None
        Countries to display.  Defaults to USA, CHN, IND, DEU, BRA.
    plot_start_year : int
        First year for pathway plots.
    approach : str | None
        Approach to show.  None picks the first found.
    processed_dir : Path | None
        Processed-data directory (for historical overlay).
    emission_category : str | None
        Original emission category (for historical overlay).
    final_categories : list[str] | None
        Categories from decomposition (e.g. ``["co2-ffi", "non-co2"]``).

    Returns
    -------
    matplotlib.figure.Figure
    """
    if countries is None:
        countries = list(DEFAULT_EXAMPLE_COUNTRIES)

    df = _load_absolute_df(output_dir)
    is_composite = final_categories is not None and len(final_categories) > 1

    # Auto-select approach
    if approach is None:
        approach = sorted(df["approach"].unique())[0]

    # For composite runs, include both budget and pathway approach variants
    if is_composite:
        budget_approach = (
            approach if approach.endswith("-budget") else f"{approach}-budget"
        )
        pathway_approach = approach.removesuffix("-budget")
        approach_mask = df["approach"].isin([budget_approach, pathway_approach])
    else:
        budget_approach = pathway_approach = approach
        approach_mask = df["approach"] == approach

    country_data = df[approach_mask & df["iso3c"].isin(countries)]

    if country_data.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            f"No data for {approach}",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=14,
        )
        return fig

    colors = dict(zip(countries, plt.cm.tab10(np.linspace(0, 1, len(countries)))))

    if is_composite:
        return _plot_example_composite(
            country_data,
            countries,
            colors,
            plot_start_year,
            budget_approach,
            pathway_approach,
            processed_dir,
            final_categories,
        )

    # Single category — filter to first scenario and detect type
    country_data = _first_scenario_filter(country_data)
    scenario_label = _first_scenario_label(country_data)
    budget_df, pathway_df = _split_budget_pathway(country_data)

    if not budget_df.empty:
        return _plot_example_budget(
            budget_df, approach, countries, colors, scenario_label
        )
    return _plot_example_pathway(
        pathway_df,
        approach,
        countries,
        colors,
        plot_start_year,
        processed_dir,
        emission_category,
        scenario_label,
    )


def _plot_example_budget(
    budget_df: pd.DataFrame,
    approach: str,
    countries: list[str],
    colors: dict,
    scenario_label: str,
) -> plt.Figure:
    """Horizontal bar chart of budget allocations for a few countries."""
    fig, ax = plt.subplots(figsize=(8, 5))

    yr_cols = _get_year_cols(budget_df)
    if not yr_cols:
        _show_empty_panel(ax, "No budget data")
        return fig

    val_col = yr_cols[0]
    bar_data = budget_df.groupby("iso3c")[val_col].first()
    bar_data = bar_data.reindex(countries).dropna().sort_values()

    y_pos = np.arange(len(bar_data))
    bar_colors = [colors.get(c, "steelblue") for c in bar_data.index]
    ax.barh(y_pos, bar_data.values, color=bar_colors, alpha=0.85, edgecolor="white")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(bar_data.index, fontsize=10)
    ax.set_xlabel("Cumulative Budget (Mt CO₂)", fontsize=10)
    ax.axvline(x=0, color="black", linewidth=0.8, alpha=0.4)
    ax.grid(axis="x", alpha=0.3)

    ax.set_title(
        f"Quick Check: {approach} — {scenario_label}",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    return fig


def _plot_example_pathway(
    pathway_df: pd.DataFrame,
    approach: str,
    countries: list[str],
    colors: dict,
    plot_start_year: int,
    processed_dir: Path | None,
    hist_cat: str | None,
    scenario_label: str,
) -> plt.Figure:
    """Line chart of pathway allocations for a few countries with historical."""
    fig, ax = plt.subplots(figsize=(10, 6))

    yr_cols = _get_year_cols(pathway_df, plot_start_year)
    years = [int(c) for c in yr_cols]

    for country in countries:
        c_data = pathway_df[pathway_df["iso3c"] == country]
        if c_data.empty:
            continue
        color = colors.get(country, "steelblue")
        vals = c_data.iloc[0][yr_cols].values.astype(float)
        ax.plot(years, vals, linewidth=1.8, color=color, label=country, alpha=0.85)

        # Historical overlay (same color, dashed)
        if processed_dir is not None and hist_cat is not None:
            hist = _load_historical(processed_dir, hist_cat, country, plot_start_year)
            if hist is not None:
                ax.plot(
                    hist[0],
                    hist[1],
                    linewidth=1.5,
                    color=color,
                    alpha=0.4,
                    linestyle="--",
                )

    # Legend entry for historical overlay
    if processed_dir is not None and hist_cat is not None:
        ax.plot([], [], color="gray", linestyle="--", linewidth=1.5, label="Historical")

    ax.axhline(y=0, color="black", linestyle="--", linewidth=0.8, alpha=0.4)
    ax.set_xlabel("Year", fontsize=10)
    ax.set_ylabel("Emissions (Mt CO₂e)", fontsize=10)
    ax.set_title(
        f"Quick Check: {approach} — {scenario_label}",
        fontsize=12,
        fontweight="bold",
    )
    ax.legend(loc="best", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_example_composite(
    country_data: pd.DataFrame,
    countries: list[str],
    colors: dict,
    plot_start_year: int,
    budget_approach: str,
    pathway_approach: str,
    processed_dir: Path | None,
    final_categories: list[str],
) -> plt.Figure:
    """Two-panel figure: CO₂ component + non-CO₂ pathway."""
    budget_df, pathway_df = _split_budget_pathway(country_data)
    co2_cats = [c for c in final_categories if c != "non-co2"]

    if not budget_df.empty:
        # rcbs + composite: CO₂ = budgets, non-CO₂ = pathways
        co2_data = _first_scenario_filter(budget_df)
        nc_data = _first_scenario_filter(pathway_df)
        co2_is_budget = True
        co2_label = f"CO₂ Budget — {budget_approach}"
    else:
        # rcb-pathways + composite: both pathways, split by emission-category
        has_ecat = "emission-category" in pathway_df.columns
        if has_ecat:
            co2_raw = pathway_df[pathway_df["emission-category"].isin(co2_cats)]
            nc_raw = pathway_df[pathway_df["emission-category"] == "non-co2"]
        else:
            co2_raw = pathway_df
            nc_raw = pd.DataFrame(columns=pathway_df.columns)
        co2_data = _first_scenario_filter(co2_raw)
        nc_data = _first_scenario_filter(nc_raw) if not nc_raw.empty else nc_raw
        co2_is_budget = False
        co2_label = f"CO₂ Pathway — {pathway_approach}"

    nc_label = f"Non-CO₂ Pathway — {pathway_approach}"
    scenario_label = _first_scenario_label(co2_data if not co2_data.empty else nc_data)

    width_ratios = [1, 1.5] if co2_is_budget else [1, 1]
    fig, (ax_co2, ax_nc) = plt.subplots(
        1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": width_ratios}
    )

    # ── Left panel: CO₂ ──────────────────────────────────────────────
    if co2_is_budget:
        yr_cols = _get_year_cols(co2_data)
        if yr_cols:
            val_col = yr_cols[0]
            bar_data = co2_data.groupby("iso3c")[val_col].first()
            bar_data = bar_data.reindex(countries).dropna().sort_values()
            y_pos = np.arange(len(bar_data))
            bar_colors = [colors.get(c, "steelblue") for c in bar_data.index]
            ax_co2.barh(
                y_pos,
                bar_data.values,
                color=bar_colors,
                alpha=0.85,
                edgecolor="white",
            )
            ax_co2.set_yticks(y_pos)
            ax_co2.set_yticklabels(bar_data.index, fontsize=10)
            ax_co2.set_xlabel("Cumulative Budget (Mt CO₂)", fontsize=10)
            ax_co2.axvline(x=0, color="black", linewidth=0.8, alpha=0.4)
            ax_co2.grid(axis="x", alpha=0.3)
    else:
        yr_cols = _get_year_cols(co2_data, plot_start_year)
        years = [int(c) for c in yr_cols]
        for country in countries:
            c_data = co2_data[co2_data["iso3c"] == country]
            if c_data.empty:
                continue
            color = colors.get(country, "steelblue")
            vals = c_data.iloc[0][yr_cols].values.astype(float)
            ax_co2.plot(
                years, vals, linewidth=1.8, color=color, label=country, alpha=0.85
            )
            if processed_dir is not None and co2_cats:
                hist = _load_historical(
                    processed_dir, co2_cats[0], country, plot_start_year
                )
                if hist is not None:
                    ax_co2.plot(
                        hist[0],
                        hist[1],
                        linewidth=1.5,
                        color=color,
                        alpha=0.4,
                        linestyle="--",
                    )
        if processed_dir is not None and co2_cats:
            ax_co2.plot(
                [], [], color="gray", linestyle="--", linewidth=1.5, label="Historical"
            )
        ax_co2.axhline(y=0, color="black", linestyle="--", linewidth=0.8, alpha=0.4)
        ax_co2.set_xlabel("Year", fontsize=10)
        ax_co2.set_ylabel("Emissions (Mt CO₂)", fontsize=10)
        ax_co2.legend(loc="best", fontsize=8)
        ax_co2.grid(alpha=0.3)
    ax_co2.set_title(co2_label, fontsize=11, fontweight="bold")

    # ── Right panel: non-CO₂ ──────────────────────────────────────────
    if not nc_data.empty:
        yr_cols = _get_year_cols(nc_data, plot_start_year)
        years = [int(c) for c in yr_cols]
        for country in countries:
            c_data = nc_data[nc_data["iso3c"] == country]
            if c_data.empty:
                continue
            color = colors.get(country, "steelblue")
            vals = c_data.iloc[0][yr_cols].values.astype(float)
            ax_nc.plot(
                years, vals, linewidth=1.8, color=color, label=country, alpha=0.85
            )
            if processed_dir is not None:
                hist = _load_historical(
                    processed_dir, "non-co2", country, plot_start_year
                )
                if hist is not None:
                    ax_nc.plot(
                        hist[0],
                        hist[1],
                        linewidth=1.5,
                        color=color,
                        alpha=0.4,
                        linestyle="--",
                    )
        if processed_dir is not None:
            ax_nc.plot(
                [], [], color="gray", linestyle="--", linewidth=1.5, label="Historical"
            )
        ax_nc.legend(loc="best", fontsize=8)

    ax_nc.axhline(y=0, color="black", linestyle="--", linewidth=0.8, alpha=0.4)
    ax_nc.set_xlabel("Year", fontsize=10)
    ax_nc.set_ylabel("Non-CO₂ Emissions (Mt CO₂e)", fontsize=10)
    ax_nc.grid(alpha=0.3)
    ax_nc.set_title(nc_label, fontsize=11, fontweight="bold")

    fig.suptitle(
        f"Quick Check: {pathway_approach} — {scenario_label}",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    return fig
