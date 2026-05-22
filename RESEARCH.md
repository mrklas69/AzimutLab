# RESEARCH — AzimutLab

Survey existujících nástrojů, metod a přístupů. Porovnávací/analytická vrstva
(„co už umí kdo a jak"). Referenční katalog konkrétních věcí (zdroje dat, spec,
nástroje k použití) žije v `docs/kb/` — sem patří *zhodnocení*, tam *evidence*.

> Skeleton (Sezení 1). Plní se průběžně, jak průzkum postupuje.

## Existující nástroje (vektorizace / kartografie)

| Nástroj | Co řeší | Relevance pro AzimutLab |
|---------|---------|--------------------------|
| CoVe | color line vectorization (v OOM) | UC4-III: liniová vektorizace už vyřešená |
| OCAD / OpenOrienteering Mapper | tvorba orienťáckých map | cílový formát (OCD/OMAP), spec referenční |
| Karttapullautin | LIDAR → orienťácká mapa (vrstevnice/vegetace) | UC2+UC4-II: LIDAR pipeline, inspirace |
| Pic2Omap (sourozenec) | raster → OMAP, ML pilot (U-Net plochy) | UC4-III + UC5: přímý předchůdce |

## Metody (k doplnění)

- Segmentace ploch (U-Net) — viz Pic2Omap ML pilot (mean IoU 0.666 within-domain).
- Color separation (palette-based, LAB nearest) — Pic2Omap `color_separator.py`.
- *(generování map, restaurace/inpainting — TBD)*

## Otevřené otázky průzkumu

- Jaké generativní přístupy dávají „realisticky vyhlížející" orienťácké mapy (UC4-I)?
- Jaký je state-of-the-art v de-creasing / dewarping fotografií dokumentů (UC3)?
