# Procedurální generátor map pro orientační běh — specifikace a prompt

> Účel dokumentu: kompletní, jazykově nezávislý popis metodiky, podle níž lze
> generovat syntetické mapy pro orientační běh ve stylu ISOM 2017-2. Slouží
> dvojím způsobem: (1) jako zadání pro implementaci ve vlastním projektu,
> (2) jako prompt pro generativní/LLM model, aby uměl tytéž mapy navrhovat.
> Cílová doména: trénink modelů pro rozpoznávání / segmentaci / generování OB map.

---

## 0. Klíčová myšlenka

Mapa se neskládá z „nakreslených čar", ale z **vrstev odvozených ze skalárních polí**.
Z toho plyne hlavní trik celé metody:

- **Vrstevnice jsou izolinie výškového pole.** Izolinie spojitého skalárního pole
  se z definice nikdy nekříží a nikdy nekončí ve vzduchu — problém „disjunktnosti"
  vrstevnic tím mizí sám, není potřeba ho hlídat.
- **Vodní toky tečou po spádnici** (gradient descent výškového pole), takže
  samovolně leží v údolích a kříží vrstevnice zhruba kolmo. Tvary „V proti proudu"
  vznikají automaticky.
- **Vegetace, paseky a rašeliniště jsou prahované šumové masky.**
- **Bodové a liniové prvky jsou bodové/čárové procesy vážené terénem**
  (např. balvany hustěji ve strmém terénu, posed u paseky).

Protože všechny vrstvy si počítáme sami, máme ke každé mapě **ground-truth zdarma**:
každá vrstva je zároveň segmentační maska. To je hlavní výhoda oproti scrapování
reálných map, kde anotaci nemáme.

---

## 1. Souřadný systém a měřítko

- Výpočetní mřížka: `GW × GH` buněk (referenčně 170 × 116; poměr ≈ 1,466).
- Výstupní plátno: `W × H` px (referenčně 672 × 458). Mapování buňka → pixel:
  `px = gx / GW * W`, `py = gy / GH * H`.
- Měřítko: 1:10 000 (1 mm mapy = 10 m terénu). Ekvidistance vrstevnic 5 m,
  hlavní (zvýrazněná) vrstevnice každá pátá (po 25 m).
- Indexování pole: row-major, `index(x, y) = y * GW + x`.

---

## 2. Generování polí (fraktální value noise)

Základní stavební kámen je fraktální „value noise" v rozsahu [0, 1].

```
funkce fractal(rng, baseScale, octaves) -> pole[GW*GH]:
    out = 0
    amp = 1; total = 0
    pro o = 0 .. octaves-1:
        c = max(2, round(baseScale * 1.9^o))         # počet buněk hrubé mřížky
        G = náhodná mřížka (c+1)×(c+1) hodnot rng()    # rng() ∈ [0,1)
        pro každý pixel (x,y):
            bilineární interpolace G se smoothstep (3t²−2t³)
            out[x,y] += interp * amp
        total += amp; amp *= 0.5
    out /= total
    min-max normalizace out do [0,1]
    návrat out
```

Použitá pole:

| Pole        | baseScale            | octaves          | význam |
|-------------|----------------------|------------------|--------|
| `hbase`     | `1.6 + rug*2.6`      | `3 + round(rug*2)` | výškopis (rug = členitost) |
| `veg`       | `3.2 + vd*1.5`       | `3`              | hustota porostu (vd = vegetace) |
| `clear`     | `2.4`                | `2`              | paseky / otevřené plochy |
| `eb`        | dvojitý box-blur `hbase` | —            | vyhlazený výškopis pro hydrologii |

> Determinismus: všechna `rng()` pocházejí z jednoho PRNG inicializovaného `seed`.
> Stejný seed + stejné parametry ⇒ identická mapa. Doporučený PRNG: `mulberry32`.

---

## 3. Odvozené veličiny

- **Sklon** `slope[x,y]` = velikost gradientu `eb` (centrální diference), normalizovaný
  na [0, 1] dělením maximem. Používá se pro: balvany, skalní stupně, rýhy, rašeliniště.
