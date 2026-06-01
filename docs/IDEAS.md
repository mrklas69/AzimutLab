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
AzimutLab. Důvod „Lab": sada nástrojů/experimentů/info, ne jediná aplikace. Doména volná,
obsazenost ověřena (kolize jen mimo doménu). *(Pruning Sez. 50: seznam vyřazených alternativ smazán.)*

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

## `synthesize_pseudorealistic_map` — generátor jako prediktor mapy (Sez. 23, %THINK) → kód Sez. 25

> **Přejmenováno zpět na `generate_map` (Sez. 39).** Důvod: v komunikaci převládl „generátor"
> (izomorfismus jméno↔kód) + funkce je dnes jediný vstup pro OBĚ větve (real i noise přes
> `terrain=`), takže „pseudorealistic" v názvu je pro noise větev nepřesné; `generate_map` je
> přesnější deštník (i pro budoucí generátory). Důvody přejmenování Sez. 23 (níže) tím z velké
> části padly. **„Pseudorealistická" zůstává jako vlastnost VÝSTUPU** (GLOSSARY „Pseudorealistic
> map"), ne názvem funkce. Kolize `generate`↔`procedural` je dnes teoretická (noise je „na zánik").

Reframe real-větve: z „feeder" na **prediktor mapy** pro konkrétní lokalitu. Cílové API
**`synthesize_pseudorealistic_map(n, e, w_km, h_km)`** — „synthesize" = skládá 2 zdroje;
„pseudorealistic" = vypadá real, není skutečné mapování; snake_case (Python). Zamítnuto
`GetPredictedMap` (`Get` = existující mapa) a `GenerateProceduralMap` („procedural" je rezervováno
pro noise-feeder, kolize s `generator-procedural.md`). Dvoufázový (A2 uživatele):

> **Realizováno Sez. 25** (přejmenování `generate()`). Finální signatura se od návrhu liší:
> `synthesize_pseudorealistic_map(lat, lon, w_km, h_km, only_real=False, out_dir="output", *, …)`.
> Odchylky: (1) `lat/lon` (WGS84) místo `n/e` — kód i konektory mluví WGS84, S-JTSK je až
> interní georef. (2) Přidán `only_real` (vypíná fázi 2, sladěno s CLI `--only-real`) a `out_dir`.
> (3) Noise (Option 1) větev + per-vrstva toggly **zachovány** jako keyword-only ocas
> (`seed/rug/det/terrain/paths/…`, default `terrain="real"`) — z popředí API zmizely, ale žijí.
> `_apply_extent(w_km, h_km)` se přesunul dovnitř funkce (rozměr je teď parametr). Dev lokality
> SV/NL/LS = `DEV_LOCATIONS` + CLI `--location` (6×4 km, DRY zdroj souřadnic).
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
- **ISSprOM / sprint pipeline (Sez. 25).** `template_sprint.omap` je hotový ISSprOM template,
  ale celý generátor stojí na ISOM (omap_export `TEMPLATE_PATH=classic`, ZABAGED→ISOM mapování
  502/521/510, ladění na lesní OB). Sprint = jiná disciplína: městský terén, dominují budovy,
  jiná symbolika. Skutečná sprint mapa = nový balík: přepínání template classic↔sprint +
  přemapování ZABAGED→**ISSprOM** + ladění na město. Míchá dvě specifikace → samostatné sezení,
  ne přílepek (foundations). Spouštěč: až bude ISOM jádro pevné a vznikne potřeba sprintu.
  Pozn.: Lidové sady (LS) zatím generujeme jako **classic ISOM** (městsko-lesní výsek — natrénuje
  i hustou zástavbu); ISSprOM verze je tato budoucí položka.
- **ISOM 2000 ↔ 2017-2 domain gap — ZAVŘENO (Sez. 37 nález → %THINK 38+40 → DONE).** Reálné mapy v
  `resources/` jsou ISOM 2000, generátor 2017-2; čísla se recyklují s jiným významem (526=budova 2000 vs
  521 v 2017-2 atd.). **Rozhodnuto: zůstat 2017-2 + deklarace verze (`meta["isom"]`, Sez. 38) + crosswalk
  pro vektor (OOM `docs/kb/ISOM2000-ISOM2017-2.crt`, GPL); NEgenerovat zvlášť 2000.** Pro UC5 (čte pixely)
  je relevantní jen vizuál, ne čísla — a vzhled kostry (101/102/103) je verzně identický; dominantní rozdíl
  je obsahový (vegetace = recall gap), ne verzní. Detail v DONE Sez. 38/40 + GLOSSARY. Nezaměňovat s [[issprom]].
