# GLOSSARY — AzimutLab

Terminologie projektu. Krátké definice + odkaz na zdroj pravdy (detail nekopírujeme —
DRY). Pojmy se zavádějí, jak je projekt potkává; doplňuj v `%END`.

## Doména — orientační běh a mapy

- **OB** — orientační běh; sportovní disciplína navigace v terénu podle mapy.
- **ISOM** (International Specification for Orienteering Maps) — norma pro klasické
  lesní OB mapy (**verze 2017-2, nejnovější — Rev 6 z 2024**, příští až ISOM2030). Symboly,
  barvy, priority. Cílová sémantika projektu. Detail: `docs/kb/isom-issprom.md`. Pozor: Rev 6
  **přečíslovalo bodové symboly** (109/110/111 vs staré 2017 112/113/115 — Sez. 13).
- **ISSprOM** — sesterská norma pro sprintové / městské mapy (2019-2). Stejný kód ≠
  stejný symbol napříč ISOM/ISSprOM (např. budovy black vs gray).
- **Vrstevnice** (contour) — izolinie výškového pole, spojnice bodů stejné nadmořské
  výšky. ISOM symbol **101**. Z principu se nekříží a nekončí ve vzduchu.
- **Index contour** (zvýrazněná / hlavní vrstevnice) — každá pátá vrstevnice, silnější
  čára pro snazší čtení. ISOM symbol **102**. V generátoru každých 25 m.
- **Form line** — pomocná vrstevnice mezi základními. ISOM **103**. Generátor zatím nedělá.
- **Ekvidistance** — svislý rozestup vrstevnic (v projektu 5 m).
- **Kopeček** (knoll) — malá vyvýšenina; je-li menší než zobrazitelná vrstevnicí, kreslí
  se bodovým symbolem. ISOM **109** (Small knoll, kulatý) / **110** (Small elongated knoll,
  protáhlý). Generátor je odvozuje z malých uzavřených vrstevnic (lokální max, Sez. 10).
  (Kódy dle ISOM 2017-2 Rev 6 — staré 2017 mělo 112/113, viz pozn. u ISOM.)
- **Prohlubeň** (depression) — malá terénní sníženina. ISOM **111** (Small depression,
  hnědý oblouk „⌣"; staré 2017 = 115). Generátor z malých uzavřených vrstevnic (lokální
  min). **112 Pit** (jiná feature class — umělá/erozní díra) generátor nedělá (neodvoditelný
  z výškopisu).
- **Kartografická generalizace** — zjednodušení reality pro čitelnost mapy. V generátoru zbyla jen
  (1) malý kopeček/prohlubeň → bodová značka místo prstence (§4.10). **Generalizace BUDOV byla zavržena
  (Sez. 27):** min. velikost (`_enforce_min_size`), Douglas-Peucker obrys, orthogonalizace/pravoúhlost
  (Sez. 27) i displacement (L2, Sez. 22) komolily skutečný tvar/polohu → smazáno, budovy kresleny **RAW
  jako voda**. Zásada: **generalizuj jen s důkazem, raw je default** (CLAUDE.md). [[budova-stavba]]
- **Draw order / priorita barev** — pořadí vykreslování vrstev v OOM. Určuje ho **pořadí (priorita)
  BAREV** v mapě (nižší priorita = navrch; Purple overprint = 0 = úplně navrch), NE pořadí symbolů
  ani objektů. Závazně definované IOF (*Printing and Colour Definitions*, kap. 7); krycí klony
  (*White over green*, *Black below brown*…) jsou jeho součást. `.omap` export generátoru zdědí
  draw order z template → color-table je doména editace v OOM, ne generátoru (Sez. 18). Pozn.:
  OOM ISOM 2017-2 sada má budovu 521 na prioritě 8 (pod vrstevnicí 6 — záměr: budova pod tratěmi).