- **Nadmořská výška** `elev[x,y] = 700 + hbase[x,y] * vrange`, kde
  `vrange = 25 + rug*90` m. Vyšší členitost ⇒ větší převýšení ⇒ víc vrstevnic.

---

## 4. Vrstvy a jejich pravidla

Pořadí níže je zároveň pořadím vykreslování (z-order, odspodu nahoru).

> **Stav implementace (Sezení 11):** `generator.py` po vědomém řezu dělá jen
> **§4.5 vrstevnice + §4.9 cesty + §4.10 bodové symboly extrémů** (+ vektor §9).
> Plošné vrstvy §4.2-4.4 (vegetace, paseky, bažiny) a §4.11 (balvany) byly
> **zahozeny** — vypadaly uměle a kazily by domain gap feederu pro UC5. Metodika
> níže zůstává platná pro přestavbu „znovu a lépe" (vrstvu po vrstvě, s důrazem
> na vizuální věrnost); historie v gitu (commit Sez. 10). §4.6-4.8 a §4.12-4.13
> nebyly nikdy implementovány.

### 4.1 Podklad
Celé plátno bílé `#FFFFFF` (= běžně průběžný les).

### 4.2 Vegetace (výplně)
Prahy `a = clamp(0.82 − vd*0.5)`, `b = a + 0.13`, `c = a + 0.23`.
Pomocí marching squares (`d3.contours().contour(veg, t)`) získáme oblast `veg ≥ t`
a vyplníme odspodu nahoru:
- `veg ≥ a` → světle zelená `#C2E8B0` (pomalý běh)
- `veg ≥ b` → středně zelená `#6DC771` (chůze)
- `veg ≥ c` → tmavě zelená `#2DA94F` (těžko prostupné)

Vyšší `vd` posouvá prahy dolů ⇒ víc zeleně.

### 4.3 Paseky (open)
`clear ≥ clearThr`, `clearThr = 0.70 + vd*0.22` → výplň žlutá `#FECA17`.

### 4.4 Rašeliniště / mokřad
Maska: `hbase < (0.10 + wat*0.16)` **a zároveň** `slope < 0.16` (nízko a plocho).
Marching squares na binární masce → výplň vodorovnou modrou šrafou, obrys modře
tečkovaně. (`wat` = vodní prvky.)

### 4.5 Vrstevnice
Pro každý práh `t ∈ {705, 710, …}` vykreslíme izolinii `elev = t` (obrys polygonu
z marching squares), tloušťka 1 px, hlavní (`(t−700) mod 25 == 0`) 3 px,
barva hnědá `#A05F1F`. **Disjunktní z principu.** (Realizace Sez. 6: 1 px / hlavní
3 px — PIL nemá antialiasing, tenčí poměr 2:1 px splýval; výraznější index navíc
pomáhá UC5 odlišit třídy 101/102. Variaci tlouštěk pro diverzitu datasetu viz §8.2.)
Malá uzavřená smyčka (lokální extrém pod prahem plochy) se negeneralizuje jako
prstenec, ale jako bodový symbol — viz §4.10 (realizace Sez. 10).

### 4.6 Rýhy / erozní rýhy (`det` = detaily)
`round(det*4)` kusů. Start ve strmé buňce (`slope > 0.4`), krátký sestup po spádnici
(≤ 22 kroků), vykreslení Catmull-Rom splajnem hnědě + drobné kolmé tiky (odliší od
vrstevnic).

### 4.7 Hranice porostů
Izolinie `veg = b` vykreslená černě tečkovaně (dash 1/2,6). Sleduje skutečné rozhraní
hustot ⇒ geometricky konzistentní.

### 4.8 Vodní toky
`round(wat*5)` toků. Start v buňce `0.45 < eb < 0.85`, gradient descent po `eb`
(skok do nejnižšího osmi-souseda) až na okraj / do lokálního minima. Toky kratší než
14 kroků se zahodí. Vykreslení vyhlazenou křivkou modře. **Počátek toku se uloží
pro pramen** (4.10).

