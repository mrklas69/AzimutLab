# IDEAS — AzimutLab

Brainstorm a alternativní přístupy. Zralé nápady značím `→ TODO` / `→ DONE`.
Kanonická architektura (až nápad dozraje) žije v `docs/architecture.md`, ne sem.

---

## Founding %THINK (Sezení 1, 2026-05-22)

### Velká teze: tohle je program, ne projekt
Pět UC, z nichž UC4-III *je* celý Pic2Omap (19 sezení, pořád WIP). Bez tvrdého MVP
řezu = garantovaný scope creep. Proto deštník (UC1) jako základ, ne pět paralelních front.

### UC jako DAG, ne seznam → `docs/architecture.md`
Klíčový nález: UC nejsou plochý seznam. Enablery (UC2 data, UC5 modely) leží pod
aplikacemi (UC3, UC4). UC1 je meta-vrstva nad vším. To určuje pořadí prací.
**Dozrálo → kanonizováno v `docs/architecture.md`.**

### Tři přístupy ke vztahu k Pic2Omap (rozhodnuto)
- **A) Monorepo / absorpce** — vtáhnout Pic2Omap hned. Plus: DRY reálné. Minus: velká migrace.
- **B) Deštník** — UC1 only, Pic2Omap žije dál. Plus: nejlevnější. Minus: „sdílené jádro" fikce.
- **C) Platforma s konektory** — nové jádro (UC5+UC2), Pic2Omap přepojit. Minus: over-engineering předem.
- **Rozhodnuto: B→A** (deštník dorůstající do monorepa). → `docs/architecture.md` „Vztah k Pic2Omap".

### MVP řez (rozhodnuto)
UC1 (KB + Sandbox + DAG mapa). Žádný CV/ML kód. Pravé „foundations before curtains".

### Jméno (rozhodnuto)
AzimutLab. Důvod „Lab": sada nástrojů/experimentů/info, ne jediná aplikace. Obsazenost
ověřena — kolize jen mimo doménu (kiosk SDK, web studio, InsurTech, solární), doména volná.
Vyřazeno: CartoLab (GIS firma + GitHub org), MapSenseLab (Mapsense obsazený v geo),
Mapwright/Mapník (map-SW kolize), Mapárna/Cartouche (chtěné mezinárodní).

---

## Realnost generátoru — dvoustupňová věrnost (zaměření desítek sezení, 2026-05-25)

> **Názvosloví: vědomě bez písmen A/B** — ta jsou obsazená vztahem k Pic2Omap
> (fáze B deštník → A monorepo). Tady jde o jinou osu: jak „reálná" je vyrobená mapa.

Cíl programu: velký dataset párů (picture, OMAP) pro trénink modelů; mapy co nejvíc
podobné reálným OB mapám. Generátor = feeder s GT zdarma (§0 spec). „Reálnost" má dvě
osy, řešíme **dvoustupňově** (rozhodnuto 2026-05-25):

### Stupeň 1 — kartografická věrnost (teď)
Čistý render, kde každá vrstva **fyzikálně sedí na terén**. Akceptační „fyzikální gate":
vrstva, co vypadá uměle, není dost vázaná na terén → **lepší vazba, ne zahození**
(poučení z bažiny zahozené v Sez. 11). Liší se od **vegetace gate** (zelená/žlutá =
zavřená, chce multi-echo LiDAR — `data-sources.md`); hydro+cesty fyzikální gate procházejí.

Pořadí věrnostních vrstev (jeden zdroj pravdy = terénní pole `eb` / reálný DMR):
1. **Cesty terénně vázané** (start, zvoleno) — §4.9 z přímého splajnu na Dijkstra
   least-cost (§9): vede údolím/sedlem. Dotahuje rozdělanou vrstvu před otevřením nové.
2. **Hydrologické jádro z flow accumulation (D8, §9)** — jedna dávka z jednoho pole:
   toky (§4.8, nikdy neimpl.) → prameny (§4.10) → **jezera/rybníky = sink-fill deprese
   (NOVÁ vrstva, ve spec chybí)** → bažiny (§4.4 znovu a lépe). Řeka pak konzistentní
   s vrstevnicemi zdarma (izomorfní s vrstevnice ← elev).
