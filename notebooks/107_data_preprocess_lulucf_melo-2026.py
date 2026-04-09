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
# # LULUCF Data Preprocessing (Melo v3.1 → NGHGI-Consistent Categories)
#
# This notebook produces NGHGI-consistent emission categories from the Melo et al. (2026)
# country-reported LULUCF CO2 timeseries. It replaces the previous Grassi et al. (2023)
# data with higher country coverage (187 countries) and an additional year (2023).
#
# ## CRITICAL: No NGHGI/BM splicing
#
# NGHGI and bookkeeping (BM) LULUCF use fundamentally different accounting conventions.
# Splicing them would create a timeseries that is neither NGHGI-consistent nor
# BM-consistent. Therefore:
# - co2-lulucf covers Melo years only (2000+)
# - Derived categories (co2, all-ghg) that include co2-lulucf are also limited to
#   Melo years for the LULUCF component
# - The earliest Melo year is exported as metadata so downstream code can enforce
#   the NGHGI start year constraint dynamically
#
# ## Data flow
#
# **Inputs** (from notebook 101 and raw data):
# - `emiss_co2-ffi_timeseries.csv` — PRIMAP fossil CO2 (primitive)
# - `emiss_all-ghg-ex-co2-lulucf_timeseries.csv` — PRIMAP all Kyoto excl. CO2-LULUCF
# - `timeseries_NGHGI_v3.1.csv` — Melo v3.1 country-level NGHGI LULUCF
#
# **Outputs** (NGHGI-consistent):
# - `emiss_co2-lulucf_timeseries.csv` — Melo NGHGI only (2000+), overwrites BM version
# - `emiss_co2_timeseries.csv` — co2-ffi + co2-lulucf (NGHGI, Melo years only)
# - `emiss_non-co2_timeseries.csv` — all-ghg-ex-co2-lulucf - co2-ffi
# - `emiss_all-ghg_timeseries.csv` — co2 + non-co2 (Melo years only)
# - `emiss_all-ghg-ex-co2-lulucf_timeseries.csv` — co2-ffi + non-co2 (unchanged)
# - `world_co2-lulucf_timeseries.csv` — WRD LULUCF for RCB corrections
# - `lulucf_metadata.yaml` — NGHGI start year and splice year for downstream use

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

# Map WRD to emissions_world_key for consistency with PRIMAP
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
# ## Step 3: Save NGHGI-consistent co2-lulucf (Melo years only, NO BM splicing)
#
# CRITICAL: This is pure Melo NGHGI data. No pre-2000 fallback from PRIMAP BM.
# Categories containing co2-lulucf are only valid for years >= nghgi_start_year.

# %%
lulucf_output_path = intermediate_dir / "emiss_co2-lulucf_timeseries.csv"
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
# - `non-co2 = all-ghg-ex-co2-lulucf - co2-ffi` (full PRIMAP year range)
# - `all-ghg = co2 + non-co2` (Melo years only, because co2 is Melo-bounded)
# - `all-ghg-ex-co2-lulucf = co2-ffi + non-co2` (full PRIMAP year range)

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


# %%
# Compute co2 = co2-ffi + co2-lulucf (limited to Melo years by intersection)
print("Computing co2 = co2-ffi + co2-lulucf...")
co2 = _align_and_compute(co2_ffi, melo_all, "add", "co2")
co2 = ensure_string_year_columns(co2)
co2_years = sorted([int(c) for c in co2.columns if c.isdigit()])
print(f"  co2 shape: {co2.shape}")
print(f"  co2 year range: {min(co2_years)}-{max(co2_years)} (bounded by Melo)")

co2_output_path = intermediate_dir / "emiss_co2_timeseries.csv"
co2.reset_index().to_csv(co2_output_path, index=False)
print(f"  Saved to: {co2_output_path}")

# %%
# Compute non-co2 = all-ghg-ex-co2-lulucf - co2-ffi (full PRIMAP range)
print("Computing non-co2 = all-ghg-ex-co2-lulucf - co2-ffi...")
non_co2 = _align_and_compute(allghg_ex, co2_ffi, "subtract", "non-co2")
non_co2 = ensure_string_year_columns(non_co2)
non_co2_years = sorted([int(c) for c in non_co2.columns if c.isdigit()])
print(f"  non-co2 shape: {non_co2.shape}")
print(f"  non-co2 year range: {min(non_co2_years)}-{max(non_co2_years)}")

non_co2_output_path = intermediate_dir / "emiss_non-co2_timeseries.csv"
non_co2.reset_index().to_csv(non_co2_output_path, index=False)
print(f"  Saved to: {non_co2_output_path}")

# %%
# Compute all-ghg = co2 + non-co2 (bounded by co2 → bounded by Melo years)
print("Computing all-ghg = co2 + non-co2...")
all_ghg = _align_and_compute(co2, non_co2, "add", "all-ghg")
all_ghg = ensure_string_year_columns(all_ghg)
allghg_years = sorted([int(c) for c in all_ghg.columns if c.isdigit()])
print(f"  all-ghg shape: {all_ghg.shape}")
print(
    f"  all-ghg year range: {min(allghg_years)}-{max(allghg_years)} (bounded by Melo)"
)

allghg_output_path = intermediate_dir / "emiss_all-ghg_timeseries.csv"
all_ghg.reset_index().to_csv(allghg_output_path, index=False)
print(f"  Saved to: {allghg_output_path}")

# %%
# Compute all-ghg-ex-co2-lulucf = co2-ffi + non-co2 (full PRIMAP range, no LULUCF)
print("Computing all-ghg-ex-co2-lulucf = co2-ffi + non-co2...")
allghg_ex_computed = _align_and_compute(
    co2_ffi, non_co2, "add", "all-ghg-ex-co2-lulucf"
)
allghg_ex_computed = ensure_string_year_columns(allghg_ex_computed)
print(f"  all-ghg-ex-co2-lulucf shape: {allghg_ex_computed.shape}")

