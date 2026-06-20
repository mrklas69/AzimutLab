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

## Modely / metody (UC5 reconstructory — živé, `model/`)

| Co | Stav | Umístění |
|----|------|----------|
| `Png2Area` (U-Net resnet34, sken → plošný ISOM label rastr, `N_AREA=21` po 404/407/409) | živý (Sez. 88-152; poslední plný test před scope expanzí mIoU 0,683) | `model/png2area/` |
| `Png2Point` (U-Net + CenterNet heatmapy, bodové symboly 204/210/417/419) | živý (Sez. 105-128; medián mF1 0,827) | `model/png2point/` |
| `Png2Line` (U-Net segmentace linií + vektorizace; 304/305 + 306 + 309 + 508* label scope) | živý, scope rozšířený Sez. 152; starý checkpoint/vectorizer watercourse-only do retrainu | `model/png2line/` |
| `ORTO → runnability` baseline | ARCHIV (slepá ulička Sez. 79, val mIoU strop ~0,25) | `model/runnability/` |

## Stack

SSoT závislostí = `requirements.txt` (runtime) + `requirements-train.txt` (trénink, plánováno B4).

- **Runtime generátor + konektory:** Python (3.12 na ntbhej / 3.14 cp314 na mrkla) + numpy +
  contourpy (marching squares) + Pillow + pyproj (WGS84→S-JTSK) + **scipy** (morfologie
  `rock_relief`) + **scikit-image** (skeletonize, Png2Line .omap assembly Sez. 132) +
  **pygeomag** (grivace WMM offline, Sez. 112). Venv v kořeni repa (`.venv`).
  (Pozn.: dřívější „scikit-image vynechán" už neplatí — přidán Sez. 132.)
- **Trénink (jen `mrkla`, GPU):** torch (cu128 Blackwell, mimo PyPI) + **segmentation-models-pytorch**
  + **matplotlib** (křivky). Detail strojů: `hardware.md`.
