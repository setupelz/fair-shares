#!/usr/bin/env bash
# Clean-install acceptance check for the wheel.
#
# Builds a wheel, installs it into a throwaway venv with runtime dependencies
# only, and asserts from a directory outside the checkout that:
#
#   1. fair_shares.library.iamc_historical.constants imports (no repo needed)
#   2. an allocation runs against a user-supplied data directory
#   3. no authoring toolchain came along for the ride
#   4. asking to build without the pipeline extra fails with both remedies named
#   5. explicit data_dir=/output_dir= work with no FAIR_SHARES_* set at all
#   6. CITATION.cff ships inside the wheel, so citations work for an installed copy
#
# Usage: tests/acceptance/clean_install.sh [data_dir] [output_dir]
# Both default to the checkout's own data/ and output/.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="${1:-$REPO/data}"
OUTPUT_DIR="${2:-$REPO/output}"
VENV="$(mktemp -d)/venv"

cd "$REPO"

echo "== building wheel =="
uv build

WHEEL="$(ls -t "$REPO"/dist/fair_shares-*.whl | head -1)"
echo "wheel: $WHEEL"

echo "== installing into a clean venv (runtime deps only) =="
uv venv "$VENV" >/dev/null
uv pip install --python "$VENV/bin/python" "$WHEEL" >/dev/null
PY="$VENV/bin/python"

echo "== criterion 1: import from an arbitrary cwd =="
(cd / && "$PY" -c "import fair_shares.library.iamc_historical.constants; print('ok')")

echo "== criterion 3: no authoring toolchain in the resolved set =="
if uv pip list --python "$PY" --format=freeze 2>/dev/null \
     | grep -Ei 'jupyterlab|^notebook|snakemake|mkdocs|papermill|ruff|pytest'; then
  echo "FAIL: authoring toolchain present in a plain install"
  exit 1
fi
echo "ok"

echo "== criteria 2 and 4: allocation from the wheel, and the build-path error =="
cd /
FAIR_SHARES_DATA_DIR="$DATA_DIR" FAIR_SHARES_OUTPUT_DIR="$OUTPUT_DIR" "$PY" - <<'PYEOF'
from fair_shares.library.exceptions import MissingPipelineDependency
from fair_shares.library.python_api import calculate_allocation_timeseries
from fair_shares.library.utils import setup_data

SOURCES = dict(
    emissions_source="primap-202503",
    gdp_source="wdi-2025",
    population_source="un-owid-2025",
    gini_source="wdi-2025",
    lulucf_source="melo-2026",
)

result = calculate_allocation_timeseries(
    emission_category="co2-ffi",
    allocation={
        "equal-per-capita-budget": {
            "allocation_year": 2015,
            "preserve_allocation_year_shares": True,
        }
    },
    shape="half-sine",
    deviation_end_year=2050,
    convergence_year=2050,
    nonco2_debt_mode=None,
    pathway_end_year=2100,
    base_share_floor_mt=0.001,
    desired_harmonisation_year=2020,
    allocation_folder="601_esabcc_2023",
    rcb_source="ar6_2020",
    climate_assessment="1.5C",
    quantile=0.5,
    **SOURCES,
)
frame = result.allocation_timeseries
assert not frame.empty, "allocation returned no rows"
print(f"criterion 2 ok: {frame.shape[0]} rows computed from the wheel")

# Building without the pipeline extra must name both remedies, not just fail.
try:
    setup_data(
        emission_category="co2-ffi",
        active_sources={
            "emissions": "primap-202503",
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "wdi-2025",
            "lulucf": "melo-2026",
            "target": "pathway",
        },
        verbose=False,
    )
except MissingPipelineDependency as exc:
    message = str(exc)
    assert "fair-shares[pipeline]" in message, message
    assert "FAIR_SHARES_DATA_DIR" in message, message
    print("criterion 4 ok:", message)
else:
    raise SystemExit("FAIL: expected MissingPipelineDependency")
PYEOF

echo "== criterion 5: explicit directories, with no FAIR_SHARES_* set =="
cd /
FS_DATA="$DATA_DIR" FS_OUTPUT="$OUTPUT_DIR" "$PY" - <<'PYEOF'
import os
from pathlib import Path

# The highest-precedence level must work on its own. It is easy to regress:
# validation and source lookup resolve directories deep below the entry point,
# so an explicit argument that is not seeded into the resolver silently fails.
assert "FAIR_SHARES_DATA_DIR" not in os.environ
assert "FAIR_SHARES_OUTPUT_DIR" not in os.environ

from fair_shares.library.python_api import calculate_allocation_timeseries

result = calculate_allocation_timeseries(
    emission_category="co2-ffi",
    allocation={
        "equal-per-capita-budget": {
            "allocation_year": 2015,
            "preserve_allocation_year_shares": True,
        }
    },
    shape="half-sine",
    deviation_end_year=2050,
    convergence_year=2050,
    nonco2_debt_mode=None,
    pathway_end_year=2100,
    base_share_floor_mt=0.001,
    desired_harmonisation_year=2020,
    allocation_folder="601_esabcc_2023",
    rcb_source="ar6_2020",
    climate_assessment="1.5C",
    quantile=0.5,
    emissions_source="primap-202503",
    gdp_source="wdi-2025",
    population_source="un-owid-2025",
    gini_source="wdi-2025",
    lulucf_source="melo-2026",
    data_dir=Path(os.environ["FS_DATA"]),
    output_dir=Path(os.environ["FS_OUTPUT"]),
)
assert not result.allocation_timeseries.empty
print("criterion 5 ok: explicit directories resolved with no environment set")
PYEOF

echo
echo "== criterion 6: the wheel can tell users how to cite a run =="
"$PY" - <<'PYEOF'
from fair_shares.library.citations import citations, package_citation

# Reads CITATION.cff from inside the package. There is no checkout here to fall
# back to, so this fails if the build stops shipping the file.
cff = package_citation()
assert cff["title"] and cff["version"] and cff["license"], cff

run = citations(
    {
        "target": "rcbs",
        "emissions": "primap-202503",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "wdi-2025",
        "lulucf": "melo-2026",
    },
    emission_category="co2-ffi",
)
text = run.text()
for expected in ("primap-202503", "gcb-2024", "regions", cff["version"]):
    assert expected in text, expected
assert "@software{fairshares-software," in run.bibtex()
print("criterion 6 ok: CITATION.cff ships in the wheel and citations render")
PYEOF

echo
echo "ALL ACCEPTANCE CHECKS PASSED"
