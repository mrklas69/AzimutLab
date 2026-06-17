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

## 0b. Projekce vs pseudorealistická dekorace (dvě fáze, Sez. 24)

Reálná („real") větev generátoru má **dvě oddělitelné fáze** (přepínač `pseudorealistic`,
default `True`; CLI `--only-real` ho vypne):

1. **Fáze 1 — projekce.** Deterministický převod toho, co JE v datech (DMR výškopis → vrstevnice,
   ZABAGED → cesty/voda/budovy/vedení/sloupy). 100% věrnost, žádný vymyšlený symbol.
2. **Fáze 2 — pseudorealistická dekorace.** Doplní symboly, které v datech NEJSOU, ale dělají mapu
   „orienťácky vypadající" (poloha vymyšlená). Dnes: rovnoměrné příčky vedení mimo evidované sloupy
   (§4.9c). Budoucí hlavní konzument: **vegetace** (zelená/žlutá = průchodnost, v datech není kvůli
   vegetace gate — to už je predikce přes UC5, ne jen dekorace).

Princip: nevymýšlet, co v datech není, pod hlavičkou „věrnost". Co se vymýšlí pro vzhled, jde do
fáze 2 a musí jít vypnout. Vazba: GLOSSARY „projekce vs predikce", „pseudorealistic",
`generate_map` (dříve `synthesize_pseudorealistic_map`, přejm. Sez. 39). Budovy jsou čistá
fáze 1 (projekce) — kreslí se RAW (Sez. 27,
generalizace zavržena); žádná „věrná kartografie" navíc, syrový footprint jako voda.

