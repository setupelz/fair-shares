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
# # 602 — Reproducing Dekker et al. 2025: Navigating the black box of fair national emissions targets
#
# **Paper:** Dekker, M. M., Hof, A. F., du Robiou Pont, Y., van den Berg, N.,
# Daioglou, V., den Elzen, M., van Heerden, R., Hooijschuur, E.,
# Schmidt Tagomori, I., Würschinger, C., & van Vuuren, D. P. (2025).
# Navigating the black box of fair national emissions targets.
# *Nature Climate Change*, 15, 752–759.
#
# **DOI:** [10.1038/s41558-025-02361-7](https://doi.org/10.1038/s41558-025-02361-7)
#
# **Approaches**
#
# 1. Grandfathering (GF) — proportional reduction from current emissions (Eq. 2)
# 2. Immediate Per Capita (PC) — allocation proportional to population (Eq. 3)
# 3. Per Capita Convergence (PCC) — linear blend from GF to PC (Eq. 4)
# 4. Equal Cumulative Per Capita (ECPC) — cumulative population-weighted budget
#    with historical discounting and sine-deviation convergence (Eqs. 5–8)
# 5. Ability to Pay (AP) — GDP per capita with cube-root cost equalization (Eqs. 9–10)
# 6. Greenhouse Development Rights (GDR) — RCI-based to 2030, then AP (Eqs. 11–12)
#
# This notebook uses `co2-ffi`; Dekker uses all-GHG including LULUCF.

