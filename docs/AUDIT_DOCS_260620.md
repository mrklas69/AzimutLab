# AUDIT:DOCS 2026-06-20

Rozsah: projektové Markdown dokumenty nalezené přes `rg --files -g "*.md"`
(58 souborů). Záměrně jsem vynechal `.venv` a vendor dokumentaci. Audit je
read-only vůči existujícím docs: tento soubor je výstup auditu, ne oprava
zjištěných driftů.

> **Follow-up ve stejném sezení:** nálezy D1-D10 byly následně opraveny jako
> docs-only pass. D11 byl dořešen slug verifierem a opravou 20 anchor fragmentů
> v `docs/DIARY-archive.md`. D12 byl dořešen označením `generator/STATISTICS.md`
> jako historického snapshotu místo regenerace starých DEV statistik.

Ověření proti source:
- `generator.omap_raster` importem vrací `N_AREA = 21`, `AREA_CODES = 20`.
- `generator.omap_raster` importem vrací `N_LINE = 5`, tedy pozadí + 4 line
  třídy: watercourse, seasonal waterchannel, narrow marsh, narrow ride.
- `isom.capabilities` importem vrací 65 capability/generator kódů.
- Lokální souborové Markdown linky jsou čisté; samostatně ale existují rozbité
  anchor fragmenty v `docs/DIARY-archive.md`.

## Kritické / vysoké nálezy

### D1 - Řídicí docs mají zastaralý živý kontrakt `Png2Area`

Doklad:
- `AGENTS.md:68` a `CLAUDE.md:82` pořád tvrdí, že `Png2Area` má
  "17 ISOM kódů + pozadí = `N_AREA=18`".
- Source aktuálně říká `N_AREA = 21` (`generator/omap_raster.py:80`) a import
  ukazuje 20 area kódů + pozadí.
- `README.md:53` už naopak říká "20 ISOM codes + background (`N_AREA=21`)".

Dopad: `AGENTS.md`/`CLAUDE.md` jsou vstupní control docs pro další agenty. Když
drží starý label-space, další sezení může navrhnout špatné trénování, špatný
počet výstupních kanálů nebo špatné docs fixy.

Navržená oprava: sjednotit control docs na "20 ISOM kódů + pozadí = `N_AREA=21`"
a historickou `N_AREA=18` zmínku ponechat jen jako chronologii Sez. 103.

### D2 - `AGENTS.md` má zastaralý `Png2Point` scope a metriku

Doklad:
- `AGENTS.md:71-72` uvádí `scope 204/210` a test mF1 `0,888`.
- `CLAUDE.md:86-87`, `README.md:53`, `docs/GLOSSARY.md:319-320` a
  `docs/DIARY.md:31` už uvádějí živý 4-třídový scope `204/210/417/419` a
  syntetický medián mF1 `0,827`.

Dopad: `AGENTS.md` je vyšší priorita pro spolupráci než běžná dokumentace.
Tahle chyba přímo odporuje pravidlu Conceptual Integrity: hlavní vstupní prompt
popisuje jiný model než zbytek projektu.

Navržená oprava: v `AGENTS.md` převzít formulaci z `CLAUDE.md`: scope
`204/210/417/419`, mF1 `0,827`, starší `0,888` označit jako superseded
2-třídovou metriku.

### D3 - `README.md` si protiřečí v headline KPI

Doklad:
- `README.md:8` uvádí Generator KPI **63.3%** (`KPI_3MAP_CANONICAL`, session
  150).
- `README.md:53` a `README.md:55` už uvádějí KPI **65.8%**.
- `docs/DIARY.md:7` a `docs/diary/2026-06-20.md:44` ukotvují current stav jako
  65,8 % po Sez. 152.

Dopad: první obraz repa je starší než tabulka pod ním. To je přesně špatné místo
pro drift, protože README headline bývá první věc, kterou agent i člověk přečte.

Navržená oprava: změnit úvod na 65.8 % / session 152 a doplnit krátkou poznámku,
že Png2Line label scope se rozšířil, ale starý checkpoint/vectorizer zůstává
watercourse-only do rebuild/retrain.

### D4 - `README.md` layout strom ještě tvrdí starý `Png2Area` label-space

Doklad:
- `README.md:135` popisuje `tile.py` jako "17 ISOM codes + background".
- `README.md:53` už říká 20 ISOM + background (`N_AREA=21`).

