# sandbox/generator-poc

Proof-of-concept procedurálního generátoru výseku mapy pro orientační běh.
První reálný kód v repu (deštníková fáze). Realizuje **MVP řez** specifikace
[`docs/kb/generator-procedural.md`](../../docs/kb/generator-procedural.md):

- **vrstevnice** — izolinie výškového pole (§4.5), hlavní zvýrazněné (3 px),
- **bodové symboly extrémů** — malé uzavřené vrstevnice → ISOM **109/110/111**
  (kopeček / protáhlý kopeček / prohlubeň; ISOM 2017-2 Rev 6, Sez. 13), generalizace (§4.10),
- **cesty** — dvě větve (`--paths`):
  - `proc` (default) — procedurální **Dijkstra least-cost** (§9, Sez. 13), hlavní plná (ISOM
    **503**) / vedlejší čárkovaná (ISOM **505**); cesty traverzují svah, nešplhají přes vrcholy,
  - `real` — **reálné komunikace z ČÚZK ZABAGED WFS** (real-půlka §4.9, Sez. 16; `zabaged.py`),
    mapované na plnou ISOM hierarchii **502-506** (silnice/cesta zpevněná/vozová/pěšina) podle
    typu a povrchu. Vyžaduje `--terrain real` (sdílí výsek s DMR → cesty sednou na terén),
- **voda** — `--water real` (real-půlka, Sez. 17; týž `zabaged.py`): vodní toky ISOM **304/305/306**
  (pojmenovaný stálý / bezejmenný stálý / občasný; podzemní se nekreslí) + vodní plochy **301**
  (modrá výplň + břeh). Vyžaduje `--terrain real`. Pramen **312** (ze `Zdroj_podzemních_vod`, v demo
  výřezu žádný). Procedurální voda (hydro jádro D8) zatím ne,
- **budovy** — `--buildings real` (real-půlka, Sez. 18; týž `zabaged.py`): `Budova_..._plocha_` →
  ISOM **521 Building** (plošný černý symbol). Vyžaduje `--terrain real`. **Kartografická generalizace
  Úroveň 1** (min. velikost 0,5 mm, zjednodušení obrysu Douglas-Peucker 0,3 mm — z ISOM rozměrů),
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
Záměrně zatím NEobsahuje: vegetaci/bažiny/balvany, tratě, rýhy, **procedurální** vodu
(reálná ze ZABAGED je, Sez. 17), severník. (Pramen 312 je v konektoru, v demo výřezu chybí.)

## Cíl

Doložit, že metoda „mapa = vrstvy ze skalárních polí" produkuje použitelná
trénovací data **s anotací zdarma** — keystone pro modelovou větev (UC5),
obchází sparse-GT past z Pic2Omap.

## Spuštění

```powershell
# z kořene repa, ve venv:
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --out sandbox\generator-poc\output
# parametry: --seed INT  --rug 0-1 (členitost terénu, jen noise)  --det 0-1 (počet cest)

# Option 2 — reálný terén z ČÚZK DMR 5G (default souřadnice = Soví vrch, Lužické hory, §8.5):
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --terrain real --out "sandbox\generator-poc\Soví vrch"
# jiná lokalita: --lat 50.82 --lon 14.67  (WGS84; dlaždice se cachuje do .dmr_cache/)

# reálné cesty + voda + budovy z ČÚZK ZABAGED WFS (real-půlka; vyžadují --terrain real):
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --terrain real --paths real --water real --buildings real --out "sandbox\generator-poc\Soví vrch"
# komunikace, voda i budovy pro výsek se cachují do .zabaged_cache/
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
| `mask_paths.png` | multi-class maska cest (1=503 / 2=505 / 3=502 / 4=504 / 5=506; proc dělá 1+2, real 2-6 dle dat) |
| `mask_water.png` | multi-class maska vody (1=304 / 2=305 / 3=306 / 4=301; jen `--water real`) |
| `mask_buildings.png` | maska budov (1=521; jen `--buildings real`) |
| `mask_symbols.png` | multi-class maska bodových symbolů extrémů (1=109 / 2=110 / 3=111) |
| `contours.geojson` | **vektor** vrstevnic (LineString + ISOM symbol 101/102; CRS S-JTSK pro real) |
| `map.omap` | OpenOrienteering Mapper mapa (vždy; template-based: vrstevnice 101/102 + cesty 502-506 + voda 301/304-306 + budovy 521 + body 109/110/111, plná ISOM knihovna) |
| `meta.json` | seed, parametry, legenda tříd, info o vektor/omap exportu |

## Stack

Python 3.14 · numpy · contourpy (marching squares) · Pillow · pyproj (jen real režimy terén/cesty/
voda/budovy, WGS→S-JTSK). Venv v kořeni repa (`.venv`). Konektory reálných dat žijí v **`connectors/`**
v kořeni LAB (`dmr.py` výškopis, `zabaged.py` komunikace + voda + budovy — sourozenci, sdílejí
`dmr.build_bbox`); generátor si jejich složku přidá na `sys.path` (Sez. 16, vytaženo ze sandboxu).

Reálná data = ČÚZK DMR 5G (výškopis) + ZABAGED Polohopis (cesty + voda + budovy), obojí open data
**CC BY 4.0** (atribuce povinná — uložena i v `meta.json`).

## Determinismus

Stejný `seed` + parametry → identická mapa. PRNG = numpy `default_rng` (PCG64);
spec doporučuje mulberry32, ale potřebujeme jen reprodukovatelnost, ne bitovou
shodu s JS referencí.
