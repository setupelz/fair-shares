"""Constants and variable aggregation rules for IAMC historical back-fill.

The :data:`IAMC_HISTORICAL_RELEASES` registry is loaded lazily from
``conf/data_sources/iamc_data_sources.yaml`` on first access, not at import
time. This keeps the module importable in environments without the YAML
(e.g. non-repo installs) until the registry is actually needed. To drop in
a new release, add an entry under ``iamc_historical`` in the YAML and set
``active_iamc_historical`` to its tag. No Python changes required. The
section is pipeline-agnostic, so CMIP7, CMIP8, or any future IAMC release
plugs in under the same key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyprojroot
import yaml

from fair_shares.library.exceptions import DataLoadingError

_CONFIG_PATH = (
    pyprojroot.here() / "conf" / "data_sources" / "iamc_data_sources.yaml"
)

_LAZY_NAMES = {
    "IAMC_HISTORICAL_RELEASES",
    "LATEST_IAMC_HISTORICAL_RELEASE",
}


def _load_unified_config() -> dict[str, Any]:
    try:
        with _CONFIG_PATH.open() as f:
            return yaml.safe_load(f) or {}
    except (FileNotFoundError, OSError) as e:
        raise DataLoadingError(
            f"Could not open IAMC data-source config at {_CONFIG_PATH}: {e}"
        ) from e
    except yaml.YAMLError as e:
        raise DataLoadingError(
            f"IAMC data-source config at {_CONFIG_PATH} is not valid YAML: {e}"
        ) from e


def _ensure_loaded() -> None:
    """Populate the lazy module-level release registries from disk."""
    cfg = _load_unified_config()
    globals()["IAMC_HISTORICAL_RELEASES"] = cfg.get("iamc_historical", {})
    globals()["LATEST_IAMC_HISTORICAL_RELEASE"] = cfg.get(
        "active_iamc_historical", ""
    )


def __getattr__(name: str):
    if name in _LAZY_NAMES:
        _ensure_loaded()
        return globals()[name]
    raise AttributeError(name)


def reload_releases() -> None:
    """Reload the release registries from disk.

    Useful after editing ``iamc_data_sources.yaml`` within a running session,
    or to force a refresh after the lazy initial load.
    """
    _ensure_loaded()


# ----------------------------------------------------------------------
# Aggregation rules. These are model-independent and stay in Python.

# Concordia's canonical LUC sector list. Used to split CO2 into
# `Energy and Industrial Processes` versus `AFOLU` at top level.
# Source: IAMconsortium/concordia notebooks/example_config.yaml
LUC_SECTORS: frozenset[str] = frozenset(
    {
        "Agricultural Waste Burning",
        "Grassland Burning",
        "Forest Burning",
        "Peat Burning",
        "Agriculture",
        "Aggregate - Agriculture and LUC",
        "CDR Afforestation",
    }
)

# Top-level IAMC variables that are sums of sectoral CEDS+GFED subvariables.
# Each entry maps a top-level name to a predicate over its sectoral children.
# Sector filtering: "all" = all children summed, "ex_luc" = children whose
# sector name is NOT in LUC_SECTORS, "ex_aircraft" = children whose sector
# is not "Aircraft" (aircraft is global-only and not attributable to a country).
SECTOR_AGGREGATION_RULES: dict[str, dict[str, object]] = {
    "Emissions|CO2|Energy and Industrial Processes": {
        "gas": "CO2",
        "sector_filter": "ex_luc_and_aircraft",
    },
    "Emissions|CH4": {"gas": "CH4", "sector_filter": "ex_aircraft"},
    "Emissions|N2O": {"gas": "N2O", "sector_filter": "ex_aircraft"},
    "Emissions|BC": {"gas": "BC", "sector_filter": "ex_aircraft"},
    "Emissions|OC": {"gas": "OC", "sector_filter": "ex_aircraft"},
    "Emissions|CO": {"gas": "CO", "sector_filter": "ex_aircraft"},
    "Emissions|NOx": {"gas": "NOx", "sector_filter": "ex_aircraft"},
    "Emissions|NH3": {"gas": "NH3", "sector_filter": "ex_aircraft"},
    "Emissions|Sulfur": {"gas": "Sulfur", "sector_filter": "ex_aircraft"},
    "Emissions|VOC": {"gas": "VOC", "sector_filter": "ex_aircraft"},
}

# Variables only available at World level in the packaged data (F-gases, ODS,
# aviation aggregates). Requesting these at regional resolution emits a warning
# and no back-fill.
GLOBAL_ONLY_VARIABLES: frozenset[str] = frozenset()
