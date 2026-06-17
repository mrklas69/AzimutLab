# HANDOFF v2: Detekce skalních útvarů z lidaru (DMR 5G)

> **⚠ ARCHIV / SPLNĚNO (Sez. 139 audit).** Algoritmus byl absorbován do
> **`generator/rock_relief.py`** (Sez. 63 — práh 46° / `ANALYSIS_RES=0.5` / morfologické
> scelení / Chaikin sedí 1:1) a dále vylepšen **density gate** (Sez. 116, `DENSITY_GATE_PCT`
> — fix over-detection 206, commit `92f373a`). Samostatná Streamlit appka `temp/rockcore/`
> už neexistuje a „zlatý regresní vzorek 48 polygonů" je po density gate neaktuální (gate
> změnil chování). Dokument se drží jako historický předávací artefakt, **není živý úkol.**

> **Předávací dokument pro novou AI session (nahrazuje HANDOFF v1).**
> Cíl: navázat na hotovou aplikaci a neopakovat chyby, které předchozí AI
> udělaly a uživatel je musel opravovat. Před první odpovědí si projdi celý
> dokument; **klíčové je srovnání obrázků 01 a 02 vedle sebe** a oddíl 5
> (chybné pokusy). Verze 2 přidává: vazbu práh–rozlišení (oddíl 4a), S-JTSK,
> zlatý regresní vzorek (oddíl 6a) a pravidlo pro dlaždice (oddíl 7).

---

## 1. Kontext uživatele

- Důchodce-programátor v ČR, technicky zdatný (Python, GIS, příkazová řádka). Vyžaduje věcnou, nepodbízivou komunikaci; chybné výstupy hodnotí tvrdě a oprávněně.
- Komunikace **česky**.
- **Windows** — `pip`/`python` nemusí být v PATH; radit `py -m pip` a `py -m streamlit`.
- Testovací lokalita: **50.5521339 N, 15.1582817 E** (Šulcák / Ztracené údolí, pískovcové skalní město).
- Cíl: **vlastní vektorové polygony skalních útvarů** s věrností podobnou Mapy.com, z otevřených dat.

---

## 2. TŘI KLÍČOVÁ FAKTA (nezpochybňovat, už ověřeno)

### Fakt 1 — Mapy.com NEMAJÍ stejné polygony jako ZABAGED

První AI tvrdila, že „Mapy.com v podstatě renderují ZABAGED skály". **Nepravda** — uživatel to vyvrátil srovnáním stejného výřezu:

- `01_source_zabaged.png` — ZABAGED: šrafa působí detailně, ale je to jen symbolická výplň; samotný polygon je generalizovaný souvislý blok přes celý masiv.
- `02_source_mapycom.png` — Mapy.com: plastické šedé tvary s věžemi, sedly, průchody, balvany.

Geometrie se neshodují. Mapy.com nejsou re-render ZABAGED.

### Fakt 2 — Detail na Mapy.com pochází z RELIÉFU, ne z polygonů

Mapy.com renderují stínovaný reliéf z podrobného výškového modelu. Členitost nese **elevační model**, ne vektorový obrys. Žádný volně dostupný polygonový dataset skal v ČR tuto úroveň detailu nemá — polygony se musí **vyrobit** z výškového modelu. Důkaz reprodukce ze stejných otevřených dat: `03_relief_dmr5g_grey.png`, `04_relief_dmr5g_mapystyle.png`.

### Fakt 3 — Zadání: vyrobit POLYGONY, ne renderovat reliéf

Uživatel nechce reliéfní podání, chce **jednobarevné výplňové polygony** footprintů skalních bloků. Jeho klíčové korekce:

> „Souvislý skalní blok v ZABAGED je ve skutečnosti členitý, mnoho skalních útvarů, průchody mezi skalami, něco jsou pouze balvany."

> „Je třeba umět ty nejtmavší oblasti proložit/aproximovat jednobarevnými polygony."

> „Musíš odebrat stínování. Oblasti ve stínu se jeví jako skalnatější."

Tj. maska **směrově nezávislá** (sklon, nikdy tmavost hillshade) a polygon = **blok** (užší než ZABAGED, ale plošný, s otevřenými průchody).

---

## 3. Datový zdroj

- **ČÚZK DMR 5G** — model reliéfu z leteckého laserového skenování **2009–2013**; úplná střední chyba výšky 0,18 m (odkrytý terén) / 0,3 m (les); rastr ~1 m.
- **Licence CC BY 4.0, © ČÚZK** (otevřená data od 1. 7. 2023).
- Endpoint (ArcGIS REST ImageServer, vrací Float32 GeoTIFF nadmořských výšek):

```
https://ags.cuzk.cz/arcgis2/rest/services/dmr5g/ImageServer/exportImage
  ?bbox=x_min,y_min,x_max,y_max&bboxSR=5514&imageSR=5514
  &size=W,H&format=tiff&pixelType=F32
  &interpolation=RSP_BilinearInterpolation&f=image
```