# Overwrite with computed version (should be identical to PRIMAP by construction)
allghg_ex_output_path = intermediate_dir / "emiss_all-ghg-ex-co2-lulucf_timeseries.csv"
allghg_ex_computed.reset_index().to_csv(allghg_ex_output_path, index=False)
print(f"  Saved to: {allghg_ex_output_path}")

# %% [markdown]
# ## Diagnostics

# %%
# Diagnostic 1: Melo NGHGI vs PRIMAP BM at world level
print("\n=== Diagnostic: Melo NGHGI vs PRIMAP BM at world level ===")

# Load original PRIMAP BM for comparison (before we overwrote it)
# We use the co2-lulucf from notebook 101 which is still in the PRIMAP BM convention
# Since we already overwrote the file, load the co2 (=ffi+lulucf) from PRIMAP
# and subtract co2-ffi to recover BM LULUCF
primap_co2_path = intermediate_dir / "emiss_co2_timeseries.csv"
if primap_co2_path.exists():
    # This is now NGHGI co2, so we can't recover BM from it.
    # Instead, compare the world WRD value directly
    print("(PRIMAP BM comparison not available — file already overwritten by NGHGI)")
    print("WRD NGHGI LULUCF values:")
    for y in melo_year_cols[-5:]:
        val = nghgi_world_output[y].iloc[0]
        print(f"  {y}: {val:.1f} MtCO2/yr")

# %%
# Diagnostic 2: Country coverage
melo_isos = set(melo_countries_raw.index)
print("\n=== Diagnostic: Country coverage ===")
print(f"Melo countries: {len(melo_isos)}")

# %%
# Diagnostic 3: Verify sum(country Melo) ≈ WRD
print("\n=== Diagnostic: sum(country Melo) vs WRD ===")
melo_country_data = melo_all.loc[
    melo_all.index.get_level_values("iso3c") != emissions_world_key
]
country_sum = melo_country_data.groupby(level=["unit", "emission-category"]).sum()

for y in melo_year_cols[-5:]:
    if y in country_sum.columns and y in nghgi_world_output.columns:
        cs = country_sum[y].iloc[0]
        wrd_val = nghgi_world_output[y].iloc[0]
        diff = cs - wrd_val
        print(
            f"  {y}: country_sum={cs:.1f}, WRD={wrd_val:.1f}, diff={diff:.1f} MtCO2/yr"
        )

# %% [markdown]
# ## Plots

# %%
# Plot world-level categories
world_key = emissions_world_key
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Plot 1: co2-lulucf (NGHGI)
ax = axes[0, 0]
world_lulucf = melo_all.loc[melo_all.index.get_level_values("iso3c") == world_key]
if not world_lulucf.empty:
    years_int = [int(c) for c in world_lulucf.columns if c.isdigit()]
    vals = [world_lulucf[str(y)].iloc[0] for y in years_int]
    ax.plot(years_int, vals, label="NGHGI (Melo)", color="steelblue", linewidth=2)
ax.set_title("co2-lulucf: World (NGHGI only)", fontweight="bold")
ax.set_ylabel("MtCO2/yr")
ax.legend()
ax.grid(True, alpha=0.3)
ax.axhline(y=0, color="black", linestyle="-", alpha=0.3)

# Plot 2: co2 (FFI + LULUCF)
ax = axes[0, 1]
world_co2 = co2.loc[co2.index.get_level_values("iso3c") == world_key]
if not world_co2.empty:
    years_int = [int(c) for c in world_co2.columns if c.isdigit()]
    vals = [world_co2[str(y)].iloc[0] for y in years_int]
    ax.plot(years_int, vals, label="co2 (NGHGI)", color="steelblue", linewidth=2)
ax.set_title("co2: World (FFI + LULUCF NGHGI)", fontweight="bold")
ax.set_ylabel("MtCO2/yr")
ax.grid(True, alpha=0.3)

# Plot 3: non-co2
ax = axes[1, 0]
world_nonco2 = non_co2.loc[non_co2.index.get_level_values("iso3c") == world_key]
if not world_nonco2.empty:
    years_int = [int(c) for c in world_nonco2.columns if c.isdigit()]
    vals = [world_nonco2[str(y)].iloc[0] for y in years_int]
    ax.plot(years_int, vals, label="non-co2", color="green", linewidth=2)
ax.set_title("non-co2: World (CH4 + N2O + F-gases)", fontweight="bold")
ax.set_ylabel("MtCO2e/yr")
ax.grid(True, alpha=0.3)

# Plot 4: all-ghg
ax = axes[1, 1]
world_allghg = all_ghg.loc[all_ghg.index.get_level_values("iso3c") == world_key]
if not world_allghg.empty:
    years_int = [int(c) for c in world_allghg.columns if c.isdigit()]
    vals = [world_allghg[str(y)].iloc[0] for y in years_int]
    ax.plot(years_int, vals, label="all-ghg (NGHGI)", color="red", linewidth=2)
ax.set_title("all-ghg: World (co2 + non-co2, NGHGI)", fontweight="bold")
ax.set_ylabel("MtCO2e/yr")
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

print("\nLULUCF preprocessing complete!")
print(f"NGHGI year range: {nghgi_start_year}-{nghgi_end_year}")
print("NO BM/NGHGI splicing — all NGHGI-consistent categories use Melo years only")
print(
    "Categories produced: co2-ffi (unchanged), co2-lulucf (NGHGI), co2, "
    "non-co2, all-ghg, all-ghg-ex-co2-lulucf"
)

# %%