- **Grivace v generátoru — `--grivation` (Sez. 37, nápad uživatele).** Generátor renderuje grid-north-up
  (S-JTSK osy); reálné OB mapy jsou **magnetic-north-up** (georef nese rotaci o grivaci = konvergence +
  magnetická deklinace; SV −11,4°). Kotva už v kódu (`meta.georef.north="grid"`, `grivation_deg:null`).
  **Dvě izomorfní polohy (různí konzumenti):** (1) `.omap` jako **metadata** — nastavit georeferencing na
  reálný Křovák (ref_point + PROJ) + atributy `declination`/`grivation` jako kartograf → OOM zobrazí mapu
  magnetic-north-up a dokreslí čáry severu sám (conceptual-integrity správně pro vektor); (2) **rotace rastru**
  `rgb.png` o grivaci + zapečený `.pgw` (až bude rastrový konzument — UC4-III sken / UC3 / UC5). Grivaci buď
  zadat (`--grivation`), nebo dopočítat (konvergence z pyproj `get_factors` + deklinace z geomag. modelu).
  Pro samotný verify-overlay NEPOTŘEBA (georef rotaci dorovná) — je to feature pro věrnost výstupu.
- **Zánik noise (Option 1) větve — predikce uživatele (Sez. 25, „sázka").** Reframe Sez. 23 udělal
  z real-prediktoru hlavní směr; noise (fraktální šum) byla úplně první PoC. Uživatel sází, že
  keyword-only ocas (`seed/rug/det/terrain/paths/…`) jednou zmizí. Pravděpodobně ano — až UC5 feeder
  poběží na reálném prediktoru, noise nemá konzumenta. **Protiargument (nezahazovat hned):** noise je
  levný **offline deterministický regresní check** (proc baseline 65 bez WFS/sítě) — spíš degraduje
  na test fixture než zmizí. Rozhodnout, až real-prediktor + UC5 dozrají; do té doby ocas zůstává.
- **Synteticky renderované trénovací mapy** (původní jiskra projektu z Pic2Omap ML pilotu) —
  patří pod UC4-I/II + UC5 trénink. **→ DONE (Sez. 4): realizováno jako PoC** —
  procedurální generátor (spec `docs/kb/generator-procedural.md`, kód `generator/`).
  **Reframe:** ne „nejvzdálenější", ale **enabler-feeder pro UC5** — GT zdarma obchází
  sparse-GT past. Reálný terén (ČÚZK DMR 5G) dosazen přes `--terrain real` (§8.5, hotovo Sez. 5).
- **Reálné vrstvy ze ZABAGED (UC2 → UC4-II). → DONE (Sez. 16–33).** Realizováno přes `zabaged.py`
  (ArcGIS REST, GeoJSON) jako **real-půlka** generátoru: cesty 502-506 (Sez. 16), voda 301/304-306
  (Sez. 17), budovy 521 (Sez. 18), vedení 510 (Sez. 24), řopíky (Sez. 27), železnice 509 + kolejiště
  501 (Sez. 28), skály 204/206/207 (Sez. 30), mosty/tunely 512 + lávky 512.2 (Sez. 31-33). Vše, co
  úvaha předpovídala, sedlo: vysoká věrnost, přesná GT z vektoru, real-only, mapování ne 1:1
  (fyzický stav → ISOM). Detail: DONE + spec §4.9* + `zabaged-isom-catalog.md`. (Lekce „ze ZM5" byl
  omyl — ZM5 zrušený rastr 1.7.2023; vektor je v ZABAGEDu. Proc hydro jádro D8 = budoucí noise-půlka.)
- **Plochy ZABAGED → ISOM (pastvina/hřbitov/hřiště/les/…) — návrh uživatele Sez. 39, s výhradou.**
  Pokračování katalogu UC2 plošnými land-use vrstvami. **Rozdělit podle toho, co je tvrdá projekce
  a co vegetační dohad (vegetace gate, Sez. 3):**
  - **Čistá projekce (lze hned):** hřbitov / hřiště / zpevněné plochy → 520 (out-of-bounds/built-up)
    nebo 501 (Paved area) — fyzický fakt, ne prostupnost. Izomorfní s budovami/kolejištěm.
  - **Vegetační dohad (BLOKOVÁNO gate):** les / pastvina / louka. ISOM zelená/žlutá kóduje
    **prostupnost (runnability), NE land-use.** Polygon „les" ze ZABAGED neříká, zda je čistý
    běžecký les (bílá) nebo hustník (tmavě zelená) — to je **UC5 predikce, ne projekce** (stejná
    logika jako runnability u průseků 508 Sez. 36, pramen 312, vegetace gate Sez. 3). Vymýšlet
    barvu prostupnosti z holého land-use = dekorace nad rámec dat. Až bude UC5 model + korpus.
  - **Před kódem: vlastní `%THINK`** — projít všechny kandidátní vrstvy a roztřídit projekce/dohad
    (verify-against-source v ZABAGED katalogu + ISOM spec, co která plocha skutečně znamená).
- **Lepší polygonizace skalních útvarů — návrh uživatele Sez. 39, oponováno (čeká na důkaz vady).**
  „Lepší polygonizace" = generalizace skal. **Naráží přímo na Sez. 30 + princip CLAUDE.md
  „generalizuj jen s důkazem, raw je default":** Sez. 30 vědomě zavrhla Chaikin smoothing
  i hybridní práh 202/206 „bez datového podkladu" → RAW jako voda (`Shape_Area` ~120 vrcholů /
  32×32 m = „už pěkné"). **Blokátor = chybí ukázaná konkrétní vada** současných RAW polygonů.
  Až bude (uživatel ukáže na výstupu, oko = source), pak rozhodnout druh generalizace s důkazem —
  ne preventivně. Pozn.: souvisí s odloženými `Skupina_balvanů__linie_`→208 / `Sesuv_půdy__suť`→210
  (TODO drobnost Sez. 30), které area-pattern teprve potřebují.

## Kartografická generalizace budov — ZAVRŽENO (Sez. 27)

**Celá generalizace budov zavržena: budovy se kreslí RAW jako voda.** Domněnka „feeder se učí číst
GENERALIZOVANOU mapu" se nepotvrdila — generalizace KOMOLILA tvar/polohu. Smazáno ~430 LOC tří úrovní:
**L1** min. velikost + Douglas-Peucker obrys (Sez. 18), **L1b** orthogonalizace/pravoúhlost (Sez. 27),
**L2** displacement od pevné sítě 8 iterací (Sez. 21-22, vč. `diagnose_displacement.py`). **Zásada →
CLAUDE.md: generalizuj jen s důkazem, raw je default** (voda byla dokonalá právě proto, že raw).
Detail v DONE (Sez. 18/22/27) + GLOSSARY „kartografická generalizace".

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

- **Reálné cesty + vodstvo z INSPIRE (UC2, navrženo Sez. 14) — VYŘEŠENO ve prospěch ZABAGED nativního.**
  Cesty (Sez. 16) i voda (Sez. 17) realizovány přes **ZABAGED nativní, NE INSPIRE TN/HY** — ZABAGED má
  bohatší kategorizaci pro les, tatáž `ags.cuzk.gov.cz` doména + GeoJSON; INSPIRE = harmonizovaná EU verze
  téhož = zbytečná abstrakce. **Trvalá lekce (oponováno):** navržené INSPIRE URL byly **WMS** (rastr) — pro
  vektor → ISOM je třeba **WFS/REST** (jinak ztrátová segmentace), izomorfní s lekcí ZM5-rastr/ZABAGED-vektor.

## Časosběr ortofota → věk porostu / vegetace (Sez. 63 %THINK + measure-first)

**Příležitost:** ČÚZK má **archiv ortofota 1998–2023** (barevné od 2002, vrstvy po ročnících přes WMS
`WMS_ORTOFOTO_ARCHIV` `LAYERS=<rok>`) + **CIR (NIR) archiv 2010–2023** (`WMS_ORTOFOTO_CIR`) → NDVI časová
řada. Vše ortorektifikované v S-JTSK (kořegistrace zadarmo, mirror `ortofoto.py`). Koncepčně nejsilnější
cesta k VĚKU/zmlazení (Sez. 61 K3): detekce holina→zmlazení dá **pozorovaný věk porostu** = co forest-age
(Sez. 62) jen vypůjčil z AOPK, ale **národní bezešvé** (vyřeší díru SV/HS), **aktuální** (vč. kůrovce 2018-24),
a krmí budoucí **UC5 model**.

**ALE měřeno (probe `temp/orto_probe/probe_ndvi.py`, NL Jizerky) — NENÍ čistý quick-win:**
- Open CIR je **display PNG, ne reflektance** (8-bit stretchnutý per-snímek) → absolutní NDVI nesmyslné,
  cross-epoch diff confounded.
- **Radiometrický drift** mezi epochami (mean NDVI 2021=0,145 vs 2023=0,115) → naivní 2-epoch práh dal
  **12,8 % „holiny" = z velké části ŠUM** (změnová mapa sůl-a-pepř, ne koherentní paseky).
- **Pokrytí lokálně řídké** — NL měl z 2010-23 jen 2021+2023 (žádná bohatá řada).

**Závěr:** deterministická change-detekce z open ČÚZK CIR = **skutečný CV projekt** (relativní normalizace +
robustní multi-epoch ne 2-epoch + kořegistrace + pokrytí), NE samostatná věrná vrstva přes ruční práh.
Invariance vůči driftu = přesně to, co **model** zvládne líp → časosběr je svou povahou vstup pro **PREDIKCI
(UC5)**, deterministicky leda hrubý feature / generátor trénovacích labelů. **AOPK věk (Sez. 62) je teď
čistší zdroj** než naivní ortofoto-change. Single-epoch CIR segmentuje les/otevřeno čistě (ale to máme ze ZABAGED).

**Fáze (až někdy):** A měření hotovo (negativní pro naivní diff) · B robustní temporal (normalizace, >2 epochy) ·
C UC5 model (ortofoto+DMR+věk → runnability, GT reálné mapy) = skutečný gate-breaker. Probe artefakty `temp/orto_probe/`.

### Drátěný model vegetace (Sez. 64 měření) — greenness z ortofota NEODDĚLÍ ISOM zeleň

Návrh uživatele: GT 3 zelené z `.omap` vs hranice z ortofota, test úspěšnosti. **Změřeno** (Velbloud,
`temp/orto_probe/probe_veg_wireframe.py`: GT bílá/open/406/408/410 po barvě reuse `compare` refs, vs CIR
NDVI + textura v S-JTSK gen-gridu): **separabilita ~50 % (náhoda) na L1/L2/L3.** Část = limit probu
(display-PNG NDVI ne reflektance, 2,5 m, 1 epocha, temporal/registrační měkkost → podstřeluje snadné úrovně),
ale STRUKTURÁLNÍ závěr platí:
- **NDVI/zeleň odlišuje vegetaci od ne-vegetace; ISOM třídy jsou VŠECHNY vegetace** (open=tráva, les=koruna,
  hustník=koruna → spektrálně totéž). Greenness = špatný nástroj na runnability.
- **Marginální hodnota nízká:** L1 (open/les) už máme deterministicky ze ZABAGED (401); L2/L3 (podrost) =
  jediné co by ortofoto přidalo, a to je gate (shora neviditelné, Sez. 59). Není vada měření, vlastnost úlohy.
- **Co z ortofota dává smysl:** struktura v ČASE (holina/věk = paseka shora vidět) → age proxy, krmí MODEL
  (strukturní rysy: CHM/výška, jemná textura, multi-temporal). Single-epoch greenness→třída ne.

**Data-reality friction (změřeno):** CIR archiv velmi řídký (Velbloud má CIR DATA jen 2023, 2016-22 prázdné);
coverage-check MUSÍ být po pixelech (prázdná bílá dlaždice je taky `image/png` — content-type nestačí); RGB
archiv hustší (Velbloud 2015/17/19/21/23). GT extrakce 3 zelených z reálné mapy po barvě FUNGUJE
(reuse `compare` ISOM_REF green_l/m/d) — to je použitelný kus pro budoucí trénovací korpus.
