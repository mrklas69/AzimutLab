# sandbox/generator-poc

Proof-of-concept procedurálního generátoru výseku mapy pro orientační běh.
První reálný kód v repu (deštníková fáze). Realizuje **MVP řez** specifikace
[`docs/kb/generator-procedural.md`](../../docs/kb/generator-procedural.md):

- **vrstevnice** — izolinie výškového pole (§4.5),
- **vegetace** — prahovaná šumová pásma bílá → 3× zelená + žluté paseky (§4.2-4.3),
- **bažiny** — nízká + plochá místa, vodorovná modrá šrafa (§4.4),
- **ground-truth masky** — každá vrstva i jako segmentační maska (§8.1).

Záměrně NEobsahuje (přijde inkrementálně): tratě, balvany, cesty, rýhy, bodové
značky, severník. A reálný terén místo šumu (§8.5, = pozdější Option 2: ČÚZK DMR 5G).

## Cíl

Doložit, že metoda „mapa = vrstvy ze skalárních polí" produkuje použitelná
trénovací data **s anotací zdarma** — keystone pro modelovou větev (UC5),
obchází sparse-GT past z Pic2Omap.

## Spuštění

```powershell
# z kořene repa, ve venv:
.venv\Scripts\python.exe sandbox\generator-poc\generator.py --out sandbox\generator-poc\output
# parametry: --seed INT  --rug 0-1  --vd 0-1  --wat 0-1
```

## Výstup (`output/`, gitignored)

| Soubor | Obsah |
|--------|-------|
| `rgb.png` | finální mapa (vstup modelu) |
| `mask_contours.png` | binární maska vrstevnic |
| `mask_veg.png` | multi-class maska vegetace (hodnoty 0-4, vizuálně tmavá — je to GT, ne náhled) |
| `mask_water.png` | binární maska bažin |
| `meta.json` | seed, parametry, legenda tříd |

## Stack

Python 3.14 · numpy · contourpy (marching squares) · Pillow. Venv v kořeni repa (`.venv`).

## Determinismus

Stejný `seed` + parametry → identická mapa. PRNG = numpy `default_rng` (PCG64);
spec doporučuje mulberry32, ale potřebujeme jen reprodukovatelnost, ne bitovou
shodu s JS referencí.
