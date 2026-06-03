# RESEARCH — AzimutLab

Survey existujících nástrojů, metod a přístupů. Porovnávací/analytická vrstva
(„co už umí kdo a jak"). Referenční katalog konkrétních věcí (zdroje dat, spec,
nástroje k použití) žije v `docs/kb/` — sem patří *zhodnocení*, tam *evidence*.

> Skeleton (Sezení 1). Plní se průběžně, jak průzkum postupuje.
> Sezení 2 (2026-05-23): doplněna metoda LIDAR → orienteering mapa.

## Existující nástroje (vektorizace / kartografie)

| Nástroj | Co řeší | Relevance pro AzimutLab |
|---------|---------|--------------------------|
| CoVe | color line vectorization (v OOM) | UC4-III: liniová vektorizace už vyřešená |
| OCAD / OpenOrienteering Mapper | tvorba orienťáckých map | cílový formát (OCD/OMAP), spec referenční |
| Karttapullautin | LIDAR → orienťácká mapa (vrstevnice/vegetace) | UC2+UC4-II: LIDAR pipeline, inspirace |
| Pic2Omap (sourozenec) | raster → OMAP, ML pilot (U-Net plochy) | UC4-III + UC5: přímý předchůdce |

## Metoda: LIDAR → orienteering mapa (Karttapullautin)

Open-source generátor orienťáckých podkladových map z **klasifikovaného leteckého
LIDAR mračna bodů** (autor Jarkko Ryyppö; dnes přepsán do Rustu —
`github.com/karttapullautin/karttapullautin`, dříve Perl). Survey jeho přístupu:

**Vstup:** klasifikované mračno bodů ve formátu **LAS/LAZ** — *ne* hotový DEM grid.
LAS standard rozlišuje třídy `Ground`, `Low / Medium / High Vegetation` (výškové prahy
nejsou pevně dané spec, ladí se). Klíčové je, že nástroj potřebuje **i vegetační echa**,
ne jen terénní body.

**Pipeline (automatické fáze):**
1. **Vrstevnice** — z `Ground` bodů se interpoluje terén → generují se vrstevnice,
   plus detekce kopečků (`knolls`) a prohlubní (`depressions`).
2. **Vegetace** — hustota vegetace z poměru vegetačních ech (odrazů od listoví/větví)
   v daných výškových pásmech → mapuje se na **ISOM zelenou** (různá hustota porostu).
   Otevřený prostor (chybějící vegetační echa) → žlutá. **Pozor:** zelená kóduje výšku/
   hustotu porostu, *ne přímo* průchodnost (runnability) — to je interpretace mapéra.
3. **Útesy/skály** (`cliffs`) — z prudkých gradientů sklonu terénu.

**Výstup:** georeferencované rastry (vrstevnice, vegetace, prohlubně, útesy).
**Konfigurace:** textový `pullauta.ini` s mnoha parametry (green shades, point density
faktory) — laděním se předchází „zeleným pruhům" a docílí rovnoměrného rozložení.

**Akademická opora:** Tibor et al., *Automatically Generated Vegetation Density Maps
with LiDAR Survey for Orienteering Purpose*, ICA Proceedings 2018 — peer-reviewed popis
metody vegetation density (viz Zdroje).

### Důsledek pro AzimutLab (váže na `docs/kb/data-sources.md`)
- **ČÚZK DMR 5G je ground-only** výškopis → stačí na **vrstevnice**, ale **ne na vegetaci**.
- Vegetace (zelená/žlutá) vyžaduje **plné klasifikované mračno bodů** se všemi echo třídami.
  **Ověřeno (Sez. 3) + DOLOŽENO MĚŘENÍM (Sez. 59): ČÚZK ho jako open data neposkytuje.**
  Sez. 59 stáhl DMP 1G list NBOR52 (Soví vrch) přes ATOM + laspy → **100 % single-return, jen
  GROUND/HIGH VEG/building, 0 % multi-echo** = jen koruny, žádný podrost. Surové LLS mračno není
  open (jen ZÚ na vyžádání), a je staré (2009-13). **`lasertool` segfaultuje na Win11**; i kdyby
  běžel, ze single-return dá jen CHM výšku korun (zavádějící proxy, vysoký les ≠ neprůchodno).
  Detail + cesta stažení mračna + kandidáti plochy hustníku v `docs/kb/data-sources.md` → „Vegetace gate".