3. *(real-půlka)* ZABAGED cesty/vodstvo jako reálný protějšek — viz „Reálné cesty…" níže.

### Stupeň 2 — věrnost skenu (až stupeň 1 stojí)
Augmentace (§8.3, neimpl.) jako **samostatná vrstva** pipeline: CMYK misregistration,
papír, JPEG, deformace sklad/sken → čistý render degraduje na „zablácený sken". Tím je
pár (picture, OMAP) realistický pro UC4-III. Vrstvy se staví jednou (stupeň 1),
realnost-artefaktu se přidá, nepřepisuje.

---

## `synthesize_pseudorealistic_map` — generátor jako prediktor mapy (Sez. 23, %THINK)

Reframe real-větve: z „feeder" na **prediktor mapy** pro konkrétní lokalitu. Cílové API
**`synthesize_pseudorealistic_map(n, e, w_km, h_km)`** — „synthesize" = skládá 2 zdroje;
„pseudorealistic" = vypadá real, není skutečné mapování; snake_case (Python). Zamítnuto
`GetPredictedMap` (`Get` = existující mapa) a `GenerateProceduralMap` („procedural" je rezervováno
pro noise-feeder, kolize s `generator-procedural.md`). Dvoufázový (A2 uživatele):
- **(1) projekce** podkladů — DMR→vrstevnice, ZABAGED→ISOM cesty/voda/budovy. *Máme*
  (deterministický převod, ne predikce) = dnešní real-větev.
- **(2) AI predikce** chybějících symbolů (vegetace/průchodnost — co v geodatech NENÍ, vegetace
  gate zavřená) z **podobných lokalit** (retrieval-augmented prior) = UC5. **Blokátor: korpus +
  licence** (ČSOS gate zavřená, Sez. 8) — bez zmapovaných map jako GT nelze učit.

