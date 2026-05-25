# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi — ČÚZK (Sez. 2), Mapový portál ČSOS (Sez. 8, gate zavřená); lokální mapy `resources/` (smíšený původ); další zdroje TBD
- [~] `resources/`: 6 reálných párů (picture, OMAP) nakopírováno (2 OOM dema vyřazena); zbývá rozlišit původ vlastní (`own/`) vs klubové (`club/`) kvůli čistotě tréninkového setu (reference/hold-out smí všechny)
- [~] Doplnit `RESEARCH.md` — LIDAR→mapa metoda hotovo (Sez. 2); zbývá generativní (UC4-I), dewarping/inpainting (UC3)

## UC2 — Data konektory (enabler, průzkum)
- [ ] Reálný ČÚZK konektor: ověřit nové (únor 2026) GetCapabilities URL; pipeline LAZ → DMR → vrstevnice (pozor: za MVP-deštník, až bude konzument)

## UC4-I / UC5 — Syntetický generátor (enabler-feeder, fáze B → první kód)
Spec: `docs/kb/generator-procedural.md` · kód: `sandbox/generator-poc/`
- [~] Procedurální generátor OB map — **přestavba „znovu a lépe" (Sez. 11):** vrstvy stavíme po jedné s důrazem na vizuální věrnost. HOTOVO: vrstevnice (§4.5) + bodové symboly extrémů **109/110/111** (§4.10, ISOM 2017-2 Rev 6 — Sez. 13 oprava ze zastaralých 112/113/115) + **terénní cesty (§9, Dijkstra least-cost, ISOM 503/507, `mask_paths.png`)** + vektor 101/102 + `.omap` (vrstevnice+cesty+body) + reálný terén `--terrain real`. ZAHOZENO (vypadalo uměle, kazilo by domain gap): vegetace, paseky, bažiny, balvany.
- [x] **Terénně vázané cesty (§9): Dijkstra least-cost** — HOTOVO Sez. 13 (cena = vzdálenost × (1+LIN·sklon+SQ·sklon²) + tvrdý strop 50 %; repulsion proti duplikaci cest). Cesty traverzují svah, nešplhají přes vrcholy. → DONE
- [!] **OMAP věrné body (#2/#4, Sez. 13):** přepnout `omap_export` z od-nuly na template-based z `resources/template_classic.omap` (vlastní čistý ISOM 2017-2 template) → zdědí věrnou geometrii bodů (110 elipsa, 111 oblouk „⌣") místo zjednodušeného kruhu. **+ přesunout `template_classic.omap`/`template_sprint.omap` z gitignored `resources/` do `sandbox/generator-poc/`** (verzované, sebeobsažné).
- [ ] Hydrologické jádro z flow accumulation (D8, §9): toky (§4.8, nikdy neimpl.) → prameny (§4.10) → **jezera/rybníky = sink-fill deprese (NOVÁ vrstva, ve spec chybí)** → bažiny (§4.4 znovu a lépe). Jeden zdroj pravdy, dělat po cestách (stupeň 1).
- [ ] Stupeň 2 — augmentační pipeline (§8.3): degradace render → „sken" (CMYK misregistration, papír, JPEG, deformace) pro UC4-III. Až stupeň 1 stojí.

## Rozhodnutí (k dozrání → IDEAS.md / architecture.md)
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo) — pozn.: generátor je první kód mimo Pic2Omap, kandidát na úvahu
- [ ] První aplikační kandidát: UC3 de-purple vs jiný — pozn.: UC5 má teď datovou cestu (C) syntetika → váhy se posunuly k UC5

## Backlog (vzdálené, nezačínat)
- [ ] UC5 jádro (palette separation jako první střípek)
- [ ] UC3 / UC4 aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