### 4.9 Cesty
`1 + round(det*1.6)` cest, konce na protilehlých okrajích (vodorovně/svisle), náhodná
pozice na okraji. Hlavní cesta plná (1,5 px), vedlejší čárkovaná. Vedení vázané na
terén — viz §9.
**Realizace Sez. 11:** hlavní = plná černá (2 px, ISOM **503 Road**), vedlejší =
čárkovaná (ISOM **507 Less distinct small footpath**, Sez. 13 oprava z 505); helpery
`_catmull_rom` (uniform splajn, krajní body zdvojené) + `_draw_dashed` (čárkování po
délce oblouku). GT do `mask_paths.png` (multi-class 1=503 / 2=507). Z-order: po
vrstevnicích, před bodovými symboly.
**✅ Terénně vázané vedení (Sez. 13):** přímý splajn s jitterem nahrazen **Dijkstra
least-cost** trasou (§9) — viz tam. Cesty traverzují svah místo přes vrchol.

### 4.10 Bodové značky (`det`)
Vzorkování buněk rejection samplingem podle predikátu:

| Značka | Predikát umístění | Vykreslení | Barva |
|--------|-------------------|------------|-------|
| Pramen | počátky toků z 4.8 | otevřený oblouk + ocásek | modrá |
| Posed | u paseky (`clear > clearThr−0.05`) | stříška na dvou nohách | černá |
| Vývrat | hustý les (`b < veg < c+0.05`) | plný trojúhelník + stonek | černá |
| Význačný strom | řídký les (`veg < a−0.05`) | zelený kroužek | zelená |

Počty: pramen `round(det*3)`, posed `round(det*2)`, vývrat `round(det*10)`,
strom `round(det*5)`.