Bbox se počítá **v metrech přímo v S-JTSK** (střed transformovat pyprojem z WGS84) → pixel je přesně zvolené rozlišení. Pozor: server vrací degradovaný `LOCAL_CS` WKT — CRS je nutné v kódu přebít na `EPSG:5514` (už implementováno ve `fetch_dem`).

**Známé limity dat** (nezastírat uživateli):
- Skenování je přes 10 let staré; řícení/těžba/zářezy po r. 2013 chybí. ČÚZK rozjel nové letecké skenování ČR s vyšší hustotou — **ověř aktuální pokrytí** pro danou lokalitu, než budeš tvrdit, že lepší data nejsou.
- Pod hustým porostem je málo pozemních bodů → povrch je interpolovaný, malé skalky unikají.
- 2.5D model neumí převisy a hřibovité věže; balvany ~1–2 m jsou pod rozlišením. Řešení obojího = surové LAZ mračno (otevřený směr, oddíl 8).

---

## 4. ALGORITMUS — finální podoba

Princip: skalní stěna je strmá, ale **plochý vršek věže** má malý sklon — pouhé prahování dá jen linku podél hrany, ne blok. Proto dvoukrokově:

1. **Sklon** z DMR 5G (`np.gradient`) — směrově nezávislý, žádné stínování.
2. **Vysoký práh** (46° při 0,5 m/px) → maska jistých skalních stěn.
3. **Morfologický uzávěr** (`binary_closing`, disk 8 px = 4 m) → stěny + obklopený vršek se scelí do footprintu bloku.
4. **Vyplnit jen malé díry** (vrcholové plošiny do 250 m²); větší díry = **průchody, nechat otevřené**.
5. Zahodit fragmenty < 60 m².
6. **Vektorizace** → `unary_union` → Douglas–Peucker 1,2 m.
7. **Chaikin** 2 iterace → organické obrysy à la Mapy.com.

Viz `08_vectorize_final_blocks.png` (výsledek) a `09_vectorize_final_overlay.png` (kontrola: obrysy sedí na skutečných stěnách).

### 4a. KRITICKÉ: práh sklonu je svázaný s rozlišením

Bilineární převzorkování „rozmazává" stěny do ramp — **čím hrubší pixel, tím nižší naměřený sklon na téže stěně**. Hodnota prahu 46° platí jen pro konkrétní m/px. Empirický důkaz z vývoje: stejné parametry daly při ~0,52 m/px 48 polygonů / 2,56 ha, ale při ~0,72 m/px jen 43 / 2,36 ha.

Proto v2 kódu **analýza běží vždy na pevných 0,5 m/px** (`rockcore.ANALYSIS_RES`); posuvník rozlišení byl z UI odstraněn. **Neměnit `ANALYSIS_RES` bez rekalibrace prahu** a přegenerování zlatého vzorku.

### 4b. Souřadnicové systémy

- Interní zpracování i metrický export: **S-JTSK / EPSG:5514** (český standard — sedí na ZABAGED, ortofoto, OOM podklady).
- Webový export: WGS84 (RFC 7946 GeoJSON).
- UI nabízí tři stažení: GeoJSON WGS84, GeoJSON S-JTSK, GeoTIFF (S-JTSK).

---

## 5. CHYBNÉ POKUSY — neopakovat

### Chyba A — nízký práh + agresivní morfologie
Práh 33°, plné `fill_holes`, inflate buffery → 13 ha, **víc než ZABAGED**, věže slité, průchody zalité. Uživatel: 2/10. Viz `05_vectorize_v1_bad_flat.png`, `06_vectorize_v1_bad_overlay.png`.

### Chyba B — vysoký práh bez scelení
Práh 44° bez closing → tenké slivery podél hran stěn, ne bloky. Viz `07_vectorize_v2_slivers.png`. (Vršky věží mají sklon ~0° a propadnou — bez closing nevznikne plocha.)

### Chyba C — maska z tmavosti hillshade
Hillshade je směrově závislý; odvrácené svahy falešně „zskalnatí". Masku stavět **jen na sklonu**.

### Chyba D — tvrdit, že Mapy.com = ZABAGED render
Původní omyl, který celou konverzaci odstartoval. Viz Fakt 1 a 2.

### Chyba E — ignorovat vazbu práh–rozlišení
Nově dokumentováno v 4a. Nenabízet uživateli „zrychlení hrubším rastrem" bez upozornění, že tím mění kalibraci detekce.

---

## 6. Aplikace (přiloženo)

**Streamlit**, dva soubory s oddělenou zodpovědností:

- **`rockcore.py`** — čistá logika: `fetch_dem` (metrický bbox v 5514, pevné rozlišení, přebití CRS), `slope_and_shade`, `rock_mask`, `polygonize` (+Chaikin), `render_*`, `to_geojson(target=…)`, `dem_geotiff_bytes`. Self-test: `python rockcore.py`.
- **`app.py`** — UI: souřadnice, posuvníky (poloměr, sigma, práh, close, fill_max, min_area, simplify, Chaikin, volitelná 2. třída), tři záložky (Polygony / Overlay / Sklon), tři exporty. `@st.cache_data` cachuje stažení DEM podle (lat, lon, half) — ladění parametrů je okamžité.

