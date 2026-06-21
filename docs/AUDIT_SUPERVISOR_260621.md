# AUDIT_SUPERVISOR_260621

**Datum:** 2026-06-21 · **Auditor:** Claude Opus 4.8 (1M) · **Rozsah:** `README.md`,
`docs/architecture.md`, `docs/ROADMAP.md`, `docs/TODO.md` (celé), `docs/DIARY.md`
(index 123–154), diáře 2026-06-19/20 (Sez. 147–154), předchozí audity
`AUDIT_SUPERVISOR_260612.md` / `AUDIT_SUPERVISOR_260619.md` / `AUDIT_DOCS_260620.md` /
`AUDIT_CODE_260614.md`, paměť (MEMORY). Přímé ověření kódu: `generator/`,
`model/`, `connectors/`, `isom/`, `isom_scan/`, `tests/`, checkpointy v
`resources/*_model/`. · **Metoda:** meta-audit směru/rizik/procesu; **8 paralelních
verifikačních agentů** ověřilo tvrzení proti zdroji (čtení souborů + grep + git +
načtení tvaru segmentačních hlav z `.pt`), ne z docs. Testy spuštěny na stroji
**mrkla** (Python 3.14.3, torch cu128, CUDA True): `unittest discover -s tests` =
**37 testů OK**. `tests/smoke.py` ověřen čtením (vyžaduje živou ČÚZK síť).

