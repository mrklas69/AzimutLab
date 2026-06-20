# AUDIT_FABLE5_260619

Datum: 2026-06-19  
Auditor: Codex GPT-5  
Rozsah: `README.md`, `docs/architecture.md`, `docs/ROADMAP.md`, `docs/TODO.md`, `docs/DIARY.md`, poslední diáře 2026-06-16 až 2026-06-18, předchozí `docs/AUDIT_FABLE5_260612.md`, `docs/IDEAS_from_chatgpt55.md`, přímé ověření `generator/`, `connectors/`, `model/`, `tests/`, `resources/isom/`, lokální `isom_scan/` a aktuální pracovní stav.  
Metoda: meta-audit směru a rizik; dokumentace ověřená proti kódu a lokálním artefaktům. Testy jsem nespouštěl: na tomto stroji v sezení nebyl dostupný funkční Python launcher (`.venv` ani `py -3.12`).

> **Status po Sez. 152 (2026-06-20):** tenhle audit zůstává historický artefakt.
> Část nálezů už byla mezitím uzavřena nebo posunuta: `Velbloud.pgw` byl lokálně
> doplněn, kanonický 3-map KPI trend pokračuje, generator smoke existuje a
> `isom_scan/` má oddělenou verzovatelnou harness hranici. Aktuální stav čti přes
> `docs/DIARY.md`, `docs/DONE.md`, `docs/TODO.md` a `README.md`, ne jako otevřený
> backlog z původních závěrů níže.

## TL;DR

Projekt se od minulého Fable auditu výrazně zlepšil v disciplíně: `ROADMAP.md` drží fázi `Generator()`, real-eval už existuje pro Png2Area/Point/Line a `measure_dod.py` má živý KOMPAS místo mrtvého binárního DoD. Největší nové riziko není nedostatek směru, ale špatná klasifikace nového průlomu: ISOM-scan/classic-CV vytěžování není "leštění rekonstruktoru", ale přímý enabler `generator()` a KOMPASu, pokud z něj lezou barvy, masky, symboly a kalibrační signály. Tuhle větev je potřeba rychle zakotvit jako "scan mining" v rámci `Generator()`, jinak ji současný zákaz reconstructor/degradation práce může nechtěně zadusit.

Druhý největší problém zůstává reprodukovatelnost měření: `measure_dod.py` defaultně pracuje s Bedřichovkou/Blatnou/Velbloudem, ale `Velbloud.pgw` na ntbhej chybí; historických 60,7 % a nových 55,3 % proto nelze porovnávat. Třetí problém je governance benchmarku: `isom_scan/` je správně gitignored kvůli copyrightu, ale uvnitř leží i přenositelné skripty a GT; `docs/TODO.md` navíc pořád tvrdí, že GT je template, zatímco `isom_scan/gt/ground_truth.json` už je `READY`. Bez rozdělení "citlivý raster" vs "bezpečný harness" se z průlomu stane lokální archeologie.

KPI Goodhart riziko trvá: pseudo hustoty 527/531 už jednou přestřelily 11x/3,3x a kalibrace na dvou mapách by problém jen zakonzervovala. Testy jsou lepší než minule, ale generátorové invarianty a smoke vrstva pořád chybí; při `generator.py` ~4,3k LOC je to reálný dluh. Pochvala patří no-silent-fallback chování (`measure_dod._missing_pgw`) a real-eval kultuře; obojí je potřeba zachovat.

## Stav námitek z minulého auditu

