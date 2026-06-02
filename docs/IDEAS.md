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

## Generátor jako prediktor mapy (Sez. 23 %THINK → kód Sez. 25, DONE) — zde jen vize

Reframe real-větve z „feeder" na **prediktor mapy** pro konkrétní lokalitu. Dvě fáze:
- **(1) projekce** podkladů — DMR→vrstevnice, ZABAGED→ISOM cesty/voda/budovy. Deterministický převod,
  *máme* (real-větev).
- **(2) predikce** chybějících symbolů (vegetace/průchodnost — co v geodatech NENÍ, vegetace gate)
  z podobných lokalit (retrieval-augmented prior) = **UC5**. **Blokátor: korpus + licence** (ČSOS gate
  Sez. 8) — bez zmapovaných map jako GT nelze učit. První predikční střípek: `--forest-age` (Sez. 62, PROXY).

Funkce přejmenována `synthesize_pseudorealistic_map`→`generate_map` (Sez. 39); „pseudorealistická" zůstává
**vlastností výstupu** (GLOSSARY), ne názvem. **Detail: DONE Sez. 23/25/39 + GLOSSARY (projekce vs predikce).**

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
- **ISOM 2000 ↔ 2017-2 domain gap — ZAVŘENO (Sez. 37→38+40, DONE).** Rozhodnuto: zůstat 2017-2 + deklarace
  verze (`meta["isom"]`) + crosswalk pro vektor (`docs/kb/ISOM2000-ISOM2017-2.crt`, GPL); NEgenerovat 2000.
  Pro UC5 je relevantní vizuál, ne čísla (kostra 101/102/103 verzně identická; dominantní rozdíl je obsahový
  = vegetace recall gap). Detail DONE Sez. 38/40 + GLOSSARY. Nezaměňovat s [[issprom]].
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
- **Synteticky renderované trénovací mapy → DONE (Sez. 4).** Původní jiskra (Pic2Omap ML pilot) realizována
  jako procedurální generátor (`generator/`, spec `generator-procedural.md`); reframe = **enabler-feeder pro
  UC5** (GT zdarma obchází sparse-GT past). Reálný terén `--terrain real` (Sez. 5).
- **Reálné vrstvy ze ZABAGED (UC2 → UC4-II) → DONE (Sez. 16–57); fáze I VYTĚŽENA (Sez. 58, doloženo měřením).**
  `zabaged.py` (ArcGIS REST, GeoJSON) = real-půlka generátoru. Úvaha sedla: vysoká věrnost, GT z vektoru,
  mapování fyzický stav → ISOM (ne 1:1). Detail: DONE + spec §4.9* + `zabaged-isom-catalog.md` (SSoT stavu
  vrstev). Lekce „ze ZM5" byl omyl (ZM5 zrušený rastr 1.7.2023; vektor je v ZABAGEDu). Proc hydro D8 = budoucí noise-půlka.
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

- **INSPIRE cesty+voda (Sez. 14) — VYŘEŠENO ve prospěch ZABAGED nativního** (bohatší kategorizace, tatáž
  doména `ags.cuzk.gov.cz`, GeoJSON; INSPIRE = zbytečná harmonizovaná EU abstrakce téhož). **Trvalá lekce:**
  pro vektor→ISOM je třeba **WFS/REST**, ne WMS (rastr = ztrátová segmentace), izomorf s lekcí ZM5-rastr/ZABAGED-vektor.

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

## UC5 runnability korpus — reálné OB mapy z Livelox (Sez. 67 %THINK + deep research)

**Kontext:** UC5 runnability model (predikce zelené 406/408/410 + žluté z ortofota/DMR/věku) je
**supervised** → potřebuje GT = co kartograf nakreslil na reálné mapě. [[vegetace-gate]] (Sez. 59) brání
syntetické GT (generátor runnability neumí věrně → trénink ze syntetiky cirkulární), takže korpus MUSÍ být
z reálných map. **Volba směru Sez. 67 = C (korpus/GT nejdřív)** před stavbou modelu.

