# DONE — AzimutLab

Dokončené úkoly (stručně co se udělalo). Aktuální/čekající: TODO.md.

## Sezení 3 (2026-05-23) — Vegetace gate (ČÚZK plné mračno = NE)
- [x] Ověřeno: ČÚZK **neposkytuje** plné klasifikované multi-echo mračno jako open data.
      Nový hustý DMP OK je z **obrazové korelace** (fotogrammetrie, jen povrch, žádné echoes),
      surové LLS mračno není open. → „Vegetace gate" zavřena, náhrada jen CHM+NIR proxy.
      Ověřeno proti primárnímu zdroji (technická zpráva DMP OK, 1/2026).
- [x] KB konsolidace (SLAP): `data-sources.md` (DMP OK, oprava DMR 5G, „Vegetace gate"),
      `RESEARCH.md` (otázka uzavřena), `TODO.md` (`[!]` hotovo).

## Sezení 2 (2026-05-23) — UC2 průzkum ČÚZK + LIDAR research
- [x] UC2 průzkum ČÚZK geoportálu: přístup (WMS/WMTS/WFS/WCS/ATOM) + **licence = CC BY 4.0**
      (gate otevřena → na ČÚZK datech lze stavět UC4-II/III s atribucí).
- [x] DMR 5G (LIDAR výškopis): dostupnost 100 % ČR, formát LAZ, licence CC BY 4.0.
- [x] Naplněn `docs/kb/data-sources.md` — ČÚZK katalog + oprava terminologie ZTMP → ZABAGED/ZTM.
- [x] Doplněn `RESEARCH.md` — metoda LIDAR → orienteering mapa (Karttapullautin); nález
      „DMR 5G ground-only ≠ vegetace, třeba plné mračno bodů".

## Sezení 1 (2026-05-22) — Founding
- [x] Seznámení s Pic2Omap (architektura, workflow, dokumentační kultura).
- [x] %THINK nad 5 UC → zjištěno, že tvoří DAG (enablery pod aplikacemi), ne seznam.
- [x] Rozhodnutí: vztah k Pic2Omap = deštník→monorepo (B→A); MVP = UC1; jméno = AzimutLab.
- [x] Založena kostra repo: README, CLAUDE.md overlay, docs/PROMPTS.md,
      docs/architecture.md (kanonický DAG), IDEAS, RESEARCH, docs/kb/ (3 soubory),
      sandbox/, TODO/DONE/DIARY, .gitignore, git init (branch main).
