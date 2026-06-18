"""
A1 reálný benchmark Png2Area — doménový gap syntetika → kartografův sken (Fable5 audit A1).

Měří `unet_best.pt` na REÁLNÉM skenu kartografovy mapy (NE na vlastní syntetice):
  X = sken (`resources/<name>.png` + `.pgw`), downscalovaný na trénovací mpp 1,33.
  Y = rasterizace KARTOGRAFOVY `.omap` do gridu skenu (ISOM 2000 → crosswalk `.crt` →
      2017-2 → 18-class `AREA_ZORDER`; bez crosswalku vyjde nesmysl, lekce Sez. 94).

Reportuje DVOJICI metrik (volba uživatele Sez. 120):
  (1) PŘÍSNÁ per-odstín mIoU — stejný kód jako `train.evaluate`, srovnatelná se syntetikou 0,537.
  (2) SOFT mIoU na sémantických skupinách (open/les/voda/…) + pixel-acc — sloučí odstíny v rodině.
      Per-odstín mIoU PODHODNOCUJE „čte model mapu" (401↔403 záměna, vzácné třídy bez supportu);
      soft metrika je poctivá odpověď na úrovni runnability-kategorie.
+ confusion dump (kam pixely utíkají) + colorized Y/pred/scan do temp/ (vizuál verify, oko = source).

Georef paper→sken px (past Sez. 111): paper µm → world (omap georef ref + Rot·scale) → sken px
(.pgw inverze). Net rotace = `rot_sign·grivation + .pgw_rotace`; rot_sign=−1 = net 0 (ověřeno
Sez. 120 vizuálně i číselně: rot_sign=+1 dá mIoU 0,058 = rotovaný overlay, −1 dá 0,256/0,354).

Stav Sez. 120: Bedřichovka per-odstín 0,256 / soft pixel-acc 0,895; Blatná 0,354 / 0,880.
Závěr: model přenáší na reálnou doménu (gap menší, než tvrdilo Sez. 119); per-odstín gap je
metrický (odstínové páry + vzácné třídy), ne kategorický.
"""
import sys
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET

Image.MAX_IMAGE_PIXELS = None                          # reálné skeny jsou velké (Bedř 114 Mpx)
_REPO = Path(__file__).resolve().parents[2]            # model/png2area/eval_real.py → kořen repa
sys.path.insert(0, str(_REPO / "generator"))
sys.path.insert(0, str(_REPO / "model"))
from omap_raster import CODE_TO_LABEL, N_AREA, LABEL_NAME, colorize, _split_rings   # noqa: E402
from compare_isom import _load_crosswalk, _resolve_targets, detect_version           # noqa: E402
from mpp import CANONICAL_MPP                                                          # noqa: E402

TARGET_MPP = CANONICAL_MPP                             # = měřítko dlaždice (SSoT mpp.py, Sez. 126); sken se naň downscaluje
_OUT = _REPO / "temp"                                  # scratch vizuál výstupy (gitignored)
_OUT.mkdir(parents=True, exist_ok=True)                # fresh clone / úklid temp/ → bez FileNotFoundError (audit CODE-D2)


def _local(tag): return tag.split("}")[-1]


def parse_carto_areas(omap_path):
    """[(rings_µm, label)] z kartografovy .omap — id-based symbol→code + crosswalk 2000→2017 → AREA label."""
    root = ET.parse(omap_path).getroot()
    ver = detect_version(str(omap_path))
    cw, v2000, v2017 = _load_crosswalk()
    id2code, id2type = {}, {}
    for el in root.iter():
        if _local(el.tag) == "symbol":
            id2code[el.get("id")] = el.get("code", "")
            id2type[el.get("id")] = int(el.get("type", "0"))   # 1=point 2=line 4/8=area (OOM)
    out = []
    for el in root.iter():
        if _local(el.tag) != "object":
            continue
        sid = el.get("symbol")
        if sid is None or id2type.get(sid, 0) < 4:             # jen plošné (type ≥ 4 = area/combined)
            continue
        try:
            ci = int(float(id2code.get(sid, "")))
        except ValueError:
            continue
        targets = _resolve_targets(ci, ver, cw, v2000, v2017)  # 2000→2017 set
        if not targets:
            continue
        label = next((CODE_TO_LABEL[str(t)] for t in targets if str(t) in CODE_TO_LABEL), None)
        if label is None:
            continue
        c = next((x for x in el if _local(x.tag) == "coords"), None)
        if c is None or not c.text:
            continue
        rings = _split_rings(c.text)
        if rings:
            out.append((rings, label))
    return out


