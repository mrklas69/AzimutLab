# Architektura — AzimutLab

**Status**: Deštník fáze B; první reálný kód (Sezení 4, 2026-05-23) — syntetický
generátor (`generator/`) jako UC4-I/UC5 enabler-feeder; UC2 konektory reálných
geodat (`connectors/`, Sez. 16–18) běží. Kanonický popis UC DAGu a vrstvení.
**Zdroj pravdy**: tento soubor. README shrnuje, IDEAS brainstormuje, implementace
(`generator/`) z něj vychází.

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
│   QGIS / ČÚZK ZABAGED /   │          │   klasifikace bod/linie/    │
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
Místo pro experimenty (každý ve vlastní složce). **Toto je první základ** — nejlevnější,
nejnižší riziko, a místo, kam ostatní UC zapisují svoje nálezy.
- `docs/kb/` = referenční katalog (data-sources, isom-issprom, tools-models).
- Složka `sandbox/` zrušena (Sez. 39) — měla jediného obyvatele (`generator-poc`), který dozrál
  na pilíř `generator/`. Až vznikne nový experiment, založí se ad-hoc (YAGNI: nedržet prázdný obal).
- Hranice domény: **zatím čistě orienteering** (ISOM/ISSprOM). Zobecnění na
  OSM/Google Maps je vědomě odložené — viz „Čekající rozhodnutí".

### UC2 — Data konektory (ENABLER)
Otestovat a vytvořit spojení na užitečné zdroje třetích stran: LIDAR, ortofoto, QGIS,
ČÚZK ZABAGED/ZTM, geoportál. Najít vhodné mapové portály/podklady/databáze.
- Krmí UC4-II (inspirované souřadnicemi) a UC4-III (georef podklady).
- **Každý zdroj nese licenci** (sloupec v `docs/kb/data-sources.md`).
- Od průzkumu k běžícím konektorům (Sez. 16–42): **`connectors/`** = první sdílená kódová
  složka mimo sandbox (drobný krok B→A; vedle ní dnes `generator/`, Sez. 39). `dmr.py` (DMR 5G
  výškopis, ArcGIS ImageServer),
  `zabaged.py` (ZABAGED Polohopis ArcGIS REST, Sez. 26: cesty + lesní průseky + voda + budovy + vedení/lanovka +
  železnice + kolejiště + skály + mosty/tunely + řopíky + plošný pokryv open land/hřbitov/parkoviště Sez. 41 +
  areály účelové zástavby 114 → 520/501 + kůlny 105 → 521, Sez. 42 +
  **Sez. 43 systematický audit katalogu: zámek/hrad → 521, zřícenina → 523, věž/vodojem/silo/… → 524, mohyla → 526,
  kříž → 530, strom → 417, sráz → 104, zeď/hradba → 513, rokle/výmol → 107 Erosion gully (Sez. 58)** — `--landmarks`/`--linefeatures`;
  **Sez. 44 dávka 4 vodní/mokřady: bažina+rašeliniště → 308 Marsh (`--marsh`; + 310 Indistinct pseudo split ~55 % Sez. 99),
  pramen → 312, jeskyně+šachta → 203.2, nádrž → 311 (`--landmarks`); hráz 528 odložena**;
  **Sez. 45 stromořadí `Liniová vegetace` → 406 Vegetation: slow running (`--treerows`, lineární les: osa→buffer→pás;
  oprava 416 = hranice porostů byla sémanticky špatně)**;
  **Sez. 52 komín → 524 (`--landmarks`) + zábrana → 519 Crossing point (`--barriers`, jen bod na zdi 513 = průchod
  plotem; zeď se pod brankou přeruší)**;
  **Sez. 54 `Ostatní plocha v sídlech` 115 → 501.1 Paved area bez obrysu (`--paved`, base výplň sídla vespod)
  — odemčeno novou podporou děr (holes): `geom_to_polygons` vrací vnitřní prsteny, plošné vrstvy je vyříznou
  (enabler napříč voda/budovy/pokryv); + color-table průlom „Dolní hnědá 50%" v template**;
  **Sez. 56 kamenolom `Povrchová těžba, lom` 118 → 520 olivová (`--surfaces`, oplocený těžební areál = zákaz
  vstupu, mirror hřbitovu; místo odloženého 201 — plocha→plocha, 201 je linie)**;
  **Sez. 57 pole balvanů `Skupina_balvanů__linie_` 13 → 208 Boulder field (`--rocks`, osa→buffer pás 1,5 mm →
  náhodné trojúhelníky, mirror stromořadí 406; plot 516–518 = doložený SKIP, ZABAGED plot nevede)**),
  **`ruian.py`** (RÚIAN katastr ArcGIS REST, **Sez. 42 — druhý ČÚZK datový zdroj**: parcely podle druhu pozemku;
  zahrada + zastavěná plocha → 520 olivová „zákaz vstupu"), **`forest.py`** (AOPK „Les_Mapy" porostní skupiny,
  **Sez. 62 — třetí datový zdroj, JINÝ server `gis.nature.cz`**: atribut `BARVA`=věk → zeleň 406/408/410, **PROXY/predikce**),
  `ortofoto.py` (ORTOFOTO podklad, Sez. 26).
  Sourozenci, sdílí `build_bbox` (geo-výsek) i **`arcgis.py`** (Sez. 42 — sdílený ArcGIS REST transport:
  paging+cache+GeoJSON parsery, DRY pro `zabaged`+`ruian`+`forest`). Generátor (UC4-I) je první konzument
  (`--terrain/--paths/--rides/--water/--buildings/--powerlines/--railways/--paved/--rocks/--bridges/--ropiky/
  --surfaces/--landmarks/--linefeatures/--marsh/--treerows/--forest-age/--barriers real`; form lines **i skalní
  plochy 206 z DMR** (rock-relief sklon, Sez. 63 — derivace z výškopisu, ne ZABAGED); olivová z RÚIAN i ZABAGED 114 jde do `--surfaces`).
  **Most UC2→UC5:** `--forest-age` byl první **predikční** vrstva (věk porostu ≠ věrná runnability, `proxy:true`) —
  ⟲ **ARCHIVOVÁN Sez. 82** (A1 measure-first: pokrytí jen 33 % korpusu, IoU 0,12 s kresbou kartografa, přestřel zelené
  3,3×; kód zůstává funkční, doložená cesta). Predikční vegetaci nahrazuje **separace z reálné mapy** (`generator/separate.py`,
  `separate_areas`). **Integrace Sez. 83:** orchestrátor `generator/pairs.py` (`build_pair(cid)`) spojí real ČÚZK vrstvy
  + separovanou vegetaci do JEDNÉ georeferencované `.omap` per Livelox classId (provenance real/predict) — UC5 továrna párů.

