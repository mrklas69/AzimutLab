# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Founding kostra repo (README, CLAUDE.md, PROMPTS, architecture, KB skeleton) — Sezení 1
- [ ] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi (váže na UC2 průzkum)
- [ ] Doplnit `RESEARCH.md` — generativní přístupy (UC4-I), dewarping/inpainting (UC3)

## UC2 — Data konektory (enabler, průzkum)
- [!] Prozkoumat ČÚZK ZTMP / geoportál: typ přístupu (WMS/WFS), **licenční podmínky**
- [ ] LIDAR (DMR 5G) — dostupnost, formát, licence

## Rozhodnutí (k dozrání → IDEAS.md / architecture.md)
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo)
- [ ] První aplikační kandidát: UC3 de-purple vs jiný — rozhodnout, až bude enabler-minimum

## Backlog (vzdálené, nezačínat)
- [ ] UC5 jádro (palette separation jako první střípek)
- [ ] UC3 / UC4 aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
