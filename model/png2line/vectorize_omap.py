"""vectorize_omap.py — Png2Line krok 1 end-to-end: sken → segmentace → vektorizace → .omap (Sez. 132).

Navazuje na eval_real.py (to měří RASTROVOU segmentaci, strict IoU 0,409 / F1 0,773 po conf_thr, Sez. 131).
Tady přidáváme sdílený „.omap assembly" krok (IDEAS): predikovanou masku watercourse zvektorizujeme
(`model/vectorize.py`: skeletonize → graf → RDP) na polyline, převedeme sken px → paper µm (inverze
georef `scan_px_to_paper`) a zapíšeme `.omap` (klon georef kartografovy mapy + liniové objekty 304).

Dvojí výstup:
  (1) MĚŘENÍ ztráty vektorizace — vektor rasterizujeme ZPĚT na masku a změříme stejnou metrikou jako
      eval_real (strict IoU + relaxed completeness/correctness vs GT). Kolik strukturální segmentace
      utopí skeletonize+RDP? (čistá vektorizace → ztráta ~0; velká ztráta → algoritmus komolí tvar).
  (2) PRODUKT — `.omap` k otevření v OOM (vizuál overlay s kartografovou mapou; oko = arbitr, Sez. 120).

Reuse z eval_real (DRY): predict_scan / parse_carto_lines / rasterize_line_Y / _map_area_mask / _disk /
BUFFER_PX / TARGET_MPP. Georef inverze ze SSoT png2area (vedle paper_to_scan_px). Vektorizace = model/vectorize.
"""
import sys
import re
import importlib.util
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation

Image.MAX_IMAGE_PIXELS = None
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "model" / "png2line"))
sys.path.insert(0, str(_REPO / "generator"))
sys.path.insert(0, str(_REPO / "connectors"))
sys.path.insert(0, str(_REPO / "model"))


def _import_path(name, path):
    """Načte modul z explicitní cesty (obchází kolizi jmen eval_real.py napříč png2{area,point,line})."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Png2Line eval_real = SSoT predikce + parseru + metriky (reuse, neduplikovat)
_line_eval = _import_path("png2line_eval_real", _REPO / "model" / "png2line" / "eval_real.py")
predict_scan = _line_eval.predict_scan
parse_carto_lines = _line_eval.parse_carto_lines
rasterize_line_Y = _line_eval.rasterize_line_Y
_map_area_mask = _line_eval._map_area_mask
_disk = _line_eval._disk
BUFFER_PX = _line_eval.BUFFER_PX
TARGET_MPP = _line_eval.TARGET_MPP
paper_to_scan_px = _line_eval.paper_to_scan_px
# georef inverze ze SSoT png2area (sken px → paper µm)
scan_px_to_paper = _line_eval._area_eval.scan_px_to_paper

from vectorize import mask_to_polylines, rasterize_polylines               # noqa: E402
from north_grid import filter_north_grid                                   # noqa: E402
from omap_raster import LINE_CLASSES, GT_LINE_WIDTH_PX                      # noqa: E402
from omap_export import TEMPLATE_PATH, _parse_symbol_ids                   # noqa: E402

_OUT = _REPO / "temp"
_OUT.mkdir(parents=True, exist_ok=True)
RDP_EPS_PX = 2.0                              # tolerance RDP [px] na kanonickém měřítku (≈ 2,7 m terénu @ 1,33 mpp)


def build_omap(polylines_paper, carto_omap_path, out_path, code):
    """Zapiš .omap s vektorizovanými liniemi. Georef se KLONUJE z kartografovy mapy (paper µm jsou
    počítané vůči její georef → musí sedět), symboly z čistého template_classic.omap. String-based
    jako omap_export (žádné flagy k ochraně, tvoříme nový soubor; konzistentní s konvencí projektu)."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    carto = Path(carto_omap_path).read_text(encoding="utf-8")
    geo = re.search(r"<georeferencing\b.*?</georeferencing>", carto, re.S)
    if geo is None:
        raise ValueError(f"{carto_omap_path}: chybí <georeferencing> — bez něj .omap nelícuje (no silent fallback)")
    template = re.sub(r"<georeferencing\b.*?</georeferencing>", lambda _: geo.group(0), template, count=1, flags=re.S)
    sym = _parse_symbol_ids(template)
    if code not in sym:
        raise ValueError(f"template nemá symbol kódu {code} — nelze zapsat watercourse")
    objs = []
    for poly in polylines_paper:
        if len(poly) < 2:
            continue
        coord_str = ";".join(f"{round(x)} {round(y)}" for x, y in poly) + ";"
        objs.append(f'<object type="1" symbol="{sym[code]}">'
                    f'<coords count="{len(poly)}">{coord_str}</coords></object>')
    body = "".join(objs)
    template = re.sub(r'<objects count="0">\s*</objects>',
                      f'<objects count="{len(objs)}">{body}</objects>', template, count=1, flags=re.S)
    Path(out_path).write_text(template, encoding="utf-8")
    return len(objs)


