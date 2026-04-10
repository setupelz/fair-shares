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
# # 604 — Reproducing Van den Berg et al. 2020: Implications of various effort-sharing approaches for national carbon budgets and emission pathways
#
# **Paper:** Van den Berg, N.J., van Soest, H.L., Hof, A.F., den Elzen, M.G.J.,
# van Vuuren, D.P., Chen, W., Drouet, L., Emmerling, J., Fujimori, S., Hoehne, N.,
# Koberle, A.C., McCollum, D.L., Schaeffer, R., Shekhar, S., Vishwanathan, S.S.,
# Vrontisi, Z., Blok, K. (2020). Implications of various effort-sharing approaches
# for national carbon budgets and emission pathways. *Climatic Change*, 162, 1805-1822.
#
# **DOI:** https://doi.org/10.1007/s10584-019-02368-y
#
# **Approach(es) reproduced:**
# - Grandfathering (GF*)
# - Immediate Equal Per Capita (IEPC*)
# - Per Capita Convergence (PCC*)
# - Equal Cumulative Per Capita (ECPC*)
# - Ability to Pay (AP*)
# - Greenhouse Development Rights (GDR*)
# - Cost-optimal (CO*)
#
# This notebook implements the pathway-based approaches. Budget analogues
# can also be computed via `equal-per-capita-budget` and `per-capita-adjusted-budget`.