| ID | Stav | Doklad | Komentář |
|----|------|--------|----------|
| A1 Doménový gap se neměří | VYŘEŠENO částečně | `model/png2area/eval_real.py`, `model/png2point/eval_real.py`, `model/png2line/eval_real.py`; deník Sez. 126-131 | Real-scan eval existuje pro tři Png2* větve. Nově Sez. 146 přidal ISOM-scan benchmark. Zbývá zakotvit harness mimo gitignored chaos. |
| A2 Purple/geometrická degradace | VYŘEŠENO částečně / TRVÁ jako phase-2 | `model/purple.py`, `model/png2area/dataset.py:40`, `model/png2point/dataset.py:45`, `docs/TODO.md:11` | Purpura je implementovaná a měřená. Geometrická augmentace zůstává v TODO, ale podle ROADMAP teď nemá být hlavní práce; má být zmražená, ne aktivní priorita. |
| A3 KPI Goodhart | TRVÁ | `docs/diary/2026-06-18.md:247`, `:253`, `:264`; `docs/TODO.md:194` | KOMPAS zlepšen, ale 527/531 přestřel dokazuje, že KPI se dá zhoršit i "přidáním pokrytí". Bez `Velbloud.pgw` nelze férově kalibrovat. |
| A4 Architecture docs drift | VYŘEŠENO částečně | `docs/ROADMAP.md`, `docs/architecture.md`, `docs/TODO.md:37` | ROADMAP a docs audit Sez. 139 směr srovnaly. Drobné statické umístění de-purple/Pic2Omap absorpce zůstává kosmetika. |
| A5 Testy a invarianty | TRVÁ částečně | `tests/test_cut.py`, `test_checkpoints.py`, `test_north_grid.py`, `test_purple.py`, `test_vectorize.py`; `generator/generator.py` ~4293 LOC | Testů přibylo, ale generátorový smoke/invariant balík stále není hotový. |
| A6 Reprodukovatelnost artefaktů | TRVÁ | `resources/*.pgw` lokálně bez `Velbloud.pgw`; `connectors/split.py:14`; `connectors/curate.py:7` | `_curation.json`/`_split.json` jsou záměrně regenerovatelné, ale lokálně nejsou; `Velbloud.pgw` blokuje srovnatelný KPI trend. |
| A7 Png2Line bez THINK | VYŘEŠENO | `model/png2line/`, `model/png2line/vectorize_omap.py:3`, `tests/test_north_grid.py` | Png2Line byl vybudován, měřen, vektorizace i dashed experiment mají dokumentovaný výsledek. |
| B1 String-level `.omap` operace | TRVÁ | `docs/TODO.md:62`; `generator/cut.py`, `generator/gen_backgrounds.py` | Sdílený resolver/konvence stále chybí. |
| B2 `ISOM_REF` dvojník | VYŘEŠENO | předchozí audit + současný stav bez návratu nálezu | Nenašel jsem nový drift stejného typu. |
| B3 Livelox ToS/licence | TRVÁ | `docs/diary/2026-06-18.md:192-195`; `isom_scan/` gitignored | Copyright opatrnost je správná, ale harness a licenční hranice se musí oddělit. |
| B4 Requirements split | TRVÁ | repo stav + Python launcher nedostupný v sezení | Praktická reprodukovatelnost na ntbhej pořád není hladká. |
| B5 DIARY index bobble | VYŘEŠENO částečně | `docs/DIARY.md`; dlouhé Sez. 146 zápisy | Index je použitelný. Délka posledních položek je snesitelný šum, ne blokátor. |
| B6 Pseudo registry | TRVÁ částečně | `generator/measure_dod.py:354`, `KOMPAS_SOURCE`; `docs/TODO.md:194` | KOMPAS_SOURCE je správný začátek, ale pseudo hustoty nemají plný crosswalk-aware kalibrační registr. |
| B7 Deep research / AI trace hygiene | TRVÁ jako procesní riziko | `docs/IDEAS_from_chatgpt55.md`; lokální `Thinking.html` | Sez. 146 ukázal obrovský přínos, ale zdrojový trace je lokální HTML v Downloads. Musí se vytěžovat do durable docs rychle a verifikovat proti zdrojům. |

## A. Námitky

### A1 KRITICKÁ - ISOM-scan/classic-CV průlom není zakotvený v řídicím modelu práce

