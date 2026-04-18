# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags,-all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Derive NGHGI-Consistent Emission Categories (Melo v3.1)
#
# Derive a parallel set of NGHGI-consistent emission categories from the
# active bookkeeping-model (BM) source's FFI and non-LULUCF Kyoto primitives
# (typically PRIMAP, configurable via ``active_emissions_source``) plus the
# Melo et al. (2026) country-reported LULUCF CO2 timeseries. Outputs live
# alongside the BM originals under ``emiss_<category>_nghgi_timeseries.csv``.
# 187 country coverage, NGHGI years 2000-2023.
#
# ## Accounting invariant
#
# NGHGI and bookkeeping (BM) LULUCF use different accounting conventions, so
# this notebook does not splice them. Derived categories that include
# ``co2-lulucf`` are bounded to the Melo year range by construction (column
# intersection in ``_align_and_compute``). ``lulucf_metadata.yaml`` exports
# the NGHGI year bounds so downstream code can enforce them.
#
# ## Data flow
#
# **Inputs** (from notebook 101 and raw data):
# - `emiss_co2-ffi_timeseries.csv` — BM-source fossil CO2 (LULUCF-independent)
# - `emiss_all-ghg-ex-co2-lulucf_timeseries.csv` — BM-source all Kyoto
#   excluding CO2-LULUCF
# - `timeseries_NGHGI_v3.1.csv` — Melo v3.1 country-level NGHGI LULUCF
#
# **Outputs** (NGHGI-consistent, ``_nghgi`` suffix):
# - `emiss_co2-lulucf_nghgi_timeseries.csv` — Melo NGHGI (Melo years)
# - `emiss_co2_nghgi_timeseries.csv` — co2-ffi + co2-lulucf
# - `emiss_non-co2_nghgi_timeseries.csv` — all-ghg-ex-co2-lulucf − co2-ffi
# - `emiss_all-ghg_nghgi_timeseries.csv` — co2 + non-co2
# - `emiss_all-ghg-ex-co2-lulucf_nghgi_timeseries.csv` — co2-ffi + non-co2
#   (recomputed; identical to the BM version by construction)
# - `world_co2-lulucf_timeseries.csv` — WRD LULUCF for RCB corrections
# - `lulucf_metadata.yaml` — NGHGI year bounds, affected files

# %% [markdown]
# ## Set paths and library imports

# %%
import matplotlib.pyplot as plt
import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.exceptions import (
    DataLoadingError,
    DataProcessingError,
)
from fair_shares.library.utils import (
    build_source_id,
    ensure_string_year_columns,
)

BLUE = "#005baa"

# %% tags=["parameters"]
emission_category = None
active_target_source = None
active_emissions_source = None
active_gdp_source = None
active_population_source = None
active_gini_source = None
active_lulucf_source = None
source_id = None

# %%
_running_via_papermill = emission_category is not None

if _running_via_papermill:
    print("Running via Papermill")

    if source_id is None:
        source_id = build_source_id(
            emissions=active_emissions_source,
            gdp=active_gdp_source,
            population=active_population_source,
            gini=active_gini_source,
            lulucf=active_lulucf_source,
            target=active_target_source,
            emission_category=emission_category,
        )

    config_path = here() / f"output/{source_id}/config.yaml"
    print(f"Loading config from: {config_path}")
    with open(config_path) as f:
        config = yaml.safe_load(f)
else:
    print("Running interactively - build desired config")

    emission_category = "co2"
    active_sources = {
        "emissions": "primap-202503",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "unu-wider-2025",
        "lulucf": "melo-2026",
        "target": "rcbs",
    }

    from fair_shares.library.utils.data.config import build_data_config

    config, source_id = build_data_config(emission_category, active_sources)
    config = config.model_dump()

    active_target_source = active_sources["target"]
    active_emissions_source = active_sources["emissions"]
    active_gdp_source = active_sources["gdp"]
    active_population_source = active_sources["population"]
    active_gini_source = active_sources["gini"]
    active_lulucf_source = active_sources["lulucf"]

# %% [markdown]
# ## Prepare parameters

# %%
project_root = here()
print(f"Project root: {project_root}")

