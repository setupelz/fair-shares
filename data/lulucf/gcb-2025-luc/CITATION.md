# Citation

## Global Carbon Budget 2025: National Land-Use Change Carbon Emissions (v1.0)

**Data product (the workbook in this directory):**

Global Carbon Project (2026). *Supplemental data of Global Carbon Budget 2025: National Land Use Change Carbon Emissions 2025 v1.0* [Data set]. ICOS Carbon Portal. https://doi.org/10.18160/GCP-2025 (PID 11676/milTbWkl0G-MSpdYG3IBIfzy)

**Paper (methods and results):**

Friedlingstein, P., et al. (2026). Global Carbon Budget 2025. *Earth System Science Data*, 18, 3211-3288. https://doi.org/10.5194/essd-18-3211-2026

**Bookkeeping models:** each sheet names the model paper to cite (BLUE: Hansis et al. 2015; OSCAR: Gasser et al. 2020; LUCE: Qin et al. 2024).

## Licence and terms of use

CC BY 4.0 (ICOS CCBY4 Data Licence, `!LICENCE.pdf` in this directory). Derived products and redistribution are allowed with attribution and an indication of changes. ICOS asks users to:

- cite the exact DOI or PID above;
- point their own users to the licence text and to ICOS for updates;
- inform the data providers when the data are used in a publication, and offer them the chance to comment, or acknowledgement or co-authorship where the data add substantial value.

The workbook's Summary sheet adds that co-authorship may need to be considered when the data are essential to the work. These are requests; the licence page states they add no contractual conditions.

## Download

Manual: the file sits behind the ICOS licence-acceptance page. Steps in `src/fair_shares/conf/data_registry.yaml` under `gcb-2025-luc`; `fair-shares fetch-data` prints them.

## Files

- `National_LandUseChange_Carbon_Emissions_2025_v1.0.xlsx`: net land-use change CO2 emissions by country, 1850-2024, from three bookkeeping models, one sheet each (`BLUE`, `OSCAR`, `LUCE`), plus `Summary`. Units: Tg C/yr (= Mt C/yr; × 44/12 for Mt CO2/yr). Columns are country names, plus `OTHER`, `DISPUTED`, `Global` and `EU27`. The Global Carbon Budget estimate is the mean of the three models. Sign convention: positive = net emission.
- `!LICENCE.pdf`, `!TOC.csv`: shipped in the ICOS zip.