**Bodové symboly z generalizace vrstevnic (terénní, nezávislé na `det`).**
Malá uzavřená vrstevnice = lokální extrém příliš malý na čitelný prstenec → kreslí
se bodovým symbolem (ISOM kartografická generalizace). Detekce: smyčka uzavřená
(první bod ≈ poslední) + plocha pod prahem (~600 m², laděno) + výška centroidu vs
úroveň vrstevnice. Lokální max → **109 Small knoll** (hnědá tečka), protáhlý
(poměr stran bbox > 2,5) → **110 Small elongated knoll** (hnědá elipsa); lokální min →
**111 Small depression** (hnědý oblouk „⌣"). **112 Pit vynechán** — je to jiná
feature class (umělá/erozní díra), z výškového pole neodlišitelný od 111.
Z-order: nad vrstevnicemi (§4.5), pod balvany (§4.11). GT do `mask_symbols.png`
(multi-class) + seznam pozic `point_symbols` v `meta.json`. (Realizace Sez. 10.)

> **ISOM kódy — pozor (Sez. 13):** používáme **ISOM 2017-2 Rev 6 (2024)** číslování
> 109/110/111. Staré ISOM 2017 mělo pro tytéž symboly 112/113/115 (Rev 6 přečíslovalo
> a v 112+ jsou teď Pit / Broken ground / Prominent landform). Ověřeno proti oficiálnímu
> OOM symbol setu `ISOM 2017-2_10000.omap`. Cesty: 503 Road, 507 Less distinct small footpath.

### 4.11 Balvany a skalní stupně (`rock`)
- Balvany: `round(rock*120)` černých teček, přijetí s pravděpodobností
  `0.25 + slope*0.9` (hustěji ve strmém terénu).
- Skalní stupně (cliffs): `round(rock*5)` v nejstrmějších buňkách, krátká černá
  hrana s tiky.

### 4.12 Severník (orientace)
Slabé svislé linie po ~58 px (reprezentují sever; reálně 300 m). Volitelné.

### 4.13 Trať (purpurová, přepínatelná)
5 kontrol rozmístěných s minimální vzájemnou vzdáleností `0.24*W`. Start trojúhelník,
kontroly kroužky (poslední dvojitý = cíl), spojnice. Číslování vpravo nahoře u kroužku.

---

## 5. Barevná paleta (ISOM 2017-2, aproximace pro obrazovku)

| Prvek | Význam | RGB | CMYK (orientačně) |
|-------|--------|-----|-------------------|
| Bílá | průběžný les | `#FFFFFF` | 0/0/0/0 |
| Žlutá | otevřená plocha | `#FECA17` | 0/27/91/0 |
| Světle zelená | pomalý běh | `#C2E8B0` | 25/0/40/0 |
| Středně zelená | chůze | `#6DC771` | 55/0/65/0 |
| Tmavě zelená | těžko prostupné | `#2DA94F` | 100/0/80/0 |
| Hnědá | vrstevnice, rýhy | `#A05F1F` | 0/56/100/18 |
| Modrá | voda, mokřad | `#2EC2F8` | 90/0/0/0 |
| Černá | skály, cesty, stavby | `#000000` | 0/0/0/100 |
| Purpurová | trať | `#C400AC` | 0/100/0/0 (Purple) |

> **Runtime implementace (jediný zdroj pravdy):** `sandbox/generator-poc/palette.py`
> (slovník `PALETTE`). Tato tabulka je metodický/jazykově nezávislý popis (slouží
> i jako prompt, §10); konkrétní RGB pro běh generátoru bere kód odtamtud, ať se
> hodnoty nerozejdou (DRY). Implementováno do `palette.py` v Sez. 8.

---

## 6. Parametry (UI ↔ vnitřní)

| Posuvník | Symbol | Rozsah | Ovlivňuje |
|----------|--------|--------|-----------|
| Členitost terénu | `rug` | 0–1 | baseScale/octaves výškopisu, převýšení `vrange`, počet vrstevnic |
| Hustota vegetace | `vd` | 0–1 | prahy zelených pásem, počet pasek, hranice porostů |
| Vodní prvky | `wat` | 0–1 | velikost rašelinišť, počet toků a pramenů |
| Skály a balvany | `rock` | 0–1 | počet balvanů a skalních stupňů |
| Detaily a značky | `det` | 0–1 | počty bodových značek, rýh, cest, hranic porostů |
| Trať | bool | — | vykreslení tratě |
| Seed | int | — | celá náhodná struktura (deterministicky) |

---

## 7. Pseudokód hlavní smyčky

```
funkce generate(seed, params):
    rng   = mulberry32(seed)
    hbase = fractal(rng, 1.6+rug*2.6, 3+round(rug*2))
    veg   = fractal(rng, 3.2+vd*1.5, 3)
    clear = fractal(rng, 2.4, 2)
    eb    = blur(blur(hbase))
    slope = normalize(|grad(eb)|)
    elev  = 700 + hbase * (25 + rug*90)

    fill background white
    fill vegetation bands from veg (a,b,c)
    fill clearings from clear
    fill+outline marsh from (hbase low ∧ slope flat)
    stroke contours from elev (every 5 m, index every 25 m)
    draw gullies (det) ; collect nothing
    dotted vegetation boundary = isoline veg=b
    draw streams (wat) -> collect spring sources
    draw paths (det)
    draw faint north lines
    scatter boulders (rock, weighted by slope) ; cliffs at steepest
    draw point symbols (springs, seats, rootstocks, special trees) [det]
    if course: place 5 controls (min distance), draw legs+circles
    draw north arrow, scale bar, footer
```

---

## 8. Generování trénovacích dat (ML pipeline)

1. **Ground-truth zdarma.** Při vykreslování každé vrstvy ji zároveň renderuj do
   samostatného kanálu/masky. Výstup jedné instance:
   - `rgb.png` — finální mapa (vstup modelu),
   - `mask_contours.png`; `mask_paths.png` (multi-class 1=503 / 2=507, Sez. 11/13);
     `mask_symbols.png` (multi-class knoll/depression z generalizace §4.10, Sez. 10).
     Masky `mask_veg/water/rock` byly se svými vrstvami zahozeny (Sez. 11, viz §4),
   - `meta.json` — seed, parametry, seznam bodových značek se souřadnicemi a typem
     (hotová detekční anotace ve stylu COCO/YOLO).
2. **Objem a diverzita.** Kombinatorika 5 parametrů × seed ⇒ prakticky neomezený
   dataset. Pro pokrytí stylů varíruj i paletu (drobné posuny odstínů), tloušťky
   čar a ekvidistanci.
3. **Augmentace specifická pro mapy:** rotace o libovolný úhel (mapa je rotačně
   neutrální až na severník — ten přegeneruj), simulace tiskových vad (lehký
   misregistration kanálů CMYK, JPEG artefakty, papírová textura, mírné rozostření),
   změna měřítka.
4. **Domain gap.** Tahle syntetika je *hladší* než realita (chybí kartografická
   generalizace a subjektivita mapaře). Doporučený postup: **předtrénink na velkém
   objemu syntetiky + fine-tuning a validace na menší sadě reálných map**
   (zdroje: World of O, Mapový portál ČSOS, MapAnt, Routegadget — viz samostatný
   přehled). Reálné mapy slouží i jako hold-out pro měření skutečné generalizace.
   **Dvoustupňová realnost (rozhodnuto 2026-05-25):** stupeň 1 = kartografická věrnost
   (čistý render, vrstvy fyzikálně vázané na terén — „fyzikální gate"), stupeň 2 = věrnost
   skenu (augmentace §8.3 jako samostatná vrstva). Roadmapa a pořadí věrnostních vrstev:
   `IDEAS.md`. (Názvosloví bez A/B — ta patří vztahu k Pic2Omap.)
5. **Náhrada šumu reálným terénem.** ✅ **Implementováno (Sez. 5)** — `--terrain real`
   v `sandbox/generator-poc/` (modul `dmr.py`). Místo `fractal()` dosadí reálný ČÚZK
   DMR 5G přes ArcGIS ImageServer `exportImage` (float32 grid přímo, ne LAZ → žádný GDAL;
   WGS84→S-JTSK přes pyproj, poměrový výsek pro izotropní buňku). Vrstevnice pak nejsou
   „věrohodné", ale skutečné; model se učí na reálné geometrii terénu. Vegetace/bažiny
   zůstávají syntetické (DMR 5G je ground-only — viz vegetace gate v `data-sources.md`).
   Produkčně vrstevnice+vegetaci z LiDARu dělá **Karttapullautin** — stojí za projekty MapAnt.

---

## 9. Doporučení k implementaci

- **Marching squares** je jediná netriviální závislost. JS: `d3-contour`.
  Python: `skimage.measure.find_contours` nebo `matplotlib`'s `contour` (pak vyber
  segmenty), případně `contourpy`. Pole drž jako `numpy.float32` row-major.
- **Šum**: vlastní value noise (viz §2) nebo knihovna (`opensimplex`, `perlin-noise`).
  Pro reprodukovatelnost vždy seeduj.
- **Hydrologie**: jednoduchý gradient descent stačí na vizuál; pro realističtější
  síť toků použij flow accumulation (D8 algoritmus) a prahuj akumulaci.
- **Terénně vázané cesty** (vylepšení §4.9): místo přímého splajnu veď cestu
  least-cost path algoritmem (Dijkstra) s cenou rostoucí se sklonem — cesty pak
  traverzují svahy místo aby šly přes vrcholy.
  - **✅ Implementováno (Sez. 13):** `generator.py` `_dijkstra_path` — 8-sousedství
    na mřížce, čistý `heapq` (žádný scipy). **Cena hrany = horizontální vzdálenost [m]
    + `PATH_SLOPE_PENALTY`·|Δvýška| [m]** (zvolen model „sklon hrany" Δh, ne izotropní
    slope buňky): pohyb podél vrstevnice levný, stoupání drahé → traverz. Konce na
    protilehlých okrajích; surová 8-směrová trasa se zředí (`PATH_SIMPLIFY`) a vyhladí
    `_catmull_rom`. Deterministická (tie-break počítadlem). Funguje pro noise i real
    (na reálném DMR cesty vedou skutečnými sedly/údolími). „Vede údolím" v plném smyslu
    (preferuje údolnice) přijde až s hydro jádrem (toky = údolnice); teď jen vazba na sklon.
- **Výstup do vektoru**: pokud potřebuješ OCD/OMAP, exportuj jednotlivé vrstvy jako
  GeoJSON/SHP a konvertuj (OpenOrienteering Mapper umí import GDAL vektorů; OCAD má
  XML skripty). Vrstevnice jdou exportovat přímo z marching squares jako polylinie.
  - **✅ Vrstevnice implementováno (Sez. 8):** `generator.py` zapisuje `contours.geojson`
    — polylinie z contourpy se symbolem **101 Contour / 102 Index contour**,
    georeferencované v **S-JTSK (EPSG:5514)** pro `--terrain real` (lokální metry pro
    noise). Žádná vektorizace rastru (AutoTrace) — jdeme z přesného zdroje (contourpy),
    ne z pixelů. 103 Form line generátor zatím nedělá.
  - **✅ `.omap` export (Sez. 8, přepsán Sez. 13, template-based Sez. 14):** `omap_export.py`
    (volá se vždy) zapíše `map.omap` s **vrstevnicemi (101/102) + cestami (503/507) +
    body (109/110/111)**, Local CRS, paper-space (1 m → `1e6/scale` µm, vycentrováno, bez
    Y-flip). NEduplikuje Pic2Omap `db2omap` (ten jde z rastru; my z přesných polylinií).
    **Vývoj přístupu:** Sez. 8 template-based (cizí `.omap`) → Sez. 13 **od nuly** (kvůli
    dědění bordelu z cizích souborů — 101.1 LIDAR, 503 Minor road, cizí podklady) → **Sez. 14
    zpět template-based, ale nad VLASTNÍM čistým template** `sandbox/generator-poc/template_classic.omap`
    (ISOM 2017-2, 169 symbolů / 35 barev, prázdné `<objects>`/`<templates>` — vyrobil uživatel
    v OOM). Skládáme jen `<objects>`; barvy/symboly/georef přebíráme z template. Zisk:
    **věrná geometrie bodů** (109 kruh, 110 elipsa `area_symbol`, 111 oblouk „⌣" `line_symbol`
    — místo dřívějšího jednotného kruhu) + plná ISOM knihovna jako reálná mapa z OOM (menší
    domain gap). Symbol id se parsují z template podle ISOM kódu (id nejsou pořadová: 503→110,
    507→114). Bodové symboly mají `rotation=0` (sever; orientaci protáhlosti 110 generátor
    zatím neukládá). `--omap-template` flag zrušen (Sez. 13). Verify: OOM headless nejde
    (jen `windows` plugin) → self-check (XML well-formed, počet objektů, symbol id) + vizuál v OOM.

---

## 10. Prompt pro generativní model (zkrácená forma)

> Vygeneruj výsek mapy pro orientační běh v měřítku 1:10 000, symbolika ISOM 2017-2.
> Postupuj po vrstvách odvozených ze skalárních polí: (1) výškopis jako fraktální
> šum, z něj vrstevnice po 5 m jako neprotínající se izolinie, hlavní každá pátá;
> (2) vodní toky vedené po spádnici výškopisu, takže leží v údolích; rašeliniště
> v nízkých plochých místech; (3) vegetace jako prahovaná pásma bílá→světle/středně/
> tmavě zelená; žluté paseky; (4) bodové značky umístěné kontextově: pramen na zřídle
> toku, posed u paseky, vývrat v houštině, význačný strom v řídkém lese; (5) cesty
> jako hladké splajny napříč mapou, erozní rýhy ve svazích, hranice porostů tečkovaně
> podél rozhraní hustot; (6) balvany hustěji ve strmém terénu, skalní stupně
> v nejstrmějších místech; (7) volitelně trať: 5 kontrol purpurově s rozumnými
> rozestupy. Drž barevnou paletu podle tabulky a pořadí vrstev (z-order) podle §4.
> Vše musí být deterministické vůči zadanému seedu.

---

*Vytvořeno jako metodický podklad pro přenos do vlastního projektu. Volně upravuj
parametry, prahy i symboliku podle cílové domény tvého modelu.*
