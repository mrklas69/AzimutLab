# KB — Tools & models

Katalog konkrétních nástrojů, knihoven a modelů použitelných v AzimutLab. (Zhodnocení
„co je lepší" patří do RESEARCH.md; sem co existuje a kde to je.)

> Skeleton (Sezení 1).

## Nástroje

| Nástroj | Účel | Odkaz / umístění |
|---------|------|------------------|
| OpenOrienteering Mapper | tvorba/editace OMAP | github.com/OpenOrienteering/mapper |
| CoVe | color line vectorization | github.com/lpechacek/cove (v OOM) |
| Karttapullautin | LIDAR → mapa | — |
| OCAD | komerční tvorba map | — |
| QGIS | GIS desktop / WMS-WFS klient | — |

## Modely / metody (z Pic2Omap)

| Co | Stav | Umístění |
|----|------|----------|
| Palette separation (LAB nearest) | produkční | `Pic2Omap/color_separator.py` |
| Area segmentation (U-Net resnet34) | pilot (mIoU 0.666 within-domain) | `Pic2Omap/train.py` |
| ISOM symbol DB (parser) | produkční | `Pic2Omap/omap_parser.py` |

## Stack (až vznikne kód)

Python 3.10+, numpy, opencv, scikit-image (zděděno z Pic2Omap). ML: torch / smp /
albumentations (odděleně, GPU box). Zatím nic nezakládáno — deštníková fáze.
