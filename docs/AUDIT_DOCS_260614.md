# %AUDIT:DOCS - AzimutLab - 2026-06-14

## Rozsah a metoda

Audit zahrnul projektové Markdown soubory v kořeni repozitáře a v adresářích
`docs/`, `connectors/`, `generator/` a `model/`. Historické záznamy v
`docs/diary/` a `docs/DONE.md` byly posuzovány jako historie: nemají se zpětně
přepisovat, ale prokazatelně chybné závěry potřebují viditelnou korekci nebo
odkaz na novější stav.

Kontrola zahrnula:

- soulad aktivních dokumentů s aktuálním kódem a datovými kontrakty;
- konzistenci README, architektury, TODO, slovníku a modulových README;
- úplnost a chronologii evidence sezení;
- relativní Markdown odkazy;
- terminologii, jazyk a strukturu dokumentace.

## Souhrn

| Závažnost | Počet |
|---|---:|
| Kritické | 2 |
| Doporučené | 6 |
| Kosmetické | 2 |

Největší problém není chybějící dokumentace, ale několik navzájem si
odporujících „aktuálních pravd“. Nepravdivé údaje o fyzickém rozlišení a
Png2Point metrice už ovlivňují technická rozhodnutí, takže nejde jen o
redakční dluh.

## Kritické nálezy

### K1 - Aktivní dokumentace zaměňuje 1,33 m/px za rozlišení modelových dlaždic

**Důkaz**

- `README.md:132`, `docs/TODO.md:315` a `docs/IDEAS.md:369,377` odvozují
  rozměry Png2Point symbolů z rozlišení přibližně 1,33 m/px.
- Aktuální generátor používá `MAP_SCALE = 10000` a `PX_PER_MM = 4.5855`, tedy
  přibližně **2,1808 m/px**.
- Metadata korpusu potvrzují přibližně 2,180-2,182 m/px.
- `model/png2area/tile.py` i `model/png2point/dataset.py` vstup pouze ořezávají,
  nepřevzorkovávají ho na 1,33 m/px.
- `generator/README.md:12-14` správně říká, že 1,33 m/px je jen pracovní
  rozlišení barevné separace a výsledné polygony se škálují zpět.

**Dopad**

Dokumentace označuje chybný předpoklad jako ověřený zdrojem. Z něj se následně
počítají velikosti augmentovaných symbolů a vyhodnocuje jejich fyzická
věrnost. To může znehodnotit další trénink i interpretaci benchmarku.

**Konkrétní oprava**

1. Zavést jediný kanonický popis tří různých rozlišení: zdroj Livelox,
   pomocný rastr separace a výsledný/modelový rastr.
2. V aktivních dokumentech nahradit tvrzení „model/tile @ 1,33 m/px“ skutečnou
   hodnotou odvozenou z konfigurace nebo metadat.
3. K historickému závěru ze sezení 123 přidat korekční poznámku; historii
   nepřepisovat.
4. Přepočítat všechny dokumentované velikosti symbolů v pixelech až po
   potvrzení zamýšlené fyzické velikosti.

### K2 - Png2Point mF1 0,897 je stále prezentováno jako platná referenční metrika

**Důkaz**

- `docs/TODO.md:29-43` a `docs/IDEAS.md:528-545` už uvádějí tři deterministické
  běhy 0,151 / 0,247 / 0,318, medián 0,247, a hodnotí 0,897 jako pravděpodobný
  outlier.
- Přesto je 0,897 nadále uváděno jako hotový výsledek v `README.md:132,201`,
  `AGENTS.md:65-66`, `CLAUDE.md:77-78`, `docs/architecture.md:115,180`,
  `docs/GLOSSARY.md:317,426,506` a na více místech `docs/TODO.md`.

**Dopad**

Kanonické dokumenty nadhodnocují kvalitu modelu přibližně třikrát až šestkrát
oproti reprodukovaným běhům. Chybná hodnota vstupuje do architektonického
statusu, srovnání syntetické a reálné domény i priorit další práce.

**Konkrétní oprava**

Dokud nebude stabilizace uzavřena, používat jednotnou formulaci:
„historický běh 0,897 je nereprodukovaný outlier; aktuální tříseedový medián je
0,247; finální baseline čeká na opravu determinismu a nový benchmark“.
Historické DONE/diary záznamy zachovat, ale propojit je s korekcí.

