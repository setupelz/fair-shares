"""The opt-in Global Carbon Budget 2025 emissions source (``gcb-2025``)."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from fair_shares.library import citations, paths
from fair_shares.library.config.models import (
    DataSourcesConfig,
    EmissionsDataParameters,
)
from fair_shares.library.data_registry import load_registry, normalise_target
from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.utils.data.config import (
    get_bunkers_source,
    get_emission_preprocessing_categories,
)
from fair_shares.library.utils.data.gcb import (
    AVIATION,
    GLOBAL,
    ISO,
    NAME,
    OIL_FIRES,
    SHIPPING,
    VALUE,
    YEAR,
    gcb_bunkers,
    gcb_fossil_co2,
)

KEY = "gcb-2025"
ALL_CATEGORIES = [
    "co2-ffi",
    "co2",
    "co2-lulucf",
    "non-co2",
    "all-ghg",
    "all-ghg-ex-co2-lulucf",
]


def _config() -> dict:
    raw = yaml.safe_load(
        paths.packaged_config("data_sources/data_sources_unified.yaml").read_text(
            encoding="utf-8"
        )
    )
    return raw["emissions"][KEY]


def _long(rows: dict[tuple[str, str | None], dict[int, float | None]]) -> pd.DataFrame:
    """Build a GCB-shaped long frame from {(name, iso): {year: value}}."""
    return pd.DataFrame(
        [
            {NAME: name, ISO: iso, YEAR: year, VALUE: value}
            for (name, iso), series in rows.items()
            for year, value in series.items()
        ]
    )


def test_registry_entry_is_opt_in_and_matches_config():
    source = load_registry()[KEY]
    assert source.tier == "optional"
    assert source.doi == "10.5281/zenodo.17417124"
    assert source.license == "CC-BY-4.0"
    (download,) = source.downloads
    assert normalise_target(_config()["path"]) == download.target


def test_a_co2_ffi_only_source_is_asked_for_no_other_category():
    available = _config()["data_parameters"]["available_categories"]
    assert available == ["co2-ffi"]
    for target in ("rcbs", "rcb-pathways"):
        requested = get_emission_preprocessing_categories(target, "co2-ffi", available)
        assert requested == ("co2-ffi",)
    # A source that declares every category is asked for the LULUCF primitives too.
    assert get_emission_preprocessing_categories("rcbs", "co2-ffi", ALL_CATEGORIES) == (
        "all-ghg-ex-co2-lulucf",
        "co2-ffi",
        "co2-lulucf",
    )
    # The config entry validates without a historical scenario.
    assert EmissionsDataParameters(**_config()["data_parameters"]).scenario is None


def test_co2_is_valid_for_a_co2_ffi_only_source_with_a_lulucf_source():
    """``co2`` = ``co2-ffi`` + inventory LULUCF, so it needs an active LULUCF source."""
    available = _config()["data_parameters"]["available_categories"]

    def config(category: str, lulucf: str | None) -> SimpleNamespace:
        parameters = SimpleNamespace(available_categories=available)
        return SimpleNamespace(
            active_emissions_source=KEY,
            emission_category=category,
            active_lulucf_source=lulucf,
            emissions={KEY: SimpleNamespace(data_parameters=parameters)},
        )

    validate = DataSourcesConfig.validate_emission_category
    validate(config("co2", "melo-2026-v4"))
    with pytest.raises(ConfigurationError, match="when a LULUCF source is active"):
        validate(config("co2", None))
    with pytest.raises(ConfigurationError, match="only provides: co2-ffi"):
        validate(config("all-ghg", "melo-2026-v4"))
    # The pipeline still asks the emissions source for co2-ffi alone.
    assert get_emission_preprocessing_categories("rcbs", "co2", available) == (
        "co2-ffi",
    )


def test_bunkers_follow_the_emissions_source():
    assert get_bunkers_source(KEY) == KEY
    assert get_bunkers_source("primap-202503") == "gcb-2024"
    run = {"target": "rcbs", "emissions": KEY, "gdp": "wdi-2025"}
    names = citations.resolve_source_names(run, emission_category="co2-ffi")
    assert KEY in names
    assert "gcb-2024" not in names


def test_blank_years_special_rows_and_world_row():
    """Synthetic file: two countries, one unmapped code, one row without a code."""
    raw = _long(
        {
            ("Aland", "AAA"): {2000: None, 2001: None, 2002: 5.0, 2003: 6.0},
            # 1999 precedes first_year and is dropped.
            ("Beland", "BBB"): {
                1999: 9.0,
                2000: 10.0,
                2001: None,
                2002: 12.0,
                2003: 13.0,
            },
            ("Unmapped", "UUU"): {2000: 1.0, 2001: 1.0, 2002: 1.0, 2003: 1.0},
            ("Some Islands", None): {2000: 0.5, 2001: 0.5, 2002: None, 2003: None},
            ("International Shipping", SHIPPING): {2000: 3, 2001: 3, 2002: 3, 2003: 3},
            ("International Aviation", AVIATION): {2000: 2, 2001: 2, 2002: 2, 2003: 2},
            (OIL_FIRES, None): {2000: None, 2001: 7.0, 2002: 0.0, 2003: 0.0},
            ("Global", GLOBAL): {2000: 16.5, 2001: 13.5, 2002: 23.0, 2003: 25.0},
        }
    )
    emissions, excluded = gcb_fossil_co2(raw, {"AAA", "BBB"}, "WLD", first_year=2000)

    values = emissions.droplevel(["unit", "emission-category"])
    assert list(values.index) == ["AAA", "BBB", "WLD"]
    assert list(values.columns) == ["2000", "2001", "2002", "2003"]
    assert emissions.index.get_level_values("unit").unique().tolist() == ["Mt * CO2e"]
    # Blanks count as zero, before the first record and inside a series.
    assert values.loc["AAA"].tolist() == [0.0, 0.0, 5.0, 6.0]
    assert values.loc["BBB"].tolist() == [10.0, 0.0, 12.0, 13.0]
    # World row = Global - shipping - aviation - oil fires.
    assert values.loc["WLD"].tolist() == [11.5, 1.5, 18.0, 20.0]
    # The unmapped code and the row without a code stay in the world row only.
    rest = values.loc["WLD"] - values.loc[["AAA", "BBB"]].sum()
    assert rest.tolist() == [1.5, 1.5, 1.0, 1.0]

    assert excluded.loc[OIL_FIRES].tolist() == [0.0, 7.0, 0.0, 0.0]
    assert gcb_bunkers(raw, first_year=2000).loc["bunkers"].tolist() == [5.0] * 4


def test_world_closure_on_the_real_file():
    """Countries + other rows + bunkers + oil fires = GCB Global, 1850-2024."""
    config = _config()
    # Another test seeds the cached data directory with a temp path.
    paths.reset_path_cache()
    path = paths.resolve_source_path(config["path"])
    if not path.exists():
        pytest.skip("GCB 2025 file not fetched")
    raw = pd.read_csv(path)
    world_key = config["data_parameters"]["world_key"]
    every_code = set(raw[ISO].dropna()) - {GLOBAL, SHIPPING, AVIATION}

    emissions, excluded = gcb_fossil_co2(raw, every_code, world_key)
    values = emissions.droplevel(["unit", "emission-category"])
    world = values.loc[world_key]
    assert list(values.columns) == [str(y) for y in range(1850, 2025)]
    assert not values.isna().any().any()

    raw = raw[raw[YEAR] >= 1850]
    global_total = raw[raw[ISO] == GLOBAL].set_index(YEAR)[VALUE]
    global_total.index = global_total.index.astype(str)
    no_code = raw[raw[ISO].isna() & (raw[NAME] != OIL_FIRES)]
    no_code = no_code.groupby(YEAR)[VALUE].sum().reindex(range(1850, 2025)).fillna(0)
    no_code.index = no_code.index.astype(str)

    # The file rounds to six decimals, so sums over 220 rows agree to about 1e-5.
    countries = values.drop(index=world_key).sum()
    assert (countries + no_code - world).abs().max() < 1e-4
    assert (world + excluded.sum() - global_total).abs().max() < 1e-9
    bunkers = gcb_bunkers(raw).loc["bunkers"]
    assert (bunkers - excluded.loc[[SHIPPING, AVIATION]].sum()).abs().max() == 0
    assert excluded.loc[OIL_FIRES, "1991"] == pytest.approx(477.924832)
