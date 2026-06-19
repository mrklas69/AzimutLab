# Handoff 2026-06-19 — mrkla/HAL3000

Předání ze Sezení 148 (ntbhej). Cíl: převzít stav po auditních nálezech 260619,
vizuálně ověřit regenerované mapy a pokračovat ve zvyšování KPI generátoru přes KOMPAS.

## Stav

- `Generator()` narativ pořád platí: ROADMAP, KOMPAS a KPI jsou hlavní řízení práce.
- `scan mining` je povolený podtah `Generator()`, pokud krmí barvy, masky, symbol candidates,
  GT/kalibrační signály nebo KOMPAS. Není to zakázaná práce na `Rekonstruktor()`.
- `resources/Velbloud.pgw` byl na ntbhej lokálně vyrobený z `.omap` georeference a `print_area`.
  `resources/` je gitignored, takže soubor není součást commitu.
- `isom_scan/` má nově durable Git hranici: textový harness je verzovatelný, copyright PNG/PDF/runs
  zůstávají lokální a ignorované.
- Lokální `.venv` na ntbhej byla znovu vytvořená přes `uv`; po opravě hlásila Python `3.14.5`.
  Na mrkla/HAL3000 použij vlastní prostředí podle stroje, hlavně kvůli CUDA.

## Co se změnilo

- Přegenerované mapy:
  - KPI sada: `maps/Bedřichovka/`, `maps/Blatná/`, `maps/Velbloud/` včetně `sep/`, `rgb.*`,
    `meta.json`, `bg_scan.png`, `.omap`.
  - DEV mapy: `Soví vrch`, `Nová Louka`, `Lidové sady`, `Hrubá Skála`, `Novina` včetně `bg_dmr.png`.
  - Starší ad-hoc mapy: `Borecké skály`, `Borný`, `Doksy`, `Hamr na Jezeře`, `Rovné skály`
    včetně `bg_dmr.png`.
- `generator/separate.py`: `403 Rough open land` má per-class `min_area_px=60`; ostatní plochy
  zůstávají na globálních 120 px.
- KPI po doplnění `Velbloud.pgw` a regeneraci:
  - baseline před zásahem: `57,6 %`;
  - po `403 min_area_px=60`: `59,5 %`;
  - plocha `66,5 % → 70,7 %`, linie `59,0 % → 59,5 %`, bod `60,1 % → 60,1 %`.
- KOMPAS po změně:
  - `403 Rough open land`: `orig 1295 / gen 488`, provedení `ok` (předtím gen 262);
  - největší zbývající díry: `508`, `204`, `416`, `306`, `409`, `109`, `202`, `404`, `410`, `501`.

## Verify příkazy

Spusť z kořene repa:

```powershell
.venv\Scripts\python.exe generator\measure_dod.py
.venv\Scripts\python.exe generator\measure_dod.py --table
.venv\Scripts\python.exe -m unittest discover -s tests
```

Očekávání ze Sezení 148:

```text
Bedřichovka    51,6 %
Blatná         64,6 %
Velbloud       62,1 %
PRŮMĚR KPI     59,5 %
```

`--table` má ukázat `403` jako `ok`, ne nový přestřel.

## Vizuální kontrola

Otevřít v OpenOrienteering Mapper:

- `maps/Bedřichovka/Bedřichovka.omap`
- `maps/Blatná/Blatná.omap`
- `maps/Velbloud/Velbloud.omap`

Zkontrolovat:

- `403` drobnější bledě žluté paseky po snížení prahu. Hledat přirozené zacelení podstřelu,
  ne žlutý šum.
- `bg_scan.png` alignment u KPI map.
- U DEV/ad-hoc map zapnout `bg_dmr.png` a rychle projít, že georef/podklady sedí a render není prázdný.

## Další KPI tahy

Držet stejnou 3-map sadu a měřit před/po přes KOMPAS.

- `508 Narrow ride`: velký podstřel, ale tvrdá ZABAGED vrstva. Nepřidávat pseudo bez zdroje.
- `204`/`210`: pseudo skalní body; měřit crosswalk-aware, hlídat přestřel a forbids.
- `306 Minor water channel`: kandidát na data/relief kombinaci.
- `409`/`404`/`410`: pattern třídy, pravděpodobně scan-mining nebo model receptive-field problém.
- `109 Small knoll`: kandidát z DMR, ale ověřit proti reliéfu a nehonit jen počty.

## Rizika

- `527` je pořád přestřel po historicky špatné crosswalk-slepé kalibraci. Nekalibrovat 527/531
  bez nového crosswalk-aware měření na stejné sadě.
- `527`/`531` a podobné pseudo hustoty nejsou další low-risk KPI páka. Goodhart riziko je vyšší než u `403`.
- `resources/Velbloud.pgw` je lokální gitignored artefakt. Pokud na mrkla/HAL3000 chybí, KPI default
  se vrátí na nesrovnatelnou 2-map sadu.
- `isom_scan` binární vstupy a run výstupy jsou ignorované z licenčních důvodů. Verzovat jen textový harness.
- Generátorový smoke/invariant balík `260619-A6` pořád chybí; před většími zásahy do `generator.py`
  ho doplnit.