> **⟲ Reframe Sez. 79-80 (pointer; plný přepis §0b = A1, TODO „Spec §0b predict").** „Fáze 2" se
> upřesnila: hlavní konzument **vegetace už NENÍ samostatný UC5 model `ortofoto→runnability`** (ten
> narazil na strop val mIoU ~0,25 → archivován, Sez. 78-79), ale **predict část `generator()`** —
> prediktivní plochy ze **separace barev z HD Livelox PNG** (Sez. 80), vektorizované do `.omap`
> s flagem `predict`. Cíl celé pipeline = krmit `reconstructor()` (sken→`.omap`). Pojmy: GLOSSARY
> `generator()` / `reconstructor()` / „Fáze I / II / III".

---

## 1. Souřadný systém a měřítko

- Výpočetní mřížka: `GW × GH` buněk (referenčně 170 × 116; poměr ≈ 1,466).
- Výstupní plátno: `W × H` px (referenčně 672 × 458). Mapování buňka → pixel
  (krajní buňka na krajní pixel): `px = gx / (GW−1) * W`, `py = gy / (GH−1) * H`
  (implementace `_grid_to_px`).
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

> **Stav implementace (Sezení 11, dnes výrazně rozšířeno):** `generator.py` po vědomém
> řezu Sez. 11 dělal jen **§4.5 vrstevnice + §4.9 cesty + §4.10 bodové symboly extrémů**
> (+ vektor §9). Od Sez. 16 přibyla celá **real-půlka §4.9a-p** (voda, budovy, vedení/lanovka,
> železnice, kolejiště, skály, mosty/tunely, landmarks, plošný pokryv, lineární prvky, stromořadí,
> predikční vegetace ze separace — viz podsekce §4.9*) a skalní plochy 206 z DMR (`rock_relief.py`, Sez. 63).
> Plošné vrstvy §4.2-4.4 (vegetace, paseky, bažiny) a §4.11 (balvany) z noise-půlky byly Sez. 11
> **zahozeny** — vypadaly uměle a kazily by domain gap feederu pro UC5. Metodika níže zůstává
> platná pro přestavbu „znovu a lépe" (vrstvu po vrstvě, s důrazem na vizuální věrnost); historie
> v gitu (commit Sez. 10). §4.6-4.8 a §4.12-4.13 (noise-půlka) nebyly nikdy implementovány.

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

**✅ Pomocné vrstevnice (form lines, ISOM 103, Sez. 29, jen `--terrain real`):** doplňková
čárkovaná vrstevnice na **poloviční ekvidistanci** (`level + 2,5 m`). ISOM ji povoluje **střídmě**
a zakazuje jako „intermediate contour" (plošné zahuštění svahů). Generátor proto kreslí jen úseky,
kde maska `_formline_mask` splňuje **dvě podmínky současně** (návrh uživatele):
(1) **mírný svah** — rozestup vrstevnic > `FORMLINE_SPACING_LIMIT_M` (40 m) ⟺ sklon < `CONTOUR_STEP/limit`;
(2) **zakřivený terén** — `|Laplacián výšky| > FORMLINE_CURV_MIN` (0,004 1/m); na rovnoměrném (lineárním)
svahu je Laplacián ≈ 0 → form line by jen kopírovala vrstevnici = vynechána. `elev` se před derivacemi
3× vyhladí (3×3 box) — tlumí mikro-texturu DMR (jinak Laplacián dělá falešné form lines všude: bez tohoto
filtru a s nízkým prahem vzniklo na NL 1466 úseků = plošný šum). Poloviční izolinie se ořeže na masku
(„část pomocné vrstevnice"), zahodí se úseky < `FORMLINE_MIN_LEN_MM` (3 mm = ~30 m, přísněji než ISOM 1,1 mm —
bez „fousků"). Render dashed hnědě (break zvětšen 0,2→0,5 mm pro rastr; `.omap` nese věrný symbol 103, OOM
renderuje autoritativně). GT `mask_formlines.png`, vektor v `contours.geojson` (kód 103). Branžový precedent:
**Karttapullautin** (poloviční hladiny + filtrace plochých partií). NL 6×4 km → 108 form lines (vs 240 vrstevnic).

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
**✅ Reálná voda (Sez. 17, real-půlka):** `--water real` vezme skutečnou hydrografii z **ČÚZK
ZABAGED Polohopis (ArcGIS REST)** (`zabaged.fetch_water`, týž konektor jako cesty) pro tentýž výsek jako
DMR. Vyžaduje `--terrain real`. **Vodní_tok** → ISOM **304** (pojmenovaný stálý) / **305**
(bezejmenný stálý) / **306** (občasný, čárkovaný); podzemní toky se nekreslí. **Vodní_plocha** →
**301** (modrá výplň + břeh). Pramen **312 Spring** se táhne ze `Zdroj_podzemních_vod` (v demo
výřezu žádný → vynechán). Modrá `C_BLUE`, GT `mask_water.png`. Z-order: po vrstevnicích, před
cestami. Procedurální §4.8 (proc voda) = noise-půlka; hydro jádro D8 budoucí (viz IDEAS). Detaily
mapování/licence: `data-sources.md` „ZABAGED vodstvo — REST konektor".

### 4.9 Cesty
`1 + round(det*1.6)` cest, konce na protilehlých okrajích (vodorovně/svisle), náhodná
pozice na okraji. Hlavní cesta plná (1,5 px), vedlejší čárkovaná. Vedení vázané na
terén — viz §9.
**Realizace Sez. 11:** hlavní = plná černá (2 px, ISOM **503 Road**), vedlejší =
čárkovaná (ISOM **505 Footpath**, Sez. 15 — 505 je v ISOM čárkovaná, návrat z 507); helpery
`_catmull_rom` (uniform splajn, krajní body zdvojené) + `_draw_dashed` (čárkování po
délce oblouku). GT do `mask_paths.png` (multi-class 1=503 / 2=505). Z-order: po
vrstevnicích, před bodovými symboly.
**✅ Terénně vázané vedení (Sez. 13):** přímý splajn s jitterem nahrazen **Dijkstra
least-cost** trasou (§9) — viz tam. Cesty traverzují svah místo přes vrchol.
**✅ Reálné cesty (Sez. 16, real-půlka):** `--paths real` nahradí procedurální Dijkstra
**reálnými komunikacemi z ČÚZK ZABAGED Polohopis (ArcGIS REST)** (`zabaged.py`, viz `data-sources.md`).
Vyžaduje `--terrain real` — sdílí výsek s DMR vrstevnicemi (`dmr.build_bbox`) → cesty sednou
na terén. Plná ISOM hierarchie **502-506** (silnice / cesta zpevněná / vozová / pěšina) dle
typu a povrchu (mapování `zabaged.map_path_to_isom`). Izomorfní s výškopisem: noise↔proc cesty,
real↔ZABAGED cesty. (Procedurální §4.9 = noise-půlka, ZABAGED = real-půlka — viz IDEAS.)

### 4.9b Budovy / stavby (real-půlka, Sez. 18)
**✅ Reálné budovy:** `--buildings real` vezme `Budova_jednotlivá_nebo_blok_budov__plocha_` ze
ZABAGED Polohopis (ArcGIS REST) (`zabaged.fetch_buildings`, týž konektor jako cesty/voda) pro tentýž výsek
→ ISOM **521 Building** (plošný černý symbol, výplň + obrys; `map_building_to_isom`). Bodová vrstva
budov je v lesních výsecích prázdná → netáhne se (jako pramen 312). Render `_draw_area_symbol`
(sdílený s vodní plochou 301 — voda modrá, budova černá). GT `mask_buildings.png`. Vyžaduje
`--terrain real`. Z-order: úplně navrch (po cestách). Izomorfní s vodou/cestami (real-půlka).

**Budovy se kreslí RAW (Sez. 27) — žádná generalizace.** Syrový ZABAGED půdorys (S-JTSK → grid → px →
polygon), přesně jako vodní plocha. Generalizace budov byla zavržena: L1 (min. velikost `_enforce_min_size`
+ Douglas-Peucker obrys, Sez. 18) i L2 displacement (Sez. 22) i orthogonalizace/pravoúhlost (Sez. 27)
KOMOLILY skutečný tvar/polohu (budova 1028994: 15 vrcholů → 5 zkomolených) → smazáno (~430 LOC). **Zásada:
generalizuj jen s důkazem, raw je default** (CLAUDE.md; voda byla dokonalá právě proto, že raw). Detail: IDEAS.

**Pozn. — OOM draw order:** vykreslovací pořadí v OOM určuje **priorita barev** (ne pořadí
objektů/symbolů v `.omap`); export jen referencuje symboly přes ISOM kód a zdědí color-table
template. Plošné symboly (301 combined, 521) potřebují v `.omap` UZAVŘENÝ path (close flag 18), jinak
je OOM nevyplní (`omap_export.area_object`, Sez. 18). Detail: GLOSSARY „Draw order / priorita barev".

### 4.9c El. vedení + lanovka/vlek (real-půlka, Sez. 24 + 55)
**✅ Reálné el. vedení + lanovka/vlek:** `--powerlines real` vezme `Elektrické_vedení` **a `Lanová dráha,
lyžařský vlek`** ze ZABAGED Polohopis (ArcGIS REST) (`zabaged.fetch_powerlines`, týž konektor) pro tentýž
výsek → ISOM **510 Power line, cableway or skilift** (tenká černá linie; `map_powerline_to_isom`).
Vyžaduje `--terrain real`. Liniové vrstvy, izomorfní s cestami. Atribut `NAPETI` (vedení) / `typ_ldv_k`
(lanovka) je v datech irelevantní → bez rozlišení 510/511 Major power line (vše 510, KISS). **ISOM 510 je
JEDEN symbol pro power line i cableway/skilift** (template id=121) → lanovka/vlek sloučeny do `--powerlines`
(Sez. 55, mirror vedení; NL 2 / LS 1 na Ještědu). GT `mask_powerlines.png`. Z-order: po cestách, před
budovami. **Pozor: 510, NE 516** (516 = Fence/plot — verify proti template, oprava zděděného předpokladu Sez. 24).

**Příčky („zuby") symbolu 510 — dvě fáze** (viz §0b a GLOSSARY „pseudorealistic"). Na OB mapě příčky
odpovídají SLOUPŮM (běžci se jimi řídí — doménový fakt). Generátor je proto NEvymýšlí rovnoměrně:
- **Fáze 1** (vždy): příčka na poloze REÁLNÉHO sloupu ze ZABAGED `Stožár_elektrického_vedení`
  **/ `Stožár lanové dráhy`** (bod, `fetch_powerline_masts`; sloup leží na vrcholu vedení/lanovky), kolmá
  na nejbližší segment (`_nearest_seg` + `_draw_tick_at`).
- **Fáze 2** (`pseudorealistic=True`, default): linie BEZ jediného evidovaného sloupu dostane
  rovnoměrné příčky (`_draw_perp_ticks`) — dekorace „vypadá jako vedení", poloha vymyšlená.
  Linie se sloupy zůstanou poctivě jen se sloupovými. `--only-real` (= `pseudorealistic=False`)
  fázi 2 vypne. Mapování/licence: `data-sources.md`, katalog `zabaged-isom-catalog.md`.

### 4.9d Železnice (real-půlka, Sez. 28)
**✅ Reálné tratě:** `--railways real` vezme `Železniční_trať` (id 75) + `Železniční_vlečka` (id 76)
ze ZABAGED Polohopis REST (`zabaged.fetch_railways`, týž konektor) → ISOM **509 Railway** (obě vrstvy,
`map_railway_to_isom`). Liniová, izomorfní s vedením. GT `mask_railways.png`. Z-order: po vedení, před
budovami. **509 je KOMBINOVANÝ symbol** (type 16: černé čárky 0,35 mm dash 1,5/break 1,0 mm + bílý
„pražcový" knockout) — render mode `"railway"` (bílý podklad + černé čárky → mezery BÍLÉ, odliší od
pěšiny 505 jejíž mezery ukazují terén). Vrstva je `Železniční_trať`, ne „Železnice" (verify-against-source).
U nádraží svazek kolejí = vlečky (`Železniční_vlečka`); „10 kolejí" jako PLOCHA = §4.9e kolejiště.

### 4.9e Kolejiště / zpevněné plochy (real-půlka, Sez. 28)
**✅ Reálné kolejiště:** `--paved real` vezme `Kolejiště` (id 122, plocha) ze ZABAGED → ISOM **501
Paved area** (`map_paved_to_isom`). Plošná, izomorfní s budovou/vodní plochou: render `_draw_area_symbol`
(`C_ROAD` výplň + `C_BROWN` obrys). GT `mask_paved.png`. Z-order: brzy (po terénu/bodech, před vodou)
= podklad, na němž leží koleje. **„10 kolejí" u nádraží v datech NEJSOU linie** — ZABAGED je generalizuje
do jedné plochy `Kolejiště` (Liberec hl. n. ~19 ha). V `.omap` jako **kombinovaný 501 (s obrysovou linií)**,
ne 501.1 (čistá plocha bez obrysu) — do kolejiště se nevstupuje, bounding line je významová (ISOM crossability).

**✅ Ostatní plocha v sídlech → 501.1 (real-půlka, Sez. 54):** `--paved real` bere i `Ostatní plocha v sídlech`
(id 115) → ISOM **501.1 Paved area BEZ obrysu** (`map_paved_to_isom` rozliší 501.1; `PAVED_OUTLINE[501.1]=None`).
Administrativní výplň zastavěného území (náměstí/dvory/parkoviště mezi budovami), defaultně přístupná → bez
bounding line. **Obří děravé polygony** (2371/1734 ha, stovky vnitřních prstenů pro budovy/zeleň/cesty) → vyžaduje
[podporu děr §4.9e′]; bez ní by 501.1 zalilo 41 % sídla (Sez. 53). **Z-order: dvouprůchod** `_generate_real_paved(urban_base=True)`
kreslí 501.1 ÚPLNĚ VESPOD (před surfaces → olivová 520 RÚIAN parcel ji nahoře překryje), `urban_base=False` kreslí
501 kolejiště na původní pozici. Barva **„Dolní hnědá 50%"** (rastr `C_PAVED` světlejší než silnice; v `.omap`
vlastní color-table slot na prioritě úplně dole, aby silnice/pěšiny vynikly — viz §4.9e″).

