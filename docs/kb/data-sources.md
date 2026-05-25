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
| ZABAGED® Polohopis | vektor: vodstvo, komunikace, vegetace, budovy, hranice | ČR | WFS, ATOM, WMS/WMTS | CC BY 4.0 | ✓ prozkoumáno |
| **DMR 5G** (ZABAGED Výškopis) | LIDAR výškopis, TIN, přesnost 0,18 m terén / 0,3 m les | ČR (100 %) | ATOM (LAZ, ~20 MB/list SM5), WMS stínovaný, **ArcGIS ImageServer `exportImage` (float TIFF, bbox)**, export přes geoprohlížeč | CC BY 4.0 | ✓ prozkoumáno + použito |
| DMP 1G | model povrchu z LLS 2009–13 (LAZ); 1. odraz = koruna/stavby | ČR | ATOM, WMS | CC BY 4.0 | ✓ (nahrazován DMP OK) |
| **DMP OK** | model povrchu z **obrazové korelace** (fotogrammetrie), GSD 0,2 m, RGB+NIR | ČR (2024+, postupně) | ATOM (LAZ), WMS | CC BY 4.0 | ✓ prozkoumáno |
| Ortofoto ČR | letecké snímky, 2letý cyklus (2025 = západní půlka) | ČR | WMS/WMTS, ATOM | CC BY 4.0 | ✓ prozkoumáno |
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

### Pasti / TODO pro reálný konektor
- **Únor 2026: ČÚZK změnil URL služeb** (doména `geoportal.cuzk.cz` → `geoportal.cuzk.gov.cz`).
  Při psaní konektoru ověřit aktuální GetCapabilities URL, nespoléhat na staré odkazy.
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
- **Vlastní** (vytvořené/aktualizované uživatelem) → držitel práv = uživatel; smí i trénink.
- **Klubové (koupené)** → „koupené" = licence k tisku/závodu, **ne autorská práva**; ta drží
  kartograf/vydavatel. Konzervativně **jen lokální reference/hold-out**; trénink (= šíření
  odvozeniny) až se svolením autora/klubu (stejná gate jako ČSOS portál výše).

**Povolené použití:**
- ✅ **Lokální reference / hold-out / kalibrace** (čtení, měření, vizuální srovnání) — všech 6,
  bez ohledu na původ (nešíří se). Hned využitelné: kalibrace vedení cest vůči terénu
  (Dijkstra cena — IDEAS „dvoustupňová věrnost"), validace generalizace modelu (§8.4 spec).
- ⚠️ **Trénink modelu** — jen vlastní mapy; klubové potřebují svolení.

**Rozlišit původ:** v `resources/` oddělit vlastní vs klubové (`own/` + `club/` nebo
`resources/MANIFEST.md` se seznamem map + původ + licence), ať je tréninkový set čistý (TODO).

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