# Resolve active LULUCF source from config
if active_lulucf_source is None:
    # Fallback: pick first available LULUCF source
    lulucf_sources = config.get("lulucf", {})
    if lulucf_sources:
        active_lulucf_source = next(iter(lulucf_sources))
    else:
        raise ValueError("No LULUCF sources configured in data_sources_unified.yaml")

lulucf_config = config["lulucf"][active_lulucf_source]
lulucf_path = lulucf_config["path"]
lulucf_params = lulucf_config["data_parameters"]

# Paths
melo_path = project_root / lulucf_path
intermediate_dir_str = f"output/{source_id}/intermediate/emissions"
intermediate_dir = project_root / intermediate_dir_str
intermediate_dir.mkdir(parents=True, exist_ok=True)

emissions_config = config["emissions"][active_emissions_source]
emissions_world_key = emissions_config["data_parameters"].get("world_key")

print(f"Active LULUCF source: {active_lulucf_source}")
print(f"LULUCF data path: {melo_path}")
print(f"Intermediate directory: {intermediate_dir_str}")
print(f"Emissions world key: {emissions_world_key}")

# %% [markdown]
# ## Step 1: Load Melo v3.1 NGHGI LULUCF data
#
# The Melo dataset provides country-reported (NGHGI convention) LULUCF CO2 fluxes
# for 187 countries from 2000-2023. Values are in MtCO2/yr where negative = net sink.

# %%
print("Loading Melo v3.1 NGHGI LULUCF data...")

if not melo_path.exists():
    raise DataLoadingError(f"Melo LULUCF file not found: {melo_path}")

melo_raw = pd.read_csv(melo_path)
print(f"  Raw data shape: {melo_raw.shape}")
print(f"  Columns: {list(melo_raw.columns)}")
print(f"  Categories: {melo_raw['Category'].unique()}")
print(f"  Year range: {melo_raw['Year'].min()}-{melo_raw['Year'].max()}")
print(f"  Countries: {melo_raw['ISO3'].nunique()}")

# %%
# Filter to LULUCF total, CO2 only, exclude EU27 (avoid double-counting)
melo_lulucf = melo_raw[
    (melo_raw["Category"] == "LULUCF")
    & (melo_raw["Gas"] == "CO2")
    & (~melo_raw["ISO3"].isin(["EU27"]))
].copy()

print(f"Filtered LULUCF CO2 rows: {len(melo_lulucf)}")
print(f"  Countries (incl WRD): {melo_lulucf['ISO3'].nunique()}")

# Pivot from long to wide: rows = ISO3, columns = years
melo_wide = melo_lulucf.pivot_table(
    index="ISO3",
    columns="Year",
    values="CFluxes_yr",
    aggfunc="sum",
)

# Rename index to match standard format
melo_wide.index.name = "iso3c"
melo_wide = ensure_string_year_columns(melo_wide)

# Derive NGHGI year range from data
melo_years = sorted([int(c) for c in melo_wide.columns if c.isdigit()])
nghgi_start_year = min(melo_years)
nghgi_end_year = max(melo_years)
melo_year_cols = [str(y) for y in melo_years]

# Separate WRD and country data
wrd_mask = melo_wide.index == "WRD"
melo_countries_raw = melo_wide.loc[~wrd_mask].copy()
melo_wrd_raw = melo_wide.loc[wrd_mask].copy()

if melo_wrd_raw.empty:
    raise DataProcessingError("WRD (world total) not found in Melo data")

# Map WRD to emissions_world_key for consistency with the active BM source
melo_wrd_raw.index = pd.Index([emissions_world_key], name="iso3c")
melo_all = pd.concat([melo_countries_raw, melo_wrd_raw])

# Add unit and emission-category to MultiIndex
melo_all.index = pd.MultiIndex.from_tuples(
    [(iso3c, "Mt * CO2e", "co2-lulucf") for iso3c in melo_all.index],
    names=["iso3c", "unit", "emission-category"],
)

print(f"  Melo wide shape: {melo_all.shape}")
print(f"  NGHGI year range: {nghgi_start_year}-{nghgi_end_year}")
print(f"  Countries: {len(melo_countries_raw)}")

# %% [markdown]
# ## Step 2: Extract WRD world total for RCB corrections
#
# The world-level NGHGI LULUCF timeseries is needed by the RCB correction pipeline
# (rcbs.py) to compute historical LULUCF deductions.

