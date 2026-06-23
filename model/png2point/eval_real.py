"""
A1.b reálný benchmark Png2Point — doménový gap injekce → kartografův sken (supervisor audit A1, část b).

Měří `point_model/unet_best.pt` na REÁLNÉM skenu (NE na injekci do čistého point_base):
  X = sken (`resources/<name>.png` + `.pgw`), downscalovaný na trénovací mpp 1,33 (= dlaždice).
  GT = POINT objekty (type=1) 204/210 z KARTOGRAFOVY `.omap` (ISOM 2000 → crosswalk `.crt` → 2017-2),
       jejich poloha převedená paper µm → sken px → ×f na downscaled grid.

Dvojice metrik (stejná optika jako Png2Area eval_real, Sez. 120): per-třída peak F1 (P/R) na realitě
proti syntetické mF1 0,897 (Sez. 106). Matching = greedy peak↔GT v toleranci TOL_PX (jako train.evaluate).
+ vizuál overlay GT (zeleně) × pred peaky (červeně 204 / modře 210) na sken → temp/ (georef verify, oko=source).

Georef: reuse `paper_to_scan_px` z model/png2area/eval_real.py (ověřená cesta, rot_sign=−1, Sez. 120) —
jediný zdroj pravdy pro paper→sken transform (DRY). Velbloud georef nebyl dosud ověřen (Sez. 111) →
vizuální overlay je verify PŘED uvěřením číslu.

Měřeno na Velbloud (skalnatá, 680×204/603×210) + Blatná + Bedřichovka (georef ověřené Sez. 120).
Slovanka odložena (UTM33 = jiný transformer než Křovák).
"""
import sys
import importlib.util
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET

Image.MAX_IMAGE_PIXELS = None
_REPO = Path(__file__).resolve().parents[2]            # model/png2point/eval_real.py → kořen repa
sys.path.insert(0, str(_REPO / "model" / "png2point"))
sys.path.insert(0, str(_REPO / "generator"))
sys.path.insert(0, str(_REPO / "connectors"))


