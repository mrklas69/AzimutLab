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

Cílová sémantika generátoru = **ISOM 2017-2** (1:10000; `sandbox/generator-poc/template_classic.omap`
je geometricky identický s oficiálním OOM 1:10000 setem, ověřeno Sez. 38). Každý výstup deklaruje
verzi (`meta["isom"]` + `.omap` `<notes>`) — ochrana proti záměně, viz níže.

## ISOM 2000 ↔ 2017-2 — verze a crosswalk (Sez. 37–38)

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

**Reference soubory v `docs/kb/` (KB nese licenci — CLAUDE.md):**
- `ISOM2000-ISOM 2017-2.crt` — autoritativní cross-reference table (OpenOrienteering Mapper, autor
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
  - *Konkrétní hodnoty:* runtime paleta generátoru = `sandbox/generator-poc/palette.py`
    (jediný zdroj pravdy, slovník `PALETTE`); metodická tabulka hex+CMYK =
    `generator-procedural.md §5`. KB tady RGB **nekopíruje** — drží sémantiku
    (pořadí/priority, cross-spec rozdíly), ne odstíny (DRY).
- **ISOM↔ISSprOM rozdíly**: stejný kód ≠ stejný symbol napříč spec (např. budovy
  BLACK v ISOM les vs GRAY v ISSprOM sprint — kořen cross-domain class gapu v Pic2Omap pilotu).