# %%
# Save WRD as world_co2-lulucf_timeseries.csv
# Format: single-row DataFrame with source index (matches expected loader format)
wrd_data = melo_all.loc[melo_all.index.get_level_values("iso3c") == emissions_world_key]
world_values = wrd_data.reset_index(level=["unit", "emission-category"], drop=True)
nghgi_world_output = pd.DataFrame(
    world_values.values,
    columns=world_values.columns,
    index=pd.Index(["nghgi_lulucf"], name="source"),
)

world_output_path = intermediate_dir / "world_co2-lulucf_timeseries.csv"
nghgi_world_output.reset_index().to_csv(world_output_path, index=False)
print(f"Saved WRD NGHGI LULUCF to: {world_output_path}")
print(f"  NGHGI end year (splice year): {nghgi_end_year}")
print(
    f"  WRD LULUCF at {nghgi_end_year}: "
    f"{nghgi_world_output[str(nghgi_end_year)].iloc[0]:.1f} MtCO2/yr"
)

# %% [markdown]
# ## Step 3: Save NGHGI-consistent co2-lulucf (Melo years only)
#
# Output is pure Melo NGHGI data across Melo years. Categories derived from
# this file inherit the Melo year range via column intersection in
# ``_align_and_compute``.

# %%
lulucf_output_path = intermediate_dir / "emiss_co2-lulucf_nghgi_timeseries.csv"
melo_all.reset_index().to_csv(lulucf_output_path, index=False)
print(f"Saved NGHGI co2-lulucf to: {lulucf_output_path}")
print(f"  Year range: {nghgi_start_year}-{nghgi_end_year} (Melo NGHGI only)")
print("  NO BM splicing — pure NGHGI convention data")

# Save NGHGI metadata for downstream use
nghgi_metadata = {
    "nghgi_start_year": nghgi_start_year,
    "nghgi_end_year": nghgi_end_year,
    "splice_year": nghgi_end_year,
    "source": "Melo et al. 2026, v3.1",
    "n_countries": len(melo_countries_raw),
    "nghgi_emissions_files": [
        "emiss_co2-lulucf_nghgi_timeseries.csv",
        "emiss_co2_nghgi_timeseries.csv",
        "emiss_non-co2_nghgi_timeseries.csv",
        "emiss_all-ghg_nghgi_timeseries.csv",
        "emiss_all-ghg-ex-co2-lulucf_nghgi_timeseries.csv",
    ],
}
metadata_path = intermediate_dir / "lulucf_metadata.yaml"
with open(metadata_path, "w") as f:
    yaml.dump(nghgi_metadata, f, default_flow_style=False)
print(f"Saved NGHGI metadata to: {metadata_path}")

# %% [markdown]
# ## Step 4: Compute derived categories
#
# From the three primitives (co2-ffi, co2-lulucf, non-co2), we compute:
# - `co2 = co2-ffi + co2-lulucf` (Melo years only)
# - `non-co2 = all-ghg-ex-co2-lulucf - co2-ffi` (full BM-source year range)
# - `all-ghg = co2 + non-co2` (Melo years only, because co2 is Melo-bounded)
# - `all-ghg-ex-co2-lulucf = co2-ffi + non-co2` (full BM-source year range)

# %%
# Load co2-ffi from notebook 101 output
co2_ffi_path = intermediate_dir / "emiss_co2-ffi_timeseries.csv"
if not co2_ffi_path.exists():
    raise DataLoadingError(
        f"co2-ffi not found: {co2_ffi_path}. Run notebook 101 first."
    )

co2_ffi = pd.read_csv(co2_ffi_path)
co2_ffi = co2_ffi.set_index(["iso3c", "unit", "emission-category"])
co2_ffi = ensure_string_year_columns(co2_ffi)
print(f"Loaded co2-ffi: {co2_ffi.shape}")

# Load all-ghg-ex-co2-lulucf from notebook 101 output (for non-co2 derivation)
allghg_ex_path = intermediate_dir / "emiss_all-ghg-ex-co2-lulucf_timeseries.csv"
if not allghg_ex_path.exists():
    raise DataLoadingError(
        f"all-ghg-ex-co2-lulucf not found: {allghg_ex_path}. Run notebook 101 first."
    )

