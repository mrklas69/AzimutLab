# KB — Data sources (UC2)

Katalog zdrojů map/geodat třetích stran. **Každý zdroj nese licenci** — bez vyjasněné
licence se na zdroj nesmí stavět UC4-II/III (viz CLAUDE.md doménové zásady).

> Sezení 2 (2026-05-23): průzkum ČÚZK. Sloupce: zdroj · typ dat · pokrytí ·
> přístup · **licence** · stav průzkumu.
> Sezení 8 (2026-05-25): Mapový portál ČSOS (reálné OB mapy, cesta B) — gate ZAVŘENA.

## ČÚZK — gate OTEVŘENA

**Klíčový nález:** od **1. 7. 2023** poskytuje ČÚZK hlavní sady jako **otevřená data
zdarma pod licencí Creative Commons CC BY 4.0** (jediná podmínka = atribuce zdroje).
Tím je splněna doménová zásada „bez vyjasněné licence nestavět nad daty" — **na těchto
sadách lze stavět UC4-II/III** (s uvedením zdroje). Právní rámec: vyhláška č. 31/1995 Sb.

### Terminologie (oprava: „ZTMP" není oficiální zkratka ČÚZK)
Dříve uváděné „ZTMP" slévalo dvě oddělené věci. Správně:
- **ZABAGED®** = Základní báze geografických dat — vektorová topografická *databáze*
  (zdroj pravdy: polohopis + výškopis).
- **ZTM** = Základní topografická mapa (ZTM5–ZTM250) — hotové kartografické *dílo*
  (rastr), od 1. 7. 2023 nahradilo Základní mapu ČR a Státní mapu 1:5000. Renderuje se
  *ze* ZABAGEDu.

### Katalog sad

| Zdroj | Typ dat | Pokrytí | Přístup | Licence | Stav |
|-------|---------|---------|---------|---------|------|
| ZABAGED® Polohopis | vektor: vodstvo, komunikace, vegetace, budovy, hranice (**katalog všech 149 vrstev → ISOM: `zabaged-isom-catalog.md`**) | ČR | **ArcGIS REST** (Sez. 26; též WFS/ATOM/WMS) | CC BY 4.0 | ✓ prozkoumáno + **použito (komunikace Sez. 16, vodstvo Sez. 17, budovy Sez. 18, el. vedení Sez. 24, koupaliště+řopíky Sez. 27, železnice+kolejiště Sez. 28)** |
| **DMR 5G** (ZABAGED Výškopis) | LIDAR výškopis, TIN, přesnost 0,18 m terén / 0,3 m les | ČR (100 %) | ATOM (LAZ, ~20 MB/list SM5), WMS stínovaný, **ArcGIS ImageServer `exportImage` (float TIFF, bbox)**, export přes geoprohlížeč | CC BY 4.0 | ✓ prozkoumáno + použito |
| DMP 1G | model povrchu z LLS 2009–13 (LAZ); 1. odraz = koruna/stavby | ČR | ATOM, WMS | CC BY 4.0 | ✓ (nahrazován DMP OK) |
| **DMP OK** | model povrchu z **obrazové korelace** (fotogrammetrie), GSD 0,2 m, RGB+NIR | ČR (2024+, postupně) | ATOM (LAZ), WMS | CC BY 4.0 | ✓ prozkoumáno |
| Ortofoto ČR | letecké snímky, 2letý cyklus (2025 = západní půlka) | ČR | WMS/WMTS, ATOM, **ArcGIS REST `arcgis1/ORTOFOTO/MapServer/export`** | CC BY 4.0 | ✓ **použito Sez. 26 (podklad map, `connectors/ortofoto.py`, dlaždicování)** |
| ZTM 5–250 | hotové topografické mapy (rastr) | ČR | WMS/WMTS, ATOM | CC BY 4.0 | ✓ prozkoumáno |
| Data50 | generalizovaná data 1:50 000 | ČR | ATOM | CC BY 4.0 | ◐ okrajově |