# %% [markdown]
# ---
# ## 1. Method Extraction
#
# Van den Berg et al. 2020 evaluate six effort-sharing approaches plus a cost-optimal
# reference from IAMs. Equations are taken from SI Table S.1. All approaches allocate
# either a cumulative carbon budget $B$ (2011-2100) or annual emission allowances
# $a_{i,t}$ for region $i$ in year $t$.
#
# **Common notation:**
# - $i$ = region/country
# - $t$ = year
# - $e_{i,t}$ = regional emissions in year $t$
# - $E_t$ = global emissions in year $t$
# - $pop_{i,t}$ = regional population
# - $POP_t$ = global population
# - $B$ = global carbon budget (2011-2100)
# - $A_t$ = global emission allowance in year $t$
# - $gdp_{i,t}$, $GDP_t$ = regional and global GDP
# - $bau_{i,t}$, $BAU_t$ = regional and global baseline (BAU) emissions
#
# ### 1.1 Grandfathering (GF*)
#
# Budget allocation proportional to base-year (2010) emission shares:
#
# $$b_i^{GF*} = \frac{e_{i,2010}}{E_{2010}} \cdot B$$
#
# Pathway allocation:
#
# $$a_{i,t}^{GF} = \frac{e_{i,2010}}{E_{2010}} \cdot A_t$$
#
# This allocates future emissions in proportion to current emission shares,
# effectively rewarding historically high emitters.
#
# ### 1.2 Immediate Equal Per Capita (IEPC*)
#
# Budget allocation proportional to cumulative population share over 2010-2100:
#
# $$b_i^{IEPC*} = \frac{\sum_{t=2010}^{2100} pop_{i,t}}{\sum_{t=2010}^{2100} POP_t} \cdot B$$
#
# Pathway allocation (annual population shares):
#
# $$a_{i,t}^{IEPC} = \frac{pop_{i,t}}{POP_t} \cdot A_t$$
#
# ### 1.3 Per Capita Convergence (PCC*)
#
# **Budget** — weighted blend of GF* and IEPC* budgets:
#
# $$b_i^{PCC*} = (1 - w) \cdot b_i^{GF*} + w \cdot b_i^{IEPC*}$$
#
# where $w \in [0, 1]$ is the weighting factor (default: 0.5).
#
# **Pathway** — linear convergence from GF shares to EPC shares by convergence year
# $t_{conv}$, consistent with paper §1.3 prose and the library implementation
# (`per_capita_convergence.py:138-157`):
#
# $$a_{i,t}^{PCC} = A_t \cdot \left[ M(t) \cdot \frac{e_{i,2010}}{E_{2010}} + (1 - M(t)) \cdot \frac{pop_{i,t}}{POP_t} \right]$$
#
# where the GF weight is
#
# $$M(t) = \begin{cases} 1 & t \le 2010 \\ \dfrac{t_{conv} - t}{t_{conv} - 2010} & 2010 < t < t_{conv} \\ 0 & t \ge t_{conv} \end{cases}$$
#
# (The raw equation in SI Table S.1 is OCR-mangled; the form above was re-derived
# from the paper's prose description and the library implementation.)
#
# Default convergence year: the questionnaire (SI Table S.3) was tied 3/3 between
# 2050 and 2075 (with 2 votes for 2100 and 1 for 2060). We lead with 2050 as the
# first sweep value, but neither year is uniquely the default.
#
# ### 1.4 Equal Cumulative Per Capita (ECPC*)
#
# Computes a historical emissions "debt" $Debt_i$ for each country:
#
# $$Debt_i = \sum_{t=s}^{2010} \left(\frac{pop_{i,t}}{POP_t} \cdot E_t \cdot d_t - e_{i,t} \cdot d_t\right)$$
#
# where $s$ is the historical start year (default: 1970 per the paper's expert-elicited
# package of discount_rate=2% + start_year=1970; individual expert votes favoured
# 1850 but the combined default was 1970), $d_t$ is a discount factor.
# The discount factor is defined such that more recent emissions are weighted more heavily
# (default discount rate: 2%, meaning $d_t$ grows at 2% per year towards the present).
#
# Paper §2.4 is explicit: "the discount rate range of 1.6-2.8% per year was used,
# with a median estimate of 2% from literature". The paper's `df=2` therefore maps
# unambiguously to 2%/yr, and fair-shares' `historical_discount_rate=0.02` is the
# matching parameter. The two implementations differ in *where* the discount is
# applied: the paper uses it inside the ECPC* debt accumulation (a sum of per-year
# differences); fair-shares uses it inside the responsibility multiplicative
# rescaling. Same rate, different point of application — see Mapping Audit and
# cumulative-per-capita-convergence docstring for the solver-vs-debt distinction.
#
# Budget allocation:
#
# $$b_i^{ECPC*} = \frac{\sum_{t=2010}^{2100} pop_{i,t}}{\sum_{t=2010}^{2100} POP_t} \cdot B + Debt_i$$
#
# This is IEPC* plus a correction for historical over/under-emission.
#
# ### 1.5 Ability to Pay (AP*)
#
# A three-step process allocating reductions from BAU based on GDP per capita cubed:
#
# **Step 1:** Uncorrected reductions proportional to $(gdp/pop)^3$ share:
#
# $$re_i^{AP*} = \frac{\sum_{t=2010}^{2100} (gdp_{i,t}/pop_{i,t})^3}{\sum_{t=2010}^{2100} (GDP_t/POP_t)^3} \cdot \left(\sum_{t=2010}^{2100} BAU_t - B\right) \cdot \frac{\sum_{t=2010}^{2100} bau_{i,t}}{\sum_{t=2010}^{2100} BAU_t}$$
#
# **Step 2:** Global correction factor to ensure reductions sum to required total:
#
# $$corr\_re = \frac{\sum_i re_i^{AP*}}{\sum_{t=2010}^{2100} BAU_t - B}$$
#
# **Step 3:** Budget after correction:
#
# $$b_i^{AP*} = \sum_{t=2010}^{2100} bau_{i,t} - \frac{re_i^{AP*}}{corr\_re}$$
#
# Default: GDP in PPP, with participation threshold of USD 5,500 PPP from 2050.
#
# ### 1.6 Greenhouse Development Rights (GDR*)
#
# Allocates reductions from BAU using a Responsibility-Capability Index (RCI):
#
# **Step 1:** Uncorrected reductions per year based on RCI and BAU surplus:
#
# $$re_{i,t}^{GDR*} = \left(\frac{gdp_{i,t}/pop_{i,t}}{GDP_t/POP_t}\right)^3 \cdot \frac{BAU_t - A_t}{BAU_t} \cdot bau_{i,t}$$
#
# Note: The full GDR* formulation uses an RCI that combines cumulative historical
# emissions (responsibility) and GDP per capita above a development threshold
# (capability). The weighting between responsibility and capability defaults to 0.5/0.5.
# The historical start year defaults to 1850.
#
# **Step 2:** Global correction factor per year:
#
# $$corr\_re_t = \frac{\sum_i re_{i,t}^{GDR*}}{BAU_t - A_t}$$
#
# **Step 3:** Allowances after correction:
#
# $$a_{i,t}^{GDR*} = bau_{i,t} - \frac{re_{i,t}^{GDR*}}{corr\_re_t}$$
#
# Budget is the sum of annual allowances:
#
# $$b_i^{GDR*} = \sum_{t=2010}^{2100} a_{i,t}^{GDR*}$$
#
# ### 1.7 Cost-Optimal (CO*)
#
# Derived from IAM scenarios in the CD-LINKS database. Emission reductions are
# allocated where cheapest globally, starting from 2020. This is not an equity-based
# approach but serves as a comparison benchmark.
#
# **Not expressible in fair-shares** — requires IAM scenario data.