allghg_ex = pd.read_csv(allghg_ex_path)
allghg_ex = allghg_ex.set_index(["iso3c", "unit", "emission-category"])
allghg_ex = ensure_string_year_columns(allghg_ex)
print(f"Loaded all-ghg-ex-co2-lulucf: {allghg_ex.shape}")


# %%
# Helper: align two DataFrames on shared countries and years for arithmetic
def _align_and_compute(df1, df2, operation, new_category):
    """Align two timeseries DataFrames and perform element-wise operation.

    Parameters
    ----------
    df1, df2 : pd.DataFrame
        Timeseries with MultiIndex (iso3c, unit, emission-category)
    operation : str
        "add" or "subtract" (df1 + df2 or df1 - df2)
    new_category : str
        emission-category label for the result

    Returns
    -------
    pd.DataFrame
        Result with MultiIndex (iso3c, unit, emission-category)
    """
    # Strip emission-category for alignment
    a = df1.reset_index(level="emission-category", drop=True)
    b = df2.reset_index(level="emission-category", drop=True)

    # Align on shared years (intersection — never extend beyond either input)
    shared_years = sorted(set(a.columns) & set(b.columns))
    a = a[shared_years]
    b = b[shared_years]

    # Align on shared index (iso3c, unit)
    shared_idx = a.index.intersection(b.index)
    a = a.loc[shared_idx]
    b = b.loc[shared_idx]

    if operation == "add":
        result = a.add(b, fill_value=0)
    elif operation == "subtract":
        result = a.subtract(b, fill_value=0)
    else:
        raise ValueError(f"Unknown operation: {operation}")

    # Re-attach emission-category
    result.index = pd.MultiIndex.from_tuples(
        [(iso3c, unit, new_category) for iso3c, unit in result.index],
        names=["iso3c", "unit", "emission-category"],
    )

    return result


def _save_and_report(
    df: pd.DataFrame, path, label: str, *, bounded_by: str | None = None
) -> None:
    """Write a derived category CSV and print a one-line summary."""
    df.reset_index().to_csv(path, index=False)
    years = sorted(int(c) for c in df.columns if c.isdigit())
    bound_note = f" (bounded by {bounded_by})" if bounded_by else ""
    print(
        f"  {label}: shape={df.shape}, "
        f"years={min(years)}-{max(years)}{bound_note}, "
        f"saved to {path.name}"
    )


# %%
# Compute derived categories. co2 and all-ghg inherit Melo year bounds via the
# column intersection inside _align_and_compute; non-co2 and all-ghg-ex retain
# the full BM-source range (no LULUCF dependency).
print("Computing co2 = co2-ffi + co2-lulucf...")
co2 = ensure_string_year_columns(_align_and_compute(co2_ffi, melo_all, "add", "co2"))
_save_and_report(
    co2,
    intermediate_dir / "emiss_co2_nghgi_timeseries.csv",
    "co2",
    bounded_by="Melo",
)

print("Computing non-co2 = all-ghg-ex-co2-lulucf - co2-ffi...")
non_co2 = ensure_string_year_columns(
    _align_and_compute(allghg_ex, co2_ffi, "subtract", "non-co2")
)
_save_and_report(
    non_co2,
    intermediate_dir / "emiss_non-co2_nghgi_timeseries.csv",
    "non-co2",
)

print("Computing all-ghg = co2 + non-co2...")
all_ghg = ensure_string_year_columns(_align_and_compute(co2, non_co2, "add", "all-ghg"))
_save_and_report(
    all_ghg,
    intermediate_dir / "emiss_all-ghg_nghgi_timeseries.csv",
    "all-ghg",
    bounded_by="Melo",
)

# all-ghg-ex-co2-lulucf has no LULUCF dependency; identical to the BM version
# by construction. Written for pipeline symmetry with the other _nghgi files.
print("Computing all-ghg-ex-co2-lulucf = co2-ffi + non-co2...")
allghg_ex_computed = ensure_string_year_columns(
    _align_and_compute(co2_ffi, non_co2, "add", "all-ghg-ex-co2-lulucf")
)
_save_and_report(
    allghg_ex_computed,
    intermediate_dir / "emiss_all-ghg-ex-co2-lulucf_nghgi_timeseries.csv",
    "all-ghg-ex-co2-lulucf",
)

# %% [markdown]
# ## Diagnostics

