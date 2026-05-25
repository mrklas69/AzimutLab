"""
dmr.py — stažení reálného výškopisu z ČÚZK DMR 5G (Option 2, spec §8.5).

Nahrazuje fraktální šum v generator.py reálným terénem. Zdroj: ArcGIS ImageServer
ČÚZK (open data, CC BY 4.0 — atribuce povinná). Služba vrací float32 grid výšek
(Bpv) pro libovolný bbox → přesně to, co generátor potřebuje do pole `elev`.

Klíčová zjištění (ověřeno feasibility testem, Sezení 5):
  - REST endpoint: .../arcgis2/rest/services/dmr5g/ImageServer/exportImage
  - pixelType F32, 1 band, nativní rozlišení 2 m, data v S-JTSK (EPSG:5514).
  - exportImage vrátí GeoTIFF, který Pillow přečte přímo jako mode="F" (žádný GDAL).

Pozn. k souřadnicím: vstup je WGS84 (lat/lon), ČÚZK pracuje v S-JTSK Křovák
(EPSG:5514) — proto převod přes pyproj. S-JTSK má v ArcGIS matematickou orientaci,
souřadnice ČR jsou záporné (x ≈ -700 tis., y ≈ -965 tis.).
"""
from __future__ import annotations

import io
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer

# REST endpoint DMR 5G ImageServeru (nové .gov.cz; cesta MUSÍ obsahovat /rest/).
_IMG_SERVER = "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"

# Transformer WGS84 → S-JTSK; always_xy=True → vstup (lon, lat), výstup (x, y).
# Vytváří se jednou na úrovni modulu (inicializace pyproj není zadarmo).
_TF_WGS84_TO_SJTSK = Transformer.from_crs("EPSG:4326", "EPSG:5514", always_xy=True)


def build_bbox(lat: float, lon: float, gw: int, gh: int, tile_m: float):
    """Spočte bbox v S-JTSK (metry) tak, aby měl poměr stran jako mřížka gw×gh.

    Kratší strana (sever-jih, osa y) = `tile_m`; delší (východ-západ, osa x) se
    natáhne v poměru gw/gh. Tím je buňka výsledného gridu izotropní (čtvercová)
    a reálný terén se nezkreslí — viz rozhodnutí Sezení 5 (poměrový výsek).

    Veřejná (Sez. 8): kromě sestavení requestu ji generator.py volá i pro
    georeferencování vektorového exportu vrstevnic (grid → S-JTSK metry).
    Vrací (xmin, ymin, xmax, ymax).
    """
    cx, cy = _TF_WGS84_TO_SJTSK.transform(lon, lat)   # střed v S-JTSK
    width_m = tile_m * (gw / gh)                       # delší strana (E-W)
    height_m = tile_m                                  # kratší strana (N-S)
    xmin, xmax = cx - width_m / 2, cx + width_m / 2
    ymin, ymax = cy - height_m / 2, cy + height_m / 2
    return xmin, ymin, xmax, ymax


def _cache_path(lat: float, lon: float, gw: int, gh: int, tile_m: float, cache_dir: Path) -> Path:
    """Cesta k cache souboru pro daný požadavek (stejné parametry → stejný soubor)."""
    # souřadnice na 6 desetin (~0,1 m) stačí na jednoznačnost dlaždice
    key = f"dmr_{lat:.6f}_{lon:.6f}_{gw}x{gh}_{int(tile_m)}m.tif"
    return cache_dir / key


def fetch_elevation_grid(
    lat: float,
    lon: float,
    gw: int,
    gh: int,
    tile_m: float = 1000.0,
    cache_dir: str | Path | None = None,
) -> np.ndarray:
    """Vrátí reálný výškopis jako float32 pole tvaru (gh, gw) — metry Bpv, sever nahoře.

    Stahuje z ČÚZK DMR 5G ImageServeru přes exportImage; výsledek cachuje na disk
    (batch generování pak netáhne tutéž dlaždici opakovaně). Server převzorkuje
    nativní 2m grid bilineárně přímo na požadované rozlišení (gw, gh).
    """
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".dmr_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath = _cache_path(lat, lon, gw, gh, tile_m, cache_dir)

    if cpath.exists():
        # cache hit — načti uložený TIFF (žádný síťový provoz)
        arr = np.asarray(Image.open(cpath), dtype=np.float32)
    else:
        # cache miss — sestav request a stáhni
        xmin, ymin, xmax, ymax = build_bbox(lat, lon, gw, gh, tile_m)
        params = {
            "bbox": f"{xmin},{ymin},{xmax},{ymax}",
            "bboxSR": "5514",
            "imageSR": "5514",
            "size": f"{gw},{gh}",                       # export rovnou na mřížku generátoru
            "format": "tiff",
            "pixelType": "F32",
            "interpolation": "RSP_BilinearInterpolation",
            "f": "image",
        }
        url = f"{_IMG_SERVER}/exportImage?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "AzimutLab-generator/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read()
        # server při chybě vrací JSON místo obrázku → srozumitelná výjimka
        if "image/tiff" not in ctype:
            raise RuntimeError(
                f"ČÚZK DMR 5G nevrátil TIFF (Content-Type={ctype!r}). "
                f"Odpověď: {raw[:300].decode('utf-8', 'replace')}"
            )
        # Validace PŘED zápisem do cache: ImageServer občas vrátí degenerovaný TIFF
        # (validní hlavička, ale oříznutá data, Content-Length přitom „sedí") — typicky
        # když bbox zasahuje za hranici ČR, kde DMR 5G nemá data. Takový soubor NESMÍ
        # do cache, jinak ho každý další běh načte a zase spadne. Proto: nejdřív zkus
        # načíst, teprve po úspěchu ulož.
        try:
            arr = np.asarray(Image.open(io.BytesIO(raw)), dtype=np.float32)
        except OSError as e:
            raise RuntimeError(
                f"ČÚZK DMR 5G vrátil neúplný TIFF ({len(raw)} B) pro ({lat}, {lon}) — "
                f"dlaždice nejspíš zasahuje mimo pokrytí (za hranicí ČR). Posuň lokalitu "
                f"hlouběji do vnitrozemí. (PIL: {e})"
            ) from e
        cpath.write_bytes(raw)                          # ulož do cache až po úspěšném načtení

    # sanity check: výšky v ČR jsou cca 115–1603 m n. m.; mimo rozsah = noData/díra
    if arr.min() < -100 or arr.max() > 2000:
        raise RuntimeError(
            f"Podezřelé výšky {arr.min():.1f}–{arr.max():.1f} m — dlaždice "
            f"({lat}, {lon}) možná zasahuje mimo pokrytí DMR 5G (noData)."
        )
    return arr
