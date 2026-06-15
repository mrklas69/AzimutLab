# DONE — AzimutLab

Dokončené úkoly (stručně co se udělalo). Aktuální/čekající: TODO.md.

## Sezení 127 (2026-06-15) — cleanup + bezpečné checkpointy + uzavření auditních dluhů
Detail: [diary/2026-06-15.md](diary/2026-06-15.md#sezení-127--cleanup--bezpečné-checkpointy--uzavření-auditních-dluhů-hal3000).
- [x] **%CALIBRATE + %AUDIT:DOCS + TODO/IDEAS pruning.** Opraveno směrování maker na
  `~/AGENTS.md` + `~/.claude/PROMPTS.md`, lokální Claude allowlist zkrácen na 11
  pravidel, README status nahrazen aktuálním snapshotem, DIARY rozdělen na posledních
  10 sezení + archiv, doplněna chybějící coverage DONE a sjednocen kontrakt Png2Area
  (17 ISOM kódů + pozadí = `N_AREA=18`, X=`rgb.png`, degradace on-the-fly).
- [x] **(CODE-C2) Bezpečné checkpointy obou živých reconstructorů.** Nový
  `model/checkpoints.py` ukládá každý běh do `runs/<run_id>/` s manifestem,
  historií, křivkou, seed/EMA konfigurací, selection/test metrikou a fingerprintem
  dat. `unet_best.pt` mění jen explicitní `--promote`; checkpoint i promote jsou
  atomické. Overfit a rozpracovaný běh nelze povýšit.
- [x] **(CODE-D3) `cut.py` už nemá silent fallback na poškozeném `.omap`.**
  Chybějící `<objects>`, párový objekt bez `<coords>`, prázdné nebo nečíselné
  souřadnice vyhazují `OmapFormatError` s cestou a identitou objektu. Verify:
  35 904 objektů v šesti referenčních `.omap` prošlo přísným parserem.
- [x] **(CODE-K1) Fialová trať skutečně generuje 5–12 kontrol.** Původní
  `n_ctrl + 1` bodů znamenalo start + jen 4–11 kontrol + cíl; nový helper vytváří
  `n_controls + 2` bodů. Regresní test ověřuje oba krajní počty.
- [x] **Ověření:** 8 unit testů, `compileall connectors generator model tests`,
  72 Markdown souborů bez rozbitých odkazů a `git diff --check`.

## Sezení 126 (2026-06-14) — MPP fix (audit C1/K1): kanonické měřítko dlaždice 1,33 → Png2Area test mIoU 0,537 → 0,683
Detail: [diary/2026-06-14.md](diary/2026-06-14.md#sezení-126--mpp-fix-audit-c1k1-kanonické-měřítko-dlaždice--png2area-test-miou-0537--0683-hal3000).
- [x] **(DOCS-K1 = CODE-C1, KRITICKÉ) Nesoulad fyzického rozlišení vyřešen var. a1.** Kořen: dlaždice 2,18 m/px,
  ale `inject.py`/`purple.py` počítaly symboly z 1,33 (mylně „= separate.TARGET_MPP", což je interní separační
  downscale) → symboly 1,64× velké; `eval_real` byl na 1,33 = rozbitý jen TRÉNINK. **Měření PŘED rozhodnutím**
  (volba uživatele „nejdřív měřit"): reálné skeny 0,15–0,32 m/px (`.pgw`), gen render 2,18 (`generator.py:1811`).
  **Volba var. a1** (resample párů na kanonické MPP, ne přepočet symbolů — měřením: tečka 210 na 1,33 = 4,5 px
  čitelná vs 2,18 = 2,75 px splývá). **Kód:** nový SSoT `model/mpp.py` (`CANONICAL_MPP=1,33` + `resample_to_mpp`
  bilineár/nearest + `read_src_mpp` z georef.pixel_size_m, no silent fallback); `inject.py`/`purple.py` PX_PER_MM
  z CANONICAL_MPP; `png2area/tile.py` resample X+Y při tile (+`target_mpp` do `_tiles.json`); `png2point/dataset.py`
  resample v `__init__`; oba `eval_real.py` ← CANONICAL_MPP; `separate.TARGET_MPP` ponechán jako oddělený koncept
  (conceptual integrity). Elegance: `PX_PER_MM` nezměněn (7,52) — symboly vždy správné pro 1,33, rozbitý byl jen
  podklad. Verify-against-source: 204 (3 px) = 4 m = ISOM 204 (r 0,4 mm @ 1:10000).
- [x] **Rebuild + retrain obou reconstructorů na 1,33.** Re-tile korpusu (10093/2029/1672 dlaždic, 2,7× víc).
  **num_workers 0→4** v `png2area/train.py` (+persistent+pin_memory): po 2,7× dlaždicích GPU hladověl (ep 889 s,
  util 0 %) → 251 s/ep (3,5×), GPU 99 %, Windows spawn nespadl. Png2Point nechán na 0 (self.maps v RAM).
  **Synt:** Png2Area test mIoU **0,537→0,683** (+14,6 pb; voda 301 0,74, 308 0,79, 521 0,73, 501 0,27). Png2Point
  multiseed 3 seedy **medián 0,874** (0,856/0,874/0,893; vs 0,888 starý — menší/správné symboly, nesrovnatelné).
- [x] **(A1) Re-benchmark `eval_real` obou na správném měřítku.** Png2Area per-odstín Bedř **0,256→0,336** (+8 pb),
  Blatná 0,357 (~0). Png2Point realita **0,19–0,36 → 0,23–0,43**: 204 stabilní (F1 0,46–0,69, R ~0,55–0,60),
  **210 z kolapsu (0,04) na 0,11–0,18** na 2/3 map (recall nízký = řídká detekce pole teček). MPP fix = správná
  oprava; reálný gap (striping/ostrost, voda 0,22, 210 recall) = samostatné fronty mimo MPP.
- [x] **(CODE-C2 částečně) Promote nejlepšího seedu** — multiseed driver kopíruje per-seed checkpoint a promotuje
  best (ne poslední) → `unet_best.pt`. Obecné run_id řešení v `train.py` zbývá.
- [x] **Přesun ChatGPT audit souborů** `AUDIT_{CODE,DOCS}_260614.md` z kořene → `docs/`.

## Sezení 125 (2026-06-14) — A2a Png2Point re-trénink odhalil seed-nestabilitu → vyřešena focal bias initem (medián 0,888) + ChatGPT audity
Detail: [diary/2026-06-14.md](diary/2026-06-14.md#sezení-125--a2a-png2point-re-trénink-odhalil-seed-nestabilitu--vyřešena-focal-bias-initem-medián-0888--chatgpt-audity-hal3000).
- [x] **(A2-derivát) Png2Point nestabilita VYŘEŠENA focal prior bias initem.** A2a re-trénink (purpura) dal
  mF1 0,194 vs Sez. 106 0,897 → measure-first diagnostika odhalila, že trénink je seed-nestabilní (mF1 **0,15–0,90**,
  model obětuje řídké 204 dle inicializace; „0,897" = nereprodukovatelný outlier). Kořen = chybějící focal prior
  bias init (`smp.Unet` default bias=0 → mrtvá fáze prvních ~15 ep). Fix `build_model` bias=−log((1−π)/π), π=0,01
  → multiseed 3 seedy **medián 0,888 / rozptyl 0,019** (vs baseline 0,247/0,167 = +0,64 medián, 8,8× menší rozptyl,
  204 ~0,92 / 210 ~0,86). `train.py --seed` (reprodukovatelnost) + `--ema` (opt-in, slepá ulička). Stabilní model
  `unet_best_biasinit_seed2.pt`. Purpura paired dopad podružný (−0,043). „0,897"→0,888 v živých docs.
- [x] **(B6) Registr pseudo vrstev do GLOSSARY** — tabulka 516 plot / 310 split / pseudo body 204/210 →
  mechanismus → kde žije (meta.json / `.omap` / stats / Y rastr). Kodifikuje [[pseudo-layer-writes-meta-and-omap]].
- [x] **ChatGPT audity DOCS+CODE (uživatel, vedlejší session) ověřeny + drobné opravy.** Hlavní nález OVĚŘEN
  proti zdroji: nesoulad rozlišení 2,18 vs 1,33 m/px (symboly 1,64× velké) → `[!]` TODO (designové rozhodnutí).
  Opraveno: `eval_real._OUT.mkdir` (D2), hardcoded „0,897" v eval_real (D1), `cut.py` docstring (K2), GLOSSARY
  soft mIoU↔pixel-acc (DOCS-C1). Zbytek → TODO audit blok + %END/ntbhej.

## Sezení 124 (2026-06-13) — A2a Png2Area: purpurová augmentace snížila dopad tratě
Detail: [diary/2026-06-13.md](diary/2026-06-13.md#sezení-124--a2a-re-trénink-png2area-s-purpura-augmentací-dopad-fialové-49--12-pb-hal3000).
- [x] Png2Area přetrénován s fialovým course-overprintem pouze ve vstupu X. Na témže modelu
  klesl dopad vložené tratě z −4,9 na −1,2 pb (clean mIoU 0,566 → purple 0,554);
  nejvíc se zacelily třídy 501.1 a 301. Produkční kód se v tomto sezení neměnil.

## Sezení 123 (2026-06-13) — A2a fialový přetisk tratě do augmentace obou reconstructorů
- [x] **A2a (Fable5 audit) — purpurový course overprint do `_augment` obou modelů.** Nový sdílený
  `model/purple.py` (mimo `generator/` = respekt hranice paralelního vlákna): `overprint_course(rgb, seed)`
  kreslí náhodnou ISOM trať (701 start △ / 702 kruh / 703 čísla / 704 spojnice / 706 finish dvojkruh)
  JEN do X; Y/heatmapa se nemění (trať není mapový obsah → model se ji učí ignorovat). Rozměry
  verify-against-source z ISOM 2000 §4.7 (papír 1:15000, `PX_PER_MM≈7,52` izomorf `inject.py`: kruh 45 px /
  start 53 px / čára 3 px); barvy `purple_a/b` z `map_gt.ISOM_REF` (Sez. 72). Integrace do
  `png2area/dataset._augment` (po D4, před degrade) + `png2point/dataset.__getitem__` (po inject, před
  degrade), prob 0,5. Vizuál ověřen na reálné dlaždici (sedí jako závodní mapa s tratí).
- [x] **Measure-first: dopad fialové na purpura-naivní Png2Area.** `temp/probe_purple_impact.py`
  (force `APPLY_PROB=1`, izolace bez D4/degrade): **test mIoU 0,537 → 0,488 (−0,049)**; nejvíc
  **501.1 −0,255 / 301 −0,139 / 406 −0,078 / 206 −0,066**. Doložený problém + baseline hodnoty A2a;
  `eval_real` ho nevidí (čisté skeny bez tratě) → měřitelné jen vloženou purpurou. Re-trénink = carry.

## Sezení 122 (2026-06-13) — Buschdörfl E2E + globální kartografická konfigurace + sémantický GT
- [x] **Buschdörfl (`classId=1201511`) georeferencován z mobilní fotografie.** SIFT/FLANN + robustní
  homografie proti Livelox skenu: 943 inlierů, medián reprojekce 1,88 px. Přenosný výstup v
  `maps/Buschdörfl/` obsahuje `.omap`, render, sken, mobilní foto, ortofoto, GT a verify artefakty.
- [x] **Crop páru na skutečný bbox mapového obsahu.** `pairs._content_quad_sjtsk` bere bbox validních
  pixelů `gt_labels != IGNORE`, transformuje jej přes Livelox affine a používá jej pro extent i finální
  `clip_omap_to_quad` před rasterizací Y. Uzavírá `[!]` nález `856040` ze Sez. 118.
- [x] **Globální nastavení AzimutLabu.** Nový kořenový `azimutlab.toml` + striktní
  `generator/project_config.py` bez silent fallbacku. `symbols.vegetation_boundary` přijímá jen
  `"416"` / `"416.1"`; default `"416.1"`. Volba řídí RGB i `.omap`, zapisuje se do `meta.json`.
  Zelená 416.1 používá přesnou tmavou barvu z OOM šablony a dle ISOM vynechává hranice kolem 410 Fight.
- [x] **Sémantický GT zachovává vodu a ISOM 520.** `gt_labels.png` zůstává kompatibilní runnability
  `0–4/255`; nový `gt_semantic_labels.png` přidává `5=voda`, `6=520`. Georef větev zapisuje
  `gt_semantic_grid(.png/_vis.png)` a `bg_gt.png` ji používá místo ztrátové runnability vizualizace.
  Buschdörfl: 6 436 vodních + 21 174 olivových pixelů v georef gridu; vizuálně ověřeno.
- [x] **KPI po změně generátoru:** čistý síťový běh **58,6 %** (plocha 69,5 / linie 58,9 / bod 52,8).
  První běh 50,8 % byl neplatný (hlasitě vynechané ZABAGED rocks po odmítnutí sítě), nebyl reportován.

## Sezení 121 (2026-06-13) — A1.b reálný benchmark Png2Point: 204 přenáší, 210 kolabuje → A1 CELÁ dokončena (HAL3000)
- [x] **A1 (Fable5 audit, KRITICKÁ) — část (b) Png2Point reálný benchmark → A1 DOKONČENA CELÁ.** Fokus z Příště 120
  (volba „Go!"). Detekce bodů 204/210 na REÁLNÉM kartografově skenu (ne injekci), dvojice optikou Sez. 120.
  - **Nález 0 (measure-first):** probe `temp/probe_points.py` (crosswalk-aware, point type=1) → Bedř/Blatná málo
    skalnaté; primární mapa **Velbloud** (680× 204 / 603× 210, S-JTSK Křovák, `.pgw` JE na HAL3000 — Sez. 111 chyběl
    na ntbhej). Slovanka (2481/3473) odložena = UTM33. Všech 6 map má `.png`+`.pgw`+`.omap`.
  - **Nález 1 — 204 Boulder PŘENÁŠÍ:** recall **0,66–0,67 stabilně napříč 3 mapami** = model reálné balvany ČTE.
    F1 204: Blatná 0,68 / Velbloud 0,63 / Bedř 0,38 (gap = precision/halucinace, ne recall). Plný černý kruh (r≈3 px)
    přežije přechod injekce→sken. Georef ověřen vizuálně (rot_sign=−1 platí i pro Velbloud, dosud neověřený Sez. 111).
  - **Nález 2 — 210 Stony KOLABUJE:** F1 ~0,04, precision ~0,02, recall 0,18/0,27/0,00. Drobné tečky (r≈1 px) splývají
    s rastrem/texturou skenu → halucinace stony pole na zrnité ploše. Injekční trénink na tuto třídu nepřenáší.
  - **Nález 3 — striping artefakt (maska pole nutná):** PŘED maskou 210 pred 59k/30k/49k peaků, **90 %+ FP MIMO mapové
    pole** na bílém okolí (= striping doménový artefakt jako Png2Area Sez. 120). Přidána `_map_area_mask` (hrubý mappix
    → reuse `map_gt._detect_map_area` Sez. 73) = zpřesnění MĚŘENÍ, ne ladění modelu (dohoda STOP na modelech dodržena).
  - **Čísla (po masce pole):** Velbloud mF1 0,335 (204 0,63 / 210 0,04) · Blatná 0,364 (0,68 / 0,05) · Bedř 0,191
    (0,38 / 0,00). Syntetická mF1 = 0,897.
  - **Kód:** nový **`model/png2point/eval_real.py`** (izomorfní s png2area): DRY reuse `paper_to_scan_px` z png2area přes
    `importlib` (kolize jmen modulů); `parse_carto_points` (type=1 + crosswalk), `predict_peaks` (tiled sigmoid heatmap
    + NMS), `_map_area_mask`, detekční helpery kopie z `train.py` (SSoT tam). py_compile OK, vizuál overlay → `temp/`.
  - **Vstup pro A2:** hlavní gap = striping/ostrost + halucinace u jemných symbolů, NE fialový přetisk (204 čte i bez něj)
    → informuje pořadí A2 („benchmark může ukázat, že fialová je menší problém než ostrost").

## Sezení 120 (2026-06-13) — A1 reálný benchmark Png2Area DOKONČEN: model čte mapu, gap je metrický (HAL3000)
- [x] **A1 (Fable5 audit, KRITICKÁ) — Png2Area reálný benchmark dotažen + povýšen.** Fokus z Příště 119 (volba
  uživatele). Dotažena diagnostika rozporu „vizuál čte ✓ vs mIoU 0,058 ✗" ze Sez. 119.
  - **Nález 1 — Sez. 119 reportovalo BUG:** `0,058` byl artefakt chybné rotace (`__main__` default `rot_sign=+1`,
    zatímco závěr diáře + vizuální overlay používaly `−1`). Ověřeno oboustranně: `+1` → 0,058, `−1` → reálná čísla.
  - **Nález 2 — model reálné mapy ČTE:** soft metrika na sémantických skupinách (open/les/voda/…) = **88–90 %
    pixelů správně** (vizuálně i číselně). Doménový gap existuje, ale je výrazně menší, než tvrdilo Sez. 119.
  - **Nález 3 — per-odstín gap je metrický, ne kategorický** (confusion matice): hlavní žrout = záměna **401↔403**
    (open vs rough-open, fuzzy i pro kartografa; Bedř 401 60 % → 403) + kolaps vzácných tříd bez supportu
    (402/308/501/voda Bedř n=489 ~0). Les naopak dobrý (recall 406 80 % / 408 81 % / 410 74 %). Striping +
    modrá halucinace = reálné artefakty (model-improvement, mimo dohodu STOP na modelech).
  - **Čísla:** Bedřichovka per-odstín mIoU **0,256** / soft pixel-acc **0,895** (grouped mIoU 0,466) · Blatná
    **0,354** / **0,880** (grouped 0,411). Per-odstín srovnatelné se syntetickou 0,537.
  - **Kód:** povýšeno `temp/eval_real.py` → **`model/png2area/eval_real.py`** (DoD A1; oprava cesty `parents[2]`,
    dokumentace vyřešeného stavu) s **dvojicí metrik** (per-odstín + soft-skupiny `GROUPS` + confusion dump) —
    volba uživatele. Verify z nové lokace identický (0,256/0,466/0,895), py_compile OK. Scratch `temp/eval_real*.py`
    smazány (subsumovány). Vizuál Y/pred/sken uložen do `temp/` (georef verify, oko = source).
  - **2. KPI zavedeno** (volba uživatele): dvojice (per-odstín / soft-skupiny) reportovat při každém tréninku
    (GLOSSARY „Domain gap", TODO KPI blok). Png2Point realita zbývá (A1.b).
  - **Censure (viz Kudos/Censure):** Sez. 119 zapsalo nepoctivé číslo 0,058 — ověřená hodnota (`rot_sign=−1`) byla
    jen v overlay/závěru, ne v default cesty `__main__`. Lekce: ověřená hodnota musí být i v default, ne jen v komentáři.

## Sezení 119 (2026-06-12) — A1 reálný benchmark Png2Area: vizuál čte mapu, číselná mIoU propastná (HAL3000, scratch)
- [~] **A1 reálný benchmark (Fable5 audit A1)** — postaven ve `temp/` (nepovýšen). **Fáze 1 vizuál HOTOVÁ**
  (`eval_real_probe.py`): model přenáší na reálný sken (Bedřichovka/Blatná struktura sedí, **voda 301
  excelentní na Blatné = Sez. 118 fix validován reálně**); artefakty striping + modrá halucinace.
  **Fáze 2 číselná ROZPRACOVÁNA** (`eval_real.py`): id-based parser kartografovy .omap (1230 obj) +
  crosswalk 2000→2017 + **georef paper→sken px vyřešen** (rot_sign=−1 net rotace 0, flipY=1) →
  **reálná mIoU 0,058 vs syntetická 0,537**. Nález: vizuál vs pixel-exact IoU se rozcházejí. Carry:
  diagnostika nízké IoU (odstínová záměna? metrika?) + povýšení `eval_real.py` → `model/png2area/`.


- [x] **Png2Area přetrénován na N_AREA 18 (voda 301 fix, precondition Sez. 110).** Celý řetěz: verify 1 páru
  (voda v Y 0 → 81 511 px) → regen 205 párů (`skip_existing=False`, ok 205/fail 2) → re-tile (`301` váha 0,0 →
  0,996) → plný trénink 40 ep. **TEST mIoU 0,537, voda 301 IoU 0,65** (dříve strukturálně 0 = cíl SPLNĚN, fix
  prošel celým řetězem do modelu). mIoU nesrovnatelné s 0,568 (Sez. 103 BEZ vody). `unet_best.pt`.
- [x] **B2 (Fable5 audit) — `ISOM_REF` křížový komentář o divergenci** doplněn do `compare_real_vs_gen.py`
  (komentářová cesta, audit dával alternativu k přejmenování). `map_gt.py` komentář už měl.
- [x] **Voda = no-draw zóna** — princip do `CLAUDE.md` (clip, ne z-order; výjimky most/hráz/břeh/tok).
- [x] **KB `docs/kb/isom-colour-order.md`** + lokální PDF `iof-printing-colour-2022.pdf` — IOF colour order
  (rešerše Fable5 vedlejšího vlákna): modrá plocha POD hnědou → vrstevnice přes vodu = CLIP, ne z-order.
  Vyvrátilo původní z-order návrh PŘED implementací (verify-against-source). Odkaz z `isom-issprom.md`.
- [x] **6 testovacích nálezů uživatele → TODO** (blok zrání generátoru): cut.py tučná hrana řezu / 416 přes vodu
  / 416 open↔open / layout text v poli (`946084`) / crop na mapový obsah (`856040`) / zubaté ploty 516.
- [x] **Reakce na Fable5 audit Sez. 117** — audit TODO blok SJEDNOCEN (duplikát smazán, Censure 1), B1/B5/B7
  doplněny, B2 [x]; AUDIT status sekce (PŘIJATO/VYŘEŠENO/ČÁSTEČNĚ). A1 reálný benchmark = next.
- [x] **Rozhodnutí:** KPI<0,95 jako gate na páry vyvrácen (Png2Area konzumuje jen plochy, voda byl BUG); dohoda
  STOP na modelech → zpět ke zrání generátoru.

## Sezení 118 (2026-06-12) — Png2Area voda 301 + auditní reakce a nálezy generátoru
Detail: [diary/2026-06-12.md](diary/2026-06-12.md#sezení-118--png2area-re-trénink-voda-301-fix-mf1--miou--6-testovacích-nálezů--reakce-na-fable5-audit-hal3000).
- [x] Po opravě stale kódu `301.1`→`301` prošel celý řetězec regen 205 párů, re-tile a
  trénink: test mIoU 0,537, voda 301 IoU 0,65. Doplněna no-draw zásada vody,
  `docs/kb/isom-colour-order.md` a šest konkrétních nálezů generátoru do TODO.

## Sezení 117 (2026-06-12) — Meta-audit Fable 5: prompt + audit + úkoly + %BEGIN zapojení (HAL3000, docs-only)
- [x] **`docs/AUDIT_FABLE5_PROMPT.md`** — opakovatelné zadání meta-auditu (role/postup/struktura/omezení;
  datum parametrické; od 2. vydání povinná tabulka stavu minulých námitek VYŘEŠENO/TRVÁ/ZHORŠENO).
- [x] **`docs/AUDIT_FABLE5_260612.md`** — 1. vydání: **A1 doménový gap syntetika→sken neměřen (KRITICKÁ)** /
  A2 purple+geometrická augmentace chybí / A3 KPI Goodhart / A4 architecture drift (odklad „plné revize"
  Sez. 79) / A5 nula testů / A6 artefakty bus-factor / A7 Png2Line bez %THINK + B1–B7 + C (9 pravidel pro
  kolegy) + D (nerozbíjet). Podloženo Explore agentem nad kódem (0 testů, metriky jen syntetika, degrade
  bez fialové, 15× sys.path).
- [x] **TODO sekce „Audit Fable 5 — námitky → úkoly"** — 12 položek s kódy/stroji/podrobnostmi pro
  jednodušší modely; 2 existující body povýšeny (reálný transfer 204/210 [!] ← A1; geometrická augmentace
  ← A2). Hotové se přesouvají do DONE s kódem námitky.
- [x] **%BEGIN zapojení (`docs/PROMPTS.md`)** — nový bod 7 audit-check (TL;DR + sekce C nejnovějšího
  auditu) + rozšíření bodu 2: cadence AUDIT_FABLE5 ≥25 sez / milník + úsudkové práce (audity, velká
  %THINK) nejsilnějším modelem, slabší model nabízí handoff.
- [x] **Censure 1 → oprava auditu:** A3(2) původně „rozšířit KPI referenci o Livelox mapy" — KPI potřebuje
  vektorovou `.omap`, Livelox je raster-only → referenci rozšíří jen další kartografické `.omap` (resources).

## Sezení 116 (2026-06-12) — Rock v2 over-detection density gate → KPI 48,2 → 55,0 % (+6,8 pb, ntbhej)
- [x] **Density gate proti rock v2 over-detection 206** (`rock_relief.DENSITY_GATE_PCT=0,08`). Fokus z Příště 115
  (volba uživatele „rekalibrace pseudo / over-detection"). **Measure-first** (`temp/probe_rock_overdetect`, fetch-once +
  threshold-sweep): klíčový nález — rozdíl skutečná vs falešná skála NENÍ práh sklonu (oba >46°: Šulcák max 83° / Bedř 77°),
  ale **regionální HUSTOTA px ≥46°**: skalnaté ≥0,16 % (SV 0,158 / HS 2,22 / golden Šulcák 3,72 %) vs ne-skalnaté ~0,04 %
  (Bedř 0,042 / Blatná 0,037 = mikroreliéf zářezů/břehů) → **88× separace**. Páka `MIN_AREA_M2` sama golden poškodí (−27 %
  @ 500 m²), density gate ne. **Volba uživatele** (3 možnosti přes AskUserQuestion): density gate ~0,08 % (per-mapa podíl
  px ≥ práh; pod → 0 ploch 206 + hlasitý INFO log, no silent). Správný pro PLOŠNÝ 206 = skalnatá oblast (osamělé skály jdou
  přes body 204/207). **Verify:** golden Šulcák **48 polygonů beze změny** (3,72 % >> práh), Bedřichovka **0** (gate, log).
- [x] **KPI verify: 48,2 → 55,0 % (+6,8 pb)** — NAD baseline Sez. 109 (54,9 %). Bedř 45,1→50,6 / Blatná 51,4→59,3;
  **bod sub 45,8 → 51,8** (210 Stony přestřel z falešné skalnatosti pryč). Naplněná predikce Sez. 110/115 opravena.
  204/210 zmizely z žebříčku děr → vrchol kompasu nyní 508/403/417/409/416 (+ nový 202 Passable rock face 120/0).
- [x] **TODO (nálezy uživatele Sez. 116):** kameny/balvany (204/210) NEumisťovat na tenké liniové plochy podél komunikací
  (SV, symboly zakryté cestou — řešení izomorfní vyloučení vody `_clip_fences_off_water`: road-corridor exclusion v pseudo
  masce) + 102.1 zdůrazněná (index) vrstevnice na násobky 50 výškových metrů (feature). Obojí zapsáno do TODO, neimplementováno.

## Sezení 115 (2026-06-11) — Rock_relief OOM + border fix (measure-first) + diagnostika poklesu KPI (ntbhej)
- [x] **Rock_relief OOM fix** (`rock_relief.py`). Measure-first (`temp/probe_rock_oom`): f64 sklon pipeline @ 50 Mpx
  peak **3,3 GB** = OOM (8,4 GB volných + běžící generátor). Nález **f64+del = f32+del = 1,9 GB** → páka je `del`
  mezivýsledků (`z,zs,gy,gx,slope_deg`) PŘED `_contour_rings`, NE dtype (peak je v `_rock_mask`/label int32) → zvolen
  **f64+del** (zachová přesnost prahu 46°, žádné golden riziko) + `_contour_rings` padded float32 (behavior-preserving).
- [x] **Rock_relief border noData fix**: `_fetch_assembled_grid` zachytí `RuntimeError` za hranicí ČR → **NaN dlaždice
  + hlasité warning** (no silent fallback); `errstate` v sklonu → NaN propadne `slope>=46`→False (bez skal u hranice).
  Drobnost: `import logging` module-level (byly 2 lokální). Verify: golden Šulcák **48/2,56 ha = match**; izolovaný HS
  847 bloků/peak 2,6 GB + SV 130 bloků/2 dlaždice NaN; **plný regen HS/SV/LS se skalami EXIT 0** (HS 847× 206, skály zpět).
- [x] **Diagnostika poklesu KPI 54,9→48,2 %** (požadavek uživatele „ořez mohl ovlivnit KPI"). Tři izolační běhy:
  **ořez (Sez. 114) VYVRÁCEN** (`temp/diag_clip_kpi`, +0,9 pb — čistá výhra), **grivace (Sez. 112) VYVRÁCENA**
  (`temp/diag_griv_kpi`, identické — georef-only), **hlavní příčina pseudo body 204/210 −3,25 pb** (`temp/diag_pseudo_kpi`,
  Bedř −5,1): rock v2 zvýšil 206 g1→g14 na ne-skalnatých → 210 přestřel 962/372 = naplněná predikce Sez. 110. Zbytek
  ~3 pb = Sez. 113 / baseline. → akční TODO (rekalibrace pseudo vs rock v2 over-detection 206).
- [x] **Velbloud.pgw analýza** (dotaz uživatele): automatika z `.omap` nejde (Local CRS bez pixel→S-JTSK, ref_point
  −681000/−971000 + scale 15000 + grivation 11,3° = jen kotva; template = neexistující ortofoto; ne Livelox). Nejjednodušší
  = solver z 2-3 ručních bodů (similarity transform). Volba uživatele: **ODLOŽENO** (carry HAL3000, rock KPI měřit tam).

## Sezení 114 (2026-06-11) — Implementace ořezu cut.py (primitiva + clip_omap + cut_box) + regen DEV map (ntbhej)
- [x] **Geometrická primitiva `cut.py`** (mini-verify 10/10): `cut_point` (nad `_point_in_quad`), `cut_line`,
  `cut_area` (Sutherland-Hodgman). **Nález:** schválený reuse `_split_by_zones_interp` pro `cut_line` NESTAČÍ
  (stavěn na díry uvnitř linie → konce vždy ponechá → neumí in→out ořez na hranici) → přímá konstrukce úseků,
  DRY reuse jen `_interp_grid_at`. Odchylka od architektury Sez. 113, doložena měřením.
- [x] **Orchestrátor `clip_omap(.omap, clip_poly)`** (mini-verify 9/9, paper µm): routing point/line/area, přepis
  `<coords>` se zachováním flagů (close 18 / hole 16), 1 objekt → N kusů (linie), scoped JEN na `<objects>` blok
  (knihovna `<symbols>` netknuta), objekty celé uvnitř beze změny (0 drift). String/regex (ne ET). Verify formátu
  proti Bedř `.omap`.
- [x] **Wrappery + integrace:** `clip_omap_to_quad` povýšen centroid→**geometrický** (quad px → paper µm; zpřesní
  pairs/measure_dod) + nový `cut_box` (papírový obdélník = degenerovaný quad) + DRY `_paper_extent`. Hook `cut_box`
  v CLI `main` (gated real terrain), log vždy (přesah jsou většinou křížící linie → `removed=0`).
- [x] **Verify ořezu = TODO bod 1 DOKONČEN:** Novina přesah 9,6× → 1,00× půlpapíru („Nisa do Vesce" pryč); regen
  všech 5 DEV map ořez 1,00× napříč tvary (uživatel OOM potvrdil „perfektní").
- [x] **Feedback → globální `AGENTS.md`** (SSoT + sync Codex, Claude/Gemini importují živě): doporučenou odpověď
  doručovat přes `AskUserQuestion` (predikce/volba), ne text v chatu. Projektová Claude memory smazána (redundance).
- [x] Paměť `lidove-sady-no-ortofoto` (sdělil uživatel; rozpor s generickým ČÚZK fetch → externí fakt).

## Sezení 113 (2026-06-11) — Test výstupů: 3 bug fixy (voda, plot druh 13, GAP) + %THINK sjednocení ořezu cut.py (mrkla)
- [x] **Balvany 204/210 + plot 516 na vodní hladině** (bod 4, Nová Louka). `_generate_pseudo_boulders` nedostával
  vodní masku; plot se generuje před vodou (z-order). Fix: `_rasterize_water_grid` (outer=voda/holes=souš) odečte
  vodu ze seed + per-tečka 210; `_clip_fences_off_water` vyřízne fence úseky nad hladinou. Verify: balvany 0 px po
  erozi břehu 3 px, plot 0 bodů >3 px od břehu, vizuál nádrže čistý.
- [x] **Plot 516 „uvězňuje" panelák** (bod 3, Lidové sady Hokejka). Fence kolem druhu 13 (zastavěná plocha = otisk
  budovy). Fix (volba uživatele): fence seed jen druh 5 (zahrada), `str(druhpozemkukod)=="5"`; druh 13 zůstává v 520.
- [x] **Čistý les GAP** (bod 2) — rozhodnutí: GAP necháváme bílý, predikci přenecháme UC5 (Novina = benchmark, ne
  tiles). Termín zapsán do GLOSSARY.md. Odhad z ortofota odložen („generalizuj s důkazem").
- [x] **`clip_quad.py` → `generator/cut.py`** (`git mv`, importy measure_dod/pairs aktualizovány) + %THINK schválená
  DRY architektura ořezu (primitiva `cut_line`/`cut_area`/`cut_point` → orchestrátor `clip_omap` → wrappery `cut_box`
  + `clip_omap_to_quad`). Hlavička cut.py + TODO bod 1 nesou plán. **Implementace primitiv = příští blok** (bod 1).

## Sezení 112 (2026-06-11) — Regen všech 7 map + grivace (3 vrstvy) + clip_quad matplotlib fix (ntbhej)
- [x] **Přegenerovány všechny 4 mapy → všech 7 map se všemi podklady** (zadání uživatele). 5 DEV (SV/NL/LS/HS/NV):
      `generate_map` plný režim (vše `real` default + ortofoto). 2 resources (Bedřichovka/Blatná): `_gen_sep`
      (separace ze skenu → `predict_areas_sjtsk` → clip na natočený quad → bg_scan podklad). Vizuál všech 7 OK.
- [x] **Bug: `clip_quad.py` táhl `matplotlib` do PRODUKČNÍ ntbhej cesty → numpy fix.** Bedř/Blatná napoprvé SELHALY
      (`No module named 'matplotlib'`): `from matplotlib.path import Path` (point-in-polygon na quad), ale `requirements.txt`
      řadí matplotlib jako **trénink-only (mrkla, křivky učení)** — produkční separační cesta na něm záviset neměla
      (vada vrstvení). Nahrazeno lehkým numpy crossing-number `_point_in_quad` (žádná nová závislost). Bedř clip
      2110 v poli / −1067 přesah (numpy ray-cast věrohodné počty).
- [x] **Grivace — A) ruční parametr `--grivation <deg>`.** `omap_export.write_omap` +kwarg `grivation` → zapíše
      `declination="G" grivation="G"` do `<georeferencing>` (Local georef → konvergence=0 → grivation=declination;
      OOM vztah `grivation=declination+grid_convergence`; izomorf s historickým skenem `resources/*.omap`). `generate_map`
      +kwarg `grivation`; `_georef_meta` `north="magnetic"` + `grivation_deg`. CLI `--grivation`. **Geometrie i rastr
      zůstávají v S-JTSK gridu** — rotaci nese jen georef metadata (volba uživatele; rotace rastru = curtains odložena).
      E2E ověřeno (Nová Louka 1×1 km → `.omap` + meta 10,88°).
- [x] **Grivace — B) ze skenu pro resources (řeší původní dotaz „odchylka Bedř od skenu").** `measure_dod._gen_sep`
      čte grivaci z `resources/<name>.omap` (`_scan_grivation`, regex `grivation="…"`) → předá do `generate_map` →
      gen.omap orientačně lícuje s bg_scan podkladem. Bedř 10,88° / Blatná 11,90° dosedly. No-silent: chybí atribut → None.
- [x] **Grivace — C) konektor `connectors/magnetic.py` (UC2, sourozenec dmr/zabaged).** `grivation(lat,lon,when)` =
      deklinace (**pygeomag WMM**, offline vestavěné koef., žádný key) + konvergence (pyproj `get_factors`).
      **Znaménko OVĚŘENO empiricky proti reálným skenům** (verify-against-source): `grivace = decl − pyproj_conv`
      (OOM `grid_convergence = −pyproj`; `decl+conv=−2°` nesmysl). Dnešní ~12,7° vs skeny ~11° (starší, deklinace
      roste ~0,13°/rok → trend potvrzuje znaménko). CLI `--grivation-auto` (dnešní) / `--grivation-date YYYY-MM-DD`.
      WMM platnost 2024–2029, mimo VARUJE (no silent fallback). **NOAA WMM REST API blocker** (vyžaduje registraci+key,
      ověřeno „Bad request") → pivot na offline lokální model; **pyIGRF zavržen** (vadná instalace bez coeff souboru)
      → **pygeomag** (+requirements). Self-check proti skenům: ČR grivace dnes 12,6–12,9°.
- [x] **Regen všech 7 s grivací auto** (volba uživatele) — s oponenturou. DEV 5 → `--grivation-auto` (SV 12,91/NL 12,65/
      LS 12,69/HS 12,61/NV 12,75°). **Resources OPONOVÁNY a ponechány ze skenu** (Bedř 10,88/Blatná 11,90): auto by
      obnovilo odchylku od historického bg_scan (~1,8°), na kterou se uživatel původně ptal → lícování > aktuálnost.

## Sezení 111 (2026-06-11) — Korpus GT 264/264 (chunked classify) + ostrý bg podklad + Velbloud .pgw dead-end (ntbhej)
- [x] **Korpus GT 258 → 264/264 — chunked `_classify` (`connectors/map_gt.py`), byte-identický.** RAM blowup `segment_gt`
      doložen měřením JEN v `_classify` (`(N,13,3) int32` ≈ 5,5 GiB @ 35 Mpx; strop ntbhej ~30 Mpx, Sez. 110) — median_filter/
      `_detect_map_area` na uint8 levné. `_classify` přepsán na řez po pixelovém rozpočtu (`_CLASSIFY_CHUNK_PX = 4 Mpx/chunk`,
      bound nezávislý na šířce), `int64→uint8` (13 < 256 referencí). **Per-pixel argmin nezávislý → byte-identický** s
      celorázovou klasifikací. **Volba chunk vs downscale výstupu:** downscale gt by rozbil tvrdý invariant
      `gt.shape == map.png.shape` (`livelox.py:404-406` RuntimeError + affine `separate.py`/`pairs.py`) → 5+ konzumentů;
      chunk = plné rozlišení, nulový zásah. **Verify:** regrese byte-identická (`temp/probe_segment_mem.py` 97 Mpx prošla,
      peak 3,4 GB); 6 obřích map (35–97 Mpx) segmentováno 29–71 s, vizuál OK (`temp/verify_*.png` — bloby izolované, vysoký
      ignore = bílý okraj); py_compile 7 konzumentů. Korpus na ntbhej **264/264 GT**.
- [x] **Ostrý bg podklad v OOM — `generator/gen_backgrounds.py` (dotaz uživatele „proč rozostřený").** Příčina: bg_scan
      warpován **do gen pixelového gridu** (Bedř gen rgb.png jen 1182×1498 @ 2,18 m/px) + klauzule `min(1.0, _BG_MAX_PX/max)`
      **zakazovala supersampling** → 135 Mpx sken (0,26 m/px) zmáčknut na ~1,72 m/px (cap 1500 ani nebyl binding). Oprava
      (3 edity): odstraněna `min(1.0,…)` (povolen supersampling — jemné kroky vzorkují detail ze zdroje) + `_BG_MAX_PX`
      1500 → **6000** + DRY helper `_bg_out_size` (dvě identické kopie v `add_backgrounds`/`add_resources_scan_background`).
      Georef nedotčen (`sx = pw/out_w` škáluje úměrně). Bedř bg_scan **1182×1498 → 4734×6000** (0,43 m/px). Verify: před/po
      (`temp/bg_sharp_cmp.png`), overlay lícování (`temp/overlay_*.png`), py_compile. Přegen Bedř+Blatná (`_gen_sep`);
      ostatní auto při dalším `measure_dod` (úprava kódu invalidovala cache přes `_code_mtime`).
- [x] **Velbloud `.pgw` rekonstrukce → doložený DEAD-END (measure-first, `temp/probe_pgw_recon.py`).** Cíl: odblokovat
      rock_relief v2 KPI před/po na skalnaté mapě na ntbhej. Negativní: (1) `Velbloud.omap` nese jen minimální georef
      (scale 1:15000 + grivation 11,3° + round-number ref_point) + ortofoto template `LIBE25.jpg` (neexistující cesta) —
      **žádný pixel→S-JTSK transform**; (2) rekonstrukce z object-bbox SELHALA při validaci na známé pravdě (Soví vrch:
      implikované m/px W→0,194 vs pravda 0,095 = 2× mimo; aspekt W≠H) — scan rotován grivací (magnetic-north) + okraje,
      grid-aligned bbox ≠ pixelový obdélník. Potvrzeno: `.pgw` rotace = grivation (Bedř −10,88° = griv 10,88°), ale origin
      a m/px neodvoditelné. **Rock KPI zůstává HAL3000 carry** (fabrikace `.pgw` = nesmyslné KPI; no silent fallback).
- [x] **AGENTS.md commitnut** — Codex protějšek projektového `CLAUDE.md` (mirror; jiný thread, Codex/ChatGPT spolupráce Sez. 110).

## Sezení 110 (2026-06-11) — Korpus na ntbhej + deep research + rock_relief v2 + ChatGPT %AUDIT:CODE (ntbhej)
- [x] **Livelox korpus na ntbhej 57 → 264 map (+207), GT ~258.** `livelox.py batch` (870 eventů, idempotentní, GT inline;
      ok 204/skip 38/fail 628 = staré smazané bloby). 22 map bez GT diagnostikováno (tranzient batch-time, standalone projde)
      → `temp/fill_missing_gt.py` doplnil 15. Nález: **`segment_gt` paměťový strop na ntbhej ~30 Mpx** (alokace N_px×13×3 int32
      = 5 GiB @ 35 Mpx) → 6 obřích map (76-97 Mpx + 2× 35) carry downscale-before-segment.
- [x] **Deep research veřejných zdrojů (deep-research skill, 103 agentů) → RESEARCH.md.** Uťat session limitem (7 potvrzeno
      3-0, zbytek neověřen — NE vyvrácen). Negativní nález: žádný otevřený archiv ZDROJOVÝCH vektorů (.omap/.ocd) → vektorová
      GT jen z `generator()`. ČSOS Archiv = jen metadatový index (96 dpi watermark náhledy + JSON API, ne data). Leady
      k doověření: arxiv 2405.04634 (ML nad OB mapami), Copernicus SWF + AOPK CC-BY (vegetace/mokřady), OO Mapper sample.
- [x] **`rock_relief` v2 — pevné 0,5 m/px + tiling fetch + despeckle r=1px** (algoritmus; KPI carry). Z jiného threadu
      handoff + zlatý vzorek (`docs/kb/rock-detection-v2/`). Probe doložil −43 % poddetekce (`TARGET_PX_M=1,5`) → `ANALYSIS_RES=0,5`
      + `_fetch_assembled_grid` (dlaždice ≤ `MAX_FETCH_PX`, seamless assembled grid → morfologie 1×, čistší než handoff §7,
      `dmr.py` netknut, reuse `fetch_elevation_grid` + inverzní transformer 5514→4326); −27 % (`OPEN_M` r=2px) → r=1px.
      `MAX_TOTAL_PX=50 Mpx` strop → zhrubne s hlasitým varováním. **Verify:** golden Šulcák 48/2,56 ha = match (48/2,53,
      tol ±2/±5 %), seamless tiling (vynucené 4 dlaždice identické), reálný HS 2×2 km 159 bloků, E2E `generate_map` HS 1×1 km
      = 49× 206 + 411× 204 pseudo. Kontrakt funkce identický. **KPI carry HAL3000/Velbloud** (Bedř/Blatná neskalnaté).
- [x] **ChatGPT 5.5 %AUDIT:CODE — verify-against-source (5 nálezů opraveno, kritický + 4).** Ověřeno proti zdroji, ne slepě.
      **① KRITICKÝ — voda 301/301.1, Png2Area Y zahazoval vodu.** `generator.py:3968` zapisuje vodu `301` (combined, od 06-01),
      `omap_raster.AREA_ZORDER` měl `301.1` (od vzniku 06-04). Měřeno: Lidové sady 58 obj → 0 v labelech. **Git timeline:**
      voda 301 (06-01) ≪ omap_raster (06-04) ≪ trénink Sez. 103 (06-09) → **omap_raster NIKDY vodu nezachytil; oba Png2Area
      tréninky (mIoU 0,640/0,568) se vodu nenaučily.** Oprava `301.1`→`301` + **root-cause SSoT** (`omap_export.AREA_CODES` =
      `frozenset(omap_raster.AREA_ZORDER)`, import bez cyklu) → voda 58→58/11→11/8→8. **② stale `_tiles.json`** (16 vs 18) →
      `class_weights()` guard selže nahlas. **③ no-silent-fallback** `build_tiles`/`load_split` → fail na prázdný split /
      chybějící páry (`--allow-missing`). **⑤** `zabaged.map_path_to_isom` 503 fallback → `ValueError`. **⑥** stale komentáře
      dataset.py. py_compile 6 souborů + 8 konzumentů OK. → Png2Area re-trénink povýšen `[!]` precondition (voda poprvé v Y).

## Sezení 109 (2026-06-10) — Diagnostika KPI pák (negativní nálezy) + podklady regrese + ořez přesahu na quad (ntbhej)
- [x] **Měření KPI pák (`temp/sim_kpi.py`) — obrat intuice:** doplnit zeleň KPI **snižuje** (406 −3,5 / 408 −2,7 pb,
      gen globálně podstřeluje → ředění); páka = **oprava přestřelů** (521 budova +2,35 / kombo +4,98 pb). Kompas
      areas: base 406/408 kreslíme (podstřel), 410 skoro chybí, pattern 409/407/404 = nula (separace pattern-slepá).
- [x] **Budovy 521 diagnostika — suppression VYVRÁCENA.** Přestřel = POČET (Bedř 634 vs 19), ne velikost/tvar.
      90 % gen budov v 520 (rasterizace), sim +2,95 pb, ALE **kartograf v 520 kreslí normálně (volba uživatele)** →
      suppression špatný směr (dotaz PŘED kódem zabránil chybě). Z-order 520 = falešný poplach (olivová se kreslí
      62,7 %; Censure 2× chybný barevný práh L1<55 / bucket).
- [x] **Bodová detekce 417 ze skenu VYVRÁCENA měřením** (`temp/probe_417`). Zelený kroužek = stejná zelená jako
      veg plochy/pattern/křížky → komponenta 1/60, matched filter 14731/60. Strukturální: bodová separace klasikou
      patří **Png2Pointu (CNN)**, ne separaci (izomorf pattern třídy Sez. 90). Censure: „417 unikátní" před měřením.
- [x] **Přesah Stráže n. Nisou doložen** (`temp/probe_clip`, vhled uživatele): gen kreslí axis-aligned bbox, 282/634
      budov (44 %) mimo natočený reálný quad = okolní sídla. Měřicí hull už ořezává → ořez na quad **KPI +0,26** =
      čistota produktu + tréninkových párů (ne KPI skok).
- [x] **Oprava podkladů — regrese „zase vypadly".** `measure_dod --table` přepisovalo produkční gen.omap bez
      podkladů (`_gen_sep` `ortho=False`, `templates=0`). `gen_backgrounds.add_resources_scan_background` (izomorf
      `add_backgrounds`, resources sken + `.pgw` afinní místo Livelox quadu; helper `_affine_inverse`) + hook v
      `_gen_sep`. Ověřeno: `templates=1`, bg_scan lícuje (verify georef).
- [x] **Ořez přesahu na quad — `clip_quad.py` (nový).** `clip_omap_to_quad`: vynech .omap objekty s centroidem mimo
      natočený quad + maska renderu na bílou. **String-regex, NE ET round-trip** (ET rozbil `inject_image_templates`
      + risk OOM). Zapojeno: `measure_dod._gen_sep` (quad = rohy skenu) + `pairs.build_pair` (quad = Livelox
      `g["quad"]`, PŘED rasterizací Y → konzistentní pár). Bedř 823 + Blatná 197 přesahů pryč, **KPI 54,9 nezměněno**,
      render rohy bílé (vizuál), .omap validní. `pairs` e2e carry HAL3000 (ntbhej korpus syrový 0/57 gt); izolovaný
      sanity (name=gen, idempotence) OK.

## Sezení 108 (2026-06-10) — Velký úklid: 4 audity rozsekly carry + nález pseudo body mimo meta.json (HAL3000)
- [x] **%CALIBRATE (+23 → 0):** C-1 projektový `CLAUDE.md` „2→3 podadresáře model/" (png2point od Sez. 105) +
      16→18 tříd; **C-2 root-cause carry** → `docs/PROMPTS.md` %BEGIN bod 4: pravidlo „úklidové audity prioritně
      na ntbhej" (běží kdekoli → HAL3000 okno patří CUDA práci; +23 vznikl 3 sezeními odkládání na HAL3000).
- [x] **pruning (+2 → 0):** TODO 307 → 228 ř (−26 %). KPI blockquote 58 → 14 ř (historie Sez. 94-107 → odkaz
      DONE/diáře) + 10 hotových `[x]` (Sez. 99-104) smazáno z TODO.
- [x] **%AUDIT:DOCS (+4 → 0):** 13 nálezů (agent, ověřeno proti DONE/`ls model/`). Kritické: `connectors/README`
      → smazaný `forest.py` (Sez. 102); architecture/README/GLOSSARY „2 modely / Png2Point neexistuje" → existuje
      (Sez. 106); GLOSSARY KPI 50,3 → 59,1. Doporučené: architecture UC5 zamrzlá Sez. 92/96 → +Png2Area 0,568
      (N_AREA 18) +Png2Point +KPI éra; Python 3.12+→3.14; „PoC"→pilíř.
- [x] **%AUDIT:CODE (+1 → 0):** 0 kritických (py_compile 16/16, forest_age mazání + focal revert čisté). D1
      (16→18 komentáře png2area/train.py), K1 (run_proxy → caller v compare_isom), D2 (legacy poznámka
      compare_real_vs_gen.py, volba NECHAT). **Oponoval D3** (sjednocení rozsahů elipsy `(3,12)` inject vs `(3,8)`
      gen by rozbilo KPI kalibraci → zdokumentována záměrná divergence); K2 ponechán (ilustrativní čísla).
- [x] **#9 STATISTICS.md regen → nález pseudo↔meta (measure-first).** Snapshot 2026-06-01 zastaralý → regen 5 DEV
      + `stats.py`. **Odhaleno:** pseudo body 204/210 (Sez. 107) jdou do `.omap` (HS 204:5588/210:12258, `isom_usage`)
      + KPI, ale **NE do `meta.json`** (`rocks_info` sestaven před přidáním pseudo) → STATISTICS je nevidělo, ač
      pseudo 310 marsh ano = **porušený izomorfismus**. **Oprava:** pseudo → `rocks_info` (sdílí sekci s reálnými
      skalami; 210.1 → ISOM 210 Stony ground) + 210 do `stats.py` SYMBOLS → re-regen. STATISTICS věrně: 204 (HS
      5588), 210 (HS 12258). KPI nedotčeno (čte `.omap`). **Lekce → memory: pseudo vrstva MUSÍ psát do meta i .omap.**
- [x] **Carry úklidu VYNULOVÁN** (poprvé po dlouhé době čistý cadence). 14 souborů (5 kód + 9 docs), py_compile čistý.
      Handoff připraven na ntbhej (Příště Sez. 109).

## Sezení 107 (2026-06-10) — Png2Point body INTEGROVÁNY do generátoru: KPI 50,3 → 59,1 % (+8,8 pb) (HAL3000)
- [x] **Pseudo injekce bodů 204 Boulder + 210 Stony ground do `gen.omap`** (`generator._generate_pseudo_boulders`
      + `_draw_stony_dot` + `omap_export` USED_CODES += `210.1`). ZABAGED tyto body nevede v reálné hustotě
      (kompas: 204 gen 3/orig 1064, 210 gen 0/orig 975 → bodové sub-KPI 18,4 %). Reuse injekční geometrie z
      `inject.py` (NE natrénovaný model — ten je pro reconstructor): 204 = kruh, 210 = pole teček `210.1` (samostatné
      `type=point` objekty). **Gated `pseudorealistic`, BEZ vlastního flagu** — visí na `rocks="real"` → `point_base`
      i `only_real` ji korektně vypnou (izomorf 310 marsh / 516 plot). Scope 204+210; **207 VYŘAZEN** (kompas 16/17
      = už pokryto, přidání = přestřel).
- [x] **Maska = DOLOŽENÁ SKALNATOST** (volba uživatele „věrná distribuce", po measure-first): 206 skalní plochy
      (DMR sklon, `rock_relief`) + reálné ZABAGED 204/207 body, dilatováno o 150 m (suť/balvany kolem stěn).
      **Sklon-maska ZAVRŽENA** (nález: sklon ≠ skalnatost — svažitá-ale-neskalnatá Bedřichovka dostala 50 % hmoty
      v bodech, orig jen 3,8 % → přestřel ředil headline → jen +0,3 pb). Doložená skalnatost koreluje s reálnou
      hustotou per mapa (Velbloud 24,3 % gen vs 22,0 % orig = skoro přesně).
- [x] **Kalibrace na SHARE, ne absolutní Σ** (nález: gen celkově podstřeluje, Σgen ≈ ⅓ Σorig → „správný absolutní
      počet" bodů dá nadměrný share → ředění). Hustota 500 boulderů/km² + 12 polí/km² masky.
- [x] **VÝSLEDEK: KPI 50,3 → 59,1 % (+8,8 pb)** (Bedř 52,8 / Blatná 59,4 / Velbloud 65,1), **bod sub-KPI 18,4 →
      54,3 %** (+35,9 pb), plocha/linie beze změny. 204/210 zmizely z žebříčku děr → vrchol teď 417/419/418 (veg
      body, bod 2 Příště) + 508/306 (linie) + 409/404/410 (pattern vegetace gate). Vizuál: body clusterované na
      skalnatých svazích (věrné). Censure: ukvapený závěr „headline na body necitlivé" (+0,3) byl artefakt přestřelu
      — measure-first per-mapa ho opravil na +8,8. Zbývající přestřel Blatné (48 % vs 18,5 %) = data-gate limit
      (skalnatost není v geodatech, věrná per-mapa distribuce nejde — jako vegetace/310).

## Sezení 106 (2026-06-10) — Png2Point DOKONČEN: point_base podklad + root-cause 204 + plný trénink test mF1 0,897 (HAL3000, CUDA+korpus)
- [x] **Probe 210 = pole bodů (oponentura uživatele „210 je area")** — `temp/probe_210.py` 5 resources map:
      210 v `.omap` VÝHRADNĚ `type=point` (~4641 obj / **0 area**; Slovanka 3473 / Velbloud 603 / Blatná 340 /
      Soví 193 / Bedř 32). **Blatná smoking-gun:** area var `210.0` v knihovně, použita **0×** (vše point `210.1`).
      Sémantika jevu (plošný) vs realizace (pole bodů) → reconstructor řídí realizace → 210 na Png2Point. Uživatelův
      postřeh ke Slovance (kameny dle velikosti: 207/206.1/203 největší, 210 = registr nejmenších) → IDEAS **B1**
      (dvojí sémantika 210 + velikostní škála = klasifikační výzva).
- [x] **Krok 1 — `point_base` render bez bodů** (`generate_map(point_base=True)` master flag): vynutí
      `rocks/landmarks/barriers="off"` + vynechá kreslení extrémů 109/110/111 do rgb (point_symbols zůstávají
      v `.omap`/meta). Plochy/linie/vegetace = kontext (206 padá s rocks=off, MVP). **Verify pixelový diff**
      (area vs point_base): 0,062 % rozdílu, rozeseté body → odstraní JEN body. Cena 73 s/mapa.
- [x] **Krok 2 — batch 40 point_base map** (`pairs.build_pair(point_base=True)` → `gen_pointbase/rgb.png`, reuse
      separace, bez area_labels; `build_pairs(point_base=True)` + `pointbase_subset(n)` proporční napříč splity +
      CLI `pairs.py pointbase 40`). **40/40 OK** (28 train / 6 val / 6 test).
- [x] **Krok 3 — dataset přepis na point_base + random-crop 512** (`png2point/dataset.py`): z předkrájených area
      dlaždic (s body) → plné point_base rendery do paměti + random-crop za běhu (`_pointbase_paths` čte podle
      splitu co existuje; `CROPS_PER_MAP=16`); D4 + injekce + degrade beze změny.
- [x] **Krok 4 — sigma + ROOT-CAUSE 204 + trénink.** sigma 204 2→3 / 210 1,5→2. **Gate selhal** (210 ✓ 0,94,
      **204 ✗ 0,00** i 150 ep). **Diagnostika `temp/diag_204.py` VYVRÁTILA mou velikostní hypotézu:** imbalance
      **19×** (210 ~203 / 204 ~10 pozitiv); JEN 204 (bez 210) loss exploduje (n_pos malé → neg člen); **204 hustý
      (~90) → naskočí F1 0→0,70** → příčina = **hustota pozitiv vs focal `n_pos` normalizace přes kanály**, ne
      velikost. **Per-kanál focal ZKOUŠENA → ZHORŠILA** (neg/malé n_pos exploduje → oba 0) → vráceno + varovný
      komentář. **Oprava:** `inject.n_boulder` (2,14)→**(40,120)** (reframe Sez. 79: detektor ikonek, hustota jen
      pro balanc). **Gate PROŠEL train mF1 0,92.** **Plný trénink (lr 1e-3 cosine, 60 ep): TEST mF1 0,897**
      (best ep 50, val 0,907 → bez leaku) — **204 F1 0,93** (P0,96/R0,90) / **210 F1 0,86** (P0,81/R0,92).
      Křivka zdravá (val plató ~0,90 od ep20). `unet_best.pt` → `resources/point_model/`. **Druhý funkční
      reconstructor po Png2Area.** POZN.: F1 = detekce injektovaných ikonek na point_base, ne reálných skenů
      (analogie Png2Area); KPI dopad až s integrací bodů do gen.omap (Příště).

## Sezení 105 (2026-06-09) — Png2Point pipeline (inject/dataset/train) + diagnostika podkladu (HAL3000, CUDA+korpus)
- [x] **Png2Point = druhý reconstructor, MVP pipeline POSTAVENA** (`model/png2point/{inject,dataset,train}.py`,
      izomorf s Png2Area). Volba uživatele (%BEGIN fokus): využít vzácné HAL3000 okno na největší doloženou KPI
      páku (bod sub-KPI 18,4 %, díry 204 7,8 / 210 7,3 pb). Přístup (A1/A2/A3, schváleno): **injekce symbolů**
      (zdroj GT) · **heatmap regrese** (architektura) · **204+210 první** (po verify ze spec).
- [x] **Verify bodových ISOM kódů** (`isom-2000-spec.pdf` + `template_classic.omap`): 204 Boulder = point, plný
      černý kruh r 0,4 mm; **210 Stony = pole jednotlivých teček 210.1** r 0,15 mm rozestup ~1,2 mm (potvrzuje
      Sez. 96 — kartograf kreslí kamenitou zem polem teček). Plná bodová knihovna v template (109/110/111, 203.x,
      204/205/207, 210.1, 311/312, 417/418/419, 524-527, 530/531) = rezervoár pro rozšíření registru.
- [x] **`inject.py`** — registr `POINT_CLASSES` (rozšiřitelný), stamp ikonek (plný kruh) + GT **Gaussian heatmapa**
      (CenterNet splat, element-wise max), sampler (204 rozeseté body / 210 jittered pole teček); PX_PER_MM 7,52
      @ 1,33 mpp / 1:10000 + size-jitter. Self-test vizuál OK (zarovnání heat↔ikonka sedí).
- [x] **`dataset.py`** — čte podklad, injekce on-the-fly (jiný seed/epocha = nekonečná augmentace, řeší vzácnost),
      D4 + degradace (reuse `degrade.py`); vrací (X rgb ImageNet-norm, Y heatmaps[N_POINT,512,512]). Val/test/overfit
      deterministická injekce (seed=idx).
- [x] **`train.py`** — smp U-Net `classes=N_POINT` + sigmoid, **penalty-reduced focal loss** (CenterNet α2/β4),
      metrika = peak NMS (3×3 max-pool) → greedy match v TOL_PX → **F1 per třída**, BF16, checkpoint best, křivka.
- [x] **Diagnostika (overfit gate SELHAL → root cause)** — gate F1≈0.01 (recall vys./precision ~0). `temp/diag_point.py`
      izoloval: (1) **úzká sigma (1px peak na full-res) nejde naučit** (protichůdný gradient) → sigma 2,5-4 + LR 1e-3
      konverguje (loss→0,09); (2) **PODKLAD: gen render obsahuje vlastní bodové symboly** (gen 204/207/208, landmarks)
      identické s injektovanými, ale bez GT → nejednoznačná funkce → na čistém/bílém podkladu model memorizuje 204 i
      210 perfektně, na gen podkladu selhává i na 1 dlaždici. **Rozhodnutí uživatele:** čistý podklad bez bodů,
      podmnožina (measure-first) → Příště Sez. 106.

## Sezení 104 (2026-06-09) — KPI přesah-ořez integrován (49,8 → 50,3 %) + podklady do gen.omap (HAL3000, CUDA+korpus)
- [x] **Přesah-ořez integrován do `measure_dod._counts_for_map` (KPI + KOMPAS SSoT)** — z prototypu Sez. 103.
      **Q1 verify** (`temp/verify_parse_consistency.py`): `parse_objects_with_centroid` (bez ořezu) = `isom_usage`
      byte-identicky (3/3 mapy) → „před/po" měří JEN ořez. Helpery `_mapped_area_mask` (sken non-white → close →
      largest comp → **convex hull**, DS=8) + `_gen_centroids` + `_clipped_gen_counts` (centroid gen objektu: paper µm
      → gen px → S-JTSK přes `rgb.pgw` → sken px přes inverz sken `.pgw` → test do/ven masky). No-silent-fallback:
      chybí sken/pgw/meta → varuj + neořez. **KPI 49,8 → 50,3 % (+0,5), obousměrné ZPŘESNĚNÍ:** Bedř 48,4→51,2 /
      Velb 46,4→48,7 (ořez přestřelu 520/521) / **Blatná 54,7→51,1 (−3,6)** (gen podstřeluje, přesah maskoval).
      **Bodový gap ZOSTŘEN sub 29,0 → 18,4 %** → Png2Point jednoznačně další páka (204 7,8/210 7,3 pb). Docstringy
      modulu+`_counts_for_map` aktualizovány. py_compile OK.
- [x] **Podklady do korpusového gen.omap — přepínatelné OOM background templates** (zadání Sez. 103 bod 5, NETRÉNINKOVÉ).
      **DRY extrakce** `omap_export._image_template_element` + `inject_image_templates` (N templates, `first_front_template=N`
      = vše pod mapou) z `ortho_template` → `write_omap` ortho cesta refaktorována na helper (**behavior-preserving**,
      single-template = identický XML, ověřeno). **Nový modul `generator/gen_backgrounds.py`** (post-process, mimo render
      core — SLAP): `add_backgrounds(gen_dir)` warpne `map.png` sken (inverz `_map_affine` rotovaného quadu) + `ortho.png`
      + `gt_grid_vis.png` (`_georef_grid` axis-aligned) do gen px gridu → `bg_scan/ortho/gt.png` (downscale 1500 px) →
      vloží templates. `pw/ph` dopočítáno z `rgb.pgw` mpp×W×1e6/scale. **GT-IGNORE fix:** magenta (255,0,255)→bílá
      (obecný `recolor` na zdroji; jinak růžová zaplní čtverec). No-silent-fallback: chybějící ortho/GT → log+skip.
      **Verify rastr:** ortofoto overlay lícuje přesně, sken blob v mapované oblasti. **Batch 205/205 OK** (0 fail,
      skip 1 test; 615 bg PNG). OOM verify ruční (uživatel). py_compile OK.

## Sezení 103 (2026-06-09) — Png2Area přetrénován N_AREA 18 + degradér do augmentace + KPI přesah prototyp (HAL3000, CUDA+korpus)
- [x] **Png2Area přetrénován na N_AREA 18 — celá pipeline.** Vše bylo stale 16-class (páry 06-05/Sez.90, tiles/model)
      → 310 vložen doprostřed AREA_ZORDER posunul labely → **regen nutný**. `temp/regen_pairs.py` (skip_existing=False)
      → **205/207 párů** (2 fail: DMR noData mimo ČR + síť timeout; ~11 s/mapa, batch 121 min). build_tiles (smazán
      starý set) train 144/3398 dlaždic, val 31/701, test 30/558. Overfit gate (80 ep) pipeline OK. **Plný 40 ep:
      test mIoU 0,568 ≈ val 0,571 (best ep33, bez leaku)**, plató od ep16. Hlavní plochy 0,70-0,92 (401 0,92/308
      marsh 0,71/521 budovy 0,66/406 0,74/403 0,70), 310 nový 0,46; vzácné strop (501 0,16/402 0,04/208 0,00/301.1
      NaN = 0 % dat). Pokles vs Sez. 91 (0,640) = 18 tříd (víc vzácných nul) + degradace-augmentace. **Vizuál
      `1024666` predikce ≈ GT** → mIoU podhodnocuje (sráží vzácné nuly), model funkční. `unet_best.pt`. **⚠ 3 h/40 ep**
      (degradace per dlaždice v num_workers=0 = bottleneck) → optimalizovat před expansion.
- [x] **Degradér z generator() → tréninková augmentace** (oprava směru, uživatel; návrat k záměru Sez. 80, opakovaný
      lapsus Sez. 80→86→103). `build_pair`/`build_pairs` `degrade` param + `scan.png` ODSTRANĚN → X páru = čistý
      `rgb.png`. `tile.py` X z rgb. **`dataset.py._augment` volá `degrade()` on-the-fly** (variabilní seed/epocha,
      import z generator/). 205 mrtvých scan.png smazáno. Regen NEopakován. Paměť `no-degradation-in-generator-phase`.
      Propagace: TODO/GLOSSARY/architecture/spec. py_compile 3/3 + smoke OK.
- [x] **Pravidlo „No silent fallback" → projektový CLAUDE.md** (Doménové zásady) — selži nahlas/zarytě varuj, nikdy
      tiše náhradní cesta; lekce cache skip-existing Sez. 99, `_missing_pgw` vzor.
- [~] **KPI/KOMPAS přesah-artefakt — nález uživatele + měřicí prototyp** (integrace ZBÝVÁ, Příště). gen obdélníkový
      výsek vs nepravidelná mapa → ČÚZK objekty přesahují → nerovnoměrný přestřel zkresluje KPI (proporce neruší).
      `temp/proto_clip.py` (maska = non-white sken → convex hull; gen objekty → S-JTSK přes rgb.pgw+sken.pgw → ořez):
      **+4,4 pb Bedř/Velb** (přestřel 520/521), **Blatná -4,8** (tam gen podstřeluje, přesah maskoval → poctivěji) =
      ořez obousměrné ZPŘESNĚNÍ. Past „bílá=nemapováno" neplatí uvnitř (401 open forest). Vizuál masky lícuje (georef OK).

## Sezení 102 (2026-06-08) — 508 measure-first (VYVRÁCENO) + forest_age proxy ARCHIVOVÁN (kód smazán) (ntbhej)
- [x] **508 Narrow ride měřením VYVRÁCENO jako páka** (+0,34 strop / +0,59 gaming) — fokus bod 3 Příště Sez. 101.
      Measure-first (`temp/measure_508.py`+`sim_508_kpi.py`): **smíšený podstřel, jiný faktor každá mapa.** Bedř
      (ISOM 2000) orig 185/15,8 km vs gen 13/3,5 km → **délka 0,22× = POKRYTÍ** (ČÚZK `Lesní průsek` = řídká
      administrativní vrstva, kartograf vidí průhledy v terénu navíc → data-bound jako 310/416); medián úseku
      orig 67 m / gen 233 m. Blatná (ISOM 2017-2) orig 125/8,4 km vs gen 19/6 km → **počet 0,15× / délka 0,72× =
      GRANULARITA** (gen kreslí 4,7× delší kusy). **Crosswalk past doložena ze zdroje:** Bedř má `509.1 Narrow ride
      - short line` (dedikovaný symbol pro krátké úseky) → 2000:509→2017:508; první skript hledal v Blatné prefix
      509 (=0), opraven na 508. **KPI simulace** (`_counts_for_map`+`_intersection`): i pokrytí STROP (gen=orig) jen
      +0,34 pb, granularita (rozsekat na ~67 m) +0,59 pb = **gaming** (mění jen #`<object>`, ne vizuál/obsah; práh
      arbitrary — odmítnuto u 403 Sez. 101). 508 = ~4 % hmoty. **Závěr: nepáka** = 4. potvrzení vyčerpání ČÚZK
      plošné+liniové páky; vrchol žebříčku = body (204/210/417/419 → Png2Point/mrkla) + pattern vegetace (gate).
      Generátor NETKNUTÝ (ušetřena implementace).
- [x] **forest_age proxy (AOPK věk → zeleň) ARCHIVOVÁN — kód SMAZÁN** (volby uživatele: archivovat teď + forest.py
      smazat). Spouštěč: regen 5 DEV map odhalil přesycenou proxy zeleň (NV skoro celá zelená). Verify-against-source:
      forest_age = **DEV-only kosmetika** (`elif` fallback za separací; `predict_areas_sjtsk` má přednost,
      `measure_dod`/`batch` volaly `"off"`) → do KPI/párů NEvstupuje. **Smazáno:** `connectors/forest.py` (git rm),
      `_generate_real_forest_age`, `_draw_forest_age_area`, větev `elif forest_age=="real"`, `--forest-age` flag/param,
      validační řádek, meta-větev, `measure_dod --proxy` režim (`run_proxy` — bezpředmětný; vyřešil i carry Příště
      bod 2 Sez. 99-101), volání v `batch.py`/`pairs.py`. **Přejmenováno** (separace dědí): `FOREST_AGE_FILL/CLASS/
      NAME` → rozpuštěno do `PREDICT_AREA_*` (identické hodnoty) + ~6 drift komentářů. **Verify PROŠEL:** py_compile
      7/7; **KPI 49,3 % IDENTICKÉ** (separační produkční cesta byte-zachována); NL `--location` **bílý les** (1716
      obj, −341 = bývalá proxy zeleň). Behavior-preserving konstrukcí. **8 živých docs** propagováno (CLAUDE/README×3/
      architecture/GLOSSARY/data-sources/generator-procedural §4.9p → archiv-pointer). DEV mapy bílý les; pseudo-
      realistic vegetace pro lokality bez skenu = nový směr (TODO/Příště).

## Sezení 101 (2026-06-08) — 416 Distinct vegetation boundary z mezitřídních hranic (KPI 46,1 → 49,3 %) (ntbhej)
- [x] **403 měřením VYVRÁCEN jako páka** (+0,1 pb) — measure-first roztřídil podstřel (orig 673/gen 152):
      slévání vyvráceno (gen 39 %/12 % PLOCHY), práh ubírá objekty ne plochu, **systémová příčina** = reálné
      mapy kreslí 403 jako dominantní open (Bedř 356 vs 401 38 = 9×), gen mapuje ČÚZK open→401. Volba uživatele
      „TTP→403" **měřením vyvrácena: granularitní propast** (ČÚZK 1 multipolygon 139,5 ha → ~46 gen obj vs
      kartograf 356 plošek; KPI počítá objekty → simulace přesunu 401→403 = +0,1 pb). Generátor NETKNUTÝ (ušetřen
      zbytečný refaktor). Bedř scan-odstín 403 (sytě žluté B=64 → `_is_pale_yellow` 401) = artefakt Livelox-
      kalibrace (KPI měří resources) → volba **dokumentovat-neladit** (zásada Sez. 82 „neleštit separaci").
- [x] **416 Distinct vegetation boundary** (`generator.py`, **největší KPI díra 633/0**) — measure-first potvrdil
      SILNOU páku (KPI simulace 0,6× = +5,4 pb). Mezitřídní hranice predikčních veg ploch (volba uživatele, ISOM
      416 = hranice různé runnability 403↔406↔408↔410). `_predict_veg_boundaries`: contour každé veg třídy
      (rock_relief) → per-bod prstenu klasifikuj vnější souseda (jiná veg vyšší třídy, dedup B>A) → souvislé
      mezitřídní úseky → **délkový práh `BOUNDARY_MIN_LEN_M`=50 m** (krátké šumové fragmenty separace odpadnou;
      reálné 416 medián 45-90 m) → RDP → polyline. `_draw_boundary` černá tečkovaná (template 416 = Black 100%
      dotted, izomorf `_draw_ride` 508). Hook v predict bloku (z `veg_area_mask_img`), 416 → `linefeature_features`
      (**0 změna omap_export** — sym["416"] z template), `mask_boundaries.png`, `stats.py` +416. **LINIE → bez
      Y-area dluhu** (Png2Line neexistuje; .omap stačí pro KPI/kompas).
- [x] **KPI 46,1 → 49,3 % (+3,2 pb)**; sub-linie 47,7 → **58,3 % (+10,6)**; oba mapy + (Bedř 44,1 / Blatná 54,6);
      416 z headline díry na 5. místo (gen 154/orig 633). Práh laděn měřením (prototyp `temp/proto_416` 50 m =
      optimum; render rozlišení dává gen 416 0,24× reálného, per-mapa plató 38=50=49,3).
- [x] **Verify**: noise byte-identický (proc 65, md5 shodný git-stash — 416 striktně v predict bloku, noise cesta
      nedotčena); vizuál Bedř (416 tečkovaně sleduje okraje zřetelných veg ploch, věrné OB stylu); py_compile OK.

## Sezení 100 (2026-06-08) — KPI fáze generator() (proporční podobnost distribuce ISOM symbolů) (ntbhej)
- [x] **KPI definován + zaveden** (přání uživatele „chci JEDEN kvantifikátor, projekt se utápí v metodologii").
      `generator/measure_dod.py` DEFAULT režim = **proporční podobnost distribuce ISOM symbolů**: histogram
      intersection `Σ min(orig_share, gen_share)` (každý vektor norm. na vlastní Σ → ruší obal-artefakt), per-mapa
      pak průměr. Jedno číslo 0–100 %. Penalizuje chybějící typ (gen=0) i přestřel (`min` ukrojí přebytek).
      4 volby uživatele: proporční / KPI primární (DoD→`--dod` archiv) / 1 agregát + 3 sub (plocha/linie/bod) /
      **cíl 55 % plošná + ≥ 85 % s Png2Point/Line**. Nahrazuje binární DoD ≥ 90 % (nedosažitelný strop 54 %,
      slepý k inkrementální práci — dissolve 520/marsh 310 ho nehnuly).
- [x] **Implementace + DRY**: `_counts_for_map` (sdílený sběr orig/gen Σ per kód, reuse kompasu i KPI) +
      `_intersection` (jádro) + `run_kpi` (default). `main` (binární DoD + analytický cut) → `--dod`; `--table`
      kompas zůstal. Robustnost: `MAPS` filtr na dostupné `.pgw` + warning (Velbloud.pgw chybí na ntbhej →
      graceful místo `FileNotFoundError`; memory `gitignored-availability-verify-not-assume`).
- [x] **Baseline KPI 46,1 %** (Bedř+Blatná; plocha 60,9 / linie 47,7 / **bod 29,0** = Png2Point dluh). Žebříček
      proporčních děr (kam mířit): 416 (633/0, −8,4 pb) / 210 / 204 / 403 / 508 / 417. **Kvantifikace stropu:**
      linie+body = 61 % symbolové hmoty (Σ 4639/7572) → bez reconstructorů strop ~50 %, dnešní 46 % je NA plošném
      stropu (tvrdá potvrzení censure Sez. 99 — plošná coverage páka z ČÚZK vyčerpaná).
- [x] **Verify**: `--table` po DRY refaktoru byte-identický (403/521/416/204 + Σ shodné = regrese 0); `--dod` jede.
      Generátor NETKNUTÝ (KPI nemění gen výstup).
- [x] **%BEGIN +bod 6** (`PROMPTS.md`): KPI + headline kompasu vždy v rekapitulaci (zdroj = poslední z diáře;
      přeměřit jen po změně generátoru → trend). DoD definice v `TODO.md` nahrazena KPI definicí (SSoT).

## Sezení 99 (2026-06-08) — 310 Indistinct marsh (pseudo fáze 2) + oprava kompas cache (ntbhej)
- [x] **Measure-first 310/313** (5 `resources/*.omap`, `temp/measure_marsh*.py`) — rozbil zadání bodu 1:
      **313 „vodopád" = mýtus** (v datech 313 = Spring BOD / 2017-2 313 0× ve všech 5; vyřazeno jako 210 Sez. 96);
      **310 Indistinct = plošný+hojný** (area všude, Slov 89× > 308) ALE z ČÚZK neodvoditelný — ZABAGED nerozlišuje
      zřetelnost (crosswalk `.crt`: 2017-2 310 ← 2000:311; 308 Marsh = 2000:310). Kritérium splitu: rašeliniště/bažina
      **geograficky binární** (NL 100 %/HS,NV 0 %) i velikost **nediskriminuje** (překryté distribuce) → obě vyvráceno.
- [x] **310 split náhodou ~55 %** (volba uživatele: trénovací mapy nemusí být reálné, reframe Sez. 79). `generator.py`:
      `_marsh_indistinct(cx,cy)` deterministický spatial-hash (jen `pseudorealistic`; `--only-real` = vše 308 = projekce,
      izomorf fence 516). `_draw_marsh_area` rozliší 308 (plné čáry) / 310 (2× řidší PŘERUŠOVANÁ staggered šrafa, věrné
      template `type=2` line_spacing 900 + point_distance 1725). Konzistentní trojice (paměť Sez. 90): generátor +
      `omap_export` USED_CODES/AREA_CODES +310 + `omap_raster` AREA_ZORDER +310 (**N_AREA 17→18** → Png2Area přetrénovat).
      `stats.py` +310. Verify: **noise byte-identický** (241 obj + md5), NL E2E `.omap` 308=2/310=7 + vizuál.
- [x] **Bod 3 „meta bug real_sections []" = NEEXISTUJE** (paměť stale-todo-verify-rationale): `veg_area` se zapisuje
      správně (224 položek, provenance predict, doloženo `maps/Blatná/meta.json`). Sez. 98 viděl STALE `meta.json` přes
      skip-existing `_gen_sep` (.omap existoval → regenerace přeskočena). Drop.
- [x] **fix kompas cache** — skip-existing `_gen_sep` dělal **kompas slepým ke změnám generátoru** (vracel cached `.omap`
      → `measure_dod` měřil starý stav, klamal napříč sezeními). `_code_mtime()`: cached `.omap` starší než nejnovější
      `generator/`+`connectors/` `.py` = stale → přegeneruj. Ověřeno (mtime logika). 2 commity (feat/fix).
- [x] **KOMPAS přínos 310 ~0** (poctivé přiznání, Censure sobě): ZABAGED mokřady na DoD mapách řídké (Bedř gen 0,
      Blatná gen 1) → DoD se nehnul. Hodnota v Livelox párech, ne na 3 resources mapách. Lekce: měř „vede ZABAGED vrstvu
      na DoD mapách?" PRVNÍ (paměť measure-coverage-source-on-dod-first).

## Sezení 98 (2026-06-07) — %AUDIT:CODE měřicího kódu + dissolve olivové 520 + plot 516 (ntbhej)
- [x] **Sync 16 commitů pozadu → ff-pull** na `d9152be` (sezení 90–97 z mrkla) PŘED prací (paměť stale-clone-fetch-first).
- [x] **Nález struktury:** `resources/` na ntbhej lokálně JE (proti předpokladu Sez. 97), jen neúplné (chybí `Velbloud.pgw`).
      Lekce: „gitignored ⇒ chybí" je nespolehlivý odhad, stav `resources/` se mezi stroji liší → ověřit `ls`.
- [x] **%AUDIT:CODE** `compare_isom.py` + `measure_dod.py` (~700 LOC od Sez. 89, 0 krit./2 dop./3 kosm., drift Sez. 95→96):
      D1 mrtvý `symbol_geometry()` smazán (nahrazen `used_geometry` v Sez. 96; `_TYPE_GEOM` ponechán) + propagace
      `architecture.md` (odkaz + strop 58→54 %); D2 DRY helper `_resolve_targets` (crosswalk-resolve 2×→1×);
      K1 osiřelé klíče `coverage()` dictu (`covered_t`/`real_freq`/`rnames`); K2 broken paměť odkaz. Behavior-preserving
      (smoke `compare_isom` CLI, `_resolve_targets(526,'2000')→{521}`).
- [x] **Přestřel olivové 520 → dissolve do bloků** (measure-first `temp/measure_520.py`: 91–96 % z RÚIAN privát drobných
      parcel medián 146–323 m², LS 52 % výseku; kompas 9×). Bez `shapely` (není v `.venv`) → **dissolve přes rastrovou masku
      `contourpy`** (reuse `rock_relief._contour_rings`/`_group_holes`). `_generate_real_surfaces`: 520 → 2 masky (celá
      olivová → bloky `_draw_surface_area`; RÚIAN-privát → plot). LS 19762→2023, HS 2066→448; kompas 520 9×→**1,3×**.
- [x] **Plot 516 Fence** (pseudo fáze 2, ZABAGED nevede Sez. 57 → věrohodná dekorace kolem zástavby; vypne `--only-real`):
      (a) **práh 0,5 ha** `FENCE_MIN_AREA_M2` (measure-first `temp/measure_fence.py`: gen 160→21≈orig 24; HS 621→61);
      (b) **RDP narovnání** `_rdp` eps 5 m (contourpy schody → přímé spojnice vrcholů); (c) **ticky DOVNITŘ**
      `_draw_fence_line` per-tick `_point_in_ring` test (ISOM 516 spec „tags inside"). Helpery `_fill_mask_rings`/
      `_dissolve_mask_to_polys`/`_draw_fence_line`; konstanty ISOM_FENCE/FENCE_*. `omap_export` USED_CODES +516, `stats.py` SYMBOLS +516.
- [x] **Regrese: noise proc baseline byte-identický** (git-stash before/after diff = 0). py_compile čisté. 5 DEV regen.
- [x] Propsáno: diář + DIARY index + DONE + TODO + README/GLOSSARY/architecture/generator-procedural/generator-README/katalog.

## Sezení 97 (2026-06-07) — Handoff HAL3000 → ntbhej (bez práce, jen %BEGIN + zarámování fokusu)
- [x] **Krátké handoff sezení** — uživatel po %BEGIN „na tomto stroji končíme, přechod na ntbhej + %END".
      Žádná kódová ani docs-featurová práce; generátor i měřicí nástroje NETKNUTÉ, proc baseline drží.
- [x] **Zjištění pro přechod — coverage measure-work je mrkla-blokovaná** (prevence pasti Sez. 86 C-1):
      `resources/` (5 vzor. `.omap`) + `resources/livelox/` korpus jsou gitignored → na ntbhej nejsou.
      Příště bod 1 (310/413 measure-first v `resources/*.omap`) i bod 2 (kompas `--table` z párů korpusu)
      = mrkla-only; body 3/4 (Png2Line/Png2Point trénink, expansion) = CUDA/korpus → taky mrkla-only.
- [x] **ntbhej fokus zarámován = %AUDIT:CODE** — cadence-zralý nejen počtem (Sez. 89 → 8 zpět, práh ≥8),
      ale i **LOC ≥500 PŘEKROČEN**: měřicí nástroje od Sez. 89 přidaly ~700 LOC (`compare_isom.py`
      +144/+39/+38, `measure_dod.py` +177/+123/+90 přes Sez. 94/95/96), nový kód `symbol_geometry`/
      `used_geometry`/`_load_crosswalk`/`--table` nikdy neauditován. Audit = čisté čtení → běží bez korpusu/CUDA.
- [x] Propsáno: diář Sez. 97 + DIARY.md index + DONE (tento záznam). Commit `docs(session)` + push → ntbhej ff-sync.

## Sezení 96 (2026-06-07) — 210 Stony = bodový gap (ne plošný) + kompas tabulka orig/gen
- [x] **A1 measure-first nad 210 Stony ground (fokus bod 1 Příště) → VYVRÁCENO plošné zařazení.**
      Změřena reálná geometrie 210 v 5 mapách: **VŠECHNY objekty jsou `type=point`** (210.0/210.1
      „individual dot"/„jediná tečka"; Slovanka 3473, Velbloud 603, Blatná 340, Soví vrch 193, Bedř 32).
      Reální kartografové kreslí kamenitou zem jako POLE TEČEK, ne plochu s pattern výplní → **210 patří
      na Png2Point dluh, ne plošný generátor** (volba uživatele „překlopit na Png2Point"). Měření ušetřilo
      psaní zbytečného DMR-drsnost konektoru.
- [x] **Kořen vady opraven — analytický cut byl nadhodnocen (variant-aware geometrie).**
      `compare_isom.symbol_geometry()` bral geom z template podle PRIMÁRNÍHO kódu (210 = area „slow
      running"), ale `isom_usage` kolabuje integer-prefixem → reálně použitá point varianta se ztratila →
      cut počítal 210 (975 obj) do plošného stropu. **Přidána `compare_isom.used_geometry(path)`** (geom
      REÁLNĚ použitého symbolu z mapy, majorita přes objekty) → `coverage()` vrací `used_geom` →
      `measure_dod` cut měří geom z reálné mapy, ne template. **Pravý plošný strop = 54 %** (z 58).
      GAP: plocha 9 typů/894 obj (Png2Area) · linie 19/1974 (Png2Line) · **bod 21/2213 (Png2Point)**.
- [x] **Kompas tabulka `measure_dod.py --table`** (volba uživatele „toto bude náš kompas") — tři kapitoly
      (Png2Area/Png2Line/Png2Point), řádky ISOM 2017-2 kódy, sloupce Σ objektů ORIG (reálné `.omap`) vs
      GEN (separační) přes 3 mapy, geom z reálné mapy. Nad rámec DoD %: ukazuje PROPORCE. Nálezy: **Png2Point
      gen Σ149/orig 3960 (~4 %)** = nejhorší; gen **PŘESTŘELUJE** 520 Settlement 838/94 (9×), 521/cesty;
      **PODSTŘELUJE** vegetaci (403/406/408); **416** veg boundary 1111/0 = největší missing linie.
- [x] **IDEAS sekce „Pokrytí do statistické míry četnosti + kompas tabulka"** (4 body uživatele):
      (A) nedetekovatelné ISOM → generovat věrohodně do obvyklé/ruční míry četnosti (cíl = kompas Σ);
      (B) Png2Point trénink injektováním symbolů na náhodné známé souřadnice (GT zdarma); (C) 416 jen do
      statistické míry (hranice vegetace většinou nejasné); (D) pattern 402/404 splývá do 401/403 (separace
      pattern-slepá) = kontext over-countu, 401/403 split = pokrok. Oponentura: kompas po statistickém fillu
      potřebuje provenance rozpad (real-derived vs predict-fill), jinak gen sloupec klame.
- [x] Generátor NETKNUTÝ (jen měřicí nástroje `compare_isom.py`/`measure_dod.py`) → proc baseline drží
      triviálně. py_compile OK, standalone `compare_isom` + `--proxy` ověřeny. memory `generator-coverage-is-the-ceiling`
      aktualizováno (210 = bod, strop 54 %, „měř geom z reálné mapy ne template").

## Sezení 95 (2026-06-07) — Analytický cut (plošný strop 58 %) + DoD baseline přepnut na separaci
- [x] **Analytický cut — `compare_isom.symbol_geometry()`** (volba uživatele „změřit strop nejdřív"):
      mapuje ISOM kód → geometrie z OOM `<symbol type>` (1=bod/2=linie/4=plocha/8=text/16=kombi,
      doloženo distribucí v `template_classic.omap`, sedí s názvoslovím Png2Point/Line/Area). `coverage()`
      rozšířen o `covered_t` (2017 cíle i pro pokryté kódy). py_compile OK.
- [x] **Rozpad DoD podle geometrie v `measure_dod.main()`** — **plošný strop 58 %** (per-mapa pokrytí,
      kdyby gen dokreslil všech 13 chybějících typů ploch; pak průměr). **DoD ≥90 % je plošně NEDOSAŽITELNÉ:**
      zbytek = linie (18 typů, 1952 obj → Png2Line) + body (17 typů, 966 obj → Png2Point), oba modely
      NEEXISTUJÍ. V rámci plošné cesty jsme na 43/58 = 74 % plošného stropu. Tabulka GAP podle geometrie.
- [x] **NÁLEZ (měření před 403 opravou): souvislé 410 v 3 mapách NEJSOU.** map_gt 410 detekuje
      (0,09–0,31 % px), ale separace vrátí **0 polygonů** (MIN_AREA_PX=120 zahodí). Velikosti 410 komponent:
      **1000+ komponent, největší 27–92 px** = tmavě zelený antialiasing na okrajích 406/408, NE souvislá
      fight plocha. **forest_age proxy 410 byl FABRIKACE** → `−410` (Sez. 94 net-nula) je SPRÁVNÉ; honit ho
      zpět = míchat fikci s pravdou. Oponoval jsem zadání „403 bez −410" daty → uživatel rekalibroval.
- [x] **DoD baseline přepnut forest_age → SEPARACE** (volba uživatele). `pairs.build_pair` vyrábí páry
      separací (`predict_areas_sjtsk`), ne forest_age → DoD MUSÍ měřit reálnou produkční cestu, ne fikci.
      `measure_dod`: `_gen_sep` helper (separace, forest_age='off') = výchozí baseline; `run_sep`→`run_proxy`
      (forest_age proxy přesunut na `--proxy`, doložení nadhodnocení). **Baseline 43/37/50 = 43 %** (číselně
      shodné = net-nula, ale POCTIVÉ): 403 covered na všech 3, fiktivní 410 missing na všech 3 (ověřeno
      per-mapa). Plošný gap obj 3231→2126. Generátor netknutý (jen měřicí nástroje), proc baseline drží.
- [x] **Připomenuta mapa projektu** (uživatel „ztrácím se") — UC DAG, smyčka generator()↔reconstructor(),
      pokrytí = strop tréninku. Bez kódu, orientační.

## Sezení 94 (2026-06-07) — DoD nástroj crosswalk-aware + poctivý matched baseline 43 % + separace = páka kvality
- [x] **NÁLEZ: `compare_isom` měřil DoD špatně** — pároval naivně integer prefixem kódu, ignoroval
      crosswalk, který repo **samo dokumentuje** (`docs/kb/isom-issprom.md` Sez. 37-40) i **veze**
      (`docs/kb/ISOM2000-ISOM2017-2.crt`). Reálné mapy jsou většinou **ISOM 2000**, generátor **2017-2**,
      číslování se RECYKLUJE (526 Building 2000 → 521 2017, 509 ride → 508, 516 vedení → 510, 518 tunel
      → 512) → false negativy i pozitivy. **Čísla Sez. 91 „38 %" i memory byla neplatná.**
- [x] **Oprava `compare_isom.py` na crosswalk-aware** (volba uživatele „opravit napřímo"): `_load_crosswalk()`
      (čte `.crt`, integer-prefix), `detect_version()` (526 Budova/Building → 2000, 521 → 2017-2; fallback
      průsek 509/508), `coverage()` (detekce verze → 2000 přemapuj přes crosswalk na 2017-2 → custom ne-ISOM
      kódy **vyřaď z jmenovatele** [volba uživatele] → kód POKRYT, kreslí-li generátor aspoň 1 z 2017 cílů).
      `main()` tiskne verzi + per-missing 2017 cíl. py_compile OK.
- [x] **`generator/measure_dod.py` — DoD driver** (povýšeno ze scratch; operační půlka brány). Extent
      z `.pgw` (4 rohy skenu → S-JTSK axis-aligned obal → WGS84 střed+rozměry), `generate_map` matched
      na obal → `compare_isom.coverage`. Cesta (a) baseline `python generator/measure_dod.py`, cesta (b)
      separace `--sep`. A3 (volba uživatele): Slovanka (UTM33) + Soví vrch (1/4 domapováno) vynechány z DoD.
- [x] **PRVNÍ poctivý mezimapový matched DoD baseline (crosswalk-aware):** Bedřichovka **43 %** (30/69) /
      Blatná **37 %** (22/60, jediná 2017) / Velbloud **50 %** (38/76) → **PRŮMĚR 43 %**. Bez tichých
      výpadků vrstev (layer_errors prázdné). Crosswalk přidal na 2000 mapách +11 (Bedř) až +13 (Velb).
      **Pravý gap je OBSAHOVÝ ne číslovací** (přesně závěr KB Sez. 40): chybí typy 416/107/108/507 (linie),
      418/419/525/527/531 (body), 404/407/409 (pattern plochy), 210 Stony (ZABAGED nevede), mikroformy.
- [x] **Cesta (b) — separace-ze-skenu změřena: páka KVALITY, NE pokrytí.** `map_gt` (na downscaled skenu,
      114 Mpx > strop) → `separate` → predict plochy v S-JTSK přes `.pgw` afinní → `generate_map(forest_age=off)`.
      Výsledek na všech 3 mapách: **nové [403], ztracené [410] → matched DoD net-nula** (43/37/50 beze změny).
      `predict_areas_sjtsk` forest_age **úplně nahradí** (generator.py:3140 `if/elif`, ověřeno) → proxy-410
      zmizí, separace vrátí věrné 403. Závěr: coverage páka = **kreslit nové typy**, ne leštit separaci zeleně.

## Sezení 93 (2026-06-07) — Úklidové sezení: %AUDIT:DOCS + pruning + rename forest_age→veg_area
- [x] **%AUDIT:DOCS** (cadence ≥10 dosažen, vynucený): **0 kritických, 4 doporučené + 1 kosmetický**,
      všechny jeden vzorec — README/architecture status zaostával za 3 mrkla-sezeními (90/91/92).
      Opraveno: **D1** „16 area tříd"→„16 area kódů + pozadí" (po 403 = N_AREA 17; README ×2, architecture,
      GLOSSARY ×3, `model/png2area/tile.py` komentář, generator/README) · **D2** mIoU 0,621→**0,640 / val
      0,654** (stabilizace Sez. 91; README, GLOSSARY) · **D3** 403 Rough open doplněno (architecture, README) ·
      **D4** Png2Area status dopsán (první funkční reconstructor, výsledek + DoD pokrytí; architecture, README) ·
      **K1** forest-age pointer „nahrazen separací Sez. 82" (GLOSSARY). 4 agentí falešné poplachy **zamítnuty
      proti zdroji** (`5122` „export selže" = posílá string „512.2"; forest-age „rozpor" = archivace doložená;
      `[[…]]` „broken" = wiki-link konvence; `predict_areas_sjtsk` CLI = interní kwarg).
- [x] **IDEAS/TODO pruning** (cadence ≥12 dosažen): TODO Png2Area blok 22ř. `[~]` historie → strukturované
      pod-checkboxy (Area `[x]` pointer DONE / class-balanced expansion `[~]` / Png2Point+Png2Line `[ ]`);
      IDEAS „Granularita area tříd" → 403 HOTOVO Sez. 92 značka. Historie zachována v DONE (Sez. 87-91).
- [x] **Rename legacy `forest_age`→`veg_area`** (TODO úkol Sez. 90, volba uživatele „udělat teď neutrální"):
      nález během mapování — rename je **širší** než TODO čekal (sdílené nosiče predict+archiv, ne jen predict
      cesta). Přejmenováno napříč 4 `.py`: proměnné `veg_area_*` (generator), výstupní soubor `mask_veg_area.png`,
      meta klíč `real_sections["veg_area"]`, `omap_export` kwarg `veg_area_features`+counter `n_veg_area`+counts
      klíč, konzumenti `separate.py`+`stats.py`. **Ponecháno legit** (archiv forest-age éra): konstanty
      `FOREST_AGE_*` (archiv-zeleň, superset = `PREDICT_AREA_*`), `--forest-age` flag/param, `forest.py` konektor,
      funkce `_generate_real_forest_age`/`_draw_forest_age_area`. Komentáře zobecněny (predict separace NEBO archiv věk).
- [x] **Ověření rename behavior-preserving:** py_compile 6/6 · grep čistý (žádný zbylý `forest_age_*` mimo
      legit) · **noise proc baseline 63=63** (generator+omap_export hlavní cesta) · **predict E2E `build_pair`
      (1088447 Přebor 2025, 75 s):** `mask_veg_area.png` vznikl, meta `veg_area` count 542 provenance predict
      symboly 403/406/408/410, starý `forest_age` klíč pryč; stale `mask_forest_age.png` sirotek (z běhu Sez. 92)
      smazán = potvrzení, že kód ho už negeneruje.

## Sezení 92 (2026-06-06) — Rozšíření pokrytí generátoru: 403 Rough open ze separace
- [x] **Měření pokrytí přes 5 vzorových map** (`temp/coverage_union.py`, scratch): union ISOM kódů
      z reálných `.omap` vs `omap_export.USED_CODES` → **46–52 %** schopnostmi (matched 38 % Sez. 91
      je přísnější). Top chybějící žádané všemi 5: 210 Stony (4641×), 416 veg hranice (linie), 403
      Rough open (2321), 419/418 body, 112 mikroformy, 409/407 hustníky, 507 footpath, 404.
- [x] **Rozhodnutí (uživatel):** vegetační rodina přes separaci, ale rozpad geometrií+metodou → teď
      jen **403** (404/407/409 pattern = separace slepá Sez. 90, 416 linie → Png2Line, 418-420 body →
      Png2Point). Architektura = vlastní area-color klasifikace v `separate.py` (SLAP, ne map_gt).
- [x] **Doložena separabilita 403** (verify-against-source z rastru, georef resources je „Local"):
      bimodalita žluté na všech 5 mapách (sytá B~54-74 vs bledá B~148-155 = ISOM Yellow 100/50 %),
      k=3 oddělil i cesty → 3 scan reference **403 (254,222,154)** / 401 sytá (255,200,58) / road
      (227,168,118).
- [x] **403 E2E napříč vrstvami:** `palette` swatch yellow_pale + `C_YELLOW_PALE` · `separate`
      AREA_CLASSES code-centric + `YELLOW_REFS`(4: +BÍLÁ) + `_is_pale_yellow`, **403 = (gt==4 open) ∩
      bledá žlutá** (staví na očištěném map_gt: median+ignore+layout) · `pairs` ořez rgb jako gt ·
      `generator` `PREDICT_AREA_*` registr (403 bledá žlutá, ne „forest_age" sémantika) ·
      `omap_raster` AREA_ZORDER+403 · `omap_export` USED_CODES/AREA_CODES+403 (template má area 403).
- [x] **Fix bug bílého papíru** (vizuál 1088447): `_fill_ignore` zaplnil okrajový IGNORE jako open,
      bílý papír je bližší bledé žluté než syté → falešné 403. 4. reference BÍLÁ → papír→bílá, ne 403.
- [x] **Verify:** `build_pair(1088447)` E2E OK (542 ploch), **403 v Y label rastru (label 4, 0,52 %,
      27313 px)**, konzistentní X↔Y. Proc/noise behavior-preserving (246=246, git-stash). py_compile 6/6.
      **Dopad: pokrytí +1 symbol na všech 5 mapách.** Carry: Q2 separace na `resources/*.png` → tvrdý DoD.

## Sezení 91 (2026-06-05) — Stabilizace Png2Area + ZMĚŘENO pokrytí generátoru (38 % ISOM) + DoD ≥90 %
- [x] **Trénink Png2Area `cap vah @10 + cosine LR`** (`model/png2area/train.py`, obě páky naráz = volba uživatele):
      `WEIGHT_CAP=10` (cap = tréninkový hyperparametr → v train.py, ne `_tiles.json`=SSoT; `--weight-cap`) +
      `CosineAnnealingLR` (jen plný trénink). **Výsledek: test mIoU 0,621→0,640, val 0,654, loss-spiky ZMIZELY**
      (hladký sestup). `208` test 0,00 = cap vzal váhu 120→10 → váha sama vzácnou třídu nezachrání (datový strop
      potvrzen → 1b expansion). Baseline zazálohován `unet_baseline_s90.pt`. Běh přes `.venv` (smp).
- [x] **Jonsdorf — měření vyvrátilo „jih ČR".** gt_labels profil: obsah jen horní ~55 % PNG, celý v DE (Oybin);
      hranice padá do prázdné spodní části → ČÚZK nedosáhne. README opraven (drift z rohů bbox quadu). Volba:
      negenerovat chudou separační .omap, plné demo čeká na `saxony.py`.
- [x] **ZMĚŘENO pokrytí ISOM generátorem = 38 %** (`generator/compare_isom.py`, ex-`temp/`): `generate_map`
      (všechny real vrstvy) vs `resources/Bedřichovka.omap` → **27/71 mapových kódů** (uživatel odhadl 40 %).
      44 chybí (416 veg hranice 447×, 403 Rough open 356×, 409/407 hustníky, 418/419/420 veg features 260×,
      112-118 mikroformy, 307/302/310 voda, 527/522/507 man-made). Dvojitá mezera: šířka + kvalita (porosty =
      AOPK proxy nesedí, žlutá 401 nadhodnocená vs bílý les). Vyvrátilo mé chybné „generator hotový".
- [x] **DoD generátoru (kritérium uživatele) propsán** do TODO + architecture + memory: fáze výroby `generator()`
      hotová až při **≥ 90 % ISOM z 5 vzorových map** v `resources/`. Censure ověřena: degradér jen na X, nikdy
      Y/GT. Memory `generator-coverage-is-the-ceiling`. Přerovnání priorit: rozšiřovat pokrytí > ladit model.

## Sezení 90 (2026-06-05) — Hlavní tah ODBLOKOVÁN: Branžež E2E verify + sanity batch + overfit gate prošel
- [x] **Branžež E2E `build_pair` (worst-case 93 Mpx)** — z 14 Branžeží vybrán `1005002` (`effectiveMppX` 0,5644,
      UTM33 rotovaný = žrout Sez. 84). **357 s ≈ 6 min** (Sez. 84 čekala 8 min bez downscale; páka A `target_mpp`
      Sez. 85 drží). Separace 1452 ploch, `scan.png` 2293×2293. **`_map_affine` na rotovaném quadu DRŽÍ** — vizuál
      rgb/scan/area_labels lícuje (jezero/open-land/les/olivová), histogram Y fyzicky sedí, labely 0–15.
- [x] **Sanity batch 10** (`build_pairs batch 10`): 1 SKIP + **9 nových OK, 0 fail, 7,7 min**, průměr **~51 s/mapa**
      (Branžež outlier). Edge-cases prošly (Slovanka UTM, rokle, Borecké/Rovné skály 25–36 s → render skal není
      žrout). → **noční batch odhad ~3 h** (207 × ~51 s), ne 12–15 h.
- [x] **`build_tiles()` korpus-vzorek** — 10 hotových (197 přeskočeno, resume): **162 train dlaždic** + 40 test,
      0 val (geo-split z 10 nerovnoměrný). Preview X↔Y lícuje.
- [x] **Overfit gate Png2Area (první trénink na REÁLNÝCH korpusových datech) — PROŠEL.** 2 mapy (Branžež+Selská
      rokle), 94 dlaždic, bez vah (čistá memorizace). **80 ep:** mIoU 0,518 (nedotrénováno, ne bug — mIoU pořád
      roste). **200 ep:** **mIoU 0,665, loss 0,10**, 11/13 přítomných tříd **0,73–0,99** (kompaktní průměr ~0,89).
      `308` mokřad **naskočil 0→0,73 náhle ~ep 190** (tenké/roztroušené třídy = pozdní latence, jen víc epoch),
      `410` fight pozdní S-křivka k 0,80.
- [x] **Px-diagnostika 0,00 tříd:** rozhoduje **TVAR, ne velikost** — `410` (0,52 %)→0,64 vs `521` budovy
      (0,46 %, podobný podíl)→0,00. Budovy = tenké rozházené obdélníky → U-Net downsampling 32× je rozpustí.
      Zbylé nuly tenké/mizivé (`501.1` 0,28 %, `402.1` 0,037 %) nebo 0 px (`402`/`301.1`/`501`/`208`).
      **Doložený limit** (ne blokátor): reálné číslo budov ukáže plný trénink (s vahami, 207 map).
- [x] **Noční batch spuštěn** (`build_pairs batch` 207 ČR, skip 10 hotových, volba uživatele „pustit teď") →
      kompletní set [scan.png, area_labels.png]. **Carry Sez. 91:** `build_tiles()` plný + **plný trénink** prvního
      Png2Area reconstructoru (val/test mIoU, median-freq váhy). Sledování: `resources/area_model/curve_full.png`
      + `history_full.csv` + konzole; checkpoint `unet_best.pt`. POZOR neplést s archivem `resources/model/`.
- [x] **Verify:** bez změny prod. kódu (jen běhy pipeline Sez. 82–88 + 2 scratch skripty `temp/`, smazány);
      proc baseline 65 nedotčen (negeneroval jsem v noise větvi). Deštníková fáze → jeden `docs(session)` commit.

### Sezení 90 — 2. část (plný trénink + pattern + Jonsdorf)
- [x] **Pattern/granularita 401/403** (koncepční dotaz uživatele): tři místa „barva→třída" (map_gt nearest-color
      pattern-blind / Png2Area CNN pattern-aware / Y per-objekt jistý). Měření 401 (Yellow100% `255,186,54`) vs 403
      (Yellow50% `255,221,154`, separabilní 106): surové „94 % oba" nafouknuté profil-variacemi, ale **vizuál `690592`
      doložil 403 jako běžné ČR rozlišení** → sloučení 403→401 = ztráta. Opraven zavádějící komentář `separate.py`.
      Rozhodnuto: trénovat hrubě, granularita = doložený směr (IDEAS).
- [x] **Noční batch + resume → 196/207 párů** (95 %). 83 fail = ČÚZK rate-limit (NE bug), resume zotaven na 11.
- [x] **Demo příprava saské alternativy → `maps/Jonsdorf/`**: Livelox „Hölle"/Oybin (1138425, SAXBO, překračuje
      hranici DE/ČR). Reference/cíl, ne saská generace (= `saxony.py`, neexistuje). Scope vymezen.
- [x] **PRVNÍ funkční Png2Area reconstructor — plný trénink.** `build_tiles` train 137/val 30/test 29 (geo-split
      bez leaku). 40 ep, BF16, ~65 min → **test mIoU 0,621 ≈ val 0,629** (vs baseline 0,25). Per-class: 401 0,93,
      412.1 0,91, 402 0,81, 520 0,78, 308 0,72, 521 budovy 0,68, … 208 0,00. **Budovy 521 ZACHRÁNĚNY** (overfit
      0,00 → 0,68, median-freq váhy + data). Vizuál `1024666` (test, neviděná) lícuje. `unet_best.pt` (ep 40).
- [x] **Nálezy:** loss-spiky (obří váhy 208=120 → cap/LR decay příště); 208/501/301.1 datový strop →
      class-balanced expansion (model=detektor, active learning, IDEAS); legacy forest_age názvosloví + layout
      watermark + degradér misregistrace 417 → TODO (neřešeno teď). Edukace train/val/test + curve_full legenda.

## Sezení 89 (2026-06-04) — %AUDIT:CODE (úklid driftu po přesunu Sez. 88)
- [x] **%AUDIT:CODE** (cadence-zralý, +8 = práh dosažen; scope = nový kód Sez. 82–88, ~2051 LOC, 10 souborů
      čteno sám). **0 kritických / 1 doporučený / 4 kosmetické** — dominanta = drift cest/komentářů po přesunu
      `git mv` Sez. 88 (vzorec konzistentní se Sez. 60/81). Izomorfismus `png2area/` ↔ `runnability/` v jádru drží.
- [x] **D1 — drift cest `runnability/dataset.py`** (přesun Sez. 88 opravil tile/train, dataset přehlédl): 4× stará
      `model/tile.py`/`model/train.py` → `model/runnability/…` (ř. 71 = zavádějící chybová hláška, ostatní docstring).
- [x] **K1 — mrtvé importy** `json` + `numpy` v `runnability/train.py` smazány (png2area protějšek je neměl).
- [x] **K2 — mrtvý `LABEL_VIS` import** v `png2area/tile.py` odebrán (jen v docstringu; `make_preview` volá jen
      `colorize`) + komentář zpřesněn.
- [x] **K3 — zastaralé cesty v komentářích** `degrade.py`/`omap_raster.py` → `model/png2area/…`.
- [x] **K4 NEMĚNĚNO** (volba uživatele) — izomorfismus tile.py: archiv má `_dist` nested + chybí guard dělení nulou
      (živý `png2area` čistší); neměnit archiv bezdůvodně, sjednotit až při reanimaci skeletu (Png2Line).
- [x] **Verify:** py_compile 5/5 + import řetězec drží + grep reziduí čistý. **proc 65 triviálně drží** (generator
      změny čistě komentářové, mimo proc cestu). Behavior-preserving. Cadence reset %AUDIT:CODE → Sez. 89.
- [x] **Handoff ntbhej → mrkla** (požadavek uživatele): hlavní tah 4. sezení mrkla-blokovaný → commit + push, mrkla
      ff-syncne a pokračuje (carry = Příště Sez. 90 body 1–2). `pip install -r requirements.txt` na mrkla ověřit.

## Sezení 88 (2026-06-04) — Png2Area loader/tile/train: dlaždicová pipeline reconstructoru (+ archiv → model/runnability/)
- [x] **Přesun archivu (runnability směr) → `model/runnability/`** (`git mv` tile/dataset/train.py). Volba uživatele
      „podadresáře oba" (symetrie: oba modely mají vlastní `{tile,dataset,train}.py`). Oprava cest: `_REPO_ROOT`
      `parents[1]`→`parents[2]`, `train.py` sys.path `model`→`model/runnability`, docstring cesty. Import ověřen
      (`_REPO_ROOT` = kořen repa, split/map_gt OK) → **behavior-preserving přesun**.
- [x] **`model/png2area/tile.py` (nový) — pre-tiling párů [scan.png, area_labels.png] na 512×512 dlaždice.**
      `build_tiles()` (korpus přes `split.dirs_for` → `<cid>/gen/`) + `build_tiles_dev()` (dev mapy z `maps/`, ntbhej
      smoke bez korpusu) + `tile_one`/`_positions`/`_crop`/`_median_freq_weights`/`make_preview`. TILE 512/stride 256,
      SSoT `N_AREA`/`LABEL_NAME`/`colorize` import z `omap_raster` (DRY, 16 tříd). Výstup `resources/area_tiles/`
      (gitignored) + `_tiles.json` (median-freq váhy) + `_preview.png`. **BEZ rejection dlaždic** (volba Sez. 88):
      scan.png je plný obdélníkový render (žádné IGNORE), pozadí (label 0) = legitimní třída „tady žádná plocha"
      → archivní `MIN_VALID` by ukrojil lesní kontext; nevyváženost řeší median-freq váhy.
- [x] **`model/png2area/dataset.py` (nový) — `AreaTileDataset` loader.** D4 aug + jas/kontrast na X, ImageNet
      norma (ResNet34 pretrained), **bez IGNORE** (y 0..15, Y z naší `.omap` je celé validní). `class_weights()`
      z `_tiles.json`. Izomorf s archivem.
- [x] **`model/png2area/train.py` (nový) — U-Net/ResNet34 trénink 16 tříd.** `in_channels=3`→`classes=N_AREA`, BF16,
      overfit/full režim, per-class IoU (confusion **bez** valid-mask), `CrossEntropyLoss(weight=)` **bez ignore_index**,
      křivka učení → `resources/area_model/` (gitignored).
- [x] **Verify (ntbhej):** py_compile 6/6. **Smoke tile Soví vrch: 70 dlaždic**, class% pozadí 66,1/401 25,8/520 4,7
      (lesní profil), median-freq potlačí pozadí (0,009)/zvedne vzácné (501 254). Formát dlaždic numpy: 70/70 shape OK,
      labely **0–15**. Preview lícuje X↔Y. Archiv import (`runnability/tile`) OK. **torch jen mrkla** → dataset/train
      torch self-check + korpusový `build_tiles()` + trénink = carry na mrkla. proc nedotčen (`model/` mimo proc cestu).

## Sezení 87 (2026-06-04) — Png2Area Y-pipeline: rasterizace plošných ISOM symbolů z .omap → label rastr
- [x] **`generator/omap_raster.py` (nový) — rasterizér plošných (Area) ISOM symbolů z `.omap` → label rastr (Y
      pro reconstructor Png2Area).** `rasterize(omap, meta) → label (H,W) uint8`; `parse_area_objects` (object
      symbol = pořadový index do `<symbols>`, ověřeno id==index) + `_split_rings` (ring-split na hole-flagu bit 16)
      + `_paper_to_px` (paper µm→px `(p/pw+0.5)·W`, `pw=world_m·1e6/scale`, triviální z meta — měřeno) + `colorize`
      + `rasterize_map_dir`. **Y per-ISOM-kód** (volba uživatele): `AREA_ZORDER` 15 kódů → `CODE_TO_LABEL` (label
      0=pozadí, 1..15), statický (konzistence napříč korpusem), seskupení tříd = modelové rozhodnutí NAD (DRY).
      Z-order zdola nahoru (501.1/520 base … 521 budovy), díry vyříznuté JEN v rámci objektu (per-objekt bbox maska).
- [x] **Y = rasterizace `.omap`, NE render masky `mask_*.png`** (reframe Sez. 79/80): pár [scan, .omap] →
      Y z téže `.omap` = self-konzistentní (nezávisí na render artefaktech). Measure-first area inventář (Soví
      vrch.omap): 10 distinct area kódů, 3582 objektů.
- [x] **Integrace `pairs.py`** (izomorfní s degrade Sez. 86): `build_pair`/`build_pairs` +param `labels=True` →
      po render+degrade rasterizuje `.omap` → `area_labels.png` (= Y páru). Skip-check posunut na `area_labels.png`
      (poslední krok). Pár = **[scan.png (X), area_labels.png (Y)]**.
- [x] **Verify (oko=source):** vizuál overlay vs `rgb.png` na **Soví vrch** (lesní, pokrytí 34 %, pixel-přesné
      zarovnání + z-order) i **Lidové sady** (městský, 59 %, 501.1 base 12 % = tvrdý test **děr** — budovy/zeleň/voda
      správně vyříznuté z base). **proc baseline 65 drží** (git diff: jen `pairs.py` + nový `omap_raster.py`;
      `generator.py`/`omap_export.py` nedotčeny → proc cesta nezměněná). py_compile + import OK (`N_AREA=16`).
      E2E `build_pair` s `labels=True` = carry na mrkla (Livelox korpus).
- [x] **(uživatelské úkoly, 2. část) Livelox mapy ≤16 km od Mařenic.** 101 eventů (2018–2026, CZ+DE), Fáze A
      (1 mapa/event, 39) + Fáze B (záchrana přes ostatní třídy, +18) → **57 map / 54 unikátních / 222,9 MB** do
      `resources/livelox/` (gitignored). 44 bez blobu (historické/MTBO = jen GPS). Statistika `_marenice_stats.{md,csv}`
      (classId/název/obec/km/datum/měřítko/EPSG/px/MB).
- [x] **(uživatelský dotaz) Saský geoportál GeoSN** → KB `data-sources.md` (DE ekvivalent ČÚZK: DGM1/DOP/ATKIS/ALKIS,
      DL-DE-BY-2.0). **DGM1 probe (measure-first):** data jsou (1m, hillshade Oybin), ale WCS 403 / WMS jen vizualizace
      / ATOM updates → raw cesta = batch dlaždice (dráž než ČÚZK). Plný DE pár navíc potřebuje ATKIS. Zaznamenáno
      jako směr `connectors/saxony.py`, ne stavěno (foundations: 8/57 map, hlavní tah = reconstructor ČR).

## Sezení 86 (2026-06-04) — %CALIBRATE (4 opravy) + fáze II degradér (sken) + integrace do pairs
- [x] **%CALIBRATE (vynucený, +17 od Sez. 69; 0 kritických).** 4 opravy (multiselect uživatele): **A-1**
      `settings.local.json` 35→18 (reincident vzorce C1 počtvrté — scratch + redundance s globálem + python
      varianty); **A-2** `CLAUDE.md` key-files +`model/` (Sez. 77) +`generator/separate.py`+`pairs.py` (drift
      mirror C4 Sez. 69); **C-1** PROMPTS `%BEGIN` bod 4 stroj×dostupnost fokusu (korpus/CUDA mrkla, ČÚZK/docs
      všude); **B-1** DIARY split → `DIARY-archive.md` (Sez. 1-51) + `DIARY.md` (Sez. 52-86, < read-cap). Sub-prah
      CLAUDE.md +7,2 % < 50 %. Nezvolené pojmenované: C-2 settings bobtnání systémové, B-2 cadence prahy drží.
- [x] **omap2png = de-facto hotové** (verify `pairs.py:7`: `rgb.png` z `generate_map` vedle `.omap`, Sez. 82
      volba C). C++ headless OOM až s důkazem doménového gapu → bod 2 redukován na samotný degradér.
- [x] **Fáze II degradér `generator/degrade.py` (nový).** `degrade(rgb, seed) → sken` + `degrade_file`. **4
      fotometrické sken-vrstvy** (plný MVP, volba uživatele) v pořadí tisk→optika→médium→snímání→komprese:
      CMYK misregistrace (±1,1 px, scipy `ndi_shift`) · blur (σ 0,4-0,9) · papír (jas 0,93-1,0) + zažloutnutí
      (teplý tint) · senzorový šum (σ 2-5) · JPEG (q 72-88). **Čistě fotometrické → Y (.omap) se nemění → pár
      konzistentní**; geometrie (rotace) je v loaderu D4 (DRY, Sez. 78). Deterministické přes seed.
- [x] **Integrace do `pairs.py`.** `build_pair`/`build_pairs` +param `degrade=True` → po renderu `scan.png`
      (= X v páru), seed = `int(cid)` (per-mapa). Čistý `rgb.png` zůstává. Resume skip-check posunut na `scan.png`.
- [x] **Verify:** proc baseline 65 drží (degrade/pairs mimo proc cestu); py_compile + import řetězec OK; vizuál
      4 vrstvy potvrzeny na Soví vrch 2× zoomu. E2E `build_pair` s degradací = carry na mrkla (korpus).

## Sezení 85 (2026-06-04) — Measure-first dlaždice: oba žrouti vyřešeny + `target_mpp` downscale separace
- [x] **Verify dluh Sez. 84 — proc baseline 65 DRŽÍ** (`--terrain noise --paths proc --seed 1` → `.omap objektů 65`).
      Změna `rock_relief._group_holes` (bbox prefilter) behavior-preserving, jak Sez. 84 předpokládal. Regrese 0.
- [x] **%THINK redesign párů — oponentura: tři páky místo rozbíjení monolitu `generate_map`.** (1) downscale
      separace na ~1,33 mpp, (2) `max_km` strop (hotovo Sez. 84), (3) finální nářez = **reuse `model/tile.py`**
      (existuje, @1,33/512/stride256). Rozbití monolitu (fetch | render po dlaždicích) zamítnuto — velký refaktor
      proti fázi B (`_apply_extent` globály), TODO odkládá na fázi A. **Tři významy „dlaždice"** rozlišeny
      (`TILE_M` georef / `tile.py` 512 CNN / „generovat dlaždice"). Insight: X = render NAŠÍ `.omap` → downscale
      Livelox gt před separací je bezpečný (neovlivní X/Y, sjednotí `MIN_AREA_PX` napříč korpusem).
- [x] **Krok 1 měření — žrout #1 (separace O(n²)): páka A potvrzena.** Stand-in Soví vrch (137 Mpx, v `resources/`
      ne korpus). Downscale gt 0,56→1,33 mpp (NEAREST, ne bilineár — labely): **31,6× zrychlení @ 5,6× méně px**
      (super-lineární žrout), polygonů 88→39 (drobky), **overlay before/after téměř identický** (věrnost OK).
      Vedlejší: `map_gt.segment_gt` nezvládne 137 Mpx (20 GiB; korpusové mapy malé → nepadá).
- [x] **Krok 1b měření — žrout #2 (render skal): NEní žrout.** HS cache-warm, `rocks=real − off` na 2/3/4 km:
      skály 2,88/5,10/5,89 s → s/km² KLESÁ → **SUB-lineární → Sez. 84 hypotéza VYVRÁCENA** (Branžež visela
      v separaci, ne renderu). `max_km` ho udrží.
- [x] **Implementace `target_mpp` downscale.** `separate.py`: `TARGET_MPP=1,33` + `separate_areas(src_mpp, target_mpp)`
      — downscale NEAREST před vektorizací, **polygony ×f ZPĚT na původní grid** (výstup v image-px vstupu →
      volající se nemění), bez `src_mpp` no-op. `pairs.py`: `_separate_to_sjtsk(src_mpp)` + `build_pair` předá
      `meta["effectiveMppX"]` (crop=plocha, downscale=rozlišení, komplementární). **Ověřeno na Soví vrch:**
      behavior-preserving (88 polygonů identicky) + downscale aktivní (16,5×) + souřadnice zpět v gt gridu
      (1998,1442 < 2371×1681). `py_compile` OK, proc 65 drží.
- [x] **`.venv` na ntbhej dorovnán** proti `requirements.txt` (chyběly scipy + matplotlib; paměť `two-machines-git-sync`).
- [ ] **Zbývá na mrkla:** Branžež `build_pair` verify (absolutní práh + `_map_affine` rotovaný quad) → odblokovat noční batch.

## Sezení 84 (2026-06-03) — Škálování párů (WIP) — batch + výkonové žrouti + směr dlaždice
- [x] **`pairs.py build_pairs(cids, skip_existing, ortho, max_km)`** — batch wrapper (mirror `livelox.build_pairs`):
      resume přes `gen/rgb.png`, tolerantní (chyba 1 mapy nepoloží dávku), souhrn ok/skip/fail; CLI `pairs.py batch [N]`.
      **Zdroj `_cr_keep_cids()` = 207 ČR ze `_split.json`** (ne 216 keep — split vyřadí 9 cizích keep map + outlier
      `1109655` najednou; real ČÚZK funguje jen pro ČR).
- [x] **`ortho=False` default** (volba uživatele) — X-zdroj páru = sken OB mapy (bílé pozadí + ISOM), ne ortofoto;
      reálné OB mapy fotopodklad nemají → ortofoto by X odklonilo od domény + ušetří ~50 % fetchů.
- [x] **`max_km=5.0` crop strop + ořez gt** (`_separate_to_sjtsk(crop_bbox)`, inverz `_map_affine` → pixel-okno) —
      render škáluje nadlineárně, obří mapy (max 106 km²) by táhly běh na víkend; pro trénink rozhoduje rozmanitost.
- [x] **`rock_relief._group_holes` bbox prefilter** — vektorový odmítací test před čistě-Python `_point_in_ring`.
      Exaktní (bbox = nutná podmínka), identita ověřena (separace 81/189 polygonů beze změny), ~2× rychlejší na malých.
- [x] **Měření (measure-first):** distribuce 207 map suma 2070 km² (medián 7, max 106); 1 malá mapa 34 s (skály 14 s
      = nejdražší fáze). **Žrout #1 separace O(n²)** (`_group_holes` point-in-ring, 4× prstenců = 11× čas). **KLÍČOVÝ
      NÁLEZ:** Branžež mpp=0.56 → **93 Mpx**; ořez na crop-bbox skoro nezabral (rotace quadu + jemné rozlišení) →
      miliony zelených px → separace neúnosná. **Žrout #2 render skal** (Český ráj hypotéza, NEpotvrzeno).
- [ ] **NEdokončeno:** hromadný běh blokován výkonem. proc baseline 65 NEOVĚŘEN (rock_relief změna se dotýká skal).
      Směr příště: **generovat rovnou dlaždice 512×512** (+ downscale na ~1.33 mpp, fetch po mapě/render po dlaždici).

## Sezení 83 (2026-06-03) — Integrace separace do generate_map() (per-classId pár real+predict) + zobecnění + oprava přetisku
- [x] **Zobecnění separace `separate_veg.py` → `separate.py`** (rename modulu i funkce: `separate_veg` →
      `separate_areas`, `LEVELS` → registr `AREA_CLASSES`). Mechanismus (`vectorize_level`) byl už agnostický;
      registr připravený na paseky/podrost (až je `map_gt` klasifikuje). **Scope (volba uživatele):** separovat
      JEN co generátor neumí z tvrdých dat (vegetace, do budoucna paseky/podrost) — voda/skály/budovy/cesty zůstávají
      „real" (ZABAGED/DMR), separace navíc = dvojí zdroj + konflikt + porušení DRY. Behavior-preserving (392 polygonů).
- [x] **Gate A (measure-first) — `build_bbox` vs Livelox `_georef_grid` obal.** Riziko integrace: real vrstvy se
      georefují přes `build_bbox(lat,lon,…)` z centroidu obalu, separace přes `_map_affine(quad)` → musí sednout do
      jednoho S-JTSK. Měřeno na 268 map: **medián Δroh 1,15 m (~1 px), p90 3,09 m**; posun jen v ŠÍŘCE (zaokrouhlení
      `gw` na celé buňky `M_PER_CELL` pokřiví poměr), výška přesná. Pro GT-feeder OK (separace ~90 %, model dotáhne).
      Outlier `1109655` (1,5 mil. m) = georef bug té mapy → vyřadit z korpusu, netáhne pipeline.
- [x] **Krok 2 — integrace do `generate_map()` + orchestrátor `generator/pairs.py` (per-classId továrna párů).**
      `generate_map` dostal **jeden nový keyword `predict_areas_sjtsk`** (helper `_draw_predict_areas`): když přijde,
      MÁ PŘEDNOST před archivovaným forest-age — separace v S-JTSK → `_poly_to_grid_px` → kreslí se stejnou cestou
      (406/408/410) i `.omap` kanál jako forest-age, jen geometrie je z páru. **`pairs.py build_pair(cid)`:** `meta` →
      `_georef_grid` → centroid→lat/lon + rozměry obalu→w_km/h_km, separace `gt_labels`→S-JTSK přes `_map_affine`,
      pak `generate_map(forest_age="off", predict_areas_sjtsk=…)`. Společný grid = Livelox `_georef_grid`, zarovnání
      přes jeden S-JTSK (.omap je vektorový/georeferencovaný — pixel-grid nepotřebný). **A3 provenience:** `forest_age`
      meta sekce nese `provenance:"predict"` + `source:"separace_realne_mapy"` (vs forest-age `proxy:true`).
- [x] **Oprava: fialový přetisk tratě vykousával zeleň → `_fill_ignore` (nález uživatele při OOM verify).** `map_gt`
      dal kroužkům kontrol (704) a spojnicím (705) label 255 IGNORE (Sez. 72, smysluplné pro archivovaný ortofoto model)
      → separace je viděla jako díry v zelených plochách. Fix: před vektorizací IGNORE pixel → **nejbližší ne-ignore
      label** (`distance_transform_edt(return_indices)`) — kroužek uvnitř zeleně → zelená. Specifické pro separaci
      (ne `map_gt`, kde ignore má vlastní smysl). Verify: výřez před/po (díry zacelené), 392 → 379 ploch.
- [x] **OOM verify Test OK na Přeboru (1088447).** Izolovaná `separate_areas.omap` (379 ploch, podklad map.png) +
      integrovaná `gen.omap` (**11 774 objektů**: real ČÚZK 5066 surfaces/3065 budov/1379 cest/285 voda/202 vrstevnic/… +
      379 ploch separované vegetace, ortofoto podklad). Uživatel: „artefakty zmizely, zelená sedí, mapa lícuje". Nález
      (sekundární): ČÚZK open land (žlutá 401) dominuje vůči realitě — pro PÁR nevadí (X = render NAŠÍ `.omap`, X↔Y konzistentní).

## Sezení 82 (2026-06-03) — A1 measure-first (forest-age → archiv) + PoC fáze I (separace zelené → .omap)
- [x] **A1 measure-first — zdroj predikční vegetace = separace z mapy, NE forest-age (ARCHIVOVÁN).** Dvě měření:
      **#1 šířka** — sken celého ČR korpusu (`temp/a1_corpus_scan.py` → `a1_coverage.json`): forest-age má zeleň jen
      na **33 % map (69/207)** → NEuniverzální (separace = univerzální, každá keep mapa nese barvu). Typ-B mapy
      (epsg 4326) dopočítány z WGS84 extentu (bug „div by zero" = projektovaný quad ve stupních). **#2 shoda** —
      na Přeboru 2025 (1092 skupin, jediná bohatá) forest-age rasterizován do gridu `gt_grid` a porovnán
      (`temp/a1_agree_prebor.py`): **IoU s kresbou kartografa 0,12**, forest-age **přestřeluje zelenou 3,3×**
      (73,5 % vs 22 %), kde proxy=406/408 mapař nakreslil běhatelný bílý les 76-79 %. Vizuál `a1_prebor_compare.png`
      potvrdil (ne artefakt zarovnání). **Závěr:** forest-age archivován (jako Orto2Colors — kód funkční, doložená
      slepá ulička); hlavička `forest.py` + architecture/GLOSSARY/TODO značí archiv.
- [x] **PoC fáze I krok 1 — separace zelené → vektorizace → `.omap` (`generator/separate_veg.py`, povýšeno z PoC).**
      Na Přeboru: `map_gt` separace (gt_labels 1/2/3 = 406/408/410) → per-úroveň maska → contourpy vektorizace
      (REUSE `rock_relief` `_contour_rings`/`_group_holes`/`_rdp`/`_chaikin`) → polygony image-px → `omap_export.
      write_omap` (image-px=grid, kanál `forest_age_features`, podklad map.png). **392 polygonů**, `.omap` validní XML
      (symboly 81/84/88 = 406/408/410). **Overlay verify** (`separate_veg_overlay.png`): vektorová zeleň věrná kresbě
      kartografa **~90 %**. Dělba real/predict: zelená = predict; real ČÚZK = integrace dalším krokem.
- [x] **Zásada: algoritmická separace = GT-FEEDER, ne finální kvalita.** ~90 % stačí — kvalitu dotáhne `Png2Area`
      model na množství párů, ne leštění prahu. Pod konstrukcí páru (X = degradovaný export z naší `.omap`) nemusí být
      separace věrná ani původní mapě. → IDEAS „separace = GT-feeder" (neutrácet sezení dolaďováním prahu).
- [x] **omap2png %THINK — rozhodnuto „náš rastr teď, C++ až s důkazem".** OOM nemá CLI/headless export (ověřeno
      manuál+issue #776); engine v C++ existuje (`RenderConfig`+`MapRenderables::draw`+Qt offscreen). Volba: `generate_map`
      už `rgb.png` produkuje (aproximace) → měřit doménový gap; C++ headless OOM (věrné) až když gap dokáže potřebu. IDEAS „omap2png".
- [x] **Názvosloví `Png2Polygon`/`Png2Linie` → `Png2Area`/`Png2Line`** (OOM terminologie Point/Line/Area, doloženo
      z `template_classic.omap` `type=1/2/4`). Propsáno GLOSSARY/IDEAS/TODO. Žádná změna proc cesty (proc 65 drží triviálně).

## Sezení 81 (2026-06-03) — Úklidové: %AUDIT:CODE + %AUDIT:DOCS + IDEAS/TODO pruning
- [x] **%AUDIT:CODE (0 kritických, 0 mrtvého kódu) — audit nového kódu od Sez. 71.** Cíl = `model/` celé (tile/
      dataset/train, 619 LOC, nikdy neauditováno) + `connectors/split.py` (nový) + livelox georef páry + map_gt
      přetisk/layout + curate. `generator.py` (3824 ř.) se od Sez. 71 NEZMĚNIL → nečten (audit Sez. 60+71 platí).
      4 opravy: **D1** archivní hlavičky do `model/*.py` (Sez. 79 reframe — kód neznal, že je archivovaný =
      conceptual integrity/SLAP); **K1** `_MAP_SCELE_DIL`→`_MAP_MERGE_DIL` (matoucí český identifikátor); **K2**
      `N_CLASS=5` duplikováno tile+train → SSoT v `map_gt` (import); **K3** `train.py --batch` default 8→16
      (zdokumentovaný baseline Sez. 78). Ověřeno py_compile + import N_CLASS z map_gt. Behavior-preserving.
- [x] **%AUDIT:DOCS — 7 oprav (po kritickém profiltrování proti zdroji).** Fan-out 3 Explore agenti, 2 přepaly
      zamítnuty (hardware mIoU 0,666 + tools-models „pilot" = korektní Pic2Omap precedent). **Tvrdé:** T1 doplněn
      chybějící **DONE Sez. 79** (propagační díra, %END checklist Sez. 34), T2 architecture „zbývá krok 4"→hotovo+
      archiv, T3 README UC5 status (byl u Sez. 74)→kroky 1-4+baseline+reframe (vyřešena vnitřní nekonzistence),
      T4 katalog duplikát `Areál_účelové_zástavby` (počítal se 2×). **Měkké (reframe pointery, plný přepis = A1):**
      M1 spec §0b, M2 data-sources+RESEARCH, M3 generator/README. Vzorně aktuální: GLOSSARY/connectors/hardware/STATISTICS.
- [x] **IDEAS/TODO pruning.** TODO: hotové `[x]` bloky (Livelox korpus+kurace, UC5 kroky 0-5, GT crop A/B) zhuštěny
      na souhrnné pointery (DONE drží detail) → TODO odlehčen ~35→~10 ř.; krok 5 archiv zhuštěn; živé `[ ]` follow-up
      nedotčeny. IDEAS: archivní hlavička do bloku „UC5 runnability model architektura (Sez. 74)" (Sez. 79 ho archivoval).
- [x] **Cadence reset Sez. 81** pro %AUDIT:CODE + %AUDIT:DOCS + pruning. %CALIBRATE +12 (nezralý). Žádný produkční
      feature, behavior-preserving (proc 65 drží). Censure 0.

## Sezení 80 (2026-06-03) — %THINK fáze I/II/III + tři pomocné modely + průzkum vektorů (žádný kód)
- [x] **Vyjasněn tok I/II/III** (oprava mého zmatku „degradér ve fázi I"): I. `generator()` = real část (ČÚZK) +
      prediktivní plochy ze **separace barev z HD Livelox PNG** (NEdegradovat — separace chce kvalitu); II. dataset
      = export PNG + **degradace** (overprint/odřeniny/bláto); III. `reconstructor()` = trénink. Livelox = zdroj
      ploch fáze I, NE vstup páru (X je až degradovaný export z naší `.omap`).
- [x] **Průzkum: pravé veřejné `.omap`/`.ocd` vektory NEEXISTUJÍ v potřebném množství** (8 web searchů + 3 fetche).
      `OpenOrienteering/mapper/examples` = jednotky open (GPL); WOC2024 = 3 mapy embargo/restricted; British O = jen
      nástroje (OS Crown Copyright); EU/Interreg/Erasmus = žádný hotový korpus. → `.omap` (Y) musí tvořit generátor
      (proto existuje, sparse-GT past). Korpus pro fázi A = Livelox 268 rastrů.
- [x] **A1 measure-first zaznamenáno:** vegetace z [[forest-age-proxy]] (data) vs mapař (Livelox separace) — změřit
      na lokalitě s obojím. **A3 provenience real/predict** do `.omap`/XML (nosná: definuje co reconstructor bere
      z dat vs ze skenu). **A2 tři modely** `Png2Polygon`/`Png2Point`/`Png2Linie` (dekompozice dle typu geometrie).
- [x] **Propagace (docs-only):** IDEAS (sekce „Tři fáze I/II/III + tři pomocné modely"), TODO (hlavní tah upřesněn
      + položka tří modelů), GLOSSARY (fáze I/II/III + tři Png2* pojmy). Censure: popletl jsem degradér (fáze I→II)
      i roli Livelox (X→zdroj ploch) — uživatel opravil.

## Sezení 79 (2026-06-03) — Konsolidace: reframe `generator()` / `reconstructor()`, ortofoto→runnability archivováno
- [x] **Směrový obrat uživatele.** Cíl Laboratoře „rozumí mapám" = **`reconstructor()`** (sken existující OB mapy
      → `.omap`, obaluje `reconstruct_map()`, dříve pracovně „mapper"), trénovaný na párech [render, `.omap`]
      z **`generator()`** (obaluje `generate_map()`; **real + predict** část — vegetace/paseky/hustníky procedurálně
      věrohodně, NE věrná predikce z dat).
- [x] **Model `ORTO → 4 barvy` (Sez. 67-78) ARCHIVOVÁN jako slepá ulička.** val mIoU strop ~0,25 (Sez. 78) =
      „rozumí ortofotu", ne mapám. Kód `model/*.py` NEMAZÁN (doložený nález „tudy ne"). Datová pipeline
      (páry, GT, split, dlaždice) zůstává znovupoužitelná.
- [x] **Klíčový insight: vegetace pro trénink NEMUSÍ být pravdivá** — reconstructor ji čte ze SKENU; `generator()`
      ji generuje procedurálně-věrohodně → **vegetace gate padá jako blokátor** (přestává blokovat UC5).
- [x] **Naming:** `reconstruct_map()` voleno přes `regenerate_map()` (kolize „re-run téže generace" vs „rastr→vektor
      rekonstrukce"). Propagace: GLOSSARY (2 dvojice pojmů `generator()`/`reconstructor()` + `generate_map()`/
      `reconstruct_map()`), TODO (reframe blok), architecture.md (UC5 reframe note „částečná propagace").
- [x] **A1 ODLOŽENO:** plná revize UC3 / UC4-III / UC5 / fázový plán + Pic2Omap absorpce (B→A). Žádný kód.

## Sezení 78 (2026-06-03) — UC5 krok 4 dokončen: loader + trénink + baseline (val mIoU 0,25)
- [x] **`model/dataset.py` — PyTorch loader nad dlaždicemi (Sez. 77).** `TileDataset(split, augment,
      limit_cids)` čte `resources/tiles/<split>/<cid>/*_x.png` (+ `_y`), vrací (x float32 `(3,512,512)`
      ImageNet-normalizovaný, y int64 `(512,512)` labely 0-4/255). **Augmentace za běhu** (volba Sez. 77):
      D4 (hflip + rot90×k — BEZ interpolace → labely přesné; obecná rotace by vyrobila smíšené px) +
      jas/kontrast jen na X. Jen train; val/test deterministické. `class_weights()` čte z `_tiles.json`
      (SSoT/DRY). Self-check: 5777/1224/1124 dlaždic OK.
- [x] **`model/train.py` — U-Net trénink + per-class IoU eval + křivka učení.** smp U-Net + ResNet34
      **ImageNet-pretrained** (precedent Pic2Omap), `CrossEntropyLoss(weight=median-freq, ignore_index=255)`,
      AdamW lr 1e-4, **BF16 autocast** (Blackwell), `cudnn.benchmark`. Metrika per-class IoU + mIoU přes
      **GPU confusion matici** (`bincount`, IGNORE vynechán; třída bez px → NaN → mimo mIoU). CLI `--overfit`
      (2 mapy, bez aug+vah = čistá memorizace) vs plný (eval val + test z best ckpt). Checkpoint best →
      `resources/model/unet_best.pt`. **Křivka učení** (žádost uživatele): po každé epoše CSV
      `history_<tag>.csv` + `curve_<tag>.png` (matplotlib Agg, 2 panely loss+mIoU / per-class IoU). +matplotlib
      do `requirements.txt`.
- [x] **Overfit gate PROŠEL (pipeline).** Loss 1,99 → 0,099, train mIoU 0,03 → 0,50, 4/5 tříd (průchodný
      0,98 / open 0,83 / 410 0,48 / 406 0,23). **408 walk = 0** vysvětleno měřením: jen ~0,3 % px v obou
      mapách + overfit bez vah → ne defekt. Gradienty/učení/eval/checkpoint/křivka ověřeny.
- [x] **Plný trénink (40 ep, batch 16, ~165 s/ep ≈ 1,8 h): baseline val mIoU 0,259 / test 0,223** (best ep 26).
      Per-class test: průchodný 0,48 / 406 0,11 / 408 0,16 / **410 fight 0,04** / open 0,32. 408 walk se
      s vahami NAUČILA (0,16) — overfitová nula byla artefakt chybějících vah.
- [x] **Nález: generalizační strop (`curve_full.png`).** Train loss klesá (1,38 → 0,69), **val mIoU PLOCHÁ
      ~0,25 od ep1** — ne hyperparametry, ale úlohový strop. Runnability = hustota podrostu pod korunami,
      z RGB ortofota shora omezeně poznatelná (doložení Sez. 59/66; Petrovič 2018 ~47 % i s LiDARem).
      **Volba uživatele:** přijmout baseline + %END, hlavní podezřelý RGB-only málo → příště bohatší vstup
      (MĚŘENÁ ablace DMR/forest-age kanálu, osa B IDEAS). Empirický baseline = od něj se poměřuje zlepšení.

## Sezení 77 (2026-06-02) — UC5 krok 4 (příprava): tréninkové dlaždice + median-freq váhy
- [x] **Nový adresář `model/` (UC5 model kód, sourozenec `connectors/`/`generator/`, sys.path skripty fáze B).**
      První obyvatel `model/tile.py`. Loader/trénink přijdou příště (krok 4 pokračování).
- [x] **`model/tile.py` — pre-tiling párů (X,Y) na 512×512 dlaždice.** Páry jsou různě velké (~800-4000 px),
      U-Net jede na fixní dlaždici. Sliding window **512 px, stride 256 (50% překryv)**, poslední dlaždice
      v řadě/sloupci zarovnaná k okraji (nic se neztratí). **Rejection:** dlaždice s <30 % validních (≠IGNORE)
      px se zahodí (rohy quadu, layout). Split (train/val/test) dědí z `split.dirs_for` — dlaždice mapy jdou
      CELÉ do jejího splitu (žádný leak). Výstup `resources/tiles/<split>/<cid>/<r>_<c>_{x,y}.png` (gitignored,
      per-cid podadresář). Volba pre-tiling vs random-crop (uživatel): deterministické + vizuálně kontrolovatelné
      + rychlé IO; augmentace (flip/rot) až v loaderu za běhu (hustší překryv = jen kopie patchů → zavrženo).
- [x] **Výsledek: ~8 125 dlaždic** (train 5 777 / val 1 224 / test 1 124). Class % **konzistentní napříč splity**
      (410 fight 1,33 / 1,83 / 2,33 — vždy nenulová) → potvrzuje reprezentativnost geo-splitu Sez. 76.
- [x] **Median-freq váhy z TRAIN dlaždic (po rejection)** `[0,16, 1,0, 1,65, 8,27, 0,89]` (pořadí 0..4;
      410 fight ~8× = sedí na odhad 8,4 Sez. 76). Uloženo v `resources/tiles/_tiles.json` jako
      `class_weights_list` pro přímé dosazení do `CrossEntropyLoss(weight=)`. + `_preview.png` (vizuál verify).
- [x] **Vizuál verify (uživatel):** triptych ortho|blend|label potvrdil pixel-na-pixel zarovnání X↔Y; dotaz
      „bílé čtverce přes les v `_y.png`" vyřešen — v syrovém grayscale labelu je **255 (IGNORE) = bílá**:
      rohy natočeného mapového quadu warpnutého do osového S-JTSK gridu = mimo o-mapu → ignore (správně,
      trénink přeskočí). Schodovitý okraj = pixelizace diagonální hranice quadu.

## Sezení 76 (2026-06-02) — UC5 krok 2 (filtr+distribuce) + krok 3 (geosplit) + 207 párů
- [x] **Krok 2 — měření datasetu (ČR/DE filtr).** ČÚZK ortofoto mimo ČR vrací jednolitou bílou 253
      (doloženo probe: CZ Branžež near-white 0,000 vs DE Olbersdorf 1,000) → kritérium filtru = podíl
      skoro-bílých px v malém ortofoto náhledu, práh **0,5**. **216 keep classic → 207 ČR / 9 cizí**
      (DE Žitavsko: OlberSee/Leipaer/Oybin/Buchberg; PL: Jakuszyce, PZL). 3 hraniční mapy vizuálně
      ověřeny (Čertovy mlýny 0,12 = roh quadu → ČR; Oybin 0,62 / Buchberg 0,77 = většina prázdná → cizí).
      Durable `resources/livelox/_cz_filter.json` (near_white per mapa).
- [x] **Krok 2 — rozložení tříd v GT (207 ČR map, 1,47 mld px).** % labeled: průchodný **69,2** /
      406 slow **11,4** / 408 walk **5,9** / **410 fight 1,35** / open **12,2**; ignore 43 % z all
      (nadhodnocené nativním layoutem, ve warpnutých párech klesne). **Váhy do loss (median-freq):**
      0,16 / 1,0 / 1,93 / **8,40** / 0,93. → tvrdá class imbalance, 410 nutno vážit.
- [x] **Krok 2 — validace 410 proti 5 mapařským `.omap`** (verify-against-source, vektor = pravda).
      Shoelace plocha symbolu 410 (oprava: kódy se suffixem `.0` — Bedřichovka „410.0"): 410 = **0,2-1,4 %**
      plochy (Bedř 0,88 / Blatná 1,38 / Slovanka 0,28 / Velbloud 0,21; Soví vrch 2,07 % = outlier, jen
      1/4 domapováno). GT 1,35 % je v reálném rozpětí → **color-GT 410 nepoddetekovává**, imbalance je
      skutečný terén. (Intuice uživatele „410 jednotky %" potvrzena.)
- [x] **Krok 3 — geografický split (`connectors/split.py`).** Náhodný per-mapa split leakuje (překryv
      map = stejný les v train+val). Řešení: souvislé komponenty grafu překryvu **S-JTSK bboxů** (union-find,
      **29 clusterů** velikosti 39…1) → greedy bin-packing na **70/15/15 = train 145 / val 31 / test 31**.
      Leak vyloučen konstrukcí (celý cluster do 1 splitu). Per-split class % reprezentativní, **410 všude
      nenulová** (1,3 / 1,6 / 1,9 %). Výstup `_split.json` (regenerovatelný, deterministický); API
      `split_of(cid)`/`dirs_for('train')` = kontrakt loaderu.
- [x] **Hromadná výroba párů (`build_pairs` + CLI `pairs` v livelox.py).** Resumovatelná (skip hotových),
      tolerantní (chyba 1 mapy nezastaví dávku), QC offset přes set. **207 párů, 0 fail** (185 vyrobeno,
      22 skip z GATE 1 testů). **GATE 1 offset přes set: medián 2,97 m** (max 50,92 = artefaktový ocas
      husté korelace, Sez. 75; medián robustní, ~2 px = zanedbatelné). Blendy vizuálně potvrzují zarovnání.

## Sezení 75 (2026-06-02) — GATE 1: zarovnané páry (X,Y) + měření georef offsetu (krok 1)
- [x] **`build_georef_pair(out_dir)` (livelox.py) — výroba zarovnaného páru (X,Y) pro UC5 trénink.**
      Z adresáře mapy (map.png + gt_labels.png + meta.json) vyrobí: **`ortho.png` = X** (ČÚZK ortofoto
      v S-JTSK gridu), **`gt_grid.png` = Y** (GT labely warpnuté do TÉHOŽ gridu, nearest, fill IGNORE 255
      mimo mapový quad), **`gt_grid_vis.png`** (barevný verify Y) + **`blend.png`** (ortofoto+mapa).
      X i Y procházejí **identickou afinní transformací** do stejného gridu → pixel-na-pixel zarovnané
      zadarmo. Vstup modelu (X) tím poprvé **fyzicky existuje** (dřív jen quad v meta.json — nález Sez. 74).
- [x] **`measure_georef_offset(ortho, warped, mpp)` — phase correlation hran (vlastní GATE 1).**
      Společný signál ortofota a mapy = HRANY (cesty/kraj lesa/voda); FFT cross-power → globální translace,
      o kterou mapu posunout, aby sedla na ČÚZK pravdu. **Peak hledán JEN v okně ±40 m** — nález Sez. 75:
      bez omezení dala mapa s pravidelnými žlutými šrafy (1047807) falešných **549 m**, ač vizuálně sedí
      dokonale (periodicita → falešný korelační peak daleko od nuly). Bez nové závislosti (ruční numpy FFT,
      ne scikit-image). Volba uživatele Q2.
- [x] **Měření GATE 1 na 25 CZ S-JTSK mapách → PROŠEL.** `python connectors/livelox.py gate1 25`:
      **medián posunu 1,33 m = 1 px**, ~84 % map ≤ 5,3 m. Georef Liveloxu je zdravý → páry jsou pixelově
      zarovnané dost pro trénink (plošná runnability GT toleruje ~1 px). **Klíčový nález:** per-mapa offset
      `>~5 m` je **nedůvěryhodný** — vizuál (blend) ho vyvrací (1106623 sedí dokonale, přesto „17 m";
      outliery jsou artefakt husté/rušivé korelace, ne reálný posun). → měření slouží jen jako **agregátní
      QC** (korpus OK), **ne** jako per-mapa korektor/filtr. Pro trénink: celý CZ korpus bez korekce georefu.
- [x] **DRY refaktor livelox.py + zobecnění (volba uživatele Q1=warp GT, Q3=afinní/measure-first).**
      Geometrie gridu vytažena do `_georef_grid(meta)` + afinní matice do `_map_affine(quad,W,H)` — sdílí
      `build_georef_blend` i `build_georef_pair`. `_warp_to_grid` zobecněn na N kanálů + `fill` parametr
      (RGB i jednokanálové labely; nearest `np.round` bezpečný pro třídy). Drobnost: cp1250 konzole UTF-8
      reconfigure (Unicode šipky v printech, jako Sez. 74).

## Sezení 74 (2026-06-02) — HW dokumentace + %THINK UC5 model + smoke test (krok 0)
- [x] **HW dokumentace (`docs/kb/hardware.md`, nový KB list):** UC5 trénink dělá z HW reálnou závislost.
      `mrkla` = **RTX 5070 (12 GB GDDR7, Blackwell GB205, 192 Tensor Cores)** + Ryzen 7 7700 + 32 GB DDR5 =
      trénovací stroj; `ntbhej` = HP EliteBook 855 G8 (parametry z webu: Ryzen 5000U + integ. Radeon Vega, BEZ
      CUDA) = jen editace/git/CPU inference. **Trénink jen na `mrkla`.** Zvýrazněna Blackwell/cu128 past. Odkaz
      v README layout; paměť `two-machines-git-sync` doplněna (stroje pro UC5 nerovnocenné).
- [x] **%THINK UC5 runnability model (IDEAS „UC5 runnability model" + TODO kroky 0-4):** rozhodnutí uživatele
      Q1-Q3 = vstup **jen ortofoto RGB**, predikce **všech 5 tříd** (eval primárně zelená per-class IoU),
      **smoke test první**. Osy A-H (úloha/vstup/zarovnání/ČR-DE/split/dlaždice/architektura/imbalance). **Hlavní
      teze (oponentura „skoč na model"):** riziko není architektura (U-Net/ResNet34 = sourozenec Pic2Omapu,
      rozhodnuto), ale **kvalita párů (X,Y)** — nález z dat: GT i georef máme, ale **vstup ortofoto NENÍ vyrobený**
      (jen `meta.json` quad; `build_georef_blend` dělá jen verify blend). Foundations: gaty (zarovnání + měření
      offsetu) PŘED model.
- [x] **Krok 0 — smoke test PyTorch+CUDA na Blackwell (`temp/smoke_test_gpu.py`):** dvojitá past zažehnána —
      `torch 2.11.0+cu128` má **cp314 wheel** (Python 3.14) i **cu128** (Blackwell), obojí ověřeno dry-run před
      stažením. Instalace torch+torchvision (cu128 index, NE PyPI = CPU build) + `smp 0.5.0`. **Smoke test ověřil
      REÁLNÝ výpočet** (ne jen `is_available` — past „no kernel image" se projeví až při operaci): sm_120
      v `arch_list`, matmul fp32+bf16 na GPU, **U-Net forward (1,3,512,512)→(1,5,512,512)** = přesně cílová úloha,
      11,4 GB volné VRAM. `requirements.txt` doplněn (cu128 instrukce + smp).

## Sezení 73 (2026-06-02) — layout mimo mapové území → label 255 ignore (GT kvalita, část B)
- [x] **Layout-ignore (`map_gt._detect_map_area`):** runnability GT kontaminoval obsah MIMO mapu (legenda,
      control-description tabulka, titulek, tiráž, logo, bílý papír kolem mapy — label 0 = falešná průchodná
      plocha). **Measure-first vyvrátil geometrii:** naivní největší-komponenta (po morf. uzavření) i XY-cut
      (projekční profil) v probu SELHALY (tabulka se spojila s mapou / kernel uřízl mapu) → křehké napříč
      variabilitou. **Zvolen hybridní BAREVNÝ detektor:** mapa má sytou ISOM paletu (`_MAP_COLOR_KEYS` = zeleň/
      modř/hněď/žluť), mimo-mapové bloky černobílé (mřížka/text) nebo bílý papír. Dlaždicová mřížka (~1/120 strany)
      → dlaždice „mapová" když >4 % mapově-barevných pixelů → dilatace scelí řídké okraje → největší souvislá
      komponenta + `fill_holes` = mapové území (vnitřní bílý les se vyplní), zbytek → `IGNORE=255`.
- [x] **`_classify` refaktor:** vrací index nejbližší ISOM barvy (ne rovnou label) → jeden argmin pro runnability
      label (`_LABEL`) i mapovou plochu (`_MAP_COLOR_KEYS`). Layout-ignore aplikován AŽ NAKONEC v `segment_gt`
      (vše mimo mapu → 255 bez ohledu na runnability/přetisk uvnitř okraje). Vedle přetisk-ignore ze Sez. 72.
- [x] **Verify (17 map, vizuál):** titulky/tiráž/loga/papírový okraj zachyceny, **mapa BEZ false-cropu** (konzervativní
      asymetrie — radši drobná kontaminace než ztráta terénu). Vysoké mimo-% (medián ~36 %) = legitimní papír kolem
      organické mapy, ne vada. Korpus přesegmentován 268/268.
- [x] **Known limitation (přijato, odloženo):** control-description tabulka s barevnými ISOM symboly blízko mapy
      proklouzne (dilatace ji spojí s mapou, symboly = mapová barva) — byl to hlavní cíl B → uživatel zvolil
      „přijmout částečné B" (titulky/papír vyřešeny). Nový TODO „detektor mřížky tabulek". Barevné titulky (žluté
      pozadí) taky občas proklouznou (volba „nechat konzervativně").

## Sezení 72 (2026-06-02) — fialový přetisk tratě → label 255 ignore (GT kvalita, část A)
- [x] **Fialový přetisk tratě → label 255 ignore (`map_gt.py`):** runnability GT kontaminoval přetisk tratě
      (kroužky kontrol/spojnice/čísla/titulek — ne ISOM runnability barva). Měření: **31 % keep map (68/216)** ho
      nese → systematické, strukturální krok (ne per-mapa tag). 2 purpurové odstíny ODEČTENY z reálných rastrů
      (verify, jako olivová Sez. 71): `purple_a` 178/24/148 (magenta) + `purple_b` 176/8/230 (fialová) → nový
      label `IGNORE=255`. Verify izolovanosti: d=138/199 od nejbližší legitimní barvy (> olivová ~100), nekrade.
      Maska oddělena PŘED median (255 by zkreslil okno), dilatace `_OVERPRINT_DILATE=2` px (antialiasovaný okraj).
      Trénink přeskočí přes `ignore_index`. `gt_vis` ignore = magenta.
- [x] **OOB šrafa (ISOM 709) → taky ignore, bez výjimky** (volba uživatele „lepší menší vzorek než zavádějící
      výjimky"): velká purpurová OOB plocha (709, 2-3 mapy) padá do stejné barvy. „Generalizuj jen s důkazem" +
      ignore konzervativně poctivé (šrafa zakrývá podklad) + KISS jedna barva/jeden mechanismus. Kdyby vadilo:
      `keep_override=false`.
- [x] **Verify:** 262617 (nejvíc přetisku) trať+titulek+tiráž → ignore 8,4 %, plochy netknuté (vizuál OK);
      970619 (bez tratě) ignore 0,0 % (žádné false-ignore); 1027569 lesní 4,7 %. Korpus přesegmentován 268/268.

## Sezení 71 (2026-06-02) — olivová 520 GT fix + %AUDIT:CODE (vynucený) + kurace korpusu (taxonomie + manifest)
- [x] **Olivová 520 → label 0 (`map_gt._classify`):** GT chyběla olivová reference → out-of-bounds (zahrady/
      zástavba) klasifikováno jako falešná zelená runnability. 2 odstíny ODEČTENY z reálných rastrů (verify-against-
      source, ne aproximace `C_OLIVE`): `olive_a` 152/184/24 (sprint) + `olive_b` 168/168/56 (lesní OCAD) → label 0.
      Verify: Máchovka olivová vesnice → bílá; korpus 268/268 přesegmentován. **Nález:** falešnou zeleň na SPRINT
      mapách dominuje navíc růžová canopy (248/200/184) + šedé budovy (120/120/120); na lesních <1,5 % → sprint
      artefakt → kurace (volba „jen olivová + kurace"), NEřešeno v segmentaci.
- [x] **%AUDIT:CODE (vynucený, +1121 LOC od Sez. 60, 0 kritických):** čten celý nový kód (livelox/rock_relief/
      forest/map_gt + generator integrace). **D1 mrtvý kód po Sez. 63** — `zabaged.fetch_rock_areas` +
      `map_rock_area_to_isom` + `ROCK_AREA_LAYERS` smazány (206 plocha přešla ZABAGED→DMR, funkce nikdo nevolal) +
      2 drifty komentářů. **K1** `livelox._ensure_connectors_on_path()` (DRY sys.path), **K2** CLI `classCount`
      přes `.get`, **K3** forest komentář řezů. Behavior-preserving: proc 81=81 (git stash, seed 42). py_compile OK.
- [x] **Kurace korpusu — `connectors/curate.py` (merge-aware) + `_curation.json`:** GT = strop supervised modelu →
      268 map otagováno. Discipline {classic/sprint/mtbo/overview} + quality tagy (auto: variant_contour/variant_black/
      base_layer/basemap/training/foreign_crs; vizuál: legend/logo/damage). `keep = keep_override JINAK (classic AND
      bez disqualify tagu)`. Reader `load_curation`/`kept_dirs('classic')` (kontrakt UC5 loaderu). Merge zachová ruční
      tagy přes re-run (idempotent). **268 → 216 keep classic.**
- [x] **Vizuál průchod (kontaktní archy):** green-gate <8 na variant/base tagy → opravilo **false-drop `1177415`**
      (podkladovka g33 = plná mapa). **False-keepy:** `1117080` OSM Bright (ne-OB podklad → auto-tag `basemap`),
      `655492`/`656122`/`732266` fotky vytištěných map (papír/loga/control-table → `damage`, disqualifying). `970619`
      legenda+logo ale mapa OK → keep. Gestalt keep set = genuine OB lesní mapy potvrzen.
- [x] **Měření kurace:** green% sprint vs les NEodlišuje (olivová už label 0); hlavní osa = měřítko. **Recency
      neměřitelná** — `meta.json` neukládá datum eventu (gap → follow-up).

## Sezení 70 (2026-06-02) — UC5 korpus škálování: `allEvents` reverz → batch 268 reálných OB map
- [x] **`allEvents` reverzováno proti zdroji (home.js):** `?tab=allEvents` = URL Knockout SPA; skutečný endpoint
      **`POST /Home/SearchEvents`** (JSON). Tělo: `geoRectangle` GeoBox {south,north,west,east}, `timePeriod`
      enum (`from`/`to` čteno jen při customTimePeriod), `orderBy`, `maxNumberOfResults` strop 500. Event nese
      `classes[].id` = classId pro `download_map` → žádný ORIS/párování (gate 2 Sez. 68).
- [x] **Klíč 8267 tříd ≠ 8267 map:** třídy 1 eventu sdílí JEDNU mapu (různé tratě) → 1 class/event (max
      participantCount) = ~840 unik. map; historická řada vzniká mezi eventy (Slovanka 9×) → zachována.
- [x] **Batch pipeline `livelox.py`:** `search_events`/`list_events_by_year` (roční okna obchází strop 500)/
      `pick_class_id`/`download_corpus` (idempotent, error-souhrn, progress+ETA) + CLI `list`/`batch`. Konstanty
      `NORTH_BOHEMIA_BOX` + `LUSATIA_BORDER_BOX`. Batch od nejnovějších (cenná data první). Geo: 840 CZ S.Čechy +
      25 DE Žitavsko-Šluknovsko (série SAXBO) = 865 eventů.
- [x] **Bug fix (nález uživatele):** `download_map` mkdir PŘED fetch → faily nechávaly prázdné adresáře. Mkdir
      přesunut ZA získání dat (vše do paměti, pak adresář+zápis). 30 prázdných uklizeno.
- [x] **ORIS návrh zavržen DATY (synergie):** měření 50 starých (2020–22) = typ A 56 % (`classBlobUrl:None`, mapa
      fyzicky není) + 404 40 % + typ B 4 %. 96 % bez rastru → ORIS dá souřadnice ne kresbu → nepomůže. ALE odhalil
      **typ B** (rastr+georef pod `boundingQuadrilateral` WGS84, `projectionEpsgCode:None`).
- [x] **Krok 2:** (a) **WGS84 fallback** (`_resolve_georef`: epsg=4326, quad z WGS84 rohů, mpp metr. aproximací,
      `georefFallbackWgs84` flag) — georef ověřen blendem (gate 2 sedí); (b) **`_open_with_retry`** backoff 2→4→8s
      (404/403/410 trvalé neretryovat, timeout/5xx/conn transient) — řeší `WinError 10060` + ban prevence, DRY se
      `_post_search_events`; (c) `sleep_s` 0,5→1,0.
- [x] **Výsledek:** běh 1 = 205 map, re-run krok 2 = **268 map** (+63: 43 typ B + ~20 transient), všech 268 se
      segmentací GT, 0 prázdných. Výtěžnost 31 % (zbytek doloženě mrtvý). **UC5 korpus z 4 → 268.** Censure 0.

## Sezení 69 (2026-06-02) — %CALIBRATE + %AUDIT:DOCS (úklidové sezení, oba audity zralé)
- [x] **Fokus „2 pak 1"** (volba uživatele) — audity teď (foundations-before-curtains: `livelox.py`/`map_gt.py`
      ze Sez. 68 ještě neprošly úklidem), škálování korpusu příští sezení.
- [x] **Stale Příště:** compare/Slovanka viselo jako vedlejší carry **9×** (od Sez. 59) → **DROP** (zůstává v TODO
      jako nález, přestane se navrhovat; mirror oplocené terény Sez. 57).
- [x] **Metoda:** dva audity najednou (precedent Sez. 34/57); %CALIBRATE sám, %AUDIT:DOCS 3 paralelní agenti →
      nálezy profiltrovány proti zdroji (5/15 tvrdých, zbytek zamítnut jako šum — lekce Sez. 46).
- [x] **%AUDIT:DOCS — 5 tvrdých + 3 měkké, vše opraveno:** T1 `README:81` DEV_LOCATIONS 3→5 lokalit (HS 5×5,
      NV 3×5, „Nová Louka"); T2 rokle → **107 Erosion gully** doplněna do `--linefeatures` ve 3 souborech
      (README/architecture/generator-README, Sez. 58 nepropsána); T3 `generator-procedural.md` **301.1 → 301**
      combined ×3 (kód Sez. 58); T4 `generator/README` parkoviště **501 → 501.1** (Sez. 57); T5 překlep
      „zvlástě"→„zvláště". Měkké: Karttapullautin URL (z RESEARCH.md, DRY), GLOSSARY heslo **rock-relief 206**,
      generator-procedural §4 stav-blok doplněn o real-půlku.
- [x] **%CALIBRATE — 5 nálezů, vše opraveno:** C1 `settings.local.json` allow-list **~190 → 15** (mrtvé
      `sandbox/generator-poc/` cesty od Sez. 39 + jednorázové scratch; opakující se nález Sez. 17/51); C2 PROMPTS
      Stale check na **všechny** Příště body (ne jen fokus); C3 cadence formulace „práh dosažen = zralý kandidát /
      o ≥2 = vynucený první bod"; C4 `CLAUDE.md` klíč. soubory `connectors/` (+ruian/forest/ortofoto/livelox/map_gt
      + arcgis.py); C5 zkráceno 6 nejdelších DIARY hooků (index překračoval read cap).
- [x] **Cleanup:** `temp/rockcore/` smazán (obsolete po handoffu Sez. 63).
- [x] **Verify:** 0× `.py` mezi změnami (10 tracked docs/config), proc baseline 65 triviálně drží. settings
      gitignored → neovlivní druhý stroj. Cadence reset: %AUDIT:DOCS + %CALIBRATE oba Sez. 69. Censure 0.

## Sezení 68 (2026-06-02) — Livelox probe gate 1+2 PROŠLY → `connectors/livelox.py` + `map_gt.py` GT + georef blend
- [x] **Foundations: request tvar ze ZDROJE** (`yoav28/livelox-map-downloader-extension` MIT, `src/popup.js` přes `gh api`) — `POST /Data/ClassInfo {classIds:[id]}` → `general.classBlobUrl` → `GET blob` → `map.images` + `map.projectedBoundingQuadrilateral`. Nehádáno.
- [x] **Probe na 4 mapách** (závod 1116300 + uživatel dodal Mimoň 1116255 / Peklicko 1144077 / Slezsko 1192962 — rozmanité).
- [x] **GATE 1 (rozlišení) PROŠEL s výhradou** — stažitelné max = `images[0]` = **1,33 m/px** (`tiles` = rozřezaný tentýž obraz, NE vyšší; thumbnaily separátní). Nativní 0,75 m/px server-side nedostupné. Konstantní napříč velikostmi i měřítky (1:10000 i 1:15000). Pro PLOŠNOU runnability GT stačí, jemné symboly ne.
- [x] **GATE 2 (přesnost quadu) PROŠEL, fit NETŘEBA** — `projectedBoundingQuadrilateral` reprojikovaný → S-JTSK, afinní warp přes ortofoto → quad sedne BEZ feature-fitu na 4 mapách (vizuál verify). → `oris.py`/fitter overkill (princip „stav až s důkazem" potvrzen).
- [x] **🔴 CRS číst z dat, nikdy hardcode** — CRS se mezi mapami liší (S-JTSK 5514 i UTM33 32633) a NEZÁVISÍ na poloze (Slezsko 18,8°E = 5514, ne UTM34); = co kartograf nastavil v OCAD. `projectionEpsgCode` z blobu, pyproj univerzálně.
- [x] **`connectors/livelox.py`** — `download_map(classId)` → `resources/livelox/<id>/`: `map.png` + `meta.json` (georef quad + epsg z dat + provenance/licence) + `blend.png` (`make_blend=True`, warp přes ortofoto = georef důkaz; `build_georef_blend` + `_fit_affine`/`_warp_to_grid`, lazy importy). Idempotentní. Sourozenec dmr/zabaged/ortofoto.
- [x] **`connectors/map_gt.py`** — `segment_gt(map.png)` → `gt_labels.png` (index 0=průchodný/1=406/2=408/3=410/4=open, trénink) + `gt_vis.png` (verify). Nearest-color na ISOM refs + majority(7px) filtr. ISOM_REF = KOPIE z `compare_real_vs_gen` (Sez. 64); DRY dluh do TODO (extrakce až 3. konzument).
- [x] **Umístění korpusu (AskUserQuestion):** `resources/livelox/<classId>/` — odděluje auto-korpus od ruční compare sbírky, per-mapa struktura, gitignored (kryje TDM/privátní režim).
- [x] **GT probe** (verify before invest) — nearest-color + majority → použitelná plošná runnability GT (zelená 3 úrovně + žlutá). Omezení: olivová 520 → brown (není v refs, runnability nevadí). Rozpady 4 map: zelená 7–18 %, open 6–23 %.
- [x] **Korpus 4 mapy** kompletní (map.png + meta.json + gt_labels/gt_vis + blend, gitignored). proc baseline 65 nedotčen (UC2/UC5 konektor mimo generátor). gitignore + idempotence + epsg-z-dat ověřeny.
- [x] **Škálování na ~200 map (vstup uživatele) → příští fokus:** Livelox `allEvents` + ORIS souřadnice. **Oponentura: ORIS netřeba** (blob georef stačí, gate 2) → pipeline = allEvents → classId → batch. Zbývá reverzovat allEvents endpoint + rate-limit.

## Sezení 67 (2026-06-02) — OOM verify Test OK + IDEAS/TODO pruning + %THINK směr → UC5 runnability korpus (Livelox)
- [x] **OOM `.omap` verify Test OK** (uzavřen hlavní carry Sez. 62→66) — forest-age 406/408/410 (NL/NV) +
      rock-relief 206 (HS/SV) ověřeny uživatelem v OpenOrienteering Mapperu. Foundations forest-age + rock-relief
      hotové → odblokováno uvažování o dalším UC5 kroku.
- [x] **IDEAS/TODO pruning** (cadence zralá +15 od Sez. 50, reset Sez. 67). **TODO:** hotové `[x]` pryč (holes
      support, 501.1, forest-age — carry OOM verify dnes uzavřen, balvany-linie 208 → zhuštěno na zbytek `Sesuv_půdy_suť`
      210); DROP oplocené terény (Sez. 57) + crossability vody (vyvráceno Sez. 58) + `map.omap` area close-flag verify
      (vyřešeno desítkami OOM verify). **IDEAS:** zhuštěno 5 dozrálých bloků → odkaz do DONE (prediktor mapy, reálné
      vrstvy ZABAGED, synteticky renderované, ISOM 2000↔2017-2, INSPIRE). Vše dozrálé žije v DONE → bez ztráty informace.
- [x] **%THINK směr projektu** (po vytěžení UC2 fáze I) — A (UC5 ortofoto model) / B (compare hloubka) / C (korpus
      nejdřív) / D (UC3 de-purple). **Volba uživatele = C.** Foundations-first: UC5 runnability model je supervised →
      potřebuje GT z reálných map; bez korpusu nestavitelný (záclona před základy).
- [x] **Conceptual-integrity nález:** teze „trénink = syntetika, licence bezpředmětná" (reframe Sez. 4, KB
      data-sources ř. 257-258) platí jen pro STRUKTURU — **runnability model reálný GT POTŘEBUJE** (vegetace gate
      Sez. 59 = generátor runnability neumí → syntetika cirkulární). KB opravena.
- [x] **Pragmatická cesta (volba uživatele):** ~99 % privátní experiment → korpus ~100 map bez licence; legalizace
      (ČSOS) AŽ pokud model funguje. Právní krytí = **TDM výjimka** (AutZ ČR 2023 / EU DSM 2019/790; přesné znění k ověření).
- [x] **Deep research „zdroje reálných OB map" (103 agentů, ~2,8M tok., 21 zdrojů, 21/25 claims confirmed):**
      **Livelox** = nejlepší dostupný zdroj — stažitelný přes interní endpointy `/Data/ClassInfo`+`/Data/ClassBlob`
      (2 open-source nástroje, yoav28 MIT + routechoiceslivegps live web), ale **jen RASTR** (PNG; vektor 3. strana
      nestáhne) + georef = 4 WGS84 rohy (→ reprojekce S-JTSK). Routegadget slabší (JPG 150-200 dpi). **MapAnt FI/ES
      vyloučit z GT** (strojové z LiDAR = cirkulární). **Petrovič 2018 (peer-reviewed) validuje směr:** derivace
      zelené z LiDAR hlučná (~47 % overlap, zelené třídy ~30-31 %) → ML má smysl. Žádný hotový ML korpus OB map.
- [x] **%THINK georef pipeline (gen jako reference = inverze compare):** ORIS lookup (metadata/fallback) → Livelox
      download (rastr+quad) → gen projekce téže lokality (tvrdá geometrie S-JTSK) jako kotva → feature-fit (podobnostní
      transformace vč. rotace=grivace) → georef rastr → segmentace = GT. **Dvě gates measure-first:** rozlišení (full-res
      vs náhled) + přesnost quadu (sedne rovnou, nebo nutný fit?). Probe lokalita = závod uživatele, olivový areál
      50.6906797N 14.8303997E. Nástroje: `livelox.py` + GT segmentace (jisté), `oris.py`/fitter (contingency, „stav až s důkazem").
- [x] **Formát-rozhodnutí (uživatel):** stáhnout OBA — vektor = GT (preferovaný, z Livelox nejde → od kartografů),
      rastr = picture (UC3/UC4-III + fallback); párovat přes georef.
- [x] Bez produkčního kódu (proc baseline 65 triviálně drží). Propagace: IDEAS (nový blok + 5 zhuštěných), TODO
      (pruning + probe), KB data-sources (Livelox sekce + oprava rozporu), GLOSSARY (Livelox + runnability), DIARY+diář.

## Sezení 66 (2026-06-02) — strategická diskuse (zelená/ortofoto) + příprava OOM verify (bez kódu)
- [x] **Vyjasněno „zelenou děláme jen z forest-age?"** — plošná runnability zeleň lesa (406/408/410) = jediný
      zdroj `--forest-age` (AOPK věk, PROXY, důsledek vegetace gate). Ale 406 jde i ze stromořadí (`--treerows`)
      a 402/402.1 udržovaná zeleň ze `--surfaces` — z tvrdých dat, gate neporušují.
- [x] **Vyjasněno „proč HS/SV bílý les"** — doložená AOPK mezera (mimo „Les_Mapy" dataset), ne bug; odlišeno od
      bílého lesa NL/NV = záměrná predikce (`BARVA` nad `BARVA_SLOW_MAX` = starý/průchodný les).
- [x] **Ortofoto predikce oponována vlastním měřením (Sez. 63/64):** (a) single-epoch greenness→ISOM třída NEJDE
      (separabilita ~50 %, všechny ISOM zelené jsou vegetace, podrost shora neviditelný = gate); (b) multi-temporal
      časosběr = UC5 model (CV projekt), ne deterministická vrstva. Závěr: „ortofoto predikce" = UC5, foundations
      tlačí dokončit OOM verify forest-age+rock-relief dřív.
- [x] **Příprava OOM verify** (lekce Sez. 65 — mtime past): ověřeno NL/NV/HS/SV `.omap` z 2026-06-02 09:13–09:20,
      `.omap`=masky shodný mtime (konzistentní). Verify checklist předán (NL nejlepší forest-age, `BARVA 11` knoflík;
      HS/SV rock-relief). OOM verify zůstává carry (uživatel zavolal %END před otevřením OOM).
- [x] Bez kódu (proc baseline 65 nedotčen). Propagace: DIARY index, DONE, diář.

## Sezení 65 (2026-06-02) — fix rock-relief HTTP 500 (server práh ~7 Mpx) + regen 5 DEV
- [x] **Nález: Sez. 63 rock-relief regen byl nekompletní** — NL/LS/SV `.omap` mtime (22:xx) o hodinu starší
      než rock-relief fáze (HS/NV 23:xx); zůstaly se starou ZABAGED 206. Uživatelův postřeh nad `.omap` datem.
- [x] **Diagnóza: ImageServer `exportImage` vrací HTTP 500 nad ~7 Mpx** (F32 tiff; empiricky 6,8 OK / 8,2 fail,
      4× deterministicky). 6×4 km @ `TARGET_PX_M=1,5` = 4000×2667 = 10,7 Mpx; `MAX_PX=4000` clampoval STRANU,
      ne PLOCHU → neochránil. Cache miss = důkaz, že NL/LS/SV hi-res fetch v Sez. 63 nikdy neuspěl. HS prošlo na
      2501×2501 (TARGET_PX_M=2,0 cache, 6,3 Mpx), NV na portrait 6,67 Mpx — odtud falešný dojem „8 map regen".
- [x] **Fix `generator/rock_relief.py`** (volba uživatele = KISS plošný cap): `MAX_AREA_PX=6_500_000` → clamp
      `gw_hi·gh_hi` odmocninou (poměr drží), `MAX_PX` ponechán jako sekundární stranová pojistka. Oprava docstring
      driftu („TARGET_PX_M ≈ 2 m" → 1,5 m). Velké landscape výseky zhrubnou na ~1,9 m/px; tiling pro 1,5 m = budoucí.
- [x] **Regen všech 5 DEV** (konzistentní rozlišení jedním capem): NL→3122×2081 (1,92 m), HS→2549×2549 (1,96 m),
      NV→1974×3291 (1,52 m). Skály 206 z DMR: **NL 197 / LS 219 / SV 239 / HS 936 / NV 49**. NL/LS/SV teď mají
      skutečnou DMR rock-relief. Vše exit 0.
- [x] **Forest-age SV bílý les = doložená mezera** (AOPK probe: SV 0 porostních skupin, Lužické hory mimo
      „Les_Mapy"). Histogram `BARVA` připraven jako OOM reference (NL 213 skupin = nejlepší; LS 12 = slabý;
      `BARVA 11` na hraně bílá/406, NL 55×). OOM verify zůstává carry (uživatel „nechme to tak").
- [x] Propagace: spec §4.9f (plošný cap + nález), DIARY index, DONE, diář.

## Sezení 63 (2026-06-01) — skalní plochy 206 z DMR sklonu (rock-relief) + forest-age na 8 map
- [x] **Forest-age na všech 8 testovacích mapách** (carry Sez. 62): NL 341 / LS 490 / NV 696 / Bedřichovka 289 /
      Blatná 177 / Velbloud 373 (matched výseky reálných map z `.pgw`); **SV 0 / HS 0 = mimo AOPK pokrytí**
      (ověřeno probem: HS 0, SV 4 slívky — Český ráj/Lužické hory v AOPK „Les_Mapy" datasetu nejsou; ne bug, doložená mezera).
- [x] **%THINK rock-relief** (handoff `temp/rockcore/HANDOFF_FOR_AI.md` — detekce skal z DMR sklonu). Studie:
      Mapy.com ≠ ZABAGED render (jiná geometrie), detail Mapy.com = z RELIÉFU; zadání = jednobarevné POLYGONY
      bloků, ne reliéf; maska na SKLONU (směrově nezávislý), ne hillshade tmavost. Tři rozhodnutí (deps/rozlišení/vztah).
- [x] **`generator/rock_relief.py`** — port rockcore bez Streamlit/rasterio/shapely: DMR fetch přes `dmr.py`
      (S-JTSK), sklon `np.gradient`, práh 46°, scipy morfologie (opening/closing/fill_holes/label), vektorizace
      přes **contourpy** (úroveň 0,5), Douglas-Peucker + Chaikin v numpy, vnoření děr (even-odd) → polygony
      [outer,díra…] v S-JTSK. **Závislost scipy** (volba uživatele; shapely/rasterio obejity).
- [x] **Integrace = NAHRAZENÍ ZABAGED 206** (volba uživatele): `_generate_real_rocks` sekce 3 už netáhne
      ZABAGED `Skalní_útvary`, místo toho `rock_relief.detect_rock_areas` → 206 (body 204/207 + pole 208 ZABAGED zůstaly).
      Týž kreslicí/omap tok (polygony [outer,díra…] = mirror geom_to_polygons).
- [x] **Verify proti Mapy.com** (požadavek uživatele): render Šulcáku (týž výsek jako handoff `02`) — na 0,8 m
      **49 polygonů = shoda s rockcore (48)** + struktura sedí na Mapy.com reliéf; jednobarevné polygony = správný typ výstupu.
- [x] **Rozlišení = 1,5 m** (`TARGET_PX_M`, volba uživatele): jeden DMR fetch do ~6 km (6000/1,5=4000=MAX_PX),
      bez tilingu; citelně jemnější než 2 m. Native ~1 m by chtěl dlaždicování (odloženo).
- [x] **requirements.txt** založen (numpy/Pillow/contourpy/pyproj/scipy) — kvůli scipy + druhý stroj (git sync).
- [x] **Verify:** proc baseline **65 drží** (rock_relief jen v `--rocks real`); 8 map regen (206 z DMR: HS 744 /
      SV 79 / NV 26 / LS 20 / NL 6 / Bedř 2 / Blatná 0 / Velbloud 0 — dle terénu; DMR má národní bezešvé pokrytí,
      i SV má skály ač forest-age ne). STATISTICS regen. Propagace: spec §4.9f, architecture, katalog (Skalní_útvary
      ⊘ nahrazeno), READMEs×3. Censure 0.

## Sezení 62 (2026-06-01) — věk porostu → zeleň (`--forest-age`, první UC5 predikční střípek, PROXY)
- [x] **%THINK nad celým návrhem** (volba uživatele před kódem) — odhalil: (a) **číselník `BARVA`→věk
      DOLOŽEN** standardem KSLH `KSLH021114.pdf` (Sez. 61 měl jen 301-redirect uložený jako `kslh.pdf`;
      skutečný PDF stažen do `temp/uhul_probe/kslh_real.pdf`): `BARVA` = ordinální věk (Tab. 4
      `Min((A+19),179) div 20`), `ZNACKA`=zakmenění (ve službě vždy 1), **`BARVA 15`=bezlesí** (Tab. 5 BZL);
      (b) **ISOM oprava**: diár Sez. 61 psal „410 Veg: walk" — 410 je *fight*, 408 je *walk*; (c) reframe
      uživatele: vrstva = **predikce** (2. půlka generátoru, „realisticky vyhlížející, mimo real jistoty").
- [x] **Kalibrační probe** (`temp/uhul_probe/calibrate.py`) — distribuce `BARVA` na NL/LS/NV;
      **`maxRecordCount=1000` → paging po 1000** (verify-against-source: bez toho by default 2000 podtrhl LS >1000).
- [x] **Konektor `connectors/forest.py`** (krok 1) — AOPK „Les_Mapy" vrstva 19, reuse `arcgis.fetch_geojson_layer`
      (server `gis.nature.cz`, S-JTSK 5514, mirror ruian). `map_forest_age_to_isom`: laditelné řezy `BARVA_*_MAX`
      → 410 fight / 408 walk / 406 slow / None (staré+bezlesí → bílá). Číselník/směr doložen, řezy = proxy kalibrace.
- [x] **Zapojení do generátoru** (krok 2) — `--forest-age real` (default), `_generate_real_forest_age` +
      `_draw_forest_age_area` (plná zeleň bez obrysu, díry; mirror surfaces/treerows), z-order nad pokryvem /
      pod stromořadím; `mask_forest_age.png` (multi-class 1=410/2=408/3=406); barvy z palety C_GREEN3/2/1;
      .omap area objekty 406/408/410 (USED_CODES + AREA_CODES + `forest_age_features` v `write_omap`);
      meta **vlastní sekce s `proxy:true` + `note`** (ne `_layer_meta_section` — jiný zdroj/licence AOPK);
      CLI flag, batch B1 off v obou větvích, stats.py SYMBOLS 408/410 + sekce `forest_age`.
- [x] **Kalibrace = ABSOLUTNÍ řezy** (rozhodnutí uživatele po vizuálu) — per-mapová kvantilová normalizace
      ZAVRŽENA: vynutila by 410 i na holé staré svahy (fabrikace) a rozbila absolutní význam + UC5 konzistenci.
      Variace mezi mapami = věrná (NL/LS zeleň menšina, NV plošně zelená = mladý hospodářský les, holý svah bílý).
- [x] **Verify:** proc baseline **65 objektů drží** (nová vrstva čistě za `--terrain real`); 5 DEV přegenerováno
      (forest_age NL 341 / LS 490 / NV velký; **SV 0 / HS 0** = mimo AOPK pokrytí, graceful); meta `proxy:true`
      + 341 omap objektů ověřeno; STATISTICS 406/408/410 (406 = stromořadí+slow). **OOM `.omap` verify = příště (ruční).**
- [x] **Propagace docs:** data-sources K1→implementováno, GLOSSARY (`forest-age-proxy` termín + projekce/predikce),
      spec §4.9p, architecture UC2/UC5 most, connectors/generator/root README, STATISTICS. Censure 0.

## Sezení 61 (2026-06-01) — probe 3 kandidátů plochy hustníku → K1 ÚHÚL věk porostu zvolen
- [x] **Probe 3 kandidátů PLOCHY hustníku (measure-first, carry podmínka Sez. 59)** — fokus z Příště Sez. 60.
      Desk verify (co každý zdroj REÁLNĚ měří) + technický probe REST. Žádný produkční kód (`temp/uhul_probe/`).
- [x] **K1 ÚHÚL věk porostu = ZVOLEN k implementaci (Sez. 62), jako hrubý proxy** (volba uživatele: odstupňovaně).
      Strojově dostupný: **AOPK `gis.nature.cz/.../Les_Mapy_20nn/MapServer` vrstva 19 „Porostní skupiny 2022"**
      (esriPolygon, **371 236** polygonů celostátně, z LHP+LHO Lesy ČR+ÚHÚL; S-JTSK 5514; licence z. 106/1999 open).
      Atribut **`BARVA` = věková třída** (20-letý interval — DOLOŽENO dokumentací porostní mapy, ne hádáno;
      `ZNAČKA`/šrafa = zakmenění; `DBID` = cizí klíč do neveřejné LHP DB; číselník `BARVA`→věk ze service NEjde
      [renderer simple] → z Informačního standardu LH).
- [x] **Slabiny K1 (změřeno):** (a) věk = hrubý proxy, ne runnability; (b) pokrytí DĚRAVÉ **3/5 DEV**
      (NL 2381 / LS 990 / NV 2243 ✓; **SV 0, HS 0** — sešito z LHP různých roků platnosti); (c) data 2022 statická.
- [x] **K2 Copernicus HRL TCD = SLABÝ** (korunový zápoj 10 m shora = tatáž zeď jako CHM Sez. 59; neproměřováno —
      strukturálně doloženo). **K3 multi-temporal ortofoto = nejsilnější koncepčně, ODLOŽEN** (jediný bez pasti
      zápoje, ale velký CV projekt = vlastní UC).
- [x] **Plán Sez. 62:** konektor na AOPK (znovupoužít `connectors/arcgis.py`), číselník `BARVA`→věk z IS LH,
      **mlazina (1. stupeň ~1-20 let) → 410 Veg: walk / tyčkovina (~21-40) → 406 slow**, starší → bílá; omap/maska/stats
      kanál; **označit jako PROXY** (GLOSSARY/spec — zelená z věku ≠ terénní runnability). Censure 0 (verify-against-source
      dodržen: BARVA=věk doloženo dokumentací; pokrytí změřeno na všech 5 DEV; K2 = už změřená zeď Sez. 59).

## Sezení 60 (2026-06-01) — %AUDIT:CODE (úklid driftu po vlně Sez. 50→59)
- [x] **%AUDIT:CODE** (LOC práh ≥500 překročen: net +616 LOC od Sez. 50, +9 sez). `generator.py` (3716 ř.)
      přečten celý sám + 2 agenti na okraj (zabaged / omap_export+compare+stats+batch), nálezy ověřeny proti
      zdroji (precedent Sez. 46/50). **0 kritických, 0 mrtvého kódu** — refaktory Sez. 50 a izomorfismus drží;
      `batch.py` B1 ověřena (16 real vrstev v obou větvích = validační smyčka).
- [x] **N1 (funkční): `stats.py` SYMBOLS doplněn o 107 Erosion gully** — `main()` iteruje jen SYMBOLS →
      STATISTICS.md rokli nesledoval (gen kreslí, `USED_CODES` má). Verify: 107 řádek v tabulce (· = Σ0 na DEV).
- [x] **N2 (funkční): `compare` GEN_CAPABILITIES synchronizován** (208/501.1/523/412/402/402.1) + komentář
      přepsán „kalibrovaný řez pro STAT 1, NE SSoT schopností (= `USED_CODES`)". Falešný klíč `line-feature`
      (bez CROSSWALK protějšku) zachycen a stažen před dokončením.
- [x] **9× drift komentářů/docstringů opraveno**: `_generate_real_rocks` (208/čtyři vrstvy), maska surfaces
      (5 tříd), `_generate_real_surfaces` docstring (park→402), z-order výčty (+208/+107), `zabaged`
      boulder-cluster docstring (208 realizováno) + „Each item"→„Každý prvek", `omap_export` docstring na
      `USED_CODES`, `stats` 510 oficiální název, omap 530 popisek. Behavior-preserving (proc 65 drží).
- [x] py_compile OK (5 souborů); STATISTICS.md regen (107/510/208 ověřeny). **%AUDIT:CODE reset Sez. 60.**

## Sezení 59 (2026-06-01) — UC5 „stonecore" = zelená věrnost → vegetace gate DOLOŽENA měřením
- [x] **UC5 první střípek = věrná zelená vegetace** (volba uživatele, „dokud nebude v lese spousta zelené,
      nebude to OB mapy připomínat") = `green real 30 % → gen 0 %` mezera ze Sez. 58. Foundations: ISOM zelená =
      runnability podrostu, NE land-use; z polygonu neodvoditelná (vegetace gate Sez. 3).
- [x] **Stažení DMP 1G mračna PLNĚ automatizováno** (UC2 cesta, `temp/lidar_probe/`): klad SM5 REST
      (`KladyMapovychListu/MapServer/24` → list NBOR52) + ATOM `openzu.cuzk.cz/opendata/DMP1G/…` + `laspy[lazrs]`.
      lasertool SEGFAULT Win11 (13 let starý Qt4) → CHM přímo z laspy.
- [x] **🔴 TVRDÝ NÁLEZ: DMP 1G = 100 % single-return** (0 % multi-echo, klasifikace jen GROUND/HIGH VEG/building) →
      vegetation height = výška KORUN (CHM), ne hustota podrostu. **Věrná ISOM runnability z open ČÚZK dat NEJDE**
      (doloženo měřením). Dvojitá vazba: multi-echo jen archiv 2009-13 (staré) / ZÚ zakázka (placené); aktuální DMP OK = single-surface.
- [x] **Rozhodnutí uživatele:** zkusit jiný podklad PLOCHY hustníku (3 kandidáti: ÚHÚL / Copernicus HRL / multi-temporal
      ortofoto), jinak zaprotokolovat vegetaci mimo real část. **Bez produkční změny** (probe v `temp/`, jen `laspy` do venv).

## Sezení 58 (2026-06-01) — ZABAGED fáze I vytěžena (doloženo) → compare prohloubení na sbírce 6 map
- [x] **Strategie: ZABAGED fáze I VYTĚŽENA, doloženo měřením.** Otázka uživatele „100% vytěžený?" → 3 roviny:
      extenzivní ~98 % (5 marg. vrstev), intenzivní (crossability), strop = vegetace gate. **Crossability vody
      probnuta a vyvrácena** (`temp/probe_water_crossability.py`): `Vodní_tok` nemá pole šířky, jediný signál
      `typtoku_k` (splavný 099), a **099 = 0 na všech 5 DEV lokalitách** (splavné řeky = nížiny, ne OB lesy) →
      i můj protiargument (rovina 2) měřením padl. Plocha→301 už dnes správně. Fokus posunut UC2→compare.
- [x] **Sbírka 6 reálných map** (TrainsLab/resources, `probe_map_collection.py`): **SampleMap = UTM zone 10 =
      Severní Amerika** vyřazena (ZABAGED nepokrývá). 5 ČR Liberecko zkopírováno do `resources/` (gitignored):
      Soví vrch/Bedřichovka/Blatná (Křovák), Slovanka (UTM33), Velbloud (Křovák). Grivace 3,75–17° = magnetic-north
      (`.pgw` rotace = −grivace, ověřeno 5/5 → PNG export použil grivaci z `.omap`).
- [x] **Compare parametrizován** (`generator/compare_real_vs_gen.py`): `_map_paths(name)`, `main(name=…)`,
      `_stat1_crosswalk` vyčleněn (podmíněn na kalibrovaný „Soví vrch"), STAT 2 univerzální, argv. **Matched výsek**
      (`probe_matched_extent.py`): gen na S-JTSK obal rotované mapy z `.pgw` rohů → WGS84 (pyproj) → footprint = celá mapa.
- [x] **Tracer Bedřichovka E2E** → vizuál odhalil **layout kontaminaci** (rám/north-lines/legenda v rozích gen mřížky) →
      re-export čistého pole z Mapperu (volba uživatele, autoritativní georef). Po očištění: blue 2,5→1,3 %, green 39,6→30,4 %,
      brown prec 53→67 % (kontaminace doložena).
- [x] **Měření gate na 3 plně domapovaných cizích mapách** (Bedř/Blatná/Velbl): gen projektuje **tvrdou geometrii**
      věrně (les IoU 50–66, vrstevnice prec 67/rec 75, cesty prec 60–75), **vegetace ~30 % real vs ~0 % gen = gate**
      konzistentně; žlutá gen PODkresluje (gate z druhé strany). **Soví vrch OUTLIER** (white 94 %) = domapováno jen
      **~1/4** (NE export bug — korekce hypotézy), vyřazen z agregátu.
- [x] **Hodnocení fáze I ~60 % pokrytí** (otázka uživatele): vážená precision vrstevnice+cesty ~65 %, +žlutá ~52 %,
      +les ~76 %. Verdikt: tvrdá geometrie ~65 % věrná, nevymýšlí si (vysoká precision); ~třetinu mapy (vegetace/
      běhatelnost) vědomě nekreslí (strop ZABAGED → skok = UC5). Číslo = míra pokrytí tvrdé geometrie, ne známka kvality.
- [x] **(dodatek po %END) Vodní plocha 301.1 → 301** (combined s černou břehovou linií). Mapaři kreslí vodní plochy
      s okrajem = neprůchodné; omap exportoval 301.1 (bez okraje), rastr okraj měl od Sez. 18 → nesoulad. Oponentura:
      uživatel navrhl 301.2, ale ověření barev (301.2 = Blue 70% dominant) → zvolil 301 (Blue 100% + bank line, zachová
      odstín). Mylný komentář Sez. 18 „combined nepřiřaditelný objektu" vyvrácen kolejištěm 501. Verify: omap 301×23 /
      301.1×0; OOM Test OK.
- [x] **(dodatek po %END) Rokle/výmol → ISOM 107 Erosion gully** (`--linefeatures`, id 94). Probe: silnice ve výstavbě
      + rokle Σ0 na 5 DEV; silnice ve výstavbě nechána ✗ (staveniště ≠ 503), rokle → 107 (linie→linie, KISS ne 108).
      Mirror sráz 104 (hnědá solid, bez ticků). Verify > naslepo: v ČR 1388 (řídká), nejhustší shluk Moravská Třebová →
      omap 107×32, OOM Test OK. Katalog ○→✓. Připraveno pro úplnost (Σ0 na DEV).

## Sezení 57 (2026-06-01) — %AUDIT:DOCS + balvany-linie → 208 + parkoviště → 501.1
- [x] **%AUDIT:DOCS (zralý +11/10), 4 nálezy ověřené proti zdroji** (3 fan-out agenti, kriticky profiltrováno):
      **N1** broken links — 53 řádků `DIARY.md` mělo `](docs/diary/…)` po přesunu root→`docs/` (Sez. 48) → z `docs/DIARY.md`
      mířily na neexistující `docs/docs/diary/…`; fix replace_all → `](diary/…)`. **N2** „katalog vyčerpán" drift ve 3
      živých docs (README/architecture/spec) — SSoT katalog už koriguje (Sez. 55), architecture si navíc protiřečila
      (ř. 70 „vyčerpán" × ř. 74 Sez. 56); opraveno (diáře/DONE/index Sez. 52 = historie, ponechány). **N3** pořadí
      54/55/56 v indexu. **N4** generator/README `--paved` doplněno 501.1. Jazyk (agent 3) = 0 chyb.
- [x] **Balvany-linie → ISOM 208 Boulder field** (`--rocks`, 4. rock vrstva). Foundations: template id=38 = `area_symbol`
      pattern (náhodné trojúhelníky, OOM vyplní sám) + probe layer 13 polyline/jen `jmeno`→KISS. **Geometrie LINIE→PLOCHA
      přes buffer** (osa→pás 1,5 mm, volba uživatele) = mirror stromořadí 406. Kód: zabaged `BOULDER_FIELD_LINE_LAYERS`/
      `fetch_boulder_field_lines`/`map_…→208`; generator 4. blok `_generate_real_rocks` + `_draw_boulder_field_area`
      (maska=pás, rastr=deterministicky seedované trojúhelníky, `_point_in_ring`); omap `USED_CODES`+`AREA_CODES`+=208.
      batch beze změny (rocks off obě větve, B1 OK). **Verify:** SV 7/HS 3/NV 4=Σ14 (rastr=meta=omap); **proc byte-identický**
      (git-stash md5); **OOM Test OK** (uživatel). STATISTICS +208 řádek (stats.py SYMBOLS).
- [x] **Plot ISOM 516–518 → doložený SKIP.** Dotaz uživatele → probe MapServeru (149 vrstev): ZABAGED plot jako vrstvu
      nevede (jen Zeď 39/Hradba 38→513, Zábrana 54→519). Mapovat 516 bez dat = vymýšlet. Zapsáno do katalogu sekce 11.
- [x] **Parkoviště `Parkoviště, odpočívka` (123) → 501.1** (oprava z 501, nález uživatele v OOM). 501.1 = bez obrysu
      (průchozí plocha splývající s okolím); kolejiště zůstává 501 (vymezený prostor). Rozděleno `map_paved_to_isom`
      (Sez. 41 sloučilo na 501 DRY). Z-order: 501.1 → spodní `urban_base` průchod. LS 51× parkoviště → 501.1.
- [x] **Stale „oplocené volné terény" → DROP** z Příště (viselo 5×; zůstává v TODO jako nález Sez. 42).

## Sezení 56 (2026-06-01) — přechod ntbhej→mrkla + kamenolom → 520
- [x] **Přechod ntbhej→mrkla:** klon byl **15 commitů pozadu** (Sez. 49–55) → ff-sync PŘED prací (%BEGIN krok 0).
      Regen 5 lokalit s ortofotem (lokální rendery se přes git nepřenáší); **omap counts byte-shodné se Sez. 55**
      (SV 6036/NL 1833/LS 35649/HS 7555/NV 2302) → reprodukovatelnost potvrzena datově.
- [x] **Kamenolom `Povrchová těžba, lom` (id 118) → ISOM 520 olivová** (`--surfaces`, návrh uživatele: oplocený
      těžební areál = zákaz vstupu). **Místo odloženého 201 Impassable cliff:** 201 je LINIE (hrana stěny s ticky),
      ZABAGED dává PLOCHU → plocha→plocha věrná, stěnu nedotahujeme (KISS, Σ1). Izomorfní s hřbitovem. Foundations:
      probe `temp/probe_quarry.py` (LS Σ1 `kámen`, 0 překryv s areály 114 — nejbližší 469 m). Kód 6 editů: `zabaged.py`
      (`LAYER_IDS` += 118, `QUARRY_LAYERS`, `fetch_quarries`, `map_quarry_to_isom`→520), `generator.py` (5. zdroj 520
      do surfaces kanálu). Pod existujícím `--surfaces` → batch beze změny (B1 OK).
- [x] **Verify:** LS regen pokryv 20159→20160 / `.omap` 35649→35650 = přesně +1 (lom). Ring px bbox přesně na
      vykreslené olivové ploše. **A1 z-order** ověřen vizuálně: kamenné/zemní útvary kreslené NAD olivovou (žádná nová
      barva). Lom jen LS → ostatní 4 lokality bez regen.
- [x] **Propagace:** katalog (lom ○→✓ + souhrn + akční seznam), architecture, spec §4.9 (pět zdrojů 520), GLOSSARY,
      README root+generator+connectors.

## Sezení 55 (2026-06-01) — lanovka/vlek → 510 (sloučeno do `--powerlines`) + probe „katalog vyčerpán" korekce
- [x] **Lanovka/vlek/stožár → ISOM 510** (`--powerlines`, sloučeno s el. vedením). Verify-against-source
      PŘED kódem: template id=121 → ISOM 510 = „Power line, cableway **or skilift**" = JEDEN symbol pro
      vedení i lanovku; probe atributů (`Lanová dráha, lyžařský vlek` id=72 = `Polyline` s `typ_ldv_k`;
      `Stožár lanové dráhy` id=61 = `Point` bez atributů) → dokonalý mirror `Elektrické_vedení` +
      `Stožár_elektrického_vedení`. Volba uživatele **sloučit do `--powerlines`** (ISOM nerozlišuje, KISS,
      precedent --rocks/--landmarks). Kód = čisté rozšíření (4 edity): `LAYER_IDS` += 72/61, `POWERLINE_LAYERS`
      + `POWERLINE_MAST_LAYERS` += lanovka/stožár, `map_powerline_to_isom` docstring, `POWERLINE_NAME` →
      oficiální ISOM „Power line, cableway or skilift". `map_powerline_to_isom` už vracelo `return 510` → 0 změn logiky.
- [x] **Verify lanovky:** proc baseline **byte-identický** (md5 `a76af84…` git-stash diff → noise větev
      nedotčena, edity izolované do real powerline). Lanovka integrována PŘESNĚ dle probe: NL 2 / LS 1,
      ostatní 0 (delta omap objektů na SV/HS = nezávislý drift reálných dat). GT maska NL nese 2 vleky
      s příčkami na stožárech (fáze 1); rgb render = symbol 510. **Žádný nový ISOM symbol** → OOM verify
      netřeba (510 už ověřeno u vedení). 5 lokalit regen + STATISTICS.
- [x] **Korekce „ZABAGED katalog vyčerpán" (Sez. 52) + probe zbylých kandidátů.** Sez. 52 prohlásil katalog
      za vyčerpaný, ALE ○ kandidáti nebyli změřeni jako Sez. 43. Probe `temp/probe_remaining_layers.py`
      (`returnCountOnly` 5 lokalit): lanovka NL 2/LS 1 (→ HOTOVO), **balvany-linie 208 Σ14**, **podjezd 519
      Σ12** (LS 11), **hráz 528 Σ13**, **brod 519 Σ6**, vodopád 313 Σ2, lom 201 Σ1, suť 210 Σ1. Katalog
      doplněn o tvrdá čísla (ať se mýtus „0" nevrací). **Oprava driftu: strom `Významný_nebo_osamělý_strom`
      ◐→✓** (implementace `LANDMARK_POINT_LAYERS_417` existuje od Sez. 43, katalog ji vedl jako kandidát).
- [x] **Propagace:** katalog (lanovka/stožár ✓ + čísla + korekce vyčerpání), architecture, spec §4.9c,
      GLOSSARY, README root+generator, TODO (`[x]`→`[~]`, katalog není vyčerpán). batch beze změny (lanovka
      pod existujícím `--powerlines`, který je v batch off obě větve — B1 OK).

## Sezení 54 (2026-05-31) — podpora děr (holes) + `Ostatní plocha v sídlech` → 501.1 + color-table průlom
- [x] **Podpora děr (holes) v plošných vrstvách (ENABLER).** ZABAGED/GeoJSON nese vnitřní prsteny (díry)
      u velkých polygonů; dosud parser zahazoval. Tři vrstvy: **(1) parser** `arcgis.geom_to_polygons`
      vrací `[[vnější, díra1, …], …]` (RFC 7946 `coords[1:]`); **(2) rastr** `_draw_area_symbol` +
      scanline helpery (`_draw_dotted_surface_area`/`_draw_marsh_area`) — bez děr RYCHLÁ PIL cesta
      (0 regrese), s děrami even-odd scanline `_fill_rings_scanline` vyřízne výřezy; **(3) `.omap`**
      `area_object` zřetězí prsteny, hole-flag 18 (16 hole+2 close) na hranicích, **poslední prsten
      close-only (2)** — konvence ověřena proti reálným mapám (SampleMap/Blatná). DRY helper
      `_poly_to_grid_px`; 6 call-sitů + treerow/ropík obaleny na tvar list-ringů.
- [x] **Verify holes:** proc baseline 65 drží; LS reálný **35639 = čistý HEAD 35639** (behavior-preserving
      — díra je další prsten v TÉMŽE objektu, ne nový); rastr 13002 px vykrojeno přesně v zastavěné
      oblasti (RÚIAN 185 děr); `.omap` 1822 objektů s děrami, 0 chybných flagů. Verify-against-source:
      probe 115 = 1363 děr na LS (68–78 % plochy obřích polygonů).
- [x] **`Ostatní plocha v sídlech` (115) → 501.1 Paved area bez obrysu** (odemčeno děrami). `map_paved_to_isom`
      rozliší 501.1 (float); `PAVED_OUTLINE` (501 obrys / 501.1 bez), `PAVED_CLASS` třída 2. **Z-order
      dvouprůchod** `_generate_real_paved(urban_base=…)`: 501.1 base ÚPLNĚ VESPOD (před surfaces) → olivová
      520 RÚIAN parcel ji nahoře překryje (verify: 520 px 1071020=1071020, nedotčené); 501 kolejiště nahoře.
      LS 501.1 = 9 objektů, 10 % výseku (ne 41 % záplava Sez. 53). LAYER_IDS 115; USED_CODES+AREA_CODES 501.1.
- [x] **Barva „Dolní hnědá 50%" (PRŮLOM color-table).** 501.1 je první velkoplošná base výplň pod mnoha
      symboly. Rastr: nová `C_PAVED=(240,205,175)` (paleta „paved", světlejší než silnice `C_ROAD`, aby
      silnice vynikly). `.omap`: **`template_classic.omap` color-table rozšířena** — nová color „Dolní hnědá
      50%" priority 35 (úplně dole, pod silničními okraji color 14 i pěšinami color 2), symbol 501.1 (id 106)
      přepojen z color 11 (chybně sdílel Upper brown se silnicemi) → 35. Default ISOM paleta NESTAČILA. OOM
      verify uživatelem ✓. Lekce → paměť `omap-colortable-base-fill-priority`, poznámka v `omap_export.py`.
- [x] **Template foundation poznámka:** `omap_export.py` hlavička + `generator/README.md` — template je ruční
      artefakt, k výrobě nestačí prázdná OOM mapa, needitovat naslepo (jen s přesnými kroky uživatele).

## Sezení 53 (2026-05-31) — udržovaná zeleň → 402 / 402.1 (štěpení podle atributu)
- [x] **`Udržovaná zeleň` (134) → ISOM 402 / 402.1** (`--surfaces`, štěpení podle atributu `typ_pudy_k`).
      Verify-against-source probe: vrstva nese `typ_pudy_k` ∈ {`PO` „park, okrasná zahrada", `UZ` „ostatní
      udržovaná zeleň"} (LS 3 PO / 14 UZ) → čistá projekce přes atribut. Dnes celá → 401 (Sez. 41); rozštěpeno.
- [x] **402 Open land with scattered trees** (park/okrasná zahrada, `PO`) = žlutá + **bílé** tečky (template
      color 30); **402.1 …with scattered bushes** (ostatní zeleň, `UZ`) = žlutá + **zelené** tečky (color 27
      „Green 60%" ≈ C_GREEN2). Geometrie z template: tečka r 0,3 mm, grid 1,05 mm (větší/hustší než 412).
      **402.1 = první „scattered bushes" zeleň z dat — vegetace gate neporušuje** (tvrdý objekt, mirror 406).
- [x] **Render:** `_draw_dotted_surface_area` zobecněn — `SURFACE_DOT[code]` = (barva, poloměr, **rozestup**)
      per-symbol (412 zachovává chování). Min. plocha < 9 mm² → fallback 401 (izomorf 412, volba uživatele).
      `.omap`: 402/402.1 = samostatný combined area symbol z template (NErozbaluje se jako 412 = 401+412.1).
- [x] **Verify:** proc baseline **65 drží**; LS render 402:13 / 402.1:203 ringů; masky tříd 4/5; `.omap` 13+203
      objektů (id 75/76); vizuál potvrzen (bílé tečky park, zelené tečky zeleň). py_compile + mappery OK.
- [x] **Propagace:** katalog (Udržovaná_zeleň 401→402/402.1), spec §4.8, GLOSSARY, README root + generator,
      stats +402/402.1 (41→43 sledovaných), 5 lokalit regen + STATISTICS. batch off obě větve (surfaces kanál, B1 OK).
- [~] **`Ostatní plocha v sídlech` (115) → 501.1 — ZKOUŠENO, ODLOŽENO** (carry-over Sez. 51/52). Probe odhalil:
      vrstva = administrativní výplň zastavěného území (obří polygony 2371/1734/494 ha se **stovkami děr**
      571/692/578 pro budovy/zeleň/cesty). Parser bere jen vnější obrys → zalila 41 % výseku lososovou
      (verify plným renderem LS + vizuál). **Vyžaduje podporu děr (holes)** → samostatný úkol (viz TODO). Kód vrácen.

## Sezení 52 (2026-05-31) — komín → 524 + zábrana → 519 na zdi (poslední kandidáti ZABAGED)
- [x] **Komín → ISOM 524 High tower** (`--landmarks`, mirror věží/sila). `Tovární komín` (id 31) přidán do
      `LANDMARK_POINT_LAYERS_524` + LAYER_IDS; atribut `vyska_obj` nevyužit (524 nemá výškové varianty → KISS).
      Žádné render změny. Verify: SV 524 6→7 (+1 komín), LS +12.
- [x] **Zábrana → ISOM 519 Crossing point** (nová orientovaná vrstva `--barriers`). Verify-against-source PŘED
      kódem: `Zábrana` (id 54) nese jediný typ `typ_k=Z` „Závora, brána" → nelze rozlišit závoru od brány.
      ISOM 519 = průchod plotem (NE závora na cestě) → **mapuje se jen bod ležící na nosné zdi 513 (≤ 5 m)**,
      ostatní (závory na cestách) se zahodí. **Změřeno (krok 0): 2/66 na LS** leží na zdi (medián 183 m) →
      vrstva řídká, ale spravedlivě naplní skutečné průchody (volba uživatele „úplnost i za nízký výtěžek").
- [x] **`fetch_barriers`** (zabaged) = resolve bodů na zdi 513 + tangenta; **`_draw_crossing_point`** = 2 čárky
      kolmé na zeď (orientace = tangenta, S-JTSK→px transformací 2 bodů); **omap** = rotatable bodový objekt
      (mirror lávky 512.2). Brány spočteny 1× v pre-fetch (sdíleno s break).
- [x] **Přerušení zdi 513 pod brankou** (ISOM „line shall be broken at the crossing point" — verify uživatel
      v OOM). Zeď se v místě branky přeruší mezerou 1,2 mm (`_split_by_zones_interp`, mechanismus passage cropu
      tunelů); sráz 104 se neřeže; count zdí v meta beze změny (mezera ≠ nový prvek).
- [x] **Propagace + verify:** batch off obě větve (B1), stats +519 (41/41 aktivních), katalog komín+zábrana ◐→✓,
      `--barriers` v argparse + validační smyčce. Proc baseline **65 drží**, 5 lokalit regen, **OOM Test OK**
      (orientace branky + přerušení zdi). **ZABAGED katalog vyčerpán** (zábrana+komín byli poslední kandidáti).

## Sezení 51 (2026-05-31) — dokončení neuzavřeného %END Sez. 50 + %CALIBRATE (zralý +16)
- [x] **Dokončen neuzavřený `%END` Sez. 50** — `%BEGIN` fetch-first odhalil hotovou-necommitnutou práci
      (`HEAD==origin/main`, ale working tree plný refaktorů + diár Sez. 50). Dva commity (kód `refactor` +
      `docs(session) [50]`) + push. Drobná vada propagace: `DIARY.md` index pořadí `…48,50,49` → srovnáno `…48,49,50`.
- [x] **%CALIBRATE** (zralý +16 od Sez. 35, reset Sez. 51) — meta-audit spolupráce. **0 kritických.**
      Role discipline čistá (projektový `CLAUDE.md` +8 % slov od Sez. 35, hluboko pod 50 % sub-prahem; čistý
      AI overlay). Cadence vyhodnocena na datech (%AUDIT:CODE/DOCS 0 kritických → checklist Sez. 34 drží stav).
      Collaboration: historické Censure clustery vyřešené pamětmi, trend zlepšení.
- [x] **D1 — `settings.local.json` allow-list 50 → 22 patternů.** Smazány mrtvé `sandbox/` reference (zrušeno
      Sez. 39), jednorázovky (`2+2`/`ping test`/`recovered`/`exit 1`/echo `$?`), překlep `DONE.md4`, konkrétní
      awk/grep s čísly řádků, mrtvé `temp/probe` skripty, redundantní konkrétní python příkazy (pokryté wildcardy).
      JSON validní. **Gitignored (stroj-specifický)** → zůstává lokální na ntbhej21, na `mrkla` se nepropíše.
- [x] **D2 — `PROMPTS.md` `%END`** — pravidlo „indexový řádek `DIARY.md` = stručný hook (1–2 věty + ISOM kódy),
      ne kopie záznamu" (index se čte celý každý `%BEGIN` → tokenová efektivita). Aplikováno hned na řádek Sez. 51.

## Sezení 50 (2026-05-31) — %AUDIT:CODE + 2 refaktory (zabaged DRY, A1 meta) + Stale + pruning
- [x] **%AUDIT:CODE** (práh ≥8 dosažen od Sez. 41; +1175 net LOC). Přečten celý `generator.py` (3511 ř.) sám
      + 2 paralelní agenti na konektory/export (nálezy kriticky ověřeny proti zdroji — lekce Sez. 46). **0 kritických.**
      Ověřeno, že historický bug B1 (batch noise větev) **neregreduje** (obě větve vypínají všech 14 dev-map vrstev).
      Kód zdravý: izomorfismus důsledný (wrappery nad `_draw_line_symbol`/`_draw_area_symbol`), DRY transport `arcgis.py` čistý.
- [x] **Bezpečný balík oprav** (behavior-preserving): dead code (`_draw_landmark` jednoprvková smyčka `for col,mc`;
      nepoužitá `ISOM_TUNNEL`; mrtvá větev `_normalize_code` 3011→301.1) + drift komentářů (z-order docstring chyběly
      landmarks/linefeatures; `zabaged.py` modul docstring zaostalý ~9 sez; `batch.py` neúplný výčet off vrstev;
      `stats.py` „10 sekcí"→14 + docstring) + katalog (`zabaged-isom-catalog.md`: 312 Spring „ústí dolů"→nahoru ∪;
      Most/Tunel/Lávka stav ◐→✓ DOKONČENO Sez. 33).
- [x] **Stale 501/513 vyřešen** (DO/DROP, visel Sez. 44→49 = 6×). **501 obrys hnědý→ČERNÝ** (verify template:
      „Paved area, **with bounding line**" = thin **black** line; nebyl px-tuning, byla chybná barva). **513 Wall
      DROP/doloženo:** rastr plná černá = legitimní px-tuning (tečka á 3 mm zaniká), `.omap` nese věrný 513 (OOM
      vykreslí tečky) — konzistentní s render-px-tuned-vs-omap-věrný (505/508).
- [x] **Refaktor `zabaged.py` (DRY, −157 ř / 1194→1037):** 14 `fetch_*` funkcí mělo identické tělo lišící se jen
      vrstvami/parserem/klíčem → 2 helpery `_collect_features` (lines/rings) + `_collect_points` (volitelný predikát).
      Speciální (`fetch_water`/`fetch_footbridges` kombinované, `fetch_state_border`/`fetch_landmarks` filtr/centroid)
      ponechány vlastní. **Behavior-preserving:** SV meta deep-diff identické (všech 14 sekcí + 6031 omap objektů).
- [x] **A1 jádro — meta-konstrukce sjednocena (`generator.py` −123 ř / 3511→3388):** `_layer_meta_section` helper
      (jediná pravda struktury sekce, dřív zkopírováno 14×) + tabulkový `real_sections` registr → `_build_meta`
      **26→18 parametrů**, zrušena asymetrie „část vrstev v `_build_meta` / část injektovaná vně". **Behavior-preserving:**
      SV meta deep-diff identické (29 klíčů vč. symbols/classes/items), proc baseline 65 drží, stats.py OK.
      **Fyzický split souboru na moduly vědomě NEproveden** — kreslicí helpery závisí na module-level globálech
      `GW/GH/W/H` (mutované `_apply_extent`); split = přepsat globály na předávaný stav = velký refaktor proti fázi B
      (sys.path skripty, ne balík). Spouštěč splitu = přechod na balík (fáze A). TODO A1 → `[~]`.
- [x] **IDEAS/TODO pruning** (práh +14/12): IDEAS zkrácen verzní gap blok (ISOM 2000↔2017, zavřen Sez. 40) + jméno
      (vyřazené alternativy); TODO zkrácen obří katalog-changelog řádek (hotové dávky Sez. 24–49 → DONE/katalog,
      ponechán akční „zbývá zábrana 519/komín 524"). Verify: 5 lokalit přegenerováno s ortofotem (počty drží), STATISTICS.

## Sezení 49 (2026-05-30) — kultura 412 dotažena + sad/zahrada → 520 (oprava 413)
- [x] **Render-verify kultury 412 dotažen** (carry-over `[!]` Sez. 48). **Root cause „render nedoběhne" nalezen:**
      `_draw_dotted_surface_area` (nový kód Sez. 48) měl **nekonečnou smyčku** — vnější `while y <= y1` nikdy
      neinkrementovalo `y` (chybělo `y += sp`; `_draw_marsh_area` má `for range` → nezamrzl, dotted přepsaný na
      `while` inkrement vypustil). Censure Sez. 48 to mylně svedl na „2 paralelní běhy + ortofoto" = **mis-diagnostika
      symptomu, ne příčiny**. Diagnostika: CPU monotónně rostlo (123→272 s), RAM konstantní, zaseknuté mezi logem
      „terén" a „plošný pokryv". Po fixu render SV ~15 s. **Verify:** pole 412 černé tečky (C_BLACK), sad → viz níže;
      .omap 401+412.1; degradace pod min. 9 mm² OK; 5 lokalit přegenerováno.
- [x] **`Ovocný sad, zahrada` (135) → 520 olivová** (oprava chybného 413 Orchard Sez. 48; rozhodnutí uživatele).
      V ČR krajině jde převážně o zahrady u rodinných domů/chalup — oplocené, nepřístupné běžci → out-of-bounds,
      ne běhatelný ovocný sad (vizuál SV potvrdil: „sady" = zelené tečk. plochy v zástavbě). **413 Orchard úplně
      smazán** (mrtvý kód: `ISOM_ORCHARD`, `SURFACE_DOT/CLASS/FILL/MIN_AREA[413]`, omap_export, stats; grep 0 živých
      reziduí). Verify: 413 = 0 napříč 5 lokalit, sady přesunuty do 520, 412 pole beze změny, maska 3 třídy.
- [x] **Ortofoto podklad vrácen** — `--no-ortho` (rychlý verify) ho vyřadil; uživatel ho používá ke kontrole.
      5 lokalit přegenerováno s ortofotem (`ortofoto.png` + připnutý `<template>` v `.omap`, opacity 0.5).

- [x] **Sezení 48 — přesun pracovních dokumentů root → `docs/`** — `git mv` 6 souborů (TODO/DONE/DIARY/IDEAS/RESEARCH/GLOSSARY) do `docs/` (zachována historie); v rootu zůstaly jen `README.md` + `CLAUDE.md` (GitHub/harness konvence). Odkazy opraveny v živých dokumentech (README layout + Docs sekce, PROMPTS %BEGIN kontext); diáře needitovány (historie). *(Kultura pole 412 / sad 413 — kód hotov, ale plný render-verify nedokončen → zůstává `[~]` v TODO, dotáhnout Sez. 49.)*

## Sezení 48 (2026-05-30) — kultura 412/413 a přesun pracovních dokumentů do `docs/`
Detail: [diary/2026-05-30.md](diary/2026-05-30.md#sezení-48--druhá-vlna-land-cover-pole-412--sad-413-kód-hotov-verify-nedokončen--přesun-docs).
- [x] Přidána druhá vlna land-cover (pole 412, tehdy sad 413; význam sadu byl opraven
  v Sez. 49) a šest pracovních dokumentů bylo přesunuto z kořene do `docs/`.

## Sezení 46 (2026-05-30) — %AUDIT:DOCS (zralý audit dokumentace)
- [x] **%AUDIT:DOCS** (+11 sez od Sez. 34, práh 10). Přečteno 27 `.md` (fan-out 3 paralelní Explore agenti
      po oblastech, nálezy kriticky profiltrovány — část byla šum/halucinace). **0 kritických nálezů** —
      propagace Sez. 44/45 čistá (zásluha propagačního checklistu Sez. 34).
- [x] **Opraveno 5 (kosmetické/doporučené):** (1) `DIARY.md` index přeskládán do číselného pořadí (byl dle
      pořadí *psaní* přes přechody strojů ntbhej↔mrkla; skript `temp/sort_diary.py` se sanity-asserty, 0 ztrát);
      (2) spec §4.9 sekvenční číslování (ad-hoc „4.9k-bis" → l/m/n; 2 odkazy); (3) `TODO.md` redundantní inline
      poznámka 416→406; (4) `README.md` mezery kolem `+` v exports řádku; (5) kotva sezení 1 v DIARY.
- [x] **Zamítnuto (agentí šum/halucinace):** „prohlubeň→prohlubň" (prohlubeň je správně), GLOSSARY pořadí
      „form line / pomocná vrstevnice" (stylistická preference), „chybí centrální CLI tabulka" (feature request).
- [x] **Ověřeno správné:** CLI flagy (`--treerows`/`--marsh` všude), ISOM 39/39 (406 ano/416 ne), masky,
      počty stromořadí konzistentní napříč 6 docs, 416 rezidua v živých docs jen historická, DONE↔TODO konzistentní,
      terminologie (S-JTSK/ZABAGED®/desetinné čárky) jednotná, GLOSSARY wikilinks bez broken cílů.

## Sezení 45 (2026-05-30) — Stromořadí 416 → 406 „lineární les" (oprava sémantiky + nový `--treerows`)
- [x] **Sémantická oprava (carry-over [!] Sez. 43).** `Liniová vegetace` (id 15, v datech výhradně stromořadí
      `typveg_k=S`) byla Sez. 43 mapována na **416 Distinct vegetation boundary** — verify-against-source spec
      (template `id=100 code=416`) ukázal, že **416 = HRANICE mezi porosty** (kraj lesa / předěl uvnitř lesa),
      NE řada stromů. Vysvětlení uživatele: alej se mapuje buď (I) řadou bodů 417/418 (vyžaduje polohy kmenů) nebo
      (II) plošně tenkou nepravidelnou „špagetou" = lineární les (stačí osa). **Data určila II** — ZABAGED dává jen osu.
- [x] **Nový `--treerows real` → ISOM 406 Vegetation: slow running** (světle zelená `C_GREEN1`). Osa linie → buffer
      na nepravidelný pás: `_buffer_polyline_irregular` (DETERMINISTICKÁ sinusová perturbace — real nelosuje, Sez. 20),
      šířka **0,7 mm ≈ 7 m**, výplň bez obrysu (jako 401/520). **Min. plocha 1,0 mm²** (`_polygon_area_px` filtr; ISOM
      spec: nejmenší zelený dot-screen = 1,0 mm² @ 1:15000 — ověřeno v `isom-2000-spec.pdf`). Plošný objekt 406 v .omap.
- [x] **První zelená vegetační plocha generátoru** — vegetace gate NEporušuje (tvrdý objekt z dat, ne hádaná hustota;
      izomorf s 308 Marsh: KISS jedna úroveň). Z-order nad plošným pokryvem (401), pod vrstevnicemi/liniemi.
- [x] **Plná vertikální integrace** (mirror vrstev): `zabaged.py` (416 ven z `fetch_line_features`; nový `fetch_tree_rows`
      + `map_tree_row_to_isom`) + `generator.py` (konstanty/buffer/filtr/render/gen/z-order/maska/meta/CLI/validace) +
      `omap_export.py` (416 ven z USED_CODES, 406 do USED_CODES+AREA_CODES) + `stats.py` + `batch.py` (obě větve `off`, lekce B1).
- [x] **Verify:** proc baseline **65 drží** (noise nepadla); SV.omap **Test OK** (uživatel v OOM); 5 lokalit přegenerováno,
      stromořadí = bývalá 416 na kus (SV 83/HS 121/LS 47/NV 18/NL 4, nic nepropadlo min-area filtrem); .omap 0× objekt 416;
      py_compile OK. Cleanup: rezidua „416 vegetace" v komentářích/docs sjednocena na 406.

## Sezení 44 (2026-05-30) — Katalog dávka 4 (mokřady/pramen/jeskyně/nádrž) + audit věrnosti renderu
- [x] **Dávka 4 (vodní/mokřady/terén)** — verify-against-source: REST jména ověřena `?f=json` (mezery/čárky/závorky,
      ne WFS podtržítka). **`--marsh real` (nový):** `Bažina, močál` + `Rašeliniště (plocha)` → **308 Marsh** (KISS vždy
      crossable; modrá vodorovná scanline šrafa á 0,45 mm; `_draw_marsh_area`). **Do `--landmarks`:** pramen `Zdroj
      podzemních vod` → **312** (modré „U" ústím nahoru), `Vstup do jeskyně`+`Ústí šachty, štoly` → **203.2 Cave**
      (černá „Λ" stříška), `Nadzemní zásobní nádrž` (plocha→centroid) → **311** (modrý čtverec). Počty sedí na probe
      Sez. 43 na kus: pramen Σ65 / nádrž Σ8 (LS6+HS2) / jeskyně Σ9 / mokřady NV15·HS10·NL9·SV5·LS0.
- [x] **Odloženo (doloženo v katalogu):** hráz `Přehradní_hráz__jez`→528 (vyžaduje legendu mapy + sporné mapování,
      jez ≈ přerušení toku), lom `Povrchová_těžba__lom`→201 (plocha lomu ≠ hrana srázu, Σ1 marginální).
- [x] **203.2 je necelý kód → string** napříč flow (`map_landmark_to_isom` vrací `int | str`; `sorted(…, key=str)`
      proti TypeError int<str — chyceno při verify regenerací, 2 místa).
- [x] **AUDIT VĚRNOSTI RENDERU** (na žádost uživatele): porovnán template (autorita) vs `_draw_*` u ~35 symbolů.
      **Root cause:** špatná konvence OOM osy y (předpoklad +y=nahoru) → zrcadlení vertikálně asymetrických bodů.
      **Uživatel chytil:** „203.1=V, 203.2=Λ, Zkontroluj!" → konvence je **+y=DOLŮ** (NEflipovat). Opraveno: **203.2 cave**
      (Λ stříška hrot nahoru, ne plný trojúhelník hrot dolů — můj chybný „fix"), **312 spring** (∪ ústí nahoru, ne dolů),
      **104 sráz** (HNĚDÁ ne černá — template color 6 Brown; linie i ticky). **Staženo (falešný poplach):** 111 depression
      (∪) a 207 boulder cluster (▲) byly CELOU DOBU správně — málem jsem je flipnul. Paměť `omap-symbol-y-axis-down`.
- [x] **704 verify pomůcka** — na žádost uživatele injektovány ISOM 704 Control number na 5 jeskyní v SV.omap
      (post-process, ne generátor; XML validováno) → uživatel ověřil v OOM „Test OK", pak SV regenerován načisto.
- [x] **Cleanup:** smazán osiřelý `sandbox/` na stroji mrkla (untracked výstupy z doby před reorgem Sez. 39; `git pull`
      je nemohl uklidit, protože gitignored). Pravidlo `<lokalita>.omap` (Sez. 42) se propagovalo správně — mátl jen sirotek.
- [x] Verify: proc baseline **65 drží**; 5 lokalit přegenerováno (počty sedí); STATISTICS 39/39; py_compile OK.

## Sezení 43 (2026-05-29) — Systematický audit katalogu: 14 chybějících ZABAGED vrstev → ISOM
- [x] **Root cause domova mládeže (verify-against-source).** Akutní nález uživatele: budova domova mládeže
      (SV/Krompach) chybí. Probe → ČÚZK vede **zámek** ve VLASTNÍ vrstvě `Zámek` (id 102), netáhli jsme ji (jen
      `Budova_..._plocha_` 99); domov mládeže = bývalý zámek. Probe historických staveb na SV odhalil i **8 zřícenin
      (Milštejn)**, 1 věžovitou stavbu, 5 věží.
- [x] **Censure! potřetí → data-driven audit celého katalogu.** Opakovaný antipattern „chybí X → to nemapujeme"
      (parkoviště 41/areály 42/zámek 43). Lék: **probe VŠECH 149 vrstev × 5 DEV_LOCATIONS** (`returnCountOnly`,
      `temp/probe_all_layers.py`) → výskyt rozhoduje, ne odhad. Nalezeno 14 netáhnutých vrstev s ISOM ekvivalentem
      + chyby konzistence (tramvaj táhnu od Sez. 31 ale řádek ✗; areál duplikát). Paměť `geoportal-data-completeness`.
- [x] **Dávka 1 — budovové stavby** (do `--buildings`, žádný nový flag): `Zámek`/`Hrad` → 521 (mirror budov);
      `Rozvalina, zřícenina` → **523 Ruin** (čárkovaný obrys bez výplně, 2. třída mask_buildings, mirror skály).
      Oprava bugu: omap export hardcodoval „521" → zřícenina by vypadla jako budova.
- [x] **Dávka 2 — bodové orient. prvky** (nový `--landmarks`, `mask_landmarks` multi-class): kříž → **530** ring,
      mohyla → **526** cairn, věž/věžovitá stavba/vodojem/silo/těžní/mlýn/motor → **524** (kříž+tečka), strom →
      **417** (zelený kroužek, `C_GREEN3`). Nulové vrstvy mapovány pro úplnost. Mirror `--rocks`.
- [x] **Dávka 3 — liniové orient. prvky** (nový `--linefeatures`, `mask_linefeatures` multi-class): sráz →
      **104 Earth bank** (plná + jednostranné ticky; Σ981 = nejčastější dosud netáhnutá), zeď/hradba → **513 Wall**,
      liniová vegetace → **416** (zelená čárkovaná; ⚠ POZDĚJI OPRAVENO Sez. 45 → 406 lineární les — 416 byla špatně).
      Mirror `--powerlines`/`--rides`.
- [x] **Kótovaný bod — SKIP doložený.** Nese jen `vyska` (virtuální výškopis, ne fyzická značka v krajině) →
      ne ISOM 603 (volba uživatele „virtuální → okomentovat skip"). Doloženo v katalogu.
- [x] **Katalog kompletně zrevidován.** 14 vrstev ◐/○→✓, konzistence (tramvaj/areál duplikát), nulové doloženy
      „0 v 5 výsecích", ✓ count ~27→~40, data-driven probe poznámka. SSoT „nic užitečného nevypadne".
- [x] **Verify:** proc baseline 65 drží (behavior-preserving), py_compile OK, 5 lokalit regen (počty sedí na probe:
      SV orient. 81 + liniové 170; budovy +zámek+8 zřícenin; LS 9131), STATISTICS +8 symbolů, vizuál SV (domov
      mládeže = zámek se kreslí). batch.py OBĚ větve nové vrstvy off (lekce B1).

## Sezení 42 (2026-05-29) — Olivová 520 z katastru (RÚIAN) + areály účelové zástavby + audit land-cover
- [x] **%THINK olivová 520 + probe RÚIAN** (verify-against-source, foundations před kódem). Nápad uživatele:
      olivovou (zákaz vstupu) volí mapař na soukromé pozemky u domů → vzít z katastru parcely se stavbou.
      Probe: **RÚIAN** běží na témže ČÚZK ArcGIS serveru, vrstva 5 `Parcela` má `druhpozemkukod` (codedValue
      doména ze serveru), `f=geojson` (izomorfní se ZABAGED), maxRec 1 000 000. **Pravidlo: druh ∈ {5 zahrada,
      13 zastavěná plocha a nádvoří} → 520**. Licence: veřejná open data zák. 111/2009 Sb. SV: 649+1212 parcel.
- [x] **Olivová 520 z RÚIAN** (nový konektor `ruian.py`, sourozenec). `fetch_private_land` (`where druhpozemkukod
      IN (5,13)`) + `map_private_land_to_isom`→520. Třetí zdroj do `_generate_real_surfaces` (z-order: olivová NAD
      žlutou → zahrada přemaže žlutý sad). 520 už plně zapojená (Sez. 41) → žádná změna draw/mask/omap/meta, jen víc
      prvků. `ISOM_CEMETERY`→`ISOM_OUT_OF_BOUNDS` (propsáno všude, 0 reziduí). Verify LS: centrum města souvisle
      olivové s žlutými parky (test uživatele „střed Liberce olivový s výjimkou parků" ✓).
- [x] **DRY refaktor — `arcgis.py`** (volba uživatele DRY > duplikace). Zobecněn `zabaged._fetch_layer` + geom
      parsery → sdílený `fetch_geojson_layer(server, layer_id, …)` + `geom_to_*` (cache-key zachován → cache se
      neinvalidovala). `zabaged.py` i `ruian.py` ho sdílí (precedent `dmr.build_bbox`). Behavior-preserving.
- [x] **Test LS → 4 nálezy opraveny + audit land-cover.** (1) **Jméno mapy** `map.omap`→`<lokalita>.omap`
      (`out.name`, orphany smazány). (2+3+4) Systematický audit **47 plošných ZABAGED vrstev** vs mapováno odhalil
      klíčovou mezeru **114 Areál účelové zástavby** (177 na LS) — řeší bílá hřiště/školy/kasárna (`typzast_k` 62
      typů): asfalt (408 autobus. nádraží/409 čerpačka) → **501**, vše ostatní → **520** olivová. Rozdělení 114 dle
      ISOM kódu mezi surfaces (520) a paved (501) kanál. Plus **105 kůlny/přístřešky → 521** (LS budovy 8273→9123).
      Audit: 151 GIA (overlay vlastnictví) + 4 (CHKO) = skip; vegetace 140/142/144 = vědomě bílá (gate); drobné
      mezery (115 ostatní plocha, zřícenina, zámek, tribuna…) → katalog/TODO.
- [x] **Verify** — `py_compile` celý balík OK; **proc baseline 65 drží**; refaktor behavior-preserving (SV 269 ploch);
      5 lokalit přegenerováno (pokryv SV 2140 / NL 174 / LS 20159 / HS 2268 / NV 603; LS areály 170 olivová + 7 asfalt,
      kůlny +850); STATISTICS regen; vizuál OK (SV zahrady u domů, LS centrum olivové). Korekce uživatele: ISOM barvy
      jsou normované (z palety), neladí se okem (paměť `isom-colors-from-palette-not-eye`).

## Sezení 41 (2026-05-29) — %AUDIT:CODE + plošný pokryv (surfaces): mapa dostala barvy
- [x] **%AUDIT:CODE** (LOC práh, 4981 ř. tracked). Kód zdravý, 0 kritických; dominanta = drift komentářů po
      refaktorech (paměť `slap-symbol-rewrite-comments`). Opraveno: **D1** crt název `ISOM2000-ISOM 2017-2.crt`
      (s mezerou) → bez mezery — **oprava Sez. 40 byla NEúplná** (mezera přežila v `generator.py:1019`, **template
      `<notes>`** propisované do každého `map.omap`, GLOSSARY, IDEAS); **D2** docstring `_draw_footbridge` 625/250→
      937/375 µm (zaostal za Sez. 35); **D3** „hybridní 202/206" reziduum v `zabaged.py` ×2 (zavrženo Sez. 30);
      **K1** stats „8 sekcí"→9; **K2** `_nearest_segment_tangent` → wrapper nad `_nearest_seg` (DRY, −18 ř.);
      **K3** GLOSSARY výčet os. A1 monolit nepovýšen (čitelný, „až bolí").
- [x] **Plošný pokryv `--surfaces real`** (Sez. 41, „konečně barvy"). %THINK → probe (verify-against-source):
      kompletní land-cover inventář ZABAGED + render struktura z template (plná výplň = tutovka, pattern = práce).
      **Volba uživatele „open land jako jedna žlutá":** louka/park/pole/sad (139/134/138/135) → ISOM **401** plná
      žlutá (`C_YELLOW` konečně ožila); hřbitov (116) → **520** olivová out-of-bounds (`C_OLIVE` nová, aproximace);
      parkoviště (123) → **501** přes `--paved` (DRY). ISOM-věrné pole 412 / sad 413 (pattern) = vědomá druhá vlna.
      Izomorfní s vodní plochou/budovou: `fetch_open_land`/`fetch_cemeteries`, `map_*_to_isom`, `_generate_real_surfaces`,
      `_draw_surface_area` (outline=None), multi-class `mask_surfaces.png` (1=open, 2=hřbitov), omap area 401/520,
      meta injekce (mimo `_build_meta` — A1, precedent Sez. 37/38). **Z-order ÚPLNĚ VESPOD** (podklad pod vrstevnicemi;
      les = bílá default = vegetace gate). `batch.py` surfaces="off" obě větve (lekce B1 Sez. 35).
- [x] **Verify** — `py_compile` OK; **proc baseline 65 drží** (regrese); 5 lokalit přegenerováno (pokryv SV 269 /
      NL 34 / LS 1105 / HS 365 / NV 103, sedí na probe); STATISTICS regen; vizuál OK (žlutá vespod, z-order sedí).
      **`compare_real_vs_gen` SV: otevřený prostor gen 0 % → 35.8 %** (real 34.7 %) — zaplnil recall mezeru Sez. 37;
      precision/recall ~55 % (projekce ≠ ruční generalizace kartografa). Zelená (hustník) zůstává 0 % = vegetace gate (UC5).

## Sezení 40 (2026-05-29) — Kapitalizace DEV_LOCATIONS + %THINK ISOM 2000↔2017-2 (verzní gap zavřen)
- [x] **Kapitalizace `DEV_LOCATIONS` sjednocena** (carry-over Sez. 39). Verify odhalil, že to nebyl plošný
      chaos, ale **jediný překlep**: `Soví Vrch` → `Soví vrch` (vrch = terénní útvar → druhé slovo malé dle
      českého pravopisu; ostatní — `Nová Louka`/`Lidové sady`/`Hrubá Skála` — jsou sídla/čtvrti/obce → správně).
      Opraveno ve 3 SSoT: `generator.py DEV_LOCATIONS`, `stats.py LOCATIONS`, `compare_real_vs_gen.py` (+ zrušen
      3řádkový komentář o nesouladu — nesoulad zmizel). `resources/` názvy ponechány (vnější daná jména).
      **Vedlejší užitek:** `maps/Soví vrch` == `resources/Soví vrch` → `compare` funguje bez kapitalizačního hacku.
- [x] **Verify** — `py_compile` 3 soubory OK; SV přegenerováno (počty sedí: budovy 1078 / řopíky 70 / průseky 46 /
      vrstevnice 462 / skály 253 / `.omap` 3502); složka na disku je `Soví vrch` (lowercase, NTFS case fix přes
      smazání staré `Soví Vrch/`); `compare` najde obě složky přirozeně; STATISTICS regen; render pixelově nezměněn.
- [x] **%THINK „vizuál vs čísla" ISOM 2000↔2017-2 → verzní domain gap ZAVŘEN** (uzavírá pravou otázku Sez. 38/39).
      Destilát: otázka se rozpadá na 2 osy dle cesty — **vektor** (symbol ID → číslo, crosswalk `.crt` řeší 1:1)
      vs **rastr** (pixely → vzhled, čísla irelevantní; = co čte UC5). Pro UC5 relevantní JEN vizuál. **Vizuální
      sonda** (jednorázový georef warp: reálná ISOM 2000 Soví vrch × náš 2017-2 render téže oblasti, grid-north,
      shodné měřítko, montáž vedle sebe) → **kartograf: „vše důležité v obou setech, snadno transformovatelné"**
      — verzní rozdíl vzhledu není podstatný (`101/102/103` = identické číslo = identická hnědá kostra). Dominantní
      rozdíl je **obsahový** (chybí vegetace žlutá/zelená = recall gap Sez. 37), NE verzní. **Rozhodnuto: zůstat
      2017-2 + deklarace verze (Sez. 38) + crosswalk pro vektor; NEgenerovat zvlášť 2000 variantu.** Propsáno do
      KB `isom-issprom.md` + IDEAS (→ DONE). Otevřený zůstává jen obsahový (vegetační) gap = UC5, jiná osa.
- [x] **Drobné docs opravy** — drift názvu crosswalku `ISOM2000-ISOM 2017-2.crt` (s mezerou) → `ISOM2000-ISOM2017-2.crt`
      (skutečný soubor bez mezery) v KB. **A1 monolit `generator.py`: DROP z „Příště"** (Stale check ≥5 sez) — vědomě
      odložený trigger „až bolí", zůstává TODO položkou, ne carry-over.

## Sezení 39 (2026-05-29) — Reorganizace kořene: sandbox → generator/ + maps/ + rename generate_map
- [x] **`sandbox/` zrušen → `generator/` (pilíř).** `git mv` 9 souborů `sandbox/generator-poc/` → `generator/`
      (historie zachována, status `R`/`RM`); `sandbox/README.md` smazán; fyzicky odstraněn zbytek (`.venv`/
      cache/výstupy = gitignored). Generátor (2600+ LOC / 24 vrstev) = dávno ne „PoC". Izomorfní s `connectors/`.
- [x] **Rename `synthesize_pseudorealistic_map()` → `generate_map()`** (reverz Sez. 23/25). Důvod původního
      přejmenování ověřen jako padlý (`stale-todo-verify-rationale`): jediný vstup pro OBĚ větve (real i noise
      přes `terrain=`) → „pseudorealistic" v názvu nepřesné; noise „na zánik" → kolize `generate`↔`procedural`
      teoretická. `out_dir` default `"output"`→`None` (→ `maps/output`). „Pseudorealistická" zůstává vlastností
      VÝSTUPU (GLOSSARY „Pseudorealistic map"), ne názvem funkce.
- [x] **Výstupy → `maps/<lokalita>/` kotvené v kořeni LAB** (přes `__file__`, ne cwd; default i pro noise).
      `_REPO_ROOT` jako SSoT umístění repa (DRY: connectors/asset/maps); `MAPS_DIR` v generator.py + batch.py +
      stats.py; cesty opraveny o úroveň výš (`parent.parent.parent`→`.parent.parent`, `parents[2]`→`[1]`).
      Izomorfní: `resources/` (reálné mapy dovnitř) ↔ `maps/` (generované ven).
- [x] **`.gitignore` zjednodušen** — ~18 ř. (per-lokalita výčet + `sandbox/**`) → jediné `maps/` + DRY cache
      (bez leading-slash matchuje `connectors/.X_cache`). **`.venv` do kořene LAB** (sdílený generator+connectors,
      Python 3.12; opraven rozpor README „venv v kořeni" vs realita).
- [x] **Docs propagace** — 14 živých `.md` (README ×6, architecture, CLAUDE, PROMPTS, connectors/README, 4× kb,
      TODO, RESEARCH, IDEAS, GLOSSARY) + sloučený `generator/README.md` (zrušen PoC framing). Diáře/DONE ponechány
      (historie). Rezidua jmen v komentářích/docstringu propsána (`slap-symbol-rewrite-comments`, grep = 0).
- [x] **Verify** — proc baseline **65 objektů drží** (souhrnný log); 6 modulů `py_compile` + batch import OK;
      5 lokalit přegenerováno do `maps/` (počty sedí na historii); STATISTICS.md regen z `maps/`; SV render
      pixelově nezměněn. **Nález:** kapitalizace `DEV_LOCATIONS` (Title-Case výstup vs lowercase `resources/`) —
      chybná „oprava" v compare vrácena (Censure, `verify-data-not-assume`); → TODO Příště konkrétně.

## Sezení 38 (2026-05-29) — %THINK ISOM 2000↔2017-2 → deklarace verze ve výstupu
- [x] **Deklarace ISOM verze v každém výstupu** (ochrana proti záměně 2000↔2017-2). `generator.py`:
      helper `_isom_meta()` (izomorfní s `_georef_meta`, injektován mimo `_build_meta` kvůli A1) →
      `meta["isom"] = {version:"2017-2", scale:10000, symbol_set}`. `template_classic.omap` `<notes>`:
      deklarace verze + **varování před číselným konfliktem** (521=Building ne High stone wall; Narrow
      ride 509→508; Railway 515→509) + odkaz na crosswalk `.crt` → **dědí se do každého `.omap`**.
- [x] **Template NEvyměněn za cizí soubor — verify dokázal, že nemá smysl.** Náš `template_classic.omap`
      je **100% geometricky identický s oficiálním OOM ISOM 2017-2 (1:10000) setem** (všechny `line_width`
      sedí; stažený 15000 set lišil ×1,5 = jen měřítko). Výměna by rozbila injekci objektů/ortofota
      (`<objects count="0">` cizí formát) + zmenšila symboly 1,5×. Lekce „měň jen s důkazem" (CLAUDE.md).
- [x] **Reference do KB** (CLAUDE.md: KB nese licenci): `docs/kb/ISOM2000-ISOM 2017-2.crt` (autoritativní
      crosswalk, GPL, OpenOrienteering/Kai Pastor) + `docs/kb/isom-2000-spec.pdf` (IOF, withdrawn; archiv
      ELTE). Crosswalk **nezávisle potvrdil** ruční crosswalk ze spec (3 jisté páry: Building 521↔526,
      Narrow ride 508↔509, Railway 509↔515).
- [x] **%THINK destilát + korekce Sez. 37.** Jediný tvrdý diskriminátor verze = `526` Building (v 2017-2
      neexistuje); `521`/`112`/`113` se recyklují s jiným významem → Sez. 37 marker byl kontaminovaný.
      Empirie použitých objektů: **4/6 reálných map v `resources/` = ISOM 2000.** Pravá otevřená osa
      (Sez. 39): liší se verze i VIZUÁLNĚ (render), nebo jen čísly (→ crosswalk stačí)?
- [x] **Verify:** proc baseline 65 drží (aditivní změna); `isom` blok 2017-2/10000 ve všech 5 lokalitách
      i v noise; 5 lokalit přegenerováno (počty drží: SV 46/NL 119/LS 20/HS 16/NV 44 průseků). Vizuál
      záměrně beze změny (deklarace textová).

## Sezení 37 (2026-05-29) — Georef výstupu (rgb.pgw + meta) + strojové porovnání s živou mapou
- [x] **Emit `rgb.pgw` + georef do `meta.json`** (enabler). `generator.py`: 3 helpery u `_write_contours_geojson`
      — `_world_file_coeffs` (pixel→S-JTSK = čistý scale+translate → rotační členy 0, +0,5 px na střed UL pixelu),
      `_write_world_file` (6 řádků, jen reálný terén), `_georef_meta` (real → S-JTSK bbox+pixel_size+world_file+
      `north:"grid"`+`grivation_deg:null`; noise → `local_m`). Georef injektován do volajícího, NE přes `_build_meta`
      (26 parametrů, A1 — nezhoršovat). Verify: `.pgw` ručně ověřen (C=xmin+½A, F=ymax+½E, B=D=0); proc 65 drží;
      všech 5 lokalit přegenerováno (mají `.pgw`).
- [x] **`compare_real_vs_gen.py`** (probe, strojové porovnání gen ↔ živá mapa, zatím Soví vrch). STAT 1 sémantický
      crosswalk + pokrytí, STAT 2 prostorová shoda po ISOM barvách (forward-map + tol). 2 bugy chyceny vlastním
      verify: int16 overflow v klasifikaci barev + ztráta tenkých linií nearest-vzorkováním → forward-mapování.
- [x] **Headline nález: ISOM 2000 (reálná SV) vs ISOM 2017-2 (gen)** — naivní kód-na-kód selhává (526=budova vs 521;
      508=nevýrazná pěšina vs náš průsek; 509=průsek vs naše železnice; 112/113/115 vs 109/110/111). 9/11 schopností
      gen má sémantický protějšek. Mezery: vegetace 262 obj / 70 ha (UC5), skály/srázy 142, ploty 31, bodové umělé 22.
- [x] **Verify-against-source: grivace** — world-file rotace reálných map = grivace, ověřeno proti `.omap` `grivation`
      na desetinu ° (SV 11,4 / Blatná 11,9 / Slovanka 3,75 = UTM u poledníku). **Závěr: co umíme z tvrdých dat,
      umisťujeme správně** (vrstevnice precision 84 % / recall 66 %; voda/černá placement 71-81 %) **a nevymýšlíme si.**
- [x] **Nález:** `GLOSSARY.md` existuje (root), Sez. 36 hlásilo chybu kvůli kontrole špatného path (`docs/`).

## Sezení 36 (2026-05-29) — Lesní průseky (ISOM 508 Narrow ride) ze ZABAGED
- [x] **Lesní průseky `--rides real` → ISOM 508 Narrow ride.** ZABAGED `Lesní průsek` (id 16, REST jméno
      s MEZEROU jako tramvaj/lávka), liniová, izomorfní s railways/powerlines. KISS vždy 508 (bez
      kategoriálního atributu — verify SV 46 prvků). Render černá čárkovaná dash 3,0/break 0,375 mm
      (dlouhé čárky, odliší od pěšiny 505). **Runnability pozadí NEKRESLENO** (vegetace = UC5 predikce
      ne data, ISOM „without background" varianta).
- [x] **Foundations před kódem** (verify-against-source): spec 508 z template id 115 + probe layer ID/atributy
      PŘED implementací (paměti `isom-spec-before-render`, `geometric-selfcheck-before-oom`) → 0 slepých iterací.
- [x] **Implementace** (mirror railways): `zabaged.fetch_forest_rides`/`map_ride_to_isom`, generator
      `_draw_ride`/`_generate_real_rides`/`--rides`/`mask_rides.png`/meta sekce, omap liniový kanál 508,
      stats 508, `batch.py` off obě větve (lekce B1 Sez. 35 — call-sites).
- [x] **Verify:** proc baseline 65 drží, průseky SV 46/NL 119/LS 20/HS 16/NV 44, vizuál čárkovaná 508 OK,
      všech 5 lokalit přegenerováno + STATISTICS.
- [x] **Propagace:** architecture UC2, spec §4.9i, katalog ◐→✓, oba sub-READMEs, hlavní README status
      (dorovnán k dnešku — chyběly i skály 30 + mosty 31-33). Nález: `GLOSSARY.md` v repu chybí (ač v checklistu).

## Sezení 35 (2026-05-28) — %AUDIT:CODE (LOC práh) + sjednocení rastru mostů/tunelů s .omap + fix batch noise
- [x] **%AUDIT:CODE** (LOC práh ≥500 překročen 3,5× = net +1756 LOC od Sez. 27). Přečteny sám
      generator/omap_export/stats/batch/palette + 3 konektory; kód zdravý, dominanta = drift komentářů.
- [x] **D1 — drift symbolu 202** (zavržená hybridní 202/206 logika popsaná jako aktivní na 5 místech
      `generator.py` vč. CLI helpu) smazán; `map_rock_area_to_isom` vrací vždy 206 (KISS).
- [x] **D2+K3 — rastr mostů/tunelů sjednocen s `.omap`.** Verify-against-source PŘED kódem (geometrie
      symbolu 512 z `template_classic.omap` id=125 + demo `Most.png`): `_draw_bridge` = 2 paralely
      (`_offset_polyline_px` ±0,75 mm) + nožičky `_draw_bridge_leg` (450 µm podél osy ven + 654 µm kolmo
      ven → `[ ]`); `_draw_tunnel` = portály `TUNNEL_PORTAL_HALF` 0,75 mm (přestal půjčovat `FOOTBRIDGE_*`).
      Konstanty na template: baseline 180→270 µm, lávka 625/250→937/375 µm. Smazán `_draw_bridge_brackets`
      + `BRIDGE_BRACKET_*` (Sez. 32 interpretace 60°, vyvrácená Most.omap demem).
- [x] **D3 — DRY:** 9× duplikovaný validační blok `real ⇒ terrain real` → smyčka (27→13 ř.).
- [x] **D4/D5 — zastaralé docstringy/komentáře:** `zabaged.py` modul (cesty→11 vrstev), `omap_export.py`
      výčet symbolů, z-order v `synthesize_pseudorealistic_map`, „Most vynechán" v `PATH_LAYERS`.
- [x] **K1/K2 — kosmetika:** zhuštěn chaotický komentář `_draw_boulder_cluster`; název 306 sjednocen
      na ISOM „Minor seasonal water channel" (`generator` + `stats`).
- [x] **B1 (kritické) — fix `batch.py --terrain noise` crash.** Noise i real větev nepředávaly
      `rocks=`/`bridges=` (default `real`) → noise padala na validaci, real je zbytečně stahovala.
      Doplněno `rocks="off", bridges="off"` do obou + komentář. Pre-existující (Sez. 30/32 nepropsáno).
- [x] **Verify:** syntax OK ×5, proc baseline 65 drží, most vizuálně OK (Novina výřez), všech 5 lokalit
      přegenerováno + STATISTICS (jen 306 název + časy, počty drží). A1 monolit (2623 ř.) = úvaha, neřešeno.

## Sezení 34 (2026-05-28) — `%AUDIT:DOCS` + pruning + `%CALIBRATE`
Detail: [diary/2026-05-28.md](diary/2026-05-28.md#sezení-34--tři-audity-najednou-auditdocs--ideastodo-pruning--calibrate).
- [x] Opraven WFS→REST drift a chybějící propagace vrstev, prořezány dozrálé IDEAS a
  `%END` dostal propagační checklist napříč vrstvami dokumentace a call-sites.

## Sezení 33 (2026-05-28) — Mosty/tunely DOKONČENY (OOM verify na NTBHEJ21) + out_dir do adresářů
- [x] **Nožičky 512 mostu — orientace ven** (Sez. 32 7. iter byla obráceně, neověřená). Diagnóza měřením
      `Most.omap` dema (ne hádáním): demo má levá strana osy reversed / pravá forward, kód zrcadlově →
      nožičky dovnitř. Symbol 125 v demu == template (identický). Fix: offset paralel na **pravou normálu**
      (záporný `BRIDGE_PARALLEL_OFFSET_UM`). Self-check relace == demo.
- [x] **Buffer crop pod mostem** (uživatel „cutnout linie 0,5 mm za závorkami"). Měření demu: cut endpointy
      perp ≈ 1250 µm = 0,75 (paralela) + 0,5. Nahradil křehkou crossing strategii (`>2 průsečíky → ignore`
      selhával na ZABAGED noise) **buffer pásem ±1,25 mm KOLMO od osy** + **úhlový filtr** (∥ osa < 25° =
      nesená trať nahoře → necropovat). Interpolovaný okraj (`_split_by_zones_interp`). Voda 130→145, cesty
      486→499 (dělení), železnice 5 (nesená ∥ ✓).
- [x] **Tunel = 512 otočené o 90°** (uživatel: tunel ≠ paralely; 512 zobrazují vjezdy). Oddělen emit:
      most = 2 paralely podél osy; **tunel = 2 krátké 512 KOLMÉ na obou koncích** (`_tunnel_portals`, 1,5 mm).
      Ortofoto verify: vjezdy na správných místech.
- [x] **Passage crop tunelu — fix 4 mm → 0,5 mm.** Dřív snap na nejbližší vrchol trati (řídké body).
      Fix: vjezdy se **projektují přesně na trať** (`_project_to_line`) + interp okraj. Self-check: konce
      železnice 499–500 µm od vjezdů.
- [x] **`--location` → výstup do složky lokality.** Názvy složek byly 2× (ASCII `DEV_LOCATIONS` / diakritika
      `stats.py`) → sjednoceno na diakritickou verzi (SSoT shoda obou). Orphany `output/` + `Hruboskalsko/` smazány.
- [x] **Úklid + DRY.** Smazány dead `_segment_intersection_pt`, `_crop_line_at_cutters`, `_apply_cut_zones`;
      vytaženy `_split_by_zones_interp`/`_emit_512_line`/`_point_on_line_px`/`_interp_grid_at`/`_project_to_line`.
      proc 65 drží; všech 5 lokalit přegenerováno do adresářů + STATISTICS 24/24.

## Sezení 32 (2026-05-28) — iterace mostů, tunelů a lávek
Detail: [diary/2026-05-28.md](diary/2026-05-28.md#souhrn-sez-32--kompletní-průběh-přesun-mrkla--ntbhej21).
- [x] Po rollbacku proběhlo sedm iterací geometrie mostů/tunelů/lávek podle uživatelského
  dema, fotografie a OOM šablony; finální OOM verify následoval v Sez. 33.

## Sezení 31 (2026-05-28) — Mosty 512 + Lávky 512.2 + oprava tramvaje 509 + DEV_LOCATIONS refaktor
- [x] **Mosty `--bridges real`** (`Most` id=73 → ISOM 512, linie+V-křídla; render = středová linie 0,18 mm
      + 4 šikmá křídla na koncích symetricky ke 35° vůči ose, template autoritativní). Probe Novina
      ukázal `jmeno 2/4` = Novinský viadukt 199 m + Malý viadukt 143 m (oba kamenné železniční,
      `material_p='neznámý'` — ZABAGED nedělí kámen separátně, ISOM stejně nerozlišuje).
- [x] **Lávky `Lávka (linie)` (67) + `Lávka (bod)` (66) → ISOM 512.2 Footbridge** (bodový symbol s
      rotací kolmo k nejbližšímu vodnímu toku — paralela řopíku→hranici). Pro liniovou lávku se
      bere střed osy (MVP, drobnost TODO). V .omap rotation v radiánech (template signatura).
      **Nález:** Lávka má v REST jméno **s mezerou a závorkou** (`Lávka (linie)`), NE WFS escape
      `Lávka__linie_` jak v katalogu Sez. 23 — ČÚZK ZABAGED má 2 konvence názvů (verify `?f=json`
      před doplněním do `LAYER_IDS`).
- [x] **Tramvaj `Tramvajová dráha` (71) → 509** (oprava Sez. 28: vynechána „jako urbánní", chyběla
      točna Lidové sady). Probe LS: 25 LineString prvků, atributy chudé → KISS, vše → 509. Doplněno
      do `RAILWAY_LAYERS`. Lekce: „urbánní" není kritérium, když ISOM nerozlišuje (jeden symbol).
- [x] **Refaktor `DEV_LOCATIONS` na per-lokalita rozměr** (5-tuple: label, lat, lon, w_km, h_km):
      `DEV_W_KM`/`DEV_H_KM` zrušeno. Existující 4 lokality zůstávají landscape 6×4 km (kanonika
      stable). Přidáno **NV `Novina` 50.7598686, 14.9601922, 3×5 km PORTRAIT** (5. lokalita, kamenné
      železniční viadukty). HS `Hrubá Skála` změněna z landscape 6×4 na **SQUARE 5×5 km** centrovaný
      na **50.5481, 15.1762** = midpoint Kacanovy ↔ Doubravice (Doubravice = část obce Hrubá Skála,
      verify-against-source: Wikipedia uvádí 8 částí obce).
- [x] **Implementace**: `connectors/zabaged.py` (`fetch_bridges`/`fetch_footbridges` + `map_bridge_to_isom`/
      `map_footbridge_to_isom`); `generator.py` ISOM konstanty 512/5122 + `_draw_bridge` (V-křídla)/
      `_draw_footbridge_point` + `_nearest_segment_tangent` (helper rotace) + `_generate_real_bridges`
      + CLI `--bridges` + meta sekce `bridges` + `mask_bridges.png` 2-class; `omap_export.py` USED_CODES
      += 512/512.2, `ROTATABLE_CODES` += 512.2, `bridge_features`/`footbridge_features` parametry.
- [x] **Verify**: proc baseline **65 drží** přesně. NV (3×5 km portrait) **22 mostů** (Bridge:17,
      Footbridge:5, vč. Novinský + Malý viadukt). HS (5×5 km square) **639 skal** (459× plné 206!),
      13 mostů. LS (6×4 km) **40 železnic** (15 trat+vleček + 25 tramvaj nová), 76 mostů.
      Kanonika `Novina/`, `Hrubá Skála/` (square), `Lidové sady/` (tramvaj) regenerována v plné variantě.

## Sezení 30 (2026-05-28) — Skály/balvany (ISOM 204/207/206) ze ZABAGED
- [x] **Skály/balvany `--rocks real`** (real-půlka, 3 ZABAGED vrstvy → 3 ISOM symboly, KISS „vrstva =
      jeden symbol" jako budovy→521 / vedení→510). Verify-against-source `temp/probe_rocks.py` na Hrubé
      Skále PŘED kódem: `Osamělý_balvan__skála__skalní_suk` (bod, 6) → **204 Boulder**;
      `Skupina_balvanů__bod_` (bod, 168) → **207 Boulder cluster**; `Skalní_útvary` (plocha, 411) →
      **206 Gigantic boulder**. Žádná vrstva nenese typ/velikost/výšku (jen `jmeno`) → per-feature
      rozhodování by nemělo datový podklad.
- [x] **Hybridní 202/206 ZAVRŽEN + Chaikin smoothing ZAVRŽEN** (drift po stěně argumentů, 2 otočky
      uživatele): (1) `Shape_Area` ukázala ~120 vrcholů / 32×32 m → polygony „už pěkné" → Chaikin smazán
      (RAW jako voda/budovy); (2) práh 500 m² pro 202↔206 byl hádaný (žádný atribut ho neopodstatnil) →
      vše → 206 plná plocha. Smazány `_chaikin_smooth`, `ISOM_CLIFF_PASSABLE`, `_draw_cliff_line`,
      `_polygon_area_sjtsk`; 202 z `USED_CODES`. Potvrzení lekce „generalizuj jen s důkazem" (Sez. 27).
- [x] **Implementace**: `connectors/zabaged.py` (`LAYER_IDS` +10/12/130, `BOULDER_LAYERS`/
      `BOULDER_CLUSTER_LAYERS`/`ROCK_AREA_LAYERS`, `fetch_boulders`/`fetch_boulder_clusters`/
      `fetch_rock_areas`, `map_*_to_isom`→204/207/206); `generator.py` (ISOM 204/206/207, `_draw_boulder`
      kruh 0,4 mm / `_draw_boulder_cluster` trojúhelník 0,8×0,7 mm / `_draw_gigantic_boulder` wrapper
      `_draw_area_symbol`, `_generate_real_rocks`, `mask_rocks.png` 3-class, `--rocks {off,real}`, z-order
      úplně navrch); `omap_export.py` (`USED_CODES` +204/206/207, `AREA_CODES` +206, `rock_point_features`/
      `rock_area_features`).
- [x] **Verify (ve `.venv`):** Hrubá Skála 5,9×4 km **585 skal** (204:6 / 207:168 / 206:411, sedí na probe
      přesně; pískovcové věže dominují); NL 6×4 km **200 skal** (204:16 / 207:178 / 206:6). proc baseline
      nedotčen (rocks jen real). Branžový precedent: Karttapullautin (bod→204/205, plocha→206, plná výplň).
- [x] **Post-script (3 cleanup commity):** `HS` doplněn do `DEV_LOCATIONS` (`--location HS`); regen do
      CZ-named složek (`output_X/` špatná konvence, smazáno); **Censure! `--no-ortho`** smazal ortofoto
      podklady kanonik → regen v plné variantě. Pravidlo → paměť: **kanonické DEV_LOCATIONS = vždy plný
      režim, nikdy `--no-ortho`**.

## Sezení 29 (2026-05-28) — Pomocné vrstevnice (form lines, ISOM 103) z DMR
- [x] **ISOM 103 = Form line** (verify-against-source, ne hádání): uživatel zmínil „103", ověřeno v
      `template_classic.omap` — 103 = **Form line** (pomocná vrstevnice), NE slope line (ta je 101.1 / 103.1).
      Není to ZABAGED vrstva — **derivace z DMR výškopisu** (týž zdroj jako vrstevnice 101/102).
- [x] **Heuristika (návrh uživatele A1+A2):** form line jen kde **(1) mírný svah** (rozestup vrstevnic >
      `FORMLINE_SPACING_LIMIT_M`=40 m ⟺ sklon < `CONTOUR_STEP/limit`) **A (2) zakřivený terén**
      (`|Laplacián výšky| > FORMLINE_CURV_MIN`=0,004) — na rovnoměrném (lineárním) svahu Laplacián ≈ 0 →
      form line by jen kopírovala vrstevnici (ISOM zakazuje „intermediate contours"). `elev` 3× vyhlazen
      (3×3 box) před derivacemi — tlumí mikro-texturu DMR. Poloviční hladina (`level + 2,5 m`) ořezána na
      masku, filtr min. délky **3 mm** (přísněji než ISOM 1,1 mm — uživatel „bez fousků").
- [x] **Implementace** `generator.py` (`ISOM_FORMLINE`, `FORMLINE_*` konstanty, `_box_smooth`,
      `_formline_mask`, `_clip_line_to_mask`, `_polyline_len_px`, render blok jen `terrain=="real"`,
      `mask_formlines.png`, meta sekce `formlines`, log) + `omap_export.py` (103 v `USED_CODES`,
      `formline_features` param, emit jako 101/102, `n_formlines` v návratu) + `_write_contours_geojson`
      (103 do `names`). Render dashed hnědě, break zvětšen 0,2→0,5 mm (rastr; `.omap` symbol 103 věrný).
- [x] **Ladění prahů přes verify (`temp/probe_formline.py`), ne poslepu:** první prahy (curv 0,0015,
      1× smooth) daly **1466** úseků = plošný šum (mikro-textura DMR). Probe citlivosti (passes × curv ×
      spacing) + distribuce délek → `curv 0,004` + `min 3 mm` = **108** (hustší než mezikrok 70, fousky <3 mm
      pryč — obě uživatelova kritéria). Branžový precedent: Karttapullautin (poloviční hladiny + filtrace).
- [x] **Verify:** proc baseline **65 drží** (form line jen real terén → noise beze změny). NL 6×4 km:
      **108 form lines** vs 240 vrstevnic; vizuál (overlay) — form line jen v plochých zakřivených partiích,
      strmé svahy (husté vrstevnice) je nemají. Uživatel ověřil `map.omap` v OOM („super").
- [x] **SLAP docs:** GLOSSARY (Form line plná definice), spec §4.5 + §9 (form line blok, výčet `.omap`
      doplněn i o vedení/železnice/kolejiště — drift Sez. 24/28), README, TODO/DONE.

## Sezení 28 (2026-05-27) — Železnice 509 (+ vlečky) + kolejiště 501 + oprava float bugu v _draw_dashed
- [x] **Železnice → ISOM 509** (real-půlka, izomorfní s vedením 510). Verify-against-source PŘED kódem:
      vrstva je **`Železniční_trať` (id 75)**, ne „Železnice" (TODO se mýlilo); **509 = kombinovaný symbol**
      (čárky 0,35 mm + bílý „pražcový" knockout), ne prostá linie jako 510. `zabaged.fetch_railways` +
      `map_railway_to_isom`→509; `generator` mode `"railway"` (bílý podklad + černé čárky → mezery BÍLÉ,
      odliší od pěšiny 505), `_draw_railway`, `_generate_real_railways`, `--railways`, `mask_railways.png`;
      `omap_export` 509 v `USED_CODES` + `railway_features`; `batch` `railways="off"`. Export odkáže symbol 509.
- [x] **Vlečky → 509 (C)** — `Železniční_vlečka` (id 76) přidána do `RAILWAY_LAYERS` (map vrací 509 pro každou
      vrstvu). U libereckého nádraží 28 tratí (vs 6 jen `Železniční_trať`) = ten svazek kolejí.
- [x] **Kolejiště → ISOM 501 Paved area (B)** — nová **plošná** vrstva `--paved`. Verify u Liberec hl. n.:
      „10 kolejí" v datech NEJSOU linie, ale **jedna plocha `Kolejiště` (id 122, ~19 ha)**. `zabaged.fetch_paved_areas`
      + `map_paved_to_isom`→501; `generator` `ISOM_PAVED`, `_draw_paved_area` (C_ROAD výplň + C_BROWN obrys),
      `_generate_real_paved`, `mask_paved.png`, meta, CLI, z-order brzy (podklad pod kolejemi); `omap_export`
      `paved_features`. **Symbol: kombinovaný 501 s OBRYSOVOU linií** (ne 501.1 bez obrysu) — uživatel „do kolejiště
      se nevstupuje" (bounding line významová); voda 301.1 byla zbytečně konzervativní.
- [x] **Oprava latentního float bugu v `_draw_dashed`** — railway render zamrzl; diagnostika (ne hádání):
      neceločíselné `dash=6,9 / gap=4,6 px` → na hranici čárka↔mezera `step`→~1e-15 → smyčka „creepuje"
      donekonečna (>100k iterací na 10,8 px segmentu). Pěšiny (přesné 7,0/4,0) to roky maskovaly. Fix: epsilon
      v podmínce (`d < seg-1e-9`) + nudge (`step<1e-9: pos+=1e-9; continue`). Hardening i 505/506/306.
- [x] **Crossability hranic → IDEAS/TODO** (princip uživatele): styl obrysu nese překonatelnost (301 uncrossable
      vs 304/305/306 crossable; kolejiště 501 obrys = zákaz vstupu). Náš generátor honoruje volbou ISOM kódu.
      Dluh: vodní plochy vždy 301, toky vždy crossable (široká nepřekonatelná řeka by byla špatně) → TODO.
- [x] **Verify:** proc baseline **65 drží**; nádraží 28 železnic + 2 kolejiště (`.omap` 28× sym 120 + 2× sym 105);
      LS 6×4 přegenerováno **15 železnic + 1 kolejiště** + 8273 budov (`.omap` 13121 obj, 15× 509 + 1× 501).

## Sezení 27 (2026-05-27) — %AUDIT:CODE + budovy RAW (pravoúhlost zavržena) + koupaliště + řopíky + logging
- [x] **%AUDIT:CODE** (D1-D5+K1-K4, kritické 0): WFS→REST terminologický drift (~25 míst, vč. CLI help);
      `batch.py` `ortho=False`; asset `řopík_10000.*`→`ropik_10000.*` (ASCII); smazán `__future__` import;
      `map_to_isom`→`map_path_to_isom`; z-order/scale/shebang/„WFS"→„REST" kosmetika. Baseline 65 drží.
- [x] **Pravoúhlost budov → ZAVRŽENA → budovy RAW.** Implementováno (dominantní osa + tolerantní snap ±15° +
      slučování hran + rekonstrukce rohů; verify LS 96,4 % hran near-orto, 214 výjimek). ALE generalizace komolila
      tvar (budova 1028994: 15→5 vrcholů) → uživatel „kresli budovy jako vodu". **Smazáno ~430 LOC**: L1 generalizace
      (DP/min-size Sez. 18 + orthogonalizace) + L2 displacement (Sez. 21-22) + `diagnose_displacement.py`. Nový
      `_generate_real_buildings` = raw jako `_generate_real_water`. **Ponaučení → CLAUDE.md: generalizuj jen s důkazem.**
- [x] **Koupaliště (#1)** — `Pozemní_nádrž` (id 107, `podtypob_k='BA'` bazén) → ISOM 301. Lesní koupaliště LS
      (~1934 m²) chybělo, protože je nádrž, ne `Vodní_plocha`. Přidáno do `WATER_AREA_LAYERS` + `map_water_to_isom`.
- [x] **Řopíky (#2) — generátorová integrace.** `zabaged.fetch_bunkers` (Bunkr LO37) + `fetch_state_border`
      (`vyzn_zsh_k='1'` = státní hranice, ověřeno). Asset loader (jen mapové objekty z `<objects>` — oprava parsovacího
      bugu). Orientace = PCA-normála linie řopíků, „ven" k nejbližší státní hranici (univerzální ČR, ruší `OUTWARD=sever`).
      `--ropiky off|real`, postprod fáze v `synthesize_pseudorealistic_map`. SV 70 řopíků (70/70 na sever k hranici).
- [x] **Logging** v `synthesize_pseudorealistic_map` — `logging` (ne print), INFO průběh po vrstvách + finální souhrn;
      CLI zapíná (`main`→`basicConfig`), `batch.py` tichý. `_try_layer` stderr→`_log.warning`. Nápad uživatele.
- [x] Přegenerováno SV (1078 budov+70 řopíků) / NL (124) / LS (8273) — vše RAW, `layer_errors=None`.

## Sezení 26 (2026-05-27) — Ortofoto podklad + WFS→REST (města kompletní) + asset pattern + reálné řopíky
- [x] **Ortofoto podklad (3a, verify proti realitě)** — `connectors/ortofoto.py` (ČÚZK ORTOFOTO MapServer
      `arcgis1`, S-JTSK 5514, CC BY 4.0, sdílený `build_bbox`, **dlaždicování** nad strop 4096 px). Generátor
      `--ortho`/`--ortho-mpp` (default 0,5 m/px) → `ortofoto.png`; `omap_export` připne podkladový `<template>`
      do `map.omap` (paper-space, x=y=0, scale=map-mm/px, opacity 0,5, pod mapou). Formát `<template>` ověřen
      proti reálnému OOM 0.9.6 výstupu. SV/NL/LS 0,5 m/px; SV verify uživatelem (sedí pixel-přesně i v rozích).
- [x] **WFS→REST fix** (řešení nálezu Sez. 25) — `zabaged._fetch_layer` z WFS GetFeature na ArcGIS REST
      `MapServer/<id>/query` + sériová paging smyčka (`resultOffset += 2000`). `LAYER_IDS` (typeName→numerické ID),
      `f=geojson` (parsery beze změny), oprava `typuskom_k` (REST malými, WFS velkými — chyceno verify PŘED kódem).
      **Města kompletní:** SV budovy 1000→**1078**, **LS 1000→8273** budov + 3951 cest. Verify `temp/probe_rest_paging.py` (overlap 0).
- [x] **Asset pattern** — dvojice `<jméno>.omap` (vizuální vzor kreslený v OOM) + `<jméno>.rules.xml` (pravidla).
      `asset/ropik_10000.omap` (budova 521 + vrstevnice 101) + `.rules.xml` (`rotation_rule`, `draw_order`, `source`).
- [x] **Reálné řopíky na SV** — ZABAGED `Bunkr` (id 37, `typbunkr_k='LO37'` = lehký objekt vz.37), 70 bodů.
      Orientace = NORMÁLA na lokální linii řopíků (PCA okolí; nápad uživatele). Post-proces vložil 70 do SV map.omap.
- [x] **Měřítko fix** — `omap_export` přepisuje georef template (15000) na `MAP_SCALE` (10000); nesoulad (side-finding) opraven.
- [x] **Displacement práh** `MAX_DISPLACE_BUILDINGS=2000` — budova↔budova O(n²) na LS (8273) neúnosné → nad práh skip
      (efekt 0,4 mm zanedbatelný). Odblokovalo LS (doběhla za minuty).
- [x] **%BEEP → Stop/Notification hook** (`settings.local.json`). **Censure! (AI)** vymyšlený fortifikační fakt v rules
      (opraveno: k nepříteli zasypáno, střílny do vnitrozemí); `OUTWARD=sever` zadrátováno → TODO univerzalita.

## Sezení 25 (2026-05-27) — Refaktor `synthesize_pseudorealistic_map` + dev lokality (SV/NL/LS 6×4) + WFS limit nález
- [x] **Přejmenování `generate()` → `synthesize_pseudorealistic_map(lat, lon, w_km, h_km, only_real=False, out_dir="output", *, …)`**
      (reframe Sez. 23). Hlavních 6 parametrů vepředu, noise (Option 1) větev + per-vrstva toggly zachovány jako
      **keyword-only ocas** (default `terrain="real"`). `lat/lon` WGS84 (ne `n/e`). `only_real` (sladěn s CLI `--only-real`)
      → interní `pseudorealistic = not only_real` jen na hranici (`_generate_real_powerlines`/`_build_meta` beze změny, DRY).
      `_apply_extent(w_km, h_km)` přesunut z `main()` dovnitř funkce (rozměr je teď parametr).
- [x] **Dev lokality `DEV_LOCATIONS` + CLI `--location` SV/NL/LS @ 6×4 km** (`DEV_W_KM/H_KM`): DRY zdroj souřadnic
      (dřív ad-hoc). `--location KÓD` přepíše lat/lon + nastaví výsek 6×4. CLI defaulty překlopeny na `real`.
- [x] **Lidové sady (LS) = classic ISOM** (oponentura sprintu): `template_sprint.omap` je ISSprOM, ale generátor stojí
      na ISOM → LS jako classic (natrénuje hustou zástavbu); **ISSprOM/sprint pipeline → IDEAS** (samostatné sezení).
- [x] **`batch.py` na nový název** (noise = DEF extent + proc/off → baseline drží; real beze změny chování). `diagnose_displacement.py`
      nedotčen (`generate()` nevolá).
- [x] **Verify** (`.venv`): proc baseline **65 drží** přesně; real 6×4 km (grid 696×464) SV 2689 / NL 1079 / LS 3701 obj,
      `layer_errors: None`, vizuály sedí na terén.
- [x] **Nález: ČÚZK ArcGIS WFS tvrdý strop 1000 obj/dotaz** (SV+LS přesně 1000 budov). Verify-against-source (`temp/wfs_probe.py`):
      `count` strop nezvedá, `startIndex` paging rozbitý (anomálie) → **NE malá změna**; robustní = spatial tiling nebo přechod
      na ArcGIS REST. **Odloženo** → TODO `[!]` (bije hlavně města = sprint doména). **Censure! (AI)** odhad „malá změna" vyvrácen verify.
- [x] **`%END` cleanup pravidlo → `docs/PROMPTS.md`:** maž jen scratch (`temp/`, `output_*/`); cache (`.dmr_cache`,
      `.zabaged_cache`) + `__pycache__` NECH (regenerovatelné, ale zrychlují).

## Sezení 24 (2026-05-27) — Katalog ZABAGED→ISOM (149 vrstev) + el. vedení (510) + dvě fáze (pseudorealistic)
- [x] **Katalog VŠECH 149 vrstev ZABAGED Polohopis → ISOM** (`docs/kb/zabaged-isom-catalog.md`, nový):
      verify-against-source GetCapabilities (149 typů) + DescribeFeatureType (geom: 57 bodů/45 linií/47 ploch)
      + ISOM kódy z `template_classic.omap`. U každé vrstvy ISOM symbol, nebo důvod nepoužití; 13 sekcí
      (komunikace/voda/terén/vegetace/stavby/…), akční seznam kandidátů. Odkaz z `data-sources.md`.
- [x] **Verify-against-source nálezy (oprava zděděných předpokladů):** (a) **el. vedení = ISOM 510, NE 516**
      (516 = Fence/plot) — táhlo se 4 dokumenty (TODO, Příště Sez. 23, data-sources, komentář zabaged.py);
      (b) **`Most` = linie, ne bod** (komentář zabaged.py tvrdil opak). Propsáno (516→510) napříč.
- [x] **El. vedení `--powerlines real`** (`zabaged.py` + `generator.py` + `omap_export.py`): `Elektrické_vedení`
      → ISOM 510 (tenká černá linie); `NAPETI` v datech prázdné → vše 510 (bez 511). Render `mode "powerline"`,
      GT `mask_powerlines.png`, `.omap` liniový objekt 510, z-order po cestách. Izomorfní s vodou/budovami napříč
      3 soubory. Verify: proc 65 drží, Soví vrch 253=246+7 vedení.
- [x] **Příčky vedení = SLOUPY (dvě fáze, koncepční reframe uživatele):** příčky ISOM 510 odpovídají sloupům
      (běžci se jimi řídí) → **fáze 1** kreslí příčku na poloze reálného sloupu (`Stožár_elektrického_vedení`,
      `fetch_powerline_masts`, `_nearest_seg`+`_draw_tick_at`), **fáze 2** (`pseudorealistic=True`, default)
      doplní rovnoměrné jen na liniích bez sloupu. **Censure! (AI):** původně jsem příčky vymyslel rovnoměrně.
- [x] **Parametr `pseudorealistic` (default True) + CLI `--only-real`** (`generate`, meta): fáze 1 = projekce
      tvrdých dat, fáze 2 = pseudorealistická dekorace (co v datech není). Zatím působí na vedení; `%THINK`
      potvrdil, že dosavadní vrstvy jsou čistá projekce (no-op), budoucí konzument = vegetace. Spec §0b.
- [x] **Úklid:** konvence dočasné výstupy → `temp/` (gitignored); generator-poc scratch smazán, kanonické
      `Soví vrch/` + `Nová louka/` (6×4 km, 1079 obj / 3 vedení). lasertool ponechán (budoucí vegetace).

## Sezení 23 (2026-05-26) — Parametrizace výseku + reframe `synthesize_pseudorealistic_map` + úplnější/věrnější cesty
- [x] **Parametrizace výseku** (`generator.py`): velikost z konstant → argumenty `--width-km`/`--height-km`
      (š×v; souřadnice `--lat/--lon`). Otočená závislost: `PX_PER_MM` + `M_PER_CELL` (rozlišení) = jedna pravda,
      `W/H/GW/GH/TILE_M/WORLD_W_M` odvozeny v `_apply_extent(w_km,h_km)`. Rozlišení drží konstantní → mm-prahy
      (`MIN_BUILDING_PX`, `DISPLACE_*`) platí pro libovolnou velikost. Default = baseline (zpětná kompat).
      `WORLD_W_M` sjednoceno na `TILE_M·GW/GH` (jako `build_bbox`) — georef-konzistence (verify-against-source úlovek).
      Testy: Soví vrch 3,3 km², Nová louka 7,25 km² portrait, refresh 5×4 km (20 km²). proc baseline **65 drží**.
- [x] **Reframe „prediktor mapy" + název API** (`%THINK`): real-větev = `synthesize_pseudorealistic_map(n,e,w_km,h_km)`
      — dvoufázový (projekce DMR+ZABAGED → AI predikce chybějících symbolů z podobných lokalit, UC5 blokováno
      korpusem+licencí). Název zvolen proti `GetPredictedMap`/`GenerateProceduralMap` (kolize „procedural" s feederem).
      Zatím vize (IDEAS) + první enabler (parametrizace); přejmenování `generate()` = samostatný příští refaktor.
- [x] **502 Wide road — hnědá výplň** (`generator.py`, `palette.py`): casing měl bílou výplň → na bílém podkladu
      neviditelný. Template `color 11` = „Upper brown 50%" → `C_ROAD` (232,167,116) + černé okraje, width 4→3 (580 µm).
- [x] **505 Footpath 2→1 px** (template 250 µm; opraven drift „375µm/2px" ze Sez. 18, verify-against-source).
- [x] **Chybějící vrstva `Silnice_neevidovaná` → 503** (`zabaged.py`): účelové/lesní asfaltky (vč. páteřní
      Bedřichov→Nová louka) byly mimo `PATH_LAYERS` → na mapě úplně chyběly. Přidána + mapování → 503 Road
      (zpevněná <5 m). Odhaleno řetězcem ověření z uživatelova GeoJSON (bbox→cache→WFS limit→GetCapabilities).
      Princip „všechna data z geoportálu" → paměť; příště el. vedení 516, Most.
- [x] **Censure! (AI) ×2 + verify-against-source:** (a) posun lokality Soví vrch přes metriku `elev_min` místo
      záměru (vrch vypadl z výseku — data ukázala NoData jen 0,21 km, posunul jsem 2,2); (b) „silnice jsou v datech"
      bez ověření fetch řetězce (chyběla celá vrstva). Lekce → paměti `verify-data-not-assume`, `geoportal-data-completeness`.

## Sezení 22 (2026-05-26) — Displacement L2 (implementace) + nález pravoúhlost budov
- [x] **Kartografická generalizace Úroveň 2 — displacement** (`generator.py`): odsazení budov od pevné
      sítě (cesty+toky=kotva) a od sebe na ISOM min. mezeru 0,4 mm (`DISPLACE_GAP_PX`≈1,83 px).
      `resolve_displacement` — greedy kolmé odsazení od nejbližší linie (mezera k OKRAJI, nese půl
      render-šířky `_line_half_width_px`), budova↔budova symetricky (každá půl), akumulovaný posun
      clampovaný na strop `MAX_DISPLACE_PX`≈3,67 px (0,8 mm). Budova = tuhé těleso → translace celého ringu.
- [x] **Inverze kontroly LOKÁLNÍ jen pro budovy** (nález proti odhadu Sez. 21 „největší skrytý náklad"):
      rastrový z-order kreslí budovy POSLEDNÍ → pevná síť (voda+cesty) hotová → žádný přepis `generate()`.
      Split `_generate_real_buildings` → `_collect_real_buildings` (fetch→map→L1, bez kresby) +
      `_resolve_and_draw_buildings` (displacement→kresba→grid pro OMAP). `_fixed_network_px` (cesty+toky
      → px linie + half_width). Tolerance WFS obaluje jen SBĚR; resolve+draw běží na sebraném.
- [x] **GT konzistence:** posun na px geometrii → render + `mask_buildings.png` + OMAP z téže geometrie
      (jako L1, px→grid inverze). Posunutá maska JE správná GT (UC5 čte mapu, ne realitu).
- [x] **Datová korekce zadání „1–2 iterace" → 8** (verify-against-source vyvrátil vlastní odhad):
      `diagnose_displacement.py` rozšířen o měření PŘED i PO displacementu (`_measure` ×2, import
      `resolve_displacement`). Při 2 iteracích budova↔budova **regreduje** (14→16 v Č. Švýcarsku — odsazení
      od cest tlačí budovy k sobě); plató od ~6 (bb zpět na baseline, dořešen slepený pár) → `DISPLACE_ITERATIONS=8`.
- [x] **Verify (čísly):** proc baseline seed 1 = **65 obj drží** (displacement se proc netýká,
      behavior-preserving). Real (Č. Švýcarsko, plná realita) = 99 budov / 57 cest / 16 vody / 55 vrstevnic,
      OMAP **232 obj**, běh 5,2 s. Kolize: budova↔síť 14→**1** (Č. ráj 2→**0**), budova↔budova neutrální
      (14→14) / +1 (6→7), dotyk/překryv 1→**0**. **Vizuál (před/po výřez): budovy odsazené kolmo od cest,
      pevná síť netknutá** — efekt decentní, kartograficky správně. Zbytkový trade-off (strop) přiznán.
- [x] **Censure! (AI — fokus bez vizuální návratnosti):** displacement je „neviditelná" generalizace
      (posun = minimum čitelnosti 0,4 mm) — měl jsem to říct při VOLBĚ fokusu (L2 = měřitelný, ne vizuální
      skok, na rozdíl od L1 tvaru). Lekce: u volby fokusu odhadnout i vizuální návratnost.
- [x] **Nález → příští fokus (uživatel): pravoúhlost budov** (L1 tvar) — lidská obydlí ≈ 99 % obdélníky,
      na mapě splňuje sotva polovina. Orthogonalizace footprintu, nezávislé na L2. → TODO `[!]`.

## Sezení 21 (2026-05-26) — `%THINK` displacementu budov + měření kolizí
Detail: [diary/2026-05-26.md](diary/2026-05-26.md#sezení-21--think-displacement-l2-generalizace--krok-0-změřit-rozsah-kolizí).
- [x] Měření ukázalo, že dominují kolize budova↔cesta, nikoli shluky budov. Návrh byl
  proto zúžen na jednoduché kolmé odsazení od pevné sítě; později byl celý směr zavržen.

## Sezení 20 (2026-05-26) — batch.py → reálné vrstvy (P1) + zrušení dělení resources
- [x] **`batch.py` → plná realita** (P1 nález %AUDIT:CODE Sez. 19): reálná sada (`--terrain real`) teď
      kreslí reálné cesty/vodu/budovy ze ZABAGED (Sez. 16-18), ne jen terén + **procedurální** cesty.
      `--terrain real` automaticky zapne `paths/water/buildings=real` (KISS); `det` se u real přestal
      losovat (cesty jdou ze ZABAGED → variace = lokalita); manifest po `generate()` čte skutečné počty
      vrstev + chyby z `meta.json` (SSoT výsledku). Bohatší UC5 dataset z reálné geometrie více míst ČR.
- [x] **`generator.py` tolerantní reálné vrstvy** — `generate(..., tolerant=False)` + helper `_try_layer`:
      v dávkovém režimu selhání WFS/sítě jedné vrstvy ji vynechá (warning + `layer_errors` v `meta.json`)
      místo pádu celé mapy; prázdná data (0 features) výjimku nevyhodí (rozlišení „nic v datech" vs „WFS
      spadlo"). CLI single-mapy beze změny (default `False` = selže hlučně). Verify: proc baseline **65 obj
      drží** (zpětně kompat.), real n=2 (Č.Švýcarsko 57/16/99, Č.ráj 26/1/22), tolerance doložena monkeypatchem.
- [x] **`resources/ own vs club` ZRUŠENO (DROP)** — trénink UC5 = **syntetika** (reframe Sez. 4), reálné
      mapy = jen verify/reference/hold-out → licenční dělení vlastní/klubové **bezpředmětné** (zpochybnil
      uživatel: „model trénujeme na vygenerovaném datasetu"). Vrácena plochá struktura `resources/`.
      Smazán **duplikát** `resources/template_classic.omap` (bit-identický; kanonická tracked kopie zůstává
      v `sandbox/generator-poc/`, kde ji čte `omap_export.py` — `resources/` je gitignored). `data-sources.md`
      conceptual-integrity oprava (trénink = syntetika, reálné mapy = verify; dělení zrušeno).

## Sezení 19 (2026-05-26) — `%AUDIT:CODE` + `%AUDIT:DOCS`
Detail: [diary/2026-05-26.md](diary/2026-05-26.md#sezení-19--auditcode--auditdocs-foundations-úklid-oba-audity-najednou).
- [x] Opraven drift z-order komentářů a ISOM 505, extrahovány souřadnicové helpery,
  doplněny budovy do živých docs a sjednocena migrace na ArcGIS REST.

## Sezení 18 (2026-05-26) — Reálné budovy (ZABAGED→521) + kartografická generalizace L1 + OOM draw order
- [x] **`connectors/zabaged.py` +budovy** (real-půlka, izomorfní s vodní plochou): `BUILDING_AREA_LAYERS`,
      `fetch_buildings` (mirror area-půlky `fetch_water`), `map_building_to_isom` (→ 521). Verify-against-source:
      diagnostika `Budova_..._plocha_` na Soví vrchu → **105 ploch**, bodová vrstva `_bod_` prázdná
      (netáhne se, jako pramen 312), `druhbud` budova/vodojem → obojí 521 (rozhodnutí uživatele-mapéra).
- [x] **`generator.py` `--buildings off|real`** (real⇒terrain real, validace). **DRY refaktor**
      `_draw_water_area` → generický `_draw_area_symbol` + wrappery (voda modrá / budova černá —
      jako `_draw_line_symbol` u linií, Sez. 17). `_generate_real_buildings`, `mask_buildings.png`,
      meta sekce „buildings". Z-order opraven dle ISOM draw orderu: vrstevnice → **body** → voda →
      cesty → budovy (body extrémů 109/110/111 byly chybně navrch, přesunuty pod cesty).
- [x] **Kartografická generalizace Úroveň 1** (na kartografický feedback uživatele). Verify-against-source
      z `template_classic.omap` (ISOM 521 popis: min. plocha 0,5×0,5 mm, mezera 0,4 mm, průchod 0,3 mm),
      `PX_PER_MM ≈ 4,58`: (a) **min. velikost budovy** `_enforce_min_size` (floor 0,5 mm); (b) **zjednodušení
      obrysu** Douglas-Peucker `_simplify_polyline` (tolerance 0,3 mm passage); (c) **tloušťka 505** 1→2 px
      (ISOM 375 µm). **Conceptual integrity:** generalizace v px → grid pro OMAP odvozen zpět (render i `.omap`
      sdílí geometrii). Displacement (Úroveň 2, kolize budov-cest) → odloženo do IDEAS + `%THINK`.
- [x] **`omap_export.py` area close-flag fix** — OOM vyplní plošný symbol jen u UZAVŘENÉHO path; flagless
      export se nevyplnil (uživatel „neviděl budovy ani vodní plochu"). Verify-against-source: OOM po otevření
      sám doplnil flag **18** (hole point 16 + close point 2). `area_object` ho generuje (301.1 + 521).
      `USED_CODES` +521, `build_features` parametr, návrat +`buildings`.
- [x] **OOM draw order objasněn (verify-against-source, ne hádání):** draw order = **priorita barev**
      (nižší = navrch; Purple overprint 0 = úplně navrch), NE pořadí symbolů/objektů ani rastrový z-order.
      Uživatel dodal IOF zdroj (kap. 7 Colour order) + čerstvý ISOM 2017-2 template (New Map). **Výměna
      template draw order nezměnila** — OOM ISOM 2017-2 sada má vrstevnice na Brown 100% (priorita 6),
      **budovu 521 na „Black below purple" (8) = pod vrstevnicí**, 502 na 11/14 (vespod). To je **záměr
      OOM** (budova pod tratěmi 7 → vedlejší efekt pod vrstevnicí 6), ne bug. **Závěr: color-table draw
      order = uživatelova OOM doména** (Colors okno), ne úkol generátoru; export referencuje symboly přes
      ISOM kód → funguje s jakýmkoli ISOM 2017-2 template.
- [x] **`template_classic.omap`** přepsán uživatelem na čerstvý ISOM 2017-2 (New Map → Save; 169 symbolů,
      35 barev). 301.1 je v sadě standardně. Export i generate ověřeny (proc 65 / real 246 drží).
- [x] **Censure! → paměť `isom-spec-before-render`:** ISOM spec (rozměry, generalizace, draw order
      z template) studovat PŘED renderem nové vrstvy, ne reaktivně po feedbacku.
- [x] **Verify (čísly):** proc baseline seed 1 = **65 obj** (behavior-preserving refaktory) · real
      (terrain+paths+water+buildings) = **246 obj** (60 vrstevnic + 58 cest + 16 vody + **105 budov** + 7 bodů).
      **Vizuál: budovy podél údolí Svitávky a cest, sedí na terén; obrysy po generalizaci čisté bloky.**

## Sezení 17 (2026-05-26) — %CALIBRATE úklid (1. svého druhu) + reálná voda ze ZABAGED WFS
- [x] **%CALIBRATE (1. meta-audit projektu)** + IDEAS/TODO pruning — oba prahy poprvé
      (grep diáře: nikdy neproběhly). Schváleno vše: **D1** projektový `settings.local.json`
      ~45→9 wildcardů (redundantní `git -C`, holé echo-stringy, jednorázové `Start-Process`);
      **D2** dvě `[x]` položky z TODO odmazány (už v DONE); **D3** `always-show-visual-output`
      povýšen do `CLAUDE.md` (tvrdé pravidlo); **D4** `MEMORY.md` index doplněn; **K1** TODO
      UC2 rámování přepsáno (2 konektory žijí); **K2** PROMPTS cadence pozn. opravena +
      ukotvena; **K3** globální `settings.local.json` `sed` one-offs smazány. Cadence reset Sez. 17.
- [x] **`connectors/zabaged.py` +voda** (real-půlka hydrografie): `fetch_water` (toky+plochy),
      `map_water_to_isom` (podzemní→None, občasný→306, pojmenovaný→304, bezejmenný→305,
      plocha→301), `_geom_to_polygons` (outer rings). Verify-against-source: GetCapabilities
      → `Vodní_tok`/`Vodní_plocha`/`Zdroj_podzemních_vod`; diagnostika atributů na Soví vrchu.
- [x] **Verify-against-source catch 312≠313:** uživatel řekl „313 pramen", template (ISOM
      2017-2 Rev 6) má **312 = Spring** (313 = Prominent water feature). Pramen nakonec
      **vynechán** — `Zdroj_podzemních_vod` 0 ve výřezu (nejbližší PS 1,9 km), nevymýšlet.
- [x] **`generator.py` `--water off|real`** (real⇒terrain real, validace). **DRY refaktor
      `_draw_line_symbol`** — jediná kreslicí logika pro cesty (černá) i vodu (modrá);
      `_draw_path`/`_draw_water_line` = tenké wrappery. `_draw_water_area` (polygon výplň+břeh),
      `_generate_real_water` (S-JTSK→grid Y-flip, mirror real-cest), `mask_water.png`, meta
      sekce „water" (dynamicky). Z-order: vrstevnice → voda → cesty → body. `C_BLUE` už v paletě.
- [x] **`omap_export.py`** `USED_CODES` +304/305/306/301.1, `write_omap` +`water_features`
      (vše type-1 objekt; plocha jako 301.1 — kombinovaný 301 je type 16, nepřiřaditelný).
- [x] **Output konsolidován** → jediný `Soví vrch/` (= uživatelova vlastní terénně mapovaná
      oblast; gitignored), scratch `output*` smazány. Opraven komentář lokality (Děčínsko →
      Soví vrch, Lužické hory). Paměť `user-field-mapper-sovi-vrch`.
- [x] **Verify (čísly):** proc baseline seed 1 = **65 objektů** (56+2+7) = baseline Sez. 14/15
      → `_draw_line_symbol` refaktor behavior-preserving. Real (terrain+paths+water): OMAP 141
      obj (60 vrstevnic + 58 cest + **16 vody** + 7 bodů). Voda = 14 toků + 2 plochy. **Vizuál:
      Svitávka v centrálním údolí, přítoky v bočních, 2 rybníky — vše sedne na terén; uživatel
      potvrdil „Voda super! Kudos!".**

## Sezení 16 (2026-05-26) — Reálné cesty ze ZABAGED WFS (první UC2 konektor)
- [x] **`zabaged.py`** (nový, první reálný UC2 konektor) — reálné komunikace z ČÚZK ZABAGED
      Polohopis WFS 2.0.0 (`ags.cuzk.gov.cz`, **tatáž doména jako DMR**). Sourozenec `dmr.py`
      (NE kopie: dmr=rastr/výškopis, zabaged=vektor/cesty), sdílí `build_bbox` → bezešvost na terén.
      **GeoJSON output přímo** (obava IDEAS z GML parsingu padla), cache `.zabaged_cache/`.
- [x] **Verify-against-source před mapováním** (`_diagnostics`): axis order [x,y]=[easting,northing]
      ověřen na reálných souřadnicích; reálné hodnoty atributů (Cesta `povrch_k` Z/T/None,
      `typcesty_k`; Pěšina `TYPUSKOM_K`; Silnice `typsil_k`) → mapování psáno na datech, ne hádané.
- [x] **Mapování ZABAGED → ISOM** (`map_to_isom`, fyzický stav = ISOM logika): Silnice/Ulice →
      502 Wide road; Cesta zpevněná → 503 Road, nezpevněná → 504 Vehicle track; Pěšina udržovaná →
      505 Footpath, neudržovaná → 506 Small footpath. Turistická_trasa vynechána (duplikace sítě).
- [x] **`generator.py` `--paths proc|real`** (real ⇒ terrain real, validace ValueError). Render
      sjednocen `_draw_path` + `PATH_STYLE`/`PATH_CLASS` (DRY, izomorfismus proc↔real; casing pro
      502, dashed dle stylu). Proc/real cesty vyčleněny do `_generate_proc_paths`/`_generate_real_paths`
      (SLAP). Inverze S-JTSK→grid (Y-flip, sdílí georef vrstevnic). `_build_meta` +`paths_mode`
      (symbols/classes/licence dynamicky dle použitých kódů).
- [x] **`omap_export.py`** `USED_CODES` +502/504/506 (v template existují: id 108/111/113).
- [x] **Rozhodnutí: ZABAGED nativní, ne INSPIRE TN** — bohatší kategorizace komunikací pro les,
      tatáž ags doména, GeoJSON. INSPIRE TN = zbytečná harmonizovaná abstrakce téhož.
- [x] **Verify (čísly):** proc baseline seed 1 = 65 objektů (56+2+7) = baseline Sez. 14/15 →
      proc nezměněna. Validace flagu selhala správně. Real = 58 cest (502/503/504/506), OMAP 125
      obj. **Vizuál: cesty sedí na terén** (silnice v údolích, pěšiny traverzují svahy, Y-flip OK).
- [x] **KB/spec/README SLAP:** `data-sources.md` sekce „ZABAGED komunikace — WFS konektor"
      (endpoint, mapování, licence CC BY 4.0), spec §4.9/§9 (real-půlka), sandbox README,
      `.gitignore` +`.zabaged_cache/`.

## Sezení 15 (2026-05-25) — %AUDIT:CODE generator-poc + přemapování cesty 507→505
- [x] **%AUDIT:CODE** (1072 LOC, 5 modulů + spec + GLOSSARY + sandbox README) — LOC práh
      (≥500) padl podruhé po dvou přestavbách. Kód zdravý (DRY paleta, čistý dead-file stav);
      hlavní nález = reziduum SLAP dluhu Sez. 13/14 (drift ISOM kódů přežil v komentářích).
- [x] **D4(a) přemapování vedlejší cesty 507→505 Footpath** — verify-against-source proti
      `template_classic.omap`: ISOM 505 Footpath JE čárkovaná → pravidelná čárka generátoru jí
      odpovídá (Sez. 13 ji mylně zamítla „505 je plná"). Propsáno do 6 souborů: generator.py,
      omap_export.py, sandbox README, GLOSSARY, spec (§4.9/§8/§9, 5 míst), TODO. Konstanta
      `ISOM_FOOTPATH=505` teď sémanticky sedí (zrušilo K1 u kořene).
- [x] **D1/D2/K2 rezidua driftu** — docstring `generate()` 112/113/115→109/110/111; komentář
      „od nuly"→template-based; komentář z-orderu „505" po přemapování konzistentní.
- [x] **K4 SLAP** — meta dict (45 řádků) vyčleněn z `generate()` do `_build_meta()`.
- [x] **K3** — nepoužitý `template_sprint.omap` odstraněn (`git rm`; bez konzumenta v kódu).
- [x] **Verify (čísly):** noise seed 1 = 65 objektů (baseline Sez. 14, jen 507→505), real seed 1
      = 60 vrstevnic + 7 bodů (baseline Sez. 8–14). OMAP well-formed, vedlejší cesta id 112 (=505
      v template, dřív id 114=507). **Vizuál v OOM potvrzen uživatelem (Test OK, 505 a 507).**

## Sezení 14 (2026-05-25) — OMAP věrné body (template-based) + SLAP úklid ISOM driftu
- [x] **Uzavřena nezacommitovaná Sez. 13** — celá odpracovaná (kód+docs), ale nikdy
      necommitnutá (chybělo `%END`); dva commity (feat + docs) + push, procesní dluh splacen.
- [x] **OMAP export přepnut na template-based** (`omap_export.py`): z od-nuly (Sez. 13) zpět na
      template-based, ale nad VLASTNÍM čistým template `sandbox/generator-poc/template_classic.omap`
      (ISOM 2017-2, 169 symbolů / 35 barev, prázdné objekty). Skládáme jen `<objects>`; symbol id
      parsujeme z template podle ISOM kódu (id nejsou pořadová: 503→110, 507→114). `rotation=0` u 110.
- [x] **Věrná geometrie bodů** — 109 kruh / 110 elipsa (`area_symbol`) / 111 oblouk „⌣"
      (`line_symbol`) zděděné z template místo dřívějšího jednotného kruhu.
- [x] **Templaty přesunuty** `template_classic.omap` + `template_sprint.omap` do `sandbox/generator-poc/`
      (verzované, sebeobsažné; originály v gitignored `resources/` ponechány — uživatelova data).
- [x] **Refresh `output/map.omap`** — 169 symbolů (plná ISOM) + 65 objektů; **vizuál v OOM potvrzen uživatelem (Test OK)** — 110 elipsa / 111 oblouk sedí.
- [x] **SLAP úklid ISOM driftu** (dluh Sez. 13): GLOSSARY (kopeček 112/113→109/110, prohlubeň
      115→111, 116→112 Pit, cesta 505→507), spec §4.9/§8.1 (cesty 505→507), sandbox README
      (kódy + zrušený `--omap-template` + Dijkstra), README status box.
- [x] **INSPIRE TN/HY větev → IDEAS** (UC2→UC4-II): reálné cesty + voda jako vektor, oponováno
      WMS→WFS, real-only, dedikované příští sezení. + GLOSSARY termín INSPIRE.

## Sezení 13 (2026-05-25) — Terénní cesty (Dijkstra) + OMAP přestavba + oprava zastaralých ISOM kódů
- [x] **Terénně vázané cesty (§9, Dijkstra least-cost)** (`generator.py`): `_dijkstra_path`
      (8-soused, `heapq`, bez scipy) nahradil přímý splajn — cesty traverzují svah, nešplhají
      přes vrcholy. Cena = vzdálenost × (1 + LIN·sklon + SQ·sklon²) + **tvrdý strop 50 %**
      (hrana strmější zakázána, fallback). Cesty drženy v souř. mřížky (zdroj pro render i export).
- [x] **Odpuzování cest (#2)** — `_add_repulsion` zvyšuje cenu kolem nakreslené cesty → další
      cesta nesplyne (least-cost mezi blízkými konci by jinak dal jednu trasu).
- [x] **Oprava cesty přes sráz (#3)** — diagnostika `_diag_paths.py` ukázala max sklon 0.85
      (lineární penalty + repulsion). Kvadrát + strop → max sklon cest ≤ 0.49, průměr 3–6 %.
- [x] **Zastaralé ISOM kódy bodů opraveny (#1 nález):** 112/113/115 → **109/110/111**
      (Small knoll / Small elongated knoll / Small depression) dle ISOM 2017-2 Rev 6 (2024).
      Ověřeno proti oficiálnímu OOM `ISOM 2017-2_10000.omap`. Promítnuto: kód, meta, spec §4.10.
- [x] **OMAP export přepsán od nuly** (`omap_export.py`): z template-based (cizí `.omap`) na
      vlastní čistou ISOM sadu — `<colors>` (Brown/Black) + `<symbols>` (7) + objekty
      vrstevnice (101/102) + cesty (503/507) + body (109/110/111). Odstranilo dědění bordelu
      (101.1 LIDAR, 503 Minor road, cizí podklady). `--omap-template` zrušen (OMAP vždy).
- [x] **ISOM verze ověřena** (IOF): 2017-2 je nejnovější (Rev 6 2024, příští až ISOM2030).
- [x] **template_classic/sprint** — uživatel vyrobil v OOM vlastní čisté ISOM/ISSprOM templaty,
      vybrán/přejmenován `template_classic.omap` (1:10000) + `template_sprint.omap` (1:4000).

## Sezení 12 (2026-05-25) — Recovery zastaralého klonu + fetch-check + vize dvoustupňové věrnosti
- [x] **Recovery:** lokální klon byl 20 commitů za origin (founding vs Sez. 11) — `%BEGIN`
      běžel na zastaralém stavu, UC2 odpracován redundantně. Záloha do branche
      `stale-hejna-2026-05-25` + `reset --hard origin/main`, gitignored smetí uklizeno.
- [x] **Fetch-check do `%BEGIN` (krok 0)** (`docs/PROMPTS.md`): `git fetch` + porovnat HEAD
      s `origin/main` před prací. Náprava příčiny omylu (clean ≠ up-to-date).
- [x] **Vize dvoustupňové věrnosti** (`IDEAS.md` + spec §8.4): stupeň 1 kartografická věrnost
      (fyzikální gate) → stupeň 2 věrnost skenu (augmentace). Bez A/B (kolize s Pic2Omap fází).
      Start = cesty Dijkstra (TODO `[!]`); hydro jádro D8 (toky/prameny/jezera-rybníky/bažiny) další.
- [x] **`resources/` = 6 reálných map** (gitignored): georef prozradil 2 OOM dema (vyřazena).
      Smíšený původ (vlastní vs klubové, „koupené" ≠ copyright) + role hold-out/reference v KB.

## Sezení 11 (2026-05-25) — Přestavba generátoru: řez na vrstevnice + cesty (§4.9)
- [x] **Cesty (§4.9)** (`generator.py`): Catmull-Rom splajn napříč mapou — `_catmull_rom`
      (uniform, krajní body zdvojené) + `_draw_dashed` (čárkování po délce oblouku). Waypointy
      okraj→okraj (H/V) + kolmý jitter, `n = 1+round(det*1.6)`. Hlavní plná černá (ISOM **503
      Road**, 2 px) / vedlejší čárkovaná (ISOM **505 Footpath**). Nová `mask_paths.png`
      (multi-class 1/2), nový param `--det`. Z-order: po vrstevnicích, před body. Splnil
      `[!]` dluh ze Sez. 10 (cesty odkládané od Sez. 6).
- [x] **Řez „znovu a lépe"** — zahozeny plošné vrstvy (vegetace §4.2, paseky §4.3, bažiny
      §4.4, balvany §4.11) + mrtvá pole (`slope/eb/gradient`, `_to_pixels`, `box_blur`,
      `_draw_dotted`) + masky `mask_veg/water/rock`. Důvod (A1): **vizuální věrnost** — vrstvy
      vypadaly uměle (bažina = pole „plusů") → kazily by domain gap feederu pro UC5. Zahodit
      špatně vypadající vrstvu > krmit model artefakty. Zůstaly vrstevnice + body 112/113/115
      + vektor/`.omap` (A2). Import palety zúžen na 3 barvy (bílá/hnědá/černá).
- [x] **`batch.py` srovnán** s novou signaturou `generate(seed, rug, det, …)` (pryč vd/wat/rock).
- [x] Verify (čísly, ne vírou): **real 60 vrstevnic + 7 bodů = bitově shodné s baseline Sez.
      8-10** (řez se vrstevnic/bodů nedotkl). Noise 56 vrstevnic + 2 cesty + 7 bodů. Staré masky
      pryč, `mask_paths` nenulová. Vizuál obou renderů čistý a „orienťácký". Cesty terén
      nerespektují (kříží kopce) — vědomá §4.9 vlastnost, §9 Dijkstra odložen.
- [x] **Volba A (procedurální cesty) potvrzena nad daty:** „převzít cesty ze ZM5" oponováno —
      ZM5 je zrušený rastr (1.7.2023 → ZTM5), vektor cest je v ZABAGED Polohopis (WFS, CC BY 4.0).
      Reálné cesty = UC2 konektor (data-driven), funguje jen pro real terén → odloženo do IDEAS.
      Procedurální §4.9 funguje noise i real. SLAP: spec §4/§4.9/§8.1, README ×2, GLOSSARY.

## Sezení 10 (2026-05-25) — Bodové symboly lokálních extrémů (§4.10)
- [x] **Generalizace malých izolinií → bodové symboly** (`generator.py`): uzavřená malá
      smyčka vrstevnice = lokální extrém → bodový symbol místo prstence (ISOM generalizace).
      Detekce dle TODO: uzavřenost + plocha shoelace pod prahem (`KNOLL_MAX_AREA_M2`=600 m²)
      + výška centroidu vs úroveň. Lok. max → **112 Small knoll** (hnědá tečka) / **113
      Elongated knoll** (poměr stran bbox > 2,5, hnědá elipsa); lok. min → **115 Small
      depression** (hnědý oblouk „⌣"). **116 Pit vědomě vynechán** — jiná feature class,
      z výškopisu neodlišitelný od 115 (oponováno TODO „všechny 4").
- [x] **`mask_symbols.png`** (multi-class GT) — konečně implementuje §8.1 (Sez. 9 D5 ji
      značila jako neimplementovanou). Třídy 1=112 / 2=113 / 3=115. + `point_symbols`
      v `meta.json` (detekční anotace COCO/YOLO styl: symbol, název, pozice mřížka i px).
- [x] Verify (čísly, ne vírou): zákon zachování `linie + symboly` drží na obou terénech
      (noise 63=56+7, real 67=60+7). **Real 67 = bitově shodné s baseline Sez. 8/9** —
      jen 7 linií se přesunulo na symboly. Maska: všech 7/7 symbolů má nenulovou třídu
      u středu; vizuál zvětšených výřezů potvrdil tvary 112/113/115 + spojitost okolních
      vrstevnic. 116/204 vynechány záměrně.

## Sezení 9 (2026-05-25) — %AUDIT:CODE + %AUDIT:DOCS (foundations úklid)
- [x] **%AUDIT:CODE** nad `sandbox/generator-poc/` (5 modulů, ~750 LOC; práh padl 8 sez/500 LOC).
      Hlavní závěr: mrtvého kódu skoro není (`%END` cleanup funguje). Opraveno: **R1** `C_WHITE`
      obcházen hardcoded `255` → zapojen z palety (DRY); **K1** `from __future__ import
      annotations` redundantní na Py 3.14 (PEP 649/749, ověřeno verzí) → smazán z 5 modulů;
      **K2** duplicita `TILE_M*(GW/GH)` → konstanta `WORLD_W_M`; **K3** jazyk v komentáři.
      **R2** (`C_PURPLE`/`Swatch.meaning`) vědomě ponecháno (izomorfní API palety).
- [x] **%AUDIT:DOCS** nad 19 `.md`. Opraveno D1-D7: **D1** `sandbox/README` „zatím prázdný"
      (5 sez. nepravda) → výčet experimentů + konvence `<NN>-` uvolněna; **D2** `architecture`
      rozpor „kód zatím žádný" vs „první reálný kód"; **D3** spec §4.5 tloušťky 0,7/1,3→1/3 px;
      **D4** `tools-models` stack +pyproj; **D5** spec §8.1 `mask_symbols` neimplementováno;
      **D7** `data-sources` URL `.cz`→`.gov.cz`.
- [x] **D6: založen `GLOSSARY.md`** (root) — doménový slovník (OB/ISOM, ČÚZK data, UC DAG,
      nástroje); propsán do README (layout + Docs). PROMPTS na něj odkazovaly, neexistoval.
- [x] Verify (ne odhad): noise + real (cache) běh OK, roh pixelu bílý, 8 barev = paleta,
      real 67 linií = bitově shodné s baseline Sez. 8 → úklid behavior-preserving.

## Sezení 8 (2026-05-25) — Vektorizace vrstevnic na ISOM + DRY paleta + ČSOS KB
- [x] **DRY: paleta → `palette.py`** (jediný zdroj pravdy): slovník `PALETTE` (slug→Swatch
      rgb+význam) + odvozené `C_*`. `generator.py` importuje (zahozeny lokální konstanty +
      inline `(0,0,0)`). Oponováno TODO „→ isom-issprom.md": runtime konzument je Python,
      parsovat MD je proti KISS → SSoT v kódu, docs (spec §5, KB) odkazují. Verify: noise
      render + batch import OK.
- [x] **Mapový portál ČSOS → KB** (`data-sources.md`): zdroj reálných OB map (cesta B,
      7000+ map, Mapová rada ČSOS + T-MAPY). **Gate ZAVŘENA dvojitě** (ověřeno ze stránky
      „O projektu"): copyright klubů + jen náhledy 96 dpi s vodoznakem, souhlas vydavatele
      nutný i pro výzkum. Verify-against-source dotáhl licenci z „nevím" na jednoznačné NE.
- [x] **Vektor vrstevnic → `contours.geojson`** (§9): polylinie z contourpy se symbolem
      **101 Contour / 102 Index contour**, georef **S-JTSK (EPSG:5514)** pro real (lokální
      metry noise). Žádná vektorizace rastru (AutoTrace) — z přesného zdroje. `dmr.build_bbox`
      zveřejněn. Verify: 67/68 linií, rozsah přesně 1465×1000 m.
- [x] **`.omap` export → `omap_export.py`** + `generator.py --omap-template`: template-based
      (nahradí `<objects>` ve funkčním ISOM `.omap`), Local CRS, paper-space transform
      (1 m→100 µm). Nesdílí kód s Pic2Omap `db2omap` (ten z rastru) — jen formát. **Verify
      uživatelem v OOM: vrstevnice sedí.** (OOM 0.9.6 jen `windows` platform → headless nejde.)
- [x] **lasertool / AutoTrace / multi-echo** do KB (`tools-models.md`, `data-sources.md`):
      lasertool = LIDAR point cloud→rastr (Karttapullautin rodina, naráží na vegetace gate);
      vektorizační nástroje pro UC4-III/UC3 (CoVe napřed); multi-echo LAS lze koupit (odloženo).

## Sezení 7 (2026-05-24) — Reálný batch dataset z lokalit ČR
- [x] **`batch.py --terrain noise|real`:** reálná větev vyrobí dataset map z různých míst ČR
      (`CZ_LOCATIONS` — 10 členitých OB oblastí). Hlavní variace = lokalita; losují se jen
      `vd/wat/rock` (`rug` u reálného terénu mrtvý). Manifest s lokalitou + souřadnicemi.
- [x] **Noise sada zachována bitově reprodukovatelná** (rozvětvení dle terénu — pořadí
      losování `master.random` se neposunulo). Variace `--rock` v noise větvi odložena (TODO).
- [x] **Montáž s popisky lokalit** (`build_montage(labels=...)`, bílý podklad + černý text);
      default `--out` → `output/dataset_<terrain>` (noise/real se nepřepíšou).
- [x] **Bug `dmr.py` (cache-before-validate):** cache zapisovala `raw` PŘED validací TIFF →
      degenerovaný soubor se uložil a každý další běh na něm spadl. Opraveno: `Image.open`
      předchází zápisu + srozumitelná `RuntimeError` (hint „mimo pokrytí / za hranicí").
- [x] **Krušné hory mimo hranici:** souřadnice 50.68,13.45 ležely na hřebeni = státní hranici,
      bbox 1466 m zasahoval za ni → ČÚZK vracel oříznutý 1364 B TIFF (ověřeno 3×, CL match).
      Posunuto na jižní svahy (50.50,13.40), převýšení 108 m. Odhaleno verify, ne tipem.
- [x] Verify (ne odhad): 10 map vygenerováno, montáž + manifest sedí, detail Moravského krasu
      (rock=0,975) ukazuje balvany ve strmu, reálné vrstevnice, bažinu v údolní nivě.

## Sezení 6 (2026-05-24) — Věrnost generátoru: balvany, obrys bažin, index contours
- [x] **Tečkovaný obrys bažin (§4.4):** `contourpy` na binární masce bažin (level 0,5),
      helper `_draw_dotted` (arc-length vzorkování teček). Obrys přesně kopíruje výplň,
      kreslen pod vrstevnicemi (z-order). Doplněn chybějící prvek spec §4.4.
- [x] **Vrstva balvanů (§4.11):** nový `--rock` parametr, `round(rock*120)` černých teček,
      přijetí `0.25 + slope*0.9` (slope-vážené = fyzikálně smysluplné), GT maska `mask_rock.png`.
- [x] **Index contours výraznější:** hlavní vrstevnice 2→3 px (baseline ukázal, že 2 px bez
      antialiasingu splývá; jasnější odlišení tříd pomáhá i UC5, v intencích spec §8.2).
- [x] Verify (ne odhad): noise render OK, `--terrain real` regrese OK (cache hit 0,31 s),
      všech 5 GT masek se zapisuje. Vizuálně ověřen obrys i slope-vážení balvanů.
- [x] `.gitignore`: vzor `output_*/` — obrana proti commitnutí pojmenovaných scratch renderů.

## Sezení 5 (2026-05-24) — Option 2: reálný ČÚZK DMR 5G terén
- [x] **Feasibility ověřena prakticky** (ne odhad): `pyproj` wheel na Py3.14 funguje;
      ČÚZK DMR 5G ArcGIS ImageServer (`/arcgis2/rest/services/dmr5g/ImageServer`,
      pixelType F32, S-JTSK) vrací float grid přes `exportImage`; Pillow čte float TIFF
      jako mode "F" → **žádný GDAL/rasterio nutný.**
- [x] **`dmr.py`** (nový): stažení DMR 5G dlaždice, WGS84→S-JTSK (pyproj), poměrový bbox
      (izotropní buňka), disk cache, sanity check výšek.
- [x] **`generator.py`**: `--terrain noise|real` + `--lat/--lon`, reálný `elev` v metrech
      → `hbase` normalizací, sjednocené hlavní vrstevnice (`level % 25`), atribuce v `meta.json`.
- [x] Ověřeno vizuálně: reálné vrstevnice (údolí/hřbety/sráz), zmenšený domain gap vs blob (§8.4).
      Regrese noise OK, cache hit 0,31 s, vegetace/bažiny správně syntetické (DMR ground-only).
- [x] SLAP propsání: spec §8.5, architecture, IDEAS, RESEARCH, data-sources (exportImage kanál),
      sandbox README (stack +pyproj, CC BY 4.0 atribuce), `.gitignore` (`.dmr_cache/`).

## Sezení 4 (2026-05-23) — Procedurální generátor OB map (MVP)
- [x] Resumé projektu (sjednocení obrazu) + debata o konektorech: tři datové cesty
      (A geodata / B korpusy / C syntetika), sim-to-real recept.
- [x] Spec generátoru zachycena do repa: `docs/kb/generator-procedural.md` (z Downloads).
- [x] **První reálný kód v repu:** `sandbox/generator-poc/generator.py` — vrstevnice
      (izolinie) + vegetace + bažiny + GT masky zdarma. Stack Python 3.14 + numpy +
      contourpy + Pillow (scikit-image vynechán, KISS + 3.14 wheels).
- [x] `batch.py` — mini dataset 16 map, reprodukovatelný z (seed0=1000, n=16), diverzita
      ověřena mozaikou.
- [x] Reframe (architecture/IDEAS): UC4-I syntetika z „úplný konec" → enabler-feeder pro UC5.

## Sezení 3 (2026-05-23) — Vegetace gate (ČÚZK plné mračno = NE)
- [x] Ověřeno: ČÚZK **neposkytuje** plné klasifikované multi-echo mračno jako open data.
      Nový hustý DMP OK je z **obrazové korelace** (fotogrammetrie, jen povrch, žádné echoes),
      surové LLS mračno není open. → „Vegetace gate" zavřena, náhrada jen CHM+NIR proxy.
      Ověřeno proti primárnímu zdroji (technická zpráva DMP OK, 1/2026).
- [x] KB konsolidace (SLAP): `data-sources.md` (DMP OK, oprava DMR 5G, „Vegetace gate"),
      `RESEARCH.md` (otázka uzavřena), `TODO.md` (`[!]` hotovo).

## Sezení 2 (2026-05-23) — UC2 průzkum ČÚZK + LIDAR research
- [x] UC2 průzkum ČÚZK geoportálu: přístup (WMS/WMTS/WFS/WCS/ATOM) + **licence = CC BY 4.0**
      (gate otevřena → na ČÚZK datech lze stavět UC4-II/III s atribucí).
- [x] DMR 5G (LIDAR výškopis): dostupnost 100 % ČR, formát LAZ, licence CC BY 4.0.
- [x] Naplněn `docs/kb/data-sources.md` — ČÚZK katalog + oprava terminologie ZTMP → ZABAGED/ZTM.
- [x] Doplněn `RESEARCH.md` — metoda LIDAR → orienteering mapa (Karttapullautin); nález
      „DMR 5G ground-only ≠ vegetace, třeba plné mračno bodů".

## Sezení 1 (2026-05-22) — Founding
- [x] Seznámení s Pic2Omap (architektura, workflow, dokumentační kultura).
- [x] %THINK nad 5 UC → zjištěno, že tvoří DAG (enablery pod aplikacemi), ne seznam.
- [x] Rozhodnutí: vztah k Pic2Omap = deštník→monorepo (B→A); MVP = UC1; jméno = AzimutLab.
- [x] Založena kostra repo: README, CLAUDE.md overlay, docs/PROMPTS.md,
      docs/architecture.md (kanonický DAG), IDEAS, RESEARCH, docs/kb/ (3 soubory),
      sandbox/, TODO/DONE/DIARY, .gitignore, git init (branch main).