def _omap_georef(omap_path):
    """(scale, grivation_deg, ref_x, ref_y) z georef sekce."""
    root = ET.parse(omap_path).getroot()
    g = next(e for e in root.iter() if _local(e.tag) == "georeferencing")
    rp = next(e for e in root.iter() if _local(e.tag) == "ref_point")
    return (float(g.get("scale")), float(g.get("grivation", "0")),
            float(rp.get("x")), float(rp.get("y")))


def _pgw_inv(pgw_path):
    """Vrátí funkci world(x,y) → sken px(col,row) z .pgw (inverze affine [A B; D E] (px) + (C,F))."""
    A, D, B, E, C, F = [float(x) for x in pgw_path.read_text().split()]
    det = A * E - B * D
    def world_to_px(wx, wy):
        dx, dy = wx - C, wy - F
        col = (E * dx - B * dy) / det
        row = (-D * dx + A * dy) / det
        return col, row
    return world_to_px


def paper_to_scan_px(omap_path, pgw_path, flip_y=True, rot_sign=-1.0):
    """Vrátí fci paper_µm(x,y) → sken px. paper→world (omap georef) → world→px (pgw inv).

    paper µm → world m: world = ref + Rot(rot_sign·griv) · (scale·1e-6 · [px, ±py]).
    rot_sign=−1 / flip_y=True = ověřená kombinace (Sez. 120, net rotace 0 proti .pgw grivaci)."""
    scale, griv, rx, ry = _omap_georef(omap_path)
    w2px = _pgw_inv(pgw_path)
    s = scale * 1e-6                                  # µm paper → m world (od ref)
    th = np.radians(rot_sign * griv)
    ct, st = np.cos(th), np.sin(th)
    sy = -1.0 if flip_y else 1.0
    def to_px(x, y):
        ux, uy = s * x, s * (sy * y)
        wx = rx + ct * ux - st * uy
        wy = ry + st * ux + ct * uy
        return w2px(wx, wy)
    return to_px


def scan_px_to_paper(omap_path, pgw_path, flip_y=True, rot_sign=-1.0):
    """Inverze paper_to_scan_px: FULL sken px (col,row) → paper µm. Pro vektorizaci → .omap (Sez. 132).

    sken px → world m (pgw forward affine) → paper µm (inverze rotace = transpozice + dělení scale).
    Stejná georef (scale/griv/ref + rot_sign=−1/flip_y), jen opačný směr — SSoT vedle paper_to_scan_px (DRY).
    POZOR: očekává FULL sken px; polyline z downscaled gridu (×f) podělit f PŘED voláním."""
    scale, griv, rx, ry = _omap_georef(omap_path)
    A, D, B, E, C, F = [float(v) for v in Path(pgw_path).read_text().split()]   # .pgw: A D B E C F
    s = scale * 1e-6
    th = np.radians(rot_sign * griv)
    ct, st = np.cos(th), np.sin(th)
    sy = -1.0 if flip_y else 1.0
    def to_paper(col, row):
        wx = A * col + B * row + C                       # px → world (pgw forward)
        wy = D * col + E * row + F
        ex, ey = wx - rx, wy - ry                        # posun od ref bodu
        ux = ct * ex + st * ey                           # inverze rotace (R⁻¹ = Rᵀ pro ortogonální R)
        uy = -st * ex + ct * ey
        return ux / s, uy / (s * sy)                     # world m → paper µm (děl scale, odflipuj y)
    return to_paper


