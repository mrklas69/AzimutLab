# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## Audit Fable 5 (2026-06-12) — námitky → úkoly
Zdroj + plný kontext a doklady: **`docs/AUDIT_FABLE5_260612.md`** (námitky A1–A7, připomínky B1–B7).
Příští audit (dle `docs/AUDIT_FABLE5_PROMPT.md`) kontroluje stav položek VYŘEŠENO/TRVÁ/ZHORŠENO —
při dokončení přesunout do DONE **s kódem námitky** (A1, B4, …), ať je dohledatelné.

- [~] *(A1, KRITICKÁ; HAL3000 — ROZPRACOVÁNO Sez. 119)* **Reálný benchmark reconstructorů — měřit
  doménový gap syntetika→sken.** **Sez. 119 (`temp/eval_real{,_probe}.py`, scratch nepovýšeno):** Fáze 1
  vizuál HOTOVÁ — model přenáší na reálný sken (struktura sedí, voda 301 excelentní na Blatné = Sez. 118
  fix validován reálně; artefakty striping + modrá halucinace). Fáze 2 číselná: id-based parser kartografovy
  .omap (1230 obj) + crosswalk 2000→2017 + **georef paper→sken px VYŘEŠEN** (rot_sign=−1 net rotace 0,
  flipY=1, ověřeno colorized Y) → **reálná mIoU 0,058 vs syntetická 0,537**. **Nález: vizuál vs pixel-exact
  IoU se ROZCHÁZEJÍ** (colorized Y georefově OK, model vizuálně čte, ale IoU propastné). **CARRY:** diagnostika
  nízké IoU (odstínová záměna 401/403/406? jemná struktura Y vs hrubá pred? striping? subpixel georef? →
  matice záměn pred×Y; zvážit „soft" metriku na hrubších skupinách) + povýšit `eval_real.py` → `model/png2area/`.
  Obě hlavní čísla (Png2Area mIoU 0,537 / Png2Point mF1 0,897) jsou jinak změřena jen na syntetice. Reportovat
  při KAŽDÉM dalším tréninku dvojici (syntetika / realita):
  (a) **Png2Area na `resources/`:** X = sken reálné mapy (PNG + `.pgw`), Y = rasterizace kartografovy
  `.omap` přes `omap_raster` — **POZOR crosswalk:** reálné mapy jsou ISOM 2000, `AREA_ZORDER` čeká 2017-2
  kódy → před rasterizací přemapovat přes `.crt` (vzor `compare_isom`, lekce Sez. 94 — bez crosswalku vyjde
  nesmysl). Start: Bedřichovka + Blatná (mají `.pgw`); metrika = stejný per-class IoU/mIoU kód jako
  `train.evaluate` (žádná nová metrika). Pseudo vrstvy generátoru (516 / 310-split / pseudo 204/210)
  v reálném Y nejsou → vyhodnotit jen třídy přítomné v kartografově `.omap` (viz B6 registr níže).
  (b) **Png2Point na reálném skenu** = existující bod „reálný transfer 204/210" (sekce Png2Point) — touto
  námitkou POVÝŠEN, měřit společně s (a). DoD úkolu: skript `model/png2area/eval_real.py` (nebo `train.py
  --real`), čísla v diáři + README status. Výsledek řídí prioritu A2 vs další pokrytí.
- [!] *(A2; mrkla, až PO [!] re-tréninku 301-voda a PO změření A1 baseline)* **Purple-course + geometrická
  augmentace.** Vrcholová úloha = sken POUŽITÉ mapy (fialový přetisk, ohyby), ale model fialovou nikdy
  neviděl jako vstup — `degrade.py` je čistě fotometrický. (a) Do `model/png2area/dataset.py._augment`
  (izomorfně png2point) přidat on-the-fly kreslení náhodné tratě ISOM purpurou: start trojúhelník, 5–12
  koleček, spojnice, čísla kontrol; barvy dle `map_gt.py` purple_a/b (178,24,148)/(176,8,230); rozměry
  z ISOM 704/705 (kolečko ⌀ 5–6 mm papíru) přepočtené přes mpp dlaždice — verify-against-source proti
  template/spec, nehádat. Kreslí se JEN do X, Y se NEMĚNÍ; patří do augmentace, NE do `build_pair`
  (paměť [[no-degradation-in-generator-phase]]). (b) Geometrická půlka (sklad/ohyb/warp X i Y zároveň,
  vedle D4) = existující bod „Stupeň 2 — augmentační pipeline" níže, touto námitkou povýšen.
- [ ] *(A3; měření HAL3000)* **KPI proti Goodhartu.** (a) Úspěch fáze `generator()` vázat na A1 benchmark;
  KPI zůstává kompas děr, ne cílová funkce — propsat do KPI bloku níže + `architecture.md`. Pravidlo pro
  každou další KPI práci: „pomůže to reconstructoru na reálném skenu?" (b) Rozšířit referenční sadu:
  KPI potřebuje VEKTOROVOU `.omap` (počty objektů) — Livelox je raster-only a referencí být nemůže;
  rozšíření = získat 3–5 dalších kartografických `.omap` (kluby/vlastní mapy) do `resources/`.
  (c) Zvážit oživení per-symbol prostorové metriky (`compare_real_vs_gen.py`, stale-drop Sez. 69) jako
  negamovatelný druhý pohled — až po (a), neotvírat metodologickou frontu navíc.
- [ ] *(A4; ntbhej, docs-only sezení, bez kódu)* **Revize architektury — splatit odklad „plné revize"
  ze Sez. 79 (~37 sezení).** `architecture.md` vede UC5 jako „palette separation/klasifikace" a
  reconstructor jen jako reframe-poznámku; taxonomie UC se rozjela s mentálním modelem uživatele
  (rekonstrukci sken→vektor nazývá „UC3", docs ji vedou jako UC4-III/Pic2Omap). Překreslit DAG kolem osy
  generator() → reconstructor (Png2Area/Point/Line) → aplikace (de-purple, Pic2Omap); taxonomii
  UC3↔UC4-III↔reconstructor rozhodnout S UŽIVATELEM (AskUserQuestion, ne fait accompli); propsat
  README + GLOSSARY + IDEAS (conceptual integrity, všechny vrstvy najednou).
- [ ] *(A5; kdekoli, bez CUDA)* **5 invariantních smoke testů** — automatizace dnešních ručních rituálů,
  NE plná test suite (over-engineering proti fázi B): (1) noise-mode checksum (proc 65 byte-identický);
  (2) golden Šulcák 48 polygonů / 2,56 ha, tol ±2/±5 % (potřebuje ČÚZK fetch nebo `.dmr_cache`);
  (3) konzistence `AREA_ZORDER` ⊆ symboly v `template_classic.omap` ∧ kódy zapisované `omap_export`
  (chytá 301/301.1 typ bugu staticky); (4) `cut.py` mini-verify primitiv (případy Sez. 114 zakonzervovat);
  (5) mini `build_pair`/rasterizace fixture → Y má nenulové px pro každý area kód přítomný v `.omap`
  (chytá 301/301.1 dynamicky). Jeden soubor `tests/smoke.py`, spustitelný `python tests/smoke.py`
  (bez pytest závislosti, KISS); do `docs/PROMPTS.md` %END přidat „měnil-li se kód: spusť smoke".
- [ ] *(A6; HAL3000)* **Záloha měřicích artefaktů** — `_curation.json` (ruční vizuální tagy Sez. 71 =
  neopakovatelná lidská práce), `_split.json` (bez něj jsou všechna mIoU neporovnatelná), chybějící
  `resources/*.pgw` (Velbloud na ntbhej). Malé textové soubory BEZ copyright obsahu → commitnout
  (rozhodnout s uživatelem: přímo do repa vs privátní kanál) + krok do %END checklistu („měřicí
  artefakty zálohovány?"). Řeší zároveň carry „kurace + split na ntbhej" (sekce korpus níže).
- [ ] *(A7; ntbhej-friendly, bez kódu)* **Png2Line — %THINK + rešerše PŘED implementací.** 61 % hmoty
  symbolů = linie+body (Sez. 100); bez Png2Line nelze splnit cíl ≥ 85 %. Rešerše (ověřit, jak to dělá
  branža — nehádat): cartographic line extraction, segmentace+skeletonizace, deep vectorization,
  polyline regrese; zkušenost Pic2Omap. Probe: přenese se injekční trik (Sez. 105, paměť
  [[png2point-inject-clean-base]]) na linie — dash vzory (508/516), křížení, překryvy? Výstup =
  IDEAS návrh + rozhodnutí přístupu s uživatelem, NE kód.
- [x] *(B2, drobnost — HOTOVO Sez. 118, komentářová cesta)* **`ISOM_REF` dvojník — křížový komentář o divergenci.**
  Audit dával alternativu „přejmenovat NEBO doplnit křížový komentář do obou" → zvolen komentář (méně invazivní). `map_gt.py`
  komentář o divergenci (olivová 520 + purpury navíc) UŽ MĚL; doplněn chybějící do `compare_real_vs_gen.py` (Sez. 118).
  Přejmenování `GT_REF` / extrakce do sdíleného modulu se nedělaly (až 3. konzument).
- [ ] *(B3, rešerše bez kódu)* **Livelox ToS — TDM opt-out check.** EU DSM čl. 4 připouští opt-out
  nositele práv ze strojové TDM výjimky; deep research Sez. 67/110 řešil dostupnost dat, NE opt-out.
  Ověřit Livelox podmínky z tohoto pohledu; do vyjasnění: checkpointy modelů privátně (možný derivát),
  žádné výřezy Livelox map v commitovaných souborech/docs.
- [ ] *(B4, drobnost)* **requirements split** — `requirements.txt` (runtime: numpy/Pillow/contourpy/
  pyproj/scipy/pygeomag) vs `requirements-train.txt` (smp/matplotlib + pozn. torch cu128 mimo PyPI).
  Hranice „matplotlib = trénink-only" je dnes nepsaná a už vystřelila (Sez. 112 clip_quad na ntbhej).
- [ ] *(B6, docs drobnost)* **Registr pseudo vrstev do GLOSSARY** — tabulka: vrstva (516 plot /
  310 split ~55 % / pseudo body 204/210) → mechanismus → kde žije (meta.json klíč · `.omap` · stats ·
  Y rastr). Kodifikuje lekci Sez. 108 ([[pseudo-layer-writes-meta-and-omap]]) a umožní A1 benchmarku
  pseudo třídy poctivě vyřadit.
- [ ] *(B1, až bolí)* **Sdílený modul pro string-level `.omap` operace.** `cut.py`/`gen_backgrounds.py` jsou správně
  moduly (monolit nepřikrmovat), ale string-regex místo XML parseru je křehké — každý nový `.omap` zápis musí myslet, ať ho
  cut/backgrounds nerozbije (Sez. 109: clip NESMÍ přes ET kvůli inject). Extrahovat konvenci string-`.omap` operací na jedno místo.
- [ ] *(B5, docs hygiena)* **DIARY index znovu bobtná.** Řádky Sez. 110-116 = mnohařádkové odstavce, index přesahuje 25k
  read-cap (vlastní důvod splitu archivu, %CALIBRATE Sez. 51/86). Vrátit disciplínu „1-2 věty hook" — detail do diáře, index =
  rozcestník. Pozor: staré řádky nepřepisovat (PROMPTS) → zkrátit nově psané + zvážit další split archivu.
- [ ] *(B7, proces)* **Deep research fázovat.** 103 agentů uťatých session limitem (Sez. 110) = nehospodárné. Příště:
  scout → cílený fan-out, průběžně sklízet do RESEARCH.md, ať i uťatý běh zanechá plnou stopu.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi — ČÚZK (Sez. 2), Mapový portál ČSOS (Sez. 8, gate zavřená); lokální mapy `resources/` (smíšený původ); další zdroje TBD
- [~] Doplnit `RESEARCH.md` — LIDAR→mapa metoda hotovo (Sez. 2); zbývá generativní (UC4-I), dewarping/inpainting (UC3)

## UC2 — Data konektory (enabler, průzkum)
- [~] **Doplnit CHYBĚJÍCÍ relevantní vrstvy ZABAGED** (Sez. 23, uživatel „stojíme o všechna data z geoportálu, ne jen vybraná"). **Katalog VŠECH 149 vrstev + stav každé: `docs/kb/zabaged-isom-catalog.md`** (SSoT). Hotové dávky (Sez. 24–56: vedení/lanovka/železnice/kolejiště/skály/mosty/průseky/land-cover/RÚIAN/areály/landmarky/mokřady/stromořadí/kultura/komín/zábrana/kamenolom) jsou v DONE + katalogu. **„KATALOG VYČERPÁN Sez. 52" KOREKCE Sez. 55:** ○ kandidáti lanovka/lom/brod/podjezd/hráz nebyli změřeni jako Sez. 43 → probe ukázal nenulový výskyt; lanovka/vlek→510 HOTOVO Sez. 55, kamenolom→520 HOTOVO Sez. 56. **Zbývají ZMĚŘENÉ ◐/○:** podjezd 519 (Σ12, LS 11, verify spec), brod 519 (Σ6), hráz 528 (Σ13, blokátor legenda), vodopád 313 (Σ2), suť 210 (Σ1). **HOTOVO Sez. 57: balvany-linie → 208 Boulder field** (buffer pás, mirror 406). **Plot 516–518 = doložený SKIP Sez. 57** (ZABAGED plot nevede). Detail + čísla v katalogu „Akční seznam".
- [~] *(idea Sez. 24, fáze 2; POVÝŠENO na aktivní směr Sez. 102)* **Vegetace jako pseudorealistická vrstva** — `pseudorealistic=True` (fáze 2). Hlavní konzument = vegetace (zelená/žlutá průchodnost, v datech není kvůli vegetace gate). **Sez. 102: forest_age proxy smazán → DEV `--location` mapy a syntetické páry bez Livelox skenu kreslí BÍLÝ LES.** Predikční vegetace dnes jde JEN ze separace reálné mapy (cesta párů) — lokality bez skenu zelený generátor nemají. Pseudorealistic = náhrada: **vymyslet věrohodnou zeleň procedurálně** (clustery v lese / perlin / hranice z terénu?). Reframe Sez. 79 ji posvětil („vegetace pro trénink nemusí být pravdivá — reconstructor ji čte ze skenu, generátor generuje procedurálně-věrohodně"). **Příště: %THINK jak generovat.** Spec §0b, GLOSSARY „pseudorealistic"/[[forest-age-proxy]].
- [ ] LiDAR pipeline LAZ → DMR → vrstevnice (zbylá point-cloud větev; za MVP-deštník, až bude konzument). Pozn.: výškopis `dmr.py` (DMR 5G, ImageServer) i cesty `zabaged.py` (ZABAGED ArcGIS REST) už jako konektory žijí v `connectors/` — tohle je plné mračno bodů (naráží na vegetace gate, viz `data-sources.md`). **Sez. 59: stažení DMP 1G mračna automatizováno** (klad SM5 REST + ATOM `openzu.cuzk.cz` + `laspy[lazrs]`) — cesta ověřena, i kdyby jen pro CHM/vrstevnice.
## UC4-I / UC5 — Syntetický generátor (enabler-feeder, fáze B → první kód)
Spec: `docs/kb/generator-procedural.md` · kód: `generator/`

> **[!] KPI generátoru — PRIMÁRNÍ KVANTIFIKÁTOR (Sez. 100, nahradil binární DoD ≥ 90 %):** „jak blízko jsme
> generování **reálně vyhlížejících** O-map" = **proporční podobnost distribuce ISOM symbolů** gen vs vzorové mapy
> = **histogram intersection** `Σ min(orig_share, gen_share)`, per-mapa průměr. Jedno číslo 0–100 %. Měř
> **`generator/measure_dod.py`** (DEFAULT režim; `--table` kompas diagnostika děr / `--dod` archiv binární DoD).
> Robustní vůči obal-artefaktu (proporce ruší rozdíl plochy); penalizuje chybějící typ i přestřel (`min` ukrojí).
> **CÍL: plošná fáze (jen ČÚZK data) ~55 %** (splněno), **s Png2Point + Png2Line ≥ 85 %** (61 % hmoty = linie + body).
>
> **Stav Sez. 107: KPI 59,1 %** (Bedř 52,8 / Blatná 59,4 / Velbloud 65,1; plocha 69,2 / linie 59,3 / **bod 18,4 →
> 54,3** po integraci pseudo bodů 204/210 na masku doložené skalnatosti). **Žebříček děr (kam mířit):**
> **417/419/418** (3,1/2,8/1,3 pb, veg body → Png2Point registr, Příště Sez. 108) / **508/306** (linie) /
> **409/404/410** (vegetace gate, ZABAGED nevede) / 109 (bod). **Další skok = registr veg bodů + Png2Line.**
>
> **Plošná + liniová páka z ČÚZK je VYČERPANÁ** (potvrzeno 4× Sez. 99-102: 403 granularitní propast +0,1, 508
> smíšený podstřel +0,34, 404/407/409 = vegetace gate). Co generátor nenakreslí, reconstructor se NIKDY nenaučí →
> pokrytí = strop tréninku (memory `generator-coverage-is-the-ceiling`). **Historie baseline (43 %→59,1 %), analytické
> cuty (plošný strop 54 %), kompas a vyvrácené páky 403/508: DONE Sez. 94-102 + diáře.**
- [x] *(generator kvalita — HOTOVO Sez. 110, algoritmus; KPI carry)* **`rock_relief` v2 — dlaždicová detekce skal
  @ 0,5 m/px + rekalibrace despeckle.** Z jiného threadu přišel vylepšený `rockcore` v2 (handoff + zlatý vzorek →
  `docs/kb/rock-detection-v2/`). Probami doloženy + opraveny dvě vady: (1) `TARGET_PX_M=1,5` poddetekoval o 43 %
  (40/1,29 ha vs 0,5 m/px) → **pevný `ANALYSIS_RES=0,5`** (práh 46° je na něj kalibrovaný, handoff §4a) + **tiling
  fetch** (`_fetch_assembled_grid`: dlaždice ≤ `MAX_FETCH_PX`, seamless assembled grid → morfologie JEDNOU; čistší
  než handoff §7 per-dlaždice; `dmr.py` netknut); (2) `OPEN_M=1,0` (r=2px) maže tenké stěny −27 % → **`OPEN_M=0,5`**
  (r=1px golden). **Verify (vše ntbhej):** golden Šulcák **48/2,56 ha = match** (golden 48/2,53, tol ±2/±5 %); seamless
  tiling (vynucené 4 dlaždice = identické); reálný Hrubá Skála 2×2 km 159 bloků; E2E `generate_map` 1×1 km HS =
  **49× 206 v .omap + 411× 204 pseudo** (downstream skalnatost maska OK). `MAX_TOTAL_PX=50 Mpx` paměťový strop →
  velký výsek zhrubne s HLASITÝM varováním (no silent fallback). **CARRY HAL3000/Velbloud:** KPI před/po **nelze na
  ntbhej změřit** — kompas Sez. 110: Bedř/Blatná **nejsou skalnaté** (206 orig=0/gen=1, 208 orig=31/gen=0), skalnatá
  Velbloud nemá `.pgw`. Víc skal na ne-skalnatých mapách KPI jen zhorší (přestřel) → KPI dopad měřit až na skalnaté
  mapě. **Sez. 111: Velbloud `.pgw` na ntbhej NEODVODITELNÝ** (`.omap` nese jen minimální georef bez pixel→S-JTSK;
  rekonstrukce z bbox vyvrácena validací — scan rotován grivací) → měřit na **HAL3000** (kartografův georef / rocky
  korpus mapa). Regen párů Y při příštím Png2Area re-trénu (skály do Y věrnější).
- [x] *(model, mrkla — PRECONDITION Sez. 110 → HOTOVO Sez. 118)* **Png2Area přetrénován na N_AREA 18 (voda 301 fix). TEST mIoU 0,537, voda 301 IoU 0,65.**
  **Sez. 110 (ChatGPT %AUDIT:CODE) odhalil, že `omap_raster` měl od narození (2026-06-04) stale `301.1`, zatímco generátor
  zapisuje vodu jako `301` od 2026-06-01 → VODA tiše vypadávala z area_labels (měřeno: Lidové sady 58/0). Oba dosavadní
  tréninky (Sez. 90/91 mIoU 0,640, Sez. 103 mIoU 0,568) se vodu NIKDY nenaučily** — reportovaná mIoU vodu nepočítala.
  Opraveno Sez. 110 (`301.1`→`301` + SSoT `AREA_CODES` ← `AREA_ZORDER`). **Sez. 118 PROVEDENO (mrkla/HAL3000):**
  (0) verify 1 páru `1005002` — voda label 8 v Y: **0 → 81 511 px** (fix prokázán PŘED batchem); (1) regen 205 párů
  force `skip_existing=False` (**ok 205 / fail 2** — `1192962` mimo DMR hranice, `874127` UnicodeEncodeError; stale pár
  874127 smazán, ať tile nevezme bez-vody); (2) re-tile `allow_missing=True` → `_tiles.json` n_area 18, `301` váha
  **0,0 → 0,996** (už ne prázdná třída); (3) plný trénink 40 ep HOTOVO (best ep 37) — **TEST mIoU 0,537, voda 301 IoU
  0,65** (dříve strukturálně 0 = dnešní cíl SPLNĚN, fix prošel celým řetězem do modelu; voda nadprůměrně naučená).
  **mIoU 0,537 je POPRVÉ POCTIVÝ (s vodou) — naivní srovnání s 0,568 (Sez. 103, BEZ vody) neplatí**; očištěno o vodu ~0,53,
  mírně níž (voda přebrala px + 2 mapy vypadly + 1 běh, ne regrese kvality). Křivka stabilní bez spiků (cap @10 + cosine drží).
  Datový strop vzácných drží: 402/208/501 IoU ~0 (známé, class-balanced expansion). `unet_best.pt` → `resources/area_model/`. Pozn.: `class-balanced expansion` u 301 moot (voda po fixu hojná). **Dohoda Sez. 118: po tomto
  STOP na modelech, zpět ke zrání generátoru** (off-water / cut / layout / crop nálezy z testu).
- [ ] *(doladění → nález uživatele Sez. 118 „zubaté ploty")* **Plot 516 kolem velké privátní oblasti (520) je ZUBATÝ** ({A}, ~6 zbytečných
  zubů na velkém pozemku). Mechanika: `_dissolve_mask_to_polys(olive_ruian_img)` → outer ring → `_rdp(eps = FENCE_SIMPLIFY_M=5 m)` →
  `_draw_fence_line` (gen ~2496-2506). RDP 5 m zuby nespolkne. **Řešení (volba uživatele „zjednodušit na vnější hraniční body"):** primárně
  **zvýšit `FENCE_SIMPLIFY_M` 5→8–10 m** (původní Sez. 98 dořešení — tohle je ten „kdyby přímost nestačila"). Pokud hluboké zuby přetrvají:
  morfologické **closing seed masky** PŘED dissolve (vyplní úzké zářezy mezi RÚIAN parcelami). **Oponuji convex hullu** (uživatelovo „vnější
  body" by mohl znamenat hull) — ztratil by legitimní konkávní tvary velkých pozemků (zálivy) a mohl by plotem pohltit sousední ne-privátní
  oblast. RDP/closing drží tvar, jen hladí. Riziko (Sez. 98): vyšší práh komolí malé bloky → ladit s `FENCE_MIN_AREA_M2` na očích.
- [x] *(bug fix, test výstupů Sez. 113 — HOTOVO)* **Balvany 204/210 + plot 516 na vodní hladině** (Nová Louka). Root
  cause: `_generate_pseudo_boulders` nedostával vodní masku → pseudo balvany padaly na 301; plot se generuje PŘED
  vodou (z-order pokryv vespod). Fix: `_rasterize_water_grid` (outer=voda, holes=ostrov→souš) odečte vodu ze seed
  masky + per-tečka check 210; `_clip_fences_off_water` (post-water) vyřízne fence úseky nad hladinou z `.omap`
  (rastr OK — voda kreslí nad). Verify měřením: balvany na vodě 0 px po erozi břehu 3 px (max shluk 16 px = okraj
  symbolu na břehu); plot 0 bodů >3 px od břehu. Vizuál nádrž čistá.
- [x] *(bug fix Sez. 113/114 — HOTOVO Sez. 114)* **Ořez `.omap` na výsek bez Livelox páru** (Novina „Nisa do Vesce",
  ±20 km přesah). Implementována schválená DRY architektura v `generator/cut.py`: primitiva `cut_point`/`cut_line`/
  `cut_area` (Sutherland-Hodgman) → orchestrátor `clip_omap` (přepis `<coords>`+flagy, scoped na `<objects>`) → wrappery
  `cut_box` (papír, CLI `--location` real) + geometrický `clip_omap_to_quad`. Mini-verify 10/10 + 9/9. **Nález: reuse
  `_split_by_zones_interp` pro `cut_line` nestačil** (ponechává konce linie → neumí in→out) → přímá konstrukce, reuse jen
  `_interp_grid_at`. Verify: regen 5 DEV ořez 1,00× (uživatel OOM „perfektní"). Detail DONE Sez. 114.
- [x] *(blokátor regenu se skalami, nález Sez. 114 — „zmizely kontury skal"; HOTOVO Sez. 115)* **`rock_relief` OOM + border noData.**
  Plný regen DEV map SE SKALAMI spadl u 3/5. **Měření (`temp/probe_rock_oom`):** f64 pipeline @ 50 Mpx peak **3,3 GB**
  (OOM @ 8,4 GB volných + běžící generátor); páka = **`del` mezivýsledků sklonu PŘED `_contour_rings`** (ne dtype — peak je
  v `_rock_mask`/label int32, f64↔f32 stejně 1,9 GB) → zvolen **f64+del** (zachová přesnost prahu 46°, peak 3,3→1,9 GB).
  **(a) OOM fix:** `del z,zs,gy,gx,slope_deg` + `_contour_rings` padded float32 (behavior-preserving, sdíleno se `separate.py`).
  **(b) border fix:** `_fetch_assembled_grid` zachytí `RuntimeError` za hranicí ČR → **NaN dlaždice + hlasité warning**
  (no silent fallback); `errstate` v sklonu → NaN propadne `slope>=46`→False (bez skal u hranice). **Verify:** golden Šulcák
  **48/2,56 ha = match** (behavior-preserving); izolovaný HS 847 bloků/peak 2,6 GB + SV 130 bloků/2 dlaždice NaN; **plný regen
  HS/SV/LS se skalami EXIT 0** (HS 847× 206 v .omap = skalní ukázka má zpět skály). Detail DONE Sez. 115.
- [x] *(KPI regrese, nález Sez. 115 → VYŘEŠENO Sez. 116 density gate)* **Pseudo body 204/210 — rock v2 over-detection na ne-skalnatých mapách.**
  Pokles 54,9→48,2 % izolován: ořez VYVRÁCEN (+0,9 pb), grivace VYVRÁCENA, **hlavní příčina pseudo body −3,25 pb** (210 Stony přestřel
  962 vs 372 z falešné skalnatosti). **Měření Sez. 116 (`temp/probe_rock_overdetect`, cesta B = kořen):** rozdíl skutečná vs falešná
  skála NENÍ práh sklonu (oba >46°), ale **regionální HUSTOTA**: skalnaté mapy ≥0,16 % px ≥46° (SV 0,158 / HS 2,22 / golden Šulcák 3,72 %),
  ne-skalnaté jen ~0,04 % (Bedř 0,042 / Blatná 0,037 — mikroreliéf: zářezy cest, břehy). **Fix = `rock_relief.DENSITY_GATE_PCT=0,08`**
  (volba uživatele): pod práh → 0 ploch 206 + hlasitý INFO log (no silent). Golden Šulcák ZACHOVÁN beze změny (48 polygonů), SV/HS zachovány,
  Bedř/Blatná falešné → 0. **KPI 48,2 → 55,0 % (+6,8 pb, NAD baseline 54,9)**, bod sub 45,8→51,8. 204/210 pryč z žebříčku děr.
- [ ] *(vizuál Soví vrch, nález uživatele Sez. 116)* **Kameny/balvany (204/210) NEumisťovat na tenké liniové plochy podél komunikací** —
  symboly jsou pak často zakryté nebo částečně zakryté liniovým symbolem cesty/silnice. Souvisí s pseudo body maskou
  (`_generate_pseudo_boulders`) — analogie k vyloučení vody (`_clip_fences_off_water`/`_rasterize_water_grid`, Sez. 113):
  vyloučit z pseudo masky úzké plošky/koridory podél cest (erodovat masku o okolí cest, nebo min. vzdálenost bodu od linie cesty).
- [ ] *(feature, vrstevnice, nález uživatele Sez. 116)* **102.1 zdůrazněná (index) vrstevnice na násobky 50 výškových metrů** —
  do mapy přidat zesílenou vrstevnici ISOM 102.1 na hladinách dělitelných 50 m (orientační čára nadmořské výšky). Dnes se kreslí
  jen 101 (běžná). Index contour = každá N-tá zesílená; uživatel chce kotvit na absolutní násobky 50 m, ne každou N-tou od základu.
- [ ] *(vizuál, ořez `cut.py`, nález uživatele Sez. 118)* **Neohraničovat tučnou čarou odstřižené hrany ploch s neproniknutelnou hranicí** —
  když `cut_area` (Sutherland-Hodgman) ořízne plochu, která má tučný černý obrys (impassable boundary, např. budova 521 / olivová
  520 / lom), OOM vykreslí border kolem CELÉHO oříznutého prstenu → obrys se domaluje i na umělou řeznou hranu (linii střihu).
  Vypadá to divně (uměle vzniklá „neproniknutelná" hrana na okraji výseku). Řešení (%THINK, neimplementovat teď): body vzniklé
  řezem (leží na clip-linii) označit OOM gap/dash flagem, aby se obrys na řezném segmentu nekreslil — vyžaduje rozlišit řezné body
  od původních v `cut_area` a ověřit OOM interpretaci flagu pro area border (verify-against-source: jak OOM přerušuje border line).
- [ ] *(bug fix, test výstupů Sez. 118)* **Hranice porostu 416 NESMÍ vést přes vodní plochu** (`resources/livelox/631730/gen/map.omap`,
  marker {A}). `_predict_veg_boundaries(class_mask, draw, bdraw)` (gen 2609) kreslí 416 čistě z mezitřídních hranic predikčních
  veg ploch (`class_mask`) — **nedostává vodní masku** → když separovaná zeleň sahá k vodě / přes ni, tečkovaná hranice projde
  přes hladinu = nepřípustné (voda není runnability-vegetace). Stejný typ vady jako balvany/plot na vodě (Sez. 113). Fix
  (analogie): per-bod check `water_cell` v `_predict_veg_boundaries` → přerušit úsek nad vodou (jako `_generate_pseudo_boulders`
  `mask &= ~water_cell`), nebo post-water clip 416 segmentů z `.omap` (`_clip_fences_off_water` vzor). Předat vodní masku do funkce.
- [ ] *(vizuál, vrstevnice přes vodu, nález uživatele Sez. 118 — řešení OPRAVENO na CLIP po rešerši IOF)* **Vrstevnice se NESMÍ zobrazovat
  přes vodní plochu — řešení CLIP (geometrie), NE z-order.** Původní hypotéza „z-order (modrá plocha nad hnědou)" VYVRÁCENA rešerší IOF
  (Fable5, Sez. 118): oficiální IOF colour order má **modrou plochu POD hnědou linií** (Printing & Colour Definitions Feb 2022, kap. 7 str. 6;
  cross-check OpenOrienteering/mapper#1966). Náš OOM template to má IOF-věrně (`Blue area` priority 15 pod `Brown` 6). Že reálné mapy nemají
  vrstevnice v jezerech je GEOMETRIE (kartograf je tam nekreslí), ne paleta — z-order by je nikdy neschoval. Fix: vrstevnice (101/102/103/104)
  vyříznout vodní maskou (`water_cell`) STEJNĚ jako 416/balvany/plot → spadá pod sdílený `off_water` filtr níže. X↔Y konzistentní pro budoucí
  Png2Line (Y bez vrstevnice ve vodě = jako reálné `.omapy`). Pozn.: břehová linie 301 (černá #4) i toky 304/305 (modrá linie #8) zůstávají NAD vodou (IOF-věrné, neclipovat).
  **Reference colour order: `docs/kb/isom-colour-order.md`** (plná tabulka ISOM 2017-2 + ISOM 2000 rozdíl + lokální PDF `iof-printing-colour-2022.pdf`).
- [ ] *(bug fix, 416, nález uživatele Sez. 118)* **Hranice porostu 416 jen tam, kde aspoň jedna sousední oblast je les (zeleň/bílá)** —
  `resources/livelox/1163841/gen/map.omap` {A}: 416 vedená mezi dvěma OPEN (oranžová↔oranžová) = nesmysl (ISOM 416 = hranice ZŘETELNĚ
  RŮZNÉ vegetace, mezi dvěma open není). `PREDICT_AREA_CLASS` = {410:1, 408:2, 406:3 (zeleň), **403:4 (rough open)**}. `_predict_veg_boundaries`
  bere libovolnou mezitřídní hranici → fix: úsek kresli jen pokud aspoň jedna strana ∈ {zeleň 406/408/410} nebo bílá (les runnable),
  NE když obě open (401/403). Ověřit přesný mechanismus na 1163841 {A} při implementaci (jak vzniká open↔open hrana — soused přes pozadí?).
- [ ] *(DRY konsolidace, princip CLAUDE.md „voda = no-draw zóna" Sez. 118)* **Sjednotit off-water masking do jednoho `off_water` helperu** —
  dnes per-vrstva: balvany `mask &= ~water_cell` (Sez. 113), plot `_clip_fences_off_water` (Sez. 113); přibývají 416 + **vrstevnice 101-104**
  (Sez. 118). Extrahovat jeden filtr beroucí `water_cell`, aplikovat na VŠECHNY terénní/predikční/pseudo geometrie (≥4 konzumenti = jasný důkaz
  pro „generalizuj s důkazem"). Výjimka jen prvky legitimně nad/přes vodou z tvrdých dat: břehová linie 301, most/lávka 512, hráz, tok 304/305.
- [x] *(bug fix, test výstupů Sez. 113 — HOTOVO)* **Plot 516 „uvězňuje" budovu** (Lidové sady, panelák Hokejka).
  Root cause: fence kolem RÚIAN parcel druhu {5 zahrada, **13 zastavěná plocha**}; panelák JE parcela druhu 13 →
  plot obkresloval otisk budovy. Fix (volba uživatele): fence seed maska `olive_ruian_img` jen druh 5 (zahrada),
  ne 13 (`str(druhpozemkukod)=="5"`); druh 13 zůstává v 520 olivové. LS regen 215 plotů (jen zahrady).
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
- [x] *(feature, nápad uživatele Sez. 37 — METADATA CESTA HOTOVA Sez. 112)* **Grivace v generátoru.** Tři vrstvy:
  (A) `--grivation <deg>` ruční → `.omap` georef `declination=grivation` (Local, izomorf skenu) + meta `north=magnetic`;
  (B) `_gen_sep` čte grivaci ZE SKENU (`_scan_grivation`) → resources gen.omap lícuje s bg_scan; (C) konektor
  `connectors/magnetic.py` (pygeomag WMM offline + pyproj konvergence; znaménko `decl−pyproj_conv` ověřeno proti skenům)
  + CLI `--grivation-auto`/`--grivation-date`. Geometrie i rastr zůstávají v gridu (volba: jen georef metadata). Detail
  DONE Sez. 112. **ZBÝVÁ (curtains, odloženo):** **rotace rastru `rgb.png` o grivaci** — až rastrový konzument
  (reconstructor) potřebuje magnetic-north sken; patří na úroveň augmentace/dlaždice (transformuje X i Y zároveň), ne
  do `generate_map` (Sez. 112 Příště).
- [x] *(UC5 korpus — HOTOVO Sez. 70-71, detail v DONE)* **Livelox korpus 268 reálných OB map** (`livelox.py`
  `search_events`/`download_corpus`, `allEvents`→`SearchEvents` reverz, WGS84 fallback, backoff) **+ kurace
  → 216 keep classic** (`curate.py` taxonomie discipline+tagy, `_curation.json`) + olivová 520 → label 0 (čistota GT).
  Tréninkové jádro = 216 foot-O map. Legalizace (ČSOS) až pokud model funguje — do té doby privátní repo + TDM výjimka.
- [~] *(Sez. 110 stahování + Sez. 111 GT HOTOVO, kurace/split carry)* **Korpus + GT na ntbhej.** `livelox batch` stáhl
  **57 → 264 map**, GT **264/264** (Sez. 111 chunked classify odblokoval 6 obřích). **ZBÝVÁ:** (a) **kurace + split
  rozhodnout** — `_curation.json`/`_split.json` na ntbhej NEJSOU (gitignored, ruční vizuální tagy Sez. 71 žijí na HAL3000)
  → buď **zkopírovat z HAL3000** (zachová tréninkový split, doporučeno), nebo auto-`curate`+`split` tady (rozejde se
  s HAL3000). Pozn.: `build_pair`/trénink je stejně CUDA-vázané (HAL3000) — ntbhej korpus slouží měření / `build_pair`
  E2E ověření / rozšíření tréninkového setu po přenosu na HAL3000.
- [x] *(HOTOVO Sez. 111 — chunked classify, NE downscale)* **`map_gt.segment_gt` zvládne obří mapy.** Měřením doloženo,
  že RAM blowup je JEN v `_classify` (`(N,13,3) int32` ~5,5 GiB @ 35 Mpx) → přepsán na **chunked** řez po pixelovém
  rozpočtu (`_CLASSIFY_CHUNK_PX=4 Mpx`), **byte-identický** (per-pixel argmin nezávislý). Zvolen místo downscalu výstupu,
  protože ten by rozbil invariant `gt.shape==map.shape` (`livelox.py` guard + affine). 6 obřích map (35–97 Mpx) → GT;
  korpus na ntbhej **264/264**. Detail DONE Sez. 111.
- [ ] *(ověření, Sez. 109; ořez povýšen Sez. 114)* **Ořez `pairs.build_pair` end-to-end na HAL3000.** `cut.clip_omap_to_quad`
  přidán do `build_pair` (před rasterizací Y → konzistentní pár; quad = Livelox `g["quad"]`) + izolovaný sanity OK, ale
  plný běh na ntbhej blokován syrovým korpusem (0 gt). Ověřit na HAL3000: že páry mají ořezané .omap+render (bez
  okolních sídel) a Y label sedí na X. Pozn.: `clip_omap_to_quad` je teď **geometrický** (Sez. 114, povýšen z centroidu →
  řeže dlouhé linie na hraně quadu, ne celé/nic dle středu) — E2E ověřit, že geometrický řez na rotovaném quadu sedí.
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
  - [x] *(HOTOVO Sez. 107, detail DONE)* **Integrovat Png2Point body do generátoru → KPI 50,3 → 59,1 % (+8,8 pb).**
    Pseudo injekce 204/210 do `gen.omap` (`_generate_pseudo_boulders` + `omap_export` `210.1`), reuse inject
    geometrie (NE model), gated `pseudorealistic` bez flagu (visí na rocks). **Scope 204+210, 207 vyřazen** (kompas
    16/17 pokryto). Měření vynutilo: maska z **doložené skalnatosti** (206+reálné body+dilatace, ne sklon — sklon ≠
    skalnatost, přestřelil) + kalibrace na **share** (ne absolutní Σ). Bod sub 18,4 → 54,3 %. Zbytek = data-gate
    (skalnatost není v geodatech → Blatná přestřel 48 %).
  - [ ] *(registr rozšíření, IDEAS B1 — Příště Sez. 108, vrchol žebříčku po 204/210)* přidat bodové třídy
    **417/419/418** (Special vegetation feature) do `POINT_CLASSES` (Png2Point) i pseudo injekce generátoru
    (mirror 204/210) → re-trénink + KPI; pak 109/111/112/115. Hustotu vyvážit dle nálezů Sez. 106/107.
  - [!] *(reálný transfer, doménový gap; POVÝŠENO auditem A1 — sekce „Audit Fable 5" nahoře)* změřit detekci 204/210 na REÁLNÉM Livelox skenu (ne injekci) — analogie
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
- [!] *(GT kvalita, nález Sez. 90 → ESKALOVÁNO Sez. 118 uživatelem — VADÍ)* **Layout/text/loga prosakují do separace jako falešná vegetace.**
  Livelox mapy s plným layoutem (NEořezané na mapové pole) → texty/titulky/loga/měřítko se separují a projdou do páru jako falešná
  vegetace ve tvaru písmen/loga. **Sez. 118 konkrétní důkaz `resources/livelox/946084/gen` {A}:** zelený titulek **„SAXBO 2025" + „KATEGORIE"
  + měřítko/datum jsou UVNITŘ mapového pole** (vytištěné přes mapu), v ISOM zelené → separace je nemůže odlišit BARVOU od porostu →
  hustý porost ve tvaru textu „SAXBO 2025". Vizuál potvrzen (rgb.png). **Volba Sez. 90 „pro trénink nevadí" PŘEHODNOCENA** — model se učí
  „zelený text = hustý porost" (halucinace). **Klíčové zjištění Sez. 118: ořez na quad NESTAČÍ** (text je UVNITŘ quadu, ne mimo jako legenda)
  → potřeba **strukturní detekce textu/popisků uvnitř pole** (barva selhává — čistá ISOM zeleň). `_detect_map_area` (Sez. 73) řeší jen layout
  MIMO pole. Směry (%THINK): (a) strukturní detektor — souvislé tenké zelené komponenty s vysokým aspect-ratio / pravidelnými rozestupy /
  ostrými hranami písma vs plošný organický porost; (b) kurace — vyřadit/cropnout mapy s titulkem v poli (titulek bývá dole/v rohu →
  cílený crop spodního pruhu? riziko ořezu mapy); (c) měřit ROZSAH (kolik z 205 párů nese text-v-poli). Souvisí s follow-up detektor
  control-description mřížky (níže, Sez. 73 known limitation). **Pozn.: nezdržuje dnešní voda re-trénink** (946084 je test split; patří do zrání korpusu, směr PO re-tréninku).
- [!] *(GT kvalita / ořez, nález uživatele Sez. 118)* **Crop gen na bbox REÁLNÉHO mapového obsahu, ne na celý Livelox quad.**
  `resources/livelox/856040/gen` {A}: reálná mapa „Mezi silnicemi" je NEPRAVIDELNÝ tvar s velkým bílým okolím; Livelox quad (obdélník)
  je VĚTŠÍ → generátor generuje i tam, kde `map.png` nemá obsah → mimo reálnou mapu separace nemá co separovat → kreslí jen syrová
  ZABAGED (bílý les, žádné zelené areas). Vizuál gen render POTVRZEN: věrohodná vegetace jen ve středu (kde byla předloha), zbytek quadu
  = syrová žlutá ZABAGED. **Řešení (volba uživatele): crop na OBDÉLNÍK s podkladem `map.png`** — detekovat bbox ne-bílé/mapové oblasti
  (**reuse `_detect_map_area` Sez. 73**, už barevně detekuje mapové pole) → crop extent místo Livelox quadu (mechanika `cut.cut_box` existuje,
  jen jiný extent; volá se v `pairs.build_pair` před rasterizací Y). **Bonus:** odřízne i layout MIMO pole (titulek/legenda MH-SK) → částečně
  řeší layout nález výše (SAXBO text UVNITŘ pole ale zůstává na strukturní detektor). Nuance: bbox obdélník nechá rohy s bílou/ZABAGED (mapa
  nepravidelná) — pro úplnou čistotu crop na MASKU tvaru (nad KISS, až kdyby vadily rohy). **Nezdržuje voda re-trénink** (856040 test split).
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
  [[no-degradation-in-generator-phase]]). **ZBÝVÁ geometrická půlka** (deformace sklad/sken, rotace warp;
  POVÝŠENO auditem A2 — sekce „Audit Fable 5" nahoře) —
  patří na úroveň dlaždice (transformuje X i Y zároveň) vedle D4 (Sez. 78). Pro UC4-III sken / reconstructor fáze III.

## Rozhodnutí (k dozrání → IDEAS.md / architecture.md)
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo) — pozn.: generátor je první kód mimo Pic2Omap, kandidát na úvahu. **Sez. 16: `connectors/` = první sdílená kódová složka mimo sandbox (drobný krok B→A); spouštěč „balík" stále otevřen — až 2. konzument konektorů. Sez. 39: generátor opustil sandbox (`generator/`), sandbox zrušen — krok B→A, ale pořád sys.path skripty, ne balík.**
- [ ] První aplikační kandidát: UC3 de-purple vs jiný — pozn.: UC5 má teď datovou cestu (C) syntetika → váhy se posunuly k UC5

## Backlog (vzdálené, nezačínat)
- [ ] UC5 jádro (palette separation jako první střípek)
- [ ] UC3 / UC4 aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