### Přístupové protokoly (OGC)
- **WMS** — prohlížecí (rastr dlaždice), zdarma a bez registrace.
- **WMTS** — předgenerované dlaždice (OGC 1.0.0, INSPIRE); měřítkové řady vč. „Google Maps".
- **WFS** — stahovací (vektor): ZABAGED Polohopis, adresy, budovy, parcely, správní jednotky.
- **WCS** — stahovací (rastr/výškopis).
- **ATOM** — předpřipravené výdejní jednotky open dat (klad listů nebo celý stát).

### Relevance pro AzimutLab
- **DMR 5G = nejcennější pro orienteering, ale jen výškopis → vrstevnice.** LIDAR ground
  points = vstup pro Karttapullautin vrstevnice (viz RESEARCH.md). **Ne vegetace** (jen
  zem — viz „Vegetace gate" níže). Krmí **UC4-II** (inspirované souřadnicemi) a poskytuje
  terénní georef pro UC4-III.
- **Ortofoto** — vizuální podklad pro UC4-II / kontext UC3.
- **ZABAGED Polohopis** — vektorová pravda o vodstvu/komunikacích/vegetaci → potenciální
  ground-truth a reference pro UC5 klasifikaci.

### Vegetace gate — ZAVŘENA pro open-data cestu (ověřeno Sez. 3, 2026-05-23)
ISOM zelená/žlutá kóduje **hustotu/průchodnost porostu** → potřebuje vertikální strukturu
z **penetrujících (multi-echo) LiDAR odrazů**. Tu žádný open produkt ČÚZK neposkytuje:
- **DMP OK** (nový, hustý) je z **obrazové korelace, ne LiDARu** → zachytí jen viditelný
  povrch (korunu), fyzicky neprochází vegetací, žádné echoes (ověřeno: technická zpráva
  DMP OK, 1/2026). Klasifikace zatím jen voda (třída 9).
- **Surové LLS mračno** (2009–13, multi-echo) **není standardní open-data sada** — dostupnost
  jen přes zeměměřický odbor ZÚ Pardubice (publikované jsou jen odvozené DMR/DMP).
- **DMR 5G** = ground-only (vrstevnice ano, vegetace ne).

**Náhradní cesta (slabší, ne plnohodnotná Karttapullautin vegetace):**
- **CHM = DMP − DMR** → *výška* vegetace (ne hustota). Slabý proxy pro zelenou.
- **NIR/RGB z DMP OK + Ortofoto** → maska lesa (les vs. otevřeno), ne průchodnost.

Důsledek pro **UC4-II**: realistická vegetace z čistě ČÚZK open dat **nejde** Karttapullautin
způsobem. Buď slabší proxy (CHM + NIR), nebo sehnat jiný zdroj multi-echo LiDARu.

**Cesta otevření gate (odloženo, Sez. 8):** plné multi-echo klasifikované mračno **lze
vyžádat / koupit** (ZÚ Pardubice, příp. krajská/zakázková data) — pak by Karttapullautin
i lokální `lasertool` (viz `tools-models.md`) vegetaci zvládly. Vědomě **odloženo do fáze
tvorby map z reálných podkladů**; teď je cíl generovat realisticky vyhlížející mapy (vektor
vrstevnic z DMR 5G, gate netřeba). Až přijde konzument, prověřit zdroj + licenci znovu.

### ZABAGED komunikace — REST konektor (POUŽITO, Sez. 16)
První reálný UC2 konektor (`connectors/zabaged.py`) — reálné cesty do generátoru
(real-půlka §4.9, izomorfní s `dmr.py` výškopisem). Ověřeno proti zdroji (verify-against-source):
- **Endpoint (Sez. 26 přechod WFS→REST):** `https://ags.cuzk.gov.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer/<id>/query`
  (ArcGIS REST; **tatáž doména `ags.cuzk.gov.cz` jako DMR/ORTOFOTO** → jedna infrastruktura). Dřív WFS 2.0.0
  `WFSServer`, ale ten tvrdě uřezával na 1000 obj/dotaz a startIndex paging byl rozbitý (Sez. 25) → REST query
  má strop 2000 + spolehlivý `resultOffset` paging → **města kompletní** (LS 1000→8273 budov). Řopíky: vrstva `Bunkr` (LO37).
- **Výhoda: vrací GeoJSON přímo** (`outputFormat=GEOJSON`) → žádný GML parsing (původní obava z IDEAS
  padla). Izomorfní s `contours.geojson`.
- **CRS:** S-JTSK (EPSG:5514), shoda s DMR. Axis order odpovědi = **[x, y] = [easting, northing]**
  (ověřeno: x ≈ -714 tis, y ≈ -964 tis pro Děčínsko) → žádný axis swap.
- **Feature typy komunikací (`PATH_LAYERS`):** `Cesta` (atributy `typcesty_k`, `povrch_k`), `Pěšina`
  (`typuskom_k`), `Silnice__dálnice` (`typsil_k`), **`Silnice_neevidovaná`** (účelové/lesní asfaltky mimo
  silniční evidenci — doplněno Sez. 23), `Ulice`. `Turistická_trasa` **vynechána** (vede po existující
  cestě → duplikace sítě). **Princip (Sez. 23, uživatel): stahovat VŠECHNY relevantní vrstvy, ne vybrané**
  — `Silnice_neevidovaná` původně chyběla → páteřní asfaltka Bedřichov→Nová louka na mapě úplně chyběla.
  Příští doplnění: el. vedení (**ISOM 510** Power line — pozor, NE 516, to je Fence/plot; oprava Sez. 24),
  `Most` (ISOM 512, **linie** dle DescribeFeatureType), `Lesní_průsek` (508), balvany/skály (204/201).
- **Kompletní katalog VŠECH 149 feature typů ZABAGED Polohopis → ISOM** (verify-against-source:
  GetCapabilities + DescribeFeatureType + template, Sez. 24): **`docs/kb/zabaged-isom-catalog.md`**
  — u každé vrstvy ISOM symbol, nebo důvod nepoužití; akční seznam kandidátů na doplnění.
- **Mapování → ISOM** (fyzický stav = ISOM logika sjízdnosti, ne 1:1): Silnice/Ulice → 502 Wide road;
  Silnice_neevidovaná → 503 Road (zpevněná účelová <5 m); Cesta zpevněná (`povrch_k` Z/T) → 503 Road,
  nezpevněná (None) → 504 Vehicle track; Pěšina udržovaná (`typuskom_k` 026) → 505 Footpath, neudržovaná
  → 506 Small footpath. (Viz `zabaged.map_path_to_isom`.)
- **Licence: CC BY 4.0** (ČÚZK ZABAGED) — atribuce povinná, uložena v `meta.json` (`paths.licence`).
- **Limit:** REST `maxRecordCount` 2000/dávku → sériová paging smyčka (`resultOffset += 2000`) stáhne i hustá
  města kompletní (Sez. 26 — dřív WFS uřezával na 1000 + rozbitý paging). SV 1078, LS 8273 budov.

### ZABAGED vodstvo — REST konektor (POUŽITO, Sez. 17)
Rozšíření téhož konektoru o hydrografii (real-půlka, `fetch_water` / `map_water_to_isom`). Stejný
endpoint / CRS / GeoJSON / axis [x,y] jako komunikace. Ověřeno proti zdroji na výřezu Soví vrchu:
- **Feature typy:** `Vodní_tok` (toky; `vydattok_p` stálý/občasný, `typtoku_k` 004=podzemní, `jmeno`),
  `Vodní_plocha` (plochy; `STOJVODA`, `TYP_VP_P`). Pramen `Zdroj_podzemních_vod` (`typzdroj_k`
  PS=pramen / VR=studna,vrt) — ve výřezu 0 (nejbližší PS 1,9 km) → nekreslen.
- **Mapování → ISOM** (fyzický stav, ne 1:1): podzemní tok (`typtoku_k=004`) → nekreslit; občasný →
  306 Minor/seasonal water channel; pojmenovaný stálý → 304 Crossable watercourse; bezejmenný stálý →
  305 Small crossable watercourse; plocha → 301 Uncrossable body of water. (Viz `zabaged.map_water_to_isom`.)
- **Pozn. ISOM:** pramen = **312 Spring** (ne 313 = Prominent water feature — verify-against-source catch, Sez. 17).
- **Licence: CC BY 4.0** (ČÚZK ZABAGED), `meta.json` `water.licence`. Soví vrch = 16 toků + 2 plochy.

### ZABAGED budovy — REST konektor (POUŽITO, Sez. 18)
Rozšíření téhož konektoru o stavby (real-půlka, `fetch_buildings` / `map_building_to_isom`). Stejný
endpoint / CRS / GeoJSON / axis [x,y] jako komunikace a vodstvo; izomorfní s vodní PLOCHOU. Ověřeno
proti zdroji na výřezu Soví vrchu:
- **Feature typy:** `Budova_jednotlivá_nebo_blok_budov__plocha_` (plochy; `druhbud`, `jmeno`). Bodová
  vrstva `_bod_` ve výřezu prázdná (0 features) → netáhne se (jako pramen `Zdroj_podzemních_vod`).
  Soví vrch = 105 ploch (`druhbud` = „budova blíže neurčená" 104× + „vodojem zemní" 1×; `jmeno` None).
- **Mapování → ISOM:** `Budova_..._plocha_` (jakýkoli `druhbud`, vč. vodojemu) → **521 Building**
  (plošný černý symbol, výplň + obrys). Bez rozlišení podle `druhbud` (KISS; rozhodnutí uživatele-mapéra).
- **Kartografická generalizace (Úroveň 1, Sez. 18):** min. velikost 0,5 mm + zjednodušení obrysu
  Douglas-Peucker (0,3 mm) z ISOM rozměrů (`template_classic.omap` × `PX_PER_MM`). Detail: spec §4.9b.
- **Licence: CC BY 4.0** (ČÚZK ZABAGED), `meta.json` `buildings.licence`.

### ZABAGED el. vedení — REST konektor (POUŽITO, Sez. 24)
Rozšíření téhož konektoru o el. vedení (`fetch_powerlines` / `map_powerline_to_isom`). Stejný
endpoint / CRS / GeoJSON / axis [x,y]. Ověřeno proti zdroji na Sovím vrchu (7 linií) i Č. ráji (2):
- **Feature typy:** `Elektrické_vedení` (linie, MultiLineString) + `Stožár_elektrického_vedení`
  (bod — poloha sloupů). Atributy `NAPETI`/`NAZEV`/`VYSKA_OBJ` jsou v datech **prázdné** (None).
- **Mapování → ISOM:** `Elektrické_vedení` → **510 Power line, cableway or skilift** (vše 510;
  `NAPETI` prázdné → bez rozlišení 511 Major power line). **Pozor: 510, NE 516** (516 = Fence/plot
  — oprava zděděného předpokladu, verify proti `template_classic.omap`, Sez. 24).
- **Příčky symbolu 510 = SLOUPY** (běžci se jimi řídí): fáze 1 kreslí příčku na poloze reálného
  sloupu (`Stožár_elektrického_vedení`), fáze 2 (pseudorealistic) doplní rovnoměrné jen na liniích
  bez evidovaného sloupu. Detail dvou fází: spec §0b + §4.9c, GLOSSARY „pseudorealistic".
- **Licence: CC BY 4.0** (ČÚZK ZABAGED), `meta.json` `powerlines.licence`.

### ZABAGED železnice — REST konektor (POUŽITO, Sez. 28)
Rozšíření téhož konektoru o tratě (`fetch_railways` / `map_railway_to_isom`). Liniová, izomorfní
s komunikacemi/vedením. Ověřeno proti zdroji:
- **Feature typy:** `Železniční_trať` (id 75, osy hlavních tratí) + `Železniční_vlečka` (id 76,
  nádražní/průmyslové vlečky — u nádraží zhušťují kolejovou síť). **Pozor: vrstva je `Železniční_trať`,
  ne „Železnice"** (oprava zděděného TODO).
- **Mapování → ISOM:** obě → **509 Railway** (KISS; ISOM nerozlišuje počet kolejí/elektrizaci).
- **Render:** 509 je v template **kombinovaný symbol** (čárky + bílý „pražcový" knockout), ne prostá
  linie jako 510 → mode `"railway"` (bílý podklad + černé čárky → bílé mezery, odliší od pěšiny 505).
- **Licence: CC BY 4.0** (ČÚZK ZABAGED), `meta.json` `railways.licence`.

### ZABAGED kolejiště / zpevněné plochy — REST konektor (POUŽITO, Sez. 28)
Plošná vrstva (`fetch_paved_areas` / `map_paved_to_isom`), izomorfní s vodní plochou/budovou:
- **Feature typy:** `Kolejiště` (id 122, plocha). **„10 kolejí vedle sebe" u nádraží v datech NEJSOU
  linie** — ZABAGED je generalizuje do jedné plochy `Kolejiště` (Liberec hl. n. ~19 ha). Jednotlivé
  tratě procházející = `Železniční_trať`/`_vlečka` (linie, viz výše).
- **Mapování → ISOM:** `Kolejiště` → **501 Paved area** (kombinovaný symbol: hnědá výplň + **obrysová
  linie**). V `.omap` kombinovaný 501 (s obrysem), ne 501.1 — **do kolejiště se nevstupuje** (bounding
  line významová; ISOM crossability hranic).
- **Licence: CC BY 4.0** (ČÚZK ZABAGED), `meta.json` `paved.licence`.

### Pasti / TODO pro reálný konektor
- **Únor 2026: ČÚZK změnil URL služeb** (doména `geoportal.cuzk.cz` → `geoportal.cuzk.gov.cz`).
  Reálná data ale jedou z `ags.cuzk.gov.cz` (ArcGIS) — ověřeno funkční pro DMR i ZABAGED (Sez. 16).
- LAZ je komprimovaný point cloud / formát výškopisu — pro vrstevnice bude potřeba pipeline
  (LAZ → DMR → vrstevnice), nikoli jen stažení. Detaily až u prvního konektoru.
- DMR 5G vznikl ze skenování **2009–2013** (dokončeno 2016) — pro restaurované/staré mapy
  ověřit, zda časový posun terénu vs. mapy nevadí.

## Mapový portál ČSOS — gate ZAVŘENA (náhledy + copyright klubů)

Digitální archiv map ČSOS — **7000+ georeferencovaných map** pro OB / MTBO / Trail-O /
sprint (filtr dle roku, archiv až 2007). Provozují **Mapová rada ČSOS + T-MAPY spol. s r.o.**
(Hradec Králové). Primárně k **online prohlížení** (mapový nástroj Seznam.cz), ne hromadné
stahování.

**Role v DAGu — datová cesta (B):** nejbližší český zdroj *hotových reálných OB map*
(komplement k ČÚZK, který dává geodata, ne hotové mapy). Teoretický potenciál:
hold-out / fine-tuning pro UC5, reálné skeny pro UC3.

**Licence — gate ZAVŘENA (ověřeno ze stránky „O projektu", 2026-05-25):**
- Autorská práva drží **vydavatelé (kluby)** uvedení v tiráži mapy — ne portál.
- Veřejné jsou jen **náhledy v nízkém rozlišení (96 dpi) s vodoznakem**.
- Jakékoli užití (**včetně výzkumu i komerčního**) vyžaduje **souhlas vydavatele**.
- → **Nestavět UC5 trénink ani UC3 na těchto datech bez svolení.** Navíc náhledy jsou
  degradované (96 dpi + watermark) → i kdyby licence dovolila, kvalita je pro
  trénink/restauraci nedostatečná. **Dvojitá gate: licence i kvalita.**

**Důsledek:** portál slouží jako **reference / orientace** (kde mapy jsou, kdo je
autor a vydavatel = koho oslovit o svolení), ne jako sklízitelný dataset. Reálný
korpus cesty (B) = nutné oslovit jednotlivé vydavatele (kluby), ne scrapovat portál.

## Lokální reálné mapy — `resources/` (6 párů picture+OMAP, smíšený původ)

Lokální sada **6 reálných OB map** jako páry **(`.png` + `.omap` + `.pgw` georef)** — datová
cesta (B), komplement k ČÚZK geodatům. **Mimo git** (`.gitignore: resources/`); zde jen metadata.
(2 výchozí ukázky OpenOrienteering Mapperu — `forest sample`, `complete map` — rozpoznány
přes georef a vyřazeny, ať neznečistí hold-out.)

| Mapa | Měřítko | Georef | Pozn. |
|------|---------|--------|-------|
| Soví vrch | 1:10 000 | S-JTSK ✓ | les, sev. Čechy |
| Bedřichovka | 1:10 000 | pgw | les |
| Blatná | 1:7 500 | pgw | |
| Slovanka2016 | 1:15 000 | pgw | |
| Velbloud | 1:15 000 | bez pgw | les 1:15k |
| SampleMap | 1:15 000 | pgw | reálná navzdory jménu |

`.omap` jsou plain XML (čitelné). Georef v **S-JTSK** (ověřeno Soví vrch) = přiložitelné na
DMR 5G (EPSG:5514) → spárování mapa↔terén. Měřítka 7,5–15 k (generátor dělá 1:10 000;
pro kalibraci cest nejbližší Soví vrch / Bedřichovka).

**Původ a práva (smíšené):**
- **Vlastní** (vytvořené/aktualizované uživatelem, zde Soví vrch) → držitel práv = uživatel.
- **Klubové (koupené)** → „koupené" = licence k tisku/závodu, **ne autorská práva**; ta drží
  kartograf/vydavatel.

**Povolené použití:**
- ✅ **Lokální reference / hold-out / kalibrace** (čtení, měření, vizuální srovnání) — všech 6,
  bez ohledu na původ (nešíří se, `resources/` je gitignored). Hned využitelné: kalibrace
  vedení cest vůči terénu (Dijkstra cena — IDEAS „dvoustupňová věrnost"), validace generalizace
  modelu (§8.4 spec); Soví vrch = autoritativní terénní ground-truth (mapováno uživatelem v terénu).
- ℹ️ **Trénink UC5 se reálných map NETÝKÁ** — model se učí na našem **syntetickém** datasetu
  z generátoru (free GT, reframe Sez. 4) → licence reálných map je pro trénink bezpředmětná.
  (Šíření odvozeniny klubové mapy by svolení vyžadovalo — to ale neděláme.)

**Pozn. (Sez. 20):** dřívější záměr dělit `resources/` na `own/`+`club/` kvůli „čistotě
tréninkového setu" byl **zrušen** — trénink je syntetický, reálné mapy se neučí, takže dělení
postrádá důvod. `resources/` zůstává plochý.

## Další zdroje (neprozkoumáno)

| Zdroj | Typ dat | Pokrytí | Přístup | Licence | Stav |
|-------|---------|---------|---------|---------|------|
| QGIS (nástroj) | — (WMS/WFS klient) | — | desktop | open source | ☐ jako konzument |
| *(zahraniční LIDAR / OSM podklady)* | | | | | ☐ vědomě odloženo |

## Zdroje (URL)

- ČÚZK otevřená data — <https://ags.cuzk.gov.cz/opendata/>
- ČÚZK Geoportál — <https://geoportal.cuzk.gov.cz/>
- DMR 5G metadata — <https://geoportal.cuzk.gov.cz/Default.aspx?mode=TextMeta&side=vyskopis&metadataID=CZ-CUZK-DMR5G-V>
- Technická zpráva DMP OK (obrazová korelace, 1/2026) — <https://geoportal.cuzk.gov.cz/Dokumenty/TECHNICKA_ZPRAVA_K_DMP_OK.pdf>
- Technická zpráva DMR 4G/5G — <https://geoportal-orto.cuzk.cz/Dokumenty/TECHNICKA_ZPRAVA_DMR_4G_a_5G.pdf>
- Podmínky poskytování dat ČÚZK — <https://cuzk.gov.cz/Predpisy/Podminky-poskytovani-prostor-dat-a-sitovych-sluzeb/Podminky-poskytovani-prostorovych-dat-CUZK.aspx>
- DMR 5G na data.europa.eu — <https://data.europa.eu/data/datasets/cz-cuzk-dmr5g-v?locale=cs>
- Mapový portál ČSOS — <https://mapy.ceskyorientak.cz/>
- ČSOS portál — prohlížeč map — <https://mapy.ceskyorientak.cz/cs/map_browser>
- ČSOS portál — katalog map — <https://mapy.ceskyorientak.cz/cs/maps>
- ČSOS portál — O projektu (práva / podmínky užití) — <https://mapy.ceskyorientak.cz/cs/text/about>

## Poznámky

- **Licence je gate, ne poznámka pod čarou** — pro ČÚZK je teď zelená (CC BY 4.0),
  ale každý nový zdroj prověřit znovu před tím, než nad ním cokoli vznikne.
- LIDAR → vrstevnice/vegetace: viz Karttapullautin přístup (RESEARCH.md).
