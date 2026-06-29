"""
ortofoto.py — stažení reálného ortofota z ČÚZK jako podklad generované mapy.

Sourozenec dmr.py (terén) a zabaged.py (vektory): táž ČÚZK ArcGIS infrastruktura
(ags.cuzk.gov.cz), týž S-JTSK (EPSG:5514), týž sdílený build_bbox. Slouží jako
georeferencovaný podklad ve výseku mapy — vizuální verify generátoru proti realitě
(sedí generované cesty/budovy/voda na letecký snímek?).

Klíčová zjištění (ověřeno proti zdroji, Sezení 26):
  - REST endpoint: .../arcgis1/rest/services/ORTOFOTO/MapServer/export — pozor,
    MapServer (ne ImageServer jako DMR) a TŘETÍ instance `arcgis1`
    (DMR = arcgis2, ZABAGED = arcgis).
  - spatialReference 102067 / latestWkid 5514 (S-JTSK Křovák) → bere týž bbox jako DMR.
  - maxImageWidth/Height = 4096 → výsek na plátno generátoru (typ. 2751×1834) se vejde
    do jednoho exportu (žádné dlaždicování).
  - export vrací RGB PNG (format=png24).
  - licence CC BY 4.0 (ČÚZK Ortofoto ČR, 2letý cyklus) — atribuce povinná.
"""

import io
import math
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

from ssl_ctx import ssl_context  # sdílený certifi TLS kontext (ČÚZK Let's Encrypt, Sez. 175)

# ortofoto je velký rastr (12000×8000 = 96 Mpx, při jemnějším mpp i víc) → vypni PIL
# DecompressionBomb ochranu (default limit 89 Mpx); zdroj je důvěryhodný ČÚZK, ne útok.
Image.MAX_IMAGE_PIXELS = None

# sdílíme build_bbox s dmr.py (DRY) — TÝŽ výsek jako terén/vektory, vše tedy sedne na sebe
from dmr import build_bbox

# REST endpoint ČÚZK ORTOFOTO MapServeru (arcgis1; cesta MUSÍ obsahovat /rest/).
_MAP_SERVER = "https://ags.cuzk.gov.cz/arcgis1/rest/services/ORTOFOTO/MapServer"

# Strop velikosti obrazu na jeden export (z MapServer metadat: maxImageWidth/Height).
_MAX_IMG_PX = 4096


def _cache_path(lat: float, lon: float, out_w: int, out_h: int,
                tile_m: float, cache_dir: Path) -> Path:
    """Cesta k cache souboru — stejné parametry (vč. výstupního rozlišení) → stejný soubor."""
    # souřadnice na 6 desetin (~0,1 m) stačí na jednoznačnost dlaždice
    key = f"orto_{lat:.6f}_{lon:.6f}_{out_w}x{out_h}_{int(tile_m)}m.png"
    return cache_dir / key


def _export_tile(xmin: float, ymin: float, xmax: float, ymax: float,
                 w: int, h: int) -> np.ndarray:
    """Stáhne JEDEN ortofoto dílek (bbox v S-JTSK, rozměr w×h px) z MapServer/export.

    Bez cache — cachuje se až slepený výsledek. Vrací RGB pole (h, w, 3) uint8.
    """
    params = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "bboxSR": "5514",
        "imageSR": "5514",
        "size": f"{w},{h}",
        "format": "png24",
        "transparent": "false",
        "f": "image",
    }
    url = f"{_MAP_SERVER}/export?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "AzimutLab-generator/0.1"})
    with urllib.request.urlopen(req, timeout=120, context=ssl_context()) as resp:  # větší dlaždice mohou trvat
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read()
    # server při chybě vrací JSON místo obrázku → srozumitelná výjimka
    if "image/png" not in ctype:
        raise RuntimeError(
            f"ČÚZK ORTOFOTO nevrátil PNG (Content-Type={ctype!r}). "
            f"Odpověď: {raw[:300].decode('utf-8', 'replace')}"
        )
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.load()
    except OSError as e:
        raise RuntimeError(f"ČÚZK ORTOFOTO vrátil neúplný PNG ({len(raw)} B): {e}") from e
    return np.asarray(img, dtype=np.uint8)


def fetch_ortofoto(
    lat: float,
    lon: float,
    gw: int,
    gh: int,
    tile_m: float,
    out_w: int,
    out_h: int,
    cache_dir: str | Path | None = None,
) -> np.ndarray:
    """Vrátí ortofoto výseku jako RGB pole tvaru (out_h, out_w, 3) uint8, sever nahoře.

    Bbox je TENTÝŽ jako u DMR/vektorů (sdílený build_bbox s gw/gh/tile_m) → podklad
    sedne pixel-přesně na mapu. Rozlišení (out_w × out_h) volí volající nezávisle na
    mřížce. Přesáhne-li delší strana strop MapServeru (4096 px), obraz se stáhne po
    DLAŽDICÍCH (rovnoměrná mřížka dílů ≤ strop) a slepí — tím lze získat libovolné
    rozlišení až k nativnímu 0,2 m/px (pozor na velikost souboru i RAM v OOM).
    """
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".ortofoto_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath = _cache_path(lat, lon, out_w, out_h, tile_m, cache_dir)

    if cpath.exists():
        # cache hit — načti uložený PNG (žádný síťový provoz)
        return np.asarray(Image.open(cpath).convert("RGB"), dtype=np.uint8)

    # bbox shodný s terénem (build_bbox: tile_m = S-J strana, E-W v poměru gw/gh)
    xmin, ymin, xmax, ymax = build_bbox(lat, lon, gw, gh, tile_m)

    if max(out_w, out_h) <= _MAX_IMG_PX:
        # vejde se do jednoho exportu
        arr = _export_tile(xmin, ymin, xmax, ymax, out_w, out_h)
    else:
        # dlaždicování: rovnoměrná mřížka dílů ≤ strop. Hranice dílů v PIXELECH (round,
        # poslední dobere zbytek) → díky lineárnímu mapování px→S-JTSK díly přesně
        # navazují bez překryvu i mezery. Sever je nahoře (row 0 = ymax).
        n_cols = math.ceil(out_w / _MAX_IMG_PX)
        n_rows = math.ceil(out_h / _MAX_IMG_PX)
        col_edges = [round(i * out_w / n_cols) for i in range(n_cols + 1)]
        row_edges = [round(j * out_h / n_rows) for j in range(n_rows + 1)]
        arr = np.empty((out_h, out_w, 3), dtype=np.uint8)
        for j in range(n_rows):
            r0, r1 = row_edges[j], row_edges[j + 1]
            for i in range(n_cols):
                c0, c1 = col_edges[i], col_edges[i + 1]
                # bbox dílu: col 0 = levý = xmin; row 0 = horní = sever = ymax
                sx0 = xmin + (xmax - xmin) * c0 / out_w
                sx1 = xmin + (xmax - xmin) * c1 / out_w
                sy1 = ymax - (ymax - ymin) * r0 / out_h    # horní okraj dílu (vyšší y)
                sy0 = ymax - (ymax - ymin) * r1 / out_h    # dolní okraj dílu
                arr[r0:r1, c0:c1] = _export_tile(sx0, sy0, sx1, sy1, c1 - c0, r1 - r0)

    # ulož slepený obraz do cache (validní obsah zaručil _export_tile u každého dílu)
    Image.fromarray(arr).save(cpath)
    return arr
