# ISOM-scan benchmark

Měří, jak dobře (vision) model rozpozná ISOM symboly **přímo ze skenu OB mapy** — bez doučení,
jen ze spec + barevné palety. Baseline „hotový model sken → ISOM" (kontext: IDEAS „Hotový pretrained
model…", Sez. 142). Testuje cloudové i lokální modely **stejným promptem na stejném vstupu**.

## Architektura
**Model produkuje jen svou odpověď (JSON). Skórování dělá oddělený `score.py` proti GT.**
Model nikdy neskóruje sám sebe (self-scoring je nedůvěryhodné + lokální modely nemají file-write).

```
# Benchmark harness (sken → JSON odpověď modelu → score)
task_isom_scan.md          # fixní prompt (vč. JSON schématu výstupu)
task_isom_scan.png         # LOKÁLNÍ vstup: ořez skenu 1127443 Branžež (1655×1868), necommitovat
*.pdf                      # LOKÁLNÍ reference: ISOM spec + IOF barvy, necommitovat
gt/ground_truth.json       # verzovaná generátorová GT (READY; only_real, data-derivovatelné kódy)
gt/task_crop_box.json      # verzovaná crop kotva pro obnovu GT/overlay
runs/_run_template.json    # verzovaná šablona běhu
runs/*.json, runs/*.png    # LOKÁLNÍ syrové výstupy modelů a overlaye, necommitovat
results.csv                # verzovaný leaderboard, připisuje score.py
score.py                   # runs/*.json × gt → metriky → results.csv
build_gt.py                # obnoví generátorovou GT (v1) z lokálního resources/livelox/1127443 korpusu
gt_from_markers.py         # markery (mark_isoms) → hybrid GT (v2): ruční body + generátorové linie/plochy + sanity-check
overlay.py                 # vykreslí GT/run body nad lokální sken

# Scan-mining PoC (per-barva bodoví kandidáti ze skenu → detections.json)
points_common.py           # sdílená mašinérie 4 detektorů (CV pipeline, shape-match, payload, vizualizace)
black_brown_poc.py         # scan-mining PoC: černá vs hnědá maska ze skenu
water_points_poc.py        # scan-mining PoC: 311/312/313 z modrých komponent
manmade_points_poc.py      # scan-mining PoC: 525/527/531 z izolovaných černých komponent
terrain_points_poc.py      # scan-mining PoC: 109/111/112/115 z malých hnědých komponent
vegetation_points_poc.py   # scan-mining PoC: 417/418 z malých zelených komponent

# Kurace / review kandidátů (rodinově AGNOSTICKÉ — běží na kterékoli detekci, ne jen manmade)
points_review.py           # kurátorský manifest + crop sheet pro PoC kandidáty
points_omap.py             # export bodových kandidátů do pracovní .omap kopie pro vizuální kontrolu
review_ui.{html,py}        # lokální HTTP UI: odškrtávání tp/fp/ignore nad review manifestem
mark_isoms.py              # lokální canvas marker: ruční point markery do JSON, ne do `.omap`
markers/*.json             # ruční pozitivní markery (recall důkaz pro KOMPAS)

# GT factory (Část A → B: SET dlaždic 512×512 → ruční dokurace GT)
build_tile_set.py          # Část A: z reálné mapy vyrobí SET dlaždic ke kuraci
gt_ui.{html,py}            # Část B: lokální HTTP UI pro dokuraci tile GT

# Kalibrační ledger
calibration_manifest.json  # per-ISOM ledger prahů/markerů/review (rozpracováno: 1/12 záznamů má doplněný recall)
calibration_manifest.py    # validace tvaru ledgeru; strict až po ruční kuraci
```

## Postup spuštění jednoho běhu
1. **Prompt modelu:** dej mu `task_isom_scan.md` + `task_isom_scan.png` + obě PDF (pokud je umí číst).
2. **Sběr:** zkopíruj `runs/_run_template.json` na `runs/<date>_<model>_<seed>.json`,
   vyplň `meta` (model, build, provider, quant, vision, pdf_ingested, temperature, seed, tokeny…)
   a do `output` vlož JSON blok, který model vrátil.