def rasterize_Y(areas, to_px, f, W, H):
    """Area objekty → Y label rastr (H,W). Z-order = label pořadí (= AREA_ZORDER index); holes carve."""
    Y = np.zeros((H, W), np.uint8)
    for rings, lab in sorted(areas, key=lambda a: a[1]):    # nižší label = vespod (kreslí se dřív)
        m = Image.new("L", (W, H), 0)
        dm = ImageDraw.Draw(m)
        for ri, ring in enumerate(rings):
            pts = [(to_px(x, y)[0] * f, to_px(x, y)[1] * f) for x, y in ring]
            if len(pts) >= 3:
                dm.polygon(pts, fill=(0 if ri else 1))     # outer=1, díry=0 (carve)
        mask = np.asarray(m, bool)
        Y[mask] = lab
    return Y


def predict_scan(arr):
    """Pustí unet_best.pt na downscalovaný sken (arr H,W,3, tiled 512/384) → pred label (H,W)."""
    import segmentation_models_pytorch as smp
    MEAN = np.array([0.485, 0.456, 0.406], np.float32)
    STD = np.array([0.229, 0.224, 0.225], np.float32)
    H, W = arr.shape[:2]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = smp.Unet("resnet34", encoder_weights=None, in_channels=3, classes=N_AREA).to(dev)
    model.load_state_dict(torch.load(_REPO / "resources" / "area_model" / "unet_best.pt",
                                     weights_only=False, map_location=dev)["model"])
    model.eval()
    T, S = 512, 384
    Hp, Wp = max(H, T), max(W, T)
    pad = np.zeros((Hp, Wp, 3), np.uint8); pad[:H, :W] = arr
    acc = np.zeros((N_AREA, Hp, Wp), np.float32); cnt = np.zeros((Hp, Wp), np.float32)
    for y in sorted(set(list(range(0, Hp - T + 1, S)) + [Hp - T])):
        for x in sorted(set(list(range(0, Wp - T + 1, S)) + [Wp - T])):
            p = (pad[y:y+T, x:x+T].astype(np.float32) / 255.0 - MEAN) / STD
            pt = torch.from_numpy(p.transpose(2, 0, 1)).unsqueeze(0).to(dev)
            with torch.no_grad(), torch.autocast(dev, dtype=torch.bfloat16, enabled=(dev == "cuda")):
                acc[:, y:y+T, x:x+T] += model(pt).softmax(1)[0].float().cpu().numpy()
            cnt[y:y+T, x:x+T] += 1
    return (acc / cnt).argmax(0)[:H, :W].astype(np.uint8)


# --- Soft metrika: sémantické skupiny (sloučení odstínů v rodině) ---
# Per-odstín IoU plete 401↔403 / 408↔410 (kartograf je sám rozlišuje fuzzy) a kolabuje na vzácných
# třídách bez supportu → podhodnocuje „čte model mapu". Soft skupiny = poctivá runnability-optika.
GROUPS = {
    "pozadí":       ["__bg__"],                          # label 0
    "open-žlutá":   ["401", "403", "402", "402.1", "412.1"],
    "les-zelená":   ["406", "408", "410"],
    "voda":         ["301"],
    "mokřad":       ["308", "310"],
    "skály":        ["206", "208"],
    "zástavba/OOB": ["501.1", "501", "521", "520"],
}


def _group_lut():
    """Pole label(0..N_AREA-1) → group id (index do seznamu jmen skupin). Nezařazené → vlastní 'jiné'."""
    names = list(GROUPS)
    lut = np.full(N_AREA, len(names), np.int64)           # default = 'jiné' (poslední+1)
    lut[0] = names.index("pozadí")                        # pozadí = label 0
    for gi, gname in enumerate(names):
        for code in GROUPS[gname]:
            if code == "__bg__":
                continue
            lab = CODE_TO_LABEL.get(code)
            if lab is not None:
                lut[lab] = gi
    return lut, names + ["jiné"]


def _iou_from_cm(cm, classes):
    """Per-class IoU z confusion matice cm (řádek=Y true, sloupec=pred) pro dané třídy."""
    out = []
    for c in classes:
        tp = cm[c, c]; fp = cm[:, c].sum() - tp; fn = cm[c, :].sum() - tp
        den = tp + fp + fn
        if den:
            out.append((c, tp / den, int(cm[c, :].sum())))   # (třída, IoU, support px v Y)
    return out


