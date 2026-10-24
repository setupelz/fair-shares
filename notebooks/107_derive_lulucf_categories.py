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
# # Derive land-use-dependent emission categories
#
# Derive the emission categories that contain land-use CO2 (``co2-lulucf``,
# ``co2``, ``all-ghg``) from the emissions source's FFI and non-LULUCF Kyoto
# primitives (typically PRIMAP, ``active_emissions_source``) plus the country
# land-use CO2 of the active LULUCF source. Outputs live alongside the
# emissions source's originals under ``emiss_<category>_lu_timeseries.csv``.
#
# The LULUCF source is the ``active_lulucf_source`` parameter (a key of the
# ``lulucf`` section of ``data_sources_unified.yaml``). Its
# ``data_parameters.basis`` sets the accounting of the land-use CO2:
#
# - ``nghgi``: national inventories, Melo LULUCF Data Hub (``melo-2026-v4``,
#   ``melo-2026``), 2000-2024;
# - ``bookkeeping``: bookkeeping models, the basis integrated assessment models
#   use, GCB 2025 national land-use change (``gcb-2025-luc``), 1850-2024.
#
# ## Accounting invariant
#
# The two bases count land-use CO2 differently, so this notebook never splices
# them. Derived categories that include ``co2-lulucf`` are bounded to the
# source's year range by construction (column intersection in
# ``_align_and_compute``). ``lulucf_metadata.yaml`` records the basis and the
# year bounds for downstream code.
#
# ## Data flow
#
# **Inputs** (from notebook 101 and raw data):
# - `emiss_co2-ffi_timeseries.csv` — fossil CO2 (LULUCF-independent)
# - `emiss_all-ghg-ex-co2-lulucf_timeseries.csv` — all Kyoto excluding
#   CO2-LULUCF
# - the active LULUCF source's file
#
# **Outputs** (``_lu`` suffix):
# - `emiss_co2-lulucf_lu_timeseries.csv` — the source's land-use CO2
# - `emiss_co2_lu_timeseries.csv` — co2-ffi + co2-lulucf
# - `emiss_non-co2_lu_timeseries.csv` — all-ghg-ex-co2-lulucf - co2-ffi
# - `emiss_all-ghg_lu_timeseries.csv` — co2 + non-co2
# - `emiss_all-ghg-ex-co2-lulucf_lu_timeseries.csv` — co2-ffi + non-co2
#   (recomputed; identical to the emissions source's version by construction)
#
# The three non-CO2 outputs above are written only when the emissions source
# declares `all-ghg-ex-co2-lulucf`. A `co2-ffi`-only source gets the two CO2 files.
#
# - `world_co2-lulucf_timeseries.csv` — world land-use CO2 for the RCB rebase
# - `lulucf_metadata.yaml` — basis, year bounds, affected files

# %% [markdown]
# ## Set paths and library imports

# %%
import re

