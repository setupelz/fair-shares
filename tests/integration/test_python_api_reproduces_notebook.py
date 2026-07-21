"""The Python API reproduces notebook 601, series for series.

``fair_shares.library.python_api.calculate_allocation_timeseries`` was extracted
from notebook 601 (§4-§6). This test guards against drift: for a spread of
single allocations it re-runs the API and asserts the resulting pathways equal
the ones the notebook wrote.

The notebook outputs are pre-saved fixtures under ``tests/fixtures/python_api/``
(example-country slices of the distributed pathways for the
``ar6_2020 / 1.5C / 0.5`` anchor). Regenerate them -- e.g. after changing the
notebook or the ported §5/§6 -- with::

    uv run python tests/fixtures/save_python_api_fixture.py

Running the API needs the processed input data under
``output/<source_id>/intermediate/processed``. Rather than trigger a long
Snakemake rebuild mid-test on a machine that has never built it, the test
skips with instructions when that tree is absent (the fixture script above
builds it as a side effect).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pyprojroot import here

from fair_shares.library.python_api import calculate_allocation_timeseries
from fair_shares.library.utils.data.config import build_data_config

FIXTURE_DIR = here() / "tests/fixtures/python_api"
EXAMPLE_COUNTRIES = ["DEU", "FRA", "USA", "CHN", "IND", "BRA", "POL"]

# The anchor + data sources the fixtures were saved for (notebook 601 defaults).
ANCHOR = {"rcb_source": "ar6_2020", "climate_assessment": "1.5C", "quantile": 0.5}
SOURCES = {
    "emissions_source": "primap-202503",
    "gdp_source": "wdi-2025",
    "population_source": "un-owid-2025",
    "gini_source": "unu-wider-2025",
    "lulucf_source": "melo-2026",
}

# Columns that identify one series (exclude provenance + per-country value
# columns, which the year-value comparison covers or which vary in null repr).
_ID_KEYS = [
    "iso3c",
    "category",
    "emission-category",
    "approach",
    "source",
    "climate-assessment",
    "quantile",
    "allocation-year",
    "first-allocation-year",
    "preserve-allocation-year-shares",
    "preserve-first-allocation-year-shares",
    "cumulative-end-year",
    "pre-allocation-responsibility-weight",
    "capability-weight",
    "pre-allocation-responsibility-year",
    "pre-allocation-responsibility-per-capita",
    "capability-per-capita",
    "pre-allocation-responsibility-exponent",
    "capability-exponent",
    "pre-allocation-responsibility-functional-form",
    "capability-functional-form",
    "capability-reference-year",
    "shape",
    "deviation-end-year",
    "nonco2-debt-mode",
    "convergence-year",
]

# Representative single allocations, each covering a distinct code path.
CASES = [
    pytest.param(
        "co2-ffi",
        {
            "equal-per-capita-budget": {
                "allocation_year": 2015,
                "preserve_allocation_year_shares": True,
            }
        },
        "half-sine",
        2050,
        None,
        id="co2-ffi-EPC",
    ),
    pytest.param(
        "co2-ffi",
        {
            "equal-per-capita-budget": {
                "allocation_year": 2015,
                "cumulative_end_year": 2050,
                "preserve_allocation_year_shares": False,
            }
        },
        "exponential",
        2100,
        None,
        id="co2-ffi-ECPC",
    ),
    pytest.param(
        "all-ghg",
        {
            "equal-per-capita-budget": {
                "allocation_year": 2015,
                "preserve_allocation_year_shares": True,
            }
        },
        "half-sine",
        2050,
        "free-rider",
        id="all-ghg-EPC-free-rider",
    ),
    pytest.param(
        "all-ghg",
        {
            "equal-per-capita-budget": {
                "allocation_year": 2015,
                "preserve_allocation_year_shares": True,
            }
        },
        "exponential",
        2075,
        "co2-debit",
        id="all-ghg-EPC-co2-debit",
    ),
    pytest.param(
        "all-ghg",
        {
            "per-capita-adjusted-budget": {
                "allocation_year": 2015,
                "capability_weight": 1.0,
                "capability_functional_form": "power",
                "capability_exponent": 1.0,
                "capability_per_capita": True,
                "capability_reference_year": 2014,
                "preserve_allocation_year_shares": True,
            }
        },
        "half-sine",
        2050,
        "co2-debit",
        id="all-ghg-PCA-capability",
    ),
    pytest.param(
        "all-ghg-ex-co2-lulucf",
        {
            "equal-per-capita-budget": {
                "allocation_year": 2015,
                "cumulative_end_year": 2050,
                "preserve_allocation_year_shares": False,
            }
        },
        "half-sine",
        2100,
        "free-rider",
        id="all-ghg-ex-ECPC",
    ),
]


def _require_processed_data(category: str) -> None:
    """Skip unless the processed input tree for this category has been built."""
    active_sources = {
        "target": "rcbs",
        "emissions": SOURCES["emissions_source"],
        "gdp": SOURCES["gdp_source"],
        "population": SOURCES["population_source"],
        "gini": SOURCES["gini_source"],
        "lulucf": SOURCES["lulucf_source"],
    }
    _, source_id = build_data_config(category, active_sources)
    processed = here() / "output" / source_id / "intermediate" / "processed"
    if not processed.is_dir():
        pytest.skip(
            f"processed input data not built ({processed.relative_to(here())}); "
            "build it by running notebook 601 or "
            "tests/fixtures/save_python_api_fixture.py"
        )


def _fixture(category: str) -> pd.DataFrame:
    path = FIXTURE_DIR / f"distributed_{category}.parquet"
    if not path.is_file():
        pytest.skip(
            f"missing fixture {path.name}; regenerate with "
            "tests/fixtures/save_python_api_fixture.py"
        )
    return pd.read_parquet(path)


def _pair_on_identity(api: pd.DataFrame, fixture: pd.DataFrame) -> pd.DataFrame:
    """Left-join every API row onto its fixture twin by identity; assert 1:1."""
    keys = [k for k in _ID_KEYS if k in api.columns and k in fixture.columns]

    def norm(df: pd.DataFrame) -> pd.DataFrame:
        out = df[keys].copy()
        for c in keys:
            out[c] = out[c].astype(object).where(df[c].notna(), "NA").astype(str)
        return out

    left = norm(api).assign(_ai=range(len(api)))
    right = norm(fixture).assign(_fi=range(len(fixture)))
    merged = left.merge(right, on=keys, how="left", indicator=True)
    unmatched = int((merged["_merge"] != "both").sum())
    assert unmatched == 0, f"{unmatched}/{len(api)} API rows have no fixture twin"
    assert merged["_fi"].is_unique, "an API row matched more than one fixture row"
    return merged


@pytest.mark.parametrize("category,allocation,shape,dev_year,mode", CASES)
def test_python_api_reproduces_notebook(category, allocation, shape, dev_year, mode):
    _require_processed_data(category)
    fixture = _fixture(category)

    result = calculate_allocation_timeseries(
        emission_category=category,
        allocation=allocation,
        shape=shape,
        deviation_end_year=dev_year,
        convergence_year=2050,
        nonco2_debt_mode=mode,
        pathway_end_year=2100,
        base_share_floor_mt=0.001,
        desired_harmonisation_year=2020,
        allocation_folder="601_esabcc_2023",
        project_root=here(),
        **ANCHOR,
        **SOURCES,
    )
    api = result.allocation_timeseries.reset_index()
    api = api[api["iso3c"].isin(EXAMPLE_COUNTRIES)].reset_index(drop=True)
    assert len(api) > 0

    merged = _pair_on_identity(api, fixture)

    year_cols = [c for c in fixture.columns if str(c).isdigit()]
    api_vals = api[year_cols].to_numpy(float)
    fix_vals = fixture.iloc[merged["_fi"].to_numpy(int)][year_cols].to_numpy(float)
    both_nan = np.isnan(api_vals) & np.isnan(fix_vals)
    diff = np.where(both_nan, 0.0, np.abs(api_vals - fix_vals))
    assert np.nanmax(diff) < 1e-6, f"max year-value diff {np.nanmax(diff)}"