# %% [markdown]
# ---
# ## 2. Mapping to fair-shares
#
# | Paper approach | fair-shares function | Key parameters | Notes |
# |---|---|---|---|
# | GF* (Grandfathering) | `per-capita-convergence` | `first_allocation_year=2010`, `convergence_year=9999` | Setting convergence far in the future holds GF shares indefinitely. |
# | IEPC* pathway | `equal-per-capita` | `first_allocation_year=2010` | Annual population shares applied to global pathway — exactly the paper's Eq. for the pathway variant. |
# | PCC* budget (w=0.5) | Composition: `equal-per-capita-budget` + `per-capita-adjusted-budget` | `allocation_year=2010`, weight GF and IEPC budget outputs | Paper Eq. is a weighted blend of GF* and IEPC* budgets; no single fair-shares function produces both in one call. |
# | PCC* pathway | `per-capita-convergence` | `first_allocation_year=2010`, `convergence_year=[2050, 2075, 2100]` | Linear GF-to-EPC blending; direct structural match. |
# | ECPC* | Composition: `equal-per-capita-budget` + post-processing | `allocation_year={1850,1970,1990}`, `cumulative_end_year=2100` | Step 1 (entitlement) runs below in the ECPC* cell. Steps 2–3 (subtract actual emissions, distribute over time) are post-processing. Negative remaining budgets for high historical emitters (the paper's headline result for USA and Russia) are a consequence of Step 2. |
# | AP* (Ability to Pay) | — | — | Requires baseline (no-policy) emissions and GDP-per-capita cubed weighting of reductions from BAU. fair-shares has no BAU-reduction engine; this framing is not expressible via share adjustment. |
# | GDR* | — | — | Requires RCI (responsibility + capability with luxury development threshold) and baseline emissions. The BAU-reduction framing is not expressible in fair-shares. |
# | CO* (Cost-optimal) | — | — | Derived from IAM scenarios (CD-LINKS); not expressible via fair-shares. |

# %% [markdown]
# ---
# ## 3. Configuration

# %%
# =============================================================================
# CONFIGURATION
# =============================================================================

allocation_folder = "604_vandenberg_2020"

# The paper's default expert choice was total CO2 incl. LULUCF (7 of 9 experts).
# However, the paper also presents energy/industry CO2 as a sensitivity case,
# and the "co2" category in fair-shares requires NGHGI preprocessing (notebooks
# 105/107) which may not yet be available. We use "co2-ffi" (fossil fuel and
# industrial CO2) which the paper explicitly includes as a comparison.
# To reproduce the paper's default, change to "co2" after running NGHGI preprocessing.
emission_category = "co2-ffi"

active_sources = {
    "target": "rcb-pathways",
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
    # "lulucf": "melo-2026",  # Only needed for "co2" (incl. LULUCF) categories
    "rcb_generator": "exponential-decay",
}

# -------------------------------------------------------------------------
# ALLOCATION APPROACH CONFIGURATIONS
# -------------------------------------------------------------------------

allocations = {
    # APPROACH 1: IEPC* pathway — §1.2, annual population shares applied to global pathway
    "equal-per-capita": [
        {
            "first_allocation_year": [2010],
            "preserve_first_allocation_year_shares": [False],
        }
    ],
    # APPROACH 2: PCC* pathway — §1.3, linear blend GF→EPC by convergence year
    "per-capita-convergence": [
        {
            "first_allocation_year": [2010],
            "convergence_year": [2050, 2075, 2100],
        }
    ],
    # APPROACH 3: ECPC* budget entitlement (§1.4) — runs in the ECPC* cell below §4
    # using equal-per-capita-budget with allocation_year={1850,1970,1990}.
    # Downstream: subtract actual emissions (Debt_i), distribute over time.
}

# GF* (§1.1): expressible as per-capita-convergence with convergence_year=9999
# but not run — preserves current emission shares.

# AP* (§1.5): requires BAU emissions and (gdp/pop)^3 weighting of reductions.
# fair-shares has no BAU-reduction engine.

# GDR* (§1.6): requires RCI with development threshold and BAU emissions.
# Not expressible in fair-shares.

# CO* (§1.7): derived from IAM scenarios (CD-LINKS). Not expressible.

EXAMPLE_COUNTRIES = ["USA", "CHN", "IND", "DEU", "BRA", "JPN", "RUS"]
PLOT_START_YEAR = 2010
desired_harmonisation_year = 2020

# %% [markdown]
# ---
# ## 4. Run Allocation