Doklad: Sez. 146 (`docs/diary/2026-06-18.md:346-417`) popisuje ISOM-scan benchmark jako průlom; `docs/IDEAS_from_chatgpt55.md` destiluje metody, zejména barvy, black-excluding-brown masku a shape descriptor; aktuálně existuje nový lokální nástroj `tools/separate_scan_colors.ps1` s `QuantizeStep` detektorem palety ze skenu. `ROADMAP.md` zároveň tvrdě drží fázi `Generator()` a potlačuje návrat k `Rekonstruktor()`.

Dopad: Hrozí falešná brzda. Pokud kolegové uvidí "scan processing", mohou to zahodit jako forbidden reconstructor work. Jenže pro `generator()` je to přesně ta část, která dává reálné barvy, separované vrstvy, symbolové kandidáty a kalibrační cíle. To je přímá cesta k lepšímu KOMPASu, ne záclona.

Doporučení: Založit v TODO/ROADMAP explicitní podtah `Generator() / scan mining`: lokální paleta ze skenu, separované PNG vrstvy, black-vs-brown maska, classic-CV symbol candidates, vazba na KOMPAS/ISOM-scan score. Zakázat jen model-polishing bez měření; nezakazovat extrakci signálu ze skenu pro generátor.

### A2 VYSOKÁ - Srovnatelný KPI trend je blokovaný chybějícím `Velbloud.pgw`

Doklad: `generator/measure_dod.py:72-78` má default `MAPS = ["Bedřichovka", "Blatná", "Velbloud"]`, ale při chybějícím `.pgw` mapu hlasitě vynechá. Lokální resources obsahují několik `.pgw`, ale ne `Velbloud.pgw`. Deník uvádí 2-map KPI 55,3 % a varuje, že je nesrovnatelný s historickým 3-map 60,7 % (`docs/diary/2026-06-18.md:247-270`).

Dopad: Tým může číst pokles/zlepšení KPI jako signál změny generátoru, ale jde zčásti o změnu měřicí sady. To je přesně Goodhart/measurement drift.

Doporučení: Před další kalibrací pseudo hustot doplnit `Velbloud.pgw` na ntbhej nebo explicitně zavést dva pojmenované benchmarky: `KPI_2MAP_NTBHEJ` a `KPI_3MAP_CANONICAL`. Headline číslo smí být jen z kanonické sady.

### A3 VYSOKÁ - ISOM-scan benchmark je cenný, ale jeho durable hranice je špatně rozdělená

Doklad: `isom_scan/` je gitignored kvůli Livelox copyrightu (`docs/diary/2026-06-18.md:192-195`), ale obsahuje i přenositelné skripty `build_gt.py`, `score.py`, `overlay.py`, `README.md` a GT. `docs/TODO.md:107` stále říká, že `gt/ground_truth.json` je template/bootstrap, zatímco lokální `isom_scan/gt/ground_truth.json` začíná `_status: "READY 2026-06-18 (generátorová GT, only_real)"`. `resources/isom/` má 113 SVG symbolů, ale audit nenašel jejich index/provenanci/licenci v docs.

Dopad: Benchmark je zároveň průlom a lokální past. Bez durable harnessu nejde opakovat score, rozšiřovat testy ani bezpečně sdílet práci mezi stroji. Bez licence u SVG katalogu hrozí další B3 varianta.

Doporučení: Rozdělit `isom_scan/` na: (1) ignorované rastery/PDF/runs, (2) verzované skripty a schema, (3) verzovanou anonymizovanou/minimální GT nebo manifest s jasnou licencí. Aktualizovat TODO stav GT z template na READY a samostatně rozhodnout `.gitignore` výjimku pro bezpečné textové soubory.

### A4 VYSOKÁ - KPI Goodhart trvá u pseudo hustot

Doklad: Deník Sez. 145 uvádí `527` přestřel 11x a `531` přestřel 3,3x (`docs/diary/2026-06-18.md:253-264`). TODO už správně říká nekalibrovat slepě na dvě mapy a nejdřív doplnit Velbloud (`docs/TODO.md:194-199`). `generator/generator.py` má více míst s komentáři ke KOMPAS přestřelům a pseudo bodům.

