# PROMPTS — AzimutLab (projektová makra)

Rozšiřuje kanonické globální definice maker z `~/.claude/PROMPTS.md`.
Tento soubor obsahuje pouze projektové override a rozšíření.

## %BEGIN — start sezení
0. **Sync s remote — PRVNÍ, před načtením kontextu.** `git fetch` + porovnej `HEAD`
   s `origin/main`. Je-li lokální pozadu, srovnej se (reset/pull) **před** jakoukoli
   prací — jinak sezení běží na zastaralém stavu. (Stalo se 2026-05-25: klon byl
   20 commitů pozadu → redundantní sezení odhalené až při pushi v %END.)
   Pozor: `git status` „clean" ≠ up-to-date.
0.5. **Načti `docs/ROADMAP.md` — etapa + zákazy (antidrift).** Měj od první minuty v hlavě,
   v jaké ETAPĚ projekt je (`Generator()` vs `Rekonstruktor()`) a co jsou ZAKÁZANÁ SLOVA
   (dnes: `Rekonstruktor()` + „degradace" — jsme v etapě Generator()). **Self-check u KAŽDÉHO
   návrhu fokusu:** „je tohle max vytěžení / plnění KOMPASu, nebo degradace / leštění modelu /
   rekonstruktor?" → druhé = STOP (špatná fáze). Důvod existence: opakované sklouznutí (~6×).
1. Načti kontext: README.md (root), `docs/architecture.md`, `docs/TODO.md`, `docs/DIARY.md` +
   poslední 1–2 diáře (docs/diary/), `docs/IDEAS.md` dle potřeby.
   (Pracovní dokumenty TODO/DONE/DIARY/IDEAS/RESEARCH/GLOSSARY žijí v `docs/` od Sez. 47;
   v rootu zůstaly jen README.md a CLAUDE.md.)
2. Audit cadence check (prahy z globálního CLAUDE.md) — spočítej od posledního
   výskytu auditu v diáři: %AUDIT:CODE ≥8 sez / ≥500 LOC, %AUDIT:DOCS ≥10,
   IDEAS/TODO pruning ≥12, %CALIBRATE ≥15. **Práh dosažen (≥)** = zralý kandidát (nabídni jako
   bod fokusu). **Práh překročen o ≥2** = vynucený první bod sezení (úklid má přednost).
   (Pozn.: cadence počítej od posledního výskytu daného auditu v diáři — od založení,
   pokud žádný (%CALIBRATE/pruning poprvé Sez. 17). %AUDIT:CODE reálně spouští LOC
   práh ≥500, ne počet sezení — `generator/` + `connectors/` už mají kód.)
   **Projektové rozšíření (Sez. 117):**
   - **Meta-audit AUDIT_SUPERVISOR: ≥25 sez** od posledního `docs/AUDIT_SUPERVISOR_*.md`, NEBO
     milník (fáze B→A, nový reconstructor, výsledek A1 benchmarku). Spouští se zadáním
     `docs/AUDIT_SUPERVISOR_PROMPT.md`. Jiná optika než %AUDIT:CODE/DOCS/%CALIBRATE
     (strategie, Goodhart, mezivrstvy) — nenahrazují se navzájem.
   - **Úsudkové práce nejsilnějším modelem.** %AUDIT:CODE / %AUDIT:DOCS / %CALIBRATE /
     AUDIT_SUPERVISOR + velká rozhodovací %THINK sezení (typ revize taxonomie UC, volba
     přístupu Png2Line) patří na nejsilnější dostupný model —
     úsudek nad velkým kontextem + verifikace nálezů proti zdroji (doklad: Sez. 93
     4 agentí falešné poplachy; Sez. 110 ChatGPT audit 1 zásah + šum). Audity jsou
     ntbhej-friendly → volba modelu nic neblokuje. Je-li audit zralý a sezení běží
     na slabším modelu, **nabídni handoff** („audit příště na silném modelu") místo
     provedení hned — výjimka: práh překročen o ≥2 a uživatel handoff nechce.
3. Stale Příště check — položka v „Příště" ≥5 sezení po sobě → DO/DROP. **Počítej VŠECHNY body,
   i vedlejší/carry** (ne jen fokus bod 1). Nález Sez. 69: „compare/Slovanka" visela jako vedlejší
   bod 3 devětkrát, protože Stale check sledoval jen hlavní fokus → eskalace zpožděna.
4. **Stroj × dostupnost fokusu.** Zjisti stroj (`hostname`) a co je tu lokálně k dispozici:
   **Livelox korpus** (`resources/livelox/`, gitignored copyright) **+ CUDA trénink = jen `mrkla`**;
   ČÚZK REST (fetch/`generate_map` real/separace) + docs + audity = **všude** (veřejná služba,
   cache `.dmr_/.zabaged_`). Nenavrhuj jako fokus to, co stroj neutáhne (nález Sez. 86 C-1: na
   ntbhej padl hlavní tah Branžež `build_pair` na chybějící korpus). Cross-stroj práce = carry na mrkla.
   **Úklidové audity (%CALIBRATE/%AUDIT:DOCS/pruning/%AUDIT:CODE) prioritně na ntbhej** (běží kdekoli,
   nepotřebují CUDA/korpus) — vzácné HAL3000/mrkla okno patří CUDA práci. Nález Sez. 108 (root-cause C-2):
   3 sezení po sobě na HAL3000 odkládala úklid jako carry → %CALIBRATE nabobtnal na +23, protože CUDA
   práce vždy přebila. Když jsi na mrkla a úklid je překročený, zvaž handoff na ntbhej místo dalšího carry.
5. Návrh fokusu z posledního „Příště" + [!] priorit v TODO. Vždy přes optiku
   UC DAGu: je navržený fokus enabler, nebo záclona?
6. **KPI + KOMPAS rekapitulace (Sez. 100, přání uživatele).** Vždy uveď aktuální stav primárního
   kvantifikátoru fáze `generator()` — **KPI** (proporční podobnost distribuce ISOM symbolů,
   `measure_dod.py` default; cíl 55 % plošná / ≥ 85 % s reconstructory) + **headline KOMPASu**
   (`--table`, největší proporční díry). Zdroj: poslední zaznamenaná hodnota z diáře/DIARY indexu
   (levné, vždy dostupné). **Přeměř** (na stroji s `resources/*.pgw`), jen pokud se od posledního
   měření měnil generátor (`connectors/`+`generator/` `.py`) → ukaž TREND vůči minulému sezení.

7. **Audit supervisor check (Sez. 117).** Existuje-li `docs/AUDIT_SUPERVISOR_*.md`, načti
   z NEJNOVĚJŠÍHO soubor TL;DR + **sekci C (doporučení pro kolegy)** a drž ta pravidla
   po celé sezení — platí opakovaně, ne jednorázově. Auditové úkoly žijí v TODO sekci
   „Audit supervisor — námitky → úkoly": řeš je jako běžné [!] položky (jedna položka =
   jeden fokus), hotové přesouvej do DONE **s kódem námitky** (A1, B4, …), ať je
   příští audit (`docs/AUDIT_SUPERVISOR_PROMPT.md`) umí odškrtat.

## %END — konec sezení
= globální %DOCS + commit pravidla. Projektová specifika:
- Diář: docs/diary/YYYY-MM-DD.md, index DIARY.md. Více sezení/den =
  sekce `## Sezení N` v témže souboru (nikdy ne suffix b/c/d).
- **Indexový řádek `DIARY.md` = stručný hook (1–2 věty + klíčové ISOM kódy), NE kopie
  záznamu.** Plný detail patří do `diary/`. Index se čte celý každý `%BEGIN` → dlouhé
  odstavce = zbytečná tokenová zátěž (nález %CALIBRATE Sez. 51). Staré řádky nepřepisovat.
- **Propagace do VŠECH vrstev (Sez. 34, root-cause %CALIBRATE):** zápis do `DIARY.md`+diáře
  nestačí. Projdi checklist a propiš dnešní změnu, kam patří (conceptual integrity, SLAP):
  - **Přidal/změnil reálnou vrstvu?** → `DONE.md` (záznam) + `architecture.md` UC2 (výčet `--…real`)
    + spec `generator-procedural.md` (sekce §4.9*) + `GLOSSARY.md` (termín) + README (status) +
    oba README (`connectors/`, `generator/`) + `zabaged-isom-catalog.md` (stav vrstvy)
    + **CALL-SITES kódu**: `batch.py` OBĚ větve (noise i real) — nová vrstva s default `real`
      MUSÍ být v batch volání explicitně `"off"`, jinak noise větev padne na validaci a real ji
      zbytečně stahuje (Sez. 35 B1: `rocks`/`bridges` to nedostaly → crash, nezachycen 30→34).
  - **Migrace/přejmenování (typ WFS→REST)?** → grep celý strom, ne jen dotčený soubor (drift Sez. 26
    přežil 7 sezení v 5 docs → audit Sez. 34).
  - **Po `%END` ověř:** každé `## Sezení N` v diáři má řádek v `DIARY.md` indexu **i** v `DONE.md`
    (Sez. 30 vypadlo z obou — audit Sez. 34).
- Identita sezení = datum + pořadí v daném dni.
- **Přidal-li jsi nové ISOM pokrytí** (nový symbol/kód v generátoru) **a jsi na stroji s `resources/*.pgw`:
  změř KPI dopad HNED** (aspoň Bedř/Blatná přes `measure_dod`, nečekej na plnou sadu ani na CUDA okno) —
  jinak se hromadí NEMĚŘENÉ pokrytí a nevíš, zda plníš díry nebo přidáváš přestřel ([[kpi-fill-undershoot-dilutes]]).
  Nález %CALIBRATE Sez. 145: KPI stálo 7 sezení (138→144) přes 4 nové typy + carry „přeměření" 4×.
- **Měnil-li se kód generátoru / konektorů / `.omap` exportu:** spusť
  `.venv\Scripts\python.exe tests\smoke.py` před commitem. Smoke chytá rozbitý základ
  (malý real-data bbox, deterministic seed, validní `.omap`, 101/305/401/502, žádný
  `layer_errors` fallback); KOMPAS dál měří kvalitu a proporce.
- Měnil-li se kód: dva commity (feat/fix → docs(session)), pak push. V deštníkové
  fázi je „kód" často jen KB/docs → jeden commit `docs(session)` stačí.
- **Cleanup (Sez. 25):** maž jen scratch výstupy — `temp/`, `output_*/` (jednorázové rendery,
  probe skripty). **Cache reálných dat NECH** (`.dmr_cache`, `.zabaged_cache`) i `__pycache__` —
  jsou regenerovatelné, ale zrychlují; rutinní mazání = zbytečný re-fetch z ČÚZK (opak účelu cache).
