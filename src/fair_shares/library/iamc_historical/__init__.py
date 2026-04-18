"""
Back-fill IAM scenarios with IAMC-consistent historical emissions.

Uses the packaged **IAMC historical composite** (CEDS + GFED + Velders + WMO
+ Adam 2024) to prepend regional history to a user-supplied scenario
:class:`pyam.IamDataFrame` at the model's native region resolution. Releases
register in ``conf/data_sources/iamc_data_sources.yaml`` under
``iamc_historical:``; the currently packaged release is the CMIP7 ScenarioMIP
2025.12.07 composite from ``iiasa/emissions_harmonization_historical``
(Nicholls, Kikstra, Zecchetto, Hoegner 2025, concept DOI
https://doi.org/10.5281/zenodo.15357372), shipped under
``data/emissions/cmip7-historical-2025.12.07/`` (CC-BY-4.0). Produces
``Emissions|CO2|Energy and Industrial Processes``, ``Emissions|CH4``,
``Emissions|N2O`` and aerosols (``BC``, ``OC``, ``CO``, ``NOx``, ``NH3``,
``Sulfur``, ``VOC``).

LULUCF is deliberately out of scope: the only supported ``Emissions|Covered``
category is ``all-ghg-ex-co2-lulucf``, built from the synthetic
``Emissions|Kyoto Gases (excl. CO2-LULUCF)`` (CO2|EIP + CH4 + N2O under GWP).

F-gases (HFCs, PFCs, SF6, NF3) and ozone-depleting substances are only
available at World level in the packaged data and are not back-filled
regionally in this version.

Public API
----------
backfill
    Prepend regional history to a scenario :class:`pyam.IamDataFrame`.
RegionMapping
    Load an IAM country-to-region mapping from a nomenclature-style YAML.
"""

from fair_shares.library.iamc_historical.backfill import backfill
from fair_shares.library.iamc_historical.covered import (
    COVERED_COMPONENTS,
    backfill_and_build_covered,
    build_covered,
    covered_components,
)
from fair_shares.library.iamc_historical.region_mapping import RegionMapping
from fair_shares.library.iamc_historical.socioeconomic import (
    backfill_population_gdp,
)

__all__ = [
    "COVERED_COMPONENTS",
    "RegionMapping",
    "backfill",
    "backfill_and_build_covered",
    "backfill_population_gdp",
    "build_covered",
    "covered_components",
]
