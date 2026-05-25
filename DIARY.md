# DIARY — AzimutLab

Index sezení. Detail v `docs/diary/YYYY-MM-DD.md`. Více sezení/den = sekce
`## Sezení N` v témže souboru (nikdy ne suffix b/c/d).

| Sezení | Datum | Téma | Detail |
|--------|-------|------|--------|
| 1 | 2026-05-22 | Founding — %THINK nad 5 UC, DAG, rozhodnutí B→A / UC1 MVP / jméno AzimutLab, založení kostry | [diary/2026-05-22.md](docs/diary/2026-05-22.md) |
| 2 | 2026-05-23 | UC2 průzkum ČÚZK (gate = CC BY 4.0 otevřena), oprava ZTMP→ZABAGED/ZTM, RESEARCH LIDAR→mapa (DMR 5G ≠ vegetace) | [diary/2026-05-23.md](docs/diary/2026-05-23.md#sezení-2--uc2-průzkum-čúzk--lidar-research) |
| 3 | 2026-05-23 | Vegetace gate ZAVŘENA: ČÚZK plné multi-echo mračno = NE (DMP OK je fotogrammetrie, ne LiDAR); KB+RESEARCH+TODO aktualizovány | [diary/2026-05-23.md](docs/diary/2026-05-23.md#sezení-3--vegetace-gate-čúzk-plné-mračno--ne) |
| 4 | 2026-05-23 | Od teorie ke kódu: procedurální generátor OB map (MVP) — spec zachycena, generator.py + batch.py + mini dataset 16 map s GT zdarma; reframe UC4-I → enabler-feeder UC5 | [diary/2026-05-23.md](docs/diary/2026-05-23.md#sezení-4--od-teorie-ke-kódu-procedurální-generátor-ob-map-mvp) |
| 5 | 2026-05-24 | Option 2: reálný ČÚZK DMR 5G terén do generátoru (`--terrain real`, `dmr.py`) — ArcGIS ImageServer exportImage → float grid bez GDAL, pyproj WGS84→S-JTSK; domain gap zmenšen, ověřeno vizuálně | [diary/2026-05-24.md](docs/diary/2026-05-24.md#sezení-5--option-2-reálný-čúzk-dmr-5g-terén-do-generátoru) |
| 6 | 2026-05-24 | Věrnost generátoru: tečkovaný obrys bažin (§4.4), vrstva balvanů (§4.11, slope-vážené + `mask_rock.png`), výraznější index contours (3 px). Baseline→verify, regrese real OK | [diary/2026-05-24.md](docs/diary/2026-05-24.md#sezení-6--věrnost-generátoru-balvany-obrys-bažin-index-contours) |
| 7 | 2026-05-24 | Reálný batch dataset: `batch.py --terrain real` z 10 lokalit ČR (`CZ_LOCATIONS`), montáž s popisky. Bug `dmr.py` cache-before-validate opraven; Krušné hory posunuty z hranice (oříznutý TIFF) | [diary/2026-05-24.md](docs/diary/2026-05-24.md#sezení-7--reálný-batch-dataset-z-lokalit-čr) |
| 8 | 2026-05-25 | Vektorizace vrstevnic na ISOM: `contours.geojson` (101/102, georef S-JTSK) + `.omap` export (`omap_export.py`, template-based, verify v OOM). DRY paleta → `palette.py`. Mapový portál ČSOS → KB (cesta B, gate zavřená). lasertool/AutoTrace/multi-echo zaznamenáno | [diary/2026-05-25.md](docs/diary/2026-05-25.md#sezení-8--vektorizace-vrstevnic-na-isom--dry-paleta--čsos-kb) |
| 9 | 2026-05-25 | %AUDIT:CODE + %AUDIT:DOCS (foundations úklid): kód čistý (R1 DRY bílá z palety, K1 `__future__` smazán 3.14, K2 `WORLD_W_M`); docs D1-D7 (sandbox „prázdný"/architecture „kód žádný" opraveny, spec §4.5 tloušťky, založen `GLOSSARY.md`). Verify 67 linií = baseline | [diary/2026-05-25.md](docs/diary/2026-05-25.md#sezení-9--auditcode--auditdocs-foundations-úklid) |
| 10 | 2026-05-25 | Bodové symboly lokálních extrémů (§4.10): malé uzavřené vrstevnice → 112/113/115 (knoll/depression), 116 Pit vynechán. `mask_symbols.png` (§8.1) + `point_symbols` v meta. Verify: zachování linie+symboly (real 67=60+7 = baseline). Cesty §4.9 → `[!]` | [diary/2026-05-25.md](docs/diary/2026-05-25.md#sezení-10--bodové-symboly-lokálních-extrémů) |