Dopad: Přidání pokrytí může snižovat KPI, protože proporční metrika trestá přebytek. To je dobrý signál metriky, ale špatný signál procesu: pseudo vrstvy se nesmí ladit podle dojmu nebo podle dvou map.

Doporučení: Pro každou pseudo vrstvu přidat mini-registry: zdroj, hustota/km2, crosswalk verze, mapová sada, datum měření, důvěryhodnost. Změnu hustoty povolit jen s `measure_dod --table` před/po na stejné sadě.

### A5 STŘEDNÍ - Starý A2 geometrický augment zůstává v TODO jako aktivní práce, i když ROADMAP ho správně zmrazil

Doklad: `docs/TODO.md:11-24` drží A2 jako `[~]` a popisuje geometrickou augmentaci jako zbývající část. Současná ROADMAP ale po Sez. 136 říká `Generator()` teď, `Rekonstruktor()` potom; Sez. 146 navíc dává silnější nemodelovou páku.

Dopad: Kolega může sáhnout po deformation/degradation práci jen proto, že je v TODO starší `[~]`, a obejít hlavní tah. To by bylo pokračování slepé uličky "model polishing".

Doporučení: Purpuru označit jako hotovou; geometrickou augmentaci přepsat na explicitní "frozen phase-2 / only with new real-scan metric trigger". Aktivní prioritu přesunout na scan mining a KOMPAS kalibraci.

### A6 STŘEDNÍ - Testy přibyly, ale generátorový smoke/invariant balík stále chybí

Doklad: Existují `tests/test_cut.py`, `tests/test_checkpoints.py`, `tests/test_north_grid.py`, `tests/test_purple.py`, `tests/test_vectorize.py`. Zároveň `generator/generator.py` má cca 4293 řádků a obsahuje mnoho pseudo registrů, splitů, kreslení a doménových bran. TODO stále vede invariantní testy a DRY dluhy.

Dopad: Každá další úprava generátoru riskuje regresi v jiné kapitole ISOM, hlavně v situaci, kdy se KPI někdy nedá spustit na kanonické sadě.

Doporučení: Před většími zásahy do `generator.py` přidat rychlý smoke: malý bbox, deterministic seed, valid `.omap`, nenulové vrstvy pro 101/305/401/502, žádný crash bez nepovoleného silent fallbacku. Nemá nahradit KOMPAS, jen chytat rozbití základu.

## B. Připomínky

### B1 `detect_version()` stále neumí rozlišit OOM-2017 vs OCAD číslování

Doklad: `generator/compare_isom.py:156`; `docs/TODO.md:202-205`.  
Dopad: Default KPI to zatím nezkresluje, protože Soví vrch není v sadě, ale past zůstává pro rozšíření měření.  
Doporučení: Než se Soví vrch vrátí do metrik, vyřešit OOM/OCAD variantu detekce.

### B2 ArcGIS paging je DRY a použitelný, ale nemá test pro `exceededTransferLimit`

Doklad: `connectors/arcgis.py` stránkuje přes `resultOffset`, ale konec detekuje jen `len(batch) < page_size`; starší audit zmiňoval riziko `exceededTransferLimit`.  
Dopad: Serverová změna nebo nestandardní odpověď může ztratit data bez doménového varování.  
Doporučení: Přidat fixture/unit test na více stránek a explicitní chování pro `exceededTransferLimit`, pokud ho ArcGIS vrací v payloadu.

### B3 `resources/isom/` potřebuje manifest a licenční status

Doklad: lokálně 113 SVG souborů typu `101-Contour.svg`, `204-Boulder.svg`; docs zatím popisují ISOM/ISSprOM znalostní bázi, ale ne tento katalog.  
Dopad: Katalog je užitečný pro shape matching a symbolové šablony, ale bez provenance se špatně používá jako UC2 zdroj.  
Doporučení: Přidat `resources/isom/README.md` nebo `docs/kb/...` záznam: odkud SVG pochází, licence, zda je safe commit/share, jaké revize ISOM pokrývá.