**§4.9e′ Podpora děr (holes) — enabler, Sez. 54.** Plošné symboly nesou z GeoJSON vnitřní prsteny (výřezy).
`arcgis.geom_to_polygons` vrací `[[vnější, díra1, …], …]` (RFC 7946 `coords[1:]`); rastr `_draw_area_symbol`
+ scanline helpery vyříznou díry **even-odd** (`_fill_rings_scanline`; bez děr rychlá PIL cesta = 0 regrese);
`.omap` `area_object` zřetězí prsteny, hole-flag 18 na hranicích, **poslední prsten close-only (2)** (konvence
z reálných map SampleMap/Blatná). Behavior-preserving co do počtu objektů (díra = další prsten v TÉMŽE objektu).
Dotýká se VŠECH plošných vrstev (voda/budovy/520/308/406/402…) → izomorfismus `_draw_area_symbol`.

**§4.9e″ Color-table priorita pro velkoplošnou base výplň — Sez. 54 (PRŮLOM).** 501.1 = první plošný symbol
ležící POD velkým množstvím jiných symbolů přes celé sídlo. Default ISOM paleta Mapperu NESTAČILA: 501.1 sdílel
color „Upper brown 50%" se silnicemi a v color-table prioritě překrýval jejich černé okraje → silnice mizely.
Fix: do `template_classic.omap` přidána vlastní color **„Dolní hnědá 50%" priority 35 (úplně dole)**, 501.1
přepojen na ni. Lekce: base-layer plošný symbol potřebuje vlastní color slot uspořádaný pod vším překrývajícím
(rastr ≠ omap: rastr kreslí pořadím, OOM prioritou). Paměť `omap-colortable-base-fill-priority`.

### 4.9f Skály a balvany (real-půlka, Sez. 30 + 57 + 63)
**✅ Reálné skály:** `--rocks real`. BODY + pole ze ZABAGED Polohopis (ArcGIS REST):
`Osamělý_balvan__skála__skalní_suk` (bod) → **204 Boulder** (kruh 0,4 mm); `Skupina_balvanů__bod_` (bod) →
**207 Boulder cluster** (trojúhelník 0,8×0,7 mm, vrchol nahoře); `Skupina_balvanů__linie_` (linie, Sez. 57) →
**208 Boulder field** (osa → buffer na úzký pás 1,5 mm, mirror stromořadí 406 §4.9n → ISOM 208 area pattern =
NÁHODNĚ rozmístěné a otočené plné trojúhelníky; `.omap` je `area_symbol` 208, OOM vyplní pattern věrně
z definice id 38, rastr = px-tuned aproximace `_draw_boulder_field_area`, deterministicky seedovaná; density
~1/mm² dle ISOM 0,8-1).

**Plocha 206 Gigantic boulder = z DMR 5G SKLONU (Sez. 63, `rock_relief.py`)** — NAHRADILA generalizovanou
ZABAGED `Skalní_útvary` (jeden blob přes celý masiv → věrná členitost věží a otevřených průchodů).
DETERMINISTICKÁ PROJEKCE z výškopisu (jako vrstevnice/form lines §4.9 z DMR), NE proxy. Algoritmus (převzat
z `temp/rockcore/`, laděno na pískovcovém Šulcáku; verify proti Mapy.com): SAMOSTATNÝ hi-res DMR fetch (~1,5 m;
render grid generátoru je na ~8 m/buňka, na věže nestačí) → sklon `np.gradient` (směrově nezávislý, NE hillshade
tmavost — ta je směrově závislá) → práh **46°** (jisté skalní stěny) → **morfologický uzávěr** (scelí stěny
+ vršek do bloku; samotný práh dá jen slivery, protože ploché vršky věží mají sklon ~0°) → vyplnit jen malé
díry (vrcholové plošiny <250 m²), velké průchody nechat → vektorizace přes **contourpy** (úroveň 0,5; NE
rasterio/shapely) → Douglas-Peucker + Chaikin (legitimní — de-pixeluje RASTER masku, NE čisté vektory jako
ZABAGED Sez. 30). Závislost **scipy** (morfologie + connected-components; jen `--rocks real`). `_draw_area_symbol`
černá výplň, polygony [outer, díra…] v S-JTSK = týž tok jako dřív. Cílové rozlišení 1,5 m (`TARGET_PX_M`),
ale ImageServer `exportImage` vrací **HTTP 500 nad ~7 Mpx** (F32 tiff, empiricky práh 6,8 OK / 8,2 fail —
Sez. 65) → **plošný cap `MAX_AREA_PX=6,5 Mpx`** (clamp PLOCHY gw·gh, ne strany; 6×4 km @ 1,5 m = 10,7 Mpx
přesto stranou < 4000, proto stranový strop neochránil). Velké landscape výseky tak zhrubnou na ~1,9 m/px;
plné 1,5 m všude = tiling (budoucí). **Pozor (Sez. 65 nález): Sez. 63 regen byl tímto prahem nekompletní** —
NL/LS/SV zůstaly na rané fázi se starou ZABAGED 206; opraveno plošným capem + regenem všech 5 DEV.
GT `mask_rocks.png` (5-class od Sez. 107). Z-order: úplně navrch (po budovách+řopících = OOM priorita skály > budovy).

**Pseudo injekce bodů 204 + 210 (FÁZE 2 pseudorealistic, Sez. 107):** ZABAGED body 204/210 nevede v reálné
hustotě (kompas: 204 gen 3/orig 1064, 210 gen 0/orig 975 → bodové sub-KPI 18,4 %; kartograf je v terénu kreslí
hustě podle skalnatosti, geodata to neumí). `_generate_pseudo_boulders` (gated `pseudorealistic`, BEZ vlastního
flagu — visí na `rocks="real"` → `point_base` i `only_real` ji vypnou; izomorf 310 marsh / 516 plot) je dosype na
**masku DOLOŽENÉ SKALNATOSTI**: 206 plochy (z DMR sklonu) + reálné ZABAGED 204/207 body, dilatováno o 150 m
(`PSEUDO_ROCK_DILATE_M`; suť/balvany vyzařují kolem stěn). 204 = kruh (reuse `_draw_boulder`), 210 = pole teček
`210.1` (samostatné `type=point` objekty, `_draw_stony_dot`, mirror `inject._sample_field`). Hustota na km² masky
(`PSEUDO_BOULDER_PER_KM2=500` / `PSEUDO_STONY_FIELD_PER_KM2=12`), kalibrovaná na **SHARE** (ne absolutní Σ — gen
celkově podstřeluje, Σgen ≈ ⅓ Σorig → správný absolutní počet by dal nadměrný share → ředění headline). **NENÍ
projekce dat** (poloha v rámci masky náhodná, reframe Sez. 79: detektor ikonek se učí tvar, ne kontext). **Nález
Sez. 107:** sklon ≠ skalnatost (obecná sklon-maska přestřelila body na svažité-ale-neskalnaté Bedřichovce → +0,3
pb), doložená skalnatost koreluje per mapa (+8,8 pb → KPI 59,1 %); věrná **per-mapa** distribuce z dat nejde
(skalnatost není v geodatech, data-gate jako vegetace). KPI 50,3 → **59,1 %**, bod sub 18,4 → 54,3 %.
**ZABAGED vrstvy nenesou typ/velikost/výšku (jen `jmeno`)** → per-feature rozhodování (hybridní 202/206) i
Chaikin smoothing na NICH ZAVRŽENY (bez datového podkladu; *generalizuj jen s důkazem*, Sez. 30). Chaikin na
DMR-206 (výš) je naopak legitimní — vyhlazuje raster masku, ne čistý vektor. Vyžaduje `--terrain real`.
(Pozn.: procedurální balvany §4.11 = zahozená noise-půlka, Sez. 11. **Plot ISOM 516–518 = doložený SKIP,
Sez. 57:** ZABAGED plot jako vrstvu nevede — jen Zeď/Hradba → 513 §4.9m, Zábrana → 519 §4.9o.)

