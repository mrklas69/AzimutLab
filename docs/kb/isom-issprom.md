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