# %% [markdown]
# ---
# ## 1. Method Extraction
#
# All equations below are extracted from the Methods section of Dekker et al. (2025).
# Variable notation follows the paper. $E(t, c)$ denotes allocated emissions for
# country $c$ at time $t$; $E(t, c_w)$ denotes global emissions; $P(t, c, s)$ denotes
# population under socio-economic scenario $s$; $t_0 = 2021$ is the analysis starting year.
#
# ### 1.1 Grandfathering (GF) — Eq. 2
#
# All countries reduce proportionally from their current emissions share:
#
# $$
# E_{\mathrm{GF}}(t, c) = \frac{E(t_0, c)}{E(t_0, c_w)} \times E(t, c_w)
# $$
#
# This preserves the relative distribution of emissions across countries — wealthy,
# high-emitting countries retain their share. The paper notes this is "argued to be
# not equitable" (Table 2) but includes it as a reference.
#
# ### 1.2 Immediate Per Capita (PC) — Eq. 3
#
# Allocations are immediately proportional to population:
#
# $$
# E_{\mathrm{PC}}(t, c) = \frac{P(t_0, c, s)}{P(t_0, c_w, s)} \times E(t, c_w)
# $$
#
# Note: the paper uses $t_0$ population for all years (static shares), not
# time-varying population. This means country shares are frozen at 2021 and
# do not track demographic change within the projection horizon.
#
# ### 1.3 Per Capita Convergence (PCC) — Eq. 4
#
# Linear blend from grandfathering to per capita over a convergence period:
#
# $$
# E_{\mathrm{PCC}}(t, c, t_{\mathrm{conv}}) = E_{\mathrm{GF}}(t, c) \times M\!\left(\frac{t_{\mathrm{conv}} - t}{t_{\mathrm{conv}} - t_0}\right) + E_{\mathrm{PC}}(t, c) \times \left(1 - M\!\left(\frac{t_{\mathrm{conv}} - t}{t_{\mathrm{conv}} - t_0}\right)\right)
# $$
#
# where $M(x) = \max(0, \min(1, x))$ (clamped linear). The convergence year
# $t_{\mathrm{conv}}$ is varied: 2040, 2050, 2080 in the paper's analysis.
#
# ### 1.4 Equal Cumulative Per Capita (ECPC) — Eqs. 5–8
#
# **Step 1:** Compute total cumulative entitlement based on historical + future
# population shares (Eq. 5):
#
# $$
# B'_{\mathrm{ECPC}}(c, s, t_{\mathrm{hist}}, r_d) = \frac{\sum_{t_i=t_{\mathrm{hist}}}^{t_0} P(t_i, c, s)}{\sum_{t_i=t_{\mathrm{hist}}}^{t_0} P(t_i, c_w, s)} \times \left(B(c_w) + \sum_{t_i=t_{\mathrm{hist}}}^{t_0} E(t_i, c_w) \times (1 - r_d)^{t_0 - t}\right)
# $$
#
# where $B(c_w)$ is the global remaining carbon budget, $t_{\mathrm{hist}}$ is the
# historical start year (1850, 1950, or 1990), and $r_d$ is the discount rate
# (0%, 1.6%, 2.0%, 2.8%).
#
# **Step 2:** Subtract historical emissions to get the net future budget (Eq. 6):
#
# $$
# B_{\mathrm{ECPC}}(c, s, t_{\mathrm{hist}}, r_d) = B'_{\mathrm{ECPC}}(c, s, t_{\mathrm{hist}}, r_d) - \sum_{t_i=t_{\mathrm{hist}}}^{t_0} E(t_i, c) \times (1 - r_d)^{t_0 - t}
# $$
#
# This budget can be **negative** for developed countries (historical debt).
#
# **Step 3:** Track remaining debt/leftover iteratively (Eq. 7):
#
# $$
# D(t, c, s, t_{\mathrm{hist}}, r_d) = B_{\mathrm{ECPC}}(c) - \sum_{t_i=t_0}^{t-1} E_{\mathrm{ECPC}}(t_i, c) + E_{\mathrm{PC}}(t, c)
# $$
#
# **Step 4:** Sine-shaped deviation from PCC allocation (Eq. 8):
#
# $$
# E_{\mathrm{ECPC}}(t, c) = \frac{D(t, c)}{t_{\mathrm{conv}} - t} \times \sin\!\left(\frac{t}{(t_{\mathrm{conv}} - t_0) \times \pi}\right) + E_{\mathrm{PCC}}(t, c, t_{\mathrm{conv}})
# $$
#
# Resolved against the Zenodo source (`imagepbl/effort-sharing`
# `src/effortsharing/allocation/ecpc.py`): the published Eq. 8 notation
# `sin(t / ((t_conv - t_0) × π))` is ambiguous about whether `t` is an
# absolute calendar year or an index since `t_0`. The published code uses
# `np.sin(np.arange(1, max_time_steps) / max_time_steps × π)` with `t` as an
# **integer index** since 2021 (so `t = 0` at 2021, `t = max_time_steps` at
# `conv_year`), which is the standard half-sine envelope: zero at the start,
# peak mid-convergence, zero at the end. fair-shares implements the same
# form (`convergence.py` line 616). Once the notation is read as
# "index since $t_0$", the paper, the code, and fair-shares all agree.
#
# **Additional detail**: in our reading of the published code, the sine
# envelope is multiplied by an amplitude factor of 3 (`sine_values * 3`),
# which we do not find in the published Eq. 8. fair-shares does not apply
# this factor. The effect is on the magnitude of the mid-convergence
# deviation; boundary conditions are unaffected.
#
# **Convergence boundary smoothing**: in our reading, the published code
# also applies a one-year smoothing step at the final convergence year
# (`t == max_time_steps - 1`), blending 67% PC with 33% of the prior
# year's ECPC allocation. We do not find this in the paper's equations
# and have not replicated it in fair-shares. It may reflect a numerical
# stability choice in the original implementation.
#
# **Note on Eq. 7 vs. Eq. 8 baseline:** The paper uses $E_{\mathrm{PC}}(t, c)$
# (immediate per capita) in Eq. 7 for tracking remaining debt, but
# $E_{\mathrm{PCC}}(t, c, t_{\mathrm{conv}})$ (per capita convergence) in
# Eq. 8 as the baseline from which the sine deviation is added. fair-shares'
# `evolve_shares_sine_deviation()` uses PCC for both equations — a minor
# implementation deviation that may slightly affect the debt-tracking dynamics
# but preserves the overall convergence behavior.
#
# ### 1.5 Ability to Pay (AP) — Eqs. 9–10
#
# Starts from **baseline** (no-policy) emissions and redistributes reductions
# based on GDP per capita with a cube-root cost equalization:
#
# **Step 1** — Compute first-order emissions to subtract (Eq. 9):
#
# $$
# E_{\mathrm{sub}}(t, c, s) = \sqrt[3]{\frac{\mathrm{GDP}(t,c,s) / P(t,c,s)}{\mathrm{GDP}(t,c_w,s) / P(t,c_w,s)}} \times \frac{E_{\mathrm{base}}(t, c_w, s) - E(t, c_w)}{E_{\mathrm{base}}(t, c_w, s)} \times E_{\mathrm{base}}(t, c, s)
# $$
#
# **Step 2** — Normalize and apply (Eq. 10):
#
# $$
# E_{\mathrm{AP}}(t, c, s) = E_{\mathrm{base}}(t, c, s) - (E_{\mathrm{base}}(t, c_w, s) - E(t, c_w)) \times \frac{E_{\mathrm{sub}}(t, c, s)}{\sum_{c_i} E_{\mathrm{sub}}(t, c_i, s)}
# $$
#
# In our understanding, the cube-root (1/3 exponent) is consistent with an
# assumption of quadratically increasing marginal abatement costs, which gives
# cubic total costs and equalizes mitigation costs as a fraction of GDP.
#
# **Note on exponent convention:** Dekker's AP uses $(gdp_{pc} / gdp_{pc,w})^{1/3}$
# — the cube root of the GDP-per-capita *ratio*, applied as a sub-linear scaling
# of each country's reduction. Van den Berg et al. (2020) — reproduced in nb604
# — defines AP* using $(gdp_{pc})^3$ as a *weighting* of cumulative reductions
# (SI Table S.1). Both are "ability to pay" operationalisations but with
# different exponents: Dekker's formulation moderates the capability signal
# (sub-linear), whereas van den Berg's amplifies it (super-linear). Dekker's
# code cites van den Berg but uses the inverted exponent.
#
# **Critical data requirement:** AP requires country-level baseline (no-policy)
# emissions projections ($E_{\mathrm{base}}$), obtained from the IMAGE IAM for SSP1–3.
# fair-shares does not include baseline emission scenarios.
#
# ### 1.6 Greenhouse Development Rights (GDR) — Eqs. 11–12
#
# Combines capability and responsibility via the Responsibility–Capability Index (RCI):
#
# $$
# E_{\mathrm{GDR}}^{\mathrm{only}}(t, c, s, w_{\mathrm{RCI}}, l) = E_{\mathrm{base}}(t, c, s) - (E_{\mathrm{base}}(t, c_w, s) - E(t, c_w)) \times \mathrm{RCI}(w_{\mathrm{RCI}}, l)
# $$
#
# RCI is only defined up to 2030, so a convergence to AP is applied (Eq. 12).
# In our reading of the published code (`gdr.py`), the blend reference year
# is 2030 (the last year of RCI availability), not $t_0$:
#
# $$
# E_{\mathrm{GDR}}(t, c, s) = E_{\mathrm{GDR}}^{\mathrm{only}}(t, c) \times M\!\left(\frac{t_{\mathrm{conv}} - t}{t_{\mathrm{conv}} - 2030}\right) + E_{\mathrm{AP}}(t, c, s) \times \left(1 - M\!\left(\frac{t_{\mathrm{conv}} - t}{t_{\mathrm{conv}} - 2030}\right)\right)
# $$
#
# GDR accounts for within-country wealth distribution through a luxury threshold $l$
# (development threshold below which individuals are exempt).

