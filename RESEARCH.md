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
  **Ověřeno (Sez. 3): ČÚZK ho jako open data neposkytuje** — nový hustý DMP OK je z obrazové
  korelace (fotogrammetrie, jen povrch, žádné echoes), surové LLS mračno není open. Detail
  + náhradní cesta (CHM, NIR maska) v `docs/kb/data-sources.md` → „Vegetace gate".
- Tohle je přímý vstup pro **UC4-II** (generování inspirované souřadnicemi/terénem).

## Datové cesty pro UC5/UC4 (A / B / C) + sim-to-real

Tři **nekonkurenční** zdroje pro modelovou větev (rozlišeno Sez. 4):

- **(A) Geodata** (ČÚZK DMR/ortofoto) — reálný terén, ale ne hotové mapy.
- **(B) Reálné korpusy map** (`.omap`/`.ocd` + skeny) — řídké, licenčně zatížené.
- **(C) Syntetická generace** — neomezený objem, **ground-truth zdarma** (každá vrstva
  je segmentační maska). Cena: domain gap (hladší než realita).

**Recept (sim-to-real):** předtrénink na (C) + fine-tuning/validace na (B); reálný terén
z (A) dosazený do (C) místo šumu (spec §8.5, **hotovo Sez. 5** — `--terrain real`, ČÚZK
DMR 5G přes ArcGIS ImageServer). Realizace (C): metoda `docs/kb/generator-procedural.md`,
PoC `sandbox/generator-poc/` (Sez. 4-5).

## Metody (z Pic2Omap)

- Segmentace ploch (U-Net) — viz Pic2Omap ML pilot (mean IoU 0.666 within-domain).
- Color separation (palette-based, LAB nearest) — Pic2Omap `color_separator.py`.
- Generování map (UC4-I) — **PoC hotov** (procedurální, viz „Datové cesty" výše).
  Restaurace/inpainting (UC3) — TBD.

## Otevřené otázky průzkumu

- ~~Poskytuje ČÚZK plné klasifikované mračno bodů jako open data?~~ **Vyřešeno (Sez. 3): NE**
  — viz „Vegetace gate" v `docs/kb/data-sources.md`. Pro vegetaci přes Karttapullautin chybí
  multi-echo mračno; náhrada jen slabší (CHM + NIR maska).
- Jaké generativní přístupy dávají „realisticky vyhlížející" orienťácké mapy (UC4-I)?
- Jaký je state-of-the-art v de-creasing / dewarping fotografií dokumentů (UC3)?

## Zdroje (URL)

- Karttapullautin (Rust) — <https://github.com/karttapullautin/karttapullautin>
- Vegetation density paper (ICA Proc. 2018) — <https://ica-proc.copernicus.org/articles/1/92/2018/ica-proc-1-92-2018.pdf>
- Green mapping guide (Jarkko R.) — <http://www.routegadget.net/karttapullautin/greenmapping.pdf>
- Lidar basemap generation (tmsw.no) — <http://tmsw.no/mapping/basemap_generation.html>