- Tohle je přímý vstup pro **UC4-II** (generování inspirované souřadnicemi/terénem).

## Datové cesty pro UC5/UC4 (A / B / C) + sim-to-real

Tři **nekonkurenční** zdroje pro modelovou větev (rozlišeno Sez. 4):

- **(A) Geodata** (ČÚZK DMR/ortofoto) — reálný terén, ale ne hotové mapy.
- **(B) Reálné korpusy map** (`.omap`/`.ocd` + skeny) — řídké, licenčně zatížené.
  Příklad: **Mapový portál ČSOS** (7000+ map) — ale gate ZAVŘENA: jen náhledy 96 dpi
  s vodoznakem, copyright klubů, souhlas vydavatele nutný i pro výzkum (viz
  `docs/kb/data-sources.md`). Korpus (B) = oslovit vydavatele, ne scrapovat portál.
- **(C) Syntetická generace** — neomezený objem, **ground-truth zdarma** (každá vrstva
  je segmentační maska). Cena: domain gap (hladší než realita).

**Recept (sim-to-real):** předtrénink na (C) + fine-tuning/validace na (B); reálný terén
z (A) dosazený do (C) místo šumu (spec §8.5, **hotovo Sez. 5** — `--terrain real`, ČÚZK
DMR 5G přes ArcGIS ImageServer). Realizace (C): metoda `docs/kb/generator-procedural.md`,
kód `generator/` (od Sez. 4, živé; pilíř od Sez. 39). Od **Sez. 8** generátor vedle rastru+masek zapisuje
i **vektor vrstevnic** (`contours.geojson`, ISOM 101/102, georef S-JTSK pro real, §9) —
krok od UC5-feedru (rastr) k UC4 OCD/OMAP výstupu; přímo z contourpy polylinií, ne
vektorizací rastru.

> **⟲ Reframe Sez. 79-80 (pointer; plná revize receptu = A1).** Recept výše platí pro tvrdou geometrii, ale cíl
> UC5 se posunul z `ortofoto→runnability` (val mIoU strop ~0,25, archivováno Sez. 78-79) na **`reconstructor()`**
> (sken existující mapy → `.omap`), trénovaný na párech [degradovaný render, `.omap`] z **`generator()`**
> (real + predict část). Sim-to-real se tím nemění principiálně (syntetika + reálné), ale „target" je rekonstrukce
> vektoru, ne predikce runnability z ortofota. Detail: GLOSSARY `generator()`/`reconstructor()`, IDEAS „Tři fáze I/II/III".

## Metody (z Pic2Omap)

- Segmentace ploch (U-Net) — viz Pic2Omap ML pilot (mean IoU 0.666 within-domain).
- Color separation (palette-based, LAB nearest) — Pic2Omap `color_separator.py`.
- Generování map (UC4-I) — **PoC hotov** (procedurální, viz „Datové cesty" výše).
  Restaurace/inpainting (UC3) — TBD.

## Otevřené otázky průzkumu

- ~~Poskytuje ČÚZK plné klasifikované mračno bodů jako open data?~~ **Vyřešeno (Sez. 3): NE,
  DOLOŽENO MĚŘENÍM (Sez. 59)** — DMP 1G je 100 % single-return (jen koruny). Viz „Vegetace gate".
- **Existuje JINÝ reálný podklad pro alespoň PLOCHU obecného hustníku (ne plnou runnability škálu)?**
  Neprozkoumáno (Sez. 59): ÚHÚL věk/zakmenění porostu / Copernicus HRL Tree Cover Density /
  multi-temporal ortofoto (paseka→porost). Probnout — při selhání všech zaprotokolovat vegetaci mimo real část.
- Jaké generativní přístupy dávají „realisticky vyhlížející" orienťácké mapy (UC4-I)?
- Jaký je state-of-the-art v de-creasing / dewarping fotografií dokumentů (UC3)?

## Zdroje (URL)

- Karttapullautin (Rust) — <https://github.com/karttapullautin/karttapullautin>
- Vegetation density paper (ICA Proc. 2018) — <https://ica-proc.copernicus.org/articles/1/92/2018/ica-proc-1-92-2018.pdf>
- Green mapping guide (Jarkko R.) — <http://www.routegadget.net/karttapullautin/greenmapping.pdf>
- Lidar basemap generation (tmsw.no) — <http://tmsw.no/mapping/basemap_generation.html>