# %% [markdown]
# ---
# ## 2. Mapping to fair-shares
#
# | Paper approach | fair-shares function | Key parameters | Notes |
# |---|---|---|---|
# | GF (Grandfathering) | `per-capita-convergence` | `convergence_year=9999` | Setting convergence far in the future holds GF shares indefinitely. fair-shares normalizes blended shares each year; Dekker does not, but the linear blend of shares summing to 1 is analytically equivalent. Not run in this notebook. |
# | PC (Immediate Per Capita) | `equal-per-capita` | `first_allocation_year=2021`, `preserve_first_allocation_year_shares=True` | Paper uses static $t_0$ population shares; `preserve_first_allocation_year_shares=True` holds allocation-year shares constant across the horizon. |
# | PCC (Per Capita Convergence) | `per-capita-convergence` | `first_allocation_year=2021`, `convergence_year=[2040, 2050, 2080]` | Both use clamped linear blending from GF to EPC. |
# | ECPC (Equal Cumulative Per Capita) | Composition: `equal-per-capita-budget` + post-processing | `allocation_year={1850,1950,1990}`, `cumulative_end_year=2050` | Step 1 (entitlement, Eq. 5) runs below in the ECPC cell. Steps 2–3 (subtract actual emissions, distribute over time — Eqs. 6–8) are post-processing outside the library. Negative remaining budgets for high historical emitters are a natural consequence of Step 2. |
# | AP (Ability to Pay) | — | — | Requires baseline (no-policy) emissions from IAM scenarios and GDP-per-capita cube-root cost equalization. fair-shares capability adjustment modifies EPC shares by GDP, not deviations from a baseline. |
# | GDR (Greenhouse Development Rights) | — | — | Requires RCI index (weighted responsibility + capability with luxury threshold) and baseline emissions. fair-shares `per-capita-adjusted` combines responsibility and capability but not in the GDR/RCI formulation. |