# %%
# BM-vs-NGHGI LULUCF at world level. BM co2-lulucf is derived implicitly as
# (BM co2 − co2-ffi) from the BM total CO2 file below; not every pipeline
# configuration produces a standalone BM emiss_co2-lulucf_timeseries.csv.
bm_co2_path = intermediate_dir / "emiss_co2_timeseries.csv"
print(f"\n=== BM ({active_emissions_source}) vs NGHGI LULUCF at world level ===")
if bm_co2_path.exists():
    bm_co2 = ensure_string_year_columns(
        pd.read_csv(bm_co2_path).set_index(["iso3c", "unit", "emission-category"])
    )
    bm_world_co2 = bm_co2.loc[bm_co2.index.get_level_values("iso3c") == emissions_world_key]
    ffi_world = co2_ffi.loc[co2_ffi.index.get_level_values("iso3c") == emissions_world_key]
    shared = sorted(
        set(bm_world_co2.columns) & set(ffi_world.columns) & set(melo_year_cols)
    )
    print(f"{'year':>6} {'NGHGI':>12} {'BM (implied)':>15} {'diff':>10}")
    for y in shared[-5:]:
        nghgi_val = nghgi_world_output[y].iloc[0]
        bm_implied = bm_world_co2[y].iloc[0] - ffi_world[y].iloc[0]
        print(f"{y:>6} {nghgi_val:>12.1f} {bm_implied:>15.1f} {nghgi_val - bm_implied:>10.1f}")
else:
    print(f"BM co2 file not found at {bm_co2_path}; skipping comparison.")

# %%
# Coverage and country-sum vs WRD consistency check.
print(f"\n=== Coverage and country-sum vs WRD ===")
print(f"Melo countries: {len(melo_countries_raw)}")
melo_country_data = melo_all.loc[
    melo_all.index.get_level_values("iso3c") != emissions_world_key
]
country_sum = melo_country_data.groupby(level=["unit", "emission-category"]).sum()
print(f"{'year':>6} {'country_sum':>12} {'WRD':>12} {'diff':>10}")
for y in melo_year_cols[-5:]:
    if y in country_sum.columns and y in nghgi_world_output.columns:
        cs = country_sum[y].iloc[0]
        wrd_val = nghgi_world_output[y].iloc[0]
        print(f"{y:>6} {cs:>12.1f} {wrd_val:>12.1f} {cs - wrd_val:>10.1f}")

# %% [markdown]
# ## Plots

# %%
def _plot_world(ax, df, world_key, *, title, ylabel, label):
    world_df = df.loc[df.index.get_level_values("iso3c") == world_key]
    if not world_df.empty:
        years_int = sorted(int(c) for c in world_df.columns if c.isdigit())
        vals = [world_df[str(y)].iloc[0] for y in years_int]
        ax.plot(years_int, vals, label=label, color=BLUE, linewidth=2)
        ax.legend()
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color="black", linestyle="-", alpha=0.3)


fig, axes = plt.subplots(2, 2, figsize=(16, 12))

_plot_world(
    axes[0, 0], melo_all, emissions_world_key,
    title="co2-lulucf: World (NGHGI only)",
    ylabel="MtCO2/yr",
    label="NGHGI (Melo)",
)
_plot_world(
    axes[0, 1], co2, emissions_world_key,
    title="co2: World (FFI + LULUCF NGHGI)",
    ylabel="MtCO2/yr",
    label="co2 (NGHGI)",
)
_plot_world(
    axes[1, 0], non_co2, emissions_world_key,
    title="non-co2: World (CH4 + N2O + F-gases)",
    ylabel="MtCO2e/yr",
    label="non-co2",
)
_plot_world(
    axes[1, 1], all_ghg, emissions_world_key,
    title="all-ghg: World (co2 + non-co2, NGHGI)",
    ylabel="MtCO2e/yr",
    label="all-ghg (NGHGI)",
)

plt.tight_layout()
plt.show()

print("\nLULUCF preprocessing complete.")
print(f"NGHGI year range: {nghgi_start_year}-{nghgi_end_year}")
print(
    "Categories produced: co2-ffi (unchanged), co2-lulucf (NGHGI), co2, "
    "non-co2, all-ghg, all-ghg-ex-co2-lulucf"
)

# %%
