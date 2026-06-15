"""
Reálný benchmark Png2Line krok 1 — doménový gap syntetika → kartografův sken (Sez. 131).

Měří `line_model/unet_best.pt` na REÁLNÉM skenu kartografovy mapy (NE na vlastní syntetice):
  X = sken (`resources/<name>.png` + `.pgw`), downscalovaný na trénovací mpp 1,33 (= dlaždice).
  GT = LINE objekty (type=2) vodních toků 304/305 z KARTOGRAFOVY `.omap` (ISOM 2000 → crosswalk `.crt`
       → 2017-2 → třída "watercourse"), nakreslené NAFOUKLE (GT_LINE_WIDTH_PX) stejně jako trénink.

Dvojice metrik (izomorfní s png2area eval_real strict+soft, Sez. 120):
  (1) PŘÍSNÉ pixel IoU watercourse — stejná optika jako train.evaluate, srovnatelné se syntetikou (0,55).
      U ~5px linie je IoU krutě citlivá na 1px posun hranice (Sez. 130) → reálný georef posun ji srazí.
  (2) RELAXOVANÉ completeness/correctness — standard pro extrakci liniových prvků (Wiedemann 1998):
      completeness (recall) = podíl GT pixelů do BUFFER_PX od predikce; correctness (precision) = podíl
      pred pixelů do BUFFER_PX od GT. Robustní vůči ~1px georef/šířkovému nesouladu → poctivá odpověď
      „trasuje model vodní tok?" na úrovni linie, ne pixelu.
+ vizuál overlay GT (zeleně) × pred (červeně) na sken → temp/ (georef verify, oko = source).

Georef: reuse `paper_to_scan_px` z model/png2area/eval_real.py (ověřená cesta, rot_sign=−1, Sez. 120) —
jediný zdroj pravdy pro paper→sken transform (DRY). Maska mapového pole (`_detect_map_area`, Sez. 73)
vyřízne halucinace na bílém okolí mimo mapu (GT je jen uvnitř pole) — izomorfní s png2point eval_real.

Měřeno na Velbloud + Blatná + Bedřichovka (georef ověřené Sez. 120). Slovanka odložena (UTM33).
"""
import sys
import importlib.util
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET
from scipy.ndimage import binary_dilation

Image.MAX_IMAGE_PIXELS = None                          # reálné skeny jsou velké (Bedř 114 Mpx)
_REPO = Path(__file__).resolve().parents[2]            # model/png2line/eval_real.py → kořen repa
sys.path.insert(0, str(_REPO / "model" / "png2line"))
sys.path.insert(0, str(_REPO / "generator"))
sys.path.insert(0, str(_REPO / "connectors"))
sys.path.insert(0, str(_REPO / "model"))


