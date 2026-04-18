# Citation

## CMIP7 ScenarioMIP historical emissions timeseries

Nicholls, Z., Kikstra, J., Zecchetto, M., & Hoegner, A. (2025). *CMIP7 ScenarioMIP historical timeseries for harmonisation and simple climate model workflow* (Version 2025.12.07) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.15357372

- **Concept DOI (latest version):** https://doi.org/10.5281/zenodo.15357372
- **This version (2025.12.07) DOI:** https://doi.org/10.5281/zenodo.17845154
- **Source pipeline:** https://github.com/iiasa/emissions_harmonization_historical

Source datasets combined into this release:

- **CEDS v_2025_03_18** — Hoesly, R. M., Smith, S. J., Feng, L., Klimont, Z., Janssens-Maenhout, G., Pitkanen, T., Seibert, J. J., Vu, L., Andres, R. J., Bolt, R. M., Bond, T. C., Dawidowski, L., Kholod, N., Kurokawa, J.-I., Li, M., Liu, L., Lu, Z., Moura, M. C. P., O'Rourke, P. R., Zhang, Q. (2018). Historical (1750-2014) anthropogenic emissions of reactive gases and aerosols from the Community Emissions Data System (CEDS). *Geoscientific Model Development*, 11, 369-408. https://doi.org/10.5194/gmd-11-369-2018
- **GFED4 / BB4CMIP7** — van der Werf, G. R., Randerson, J. T., Giglio, L., van Leeuwen, T. T., Chen, Y., Rogers, B. M., Mu, M., van Marle, M. J. E., Morton, D. C., Collatz, G. J., Yokelson, R. J., & Kasibhatla, P. S. (2017). Global fire emissions estimates during 1997-2016. *Earth System Science Data*, 9, 697-720. https://doi.org/10.5194/essd-9-697-2017
- **Global Carbon Budget 2024** (for `Emissions|CO2|AFOLU` at World level) — Friedlingstein et al. 2025, see `data/emissions/gcb-2024v1.0/CITATION.md`
- **Velders et al. 2022** (HFC inversions) — Velders, G. J. M., Daniel, J. S., Montzka, S. A., Vimont, I., Rigby, M., Krummel, P. B., Muhle, J., O'Doherty, S., Prinn, R. G., Weiss, R. F., & Young, D. (2022). Projections of hydrofluorocarbon (HFC) emissions and the resulting global warming based on recent trends in observed abundances and current policies. *Atmospheric Chemistry and Physics*, 22, 6087-6101. https://doi.org/10.5194/acp-22-6087-2022
- **WMO 2022** (ODS + Halon inversions) — World Meteorological Organization (2022). *Scientific Assessment of Ozone Depletion: 2022*. GAW Report No. 278.
- **Adam et al. 2024** (HFC-23 inversions) — Adam, B., et al. (2024). Publications/metadata per the Zenodo record.

## Licence

Distributed under **CC-BY-SA-4.0**. The ShareAlike clause extends protections
from the F-gas and Montreal Protocol inversion inputs that fed the composite.
Upstream component licences remain as issued (BB4CMIP7 and CEDS are CC-BY-4.0);
component-level linkage is tracked upstream
(https://github.com/iiasa/emissions_harmonization_historical/issues/150).

Cite the concept DOI above and the upstream source datasets when reporting
derived values.

## Files

- `country-history.feather` — country-level CEDS+GFED historical emissions, 1750-2023, wide format, index = (model, scenario, region, variable, unit). Region holds lowercase ISO3 codes plus a ``global`` pseudo-code for aviation-style aggregates. Loaded by `fair_shares.library.iamc_historical.sources.load_historical`.
- `global-workflow-history.csv` — global totals covering every IAMC variable including F-gases and `Emissions|CO2|AFOLU` (GCB-extended). Used for World-level lookups and for verifying regional aggregation mass conservation.