### UC5 — Modely „rozumí mapám" (ENABLER)
Sada modelů, které mapám rozumí: 100% separace barev použité palety; klasifikace
bodových, liniových i plošných ISOM symbolů.

> **⟲ Reframe Sez. 79 (částečná propagace, plná revize = A1).** „Rozumí mapám" = **`reconstructor()`**
> (sken → `.omap`, dříve pracovně „mapper"), trénovaný na párech z **`generator()`** (real + **predict**
> část — vegetace procedurálně, viz GLOSSARY). Model **`ORTO → 4 barvy`** popsaný níže (Sez. 74-78) narazil
> na strop val mIoU ~0,25 → **archivovaná odbočka**, NE hlavní směr (nemazat — doloženo). Foundations:
> nejdřív `generator()` predict část, pak `reconstructor()`. Datová pipeline (páry, GT, split, dlaždice)
> zůstává užitečná. **Plná revize UC3 / UC4-III / fázový plán / Pic2Omap absorpce odložena (A1).** Pojmy:
> GLOSSARY `generator()` / `reconstructor()`.
>
> **DoD generátoru (Sez. 91):** `generator()` je strop tréninku — co nenakreslí do `.omap`, to se
> `reconstructor()` nenaučí. **Fáze výroby hotová až při ≥ 90 % pokrytí ISOM mapových symbolů 5 vzorových map
> v `resources/`** (`generator/measure_dod.py` driver, crosswalk-aware; **separační baseline 43 %**, Sez. 94-95).
> Větší páka = rozšiřovat pokrytí generátoru, ne ladit model.
> **Sez. 95-96 — DoD ≥ 90 % je PLOŠNĚ NEDOSAŽITELNÉ.** Analytický cut (`compare_isom.used_geometry`, geometrie
> reálně použitého symbolu z OOM `<symbol type>`, variant-aware): **plošný strop 54 %** (kdyby gen dokreslil
> chybějící typy ploch; Sez. 96 přeřadil 210 Stony z plochy na bod — kartografové ho kreslí polem teček); zbytek =
> linie (→ Png2Line) + body (→ Png2Point), oba modely zatím NEEXISTUJÍ → cesta k 90 % vede přes
> ně, ne přes leštění ploch. DoD baseline přepnut z forest_age proxy na **separaci** (reálná produkční cesta párů
> `pairs.build_pair`; forest_age proxy 410 byl fabrikace — souvislé 410 v mapách nejsou, viz Sez. 95 měření).
- Sdílené jádro (DRY) — krmí UC3 (poznat fialovou = klasifikace) i UC4-III (pic2omap).
- Přímá návaznost na Pic2Omap `color_separator.py` / detektory — kandidát na první
  reálně sdílený kód při přechodu na monorepo.
