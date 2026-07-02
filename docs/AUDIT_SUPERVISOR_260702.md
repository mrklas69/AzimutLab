# AUDIT_SUPERVISOR_260702

**Datum:** 2026-07-02 · **Auditor:** Claude Opus 4.8 (1M) · **Rozsah:** `README.md`,
`docs/architecture.md`, `docs/ROADMAP.md`, `docs/TODO.md` (celé), `docs/DIARY.md` (index
123–178) + diáře 2026-06-28/29 a 2026-07-01 (Sez. 175–178), `docs/GLOSSARY.md` (výběrově),
předchozí audity `AUDIT_SUPERVISOR_260612.md` / `_260619.md` / `_260621.md`, paměť (MEMORY).
Přímé ověření kódu: `generator/measure_dod.py`, `isom/capabilities.py`, `generator/omap_raster.py`,
`model/{norm,png2*/}`, `connectors/arcgis.py`, `generator/compare_isom.py`, `tests/`, git log,
`git ls-files`, `.gitignore`, tvary hlav kanonických checkpointů (`torch.load`),
`isom_scan/calibration_manifest.json`. · **Metoda:** meta-audit směru/rizik/procesu; **4 paralelní
verifikační agenti** ověřili tvrzení proti zdroji (načtení tvarů `.pt`, běh `unittest`, `git ls-files`,
grep DRY/SSoT), ne z docs. Testy spuštěny na stroji **HAL3000/mrkla** (`.venv`, torch cu128):
`unittest discover -s tests` = **80 OK + 1 skip**. `git status` = **čistý strom** (žádné paralelní
vlákno, žádný untracked artefakt).

---

## TL;DR

Projekt od auditu 260621 udělal poctivý pokrok a **KRITICKÁ námitka A1 je definitivně vyřešená**:
všechny tři reconstructory mají checkpoint tvarů, které lícují se scope v kódu (area 21/21, line 2/2,
point 10/10), `eval_real` na reálném skenu zas běží (retrain Sez. 156/162). Přibyla i data-gate
poctivost (`DATA_GATE_CEILING`, Sez. 177–178), GT factory s ručním recall (anti-Goodhart), tracked
`.pgw` i `calibration_manifest`, 80 testů. **Tři nejzávažnější věci ale míří na strategický patový
stav, do kterého fáze `Generator()` dojela:** **(A1)** exit-kritérium fázové závory (KPI ≥ 85 %) je
sankcionovanými prostředky nejspíš nedosažitelné — Sez. 177 sám doložil, že `gen=0` díry jsou
systematicky **data-gate** (ČÚZK je nenese) a plošná+liniová páka z ČÚZK je „VYČERPANÁ"; jediná
zbývající coverage cesta (scan-mining injekce) je blokovaná na **ruční GT uživatele**, která
stagnuje (mapfield 6 sezení, 311/313 čeká). **(A2)** vrcholová metrika `eval_real` **zamrzla ~16
sezení** (checkpointy Sez. 156/162, od té doby žádný retrain) a reálný transfer je prostřední a
nezlepšuje se (Png2Area Bedř soft 0,525 / Blatná 0,363, 210 kolabuje, 404/407/409 halucinují) — leští
se feeder KPI, cíl stojí. **(A3)** nejcennější neopakovatelný artefakt `_curation.json` (ruční vizuální
tagy) + `_split.json` (eval kontrakt) jsou **napříč TŘEMI audity pořád necommitnuté** — levná oprava se
odkládá počtvrté. Pod tím trvá menší dluh: chybějící A5 invarianty (golden/AREA_ZORDER/301 guard),
`isom_scan/` nezmíněný v žádných řídících docs, DIARY index bobtná (sám si to poznamenal).

---

## Stav námitek z minulého auditu (260621, Opus 4.8)