3. **Skóruj:** `python score.py runs/<date>_<model>_<seed>.json`
   → připíše řádek do `results.csv`.
4. **Více běhů najednou:** `python score.py runs/*.json`

> **Reprodukovatelnost:** každý model spusť na **N seedech** a reportuj **medián** (jeden běh = šum;
> izomorfní s medián-3-seedů u Png2Point). Při změně `task.md`/GT zvyš `BENCHMARK_VERSION` v `score.py`.

## Metriky (`results.csv`)
- **Run metadata** — `model, build, provider, quant, ctx_window, vision, pdf_ingested, temperature, seed, …`.
  Capability flagy (`vision`, `pdf_ingested`, `quant`, `ctx_window`) odhalí, jestli model hraje stejnou hru
  (model bez vize / bez PDF readeru ≠ srovnatelný).
- **Self-report** — `n_point, n_line, n_area, n_codes` (co model tvrdí; NE správnost).
- **Skórované vs GT** — `point_F1` (**headline**, macro-F1 bodových kódů, distance-match do `--tol-px`),
  `area_count_fid` (věrnost počtů ploch/linií), `class_recall` (podíl GT kódů, které model vůbec našel).

**Headline KPI = `point_F1`** (jedno primární číslo, anti-sprawl). Zbytek je diagnostika.

## Ground truth
Vektorová GT (`.omap`) pro původní sken neexistuje. Aktuální verzovaná GT je proto
**generátorová READY kotva**:

1. `build_gt.py` spustí `generate_map(..., only_real=True)` na stejném Branžež quad výřezu jako sken.
2. Výstup transformuje přes `.pgw`/S-JTSK do souřadnic `task_isom_scan.png`.
3. `score_codes` omezí skórování jen na data-derivovatelné kódy, kde generátor nekreslí pseudo pravdu.

Tohle není plná pravda skenu. Je to tvrdá automatická kotva pro srovnatelné měření hotových vision modelů
a pro scan-mining utilitky. Ruční kartografická korekce může přijít později, ale nesmí se tiše míchat
se stávající generátorovou GT bez zvýšení `BENCHMARK_VERSION`.

Hrubá automatická kotva ploch: `resources/livelox/1127443/gt_labels.png` (runnability segmentace les/otevřeno/voda).

## Scan-mining PoC utilitky
`black_brown_poc.py` odděluje neutrální černou kresbu od hnědých vrstevnic. Navazující
`manmade_points_poc.py` z téhle černé kresby hledá malé izolované komponenty podobné
symbolům **525 Small tower**, **527 Fodder rack** a **531 Prominent man-made feature: x**.
Výstup (`detections.json`, overlay, contact sheet, maska) je diagnostika pro oko/kuraci,
ne tréninková pravda. 525/527/531 zatím zůstávají v generátoru pseudo fallback; capability
registry je označuje jen jako `classic_cv_poc`, ne jako live mapper-scan.

Kurace kandidátů:
```powershell
python isom_scan/points_review.py --detections temp/manmade_points_bedrichovka/detections.json
```
To vytvoří `review_manifest.json`, `review_sheet.png` a `crops/*.png`. Do manifestu se ručně
doplní `review.verdict` (`tp` / `fp` / `ignore`) a případně `review.true_code`. Teprve takový
manifest je vstup pro ladění prahů; samotný PoC výstup není GT.

Kalibrační protokol pro jeden ISOM kód:
1. Přesné pozitivní markery ukládej primárně do JSONu přes lokální canvas marker:
   `python isom_scan/mark_isoms.py --image "maps/Buschdörfl/bg_scan.png" --codes 311,312,313`.
2. `.omap` `602/704` používej už jen jako volitelný dočasný overlay, ne jako zdroj pravdy.
3. Spusť příslušný PoC skript s kandidátními parametry a vyrob review sheet.
4. Změř recall vůči markerům, false positives vůči negativním příkladům a uprav prahy pro konkrétní kód.
5. Parametry zapiš jako per-ISOM kalibraci; dokud nejsou opakovatelné, výstup zůstává jen pracovní vrstva.