> **Pozn. k živému stavu při auditu:** během tohoto sezení **běží paralelní vlákno**
> (fokus „260621-Buschdörfl" / per-ISOM kalibrace). Pracovní strom se mezi začátkem
> auditu a během agentů změnil — přibylo `M docs/TODO.md` (nově tvrdí KPI **66,2 %** a
> „ledger zavedený"), `M .gitignore`, `M isom_scan/README.md`, `?? isom_scan/calibration_manifest.{json,py}`,
> `?? tests/test_calibration_manifest.py`. Vše **untracked / necommitnuté**. Audit
> hodnotí committed stav (`b4b8e40`) plus tento in-flight pracovní strom a explicitně to odlišuje.

---

## TL;DR

Disciplína projektu drží: fázová závora (`ROADMAP`) reálně udržela energii mimo leštění
reconstructoru, measure-first chytá přestřely (527, 210 revert, dashed 508/516 zavržen
měřením), a `eval_real` kultura existuje pro všechny tři reconstructory na **reálných
skenech** (anti-Goodhart). Z auditu 260619 je většina vypořádaná (Velbloud.pgw, scan-mining
framing, `isom_scan` governance, smoke, zmražená geometrie). **Tři nejzávažnější věci míří
ale na rozpor mezi rychlostí deklarace a rychlostí ověření:** **(A1)** rozšíření scope
v Sez. 152 (`N_AREA` 18→21, `N_LINE` 2→5) je v kódu i docs, ale kanonické checkpointy
area i line zůstaly staré — `eval_real` na ně **nelze spustit** (shape mismatch) → nové
typy 404/407/409 a 306/309/508* **nikdy nebyly změřeny na realitě**, a headline čísla
0,683/0,774 popisují starý menší scope; to je inverze foundations-before-curtains uvnitř
fáze `Generator()`. **(A2)** Scan mining běží před vlastní governance — `calibration_manifest.json`
nemá u žádného kódu změřený recall (samé `null`, `_status: IN_PROGRESS`), je untracked, a
přesto ho `TODO` tvrdí jako „zavedený/verzovaný"; je to ledger prahů, ne kalibrace. **(A3)**
KPI feeder (65,8 %) a cíl (čte reconstructor realitu?) se rozešly — generátor „pokrývá" typy,
jejichž reconstructor není na nový scope natrénovaný; navíc se v `TODO` objevila druhá,
nepropsaná hodnota **66,2 %** (sirotek). Pod tím trvá napříč třemi audity bus-factor-1
reprodukovatelnost (`_curation.json`/`_split.json`/`.pgw` jen lokálně) a orientační soubory
(`CLAUDE.md`, README layout) nezmiňují celou aktivní větev `isom_scan/`.

---

## Stav námitek z minulého auditu (260619, Codex GPT-5)

| ID | Námitka | Stav | Doklad |
|----|---------|------|--------|
| A1 | Scan-mining průlom nezakotvený v řídicím modelu | **VYŘEŠENO** (zakotvení) / **nové riziko v provádění → A2** | `ROADMAP.md:42-46`, `README.md:17-18`, `GLOSSARY` Scan mining; ale viz A2 (provádění bez governance) |
| A2 | `Velbloud.pgw` blokuje srovnatelný 3-map KPI | **VYŘEŠENO** / částečně | `measure_dod.py:74` 3-map sada, `_missing_pgw:78-81` hlásí; ale `run_kpi:478-485` netiskne label sady (B-úroveň) + `resources/` gitignored → záloha nevyřešená |
| A3 | `isom_scan/` špatná durable hranice | **VYŘEŠENO** / spirit regreduje | `.gitignore:17-34` split potvrzen, 16 textových souborů tracked; ale `resources/isom/index.json` neexistuje (unknown_license=113) a nová kalibrace zas untracked |
| A4 | KPI Goodhart u pseudo hustot | **TRVÁ** | 527 opraveno (`generator.py:549`), ale strojový registr hustot NEEXISTUJE (holé konstanty `generator.py:446-551`); nově 66,2 % sirotek + manifest s null recall zván „kalibrace" |
| A5 | Geometrická augmentace = zmražená phase-2 | **VYŘEŠENO** | `TODO.md:48-51` explicitně frozen |
| A6 | Generátorový smoke chybí | **VYŘEŠENO** (smoke) / **TRVÁ** (invarianty) | `tests/smoke.py:1-148` (tolerant=False), ale 5-invariant balík z 260612-A5 z velké části chybí (301/301.1 statický guard není) |
| B1 | `detect_version` OOM vs OCAD | **TRVÁ** | `compare_isom.py:188` binární + tichý default `return "2017-2"` |
| B2 | arcgis paging bez `exceededTransferLimit` testu | **TRVÁ** | `arcgis.py:79,81`; grep `exceededTransferLimit` = 0; žádný paging test |
| B3 | `resources/isom/` manifest + licence | **TRVÁ** | `index.json` neexistuje, `build_symbol_index` → unknown_license=113 |
| B4 | `Thinking.html` destilovat | **VYŘEŠENO** | `IDEAS_from_chatgpt55.md` existuje (nehodnoceno hloubkově) |
| B5 | `separate_scan_colors.ps1` mimo architekturu | **TRVÁ** částečně | `tools/` pořád chybí v README „Repository layout" |
| B6 | Requirements / prostředí tření | **TRVÁ** částečně | `.venv` na mrkla funkční; `requirements-train.txt` neexistuje (jen komentář `requirements.txt:12`) |

Z auditu **260612** zůstávají živé a v tomto vydání zhoršené/nepohnuté: **A5** (testy/invarianty
— jen `cut` + smoke, golden/AREA_ZORDER/build_pair chybí), **A6** (reprodukovatelnost bus factor 1).

---

## A. Námitky (strategické/závažné)

### A1 — KRITICKÁ: Rozšíření scope (Sez. 152) deklarováno v kódu+docs, ale 2 ze 3 reconstructorů na něj nejsou natrénované → vrcholový benchmark nově NEMĚŘITELNÝ

**Doklad:** Načtení tvaru segmentačních hlav z kanonických checkpointů:
`resources/area_model/unet_best.pt` → `segmentation_head.0.weight=(18,…)` = **n_area=18**,
ale kód `generator/omap_raster.py:80` má `N_AREA=21`. `resources/line_model/unet_best.pt`
→ `(2,…)` = **n_line=2**, ale `omap_raster.py:269` má `N_LINE=5`. `eval_real` staví model
s aktuálním `N_*` (`png2area/eval_real.py:167`, `png2line/eval_real.py:158`) a hned
`load_state_dict` → **shape-mismatch `RuntimeError`**. Point je v pořádku (`(4,…)` = `N_POINT=4`,
lící). README headline `0.683` (area) a `0.774` (line) jsou čísla **starého** scope
(`README.md:139` „before 21-class expansion"; `architecture.md:221` „N_LINE=2 tehdy").
Diář Sez. 152 sám varuje („Rebuild/retrain… invalidují staré tiles/checkpointy…
Nepropagovat staré metriky jako důkaz nového scope", `diary/2026-06-20.md:55-56`).

**Dopad:** Vrcholová úloha projektu = rekonstrukce z **reálného** skenu. Druhé KPI (čte
reconstructor realitu?) je jediná metrika, která o tom vypovídá — a pro 2 ze 3 modelů ho
**dnes nejde spustit**. Nové typy 404/407/409 (plochy) a 306/309/508* (linie) jsou
nakreslené v generátoru a přibarvené do KPI, ale **nikdy nebyly ověřené na realitě**.
Feeder KPI (65,8 %) tak roste, zatímco metrika cíle stojí zamrzlá na stale checkpointech.
To je inverze „foundations before curtains" **uvnitř** fáze `Generator()`: scope se deklaruje
rychleji, než se trénuje a validuje.

**Doporučení (akce v sezení, CUDA = mrkla/HAL3000):** Před další scope prací: retrénovat
`png2area` na `N_AREA=21` a `png2line` na `N_LINE=5`, projít `eval_real` na reálném skenu,
`--promote`. **Do té doby** v `README`/`architecture` označit 0,683/0,774 jako
„stale scope (n_area=18 / n_line=2), retrain pending", ať číslo netvrdí aktuální stav.
Zvážit pravidlo: *scope se nedeklaruje jako hotový bez retrain+eval_real+promote v témže
nebo navazujícím CUDA sezení* (viz C1).

### A2 — VYSOKÁ: Scan mining běží před vlastní governance — „kalibrace" bez změřeného recall, vydávaná za hotovou, přitom untracked

**Doklad:** `isom_scan/calibration_manifest.json` (`_status: IN_PROGRESS`, `updated 2026-06-21`)
má 9 záznamů (109/111/112/115/417/418/525/527/531), ale validator (`calibration_manifest.py`)
hlásí **26 warnings: u VŠECH 9 chybí `marker_recall` i `false_positive_count`** (samé `null`);
8/9 má `positive_marker_count=0`, jen 109 má 40 markerů, ale `review` je `unreviewed`,
`recall=null`. Je to ledger prahů, **ne** záznam změřené kalibrace. Přesto `docs/TODO.md`
(pracovní strom, paralelní vlákno) tvrdí „Per-ISOM calibration ledger je zavedený v
`isom_scan/calibration_manifest.json`" — a soubor je **untracked** (`git status: ?? …calibration_manifest.json`,
`?? …calibration_manifest.py`, `?? tests/test_calibration_manifest.py`). Capability registr a
manifest si protiřečí: `capabilities.py:196` má `417=SCAN_LIVE_POINT` → `preferred_kind=mapper_scan`
(povýšeno), ale manifest ho vede jako `candidate_needs_markers`; **112 a 115 v `capabilities.py`
úplně chybí** (`capability_by_code('112')` → `KeyError`), ač jsou v manifestu i SVG dumpu.
Empirický podklad kalibrace je **100 % gitignored** (`temp/`, `maps/Buschdörfl`, `maps/Hamr`).

**Dopad:** ROADMAP carve-out („scan mining je legální, když krmí pokrytí/KOMPAS") se stal
mezerou: Sez. 154 byla podstatná práce s **nulovým KPI posunem** (diář sám: „bez KPI povýšení
před kurací") a **bez** kurátorovaného reprodukovatelného artefaktu. To je přesně vzorec, který
projekt jinde trestá — per-symbol ruční ladění na jednotlivých skenech (`--min-area 25`,
`--score-threshold 0.87`), jen přemístěné z „leštění modelu" do „leštění scan-miningu".
Nazvat `null`-recall ledger „kalibrací" je latentní Goodhart (vypadá změřeně, není), přesně
před čím varoval 260619-A4. Untracked stav + claim „hotovo" v `TODO` porušuje
verify-against-source: druhý stroj uvidí „zavedený ledger" bez souboru.

**Doporučení:** Než se scan-transfer rozšíří na `311/312/313` (další krok paralelního vlákna),
**uzavřít smyčku u stávajících kódů**: změřit 602-marker recall/FP (measure-first), teprve pak
status „calibrated"; **commitnout** manifest + validator + testy (textové, `.gitignore:24` je už
whitelistuje) + odvozené ne-copyright detekce (`detections.json` souřadnice+score) do
`isom_scan/runs/`, ať jde kalibrace ověřit bez copyright skenů; **smířit** `capabilities.py`
↔ manifest (doplnit 112/115, u 417/419 poznamenat, že live signál je trénovaný Png2Point, ne
classic-CV PoC). Jeden zdroj pravdy o zralosti kódu.

### A3 — VYSOKÁ: KPI feeder a cíl se rozešly; 65,8 % nadhodnocuje připravenost + nově sirotek 66,2 %

**Doklad:** KPI vyrostl 57,6 → 65,8 % za 6 sezení (`diary` 148–152), směs skutečného nového
pokrytí (403 separace, 404/407/409) a rekalibrace hustot (527 103→3, `PSEUDO_BOULDER` 500→900,
508 přesun kanálu). Žebříček děr KOMPASu (`architecture.md:239`: 403/416/306/202/109/501/308/108/408/208)
je ale pořád **hlavně linie/body**, jejichž reconstructor není na nový scope natrénovaný (A1).
Generátor tedy „pokrývá" typy, které reconstructor zatím neumí přečíst. **Nově:** `docs/TODO.md:21`
(paralelní vlákno, toto sezení) zavádí druhou hodnotu „oprava 407/409 GT brány ji posunula na
**66,2 %**" — grep `66[.,]2` přes celý repo = **jediný výskyt**; README (`:8`), architecture (`:237`),
DIARY (`:7-9`), DONE i GLOSSARY drží 65,8 %, žádný diář 66,2 nepodkládá. Dvě „aktuální" hodnoty
primárního kvantifikátoru fáze ve stejném souboru. Navíc `run_kpi` headline (`measure_dod.py:478-485`)
**netiskne mapovou sadu** (na rozdíl od `run_table:427`), takže 2-map ntbhej a 3-map canonical
lze tiše porovnávat jako trend (zbytek 260619-A2).

**Dopad:** Jakmile KPI měří pokrytí typů, jejichž reconstructor neexistuje/není natrénovaný, je
65,8 % horní odhad připravenosti, ne důkaz, že páry lépe trénují. Sirotek 66,2 % je SSoT trhlina
na čísle, na kterém visí celá fáze — čtenář (i `%BEGIN` shrnutí) neví, co je aktuální. Comparability
past mezi stroji trvá.

**Doporučení:** (1) Restejnit **úspěch fáze na `eval_real` na AKTUÁLNÍM scope** (A1), ne na KPI
samotném — restate 260612-A3. (2) Vyřešit 66,2 vs 65,8: buď doložit měřením na `KPI_3MAP_CANONICAL`
+ propsat všude + diář, nebo větu z `TODO` smazat. (3) Orazítkovat `run_kpi` headline počtem+jmény
map (mirror `run_table:427`), ideálně dva labely `KPI_2MAP_NTBHEJ` / `KPI_3MAP_CANONICAL`.

### A4 — VYSOKÁ: Reprodukovatelnost — bus factor 1 trvá přes tři audity; ruční kurace i scan-mining práce žijí jen lokálně

**Doklad:** `_curation.json` drží **neregenerovatelná ruční pole** — vizuální tagy
`legend/logo/damage/composite` (`curate.py:66`), `keep_override` (`:150-151`), `reviewed`
z lidského 2. průchodu (`:16-18`); `build_curation` je jen **merguje** (`:143`), neumí
reprodukovat. Soubor je gitignored (`.gitignore:47 resources/*`, bez výjimky pro livelox).
`_split.json` není zamrzlý (`split.py:14`) → růst korpusu = re-split → kontaminace test setu
mezi sezeními. `Velbloud.pgw` obnoven, ale `resources/` gitignored → záloha pořád nevyřešená
(přiznáno `TODO.md:99` „kanál pořád nevyřešený"). Nově i celá scan-mining kalibrace
(`calibration_manifest.{json,py}` + 3 testy) untracked. Všechny tyto soubory jsou malý text
bez copyrightu (classId+name+tagy / souřadnice).

**Dopad:** Ztráta jednoho disku = znovu ručně projít ~268 map (`_curation`) + neporovnatelnost
všech dosavadních mIoU (`_split`) + ztráta kalibračního ledgeru. Tato námitka trvá od 260612-A6
přes 260619-A6 do dneška — levná oprava (commit malých textů) se opakovaně odkládá.

**Doporučení:** Commitnout `_curation.json` (+ `_split.json` a `_cz_filter.json` zamrazit jako
kontrakt evaluace; re-split jen vědomě) — buď přímo, nebo do privátní větve. Commitnout
`calibration_manifest`. Do `%END` přidat krok „měřicí/kurační artefakty zálohovány?".

---

## B. Připomínky (taktické)

**B1 — `CLAUDE.md` (čten každý `%BEGIN`) a README layout nezmiňují celou aktivní větev `isom_scan/`.**
`CLAUDE.md` „Klíčové soubory" (ř. 57-94) vyjmenovává connectors/generator/model, ale **ani `isom/`
ani `isom_scan/`**; navíc říká model/ má „**Tři** podadresáře" a vynechává `png2line/` (3. živý
reconstructor) i `N_LINE`. README „Repository layout" má `isom/` (`:107`), ale `isom_scan/` chybí
(grep=0), stejně `tools/` a `AGENTS.md`. → orientace začínajícího sezení má zastaralý obraz hlavního
tahu. **Akce:** doplnit `isom_scan/`+`isom/` do obou; opravit „Tři" → „čtyři podadresáře, tři živé
reconstructory".

**B2 — `detect_version` tichý default porušuje no-silent-fallback (= 260619-B1, TRVÁ).**
`compare_isom.py:188 return "2017-2"` bez varování, když mapa nemá 526/521 ani 509/508; dvojí
číslování OOM 524-531 vs OCAD 535-540 neřešeno. Headline imunní (Soví vrch mimo sadu), ale past
při návratu Sovího vrchu do metrik. **Akce:** aspoň `warn` na stderr (izomorf `_missing_pgw`),
ideálně + rozlišení OOM/OCAD (`id="OCD"` / přítomnost 535-540).

**B3 — Dozrálé DRY dluhy s rizikem skew na vrcholové metrice.** `_IMAGENET_MEAN/STD` je **7×**
(4× `dataset.py` konstanta + 3× `eval_real.py` inline magic-number) → změna normalizace v tréninku
se **tiše nepropíše** do `eval_real` = train/serve skew na oficiální sim-to-real metrice. `parse_symbol_ids`
regex duplikován (`omap_export.py:105` vs `cut.py:227`) s asymetrií: `omap_export` selže nahlas
(`:107-109 raise`), `cut` **tiše degraduje** (`cut.py:450-453`: chybějící 301.1/301.4 → voda dostane
černý obrys na řezné hraně, porušení „voda = no-draw zóna" bez varování). Tiling helper 3× (sám
přiznáno `png2line/tile.py:23`), `_place_points_in_mask` neextrahováno (`TODO.md:134`).
**Akce (levný balíček fáze B):** `model/norm.py` (ImageNet SSoT) + sdílený `parse_symbol_ids()` se
validací požadovaných kódů + sdílený tiling — uzavře 3 DRY dluhy i skew/silent-fallback díru naráz.

**B4 — arcgis paging latentně tiše ořezává (= 260619-B2, TRVÁ).** `arcgis.py:79 if len(batch) < page_size: break`
+ `:81 offset += page_size` (ne `+= len(batch)`); žádný `exceededTransferLimit` check, žádný test.
Maskováno jen tím, že `_PAGE=2000 == ověřený ZABAGED maxRecordCount`; RÚIAN jede na default 2000
„z předpokladu". ČÚZK měnil služby (únor 2026) → server-side změna `maxRecordCount` není hypotetická.
**Akce:** `offset += len(batch); if not batch: break` + fixture/unit test (3 dávky + prázdná).

**B5 — `compare_isom.py` drží zastaralý DoD ≥90 % / 5-map rámec.** Modul docstring (`:3-6`) a
`main()` (`:230`) tvrdí „hotovo při ≥90 % … 5 vzorových map (Slovanka/Soví…)", zatímco realita
(`measure_dod.py:19,74`) je KPI histogram intersection / 3 mapy / ≥90 % archivováno. První čtený
zdroj dává špatný rámec — stejná třída driftu jako 260619-A4. **Akce:** sjednotit s `measure_dod`.

**B6 — DIARY index porušuje vlastní pravidlo „1-2 věty hook" (recidiva 260612-B5 → 260614-D4 → propadlo přes 260620-D10).**
`PROMPTS.md:73` říká stručný hook; realita: **13 z 32 řádků > 1000 znaků** (max 1488, ř.21/Sez.140).
Index se čte celý každý `%BEGIN` = drahý kontext. **Akce:** zkrátit hooky (detail je v `docs/diary/`),
nebo vědomě revidovat pravidlo + lehká délková kontrola do `%END`.

**B7 — `tests/smoke.py` není v `unittest discover`** (název nezačíná `test`) → jediný E2E test
determinismu + nenulových vrstev `discover` mine (běží jen ručně z `%END`); navíc běží na živé
síti (flake/CI-nemožnost). **A5 z 260612 stále otevřená:** golden Šulcák / noise-mode / build_pair-Y /
**statický `AREA_ZORDER`⊆template + 301/301.1 guard** neexistují (`tests/` grep=0) — přitom právě
301/301.1 byl důvod vzniku A5 (žil 8 dní). **Akce:** doplnit aspoň statický `AREA_ZORDER`/301 guard
(offline, levné); `test_calibration_manifest` přepsat z `assertGreater(warnings,0)` na fázově nezávislý
invariant (jinak selže, až se kurace dokončí).

**B8 — Drobnosti:** `requirements-train.txt` neexistuje (jen komentář, 260612-B4 TRVÁ);
`area_model/unet_best.pt` je **legacy bez provenance** (prázdná metadata, žádný `manifest/promoted.json` —
obchází `checkpoints.py`, vznikl před ní → nereprodukovatelný; doplní se příštím retrainem A1);
pseudo hustoty 204/210 jsou pevné skaláry, 417-531 náhodné rozsahy (`generator.py:446` vs `:541`) —
nekonzistentní izomorfismus dvou sesterských vrstev; TODO položka D8 zastaralá (tvrdí chybějící
soubory v README, které jsou přítomné — vyřešeno Sez. 145).

---

## C. Doporučení pro kolegy (Opus, Sonnet, Codex, ChatGPT …)

1. **Scope se nedeklaruje bez tréninku.** Když změníš `N_AREA`/`N_LINE`/`POINT_CLASSES`,
   retrénuj + `eval_real` + `--promote` ve stejném (nebo navazujícím CUDA) sezení, jinak scope
   **neoznačuj jako hotový**. Deklarace bez tréninku = stale checkpoint + nepravdivé headline
   číslo (A1, doklad: area n_area=18 vs 21, line n_line=2 vs 5).
2. **„Kalibrace" = změřený recall/FP proti markerům.** Dokud je recall `null`, je to „kandidát
   s prahy", ne kalibrace. Neznač v `TODO` „Hotovo/verzované", co je untracked nebo neměřené (A2).
3. **Scan mining je legální jen když krmí KPI/KOMPAS NEBO produkuje kurátorovaný reprodukovatelný
   artefakt.** Per-symbol ladění na jednom skenu bez manifestu/kurace/metriky = PoC limbo, ne
   „tah na branku" (A2; ROADMAP `:82` „rozšiřovat POKRYTÍ, ne doladit symbol o procenta").
4. **KPI je feeder kompas, ne cíl.** Úspěch fáze vázat na `eval_real` na **aktuálním** scope.
   Když KPI roste a `eval_real` stojí na stale checkpointu, KPI měří špatnou věc (A3).
5. **Jedna metrika = jedno číslo.** Nezaváděj 2. KPI hodnotu (66,2) bez propsání všude + diář
   dokladu; jinak `%BEGIN` neví, co je current (A3).
6. **Paralelní vlákna: řídící docs (TODO/README) píše hlavní vlákno.** Untracked artefakt ≠
   „hotovo". Před zápisem `git status` + `git log` (paměť `parallel-threads-verify-shared-docs`;
   tento audit zastihl `TODO` modifikované paralelně s claimem o necommitnutém souboru).
7. **Malé textové artefakty bez copyrightu commitni** (kurace/split/pgw/manifest) — ruční práce
   a měřicí kontrakt nesmí žít jen na jednom stroji (A4).
8. **Nový balík/větev → hned do README layout + `CLAUDE.md` klíčové soubory** (čteno každý
   `%BEGIN`); jinak hlavní tah projektu chybí v orientaci (B1).
9. **`eval_real` musí číst stejné konstanty jako trénink** (normalizace, MPP) přes sdílený modul —
   jinak tichý train/serve skew na vrcholové metrice (B3).
10. **No-silent-fallback i v paging/detect_version/cut bordered-area** — chybějící předpoklad =
    hlasité varování, ne tichá náhradní cesta (vzor `_missing_pgw`, B2/B4/B3).

---

## D. Co funguje — nerozbíjet

- **Fázová závora (`ROADMAP`) reálně drží** — energie mimo nekonečné leštění reconstructoru;
  self-check `%BEGIN` krok 0.5 je účinný.
- **measure-first jako zákon:** KOMPAS chytil 527 přestřel, 210 hustota revertována měřením
  (`diary/2026-06-19.md:243`), dashed 508/516 zkoušen a **zavržen měřením** (Sez. 133). Negativní
  výsledky se dokládají, ne mažou.
- **`eval_real` na REÁLNÝCH skenech existuje pro všechny tři reconstructory** (X = `resources/<name>.png`+`.pgw`,
  Y = kartografova `.omap` přes crosswalk) — správný anti-Goodhart benchmark; chybí „jen" retrain pro nový scope.
- **No-silent-fallback dobře implementován tam, kde na tom záleží:** `_missing_pgw` (`measure_dod.py:78`),
  `smoke.py:111 tolerant=False`, `checkpoints.py:239` promote vyžaduje `status=='completed'`,
  `cut.py` formát-chyby `raise OmapFormatError`.
- **SSoT opravy se propisují:** `model/mpp.CANONICAL_MPP` (inject/purple/eval_real importují, ne
  hardcode), `purple.overprint_course` kreslí jen do X, capability registr je v KOMPASu **jen
  informativní sloupec** — scan kandidáti se do KPI počtů nepřičítají (žádný Goodhart leak).
- **`isom_scan` governance scaffold:** `.gitignore` split (text vs copyright raster) sedí přesně,
  exporter píše do `--out` kopie (nepřepisuje zdroj).
- **37 testů prochází**, verify-against-source opakovaně chytá falešné poplachy (Sez. 141/143/144).

---

*Příští vydání: porovnat stav A1–A4 + B1–B8 (VYŘEŠENO/TRVÁ/ZHORŠENO) dle `AUDIT_SUPERVISOR_PROMPT.md`
bodu 3. Pozor zvlášť na A1 (proběhl retrain na nový scope?) a A2 (má manifest změřený recall a je
committed?).*
