# sandbox/generator-poc

Proof-of-concept procedurálního generátoru výseku mapy pro orientační běh.
První reálný kód v repu (deštníková fáze). Realizuje **MVP řez** specifikace
[`docs/kb/generator-procedural.md`](../../docs/kb/generator-procedural.md):

- **vrstevnice** — izolinie výškového pole (§4.5), hlavní zvýrazněné (3 px),
- **vegetace** — prahovaná šumová pásma bílá → 3× zelená + žluté paseky (§4.2-4.3),
- **bažiny** — nízká + plochá místa, vodorovná modrá šrafa + tečkovaný obrys (§4.4),
- **balvany** — černé tečky, slope-vážené (hustěji ve strmém terénu) (§4.11),
- **ground-truth masky** — každá vrstva i jako segmentační maska (§8.1),
- **reálný terén** — `--terrain real` dosadí ČÚZK DMR 5G místo šumu (§8.5, Option 2;
  výškopis z `dmr.py`, vegetace/bažiny zůstávají syntetické).
- **vektor vrstevnic** — `contours.geojson` (ISOM **101/102** linie, georef S-JTSK pro
  real terén) a volitelně `map.omap` přes `--omap-template` (§9; `omap_export.py`).
  Vrstevnice jsou přímo polylinie z contourpy — ne vektorizace pixelů.

Záměrně NEobsahuje (přijde inkrementálně): tratě, cesty, rýhy, bodové
značky, severník.

## Cíl

Doložit, že metoda „mapa = vrstvy ze skalárních polí" produkuje použitelná
trénovací data **s anotací zdarma** — keystone pro modelovou větev (UC5),
obchází sparse-GT past z Pic2Omap.

## Spuštění

```powershell
# z kořene repa, ve venv:
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --out sandbox\generator-poc\output
# parametry: --seed INT  --rug 0-1  --vd 0-1  --wat 0-1  --rock 0-1

# Option 2 — reálný terén z ČÚZK DMR 5G (default souřadnice = Děčínsko, §8.5):
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --terrain real --out sandbox\generator-poc\output
# jiná lokalita: --lat 50.82 --lon 14.67  (WGS84; dlaždice se cachuje do .dmr_cache/)

# + vektorový .omap (vrstevnice 101/102) přes ISOM template — otevři výsledek v OOM:
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --terrain real `
    --omap-template "cesta\k\ISOM_template.omap" --out sandbox\generator-poc\output
```

Dávkový dataset (`batch.py`) — sada map + manifest + náhledová mozaika:

```powershell
# noise sada (16 map, reprodukovatelná z seed0+n):
.venv\Scripts\python.exe sandbox\generator-poc\batch.py --out sandbox\generator-poc\output\dataset_noise
# reálná sada z lokalit ČR (CZ_LOCATIONS — 10 členitých OB oblastí, DMR 5G terén):
.venv\Scripts\python.exe sandbox\generator-poc\batch.py --terrain real --out sandbox\generator-poc\output\dataset_real
```

## Výstup (`output/`, gitignored)

| Soubor | Obsah |
|--------|-------|
| `rgb.png` | finální mapa (vstup modelu) |
| `mask_contours.png` | binární maska vrstevnic |
| `mask_veg.png` | multi-class maska vegetace (hodnoty 0-4, vizuálně tmavá — je to GT, ne náhled) |
| `mask_water.png` | binární maska bažin |
| `mask_rock.png` | binární maska balvanů |
| `contours.geojson` | **vektor** vrstevnic (LineString + ISOM symbol 101/102; CRS S-JTSK pro real) |
| `map.omap` | OpenOrienteering Mapper mapa (jen s `--omap-template`; vrstevnice 101/102) |
| `meta.json` | seed, parametry, legenda tříd, info o vektor/omap exportu |

## Stack

Python 3.14 · numpy · contourpy (marching squares) · Pillow · pyproj (jen `--terrain real`,
WGS84→S-JTSK). Venv v kořeni repa (`.venv`).

Reálný terén = ČÚZK DMR 5G open data, **CC BY 4.0** (atribuce povinná — uložena i v `meta.json`).

## Determinismus

Stejný `seed` + parametry → identická mapa. PRNG = numpy `default_rng` (PCG64);
spec doporučuje mulberry32, ale potřebujeme jen reprodukovatelnost, ne bitovou
shodu s JS referencí.