Verzovaný ledger prahů (a rozpracované kalibrace) je `calibration_manifest.json` — **stav: rozpracováno**,
`marker_recall` je doplněn jen u 1/12 kódů (zbytek `null`, `_status: IN_PROGRESS`). Je to ledger prahů, ne
hotová kalibrace s recall. Základní kontrola:
```powershell
python isom_scan/calibration_manifest.py
```
Bez `--strict` validátor hlásí chybějící ruční hodnoty jako `WARN`, ne jako chybu. Tvrdě selhává
jen na rozbitém schématu nebo duplicitních ISOM kódech. `--strict` zapni až ve chvíli, kdy jsou
markery, recall i false-positive počty pro laděné symboly doplněné.

Pro Hamr na Jezeře `109` tenhle postup ukázal důležitý detail: score práh sám nestačí, protože slabé
tečky z liniového `108` vypadají podobně. `--min-area 25` je zatím kalibrovaný filtr, který tyto
negativní příklady odstranil při zachování marker recall.

Pracovní `.omap` kopie pro kontrolu kandidátů:
```powershell
python isom_scan/points_omap.py `
  --review temp/manmade_points_buschdorfl/review/review_manifest.json `
  --include-unreviewed `
  --map "maps/Buschdörfl/Buschdörfl.omap" `
  --out temp/manmade_points_buschdorfl/Buschdörfl_candidates.omap
```
Export čte transformaci existujícího `bg_scan.png` template v mapě a zdrojovou `.omap`
nepřepisuje. U review manifestu defaultně exportuje jen `tp`; `--include-unreviewed`
je určené pro první vizuální průchod.

Hnědé terrain-point kandidáty. Výchozí sada je 111/112/115, konkrétní symbol lze
omezit přes `--codes`:
```powershell
python isom_scan/terrain_points_poc.py `
  --input "maps/Buschdörfl/bg_scan.png" `
  --out-dir temp/terrain_points_buschdorfl `
  --max-dim 3000
python isom_scan/terrain_points_poc.py `
  --input "maps/Hamr na Jezeře/bg_scan.png" `
  --out-dir temp/terrain109_hamr `
  --codes 109 `
  --max-dim 3000 `
  --score-threshold 0.87 `
  --min-area 25
python isom_scan/points_review.py `
  --detections temp/terrain_points_buschdorfl/detections.json `
  --crop-px 220
```
Hnědá kresba sdílí barvu s vrstevnicemi, takže výstup má vyšší riziko false positive
než černé man-made body. Pro `109` je důležitý `--min-area`, jinak se jednotlivé
slabé tečky z liniového `108` pletou s bodovou kupkou. Používej ho jako
kandidátní review vrstvu, ne jako pravdu.

Zelené vegetation-point kandidáty 417/418:
```powershell
python isom_scan/vegetation_points_poc.py `
  --input "maps/Buschdörfl/bg_scan.png" `
  --out-dir temp/vegetation_points_buschdorfl
python isom_scan/points_review.py `
  --detections temp/vegetation_points_buschdorfl/detections.json `
  --crop-px 180
```
Při update mapy, která už obsahuje pseudo 417/418, použij export s
`--replace-existing-codes`, jinak se scan kandidáty smíchají se starou pseudo vrstvou.

## Git hranice
Verzovat: skripty, prompt, README, `results.csv`, `gt/ground_truth.json`, `gt/task_crop_box.json`,
`runs/_run_template.json`.

Necommitovat: `task_isom_scan.png`, PDF reference, overlay/mask PNG, `runs/*.json` výsledky modelů,
lokální `resources/livelox/1127443/` korpus. Když chybí lokální vstup, skript má selhat nahlas,
ne vyrábět náhradní sken.

## Odloženo (curtains)
Cost tracking přes API, varianty no-spec / tiling pro malý kontext, leaderboard render. Až po základu
(GT + JSON + score.py + results.csv).