## Doporučené nálezy

### D1 - Dokumenty si odporují v kontraktu Png2Area datové pipeline

**Důkaz**

- Aktuální `generator/omap_raster.py` definuje 17 ISOM area kódů plus
  background, tedy `N_AREA = 18`.
- Aktuální vstup Png2Area je `rgb.png`; degradace probíhá on-the-fly v datasetu
  a nevyrábí se trvalý `scan.png`.
- `generator/README.md:15-22,159` stále popisuje `degrade=True`, `scan.png` a
  16 kódů plus background.
- `README.md:184-197` střídá starou `scan.png` pipeline a tvrzení „18 area
  codes + background“, což by znamenalo 19 tříd.
- `docs/GLOSSARY.md:306,399,414-415` obsahuje současně varianty 16 kódů,
  18 kódů plus background a `N_AREA = 18`.
- `docs/architecture.md:159` rovněž uvádí 18 ISOM kódů plus background.

**Dopad**

Čtenář nemůže z dokumentace spolehlivě určit počet tříd, rozsah labelů ani
skutečný pár X/Y. To je porušení DRY a conceptual integrity na hranici
generátor-model.

**Konkrétní oprava**

Zapsat jeden kontrakt: **17 ISOM kódů + background, labely 0-17,
`N_AREA = 18`, X = `rgb.png`, degradace on-the-fly, Y =
`area_labels.png`**. Modulové README, architekturu, slovník a kořenové README
odvodit z tohoto jediného zdroje.

### D2 - `docs/TODO.md` funguje zároveň jako aktivní plán i archiv

**Důkaz**

- Vlastní pravidlo na `docs/TODO.md:3` říká, že `[x]` se přesouvá do DONE.
- Soubor nyní obsahuje 23 položek `[x]`, vedle 43 otevřených `[ ]`,
  17 rozpracovaných `[~]` a 2 blokovaných `[!]`.
- Dokončené bloky zachovávají staré pipeline a metriky, čímž vytvářejí část
  rozporů popsaných výše.

**Dopad**

Aktivní backlog je obtížně čitelný a není jasné, které tvrzení je plán,
historie nebo aktuální stav. Totéž se udržuje paralelně v TODO, DONE, DIARY a
README.

**Konkrétní oprava**

Přesunout všech 23 dokončených položek do `docs/DONE.md`, v TODO ponechat jen
otevřené, rozpracované a blokované úkoly. Pokud je potřeba kontext, ponechat
jednořádkový odkaz na příslušné DONE/sezení.

### D3 - `docs/DONE.md` nemá úplnou evidenci sezení

**Důkaz**

Porovnání nadpisů v denících s nadpisy v DONE našlo deníková sezení bez
odpovídající sekce v DONE: **19, 21, 32, 34, 48, 118 a 124**. Poslední dvě jsou
současná:

- `docs/diary/2026-06-12.md:145` - sezení 118;
- `docs/diary/2026-06-13.md:3` - sezení 124;
- obě jsou současně uvedena v `docs/DIARY.md`.

Projektový `%END` přitom požaduje zápis každého sezení do DIARY i DONE.

**Dopad**

Historie dokončené práce není úplná a automatické dohledání výsledků podle
sezení vrací rozdílné odpovědi podle použitého dokumentu.

**Konkrétní oprava**

Doplnit sedm chybějících sekcí z existujících deníků. U starších sezení stačí
stručný souhrn a odkaz; nevymýšlet detaily, které nejsou v primárním záznamu.

### D4 - Index `docs/DIARY.md` není chronologický a přestal být stručným indexem

**Důkaz**

- Po sestupné řadě 124 až 92 následuje pořadí 52, 53, 54, 55, 56, 58, 57,
  59, 61, 60 atd.; sezení 103 je až na konci.
- `docs/PROMPTS.md` požaduje 1-2 věty jako hook, ale některé řádky mají přes
  1 200 znaků; celý index má přibližně 69 kB v pouhých 82 řádcích.
- Detailní obsah už existuje v denících a DONE, takže index jej duplikuje.

**Dopad**

Index neplní navigační funkci, obtížně se kontroluje a při každém zápisu roste
riziko špatného vložení nebo dalšího rozporu.