Cíl A3: co nejrealističtěji vyhlížející mapa. Noise-větev zůstává procedurální feeder (nemíchat osy).
**Foundations:** predikce zralá jako VIZE, ne kód; pod ní musí stát parametrizace (DONE Sez. 23) +
korpus s licencí. **Pojem projekce vs predikce → GLOSSARY** (ať se „predikce" neříká převodu).

---

## Nezralé nápady (k dozrání)

- **UC3 jako první aplikace (ne UC4-III).** De-purple + de-crease potřebuje jen segmentaci
  fialové, ne plný UC5 → levnější hmatatelný výsledek dřív. Zvážit, až bude enabler-minimum.
- **Spouštěč B→A kvantifikovat.** „Dozrálé UC5-jádro" = který konkrétní sdílený modul?
  Kandidát: až palette separation z Pic2Omap (`color_separator.py`) potřebuje druhý konzument.
- **Kanonická mezivrstva napříč UC** — převzít Pic2Omap `db.json`, nebo vlastní? Řešit
  s prvním kódem mimo Pic2Omap (DRY vs předčasná abstrakce).
- **Zobecnění domény (OSM/Google).** Vědomě odložené — viz `docs/architecture.md`
  „Čekající rozhodnutí". Past na conceptual integrity, dokud orienteering jádro nestojí.
- **Synteticky renderované trénovací mapy** (původní jiskra projektu z Pic2Omap ML pilotu) —
  patří pod UC4-I/II + UC5 trénink. **→ DONE (Sez. 4): realizováno jako PoC** —
  procedurální generátor (spec `docs/kb/generator-procedural.md`, kód `sandbox/generator-poc/`).
  **Reframe:** ne „nejvzdálenější", ale **enabler-feeder pro UC5** — GT zdarma obchází
  sparse-GT past. Reálný terén (ČÚZK DMR 5G) dosazen přes `--terrain real` (§8.5, hotovo Sez. 5).
- **Reálné cesty/komunikace ze ZABAGED (UC2 → UC4-II). → DONE (Sez. 16).** Realizováno: `zabaged.py`
  (WFS, GeoJSON), `--paths real`, mapování ZABAGED→ISOM 502-506. Vše, co tato úvaha předpovídala,
  sedlo: vysoká věrnost (cesty vedou údolími na reálném terénu), přesná GT z vektoru, real-only,
  mapování ne 1:1 (povrch/udržovanost → sjízdnost). Detail: `data-sources.md` + spec §4.9/§9.
  Procedurální §4.9 = noise-půlka, ZABAGED = real-půlka (izomorfní s výškopisem noise/real).
  Pozn.: „ze ZM5" byl omyl — ZM5 je zrušený rastr (1.7.2023 → ZTM5), vektor je v ZABAGEDu.
  **Voda → DONE (Sez. 17).** Realizováno týmž konektorem (`fetch_water`): `Vodní_tok` →
  toky ISOM 304/305/306 (dle stálý/občasný/pojmenovaný; podzemní skip), `Vodní_plocha` → 301.
  **Pramen 312 vynechán** — `Zdroj_podzemních_vod` 0 ve výřezu (nevymýšlet, co v datech není).
  Proc hydro jádro D8 = DROP (budoucí noise-půlka, nemíchat osy). Detail: `data-sources.md`.
  **Budovy → DONE (Sez. 18).** Týž konektor (`fetch_buildings`): `Budova_..._plocha_` → ISOM **521**
  (plošný černý symbol, izomorfní s vodní plochou 301). Bodová vrstva budov prázdná → netáhne se.
  Vodojem → taky 521 (rozhodnutí uživatele-mapéra). Real-půlka kompletní pro cesty+voda+budovy.

## Kartografická generalizace (Sez. 18)

Reálná OB mapa NENÍ syrová geometrie — kartograf vynucuje minimální dimenze, zjednodušuje obrysy,
odsazuje kolidující objekty (*displacement*). Syrová data zvětšují domain gap feederu (UC5 se učí
číst GENERALIZOVANOU mapu). Rozměry ze spec (ISOM, `template_classic.omap`, papírové mm × `PX_PER_MM`).
GT zůstává konzistentní (maska z téže generalizované geometrie).

- **Úroveň 1 → DONE (Sez. 18):** min. velikost budovy 0,5 mm (`_enforce_min_size`), zjednodušení
  obrysu Douglas-Peucker (`_simplify_polyline`, 0,3 mm passage), tloušťka 505 → 2 px. Levné, foundational.
- **Úroveň 1b — pravoúhlost budov (→ TODO `[!]`, fokus Sez. 23):** lidská obydlí ≈ 99 % obdélníky;
  reálné ZABAGED footprinty mají šikmé/zaoblené hrany a Douglas-Peucker je nenarovná na pravé úhly →
  na mapě je pravoúhlá sotva polovina (nález uživatele Sez. 22). Orthogonalizace TVARU: dominantní osa
  budovy + snap hran na násobky 90°, příp. min-area bounding rectangle u malých. **Nezávislé na L2**
  (displacement translatuje tuhý ring, tvar neřeší). Metoda k probrání (uživatelovy noty).
- **Úroveň 2 — displacement → DONE (Sez. 22):** odsazení budov od pevné sítě (cesty+toky=kotva) a od
  sebe na ISOM 0,4 mm (≈1,83 px). `resolve_displacement` — greedy kolmé odsazení (mezera k OKRAJI),
  budova↔budova symetricky, strop 0,8 mm, 8 iterací. Budova = tuhé těleso → translace celého ringu.
  - **Krok 0 (Sez. 21):** Č. Švýcarsko ~28/99 v kolizi, dominuje budova↔cesta, shluky budov ~0
    → greedy stačí (ne NP-hard relaxace). **Pořadí: L1 (tvar) → L2 (poloha).**
  - **Inverze kontroly = LOKÁLNÍ** (Sez. 22 nález proti odhadu Sez. 21): z-order kreslí budovy poslední
    → pevná síť hotová → split jen budov (`_collect_real_buildings`+`_resolve_and_draw_buildings`),
    žádný přepis `generate()`.
  - **GT konzistence:** posun na px geometrii → render + maska + OMAP z téže geometrie (jako L1).
  - **Datová korekce „1–2 iterace" → 8** (Sez. 22): při 2 budova↔budova regresuje (14→16, odsazení od
    cest tlačí budovy k sobě); plató od ~6. Verify `diagnose_displacement.py` (před/po): síť 14→1, dotyk 1→0.
  - **Zbytkové (odloženo):** vodní plochy do kotvy (zatím jen toky, shoda s krokem 0); ladění stropu.

