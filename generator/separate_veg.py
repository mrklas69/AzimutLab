"""separate_veg.py — separace predikční vegetace (406/408/410) z reálné OB mapy → vektor → .omap.

ZÁRODEK MODULU (povýšeno z PoC, Sez. 82). Hlavní tah reframe (Sez. 79/80): predikční vegetaci
generátoru NEbrat z dat (forest-age ARCHIVOVÁN Sez. 82 — pokrytí jen 33 % korpusu, IoU 0,12 s kresbou
kartografa, přestřel zelené 3,3×), ale SEPAROVAT z reálné Livelox mapy. Mapař = ground truth (nakreslil,
co v terénu viděl), univerzální (každá keep mapa nese barvu k separaci), a pár [render, .omap] je
z definice KONZISTENTNÍ.

Role v pipeline (Sez. 80, A2): tahle algoritmická separace = LEVNÝ GT-FEEDER pro budoucí model
`Png2Area` (OOM area symbol = plošný = jedna ze tří CV úloh Png2Point/Png2Line/Png2Area). NEMÁ být
věrná na 100 % (PoC ~90 %) — kvalitu dotáhne model trénovaný na množství párů, ne leštění prahu
(zásada Sez. 82: „separace = feeder, neleštit"). Pod konstrukcí páru ze Sez. 80 (X = degradovaný
export z NAŠÍ .omap) nemusí být dokonce ani věrná původní mapě — jen půjčuje realistické tvary, aby
.omap nevypadala jako náhodné kaňky.

Tok: map_gt separace (gt_labels 0-4/255; zelené 1/2/3 = 406/408/410) → per-úroveň maska → contourpy
vektorizace (REUSE rock_relief: _contour_rings/_group_holes/_rdp/_chaikin) → polygony [outer, díra…]
v image-px → omap_export.write_omap (image-px = grid, .omap nese podklad map.png pro OOM verify).

DALŠÍ KROK (Sez. 82 Příště): integrace do generate_map() — real ČÚZK vrstvy + tahle predikční
separace v JEDNÉ .omap (kanál predict_veg, nahradí --forest-age) + A3 provenience flag real/predict.

Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""
import json
import sys
import pathlib

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_closing, label

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# connectors/ MUSÍ na path PŘED importem rock_relief — ten táhne `from dmr import …` (sourozenec
# v connectors/). generator/ je sys.path[0] při přímém spuštění; connectors/ doplníme my (sys.path
# skript, fáze B — ne balík).
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))

# rock_relief (vektorizační pipeline) i omap_export jsou sourozenci v generator/
from rock_relief import _contour_rings, _group_holes, _rdp, _chaikin  # noqa: E402
from omap_export import write_omap  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
_CORPUS_DIR = _REPO_ROOT / "resources" / "livelox"

# zelený label (z map_gt: 1=406 slow, 2=408 walk, 3=410 fight) → ISOM kód + vizualizační barva
LEVELS = {1: ("406", (181, 230, 181)), 2: ("408", (120, 200, 140)), 3: ("410", (40, 160, 90))}

# čištění masky před vektorizací (image-px ~1,33 m/px): malý uzávěr scelí roztřepený okraj, min.
# plocha zahodí pixelový šum. ISOM min. mapovatelná plocha ~1 mm² = (10 m)² ≈ 56 px @ 1,33 m;
# bereme konzervativně 120 px (~2 mm²) — PoC neřeší drobky. RDP/Chaikin de-pixelují obrys.
CLOSE_ITERS = 1
MIN_AREA_PX = 120
SIMPLIFY_PX = 1.5
CHAIKIN_ITERS = 2


def vectorize_level(mask: np.ndarray) -> list:
    """Boolean maska jedné úrovně → polygony [outer, díra…] v image-px (REUSE rock_relief).

    Vrací list polygonů, každý = [vnější prsten, díra1, …]; prsten = np.array (col, row).
    Týž tvar jako rock_relief.detect_rock_areas / zabaged.geom_to_polygons → zapadne do
    omap_export.write_omap (area_object) i kreslení beze změny."""
    m = binary_closing(mask, iterations=CLOSE_ITERS)
    # zahoď malé komponenty (pixelový šum)
    lab, n = label(m)
    if n:
        sizes = np.bincount(lab.ravel())
        for i in range(1, len(sizes)):
            if sizes[i] < MIN_AREA_PX:
                m[lab == i] = False
    if not m.any():
        return []
    rings = _contour_rings(m)                 # (col,row) prstence
    if not rings:
        return []
    out = []
    for poly in _group_holes(rings):          # [[outer, díra…], …]
        cleaned = [_chaikin(_rdp(r, SIMPLIFY_PX), CHAIKIN_ITERS) for r in poly if len(r) >= 4]
        if cleaned and len(cleaned[0]) >= 4:
            out.append(cleaned)
    return out


def separate_veg(gt_labels: np.ndarray) -> dict:
    """Z GT labelů (map_gt: 0-4/255) → {label: [polygony]} pro zelené úrovně 1/2/3.

    Jádro GT-feederu: vstup = runnability segmentace mapy (map_gt.segment_gt), výstup = vektorové
    plochy predikční vegetace per ISOM úroveň (406/408/410), v image-px. Konzument: write_omap /
    overlay / (budoucí) generate_map predict_veg kanál."""
    return {lbl: vectorize_level(gt_labels == lbl) for lbl in LEVELS}


def _render_overlay(rgb: np.ndarray, level_polys: dict, out_path: pathlib.Path) -> None:
    """Verify: ztlumená původní mapa + vektorová zeleň přes ni (vizuální důkaz věrnosti)."""
    base = (rgb.astype(np.float32) * 0.35 + 255 * 0.65).astype(np.uint8)
    ov = Image.fromarray(base).convert("RGB")
    d = ImageDraw.Draw(ov, "RGBA")
    for lbl, (_, col) in LEVELS.items():
        for poly in level_polys[lbl]:
            outer = [(float(x), float(y)) for x, y in poly[0]]
            if len(outer) >= 3:
                d.polygon(outer, fill=(*col, 170), outline=(0, 0, 0, 120))
            for hole in poly[1:]:                 # díry zpět na podklad
                hp = [(float(x), float(y)) for x, y in hole]
                if len(hp) >= 3:
                    d.polygon(hp, fill=(255, 255, 255, 0))
    ov.save(out_path)


def main(cid: str) -> None:
    """PoC běh na jedné mapě korpusu: separace → overlay (verify) + .omap (OOM verify)."""
    map_dir = _CORPUS_DIR / cid
    meta = json.loads((map_dir / "meta.json").read_text(encoding="utf-8"))
    rgb = np.asarray(Image.open(map_dir / "map.png").convert("RGB"))
    gt = np.asarray(Image.open(map_dir / "gt_labels.png"))   # 0-4/255 (map_gt separace)
    H, W = gt.shape
    print(f"{cid} {W}x{H}  scale 1:{int(meta['mapScale'])}  mpp {meta['effectiveMppX']:.2f}")

    level_polys = separate_veg(gt)
    for lbl, (code, _) in LEVELS.items():
        px = int((gt == lbl).sum())
        print(f"  {code} (label {lbl}): {px:>8} px = {100*px/gt.size:4.1f}%  "
              f"→ {len(level_polys[lbl]):4d} polygonů")

    _render_overlay(rgb, level_polys, map_dir / "separate_veg_overlay.png")
    print(f"overlay → {map_dir/'separate_veg_overlay.png'}")

    # .omap: zelená jako forest_age_features (image-px = grid), map.png podklad pro OOM verify
    feats = [([[(float(x), float(y)) for x, y in r] for r in poly], code)
             for lbl, (code, _) in LEVELS.items() for poly in level_polys[lbl]]
    counts = write_omap(
        contour_features=[], path_features=[], point_symbols=[], water_features=[],
        building_features=[], powerline_features=[],
        gw=W, gh=H, world_w_m=meta["effectiveMppX"] * W, world_h_m=meta["effectiveMppY"] * H,
        scale=float(meta["mapScale"]), out_path=map_dir / "separate_veg.omap",
        ortho_template={"name": "map.png", "img_w": W, "img_h": H, "opacity": 1.0},
        forest_age_features=feats,
    )
    print(f".omap  → {map_dir/'separate_veg.omap'}  (objektů {counts['objects']}, "
          f"zeleň {counts['forest_age']}, podklad map.png)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows cp1250 vs Unicode (Sez. 74)
    except Exception:
        pass
    main(sys.argv[1] if len(sys.argv) > 1 else "1088447")
