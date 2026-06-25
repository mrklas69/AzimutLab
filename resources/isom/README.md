# Katalog ISOM symbolů

`resources/isom/` je lokální referenční katalog symbolů pro scan mining. SVG soubory jsou tvarové
reference ISOM symbolů. **Nejsou** zdrojem skenových barev — barvy skenu se musí detekovat ze vstupního
rastru.

Očekávané lokální rozložení:

```text
resources/isom/
  index.json              # generovaný/lokální, dle index.schema.json
  index.schema.json       # verzovaný kontrakt
  svg/                    # lokální SVG dump, neverzovaný dokud není jasná provenance
  descriptors/            # generované deskriptory, lokální
```

Builder akceptuje i současné ploché rozložení dumpu (`resources/isom/*.svg`).
Pro nové kurátorované kopie používej `svg/`, aby katalog uměl později čistě oddělit
raw importy od generovaných deskriptorů.

Sestavit nebo zvalidovat lokální index:

```powershell
.venv\Scripts\python.exe tools\build_symbol_index.py --resources resources\isom
.venv\Scripts\python.exe tools\build_symbol_index.py --resources resources\isom --write
.venv\Scripts\python.exe tools\list_isom_capabilities.py --resources resources\isom
```

`--write` umí vygenerovat draft `index.json` z názvů SVG (`525_small_tower.svg`). Draft záznamy mají
`geom="unknown"` a `license="unknown"`, dokud nejsou kurátorované. Produkční konzumenti volají API
s `strict=True`.

Generátorové / zdrojové capabilities žijí v `isom/capabilities.py`, ne v SVG souborech.
Politika konfliktu: mapper scan > external geodata > pseudo. V praxi: pokud sken reálného mapaře
nesouhlasí se ZABAGED, vyhrává scan-mined evidence mapaře.

Nevkládej inline SVG do CSV. Raw SVG drž v `svg/` při kuraci, stabilní metadata v `index.json`
a generované strojové deskriptory v `descriptors/`.