| ID | Námitka | Stav | Doklad |
|----|---------|------|--------|
| A1 | Scope deklarován, checkpointy staré → `eval_real` shape-mismatch | **VYŘEŠENO** | `omap_raster.py:80` N_AREA=21 · `:266` N_LINE=2 · `inject.py:179` N_POINT=10; `.pt` hlavy `(21,·)/(2,·)/(10,·)` + meta `n_area/n_line/n_point` lícují (Sez. 156/162); eval_real Bedř soft 0,525 (`architecture.md:203`) |
| A2 | Scan-mining „kalibrace" bez recall + untracked | **VYŘEŠENO z velké části** | `calibration_manifest.json` je **tracked** (`git ls-files`); recall MĚŘEN proti ruční GT 109/111/112/115/204 (Sez. 169–174, F1 v `review.note`); capabilities↔manifest ověřeno konzistentní (Sez. 177, `diary/2026-06-29.md:82-90`). Zbytek: číselné pole `marker_recall`=null (data v próze), 311/313 blok na ruční GT |
| A3 | KPI feeder ≠ cíl; sirotek 66,2 vs 65,8 | **ČÁSTEČNĚ / mutuje** | Sirotek 66,2 vyřešen (Sez. 159 revert); headline 68,7 % single-source konzistentní (README:8 / architecture:263); two-machine label discipline (68,7 canonical vs 68,4 ntbhej). ALE `eval_real` (cíl) zamrzlá — viz **nový A2** níže; `run_kpi` pořád netiskne label sady (`measure_dod.py:538` vs `run_table:485`) |
| A4 | Bus factor 1 (kurace/split/pgw/manifest jen lokálně) | **ČÁSTEČNĚ** | `.pgw` 6/6 tracked (Sez. 164), `calibration_manifest` tracked. ALE `_curation.json`+`_split.json`+`_cz_filter.json` = **NOT TRACKED** (`git ls-files`; fyzicky existují jen na HAL3000) → viz **nový A3** |
| B1 | CLAUDE.md/README nezmiňují `isom_scan/`+`isom/` | **ČÁSTEČNĚ / TRVÁ** | README má `isom/` (`:117`), CLAUDE.md „Čtyři podadresáře" OK; ale `isom_scan/` (19 `.py`) **nikde v řídících docs**, CLAUDE.md nezmiňuje ani `isom/` ani `isom_scan/` |
| B2 | `detect_version` tichý default | **VYŘEŠENO** | `compare_isom.py:188` stderr VAROVÁNÍ před defaultem `return "2017-2"` (Sez. 175) + `test_compare_isom.py` |
| B3 | `_IMAGENET` 7× → train/serve skew | **VYŘEŠENO** | `model/norm.py:11-12` SSoT; všech 6 živých loaderů/eval z něj importuje (Sez. 158, audit D4); 1 reziduum jen v archivu `runnability/dataset.py:48`. Zbývá: tiling 3× + `MAP_SCALE` 3× (viz B) |
| B4 | arcgis paging bez `exceededTransferLimit` | **VYŘEŠENO** | `arcgis.py:99` `offset += len(batch)` + `exceededTransferLimit` check + loud-fail; `test_arcgis.py` (3 dávky+prázdná) (Sez. 175) |
| B5 | `compare_isom` stale DoD ≥90 %/5-map docstring | **NEPŘEOVĚŘENO** (pravděpodobně TRVÁ) | mimo hlavní fokus; `compare_isom` je legacy sonda, headline imunní |
| B6 | DIARY index >1000 znaků hooky | **TRVÁ (self-flagged)** | `DIARY.md:5-8` (Sez. 178) sám: „řádky ~140-177 jsou dlouhé odstavce … token-zátěž … pruning kandidát" → odloženo |
| B7 | `smoke.py` mimo `unittest discover` | **VYŘEŠENO** | `tests/test_smoke.py` wrapper (SkipTest bez `AZIMUT_RUN_SMOKE=1`) → v discoveru = ten 1 skip |
| B8 | `requirements-train.txt` / legacy ckpt provenance / RNG | **ČÁSTEČNĚ** | `requirements-train.txt` NEEXISTUJE (jen komentář `requirements.txt:13`); area ckpt už MÁ provenance (meta v `.pt`, Sez. 156 retrain); RNG streamy pořád sdílené (TODO otevřené) |

**Z 260612 zůstává živé a nepohnuté:** **A5** (5 invariantních smoke testů — jen smoke+B7 hotové;
**golden Šulcák / AREA_ZORDER⊆template / statický 301/301.1 guard / build_pair-Y fixture CHYBÍ**,
`grep tests/` = 0), **A6** = 260621-A4 (bus factor 1 kurace/split). A3-ref-set (rozšířit KPI referenci
nad 3 mapy) TRVÁ. **B3/260619** (`resources/isom/index.json` kurátorovaný + licence 113 SVG) = ČÁSTEČNĚ
(schema+builder ano, kurátorovaný index+licence ne).

