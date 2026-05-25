# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi — ČÚZK (Sez. 2), Mapový portál ČSOS (Sez. 8, gate zavřená); další zdroje TBD
- [~] Doplnit `RESEARCH.md` — LIDAR→mapa metoda hotovo (Sez. 2); zbývá generativní (UC4-I), dewarping/inpainting (UC3)

## UC2 — Data konektory (enabler, průzkum)
- [ ] Reálný ČÚZK konektor: ověřit nové (únor 2026) GetCapabilities URL; pipeline LAZ → DMR → vrstevnice (pozor: za MVP-deštník, až bude konzument)

## UC4-I / UC5 — Syntetický generátor (enabler-feeder, fáze B → první kód)
Spec: `docs/kb/generator-procedural.md` · kód: `sandbox/generator-poc/`
- [~] Procedurální generátor OB map — MVP (Sez. 4) + reálný terén `--terrain real` (Sez. 5) + věrnost: index contours / tečkovaný obrys bažin / balvany (Sez. 6) + reálný batch dataset z lokalit ČR (Sez. 7) + DRY paleta `palette.py` + vektor vrstevnic GeoJSON 101/102 + `.omap` export (Sez. 8) + bodové symboly extrémů 112/113/115 + `mask_symbols.png` (Sez. 10)
- [!] Cesty (§4.9): Catmull-Rom splajn, příp. terénně vázané (Dijkstra §9) — DO brzy (Sez. 10: stale práh, rozhodnuto realizovat, ne odkládat)
- [ ] Batch noise sada: variace `--rock` i v noise větvi (zatím jen real — noise zachován bitově reprodukovatelný, viz Sez. 7)

## Rozhodnutí (k dozrání → IDEAS.md / architecture.md)
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo) — pozn.: generátor je první kód mimo Pic2Omap, kandidát na úvahu
- [ ] První aplikační kandidát: UC3 de-purple vs jiný — pozn.: UC5 má teď datovou cestu (C) syntetika → váhy se posunuly k UC5

## Backlog (vzdálené, nezačínat)
- [ ] UC5 jádro (palette separation jako první střípek)
- [ ] UC3 / UC4 aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