### B4 `Thinking.html` je vstup, ne artefakt projektu

Doklad: lokálně `C:\Users\hejna\Downloads\Thinking.html` má cca 25,7 MB; `docs/IDEAS_from_chatgpt55.md` už destiluje část metod.  
Dopad: Bez další destilace se ztrácí kontext, ale commitovat celý trace by byl špatný směr.  
Doporučení: Vytěžit jen metody, parametry a ověřené doménové závěry do `IDEAS.md`/TODO; trace nebrat jako source of truth.

### B5 `tools/separate_scan_colors.ps1` je užitečný, ale zatím bokem architektury

Doklad: aktuální pracovní strom má nový `tools/` skript; skript umí lokální quantized palette (`QuantizeStep`) a generuje separované PNG vrstvy/manifest.  
Dopad: Je to přesně reakce na vybledlé/tiskem posunuté barvy, ale bez zařazení k `generator()`/benchmarku zůstane ad-hoc utilita.  
Doporučení: Pokud zůstane, doplnit do README/TODO jako `scan mining` utilitu a přidat minimální smoke nad malým PNG fixture.

### B6 Requirements / prostředí zůstává třecí plocha

Doklad: během auditu nefungoval `.venv` Python ani `py -3.12`, zatímco projekt má Python skripty všude a ntbhej/mrkla dělení práce.  
Dopad: Auditor/kolega snadno ověří docs, ale nespustí testy ani metriky; to oslabuje verify-against-source.  
Doporučení: Udržet krátký "ntbhej smoke setup" v README nebo TODO: jaký Python, jak spustit jen testy bez CUDA, jak ověřit `measure_dod` dostupnost dat.

## C. Doporučení pro kolegy

1. Když práce vytěžuje sken do barev, masek nebo symbolových kandidátů pro `generator()`, neházej ji do zakázané reconstructor fáze. Je to `Generator() / scan mining`.
2. Neporovnávej KPI čísla, pokud se změnila mapová sada. Chybějící `Velbloud.pgw` znamená nový benchmark label, ne nový trend.
3. U gitignored dat vždy odděl bezpečný harness od licencovaného vstupu. `isom_scan/*.py` a schema nemají mizet jen proto, že PNG/PDF nesmí do gitu.
4. Fixed ISOM paleta je jen referenční teorie. Pro reálný sken detekuj lokální paletu a uchovej mean RGB/quantized RGB v manifestu.
5. Pseudo hustoty měň jen po crosswalk-aware měření na stejné sadě. Přestřel je stejně důležitý bug jako podstřel.
6. Před dalším zásahem do `generator.py` přidej nebo spusť smoke/invariant test. KOMPAS je metrika kvality, ne náhrada základní regresní ochrany.
7. AI trace zvenku ber jako zdroj hypotéz. Do projektu patří až ověřený výtěžek s dokladem proti ISOM/spec/geometrii/skenu.
8. No-silent-fallback se nesmí oslabit. `measure_dod._missing_pgw` je dobrý vzor: hlasitě varuje a výsledek označuje jako nesrovnatelný.

## D. Co funguje

- `ROADMAP.md` konečně účinně drží projekt mimo nekonečný model-polishing.
- Real-eval kultura se zlepšila: Png2Area/Point/Line mají měření na reálných skenech, ne jen syntetiku.
- `measure_dod.py` jako KOMPAS je správnější než starý binární DoD; penalizace přestřelu 527/531 ukázala užitečný signál.
- Vizuální verify zůstává reálně funkční procesní brzda: Sez. 146 chytil chyby GT zarovnání před slepou důvěrou.
- `docs/IDEAS_from_chatgpt55.md` je dobrý vzor, jak z externího AI průlomu udělat projektový výtěžek místo jednorázové fascinace.
- `model/mpp.py` a `CANONICAL_MPP` ukazují, že SSoT opravy už se propisují napříč modelem.
- `connectors/arcgis.py` je slušný DRY transportní základ; riziko je v testech, ne v samotném směru.
