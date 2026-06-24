# Architektura — AzimutLab

**Status**: Deštník fáze B; první reálný kód (Sezení 4, 2026-05-23) — syntetický
generátor (`generator/`) jako enabler-feeder; UC2 konektory reálných
geodat (`connectors/`, Sez. 16–18) běží. Kanonický popis UC DAGu a vrstvení.
**Zdroj pravdy pro statickou strukturu** (UC vrstvení, vztah k Pic2Omap): tento soubor.
README shrnuje, IDEAS brainstormuje, implementace (`generator/`) z něj vychází.

> **SSoT směru a etap = `docs/ROADMAP.md`** (Sez. 136), čtený každým `%BEGIN` (krok 0.5).
> ROADMAP drží **osu `Generator()` → `Rekonstruktor()`** a fázovou závoru (jsme v Etapě 1
> `Generator()`; „degradace"/„rekonstruktor" = zatím zakázaná slova). Tenhle soubor popisuje
> statické UC vrstvení; **kde se rozcházejí, platí ROADMAP.** Mapování os: `Generator()` =
> UC4-I enabler-feeder; `Rekonstruktor()` (sken → `.omap`) = cílový produkt, dříve roztříštěný
> přes UC3 (de-purple) + UC4-III (Pic2Omap) + UC5 modely — dnes ho nesou tři reconstructory
> (Png2Area/Point/Line, viz UC5).

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
│   LIDAR / ortofoto /      │          │   reconstructory sken→.omap │
│   QGIS / ČÚZK ZABAGED /   │          │   Png2Area / Png2Point /    │
│   geoportál               │          │   Png2Line (ISOM geometrie) │
└───────┬───────────────────┘          └───────────┬─────────────────┘
        │                                           │
        └────────────────────┬──────────────────────┘
┌────────────────────────────▼──────────────────────────────────────┐
│ APP     UC3  Restaurování map      UC4  Generátory                  │
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
  zahrada + zastavěná plocha → 520 olivová „zákaz vstupu"), `ortofoto.py` (ORTOFOTO podklad, Sez. 26),
  **`magnetic.py`** (Sez. 112 — grivace = deklinace `pygeomag` WMM offline + konvergence `pyproj`; orientace
  severníku OB mapy pro `--grivation-auto`; NEní ČÚZK/ArcGIS — lokální model + projekce).
  Sourozenci, sdílí `build_bbox` (geo-výsek) i **`arcgis.py`** (Sez. 42 — sdílený ArcGIS REST transport:
  paging+cache+GeoJSON parsery, DRY pro `zabaged`+`ruian`). Generátor (UC4-I) je první konzument
  (`--terrain/--paths/--rides/--water/--buildings/--powerlines/--railways/--paved/--rocks/--bridges/--ropiky/
  --surfaces/--landmarks/--linefeatures/--marsh/--treerows/--barriers real`; form lines **i skalní
  plochy 206 z DMR** (rock-relief sklon, Sez. 63 — derivace z výškopisu, ne ZABAGED); olivová z RÚIAN i ZABAGED 114 jde do `--surfaces`).
  **Most UC2→UC5:** první **predikční** vrstva byl `--forest-age` (AOPK věk porostu → zeleň, `forest.py`/`gis.nature.cz`)
  — ⟲ **ARCHIVOVÁN Sez. 82, kód SMAZÁN Sez. 102** (A1 measure-first: pokrytí jen 33 % korpusu, IoU 0,12 s kresbou
  kartografa, přestřel zelené 3,3×; doložená slepá ulička, git/diář ji drží). JEDINÝ zdroj predikční vegetace je
  **separace z reálné mapy** (`generator/separate.py`, `separate_areas`); pseudorealistic vegetace pro lokality bez
  skenu = budoucí směr (DEV `--location` mapy proto kreslí bílý les). **Integrace Sez. 83:** orchestrátor
  `generator/pairs.py` (`build_pair(cid)`) spojí real ČÚZK vrstvy + separovanou vegetaci do JEDNÉ georeferencované
  `.omap` per Livelox classId (provenance real/predict) — UC5 továrna párů.