Dopad: menší než D1, ale jde o stejný živý kontrakt na druhém místě ve stejném
souboru. To je typický DRY signál: jedna informace existuje víckrát a jedna kopie
zůstala stará.

Navržená oprava: změnit layout popis na "20 ISOM codes + background (`N_AREA=21`)".

### D5 - `docs/TODO.md` už není čistě aktivní TODO

Doklad:
- `docs/TODO.md:3` definuje `[x] hotovo (přesouvá se do DONE)`.
- Přesto obsahuje hotové položky, např. `docs/TODO.md:35-42`,
  `docs/TODO.md:155-160`, `docs/TODO.md:255` a další `[x]` bloky níže.
- V souboru zůstávají i rozsáhlé historické bloky, např. sekce kolem
  `docs/TODO.md:307` a modelové historie kolem `docs/TODO.md:385-446`.

Dopad: `TODO.md` ztrácí roli aktivního pracovního seznamu. Při `%BEGIN` nebo
`%END` pak agent musí ručně odhadovat, co je otevřené, hotové, zmrazené a co je
jen historie. To zvyšuje riziko, že se začne pracovat na uzavřeném nebo
superseded úkolu.

Navržená oprava: přesunout hotové `[x]` detaily do `DONE.md`/diary, v `TODO.md`
nechat jen `[ ]`, `[~]`, `[!]` a explicitně označený "frozen/backlog" bez dojmu,
že jde o aktivní práci.

## Střední nálezy

### D6 - `docs/architecture.md` míchá aktuální a historický `Png2Area` stav

Doklad:
- `docs/architecture.md:179` v živém popisu `Png2Area` pořád uvádí
  "17 ISOM kódů + pozadí = `N_AREA 18`".
- Níže je chronologie `N_AREA 18` v pořádku (`docs/architecture.md:191`), ale
  první aktuální odstavec má mluvit o dnešním kontraktu.

Dopad: architektura má být SSoT modelu. Když se v aktuálním odstavci tváří jako
Sez. 103, čtenář neví, zda README nebo architecture vyhrává.

Navržená oprava: v aktuálním popisu změnit na `N_AREA=21` / 20 ISOM kódů +
pozadí a historickou `N_AREA 18` ponechat v timeline.

### D7 - `docs/GLOSSARY.md` obsahuje současně správný i starý label-space

Doklad:
- `docs/GLOSSARY.md:307-308` správně říká aktuálně 20 ISOM kódů + pozadí.
- `docs/GLOSSARY.md:419` a `docs/GLOSSARY.md:437` ale definují `omap_raster` /
  `Png2Area` jako 17 ISOM kódů + pozadí = `N_AREA 18`.
- `docs/GLOSSARY.md:582` pořád říká "synt referenci nahradit 0,888", což je po
  4-třídovém `Png2Point` scope už zavádějící bez kontextu.

Dopad: slovník je referenční dokument. Smí nést historii, ale aktuální definice
musí být jednoznačná.

Navržená oprava: u `omap_raster` a `Png2Area` oddělit "aktuálně" od "historicky".
U `Png2Point` explicitně říct, že `0,888` je superseded 2-třídová metrika a živý
4-třídový benchmark je `0,827`.

### D8 - `docs/AUDIT_SUPERVISOR_260619.md` je historicky správný, ale dnes působí živě

Doklad:
- `docs/AUDIT_SUPERVISOR_260619.md:12`, `:45-51`, `:126` tvrdí, že chybějící
  `Velbloud.pgw` blokuje srovnatelný trend.
- `docs/TODO.md:35-42`, `docs/DONE.md:79-82` a lokální filesystem potvrzují, že
  `resources/Velbloud.pgw` byl následně vytvořen.
- Stejný audit ještě uvádí některé A6/body jako trvající, zatímco `DONE.md`
  později část uzavírá.

Dopad: auditní artefakt má zůstat historický, ale `%BEGIN`/další agent ho může
číst jako aktuální backlog. To vede k opakování už vyřešených problémů.

Navržená oprava: nepřepisovat historické nálezy; přidat na začátek krátký blok
"Status po Sez. 152" s odkazy na `TODO.md`/`DONE.md`.

### D9 - Handoff z 2026-06-19 je po Sez. 150-152 superseded

Doklad:
- `docs/HANDOFF_260619_MRKLA_HAL3000.md:28` ukazuje KPI po doplnění
  `Velbloud.pgw` jako 59,5.