---

## A. Námitky (strategické/závažné)

### A1 — VYSOKÁ: Exit-kritérium fázové závory (KPI ≥ 85 %) je sankcionovanými prostředky nejspíš nedosažitelné → riziko trvalého uvíznutí v `Generator()` nebo tichého posunu laťky

**Doklad:** `ROADMAP.md:59` váže postup do Etapy 2 na „KPI dostatečné a KOMPAS téměř plná"; číselně
je cíl **≥ 85 %** (`architecture.md:272`, `GLOSSARY.md:378`, `TODO.md:180`). Aktuální KPI = **68,7 %**
(canonical, `README.md:8`). Jenže Sez. 177 (`diary/2026-06-29.md:95-101`) sám doložil, že žebříček
`gen=0` děr je **systematicky data-gate**: 202 (195/0, sráz je linie bez ZABAGED zdroje), 201 (36/0),
107/108 (rýhy, ZABAGED 0 na Liberecku), 205 (atribut výšky chybí), 208 (133/0), 308 (158/0, prázdná
data) — a `architecture.md:238-239` uzavírá, že „plošná + liniová páka z čistě ČÚZK dat je VYČERPANÁ"
(potvrzeno 4×). Zbývajících ~16 pb k 85 % leží v line/point typech, které generátor umí nakreslit
jen přes **scan-mining** (injekce reálných symbolů ze skenů) — a ta je blokovaná na **ruční GT
uživatele**: 311/313 „blokuje ruční pozitivní GT, ne kód" (`diary/2026-06-29.md:87-89`), mapfield
Velbloud „STÁLE OTEVŘENO (6. sezení v kuse, 173→178)" (`diary/2026-07-01.md:58`).

**Dopad:** Sankcionovaná páka (generator coverage z ČÚZK) je vyčerpaná; jediná zbývající (scan-mining)
běží rychlostí blízkou nule, protože visí na uživatelově ruční práci. To vede k jednomu ze dvou
konců: **(a)** laťka 85 % se nikdy nedosáhne a projekt zůstane v `Generator()` neomezeně dlouho, nebo
**(b)** se práh tiše sníží ad-hoc. Obojí je forma Goodhartu na úrovni fáze (metrika řídí, i když ji
nejde legitimně naplnit). Poslední 3 sezení to už ukazují: Sez. 176 +0,7 pb (poslední reálný pohyb),
Sez. 177 a 178 = **0 pb** (pruning, data-gate anotace).

**Doporučení (rozhodnutí pro uživatele, docs-only, bez CUDA):** operacionalizovat exit-kritérium.
Buď **(a)** revidovat práh: 85 % byl stanoven PŘED poznáním data-gate stropu; realistický strop
pokrytí je nižší (data-gate díry principiálně nelze zavřít bez scan-miningu) → definovat „KOMPAS téměř
plný" jako **„všechny NE-data-gate díry v `ok`"** (to je skoro splněné — `DATA_GATE_CEILING` už kódy
odlišuje) a headline práh snížit/rozdělit na „ČÚZK-dosažitelnou" a „scan-mining" složku. Nebo **(b)**
přiznat, že další KPI postup = uživatelova ruční GT, a naplánovat ji jako **explicitní blocker
sezení**, ne odkládaný carry. Ať tak či tak: přestat vydávat nulová sezení za progres.

### A2 — VYSOKÁ: Vrcholová metrika `eval_real` zamrzla ~16 sezení; reálný transfer je prostřední a nezlepšuje se (restated 260612-A1/A3, 260621-A3)

