"""Regenerate the notebook-601 fixtures for the Python-API reproduction test.

This runs notebook 601 (the ESABCC reproduction) for a single RCB anchor via
jupytext, then saves each emission category's distributed pathways -- sliced to
a handful of example countries to keep the fixtures small -- under
``tests/fixtures/python_api/``.

``tests/integration/test_python_api_reproduces_notebook.py`` then re-runs the
Python API (``calculate_allocation_timeseries``) for representative single
allocations and asserts it reproduces these saved notebook outputs, so the API
never silently drifts from the notebook it was extracted from.

Run:  ``uv run python tests/fixtures/save_python_api_fixture.py``

Requires the processed input data (``setup_data`` uses the cached
``output/<source_id>/intermediate/processed`` tree, regenerating it via
snakemake if absent).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pandas as pd
from pyprojroot import here

# The anchor the fixtures are saved for. The notebook's own default; kept
# explicit so the test knows which (rcb_source, climate_assessment, quantile) to
# reproduce.
ANCHOR = {"source": "ar6_2020", "climate-assessment": "1.5C", "quantile": 0.5}

# Slice each parquet to these before saving -- enough to include CO2 debtors and
# creditors while keeping the committed fixtures tiny.
EXAMPLE_COUNTRIES = ["DEU", "FRA", "USA", "CHN", "IND", "BRA", "POL"]

NOTEBOOK = "notebooks/601_reproduce_esabcc_2023.py"
ALLOCATION_FOLDER = "601_esabcc_2023"
DISTRIBUTED = "distributed_remaining_pathways.parquet"
FIXTURE_DIR = "tests/fixtures/python_api"


def main() -> None:
    project_root = here()
    fixture_dir = project_root / FIXTURE_DIR
    fixture_dir.mkdir(parents=True, exist_ok=True)

    # Run the notebook for ANCHOR (the notebook default, so no injection needed).
    print(f"Executing {NOTEBOOK} ...")
    subprocess.run(
        ["uv", "run", "jupytext", "--to", "notebook", "--execute", NOTEBOOK],
        cwd=project_root,
        env=os.environ.copy(),
        check=True,
    )

    parquets = sorted(
        (project_root / "output").glob(
            f"*/allocations/{ALLOCATION_FOLDER}/{DISTRIBUTED}"
        )
    )
    if not parquets:
        raise SystemExit("notebook produced no distributed parquets")

    saved = []
    for parquet in parquets:
        df = pd.read_parquet(parquet)
        category = str(df["category"].iloc[0])
        sliced = df[df["iso3c"].isin(EXAMPLE_COUNTRIES)].reset_index(drop=True)
        out = fixture_dir / f"distributed_{category}.parquet"
        sliced.to_parquet(out, index=False)
        print(f"  {category}: {len(sliced)} rows -> {out.relative_to(project_root)}")
        saved.append(category)

    (fixture_dir / "metadata.json").write_text(
        json.dumps(
            {
                "anchor": ANCHOR,
                "example_countries": EXAMPLE_COUNTRIES,
                "categories": saved,
                "regenerate_with": "uv run python tests/fixtures/save_python_api_fixture.py",
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Wrote {len(saved)} fixtures to {fixture_dir}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