# %% [markdown]
# ---
# ## 3. Configuration

# %%
# =============================================================================
# CONFIGURATION
# =============================================================================

allocation_folder = "602_dekker_2025"

emission_category = "co2-ffi"

active_sources = {
    "target": "rcb-pathways",  # pathway-based targets for convergence approaches
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
    "lulucf": "melo-2026",
    "rcb_generator": "exponential-decay",
}

desired_harmonisation_year = 2021

# -------------------------------------------------------------------------
# ALLOCATION APPROACH CONFIGURATIONS
# -------------------------------------------------------------------------

allocations = {
    # APPROACH 1: Immediate Per Capita (PC) — Eq. 3, static population shares at t0=2021
    "equal-per-capita": [
        {
            "first_allocation_year": [2021],
            "preserve_first_allocation_year_shares": [True],
        },
    ],
    # APPROACH 2: Per Capita Convergence (PCC) — Eq. 4, linear blend GF→PC
    "per-capita-convergence": [
        {
            "first_allocation_year": [2021],
            "convergence_year": [2040, 2050, 2080],
        },
    ],
    # APPROACH 3: ECPC budget entitlement (Eq. 5) — runs in the ECPC cell below §4
    # using equal-per-capita-budget with allocation_year={1850,1950,1990}.
    # Downstream: subtract actual emissions (Eq. 6), distribute via sine-deviation (Eqs. 7-8).
}

# AP (Eqs. 9-10): requires baseline (no-policy) emissions and GDP-per-capita
# cube-root cost equalization. fair-shares has no BAU-reduction engine.

# GDR (Eqs. 11-12): requires RCI index with luxury development threshold
# and baseline emissions. Not expressible in fair-shares.

EXAMPLE_COUNTRIES = ["USA", "CHN", "IND", "DEU", "BRA"]
PLOT_START_YEAR = 2015

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

# %% [markdown]
# ### ECPC: Budget entitlement (Step 1 of composition)
#
# Dekker's ECPC starts by computing per-country cumulative entitlements
# from a historical year (Eq. 5). This is Step 1 of the composition.
# Step 2 (subtract actual historical emissions per country — Eq. 6) and
# Step 3 (distribute the remainder over time via sine-deviation convergence
# — Eqs. 7–8) are post-processing outside the library.

# %%
# Run budget allocation for ECPC entitlement computation.
# Uses rcbs target (separate from the rcb-pathways target above).
from fair_shares.library.utils import setup_data as setup_data_fn

ecpc_sources = {**active_sources, "target": "rcbs"}
ecpc_sources.pop("rcb_generator", None)  # not needed for budget target

ecpc_setup = setup_data_fn(
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
            # TODO: Dekker uses 1850 as a historical start year, but fair-shares
            # validates allocation_year >= 1900. Relaxing this requires reviewing
            # data availability (emissions, population) pre-1900.
            "allocation_year": [1950, 1990],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
        },
    ],
}

ecpc_output_dir = project_root / "output" / ecpc_setup["source_id"] / "allocations" / "602_dekker_2025_ecpc"