- **Cesta / pěšina** — liniová komunikace. ISOM škála dle zřetelnosti/sjízdnosti:
  **502 Wide road** (silnice — hnědý pás s černými okraji, render `casing` s `C_ROAD` výplní; pozor:
  502 a 503 jsou v ISOM templatu STEJNĚ tlusté, liší se plná/čárkovaná) · **503 Road** (zpevněná,
  plná černá 2 px) · **504 Vehicle track** (vozová, nezpevněná, čárkovaná 2 px) · **505 Footpath**
  (pěšina, čárkovaná **1 px** — template 250 µm, Sez. 23) · **506 Small footpath** (malá/neudržovaná).
  Generátor má dvě větve (`--paths`): **proc** = procedurální Dijkstra least-cost (§9), hlavní 503 /
  vedlejší 505; **real** = reálné komunikace ze ZABAGED WFS (Sez. 16), plná hierarchie 502-506 dle
  povrchu/udržovanosti. Vrstvy: `Silnice__dálnice`/`Ulice`→502, **`Silnice_neevidovaná`** (účelové/lesní
  asfaltky, Sez. 23)→503, `Cesta` zpevněná→503 / nezpevněná→504, `Pěšina`→505/506.
- **Vodní tok / vodní plocha** (hydrografie) — voda na OB mapě, modrá. Toky ISOM **304**
  Crossable watercourse (hlavní, pojmenovaný) / **305** Small crossable watercourse (přítok) /
  **306** Minor/seasonal water channel (občasný, čárkovaný); plochy **301** Uncrossable body
  of water (výplň + břehová linie). **312 Spring** (pramen — pozor, ne 313 = Prominent water
  feature). Generátor `--water real` (Sez. 17): reálná půlka ze ZABAGED `Vodní_tok`/`Vodní_plocha`
  + `Pozemní_nádrž` (umělé nádrže vč. **koupališť/bazénů** `podtypob_k='BA'` → 301, Sez. 27 — Lesní
  koupaliště LS chybělo, je nádrž ne `Vodní_plocha`); podzemní toky (`typtoku_k=004`) se nekreslí.
- **Budova / stavba** — umělý objekt na OB mapě. ISOM **521 Building** (plošný černý symbol,
  výplň + obrys). Generátor `--buildings real` (Sez. 18): reálná půlka ze ZABAGED
  `Budova_jednotlivá_nebo_blok_budov__plocha_` (mapování `map_building_to_isom` → 521; vodojem
  taky 521). Render izomorfní s vodní plochou 301 (`_draw_area_symbol`), jen černá místo modré.
  **RAW půdorys (Sez. 27):** kresleno přesně jako voda (syrový ZABAGED ring), BEZ generalizace či
  displacementu — ty komolily tvar/polohu (viz [[kartografická-generalizace]]).
- **El. vedení** — elektrické vedení na OB mapě. ISOM **510 Power line, cableway or skilift**
  (tenká černá linie s kolmými příčkami na SLOUPECH — běžci se jimi řídí). Generátor `--powerlines
  real` (Sez. 24): reálná půlka ze ZABAGED `Elektrické_vedení` (linie → osa) + `Stožár_elektrického_
  vedení` (body → příčky). Mapování `map_powerline_to_isom` → vždy 510 (`NAPETI` v datech prázdné →
  bez rozlišení 511 Major power line). **Pozor: 510, NE 516** (516 = Fence/plot — oprava zděděného
  předpokladu, verify proti template, Sez. 24). Příčky = dvě fáze (viz [[pseudorealistic]]).
