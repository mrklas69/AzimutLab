# ISOM-scan benchmark

Měří, jak dobře (vision) model rozpozná ISOM symboly **přímo ze skenu OB mapy** — bez doučení,
jen ze spec + barevné palety. Baseline „hotový model sken → ISOM" (kontext: IDEAS „Hotový pretrained
model…", Sez. 142). Testuje cloudové i lokální modely **stejným promptem na stejném vstupu**.

## Architektura
**Model produkuje jen svou odpověď (JSON). Skórování dělá oddělený `score.py` proti GT.**
Model nikdy neskóruje sám sebe (self-scoring je nedůvěryhodné + lokální modely nemají file-write).

```
task_isom_scan.md          # fixní prompt (vč. JSON schématu výstupu)
task_isom_scan.png         # LOKÁLNÍ vstup: ořez skenu 1127443 Branžež (1655×1868), necommitovat
*.pdf                      # LOKÁLNÍ reference: ISOM spec + IOF barvy, necommitovat
gt/ground_truth.json       # verzovaná generátorová GT (READY; only_real, data-derivovatelné kódy)
gt/task_crop_box.json      # verzovaná crop kotva pro obnovu GT/overlay
runs/_run_template.json    # verzovaná šablona běhu
runs/*.json, runs/*.png    # LOKÁLNÍ syrové výstupy modelů a overlaye, necommitovat
results.csv                # verzovaný leaderboard, připisuje score.py
score.py                   # runs/*.json × gt → metriky → results.csv
build_gt.py                # obnoví GT z lokálního resources/livelox/1127443 korpusu
overlay.py                 # vykreslí GT/run body nad lokální sken
black_brown_poc*.{py,ps1}  # scan-mining PoC: černá vs hnědá maska ze skenu
manmade_points_poc.py      # scan-mining PoC: 525/527/531 z izolovaných černých komponent
manmade_points_review.py   # kurátorský manifest + crop sheet pro PoC kandidáty
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
python isom_scan/manmade_points_review.py --detections temp/manmade_points_bedrichovka/detections.json
```
To vytvoří `review_manifest.json`, `review_sheet.png` a `crops/*.png`. Do manifestu se ručně
doplní `review.verdict` (`tp` / `fp` / `ignore`) a případně `review.true_code`. Teprve takový
manifest je vstup pro ladění prahů; samotný PoC výstup není GT.

## Git hranice
Verzovat: skripty, prompt, README, `results.csv`, `gt/ground_truth.json`, `gt/task_crop_box.json`,
`runs/_run_template.json`.

Necommitovat: `task_isom_scan.png`, PDF reference, overlay/mask PNG, `runs/*.json` výsledky modelů,
lokální `resources/livelox/1127443/` korpus. Když chybí lokální vstup, skript má selhat nahlas,
ne vyrábět náhradní sken.

## Odloženo (curtains)
Cost tracking přes API, varianty no-spec / tiling pro malý kontext, leaderboard render. Až po základu
(GT + JSON + score.py + results.csv).