# %%
import matplotlib.pyplot as plt
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.notebook_helpers import (
    load_allocation_data,
    print_results_summary,
    run_all_allocations,
)
from fair_shares.library.utils import (
    convert_parquet_to_wide_csv,
    setup_data,
)
from fair_shares.library.utils.data.config import (
    is_composite_category,
    validate_data_source_config,
)
from fair_shares.library.visualization import plot_example_result

plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()

validation = validate_data_source_config(emission_category, active_sources)
if not validation["valid"]:
    raise ConfigurationError(
        "Configuration errors:\n" + "\n".join(f"  - {i}" for i in validation["issues"])
    )

target = active_sources["target"]
if target != "rcbs" or is_composite_category(emission_category):
    harmonisation_year = desired_harmonisation_year
else:
    harmonisation_year = None

# %%
from fair_shares.library.utils.data.config import build_data_config, get_final_categories
from fair_shares.library.utils.data.setup import build_data_paths

try:
    setup_info = setup_data(
        project_root=project_root,
        emission_category=emission_category,
        active_sources=active_sources,
        harmonisation_year=harmonisation_year,
        verbose=True,
    )
    source_id = setup_info["source_id"]
    processed_dir = setup_info["paths"]["processed_dir"]
    original_emission_category = emission_category
    emission_category = setup_info["emission_category"]
    final_categories = setup_info["final_categories"]
    harmonisation_year = setup_info["config"].harmonisation_year
except Exception as e:
    print(f"Snakemake pipeline failed ({type(e).__name__}), checking for existing data...")
    data_config, source_id = build_data_config(
        emission_category, active_sources, harmonisation_year=harmonisation_year
    )
    paths = build_data_paths(project_root, source_id, emission_category, target=target)
    processed_dir = paths["processed_dir"]
    original_emission_category = emission_category
    final_categories = get_final_categories(target, emission_category)
    harmonisation_year = data_config.harmonisation_year

    if processed_dir.exists():
        print(f"Found existing processed data at: {processed_dir}")
        print("Proceeding with existing data.")
    else:
        raise RuntimeError(
            f"No processed data found at {processed_dir}. "
            "Run the preprocessing pipeline first."
        ) from e

# %%
loaded_data = load_allocation_data(
    processed_dir=processed_dir,
    target=target,
    final_categories=final_categories,
    emission_category=emission_category,
)

output_dir = project_root / "output" / source_id / "allocations" / allocation_folder

data_context = {
    "source-id": source_id,
    "allocation-folder": allocation_folder,
    "emission-category": emission_category,
    "target-source": target,
    "emissions-source": active_sources["emissions"],
    "gdp-source": active_sources["gdp"],
    "population-source": active_sources["population"],
    "gini-source": active_sources["gini"],
}

param_manifest_rows = run_all_allocations(
    allocations=allocations,
    loaded_data=loaded_data,
    output_dir=output_dir,
    data_context=data_context,
    target=target,
    final_categories=final_categories,
    harmonisation_year=harmonisation_year,
)

# %%
fig = plot_example_result(
    output_dir=output_dir,
    countries=EXAMPLE_COUNTRIES,
    plot_start_year=PLOT_START_YEAR,
    processed_dir=processed_dir,
    emission_category=original_emission_category,
    final_categories=final_categories,
)
plt.show()

# %%
print_results_summary(
    output_dir=output_dir,
    param_manifest_rows=param_manifest_rows,
    allocations=allocations,
)

# %%

# %% [markdown]
# ### ECPC*: Budget entitlement (Step 1 of composition)
#
# Van den Berg's ECPC* starts by computing per-country cumulative
# entitlements from a historical year. This is Step 1 of the
# composition. Step 2 (subtract actual emissions) and Step 3
# (distribute remainder over time) are post-processing outside
# the library.

# %%
# Run budget allocation for ECPC* entitlement computation.
# Uses rcbs target (separate from the rcb-pathways target above).

ecpc_sources = {**active_sources, "target": "rcbs"}
ecpc_sources.pop("rcb_generator", None)  # not needed for budget target

ecpc_setup = setup_data(
    project_root=project_root,
    emission_category="co2-ffi",
    active_sources=ecpc_sources,
    harmonisation_year=None,
    verbose=True,
)

ecpc_data = load_allocation_data(
    processed_dir=ecpc_setup["paths"]["processed_dir"],
    target="rcbs",
    final_categories=["co2-ffi"],
    emission_category="co2-ffi",
)

ecpc_allocations = {
    "equal-per-capita-budget": [
        {
            # TODO: Paper uses 1850 as a historical start year, but fair-shares
            # validates allocation_year >= 1900. Relaxing this requires reviewing
            # data availability (emissions, population) pre-1900.
            "allocation_year": [1970, 1990],
            "cumulative_end_year": [2100],
            "preserve_allocation_year_shares": [False],
        },
    ],
}