**Konkrétní oprava**

Seřadit tabulku deterministicky sestupně podle čísla sezení a zkrátit hooky na
skutečné 1-2 věty. Detail ponechat v cílovém deníku. Přidat lehkou kontrolu
unikátnosti a pořadí.

### D5 - Kořenové README supluje changelog a tím rychle zastarává

**Důkaz**

- Stavový sloupec UC5 na `README.md:132` má přes 5 700 znaků a chronologicky
  opakuje desítky sezení.
- Stejný obsah žije v `docs/DONE.md`, `docs/DIARY.md` a denících.
- Právě tento blok stále obsahuje 0,897, starý počet area tříd a další
  překonané mezivýsledky.
- Repository layout na `README.md:184-201` popisuje již neplatnou `scan.png`
  pipeline.

**Dopad**

README není rychlý vstup do projektu, ale čtvrtá kopie historie. Změna konceptu
se proto nepropíše do všech vrstev a aktivní dokument působí autoritativně,
i když je zastaralý.

**Konkrétní oprava**

Omezit README na aktuální snapshot UC DAG, dnešní stav každého UC, hlavní
vstupy a odkazy na architekturu, TODO, DONE a DIARY. Chronologii ponechat pouze
v DONE/DIARY.

### D6 - Projektové dokumenty neukazují jednotný zdroj definic maker

**Důkaz**

- `docs/PROMPTS.md:3` a `CLAUDE.md:3` tvrdí, že projekt rozšiřuje makra z
  `~/.claude/CLAUDE.md`.
- `AGENTS.md:3` odkazuje na `~/.Codex/AGENTS.md`.
- Samotné definice použité při tomto auditu byly načteny z
  `~/.claude/PROMPTS.md`.

**Dopad**

Různí asistenti mohou načíst jinou definici stejného makra. To je zvlášť
rizikové u `%BEGIN`, `%END` a auditů, protože ty mění proces a evidenci.

**Konkrétní oprava**

Stanovit jeden explicitní kanonický soubor pro definice maker a v
`AGENTS.md`, `CLAUDE.md` i `docs/PROMPTS.md` popsat stejnou prioritu:
globální definice -> projektový override. Dokumenty jednotlivých asistentů
mají být pouze router, ne konkurenční zdroj pravdy.

## Kosmetické nálezy

### C1 - Slovník zaměňuje soft grouped mIoU a soft pixel accuracy

`docs/GLOSSARY.md:502-503` píše „soft mIoU ... pixel-acc 0,88-0,90“.
`docs/DONE.md:70` a deník správně rozlišují grouped mIoU a pixel accuracy.
Hodnoty 0,88-0,90 patří pixel accuracy, nikoli mIoU.

**Oprava:** pojmenovat každou metriku samostatně a uvádět hodnotu jen u
odpovídajícího názvu.

### C2 - České označení UC3 „Restaurace“ je významově zavádějící

`docs/architecture.md:32,189` používá „Restaurace“ pro obnovu map. V běžné
češtině jde primárně o stravovací zařízení; odborně přesnější je
„restaurování map“ nebo stručně „obnova map“. `docs/RESEARCH.md:89` přebírá
stejný termín.

**Oprava:** sjednotit název UC3 na „Restaurování map“ a anglický ekvivalent
`Map restoration`.

## Kontroly bez nálezu

- Standardní relativní Markdown odkazy neobsahují chybějící cílové soubory.
- Čísla sezení v `docs/DIARY.md` jsou unikátní a všechna indexovaná sezení od
  52 výše mají odpovídající deníkový nadpis.
- Dokumentované použití Pythonu 3.14 odpovídá projektovému `.venv`
  (Python 3.14.3).
- `connectors/README.md` správně označuje `forest.py` jako archivovaný/smazaný;
  nejde o tichý odkaz na existující modul.

## Doporučené pořadí nápravy

1. Opravit fyzické rozlišení a přepočítat Png2Point augmentaci.
2. Označit 0,897 jako nereprodukovaný outlier ve všech aktivních dokumentech.
3. Sjednotit kontrakt Png2Area pipeline a počty tříd.
4. Vyčistit TODO a zkrátit README na aktuální snapshot.
5. Doplnit DONE a opravit DIARY index.
6. Sjednotit routing maker a následně provést jazykové opravy.
