# Architektura — AzimutLab

**Status**: Founding (Sezení 1, 2026-05-22). Kanonický popis UC DAGu a vrstvení.
**Zdroj pravdy**: tento soubor. README shrnuje, IDEAS brainstormuje, kód (zatím žádný)
implementuje sem.

AzimutLab není jedna aplikace — je to **deštník nad pěti use-casy, které tvoří
orientovaný graf závislostí (DAG), ne plochý seznam.** Tahle struktura určuje pořadí
prací: enablery před aplikacemi.

## Vrstvy

```
┌─────────────────────────────────────────────────────────────────┐
│ META    UC1  Knowledgebase + Sandbox                              │
│              know-how, odkazy, zdroje, izolované experimenty       │
└───────────────────────────────┬───────────────────────────────────┘
                                 │ vše ostatní se sem zapisuje
        ┌────────────────────────┴────────────────────────┐
┌───────▼───────────────────┐          ┌───────────────────▼─────────┐
│ ENABLER  UC2  Data        │          │ ENABLER  UC5  Modely        │
│   konektory               │          │   „rozumí mapám"            │
│   LIDAR / ortofoto /      │          │   palette separation,       │
│   QGIS / ČÚZK ZTMP /      │          │   klasifikace bod/linie/    │
│   geoportál               │          │   plocha (ISOM)             │
└───────┬───────────────────┘          └───────────┬─────────────────┘
        │                                           │
        └────────────────────┬──────────────────────┘
┌────────────────────────────▼──────────────────────────────────────┐
│ APP     UC3  Restaurace            UC4  Generátory                  │
│         de-purple, de-crease,         I.  plausible-random          │
│         digitální restaurování        II. inspirované (obraz/coords)│
│         opotřebených map               III.přesné = Pic2Omap        │
│                                            (sken → OCD/OMAP)         │
└────────────────────────────────────────────────────────────────────┘
```

## Use cases — detail

### UC1 — Knowledgebase + Sandbox (META) · MVP
Shromáždit informace, důležité odkazy a know-how pro orienteering kartografii.
Sandbox pro experimenty, každý ve vlastní složce. **Toto je první základ** — nejlevnější,
nejnižší riziko, a místo, kam ostatní UC zapisují svoje nálezy.
- `docs/kb/` = referenční katalog (data-sources, isom-issprom, tools-models).
- `sandbox/` = izolované experimenty.
- Hranice domény: **zatím čistě orienteering** (ISOM/ISSprOM). Zobecnění na
  OSM/Google Maps je vědomě odložené — viz „Čekající rozhodnutí".

### UC2 — Data konektory (ENABLER)
Otestovat a vytvořit spojení na užitečné zdroje třetích stran: LIDAR, ortofoto, QGIS,
ČÚZK ZTMP, geoportál. Najít vhodné mapové portály/podklady/databáze.
- Krmí UC4-II (inspirované souřadnicemi) a UC4-III (georef podklady).
- **Každý zdroj nese licenci** (sloupec v `docs/kb/data-sources.md`).
- MVP fáze = *průzkum* (survey + licence), ne ještě běžící konektory.

### UC5 — Modely „rozumí mapám" (ENABLER)
Sada modelů, které mapám rozumí: 100% separace barev použité palety; klasifikace
bodových, liniových i plošných ISOM symbolů.
- Sdílené jádro (DRY) — krmí UC3 (poznat fialovou = klasifikace) i UC4-III (pic2omap).
- Přímá návaznost na Pic2Omap `color_separator.py` / detektory — kandidát na první
  reálně sdílený kód při přechodu na monorepo.

### UC3 — Restaurace (APP)
Odebrat fialovou vrstvu (kontroly, občerstvení, zakázané oblasti) ze závodních
(často opotřebených, tištěných) map a digitálně je restaurovat (deskew, de-crease,
inpainting).
- **Nejlevnější aplikační kandidát**: stačí segmentace fialové, ne plný UC5.

### UC4 — Generátory (APP)
- **I. plausible-random** — náhodné, ale realisticky vyhlížející mapy (ne náhodný
  soubor ISOM symbolů; terén/vrstevnice musí dávat smysl). **Nejtěžší, nejvzdálenější.**
- **II. inspirované** — mapou (obrázkem) nebo souřadnicemi konkrétní lokality (→ UC2).
- **III. přesné** — **vrchol projektu**: sken zablácené pomačkané závodní mapy → OCD/OMAP.
  Toto *je* Pic2Omap. Žije ve vlastním repu (WIP); při přechodu na monorepo → `apps/pic2omap`.

## Vztah k Pic2Omap — fázový plán

| Fáze | Stav | Co to znamená |
|------|------|---------------|
| **B** (teď) | Deštník | AzimutLab = meta-vrstva (UC1). Pic2Omap běží jako samostatné repo. AzimutLab na něj odkazuje, neduplikuje. |
| **A** (cíl) | Monorepo | Až UC5-jádro dozraje a Pic2Omap ho reálně konzumuje → Pic2Omap se vtáhne jako `apps/pic2omap`. Sdílené jádro reálně sdílené. |

Spouštěč přechodu B→A: **existuje sdílený kód, který by Pic2Omap jinak duplikoval.**
Dokud neexistuje, monorepo by bylo prázdná struktura (over-engineering).

## Izomorfismus s Pic2Omap

Pic2Omap má pattern `raster → pic2db → db.json (SSoT) → db2omap → OMAP`. Stejná osa
platí pro celý AzimutLab: každá mapa (skenovaná, generovaná, restaurovaná) má kanonickou
mezivrstvu, ze které/do které se transformuje. UC4-III je hrana raster→DB, UC4-I/II jsou
hrana DB→raster. To je důvod, proč mají sdílet jádro (UC5), ne každý vlastní reprezentaci.

## Čekající rozhodnutí

- **Zobecnění domény** (OSM / Google Maps / obecná kartografie) — zmíněno v UC1 zadání,
  ale vědomě odloženo: ISOM orienteering je vyhraněná doména (přesná sémantika symbolů),
  předčasné zobecnění rozmělní conceptual integrity. Rozhodnout, až bude orienteering jádro stát.
- **Přesný spouštěč B→A** — kvantifikovat „dozrálé UC5-jádro" (jaký konkrétní sdílený modul).
- **Formát kanonické mezivrstvy napříč UC** — převzít Pic2Omap `db.json`, nebo vlastní?
  (Řešit, až vznikne první kód mimo Pic2Omap.)
