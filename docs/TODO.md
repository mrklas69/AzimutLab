# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi — ČÚZK (Sez. 2), Mapový portál ČSOS (Sez. 8, gate zavřená); lokální mapy `resources/` (smíšený původ); další zdroje TBD
- [~] Doplnit `RESEARCH.md` — LIDAR→mapa metoda hotovo (Sez. 2); zbývá generativní (UC4-I), dewarping/inpainting (UC3)

## UC2 — Data konektory (enabler, průzkum)
- [~] **Doplnit CHYBĚJÍCÍ relevantní vrstvy ZABAGED** (Sez. 23, uživatel „stojíme o všechna data z geoportálu, ne jen vybraná"). **Katalog VŠECH 149 vrstev + stav každé: `docs/kb/zabaged-isom-catalog.md`** (SSoT). Hotové dávky (Sez. 24–56: vedení/lanovka/železnice/kolejiště/skály/mosty/průseky/land-cover/RÚIAN/areály/landmarky/mokřady/stromořadí/kultura/komín/zábrana/kamenolom) jsou v DONE + katalogu. **„KATALOG VYČERPÁN Sez. 52" KOREKCE Sez. 55:** ○ kandidáti lanovka/lom/brod/podjezd/hráz nebyli změřeni jako Sez. 43 → probe ukázal nenulový výskyt; lanovka/vlek→510 HOTOVO Sez. 55, kamenolom→520 HOTOVO Sez. 56. **Zbývají ZMĚŘENÉ ◐/○:** podjezd 519 (Σ12, LS 11, verify spec), brod 519 (Σ6), hráz 528 (Σ13, blokátor legenda), vodopád 313 (Σ2), suť 210 (Σ1). **HOTOVO Sez. 57: balvany-linie → 208 Boulder field** (buffer pás, mirror 406). **Plot 516–518 = doložený SKIP Sez. 57** (ZABAGED plot nevede). Detail + čísla v katalogu „Akční seznam".
- [ ] *(idea Sez. 24, fáze 2)* **Vegetace jako pseudorealistická vrstva** — `pseudorealistic=True` (fáze 2) je dnes jen příčky vedení; hlavní budoucí konzument = vegetace (zelená/žlutá průchodnost, v datech není kvůli vegetace gate). To už je **predikce** (UC5, blokováno korpusem+licencí), ne jen dekorace. Až bude UC5 model. Spec §0b, GLOSSARY „pseudorealistic".
- [ ] LiDAR pipeline LAZ → DMR → vrstevnice (zbylá point-cloud větev; za MVP-deštník, až bude konzument). Pozn.: výškopis `dmr.py` (DMR 5G, ImageServer) i cesty `zabaged.py` (ZABAGED ArcGIS REST) už jako konektory žijí v `connectors/` — tohle je plné mračno bodů (naráží na vegetace gate, viz `data-sources.md`). **Sez. 59: stažení DMP 1G mračna automatizováno** (klad SM5 REST + ATOM `openzu.cuzk.cz` + `laspy[lazrs]`) — cesta ověřena, i kdyby jen pro CHM/vrstevnice.
## UC4-I / UC5 — Syntetický generátor (enabler-feeder, fáze B → první kód)
Spec: `docs/kb/generator-procedural.md` · kód: `generator/`
- [~] Procedurální generátor OB map — **přestavba „znovu a lépe" (Sez. 11):** vrstvy stavíme po jedné s důrazem na vizuální věrnost. HOTOVO: vrstevnice (§4.5) + bodové symboly extrémů **109/110/111** (§4.10, ISOM 2017-2 Rev 6 — Sez. 13 oprava ze zastaralých 112/113/115) + **terénní cesty (§9, Dijkstra least-cost, ISOM 503/505, `mask_paths.png`)** + vektor 101/102 + **`.omap` template-based** (Sez. 14 — věrná geometrie bodů 110 elipsa / 111 oblouk + plná ISOM knihovna z `template_classic.omap`) + reálný terén `--terrain real` + **reálné cesty `--paths real`** (Sez. 16 — ZABAGED REST, ISOM 502-506) + **reálná voda `--water real`** (Sez. 17 — ZABAGED toky 304/305/306 + plochy 301 vč. `Pozemní_nádrž`/koupaliště Sez. 27, `mask_water.png`) + **reálné budovy `--buildings real`** (Sez. 18 — ZABAGED `Budova_..._plocha_` → ISOM 521, `mask_buildings.png`; **RAW půdorys od Sez. 27** — generalizace i displacement smazány, kresleno jako voda) + **el. vedení + lanovka/vlek `--powerlines real`** (Sez. 24 + 55, ISOM 510 „Power line, cableway or skilift") + **řopíky `--ropiky real`** (Sez. 27, asset, orientace k hranici) + **logging** (Sez. 27, INFO průběh+souhrn) + **železnice `--railways real`** (Sez. 28+31, `Železniční_trať`+`_vlečka`+`Tramvajová dráha` → ISOM 509, kombinovaný symbol; oprava float bugu v `_draw_dashed`; tramvaj doplněna Sez. 31 — Sez. 28 ji vynechala jako „urbánní", chyběla točna LS) + **kolejiště `--paved real`** (Sez. 28, `Kolejiště` → ISOM 501 Paved area, kombinovaný s obrysem) + **pomocné vrstevnice `--terrain real`** (Sez. 29, ISOM 103 form lines — heuristika z DMR: mírný svah AND zakřivený terén, sklon+Laplacián; min. délka 3 mm bez „fousků"; `mask_formlines.png`; NL 108) + **skály/balvany `--rocks real`** (Sez. 30, ZABAGED `Osamělý_balvan`→204 / `Skupina_balvanů__bod_`→207 / `Skalní_útvary`→206; KISS vrstva→jeden symbol, hybridní 202/206 podle plochy i Chaikin smoothing zavrženy „bez datového podkladu"; `mask_rocks.png` 3-class; Hrubá Skála 585). **Sez. 31 také:** rozšíření `DEV_LOCATIONS` na per-lokalita rozměr (5-tuple) → 5. lokalita NV `Novina` PORTRAIT 3×5 km (testuje různé formáty výseků); HS `Hrubá Skála` z landscape 6×4 na **SQUARE 5×5 km** centrovaný na midpoint Kacanovy↔Doubravice. **mosty/tunely/lávky `--bridges real` → 512/512.2** (Sez. 31-33; finální Sez. 33: most = 2 paralely 512 + buffer crop pod mostem, tunel = 512 otočené 90° na vjezdech + passage crop trati projekcí, lávka = 512.2; `mask_bridges.png`) + **`--location` → výstup do složky lokality** (Sez. 33, název = SSoT sdílený se `stats.py`) + **lesní průseky `--rides real`** (Sez. 36, `Lesní průsek` id 16 → ISOM 508 Narrow ride, černá čárkovaná dash 3,0/0,375 mm, KISS vždy 508, bez runnability pozadí = vegetace UC5; `mask_rides.png`; SV 46/NL 119/LS 20/HS 16/NV 44) + **plošný pokryv `--surfaces real`** (Sez. 41, open land louka/park/pole/sad → ISOM 401 žlutá KISS + hřbitov → 520 olivová; parkoviště → 501; z-order vespod; `mask_surfaces.png` multi-class; SV 269/NL 34/LS 1105/HS 365/NV 103) + **udržovaná zeleň → 402/402.1** (Sez. 53, štěpení `typ_pudy_k`: park/okrasná zahrada `PO` → 402 žlutá+bílé tečky, ostatní zeleň `UZ` → 402.1 žlutá+zelené tečky; `SURFACE_DOT` per-symbol rozestup; tříds 4/5; 402.1 = první scattered-bushes zeleň z dat, gate neporušuje) + **bodové vodní/terénní + mokřady `--landmarks`/`--marsh` (Sez. 44, dávka 4):** pramen→312 (modré „U" ústím nahoru), jeskyně/šachta→203.2 (černá „Λ" stříška hrot nahoru), nádrž→311 (modrý čtverec) do `--landmarks`; bažina+rašeliniště→308 Marsh (modrá vodorovná šrafa) jako nový `--marsh`. **+ AUDIT VĚRNOSTI RENDERU (Sez. 44):** opraveno 203.2 cave (Λ ne plný trojúhelník) + 312 spring (∪ ústí nahoru) + 104 sráz (hnědá ne černá); root cause = špatná konvence omap osy y (+y=DOLŮ, NEflipovat) → paměť `omap-symbol-y-axis-down`; 111/207 byly správně (falešný poplach stažen). **+ komín → 524 High tower** (Sez. 52, `--landmarks`, mirror věží) **+ zábrana → 519 Crossing point** (Sez. 52, nový `--barriers`: bod na zdi 513 → branka, orientace = tangenta zdi, zeď se pod brankou přeruší; jen 2/66 na LS = řídká vrstva, závory na cestách zahozeny). ZAHOZENO: vegetace/paseky/bažiny/balvany (uměle); **L1 generalizace + L2 displacement budov (Sez. 27 — komolily tvar/polohu)**.
- [ ] *(nález Sez. 26)* **Q duplicita budovy** — uživatel označil markerem 704 místo s podezřením na dvojitou budovu; můj paper→S-JTSK přepočet polohy markeru byl nepřesný (ZABAGED dotaz mířil vedle) → nedořešeno, NEhádáno. Dořešit s přesným přepočtem. (Pozn.: počet budov 1078 REST + 70 řopíků sedí → generátor neduplikuje. Od Sez. 27 budovy RAW = věrný footprint, žádné umělé obdélníky.)
- [ ] *(odloženo Sez. 23)* NoData masking u hranic: DMR vrací 0 m mimo území ČR → artefaktová změť vrstevnic (Soví vrch 5×4 km zasáhl hranici). Nekreslit vrstevnice tam, kde elev = NoData → robustní výseky u hranic. Dnes obejito posunem středu (0,44 km).
- [ ] *(odloženo, noise-půlka)* Hydrologické jádro z flow accumulation (D8, §9): toky (§4.8) → prameny (§4.10) → jezera/rybníky (sink-fill deprese) → bažiny. **Sez. 17: voda realizována reálně (ZABAGED), D8 = procedurální protějšek do budoucna (nemíchat osy).**
- [ ] *(drobnost, vylepšení form line Sez. 29)* **souvislé smyčky** — form line jsou teď krátké úseky/obloučky (per-pixel maska). ISOM-věrnější by byly souvislé smyčky kolem lokálních kopečků/depresí (jiný přístup než maska). MVP uzavřen (uživatel), tohle až kdyby vadilo. Prahy `FORMLINE_*` jsou laděné na NL — ověřit i na SV/LS.
- [ ] *(odložená marginálie, nález Sez. 30; `Skupina_balvanů__linie_` → 208 HOTOVO Sez. 57)* **`Sesuv_půdy__suť` → 210 Stony ground** — Σ1, verify až v lokalitě se sutěmi (Jeseníky / Krkonoše Sněžka); na Hrubé Skále 3/0 prvků. Když bude, doplnit `STONY_GROUND_LAYERS` v zabaged.py.
- [~] *(verify nástroj, Sez. 37; ROZŠÍŘENO Sez. 58)* **`compare_real_vs_gen.py` — multi-mapa hotová.** Sez. 58:
  parametrizován názvem (`_map_paths`, STAT 1 podmíněn na kalibr. „Soví vrch", STAT 2 univerzální), **matched výsek**
  (gen na S-JTSK obal reálné mapy z `.pgw`). **Sbírka 6 reál. map** (`resources/`, gitignored): 5 ČR (SampleMap=USA
  vyřazena). **Změřeno na 3 cizích mapách** (Bedř/Blatná/Velbl): fáze I ~60 % precision tvrdé geometrie, vegetace
  ~30 % = gate. **ZBÝVÁ:** (a) **Soví vrch** — domapováno jen ~1/4 (čeká na dokončení → pak STAT 1 crosswalk + terénní GT);
  (b) **Slovanka UTM33** — jiný georef transformer než Křovák; (c) **vektor-na-vektor rozpad** recall po sémantických
  skupinách (per-vrstva masky gen + rasterizace real `.omap`) — rozbít „black" na cesty/stavby/skály, „shoda symbolu" ne
  jen barvy; (d) STAT 2 je barevná, tol 4 m = placement, ne přesná poloha.
  **(Stale DROP Sez. 69** — viselo 9× jako vedlejší carry; zůstává jako nález, přestane se navrhovat v Příště.)
- [ ] *(feature, nápad uživatele Sez. 37)* **Grivace v generátoru `--grivation`** — gen je grid-north-up, reálné OB
  mapy magnetic-north-up. Dvě polohy: `.omap` declination/grivation metadata (izomorfní s kartografem) / rotace rastru
  (až rastrový konzument). Kotva v `meta.georef`. Detail IDEAS „Grivace v generátoru".
- [x] *(UC5 korpus — HOTOVO Sez. 70-71, detail v DONE)* **Livelox korpus 268 reálných OB map** (`livelox.py`
  `search_events`/`download_corpus`, `allEvents`→`SearchEvents` reverz, WGS84 fallback, backoff) **+ kurace
  → 216 keep classic** (`curate.py` taxonomie discipline+tagy, `_curation.json`) + olivová 520 → label 0 (čistota GT).
  Tréninkové jádro = 216 foot-O map. Legalizace (ČSOS) až pokud model funguje — do té doby privátní repo + TDM výjimka.
### UC5 runnability model — kroky (Sez. 74 %THINK; architektura v IDEAS „UC5 runnability model")
Rozhodnuto: vstup **jen ortofoto RGB**, **5 tříd** (eval zelená), **smoke test první**. Trénink jen na
`mrkla` (RTX 5070, BF16) — `docs/kb/hardware.md`. Gaty PŘED model (pár (X,Y) = foundation).

> **⟲ REFRAME Sez. 79 — směrový obrat.** Model `ORTO → 4 barvy` (kroky 0-4 níže) dal val mIoU strop ~0,25
> (Sez. 78) → **archivováno** (NE smazáno; doložená slepá ulička „z ortofota shora podrost nevidět"). Cíl
> „rozumí mapám" = **`reconstructor()`** (sken → `.omap`, dříve „mapper"), ne ortofoto→runnability. Feeder =
> **`generator()`** s **predict částí** (vegetace/paseky/hustníky procedurálně, aby render vypadal reálně —
> NE věrná predikce z dat; pravdivost vůči lokalitě nepodstatná, pár [render, `.omap`] musí být konzistentní).
> **Foundations: nejdřív dotáhnout `generator()` predict část, pak `reconstructor()`.** Pojmy: GLOSSARY
> `generator()`/`reconstructor()`. Korpus / páry (X,Y) / GT pipeline (kroky 1-3) **ZŮSTÁVAJÍ** užitečné.
> Plná revize architektury (UC3 / UC4-III / UC5 / fázový plán / Pic2Omap absorpce) = **A1 odložena**.
- [~] **(HLAVNÍ TAH) `generator()` fáze I — prediktivní plochy ze separace Livelox mapy.** %THINK Sez. 80 (IDEAS
  „Tři fáze I/II/III"). **A1 measure-first VYŘEŠENO Sez. 82** (DONE): zdroj predikční vegetace = **separace z mapy**,
  ne [[forest-age-proxy]] (ten ARCHIVOVÁN — 33 % pokrytí, IoU 0,12, přestřel 3,3×). **PoC krok 1 HOTOVO Sez. 82**
  (`generator/separate.py`, zobecněno Sez. 83 `separate_veg`→`separate_areas`/`AREA_CLASSES`): separace zelené
  406/408/410 → vektorizace (contourpy reuse `rock_relief`) → `.omap`, věrné ~90 %. **OOM verify HOTOVO Sez. 83**
  (izolovaná + integrovaná). **Integrace HOTOVO Sez. 83** (DONE): `generate_map` +kwarg `predict_areas_sjtsk`
  (přednost před archiv forest-age, provenance `predict`) + orchestrátor `generator/pairs.py build_pair(cid)`
  (per-classId, Livelox grid, Gate A ~1 px) + `_fill_ignore` (přetisk tratě 704/705 → nejbližší label). **ZBÝVÁ:**
  - [~] **Škálovat páry** přes korpus → set pro trénink `Png2Area`. **Sez. 84: batch `build_pairs` HOTOV**
    (resume/tolerantní/souhrn, zdroj = 207 ČR ze `_split.json` → vyřadí 9 cizích keep + outlier `1109655`;
    `ortho=False`; `max_km=5` crop + ořez gt; bbox prefilter v `rock_relief._group_holes`). **ALE hromadný běh
    BLOKOVÁN výkonem** — generátor nestavěný na různorodé lokality. Dva žrouti: (#1) separace O(n²) `_group_holes`
    + KLÍČ Branžež mpp=0.56 → 93 Mpx, ořez na crop-bbox nezabral (rotace+rozlišení) → miliony zelených px;
    (#2) render skal (Český ráj, nepotvrzeno). Zásada: separace = GT-feeder, NEleštit práh; kvalitu dotáhne model.
  - [~] **(HLAVNÍ TAH, překlopen Sez. 85) Výkon párů — TŘI PÁKY místo rozbíjení monolitu.** %THINK Sez. 85
    oponoval „redesign na dlaždice 512×512 + rozbití monolitu `generate_map`" (velký refaktor `_apply_extent`
    globálů proti fázi B). **Měřeno (measure-first):** (#1 separace O(n²)) páka A **downscale gt na ~1,33 mpp
    PŘED separací = 31,6× zrychlení @ 5,6× méně px**, věrnost OK (stand-in Soví vrch); (#2 render skal)
    **SUB-lineární → Sez. 84 hypotéza VYVRÁCENA**, `max_km` ho udrží. → tři páky: **(A) downscale HOTOVO Sez. 85**
    (`separate.TARGET_MPP` + `separate_areas(src_mpp)` + `pairs` předá `effectiveMppX`; polygony ×f zpět na grid,
    behavior-preserving, ověřeno Soví vrch 16,5×), **(B) `max_km` strop** hotovo Sez. 84, **(C) finální nářez =
    reuse `model/tile.py`** (existuje @1,33/512/stride256). **ZBÝVÁ (mrkla):** Branžež `build_pair` verify —
    absolutní práh (8 min → ?) + `_map_affine` na rotovaném quadu → pak odblokovat **noční batch `build_pairs`**
    přes 207 ČR. Vedlejší: `map_gt.segment_gt` nezvládne >~100 Mpx (20 GiB; korpusové mapy malé → neakutní).
  - [x] **(verify dluh Sez. 84) Ověřit proc baseline 65 — HOTOVO Sez. 85** (`.omap objektů 65`; `_group_holes`
    bbox prefilter behavior-preserving, regrese 0).
- [ ] *(enabler fáze II, rozhodnuto Sez. 82 — IDEAS „omap2png")* **omap2png** — render `.omap`→PNG pro export páru.
  OOM nemá CLI/headless. **Volba: náš rastr teď** (`generate_map` už `rgb.png` dělá), C++ headless OOM až měřený
  doménový gap dokáže potřebu. Až bude integrace fáze I + degradér fáze II.
- [ ] *(navazuje na hlavní tah, Sez. 80; přejmenováno Sez. 82)* **Tři pomocné modely `reconstructor()` — `Png2Area` /
  `Png2Point` / `Png2Line`** (OOM Point/Line/Area, `type=1/2/4`). Dekompozice podle typu geometrie ISOM (tři CV
  úlohy). GT zdarma z `.omap` (typ symbolu). Pořadí: Area první (reuse U-Net Sez. 78, vstup mapa ne ortofoto),
  Point druhý (generátor má přesné polohy bodů = „bodová větev" posed/pramen/vývrat, ISOM kódy ověřit ze spec),
  Line poslední (nejtěžší, segmentace+skeletonizace). Detail IDEAS. Až fáze I/II dají páry.
- [x] **Kroky 0-4 HOTOVO (Sez. 74-78, detail v DONE) — celá datová+model pipeline.** Krok 0 smoke test
  (`torch cu128` na Blackwell) · krok 1 GATE 1 zarovnané páry `build_georef_pair` + georef QC (medián 1,33 m,
  prošel) · krok 2 ČR/DE filtr (207 ČR/9 cizí) + class distribution + median-freq váhy · krok 3 geosplit
  `split.py` (145/31/31, bez leaku) + 207 párů · krok 4 baseline `model/dataset.py`+`train.py` (U-Net/ResNet34,
  BF16): **val mIoU 0,259 / test 0,223**, křivka = **generalizační strop** (RGB-only málo, runnability = podrost
  shora nevidět). Trénink jen `mrkla` (RTX 5070).
- [×ARCHIV] **Krok 5 (zlepšení baseline) → ARCHIVOVÁNO Sez. 79.** Směr `ortofoto→runnability` je doložená slepá
  ulička (reframe výše) → nahrazeno `generator()` predict částí. Původní nápady (diagnostika / ablace bohatšího
  vstupu DMR-sklon/forest-age / recency korpus) zůstávají jako možný *budoucí* vstup, kdyby se k ortofoto vstupu
  vrátilo — dnes mimo hlavní směr.
- [ ] *(integrace, deferred Sez. 76)* **ČR/DE filtr do `kept_dirs`** — dnes `_cz_filter.json` je jen měřicí
  artefakt (nemění `keep`). Tréninkový loader jede přes `split.dirs_for()` (už ČR-only), takže neakutní;
  doladit, až loader vznikne (krok 4) — buď číst split, nebo přidat filtr do `curate.keep`.

- [ ] *(kurace follow-up Sez. 71, před tréninkem)* **recency osa** — `meta.json` neukládá datum eventu → časový
  nesoulad vstup(ortofoto recent)×GT(starý) NELZE měřit. Uložit datum eventu do `meta.json` při `download_map`
  (z `event["timeInterval"]["start"]`) + volitelně doplnit re-dotazem na existující 268. Pak řez „posledních N let".
- [x] *(GT kvalita, strukturální — HOTOVO Sez. 72-73, detail v DONE)* **přetisk + layout crop → label 255 ignore.**
  Část A: fialový přetisk tratě → ignore (`map_gt.py`, 2 purpurové odstíny + dilatace, 31 % keep map; OOB šrafa
  709 taky). Část B: layout mimo mapu → ignore přes **barevný** detektor `_detect_map_area` (mapa = sytá ISOM
  paleta, okraj = černobílé/papír; konzervativní, bez false-cropu terénu). Known limitation → follow-up níže.
- [ ] *(GT kvalita follow-up, known limitation Sez. 73)* **detektor mřížky control-description tabulek** —
  layout-ignore Sez. 73 (barevnost) tabulku s barevnými ISOM symboly blízko mapy nezachytí. Cílený detektor na
  PRAVIDELNOU MŘÍŽKU černých čar (projekční profil / periodicita černých pixelů v pravoúhlém bloku) by ji vyřízl
  nezávisle na barevnosti symbolů uvnitř. Před implementací změřit rozsah (kolik keep map nese nezachycenou
  tabulku, jakou plochu kontaminuje) — viz volba Sez. 73 (přijato částečné B, tabulka odložena).
- [ ] *(rozšíření korpusu Sez. 70, volitelné — až bude UC5 model konzumovat)* víc map/event u etapových závodů (dnes
  1/event = ztráta vedlejších map), nebo dedup map podle georef overlap. Zatím 216 keep stačí.
- [ ] *(DRY dluh, nález Sez. 68; ROZEŠLO SE Sez. 71)* **`ISOM_REF`** — `generator/compare_real_vs_gen.py` (SSoT, Sez. 64)
  vs KOPIE v `connectors/map_gt.py`, která teď navíc nese OLIVOVOU (runnability-specifická, compare ji nemá). Už ne
  čistý duplikát → extrakce do sdíleného modulu až 3. konzument (princip „generalizuj jen s důkazem").
- [~] *(architektura, nález A1 %AUDIT:CODE Sez. 35; jádro vyřešeno Sez. 50)* **`generator.py` monolit
  (3388 ř.)** — `_build_meta` smell + duplikace meta-konstrukce vyřešena Sez. 50: `_layer_meta_section`
  helper + tabulkový `real_sections` registr → `_build_meta` 26→18 param, smazána asymetrie „část vrstev
  uvnitř / část injektovaná vně" (izomorfismus); zabaged.py `fetch_*` sjednoceno (`_collect_features`/
  `_collect_points`, −157 ř). **ZBÝVÁ (podmíněně, „až bolí"):** fyzický split souboru na moduly
  (`draw_helpers.py`/`real_layers.py`/`bridges.py`) — vědomě NEproveden Sez. 50: kreslicí helpery závisí na
  module-level globálech `GW/GH/W/H` (mutované `_apply_extent`), jejich přesun = přepsat globály na předávaný
  stav = velký refaktor proti fázi B (sys.path skripty, ne balík; KISS). Sledovat jako podmínku, nepsat do
  „Příště", dokud bolest nenastane (Stale check ≥5 sez, Sez. 40). Spouštěč splitu = přechod na balík (fáze A).
- [ ] *(drobnost, doladění mostů/tunelů Sez. 33)* laděné konstanty `BRIDGE_CROP_HALFWIDTH_MM` (1,25), `BRIDGE_CARRIED_PARALLEL_DEG` (25°), `TUNNEL_PORTAL_HALF_UM` (750), passage `near_mm` (2,0) — ověřit i na LS silničním tunelu a hustší síti; případně tunelu cropovat i vodu (dnes jen železnice/cesty).
- [ ] *(drobnost, nález Sez. 31)* **Podjezd ZABAGED** — `Podjezd (bod)` id=64 + `Podjezd (linie)` id=77; tematická skupina s Most/Tunel. Mapování → 519 Underpass? Verify-against-source spec před implementací (paměť `isom-spec-before-render`).
- [ ] *(drobnost, nález Sez. 31)* **tramvaj LS verify v OOM** — 25 nových liniových objektů 509 (Tramvajová dráha včetně točny Lidové sady, LS celkem 40 železničních linií). Vykreslí OOM kombinovaný symbol 509 (čárky + bílý knockout) korektně i přes městskou síť?
- [ ] *(rozšíření cest/vody)* věrná dvojitá linie 502 Wide road (teď PoC casing), ladění 505/506, ořez reálných linií na bbox; (voda) „hranatý" malý rybník, věrný kombinovaný 301 s břehovou linií v OMAP (teď 301.1).
- [ ] *(drobnost, nález %AUDIT:CODE Sez. 19 — P2)* OMAP export 110 Small elongated knoll: rastr respektuje orientaci `horiz`, ale `.omap` exportuje vždy `rotation="0"`. Předat orientaci protáhlosti do exportu (rastr↔omap konzistence).
- [ ] *(anotace, až bude vstup)* čtečka čísel kontrol **ISOM 704** ze separátního anotačního `.omap` (kanál uživatel → AI: označí místo v OOM, generátor nepřepíše; já přečtu polohu/číslo). Workflow rozhodnut Sez. 18.
- [ ] Stupeň 2 — augmentační pipeline (§8.3): degradace render → „sken" (CMYK misregistration, papír, JPEG, deformace) pro UC4-III. Až stupeň 1 stojí.

## Rozhodnutí (k dozrání → IDEAS.md / architecture.md)
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo) — pozn.: generátor je první kód mimo Pic2Omap, kandidát na úvahu. **Sez. 16: `connectors/` = první sdílená kódová složka mimo sandbox (drobný krok B→A); spouštěč „balík" stále otevřen — až 2. konzument konektorů. Sez. 39: generátor opustil sandbox (`generator/`), sandbox zrušen — krok B→A, ale pořád sys.path skripty, ne balík.**
- [ ] První aplikační kandidát: UC3 de-purple vs jiný — pozn.: UC5 má teď datovou cestu (C) syntetika → váhy se posunuly k UC5

## Backlog (vzdálené, nezačínat)
- [ ] UC5 jádro (palette separation jako první střípek)
- [ ] UC3 / UC4 aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