def _import_path(name, path):
    """Načte modul z explicitní cesty pod daným jménem (obchází kolizi jmen eval_real.py
    v png2area i png2point — přímé spuštění skriptu by `import eval_real` namířilo na sebe)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# DRY: paper→sken transform z Png2Area eval_real (SSoT ověřené georef, rot_sign=−1, Sez. 120)
_area_eval = _import_path("png2area_eval_real", _REPO / "model" / "png2area" / "eval_real.py")
paper_to_scan_px = _area_eval.paper_to_scan_px
from compare_isom import _load_crosswalk, _resolve_targets, detect_version      # noqa: E402
from inject import POINT_CLASSES, N_POINT, CODE_TO_IDX                          # noqa: E402
from map_gt import _detect_map_area                                            # noqa: E402
from mpp import CANONICAL_MPP
from norm import IMAGENET_MEAN, IMAGENET_STD                                    # noqa: E402  SSoT (audit D4, Sez. 158)                                                   # noqa: E402  (inject už přidal model/ na path)

TARGET_MPP = CANONICAL_MPP                             # = měřítko dlaždice (SSoT mpp.py, Sez. 126); sken se naň downscaluje
_OUT = _REPO / "temp"                                  # scratch vizuál výstupy (gitignored)
_OUT.mkdir(parents=True, exist_ok=True)                # fresh clone / úklid temp/ → bez FileNotFoundError (audit CODE-D2)
_CODES = [pc.code for pc in POINT_CLASSES]

# --- detekční konstanty + helpery (SSoT = model/png2point/train.py; sem zkopírováno ať netáhneme
#     matplotlib/dataset import jen kvůli třem čistým funkcím — izomorfní s png2area/eval_real) ---
TOL_PX = 3           # tolerance matchingu peak↔GT (px) — shodně s train.TOL_PX
# Práh detekce = PER TŘÍDA z registru (POINT_CLASSES[c].peak_thr, Sez. 129) — SSoT shodné s train.evaluate.


def _local(tag):
    return tag.split("}")[-1]


# SSoT: model/peaks.py (audit D4, Sez. 158) — sdíleno s train.py (čisté torch/numpy, bez matplotlib importu).
from peaks import nms as _nms, peaks_xy as _peaks_xy, match_counts as _match_counts  # noqa: E402


def parse_carto_points(omap_path):
    """[(x_µm, y_µm, idx)] z kartografovy .omap — POINT objekty (type=1) ve scope POINT_CLASSES přes crosswalk.

    idx = kanál heatmapy (CODE_TO_IDX, dnes 204→0, 210→1, 417→2, 419→3, 531→4). Crosswalk 2000→2017 (bez něj
    nesmysl, Sez. 94): skalnaté ISOM 2000 mapy mají boulder=206, stony=210; 2017-2 přečíslovalo boulder→204.
    POZOR vegetace (Sez. 128): ISOM 2000 417 → 2017-2 419, 2000 419 → 2017-2 418 (záměna v .crt) — crosswalk
    `_resolve_targets` ji vyřeší automaticky, scope se řídí cílovými 2017-2 kódy v CODE_TO_IDX."""
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
        if sid is None or id2type.get(sid, 0) != 1:            # jen bodové (type=1)
            continue
        try:
            ci = int(float(id2code.get(sid, "")))
        except ValueError:
            continue
        targets = _resolve_targets(ci, ver, cw, v2000, v2017)
        if not targets:
            continue
        hit = {str(t) for t in targets} & set(CODE_TO_IDX)     # cílová třída ve scope 204/210?
        if not hit:
            continue
        idx = CODE_TO_IDX[sorted(hit)[0]]                      # kanál heatmapy
        c = next((x for x in el if _local(x.tag) == "coords"), None)
        if c is None or not c.text:
            continue
        toks = c.text.replace(";", " ").split()                # "x y [flag]; ..." → první bod
        if len(toks) >= 2:
            out.append((float(toks[0]), float(toks[1]), idx))
    return out


def _map_area_mask(scan_arr):
    """Bool maska mapového pole (True=mapa). Hrubý mappix = barevné/tmavé px (saturace nebo tmavá
    kresba) → reuse _detect_map_area (Sez. 73, dlaždice+největší komponenta+fill_holes scelí bílý
    les uvnitř, odřízne bílé okolí). Vyřadí 210/204 halucinace na bílém okolí mimo mapu (FP nefér:
    kartografovo GT je jen uvnitř pole)."""
    mx = scan_arr.max(2).astype(np.int16)
    mn = scan_arr.min(2).astype(np.int16)
    colored = ((mx - mn) > 25) | (mx < 200)               # saturovaný NEBO tmavý = mapová kresba
    return _detect_map_area(colored)


def _load_model(dev):
    """U-Net ResNet34, N_POINT heatmapa kanálů. Default váhy = kanonický point_model/unet_best.pt;
    env POINT_CKPT přepíše cestu (eval běhu z runs/<id>/best.pt PŘED promote — multiseed bez přepisu
    kanonického, audit C1: eval_real na novém scope nemusí čekat na promote)."""
    import os
    import segmentation_models_pytorch as smp
    model = smp.Unet("resnet34", encoder_weights=None, in_channels=3, classes=N_POINT).to(dev)
    ckpt_path = os.environ.get("POINT_CKPT") or (_REPO / "resources" / "point_model" / "unet_best.pt")
    ckpt = torch.load(ckpt_path, weights_only=False, map_location=dev)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model


def predict_peaks(arr, model, dev, thr=None):
    """Pustí model na downscalovaný sken (arr H,W,3, tiled 512/384), akumuluje sigmoid heatmapu přes
    překryvy → NMS peak + práh → list[(K,2) xy] per třída. (Detekce jako train.evaluate, jen na celém skenu.)

    thr=None → per-třída práh z registru (POINT_CLASSES[c].peak_thr, Sez. 129); float → globální override."""
    MEAN, STD = IMAGENET_MEAN, IMAGENET_STD              # SSoT model/norm.py (audit D4, Sez. 158)
    H, W = arr.shape[:2]
    T, S = 512, 384
    Hp, Wp = max(H, T), max(W, T)
    pad = np.zeros((Hp, Wp, 3), np.uint8); pad[:H, :W] = arr
    acc = np.zeros((N_POINT, Hp, Wp), np.float32); cnt = np.zeros((Hp, Wp), np.float32)
    for y in sorted(set(list(range(0, Hp - T + 1, S)) + [Hp - T])):
        for x in sorted(set(list(range(0, Wp - T + 1, S)) + [Wp - T])):
            p = (pad[y:y+T, x:x+T].astype(np.float32) / 255.0 - MEAN) / STD
            pt = torch.from_numpy(p.transpose(2, 0, 1)).unsqueeze(0).to(dev)
            with torch.no_grad(), torch.autocast(dev, dtype=torch.bfloat16, enabled=(dev == "cuda")):
                acc[:, y:y+T, x:x+T] += torch.sigmoid(model(pt))[0].float().cpu().numpy()
            cnt[y:y+T, x:x+T] += 1
    heat = (acc / cnt)[:, :H, :W]                              # průměr přes překryvy, ořež padding
    # NMS na celé heatmapě (na dev pro rychlost) → peaky per třída
    ht = torch.from_numpy(heat).unsqueeze(0).to(dev)           # (1,N_POINT,H,W)
    nms = _nms(ht)[0].cpu().numpy()
    thrs = [pc.peak_thr for pc in POINT_CLASSES] if thr is None else [thr] * N_POINT
    return [_peaks_xy(nms[c], thrs[c]) for c in range(N_POINT)]


def _overlay(scan_img, gt_pts, pred_peaks, f, to_px):
    """Vizuál georef verify: GT body (zeleně) + pred peaky per třída na sken.
    Pred barvy: 204 červeně / 210 modře / 417 azurově / 419 fialově / 531 oranžově / 525 zlatě / 527 magenta
    (kontrolní, nesouvisí s ISOM)."""
    img = scan_img.convert("RGB").copy()
    d = ImageDraw.Draw(img)
    for x, y, idx in gt_pts:                                   # GT zeleně (kroužek)
        cx, cy = to_px(x, y)
        cx, cy = cx * f, cy * f
        d.ellipse([cx-4, cy-4, cx+4, cy+4], outline=(0, 200, 0), width=1)
    # barvy per kanál (drží i pro N_POINT>2; padding zelenou, kdyby přibyla další třída)
    pcol = [(230, 40, 40), (40, 90, 230), (20, 200, 200), (200, 40, 200), (255, 140, 0), (240, 200, 0), (255, 0, 255)]
    for c in range(N_POINT):
        col = pcol[c] if c < len(pcol) else (0, 200, 0)
        for px, py in pred_peaks[c]:
            d.point([(px, py)], fill=col)
    return img


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

    gt_raw = parse_carto_points(omap)
    print(f"{name}: {len(gt_raw)} bodů {_CODES}; ver {detect_version(str(omap))}; sken {W0}x{H0}→{W}x{H}")

    to_px = paper_to_scan_px(omap, pgw)                        # rot_sign=−1, flip_y=True (default, ověřeno)
    # GT body do downscaled grid px (×f) + filtr na plátno
    gt_xy = [[] for _ in range(N_POINT)]
    for x, y, idx in gt_raw:
        cx, cy = to_px(x, y)
        cx, cy = cx * f, cy * f
        if 0 <= cx < W and 0 <= cy < H:
            gt_xy[idx].append((cx, cy))
    gt_xy = [np.array(g, np.float32) if g else np.zeros((0, 2), np.float32) for g in gt_xy]

    scan_arr = np.asarray(scan_img)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = _load_model(dev)
    pred = predict_peaks(scan_arr, model, dev)

    # maska mapového pole — vyřadí pred peaky na bílém okolí (halucinace mimo mapu, GT je jen uvnitř)
    area = _map_area_mask(scan_arr)
    pred_in = []
    dropped = []
    for c in range(N_POINT):
        if len(pred[c]):
            keep = area[pred[c][:, 1].astype(int), pred[c][:, 0].astype(int)]
            pred_in.append(pred[c][keep])
            dropped.append(int((~keep).sum()))
        else:
            pred_in.append(pred[c]); dropped.append(0)

    # per-třída F1 (na predikcích uvnitř mapového pole)
    f1s = []
    for c in range(N_POINT):
        tp, fp, fn = _match_counts(pred_in[c], gt_xy[c], TOL_PX)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1s.append(f1)
        print(f"    {_CODES[c]:>4}: GT={len(gt_xy[c]):>4} pred={len(pred_in[c]):>5}"
              f"(−{dropped[c]} mimo pole)  TP={tp:>4} FP={fp:>5} FN={fn:>4}  "
              f"P={prec:.3f} R={rec:.3f} F1={f1:.3f}")
    mf1 = float(np.mean(f1s))
    # POZN. (Sez. 125): syntetická referenční mF1 je NESTABILNÍ (0,15–0,90 dle seedu) — „0,897" (Sez. 106)
    # byl nereprodukovaný outlier. Hardcoded srovnání odstraněno; aktuální syntetické číslo viz train.py TEST.
    print(f"  [REALITA] mean F1 {mf1:.3f}")
    pred = pred_in                                            # overlay ukáže jen in-field peaky

    _overlay(scan_img, gt_raw, pred, f, to_px).save(_OUT / f"realpt_{name}_overlay.png")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # diakritický argv padá v harness (gotcha Sez. 119) → názvy hardcoded, bez argv
    targets = [sys.argv[1]] if len(sys.argv) > 1 else ["Velbloud", "Blatná", "Bedřichovka"]
    for nm in targets:
        print("=" * 70)
        main(nm)
