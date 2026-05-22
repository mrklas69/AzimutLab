# PROMPTS — AzimutLab (projektová makra)

Rozšiřuje globální makra (`~/.claude/CLAUDE.md`). Jen projektová specifika.

## %BEGIN — start sezení
1. Načti kontext: README.md, `docs/architecture.md`, TODO.md, DIARY.md +
   poslední 1–2 diáře (docs/diary/), IDEAS.md dle potřeby.
2. Audit cadence check (prahy z globálního CLAUDE.md) — spočítej od posledního
   výskytu auditu v diáři: %AUDIT:CODE ≥8 sez / ≥500 LOC, %AUDIT:DOCS ≥10,
   IDEAS/TODO pruning ≥12, %CALIBRATE ≥15. Práh překročen o ≥2 → první bod sezení.
   (Pozn.: dokud jsme deštník bez kódu, %AUDIT:CODE prakticky neaktivní —
   sleduj hlavně %AUDIT:DOCS a KB konzistenci.)
3. Stale Příště check — položka v „Příště" ≥5 sezení po sobě → DO/DROP.
4. Návrh fokusu z posledního „Příště" + [!] priorit v TODO. Vždy přes optiku
   UC DAGu: je navržený fokus enabler, nebo záclona?

## %END — konec sezení
= globální %DOCS + commit pravidla. Projektová specifika:
- Diář: docs/diary/YYYY-MM-DD.md, index DIARY.md. Více sezení/den =
  sekce `## Sezení N` v témže souboru (nikdy ne suffix b/c/d).
- Identita sezení = datum + pořadí v daném dni.
- Měnil-li se kód: dva commity (feat/fix → docs(session)), pak push. V deštníkové
  fázi je „kód" často jen KB/docs → jeden commit `docs(session)` stačí.