## OOM draw order = priorita barev (Sez. 18, zafixováno)

Draw order v OpenOrienteering Mapper určuje **pořadí (priorita) BAREV**, ne pořadí symbolů/objektů
ani rastrový z-order generátoru. Nižší priorita = navrch (Purple overprint = 0 = úplně navrch).
Pořadí je závazně definované IOF (*Printing and Colour Definitions*, kap. 7 Colour order); krycí
klony (*White over green*, *Black below brown*…) jsou jeho součást — neladí se ručně.

- **Důsledek pro generátor:** `.omap` export referencuje symboly přes ISOM kód → zdědí draw order
  template. **Color-table = uživatelova OOM doména** (Colors okno), ne úkol generátoru.
- **OOM ISOM 2017-2 ≠ ideální IOF:** reálná sada má budovu 521 na „Black below purple" (priorita 8,
  pod vrstevnicí 6) — záměr (budova pod tratěmi 7), vedlejší efekt = vrstevnice nad budovou. Chtít
  budovy nad vrstevnice = vědomá odchylka od ISOM separace (uživatel v OOM).
- **Anotační kanál uživatel → AI:** čísla kontrol **ISOM 704** v separátním `.omap` (ne v `map.omap`,
  který se přepisuje); čtečka 704 → až bude první vstup (foundations — nestavět bez konzumenta).

- **Reálné cesty + vodstvo z INSPIRE (UC2 → UC4-II, navrženo Sez. 14).** Uživatel navrhl dosadit
  reálné cesty z **INSPIRE Transport Networks (TN)** a vodu z **INSPIRE Hydrography (HY)** jako
  vektorovou vrstvu → ISOM symboly (502-507 / 301-305) + GT maska (rozhodnuto: vektor, ne podklad).
  > **Aktualizace (Sez. 16): cesty realizovány přes ZABAGED nativní, NE INSPIRE TN** (viz bod výše).
  > Důvod: ZABAGED má bohatší kategorizaci komunikací pro les + tatáž `ags.cuzk.gov.cz` doména jako
  > DMR + GeoJSON output. INSPIRE TN = harmonizovaná EU verze téhož → zbytečná abstrakce. **INSPIRE HY
  > voda: rozhodnuto Sez. 17 = ZABAGED nativní** (jako cesty), ne INSPIRE HY (zbytečná harmonizovaná abstrakce).
  **Past (oponováno):** navržené URL byly **WMS** (`WMS_INSPIRE_TN/HY`) = rastr (obrázek), z něj by
  se vektor musel segmentovat — ztrátový UC4-III problém. Správně **WFS** (`WFS_INSPIRE_TN/HY`, GML
  vektor) nebo INSPIRE download. Izomorfní s lekcí ZM5-rastr/ZABAGED-vektor (výše).
  - **Vztah k ZABAGED úvaze (výše):** TN je harmonizovaná EU verze téhož, co ZABAGED Polohopis
    (komunikace) — dva zdroje téhož; rozhodnout, který (ZABAGED nativní vs INSPIRE harmonizovaný).
  - **Vztah k procedurální větvi:** INSPIRE HY voda je **data-driven alternativa** k plánovanému
    procedurálnímu **D8 hydro jádru** (toky/jezera/bažiny z výškopisu, stupeň 1). Nemíchat: proc =
    noise-půlka, INSPIRE = real-půlka.
  - **Cena/podmínky:** nový WFS konektor (první reálný UC2 konektor — dosud „research only"),
    GML parsing, mapování kategorií → ISOM (ne 1:1), **real-only** (georef S-JTSK), licence INSPIRE
    ČÚZK ověřit do KB. **Foundations:** velký kus → dedikované příští sezení, ne přílepek (rozhodnuto
    Sez. 14: zatím jen zápis sem, UC2 konektor samostatně).