### 4.9g Mosty / tunely / lávky (real-půlka, Sez. 31–33)
**✅ Reálné mosty:** `--bridges real` vezme ze ZABAGED (ArcGIS REST) `Most` (id 73), `Tunel` (id 74) a
`Lávka (linie)`/`Lávka (bod)` (id 67/66). **Most → 2 paralelní linie ISOM 512** offsetnuté na pravou normálu
osy (= hranatá závorka „[ ]" z default OOM template, verify proti uživatelovu `Most.omap` demu) + **buffer
crop nesené trati pod mostem** ±1,25 mm kolmo, s úhlovým filtrem (∥ osa < 25° = nesená trať, necropuje se).
**Tunel → 512 otočené o 90°** = krátké kolmé závorky na obou vjezdech (`_tunnel_portals`) + passage crop trati
projekcí vjezdu na trať (mezera 0,5 mm). **Lávka → bodový symbol 512.2 Footbridge** (rotace kolmo k toku).
GT `mask_bridges.png`. Geometrický self-check proti demu/datům PŘED OOM verify (paměť `geometric-selfcheck-before-oom`).

### 4.9h Řopíky (real-půlka, Sez. 26–27)
**✅ Reálné řopíky:** `--ropiky real` vezme `Bunkr` (`typbunkr_k='LO37'`, čs. lehké opevnění vz. 37) ze ZABAGED
jako **bodový orientační prvek** (NE budova 521) — vložený `asset/ropik_10000.omap` (asset pattern), orientovaný
„čelním zasypaným náspem VEN" k nejbližší **státní hranici** (`Hranice správní jednotky` `vyzn_zsh_k='1'`,
univerzální ČR). Fáze 1 (projekce reálných dat), ne pseudorealistická dekorace. Vyžaduje `--terrain real`.

### 4.9i Lesní průseky (real-půlka, Sez. 36)
**✅ Reálné průseky:** `--rides real` vezme `Lesní průsek` (id 16, REST jméno s MEZEROU jako tramvaj/lávka)
ze ZABAGED Polohopis REST (`zabaged.fetch_forest_rides`, `map_ride_to_isom`) → ISOM **508 Narrow ride** =
průhled lesem BEZ zřetelné vyšlapané cesty (ISOM odlišuje od cest 503–506). KISS, vrstva → vždy 508 (bez
kategoriálního atributu — verify SV 46 prvků). Liniová, izomorfní s cestami: render mode `"dashed"`
(`_draw_ride`), dash/break z template 508 = **3,0 / 0,375 mm** (dlouhé čárky, malé mezery → „skoro plná",
odliší od pěšiny 505 7,0/4,0). GT `mask_rides.png`. Z-order: po cestách, před vedením. **Runnability pozadí
(žlutá/zelená dle prostupnosti) se NEKRESLÍ** — vegetace není v datech (gate Sez. 3), je to UC5 predikce ne
projekce → ISOM varianta „without background". Vyžaduje `--terrain real`. Hustota: SV 46 / NL 119 / LS 20 /
HS 16 / NV 44.

### 4.9j Plošný pokryv / land-cover (real-půlka, Sez. 41-49)
**✅ Reálný pokryv:** `--surfaces real` vezme plošné pokryvové vrstvy a mapuje na ISOM symboly (`zabaged.fetch_open_land`
/ `fetch_cemeteries` / `fetch_utility_areas` + `ruian.fetch_private_land`, mappery `map_*_to_isom`):
- **Open land → ISOM 401** (plná ŽLUTÁ, bez obrysu): `Trvalý travní porost` (louka). Louka není kultura → bez
  patternu. Odstín 401 (sytá) = real část z dat; **403 Rough open (bledá žlutá) = PREDIKČNÍ ze separace**
  (Sez. 92, §4.9-predict) — ZABAGED 401/403 nerozliší (oba travní porost), 403 přichází jen ze separace mapy.
- **Udržovaná zeleň → ISOM 402 / 402.1** ✅ (Sez. 53): `Udržovaná zeleň` se ŠTĚPÍ podle atributu `typ_pudy_k`:
  `PO` „park, okrasná zahrada" → **402 Open land with scattered trees** (žlutá + BÍLÉ tečky = rozptýlené stromy,
  template color 30); `UZ` „ostatní udržovaná zeleň" → **402.1 …with scattered bushes** (žlutá + ZELENÉ tečky =
  rozptýlené keře, template color 27 „Green 60%" ≈ C_GREEN2). Tečky r 0,3 mm, grid 1,05 mm (větší/hustší než 412).
  Pod ISOM min. plochou 9 mm² → degraduje na 401 (izomorf 412). Render `_draw_dotted_surface_area`; .omap věrný
  samostatný combined area symbol (402/402.1 v template, NErozbaluje se jako 412). **402.1 = první „scattered
  bushes" zeleň z dat — vegetace gate neporušuje** (tvrdý ZABAGED objekt nesoucí kategorii, mirror stromořadí 406).
- **Pole → ISOM 412 Cultivated land** ✅ (Sez. 47-48): `Orná půda a ostatní dále nespecifikované plochy` → žlutá
  výplň + **černý tečkový pattern** (template 412.1, tečka r 0,15 mm, grid 1,2 mm, kotvený globálně k severu).
  Pod ISOM min. plochou 3×3 mm = 9 mm² → degraduje na 401 (izomorf se stromořadím Sez. 45). Render `_draw_dotted_surface_area`,
  .omap rozbal 412 = 401 + 412.1 (combined type 16 nepřiřaditelný objektu, precedent voda 301 / most 1→2).
- **Sad/zahrada → ISOM 520** ✅ (Sez. 49, oprava chybného 413 Orchard Sez. 48): `Ovocný sad, zahrada`. V ČR krajině
  jde převážně o **zahrady u rodinných domů a chalup — oplocené, nepřístupné běžci** → out-of-bounds olivová, ne
  běhatelný ovocný sad (rozhodnutí uživatele). Viz olivová níže (čtvrtý zdroj).
- **Olivová → ISOM 520 Area which shall not be entered** (plná OLIVOVÁ, zákaz vstupu — „zelená" v hantýrce
  orienťáků). **Pět zdrojů (Sez. 42 + 49 + 56):**
  - **Hřbitov** (`Hřbitov` ZABAGED): ISOM 2017-2 nemá vlastní hřbitovní symbol (verify template) → 520.
  - **Sad/zahrada** (`Ovocný sad, zahrada` ZABAGED, Sez. 49): zahrady u domů/chalup, oplocené → 520 (viz výše).
  - **Privátní pozemek u domu** (RÚIAN katastr, `ruian.fetch_private_land`): parcely `druhpozemkukod ∈ {5 zahrada,
    13 zastavěná plocha a nádvoří}` → 520. Živý mapař maluje olivovou tam, kam běžci nesmí (soukromé zahrady/dvory);
    druh pozemku to nese deterministicky (~80 % případů). Limit: oplocené louky/pole u domů (druh 2/7) zůstanou
    žluté — viz TODO „oplocené volné terény".
  - **Oplocené areály účelové zástavby** (ZABAGED `Areál účelové zástavby` 114, `map_utility_area_to_isom`):
    škola/hřiště/sport/stadión/kasárna/průmysl/garáže/nemocnice/zahrádkářská osada… → 520 (oplocený = zákaz vstupu).
  - **Kamenolom** (ZABAGED `Povrchová těžba, lom` 118, `map_quarry_to_isom`, Sez. 56): oplocený těžební areál se
    zákazem vstupu → 520. **NE 201 Impassable cliff:** 201 je LINIE (hrana stěny s ticky), ZABAGED dává PLOCHU →
    plocha→plocha je věrná, stěnu nedotahujeme (KISS, Σ1 marginální). Kamenné útvary (206 ad.) zůstávají v z-orderu
    NAD olivovou (skály se kreslí po surfaces). `druhtez_p` (kámen/…) ISOM nerozlišuje.

