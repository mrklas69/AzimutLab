"""pairs.py — per-classId továrna párů [render, .omap] z reálné Livelox mapy (UC5, Sez. 83).

Reframe (Sez. 79): generator() = továrna párů pro reconstructor(). Tahle orchestrace spojí pro
JEDEN Livelox classId dvě části do JEDNÉ georeferencované .omap:
  - REAL část: tvrdé ČÚZK vrstvy (cesty/voda/budovy/skály/…) z generate_map() pro výsek mapy,
  - PREDICT část: plošnou vegetaci SEPAROVANOU z té reálné mapy (separate.separate_areas, Sez. 82/83).
Render rgb.png (čistý) i .omap (Y-cíl) vyrobí generate_map; degradér fáze II (Sez. 86) z rgb.png
vyrobí scan.png (= X v páru, „sken"). Y páru (Sez. 87) = area_labels.png: rasterizace plošných ISOM
symbolů z .omap (omap_raster) → label rastr pro reconstructor model Png2Area. Provenance real/predict
je v meta.json (A3, Sez. 83). Pár pro trénink = [scan.png (X), area_labels.png (Y)].

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
from separate import separate_areas  # noqa: E402
from generator import generate_map        # noqa: E402
from degrade import degrade_file          # noqa: E402
from omap_raster import rasterize_map_dir  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
_CORPUS = _REPO_ROOT / "resources" / "livelox"
_SJTSK_TO_WGS84 = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)


def _separate_to_sjtsk(cid_dir: pathlib.Path, quad: list, crop_bbox=None,
                       src_mpp: float | None = None) -> list:
    """gt_labels → separace plošných tříd → polygony v S-JTSK (image-px → _map_affine).

    Vrací [(poly [vnější,díra…] v S-JTSK, code:int)] — tvar, který generate_map čeká v
    `predict_areas_sjtsk`. `_map_affine(quad)` je 2×3 matice image-px (col,row) → S-JTSK (x,y).

    `crop_bbox` (xmin,ymin,xmax,ymax v S-JTSK; Sez. 84) ořízne gt na pixel-okno odpovídající výseku
    PŘED separací — nutné, protože separace husté vegetace je O(n² prstenců) a separovat celou obří
    mapu (43 km²) by trvalo desítky minut, zatímco generuje se jen výsek (max_km). None = plný gt.

    `src_mpp` (Sez. 85): rozlišení mapy [m/px] z meta → separace downscaluje gt na TARGET_MPP před
    vektorizací (31,6× zrychlení žroutu #1, věrnost zachována). Crop i downscale jsou komplementární:
    crop zmenší PLOCHU, downscale ROZLIŠENÍ — Branžež (rotovaná, 0,56 mpp) potřebuje obojí (Sez. 84)."""
    gt = np.asarray(Image.open(cid_dir / "gt_labels.png"))   # 0-4/255 (map_gt separace)
    rgb = np.asarray(Image.open(cid_dir / "map.png").convert("RGB"))  # sken (403 split žluté, Sez. 92)
    H, W = gt.shape
    A = _map_affine(quad, W, H)                              # (col,row) → S-JTSK
    c0 = r0 = 0
    if crop_bbox is not None:
        # inverz afinní (S-JTSK → col,row): 4 rohy crop bboxu → pixel-okno (clip na rozměr gt)
        M = np.vstack([A, [0.0, 0.0, 1.0]])                 # 3×3 homogenní
        Ainv = np.linalg.inv(M)[:2]                          # zpět 2×3
        xmin, ymin, xmax, ymax = crop_bbox
        corners = np.array([[xmin, xmin, xmax, xmax], [ymin, ymax, ymin, ymax], [1, 1, 1, 1]])
        cr = Ainv @ corners                                  # (2,4) col,row
        c0 = max(0, int(np.floor(cr[0].min()))); c1 = min(W, int(np.ceil(cr[0].max())))
        r0 = max(0, int(np.floor(cr[1].min()))); r1 = min(H, int(np.ceil(cr[1].max())))
        gt = gt[r0:r1, c0:c1]                                # ořez → menší rastr = méně prstenců
        rgb = rgb[r0:r1, c0:c1]                              # rgb ořez STEJNĚ jako gt (zarovnání 403 masky)

    polys = separate_areas(gt, rgb=rgb, src_mpp=src_mpp)     # downscale na TARGET_MPP (polygony zpět v image-px)
    out: list = []
    for code, polys_c in polys.items():                     # {ISOM kód: [polygony]}
        for poly in polys_c:                                # poly = [outer, díra…], prsten = (col,row)
            rings_sjtsk = []
            for ring in poly:
                pts = np.asarray(ring, dtype=float)          # (N,2) col,row v OŘÍZNUTÉM gridu
                pts[:, 0] += c0; pts[:, 1] += r0             # lokální px → globální px (offset okna)
                hom = np.vstack([pts.T, np.ones(len(pts))])  # (3,N) [col;row;1]
                xy = (A @ hom).T                             # (N,2) S-JTSK
                rings_sjtsk.append([(float(x), float(y)) for x, y in xy])
            out.append((rings_sjtsk, int(code)))
    return out


def build_pair(cid, out_dir: str | None = None, ortho: bool = False, max_km: float = 5.0,
               degrade: bool = True, labels: bool = True):
    """Vyrobí pár [sken scan.png (X), area_labels.png (Y)] pro Livelox classId: real ČÚZK + separace.

    Odvodí výsek z Livelox _georef_grid (centroid → lat/lon, rozměry obalu → w_km/h_km), separuje
    vegetaci z mapy do S-JTSK a předá ji generate_map jako `predict_areas_sjtsk` (jediný zdroj
    predikční zeleně). Vrací cestu k výstupní složce. `out_dir` None → `resources/livelox/<cid>/gen`.

    `degrade` (Sez. 86): po renderu degraduje rgb.png → scan.png (= X v páru, fáze II). Seed = cid →
    per-mapa reprodukovatelný sken. Čistý rgb.png zůstává (debug / Y-vizuál). False = jen čistý render.

    `labels` (Sez. 87): po renderu rasterizuje plošné ISOM symboly z .omap → area_labels.png (= Y v
    páru, reconstructor Png2Area). Odvozeno z .omap (NE z render masek) → pár self-konzistentní.

    `max_km` (Sez. 84): strop strany výseku okolo centroidu — render skal/objektů roste nadlineárně
    s plochou, obří mapy (max 106 km²) by tažily noční běh na víkend. Pro trénink rozhoduje rozmanitost
    lokalit a počet dlaždic, ne aby pár pokryl celou obří mapu → centrální výsek 5×5 km stačí. Separace
    je v S-JTSK → na menší canvas se sama ořízne (_poly_to_grid_px). None/0 = bez stropu (plný obal)."""
    cid = str(cid)
    cid_dir = _CORPUS / cid
    meta = json.loads((cid_dir / "meta.json").read_text(encoding="utf-8"))
    g = _georef_grid(meta)
    xmin, ymin, xmax, ymax = g["xmin"], g["ymin"], g["xmax"], g["ymax"]
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    lon, lat = _SJTSK_TO_WGS84.transform(cx, cy)             # centroid obalu → WGS84
    w_km, h_km = (xmax - xmin) / 1000.0, (ymax - ymin) / 1000.0
    if max_km:                                               # zastropuj stranu (centroid držím)
        w_km, h_km = min(w_km, max_km), min(h_km, max_km)

    # crop bbox v S-JTSK okolo centroidu (= výsek, co generate_map vykreslí) → ořez gt před separací
    hw, hh = w_km * 500.0, h_km * 500.0                       # km/2 → m
    crop_bbox = (cx - hw, cy - hh, cx + hw, cy + hh)
    predict_sjtsk = _separate_to_sjtsk(cid_dir, g["quad"], crop_bbox,
                                       src_mpp=meta.get("effectiveMppX"))
    out = out_dir or str(cid_dir / "gen")
    print(f"{cid} \"{meta.get('name', '?')}\"  výsek {w_km:.2f}×{h_km:.2f} km @ "
          f"({lat:.5f}, {lon:.5f})  separace {len(predict_sjtsk)} ploch")
    res = generate_map(lat, lon, w_km, h_km,
                       predict_areas_sjtsk=predict_sjtsk, out_dir=out, ortho=ortho)
    if degrade:                                              # fáze II: čistý render → „sken" (X)
        degrade_file(pathlib.Path(out) / "rgb.png", seed=int(cid) & 0xFFFFFFFF)
    if labels:                                               # Y páru: plošné symboly z .omap → label rastr
        lab = rasterize_map_dir(pathlib.Path(out))
        Image.fromarray(lab, mode="L").save(pathlib.Path(out) / "area_labels.png")
    return res


def _cr_keep_cids() -> list:
    """ČR keep mapy = klíče _split.json (split.py drží 207 ČR keep classic, geo-split train/val/test).

    Zdroj párů (Sez. 84): split místo curate.kept_dirs('classic') (=216) řeší DVĚ věci najednou —
    vyřadí 9 cizích keep map (real ČÚZK vrstvy fungují jen pro ČR; cizí pár by neměl real část)
    I outlier 1109655 (georef bug, vyřazen už geosplitem → není ve split). Foundations-čistý zdroj."""
    sys.path.insert(0, str(_REPO_ROOT / "connectors"))
    from split import load_split        # noqa: E402 — sys.path skript
    return sorted(load_split().keys())


def build_pairs(cids=None, skip_existing: bool = True, ortho: bool = False,
                max_km: float = 5.0, degrade: bool = True, labels: bool = True) -> dict:
    """Hromadně vyrobí páry-zdroje [render, .omap] pro seznam Livelox classId (UC5 trénink, Sez. 84).

    Volá build_pair na každý cid. Vlastnosti dávky (mirror livelox.build_pairs):
      - resumovatelné: skip_existing přeskočí mapy s hotovým gen/rgb.png (re-běh po přerušení
        nestahuje ČÚZK znovu — fetch je drahý, ~204× = hodiny),
      - tolerantní: chyba jedné mapy (síť/georef/separace) dávku NEzastaví, jen se zaznamená.
    cids None → ČR keep ze split (_cr_keep_cids). Vrací souhrn {ok, skipped, failed:[(cid,err)]}.
    """
    cids = list(cids) if cids is not None else _cr_keep_cids()
    summary = {"ok": [], "skipped": [], "failed": []}
    total = len(cids)
    for i, cid in enumerate(cids, 1):
        cid = str(cid)
        # finální artefakt dávky = POSLEDNÍ zapsaný krok (crash mezi kroky → re-běh dokončí):
        # labels (area_labels.png, Y) > degrade (scan.png, X) > čistý render (rgb.png)
        final = "area_labels.png" if labels else ("scan.png" if degrade else "rgb.png")
        gen_out = _CORPUS / cid / "gen" / final
        if skip_existing and gen_out.exists():
            summary["skipped"].append(cid)
            print(f"[{i}/{total}] {cid} SKIP (gen/{final} hotovo)")
            continue
        try:
            build_pair(cid, ortho=ortho, max_km=max_km, degrade=degrade, labels=labels)
            summary["ok"].append(cid)
            print(f"[{i}/{total}] {cid} OK  (ok={len(summary['ok'])} "
                  f"skip={len(summary['skipped'])} fail={len(summary['failed'])})")
        except Exception as e:                       # tolerantní: 1 mapa nepoloží dávku
            summary["failed"].append((cid, f"{type(e).__name__}: {e}"))
            print(f"[{i}/{total}] {cid} FAIL: {type(e).__name__}: {e}")
    print(f"\nhotovo: ok {len(summary['ok'])}, skip {len(summary['skipped'])}, "
          f"fail {len(summary['failed'])}")
    if summary["failed"]:
        print("selhaly:", ", ".join(c for c, _ in summary["failed"]))
    return summary


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows cp1250 vs Unicode (Sez. 74)
    except Exception:
        pass
    arg = sys.argv[1] if len(sys.argv) > 1 else "1088447"
    if arg == "batch":
        # `batch` = celý ČR keep set; `batch <N>` = jen prvních N (sanity vzorek před nočním během)
        cids = _cr_keep_cids()
        if len(sys.argv) > 2:
            cids = cids[: int(sys.argv[2])]
        build_pairs(cids)
    else:
        path = build_pair(arg)
        print(f"pár → {path}")
