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
| ZABAGED® Polohopis | vektor: vodstvo, komunikace, vegetace, budovy, hranice (**katalog všech 149 vrstev → ISOM: `zabaged-isom-catalog.md`**) | ČR | **ArcGIS REST** (Sez. 26; též WFS/ATOM/WMS) | CC BY 4.0 | ✓ prozkoumáno + **použito (komunikace Sez. 16, vodstvo Sez. 17, budovy Sez. 18, el. vedení Sez. 24, koupaliště+řopíky Sez. 27, železnice+kolejiště Sez. 28, plošný pokryv Sez. 41, areály účelové zástavby 114 + kůlny 105 Sez. 42, **systematický audit katalogu Sez. 43: zámek/hrad→521, zřícenina→523, bodové orient. prvky 524/526/530/417, liniové 104/513**, **dávka 4 Sez. 44: mokřady→308, pramen→312, jeskyně/šachta→203.2, nádrž→311**, **stromořadí→406 lineární les Sez. 45**)** |
| **RÚIAN** (Registr územní identifikace, adres a nemovitostí) | vektor: katastrální parcely (druh pozemku), stavební objekty, adresy, správní hranice | ČR | **ArcGIS REST** `RUIAN/MapServer` (týž server jako ZABAGED) | **veřejná otevřená data, zák. 111/2009 Sb., bezúplatně** (atribuce ČÚZK) | ✓ **použito Sez. 42 (`connectors/ruian.py`: parcely druhu zahrada+zastavěná → olivová 520 privátní pozemek)** |
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

### Vegetace gate — ZAVŘENA pro open-data cestu (ověřeno Sez. 3; DOLOŽENO MĚŘENÍM Sez. 59)
> **⟲ Reframe Sez. 79 (pointer):** gate (níže) zůstává platným faktem o open-LiDAR datech, ale **přestal být
> blokátorem UC5**. Cíl `reconstructor()` (sken→`.omap`) čte vegetaci **ze skenu mapy**, ne z ČÚZK dat; feeder
> `generator()` ji generuje procedurálně-věrohodně (predict část) — nemusí být pravdivá vůči lokalitě. Viz
> GLOSSARY `generator()`/`reconstructor()`.

ISOM zelená/žlutá kóduje **hustotu/průchodnost porostu** → potřebuje vertikální strukturu
z **penetrujících (multi-echo) LiDAR odrazů**. Tu žádný open produkt ČÚZK neposkytuje:
- **DMP OK** (nový 2024-25, hustý) je z **obrazové korelace, ne LiDARu** → zachytí jen viditelný
  povrch (korunu), fyzicky neprochází vegetací, žádné echoes (ověřeno: technická zpráva
  DMP OK, 1/2026). **Sez. 59 oprava KB:** klasifikuje i „vysoká vegetace" (vedle vody/budov/mostů)
  + nese RGB+NIR — ale pořád jen povrch (koruna), žádný podrost.
- **Surové LLS mračno** (2009–13, multi-echo) **není standardní open-data sada** — dostupnost
  jen přes ZÚ Praha/Pardubice na vyžádání (publikované jsou jen odvozené DMR/DMP). Ověřeno Sez. 59
  na geoportálu: výškopis nabízí DMR 4G/5G, DMP 1G, DMP OK, vrstevnice — **žádné surové mračno**.
- **DMR 5G** = ground-only (vrstevnice ano, vegetace ne).

**🔴 DŮKAZ Sez. 59 (verify-against-source, ne KB odhad):** stažen DMP 1G list **NBOR52** (Soví vrch,
2,7 MB) přes ATOM → laspy analýza: **100 % single-return** (0 % multi-echo), klasifikace jen
**GROUND 27,8 % / HIGH VEG 68,4 % / building 3,8 %** — žádná low/med veg třída, **nulová penetrace
pod koruny**. → z DMP 1G lze spočítat jen **CHM (výška korun)**, ne hustotu podrostu = runnability.
A CHM je **zavádějící proxy**: vysoký zralý les (vysoký CHM) je často PRŮCHODNÝ (na mapě bílá) →
mapovat CHM na ISOM zelenou by bylo fyzikálně špatně. **lasertool** (`tools-models.md`) segfaultuje
na Win11; i kdyby běžel, ze single-return mračna dá jen tutéž CHM výšku korun.

**Dvojitá vazba (strukturální strop, ne administrativní):** multi-echo (podrost) = jen archiv
**LLS 2009-13 = 13+ let stará vegetace** (nejdynamičtější prvek mapy); **aktuální DMP OK 2024-25 =
single-surface** (bez podrostu). Co je multi-echo je staré, co je aktuální nemá podrost.

