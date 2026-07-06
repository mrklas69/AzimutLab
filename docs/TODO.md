# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[!]` priorita. Hotové položky patří do `DONE.md`/diary;
v aktivních seznamech nepoužívej `[x]`.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## Audit supervisor (2026-07-02) — námitky → úkoly
Zdroj + plný kontext a doklady: **`docs/AUDIT_SUPERVISOR_260702.md`** (Opus 4.8, 4 verifikační agenti
proti kódu). **260621-A1 (KRITICKÁ, checkpoint↔scope mismatch) definitivně VYŘEŠENA.** Vyřešeno v
tomtéž sezení bez CUDA (docs-only + testy): **A3** `_curation.json`/`_split.json`/`_cz_filter.json`
committed (`5d4dc5b`), **B1** AREA_ZORDER/301 invariantní testy (`032cce9`), **B2** `isom_scan/` do
README+CLAUDE.md (`c6397aa`), **B4a/b** `run_kpi` MAPS label + `requirements-train.txt` split (`ab4de2d`).
**B6 VYŘEŠENO Sez. 180 (%CALIBRATE):** `DIARY.md` index 144–179 zkrácen na hooky + root-cause fix —
`CLAUDE.md` Png2Point bullet zkrácen (16 sezení nabobtnalý), `GLOSSARY.md` KPI changelog nahrazen aktuální
hodnotou + `[[Sirotek]]` definicí, `TODO.md` smazán 4651znakový duplicitní stavební log (už v `DONE.md`),
`docs/PROMPTS.md` %END rozšířen o pravidlo „definiční docs nesou stav, ne historii" (viz DONE).

- [!] *(A1; VYSOKÁ, rozhodnutí uživatele)* **Exit-kritérium fázové závory (KPI ≥ 85 %) je sankcionovanými
  prostředky nejspíš nedosažitelné.** ČÚZK plošná+liniová páka „VYČERPANÁ" (potvrzeno 4×), gen=0 díry jsou
  systematicky data-gate (Sez. 177 `DATA_GATE_CEILING`). Jediná zbývající páka = scan-mining, blokovaná na
  ruční GT uživatele (311/313 čeká; mapfield Velbloud/Blatná/Soví vrch VYŘEŠENO Sez. 179 — viz DONE).
  Doporučení auditu: buď (a) operacionalizovat práh „KOMPAS téměř plný" = „všechny NE-data-gate díry v
  `ok`" a rozdělit headline na ČÚZK-dosažitelnou + scan-mining složku, nebo (b) naplánovat ruční GT jako
  explicitní blocker sezení, ne odkládaný carry. Přestat vydávat nulová KPI sezení za progres.
- [~] *(A2; VYSOKÁ, CUDA fokus; ČÁST HOTOVO Sez. 179 — 210 collapse zkoumán, NEpromováno)*
  **`eval_real` (vrcholová metrika) zamrzlá ~16 sezení.** Checkpointy naposled Sez. 156/162.
  **Sez. 179: 210 Stony ground diagnóza + izolovaný experiment** — verify-against-source ukázal
  210.1 dot ISOM-spec 150 µm ≈ 2,25 px na `CANONICAL_MPP` (rozlišovací strop, ne training bug).
  Jednotřídní retrain @2× jemnější MPP (0,665): recall vyřešen (0,16–0,22→0,94–1,00), ale reálný
  transfer SMÍŠENÝ (Blatná +143 %, Velbloud −53 %, Bedřichovka beze změny — jemné rozlišení odkryje
  mapa-závislý skenovací šum) → **NEPROMOVÁNO**, kanonický model netknutý. Detail DONE/diary Sez. 179,
  paměť [[png2point-210-resolution-vs-noise-tradeoff]]. **ZBÝVÁ:** 404/407/409 halucinace (jiný přístup
  než Sez. 165) nebo class-balanced expansion 208/501/301, případně hard-negative mining pro 210
  (reálná skenová textura jako trénovací negativ — další CUDA investice, nejistý výsledek).
- [ ] *(B3, odloženo do fáze A)* **DRY: tiling 3× (`png2area/tile.py` ≈ `png2line/tile.py`, ~42 % liší) +
  `MAP_SCALE=10000` opsáno 3× (generator.py/inject.py/purple.py).** Audit sám: spouštěč extrakce = přechod
  na balík (fáze A), do té doby komentářový sync stačí. POZOR: `PX_PER_MM` má DVĚ legitimně různé hodnoty
  (generator 4,59 vs model 7,52, jiný `TARGET_MPP`) — NESJEDNOCOVAT naslepo (paměť `canonical-mpp-tile-resolution`).
- [ ] *(B5, marginální)* **`resources/isom/index.json` kurátorovaný + licence 113 SVG.** Committed je jen
  `index.schema.json` (kontrakt) + builder; provenance/licence 113 SVG „unknown". Začít živými bodovými
  třídami (204/210/417/419) při první příležitosti — dokud katalog není aktivní UC2 zdroj, nízká priorita.

## Sezení 165 — carry / follow-ups
- *(fokus B UZAVŘEN NEGATIVNĚ Sez. 165 — DONE)* **Guard:** vzácnou pattern třídu (409/208) NEjde naučit jen víc daty
  (retrain `s165` REGREDOVAL reálný transfer, halucinace 407→409) → class-balance/oversampling, ne slepý retrain; nemrhat
  CUDA oknem. Generator 409 gate ZŮSTÁVÁ (KPI+). Paměť [[rare-pattern-class-retrain-regresses]].
- [ ] *(isom_scan %AUDIT:CODE opt-iny, Sez.165 — measure-first, MĚNÍ výstup detektorů)* **D2/D3 component-leak fix +
  D4 detector name-SSoT.** Fork je nechal jako dokumentovaný opt-in v `points_common` (label-izolace přepíše skóre,
  SSoT názvy přepíšou `name`). Aplikovat jen s měřením dopadu na kvalitu detekce, ne slepě. + **D7** `gt_ui` „celá
  paleta" docstring vs frontend theme-filtr = **UX rozhodnutí uživatele** (filtr je možná záměrný fokus „čistá
  pracovní paleta", nebo bug proti recall-first). + `gt_ui`→`symbol_index` palette loader (marginální, gt_ui potřebuje svg filename).
- [ ] *(benchmark fér, Sez.165)* **ISOM-scan re-run iter3 pro Opus + ChatGPT5.5.** Copilot i ChatGPT MAJÍ iter3
  (`results.csv` `build=iter3-coached`); zbývá **Opus 4.8** (Sez.146 jen 1 uncoached) + **ChatGPT5.5** (starý 0,50 běh) →
  re-run pod stejným iter3 pravidlem pro fér leaderboard. Ne-CUDA (uživatel pustí modely, já skóruju). Nález: headline
  `point_F1` (bodová lokalizace) je zeď i po coachingu (ChatGPT recall 1,0 / point_F1 0,0) → klíč = ruční GT (viz níže).
- [~] *(isom_scan candidate quality; ČÁST HOTOVO Sez. 170 — excentricita+`open_px`+`reject_collinear_runs` ve
  `points_common` default-off, 109 measure-calibrated F1 0,65, DONE)* **ZBÝVÁ geometrické diskriminátory bodů:**
  (a) circularity `4πA/P²` + convex-hull solidity (jiná metrika než ecc — pro balvany 204/210 černou maskou);
  (b) skeleton-endpoint topologie (⊤ 525/526 = 3 konce, × 530/531 = 4, Λ 527 = 2-3 → rozliší man-made glyfy
  specifičtěji než shape_f1). Measure-first na review manifestu. HoughCircles = IDEAS (marginální vůči CenterNet).