def _import_path(name, path):
    """Načte modul z explicitní cesty pod daným jménem (obchází kolizi jmen eval_real.py
    v png2area/png2point/png2line — přímé spuštění skriptu by `import eval_real` namířilo na sebe)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# DRY: paper→sken transform z Png2Area eval_real (SSoT ověřené georef, rot_sign=−1, Sez. 120)
_area_eval = _import_path("png2area_eval_real", _REPO / "model" / "png2area" / "eval_real.py")
paper_to_scan_px = _area_eval.paper_to_scan_px
from omap_raster import (                                                       # noqa: E402
    N_LINE, LINE_LABEL_NAME, LINE_CODE_TO_LABEL, LINE_CONF_THR, GT_LINE_WIDTH_PX, colorize_lines)
from compare_isom import _load_crosswalk, _resolve_targets, detect_version      # noqa: E402
from map_gt import _detect_map_area                                            # noqa: E402
from mpp import CANONICAL_MPP                                                   # noqa: E402

TARGET_MPP = CANONICAL_MPP                             # = měřítko dlaždice (SSoT mpp.py, Sez. 126); sken se naň downscaluje
_OUT = _REPO / "temp"                                  # scratch vizuál výstupy (gitignored)
_OUT.mkdir(parents=True, exist_ok=True)                # fresh clone / úklid temp/ → bez FileNotFoundError

# Toleranční buffer relaxované metriky [px]. GT i predikce jsou ~GT_LINE_WIDTH_PX (3 px) široké → ~1px
# georef posun strict IoU srazí, ač linie trasuje správně. Buffer 2 px = poctivá tolerance „je predikce
# u GT linie" bez toho, aby spolkla hrubé chyby. Laditelná known-limitation konstanta (jako TOL_PX u bodů).
BUFFER_PX = 2


def _local(tag):
    return tag.split("}")[-1]


def _disk(r: int) -> np.ndarray:
    """Kruhový strukturní element o poloměru r (pro binary_dilation buffer relaxované metriky)."""
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    return (xx * xx + yy * yy) <= r * r


def parse_carto_lines(omap_path):
    """[(points_µm, label)] z kartografovy .omap — LINE objekty (type=2) ve scope LINE_CLASSES přes crosswalk.

    label = LINE_CODE_TO_LABEL[cíl] (dnes watercourse 304/305 → 1). Crosswalk 2000→2017 (bez něj nesmysl,
    lekce Sez. 94): kartografovy mapy bývají ISOM 2000, scope se řídí cílovými 2017-2 kódy v LINE_CODE_TO_LABEL.
    Polyline čteme jako vrcholy (flagy close/bezier ignorujeme — bezier control body bereme jako vrcholy,
    aproximace polygonem jako u rasterize_lines)."""
    root = ET.parse(omap_path).getroot()
    ver = detect_version(str(omap_path))
    cw, v2000, v2017 = _load_crosswalk()
    id2code, id2type = {}, {}
    for el in root.iter():
        if _local(el.tag) == "symbol":
            id2code[el.get("id")] = el.get("code", "")
            id2type[el.get("id")] = int(el.get("type", "0"))   # 1=point 2=line 4/8=area
    out = []
    for el in root.iter():
        if _local(el.tag) != "object":
            continue
        sid = el.get("symbol")
        if sid is None or id2type.get(sid, 0) != 2:            # jen liniové (type=2)
            continue
        try:
            ci = int(float(id2code.get(sid, "")))
        except ValueError:
            continue
        targets = _resolve_targets(ci, ver, cw, v2000, v2017)
        if not targets:
            continue
        hit = {str(t) for t in targets} & set(LINE_CODE_TO_LABEL)   # cílová třída ve scope 304/305?
        if not hit:
            continue
        lab = LINE_CODE_TO_LABEL[sorted(hit)[0]]
        c = next((x for x in el if _local(x.tag) == "coords"), None)
        if c is None or not c.text:
            continue
        pts = []
        for tok in c.text.strip().split(";"):                 # "x y [flag]; ..." → vrcholy polyline
            nums = tok.split()
            if len(nums) >= 2:
                try:
                    pts.append((float(nums[0]), float(nums[1])))
                except ValueError:
                    continue
        if len(pts) >= 2:
            out.append((pts, lab))
    return out


def rasterize_line_Y(lines, to_px, f, W, H):
    """LINE objekty → Y label rastr (H,W) uint8, kreslené NAFOUKLE (GT_LINE_WIDTH_PX) jako trénink.

    Izomorfní s omap_raster.rasterize_lines, jen souřadnice jdou přes ověřený paper_to_scan_px (× f na
    downscaled grid), ne přes meta-based _paper_to_px. Kulaté spoje v lomech (kroužek na vrcholech)."""
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    r = GT_LINE_WIDTH_PX / 2.0
    for pts, lab in sorted(lines, key=lambda o: o[1]):        # z-order: nižší label dřív (krok 1 = jedna třída)
        px = [(to_px(x, y)[0] * f, to_px(x, y)[1] * f) for x, y in pts]
        if len(px) >= 2:
            d.line(px, fill=lab, width=GT_LINE_WIDTH_PX)
        for cx, cy in px:                                     # kulaté spoje (PIL line nemá round join)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=lab)
    return np.asarray(img, dtype=np.uint8)


def predict_scan(arr):
    """Pustí line_model/unet_best.pt na downscalovaný sken (arr H,W,3, tiled 512/384) → pred label (H,W).

    Izomorfní s png2area.eval_real.predict_scan (softmax akumulace přes překryvy → argmax), jen N_LINE
    tříd a line_model váhy. NAVÍC (Sez. 131): per-class softmax práh LINE_CONF_THR — pixel přiřazený
    liniové třídě, jehož konfidence < conf_thr, se sráží na pozadí (ořez FP, model fíruje na tenkou linii
    obecně; sweep ukázal +63 % strict IoU). Holý argmax = conf_thr 0,5; watercourse má 0,95."""
    import segmentation_models_pytorch as smp
    MEAN = np.array([0.485, 0.456, 0.406], np.float32)
    STD = np.array([0.229, 0.224, 0.225], np.float32)
    H, W = arr.shape[:2]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = smp.Unet("resnet34", encoder_weights=None, in_channels=3, classes=N_LINE).to(dev)
    model.load_state_dict(torch.load(_REPO / "resources" / "line_model" / "unet_best.pt",
                                     weights_only=False, map_location=dev)["model"])
    model.eval()
    T, S = 512, 384
    Hp, Wp = max(H, T), max(W, T)
    pad = np.zeros((Hp, Wp, 3), np.uint8); pad[:H, :W] = arr
    acc = np.zeros((N_LINE, Hp, Wp), np.float32); cnt = np.zeros((Hp, Wp), np.float32)
    for y in sorted(set(list(range(0, Hp - T + 1, S)) + [Hp - T])):
        for x in sorted(set(list(range(0, Wp - T + 1, S)) + [Wp - T])):
            p = (pad[y:y+T, x:x+T].astype(np.float32) / 255.0 - MEAN) / STD
            pt = torch.from_numpy(p.transpose(2, 0, 1)).unsqueeze(0).to(dev)
            with torch.no_grad(), torch.autocast(dev, dtype=torch.bfloat16, enabled=(dev == "cuda")):
                acc[:, y:y+T, x:x+T] += model(pt).softmax(1)[0].float().cpu().numpy()
            cnt[y:y+T, x:x+T] += 1
    prob = (acc / cnt)[:, :H, :W]                              # (N_LINE,H,W) průměr přes překryvy
    pred = prob.argmax(0).astype(np.uint8)
    for lab in range(1, N_LINE):                              # foreground třídy: demote pod conf_thr na pozadí
        below = (pred == lab) & (prob[lab] <= LINE_CONF_THR[lab])
        pred[below] = 0
    return pred


def _map_area_mask(scan_arr):
    """Bool maska mapového pole (True=mapa) — reuse _detect_map_area (Sez. 73). Vyřadí pred linie na bílém
    okolí mimo mapu (FP nefér: kartografovo GT je jen uvnitř pole). Izomorfní s png2point eval_real."""
    mx = scan_arr.max(2).astype(np.int16)
    mn = scan_arr.min(2).astype(np.int16)
    colored = ((mx - mn) > 25) | (mx < 200)               # saturovaný NEBO tmavý = mapová kresba
    return _detect_map_area(colored)


def _overlay(scan_img, gt_mask, pred_mask):
    """Vizuál georef verify: GT linie (zeleně) + predikce (červeně) přes sken. Překryv (oba) = žlutě."""
    img = scan_img.convert("RGB").copy()
    arr = np.asarray(img).copy()
    arr[gt_mask] = (0, 200, 0)                            # GT zeleně
    arr[pred_mask] = (230, 40, 40)                        # predikce červeně
    arr[gt_mask & pred_mask] = (240, 220, 0)             # překryv (TP) žlutě
    return Image.fromarray(arr)


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
    print(f"{name}: {len(lines)} liniových objektů watercourse; ver {detect_version(str(omap))}; "
          f"sken {W0}x{H0}→{W}x{H}")

    to_px = paper_to_scan_px(omap, pgw)                  # rot_sign=−1, flip_y=True (default, ověřeno Sez. 120)
    Y = rasterize_line_Y(lines, to_px, f, W, H)
    pred = predict_scan(scan_arr)

    field = _map_area_mask(scan_arr)
    gt = (Y == 1) & field                                # watercourse GT uvnitř mapového pole
    pr = (pred == 1) & field                             # predikce watercourse uvnitř pole
    dropped = int(((pred == 1) & ~field).sum())          # halucinace mimo pole (info)

    if gt.sum() == 0:
        print(f"    watercourse: GT prázdné (0 px) — mapa nemá toky 304/305 ve scope, přeskakuji metriku")
        _overlay(scan_img, gt, pr).save(_OUT / f"realline_{name}_overlay.png")
        return None

    # (1) PŘÍSNÉ pixel IoU (stejná optika jako train.evaluate) — srovnatelné se syntetikou
    inter = int((gt & pr).sum())
    union = int((gt | pr).sum())
    iou = inter / union if union else 0.0

    # (2) RELAXOVANÉ completeness/correctness (buffer BUFFER_PX, Wiedemann 1998)
    se = _disk(BUFFER_PX)
    gt_d = binary_dilation(gt, se)
    pr_d = binary_dilation(pr, se)
    completeness = int((gt & pr_d).sum()) / int(gt.sum())            # recall: GT pokryté predikcí
    correctness = (int((pr & gt_d).sum()) / int(pr.sum())) if pr.sum() else 0.0   # precision: pred u GT
    rf1 = (2 * completeness * correctness / (completeness + correctness)
           if (completeness + correctness) else 0.0)

    print(f"    watercourse: GT={int(gt.sum()):>7} px  pred={int(pr.sum()):>7} px (−{dropped} mimo pole)")
    print(f"    [PŘÍSNÉ]    pixel IoU {iou:.3f}  (vs syntetika 0,55)")
    print(f"    [RELAXOVANÉ buffer {BUFFER_PX}px]  completeness {completeness:.3f}  "
          f"correctness {correctness:.3f}  F1 {rf1:.3f}")

    colorize_lines(Y).save(_OUT / f"realline_{name}_Y.png")
    colorize_lines(pred).save(_OUT / f"realline_{name}_pred.png")
    _overlay(scan_img, gt, pr).save(_OUT / f"realline_{name}_overlay.png")
    return {"iou": iou, "completeness": completeness, "correctness": correctness, "f1": rf1}


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # diakritický argv padá v harness (gotcha Sez. 119) → názvy hardcoded, bez argv
    targets = [sys.argv[1]] if len(sys.argv) > 1 else ["Velbloud", "Blatná", "Bedřichovka"]
    res = []
    for nm in targets:
        print("=" * 70)
        r = main(nm)
        if r:
            res.append((nm, r))
    if len(res) > 1:
        print("=" * 70)
        mi = float(np.mean([r["iou"] for _, r in res]))
        mf = float(np.mean([r["f1"] for _, r in res]))
        print(f"[SOUHRN] {len(res)} map  průměr pixel IoU {mi:.3f}  relaxované F1 {mf:.3f}")