**Doklad:** kanonické checkpointy naposled modifikovány `area_model` + `line_model` **2026-06-22**
(Sez. 156), `point_model` **2026-06-24** (Sez. 162). Od té doby (Sez. 163–178, ~16 sezení, ~8 dní)
`git log` neukazuje **žádný** retrain/promote reconstructoru — samé `feat(isom_scan)`, KPI kalibrace,
GT factory, docs, audity. Reálný transfer je přitom prostřední a statický: Png2Area **Bedř soft mIoU
0,525 / Blatná 0,363** (nové 404/407/409 „slabý reálný transfer, model je halucinuje", `architecture.md:204`),
Png2Point **210 kolabuje 0,00–0,25**, 417 „střední", 112/527 „střední-dobré" (`README.md:16`,
`TODO.md:186-193`). Feeder KPI (68,7 %) se leští, cílová metrika stojí.

**Dopad:** Vrcholová úloha projektu je rekonstrukce z **reálného** skenu; `eval_real` je jediná
metrika, která o ní vypovídá. Kombinace A1 (coverage páka vyčerpaná) + A2 (reconstructor zmražený)
znamená, že se **nezlepšuje ani feeder, ani cíl** — energie teče do KOMPAS meta-práce (data-gate
anotace Sez. 178, pruning Sez. 177). To je přesně „utápění v metodologii", před kterým projekt
varuje, jen přesunuté do KOMPASu. Fázová závora tenhle stav legitimizuje („reconstructor polishing
frozen"), ale audit musí upozornit: závora měla energii nasměrovat do **coverage** — a ta je hotová.

**Doporučení (rozhodnutí pro uživatele):** buď **(a)** uznat, že `Generator()` coverage je
~vyčerpaná, a cíleně otevřít závoru pro **měřitelnou reconstructor práci** (210 collapse, 404/407/409
halucinace, class-balanced expansion 208/501/301 — vše konkrétní eval_real cíle, ne „leštění"), nebo
**(b)** tvrdě prioritizovat scan-mining s uživatelovou GT jako jediný zbývající coverage lever (A1).
Nepokračovat v sériích nulových KPI sezení na CUDA stroji.

### A3 — VYSOKÁ: Reprodukovatelnost — `_curation.json`+`_split.json` necommitnuté napříč TŘEMI audity (levná oprava odložená počtvrté)

**Doklad:** `git ls-files` — `_curation.json`, `_split.json`, `_cz_filter.json` = **NOT TRACKED**
(gitignored pod `resources/*`); fyzicky existují jen lokálně (`resources/livelox/_curation.json` atd.).
`_curation.json` drží **neregenerovatelné ruční vizuální tagy** (Sez. 71 = neopakovatelná lidská práce
kurace 268 map), `_split.json` je eval kontrakt (bez něj jsou všechna mIoU neporovnatelná). Tato
námitka trvá od **260612-A6 → 260619-A6 → 260621-A4 → sem**. Pokrok od 260621: `.pgw` (6/6) i
`calibration_manifest.json` už tracked JSOU — tj. mechanismus commitu malých textů bez copyrightu je
prokázaný, jen se na tyto dva soubory neaplikoval.

**Dopad:** Ztráta disku HAL3000 = znovu ručně projít ~268 map (`_curation`) + neporovnatelnost všech
dosavadních mIoU (`_split`). Bus factor 1 na jediné neopakovatelné lidské práci v projektu.

**Doporučení (levné, bez CUDA):** commitnout `_curation.json` + zamrazit `_split.json` /
`_cz_filter.json` jako eval kontrakt (buď přímo — jsou to classId + tagy bez copyright obsahu — nebo
do privátní větve, jako se to udělalo pro `.pgw`). Přidat do `%END` krok „měřicí/kurační artefakty
zálohovány/tracked?". Rozhodnout s uživatelem TEĎ, ne příště.

---

## B. Připomínky (taktické)

**B1 — A5 invariantní testy pořád chybí (jen smoke+B7 hotové).** Z receptu 260612-A5 zůstávají
NEDOPLNĚNY: **golden Šulcák** (48 polygonů / 2,56 ha), **statický `AREA_ZORDER` ⊆ `template_classic.omap`
∧ kódy `omap_export`**, **statický 301/301.1 semantický guard**, **`build_pair`-Y fixture** (Y má
nenulové px pro každý area kód). `grep tests/` = 0 pro všechny čtyři; `test_omap_symbols.py` kryje jen
parser-úroveň (301 vs 301.1 jako dva symboly), ne semantický alias. Právě 301/301.1 byl důvod vzniku
A5 (bug žil 8 dní). **Akce:** doplnit aspoň statický `AREA_ZORDER`/301 guard (offline, levné) +
`build_pair`-Y mini-fixture — chytají 301-typ bug staticky i dynamicky.

**B2 — `isom_scan/` (19 `.py`, aktivní scan-mining větev) není v žádných řídících docs.** README
„Repository layout" má `isom/` (`:117`), ale `isom_scan/` grep=0; CLAUDE.md „Klíčové soubory"
nezmiňuje ani `isom/` ani `isom_scan/`. Přitom je to celá GT-factory + scan-transfer mašinérie, na
které stojí jediná zbývající coverage páka (A1). **Akce:** doplnit `isom_scan/` (+ `isom/`) do README
layout a CLAUDE.md „Klíčové soubory". (= reinkarnace 260621-B1, jen `isom/` mezitím do README přibylo.)

**B3 — DRY dluhy zralé na fázi A: tiling 3× a `MAP_SCALE` 3×.** `model/png2area/tile.py` (307 ř.) ≈
`png2line/tile.py` (291 ř.) — ~42 % řádků se liší, žádný extrahovaný modul (docstring sám přiznává
„izomorfní"). `MAP_SCALE = 10000` opsáno 3× (`generator.py:75`, `inject.py:49`, `purple.py:35`).
**Pozor:** `PX_PER_MM` má **dvě legitimně různé hodnoty** (generator 4,59 vs model 7,52, jiný
`TARGET_MPP`) — NESJEDNOCOVAT naslepo (paměť `canonical-mpp-tile-resolution`), pravý duplikát je jen
`MAP_SCALE`. Spouštěč extrakce = přechod na balík (fáze A); do té doby komentářový sync.

**B4 — `run_kpi` headline netiskne mapovou sadu; `requirements-train.txt` neexistuje.** (a)
`measure_dod.py:538` (KPI headline) na rozdíl od `run_table:485` netiskne `MAPS` — per-mapa řádky sice
jména ukazují, ale chybí explicitní label `KPI_3MAP_CANONICAL` vs `KPI_2MAP_NTBHEJ` (260621-A3 zbytek).
(b) `requirements.txt:13` odděluje train/runtime jen komentářem; fyzický `requirements-train.txt` +
import-guard by zabránil recidivě (matplotlib/clip_quad na ntbhej, Sez. 112). Obojí levné.

**B5 — `resources/isom/index.json` kurátorovaný + licence 113 SVG.** Committed je jen
`index.schema.json` (kontrakt) + builder; kurátorovaný `index.json` neexistuje, provenance/licence 113
SVG = „unknown" (`resources/isom/README.md`). Marginální, dokud se katalog nepoužije jako UC2 zdroj —
ale KB-zásada „každý zdroj nese licenci" (`CLAUDE.md`) platí. Začít živými bodovými třídami (204/210/
417/419) při první příležitosti.

**B6 — DIARY index bobtná (self-flagged, recidiva 260612-B5 → 260621-B6).** `DIARY.md:5-8` sám
poznamenal, že řádky ~140-177 jsou dlouhé odstavce = token-zátěž každý `%BEGIN`, a odložil pruning na
„příští %AUDIT:DOCS/%CALIBRATE". Obojí je právě teď zralé (`diary/2026-07-01.md:7` %CALIBRATE 15
sezení). **Akce:** při nejbližším úklidovém sezení zkrátit staré hooky na 1–2 věty (detail je v
`docs/diary/`).

---

## C. Doporučení pro kolegy (Opus, Sonnet, Codex, ChatGPT …)

1. **Nulové KPI sezení na CUDA stroji = špatná alokace.** Sez. 176/177/178 běžely na **HAL3000**
   (vzácný CUDA + canonical stroj) a nedělaly žádnou CUDA práci (přeměření/pruning/anotace). Paměť
   `cleanup-do-now-not-ntbhej-handoff` platí obráceně taky: docs/analýzu dělej kde chceš, **CUDA stroj
   šetři na to, co jiný neutáhne** (retrain, canonical KPI). Před fokusem se ptej: „potřebuje tohle
   HAL3000?"
2. **Data-gate strop je poctivost, ne cíl.** `DATA_GATE_CEILING` (Sez. 178) správně odlišuje doložený
   strop od akční díry — ale samotné rozšiřování stropů (anotace dalších `gen=0` kódů) **nezvedá ani
   KPI, ani eval_real**. Když sezení produkuje jen „proč to nejde", je to signál, že coverage páka je
   vyčerpaná (A1) — eskaluj rozhodnutí uživateli, neškáluj anotace.
3. **Scan-mining je jediná zbývající coverage páka, a visí na uživateli.** 311/313 i mapfield blokuje
   ruční GT (`diary/2026-06-29.md:87`, `2026-07-01.md:58`). Když je zablokovaný, **řekni to nahlas jako
   blocker a nabídni DROP**, nedefaultuj na náhradní docs práci — jinak „tah na branku" tiše stagnuje.
4. **`eval_real` je vrcholová metrika — sleduj, jestli se hýbe.** Reconstructory se netrénovaly 16
   sezení; kdykoli měníš scope (`N_AREA`/`N_LINE`/`POINT_CLASSES`), retrénuj + `eval_real` + `--promote`
   v témže/navazujícím CUDA sezení (260621-C1). Bez toho headline čísla popisují mrtvý checkpoint.
5. **Verify-against-source > zelený test.** Sez. 178 bug (`str` klíč vs `int` kód v `_provedeni`) prošel
   unit testem se string vstupem a odhalil ho až živý `--table` na reálných datech (`diary/2026-07-01.md:36`).
   Testuj s REÁLNÝM typem vstupu (paměť `measure-dod-codes-are-int-not-str`), ne pohodlným stringem.
6. **Malý textový artefakt bez copyrightu commitni HNED.** `.pgw` a `calibration_manifest` už tracked
   jsou; `_curation.json`/`_split.json` ne — čtvrtý audit v řadě. Neopakovatelná ruční práce nesmí žít
   na jednom disku (A3).
7. **Nová větev → hned do README layout + CLAUDE.md.** `isom_scan/` (19 souborů) chybí v obou napříč
   dvěma audity (B2). Orientace `%BEGIN` musí vidět celý hlavní tah.

---

## D. Co funguje — nerozbíjet

- **A1 z 260621 (KRITICKÁ) definitivně uzavřena.** Retrain Sez. 156/162 srovnal checkpoint ↔ scope
  (21/2/10), `.pt` navíc self-dokumentují meta (`n_area`/epoch/miou); `eval_real` zas běží. Přesně
  správná reakce na kritický nález.
- **Data-gate poctivost (Sez. 177–178).** `_provedeni` rozlišuje `strop` (doložená příčina) od `chybí`
  (akční díra); registr **mimo** `isom.capabilities` → nesahá na invariant `CAPABILITIES == USED_CODES`
  (test-vynucený, `test_symbol_capabilities.py:47`). Anti-Goodhart učebnice: metrika nelže o zralosti.
- **GT factory s ručním recall (Sez. 169–174).** Scan-mining kandidáti měřeni proti ruční GT (109 F1
  0,65, boulder 204 **doložený strop CV** F1 0,26 → NEexportováno) — přesně měření-first, které
  260621-A2 chtěl; ceiling se přiznává, ne obchází.
- **Sirotek discipline.** 68,7 % canonical vs 68,4 % ntbhej jsou explicitně odlišené labely
  (`README.md:10`), ne tichý sirotek jako kdysi 66,2/65,8. Konzistentní napříč README/architecture/DIARY.
- **DRY/SSoT se propisuje.** `model/norm.py` (ImageNet SSoT, 6 živých konzumentů), `omap_symbols.parse_symbol_ids`
  (sdílený export+cut), `peaks.py` (train↔eval png2point) — train/serve skew na vrcholové metrice
  eliminován.
- **No-silent-fallback tam, kde záleží.** `arcgis` paging loud-fail + `exceededTransferLimit`,
  `detect_version` stderr warn, `cut` odmítá chybějící 301.1/301.4, `smoke.py tolerant=False`,
  `measure_dod._missing_pgw`.
- **80 testů OK + 1 skip**, čistý strom, žádné paralelní vlákno; verify-against-source opakovaně chytá
  falešné poplachy (Sez. 178 type bug, Sez. 176 práh naslepo).

---

*Příští vydání: porovnat stav A1–A3 (VYŘEŠENO/TRVÁ/ZHORŠENO). Pozor zvlášť na A1 (operacionalizoval se
exit-práh / pohnul se scan-mining?), A2 (proběhl reconstructor retrain / hýbe se eval_real?), A3
(commitnut `_curation`/`_split`?).*