- [~] *(benchmark robustnost; INFRASTRUKTURA HOTOVO Sez. 168/171 — `mark_isoms` 21 kódů, `gt_from_markers`→hybrid GT v2,
  master 187 bodů / 21 kódů, `score` čte `_benchmark_version`, zeď point_F1 prolomena ChatGPT 5.5 0,269; DONE)*
  **ZBÝVÁ: re-run modelů na v2 GT** — Opus 4.8 / ChatGPT 5.5 aktuálním promptem → fér leaderboard (staré Sez. 146 běhy
  = 2-bodový úkol, orientační dolní odhad). Ne-CUDA (uživatel pustí modely, já skóruju). Caveat: 1 sken Branžež,
  subjektivita balvan-vs-sráz. Anti-Goodhart, dokládá recall ([[isom-gt-factory-tool]]).

## Audit supervisor (2026-06-19) — námitky → úkoly
Zdroj + plný kontext a doklady: **`docs/AUDIT_SUPERVISOR_260619.md`**. Tento audit navazuje na
průlom Sez. 146/147: classic-CV práce nad reálným skenem je legitimní `Generator() / scan mining`,
pokud krmí barvy, masky, symbolové kandidáty nebo KOMPAS.

- [~] *(260619-A1; Generator()/scan mining)* **Zakotvit scan mining jako aktivní podtah Generator().**
  ROADMAP už říká, že sken→barvy/masky/symbolové kandidáty/KOMPAS signály patří do Etapy 1. Pracovní
  struktura je rozdělená: `isom_scan` textový harness/GT manifest je verzovatelný, copyright rastry/PDF/runs
  zůstávají ignorované, `tools/separate_scan_colors.ps1` existuje jako první obecná utilita. `isom/`
  už drží symbolový SVG index + capability registry (real/mixed/pseudo/mapper_scan), `omap_export.USED_CODES`
  i KOMPAS jsou na něj napojené. První KOMPAS zásah hotov: 403 separace dostala per-class min-area 60 px.
  Navazující kalibrace 527 na stejné 3-map sadě zvedla headline KPI na **62,5 %**; přesun
  `Cesta typcesty_k=025` do 508 kanálu ji pak zvedl na **63,3 %**. Sez. 152 přidala scan/pattern
  area třídy 404/407/409, rozšířila liniový scope na 306/309/508* a po kalibraci 204 posunula
  headline na **65,8 %**. Sez. 154 rozšířila `isom_scan` na per-ISOM point kandidáty:
  525/527/531 z černých komponent, 109/111/112/115 z hnědé kresby, 417/418 ze zelené kresby,
  obecný review manifest a `.omap` export. Capability registry je pořád jen `classic_cv_poc`;
  povýšení na live mapper-scan smí přijít až po kuraci a metrice.
- [!] *(260620-Buschdörfl; Generator()/scan mining)* **Scan-transfer bodových a liniových gapů ze skenu.**
  Test `maps/Buschdörfl/Buschdörfl.omap` ukázal, že mapařský sken nese prakticky důležité symboly, které
  ZABAGED nedodá a pseudo je pro ně slabší zdroj. Hotový lokální průchod: 525/527/531, 111/112/115 a 417/418.
  Hamr na Jezeře ověřil přesné `602` markery pro `109`; negativní příklady `108` potvrdily nutnost
  per-symbol tvarových filtrů (`--min-area 25` u 109). **Zbývá:** hlavní modré pointy `311/312/313`,
  další černé bodové skupiny, drobné 301/308/310 vodní/mokřadní plochy a uzavřené 516/517/518 oplocenky.
  Výstup má být kurátorský manifest + pracovní `.omap` kandidáti, nejdřív na Buschdörfl/Hamr, potom ověřit
  na jedné české mapě. Per-ISOM calibration ledger je zavedený v `isom_scan/calibration_manifest.json`.
  **Stav 311/312/313 (ověřeno Sez. 177 z manifestu): detektor `water_points_poc.py` UŽ běžel** — 312
  `candidate_calibrated` (recall 1.0, 1 GT marker), 311 = 4 kandidáti ale **0 pozitivních GT** (uživatel je
  ve 2. průchodu nepotvrdil), 313 bez kandidátů i GT. **Blokuje tedy RUČNÍ pozitivní GT (uživatel) / jiná mapa,
  ne kód.** Stejně 417/418 (`unreviewed`) čekají na review verdiktů. **Vysoká priorita před dalšími ZABAGED
  honbami:** tahle data jsou v mapářském skenu, ne v ČÚZK.
