# KB — Tools & models

Katalog konkrétních nástrojů, knihoven a modelů použitelných v AzimutLab. (Zhodnocení
„co je lepší" patří do RESEARCH.md; sem co existuje a kde to je.)

> Skeleton (Sezení 1).

## Nástroje

| Nástroj | Účel | Odkaz / umístění |
|---------|------|------------------|
| OpenOrienteering Mapper | tvorba/editace OMAP; import GDAL vektorů (GeoJSON→symboly) | github.com/OpenOrienteering/mapper |
| CoVe | color line vectorization (orienťácké čáry) | github.com/lpechacek/cove (v OOM) |
| Karttapullautin | LIDAR → mapa | github.com/karttapullautin/karttapullautin (viz RESEARCH.md) |
| lasertool | LIDAR point cloud (LAS/ASC) → rastr: terén + „vegetation height image" | lokálně `lasertool/` (Win32 Qt4, ~2011; liblas+Triangle); rodina tmsw.no basemap |
| AutoTrace | bitmap → vektor (raster tracing): SVG/DXF/EMF… | autotrace.sourceforge.net (GPL) |
| OCAD | komerční tvorba map | — |
| QGIS | GIS desktop / WMS-WFS klient; import/CRS vektoru | — |

**Vektorizace rastru (UC4-III / UC3) vs vektor zdarma (UC4-I).** Pro *reálné skeny* map
(bez zdrojových vektorů) je raster→vektor nutný: **AutoTrace** + nástroje z jeho Links
(**WinTopo** raster→vektor GIS, **Ras2Vec**, **CR2V** color segmentation). Pro orienťácké
*čáry* je ale `CoVe` napřed (specializovaný). Pozn.: **náš generátor (UC4-I) vektorizaci
nepotřebuje** — vrstevnice má rovnou jako polylinie z contourpy (export `contours.geojson`,
viz `generator-procedural.md §9`). AutoTrace je pro opačný směr (pixely → vektor).

**lasertool** jde naopak *point cloud → rastr* (rodina Karttapullautin), **ne** vektorizace.
Vegetation height (CHM) ale potřebuje **multi-echo klasifikované mračno** — naráží na stejnou
vegetace gate jako Karttapullautin (viz `data-sources.md`). **Sez. 59 ověřeno prakticky:**
(a) `lasertool` (Win32 Qt4 2011) **segfaultuje na Win11** (exit 139); (b) i kdyby běžel, open
ČÚZK DMP 1G je **100 % single-return** (změřeno laspy) → dá jen výšku korun (CHM), ne hustotu
podrostu = runnability. CHM lze spočítat i přímo z laspy (bez lasertool). → vegetace gate DOLOŽENA.

## Modely / metody (z Pic2Omap)

| Co | Stav | Umístění |
|----|------|----------|
| Palette separation (LAB nearest) | produkční | `Pic2Omap/color_separator.py` |
| Area segmentation (U-Net resnet34) | pilot (mIoU 0.666 within-domain) | `Pic2Omap/train.py` |
| ISOM symbol DB (parser) | produkční | `Pic2Omap/omap_parser.py` |
| Procedurální generátor (skalární pole → vrstvy + GT masky + vektor + .omap) | pilíř (od Sez. 4; `generator/` od Sez. 39) | `generator/` |

## Stack

- **PoC generátor** (Sez. 4): Python 3.14 + numpy + contourpy (marching squares) +
  Pillow + pyproj (jen `--terrain real`, WGS84→S-JTSK). Venv v kořeni repa (`.venv`).
  `scikit-image` vynechán (KISS + jistota wheelů na 3.14).
- **Zděděno z Pic2Omap** (až bude konzument): numpy, opencv. ML: torch / smp /
  albumentations (odděleně, GPU box).