def _metrics(pred_mask, gt_mask):
    """Strict pixel IoU + relaxed completeness/correctness/F1 (izomorf eval_real, Sez. 131)."""
    inter = int((gt_mask & pred_mask).sum())
    union = int((gt_mask | pred_mask).sum())
    iou = inter / union if union else 0.0
    se = _disk(BUFFER_PX)
    gt_d = binary_dilation(gt_mask, se)
    pr_d = binary_dilation(pred_mask, se)
    comp = int((gt_mask & pr_d).sum()) / int(gt_mask.sum()) if gt_mask.sum() else 0.0
    corr = int((pred_mask & gt_d).sum()) / int(pred_mask.sum()) if pred_mask.sum() else 0.0
    f1 = (2 * comp * corr / (comp + corr)) if (comp + corr) else 0.0
    return iou, comp, corr, f1


def main(name):
    omap = _REPO / "resources" / f"{name}.omap"
    pgw = _REPO / "resources" / f"{name}.pgw"
    png = _REPO / "resources" / f"{name}.png"
    src_mpp = (lambda v: (v[0]**2 + v[1]**2)**0.5)([float(x) for x in pgw.read_text().split()])
    f = src_mpp / TARGET_MPP

    full = Image.open(png).convert("RGB")
    W0, H0 = full.size
    W, H = max(32, round(W0 * f)), max(32, round(H0 * f))
    scan_img = full.resize((W, H), Image.BILINEAR)
    scan_arr = np.asarray(scan_img)

    lines = parse_carto_lines(omap)
    to_px = paper_to_scan_px(omap, pgw)
    Y = rasterize_line_Y(lines, to_px, f, W, H)
    pred = predict_scan(scan_arr)
    field = _map_area_mask(scan_arr)
    gt = (Y == 1) & field
    pr = (pred == 1) & field                              # raster baseline (po conf_thr)

    if gt.sum() == 0:
        print(f"{name}: GT watercourse prázdné — přeskakuji")
        return None

    # 1) vektorizace predikované masky → polyline (downscaled px)
    polylines_px = mask_to_polylines(pr, rdp_eps=RDP_EPS_PX, min_len_px=GT_LINE_WIDTH_PX)

    # 2) měření ztráty: rasterizuj vektor ZPĚT (stejná šířka jako GT) → vs GT vs raster baseline
    vec_mask = rasterize_polylines(polylines_px, (H, W), width=GT_LINE_WIDTH_PX) & field
    iou_b, comp_b, corr_b, f1_b = _metrics(pr, gt)        # raster baseline (Sez. 131)
    iou_v, comp_v, corr_v, f1_v = _metrics(vec_mask, gt)  # po vektorizaci

    # 3) .omap zápis: polyline downscaled px → FULL px (÷f) → paper µm (inverze georef)
    to_paper = scan_px_to_paper(omap, pgw)
    code = LINE_CLASSES[0].codes[0]                       # watercourse → "304" (primární kód třídy)
    polylines_paper = [[to_paper(x / f, y / f) for (x, y) in poly] for poly in polylines_px]
    polylines_paper, north_grid = filter_north_grid(polylines_paper)
    out_omap = _OUT / f"vecline_{name}.omap"
    n_obj = build_omap(polylines_paper, omap, out_omap, code)

    n_verts = sum(len(p) for p in polylines_px)
    print(f"{name}: {len(polylines_px)} polyline / {n_verts} vrcholů → {out_omap.name} ({n_obj} obj, kód {code})")
    if north_grid.removed_ids:
        print(
            f"    [NORTH GRID] odstraněno {len(north_grid.removed_ids)} poledníkových fragmentů "
            f"na {len(north_grid.grid_centers_um)} liniích "
            f"(úhel {north_grid.target_angle_deg:.1f}°, spacing {north_grid.spacing_median_um:.0f} µm)"
        )
    print(f"    [RASTER baseline] IoU {iou_b:.3f}  comp {comp_b:.3f}  corr {corr_b:.3f}  F1 {f1_b:.3f}")
    print(f"    [VEKTOR        ]  IoU {iou_v:.3f}  comp {comp_v:.3f}  corr {corr_v:.3f}  F1 {f1_v:.3f}")
    print(f"    ztráta vektorizace: ΔIoU {iou_v-iou_b:+.3f}  ΔF1 {f1_v-f1_b:+.3f}")

    # vizuál: vektor (modře) přes sken + GT (zeleně)
    vis = scan_img.convert("RGB").copy()
    va = np.asarray(vis).copy()
    va[gt] = (0, 200, 0)
    va[vec_mask] = (230, 40, 40)
    va[gt & vec_mask] = (240, 220, 0)
    Image.fromarray(va).save(_OUT / f"vecline_{name}_overlay.png")
    return {"iou_baseline": iou_b, "iou_vector": iou_v, "f1_baseline": f1_b, "f1_vector": f1_v,
            "n_polylines": len(polylines_px), "n_verts": n_verts}


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    targets = [sys.argv[1]] if len(sys.argv) > 1 else ["Velbloud", "Blatná", "Bedřichovka"]
    res = []
    for nm in targets:
        print("=" * 70)
        r = main(nm)
        if r:
            res.append((nm, r))
    if len(res) > 1:
        print("=" * 70)
        db = float(np.mean([r["iou_vector"] - r["iou_baseline"] for _, r in res]))
        df = float(np.mean([r["f1_vector"] - r["f1_baseline"] for _, r in res]))
        print(f"[SOUHRN] {len(res)} map  průměr ztráta vektorizace ΔIoU {db:+.3f}  ΔF1 {df:+.3f}")
