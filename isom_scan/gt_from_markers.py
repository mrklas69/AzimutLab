#!/usr/bin/env python3
"""Sestaví hybrid ISOM-scan GT z ručních markerů (mark_isoms) — Sez. 168.

Ruční bodová GT (kartografovo oko = pravda na reálném skenu) NAHRADÍ generátorové BODOVÉ detections;
liniové/plošné generátorové detections ZŮSTANOU (dokud se taky nepředělají ručně, „začneme bodovými").
Tím se prolomí zeď headline `point_F1`: generátorová GT (build_gt only_real) měla jen 2 skórovatelné
body 526/530 na ~1 lokaci (artefakt) → desítky ručních bodů s jednoznačnou pozicí.

Verzování (build_gt README pravidlo): ruční GT se NEMÍCHÁ tiše s generátorovou → nese `_benchmark_version`
"2.0", které score.py reportuje místo konstanty 1.0; původní v1 se zálohuje vedle.

Vstup:  markers JSON z mark_isoms (poziční arg); existující gt/ground_truth.json (zachová ne-bodové).
Výstup: gt/ground_truth.json (hybrid) + záloha gt/ground_truth.v1.json.bak.

Spouštět z kořene přes .venv:
  python isom_scan/gt_from_markers.py isom_scan/markers/bransez_gt.json
"""
import argparse
import json
import math
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
GT_PATH = HERE / "gt" / "ground_truth.json"
SANITY_TOL_PX = 20   # dva RŮZNÉ bodové kódy blíž než tohle = red flag (izomorf score.DEFAULT_TOL_PX)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# anglické názvy bodů = mark_isoms.CODE_LABELS (SSoT); import přímo, ať se nederiftuje
sys.path.insert(0, str(HERE))
from mark_isoms import CODE_LABELS  # noqa: E402


def _name(code: str) -> str:
    return CODE_LABELS.get(code, {}).get("name", "")


def _point_detections(markers: list[dict]) -> dict:
    """Seskupí ruční markery dle kódu → {code: {code,name,geom=point,count,points}}."""
    by_code: dict[str, dict] = {}
    for m in markers:
        code = str(m["code"])
        d = by_code.setdefault(code, {"code": code, "name": _name(code), "geom": "point",
                                      "count": 0, "points": [], "confidence": 1.0})
        d["count"] += 1
        d["points"].append({"x": round(float(m["x"]), 1), "y": round(float(m["y"]), 1)})
    return by_code


def _close_pairs(by_code: dict, tol: float) -> list[tuple]:
    """Najde dvojice bodů RŮZNÝCH kódů blíž než `tol` (podezřelé — jeden objekt značený dvěma kódy)."""
    pts = [(c, p) for c, d in by_code.items() for p in d["points"]]
    out = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            (ca, pa), (cb, pb) = pts[i], pts[j]
            if ca == cb:                                  # víc instancí téhož kódu = legitimní
                continue
            dist = math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
            if dist < tol:
                out.append((ca, pa, cb, pb, dist))
    return out


def build(markers_path: pathlib.Path, gt_path: pathlib.Path, version: str) -> dict:
    man = json.loads(markers_path.read_text(encoding="utf-8"))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    markers = man.get("markers", [])
    if not markers:
        raise SystemExit(f"{markers_path}: žádné markery (naklikej nejdřív přes mark_isoms)")

    by_code = _point_detections(markers)
    non_point = [d for d in gt.get("detections", []) if d.get("geom") != "point"]   # zachovej gen linie/plochy

    # sanity-check (build_gt README red flag 526/530): nahlas, ať uživatel rozhodne, ne tiše
    for ca, pa, cb, pb, dist in _close_pairs(by_code, SANITY_TOL_PX):
        print(f"  ⚠ blízké body různých kódů: {ca}@({pa['x']:.0f},{pa['y']:.0f}) ~ "
              f"{cb}@({pb['x']:.0f},{pb['y']:.0f}) = {dist:.1f} px (jeden objekt dvěma kódy?)", file=sys.stderr)

    # score_codes: ne-bodové z původních (kde gen má pravdu) + VŠECHNY ruční bodové (ruční GT = pravda)
    orig = set(gt.get("score_codes", []))
    non_point_codes = {d["code"] for d in non_point}
    score_codes = sorted((orig & non_point_codes) | set(by_code))

    detections = sorted(list(by_code.values()) + non_point, key=lambda d: d["code"])
    return {
        "_status": f"READY {time.strftime('%Y-%m-%d')} (hybrid: ruční bodová GT + generátorové linie/plochy)",
        "_benchmark_version": version,
        "_doc": "Bodové detections = ruční markery (mark_isoms) na task_isom_scan.png — kartografovo oko = "
                "pravda na reálném skenu. Linie/plochy = generátorové (build_gt only_real), dokud se taky "
                "nepředělají ručně. Body v px task_isom_scan.png (origin l-h).",
        "_caveats": [
            "Bodové kódy se skórují VŠECHNY (ruční GT je pravda) — žádný score_codes ořez jako u generátorové GT.",
            "Linie/plochy zůstávají generátorové (data-derivovatelné score_codes) — point_F1 je ruční, "
            "area_count_fid generátorové. Nemíchat výsledky v1/v2 (jiné _benchmark_version).",
            "1 sken (Branžež) — robustní benchmark chce víc map; zatím MVP na prolomení zdi point_F1.",
        ],
        "image": gt.get("image", "task_isom_scan.png"),
        "image_size": man.get("image_size", gt.get("image_size")),
        "source": {**gt.get("source", {}), "point_gt": "manual (mark_isoms)",
                   "markers": markers_path.name},
        "score_codes": score_codes,
        "detections": detections,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markers", help="markers JSON z mark_isoms")
    ap.add_argument("--gt", default=str(GT_PATH), help="cílová ground_truth.json (default isom_scan/gt/)")
    ap.add_argument("--version", default="2.0", help="_benchmark_version hybrid GT (default 2.0)")
    args = ap.parse_args()

    gt_path = pathlib.Path(args.gt)
    out = build(pathlib.Path(args.markers), gt_path, args.version)

    bak = gt_path.with_name("ground_truth.v1.json.bak")                  # záloha generátorové v1 (jednou)
    if not bak.exists():
        bak.write_text(gt_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  záloha v1 → {bak.name}")
    gt_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    n_pt = sum(d["count"] for d in out["detections"] if d["geom"] == "point")
    n_codes = sum(1 for d in out["detections"] if d["geom"] == "point")
    print(f"hybrid GT v{args.version}: {n_codes} bodových kódů / {n_pt} bodů + "
          f"{len(out['detections']) - n_codes} ne-bodových; score_codes={len(out['score_codes'])} → {gt_path}")


if __name__ == "__main__":
    main()