### UC5 — Modely „rozumí mapám" (ENABLER)
Sada modelů, které mapám rozumí. **Dnešní podoba (= `Rekonstruktor()` v ROADMAP): tři
reconstructory `sken → ISOM geometrie .omap`** podle typu symbolu — **Png2Area** (plošné),
**Png2Point** (bodové), **Png2Line** (liniové). Trénují se na párech `[render, .omap]`
z `Generator()`. (Separace barev palety přežívá jen jako pomocník fáze I generátoru —
`generator/separate.py` krmí Png2Area —, NE jako cíl UC5 modelu; historický rámec „palette
separation / klasifikace" je opuštěný, viz reframe Sez. 79 níže.)

> **⟲ Reframe Sez. 79 (propagace dokončena Sez. 139 — sladěno s ROADMAP).** „Rozumí mapám" = **`reconstructor()`**
> (sken → `.omap`, dříve pracovně „mapper"), trénovaný na párech z **`generator()`** (real + **predict**
> část — vegetace procedurálně, viz GLOSSARY). Model **`ORTO → 4 barvy`** popsaný níže (Sez. 74-78) narazil
> na strop val mIoU ~0,25 → **archivovaná odbočka**, NE hlavní směr (nemazat — doloženo). Foundations:
> nejdřív `generator()` predict část, pak `reconstructor()`. Datová pipeline (páry, GT, split, dlaždice)
> zůstává užitečná. **Taxonomie směru rozhodnuta `ROADMAP.md` (osa Generator()→Rekonstruktor(), Sez. 136);
> sladěno do této sekce Sez. 139.** Zbývá jen kosmetická revize statického UC3/UC4-III/Pic2Omap rámce
> (umístění de-purple a Pic2Omap absorpce v 5-UC DAGu) — neblokuje. Pojmy: GLOSSARY `generator()` / `reconstructor()`.
>
> **DoD generátoru (Sez. 91):** `generator()` je strop tréninku — co nenakreslí do `.omap`, to se
> `reconstructor()` nenaučí. **Fáze výroby hotová až při ≥ 90 % pokrytí ISOM mapových symbolů 5 vzorových map
> v `resources/`** (`generator/measure_dod.py` driver, crosswalk-aware; **separační baseline 43 %**, Sez. 94-95).
> Větší páka = rozšiřovat pokrytí generátoru, ne ladit model.
> **Sez. 95-96 — DoD ≥ 90 % je PLOŠNĚ NEDOSAŽITELNÉ.** Analytický cut (`compare_isom.used_geometry`, geometrie
> reálně použitého symbolu z OOM `<symbol type>`, variant-aware): **plošný strop 54 %** (kdyby gen dokreslil
> chybějící typy ploch; Sez. 96 přeřadil 210 Stony z plochy na bod — kartografové ho kreslí polem teček); zbytek =
> linie (→ Png2Line) + body (→ Png2Point) → cesta k 90 % vede přes ně, ne přes leštění ploch.
> **Png2Point HOTOVÝ Sez. 106, stabilizován Sez. 125, na kanonickém měřítku Sez. 126, scope rozšiřován 204/210→+417/419
> (Sez. 128) →+531/525/527 černé man-made (Sez. 158-159) →+109/111/112 hnědé terénní (Sez. 161-162) = 10 tříd** (test
> mF1 0,745 medián 3 seedů STABILNÍ na MPP 1,33; reálný transfer: 111/419/525/109/531 silné, 112/527 střední-dobré,
> 417 střední, 204 stabilní, 210 kolabuje; 112 reconstructor-only — gen nekreslí, mimo USED_CODES),
> pseudo body 204/210 integrovány do generátoru Sez. 107 (KPI 50,3 → 59,1 %), **pseudo 417/419 integrovány Sez. 136,
> +418 Sez. 137** (princip kamenů: 417 doplní řídký ZABAGED na reálnou hustotu, 418/419 čistě pseudo; 418 = plný zelený
> disk / 417 kroužek / 419 X; mimo voda/skály/budovy/cesty/zpevněné, ISOM rozestup; KPI 58,6 → 61,7 %, KOMPAS pokrytí —
> proporčně Goodhart-citlivé, jako POKRYTÍ legitimní; 418 NENÍ ve scope Png2Point detekce — generátor kreslí pro budoucí trénink);
> **Png2Line HOTOVÝ Sez. 130-132** (krok 1 watercourse 304/305, test mIoU 0,774, reálný transfer prokázán —
> completeness 0,85–0,93, strict IoU 0,409 po conf_thr 0,95; vektorizace maska→polyline Sez. 132; krok 2 dashed
> 508+516 zkoušen a zavržen Sez. 133). DoD baseline přepnut z forest_age proxy na
> **separaci** (reálná produkční cesta párů
> `pairs.build_pair`; forest_age proxy 410 byl fabrikace — souvislé 410 v mapách nejsou, viz Sez. 95 měření).
- Sdílené jádro (DRY) — krmí UC3 (poznat fialovou = klasifikace) i UC4-III (pic2omap).
- Přímá návaznost na Pic2Omap `color_separator.py` / detektory — kandidát na první
  reálně sdílený kód při přechodu na monorepo.
- **Runnability korpus (Sez. 67–68):** UC5 model predikce běhatelnosti (zelená 406/408/410 +
  žlutá open z ortofota/DMR/věku) je **supervised** → potřebuje GT = co kartograf nakreslil.
  Vegetace gate (Sez. 59) brání věrné runnability z open dat → reálný GT je nutný (syntetika
  cirkulární). Zdroj = **Livelox** (`connectors/livelox.py`, Sez. 68): reálná OB mapa jako
  rastr + georef (gate 1+2 prošly — 1,33 m/px stačí na plošnou GT, quad sedne bez fitu);
  GT segmentace `connectors/map_gt.py`: kompatibilní runnability `gt_labels` drží 0–4/255
  (zelená/žlutá; voda+520 → 0), zatímco sémantická větev `gt_semantic_labels` zachovává
  **5=voda, 6=ISOM 520** (Sez. 122). Fialový přetisk tratě → label 255 ignore (Sez. 72);
  layout mimo mapu — legenda/tabulka/titulek/papír — → 255 ignore přes `_detect_map_area`
  (Sez. 73 část B). `bg_gt` používá sémantickou, ne ztrátovou runnability vizualizaci.
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
  (sourozenec `connectors/`/`generator/`, sys.path fáze B); **tři podadresáře**: `runnability/` (archiv) +
  `png2area/` + `png2point/` (oba živé reconstructory).
- **Krok 4 dokončen (Sez. 78) + ARCHIVOVÁN (Sez. 79), přesun do `model/runnability/` (Sez. 88):** loader
  (`model/runnability/dataset.py`, D4 aug + ImageNet norma) + trénink (`model/runnability/train.py`, smp
  U-Net/ResNet34, BF16, per-class IoU). Baseline **val mIoU 0,259 / test 0,223**, ale křivka = **generalizační
  strop** (val plochá ~0,25 od ep1 → RGB-only málo, runnability = podrost pod korunami shora nevidět). → směr
  `ORTO → 4 barvy` **archivovaná odbočka** (viz reframe note výše), kód nemazán. Datová pipeline
  (páry/GT/split/dlaždice) zůstává znovupoužitelná — reálně reusována Png2Area modelem níže.
- **Png2Area reconstructor — PRVNÍ FUNKČNÍ MODEL (Sez. 88 kód → Sez. 90-91 trénink), `model/png2area/{tile,dataset,train}.py`:**
  první ze tří CV úloh dekompozice OOM (Area/Point/Line). Učí se na páru **[`rgb.png` (X, ČISTÝ gen render),
  `area_labels.png` (Y, **20 ISOM kódů + pozadí = `N_AREA 21`** ze
  `omap_raster`, historicky +403 Sez. 92 / +310 Sez. 99 / +404+407+409 Sez. 152)]** vyrobeném
  `generator/pairs.py`. Fotometrická degradace (sken-vady) NENÍ v páru — aplikuje se on-the-fly jako augmentace
  v `dataset.py` (Sez. 103, degradace patří do tréninkové fáze II/III, ne do generator() výroby párů). Izomorf
  s archivem (reuse tiling 512/256, median-freq, D4, ImageNet, U-Net/ResNet34) — liší se: vstup je **mapa, ne ortofoto**
  (proto vysoký strop, na rozdíl od archivu), **bez rejection** (pozadí = legitimní třída) a **bez IGNORE** (Y z naší
  `.omap` je celé validní). Dlaždice → `resources/area_tiles/`; každý tréninkový
  běh → `resources/area_model/runs/<run_id>/`. **Výsledek
  (Sez. 90):** plný trénink 40 ep → **test mIoU 0,621 ≈ val 0,629** (bez leaku, vs runnability baseline 0,25); budovy
  `521` zachráněny 0,00→0,68 (median-freq váhy + data). **Stabilizace (Sez. 91):** cap vah @10 + cosine LR →
  test mIoU 0,640 (loss-spiky zmizely); vzácné třídy (`208`/`501`/`301.1`) = datový strop → class-balanced
  expansion. **Pokrytí area tříd (Sez. 92):** přidána **403 Rough open** (bledá žlutá ze separace). **Přetrénován
  N_AREA 18 (Sez. 103):** +310 Indistinct marsh → 18 tříd; regen 205 párů + degradace-augmentace → test mIoU
  0,568 ≈ val 0,571 (hlavní plochy 0,70-0,92). **Voda 301 fix re-trénink (Sez. 118):** `omap_raster` měl od narození
  stale `301.1` → voda strukturálně vypadávala z Y (oba předchozí tréninky ji NIKDY neviděly, mIoU ji nepočítala);
  fix `301.1`→`301` + SSoT (Sez. 110) → regen 205 párů + re-tile → **test mIoU 0,537, VODA 301 IoU 0,65** (poprvé
  měřená, dříve strukturálně 0 = nadprůměrně naučená). mIoU 0,537 nesrovnatelné s 0,568 (to vodu nepočítalo).
  **MPP fix re-trénink (Sez. 126, audit C1/K1):** dlaždice byly 2,18 m/px, ale symboly/eval na 1,33 → kanonické
  měřítko `model/mpp.CANONICAL_MPP=1,33`, re-tile + retrain → **test mIoU 0,683** (+14,6 pb; voda 301 0,74).
  **Scope 21-class retrain (Sez. 156, audit A1):** regen 206 párů + re-tile na `N_AREA=21` (404/407/409) +
  retrain (`s156_area21_s42`) → **test mIoU 0,577** (pokles vs 0,683 = ředění 3 vzácnými třídami: 409 IoU
  0,03 datový strop, 404 0,36, 407 0,49; hlavní třídy drží 0,72–0,90). **eval_real ZAS BĚŽÍ na novém scope**
  (dřív shape-mismatch crash = jádro A1): Bedř soft mIoU 0,525 / pixel-acc 0,887, Blatná per-shade 0,232 /
  soft 0,363. Nález: 404/407/409 mají slabý reálný transfer (vzácné v ČR mapách, model je halucinuje, krade
  pixely od hlavních odstínů) — soft skupinová metrika to pohltí, přísná per-odstín klesá. Promotnut (`.bak`
  pojistka 18-class). Kanonický `resources/area_model/unet_best.pt` se mění pouze explicitním
  `train.py --promote <run_id>`.
- **Png2Point reconstructor — DRUHÝ FUNKČNÍ MODEL (Sez. 105-106), `model/png2point/{inject,dataset,train}.py`:**
  druhá ze tří CV úloh (bodové ISOM → lokalizace+klasifikace). **Injekce ikonek** na čistý `point_base` render
  (bez bodů, master flag `generate_map`) = GT zdarma + libovolně instancí (řeší vzácnost) + **heatmap regrese**
  (CenterNet focal, peak NMS → F1). Scope **10 tříd: 204 Boulder + 210 Stony + 417/419 zelené veg + 531/525/527 černé man-made (X/⊤/Λ) +
  109/111/112 hnědé terénní (disk/oblouk ∪/vyplněný ▽)** (210 = pole teček `210.1`, ne plocha — probe Sez. 106;
  417/419 Sez. 128 zelené s bílou knockout svatozáří; 531/525/527 Sez. 158-159; 109/111/112 Sez. 161-162; registr
  `inject.POINT_CLASSES` generalizován kind/color/n_range/peak_thr. **112 reconstructor-only** — gen nekreslí, mimo capability/USED_CODES). Root-cause 204 (Sez. 106): příčina F1 0,00 = **hustota pozitiv vs focal `n_pos` normalizace**
  (19× imbalance 210/204), ne velikostní záměna → `n_boulder` hustě → single-run **mF1 0,897**, ALE nestabilní.
  **Stabilizace Sez. 125: skutečný kořen = chybějící focal prior bias init** (mrtvá fáze prvních ~15 ep) →
  bias init → **test mF1 0,888 medián 3 seedů / rozptyl 0,019** (204 ~0,92 / 210 ~0,86, obě stabilně živé).
  **MPP fix (Sez. 126):** retrain na kanonickém měřítku 1,33 → **mF1 medián 0,874** (0,888 bylo na starém měřítku
  se symboly 1,64× velkými); reálný transfer 210 z kolapsu (F1 0,04) na 0,11–0,18 (tečka 4,5 px přežije sken).
  **Scope +417/419 (Sez. 128):** 4-třídový model, synt mF1 medián 0,827; reálný transfer **419 silný 0,67–0,76**
  (líp než 204 — výrazný zelený X + svatozář), **417 střední 0,40–0,49** (čte, přestřeluje) → lekce „distinktivní
  symboly se přenášejí" (paměť [[png2point-inject-clean-base]]) potvrzena. KPI pseudo injekce odložena (Goodhart).
  **Scope +531 (Sez. 158):** 5-třídový model (531 Prominent man-made = ČERNÝ X, mirror 419 bez svatozáře —
  verify-against-source template id 156, `halo` flag v `inject.PointClass`). **Měřitelnost ověřena PŘED tréninkem**
  (anti-A1: probe crosswalk-aware 531 GT Velbloud 20 / Blatná 3 / Bedř 3). Synt mF1 medián 0,811 (5 tříd, 3 seedy);
  **reálný transfer 531 medián Velbloud F1 0,708 = na úrovni 419** → lekce „distinktivní X přenáší" platí i pro
  ČERNÝ man-made X (ne jen zelený veg). `peak_thr=0,60` (sweep, plochá část křivky, izomorf 417/419 Sez. 129);
  **4 staré třídy bez regrese** napříč seedy (bodový scope snese 5. třídu — na rozdíl od liniového 5-class Sez. 156).
  531 povýšen na `SCAN_LIVE_POINT` (capability registr). Blatná/Bedř 531 šum (3 GT). KPI netknuto (capability informativní).
  Stejný checkpoint kontrakt jako Area: běh je izolovaný v
  `resources/point_model/runs/<run_id>/` a kanonický `unet_best.pt` se mění jen
  explicitním `--promote`.
- **Png2Line reconstructor — TŘETÍ FUNKČNÍ MODEL (Sez. 130-132), `model/png2line/{tile,dataset,train}.py`:**
  třetí ze tří CV úloh (liniové ISOM → per-class segmentace). Architektura A (rozhodnuta Sez. 130):
  model = jen segmentace (dilatovaná GT proti rozpouštění tenkých linií), vektorizace = sdílený downstream
  „.omap assembly" (`model/vectorize.py` skeletonize→graf→RDP, Sez. 132). **Krok 1 watercourse 304/305
  (`N_LINE=2` tehdy): test mIoU 0,774 / IoU 0,55** (Sez. 131); reálný transfer PROKÁZÁN (completeness 0,85–0,93 =
  trasuje reálné toky, žádný kolaps jako 210), **strict IoU 0,409 / F1 0,773** po conf_thr prahu 0,95 (registr
  `LineClass.conf_thr`, izomorf `peak_thr`). **Krok 2 dashed 508+516 zkoušen a ZAVRŽEN měřením (Sez. 133):**
  doménový gap (completeness strop 0,14–0,22) + multi-class zhoršil watercourse. **Sez. 152 rozšířila label
  scope na 306/309/508*** bez návratu k 516. **Sez. 156 (audit A1) retrénoval `N_LINE=5` a ZMĚŘIL na realitě
  → watercourse REGREDOVAL** (real IoU 0,409→~0,26, F1 0,773→~0,67 na 3 mapách; **309 narrow_marsh úplný
  kolaps F1 0,00**, 306/508 slabé) → **REVERT na 2-class watercourse-only** (`krok1_watercourse_s0`,
  `.bak` pojistka). Druhé potvrzení Sez. 133: multi-class line (zvl. dashed 508) zhoršuje watercourse.
  Pozn.: `LINE_CLASSES`/`N_LINE` žije jen v `omap_raster`+`png2line/` (NE v `measure_dod`/`generate_map`)
  → KPI 65,8 % netknuto; revert `LINE_CLASSES` kódu na N_LINE=2 = KPI-bezpečný follow-up. Stejný
  checkpoint kontrakt (`--promote`). Poledníkový detektor `north_grid.py` (Sez. 132/134) filtruje falešné toky
  z modrých magnetických poledníků.
- **Checkpoint kontrakt živých modelů (CODE-C2, Sez. 127):**
  `model/checkpoints.py` je SSoT pro Png2Area i Png2Point. `best.pt`,
  `history.csv`, `curve.png` a `manifest.json` patří jednomu `run_id`;
  checkpoint nese seed, hyperparametry, epochu, selection/test metriku a SHA-256
  fingerprint splitu/datového manifestu. Checkpoint i promote používají dočasný
  soubor + atomický rename. Nedokončený nebo diagnostický overfit běh nelze
  povýšit.
- **KPI generátoru = primární kvantifikátor (Sez. 100+):** proporční podobnost distribuce ISOM symbolů gen vs
  reálné mapy (histogram intersection), nahradil binární DoD ≥ 90 % (nedosažitelný).
  **Stav Sez. 160: 66,2 %** (Sez. 152 bylo 65,8 na stale `.omap`; plná regenerace KPI sady
  s committed `separate.py` 407/409 gate `4a8712e` doložila 66,2 — vyřešen audit A3/A4 sirotek)
  na kanonické 3-map sadě Bedřichovka/Blatná/Velbloud
  (plocha 75,0 / linie 66,4 / bod 67,9; Bedř 58,5 / Blatná 65,6 / Velbloud 74,3);
  největší díry 403/416/409/306/202/109/501/308/108/208.
  Cíl plošná ~55 % (splněn), s reconstructory ≥ 85 %. KPI je kompas děr, nikoli cílová funkce; úspěch
  se ověřuje také na reálném domain-gap benchmarku. Měř `generator/measure_dod.py` (default KPI,
  `--table` kompas — sloupce `zdroj · gen · scan · provedení`; původ symbolů drží `isom.capabilities`).
  Detail TODO/DONE.

### UC3 — Restaurování map (APP)
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