def print_confusion(cm, present):
    """Pro každou pravou třídu v Y vypíše, KAM model její pixely klasifikoval (top-3 predikce)."""
    print("  confusion (pravá třída Y → kam model predikoval, % z pravých px):")
    for c in present:
        sup = int(cm[c, :].sum())
        if sup == 0:
            continue
        row = cm[c, :]
        top = sorted(range(N_AREA), key=lambda p: -row[p])[:3]
        frags = [f"{LABEL_NAME[p]}={100*row[p]/sup:.0f}%" for p in top if row[p] > 0]
        print(f"    {LABEL_NAME[c]:>6} (n={sup:>9}): " + "  ".join(frags))


def main(name, flip_y=True, rot_sign=-1.0):
    omap = _REPO / "resources" / f"{name}.omap"
    pgw = _REPO / "resources" / f"{name}.pgw"
    png = _REPO / "resources" / f"{name}.png"
    src_mpp = (lambda v: (v[0]**2 + v[1]**2)**0.5)([float(x) for x in pgw.read_text().split()])
    f = src_mpp / TARGET_MPP

    # downscale skenu na trénovací mpp (= vstup modelu); ukládá scan/Y/pred do temp/ pro vizuál verify
    full = Image.open(png).convert("RGB")
    W0, H0 = full.size
    W, H = max(32, round(W0 * f)), max(32, round(H0 * f))
    scan_img = full.resize((W, H), Image.BILINEAR)
    scan_img.save(_OUT / f"real_{name}_scan.png")

    areas = parse_carto_areas(omap)
    print(f"{name}: {len(areas)} area objektů; ver {detect_version(str(omap))}; sken {W0}x{H0}→{W}x{H}")

    to_px = paper_to_scan_px(omap, pgw, flip_y, rot_sign)
    Y = rasterize_Y(areas, to_px, f, W, H)
    pred = predict_scan(np.asarray(scan_img))
    colorize(Y).save(_OUT / f"real_{name}_Y.png")       # reálné Y (georef verify)
    colorize(pred).save(_OUT / f"real_{name}_pred.png")  # predikce

    # confusion matice (řádek=Y true, sloupec=pred) — jediný zdroj pro obě metriky
    cm = np.zeros((N_AREA, N_AREA), np.int64)
    np.add.at(cm, (Y.reshape(-1), pred.reshape(-1)), 1)
    present = sorted(set(np.unique(Y).tolist()) | {0})            # třídy přítomné v Y (+ pozadí)

    # (1) PŘÍSNÁ per-odstín mIoU (stejný kód jako train.evaluate) — srovnatelná se syntetikou
    pc = _iou_from_cm(cm, present)
    miou = float(np.mean([v for _, v, _ in pc])) if pc else 0.0
    print(f"  [PŘÍSNÁ per-odstín] mIoU {miou:.3f} ({len(pc)} tříd v Y) vs syntetická 0,683 (Sez. 126 MPP fix)")
    print("    " + "  ".join(f"{LABEL_NAME[c]}={v:.2f}" for c, v, _ in pc))

    # (2) confusion dump — kam pixely utíkají (test hypotézy odstínové záměny)
    print_confusion(cm, present)

    # (3) SOFT mIoU na sémantických skupinách (open/les/voda/...) — sloučí odstíny v rodině
    lut, gnames = _group_lut()
    NG = len(gnames)
    gcm = np.zeros((NG, NG), np.int64)
    np.add.at(gcm, (lut[Y].reshape(-1), lut[pred].reshape(-1)), 1)
    gpresent = sorted(set(lut[Y].reshape(-1).tolist()))
    gpc = _iou_from_cm(gcm, gpresent)
    gmiou = float(np.mean([v for _, v, _ in gpc])) if gpc else 0.0
    gacc = np.trace(gcm) / gcm.sum()
    print(f"  [SOFT skupiny] mIoU {gmiou:.3f}  pixel-acc {gacc:.3f}  ({len(gpc)} skupin)")
    print("    " + "  ".join(f"{gnames[g]}={v:.2f}(n={n})" for g, v, n in gpc))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # diakritický argv padá v harness (gotcha Sez. 119) → názvy hardcoded, bez argv
    targets = [sys.argv[1]] if len(sys.argv) > 1 else ["Bedřichovka", "Blatná"]
    for nm in targets:
        print("=" * 70)
        main(nm)