**Pragmatická cesta (volba uživatele):** projekt je z ~99 % privátní nekomerční experiment (repo private)
→ korpus ~100 map stažených **bez předchozí licence**; legalizace AŽ pokud model funguje (pak oslovit ČSOS
o spolupráci). Právní krytí: **TDM výjimka** (autorský zákon ČR po novele 2023 / EU DSM 2019/790 —
rozmnožování pro automatizovanou analýzu = vědecký výzkum, nekomerční bez opt-out). *(Přesné znění k ověření.)*

**Zdroj = Livelox (deep research Sez. 67, vysoká shoda 3-0):**
- Stažitelný přes interní endpointy `/Data/ClassInfo` + `/Data/ClassBlob` (POST `classId` → URL mapy +
  4 rohy quad). Dva nezávislé aktivní open-source nástroje: `yoav28/livelox-map-downloader-extension`
  (MIT), `routechoiceslivegps/map-downloader` (běží live `map-download.routechoices.com/livelox/`).
- **Jen RASTR** (PNG/WebP) — vektor Livelox přijímá na uploadu, ale 3. strana nestáhne → **GT runnability =
  barevná segmentace** (reuse `compare` refs Sez. 64), ne čistý symbol. Čistý vektor `.omap` jen přímo od
  kartografů (otevřená cesta).
