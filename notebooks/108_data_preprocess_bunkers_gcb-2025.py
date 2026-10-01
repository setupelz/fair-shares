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
# # International Bunker Fuel CO2 Preprocessing (GCB 2025)
#
# International bunkers are the sum of international shipping (`XIS`) and
# international aviation (`XIA`) in the Global Carbon Budget 2025 flat file,
# 1850 to 2024, in MtCO2 per year. Both series start in 1950; earlier years
# are blank in the file and count as zero. Bunker emissions are subtracted
# from global RCBs before country-level allocation.
#
# **Source:** Andrew and Peters (2025), doi:10.5281/zenodo.17417124
# **Input:** data/emissions/gcb-2025/GCB2025v15_MtCO2_flat.csv
# **Output:** intermediate/emissions/bunker_timeseries.csv

# %%
import pandas as pd
from pyprojroot import here

from fair_shares.library.utils import build_source_id
from fair_shares.library.utils.data.gcb import gcb_bunkers

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
if emission_category is not None and source_id is None:
    source_id = build_source_id(
        emissions=active_emissions_source,
        gdp=active_gdp_source,
        population=active_population_source,
        gini=active_gini_source,
        lulucf=active_lulucf_source,
        target=active_target_source,
        emission_category=emission_category,
    )
elif source_id is None:
    source_id = "gcb-2025_wdi-2025_un-owid-2025_wdi-2025_rcbs_co2-ffi"

project_root = here()
intermediate_dir = project_root / f"output/{source_id}/intermediate/emissions"
intermediate_dir.mkdir(parents=True, exist_ok=True)

# %%
raw = pd.read_csv(project_root / "data/emissions/gcb-2025/GCB2025v15_MtCO2_flat.csv")
bunkers = gcb_bunkers(raw)

output_path = intermediate_dir / "bunker_timeseries.csv"
bunkers.reset_index().to_csv(output_path, index=False)
print(f"Saved bunker timeseries to: {output_path}")
print(f"  Year range: {bunkers.columns[0]}-{bunkers.columns[-1]}")
print(f"  Last year value: {bunkers.iloc[0, -1]:.1f} MtCO2/yr")
