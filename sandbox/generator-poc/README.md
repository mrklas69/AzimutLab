# sandbox/generator-poc

Proof-of-concept procedurálního generátoru výseku mapy pro orientační běh.
První reálný kód v repu (deštníková fáze). Realizuje **MVP řez** specifikace
[`docs/kb/generator-procedural.md`](../../docs/kb/generator-procedural.md):

- **vrstevnice** — izolinie výškového pole (§4.5), hlavní zvýrazněné (3 px),
- **bodové symboly extrémů** — malé uzavřené vrstevnice → ISOM **109/110/111**
  (kopeček / protáhlý kopeček / prohlubeň; ISOM 2017-2 Rev 6, Sez. 13), generalizace (§4.10),
- **cesty** — terénně vázané **Dijkstra least-cost** (§9, Sez. 13), hlavní plná (ISOM **503**) /
  vedlejší čárkovaná (ISOM **505 Footpath**); cesty traverzují svah, nešplhají přes vrcholy,
- **ground-truth masky** — každá vrstva i jako segmentační maska (§8.1),
- **reálný terén** — `--terrain real` dosadí ČÚZK DMR 5G místo šumu (§8.5, Option 2;
  výškopis z `dmr.py`).
- **vektor** — `contours.geojson` (ISOM **101/102** linie, georef S-JTSK pro real terén) a
  `map.omap` (vždy; §9; `omap_export.py`). OMAP je **template-based** nad vlastním čistým ISOM
  2017-2 template `template_classic.omap` → věrná geometrie bodů (110 elipsa, 111 oblouk) + plná
  symbolová knihovna. Vrstevnice jsou přímo polylinie z contourpy — ne vektorizace pixelů.

**Přestavba (Sezení 11):** generátor stavíme „znovu a lépe", vrstvu po vrstvě, s
důrazem na vizuální věrnost. Plošné vrstvy (vegetace, paseky, bažiny, balvany) byly
vědomě **zahozeny** (vypadaly uměle → kazily by domain gap feederu); historie v gitu.
Záměrně zatím NEobsahuje: vegetaci/bažiny/balvany, tratě, rýhy, vodní toky, det-řízené
bodové značky (pramen/posed/…), severník.

## Cíl

Doložit, že metoda „mapa = vrstvy ze skalárních polí" produkuje použitelná
trénovací data **s anotací zdarma** — keystone pro modelovou větev (UC5),
obchází sparse-GT past z Pic2Omap.

## Spuštění

```powershell
# z kořene repa, ve venv:
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --out sandbox\generator-poc\output
# parametry: --seed INT  --rug 0-1 (členitost terénu, jen noise)  --det 0-1 (počet cest)

# Option 2 — reálný terén z ČÚZK DMR 5G (default souřadnice = Děčínsko, §8.5):
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --terrain real --out sandbox\generator-poc\output
# jiná lokalita: --lat 50.82 --lon 14.67  (WGS84; dlaždice se cachuje do .dmr_cache/)
```

Každý běh píše i `map.omap` (template-based nad `template_classic.omap` — otevři v OOM).

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
| `mask_paths.png` | multi-class maska cest (1=503 hlavní / 2=505 vedlejší; GT, ne náhled) |
| `mask_symbols.png` | multi-class maska bodových symbolů extrémů (1=109 / 2=110 / 3=111) |
| `contours.geojson` | **vektor** vrstevnic (LineString + ISOM symbol 101/102; CRS S-JTSK pro real) |
| `map.omap` | OpenOrienteering Mapper mapa (vždy; template-based: vrstevnice 101/102 + cesty 503/505 + body 109/110/111, plná ISOM knihovna) |
| `meta.json` | seed, parametry, legenda tříd, info o vektor/omap exportu |

## Stack

Python 3.14 · numpy · contourpy (marching squares) · Pillow · pyproj (jen `--terrain real`,
WGS84→S-JTSK). Venv v kořeni repa (`.venv`).

Reálný terén = ČÚZK DMR 5G open data, **CC BY 4.0** (atribuce povinná — uložena i v `meta.json`).

## Determinismus

Stejný `seed` + parametry → identická mapa. PRNG = numpy `default_rng` (PCG64);
spec doporučuje mulberry32, ale potřebujeme jen reprodukovatelnost, ne bitovou
shodu s JS referencí.
