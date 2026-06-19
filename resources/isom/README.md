# ISOM symbol catalog

`resources/isom/` is the local symbol reference catalog for scan mining. SVG files are shape references for ISOM symbols. They are not the source of scan colors; scan colors must be detected from the input raster.

Expected local layout:

```text
resources/isom/
  index.json              # generated/local, follows index.schema.json
  index.schema.json       # tracked contract
  svg/                    # local SVG dump, not tracked until provenance is clear
  descriptors/            # generated descriptors, local
```

The builder also accepts the current flat dump layout (`resources/isom/*.svg`).
Use `svg/` for new curated copies so the catalog can later separate raw imports
from generated descriptors cleanly.

Build or validate the local index:

```powershell
.venv\Scripts\python.exe tools\build_symbol_index.py --resources resources\isom
.venv\Scripts\python.exe tools\build_symbol_index.py --resources resources\isom --write
.venv\Scripts\python.exe tools\list_isom_capabilities.py --resources resources\isom
```

`--write` can generate a draft `index.json` from SVG filenames like `525_small_tower.svg`. Draft records use `geom="unknown"` and `license="unknown"` until curated. Production consumers should call the API with `strict=True`.

Generator/source capabilities live in `isom/capabilities.py`, not in SVG files.
The conflict policy is: mapper scan > external geodata > pseudo. In practice,
if a real mapper's scan disagrees with ZABAGED, scan-mined mapper evidence wins.

Do not put inline SVG into CSV. Keep raw SVG files in `svg/` when curating,
stable metadata in `index.json`, and generated machine descriptors in
`descriptors/`.