- **Runnability korpus (Sez. 67–68):** UC5 model predikce běhatelnosti (zelená 406/408/410 +
  žlutá open z ortofota/DMR/věku) je **supervised** → potřebuje GT = co kartograf nakreslil.
  Vegetace gate (Sez. 59) brání věrné runnability z open dat → reálný GT je nutný (syntetika
  cirkulární). Zdroj = **Livelox** (`connectors/livelox.py`, Sez. 68): reálná OB mapa jako
  rastr + georef (gate 1+2 prošly — 1,33 m/px stačí na plošnou GT, quad sedne bez fitu);
  GT segmentace `connectors/map_gt.py` (zelená/žlutá z barev; olivová 520 → label 0, Sez. 71;
  fialový přetisk tratě → label 255 ignore, Sez. 72; layout mimo mapu — legenda/tabulka/titulek/
  papír — → 255 ignore přes barevný detektor `_detect_map_area`, Sez. 73 část B).
  Korpus `resources/livelox/` (gitignored, privátní/TDM). **Škálováno Sez. 70: 268 map** (allEvents batch).
  **Kurace Sez. 71** (`connectors/curate.py` → `_curation.json`): GT = strop supervised modelu → mapy
  otagovány (discipline classic/sprint/mtbo/overview + quality tagy) a vybráno **216 keep classic** =
  tréninkové jádro (foot-O les; sprint/mtbo/varianty/foto/OSM-podklad mimo). Reader `kept_dirs('classic')`.
- **Model — start Sez. 74 (%THINK + krok 0):** rozhodnuto vstup **jen ortofoto RGB**, **5 tříd**
  (0 podklad / 1-3 zelená / 4 open + 255 ignore), architektura **U-Net + ResNet34** (smp, BF16). Hlavní
  teze: riziko není architektura, ale kvalita párů (X,Y) — **vstup ortofoto zatím není vyrobený** (gaty
  před modelem: zarovnané páry + měření georef offsetu). Trénink jen na `mrkla` (RTX 5070, `docs/kb/
  hardware.md`). **Krok 0 hotový:** PyTorch `cu128` na Blackwell ověřen (smoke test, U-Net forward na GPU).
  Architektura: IDEAS „UC5 runnability model"; kroky: TODO.
- **Datová pipeline hotová (kroky 1-3, Sez. 75-76):** zarovnané páry (X,Y) `build_georef_pair` + georef
  QC (GATE 1, medián ~1-3 px); ČR/DE filtr (`_cz_filter.json`: 216 keep → **207 ČR**, cizí mají prázdné
  ČÚZK ortofoto); class distribution (410 fight 1,35 % → váhy do loss, validováno proti 5 mapařským `.omap`);
  **geografický split** (`connectors/split.py` → `_split.json`: train/val/test 145/31/31, clustery dle
  překryvu bboxů = bez leaku); hromadná výroba **207 párů** (`build_pairs`); **tréninkové dlaždice**
  (`model/runnability/tile.py`, Sez. 77 — pre-tiling párů na 512×512, stride 256, rejection <30 % validních px →
  **~8 125 dlaždic** v `resources/tiles/`, median-freq váhy `_tiles.json`). Adresář **`model/`** = UC5 model kód
  (sourozenec `connectors/`/`generator/`, sys.path fáze B); od Sez. 88 dva podadresáře `runnability/` (archiv) +
  `png2area/` (živý reconstructor model).