ecpc_context = {
    "source-id": ecpc_setup["source_id"],
    "allocation-folder": "602_dekker_2025_ecpc",
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
print(f"ECPC entitlements written to: {ecpc_output_dir}")
print("To match Dekker's full ECPC (Eqs. 5–8):")
print("  1. Load the entitlements from the parquet above")
print("  2. Subtract each country's actual cumulative emissions (t_hist to present) — Eq. 6")
print("  3. Negative remainders = historical debt")
print("  4. Distribute the remaining budget over time via sine-deviation convergence — Eqs. 7–8")

# %% [markdown]
# ---
# ## 5. Implementation Notes
#
# This notebook implements Dekker et al. 2025's allocation methodology using
# fair-shares' canonical data stack. The equations in § 1 are realised with the
# configurations in § 3; this section documents the implementation choices where
# fair-shares differs from Dekker's own implementation.
#
# ### 5.1 Data stack
#
# fair-shares uses the following sources for this notebook:
#
# | Role | Source |
# |---|---|
# | Emissions pathway targets | `rcb-pathways` (exponential-decay generator) |
# | Historical emissions | `primap-202503` |
# | GDP | `wdi-2025` |
# | Population | `un-owid-2025` |
# | Gini | `unu-wider-2025` |
# | LULUCF | `melo-2026` |
# | RCB pathway shape | `exponential-decay` |
#
# Dekker et al. use all-GHG including LULUCF as the emissions scope; this
# notebook uses `co2-ffi` for cleaner library coverage. This is a substantive
# scope difference: LULUCF-heavy countries (e.g. BRA, IDN) will see materially
# different absolute allocations. fair-shares allocations here represent the
# fair-shares answer for each methodology applied to this data stack — they are
# not designed to reproduce Dekker's specific published numbers.
#
# ### 5.2 Key architectural choices
#
# **PC (Immediate Per Capita).** Dekker's Eq. 3 uses static population shares at
# $t_0$. fair-shares maps this via `equal-per-capita` with
# `preserve_first_allocation_year_shares=True`, which holds the allocation-year
# population shares constant across the projection horizon.
#
# **PCC (Per Capita Convergence).** Direct structural match: both use a clamped
# linear blend from grandfathering to per capita. fair-shares renormalises blended
# shares each year for numerical stability; Dekker's Eq. 4 does not explicitly
# renormalise, but the linear blend of shares that already sum to 1 preserves the
# sum analytically.
#
# **ECPC (Cumulative Per Capita).** Dekker's full ECPC is a three-step composition:
# (1) compute per-country cumulative entitlements from a historical year (Eq. 5),
# (2) subtract actual historical emissions to obtain a net remaining budget — which
# can be negative for developed countries (Eq. 6), (3) distribute the remainder
# over time using a sine-deviation convergence pathway (Eqs. 7–8). Step 1 is
# demonstrated in the ECPC cell above: `equal-per-capita-budget` with
# `allocation_year={1850,1950,1990}` and `cumulative_end_year=2050` computes the
# per-country entitlement (Eq. 5). Steps 2 and 3 are post-processing outside the
# library: subtract each country's actual cumulative emissions from the entitlement
# (Eq. 6), then distribute the remainder via sine-deviation convergence (Eqs. 7–8).
#
# Additionally, in our reading of Dekker's published code
# (`imagepbl/effort-sharing`), the half-sine envelope is multiplied by a factor
# of 3, which we do not find in the published Eq. 8. fair-shares does not apply
# this factor. See § 1.4 for discussion of this and the convergence boundary
# smoothing step.
#
# **AP and GDR.** Not expressible in fair-shares. AP requires country-level
# baseline (no-policy) emissions and GDP-per-capita cube-root cost equalization
# (Eqs. 9–10). GDR requires the Responsibility–Capability Index and a luxury
# development threshold (Eqs. 11–12). See § 2 mapping table for details.
#
# ### 5.3 Where fair-shares and Dekker differ on inputs
#
# | Dimension | fair-shares | Dekker |
# |---|---|---|
# | Emissions scope | `co2-ffi` | All-GHG including LULUCF |
# | Population source | UN-OWID 2025 | IIASA SSP2 (vintage unspecified in paper) |
# | GDP source | WDI 2025 | See paper for details |
# | Historical emissions | PRIMAP 2025-03 | See paper for details |
# | Analysis start year (t0) | 2021 | 2021 |
# | Aggregation | Country-level | Country-level (see paper for details) |
#
# Downstream users who want to cross-check fair-shares against Dekker's specific
# published numbers should match Dekker's data stack — emissions scope,
# population vintage, and GDP source. Without harmonising those inputs, data
# vintage and scope differences will dominate any numerical comparison.

# %%