- Dnešní current stav je 65,8 (`README.md:53`, `docs/DIARY.md:7`).
- `docs/HANDOFF_260619_MRKLA_HAL3000.md:87` stále řeší chybějící `Velbloud.pgw`
  jako potenciální blokátor.

Dopad: handoff soubor má legitimní historickou hodnotu, ale v aktivním `docs/`
adresáři bez superseded hlavičky vypadá jako aktuální předání.

Navržená oprava: přidat "Superseded by DIARY sessions 150-152" header, případně
soubor přesunout do archivní části, pokud projekt chce držet aktivní `docs/`
čistší.

### D10 - `docs/DIARY.md` hlavička nesedí na rozsah indexu

Doklad:
- `docs/DIARY.md:3` říká "Aktivní index posledních ~20 sezení (126-152)".
- Rozsah 126-152 je 27 sezení.

Dopad: malý faktický drift, ale u control/closeout procesu je důležité, aby index
nelhal o vlastní velikosti.

Navržená oprava: buď změnit text na "~27 sezení", nebo index skutečně prořezat na
zamýšlené okno a starší řádky přesunout do archivu.

## Nižší / technické nálezy

### D11 - `docs/DIARY-archive.md` má rozbité anchor fragmenty

Status po follow-upu: opraveno 20 fragmentů; verifier hlásí 120/120 anchorů OK.

Doklad:
- `docs/DIARY-archive.md:7` odkazuje na
  `diary/2026-05-22.md#2026-05-22--sezení-1-founding`.
- Cílový soubor má na `docs/diary/2026-05-22.md:1` heading
  `# 2026-05-22 — Sezení 1 (Founding)`, který se na uvedený fragment neshoduje.
- Rychlý anchor scan našel mnoho podobných kandidátů v archive indexu. Po jednom
  ručním ověření je problém reálný, ne jen false positive skriptu.

Dopad: odkaz na soubor funguje, ale skok na konkrétní sezení ne. U dlouhých
deníků to zhoršuje dohledatelnost rozhodnutí.

Navržená oprava: před hromadnou změnou použít robustnější GitHub/Markdown slug
verifier a opravit anchor fragmenty v `docs/DIARY-archive.md`.

### D12 - `generator/STATISTICS.md` je pravděpodobně starý snapshot

Status po follow-upu: vyřešeno označením souboru jako historického snapshotu
2026-06-10 / Sez. 108. Regenerace nebyla spuštěna.

Doklad:
- `generator/STATISTICS.md:3` říká, že jde o 5 `DEV_LOCATIONS`.
- `generator/STATISTICS.md:72` uvádí 52 sledovaných ISOM symbolů, 47 používaných.
- Source capability registry má dnes 65 generator kódů a hlavní KPI běží na
  `KPI_3MAP_CANONICAL`, ne na pěti starých DEV lokacích.
- Poslední aktualizace v souboru je 2026-06-10.

Dopad: pokud je soubor pořád považovaný za aktivní statistiku, je zastaralý. Pokud
je to historický snapshot, chybí mu archivní/superseded označení.

Navržená oprava: rozhodnout roli souboru. Buď regenerovat na dnešní kanonický
scope, nebo nahoře přidat "historical snapshot / superseded".

## Doporučené pořadí oprav

1. Sjednotit živý stav v `AGENTS.md`, `CLAUDE.md`, `README.md`,
   `docs/architecture.md`, `docs/GLOSSARY.md`.
2. Pročistit `docs/TODO.md`, aby znovu znamenal aktivní backlog.
3. Označit `AUDIT_SUPERVISOR_260619.md` a `HANDOFF_260619_MRKLA_HAL3000.md` jako
   historické/superseded místo přepisování jejich původních závěrů.
4. Opravit hlavičku nebo rozsah `docs/DIARY.md`.
5. Samostatně spustit anchor verifier a opravit `docs/DIARY-archive.md`.
6. Rozhodnout, jestli `generator/STATISTICS.md` regenerovat, nebo archivně
   označit.

## Co jsem záměrně neopravoval

- Neměnil jsem existující dokumentaci, protože `%AUDIT:DOCS` má nejdřív dodat
  nálezy a návrhy.
- Nepřepisoval jsem historické `DONE.md` a starší auditní artefakty jen proto, že
  obsahují starší čísla. Historie může zůstat stará, pokud je jasně oddělená od
  aktuálního kontraktu.