- Georef = **4 WGS84 rohy** (bounding quad, žádný EPSG/world-file) → reprojekce do S-JTSK 5514 (pyproj).
- Obchází Livelox podmínky („maps not accessible through API for copyright reasons"); práva drží
  kartograf/pořadatel/federace. Privátní experiment OK, **legalizace před jakýmkoli sdílením modelu/korpusu**.

**Formát-rozhodnutí (uživatel):** stáhnout OBA zdroje když jdou — **vektor = GT** (preferovaný, čistý symbol),
**rastr = picture** (= „picture" půlka páru pro UC3/UC4-III + fallback); párovat přes společný georef. Z Livelox
reálně jen rastr; vektor shánět jinde.

**Georef pipeline (gen jako reference = inverze compare):** ORIS lookup (název→lokalita, jen metadata/fallback)
→ Livelox download (rastr + quad) → **gen projekce téže lokality** (tvrdá geometrie ZABAGED v S-JTSK = cesty/
voda/olivové 520/budovy) jako **kotva** → feature-fit reálného rastru na projekci (podobnostní transformace
x/y/scale/**rotace = [[grivace]]** ~−11°) → georef rastr → segmentace zelená/žlutá = GT. Lokální deformace map
→ reziduál OK (plošná runnability chce ~metr, ne pixel).

**Dvě gates (measure-first, dřív než korpus 100 map):**
- **Gate 1 — rozlišení:** je Livelox rastr full-res, nebo down-scaled náhled (`images[0]` může být jedna
  dlaždice)? Nezměřeno. Rozhodne, jestli Livelox není druhý ČSOS-watermark slepý roh.
- **Gate 2 — přesnost quadu:** sedne reprojikovaný quad rovnou na ortofoto, nebo je nutný feature-fit? Pokud
  quad přesný → ORIS i fitter zbytečné (overkill). **Probe lokalita = závod uživatele** (Český pohár štafet,
  `classId=1116300`), olivový areál uprostřed mapy **50.6906797N, 14.8303997E** = kotevní bod fitu.

**Validace směru (Petrovič 2018, peer-reviewed, ICA):** používá přesně paradigma „GT = co kartograf nakreslil";
měří, že derivace zelené z LiDAR je hlučná — i po tuningu ~47 % overlap, **zelené třídy nejhorší ~30-31 %**.
Nezávislé potvrzení, že deterministická vrstva nestačí → ML dává smysl (opora celého UC5 směru).

**MapAnt FI / MapantES VYLOUČIT z GT** — strojově generované z LiDAR (Karttapullautin) → trénink cirkulární.
Žádný hotový ML korpus OB map neexistuje (jen metodické papery s jednotlivými referenčními mapami).

**Nástroje do laboratoře:** `connectors/livelox.py` (jistý), GT extraktor segmentace zelená/žlutá (jistý),
`connectors/oris.py` (contingency — metadata/fallback), georef fitter rastr↔gen (contingency — jen když gate 2
selže). **Nestav fitter, dokud quad neselže** (princip „stav až s důkazem").

**Mezery deep research (neověřeno):** World of O Map Archive / MapRun / Attackpoint / IOF Eventor /
skandinávské archivy — možný zdroj VEKTORU (preferovaná GT); objem map ČR/globál; batch/rate-limit Livelox;
nativní rozlišení.

## UC5 runnability model — architektura (Sez. 74 %THINK)

Korpus (216 keep) + čistá GT (`map_gt.py`, labely 0-4 + 255 ignore) hotové → stavba prvního
**supervised modelu**. HW doložen: trénink jen na `mrkla` (RTX 5070, 12 GB, BF16) — viz
`docs/kb/hardware.md`. Rozhodnutí uživatele (Q1-Q3): **vstup jen ortofoto RGB**, **predikce
všech 5 tříd** (eval primárně zelená), **smoke test první**.

**Hlavní teze (oponentura „skoč rovnou na model"):** největší riziko NENÍ architektura
(segmentačních sítí je pět a všechny fungují), ale **kvalita párů (vstup, GT)**. Model je tak
dobrý jako zarovnání vstupu s cílem. GT je hustá/čistá, ale **vstup (ortofoto) zatím vůbec
neexistuje vyrobený** — jen georef v `meta.json`. Foundations: pár (X,Y) je základ, model
záclona. Gaty PŘED model.

**Osy rozhodnutí:**
- **A. Úloha:** 5 tříd (0 podklad / 1-3 zelená 406/408/410 / 4 open) + 255 ignore. Eval
  **per-class IoU** (průměr by maskoval, že fight(3) je vzácný a model ho ignoruje); hodnota = zelená.
- **B. Vstup = jen ortofoto RGB** (volba uživatele). DMR/forest-age kanály až jako MĚŘENÁ ablace,
  jen když RGB nestačí (lekce „raw default, generalizuj s důkazem"; navíc ISOM zeleň = vegetace,
  ne sklon → DMR slabá vazba).
- **C. GATE 1 — zarovnané páry (measure-first):** `build_georef_blend` z 80 % hotový (warpne mapu
  do S-JTSK gridu + stáhne ortofoto výseku) → rozšířit, aby uložil čistý ortofoto rastr + GT
  přewarpovaný do téhož gridu. **Změřit georef offset** (overlay cesty/vody mapy na ortofoto):
  systematický posun >~3-5 m = model se učí šum. Sez. 68 „quad sedne bez fitu" byl vizuál na 4
  mapách, ne změřená pixelová přesnost.
- **D. ČR vs DE:** ČÚZK ortofoto jen ČR (S-JTSK). DE keep mapy (Žitavsko) nemají vstup →
  **samy se odfiltrují** (ČÚZK export mimo ČR = prázdná dlaždice). Saské DOP = volitelný pozdější
  konektor. Změřit, kolik keep map zbude (čistě ČR set).
- **E. Split (leak past):** mapy se geograficky překrývají → **náhodný per-mapa split LEAKUJE**
  (stejný les v train i val). Split MUSÍ být geografický (clustery dle bbox overlapu; souvisí
  s odloženým „dedup georef overlap" Sez. 70).
- **F. Dlaždice:** 93 Mpx/mapa se nevejde do 12 GB → dlaždice 512×512 s overlapem, společný grid
  ~1,0-1,33 m/px (512 px ≈ 600-680 m = vegetační kontext).
- **G. Architektura:** `segmentation-models-pytorch` U-Net + ImageNet-pretrained ResNet34 encoder
  (precedent Pic2Omapu, sourozenec; vejde se do 12 GB; transfer pomáhá při 216 mapách). BF16
  mixed precision (Blackwell Tensor Cores). Žádná exotika, dokud baseline nestojí.
- **H. Class imbalance:** 0 dominuje, fight(3) vzácný → CrossEntropy(`ignore_index=255`) +
  class weights / Dice / Focal. Změřit rozložení tříd nejdřív.

**Produkt:** natrénované váhy (`.pt`, gitignored) + inference skript. NE knihovna (fáze B =
sys.path skripty). Cíl: nová vrstva generátoru `--vegetation predicted`, která zacelí vegetace
gate (druhá půlka generátoru = predikce, viz „Generátor jako prediktor").