Spuštění (Windows): `py -m pip install -r requirements.txt`, pak `py -m streamlit run app.py`.

Změny algoritmu patří do `rockcore.py`; `app.py` je jen tenká UI vrstva.

### 6a. Zlatý regresní vzorek

Po **jakékoliv** úpravě `rockcore.py` spusť `python rockcore.py` a porovnej s referencí:

| Parametr | Hodnota |
|---|---|
| lokalita | 50.5521339 N, 15.1582817 E |
| poloměr / rozlišení | 360 m / **0,5 m/px** (1440×1440 px) |
| práh sklonu | 46° |
| close / fill_max / min_area | 8 px (4 m) / 250 m² / 60 m² |
| simplify / Chaikin | 1,2 m / 2 iterace |
| **očekávaný výsledek** | **48 polygonů, 2,53 ha** (tolerance: počet ±2, plocha ±5 %) |

Strojově čitelně v `golden_params.json`; referenční geometrie v `golden_skaly_sjtsk.geojson`. Pokud se výsledek liší víc, než říká tolerance, změna rozbila kalibraci — řekni to uživateli, nezamlčuj to.

---

## 7. Pravidlo pro budoucí dávkové zpracování (dlaždice)

Closing i Chaikin se chovají špatně u hranice výřezu — útvar přeseknutý okrajem se zdeformuje. Při zpracování po dlaždicích: **překryv sousedních dlaždic minimálně `close_r` + pár px** (prakticky ≥ 10 m), polygony slévat `unary_union` přes hranice a ořezávat až **po** sloučení. Jednotlivý výřez v appce tím netrpí jen proto, že skály bývají uvnitř; u dávky je to povinné.

---

## 8. Otevřené směry (zájmy uživatele)

- **Klikací mapa** pro výběr bodu (`streamlit-folium`) místo psaní souřadnic.
- **Podkladová mapa** (ortofoto / ZTM z ČÚZK WMS) pod polygony.
- **Dávkové zpracování** většího území (viz pravidlo v odd. 7).
- **LAZ mračno** místo rastru — převisy, pukliny, balvany pod 1m gridem; také novější skenování ČÚZK.
- **Druhá třída** (balvanitý terén nižším prahem) — UI připraveno, ladění otevřené.
- Pozn.: zadání „nejtmavší oblasti" bylo vědomě reinterpretováno jako „nejstrmější" (se souhlasem uživatele — sám stínování zakázal); tmavost hillshade a detekovaná skála se nemusí krýt přesně a je to záměr.

---

## 9. Inventář příloh

| Soubor | Co to je |
|---|---|
| `01_source_zabaged.png` | Screenshot uživatele: ZABAGED skály (souvislé šrafované bloky) |
| `02_source_mapycom.png` | Screenshot uživatele: Mapy.com téže lokality (členitý reliéf) |
| `03_relief_dmr5g_grey.png` | Reprodukce reliéfu z DMR 5G — šedý hillshade |
| `04_relief_dmr5g_mapystyle.png` | Totéž v barvách Mapy.com (důkaz Faktu 2) |
| `05_vectorize_v1_bad_flat.png` | Chyba A — 13 ha, větší než ZABAGED |
| `06_vectorize_v1_bad_overlay.png` | Chyba A — overlay |
| `07_vectorize_v2_slivers.png` | Chyba B — slivery bez scelení |
| `08_vectorize_final_blocks.png` | Finální správný výsledek (bloky) |
| `09_vectorize_final_overlay.png` | Kontrola finálu na hillshade |
| `app.py` | Streamlit UI (v2: pevné rozlišení, 3 exporty) |
| `rockcore.py` | Jádro (v2: S-JTSK, metrický bbox, přebití CRS) |
| `requirements.txt` | Závislosti |
| `README.md` | README pro uživatele |
| `golden_params.json` | Parametry + očekávaný výsledek regresního testu |
| `golden_skaly_sjtsk.geojson` | Referenční geometrie (S-JTSK) |

---

## 10. Pokyny pro novou AI

- Komunikuj **česky**, věcně; nevysvětluj základy GIS/Pythonu.
- Před první odpovědí o tématu se podívej na **obrázky 01 a 02**.
- Neopakuj **chyby A–E** (oddíl 5).
- Po každé úpravě `rockcore.py` ověř **zlatý vzorek** (oddíl 6a) a odchylky přiznej.
- Neměň `ANALYSIS_RES` ani práh bez rekalibrace (oddíl 4a).
- Na Windows raď `py -m pip` / `py -m streamlit`.
- Netvrď nic o datech/službách bez ověření — přesně tahle neopatrnost způsobila chybu D.
