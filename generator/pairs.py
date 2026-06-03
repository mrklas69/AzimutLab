"""pairs.py — per-classId továrna párů [render, .omap] z reálné Livelox mapy (UC5, Sez. 83).

Reframe (Sez. 79): generator() = továrna párů pro reconstructor(). Tahle orchestrace spojí pro
JEDEN Livelox classId dvě části do JEDNÉ georeferencované .omap:
  - REAL část: tvrdé ČÚZK vrstvy (cesty/voda/budovy/skály/…) z generate_map() pro výsek mapy,
  - PREDICT část: plošnou vegetaci SEPAROVANOU z té reálné mapy (separate.separate_areas, Sez. 82/83).
Render rgb.png (X-zdroj; degradér fáze II přijde později) i .omap (Y-cíl) vyrobí generate_map.
Provenance real/predict je v meta.json (A3, Sez. 83).

Společný grid = Livelox _georef_grid (Sez. 75): axis-aligned S-JTSK obal quadu. Real vrstvy se
georefují přes build_bbox(lat,lon,…) z CENTROIDU obalu (Gate A Sez. 83: shoda s obalem medián ~1 px,
posun jen v šířce ze zaokrouhlení mřížky — pro GT-feeder OK), separace přes _map_affine(quad) —
obojí skončí v jednom S-JTSK → .omap je zarovnaná.

Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""
import json
import sys
import pathlib

import numpy as np
from PIL import Image

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# connectors/ i generator/ na path PŘED importy (sys.path skript, fáze B — ne balík)
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))

from pyproj import Transformer            # noqa: E402
from livelox import _georef_grid, _map_affine  # noqa: E402
from separate import separate_areas, AREA_CLASSES  # noqa: E402
from generator import generate_map        # noqa: E402

Image.MAX_IMAGE_PIXELS = None
_CORPUS = _REPO_ROOT / "resources" / "livelox"
_SJTSK_TO_WGS84 = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)


def _separate_to_sjtsk(cid_dir: pathlib.Path, quad: list) -> list:
    """gt_labels → separace plošných tříd → polygony v S-JTSK (image-px → _map_affine).

    Vrací [(poly [vnější,díra…] v S-JTSK, code:int)] — tvar, který generate_map čeká v
    `predict_areas_sjtsk`. `_map_affine(quad)` je 2×3 matice image-px (col,row) → S-JTSK (x,y)."""
    gt = np.asarray(Image.open(cid_dir / "gt_labels.png"))   # 0-4/255 (map_gt separace)
    H, W = gt.shape
    A = _map_affine(quad, W, H)                              # (col,row) → S-JTSK
    polys = separate_areas(gt)
    out: list = []
    for lbl, (code, _) in AREA_CLASSES.items():
        for poly in polys[lbl]:                              # poly = [outer, díra…], prsten = (col,row)
            rings_sjtsk = []
            for ring in poly:
                pts = np.asarray(ring, dtype=float)          # (N,2) col,row
                hom = np.vstack([pts.T, np.ones(len(pts))])  # (3,N) [col;row;1]
                xy = (A @ hom).T                             # (N,2) S-JTSK
                rings_sjtsk.append([(float(x), float(y)) for x, y in xy])
            out.append((rings_sjtsk, int(code)))
    return out


def build_pair(cid, out_dir: str | None = None, ortho: bool = True):
    """Vyrobí pár-zdroj [render rgb.png, .omap] pro Livelox classId: real ČÚZK + separace vegetace.

    Odvodí výsek z Livelox _georef_grid (centroid → lat/lon, rozměry obalu → w_km/h_km), separuje
    vegetaci z mapy do S-JTSK a předá ji generate_map jako `predict_areas_sjtsk` (forest_age="off",
    nahrazeno separací). Vrací cestu k výstupní složce. `out_dir` None → `resources/livelox/<cid>/gen`."""
    cid = str(cid)
    cid_dir = _CORPUS / cid
    meta = json.loads((cid_dir / "meta.json").read_text(encoding="utf-8"))
    g = _georef_grid(meta)
    xmin, ymin, xmax, ymax = g["xmin"], g["ymin"], g["xmax"], g["ymax"]
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    lon, lat = _SJTSK_TO_WGS84.transform(cx, cy)             # centroid obalu → WGS84
    w_km, h_km = (xmax - xmin) / 1000.0, (ymax - ymin) / 1000.0

    predict_sjtsk = _separate_to_sjtsk(cid_dir, g["quad"])
    out = out_dir or str(cid_dir / "gen")
    print(f"{cid} \"{meta.get('name', '?')}\"  výsek {w_km:.2f}×{h_km:.2f} km @ "
          f"({lat:.5f}, {lon:.5f})  separace {len(predict_sjtsk)} ploch")
    return generate_map(lat, lon, w_km, h_km, forest_age="off",
                        predict_areas_sjtsk=predict_sjtsk, out_dir=out, ortho=ortho)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows cp1250 vs Unicode (Sez. 74)
    except Exception:
        pass
    cid = sys.argv[1] if len(sys.argv) > 1 else "1088447"
    path = build_pair(cid)
    print(f"pár → {path}")
