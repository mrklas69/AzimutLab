# TODO — AzimutLab

Markery: `[ ]` čeká · `[~]` rozděláno · `[x]` hotovo (přesouvá se do DONE) · `[!]` priorita.
Vždy přes optiku UC DAGu (`docs/architecture.md`): enabler před aplikací.

## UC1 — Knowledgebase + Sandbox (MVP, fáze B)
- [~] Naplnit `docs/kb/data-sources.md` reálnými zdroji + licencemi — ČÚZK (Sez. 2), Mapový portál ČSOS (Sez. 8, gate zavřená); lokální mapy `resources/` (smíšený původ); další zdroje TBD
- [~] `resources/`: 6 reálných párů (picture, OMAP) nakopírováno (2 OOM dema vyřazena); zbývá rozlišit původ vlastní (`own/`) vs klubové (`club/`) kvůli čistotě tréninkového setu (reference/hold-out smí všechny)
- [~] Doplnit `RESEARCH.md` — LIDAR→mapa metoda hotovo (Sez. 2); zbývá generativní (UC4-I), dewarping/inpainting (UC3)

## UC2 — Data konektory (enabler, průzkum)
- [ ] LiDAR pipeline LAZ → DMR → vrstevnice (zbylá point-cloud větev; za MVP-deštník, až bude konzument). Pozn.: výškopis `dmr.py` (DMR 5G, ImageServer) i cesty `zabaged.py` (ZABAGED WFS) už jako konektory žijí v `connectors/` — tohle je plné mračno bodů (naráží na vegetace gate, viz `data-sources.md`)

## UC4-I / UC5 — Syntetický generátor (enabler-feeder, fáze B → první kód)
Spec: `docs/kb/generator-procedural.md` · kód: `sandbox/generator-poc/`
- [~] Procedurální generátor OB map — **přestavba „znovu a lépe" (Sez. 11):** vrstvy stavíme po jedné s důrazem na vizuální věrnost. HOTOVO: vrstevnice (§4.5) + bodové symboly extrémů **109/110/111** (§4.10, ISOM 2017-2 Rev 6 — Sez. 13 oprava ze zastaralých 112/113/115) + **terénní cesty (§9, Dijkstra least-cost, ISOM 503/505, `mask_paths.png`)** + vektor 101/102 + **`.omap` template-based** (Sez. 14 — věrná geometrie bodů 110 elipsa / 111 oblouk + plná ISOM knihovna z `template_classic.omap`) + reálný terén `--terrain real` + **reálné cesty `--paths real`** (Sez. 16 — ZABAGED WFS, ISOM 502-506) + **reálná voda `--water real`** (Sez. 17 — ZABAGED toky 304/305/306 + plochy 301, `mask_water.png`). ZAHOZENO (vypadalo uměle, kazilo by domain gap): vegetace, paseky, bažiny, balvany.
- [ ] **Reálné budovy/stavby (UC2 → UC4-II)** — *uživatelův další plán (Sez. 17)*: rozšířit `zabaged.py` o `Budova_jednotlivá_nebo_blok_budov__plocha_` → ISOM **521 Building** (+ příp. 526/527 dle typu) + GT. Plocha (render výplň+obrys, izomorfní s vodní plochou 301). Stejný konektor (real-půlka).
- [ ] *(odloženo, noise-půlka)* Hydrologické jádro z flow accumulation (D8, §9): toky (§4.8) → prameny (§4.10) → jezera/rybníky (sink-fill deprese) → bažiny. **Sez. 17: voda realizována reálně (ZABAGED), D8 = procedurální protějšek do budoucna (nemíchat osy).**
- [ ] *(rozšíření cest/vody)* věrná dvojitá linie 502 Wide road (teď PoC casing), ladění 505/506, ořez reálných linií na bbox; (voda) „hranatý" malý rybník, věrný kombinovaný 301 s břehovou linií v OMAP (teď 301.1).
- [ ] Stupeň 2 — augmentační pipeline (§8.3): degradace render → „sken" (CMYK misregistration, papír, JPEG, deformace) pro UC4-III. Až stupeň 1 stojí.

## Rozhodnutí (k dozrání → IDEAS.md / architecture.md)
- [ ] Kvantifikovat spouštěč B→A (který konkrétní sdílený modul povýší na monorepo) — pozn.: generátor je první kód mimo Pic2Omap, kandidát na úvahu. **Sez. 16: `connectors/` = první sdílená kódová složka mimo sandbox (drobný krok B→A); spouštěč „balík" stále otevřen — až 2. konzument konektorů nebo generátor opustí sandbox.**
- [ ] První aplikační kandidát: UC3 de-purple vs jiný — pozn.: UC5 má teď datovou cestu (C) syntetika → váhy se posunuly k UC5

## Backlog (vzdálené, nezačínat)
- [ ] UC5 jádro (palette separation jako první střípek)
- [ ] UC3 / UC4 aplikace
- [ ] Zobecnění domény (OSM/Google) — vědomě odložené
