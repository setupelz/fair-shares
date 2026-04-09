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
# # International Bunker Fuel CO2 Preprocessing
#
# Extracts international bunker fuel (aviation + shipping) CO2 emissions from
# the Global Carbon Budget (GCB) fossil emissions dataset.  Bunker emissions
# are subtracted from global RCBs before country-level allocation.
#
# **Source:** GCB 2024 v1.0 — National Fossil Carbon Emissions
# **Input:** data/bunkers/gcb-2024/National_Fossil_Carbon_Emissions_2024v1.0.xlsx
# **Output:** intermediate/emissions/bunker_timeseries.csv

# %%
from pathlib import Path

import pandas as pd
from pyprojroot import here

from fair_shares.library.exceptions import DataLoadingError
from fair_shares.library.utils import get_default_unit_registry

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
from fair_shares.library.utils import build_source_id

_running_via_papermill = emission_category is not None

if _running_via_papermill:
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
else:
    emission_category = "co2-ffi"
    source_id = "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_rcbs_co2-ffi"

project_root = here()
intermediate_dir = project_root / f"output/{source_id}/intermediate/emissions"
intermediate_dir.mkdir(parents=True, exist_ok=True)

# %%
gcb_bunker_path = (
    project_root
    / "data/bunkers/gcb-2024/National_Fossil_Carbon_Emissions_2024v1.0.xlsx"
)
print(f"Loading GCB bunker data from: {gcb_bunker_path}")

if not gcb_bunker_path.exists():
    raise DataLoadingError(f"GCB bunker fuel file not found: {gcb_bunker_path}")

gcb_sheet = pd.read_excel(
    gcb_bunker_path,
    sheet_name="Territorial Emissions",
    header=11,
    index_col=0,
)

bunker_col = gcb_sheet["Bunkers"].dropna()


def _is_year(v):
    try:
        return 1800 <= int(v) <= 2200
    except (ValueError, TypeError):
        return False


bunker_col = bunker_col[bunker_col.index.map(_is_year)]
bunker_col.index = bunker_col.index.astype(int)

# Convert MtC/yr -> MtCO2/yr
ur = get_default_unit_registry()
conversion = (1 * ur("Mt C")).to("Mt CO2").magnitude
bunker_col = bunker_col * conversion
print(f"  Unit conversion: MtC -> MtCO2 (factor: {conversion:.4f})")

# Build standard single-row DataFrame with source index and string year columns
years = sorted(bunker_col.index)
bunker_df = pd.DataFrame(
    [bunker_col[years].values],
    columns=[str(int(y)) for y in years],
    index=pd.Index(["bunkers"], name="source"),
)

output_path = intermediate_dir / "bunker_timeseries.csv"
bunker_df.reset_index().to_csv(output_path, index=False)
print(f"Saved bunker timeseries to: {output_path}")
print(f"  Year range: {min(years)}-{max(years)}")
print(f"  Last year value: {bunker_df[str(max(years))].iloc[0]:.1f} MtCO2/yr")