**§4.9j′ Olivová 520 dissolve do bloků + plot 516 — Sez. 98 (measure-first).** RÚIAN katastr fragmentuje
zástavbu na tisíce DROBNÝCH parcel (`temp/measure_520.py`: 91–96 % objektů 520 z RÚIAN privát, medián
146–323 m²; LS 52 % výseku → kompas přestřel 520 gen/orig **9×**). Kartograf kreslí jeden souvislý olivový
blok, ne mozaiku → **dissolve**: všechny zdroje 520 → sběrná maska → contourpy vektorizace
(`_dissolve_mask_to_polys`, reuse `rock_relief._contour_rings`/`_group_holes` §4.9l — **bez `shapely`**, není
v `.venv`) → souvislé bloky. RÚIAN-privát má vlastní pod-masku (zdroj plotu). Kompas 520 9×→**1,3×**.
**Plot 516 Fence (pseudo fáze 2):** ZABAGED plot nevede (§4.9m, Sez. 57) → linii dokreslujeme věrohodně po
obvodu RÚIAN-privát bloků ≥ `FENCE_MIN_AREA_M2` 0,5 ha (kalibr. measure-first `temp/measure_fence.py`: gen
160→21 ≈ orig 24). Obvod narovnán `_rdp` (contourpy schody → přímé spojnice vrcholů); ticky DOVNITŘ pozemku
(`_draw_fence_line` per-tick `_point_in_ring`, ISOM 516 spec „If the fence forms an enclosed area, tags inside").
Vypne `--only-real`. Jen `.omap` (USED_CODES +516) + rgb; vlastní GT maska zatím ne (linie mimo plošné Png2Area Y).
- **Asfaltové dopravní areály → ISOM 501** (přes paved kanál): `Areál účelové zástavby` typu `408 autobusové
  nádraží` / `409 čerpací stanice` (rozdělení 114 podle ISOM kódu: 520→surfaces, 501→paved). Kolejiště → 501
  (s obrysem, vymezený prostor). **Parkoviště (`Parkoviště, odpočívka` 123) → 501.1 BEZ obrysu (Sez. 57)** —
  průchozí zpevněná plocha splývající s okolím (ISOM 501 jen „where distinct boundary"; parkoviště jde do
  spodního z-order průchodu jako base výplň, mirror ostatní plochy v sídlech).
- **Drobné stavby → ISOM 521** (přes budovy): `Kůlna, skleník, fóliovník, přístřešek` (105) → 521 (Sez. 42).

Plošné, izomorfní s vodní plochou/budovou/kolejištěm: render `_draw_area_symbol` s `outline=None`, barva dle
`SURFACE_FILL` (`C_YELLOW` / `C_OLIVE` — **barvy normované ISOM, z palety, neladí se okem**); 412 pole / 402 park /
402.1 zeleň navíc tečkový pattern (`_draw_dotted_surface_area`, barva+poloměr+rozestup per-symbol ze `SURFACE_DOT`).
Jedna multi-class GT `mask_surfaces.png` (1=open land, 2=olivová, 3=pole, 4=402 park, 5=402.1 zeleň). **Z-order: ÚPLNĚ VESPOD** (podklad pod vrstevnicemi; olivová NAD žlutou/polem — privátní zahrada RÚIAN
přemaže pokryv pod ní; les zůstává bílá = vegetace gate). Vyžaduje `--terrain real`. Hustota pokryvu (Sez. 49,
po přesunu sad→520): SV 2040 olivová / 16 pole / NL 145 / 7 / LS 19761 / 21 / HS 2066 / 57 / NV 552 / 11.
**Verify Sez. 41** (`compare_real_vs_gen` SV):
otevřený prostor gen **0 % → 35.8 %** (real 34.7 %); Sez. 42 přidalo privátní pozemky + areály (LS centrum souvisle
olivové s žlutými parky = test uživatele „střed Liberce olivový s výjimkou parků").

### 4.9k Bodové orientační prvky (real-půlka, Sez. 43)
**✅ `--landmarks real`** vezme bodové ZABAGED vrstvy → ISOM 52x-53x + 417 (KISS vrstva → jeden symbol,
`zabaged.map_landmark_to_isom`): kříž/sloup kult. významu → **530** (ring), mohyla/pomník/náhrobek → **526 Cairn**,
věž/věžovitá nástavba + vodojem věžový + silo + těžní věž + větrný mlýn/motor + tovární komín (Sez. 52) + (plošná)
věžovitá stavba (centroid) → **524 High tower**, významný/osamělý strom → **417 Prominent large tree** (zelený kroužek, mimo vegetace gate —
liniový/bodový orient. prvek, ne plošná průchodnost). Render `_draw_landmark` (524 kříž+tečka / 526 kroužek+tečka /
530 kroužek / 417 zelený kroužek); multi-class `mask_landmarks.png`. Bodové objekty type 0 v .omap. Vyžaduje
`--terrain real`. Výskyt: SV 81 / LS ~99 (kříž 33/strom 38/věž 6/cairn 4 na SV). Nulové vrstvy (vodojem/silo/…)
mapovány pro úplnost (jinde se vyskytnou — princip „nic užitečného nevypadne").

**Sez. 44 (dávka 4 vodní/terénní body)** rozšířila `--landmarks` o: pramen (`Zdroj podzemních vod`) →
**312 Spring** (modré „U" ústím nahoru), vstup do jeskyně + ústí šachty/štoly → **203.2 Cave** (černá „Λ" stříška
hrotem nahoru = „with a distinct entrance"; 203.1 by byl V hrotem dolů „without entrance" — ověřeno uživatelem,
audit Sez. 44), nadzemní zásobní nádrž (plocha → centroid) → **311 Well/fountain/water tank** (modrý čtverec).
Výskyt: pramen Σ65 (přesně sedí na probe), jeskyně+šachta Σ9, nádrž Σ8 (LS 6 / HS 2). **POZOR konvence (audit
Sez. 44):** OOM `.omap` symbol coords mají osu **+y = DOLŮ** — rastrový render NEFLIPUJE (`screen_y = cy + omap_y`);
opačný předpoklad zrcadlil cave/spring → paměť `omap-symbol-y-axis-down`.

**Sez. 136 (pseudo body 417/419, FÁZE 2 `pseudorealistic`)** — `_generate_pseudo_veg_points`, izomorf pseudo
boulders (Sez. 107). Asymetrie: Png2Point **čte** 417/419, ale generátor je skoro nekreslil (417 jen řídce z ZABAGED
`Významný_strom`, 419 vůbec). Princip kamenů: **417 doplnit** na reálnou hustotu (cíl − reálné ZABAGED), **419 čistě
pseudo**. Hustota MĚŘENA z kartografových `.omap` (medián 417 ~27/km², 419 ~18/km²), losovaná per mapa. **Umístění**
(volba uživatele): MIMO vodu + MIMO 206 skály (strom neroste v balvanitém poli) + MIMO budovy/cesty/zpevněné
+ **MIMO železnici 509** (Sez. 138 E3 {A} Novina — balvany 204/210 padaly na žel. koridor; `railway_mask_img`
doplněna do `_build_forbid_px`)
(`_build_forbid_px`, **px rozlišení** — tenké 501/cesty pásy by se na gridu ztratily, symbol pod nimi zakryt; sdíleno
s pseudo boulders, DRY). **ISOM rozestup** (symboly se nepřekrývají): rejection sampling, min. vzdálenost středů
≥ r_a+r_b+mezera. Render `_draw_landmark` (417 zelený kroužek; **419 = zelený X**, mirror inject `_stamp_cross`).
Gated `pseudorealistic` (visí na `landmarks="real"`), pseudo → `landmarks_info` (meta) i `.omap`. KPI 58,6 → 61,1 %
(POKRYTÍ; proporčně Goodhart-citlivé — poloha pseudo).

**Sez. 137 (+418 Prominent bush or tree)** — třetí pseudo veg třída do téhož `_generate_pseudo_veg_points` (izomorf
417/419). Čistě pseudo (keře/buše ZABAGED nemapuje, jako 419). Hustota MĚŘENA stejnou crosswalk-aware metodou
(medián ~17,8/km², rozsah 6,6–25,3 → losovaný rozsah `(8, 26)`). Render `_draw_landmark` = **zelený PLNÝ disk**
(template id=103 `outer_color=3`, vnější r 0,375 mm) — vizuálně odlišný od 417 (dutý kroužek) i 419 (X). Sdílí
forbid masku + rejection sampling. `USED_CODES += "418"`, `LANDMARK_CLASS=9`. KPI 61,1 → 61,7 % (bod 59,2 → 62,4),
KOMPAS 418 z díry (orig 178/gen 0) na pokryté (gen 90). POZN.: 418 **NENÍ** ve scope Png2Point detekce — generátor
ho kreslí, aby se reconstructor jednou mohl naučit (pokrytí = strop, paměť `generator-coverage-is-the-ceiling`).

### 4.9l Mokřady (real-půlka, Sez. 44, dávka 4)
**✅ `--marsh real`** vezme plošné ZABAGED vrstvy `Bažina, močál` + `Rašeliniště (plocha)` → **308 Marsh**
(`zabaged.map_marsh_to_isom`, KISS vždy crossable 308 — data nenesou atribut překonatelnosti, NE 307 uncrossable).
Render `_draw_marsh_area` = MODRÁ vodorovná šrafa (scanline, rozestup 0,45 mm dle template patternu) ořezaná na
polygon; `.omap` = area_object 308 (OOM nakreslí pattern). Z-order nad plošným pokryvem (401/520), pod liniemi.

**✅ 310 Indistinct marsh (pseudo fáze 2, Sez. 99)** — ZABAGED nerozlišuje zřetelnou (308) vs nezřetelnou (310)
bažinu (measure-first: atribut rašeliniště/bažina geograficky binární, velikost nediskriminuje; „indistinct" =
kartografická interpretace okraje, ne katastrální fakt). Reálné mapy mají 308+310 PROMÍCHANÉ v mapě (medián ~59 %
na 310). → `_marsh_indistinct(cx,cy)` deterministická pseudonáhoda ~55 % (spatial-hash z centroidu, stabilní mezi
běhy) reklasifikuje část mokřadů na 310, JEN když `pseudorealistic` (`--only-real` = vše 308 = čistá projekce;
izomorf plotu 516). Render 310 = 2× řidší (0,90 mm) PŘERUŠOVANÁ staggered šrafa (`_draw_dashed_hline`, věrné
template `type=2` line_spacing 900 + point_distance 1725). `.omap` area_object 310; Y-pipeline `omap_raster`
AREA_ZORDER +310 (N_AREA 17→18). **Pozn.: coverage páka na DoD ~0** — ZABAGED mokřady na resources mapách řídké;
hodnota v Livelox párech mokřadnatých lokalit.
`mask_marsh.png`. Výskyt: NV 15 / HS 10 / NL 9 / SV 5 / LS 0 (sedí na probe Sez. 43).

### 4.9m Liniové orientační prvky (real-půlka, Sez. 43)
**✅ `--linefeatures real`** vezme liniové ZABAGED vrstvy → ISOM (KISS, `zabaged.map_line_feature_to_isom`):
stupeň/sráz → **104 Earth bank** (plná HNĚDÁ linie + jednostranné kolmé ticky; barva opravena z černé na hnědou
= template color 6 Brown, audit Sez. 44; orientace na nižší stranu svahu = TODO, chce DMR sklon; Σ981 = nejčastější
dosud netáhnutá), zeď + hradba/val/bašta → **513 Wall** (plná). Render
`_draw_line_feature` (wrapper nad `_draw_line_symbol` + ticky pro 104); multi-class `mask_linefeatures.png`. Liniové
objekty v .omap (OOM kreslí symbol z definice). Vyžaduje `--terrain real`. Výskyt SV: sráz 71 / zeď 16.
(Stromořadí `Liniová vegetace` jde od Sez. 45 plošně jako 406 — viz §4.9n.)

### 4.9n Stromořadí jako „lineární les" (real-půlka, Sez. 45)
**✅ `--treerows real`** vezme `Liniová vegetace` (id 15, v datech výhradně stromořadí `typveg_k=S`) → **406
Vegetation: slow running** (světle zelený pás). **Oprava 416 → 406:** Sez. 43 mapovala na 416, ale verify-against-source
spec ukázal, že **416 Distinct vegetation boundary = HRANICE mezi porosty** (kraj lesa / předěl uvnitř lesa), NE řada
stromů. ISOM kreslí stromořadí buď řadou bodů 417/418 (vyžaduje polohy kmenů — data je nemají, jen osu) nebo plošně
jako úzký pás lesa → volíme **plošně** (cesta II): osa linie → buffer na nepravidelný pás („špageta", deterministická
sinusová perturbace — real nelosuje), šířka **0,7 mm ≈ 7 m**, výplň 406 bez obrysu. **Min. plocha 1,0 mm²** (ISOM spec:
nejmenší zelený dot-screen je 1,0 mm² @ 1:15000) → menší úseky se zahodí. Render `_buffer_polyline_irregular` +
`_polygon_area_px` filtr + `_draw_treerow_area`; `mask_treerows.png`; plošný objekt 406 v .omap. **První zelená
vegetační plocha generátoru** — vegetace gate NEporušuje (tvrdý objekt z dat, ne hádaná hustota; izomorf s 308 Marsh:
KISS jedna úroveň). Z-order nad plošným pokryvem (401), pod vrstevnicemi/liniemi. Výskyt: SV 83 / HS 121 / LS 47 /
NV 18 / NL 4.

### 4.9o Prostupy v plotě — Crossing point (real-půlka, Sez. 52)
**✅ `--barriers real`** vezme `Zábrana` (id 54, jediný typ `typ_k=Z` „Závora, brána") → **519 Crossing point**.
ISOM 519 = průchod PŘES plot/zeď (branka, schůdky), **NE závora na cestě** → mapuje se jen bod ležící na nosné
**zdi 513 (≤ 5 m)**; závory na cestách (v OB irelevantní — běžec je obejde) se zahodí. **Verify-against-source
(krok 0, Sez. 52):** z 66 zábran na LS leží na 513 jen **2** (medián vzdálenosti od zdi 183 m) → vrstva řídká,
ale spravedlivě naplní skutečné průchody (volba uživatele „úplnost i za nízký výtěžek"). `zabaged.fetch_barriers`
spáruje bod s nejbližší zdí + vrátí tangentu; render `_draw_crossing_point` = **2 čárky kolmé na zeď** posunuté
±0,45 mm podél ní (plot prochází mezerou; symbol id 134, rotatable). Orientace = tangenta zdi přepočtená S-JTSK→px
transformací dvou bodů. **Zeď 513 se pod brankou PŘERUŠÍ** mezerou 1,2 mm (`_split_by_zones_interp`, mechanismus
passage cropu tunelů — ISOM „line shall be broken at the crossing point" pro nepřekonatelný plot); sráz 104 se neřeže;
počet zdí v meta beze změny. Jediná orientovaná bodová vrstva vedle řopíků/lávek. `mask_barriers.png` (single-class);
bodový objekt 519 s rotací v .omap (mirror lávky 512.2, OOM Test OK Sez. 52). Vyžaduje `--terrain real`. Výskyt: LS 2,
ostatní 0 (řídké). (Pozn.: „katalog vyčerpán" prohlášené zde v Sez. 52 **korigováno Sez. 55** — viz `zabaged-isom-catalog.md`; po měření zbývají kandidáti 208/519/528.)

### 4.9p Predikční vegetace → zeleň + 403 (Sez. 82/83/92)
> **Forest-age proxy (AOPK věk porostu, Sez. 62) — ⟲ ARCHIVOVÁNO Sez. 82, kód SMAZÁN Sez. 102.**
> A1 measure-first (Sez. 82) ho vyřadil jako zdroj predikční vegetace: pokrytí jen 33 % korpusu, IoU
> s kresbou kartografa 0,12, přestřel zelené 3,3×. JEDINÝ zdroj predikční vegetace je nyní **separace
> z reálné mapy** (`generator/separate.py`, [[separate_areas]]; integrováno Sez. 83 do `generate_map`
> přes kwarg `predict_areas_sjtsk` + orchestrátor `generator/pairs.py`). `connectors/forest.py`, `--forest-age`
> flag, funkce `_generate_real_forest_age`/`_draw_forest_age_area` SMAZÁNY (doložená slepá ulička, git/diář ji
> drží — jako Orto2Colors). DEV `--location` mapy proto kreslí bílý les; pseudorealistic vegetace pro lokality
> bez skenu = budoucí směr (TODO). Detail archivu: DONE Sez. 82/102.

#### 4.9p-predict — Predikční plochy ze SEPARACE reálné mapy (Sez. 82/83/92, ŽIVÁ cesta)
Zdroj predikční vegetace: **separace barev z Livelox mapy** (`generator/separate.py`,
[[separate_areas]]). map_gt segmentace mapy → per-ISOM-kód maska → contourpy vektorizace → polygony v S-JTSK
(přes Livelox quad) → `generate_map(predict_areas_sjtsk=…)` (provenance `predict`, render `_draw_predict_areas`).
**Třídy (registr `AREA_CLASSES` v separate.py + `PREDICT_AREA_*` v generator.py):**
- **406/408/410** (zeleň) — přímo z map_gt runnability labelu (1/2/3), plná zelená výplň.
- **403 Rough open** (Sez. 92, bledá žlutá `C_YELLOW_PALE`) — rozštěp žluté UVNITŘ open (gt label 4):
  `_is_pale_yellow` (nearest-color mezi scan ref **403 (254,222,154)** / 401 sytá / road / bílá-záchyt)
  oddělí bledou (403, predikt) od syté (401, real část — neseparuje se, scope „jen co data neumí").
  Staví na OČIŠTĚNÉM gt z map_gt (median + ignore přetisku + layout crop). Doloženo bimodalitou žluté
  na 5 vzorových mapách. **Pattern třídy (404/407/409) separace NEumí** (per-pixel slepá na tečky/pruhy,
  nález Sez. 90) → vlastní budoucí krok (model nebo generátor kreslí + Y rozšíří).
Zásada: separace = GT-feeder (~90 %, NEleštit práh; kvalitu dotáhne `Png2Area` model). Y rastr = `omap_raster`
(403 v `AREA_ZORDER` + `omap_export.AREA_CODES`/`USED_CODES`).

**416 Distinct vegetation boundary (LINIE, Sez. 101)** — odvozenina z predikčních veg ploch, NE samostatná
vrstva. Měření Sez. 101: 416 = **největší proporční díra KPI** (orig 633 / gen 0). Reálné mapy kreslí ZŘETELNÉ
hranice mezi oblastmi různé runnability (403↔406↔408↔410) tečkovanou linií; data (separace) nemají info o
„zřetelnosti" → bereme **mezitřídní** hranice (kde se stýkají různé veg třídy) + **délkový práh
`BOUNDARY_MIN_LEN_M`=50 m** (krátké šumové fragmenty separace odpadnou; reálné 416 medián 45-90 m, mezi-veg
samo přestřeluje 147/596 % obvodu). Algoritmus `_predict_veg_boundaries` (generator.py): contour každé veg
třídy z `veg_area_mask_img` (`PREDICT_AREA_CLASS` rastr) → per-bod prstenu klasifikuj, je-li v okolí JINÁ veg
vyšší třídy (dedup B>A, ať hrana A↔B jen jednou) → souvislé mezitřídní úseky → práh → RDP → polyline. Render
`_draw_boundary` (černá tečkovaná, izomorf `_draw_ride` 508); .omap přes `linefeature_features` (sym 416 z
template, **0 změna omap_export**); `mask_boundaries.png`. **LINIE → bez Y-area dluhu** (v době Sez. 101
Png2Line ještě neexistoval; .omap stačí pro KPI/kompas. Png2Line vznikl Sez. 130-132 — viz `model/png2line/`,
scope zatím watercourse 304/305, 416 jím není pokryto). Stejný typ problému jako marsh 310 (data nediskriminují), ale heuristika
MEZITŘÍDNÍ je doménově věrná. **KPI 46,1 → 49,3 %** (+3,2 pb; sub-linie 47,7 → 58,3). Zásada „neleštit": gen 416
je 0,24× reálného (per-mapa plató), nedoháníme na 1,0× (přestřel by KPI snižoval přes `min`).

**Render** `_draw_predict_areas` = plná zelená/bledožlutá výplň BEZ obrysu (vegetační/open plošný symbol,
izomorf s 406 stromořadím §4.9n / 401 / 520; díry zachovány přes scanline). Z-order: NAD plošným pokryvem
(401/520 podklad), pod stromořadím/mokřady/vrstevnicemi/liniemi. `mask_veg_area.png` (multi-class: 1=fight
410, 2=walk 408, 3=slow 406, 4=403). Plošné objekty v .omap (`AREA_CODES`). Provenance `predict` v meta
(`proxy:true`, `source:separace_realne_mapy`). Bez `predict_areas_sjtsk` (DEV `--location`) = bílý les.

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
Rastr z-order (Sez. 18): hned po vrstevnicích (§4.5) = POD vodou/cestami/budovami (hnědý
terénní detail, černé komunikace ho překryjí). GT do `mask_symbols.png` (multi-class) +
seznam pozic `point_symbols` v `meta.json`. (Realizace Sez. 10, z-order opraven Sez. 18.)

> **ISOM kódy — pozor (Sez. 13):** používáme **ISOM 2017-2 Rev 6 (2024)** číslování
> 109/110/111. Staré ISOM 2017 mělo pro tytéž symboly 112/113/115 (Rev 6 přečíslovalo
> a v 112+ jsou teď Pit / Broken ground / Prominent landform). Ověřeno proti oficiálnímu
> OOM symbol setu `ISOM 2017-2_10000.omap`. Cesty: 503 Road, 505 Footpath (vedlejší čárkovaná, Sez. 15).

### 4.11 Balvany a skalní stupně (`rock`) — ⚠ ZAVRŽENO (noise-půlka, Sez. 11)
> Procedurální balvany vypadaly uměle (kazily by domain gap feederu) → zahozeny při přestavbě
> Sez. 11. Reálné skály/balvany ze ZABAGED viz §4.9f (`--rocks real`). Ponecháno jako spec vize.
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
| Hnědá silniční | výplň silnice 502 | `#E8A774` | 0/28/50/9 (Upper brown 50%) |
| Modrá | voda, mokřad | `#2EC2F8` | 90/0/0/0 |
| Černá | skály, cesty, stavby | `#000000` | 0/0/0/100 |
| Purpurová | trať | `#C400AC` | 0/100/0/0 (Purple) |

> **Runtime implementace (jediný zdroj pravdy):** `generator/palette.py`
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
   - `rgb.png` — finální mapa (vstup modelu); u `--terrain real` i `rgb.pgw` (world file, georef
     rastru do S-JTSK, **rastr vždy grid-north-up**; grivace od Sez. 112 jen do `.omap` georef metadat
     `declination=grivation`, NE do rastru — rotace rastru je odložená curtains; `--grivation`/`-auto`/
     `-date`, konektor `magnetic.py`),
   - `mask_contours.png`; `mask_paths.png` (multi-class, proc 1=503 / 2=505, real +502/504/506,
     Sez. 11/15); `mask_symbols.png` (multi-class knoll/depression z generalizace §4.10, Sez. 10);
     `mask_water.png` (multi-class toky/plocha, jen `--water real`, Sez. 17); `mask_buildings.png`
     (jen `--buildings real`, Sez. 18). Masky `mask_veg/rock` byly se svými vrstvami zahozeny
     (Sez. 11, viz §4); `mask_water` se vrátila Sez. 17 jako reálná (ZABAGED), ne procedurální,
   - `meta.json` — seed, parametry, seznam bodových značek se souřadnicemi a typem
     (hotová detekční anotace ve stylu COCO/YOLO); blok `georef` (S-JTSK bbox + `.pgw`, Sez. 37)
     a `isom` (deklarace verze symbolů `2017-2` + měřítko, Sez. 38 — ochrana proti záměně s ISOM 2000).
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
   skenu (augmentace §8.3 jako samostatná vrstva). **Fotometrická půlka stupně 2 implementována
   Sez. 86** (`generator/degrade.py`: CMYK misregistrace, blur, papír+zažloutnutí, šum, JPEG —
   čistě fotometrické, Y se nemění). **Aplikuje se jako AUGMENTACE on-the-fly v tréninku
   `model/png2area/dataset.py` (Sez. 103), NE v `build_pair`** — degradace nepatří do generator() fáze I
   (ta drží render věrný, X páru = `rgb.png`); zapečení do `scan.png` bylo chyba opravená Sez. 103. Geometrická
   půlka (rotace/deformace) patří na úroveň páru/dlaždice (X+Y zároveň), ne sem. Roadmapa a pořadí vrstev:
   `IDEAS.md`. (Názvosloví bez A/B — ta patří vztahu k Pic2Omap.)
5. **Náhrada šumu reálným terénem.** ✅ **Implementováno (Sez. 5)** — `--terrain real`
   (generátor v `generator/`, konektor `connectors/dmr.py` od Sez. 16). Místo
   `fractal()` dosadí reálný ČÚZK
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
    na mřížce, čistý `heapq` (žádný scipy). **Cena hrany = vzdálenost [m] × (1 +
    `PATH_SLOPE_LIN`·sklon + `PATH_SLOPE_SQ`·sklon²)** + odpuzování od už nakreslených cest;
    sklon = |Δvýška|/vzdálenost (model „sklon hrany", ne izotropní slope buňky). Kvadratický
    člen tvrdě trestá srázy (Sez. 13 #3: čistě lineární nechával krátký sráz levnější než
    objížďku), hrana strmější než `PATH_MAX_SLOPE` (50 %) je zakázaná (tvrdý strop, fallback).
    Pohyb podél vrstevnice levný, stoupání drahé → traverz. Konce na
    protilehlých okrajích; surová 8-směrová trasa se zředí (`PATH_SIMPLIFY`) a vyhladí
    `_catmull_rom`. Deterministická (tie-break počítadlem). Funguje pro noise i real
    (na reálném DMR cesty vedou skutečnými sedly/údolími). „Vede údolím" v plném smyslu
    (preferuje údolnice) přijde až s hydro jádrem (toky = údolnice); teď jen vazba na sklon.
- **Reálné cesty místo procedurálních** (real-půlka, Sez. 16): `--paths real` vezme skutečnou
  síť komunikací z **ČÚZK ZABAGED Polohopis (ArcGIS REST)** (vektor, GeoJSON) pro tentýž výsek jako DMR.
  - **✅ Implementováno:** `zabaged.py` (sourozenec `dmr.py`) — ArcGIS REST `MapServer/<id>/query` s BBOX
    + `resultOffset` paging (přechod z WFS Sez. 26), cache `.zabaged_cache/`. Linie v S-JTSK → grid inverzí
    georef vrstevnic (Y-flip). Mapování ZABAGED kategorií → ISOM 502-506 (`map_path_to_isom`); render
    sjednocen s proc přes `_draw_path`/`PATH_STYLE`. Detaily: `data-sources.md` „ZABAGED komunikace — REST konektor".
    Vrstvy (`PATH_LAYERS`, Sez. 23 doplněno): `Silnice__dálnice`/`Ulice`→502, **`Silnice_neevidovaná`**
    (účelové/lesní asfaltky)→503, `Cesta` zpevněná→503 / nezpevněná→504, `Pěšina`→505/506. Pozn.: 502
    Wide road kreslen `casing` s **hnědou výplní** (`C_ROAD` = Upper brown 50%) + černé okraje (Sez. 23,
    dřív bílá výplň = neviditelná); 503 a 504 jsou v ISOM stejně tlusté (350 µm, liší se plná/čárkovaná);
    505 šířka 1 px (template 250 µm). **Princip (Sez. 23): stáhnout VŠECHNY relevantní vrstvy, ne vybrané**
    — selektivní `PATH_LAYERS` vynechal `Silnice_neevidovaná` → páteřní asfaltka úplně chyběla na mapě.
- **Výstup do vektoru**: pokud potřebuješ OCD/OMAP, exportuj jednotlivé vrstvy jako
  GeoJSON/SHP a konvertuj (OpenOrienteering Mapper umí import GDAL vektorů; OCAD má
  XML skripty). Vrstevnice jdou exportovat přímo z marching squares jako polylinie.
  - **✅ Vrstevnice implementováno (Sez. 8):** `generator.py` zapisuje `contours.geojson`
    — polylinie z contourpy se symbolem **101 Contour / 102 Index contour**,
    georeferencované v **S-JTSK (EPSG:5514)** pro `--terrain real` (lokální metry pro
    noise). Žádná vektorizace rastru (AutoTrace) — jdeme z přesného zdroje (contourpy),
    ne z pixelů. **103 Form line (pomocné vrstevnice, Sez. 29)** jdou do téhož souboru (kód 103,
    jen `--terrain real`) — viz §4.5.
  - **✅ `.omap` export (Sez. 8, přepsán Sez. 13, template-based Sez. 14):** `omap_export.py`
    (volá se vždy) zapíše `map.omap` s **vrstevnicemi (101/102) + pomocnými vrstevnicemi (103, Sez. 29)
    + cestami (502-506) + vodou (toky 304/305/306 + plocha 301 combined s břehovou linií, Sez. 58) + budovami (521) + el. vedením (510,
    Sez. 24) + železnicí (509, Sez. 28) + kolejištěm (501, Sez. 28) + body (109/110/111)**, Local CRS,
    paper-space (1 m → `1e6/scale` µm, vycentrováno, bez Y-flip). Plošné symboly (301 combined, 521)
    se exportují jako UZAVŘENÝ path s close flagem 18, jinak je OOM nevyplní (Sez. 18).
    NEduplikuje Pic2Omap `db2omap` (ten jde z rastru; my z přesných polylinií).
    **Vývoj přístupu:** Sez. 8 template-based (cizí `.omap`) → Sez. 13 **od nuly** (kvůli
    dědění bordelu z cizích souborů — 101.1 LIDAR, 503 Minor road, cizí podklady) → **Sez. 14
    zpět template-based, ale nad VLASTNÍM čistým template** `generator/template_classic.omap`
    (ISOM 2017-2, 169 symbolů / 35 barev, prázdné `<objects>`/`<templates>` — vyrobil uživatel
    v OOM). Skládáme jen `<objects>`; barvy/symboly/georef přebíráme z template. Zisk:
    **věrná geometrie bodů** (109 kruh, 110 elipsa `area_symbol`, 111 oblouk „⌣" `line_symbol`
    — místo dřívějšího jednotného kruhu) + plná ISOM knihovna jako reálná mapa z OOM (menší
    domain gap). Symbol id se parsují z template podle ISOM kódu (id nejsou pořadová: 503→110,
    505→112). Bodové symboly mají `rotation=0` (sever; orientaci protáhlosti 110 generátor
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