- **Krok 4 dokončen (Sez. 78) + ARCHIVOVÁN (Sez. 79), přesun do `model/runnability/` (Sez. 88):** loader
  (`model/runnability/dataset.py`, D4 aug + ImageNet norma) + trénink (`model/runnability/train.py`, smp
  U-Net/ResNet34, BF16, per-class IoU). Baseline **val mIoU 0,259 / test 0,223**, ale křivka = **generalizační
  strop** (val plochá ~0,25 od ep1 → RGB-only málo, runnability = podrost pod korunami shora nevidět). → směr
  `ORTO → 4 barvy` **archivovaná odbočka** (viz reframe note výše), kód nemazán. Datová pipeline
  (páry/GT/split/dlaždice) zůstává znovupoužitelná — reálně reusována Png2Area modelem níže.
- **Png2Area reconstructor — PRVNÍ FUNKČNÍ MODEL (Sez. 88 kód → Sez. 90-91 trénink), `model/png2area/{tile,dataset,train}.py`:**
  první ze tří CV úloh dekompozice OOM (Area/Point/Line). Učí se na páru **[`scan.png` (X, degradovaný render),
  `area_labels.png` (Y, **16 ISOM area kódů + pozadí** ze `omap_raster`)]** vyrobeném `generator/pairs.py`. Izomorf
  s archivem (reuse tiling 512/256, median-freq, D4, ImageNet, U-Net/ResNet34) — liší se: vstup je **mapa, ne ortofoto**
  (proto vysoký strop, na rozdíl od archivu), **bez rejection** (pozadí = legitimní třída) a **bez IGNORE** (Y z naší
  `.omap` je celé validní). Dlaždice → `resources/area_tiles/`, checkpoint → `resources/area_model/`. **Výsledek
  (Sez. 90):** plný trénink 40 ep → **test mIoU 0,621 ≈ val 0,629** (bez leaku, vs runnability baseline 0,25); budovy
  `521` zachráněny 0,00→0,68 (median-freq váhy + data). **Stabilizace (Sez. 91):** cap vah @10 + cosine LR →
  **test mIoU 0,640 / val 0,654** (loss-spiky zmizely); vzácné třídy (`208`/`501`/`301.1`) = datový strop →
  class-balanced expansion. **Pokrytí area tříd (Sez. 92):** přidána **403 Rough open** (bledá žlutá ze separace,
  první vegetační třída nad zeleň) → 16 area kódů; další rozšiřování řídí DoD pokrytí (viz reframe note výše).

### UC3 — Restaurace (APP)
Odebrat fialovou vrstvu (kontroly, občerstvení, zakázané oblasti) ze závodních
(často opotřebených, tištěných) map a digitálně je restaurovat (deskew, de-crease,
inpainting).
- **Nejlevnější aplikační kandidát**: stačí segmentace fialové, ne plný UC5.

### UC4 — Generátory (APP)
- **I. plausible-random** — náhodné, ale realisticky vyhlížející mapy (ne náhodný
  soubor ISOM symbolů; terén/vrstevnice musí dávat smysl). Plná verze zůstává nejtěžší,
  ale **jako generátor trénovacích dat s ground-truth zdarma je to enabler-feeder pro UC5**
  (reframe Sez. 4) — ne „úplný konec". Kód: `generator/` (pilíř, povýšen ze sandboxu Sez. 39), metoda:
  `docs/kb/generator-procedural.md` (skalární pole → vrstvy; reálný terén §8.5 = `--terrain real`,
  ČÚZK DMR 5G, hotovo Sez. 5).
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