- [!] *(260619-A4; Goodhart)* **Pseudo hustoty měnit jen přes crosswalk-aware měření na stejné sadě.**
  527 přestřel je na kanonické sadě opravený (103→3, KPI 62,0→62,5); 508 `Cesta typcesty_k=025`
  přesun je ověřený KOMPASem (508 `ok`, headline 63,3); **210 Stony ground opraveno Sez. 166** (`PSEUDO_STONY_FIELD_PER_KM2
  12→7` přes `measure_dod --table` před/po na 3-map ntbhej, KPI +1,5 pb, 210→ok — vzorová governance). 531 zůstává
  kandidát (ale RNG-křehký, viz „nezávislé RNG streamy" níže). Pro každou pseudo vrstvu držet zdroj, hustotu/km², mapovou
  sadu, datum měření a důvěryhodnost; změnu povolit jen s `measure_dod --table` před/po na stejné sadě.
## Audit supervisor (2026-06-12) — námitky → úkoly
Zdroj + plný kontext a doklady: **`docs/AUDIT_SUPERVISOR_260612.md`** (námitky A1–A7, připomínky B1–B7).
Příští audit (dle `docs/AUDIT_SUPERVISOR_PROMPT.md`) kontroluje stav položek VYŘEŠENO/TRVÁ/ZHORŠENO —
při dokončení přesunout do DONE **s kódem námitky** (A1, B4, …), ať je dohledatelné.

- [~] *(A2; phase-2 — (a) purpura HOTOVO Sez. 123 + Png2Area re-trénink Sez. 124; Png2Point re-trénink Sez. 125 ODHALIL NESTABILITU; (b) geometrická část ZMRAŽENA 260619-A5)* **Purple-course + geometrická augmentace.**
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
  purpuru doměřit až na stabilním základě. **(b) Geometrická půlka je po ROADMAP a auditu 260619 zmražená
  phase-2 práce** (sklad/ohyb/warp X i Y zároveň, vedle D4). Neotevírat jako aktivní fokus v etapě
  `Generator()`, pokud nebude explicitní real-scan metric trigger; technická poznámka pro budoucno:
  warp Y nejvýš nearest-neighbor, jinak mezi třídami vyrobí smíšené pixely.
- [ ] *(A3; měření HAL3000)* **KPI proti Goodhartu.** (a) Úspěch fáze `generator()` vázat na A1 benchmark;
  KPI zůstává kompas děr, ne cílová funkce — propsat do KPI bloku níže + `architecture.md`. Pravidlo pro
  každou další KPI práci: „pomůže to reconstructoru na reálném skenu?" (b) Rozšířit referenční sadu:
  KPI potřebuje VEKTOROVOU `.omap` (počty objektů) — Livelox je raster-only a referencí být nemůže;
  rozšíření = získat 3–5 dalších kartografických `.omap` (kluby/vlastní mapy) do `resources/`.
  (c) Zvážit oživení per-symbol prostorové metriky (`compare_real_vs_gen.py`, stale-drop Sez. 69) jako
  negamovatelný druhý pohled — až po (a), neotvírat metodologickou frontu navíc.
- [ ] *(A4; taxonomie VYŘEŠENA ROADMAPem + Sez. 139; zbývá jen kosmetika)* **Kosmetická revize statického 5-UC DAGu**
  v `architecture.md` — dorovnat APP boxy de-purple (UC3) a Pic2Omap absorpce (UC4-III) na osu `Generator()`→`Rekonstruktor()`. Neblokuje.
- [ ] *(A5; kdekoli, bez CUDA)* **5 invariantních smoke testů** — automatizace dnešních ručních rituálů,
  NE plná test suite (over-engineering proti fázi B): (1) noise-mode checksum (proc 65 byte-identický);
  (2) golden Šulcák 48 polygonů / 2,56 ha, tol ±2/±5 % (potřebuje ČÚZK fetch nebo `.dmr_cache`);
  (3) konzistence `AREA_ZORDER` ⊆ symboly v `template_classic.omap` ∧ kódy zapisované `omap_export`
  (chytá 301/301.1 typ bugu staticky; Sez. 175 částečně kryje `test_omap_symbols.py`);
  (4) `cut.py` mini-verify primitiv (případy Sez. 114 zakonzervovat; Sez. 175 kryje chybějící fill/border symboly);
  (5) mini `build_pair`/rasterizace fixture → Y má nenulové px pro každý area kód přítomný v `.omap`
  (chytá 301/301.1 dynamicky). `tests/smoke.py` existuje a `tests/test_smoke.py` ho chrání před těžkým
  auto-spuštěním; zbývá golden Šulcák/build_pair fixture + %END připomínka „měnil-li se kód: spusť smoke".
- [ ] *(B3, rešerše bez kódu)* **Livelox ToS — TDM opt-out check.** EU DSM čl. 4 připouští opt-out
  nositele práv ze strojové TDM výjimky; deep research Sez. 67/110 řešil dostupnost dat, NE opt-out.
  Ověřit Livelox podmínky z tohoto pohledu; do vyjasnění: checkpointy modelů privátně (možný derivát),
  žádné výřezy Livelox map v commitovaných souborech/docs.
- [ ] *(B1, až bolí)* **Sdílený modul pro string-level `.omap` operace.** `cut.py`/`gen_backgrounds.py` jsou správně
  moduly (monolit nepřikrmovat), ale string-regex místo XML parseru je křehké — každý nový `.omap` zápis musí myslet, ať ho
  cut/backgrounds nerozbije (Sez. 109: clip NESMÍ přes ET kvůli inject). Extrahovat konvenci string-`.omap` operací na jedno místo.
- [ ] *(B7, proces)* **Deep research fázovat.** 103 agentů uťatých session limitem (Sez. 110) = nehospodárné. Příště:
  scout → cílený fan-out, průběžně sklízet do RESEARCH.md, ať i uťatý běh zanechá plnou stopu.

*(ChatGPT audity 2026-06-14 / Sez. 125 — DOCS+CODE: nálezy vypořádány Sez. 125-127, zdroje
`AUDIT_DOCS_260614.md` / `AUDIT_CODE_260614.md` archivovány Sez. 139.)*

## %AUDIT:CODE (Sez. 143/175) — nálezy → úkoly
5 paralelních agentů + ruční verify proti zdroji (18 103 LOC). **OPRAVENO Sez. 143 (quick wins):**
C1 separate RAM (row-chunk, odblokuje měření na ntbhej) · D1 USED_CODES +416/416.1 · D5 `_line_line_pt`
guard · D7 stale 0,537→0,683 · K1 Png2Polygon→Png2Area · K3 530/531 rozlišení · K4 docstring 509 ·
K5 mrtvý `_TEMPLATE`. **Sez. 175:** D2 warning místo tichého defaultu `compare_isom.detect_version`, D3 sdílený
`omap_symbols.parse_symbol_ids()` + hlasitý fill/border split vody, D4 ArcGIS paging přes `exceededTransferLimit`,
D8 README layout drift a TLS docs. (K7 „51 kódů" = falešný poplach, číslo jen v docs.) **ZBÝVÁ:**
- [ ] *(D6, DRY)* `_generate_pseudo_boulders` (generator.py:2942) vs `_generate_pseudo_points` (3066) duplikují ~40-50 LOC
  umísťovací mašinérie (grid/area_km2/water mask/forbid/rejection). Extrahovat `_place_points_in_mask`. Pozn.: SLAP —
  `_generate_pseudo_boulders` navíc míchá 204 (rejection) + 210 (pole teček) → kandidát `_place_stony_fields`.
- [ ] *(D9, DRY napříč model/)* `PX_PER_MM`/`MAP_SCALE` (3× purple/inject/generator), `_IMAGENET_MEAN/STD` (6×),
  peak-detekce kopie (train↔eval png2point i png2line), tiling helper (`_positions`/`_crop`/`TILE=512`). Vlastní
  „extrahovat až 3. konzument" triggery už nastaly → konsolidovat (`mpp.py` / nový `peakdetect.py`/`norm.py`/`tiling.py`).
- [ ] *(kosmetické carry)* K2 stale komentáře „204/210" po rozšíření na 4 třídy `png2point/eval_real.py:6,60,144` ·
  K6 stale `connectors/__pycache__/forest.cpython-312.pyc` (gitignored) · K8 matoucí `v2000/c2000` názvy `compare_isom.py:109`
  (pravý sloupec `.crt` = OCAD-2017, ne 2000) · K9 ring-split bit 2 (`cut`) vs bit 16 (`omap_raster`) — okomentovat vztah.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi — ČÚZK (Sez. 2), Mapový portál ČSOS (Sez. 8, gate zavřená); lokální mapy `resources/` (smíšený původ); další zdroje TBD
- [~] Doplnit `RESEARCH.md` — LIDAR→mapa metoda hotovo (Sez. 2); zbývá generativní (UC4-I), dewarping/inpainting (UC3)

## ISOM-scan benchmark / scan mining (`isom_scan/`) — baseline „hotový model sken → ISOM"
Empirický test hypotézy z IDEAS „Hotový pretrained model…" (Sez. 142, ~5 %): jak dobře cloudové
i lokální (vision) modely rozpoznají ISOM symboly přímo ze skenu, bez doučení. **Scaffold HOTOVO:**
fixní prompt + JSON schema (`task_isom_scan.md`), oddělený skórovač (`score.py` — model NESkóruje sám
sebe), `results.csv` (run meta / self-report / KPI), `runs/` šablona, `README.md`. Vstup = ořez skenu
`1127443` Branžež. Headline KPI = `point_F1` (anti-sprawl, [[kpi-one-quantifier-not-methodology-sprawl]]).
*(HOTOVO Sez. 146/154/159, detail DONE: GT `only_real=True` Branžež NCC 0,945 · durable harness/copyright split ·
black-vs-brown + point PoC vrstvy · `calibration_manifest.json`+`.py` shape guard.)*
- [!] **Modré pointy `311/312/313` ze skenu.** Navázat na calibration ledger: nejdřív vyrobit kandidáty
  nad Buschdörfl/Hamr, doplnit pozitivní `602` markery a až potom řešit export do pracovní `.omap`.
- [ ] **Kurátorovat `resources/isom/index.json`** — lokální SVG dump 113 symbolů je načitatelný, ale zatím
  draft (`geom/license/isom_version` neznámé). Začít živými bodovými třídami 204/210/417/419 a kandidáty
  418/525/527/531; vyplnit provenance/licenci, geometrii, měřítkové footprinty a případné OOM/OCAD aliasy.
- [ ] **Proběhnout pole modelů** (cloud: Opus/Sonnet/…; lokální: LM Studio) — N seedů, medián; vyplnit `runs/` + skórovat.
- [ ] *(curtains, odložit)* cost tracking přes API · varianty no-spec / tiling pro malý kontext · leaderboard render.
- [ ] *(DRY drobnost)* 2× PDF v `isom_scan/` jsou kopie `docs/kb/` — pro přenosný balík OK; zvážit odkaz, pokud zůstane jen v repu.
- [ ] *(reference)* zvážit `isom-2017-2-spec.pdf` do `docs/kb/` (dnes jen ISOM 2000 stand-in; vzhled OK, číslování ne).

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
> **2. KPI — reálný doménový gap (Sez. 120–121, re-benchmark Sez. 126 po MPP fixu, supervisor audit A1):** KPI výše měří jen
> FEEDER (kvalita generátoru); zda reconstructor reálné mapy ČTE, měří `model/png2{area,point,line}/eval_real.py` na
> kartografových skenech. Po MPP fixu (Sez. 126, kanonické měřítko dlaždice 1,33) přeměřeno na správném měřítku:
> **Png2Area** (per-odstín mIoU / soft pixel-acc): **Bedř 0,336 (z 0,256) / 0,91, Blatná 0,357 / 0,89** (synt test
> mIoU 0,683). **Png2Point** (peak mF1 synt / realita; **10 tříd 204/210/417/419/531/525/527/109/111/112 od Sez. 162**): synt **0,745**
> (medián 3 seedů, STABILNÍ rozptyl 0,738–0,763 — těsnější než Sez. 161) / **realita**: **111 Small depression SILNÝ
> 0,71–0,89** (HNĚDÝ oblouk ∪, LEPŠÍ než 109; Sez. 162), **419 SILNÝ 0,67–0,76** (zelený X + svatozář),
> **531 SILNÝ Velbloud 0,708** (černý man-made X, Sez. 158), **525 Small tower SILNÝ Bedř 0,766** (černý ⊤, Sez. 159),
> **109 Small knoll SILNÝ medián 0,65** (HNĚDÝ disk, Bedř 0,53 / Blatná 0,65 / Velbl 0,80 — hnědá PŘENÁŠÍ přes konkurenci
> vrstevnic; Sez. 161), **112 Pit STŘEDNÍ-DOBRÝ 0,53–0,77** (HNĚDÝ vyplněný ▽, recall nižší konzervativní; Sez. 162 —
> **reconstructor-only, gen NEkreslí → mimo USED_CODES**), **527 Fodder rack STŘEDNÍ-DOBRÝ 0,50–0,83** (černý Λ,
> seed-citlivý), **417 Prom. large tree 0,40–0,57**, 204 stabilní 0,44–0,73, **210 pořád kolabuje 0,00–0,25** (drobné tečky).
> Práh detekce **per třída `PointClass.peak_thr`** (zelené 0,40–0,45, černé man-made + hnědé terénní VYSOKÝ 0,60 — FP z cest/textu/vrstevnic;
> měř per-mapa MACRO, ne sweep micro-agregát — Sez. 162 lekce u 112 prahu).
> **Png2Line krok 1 watercourse 304/305 (Sez. 131, NOVÝ 3. reconstructor; pixel IoU / relaxed completeness/correctness):**
> synt test mIoU 0,774 / IoU 0,55 · **realita: completeness 0,85–0,93 = model TRASUJE reálné toky** (žádný kolaps
> jako 210), **strict IoU 0,409 / F1 0,773** po conf_thr prahu 0,95 (registr `LineClass.conf_thr`, izomorf `peak_thr`;
> argmax přestřeloval na cesty → IoU 0,251→0,409). **Sez. 152 rozšířila Y scope na 306/309/508***,
> ale starý checkpoint i watercourse-only vektorizér tím nejsou automaticky nové řešení; line tiles/model
> po změně `N_LINE` vyžadují rebuild + retrain.
> Pravidlo: nová KPI práce se ptá „pomůže to reconstructoru na reálném skenu?".
>
> **Stav Sez. 176: canonical KPI 68,7 %** (HAL3000, `KPI_3MAP_CANONICAL`; plocha **79,4** / linie **68,7** /
> bod **65,0**; Velbloud 71,9). Sez. 176 přeměřil stale canonical (67,5→**68,0**) + opravil watercourse 304/305
> klasifikaci (délka toku per `idvt` místo pojmenovanosti — ISOM kritérium je ŠÍŘKA, ZABAGED ji nenese, pojmenované
> toky jsou drobné lesní potoky = 305; práh `WATERCOURSE_MAIN_LEN_M=3000 m`): **304 gen 46→11 ≈ orig 12, 305 44→79
> podstřel→ok, linie 66,8→68,7 → headline 68,0→68,7**. Bezpečné pro Png2Line (304+305 = 1 label-třída). ntbhej 68,4
> (Sez. 173) = separátní stroj-baseline, stale vůči watercourse opravě (sirotek-disciplína, nemíchat).
> Sez. 164 (canonical 67,5): gate 407/409 (`label==solid-zeleň 4a8712e` →
> `!=open`): 409 ožilo **0 → 114 gen** (vypadlo z žebříčku děr, bylo #3 / 1,6pb), 407 12→83; plocha 75,0 → 78,8,
> headline 66,2 → 67,5. Diagnóza: gate `==2` vyžadoval solid zeleň, ale 409 leží na BÍLÉM lese (GT label 0) →
> 0 polygonů. Sez. 160 (66,2) doložila sirotka plnou regenerací `maps/` (audit A3/A4): committed `separate.py`
> gate OVLIVŇUJE `.omap` KPI počty přes `predict_areas_sjtsk`. Sez. 159 „65,8 netknuto" platilo jen na stale `.omap`.
> Sez. 150 zkalibrovala 527 dolů po KOMPAS přestřelu `orig 8 / gen 103` → `gen 3`
> (headline 62,0 → 62,5) a přesunula `Cesta typcesty_k=025` z path 504 do ride 508
> (headline 62,5 → 63,3; 508 `ok`, 504 už ne přestřel). Sez. 152 přidala 404/407/409
> do scan separace / `N_AREA=21`, rozšířila `N_LINE` na 304/305 + 306 + 309 + 508* a zvedla
> `PSEUDO_BOULDER_PER_KM2` 500→900. Sez. 154 přidala kandidátní scan-transfer pro bodové kódy
> 109/111/112/115/417/418 a obecný `.omap` export, ale bez KPI povýšení před kurací. **Žebříček děr (Sez. 176):**
> **403 / 416 / 306 / 210 / 202 / 501 / 308 / 109 / 108 / 208** (304/305 vypadly po watercourse opravě). **KOMPAS `--table` má
> sloupce `zdroj · gen · scan · provedení`**; původ symbolů je v `isom.capabilities`, kde `gen` popisuje
> fallback generátoru a `scan` ukazuje mapper-scan signál. `_provedeni` zůstává AUTO ze share orig:gen.
> Další velká strukturální páka zůstává Png2Line; KPI je kompas děr, ne cílová funkce.
> **Sez. 172 (ntbhej): 109/111 půlhladinová detekce** — half-vrstevnicové smyčky (`level+2,5 m`) → `_classify_loop`
> s guardem `|elev−hlevel|<2,5 m` (bez zdvojení / vrcholů velkých kopců): **109 18→32 (+78 %), 111 31→52 →„ok"**.
> ntbhej KPI 67,1→**67,3** (+0,2 pb), bod 67,9→**70,2** (+2,3 pb), žádná regrese (109 vypadlo z top-5 děr). Reframe:
> 109 nebyl díra, ale podstřel (gen ho kreslí z plných 5 m vrstevnic; DMR strop na drobné kupky). Canonical HAL3000
> (67,5) NEpřeměřeno → carry (sirotek-disciplína, nemíchat). Trénink netknut (Png2Point z `inject.py`, ne gen .omap).
> **Sez. 173 (ntbhej): budovy 521 + ruční crop polygon (mapfield).** (1) **521 granularita** — vyřazena vrstva „Kůlna…"
> + `BUILDING_MIN_AREA_PX2` 0,2 mm² (ISOM min, jen 521): gen 498→370, čisté A/B **plocha +1,9 pb** (Bedř +4,9 / Blatná 0
> kontrola); headline neutrální = bodový měřicí šum (Velbloud). (2) **Ruční crop polygon** (nález „zelená z log" =
> banner/loga jako falešný les, KPI counts kontaminované): `resources/<name>_mapfield.json` nahrazuje auto detekci
> i convex hull v separaci+KPI. Provizorní Bedř: **KPI 62,3→66,1** (plocha 69,2→78,5), **ntbhej headline 67,3→68,4 (+1,2)**.
> Canonical HAL3000 (67,5) NEpřeměřeno (sirotek-disciplína, nemíchat ntbhej↔canonical; budovy+mapfield = změny kódu
> přenositelné → carry HAL3000 přeměření). Metodický nález: agregátní HI sim PŘESTŘELILA (per-mapa norm) → simuluj per-mapa.
>
> **Plošná + liniová páka z čistě ČÚZK dat je VYČERPANÁ** (potvrzeno 4× Sez. 99-102: 403 granularitní propast +0,1,
> 508 smíšený podstřel +0,34; Sez. 152 potvrzuje, že 404/407/409 patří do mapper-scan separace, ne do ČÚZK).
> Co generátor nenakreslí, reconstructor se NIKDY nenaučí →
> pokrytí = strop tréninku (memory `generator-coverage-is-the-ceiling`). **Historie baseline (43 %→59,1 %), analytické
> cuty (plošný strop 54 %), kompas a vyvrácené páky 403/508: DONE Sez. 94-102 + diáře.**
- [ ] *(vizuální realismus DEV map, nález uživatele Sez. 164)* **DEV `--location` mapy: separovat vegetaci z překrývajícího skenu + zúžit výsek na pokrytou oblast.**
  DEV mapy kreslí BÍLÝ LES (Sez. 102: veg jen ze separace párového skenu, DEV prý nemá). Jenže `scan-auto`
  překrývající sken NAJDE (Sez. 164 regen: Soví vrch 100 % / ostatní 19–30 %), jen ho používáme jako podklad,
  ne pro separaci → nekonzistence (KPI/Livelox cesta separuje, DEV ne). **Přístup (volba uživatele A1):** místo
  prahu pokrytí **zúžit DEV výsek na bbox skenové coverage** (rozsah DEV lokality NENÍ závazný) → celá mapa
  pokrytá veg, žádná tvrdá hrana. Mašinérie existuje (`separate_areas` + `generate_map(predict_areas_sjtsk=…)`,
  vzor `measure_dod._separate_resources_to_sjtsk` / `pairs._separate_to_sjtsk`). **Separovat z ORIGINÁLU skenu,
  ne z warpu** (memory `bg-scan-warp-vs-livelox-origin`). Caveat: sken = jiný překrývající event → veg přibližná
  (Sez. 79 OK pro DEV verify). Není CUDA, nezvyšuje KPI (měří se na KPI mapách). Reverzuje Sez. 102 white-forest.
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
- [~] *(vizuál, ořez `cut.py`, nález Sez. 118; SINGLE-RUN Sez. 138; **FILL/BORDER SPLIT KÓD HOTOVO Sez. 142**)* **Neohraničovat tučnou čarou odstřižené hrany ploch s neproniknutelnou hranicí.**
  **HOTOVO Sez. 142 (kód + unit verify):** fill/border split nahradil flag-16 trik pro ohraničené plochy — `cut._emit_bordered_area` emituje klipnutou
  vodu jako **fill-only 301.1** + **břehovou linii 301.4 jen na reálných úsecích** (`_border_runs`, klasifikace segmentu podle STŘEDU → robustní v rohu i
  multi-run, libovolný počet řezů automaticky). `_BORDERED_AREA` registr (kód→fill+border), id resolve z `<symbols>`. `omap_raster` alias `301.1→label 8`
  (footgun Sez. 110: jinak tiše z Y; `N_AREA` beze změny). **Nález (verify-against-source):** jediná emitovaná combined ohraničená plocha = **voda 301**;
  520/521 jsou fill-only (border problém nemají — TODO seznam „521/520/lom" byl falešný). **501 odloženo:** jeho fill 501.1 koliduje s base-fill třídou
  v `omap_raster` (chce vlastní symbol) + border je tenká hnědá (marginální). Unit probe: jednoduchý řez / **roh** / plný `clip_omap` / Y alias — vše OK.
  **ZBÝVÁ — OOM vizuál na reálném Borný = carry HAL3000/mrkla:** ntbhej regenerace selhala na RAM (`separate.py` 1,38 GiB flat array, sourozenec
  `segment_gt` blokátoru) + disk. Otevřít `Borný_v142.omap` v OOM, ověřit roh Máchova jezera bez černého obrysu na obou řezných hranách.
- [~] *(KPI kvalita, nález uživatele Sez. 140; **210 HOTOVO Sez. 166**)* **Přestřel hustoty symbolů na skalnatých mapách.**
  Vizuální dojem z overlay (Rovné skály): gen má víc objektů než kartografův originál. **HOTOVO Sez. 166 (210 Stony ground,
  ntbhej plná 3-map):** `--table` měřením potvrzen proporční přestřel (gen_share 11,8 % vs orig 7,3 %, invertuje poměr 204:210),
  ač absolutně podstřeluje (622<975, gen globálně kreslí míň) → `PSEUDO_STONY_FIELD_PER_KM2 12→7` (proporční match), **KPI
  65,6→67,1 % +1,5 pb**, 210→ok. Simulace z counts PŘED kódem našla optimum 0,5–0,6 + odhalila past (share-based ≠ absolutní).
  **204 = ok** (r 1,08, `PSEUDO_BOULDER=900` Sez. 152 dobře vyladěn — nesahat). **ZBÝVÁ:** **417/525 pseudo** (marginální
  +~0,3 pb, RNG-křehké — čekají na nezávislé RNG streamy; 521 budovy HOTOVO Sez. 173). Paměť [[kpi-fill-undershoot-dilutes]] + [[kpi-overshoot-share-not-absolute]].
- [ ] *(KPI páka, real-data granularita — 521 HOTOVO Sez. 173 `fc6afa0`, DONE)* **503 přestřel granularita/projekce.**
  Zvážit izomorfně s 521 (vyřazení jemné vrstvy + ISOM min-size 0,2 mm²). Pozn.: 304 už řešen jinak (watercourse délka per `idvt`, Sez. 176).
- [~] *(scan-vytěžení bodů, ROADMAP Etapa 1 — nález/přesměrování uživatele Sez. 173; **balvany UZAVŘENY Sez. 174 = strop CV**)*
  **Rozšířit scan-detekci bodů na další ISOM typy proti GT Branžež.** Baseline Sez.173 (vs ruční GT 187/21): kalibrovaný
  109/111/112/115 + 419; **9 bohatě-GT kódů BEZ detektoru**. **Sez. 174: balvany 204(9)/205(7)/204.5(10) = jedna třída
  „boulder" → DOLOŽENÝ STROP classic-CV** (`boulder_points_poc.py`, F1 0,260; balvan pixelově nerozlišitelný od fragmentu
  srázové kresby 202 na skalnaté Branžeži — fill/ecc/solidity/area/okolní-černá VŠECHNY stejné rozdělení TP/FP; manifest
  `204 classic_cv_ceiling`, NEexportováno, řeší Png2Point ML). **ZBÝVÁ roadmapa (priorita dle šance):** **308.1(6) bažina**
  (modrá maska = distinktivní barva, NE černá v moři srázů → lepší šance) · **106(7) val rozpadlý** · spádovky **103.1(26) /
  101.1(14)** = NÍZKÁ priorita (směrové čárky NA vrstevnicích = fragmentový FP šum jako 109, riziko Goodhart). 203.1(5) <5-ish
  shluk. Match infra = `score.match_points` (Hungarian, tol 12; scratch `score_boulder.py` vzor). Anti-Goodhart: kódy s <5 GT
  neladit do přemíry (strop CV = argument pro ML, jako 112/115/204). Kalibrace → `calibration_manifest`.
- [ ] *(scan-vytěžení, nález Sez. 173)* **418 přestřel ze skenu.** `vegetation_points_poc` default masivně přestřeluje 418
  (overlay stovky FP modrých) → kalibrovat proti GT (jako 419/111). Pozn: 418 GT na Branžeži jen 1 → potřeba víc GT / jiná mapa.
- [ ] *(mapfield doladit, nález Sez. 173)* **Bedřichovka mapfield provizorní → přesný** (`tools/mark_mapfield.py`, drobnost
  pravý horní roh). *(ZBÝVÁ — jediná drobnost, ostatní vyřešeno Sez. 179.)* Livelox
  páry mají taky layout (pairs separace bez map_field_mask) → zvážit mapfield i tam.
  *(Sez. 179 DONE: Velbloud + Blatná naklikány, ale hypotéza „čistý layout" se POTVRDILA — vizuální
  kontrola po naklikání ukázala, že mapová kresba sahá k okrajům skenu u obou, žádný banner/logo;
  naklikaný polygon ≈ celý obrázek = no-op vůči auto-detekci. Soví vrch měl reálnou kontaminaci
  (crop vynechal ~3/4 skenu, „1/4 domapováno") → tam měl smysl. Proces-chyba: měl jsem se na skeny
  podívat PŘED voláním nástroje, ne až po ruční práci uživatele — paměť [[screen-before-manual-gui-tool]].
  Bonus fix: `mark_mapfield.py` chyběl `Image.MAX_IMAGE_PIXELS = None` guard, spadl na Soví vrch 264 Mpx.)*
- [ ] *(robustnost generátoru, nález Sez. 166)* **Nezávislé RNG streamy pro pseudo body.** `generate_map` má JEDEN sdílený
  `np.random.default_rng(seed=1)` (gen 3880) mezi `_generate_pseudo_boulders` (210) a `_generate_pseudo_points` (417/419/418/525/527/531).
  Změna hustoty JEDNOHO symbolu (n_fields/n_*) posune RNG stav → ostatní pseudo counts se DETERMINISTICKY změní (Sez. 166: 210
  kalibrace náhodně 419 250→147, 525 6→20) → KPI kalibrace jednoho symbolu je **zašuměná cascade**. Fix: `rng.spawn()` per pseudo
  symbol (nezávislý stream) → kalibrace izolovaná, čistá atribuce. Pak teprve doladit 417/525 přestřely. Pozn.: dopad na trénink
  NULOVÝ (Png2Point z `inject.py`, ne gen .omap), čistě měřicí/KPI robustnost.
- [ ] *(měření, audit A3 — nález Sez. 166)* **Baseline sirotek: ntbhej KPI ≠ HAL3000 canonical.** Sez. 166 ntbhej plná 3-map
  = **65,6 %**, ale `KPI_3MAP_CANONICAL` (HAL3000, Sez. 164) = **67,5 %**. Rozdíl lokalizován do **Bedřichovky** (ntbhej 57,4 vs
  README 58,5 vs TODO 61,9 — i HAL3000 doklady se rozcházejí); Blatná/Velbloud sedí napříč stroji. Kód generátoru 164→HEAD
  NEZMĚNĚN → STROJOVÝ rozdíl (Bedř = největší sken, separace RAM-downscale / DMR fetch citlivá). **Prozkoumat** (ntbhej↔HAL3000
  separace téže mapy) + sjednotit headline (audit A3: dva labely KPI_3MAP_NTBHEJ / KPI_3MAP_CANONICAL, nemíchat). **+ HAL3000
  přeměření po 210 kalibraci + 109/111 půlhladinové detekci** (canonical 67,5 → ~69,2? — Δ 210 +1,5 + 109/111 +0,2 přenositelné = změny kódu).
- [~] *(vytěžení, nové body; 525/527/531 HOTOVO Sez. 141 + kalibrace 527 Sez. 150, DONE)* **523.1 Ruin min size — ODLOŽENO**
  (volba uživatele Sez. 141): měřením marginální (1/5 map, 1 objekt Velbloud) + invazivní (buildings vrací area, 523.1 je
  point → cross-pipeline změna) → reálná páka ≈ 0. Když se bude dělat: footprint < ISOM min 144 m² → bodový čtverec 523.1
  místo zanikajícího obrysu 523.
- [~] *(KPI kalibrace; 527 HOTOVO Sez. 150 — `PSEUDO_FODDER_PER_KM2=(0.08,0.35)` gen 3, + 508 přesun `Cesta typcesty_k=025`,
  headline 62,0→63,3, DONE)* **ZBÝVÁ hlídat 531** a spojit s „Přestřel hustoty 204/210" výše (táž páka
  [[kpi-fill-undershoot-dilutes]]). Změny jen s `measure_dod --table` před/po na stejné sadě.
- [ ] *(robustnost měření, nález Sez. 141)* **`compare_isom.detect_version` — trojí realita místo binární.** Dnes
  vrací jen „2000"/„2017-2" (podle Building 526/521), ale existují TŘI číslovací sady: ISOM2000 / OOM-2017 (524-531) /
  OCAD-2017 (535-540, Building=526 → mylně detekováno „2000"). Funguje náhodou pro OCAD mapy (crosswalk pravý sloupec
  = OCAD), ale **Soví vrch (OOM-2017, krmelec kóduje přímo 527) → `resolve(527,"2000")={520}` = nesmysl**. Soví vrch
  NENÍ v default KPI sadě (Bedř/Blatná/Velbloud) → headline nezkresluje, ale past. Fix: rozlišit OOM vs OCAD set
  (např. dle `<symbols id="OCD">` nebo přítomnosti 535-540) → správné crosswalk routování. Paměť [[isom-dual-numbering-oom-ocad]].
- [~] *(vytěžení; (a) pseudo 516/517/518 HOTOVO Sez. 144 — varianta plotu kolem RÚIAN zahrad, váhy 0,42/0,16/0,42,
  KPI/KOMPAS dopad změřen Sez. 145, DONE)* **ZBÝVÁ (b) Png2Line ze skenu** (Etapa 2, povýšeno `260620-Buschdörfl`) —
  detekce uzavřené smyčky plotu = JINÝ přístup (topologie uzávěru), ne starý dashed multi-class pokus (Sez. 133).
- [ ] *(bug fix, test výstupů Sez. 118)* **Hranice porostu 416 NESMÍ vést přes vodní plochu** (`resources/livelox/631730/gen/map.omap`,
  marker {A}). `_predict_veg_boundaries(class_mask, draw, bdraw)` (gen 2609) kreslí 416 čistě z mezitřídních hranic predikčních
  veg ploch (`class_mask`) — **nedostává vodní masku** → když separovaná zeleň sahá k vodě / přes ni, tečkovaná hranice projde
  přes hladinu = nepřípustné (voda není runnability-vegetace). Stejný typ vady jako balvany/plot na vodě (Sez. 113). Fix
  (analogie): per-bod check `water_cell` v `_predict_veg_boundaries` → přerušit úsek nad vodou (jako `_generate_pseudo_boulders`
  `mask &= ~water_cell`), nebo post-water clip 416 segmentů z `.omap` (`_clip_fences_off_water` vzor). Předat vodní masku do funkce.
- [ ] *(vizuál, vrstevnice přes vodu, nález uživatele Sez. 118 — řešení OPRAVENO na CLIP po rešerši IOF)* **Vrstevnice se NESMÍ zobrazovat
  přes vodní plochu — řešení CLIP (geometrie), NE z-order.** Původní hypotéza „z-order (modrá plocha nad hnědou)" VYVRÁCENA rešerší IOF
  (supervisor audit, Sez. 118): oficiální IOF colour order má **modrou plochu POD hnědou linií** (Printing & Colour Definitions Feb 2022, kap. 7 str. 6;
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
- [ ] *(nález Sez. 26)* **Q duplicita budovy** — uživatel označil markerem 704 místo s podezřením na dvojitou budovu; můj paper→S-JTSK přepočet polohy markeru byl nepřesný (ZABAGED dotaz mířil vedle) → nedořešeno, NEhádáno. Dořešit s přesným přepočtem. (Pozn.: počet budov 1078 REST + 70 řopíků sedí → generátor neduplikuje. Od Sez. 27 budovy RAW = věrný footprint, žádné umělé obdélníky.)
- [ ] *(odloženo Sez. 23)* NoData masking u hranic: DMR vrací 0 m mimo území ČR → artefaktová změť vrstevnic (Soví vrch 5×4 km zasáhl hranici). Nekreslit vrstevnice tam, kde elev = NoData → robustní výseky u hranic. Dnes obejito posunem středu (0,44 km).
- [ ] *(odloženo, noise-půlka)* Hydrologické jádro z flow accumulation (D8, §9): toky (§4.8) → prameny (§4.10) → jezera/rybníky (sink-fill deprese) → bažiny. **Sez. 17: voda realizována reálně (ZABAGED), D8 = procedurální protějšek do budoucna (nemíchat osy).**
- [ ] *(drobnost, vylepšení form line Sez. 29)* **souvislé smyčky** — form line jsou teď krátké úseky/obloučky (per-pixel maska). ISOM-věrnější by byly souvislé smyčky kolem lokálních kopečků/depresí (jiný přístup než maska). MVP uzavřen (uživatel), tohle až kdyby vadilo. Prahy `FORMLINE_*` jsou laděné na NL — ověřit i na SV/LS.
- [ ] *(odložená marginálie, nález Sez. 30; `Skupina_balvanů__linie_` → 208 HOTOVO Sez. 57)* **`Sesuv_půdy__suť` → 210 Stony ground** — Σ1, verify až v lokalitě se sutěmi (Jeseníky / Krkonoše Sněžka); na Hrubé Skále 3/0 prvků. Když bude, doplnit `STONY_GROUND_LAYERS` v zabaged.py.
- *(verify nástroj `compare_real_vs_gen.py` HOTOVO Sez. 37–58 — multi-mapa; **Stale DROP Sez. 69**, detail DONE)*
  ~60 % precision tvrdé geometrie / vegetace ~30 % gate na 3 cizích mapách. Otevřené zbytky (Soví vrch ~1/4 domapováno,
  Slovanka UTM33, vektor-na-vektor rozpad po sémantických skupinách) zůstávají evidovaný nález — **NEnavrhovat v Příště** (viselo 9×).
- [~] *(Sez. 110 stahování + Sez. 111 GT HOTOVO, kurace/split carry)* **Korpus + GT na ntbhej/Stella.** `livelox batch` stáhl
  **57 → 264 map**, GT **264/264** (Sez. 111 chunked classify odblokoval 6 obřích). **ZBÝVÁ:** (a) **kurace + split
  rozhodnout** — `_curation.json`/`_split.json` na ntbhej NEJSOU (gitignored, ruční vizuální tagy Sez. 71 žijí na HAL3000)
  → buď **zkopírovat z HAL3000** (zachová tréninkový split, doporučeno), nebo auto-`curate`+`split` tady (rozejde se
  s HAL3000). Pozn.: `build_pair`/trénink je stejně CUDA-vázané (HAL3000) — ntbhej korpus slouží měření / `build_pair`
  E2E ověření / rozšíření tréninkového setu po přenosu na HAL3000. **Sez. 181:** Stella má zatím jen tracked metadata
  v `resources/livelox/`, syrový gitignored korpus chybí; `pairs.py map`/`scan-auto` tam nepouštět bez privátního syncu.
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
- *(HLAVNÍ TAH — HOTOVO Sez. 82–90, detail DONE)* **`generator()` fáze I — predikční plochy ze separace Livelox mapy.**
  Zdroj predikční vegetace = separace z mapy (`generator/separate.py` 406/408/410 → `.omap` ~90 %; [[forest-age-proxy]]
  ARCHIVOVÁN). Integrace `generate_map(predict_areas_sjtsk)` + orchestrátor `pairs.build_pair(cid)` (per-classId, Gate A ~1 px).
  Výkon párů vyřešen třemi pákami (downscale na ~1,33 mpp PŘED separací 31,6× / `max_km` strop / reuse `tile.py`);
  noční `build_pairs` 207 ČR doběhl, degradér on-the-fly v loaderu (ne v build_pair).
- [~] **Fáze II/III degradér `generator/degrade.py` — MVP HOTOVO Sez. 86, PŘESUNUT do augmentace Sez. 103.**
  `degrade(rgb, seed)` 4 fotometrické sken-vrstvy (CMYK misregistrace / blur / papír+zažloutnutí / šum+JPEG),
  čistě fotometrické (Y se nemění). **Sez. 103: odstraněn z `build_pair` (zapékal `scan.png` do páru = chyba,
  degradace nepatří do generator() fáze I) → volá se on-the-fly v `model/png2area/dataset.py._augment` jako
  augmentace (jiná realizace každou epochu).** X páru = ČISTÝ `rgb.png`. Paměť [[no-degradation-in-generator-phase]].
  **ZBÝVÁ:** porovnat s reálnou Livelox mapou (cílová doména, mrkla) + **doladit misregistraci ±0,7 px (DŮKAZ
  Sez. 90):** ±1,1 px rozdvojuje tenké symboly — zelený kroužek **417** (Prominent large tree) na zeleném
  podkladu → světlé lemy = „dva bílé kruhy". Pro Png2Area nevadí (417=bod, není v Y), ale pro **Png2Point** musí
  tenké symboly po degradaci zůstat čitelné → zmírnit posun nebo škálovat misregistraci dle tloušťky prvku.
- *(reconstructory `Png2Area`/`Png2Point`/`Png2Line` — dekompozice dle typu geometrie ISOM `type=4/1/2`,
  GT zdarma z `.omap`; pořadí Area→Point→Line; detail IDEAS „Tři fáze I/II/III" + DONE)*
  - *(Png2Area HOTOVO Sez. 87–126, detail DONE)* PRVNÍ reconstructor: Y-pipeline `omap_raster.py` (`N_AREA 21`),
    `model/png2area/{tile,dataset,train}.py`, nález **tvar > velikost** (tenké třídy se downsamplingem rozpustí);
    test mIoU 0,568 → **0,683** (Sez. 126 MPP fix). Archiv ortho-baseline `git mv` → `model/runnability/`.
  - [~] *(odsunuto za pokrytí generátoru)* **class-balanced expansion** — model = detektor vzácných 208/501/301
    (`208` test 0,00 = cap vzal váhu → datový strop) → cílený Livelox download → přetrénovat (IDEAS „Class-balanced
    corpus expansion").
  - *(Png2Point HOTOVO Sez. 105–106, detail DONE)* DRUHÝ reconstructor: injekce symbolů + CenterNet heatmap
    (`model/png2point/{inject,dataset,train}.py`); root-cause 204 = hustota pozitiv vs focal `n_pos`. Synt mF1 později
    stabilizován focal bias initem (Sez. 125, medián 3 seedů). Reálný transfer + scope viz KPI blok výše.
  - *(Png2Point → generátor HOTOVO Sez. 107, detail DONE)* pseudo injekce 204/210 do `gen.omap` z **doložené
    skalnatosti** (206+reálné body+dilatace, ne sklon) + kalibrace na **share** → KPI bod 18,4 → 54,3 %.
  - [~] *(rozšiřování bodového scope Png2Point; 417/419/418/109/111/112 HOTOVO Sez. 128–162, detail DONE + KPI blok)*
    **Bodové třídy do `POINT_CLASSES`.** Registr generalizován (kind/color/n_range/peak_thr); zelené 417/419 + 418 bush
    pseudo-injekce do generátoru (princip kamenů); hnědé terénní 109/111/112 (111 lepší než 109; 112 reconstructor-only).
    **110 STOP doložen Sez. 164** (probe: jen 8 GT v eval sadě Bedř 5/Blatná 1/Velbl 2 — Slovanka UTM33 blokovaná,
    Soví v. neúplná; gen 110 už kreslí → přínos jen reconstructor-transfer, který neměřitelný; navíc elipsa ≈ disk 109
    na bodovém měřítku). Rodina 109/110/111 uzavřena na 109+111. **ZBÝVÁ:** **115** (ISOM 2017-2 Special terrain feature,
    jiný zdroj) — nízká priorita (TOTAL 8). Alt směr: **311/312/313** modré pointy ze skenu (governance A2 first).
  - [~] *(Png2Line TŘETÍ reconstructor — krok 1 watercourse 304/305 HOTOVO Sez. 130–132, detail DONE + KPI blok)*
    Per-class segmentace linií (U-Net izomorfní s png2area, dilatovaná GT) + vektorizace maska→polyline→`.omap`
    (`model/vectorize.py`, `vectorize_omap.py`). Krok 2 dashed 508/516 jako přidaná třída = **2× zavržen měřením** (Sez. 133/156).
    **ZBÝVÁ:** (b2) **dashed JINÝM přístupem** (morfologické přemostění přerušení / dashed augmentace, NE další třída);
    (c) **gap-bridging u junkcí** (vektorizace tříští toky na uzlech). CUDA-vázané (HAL3000/mrkla).
  - [ ] *(follow-up Sez. 134; poledníkový detektor HOTOV + OVĚŘEN — DONE Sez. 134)* **Napojit `north_grid` filtr do
    produkční cesty + ověřit na 2. mapě.** Detektor `model/png2line/north_grid.py` (Codex `ac953ab`, dotažen Sez. 134:
    data-driven rozestup) ověřen na Buschdörfl (5-liniový grid 77,4°, 27 poledníků odstraněno, vody zachovány); gen render
    poledníky nekreslí = doménový gap. **ZBÝVÁ:** (a) dnes filtr volá jen `vectorize_omap.main` (verify nástroj) — zvážit
    napojení do `eval_real`/budoucí inference; (b) ověřit na 2. reálné mapě s poledníky (jediný doložený případ = Buschdörfl);
    (c) edge případ černé poledníky (watercourse je nebere, ale budoucí liniové třídy ano).
- [~] *(area granularita — 403 odstín HOTOVO Sez. 92, detail DONE + IDEAS „Granularita area tříd")* **Pattern vs odstín.**
  Osy: ODSTÍN umí nearest-color separace (403 bledá žlutá ✓), PATTERN slepý. **ZBÝVÁ patternová rodina**
  (404/412/413/414 + zelené directional 406.1/408.1) — konzistentní trojice „generátor kreslí + render nese signál +
  `omap_raster` má label"; separace per-pixel pattern neumí (jen model/generátor).
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
- [ ] *(rozšíření cest/vody)* věrná dvojitá linie 502 Wide road (teď PoC casing), ladění 505/506, ořez reálných linií na bbox; (voda) „hranatý" malý rybník / tvarová věrnost zdrojové geometrie. Kombinovaný 301 s břehovou linií v OMAP je hotový; cut ho na hraně výřezu rozkládá na fill 301.1 + skutečný břeh 301.4.
- [ ] *(drobnost, nález %AUDIT:CODE Sez. 19 — P2)* OMAP export 110 Small elongated knoll: rastr respektuje orientaci `horiz`, ale `.omap` exportuje vždy `rotation="0"`. Předat orientaci protáhlosti do exportu (rastr↔omap konzistence).
- [ ] *(anotace, až bude vstup)* čtečka čísel kontrol **ISOM 704** ze separátního anotačního `.omap` (kanál uživatel → AI: označí místo v OOM, generátor nepřepíše; já přečtu polohu/číslo). Workflow rozhodnut Sez. 18.
- [~] Stupeň 2 — augmentační pipeline (§8.3): degradace render → „sken". **Fotometrická půlka HOTOVO Sez. 86,
  zapojena jako AUGMENTACE Sez. 103** (`degrade.py` volán v `model/png2area/dataset.py._augment` on-the-fly, ne
  v build_pair — degradace patří do tréninkové pipeline, ne do generator() výroby párů, viz
  [[no-degradation-in-generator-phase]]). **ZBÝVÁ geometrická půlka** (deformace sklad/sken, rotace warp;
  POVÝŠENO auditem A2 — sekce „Audit supervisor" nahoře) —
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
