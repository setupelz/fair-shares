"""Load IAMC historical composite timeseries packaged with fair-shares.

Releases are registered in ``conf/data_sources/iamc_data_sources.yaml`` under
``iamc_historical:``. Files ship under ``data/emissions/<release-dir>/``.
The current release is the CMIP7 ScenarioMIP 2025.12.07 composite (CC-BY-4.0,
concept DOI https://doi.org/10.5281/zenodo.15357372). Future CMIP8 or other
IAMC releases slot in under the same section. No runtime download is
required. Users can pass ``history_path=`` to override with a local file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import pandas as pd
import pyprojroot

from fair_shares.library.exceptions import DataLoadingError
from fair_shares.library.iamc_historical.constants import LATEST_IAMC_HISTORICAL_RELEASE, IAMC_HISTORICAL_RELEASES

logger = logging.getLogger(__name__)

FileKind = Literal["country_feather", "global_csv"]


def _resolve_version(version: str) -> str:
    if version == "latest":
        return LATEST_IAMC_HISTORICAL_RELEASE
    if version not in IAMC_HISTORICAL_RELEASES:
        available = ", ".join(sorted(IAMC_HISTORICAL_RELEASES))
        raise DataLoadingError(
            f"Unknown history_version '{version}'. Known versions: {available}"
        )
    return version


def packaged_historical_path(
    version: str = "latest", kind: FileKind = "country_feather"
) -> Path:
    """Return the packaged historical file path for a given version and kind."""
    resolved = _resolve_version(version)
    record = IAMC_HISTORICAL_RELEASES[resolved]
    files = record["files"]
    if kind not in files:  # type: ignore[operator]
        raise DataLoadingError(
            f"Unknown file kind '{kind}' for version {resolved}. "
            f"Known kinds: {sorted(files)}"  # type: ignore[arg-type]
        )
    filename = str(files[kind])  # type: ignore[index]
    package_dir = str(record["package_dir"])
    path = pyprojroot.here() / package_dir / filename
    if not path.exists():
        raise DataLoadingError(
            f"Packaged IAMC historical release {resolved!r} not found at {path}. "
            "Expected it to ship with the fair-shares repository. "
            "If you are using a checkout without the data/ directory, pass "
            "history_path=<your local file> to the adapter."
        )
    return path


def load_historical(path: str | Path) -> pd.DataFrame:
    """Load a historical emissions file in feather, parquet, or CSV format.

    Returns a long-format DataFrame with columns
    ``["model", "scenario", "region", "variable", "unit", <year columns>]``.

    Notes
    -----
    Year columns arriving as digit-strings (typical for CSV / feather ingest)
    are normalised to ``int`` only when the parsed value falls within the
    1700–2200 range. This range filter is local to this loader — it is the
    signal used here to distinguish "this looks like a year column" from
    other digit-string column names. Downstream code uses
    :func:`fair_shares.library.utils.dataframes.get_year_columns`, which has
    **no** such range filter and will accept any integer-convertible column
    as a year. If future historical data extends below 1700 or above 2200,
    the range in this function must be widened, and any independent year
    detection in ``get_year_columns`` should be reviewed alongside.
    """
    path = Path(path)
    if not path.exists():
        raise DataLoadingError(f"Historical file not found: {path}")
    suffix = "".join(path.suffixes)
    if suffix.endswith(".feather"):
        df = pd.read_feather(path)
        if df.index.names != [None]:
            df = df.reset_index()
    elif suffix.endswith(".parquet") or suffix.endswith(".parquet.gzip"):
        df = pd.read_parquet(path)
        if df.index.names != [None]:
            df = df.reset_index()
    elif suffix.endswith(".csv"):
        df = pd.read_csv(path)
    else:
        raise DataLoadingError(
            f"Unsupported historical file extension on {path}. "
            "Supported: .feather, .parquet(.gzip), .csv"
        )
    expected = {"model", "scenario", "region", "variable", "unit"}
    missing = expected - set(df.columns)
    if missing:
        raise DataLoadingError(
            f"Historical file {path} is missing required columns: {sorted(missing)}"
        )
    # Normalise year columns to ``int`` regardless of source format.
    renames = {
        c: int(c)
        for c in df.columns
        if isinstance(c, str) and c.isdigit() and 1700 <= int(c) <= 2200
    }
    if renames:
        df = df.rename(columns=renames)
    return df


def fetch_historical(
    version: str = "latest",
    kind: FileKind = "country_feather",
    history_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch a historical DataFrame, preferring a user-supplied file if given.

    If ``history_path`` is supplied, load it directly. Otherwise resolve the
    packaged IAMC historical file shipped with the repository.
    """
    if history_path is not None:
        return load_historical(Path(history_path))
    return load_historical(packaged_historical_path(version=version, kind=kind))
