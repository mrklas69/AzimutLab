# KB — ISOM / ISSprOM (symbolová sémantika)

Referenční znalost o orienťáckých mapových specifikacích. Jádro „porozumění mapám" (UC5)
i cílová sémantika generátorů (UC4).

> Skeleton (Sezení 1). Detailní spec-checky už existují v Pic2Omap
> (`docs/spec_check_ISOM-2017-2.md`, `docs/spec_check_ISSprOM-2019-2.md`) — sem patří
> průřez/odkazy, ne duplikace (deštníková fáze, viz CLAUDE.md).

## Specifikace

| Spec | Doména | Verze | Pic2Omap spec-check |
|------|--------|-------|----------------------|
| ISOM 2017-2 | les / klasická OB | 2017-2 | `Pic2Omap/docs/spec_check_ISOM-2017-2.md` |
| ISSprOM 2019-2 | sprint / urban | 2019-2 | `Pic2Omap/docs/spec_check_ISSprOM-2019-2.md` |
| ISOM 2000 | les / klasická OB (withdrawn) | 2000 | — (lokální PDF `isom-2000-spec.pdf`) |

Cílová sémantika generátoru = **ISOM 2017-2** (1:10000; `generator/template_classic.omap`
je geometricky identický s oficiálním OOM 1:10000 setem, ověřeno Sez. 38). Každý výstup deklaruje
verzi (`meta["isom"]` + `.omap` `<notes>`) — ochrana proti záměně, viz níže.

**Colour order (z-order / printing order)** = samostatná reference [[isom-colour-order]]
(`isom-colour-order.md`): pořadí barev rozhoduje, co překryje co. Klíč pro generátor: modrá vodní
plocha je POD hnědou vrstevnicí (ISOM 2017-2) → vrstevnice přes vodu se řeší geometrií (clip), ne
paletou (Sez. 118). ISOM 2000 má pořadí opačné (spot tisk + overprint).

## ISOM 2000 ↔ 2017-2 — verze a crosswalk (Sez. 37–40)

**Číslování symbolů se mezi ISOM 2000 a 2017-2 RECYKLUJE s jiným významem** — naivní kód-na-kód
mapování by tiše prohodilo významy. Tvrdé příklady (verify ze spec):

| kód | ISOM 2000 | ISOM 2017-2 |
|-----|-----------|-------------|
| 521 | High stone wall | **Building** |
| 526 | Building | — (neexistuje → jediný tvrdý diskriminátor verze) |
| 508 | Less distinct small path | **Narrow ride** |
| 509 | **Narrow ride** | Railway |
| 515 | Railway | — |

**Empirie korpusu** (Sez. 38, parse `resources/*.omap` použité objekty): **4/6 reálných českých OB
map = ISOM 2000** (marker `526` Building). Implikace pro UC5 (cesta B fine-tuning): pokud je korpus
převážně 2000, syntetika 2017-2 zavádí systematický posun → [[domain-gap]] na sémantice symbolů.

**Dvojí číslování stejné verze — OOM vs OCAD (Sez. 141, nález uživatele).** Pozor: i V RÁMCI ISOM 2017-2
mají tytéž man-made point symboly DVĚ číslovací sady podle programu, kde mapa vznikla (`code` v `.omap`):

| symbol | OOM set (náš `template_classic.omap`, generátor) | OCAD set |
|---|---|---|
| High tower | 524 | 535 |
| Small tower (posed) | 525 | 536 |
| Cairn | 526 | 537 |
| Fodder rack (krmelec) | 527 | 538 |
| Prom. man-made – ring | 530 | 539 |
| Prom. man-made – x | 531 | 540 |

Doloženo: Bedřichovka.omap `id="OCD"` kóduje krmelec `538.0`, posed `536.0`; Soví vrch (OOM) krmelec `527`.
Crosswalk = pravý sloupec `ISOM2000-ISOM2017-2.crt`. **Měř výskyt symbolů CROSSWALK-AWARE** (`measure_dod`/
`compare_isom`, integer prefix `538.0→538`) — naivní `grep code="527"` OCAD mapy minul. `detect_version` je dnes
binární (2000/2017-2), ale realita je trojí (ISOM2000 / OOM-2017 / OCAD-2017) → latentní past (TODO).

**ZÁVĚR — verzní gap zavřen (Sez. 40, %THINK „vizuál vs čísla").** Otázka se rozpadá na dvě nezávislé
osy podle cesty dat: **vektor** (`.omap` symbol ID → verzi nese ČÍSLO) vs **rastr** (pixely → verzi nese
VZHLED). Pro vektor je gap vyřešen crosswalkem (1:1 přemapování); pro rastr (= co čte UC5 model) jsou čísla
úplně **irelevantní** — záleží jen vizuál. A vizuální osa byla ověřena: srovnání reálné ISOM 2000 mapy
(Soví vrch) s naším 2017-2 renderem téže oblasti (georef warp, grid-north, stejné měřítko) ukázalo, že
**rozdíl vzhledu symbolů NENÍ podstatný** (kartograf: „vše důležité v obou setech, snadno transformovatelné";
crosswalk `101/102/103` = identické číslo = identický vzhled hnědé kostry). Dominantní vizuální rozdíl mezi
reálnou mapou a generátorem je **OBSAHOVÝ** (chybějící vegetace žlutá/zelená = recall gap Sez. 37), NE verzní.
→ **Generátor zůstává 2017-2 + deklarace verze (Sez. 38) + crosswalk pro vektor; negenerovat zvlášť 2000
variantu.** Otevřený zůstává jen obsahový (vegetační) gap = UC5 predikce za zavřenou vegetace gate, jiná osa.

**Reference soubory v `docs/kb/` (KB nese licenci — CLAUDE.md):**
- `ISOM2000-ISOM2017-2.crt` — autoritativní cross-reference table (OpenOrienteering Mapper, autor
  Kai Pastor). Formát `<kód 2017-2>  <kód 2000>`, 168 ř. **Licence: GPL v3+** (součást OOM repo
  `symbol sets/`). Nezávisle potvrdil ruční crosswalk ze spec. Crosswalk přes SÉMANTIKU, ne čísla.
- `isom-2000-spec.pdf` — International Specification for Orienteering Maps 2000. **Licence: IOF**
  (withdrawn, nahrazeno 2017/2017-2; archiv ELTE `lazarus.elte.hu/mc/specs/`). Referenční, ne k šíření.

Pozn.: symbol set je **vyměnitelný `.omap` soubor** (OOM „Nahrát symboly ze souboru"), ne závislost
na verzi SW — aktuální OOM dodává ISOM 2017-2, ne ale poslední průběžnou revizi Rev 6 (2024).

## Klíčové koncepty (pro UC5 / UC4)

- **Tři typy symbolů**: bodové / liniové / plošné — osa klasifikace (UC5).
- **Paleta a priority** — barvy mají pořadí (priority); RGB-identické páry (`403.0`≡`403.1`)
  color separation nerozliší → potřeba sémantiky, ne jen barvy.
  - *Konkrétní hodnoty:* runtime paleta generátoru = `generator/palette.py`
    (jediný zdroj pravdy, slovník `PALETTE`); metodická tabulka hex+CMYK =
    `generator-procedural.md §5`. KB tady RGB **nekopíruje** — drží sémantiku
    (pořadí/priority, cross-spec rozdíly), ne odstíny (DRY).
- **ISOM↔ISSprOM rozdíly**: stejný kód ≠ stejný symbol napříč spec (např. budovy
  BLACK v ISOM les vs GRAY v ISSprOM sprint — kořen cross-domain class gapu v Pic2Omap pilotu).