**Stažení DMP 1G mračna — cesta OVĚŘENA Sez. 59 (pro budoucí konzument):** nomenklatura listu
REST query na `KladyMapovychListu/MapServer/24` (klad SM5, bodem v S-JTSK) → ATOM
`atom.cuzk.gov.cz/get.ashx?theme=DMP1G-SJTSK` → URL vzor `openzu.cuzk.cz/opendata/DMP1G/epsg-5514/<MAPNOM>.zip`.
LAZ čte `laspy[lazrs]` (ve venv). Mirror `zabaged.py` REST. (Užitečné, i kdyby jen pro CHM/vrstevnice.)

**Kandidáti na PLOCHU hustníku (jiná osa než LiDAR) — PROBNUTO Sez. 61 (measure-first):** ne plná
runnability škála, jen „kde je obecný hustník".
1. **K1 ÚHÚL věk porostu = IMPLEMENTOVÁNO Sez. 62 (`connectors/forest.py`, `--forest-age`), jako hrubý PROXY.**
   Zdroj: **AOPK `gis.nature.cz/arcgis/rest/services/Aplikace/Les_Mapy_20nn/MapServer`** vrstva **19 „Porostní
   skupiny 2022"** (esriPolygon, **371 236 polygonů celostátně**, z LHP+LHO Lesy ČR+ÚHÚL; S-JTSK 5514; licence
   z. 106/1999 open; `maxRecordCount=1000` → paging po 1000). Atribut **`BARVA` = ordinální kódování věku**
   (směr nízká=mladá — DOLOŽENO standardem KSLH `KSLH021114.pdf`/NLI, Tab. 4 `Min((A+19),179) div 20`;
   `ZNACKA` zakmenění je ve službě vždy 1 = nepoužitelné; **`BARVA 15` = bezlesí** dle KSLH Tab. 5 „Obraz BZL").
   Číselník `BARVA`→přesný rok AOPK nezveřejňuje → řezy jsou **laditelné konstanty** v `forest.py` (kalibrace
   proxy, ne věrnost; ověřeno vizuálně). **Mapování (3 odstíny + bílá):** mlazina → **410 fight** (nejtmavší) /
   tyčkovina → **408 walk** / mladší kmenovina → **406 slow** / staré+bezlesí → bílá. Charakter = **PREDIKCE**
   (2. půlka generátoru, věk≠runnability), značeno `proxy:true` v meta. **Slabiny:** věk = hrubý proxy; pokrytí
   DĚRAVÉ **3/5 DEV** (NL/LS/NV ✓; **SV 0, HS 0**); data 2022. Vizuál Sez. 62: NL/LS realisticky (zeleň menšina),
   NV plošně zelená (nejspíš věrná — mladý hospodářský les). Probe + KSLH PDF: `temp/uhul_probe/`.
2. **K2 Copernicus HRL TCD = SLABÝ** (korunový zápoj 10 m shora = tatáž zeď jako CHM Sez. 59; nerozliší hustník
   od zapojeného lesa; neproměřováno — strukturálně doloženo Sez. 59).
3. **K3 Multi-temporal ortofoto = NEJSILNĚJŠÍ koncepčně, ODLOŽEN** (jediný bez pasti zápoje — časová změna
   paseka→zápoj = mladý hustník, ČÚZK archiv open; ale velký CV projekt na časové řadě = vlastní UC).

Důsledek pro **UC4-II**: realistická vegetace z čistě ČÚZK open dat **nejde** Karttapullautin
způsobem (doloženo). Buď jiný podklad plochy hustníku (kandidáti výše), nebo sehnat multi-echo LiDAR
(staré 2009-13 / ZÚ zakázka), nebo UC5 model z reálných map. Vědomě **odloženo do fáze tvorby map
z reálných podkladů** — teď je cíl generovat tvrdou geometrii (gate netřeba). Až přijde konzument,
prověřit zdroj + licenci znovu.

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
- ⚠️ **KOREKCE Sez. 67 (conceptual integrity): „trénink = jen syntetika" platí pro STRUKTURU, NE pro
  runnability.** Reframe Sez. 4 („model se učí na syntetickém datasetu, licence reálných map bezpředmětná")
  vznikl PŘED doložením [vegetace gate](#vegetace-gate--zavřena-pro-open-data-cestu-ověřeno-sez-3-doloženo-měřením-sez-59)
  (Sez. 59). Pro **tvrdou geometrii** syntetika stačí (generátor ji umí, GT zdarma). **Ale runnability model
  (zelená 406/408/410, žlutá) supervised potřebuje GT = co kartograf nakreslil na reálné mapě** — generátor
  runnability neumí věrně (gate) → syntetický trénink by byl cirkulární. **Runnability korpus tedy reálné mapy
  + jejich licenci POTŘEBUJE.** Pragmatická cesta Sez. 67: privátní nekomerční experiment (TDM výjimka), legalizace
  (ČSOS) až pokud model funguje. Detail: IDEAS „UC5 runnability korpus".

**Pozn. (Sez. 20):** dřívější záměr dělit `resources/` na `own/`+`club/` kvůli „čistotě
tréninkového setu" byl **zrušen** — pro syntetický trénink STRUKTURY dělení postrádá důvod (viz korekce výše:
runnability je jiný případ). `resources/` zůstává plochý.

## Livelox — cesta B nástroj pro runnability korpus (deep research Sez. 67)

Platforma pro sdílení tras závodů s mapou na pozadí (<https://www.livelox.com>). **Nejlepší technicky dostupný
zdroj reálných OB map ve vysokém rozlišení** pro UC5 runnability korpus (volba směru Sez. 67).

**Stažitelnost (ověřeno Sez. 68, request tvar ze zdroje `yoav28` extension):** `POST /Data/ClassInfo`
(body `{classIds:[id], …}`) → `general.classBlobUrl` → `GET` Azure blob → `map.images[]` + georef quad.
(Není separátní `/Data/ClassBlob` endpoint — blob URL přijde z ClassInfo.) Dva nezávislé aktivní open-source
nástroje: `yoav28/livelox-map-downloader-extension` (Chrome ext., MIT) a `routechoiceslivegps/map-downloader`.

- **Formát: jen RASTR** (PNG/WebP). Vektor `.omap`/`.ocd` Livelox na uploadu přijímá, ale server-side
  rasterizuje → 3. strana stáhne jen rastr. **GT runnability = barevná segmentace** (ne čistý symbol).
- **Georef: quad** — `projectedBoundingQuadrilateral` (4 rohy v **CRS mapy**) + `boundingQuadrilateral` (WGS84).
  **🔴 EPSG ČÍST Z DAT** (`projectionEpsgCode`): liší se mezi mapami (Sez. 68: S-JTSK 5514 i UTM33 32633) a
  **NEZÁVISÍ na poloze** (Slezsko 18,8°E = 5514, ne UTM34) → CRS = co kartograf nastavil v OCAD, ne zóna.
- **Rozlišení (gate 1 ZMĚŘENO Sez. 68):** stažitelné max = `images[0]` = **~1,33 m/px** (`map.tiles` = jen
  rozřezaný tentýž obraz, NE vyšší; nativní `resolution`=0,75 m/px je server-side nedostupné). Konstantní
  napříč velikostmi i měřítky. **Stačí na PLOŠNOU runnability GT**, jemné symboly ne.
- **Přesnost quadu (gate 2 ZMĚŘENO Sez. 68):** reprojikovaný quad sedne na ortofoto **bez feature-fitu** na
  4 mapách (vizuál) → `oris.py` lookup ani georef fitter nejsou potřeba („stav až s důkazem").

**Konektor hotov Sez. 68, ŠKÁLOVÁN Sez. 70:** `connectors/livelox.py` (`download_map(classId)` →
`resources/livelox/<id>/`: `map.png` + `meta.json` + `blend.png`) + `connectors/map_gt.py` (runnability GT).
**Batch Sez. 70:** `allEvents` reverzováno na **`POST /Home/SearchEvents`** (GeoBox + `timePeriod`; classId v
`classes[].id`) → `search_events`/`download_corpus` (1 class/event, idempotent, backoff retry). **Korpus 268 map**
(severní Čechy CZ + Žitavsko-Šluknovsko DE / série SAXBO; ORIS souřadnice netřeba — blob nese georef).
**Limit zdroje doložen:** jen ~31 % eventů (268/865) má stažitelnou mapu — Livelox staré (≤2022) bloby z velké
části smazal (typ A: mapa fyzicky není; typ B = jen WGS84 quad → kód má fallback). Proto ORIS-párování zavrženo
(96 % starých postrádá rastr, ne jen souřadnice).

**Licence — gate (jako ČSOS):** Livelox docs verbatim „maps and routes are not accessible through the API
for copyright reasons"; stažení přes interní endpointy ty podmínky **obchází**. Práva drží kartograf/pořadatel/
federace (ne Livelox). **Privátní nekomerční experiment OK (TDM výjimka); legalizace (oslovit ČSOS/Livelox)
nutná před jakýmkoli sdílením modelu nebo korpusu.**

**Vyloučit z GT: MapAnt FI / MapantES** — strojově generované z LiDAR (Karttapullautin) → runnability není
kartografova, trénink by byl cirkulární. **Routegadget** = sekundární (jen JPG/GIF 150-200 dpi, strop 1700 px).

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
