# CLAUDE.md — AzimutLab (projektový overlay)

Rozšiřuje globální `~/.claude/CLAUDE.md`, nepřevažuje. Makra %BEGIN/%END:
viz `docs/PROMPTS.md`. Stav/architektura/UC DAG: README.md + `docs/architecture.md`
(ne sem).

## Doménové pracovní zásady
- **Foundations before curtains — tvrdě.** Projekt je deštník nad 5 UC (DAG, ne
  seznam). Enablery (UC2 data / UC5 modely) jdou před aplikacemi (UC3/UC4).
  Než sáhneš na aplikaci, ověř, že enabler pod ní stojí. Scope creep je
  primární riziko — vždy se ptej „je tohle MVP, nebo záclona?".
- **Verify-against-source.** Zděděno z Pic2Omap: `.omap`/`.ocd` XML a spec
  (ISOM/ISSprOM) jsou pravda; než uvěříš agregátu, koukni do geometrie/dat.
- **KB je živá, ne archiv.** Každý zdroj dat (UC2) nese v `docs/kb/` i licenci.
  Stavět UC4-II/III na datech bez vyjasněné licence = chyba.
- **Pic2Omap je sourozenec, ne kopie.** Dokud jsme deštník (fáze B), Pic2Omap
  žije ve vlastním repu — neduplikuj jeho kód sem; odkazuj. Absorpce (fáze A)
  je vědomý budoucí krok, ne tichý drift.

## %THINK — doménové rozšíření
U map/CV/generování zvaž: ISOM↔ISSprOM spec rozdíly, paper-space vs world georef,
limity color separation (RGB-identické páry), sparse-GT past. U generátorů (UC4):
realistické ≠ náhodný soubor symbolů — vrstevnice/terén musí dávat fyzický smysl.

## Klíčové soubory (orientace; plný rozpis README „Repository layout")
- `docs/architecture.md` — kanonický UC DAG, vrstvení, vztah k Pic2Omap (SSoT modelu).
- `docs/kb/` — knowledgebase (data-sources / isom-issprom / tools-models).
- `connectors/` — UC2 konektory reálných geodat (`dmr.py` výškopis, `zabaged.py` cesty);
  vytaženo ze sandboxu (Sez. 16), sourozenci sdílí `dmr.build_bbox`. Sys.path skripty, ne balík.
- `sandbox/` — izolované experimenty (každý vlastní složka + README).
- `connectors/` = první sdílená kódová složka mimo sandbox (krok k fázi A) — pořád ale **ne
  produkční balík** (ten přijde s přechodem na monorepo, fáze A).
