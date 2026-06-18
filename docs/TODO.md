# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## Audit Fable 5 (2026-06-12) — námitky → úkoly
Zdroj + plný kontext a doklady: **`docs/AUDIT_FABLE5_260612.md`** (námitky A1–A7, připomínky B1–B7).
Příští audit (dle `docs/AUDIT_FABLE5_PROMPT.md`) kontroluje stav položek VYŘEŠENO/TRVÁ/ZHORŠENO —
při dokončení přesunout do DONE **s kódem námitky** (A1, B4, …), ať je dohledatelné.

- [~] *(A2; mrkla — (a) purpura HOTOVO Sez. 123 + Png2Area re-trénink Sez. 124; Png2Point re-trénink Sez. 125 ODHALIL NESTABILITU → [!] položka níže; ZBÝVÁ (b))* **Purple-course + geometrická augmentace.**
  Vrcholová úloha = sken POUŽITÉ mapy (fialový přetisk, ohyby), ale model fialovou nikdy neviděl jako
  vstup — `degrade.py` je čistě fotometrický. **(a) Purpura HOTOVO Sez. 123:** `model/purple.py`
  (sdílený util mimo `generator/`) `overprint_course(rgb, seed)` kreslí ISOM trať (701 start △ / 702
  kruh / 703 čísla / 704 spojnice / 706 finish) JEN do X, Y/heatmapa netknuté; rozměry
  verify-against-source ISOM 2000 §4.7 (`PX_PER_MM≈7,52` izomorf `inject.py`), barvy `purple_a/b`
  (Sez. 72). Integrace do obou `dataset.py` (po D4/inject, před degrade, prob 0,5). Measure-first
  doložil hodnotu: fialová sráží purpura-naivní Png2Area test mIoU 0,537 → 0,488 (−4,9 pb; 501.1 −0,255).
  **Png2Area re-trénink HOTOVO Sez. 124** (best ep 21, TEST mIoU 0,566; re-probe `temp/probe_purple_impact.py`
  clean 0,566 → purpura 0,554 = **Δ −0,012**, dopad ↓ ~75 % vs naivních −0,049; 501.1 −0,255→−0,016 /
  301 −0,139→−0,017 → hypotéza A2a potvrzena). **Png2Point re-trénink Sez. 125: NEDOKONČITELNÝ jako rutina —
  odhalil, že trénink je vážně nestabilní** (mF1 0,15–0,90 dle seedu; „0,897" Sez. 106 = outlier). Purpura dopad
  paired (seed=0): **ON−OFF −0,043** (mírně škodí, podružné vůči nestabilitě). Stabilizace = [!] položka níže;
  purpuru doměřit až na stabilním základě. **(b) Geometrická
  půlka** (sklad/ohyb/warp X i Y zároveň, vedle D4) = existující bod „Stupeň 2 — augmentační pipeline"
  níže, touto námitkou povýšen. Pozor u Png2Area: warp Y by mezi třídami vyrobil smíšené px (proto D4
  jen rot90) → nearest-neighbor na Y, nebo warp jen X.
- [ ] *(A3; měření HAL3000)* **KPI proti Goodhartu.** (a) Úspěch fáze `generator()` vázat na A1 benchmark;
  KPI zůstává kompas děr, ne cílová funkce — propsat do KPI bloku níže + `architecture.md`. Pravidlo pro
  každou další KPI práci: „pomůže to reconstructoru na reálném skenu?" (b) Rozšířit referenční sadu:
  KPI potřebuje VEKTOROVOU `.omap` (počty objektů) — Livelox je raster-only a referencí být nemůže;
  rozšíření = získat 3–5 dalších kartografických `.omap` (kluby/vlastní mapy) do `resources/`.
  (c) Zvážit oživení per-symbol prostorové metriky (`compare_real_vs_gen.py`, stale-drop Sez. 69) jako
  negamovatelný druhý pohled — až po (a), neotvírat metodologickou frontu navíc.
- [~] *(A4; taxonomie VYŘEŠENA ROADMAPem + Sez. 139 audit; zbývá kosmetická revize statického DAGu)*
  **Revize architektury — odklad „plné revize" ze Sez. 79.** **Taxonomie směru rozhodnuta:** ROADMAP
  (Sez. 136) dal osu `Generator()` → `Rekonstruktor()`, `%AUDIT:DOCS` Sez. 139 ji sladil do `architecture.md`
  (UC5 = tři reconstructory Png2Area/Point/Line, ne „palette separation"; status hlavička odkazuje ROADMAP
  jako SSoT směru; KPI/Png2Line drift opraven) + README + GLOSSARY + IDEAS. **ZBÝVÁ jen kosmetická revize
  statického 5-UC DAGu:** umístění de-purple (UC3) a Pic2Omap absorpce (UC4-III) v rámci `Rekonstruktor()`
  etapy — neblokuje, není to „rozhodnout taxonomii", jen dorovnat APP boxy DAGu na osu ROADMAP.
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
- [ ] *(B3, rešerše bez kódu)* **Livelox ToS — TDM opt-out check.** EU DSM čl. 4 připouští opt-out
  nositele práv ze strojové TDM výjimky; deep research Sez. 67/110 řešil dostupnost dat, NE opt-out.
  Ověřit Livelox podmínky z tohoto pohledu; do vyjasnění: checkpointy modelů privátně (možný derivát),
  žádné výřezy Livelox map v commitovaných souborech/docs.
- [ ] *(B4, drobnost)* **requirements split** — `requirements.txt` (runtime: numpy/Pillow/contourpy/
  pyproj/scipy/pygeomag) vs `requirements-train.txt` (smp/matplotlib + pozn. torch cu128 mimo PyPI).
  Hranice „matplotlib = trénink-only" je dnes nepsaná a už vystřelila (Sez. 112 clip_quad na ntbhej).
- [ ] *(B1, až bolí)* **Sdílený modul pro string-level `.omap` operace.** `cut.py`/`gen_backgrounds.py` jsou správně
  moduly (monolit nepřikrmovat), ale string-regex místo XML parseru je křehké — každý nový `.omap` zápis musí myslet, ať ho
  cut/backgrounds nerozbije (Sez. 109: clip NESMÍ přes ET kvůli inject). Extrahovat konvenci string-`.omap` operací na jedno místo.
- [ ] *(B7, proces)* **Deep research fázovat.** 103 agentů uťatých session limitem (Sez. 110) = nehospodárné. Příště:
  scout → cílený fan-out, průběžně sklízet do RESEARCH.md, ať i uťatý běh zanechá plnou stopu.

*(ChatGPT audity 2026-06-14 / Sez. 125 — DOCS+CODE: nálezy vypořádány Sez. 125-127, zdroje
`AUDIT_DOCS_260614.md` / `AUDIT_CODE_260614.md` archivovány Sez. 139.)*

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
> **2. KPI — reálný doménový gap (Sez. 120–121, re-benchmark Sez. 126 po MPP fixu, Fable5 A1):** KPI výše měří jen
> FEEDER (kvalita generátoru); zda reconstructor reálné mapy ČTE, měří `model/png2{area,point,line}/eval_real.py` na
> kartografových skenech. Po MPP fixu (Sez. 126, kanonické měřítko dlaždice 1,33) přeměřeno na správném měřítku:
> **Png2Area** (per-odstín mIoU / soft pixel-acc): **Bedř 0,336 (z 0,256) / 0,91, Blatná 0,357 / 0,89** (synt test
> mIoU 0,683). **Png2Point** (peak mF1 synt / realita; **4 třídy 204/210/417/419 od Sez. 128**): synt **0,827**
> (medián 3 seedů: 417 0,85 / 419 0,86 / 204 0,77 / 210 0,84) / **realita mean 0,43–0,57** (per-class práh Sez. 129):
> **419 Prom. veg. feature SILNÝ 0,67–0,76** (líp než 204, výrazný zelený X + bílá svatozář), **417 Prom. large tree
> 0,48–0,57** (Sez. 135 cause-fix: injekce na reálnou hustotu `n_range (20,60)→(10,30)`, re-trénink; ~neutrální vůči
> Sez. 129 prahu, ale bez recall kolapsu; P 0,39–0,66), 204 stabilní 0,44–0,73, **210 pořád kolabuje
> 0,00–0,25** (drobné tečky). Práh detekce je **per třída v registru `PointClass.peak_thr`** (zelené chtějí vyšší).
> **Png2Line krok 1 watercourse 304/305 (Sez. 131, NOVÝ 3. reconstructor; pixel IoU / relaxed completeness/correctness):**
> synt test mIoU 0,774 / IoU 0,55 · **realita: completeness 0,85–0,93 = model TRASUJE reálné toky** (žádný kolaps
> jako 210), **strict IoU 0,409 / F1 0,773** po conf_thr prahu 0,95 (registr `LineClass.conf_thr`, izomorf `peak_thr`;
> argmax přestřeloval na cesty → IoU 0,251→0,409). Strukturální cure zbylé precision = krok 2 (víc liniových tříd).
> Pravidlo: nová KPI práce se ptá „pomůže to reconstructoru na reálném skenu?".
>
> **Stav Sez. 138: KPI 60,7 %** (Bedř 53,6 / Blatná 61,5 / Velbloud 67,0; plocha 69,5 /
> linie 58,9 / bod 62,0). Pokles z 61,7 % (Sez. 137) = **vědomý důsledek E3** (rejection sampling balvanů =
> ISOM-korektní nepřekrývání; Velbloud nejskalnatější −2,4; plocha/linie beze změny). **Žebříček děr:**
> **508 / 403 / 409 / 202** (417/418/419 vytěženy pseudo body Sez. 136-137). **KOMPAS `--table` má nově
> sloupce `zdroj · věrohodnost · provedení`** (Sez. 138, registr `KOMPAS_SOURCE` 51 kódů + `_provedeni` AUTO
> ze share orig:gen). Další velká strukturální páka zůstává Png2Line; KPI je kompas děr, ne cílová funkce.
>
> **Plošná + liniová páka z ČÚZK je VYČERPANÁ** (potvrzeno 4× Sez. 99-102: 403 granularitní propast +0,1, 508
> smíšený podstřel +0,34, 404/407/409 = vegetace gate). Co generátor nenakreslí, reconstructor se NIKDY nenaučí →
> pokrytí = strop tréninku (memory `generator-coverage-is-the-ceiling`). **Historie baseline (43 %→59,1 %), analytické
> cuty (plošný strop 54 %), kompas a vyvrácené páky 403/508: DONE Sez. 94-102 + diáře.**
- [ ] *(doladění → nález uživatele Sez. 118 „zubaté ploty")* **Plot 516 kolem velké privátní oblasti (520) je ZUBATÝ** ({A}, ~6 zbytečných
  zubů na velkém pozemku). Mechanika: `_dissolve_mask_to_polys(olive_ruian_img)` → outer ring → `_rdp(eps = FENCE_SIMPLIFY_M=5 m)` →
  `_draw_fence_line` (gen ~2496-2506). RDP 5 m zuby nespolkne. **Řešení (volba uživatele „zjednodušit na vnější hraniční body"):** primárně
  **zvýšit `FENCE_SIMPLIFY_M` 5→8–10 m** (původní Sez. 98 dořešení — tohle je ten „kdyby přímost nestačila"). Pokud hluboké zuby přetrvají:
  morfologické **closing seed masky** PŘED dissolve (vyplní úzké zářezy mezi RÚIAN parcelami). **Oponuji convex hullu** (uživatelovo „vnější
  body" by mohl znamenat hull) — ztratil by legitimní konkávní tvary velkých pozemků (zálivy) a mohl by plotem pohltit sousední ne-privátní
  oblast. RDP/closing drží tvar, jen hladí. Riziko (Sez. 98): vyšší práh komolí malé bloky → ladit s `FENCE_MIN_AREA_M2` na očích.
- [ ] *(feature, vrstevnice, nález uživatele Sez. 116)* **102.1 zdůrazněná (index) vrstevnice na násobky 50 výškových metrů** —
  do mapy přidat zesílenou vrstevnici ISOM 102.1 na hladinách dělitelných 50 m (orientační čára nadmořské výšky). Dnes se kreslí
  jen 101 (běžná). Index contour = každá N-tá zesílená; uživatel chce kotvit na absolutní násobky 50 m, ne každou N-tou od základu.
- [~] *(vizuál, ořez `cut.py`, nález uživatele Sez. 118; **SINGLE-RUN HOTOVO Sez. 138**)* **Neohraničovat tučnou čarou odstřižené hrany ploch s neproniknutelnou hranicí** —
  když `cut_area` ořízne plochu s tučným černým obrysem (521 / 520 / lom / voda 301), OOM vykreslí border kolem CELÉHO prstenu → obrys i na
  umělou řeznou hranu. **HOTOVO single-run Sez. 138:** `cut._emit_area` detekuje neatline úsek (`_on_clip_edge`), přerotuje ho na **uzavírací
  segment** + flag **16** (hole bez close bitu 2) → OOM border na řezné hraně nekreslí, výplň drží (probe v2 ověřen uživatelem; `omap_raster`
  dělí ringy na bitu 16 → area_labels netknuté). **ZBÝVÁ multi-run limit:** plocha dotýkající se hrany na **2+ místech** ({X} Novina: voda 301
  se dvěma horními úseky) → potlačí se jen NEJDELŠÍ úsek, ostatní zbydou. Mid-ring hole NEJDE (probe v3 ověřen: rozseče path → bez výplně; OOM
  hole = oddělovač pod-cest, ne border-gap). **ZAŘAZENO JAKO FOKUS (volba uživatele Sez. 140)** — nová instance: **roh** Borný (Máchovo
  jezero v levém dolním rohu = DVA řezné úseky, svislá + vodorovná hrana mapy; `_neatline_to_close` vezme jen nejdelší, druhý zbyde; spojit
  nejde — uzavírací segment je přímka → diagonála přes roh by uřízla výplň). **Řešení = uživatelův algoritmus doslova:** (1) ořízni mapu;
  (2) prochází-li řez ohraničenou plochou, hranice v místě řezu BEZ obrysu. Implementace = **oddělit výplň od obrysu** v template: ohraničená
  plocha (301/520/521/lom) = **fill-only symbol** + **samostatný obrysový liniový symbol** (301 břeh / 520·521·lom obrys); `cut._emit_area`
  emituje obrysovou linii JEN na segmentech mimo `_on_clip_edge` (reálné břehy) → funguje pro libovolný počet řezů (roh/multi-run) automaticky.
  Verify vizuální v OOM. Vlastní sezení (středně velký kus, template + cut emit + per-symbol fill/border split).
- [ ] *(KPI kvalita, nález uživatele Sez. 140 — gen „bohatší" než originál sken)* **Přestřel hustoty symbolů na skalnatých mapách.**
  Vizuální dojem z overlay (Rovné skály): gen má víc objektů než kartografův originál. Hlavní podezřelí: **balvany 204/210**
  (gen sype z DMR sklonu + pseudo injekce; kartograf generalizuje) + **pseudo body 417/418/419**. KPI dopad: přestřel KPI SNIŽUJE
  (`min` ukrojí přebytek) → oprava = páka (paměť [[kpi-fill-undershoot-dilutes]]). **Measure-first:** Livelox je raster (KPI nejde) →
  změřit per-symbol přestřel na `resources/` měřicích mapách (Bedř/Blatná/Velbloud, `.pgw`); kde gen přestřeluje, kalibrovat hustotu dolů.
- [~] *(vytěžení, nové body, nález uživatele Sez. 140; **525/527/531 HOTOVO Sez. 141**, 523.1 carry)* **Bodové symboly
  523.1 / 525 / 527 / 531.** **HOTOVO Sez. 141:** 527 Fodder rack (krmelec) / 525 Small tower (posed) / 531 Prom. man-made x
  jako **pseudo man-made body** (ZABAGED je nevede → čistě pseudo na měřenou hustotu, izomorf veg 418/419;
  `_generate_pseudo_points` zobecnění, render Λ+noha / ⊤ / černý X). Měření crosswalk-aware (paměť
  [[isom-dual-numbering-oom-ocad]]): medián 527 ~7,7/km² (5/5 map), 525 ~1,1, 531 ~1,3. **ZBÝVÁ 523.1 Ruin min
  size — ODLOŽENO** (volba uživatele Sez. 141): měřením marginální (1/5 map, 1 objekt Velbloud) + invazivní
  (buildings vrací area, 523.1 je point → cross-pipeline změna signatury/render/omap) → reálná páka ≈ 0. Když se
  bude dělat: footprint < ISOM min 0,8×0,8 mm (144 m²) → bodový čtverec 523.1 místo zanikajícího obrysu 523.
- [ ] *(KPI verify, carry Sez. 141 — ntbhej RAM limit)* **Přeměřit KPI/KOMPAS dopad pseudo bodů 527/525/531** na
  HAL3000/mrkla. `measure_dod` na ntbhej padá na `ArrayMemoryError` (`map_gt.segment_gt` separace skenu Bedřichovky
  3,4 Mpx × 13 barev; known >~100 Mpx limit) + chybí Velbloud.pgw. Ověřit, že 3 nové man-made typy zaplnily KOMPAS
  díry (orig>0 z crosswalku) + dopad na KPI (60,7 % Sez. 138).
- [ ] *(robustnost měření, nález Sez. 141)* **`compare_isom.detect_version` — trojí realita místo binární.** Dnes
  vrací jen „2000"/„2017-2" (podle Building 526/521), ale existují TŘI číslovací sady: ISOM2000 / OOM-2017 (524-531) /
  OCAD-2017 (535-540, Building=526 → mylně detekováno „2000"). Funguje náhodou pro OCAD mapy (crosswalk pravý sloupec
  = OCAD), ale **Soví vrch (OOM-2017, krmelec kóduje přímo 527) → `resolve(527,"2000")={520}` = nesmysl**. Soví vrch
  NENÍ v default KPI sadě (Bedř/Blatná/Velbloud) → headline nezkresluje, ale past. Fix: rozlišit OOM vs OCAD set
  (např. dle `<symbols id="OCD">` nebo přítomnosti 535-540) → správné crosswalk routování. Paměť [[isom-dual-numbering-oom-ocad]].
- [ ] *(vytěžení/Etapa 2, nález uživatele Sez. 140)* **Oplocenky = uzavřené linie 516–518.** ZABAGED ploty NEvede (doložený SKIP Sez. 57,
  katalog sekce 11) → data gap. Dvě cesty: **(a) pseudo** (Etapa 1) — umístit oplocenky procedurálně na okraje lesa/školky (dekorace,
  losovaná hustota); **(b) Png2Line ze skenu** (Etapa 2, za fázovou závorou) — detekce uzavřené smyčky plotu = JINÝ přístup než watercourse
  (topologie uzávěru) + dashed 516 už narazila na doménový gap (Sez. 133).
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
- [~] *(Sez. 110 stahování + Sez. 111 GT HOTOVO, kurace/split carry)* **Korpus + GT na ntbhej.** `livelox batch` stáhl
  **57 → 264 map**, GT **264/264** (Sez. 111 chunked classify odblokoval 6 obřích). **ZBÝVÁ:** (a) **kurace + split
  rozhodnout** — `_curation.json`/`_split.json` na ntbhej NEJSOU (gitignored, ruční vizuální tagy Sez. 71 žijí na HAL3000)
  → buď **zkopírovat z HAL3000** (zachová tréninkový split, doporučeno), nebo auto-`curate`+`split` tady (rozejde se
  s HAL3000). Pozn.: `build_pair`/trénink je stejně CUDA-vázané (HAL3000) — ntbhej korpus slouží měření / `build_pair`
  E2E ověření / rozšíření tréninkového setu po přenosu na HAL3000.
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
    dnes produkuje čistý `rgb.png`; degradace je on-the-fly v loaderu. **Branžež verify + noční batch HOTOVO Sez. 90:**
    `build_pair(1005002)` worst-case 93 Mpx **357 s** (downscale drží), `_map_affine` na rotovaném quadu lícuje
    (vizuál); sanity `batch 10` 9/9 OK **~51 s/mapa** → noční `build_pairs batch` 207 ČR **SPUŠTĚN** (resume). Vedlejší:
    `map_gt.segment_gt` nezvládne >~100 Mpx (20 GiB; korpus malý → neakutní).
  - [x] **(verify dluh Sez. 84) Ověřit proc baseline 65 — HOTOVO Sez. 85** (`.omap objektů 65`; `_group_holes`
    bbox prefilter behavior-preserving, regrese 0).
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
    Y-pipeline `omap_raster.py` (**17 ISOM kódů + pozadí = `N_AREA 18`**, statický z-order, díry per-objekt) → loader/tile/train
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
  - [~] *(registr rozšíření, IDEAS B1; DETEKCE HOTOVO Sez. 128, decoupling)* bodové třídy **417/419** přidány do
    `POINT_CLASSES` (Png2Point) — registr generalizován (kind/color/n_range/**peak_thr**), zelený prstenec 417 + X 419
    s bílou knockout svatozáří (verify ISOM 2017-2). Synt medián 3 seedů mF1 0,827; **reálný transfer (eval_real, audit
    A1): 419 SILNÝ 0,67–0,76, 417 0,48–0,57** (Sez. 129 práh + Sez. 135 řidší injekce). **ZBÝVÁ:** (a) **KPI pseudo injekce do
    generátoru (půlka 2) — HOTOVO Sez. 136** (volba uživatele: pseudorealistická dekorace, ne KPI honba): `_generate_pseudo_veg_points`
    (princip kamenů, 417 doplnit řídký ZABAGED na reálnou hustotu / 419 čistě pseudo; mimo voda/skály/budovy/cesty/zpevněné +
    ISOM rozestup). KPI 58,6 → 61,1 % (POKRYTÍ; proporčně Goodhart-citlivé — vědomě, měřítko zůstává reálný transfer);
    (b) **417 precision — HOTOVO: Sez. 129 symptom-práh + Sez. 135 PŘÍČINA** (cause-fix: injekce
    ⌀40/dlaždici = 2–3× nad reálnou hustotou ~12–20 → `inject.py n_range (20,60)→(10,30)`; re-trénink `s135_417sparse_s0`
    synt 417 F1 0,90 R0,98 / **real F1 0,48–0,57**);
    (c) **418 Prominent bush — pseudo injekce do generátoru HOTOVO Sez. 137** (zelený plný disk, stejná mašinérie jako
    417/419 → třetí třída do `_generate_pseudo_veg_points`; čistě pseudo, hustota měřena ~17,8/km² → `(8,26)`; `USED_CODES += 418`;
    KPI 61,1 → 61,7 %, KOMPAS orig 178/gen 90 ✓; POZN. 418 mimo Png2Point scope = generátor kreslí pro budoucí trénink);
    (d) pak 109/111/112/115.
  - [x] *(reálný transfer, doménový gap; A1.b HOTOVO Sez. 121 — detail DONE)* změřena detekce 204/210 na REÁLNÉM
    kartografově skenu (`model/png2point/eval_real.py`): **204 přenáší (recall 0,66–0,67, F1 0,38–0,68), 210
    kolabuje (F1 ~0,04)**. Injekční trénink přenáší na výrazné symboly (plný kruh 204), ne na pole drobných teček (210).
  - [~] **`Png2Line` — TŘETÍ funkční reconstructor, KROK 1 HOTOVO Sez. 130-131** (přístup ROZHODNUT Sez. 130,
    IDEAS „Png2Line — segmentace + odložená vektorizace"). Per-class segmentace linií (U-Net izomorfní s
    `png2area`, GT z `.omap` rasterizace, **dilatovaná GT** proti rozpouštění tenkých linií). **Krok 1 watercourse
    304/305 (`N_LINE=2`): plný trénink test mIoU 0,774 / IoU 0,55** (Sez. 131); **reálný transfer PROKÁZÁN**
    (`model/png2line/eval_real.py`, completeness 0,90–0,96 = trasuje reálné toky, žádný kolaps; slabina precision).
    **conf_thr práh 0,95** (registr `LineClass`, izomorf `peak_thr`) srazil přestřel: real IoU 0,251→0,409,
    F1 0,659→0,773. **(a) vektorizace maska→polyline HOTOVO Sez. 132** (`model/vectorize.py` skeletonize→graf→RDP +
    `rasterize_polylines`; `scan_px_to_paper` inverze georef SSoT; `model/png2line/vectorize_omap.py` predikce→
    vektorizace→`.omap` klon georef + měření; **ztráta ΔIoU −0,039 / ΔF1 −0,028** = drží strukturu; +scikit-image;
    `tests/test_vectorize.py` 6 testů; Buschdörfl NĚMECKÁ Livelox 98 % vektoru na modrých tocích).
    **Krok 2 dashed 508+516 ZKOUŠEN A ZAVRŽEN Sez. 133** (DONE): měření (eval_real + conf_thr sweep) doložilo
    DVA negativní nálezy — 508/516 doménový gap (completeness strop 0,14–0,22, prahem neřešitelný, vzor 210)
    + multi-class zhoršil watercourse (thr 0,99 jen 0,311 vs krok 1 0,409). Revert na N_LINE=2. **ZBÝVÁ:**
    (b2) **krok 2 v2 — dashed JINÝM přístupem** (ne přidání třídy): verify gen renderu dashed vs realita /
    dashed-specifická augmentace (přerušení v X) / morfologické přemostění přerušení před segmentací;
    (c) **gap-bridging u junkcí** (vektorizace tříští toky na uzlech — Velbloud 197 / Buschdörfl 143 polyline;
    crude junction handling). Reuse `tile`/`dataset`/`degrade`/`purple`. CUDA-vázané (HAL3000/mrkla).
  - [ ] *(follow-up Sez. 134; poledníkový detektor HOTOV + OVĚŘEN — DONE Sez. 134)* **Napojit `north_grid` filtr do
    produkční cesty + ověřit na 2. mapě.** Detektor `model/png2line/north_grid.py` (Codex `ac953ab`, dotažen Sez. 134:
    data-driven rozestup) ověřen na Buschdörfl (5-liniový grid 77,4°, 27 poledníků odstraněno, vody zachovány); gen render
    poledníky nekreslí = doménový gap. **ZBÝVÁ:** (a) dnes filtr volá jen `vectorize_omap.main` (verify nástroj) — zvážit
    napojení do `eval_real`/budoucí inference; (b) ověřit na 2. reálné mapě s poledníky (jediný doložený případ = Buschdörfl);
    (c) edge případ černé poledníky (watercourse je nebere, ale budoucí liniové třídy ano).
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
- *(ARCHIV Sez. 79)* **Krok 5 (zlepšení `ortofoto→runnability` baseline)** = doložená slepá ulička, nahrazena
  `generator()` predict částí; archiv `model/runnability/`. Případné budoucí nápady (ablace DMR-sklon, recency korpus)
  jen kdyby se k ortofoto vstupu vrátilo. Detail DONE/architecture.
- [ ] *(integrace, deferred Sez. 76)* **ČR/DE filtr do `kept_dirs`** — dnes `_cz_filter.json` je jen měřicí
  artefakt (nemění `keep`). Tréninkový loader jede přes `split.dirs_for()` (už ČR-only), takže neakutní;
  doladit, až loader vznikne (krok 4) — buď číst split, nebo přidat filtr do `curate.keep`.

- [ ] *(kurace follow-up Sez. 71, před tréninkem)* **recency osa** — `meta.json` neukládá datum eventu → časový
  nesoulad vstup(ortofoto recent)×GT(starý) NELZE měřit. Uložit datum eventu do `meta.json` při `download_map`
  (z `event["timeInterval"]["start"]`) + volitelně doplnit re-dotazem na existující 268. Pak řez „posledních N let".
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
- [ ] *(DRY dluhy, %AUDIT:CODE Sez. 135 — neopravené, evidováno pro fázi A)* **Sdílené moduly mezi reconstructory.**
  Audit našel dozrálé DRY duplicity, vědomě NEopravené teď (riziko v živém kódu reconstructorů / fáze B sys.path;
  „generalizuj s důkazem" splněn — 3.+ konzument existuje, spouštěč extrakce = přechod na balík fáze A):
  - **tiling** `png2area/tile.py` ≈ `png2line/tile.py` (`make_preview`/`_positions`/`_crop`/`_median_freq_weights`/
    `_write_tiles_json`) — v kódu dokumentovaný dluh „extrakce až 3. konzument"; `png2line` NYNÍ existuje = naplněno.
  - **eval_real downscale** (pgw→src_mpp→resize, ~5 ř.) duplikováno 4× (`png2{area,point,line}/eval_real.py` +
    `vectorize_omap.py`) → helper do `mpp.py` (kde žije `CANONICAL_MPP`).
  - **`_map_area_mask`** identický v `png2point`+`png2line` eval_real (prahy 25/200) → sdílet (png2line už
    importuje `paper_to_scan_px` z png2area, cesta existuje).
  - **`PX_PER_MM`/`MAP_SCALE`** duplikát `inject.py`+`purple.py` (oba importují `CANONICAL_MPP`) → `mpp.py` SSoT.
  - drobné (fáze A, komentář drží sync): `_point_in_ring` 2 verze v `generator.py`; `BRIDGE/TUNNEL 750µm`
    `generator`↔`omap_export`.
- [ ] *(no-silent-fallback, NEJISTÉ, %AUDIT:CODE Sez. 135)* **`split.py:72` tichý default `nw.get(d.name, 1.0)`** —
  mapa chybějící v `_cz_filter.json` je bez varování „cizí" → po rozšíření korpusu se tréninkový pool tiše zmenší.
  Nízké riziko (default konzervativní), NEopraveno (riziko regrese ve splitu = reprodukovatelnost mIoU). Doladit:
  hlásit `cid` chybějící ve filtru, až bude loader sahat na potenciálně stale `_cz_filter`.
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
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo). `connectors/`+`generator/`+
  `model/` jsou sdílené složky mimo sandbox (krok B→A), ale pořád sys.path skripty, ne balík; spouštěč „balík" otevřen.
- [ ] První aplikační kandidát UC3 de-purple vs jiný — detail IDEAS. Pozn.: po ROADMAP je de-purple součást
  `Rekonstruktor()` etapy (zmrazena za fázovou závorou, jsme v `Generator()`).

## Backlog (vzdálené, nezačínat)
- [ ] `Rekonstruktor()` etapa (sken→.omap) — za fázovou závorou ROADMAP, až bude KPI/KOMPAS dost
- [ ] UC3 de-purple / UC4-II inspired aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
