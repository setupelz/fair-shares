"""Parse IAM country-to-region mappings and aggregate country data to regions."""

from __future__ import annotations

import ast
import difflib
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import country_converter as coco
import pandas as pd
import yaml

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError
from fair_shares.library.utils.dataframes import get_year_columns

# Live-load default for :meth:`RegionMapping.from_common_definitions`. Mirrors
# the pattern in ``iiasa/emissions_harmonization_historical/src/region_mapping.py``:
# fetch the composed ``region_df.csv`` from the upstream repo's ``main`` branch,
# cache locally, fall back to a known-good commit if network is unavailable.
_REGION_DF_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/iiasa/"
    "emissions_harmonization_historical/{ref}/data/regionmapping/region_df.csv"
)
_REGION_DF_FALLBACK_REF = "main"

logger = logging.getLogger(__name__)


@dataclass
class RegionMapping:
    """A country-to-region mapping for a single IAM model.

    ``regions`` maps region name (e.g. ``"WITCH 7.0|Brazil"``) to a list of
    lowercase ISO3 codes. The input YAML typically uses country names; we
    convert those to ISO3 on load via ``country_converter``.
    """

    model: str
    regions: dict[str, list[str]]

    def add_countries(self, region: str, iso3_codes: list[str]) -> None:
        """Append ISO3 codes to an existing region (in place).

        Useful for filling known small-territory gaps in ``common-definitions``
        without waiting for an upstream PR. Example::

            rm = RegionMapping.from_common_definitions("MESSAGEix-GLOBIOM 1.1-R12")
            rm.add_countries("MESSAGEix-GLOBIOM 1.1-R12|Eastern Europe", ["kos"])
        """
        if region not in self.regions:
            known = sorted(self.regions)
            raise ConfigurationError(
                f"Region {region!r} not in mapping. Known: {known}"
            )
        existing = set(self.regions[region])
        for code in iso3_codes:
            lower = code.lower()
            if lower not in existing:
                self.regions[region].append(lower)
                existing.add(lower)

    # ------------------------------------------------------------------
    # loaders

    @classmethod
    def from_nomenclature_yaml(cls, path: str | Path) -> RegionMapping:
        """Load a ``nomenclature``-style regions YAML.

        The expected schema (what ``emissions_harmonization_historical`` and
        ``IAMconsortium/common-definitions`` use) looks like::

            - WITCH 7.0:
              - WITCH 7.0|Brazil:
                  countries:
                    - Brazil
              - WITCH 7.0|Canada:
                  countries:
                    - Canada
                    - Saint Pierre and Miquelon
        """
        path = Path(path)
        if not path.exists():
            raise ConfigurationError(f"Region mapping YAML not found: {path}")
        with path.open() as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, list) or not raw:
            raise ConfigurationError(
                f"Region mapping YAML at {path} must be a non-empty list"
            )
        # Top-level is a list with a single dict {model_name: [region_blocks]}
        top = raw[0]
        if not isinstance(top, dict) or len(top) != 1:
            raise ConfigurationError(
                f"Region mapping YAML at {path} must have a single top-level model key"
            )
        model_name = next(iter(top))
        region_blocks = top[model_name]
        regions = _parse_region_blocks(region_blocks, source=str(path))
        iso3_regions = {
            region: _names_to_iso3(countries, region=region, source=str(path))
            for region, countries in regions.items()
        }
        return cls(model=model_name, regions=iso3_regions)

    @classmethod
    def from_countries_dict(
        cls, model: str, regions: dict[str, list[str]]
    ) -> RegionMapping:
        """Construct from a plain dict of region -> country-name list."""
        iso3 = {
            region: _names_to_iso3(countries, region=region, source="<dict>")
            for region, countries in regions.items()
        }
        return cls(model=model, regions=iso3)

    @staticmethod
    def write_excel_template(
        path: str | Path, *, model: str, regions: list[str] | None = None
    ) -> Path:
        """Write a blank fill-in workbook for a model not in common-definitions.

        One sheet, three columns — ``model``, ``region``, ``country`` — one
        country per row. ``region`` is the bare label (the ``"<model>|"``
        prefix is added on load); ``country`` is a name or ISO3 code. Pass
        ``regions`` to pre-list the model's region labels. Hand the file over,
        get it filled in, then load with :meth:`from_excel_template`.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if regions:
            rows = [{"model": model, "region": r, "country": ""} for r in regions]
        else:
            rows = [
                {"model": model, "region": "Latin America", "country": "Brazil"},
                {"model": model, "region": "Latin America", "country": "Argentina"},
                {"model": model, "region": "Western Europe", "country": "France"},
            ]
        pd.DataFrame(rows, columns=["model", "region", "country"]).to_excel(
            path, sheet_name="mapping", index=False
        )
        return path

    @classmethod
    def from_excel_template(
        cls, path: str | Path, *, model: str | None = None
    ) -> RegionMapping:
        """Load a mapping from a filled-in :meth:`write_excel_template` workbook.

        Reads the ``mapping`` sheet (columns ``model``, ``region``, ``country``;
        one country per row). ``country`` may be a name or ISO3 code. The model
        comes from the ``model`` column unless ``model=`` is passed.
        """
        path = Path(path)
        if not path.exists():
            raise ConfigurationError(f"Region template workbook not found: {path}")
        try:
            df = pd.read_excel(path, sheet_name="mapping", dtype=str)
        except ValueError as exc:
            raise ConfigurationError(
                f"No 'mapping' sheet in {path}. Generate one with "
                f"RegionMapping.write_excel_template()."
            ) from exc
        df.columns = [str(c).strip().lower() for c in df.columns]
        missing = {"region", "country"} - set(df.columns)
        if missing:
            raise ConfigurationError(
                f"Template {path} missing columns: {sorted(missing)}. "
                f"Expected: model, region, country."
            )
        df = df.fillna("").apply(lambda s: s.str.strip())
        df = df[df["region"].ne("") & df["country"].ne("")]
        if df.empty:
            raise ConfigurationError(
                f"No filled-in region/country rows in {path}. "
                f"Add at least one row before loading."
            )
        if model is None:
            models = sorted(set(df["model"]) - {""}) if "model" in df else []
            if len(models) != 1:
                raise ConfigurationError(
                    f"Template {path} must name exactly one model in the 'model' "
                    f"column; found {models}. Pass model= to disambiguate."
                )
            model = models[0]
        regions: dict[str, list[str]] = {}
        for region, country in zip(df["region"], df["country"], strict=True):
            key = region if "|" in region else f"{model}|{region}"
            regions.setdefault(key, []).append(country)
        iso3_regions = {
            region: _names_to_iso3(countries, region=region, source=str(path))
            for region, countries in regions.items()
        }
        return cls(model=model, regions=iso3_regions)

    @classmethod
    def from_common_definitions(
        cls,
        model: str,
        *,
        ref: str = _REGION_DF_FALLBACK_REF,
        cache_dir: Path | None = None,
        refresh: bool = False,
    ) -> RegionMapping:
        """Live-load an IAM mapping from the IAMC community ``region_df.csv``.

        Fetches the composed country-to-region CSV from
        ``iiasa/emissions_harmonization_historical`` (built from
        ``IAMconsortium/common-definitions``, CC0-1.0) at ``ref``, caches it
        under ``~/.cache/fair-shares/common-definitions/<ref>/region_df.csv``,
        and filters to rows belonging to ``model`` (matched on the part before
        ``"|"`` in the ``name`` column).

        Parameters
        ----------
        model
            The IAM model identifier as it appears in ``region_df.csv``, e.g.
            ``"MESSAGEix-GLOBIOM 1.1-R12"`` or ``"WITCH 6.0"``.
        ref
            Git ref (branch, tag, or commit SHA) to fetch. Defaults to ``main``.
            Pin to a commit SHA for reproducibility.
        cache_dir
            Override the cache directory. Defaults to
            ``~/.cache/fair-shares/common-definitions``.
        refresh
            If True, force-download even if the file is cached.
        """
        cache_root = (
            Path(cache_dir).expanduser()
            if cache_dir
            else Path(
                os.environ.get(
                    "FAIRSHARES_COMMON_DEFINITIONS_CACHE",
                    "~/.cache/fair-shares/common-definitions",
                )
            ).expanduser()
        )
        cache_path = cache_root / ref / "region_df.csv"
        if refresh or not cache_path.exists():
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            url = _REGION_DF_URL_TEMPLATE.format(ref=ref)
            logger.info("Downloading common-definitions region_df: %s", url)
            tmp = cache_path.with_suffix(cache_path.suffix + ".part")
            if tmp.exists():
                tmp.unlink()
            try:
                with urllib.request.urlopen(url, timeout=30) as response, tmp.open(
                    "wb"
                ) as out:
                    while chunk := response.read(1 << 16):
                        out.write(chunk)
            except (TimeoutError, urllib.error.URLError) as exc:
                raise ConfigurationError(
                    f"could not fetch region_df.csv from {url}: {exc}. "
                    f"Pass ref=<git sha> to use a cached version, or set "
                    f"FAIRSHARES_COMMON_DEFINITIONS_CACHE to a pre-populated directory."
                ) from exc
            tmp.rename(cache_path)

        df = pd.read_csv(cache_path)
        required = {"name", "iso3"}
        missing = required - set(df.columns)
        if missing:
            raise ConfigurationError(
                f"region_df.csv at {cache_path} missing columns: {sorted(missing)}"
            )

        # Rows belonging to this model: ``name`` startswith ``"<model>|"``
        prefix = f"{model}|"
        mask = df["name"].astype(str).str.startswith(prefix)
        if not mask.any():
            known = sorted(
                {n.split("|", 1)[0] for n in df["name"].astype(str) if "|" in n}
            )
            # Show the full list (it is short) — truncating hides whether the
            # model is present at all. Offer close matches for typo/version slips.
            suggestions = difflib.get_close_matches(model, known, n=3, cutoff=0.5)
            hint = (
                f"Closest matches: {suggestions}. "
                if suggestions
                else "No close matches — this model has no mapping in "
                "common-definitions. Either point ref= at a branch that defines "
                "it, or provide the regions yourself: generate a fill-in sheet "
                "with RegionMapping.write_excel_template('regions.xlsx', "
                f"model={model!r}) and load the filled copy with "
                "RegionMapping.from_excel_template('regions.xlsx'). "
            )
            raise ConfigurationError(
                f"No regions for model {model!r} in region_df.csv "
                f"(ref={ref!r}, cache={cache_path}). "
                f"{hint}"
                f"Known models ({len(known)}): {known}"
            )
        subset = df[mask]

        regions: dict[str, list[str]] = (
            subset.set_index("name")["iso3"]
            .apply(
                lambda s: []
                if pd.isna(s) or s in ("", "[]")
                else [str(c).lower() for c in ast.literal_eval(str(s))]
            )
            .to_dict()
        )
        return cls(model=model, regions=regions)

    # ------------------------------------------------------------------
    # queries

    @property
    def region_names(self) -> list[str]:
        """Sorted region names (the mapping's keys)."""
        return sorted(self.regions)

    @property
    def countries(self) -> set[str]:
        """All ISO3 codes across every region."""
        return {c for cs in self.regions.values() for c in cs}

    def region_for(self, iso3: str) -> str | None:
        """Return the region containing ``iso3``, or None if unmapped."""
        iso3 = iso3.lower()
        for region, members in self.regions.items():
            if iso3 in members:
                return region
        return None

    def aggregate(
        self,
        country_df: pd.DataFrame,
        country_col: str = "region",
        aggfunc: str = "sum",
    ) -> pd.DataFrame:
        """Aggregate a country-level long DataFrame to model regions.

        Parameters
        ----------
        country_df
            Long DataFrame with ISO3 country codes in ``country_col`` and year
            columns holding numeric values. Non-year columns other than
            ``country_col`` are treated as group keys and preserved.
        country_col
            Column holding lowercase ISO3 country codes.
        aggfunc
            Aggregation function passed to :meth:`pandas.DataFrame.groupby.agg`.
            Defaults to ``"sum"`` (the only sensible choice for emissions).

        Returns
        -------
        pd.DataFrame
            Long DataFrame with ``country_col`` replaced by a region column of
            the same name, aggregated across the members of each region.
        """
        if country_col not in country_df.columns:
            raise DataProcessingError(
                f"Expected country column '{country_col}' not in DataFrame"
            )
        # Build reverse index: ISO3 -> region
        reverse = {
            iso3: region for region, members in self.regions.items() for iso3 in members
        }
        tagged = country_df.copy()
        tagged[country_col] = tagged[country_col].str.lower().map(reverse)
        missing_mask = tagged[country_col].isna()
        if missing_mask.any():
            unmapped = sorted(
                country_df.loc[missing_mask, country_col].str.lower().unique()
            )
            logger.warning(
                "Dropping %d rows for ISO3 codes not in mapping for model %s: %s",
                missing_mask.sum(),
                self.model,
                unmapped[:10] + (["..."] if len(unmapped) > 10 else []),
            )
            tagged = tagged.loc[~missing_mask]
        year_cols = get_year_columns(tagged, return_type="original")
        non_year_cols = [c for c in tagged.columns if c not in year_cols]
        grouped = tagged.groupby(non_year_cols, dropna=False, as_index=False)[
            year_cols
        ].agg(aggfunc)
        return grouped


# ----------------------------------------------------------------------
# helpers


def _parse_region_blocks(
    blocks: list[Any], *, source: str
) -> dict[str, list[str]]:
    """Extract the region -> country-name list mapping from nomenclature YAML."""
    out: dict[str, list[str]] = {}
    if not isinstance(blocks, list):
        raise ConfigurationError(
            f"Expected a list of region blocks in {source}, got {type(blocks).__name__}"
        )
    for block in blocks:
        if not isinstance(block, dict) or len(block) != 1:
            raise ConfigurationError(
                f"Each region block in {source} must be a single-key dict; got {block!r}"
            )
        region = next(iter(block))
        body = block[region]
        if not isinstance(body, dict) or "countries" not in body:
            raise ConfigurationError(
                f"Region block '{region}' in {source} must contain 'countries'"
            )
        countries = body["countries"]
        if not isinstance(countries, list):
            raise ConfigurationError(
                f"Region block '{region}' in {source} must have 'countries' as a list"
            )
        if not countries:
            logger.debug(
                "Region '%s' in %s has empty countries list; keeping as aggregate",
                region,
                source,
            )
        out[region] = list(countries)
    return out


_coco_converter: coco.CountryConverter | None = None


def _get_coco() -> coco.CountryConverter:
    global _coco_converter
    if _coco_converter is None:
        _coco_converter = coco.CountryConverter()
    return _coco_converter


def _names_to_iso3(
    names: list[str], *, region: str, source: str
) -> list[str]:
    """Convert a list of country names to lowercase ISO3 codes."""
    cc = _get_coco()
    iso3 = cc.pandas_convert(pd.Series(names), to="ISO3")
    bad = [n for n, c in zip(names, iso3, strict=True) if not isinstance(c, str) or c in {"not found", ""}]
    if bad:
        raise ConfigurationError(
            f"Could not resolve ISO3 for countries in region '{region}' "
            f"(source={source}): {bad}"
        )
    return [c.lower() for c in iso3]