import matplotlib.pyplot as plt
import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.exceptions import (
    DataLoadingError,
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
        "emissions": "primap-202609",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "wdi-2025",
        "lulucf": "melo-2026-v4",  # or "melo-2026"
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

# Paths and accounting basis
lulucf_file = project_root / lulucf_path
lulucf_basis = lulucf_params.get("basis", "nghgi")
if lulucf_basis == "nghgi":
    # Release label from the file name (timeseries_NGHGI_v3.1.csv -> v3.1).
    _version_match = re.search(r"_v?(\d+(?:\.\d+)+)\.csv$", lulucf_file.name)
    if _version_match is None:
        raise ValueError(
            f"Cannot read a Melo release from file name: {lulucf_file.name}"
        )
    lulucf_release = f"Melo et al. 2026, v{_version_match.group(1)}"
else:
    lulucf_release = (
        f"GCB 2025 national land-use change, mean of "
        f"{', '.join(lulucf_params['models'])}"
    )
intermediate_dir_str = f"output/{source_id}/intermediate/emissions"
intermediate_dir = project_root / intermediate_dir_str
intermediate_dir.mkdir(parents=True, exist_ok=True)

emissions_config = config["emissions"][active_emissions_source]
emissions_world_key = emissions_config["data_parameters"].get("world_key")
# The non-CO2 categories need all-ghg-ex-co2-lulucf from the emissions source.
has_non_co2_input = "all-ghg-ex-co2-lulucf" in emissions_config["data_parameters"].get(
    "available_categories", []
)

print(f"Active LULUCF source: {active_lulucf_source}")
print(f"LULUCF data path: {lulucf_file}")
print(f"LULUCF basis: {lulucf_basis} ({lulucf_release})")
print(f"Intermediate directory: {intermediate_dir_str}")
print(f"Emissions world key: {emissions_world_key}")
if not has_non_co2_input:
    print(
        f"Emissions source '{active_emissions_source}' declares no "
        "all-ghg-ex-co2-lulucf: writing co2-lulucf and co2 only, skipping "
        "non-co2, all-ghg and all-ghg-ex-co2-lulucf."
    )

# %% [markdown]
# ## Step 1: Load the LULUCF source
#
# One loader per accounting basis (``data_parameters.basis``), both returning
# country land-use CO2 plus a world row in Mt CO2/yr, negative = net sink:
#
# - ``nghgi``: Melo LULUCF Data Hub, country-reported (NGHGI convention),
#   long format, world row ``WRD``.
# - ``bookkeeping``: GCB national land-use change, mean of the bookkeeping
#   models, world row from the workbook's ``Global`` column.

# %%
from fair_shares.library.utils.data.lulucf import (
    load_gcb_national_luc,
    load_nghgi_lulucf,
)

print(f"Loading {lulucf_release} ({lulucf_basis} basis)...")
if lulucf_basis == "nghgi":
    lulucf_wide = load_nghgi_lulucf(
        lulucf_file,
        emissions_world_key,
        iso3_column=lulucf_params["iso3_column"],
        year_column=lulucf_params["year_column"],
        value_column=lulucf_params["value_column"],
        category_filter=lulucf_params["category_filter"],
        gas_filter=lulucf_params["gas_filter"],
        source_world_key=lulucf_params["world_key"],
        exclude_regions=lulucf_params.get("exclude_regions", []),
    )
else:
    lulucf_wide = load_gcb_national_luc(
        lulucf_file, lulucf_params["models"], emissions_world_key
    )
lulucf_wide = ensure_string_year_columns(lulucf_wide)

lulucf_years = sorted(int(c) for c in lulucf_wide.columns if c.isdigit())
lulucf_start_year = min(lulucf_years)
lulucf_end_year = max(lulucf_years)
lulucf_year_cols = [str(y) for y in lulucf_years]

world_mask = lulucf_wide.index == emissions_world_key
lulucf_countries = lulucf_wide.loc[~world_mask].copy()
lulucf_all = lulucf_wide

# Add unit and emission-category to MultiIndex
lulucf_all.index = pd.MultiIndex.from_tuples(
    [(iso3c, "Mt * CO2e", "co2-lulucf") for iso3c in lulucf_all.index],
    names=["iso3c", "unit", "emission-category"],
)

print(f"  Shape: {lulucf_all.shape}")
print(f"  Year range: {lulucf_start_year}-{lulucf_end_year}")
print(f"  Countries: {len(lulucf_countries)}")

# %% [markdown]
# ## Step 2: Extract WRD world total for RCB corrections
#
# The world land-use CO2 of the active source is needed by the RCB rebase
# (rcbs.py) for the observed years before a budget's baseline.

# %%
# Save the world row as world_co2-lulucf_timeseries.csv
# Format: single-row DataFrame with source index (matches expected loader format)
wrd_data = lulucf_all.loc[
    lulucf_all.index.get_level_values("iso3c") == emissions_world_key
]
world_values = wrd_data.reset_index(level=["unit", "emission-category"], drop=True)
lulucf_world_output = pd.DataFrame(
    world_values.values,
    columns=world_values.columns,
    index=pd.Index(["lulucf"], name="source"),
)

world_output_path = intermediate_dir / "world_co2-lulucf_timeseries.csv"
lulucf_world_output.reset_index().to_csv(world_output_path, index=False)
print(f"Saved world LULUCF ({lulucf_basis} basis) to: {world_output_path}")
print(f"  End year (splice year): {lulucf_end_year}")
print(
    f"  World LULUCF at {lulucf_end_year}: "
    f"{lulucf_world_output[str(lulucf_end_year)].iloc[0]:.1f} MtCO2/yr"
)

# %% [markdown]
# ## Step 3: Save co2-lulucf from the LULUCF source (its years only)
#
# Output is the source's land-use CO2 across its own years, on its own basis.
# Categories derived from this file inherit that year range via column
# intersection in ``_align_and_compute``.

# %%
lulucf_output_path = intermediate_dir / "emiss_co2-lulucf_lu_timeseries.csv"
lulucf_all.reset_index().to_csv(lulucf_output_path, index=False)
print(f"Saved co2-lulucf ({lulucf_basis} basis) to: {lulucf_output_path}")
print(f"  Year range: {lulucf_start_year}-{lulucf_end_year}, no splicing across bases")

# Save LULUCF metadata for downstream use
lulucf_emissions_files = [
    "emiss_co2-lulucf_lu_timeseries.csv",
    "emiss_co2_lu_timeseries.csv",
]
if has_non_co2_input:
    lulucf_emissions_files += [
        "emiss_non-co2_lu_timeseries.csv",
        "emiss_all-ghg_lu_timeseries.csv",
        "emiss_all-ghg-ex-co2-lulucf_lu_timeseries.csv",
    ]
lulucf_metadata = {
    "lulucf_start_year": lulucf_start_year,
    "lulucf_end_year": lulucf_end_year,
    "splice_year": lulucf_end_year,
    "basis": lulucf_basis,
    "source": lulucf_release,
    "n_countries": len(lulucf_countries),
    "lulucf_emissions_files": lulucf_emissions_files,
}
metadata_path = intermediate_dir / "lulucf_metadata.yaml"
with open(metadata_path, "w") as f:
    yaml.dump(lulucf_metadata, f, default_flow_style=False)
print(f"Saved LULUCF metadata to: {metadata_path}")

# %% [markdown]
# ## Step 4: Compute derived categories
#
# From the three primitives (co2-ffi, co2-lulucf, non-co2), we compute:
# - `co2 = co2-ffi + co2-lulucf` (LULUCF source years only)
# - `non-co2 = all-ghg-ex-co2-lulucf - co2-ffi` (full BM-source year range)
# - `all-ghg = co2 + non-co2` (Melo years only, because co2 is bounded by the LULUCF source)
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
if has_non_co2_input:
    allghg_ex_path = intermediate_dir / "emiss_all-ghg-ex-co2-lulucf_timeseries.csv"
    if not allghg_ex_path.exists():
        raise DataLoadingError(
            f"all-ghg-ex-co2-lulucf not found: {allghg_ex_path}. "
            "Run notebook 101 first."
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
# Compute derived categories. co2 and all-ghg inherit the LULUCF source's year bounds via the
# column intersection inside _align_and_compute; non-co2 and all-ghg-ex retain
# the full BM-source range (no LULUCF dependency).
print("Computing co2 = co2-ffi + co2-lulucf...")
co2 = ensure_string_year_columns(_align_and_compute(co2_ffi, lulucf_all, "add", "co2"))
_save_and_report(
    co2,
    intermediate_dir / "emiss_co2_lu_timeseries.csv",
    "co2",
    bounded_by="the LULUCF source",
)

if has_non_co2_input:
    print("Computing non-co2 = all-ghg-ex-co2-lulucf - co2-ffi...")
    non_co2 = ensure_string_year_columns(
        _align_and_compute(allghg_ex, co2_ffi, "subtract", "non-co2")
    )
    _save_and_report(
        non_co2,
        intermediate_dir / "emiss_non-co2_lu_timeseries.csv",
        "non-co2",
    )

    print("Computing all-ghg = co2 + non-co2...")
    all_ghg = ensure_string_year_columns(
        _align_and_compute(co2, non_co2, "add", "all-ghg")
    )
    _save_and_report(
        all_ghg,
        intermediate_dir / "emiss_all-ghg_lu_timeseries.csv",
        "all-ghg",
        bounded_by="the LULUCF source",
    )

    # all-ghg-ex-co2-lulucf has no LULUCF dependency; identical to the BM version
    # by construction. Written for pipeline symmetry with the other _nghgi files.
    print("Computing all-ghg-ex-co2-lulucf = co2-ffi + non-co2...")
    allghg_ex_computed = ensure_string_year_columns(
        _align_and_compute(co2_ffi, non_co2, "add", "all-ghg-ex-co2-lulucf")
    )
    _save_and_report(
        allghg_ex_computed,
        intermediate_dir / "emiss_all-ghg-ex-co2-lulucf_lu_timeseries.csv",
        "all-ghg-ex-co2-lulucf",
    )

# %% [markdown]
# ## Diagnostics

# %%
# BM-vs-NGHGI LULUCF at world level. BM co2-lulucf is derived implicitly as
# (BM co2 - co2-ffi) from the BM total CO2 file below; not every pipeline
# configuration produces a standalone BM emiss_co2-lulucf_timeseries.csv.
bm_co2_path = intermediate_dir / "emiss_co2_timeseries.csv"
print(
    f"\n=== {active_emissions_source} (implied) vs {lulucf_basis} LULUCF at world level ==="
)
if bm_co2_path.exists():
    bm_co2 = ensure_string_year_columns(
        pd.read_csv(bm_co2_path).set_index(["iso3c", "unit", "emission-category"])
    )
    bm_world_co2 = bm_co2.loc[
        bm_co2.index.get_level_values("iso3c") == emissions_world_key
    ]
    ffi_world = co2_ffi.loc[
        co2_ffi.index.get_level_values("iso3c") == emissions_world_key
    ]
    shared = sorted(
        set(bm_world_co2.columns) & set(ffi_world.columns) & set(lulucf_year_cols)
    )
    print(f"{'year':>6} {lulucf_basis:>12} {'implied':>15} {'diff':>10}")
    for y in shared[-5:]:
        lulucf_val = lulucf_world_output[y].iloc[0]
        bm_implied = bm_world_co2[y].iloc[0] - ffi_world[y].iloc[0]
        print(
            f"{y:>6} {lulucf_val:>12.1f} {bm_implied:>15.1f} {lulucf_val - bm_implied:>10.1f}"
        )
else:
    print(f"BM co2 file not found at {bm_co2_path}; skipping comparison.")

# %%
# Coverage and country-sum vs WRD consistency check.
print("\n=== Coverage and country sum vs world row ===")
print(f"LULUCF source countries: {len(lulucf_countries)}")
melo_country_data = lulucf_all.loc[
    lulucf_all.index.get_level_values("iso3c") != emissions_world_key
]
country_sum = melo_country_data.groupby(level=["unit", "emission-category"]).sum()
print(f"{'year':>6} {'country_sum':>12} {'world':>12} {'diff':>10}")
for y in lulucf_year_cols[-5:]:
    if y in country_sum.columns and y in lulucf_world_output.columns:
        cs = country_sum[y].iloc[0]
        wrd_val = lulucf_world_output[y].iloc[0]
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


# The non-CO2 row is drawn only when those categories were derived.
n_rows = 2 if has_non_co2_input else 1
fig, axes = plt.subplots(n_rows, 2, figsize=(16, 6 * n_rows), squeeze=False)

_plot_world(
    axes[0, 0],
    lulucf_all,
    emissions_world_key,
    title=f"co2-lulucf: World ({lulucf_basis})",
    ylabel="MtCO2/yr",
    label=lulucf_release,
)
_plot_world(
    axes[0, 1],
    co2,
    emissions_world_key,
    title=f"co2: World (FFI + LULUCF, {lulucf_basis})",
    ylabel="MtCO2/yr",
    label=f"co2 ({lulucf_basis})",
)
if has_non_co2_input:
    _plot_world(
        axes[1, 0],
        non_co2,
        emissions_world_key,
        title="non-co2: World (CH4 + N2O + F-gases)",
        ylabel="MtCO2e/yr",
        label="non-co2",
    )
    _plot_world(
        axes[1, 1],
        all_ghg,
        emissions_world_key,
        title=f"all-ghg: World (co2 + non-co2, {lulucf_basis})",
        ylabel="MtCO2e/yr",
        label=f"all-ghg ({lulucf_basis})",
    )

plt.tight_layout()
plt.show()

print("\nLULUCF preprocessing complete.")
print(f"LULUCF basis: {lulucf_basis}; years {lulucf_start_year}-{lulucf_end_year}")
if has_non_co2_input:
    print(
        f"Categories produced: co2-ffi (unchanged), co2-lulucf ({lulucf_basis}), co2, "
        "non-co2, all-ghg, all-ghg-ex-co2-lulucf"
    )
else:
    print(f"Categories produced: co2-ffi (unchanged), co2-lulucf ({lulucf_basis}), co2")

# %%
