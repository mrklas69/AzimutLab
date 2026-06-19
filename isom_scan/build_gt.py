#!/usr/bin/env python3
"""Postaví generátorovou ground-truth pro ISOM-scan benchmark (Sez. 144).

Myšlenka (volba uživatele): spustit generate() na PŘESNĚ stejné geografické ploše jako
reálný sken (Livelox classId), BEZ pseudo predikcí (`only_real=True`) → tvrdá-data ISOM
symboly (vrstevnice/voda/cesty/budovy/skály z DMR) jsou GT ≈ 100 %. Pseudo (balvanová pole,
vegetační body, plot 516) se vědomě VYNECHÁ — tam ani generátor nemá pravdu.

Řetězec souřadnic: symbol paper µm → gen px (_paper_to_px) → S-JTSK (gen bbox) →
EPSG:32633 → scan map.png px (inv _map_affine) → task crop px (zaznamenaný box).

Fáze (idempotentní — hotové kroky přeskočí, hlásí to nahlas):
  1. generate_map + clip_omap_to_quad   → gen_gt/<name>.omap
  2. (TODO další commit) extrakce symbolů + zarovnání → gt/ground_truth.json

Spouštět z kořene přes .venv (sys.path skript, fáze B):
  python isom_scan/build_gt.py
"""
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "connectors"))
sys.path.insert(0, str(REPO / "generator"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

CID = "1127443"
CID_DIR = REPO / "resources" / "livelox" / CID
GEN_DIR = CID_DIR / "gen_gt"
NAME = GEN_DIR.name   # generate_map pojmenuje .omap podle basename out_diru (jako build_pair) — DRY, nedrift


def compute_extent():
    """lat/lon + w_km/h_km + content_quad z meta — replikuje pairs.build_pair 139-149, BEZ max_km."""
    from livelox import _georef_grid
    from pairs import _content_quad_sjtsk, _SJTSK_TO_WGS84
    meta = json.loads((CID_DIR / "meta.json").read_text(encoding="utf-8"))
    g = _georef_grid(meta)
    content_quad = _content_quad_sjtsk(CID_DIR, g["quad"])
    xs = [p[0] for p in content_quad]
    ys = [p[1] for p in content_quad]
    xmin, ymin, xmax, ymax = min(xs), min(ys), max(xs), max(ys)
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    lon, lat = _SJTSK_TO_WGS84.transform(cx, cy)
    w_km, h_km = (xmax - xmin) / 1000.0, (ymax - ymin) / 1000.0   # BEZ max_km = celá mapa
    return lat, lon, w_km, h_km, content_quad, meta


def stage_generate():
    omap = GEN_DIR / f"{NAME}.omap"
    if omap.exists():
        print(f"[1] gen .omap už existuje ({omap}) — přeskakuji generaci.")
        return
    from generator import generate_map
    from cut import clip_omap_to_quad
    lat, lon, w_km, h_km, content_quad, _ = compute_extent()
    print(f"[1] generate_map only_real  výsek {w_km:.2f}×{h_km:.2f} km @ ({lat:.5f},{lon:.5f}) → {GEN_DIR}")
    generate_map(lat, lon, w_km, h_km, only_real=True, out_dir=str(GEN_DIR), ortho=False)
    kept, removed = clip_omap_to_quad(str(GEN_DIR), NAME, content_quad)
    print(f"[1] ořez na quad: {kept} objektů v poli, {removed} přesah odstraněn")


import xml.etree.ElementTree as ET

import numpy as np

GT_OUT = REPO / "isom_scan" / "gt" / "ground_truth.json"
CROP_BOX = REPO / "isom_scan" / "gt" / "task_crop_box.json"
TASK_W, TASK_H = 1655, 1868

# Kódy, proti kterým se MÁ skórovat = data-derivovatelné, generátor je věrný (≈100 %).
# VYNECHÁNO (generátor pravdu nemá → nefér měřit): husté skály 204/206/207/208/210 (ZABAGED řídký
# vs pískovec), vegetační hustota 406-410 + body 416-419 (only_real je nekreslí), pseudo 525/527/531/516,
# poledník 601. Viz _caveats. Lze ručně doladit v ground_truth.json["score_codes"].
SCORE_CODES = {
    "101", "102", "103", "104", "301", "301.1", "304", "305", "306", "308",
    "401", "403", "405", "412", "501", "501.1", "502", "503", "504", "505", "506", "508",
    "509", "510", "513", "520", "521", "523", "524", "526", "530", "311", "312", "203.2",
}


def _strip(tag):
    return tag.rsplit("}", 1)[-1]


def parse_objects(omap_path):
    """Obecný parser .omap → [(code, name, geom, [(x,y)…paper µm])]. geom z type + area-set."""
    from omap_raster import CODE_TO_LABEL
    area_codes = set(CODE_TO_LABEL)
    root = ET.parse(omap_path).getroot()
    sp = next(e for e in root.iter() if _strip(e.tag) == "symbols")
    syms = [s for s in sp if _strip(s.tag) == "symbol"]
    codes = [s.get("code") for s in syms]
    names = [s.get("name", "") for s in syms]
    op = next(e for e in root.iter() if _strip(e.tag) == "objects")
    out = []
    for o in op.iter():
        if _strip(o.tag) != "object":
            continue
        si = int(o.get("symbol", -1))
        if not (0 <= si < len(codes)):
            continue
        code, name, otype = codes[si], names[si], o.get("type", "1")
        c = next((x for x in o if _strip(x.tag) == "coords"), None)
        if c is None or not c.text:
            continue
        pts = []
        for vtx in c.text.strip().rstrip(";").split(";"):
            f = vtx.split()
            if len(f) >= 2:
                pts.append((float(f[0]), float(f[1])))   # paper µm (x,y); flagy ignoruj
        if not pts:
            continue
        geom = "point" if otype == "0" else ("area" if code in area_codes else "line")
        out.append((code, name, geom, pts))
    return out


def make_gen_to_task():
    """Vrátí funkci paper µm (gen .omap) → task crop px, přes S-JTSK + scan georef + crop box."""
    from omap_raster import _paper_to_px
    from livelox import _georef_grid, _map_affine
    gm = json.loads((GEN_DIR / "meta.json").read_text(encoding="utf-8"))
    to_px, _, _ = _paper_to_px(gm)                       # paper µm → gen px
    pA, pD, pB, pE, pC, pF = [float(x) for x in (GEN_DIR / "rgb.pgw").read_text().split()]
    meta_scan = json.loads((CID_DIR / "meta.json").read_text(encoding="utf-8"))
    g = _georef_grid(meta_scan)
    As = np.array(_map_affine(g["quad"], meta_scan["imageWidth"], meta_scan["imageHeight"]))  # [col,row,1]→[E,N]
    Asinv = np.linalg.inv(np.vstack([As, [0, 0, 1.0]]))  # [E,N,1]→[col,row]
    box = json.loads(CROP_BOX.read_text(encoding="utf-8"))
    x0, y0 = box["x0"], box["y0"]

    def to_task(x, y):
        col, row = to_px(x, y)                            # gen px
        E = pA * col + pC                                 # S-JTSK (pgw, bez skew)
        N = pE * row + pF
        v = Asinv @ np.array([E, N, 1.0])                 # map.png px
        return v[0] - x0, v[1] - y0                       # task crop px

    return to_task


def _centroid(pts):
    xs, ys = zip(*pts)
    return sum(xs) / len(xs), sum(ys) / len(ys)


def stage_extract():
    omap = GEN_DIR / f"{NAME}.omap"
    objs = parse_objects(omap)
    to_task = make_gen_to_task()
    # crosswalk-aware kontrola počtů (CLAUDE.md: výskyt přes compare_isom, ne ad-hoc)
    from compare_isom import isom_usage
    usage, _ = isom_usage(str(omap))
    print(f"[2] {len(objs)} objektů v gen .omap; compare_isom kódů: {len(usage)}")

    by_code = {}
    for code, name, geom, pts in objs:
        rep = _centroid(pts) if geom != "point" else pts[0]
        tx, ty = to_task(*rep)
        if not (0 <= tx < TASK_W and 0 <= ty < TASK_H):   # mimo mapové pole skenu → zahoď (= clip)
            continue
        d = by_code.setdefault(code, {"code": code, "name": name, "geom": geom,
                                      "count": 0, "points": []})
        d["count"] += 1
        d["points"].append({"x": round(tx, 1), "y": round(ty, 1)})

    # u ploch/linií zkrať reprezentativní body na ~3 (count zůstává)
    detections = []
    for code, d in sorted(by_code.items()):
        if d["geom"] != "point" and len(d["points"]) > 3:
            d["points"] = d["points"][:3]
        d["confidence"] = 1.0
        detections.append(d)

    score_codes = sorted(c for c in by_code if c in SCORE_CODES)
    gt = {
        "_status": "READY 2026-06-18 (generátorová GT, only_real)",
        "_doc": "GT z generate_map(only_real=True) na Branžež quad — tvrdá ČÚZK/DMR data, BEZ pseudo. "
                "Body v task_isom_scan.png px (origin l-h). Zarovnání: gen paper→S-JTSK→scan→crop box.",
        "_caveats": [
            "Skóruje se JEN přes score_codes (data-derivovatelné). Husté skály (204/206/207/208/210), "
            "vegetační hustota (406-410) a body (416-419) NEJSOU ve score_codes: generátor je z dat nekreslí "
            "věrně (pískovec >> ZABAGED balvany; vegetace gate). Měřit modely proti nim by bylo nefér.",
            "Pseudo (525/527/531/516/310 split) vyloučeno už generací (only_real, pseudorealistic=False).",
            "Počty = objekty padnoucí do mapového pole skenu (bounds-filter = clip).",
        ],
        "image": "task_isom_scan.png",
        "image_size": {"w": TASK_W, "h": TASK_H},
        "source": {"classId": CID, "isom_version": "2017-2", "via": "generate_map only_real + georef align"},
        "score_codes": score_codes,
        "detections": detections,
    }
    GT_OUT.write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    pt = sum(d["count"] for d in detections if d["geom"] == "point")
    print(f"[2] GT zapsána: {len(detections)} kódů, {pt} bodových výskytů v poli; "
          f"score_codes={len(score_codes)} → {GT_OUT}")
    print(f"    score_codes: {', '.join(score_codes)}")


def main():
    stage_generate()
    stage_extract()
    print("[hotovo] GT připravena. Skóruj: python isom_scan/score.py isom_scan/runs/*.json")


if __name__ == "__main__":
    main()
