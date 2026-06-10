# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi — ČÚZK (Sez. 2), Mapový portál ČSOS (Sez. 8, gate zavřená); lokální mapy `resources/` (smíšený původ); další zdroje TBD
- [~] Doplnit `RESEARCH.md` — LIDAR→mapa metoda hotovo (Sez. 2); zbývá generativní (UC4-I), dewarping/inpainting (UC3)

## UC2 — Data konektory (enabler, průzkum)
- [~] **Doplnit CHYBĚJÍCÍ relevantní vrstvy ZABAGED** (Sez. 23, uživatel „stojíme o všechna data z geoportálu, ne jen vybraná"). **Katalog VŠECH 149 vrstev + stav každé: `docs/kb/zabaged-isom-catalog.md`** (SSoT). Hotové dávky (Sez. 24–56: vedení/lanovka/železnice/kolejiště/skály/mosty/průseky/land-cover/RÚIAN/areály/landmarky/mokřady/stromořadí/kultura/komín/zábrana/kamenolom) jsou v DONE + katalogu. **„KATALOG VYČERPÁN Sez. 52" KOREKCE Sez. 55:** ○ kandidáti lanovka/lom/brod/podjezd/hráz nebyli změřeni jako Sez. 43 → probe ukázal nenulový výskyt; lanovka/vlek→510 HOTOVO Sez. 55, kamenolom→520 HOTOVO Sez. 56. **Zbývají ZMĚŘENÉ ◐/○:** podjezd 519 (Σ12, LS 11, verify spec), brod 519 (Σ6), hráz 528 (Σ13, blokátor legenda), vodopád 313 (Σ2), suť 210 (Σ1). **HOTOVO Sez. 57: balvany-linie → 208 Boulder field** (buffer pás, mirror 406). **Plot 516–518 = doložený SKIP Sez. 57** (ZABAGED plot nevede). Detail + čísla v katalogu „Akční seznam".
- [~] *(idea Sez. 24, fáze 2; POVÝŠENO na aktivní směr Sez. 102)* **Vegetace jako pseudorealistická vrstva** — `pseudorealistic=True` (fáze 2). Hlavní konzument = vegetace (zelená/žlutá průchodnost, v datech není kvůli vegetace gate). **Sez. 102: forest_age proxy smazán → DEV `--location` mapy a syntetické páry bez Livelox skenu kreslí BÍLÝ LES.** Predikční vegetace dnes jde JEN ze separace reálné mapy (cesta párů) — lokality bez skenu zelený generátor nemají. Pseudorealistic = náhrada: **vymyslet věrohodnou zeleň procedurálně** (clustery v lese / perlin / hranice z terénu?). Reframe Sez. 79 ji posvětil („vegetace pro trénink nemusí být pravdivá — reconstructor ji čte ze skenu, generátor generuje procedurálně-věrohodně"). **Příště: %THINK jak generovat.** Spec §0b, GLOSSARY „pseudorealistic"/[[forest-age-proxy]].
- [ ] LiDAR pipeline LAZ → DMR → vrstevnice (zbylá point-cloud větev; za MVP-deštník, až bude konzument). Pozn.: výškopis `dmr.py` (DMR 5G, ImageServer) i cesty `zabaged.py` (ZABAGED ArcGIS REST) už jako konektory žijí v `connectors/` — tohle je plné mračno bodů (naráží na vegetace gate, viz `data-sources.md`). **Sez. 59: stažení DMP 1G mračna automatizováno** (klad SM5 REST + ATOM `openzu.cuzk.cz` + `laspy[lazrs]`) — cesta ověřena, i kdyby jen pro CHM/vrstevnice.
## UC4-I / UC5 — Syntetický generátor (enabler-feeder, fáze B → první kód)
Spec: `docs/kb/generator-procedural.md` · kód: `generator/`

> **[!] KPI generátoru — PRIMÁRNÍ KVANTIFIKÁTOR (Sez. 100, nahrazuje binární DoD ≥ 90 %):** „jak moc se
> blížíme generování **reálně vyhlížejících** O-map" = **proporční podobnost distribuce ISOM symbolů** gen vs
> vzorové mapy = **histogram intersection** `Σ min(orig_share, gen_share)`, per-mapa pak průměr. Jedno číslo
> 0–100 % („kolik % symbolové hmoty gen mapy se proporčně překrývá s reálnou"). Měř **`generator/measure_dod.py`**
> (DEFAULT režim bez flagu; `--table` kompas diagnostika / `--dod` archiv binární DoD + analytický cut / `--proxy`).
> Proč ne binární DoD ≥ 90 %: byl nedosažitelný (strop 54 %) a slepý k inkrementální práci (dissolve 520 9×→1,3×,
> marsh 310 ho nehnuly); KPI dává partial credit za přibližování proporcí + je robustní vůči **obal-artefaktu**
> (proporce ruší rozdíl plochy — gen grid-north obal > natočený výsek). Penalizuje chybějící typ (gen=0) i přestřel
> (`min` ukrojí přebytek). **CÍL: plošná fáze (jen ČÚZK data) ~55 %, s Png2Point + Png2Line ≥ 85 %** (61 % symbolové
> hmoty = linie + body → bez reconstructorů je strop ~50 %). **Stav Sez. 104: KPI 50,3 %** (= 49,8 % před ořezem +
> přesah-ořez +0,5 pb; Bedř+Blatná+Velbloud na HAL3000; plocha 69,2 / linie 59,3 / **bod 18,4** = Png2Point dluh,
> ZOSTŘEN ořezem z 29,0). Žebříček děr (kam mířit): **204** (7,8 pb) **/210** (7,3 pb, body → Png2Point) /403 (granularita, vyvr.)/
> **508** (vyvr. Sez. 102)/416 (hotovo)/**417/419** (body)/409 (gate). **Vrchol je téměř celý bodový/gate → další skok = reconstructory.**
> **Sez. 102 — 508 Narrow ride NENÍ páka** (jako 403): smíšený podstřel (Bedř délka 0,22× = POKRYTÍ ČÚZK řídké /
> Blatná počet 0,15× = GRANULARITA gen 4,7× delší kusy), KPI simulace i pokrytí STROP gen=orig jen **+0,34 pb**,
> granularita +0,59 = gaming (mění jen #objektů) → nepáka. **4. potvrzení vyčerpání ČÚZK plošné+liniové páky.**
> Co generátor nenakreslí, reconstructor se NIKDY nenaučí → pokrytí = strop tréninku (memory
> `generator-coverage-is-the-ceiling`). **Větší páka než ladit model = přiblížit distribuci symbolů realitě.**
> **Sez. 101 — 403 NENÍ páka (granularitní propast), 416 ANO (+3,2 pb).** 403 podstřel (673/152) měřením: NE slévání
> (gen 39 %/12 % plochy), systémově reálné mapy kreslí 403 jako dominantní open (Bedř 9× nad 401) ale ČÚZK vrací TTP
> **hrubě** (1 multipolygon 139,5 ha → ~46 gen obj vs kartograf 356 plošek) → simulace přesunu 401→403 = +0,1 pb
> (KPI počítá objekty, granularitu plošné mapování neopraví — strop i UVNITŘ ploch). Bedř scan-odstín 403 = artefakt
> Livelox-kalibrace (separace měří resources) → dokumentovat-neladit. **416 = silná páka** (633/0 největší díra):
> mezitřídní hranice predikčních veg ploch + délkový práh 50 m (reálné medián 45-90 m, mezi-veg samo přestřeluje
> 147/596 %) → KPI +3,2 pb. **Plošná páka z ČÚZK definitivně vyčerpaná** (potvrzeno 3× Sez. 99-101); další skok = reconstructory.
> **Stav Sez. 94 (POCTIVÝ baseline):** `compare_isom` opraven na **crosswalk-aware** — Sez. 91 „38 %" bylo
> NEPLATNÉ (naivní integer-prefix ignoroval `.crt`; reálné mapy ISOM 2000 vs gen 2017-2, číslování recykluje).
> Matched přes 3 mapy (A3: Slovanka UTM33 + Soví vrch 1/4 vynechány): Bedř **43 %** / Blatná **37 %** (jediná
> 2017) / Velbloud **50 %** → **PRŮMĚR 43 %**. **Gap je OBSAHOVÝ ne číslovací:** chybí TYPY — 416/107/108/507
> (linie → Png2Line), 418/419/525/527/531 (body → Png2Point), **404/407/409 (pattern plochy)**, 210 Stony
> (ZABAGED nevede), mikroformy 112/113/105. **Separace ze skenu = páka KVALITY ne pokrytí** (Sez. 94 cesta b:
> +403 −410 net-nula, `predict_areas_sjtsk` forest_age výlučně nahradí). Coverage páka = kreslit nové TYPY.
> **Q2 carry VYŘEŠEN Sez. 94** (tvrdý DoD na resources změřen 43 %).
> **Stav Sez. 95 — DoD ≥ 90 % je PLOŠNĚ NEDOSAŽITELNÉ + baseline přepnut na separaci.** Analytický cut
> (`compare_isom.symbol_geometry`, geometrie z OOM `<symbol type>`): **plošný strop 58 %** (kdyby gen dokreslil
> všech 13 chybějících typů ploch). Zbytek = **linie 18 typů/1952 obj → Png2Line** + **body 17 typů/966 obj →
> Png2Point** (oba modely NEEXISTUJÍ). Reálný strop < 58 % (pattern vegetace 404/407/409/113 ~590 obj = dvojitá
> mezera separace-slepá+gate). DoD baseline přepnut forest_age→**SEPARACE** (`measure_dod` výchozí = `_gen_sep`,
> produkční cesta párů; `--proxy` = doložení nadhodnocení): 403 covered, fiktivní 410 missing (souvislé 410 v
> mapách = ŠUM, forest_age fabrikoval). **Cesta k 90 % = Png2Line + Png2Point**, plošné nové typy jen do stropu.
> **Stav Sez. 96 — 210 je BODOVÝ gap (ne plošný) + variant-aware strop 54 % + kompas tabulka.** A1 measure-first
> nad 210: reálná geometrie v 5 mapách = **VŠE `type=point`** (210.0/210.1 „individual dot"; Slovanka 3473/Velbloud
> 603/…) → kartografové kreslí kamenitou zem POLEM TEČEK → **210 patří na Png2Point, NE plošný generátor**.
> Kořen: `symbol_geometry` bral geom z template-primary (210=area), reálná point varianta se ztratila → cut
> nadhodnocoval. Oprava `compare_isom.used_geometry` (geom z REÁLNÉ mapy) → cut variant-aware → **pravý plošný
> strop 54 %** (z 58); GAP plocha 9/894 · linie 19/1974 · **bod 21/2213**. Nový **`measure_dod.py --table`** =
> KOMPAS (orig vs gen Σ obj per ISOM kód, 3 kapitoly): Png2Point gen Σ149/orig 3960 nejhorší, gen přestřeluje
> 520/521/cesty, podstřeluje vegetaci, 416 veg boundary 1111/0. Strategie → IDEAS „Pokrytí do statistické míry
> četnosti" (generovat věrohodně do míry + Png2Point injekce symbolů + 416 do míry). Plošné nové typy se zdrojem
> jen 310/413 (ověřit jejich geometrii — 413 „single dot" → možná taky bod!), do ~54 % stropu.
> **Stav Sez. 98 — přestřel olivové 520 OPRAVEN + plot 516 přidán (rychlé výhry).** Measure-first
> (`temp/measure_520.py`): 520 = 91–96 % z RÚIAN privát drobných katastrálních parcel (LS 52 % výseku) →
> kompas 520 gen/orig **9× přestřel**. **Dissolve do bloků** přes contourpy masku (bez `shapely`; reuse
> `rock_relief`): LS 19762→2023, HS 2066→448, kompas 520 9×→**1,3×** (HOTOVO, DONE). **Plot 516 Fence**
> (pseudo fáze 2, ZABAGED nevede): práh 0,5 ha (gen 160→21≈orig 24) + RDP narovnání + ticky DOVNITŘ
> (ISOM „tags inside") — HOTOVO. Kompas potvrdil **521 budovy + cesty 503/504 přestřel je OBAL-ARTEFAKT**
> (gen grid-north obal vs natočený menší výsek) — NEŘEŠIT dissolvem (budovy se kreslí jednotlivě).
- [x] *(HOTOVO Sez. 104, detail DONE)* **Přesah-artefakt: ořez gen na mapovanou oblast při KPI/KOMPAS** —
  integrován do `measure_dod._counts_for_map` (`_clipped_gen_counts`: centroid gen objektu → S-JTSK → sken px →
  convex-hull maska skenu). Q1 verify: `parse_objects_with_centroid` = `isom_usage` byte-identicky → „před/po"
  měří jen ořez. **Oficiální KPI 49,8 → 50,3 % (+0,5), obousměrné** (Bedř/Velb + ořez přestřelu, Blatná − odhalí
  maskovaný podstřel). Bodový gap ZOSTŘEN sub 29,0 → 18,4 % → Png2Point jednoznačně další páka.
- [x] *(HOTOVO Sez. 104, detail DONE)* **Podklady do korpusového `gen.omap` — přepínatelný OOM background** —
  `generator/gen_backgrounds.py` (post-process) warpne sken/ortho/GT do gen px gridu → background templates
  (`count=0`→3); DRY extrakce `omap_export._image_template_element`/`inject_image_templates` (refaktor
  ortho_template behavior-preserving); GT-IGNORE magenta→bílá. Batch 205/205 OK (615 bg PNG). OOM verify ruční.
- [x] *(HOTOVO Sez. 99, detail DONE)* **310 Indistinct marsh** na `--marsh` — measure-first rozbil zadání: **313
  vodopád = mýtus** (bod Spring/0×, vyřazeno), **310 z ČÚZK neodvoditelný** (ZABAGED nerozlišuje zřetelnost) →
  **pseudo split náhodou ~55 %** (`_marsh_indistinct`, jen pseudorealistic; N_AREA 17→18). **POZOR: KOMPAS přínos ~0**
  (ZABAGED mokřady na DoD mapách řídké — Bedř gen 0/Blatná 1); hodnota jen v Livelox párech. Lekce → bod níž.
- [x] *(coverage — ZMĚŘENO Sez. 100, lekce Sez. 99)* **vybrat plošný typ, co kompas REÁLNĚ zvedne** → MĚŘENÍ: plošné
  gen=0 díry jsou **404/407/409** (Undergrowth + Rough open w/ scattered trees = vegetace gate, ZABAGED NEVEDE — stejná
  past jako 310) + 515 (neznámé). **Závěr: plošná coverage páka z ČÚZK je téměř vyčerpaná** (kvantifikováno KPI: sub
  plocha 60,9 % vs bod 29,0 %; 61 % hmoty = linie+body). Další skok = Png2Point/Line, ne nové plošné typy.
- [x] *(VYVRÁCENO Sez. 101 — granularitní propast, detail DONE)* **403 podstřel NENÍ páka** (+0,1 pb). Measure-first:
  ne slévání (gen 39 %/12 % plochy), systémově reálné mapy kreslí 403 jako dominantní open (Bedř 9× nad 401) ALE ČÚZK
  vrací TTP hrubě (1 multipolygon → ~46 gen obj vs kartograf 356 plošek) → KPI počítá objekty, přemapování 401→403 = +0,1.
  Bedř scan-odstín = artefakt Livelox-kalibrace → dokumentovat-neladit. Generátor netknutý (ušetřen refaktor).
- [x] *(HOTOVO Sez. 101 — +3,2 pb, detail DONE)* **416 Distinct vegetation boundary** (orig 633 / gen 0 → gen 154) —
  měřením potvrzená SILNÁ páka. **Mezitřídní hranice** predikčních veg ploch (403↔406↔408↔410, volba uživatele) +
  **délkový práh 50 m** (mezi-veg samo přestřeluje 147/596 %, reálné medián 45-90 m). `_predict_veg_boundaries` +
  `_draw_boundary` (černá tečkovaná, izomorf 508) + linefeature (0 změna omap_export). LINIE → bez Y dluhu. KPI 46,1→49,3.
- [x] *(VYVRÁCENO Sez. 102 — nepáka, detail DONE)* **508 Narrow ride podstřel NENÍ páka** (+0,34 strop / +0,59 gaming).
  Measure-first: smíšený podstřel (Bedř délka 0,22× = POKRYTÍ ČÚZK `Lesní průsek` řídké / Blatná počet 0,15× =
  GRANULARITA gen 4,7× delší kusy; medián úseku orig 50-67 m). KPI simulace: i pokrytí STROP gen=orig jen +0,34 pb,
  rozsekání na úseky +0,59 = gaming (mění jen #objektů, ne vizuál; práh arbitrary). 508 = ~4 % hmoty. Generátor netknutý.
- [x] *(VYŘEŠENO Sez. 99 — bug neexistuje)* meta.json „real_sections []" u predict cesty: `veg_area` se ZAPISUJE
  správně (224 položek, provenance predict). Sez. 98 viděl STALE `meta.json` přes skip-existing `_gen_sep` → odhalena
  cache past (níž), opravena.
- [x] *(fix HOTOVO Sez. 99)* **kompas cache invalidace** — skip-existing `_gen_sep` dělal kompas slepým ke změnám
  generátoru (měřil cached `.omap`) → `_code_mtime()` invalidace (cached < kód = stale → přegeneruj).
- [x] *(VYŘEŠENO Sez. 102 — bezpředmětné)* skip-existing past v `run_proxy` (`--proxy` cesta) — `run_proxy` celý
  SMAZÁN při archivaci forest_age proxy (Sez. 102), bod zaniká.
- [ ] *(model, carry mrkla — nález Sez. 99)* **Png2Area přetrénovat na N_AREA 18** (310 přidán do AREA_ZORDER) —
  spojit s class-balanced expansion (208/501/301.1).
- [ ] *(doladění, Sez. 98)* plot 516 `FENCE_SIMPLIFY_M` 5→8–10 m, kdyby přímost obvodu nestačila (riziko zkomolení malých bloků).
- [~] Procedurální generátor OB map — **přestavba „znovu a lépe" (Sez. 11):** vrstvy stavíme po jedné s důrazem na vizuální věrnost. HOTOVO: vrstevnice (§4.5) + bodové symboly extrémů **109/110/111** (§4.10, ISOM 2017-2 Rev 6 — Sez. 13 oprava ze zastaralých 112/113/115) + **terénní cesty (§9, Dijkstra least-cost, ISOM 503/505, `mask_paths.png`)** + vektor 101/102 + **`.omap` template-based** (Sez. 14 — věrná geometrie bodů 110 elipsa / 111 oblouk + plná ISOM knihovna z `template_classic.omap`) + reálný terén `--terrain real` + **reálné cesty `--paths real`** (Sez. 16 — ZABAGED REST, ISOM 502-506) + **reálná voda `--water real`** (Sez. 17 — ZABAGED toky 304/305/306 + plochy 301 vč. `Pozemní_nádrž`/koupaliště Sez. 27, `mask_water.png`) + **reálné budovy `--buildings real`** (Sez. 18 — ZABAGED `Budova_..._plocha_` → ISOM 521, `mask_buildings.png`; **RAW půdorys od Sez. 27** — generalizace i displacement smazány, kresleno jako voda) + **el. vedení + lanovka/vlek `--powerlines real`** (Sez. 24 + 55, ISOM 510 „Power line, cableway or skilift") + **řopíky `--ropiky real`** (Sez. 27, asset, orientace k hranici) + **logging** (Sez. 27, INFO průběh+souhrn) + **železnice `--railways real`** (Sez. 28+31, `Železniční_trať`+`_vlečka`+`Tramvajová dráha` → ISOM 509, kombinovaný symbol; oprava float bugu v `_draw_dashed`; tramvaj doplněna Sez. 31 — Sez. 28 ji vynechala jako „urbánní", chyběla točna LS) + **kolejiště `--paved real`** (Sez. 28, `Kolejiště` → ISOM 501 Paved area, kombinovaný s obrysem) + **pomocné vrstevnice `--terrain real`** (Sez. 29, ISOM 103 form lines — heuristika z DMR: mírný svah AND zakřivený terén, sklon+Laplacián; min. délka 3 mm bez „fousků"; `mask_formlines.png`; NL 108) + **skály/balvany `--rocks real`** (Sez. 30, ZABAGED `Osamělý_balvan`→204 / `Skupina_balvanů__bod_`→207 / `Skalní_útvary`→206; KISS vrstva→jeden symbol, hybridní 202/206 podle plochy i Chaikin smoothing zavrženy „bez datového podkladu"; `mask_rocks.png` 3-class; Hrubá Skála 585). **Sez. 31 také:** rozšíření `DEV_LOCATIONS` na per-lokalita rozměr (5-tuple) → 5. lokalita NV `Novina` PORTRAIT 3×5 km (testuje různé formáty výseků); HS `Hrubá Skála` z landscape 6×4 na **SQUARE 5×5 km** centrovaný na midpoint Kacanovy↔Doubravice. **mosty/tunely/lávky `--bridges real` → 512/512.2** (Sez. 31-33; finální Sez. 33: most = 2 paralely 512 + buffer crop pod mostem, tunel = 512 otočené 90° na vjezdech + passage crop trati projekcí, lávka = 512.2; `mask_bridges.png`) + **`--location` → výstup do složky lokality** (Sez. 33, název = SSoT sdílený se `stats.py`) + **lesní průseky `--rides real`** (Sez. 36, `Lesní průsek` id 16 → ISOM 508 Narrow ride, černá čárkovaná dash 3,0/0,375 mm, KISS vždy 508, bez runnability pozadí = vegetace UC5; `mask_rides.png`; SV 46/NL 119/LS 20/HS 16/NV 44) + **plošný pokryv `--surfaces real`** (Sez. 41, open land louka/park/pole/sad → ISOM 401 žlutá KISS + hřbitov → 520 olivová; parkoviště → 501; z-order vespod; `mask_surfaces.png` multi-class; SV 269/NL 34/LS 1105/HS 365/NV 103) + **udržovaná zeleň → 402/402.1** (Sez. 53, štěpení `typ_pudy_k`: park/okrasná zahrada `PO` → 402 žlutá+bílé tečky, ostatní zeleň `UZ` → 402.1 žlutá+zelené tečky; `SURFACE_DOT` per-symbol rozestup; tříds 4/5; 402.1 = první scattered-bushes zeleň z dat, gate neporušuje) + **bodové vodní/terénní + mokřady `--landmarks`/`--marsh` (Sez. 44, dávka 4):** pramen→312 (modré „U" ústím nahoru), jeskyně/šachta→203.2 (černá „Λ" stříška hrot nahoru), nádrž→311 (modrý čtverec) do `--landmarks`; bažina+rašeliniště→308 Marsh (modrá vodorovná šrafa) jako nový `--marsh` (+ **310 Indistinct** pseudo split ~55 %, přerušovaná šrafa, Sez. 99). **+ AUDIT VĚRNOSTI RENDERU (Sez. 44):** opraveno 203.2 cave (Λ ne plný trojúhelník) + 312 spring (∪ ústí nahoru) + 104 sráz (hnědá ne černá); root cause = špatná konvence omap osy y (+y=DOLŮ, NEflipovat) → paměť `omap-symbol-y-axis-down`; 111/207 byly správně (falešný poplach stažen). **+ komín → 524 High tower** (Sez. 52, `--landmarks`, mirror věží) **+ zábrana → 519 Crossing point** (Sez. 52, nový `--barriers`: bod na zdi 513 → branka, orientace = tangenta zdi, zeď se pod brankou přeruší; jen 2/66 na LS = řídká vrstva, závory na cestách zahozeny). ZAHOZENO: vegetace/paseky/bažiny/balvany (uměle); **L1 generalizace + L2 displacement budov (Sez. 27 — komolily tvar/polohu)**.
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
    reuse `model/tile.py`** (existuje @1,33/512/stride256). **Degradér fáze II HOTOVO Sez. 86** — `build_pair`
    teď s `degrade=True` produkuje i `scan.png` (= X páru, sken). **Branžež verify + noční batch HOTOVO Sez. 90:**
    `build_pair(1005002)` worst-case 93 Mpx **357 s** (downscale drží), `_map_affine` na rotovaném quadu lícuje
    (vizuál); sanity `batch 10` 9/9 OK **~51 s/mapa** → noční `build_pairs batch` 207 ČR **SPUŠTĚN** (resume). Vedlejší:
    `map_gt.segment_gt` nezvládne >~100 Mpx (20 GiB; korpus malý → neakutní).
  - [x] **(verify dluh Sez. 84) Ověřit proc baseline 65 — HOTOVO Sez. 85** (`.omap objektů 65`; `_group_holes`
    bbox prefilter behavior-preserving, regrese 0).
- [x] *(enabler fáze II — HOTOVO Sez. 86)* **omap2png = de-facto hotové** — `generate_map` produkuje `rgb.png`
  vedle `.omap` (verify `pairs.py:7`, Sez. 82 volba C „náš rastr"). C++ headless OOM až měřený doménový gap
  dokáže potřebu (reconstructor selže na reálných OOM/tištěných mapách). „omap2png" v doslovném smyslu (parsovat
  libovolnou `.omap`) jen pro OOM věrnost = cesta A, neakutní.
- [~] **Fáze II/III degradér `generator/degrade.py` — MVP HOTOVO Sez. 86, PŘESUNUT do augmentace Sez. 103.**
  `degrade(rgb, seed)` 4 fotometrické sken-vrstvy (CMYK misregistrace / blur / papír+zažloutnutí / šum+JPEG),
  čistě fotometrické (Y se nemění). **Sez. 103: odstraněn z `build_pair` (zapékal `scan.png` do páru = chyba,
  degradace nepatří do generator() fáze I) → volá se on-the-fly v `model/png2area/dataset.py._augment` jako
  augmentace (jiná realizace každou epochu).** X páru = ČISTÝ `rgb.png`. Paměť [[no-degradation-in-generator-phase]].
  **ZBÝVÁ:** porovnat s reálnou Livelox mapou (cílová doména, mrkla) + **doladit misregistraci ±0,7 px (DŮKAZ
  Sez. 90):** ±1,1 px rozdvojuje tenké symboly — zelený kroužek **417** (Prominent large tree) na zeleném
  podkladu → světlé lemy = „dva bílé kruhy". Pro Png2Area nevadí (417=bod, není v Y), ale pro **Png2Point** musí
  tenké symboly po degradaci zůstat čitelné → zmírnit posun nebo škálovat misregistraci dle tloušťky prvku.
- [~] *(navazuje na hlavní tah, Sez. 80; přejmenováno Sez. 82)* **Tři pomocné modely `reconstructor()` — `Png2Area` /
  `Png2Point` / `Png2Line`** (OOM Point/Line/Area, `type=1/2/4`; dekompozice podle typu geometrie ISOM = tři CV
  úlohy, GT zdarma z `.omap`). Pořadí (foundations): Area → Point → Line. Detail IDEAS „Tři fáze I/II/III".
  - [x] **`Png2Area` HOTOVO Sez. 87-91 — PRVNÍ funkční reconstructor** (plný detail DONE Sez. 87/88/90/91):
    Y-pipeline `omap_raster.py` (**16 area kódů + pozadí**, statický z-order, díry per-objekt) → loader/tile/train
    `model/png2area/{tile,dataset,train}.py` (512/stride256 BEZ rejection, U-Net bez ignore_index, median-freq váhy)
    → overfit gate (nález **tvar > velikost**: tenké třídy se downsamplingem rozpustí) → **plný trénink test mIoU
    0,621→0,640, val 0,654** (cap vah @10 v train.py + cosine LR, loss-spiky zmizely); budovy 521 zachráněny
    0,00→0,68 (váhy+data); `unet_best.pt`. Archiv `git mv` → `model/runnability/`.
    **PŘETRÉNOVÁN N_AREA 18 Sez. 103** (310 přidán Sez. 99): regen 205 párů → tiles 144/31/30 → **test mIoU 0,568 ≈
    val 0,571** (pokles vs 0,640 = 18 tříd víc vzácných nul + degradace-augmentace; hlavní plochy 0,70-0,92, 308
    marsh 0,71/521 0,66/310 0,46; vizuál `1024666` predikce≈GT → mIoU podhodnocuje). **⚠ 3 h/40 ep** = degradace per
    dlaždice v `num_workers=0` → optimalizovat (lehčí/pravděpodobnostní degradace / num_workers Win) PŘED expansion.
  - [~] *(odsunuto za pokrytí generátoru)* **class-balanced expansion** — model = detektor vzácných 208/501/301.1
    (`208` test 0,00 = cap vzal váhu → datový strop) → cílený Livelox download → přetrénovat (IDEAS „Class-balanced
    corpus expansion").
  - [x] **`Png2Point` HOTOVO Sez. 105-106 — DRUHÝ funkční reconstructor** (detail DONE). Sez. 105 pipeline
    (`model/png2point/{inject,dataset,train}.py`): A1 injekce symbolů + A2 heatmap regrese (CenterNet focal) + A3
    scope 204+210. **Sez. 106 dokončeno:** `point_base` render bez bodů (master flag `generate_map`, diff verify) +
    batch 40 map napříč splity (`pairs pointbase`) + dataset random-crop point_base + **root-cause 204** (gate selhal
    → diagnostika: příčina **hustota pozitiv vs focal `n_pos` normalizace**, ne velikostní záměna; `n_boulder`→(40,120))
    → **plný trénink TEST mF1 0,897** (204 0,93 / 210 0,86, bez leaku). `unet_best.pt` → `resources/point_model/`.
    Nález: per-kanál focal ZHORŠILA (vrátit); F1 = injekce na point_base, ne reálné skeny.
  - [ ] *(KPI integrace — HLAVNÍ PÁKA, Příště Sez. 107)* **Integrovat Png2Point body do generátoru** — injekce
    204/210 do `gen.omap` ve statistické míře (kompas cílové Σ) → teprve TADY naroste bodové sub-KPI (dnes 18,4 %).
    Trénink modelu = hotový enabler; KPI dopad = integrace generátoru.
  - [ ] *(registr rozšíření, IDEAS B1)* přidat další bodové třídy do `POINT_CLASSES` (417/419/109/111/112/115 —
    vše point) → re-trénink; hustotu vyvážit dle nálezu Sez. 106 (řídká třída potřebuje srovnatelný počet instancí).
  - [ ] *(reálný transfer, doménový gap)* změřit detekci 204/210 na REÁLNÉM Livelox skenu (ne injekci) — analogie
    Png2Area gen-vs-realita; rozhodne, zda injekční trénink přenese na skutečné mapy.
  - [ ] **`Png2Line`** (poslední, nejtěžší) — liniové ISOM → polyline (segmentace + skeletonizace).
- [~] **(doložený směr Sez. 90, ROZSAH po 1. tréninku) Granularita area tříd — pattern vs odstín.** Měření
  401/403: **403 (bledá žlutá Rough open) je v ČR mapách běžné rozlišení** (vizuál `690592` doložil), sloučení
  403→401 v generátoru = doložená ztráta. Detail + metoda + dvě osy (ODSTÍN nearest-color umí / PATTERN jen CNN)
  v IDEAS „Granularita area tříd". **Rozhodnuto (volba uživatele): trénovat hrubě teď, rozšířit po 1. plném
  tréninku z reálného per-class chování.** Rozsah: **(a) 403 odstín HOTOVO Sez. 92** — separace `_is_pale_yellow`
  rozštěpí žlutou uvnitř open (sytá 401 real / bledá 403 predikt), 3 doložené scan reference + bílá záchyt;
  E2E přes palette/separate/pairs/generator/omap_raster/omap_export; +1 symbol/5 map. ZBÝVÁ: **(b) patternová
  rodina** (404/412/413/414 + zelené directional 406.1/408.1) — generátor kreslit + Y rozšířit, separace
  pattern-aware (těžké, separace per-pixel slepá → jen model nebo generátor kreslí). Konzistentní trojice:
  generátor umí + render kreslí signál + Y má label. Y se jen přerasterizuje (`omap_raster`).
- [ ] *(GT kvalita, nález Sez. 90 — NEŘEŠIT TEĎ, volba uživatele)* **Layout/watermark prosakuje do separace** —
  Livelox mapy s plným layoutem (NEořezané na mapové pole; např. `652602` SKALÁČEK: titulek + sponzorská loga
  + watermark „APP AGENT" + čárový kód) → `map_gt` je zčásti klasifikuje jako zeleň → projde do páru jako falešná
  vegetace ve tvaru textu/loga. `_detect_map_area` (Sez. 73) část vyřízne (652602 gt 13 % ignore), ale watermark
  UVNITŘ mapy + loga proklouznou. **Volba uživatele: pro trénink nevadí** — pár [scan, area_labels] je KONZISTENTNÍ
  (X i Y z téže gen.omap), mapování X→Y validní. Dvě kategorie: (a) watermark uvnitř pole = zeleň na lese, neškodí;
  (b) logo/titulek MIMO pole = „papír jako les", soustavný šum kdyby přes hodně map. **Reálné riziko = ROZSAH** →
  po 1. tréninku změřit, kolik párů nese layout (near-near vs `_detect_map_area` zlepšit / agresivnější crop).
- [x] *(úklid, conceptual integrity — HOTOVO Sez. 93)* **Legacy „forest_age" názvosloví v predict cestě
  přejmenováno na neutrální `veg_area`** — sdílené nosiče predict separace i archiv věku (proměnné
  `veg_area_*` / soubor `mask_veg_area.png` / meta klíč `real_sections["veg_area"]` / `omap_export`
  kwarg+counter) napříč generator/omap_export/separate/stats. Zůstaly legit `FOREST_AGE_*` konstanty
  (archiv-zeleň), `--forest-age` flag, `forest.py` konektor. Behavior-preserving (noise proc 63=63). Detail DONE.
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
- [~] Stupeň 2 — augmentační pipeline (§8.3): degradace render → „sken". **Fotometrická půlka HOTOVO Sez. 86,
  zapojena jako AUGMENTACE Sez. 103** (`degrade.py` volán v `model/png2area/dataset.py._augment` on-the-fly, ne
  v build_pair — degradace patří do tréninkové pipeline, ne do generator() výroby párů, viz
  [[no-degradation-in-generator-phase]]). **ZBÝVÁ geometrická půlka** (deformace sklad/sken, rotace warp) —
  patří na úroveň dlaždice (transformuje X i Y zároveň) vedle D4 (Sez. 78). Pro UC4-III sken / reconstructor fáze III.

## Rozhodnutí (k dozrání → IDEAS.md / architecture.md)
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo) — pozn.: generátor je první kód mimo Pic2Omap, kandidát na úvahu. **Sez. 16: `connectors/` = první sdílená kódová složka mimo sandbox (drobný krok B→A); spouštěč „balík" stále otevřen — až 2. konzument konektorů. Sez. 39: generátor opustil sandbox (`generator/`), sandbox zrušen — krok B→A, ale pořád sys.path skripty, ne balík.**
- [ ] První aplikační kandidát: UC3 de-purple vs jiný — pozn.: UC5 má teď datovou cestu (C) syntetika → váhy se posunuly k UC5

## Backlog (vzdálené, nezačínat)
- [ ] UC5 jádro (palette separation jako první střípek)
- [ ] UC3 / UC4 aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