ecpc_output_dir = project_root / "output" / ecpc_setup["source_id"] / "allocations" / "604_vandenberg_2020_ecpc"

ecpc_context = {
    "source-id": ecpc_setup["source_id"],
    "allocation-folder": "604_vandenberg_2020_ecpc",
    "emission-category": "co2-ffi",
    "target-source": "rcbs",
    "emissions-source": active_sources["emissions"],
    "gdp-source": active_sources["gdp"],
    "population-source": active_sources["population"],
    "gini-source": active_sources["gini"],
}

run_all_allocations(
    allocations=ecpc_allocations,
    loaded_data=ecpc_data,
    output_dir=ecpc_output_dir,
    data_context=ecpc_context,
    target="rcbs",
    final_categories=["co2-ffi"],
    harmonisation_year=None,
)

print()
print(f"ECPC* entitlements written to: {ecpc_output_dir}")
print("To match van den Berg's full ECPC*:")
print("  1. Load the entitlements from the parquet above")
print("  2. Subtract each country's actual cumulative emissions (t_hist to present)")
print("  3. Negative remainders = historical debt")
print("  4. Distribute the remaining budget over time via a convergence pathway")

# %% [markdown]
# ---
# ## 5. Implementation Notes
#
# This notebook implements van den Berg et al.'s allocation methodology using
# fair-shares' canonical data stack. The equations in § 1 are realised with the
# configurations in § 3; this section documents the implementation choices.
#
# ### 5.1 Data stack
#
# The `active_sources` dict in § 3 specifies the following sources:
#
# - **Emissions:** `primap-202503` — historical country-level CO2-FFI emissions
# - **GDP:** `wdi-2025` — World Bank GDP data (PPP)
# - **Population:** `un-owid-2025` — UN population projections via Our World in Data
# - **Gini:** `unu-wider-2025` — income inequality data
# - **Target / global pathway:** `rcb-pathways` — global pathways derived from
#   remaining carbon budgets, with `exponential-decay` shape
#
# The paper's default emission category is total CO2 including LULUCF; this
# notebook uses `co2-ffi` (fossil fuel and industrial CO2), which the paper
# includes as a comparison case. Switching to total CO2 requires NGHGI
# preprocessing (notebooks 105/107).
#
# ### 5.2 Key architectural choices
#
# Van den Berg et al. construct allocations via two distinct paradigms: (1)
# share-of-global-pathway approaches (IEPC*, PCC*, ECPC*) and (2) BAU-reduction
# approaches (AP*, GDR*). fair-shares operates in the share-of-pathway paradigm
# throughout; only approaches in category (1) are expressible.
#
# IEPC* and PCC* map directly to `equal-per-capita` and `per-capita-convergence`
# respectively — the underlying equations are identical.
#
# For ECPC*, the paper subtracts actual historical emissions from each country's
# cumulative per-capita entitlement, producing negative budgets for high
# historical emitters (the headline result for USA and Russia). Step 1 —
# computing the per-country entitlement — is demonstrated in the ECPC* cell
# above via `equal-per-capita-budget(allocation_year={1850,1970,1990},
# cumulative_end_year=2100)`. Steps 2 and 3 are post-processing: subtract each
# country's actual cumulative emissions from the entitlement (Step 2); distribute
# the remainder over time (Step 3). Negative budgets for high historical emitters
# are the natural result of Step 2.
#
# AP* and GDR* allocate *reductions from BAU* using cubic GDP-per-capita
# weighting (AP*) and an RCI with development threshold (GDR*). fair-shares has
# no BAU-reduction engine — these approaches are not expressible and are not run
# in this notebook. See § 2 mapping table for the structural gap.
#
# ### 5.3 Where fair-shares and van den Berg differ on inputs
#
# The paper operates at the regional level (11 IMAGE regions in the CD-LINKS
# framework). fair-shares operates country-level throughout, aggregating to
# regions only on output. The global budget construction also differs: the paper
# uses a fixed budget (1075 GtCO2 main, 400 GtCO2 sensitivity); this notebook
# uses rcb-pathways, which generates a range of budgets from RCB scenarios.
#
# Downstream users comparing fair-shares output to van den Berg's published
# figures should expect differences driven by the data stack choices listed
# above (emission category, GDP source, population projections), and the mechanism
# difference for ECPC* (Step 1 is now demonstrated; Steps 2–3 remain post-processing).
# AP* and GDR* are not run — they require BAU-reduction framing not available in fair-shares.

# %%