- **Železnice** — železniční trať na OB mapě. ISOM **509 Railway** — v `template_classic.omap` **kombinovaný
  symbol** (type 16): černé čárky (0,35 mm; dash 1,5 / break 1,0 mm) + bílý „pražcový" knockout (`White for
  railway`), NE prostá linie jako vedení 510. Generátor `--railways real` (Sez. 28): reálná půlka ze ZABAGED
  `Železniční_trať` (id 75) + `Železniční_vlečka` (76, nádražní/průmyslové vlečky — u nádraží svazek kolejí);
  obě → 509 (`map_railway_to_isom`, KISS). Render mode `"railway"` = bílý knockout podklad + černé čárky navrch
  → mezery jsou BÍLÉ (odliší od pěšiny 505, jejíž mezery ukazují terén). Pozor: vrstva je `Železniční_trať`,
  ne „Železnice" (oprava TODO, Sez. 28).
- **Kolejiště / zpevněná plocha** — nádražní kolejová plocha (a obecně zpevněné plochy). ISOM **501 Paved
  area** — kombinovaný symbol (hnědá výplň + **obrysová linie**). Generátor `--paved real` (Sez. 28): reálná
  plošná půlka ze ZABAGED `Kolejiště` (id 122; `map_paved_to_isom` → 501), render `_draw_paved_area`
  (`C_ROAD` výplň + `C_BROWN` obrys, izomorfní s vodní plochou/budovou). **„10 kolejí" u nádraží v datech
  NEJSOU linie — ZABAGED je generalizuje do jedné plochy `Kolejiště`** (Liberec hl. n. ~19 ha). V `.omap`
  jako **kombinovaný 501 (s obrysem)**, ne 501.1 bez obrysu — **do kolejiště se nevstupuje**, bounding line
  je významová (rozhodnutí uživatele, Sez. 28; viz [[crossability]]). Sym id 105 (501.1 = id 106, čistá plocha).
- **Crossability (překonatelnost hranic)** — ISOM kóduje **stylem obrysu/linie, zda lze hranici překonat**:
  301 Uncrossable body of water (plný břeh = NEpřekonat, obíhat) vs 304/305/306 crossable watercourse
  (přebrodit/překročit); plný obrys nepřekonatelné plochy (301, kolejiště 501) = bariéra. Generátor to honoruje
  **volbou ISOM symbolu** (a tím i v GT masce přes třídu). Dluh (Sez. 28): všechny vodní plochy → 301, všechny
  toky → crossable → široká nepřekonatelná řeka by byla špatně (TODO). „Brodnost" jako terénní znalost =
  část [[projekce-vs-predikce|predikce]] (UC5), ne vždy atribut v datech.
- **noise-půlka / real-půlka** — dvě paralelní datové osy generátoru: *syntetická* (fraktální
  šum / procedurální cesty) vs *reálná* (ČÚZK DMR 5G výškopis / ZABAGED komunikace + voda + budovy
  + vedení + železnice + kolejiště). Izomorfní: `--terrain noise|real` ↔ `--paths proc|real` ↔
  `--water off|real` ↔ `--paved off|real` ↔ `--buildings off|real` ↔ `--powerlines off|real` ↔
  `--railways off|real`. Nemíchat zdroje napříč osou.
- **Ground-truth (GT)** — referenční „pravdivá" anotace pro trénink/validaci modelu.
  Klíčová výhoda generátoru: každá vrstva je zároveň segmentační maska → GT zdarma.

- **Řopík** (lehké opevnění, ŘOP vz.37) — betonový pohraniční bunkr (čs. opevnění 30. let). V ZABAGED
  bodová vrstva `Bunkr` (`typbunkr_k='LO37'`). Na OB mapě = bodový orientační prvek (NE budova 521):
  asset `ropik_10000.omap` (bunkr na náspu). Generátor `--ropiky real` (integrace Sez. 27): `fetch_bunkers`
  + asset placement; orientace = normála na lokální linii řopíků, „čelní zasypaný násep" VEN k nejbližší
  **státní hranici** (`Hranice správní jednotky` `vyzn_zsh_k='1'`, univerzální ČR — sever u SV, JV u Šumavy).
  Fáze 1 (projekce, real data), NE pseudorealistická dekorace. Sez. 26-27.

## Data a geoinformatika

- **ČÚZK** — Český úřad zeměměřický a katastrální. Od 1. 7. 2023 poskytuje hlavní sady
  jako open data **CC BY 4.0**. Detail + katalog: `docs/kb/data-sources.md`.
- **ZABAGED®** — Základní báze geografických dat; vektorová topografická *databáze*
  (polohopis + výškopis). Zdroj pravdy, ze kterého se renderují mapy.
- **ZTM** — Základní topografická mapa (ZTM5–ZTM250); hotové kartografické *dílo* (rastr).
- **DMR 5G** — Digitální model reliéfu 5. generace; LiDAR výškopis terénu (ground-only),
  přesnost ~0,18 m. Zdroj reálného terénu pro `--terrain real` (modul `dmr.py`).
- **DMP OK** — Digitální model povrchu z obrazové korelace (fotogrammetrie, **ne LiDAR**)
  → jen viditelný povrch, žádné penetrující odrazy.
- **CHM** (Canopy Height Model) — model výšky vegetace = DMP − DMR. Slabý proxy pro hustotu
  porostu (zelenou), ne plnohodnotná náhrada multi-echo LiDARu.
- **Multi-echo / LLS mračno** — klasifikované LiDAR mračno bodů se všemi odrazy (terén +
  vegetační echa). Potřebné pro vegetaci à la Karttapullautin; ČÚZK ho jako open data nemá
  (viz „Vegetace gate" v `data-sources.md`).
- **S-JTSK** (EPSG:5514) — Systém jednotné trigonometrické sítě katastrální; národní
  souřadný systém ČR (Křovák). ČÚZK data jsou v něm.
- **WGS84** (EPSG:4326) — globální zeměpisné souřadnice (lat/lon). Vstup `--lat/--lon`,
  přepočet na S-JTSK přes `pyproj`.
- **WMS / WMTS / WFS / WCS / ATOM** — OGC přístupové protokoly ČÚZK (prohlížecí rastr /
  dlaždice / vektor / rastr-výškopis / předpřipravené open-data jednotky). Pro generátor
  je klíčový **WFS** (vektor) — WMS vrací jen obrázek (z něj by se data musela segmentovat).
- **INSPIRE** — směrnice EU pro harmonizovaná geodata; ČÚZK publikuje témata jako služby.
  Relevantní: **TN** (Transport Networks — dopravní sítě) pro reálné cesty, **HY**
  (Hydrography — vodstvo) pro reálnou vodu. Data-driven zdroj pro UC4-II (viz IDEAS).
- **georef** (georeferencování) — přiřazení world souřadnic geometrii. `contours.geojson`
  je u `--terrain real` georeferencován v S-JTSK.

- **Ortofoto podklad** — letecký snímek výseku (ČÚZK ORTOFOTO MapServer `arcgis1`, CC BY 4.0,
  `connectors/ortofoto.py`, dlaždicování nad 4096 px) připnutý do `.omap` jako podkladový template
  (paper-space) pro vizuální verify generátoru proti realitě. CLI `--ortho`/`--ortho-mpp`. Sez. 26.

## Projekt — struktura a principy

- **UC** (use case) — jeden z pěti záměrů projektu (UC1-UC5). Tvoří **DAG**, ne seznam.
  Kanonický popis: `docs/architecture.md`.
- **DAG** (directed acyclic graph) — orientovaný acyklický graf závislostí. Zde: enablery
  (UC2 data, UC5 modely) leží pod aplikacemi (UC3 restaurace, UC4 generátory).
- **Enabler / aplikace** — enabler je předpoklad (data, model), aplikace je koncový produkt.
  Pravidlo: enabler před aplikací („foundations before curtains").
- **Feeder / enabler-feeder** — generátor (UC4-I) coby zdroj trénovacích dat pro UC5;
  „krmí" model. Reframe Sez. 4: ne konečný produkt, ale enabler.
- **Prediktor mapy / `synthesize_pseudorealistic_map`** — reframe real-větve generátoru (Sez. 23):
  pro konkrétní lokalitu (souřadnice + rozměry) vyrobit mapu. Realizováno Sez. 25 (přejmenování
  `generate()`): `synthesize_pseudorealistic_map(lat, lon, w_km, h_km, only_real=False, out_dir, *, …)`
  — `lat/lon` WGS84, `only_real` vypíná fázi 2; noise/toggly zachovány jako keyword-only ocas.
  Opačná tvář k noise-feederu. Detail: IDEAS.
- **Projekce vs predikce** — dvě fáze prediktoru mapy. *Projekce* = deterministický převod dostupných
  geodat na ISOM (DMR→vrstevnice, ZABAGED→cesty/voda/budovy; *máme*). *Predikce* = odhad symbolů, které
  v datech NEJSOU (vegetace/průchodnost) z naučeného prioru podobných lokalit (UC5, blokováno korpusem +
  licencí). Nezaměňovat: dnešní `--terrain real` je **projekce**, ne predikce.
- **Pseudorealistic map** — výstup prediktoru: mapa, která *vypadá* realisticky, ale není skutečné
  terénní mapování (syntéza projekce + AI predikce). Pojmenování poctivě přiznává umělost (Sez. 23).
- **pseudorealistic (parametr) / fáze 1-2** — přepínač real-větve generátoru (Sez. 24, default
  `True`; CLI `--only-real` = `False`). **Fáze 1 = projekce** (deterministický převod tvrdých dat,
  100% věrnost). **Fáze 2 = pseudorealistická dekorace** (doplní symboly, co v datech nejsou, ale
  dělají mapu „orienťácky vypadající"; poloha vymyšlená → musí jít vypnout). Dnes jediný konzument
  fáze 2 = rovnoměrné příčky [[el-vedení]] mimo evidované sloupy; budoucí hlavní = vegetace (gate).
  Generalizace L1/L2 budov NENÍ fáze 2 (věrná kartografie, kterou ISOM předepisuje). Spec §0b.
  Vztah k [[projekce-vs-predikce]]: fáze 2 sahá od dekorace (příčky) po predikci (vegetace, UC5).
- **Deštník / fáze B→A** — AzimutLab je teď meta-vrstva (fáze B, deštník) nad sourozeneckým
  Pic2Omap; cíl je monorepo (fáze A), které Pic2Omap absorbuje, až vznikne sdílené jádro.
- **Pic2Omap** — sourozenecký projekt (raster OB mapa → vektor `.omap`); UC4-III. Žije ve
  vlastním repu, neduplikovat sem (CLAUDE.md).
- **Gate** — licenční/datová brána: bez vyjasněné licence (nebo dostupnosti dat) se nad
  zdrojem nestaví. „Vegetace gate" = zavřená cesta k vegetaci z ČÚZK open dat.
- **Domain gap** — rozdíl mezi syntetikou a realitou (syntetika je hladší). Řeší se
  sim-to-real receptem.
- **Sim-to-real** — předtrénink na syntetice (cesta C) + fine-tuning/validace na reálných
  mapách (cesta B); reálný terén (A) dosazený do generátoru.
- **Cesty A / B / C** — datové zdroje pro UC5: (A) geodata ČÚZK, (B) reálné korpusy map,
  (C) syntetická generace. Detail: `RESEARCH.md`.
- **Sparse-GT past** — málo ground-truth anotací (z Pic2Omap pilotu); generátor ji obchází
  (GT zdarma).
- **SLAP** (Single Level of Abstraction Principle) — při změně konceptu aktualizovat všechny
  vrstvy najednou (model / kód / docs / data). Viz CLAUDE.md.

- **Asset** — znovupoužitelný vzor objektu pro generátor (zatím řopík). **Asset pattern** (Sez. 26):
  dvojice `<jméno>.omap` (vizuální geometrie kreslená v Mapperu — přesné body + ISOM symboly) +
  `<jméno>.rules.xml` (pravidla, co `.omap` nepojme: `rotation_rule`, `draw_order`, `source`). Žije v `asset/`.

## Nástroje a knihovny

- **OOM** (OpenOrienteering Mapper) — open-source editor OB map; cílový formát `.omap`.
- **OCAD** — komerční SW pro tvorbu map; formát `.ocd`.
- **Karttapullautin** — generátor OB podkladů z klasifikovaného LiDAR mračna (vrstevnice +
  vegetace). Stojí za projekty MapAnt. Survey: `RESEARCH.md`.
- **CoVe** — color line vectorization pro orienťácké čáry (v OOM).
- **AutoTrace** — bitmap → vektor (raster tracing). Pro reálné skeny (UC4-III/UC3), **ne**
  pro náš generátor (ten má vektor z contourpy přímo).
- **lasertool** — lokální binárka: LiDAR point cloud → rastr (rodina Karttapullautin).
- **contourpy** — Python knihovna marching squares; generátor z ní bere vrstevnice jako
  polylinie.
- **marching squares** — algoritmus pro izolinie skalárního pole na mřížce.
- **Catmull-Rom splajn** — interpolační křivka procházející všemi kontrolními body
  (hladká; tečna v bodě ~ směr sousedů). Generátor jím kreslí cesty (§4.9); krajní
  body zdvojuje (clamp), aby prošel i konci. Helper `_catmull_rom`.
- **pyproj** — transformace souřadnic (WGS84 ↔ S-JTSK); závislost jen pro `--terrain real`.
- **`.omap` / `.ocd`** — XML/binární formáty OB map (OOM / OCAD). Generátor umí `.omap`
  export (template-based, `omap_export.py`).
- **GeoJSON** — textový vektorový formát; `contours.geojson` = vrstevnice jako LineString
  s ISOM symbolem.
