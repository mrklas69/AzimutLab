# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi — ČÚZK hotovo (Sez. 2), další zdroje TBD
- [~] Doplnit `RESEARCH.md` — LIDAR→mapa metoda hotovo (Sez. 2); zbývá generativní (UC4-I), dewarping/inpainting (UC3)

## UC2 — Data konektory (enabler, průzkum)
- [ ] Reálný ČÚZK konektor: ověřit nové (únor 2026) GetCapabilities URL; pipeline LAZ → DMR → vrstevnice (pozor: za MVP-deštník, až bude konzument)

## UC4-I / UC5 — Syntetický generátor (enabler-feeder, fáze B → první kód)
Spec: `docs/kb/generator-procedural.md` · kód: `sandbox/generator-poc/`
- [~] Procedurální generátor OB map — MVP hotov (vrstevnice/vegetace/bažiny + GT masky, Sez. 4)
- [ ] Doladit věrnost: výrazné index contours, tečkovaný obrys bažin, +1-2 vrstvy (cesty/balvany)
- [!] Option 2 — reálný ČÚZK DMR 5G místo šumu (§8.5): souřadnice 50.8214458N 14.6712747E, výsek 1×1 km
- [ ] DRY: paleta generátoru → jediný zdroj `docs/kb/isom-issprom.md`

## Rozhodnutí (k dozrání → IDEAS.md / architecture.md)
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo) — pozn.: generátor je první kód mimo Pic2Omap, kandidát na úvahu
- [ ] První aplikační kandidát: UC3 de-purple vs jiný — pozn.: UC5 má teď datovou cestu (C) syntetika → váhy se posunuly k UC5

## Backlog (vzdálené, nezačínat)
- [ ] UC5 jádro (palette separation jako první střípek)
- [ ] UC3 / UC4 aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
