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
- [x] *(UC5 korpus, IDEAS „UC5 runnability korpus")* **Livelox korpus reálných OB map — ŠKÁLOVÁNO Sez. 70 (268 map).**
  Probe gate 1+2 Sez. 68 + batch Sez. 70: `allEvents` reverzováno → `POST /Home/SearchEvents` (GeoBox, `timePeriod`,
  classId v `classes[].id`); `search_events`/`download_corpus` v `livelox.py` (1 class/event, idempotent, od nejnovějších);
  geo S.Čechy CZ + Žitavsko DE (SAXBO). **268 map** (31 % z 865 eventů, zbytek doloženě mrtvý — Livelox staré mapy nemá).
  **WGS84 fallback** (typ B +43) + **backoff retry**. **ORIS zavržen daty** (96 % starých bez rastru → nepomůže). DONE.
  **Legalizace (oslovit ČSOS) až pokud model funguje** — do té doby privátní repo + TDM výjimka.
- [x] *(HOTOVO Sez. 71)* **olivová 520 → label 0 (čistota GT) + kurace korpusu** (`connectors/curate.py` merge-aware +
  `_curation.json`, taxonomie discipline+tagy, **268 → 216 keep classic**). Detail v DONE. Tréninkové jádro = 216
  foot-O map s čistou olivovou GT.
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
- [ ] **(HLAVNÍ TAH, upřesněno Sez. 80) `generator()` fáze I — prediktivní plochy ze separace HD Livelox PNG.**
  %THINK hotový (Sez. 80, IDEAS „Tři fáze I/II/III"). Tok: I. generator() = reálná část (ČÚZK) + prediktivní
  plochy (separace barev z NEdegradované Livelox PNG → vektorizace contourpy → `.omap` s flagem real/predict);
  II. dataset = export PNG + degradace (overprint/odřeniny/bláto); III. reconstructor() = trénink. **Pravé veřejné
  `.omap` vektory NEEXISTUJÍ** (průzkum Sez. 80) → `.omap` tvoří generátor. **PoC (čeká na souhlas Q1/Q2):** na
  1 Livelox mapě separace celé plošné palety → vektorizace → vlož do generované `.omap` s flagem → vizuál v OOM.
  Před tím rozhodnout dělbu ploch real/predict + **measure-first: vegetace z [[forest-age-proxy]] vs mapař (Livelox
  separace)?** Spec §0b „predict", GLOSSARY (rozšířit o `Png2Polygon`/`Png2Linie`/`Png2Point`).
- [ ] *(navazuje na hlavní tah, Sez. 80)* **Tři pomocné modely `reconstructor()` — `Png2Polygon` / `Png2Point` /
  `Png2Linie`.** Dekompozice podle typu geometrie ISOM (area/line/point = tři CV úlohy). GT zdarma z `.omap`
  (typ symbolu). Pořadí: Polygon první (reuse U-Net Sez. 78, vstup mapa ne ortofoto), Point druhý (generátor má
  přesné polohy bodů = „bodová větev" posed/pramen/vývrat, ISOM kódy ověřit ze spec), Linie poslední (nejtěžší,
  segmentace+skeletonizace). Detail IDEAS „Tři fáze I/II/III + tři pomocné modely". Až fáze I/II dají páry.
- [x] **Krok 0 HOTOVO (Sez. 74) — smoke test PyTorch+CUDA na Blackwell.** `torch 2.11.0+cu128`
  (cp314 wheel) + `torchvision` + `smp 0.5.0`; ověřeno empiricky `temp/smoke_test_gpu.py`: sm_120
  v `arch_list`, matmul fp32+bf16 + U-Net forward (1,3,512,512)→(1,5,512,512) reálně na GPU, 11,4 GB
  volné VRAM. Past „no kernel image" zažehnána. `requirements.txt` doplněn (cu128 index, ne PyPI).
- [x] **Krok 1 HOTOVO (Sez. 75) — GATE 1 zarovnané páry + měření offsetu PROŠEL.** `build_georef_pair`
  (livelox.py) vyrobí `ortho.png` (X) + `gt_grid.png` (Y, GT warpnutá do téhož S-JTSK gridu, nearest,
  fill IGNORE) + verify (`gt_grid_vis.png`, `blend.png`); X i Y přes identickou afinní transformaci =
  pixel-na-pixel. `measure_georef_offset` = phase correlation hran, hledá peak JEN v okně ±40 m
  (artefakt periodicity: bez omezení dala 1047807 falešných 549 m). CLI `pair`/`gate1`. **Měření 25
  CZ S-JTSK map: medián 1,33 m (1 px)** → georef Liveloxu zdravý, GATE 1 prošel. **Nález:** per-mapa
  offset >~5 m je nedůvěryhodný (artefakt husté/rušivé korelace — 1106623 sedí vizuálně dokonale, přesto
  „17 m") → měření = **agregátní QC, ne per-mapa korektor**; vizuál (blend) je arbitr. Detail v DONE.
- [x] **Krok 2 HOTOVO (Sez. 76) — měření datasetu.** ČR/DE filtr (near-white ortofoto probe, práh 0,5):
  216 keep → **207 ČR / 9 cizí** (DE Žitavsko + PL, prázdné ČÚZK) → `_cz_filter.json`. Class distribution
  (% labeled): průchodný 69 / 406 11,4 / 408 5,9 / **410 fight 1,35** / open 12,2 → **váhy median-freq**
  (410 w≈8,4). 410 validováno proti 5 mapařským `.omap` (0,2-2,07 % → GT realistická, nepoddetekováno).
- [x] **Krok 3 HOTOVO (Sez. 76) — geografický split.** `connectors/split.py`: clustery dle překryvu
  S-JTSK bboxů (union-find, 29 clusterů) → greedy **70/15/15 = train 145 / val 31 / test 31** → `_split.json`.
  Bez leaku (celý cluster do 1 splitu), všechny splity reprezentativní (410 nenulová 1,3-1,9 %). Pak hromadná
  výroba **207 párů** (`build_pairs`, 0 fail, medián offset 2,97 m = artefakt ocas, vizuál OK).
- [x] **Krok 4 — baseline HOTOVO Sez. 78.** `model/dataset.py` (loader nad dlaždicemi, D4 aug + jas/kontrast
  za běhu, ImageNet norma, váhy z `_tiles.json`) + `model/train.py` (smp U-Net/ResNet34 ImageNet-pretrained,
  `CrossEntropyLoss(weight, ignore_index=255)`, BF16, per-class IoU přes GPU confusion matici, `--overfit`
  gate, checkpoint best, **křivka učení** `curve_full.png`+CSV po každé epoše). Overfit gate prošel. Plný
  trénink (40 ep, batch 16): **val mIoU 0,259 / test 0,223**; per-class test 410 fight 0,04. **Nález:
  generalizační strop** (train loss klesá, val mIoU plochá ~0,25 od ep1) → úlohový strop, RGB-only málo
  (runnability=podrost pod korunami). Detail v DONE. Trénink jen `mrkla` (RTX 5070, BF16).
- [×ARCHIV] **Krok 5 — zlepšení baseline (Sez. 78 nález) → ARCHIVOVÁNO Sez. 79** (ortofoto→runnability je
  slepá ulička, viz reframe výše; nahrazeno `generator()` predict částí). Původní zadání zachováno níže pro
  historii: (a) **diagnostika** pred vs GT na pár val dlaždicích
  (rozumné záměny sousedních runnability tříd vs strukturální selhání?); (b) pokud potvrzen RGB-strop →
  **MĚŘENÁ ablace bohatšího vstupu** — DMR sklon/CHM jako 4. kanál nebo forest-age (osa B IDEAS „raw default,
  generalizuj s důkazem" — teď je důkaz stropu); (c) případně **recency-filtrovaný korpus** (časový nesoulad
  input ortofoto × GT ze staré mapy, viz TODO „recency osa"). Hlavní podezřelý (volba uživatele Sez. 78):
  RGB-only nestačí na hustotu podrostu shora.
- [ ] *(integrace, deferred Sez. 76)* **ČR/DE filtr do `kept_dirs`** — dnes `_cz_filter.json` je jen měřicí
  artefakt (nemění `keep`). Tréninkový loader jede přes `split.dirs_for()` (už ČR-only), takže neakutní;
  doladit, až loader vznikne (krok 4) — buď číst split, nebo přidat filtr do `curate.keep`.

- [ ] *(kurace follow-up Sez. 71, před tréninkem)* **recency osa** — `meta.json` neukládá datum eventu → časový
  nesoulad vstup(ortofoto recent)×GT(starý) NELZE měřit. Uložit datum eventu do `meta.json` při `download_map`
  (z `event["timeInterval"]["start"]`) + volitelně doplnit re-dotazem na existující 268. Pak řez „posledních N let".
- [x] *(GT kvalita, strukturální — nález Sez. 71)* **legenda/okraj/přetisk crop** — strukturální GT krok místo
  per-mapa tagování legend (nespolehlivé v 240px náhledu). **Část A HOTOVO Sez. 72: fialový přetisk tratě → label
  255 ignore** (`map_gt.py`, 2 purpurové odstíny z dat, maska dilatovaná po median; 31 % keep map; OOB šrafa 709
  taky ignore). **Část B HOTOVO Sez. 73 (částečně): layout mimo mapové území → 255 ignore.** Hybridní detektor
  (`_detect_map_area`): NE geometrie (křehká — naivní největší-komponenta i XY-cut selhaly v probu), ale
  **barevnost** — mapa má sytou ISOM paletu, mimo-mapové bloky černobílé/papír. Dlaždice → barevné > 4 % →
  dilatace scelí řídké oblasti → největší komponenta + fill holes = mapa, zbytek ignore. Verify 12 map: titulky/
  tiráž/loga/papírový okraj zachyceny, mapa BEZ false-cropu (konzervativní asymetrie). **Known limitation:
  control-description tabulka s barevnými ISOM symboly blízko mapy proklouzne** (dilatace ji spojí s mapou,
  symboly = mapová barva) — viz nový TODO „detektor mřížky tabulek". Barevné titulky (žluté pozadí) taky občas
  proklouznou (volba „nechat konzervativně", Sez. 73).
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
