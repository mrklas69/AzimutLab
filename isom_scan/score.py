#!/usr/bin/env python3
"""Skórovač ISOM-scan benchmarku.

Vstup: run soubor(y) `runs/*.json` (operátorem vyplněná meta + vložený JSON výstup
modelu) + ground truth `gt/ground_truth.json`. Výstup: řádek na běh připsaný do
`results.csv`. Model NIKDY neskóruje sám sebe — to dělá tento skript proti GT.

Metriky:
  - point_F1       — macro-F1 přes bodové ISOM kódy (distance-match do TOL_PX); headline.
  - area_count_fid — věrnost počtů u ploch/linií (1 - |Δ|/max), průměr přes kódy.
  - class_recall   — podíl GT kódů (libovolná geom), které model vůbec zachytil.

Bez GT (template/prázdná) → scored metriky = "NA" (no silent fallback: hlásí WARN).

Použití:
  python score.py runs/2026-06-18_opus-4.8_seed0.json
  python score.py runs/*.json --gt gt/ground_truth.json --out results.csv --tol-px 20
"""
import argparse
import csv
import json
import math
import os
import sys

# Windows konzole bývá cp1250 → diakritika i šipky v printu padají; vynuť UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

BENCHMARK_VERSION = "1.0"
DEFAULT_TOL_PX = 20  # tolerance distance-matchu bodů (px na 1655×1868; ~18 mm v terénu)

CSV_FIELDS = [
    # --- run metadata (z meta bloku run souboru) ---
    "run_id", "date", "benchmark_version", "model", "build", "provider",
    "quant", "ctx_window", "vision", "pdf_ingested", "temperature", "seed",
    "prompt_tokens", "completion_tokens", "latency_s", "cost_usd",
    # --- self-report (co model tvrdí; NEsprávnost) ---
    "n_point", "n_line", "n_area", "n_codes",
    # --- skórované vs GT (KPI) ---
    "point_F1", "area_count_fid", "class_recall", "headline_score",
]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def gt_is_filled(gt):
    """GT je připravená ke skórování JEN když `_status` začíná 'READY'.

    Bezpečné chování: TEMPLATE (prázdná) i BOOTSTRAP (rozpracovaný nástřel) → NEskórovat
    (vrať NA), aby se modely neměřily proti neúplné pravdě. Kartograf po dokončení
    korekce přepíše `_status` na 'READY …' → skórování se aktivuje (no-silent-fallback)."""
    dets = gt.get("detections", [])
    if not dets:
        return False
    if not str(gt.get("_status", "")).startswith("READY"):
        return False
    return any(int(d.get("count", 0)) > 0 for d in dets)


def index_by_code(detections):
    return {str(d["code"]): d for d in detections}


def split_geoms(detections):
    point, area_line = set(), set()
    for d in detections:
        code, geom = str(d["code"]), d.get("geom", "")
        (point if geom == "point" else area_line).add(code)
    return point, area_line


def match_points(gt_pts, pred_pts, tol):
    """Greedy nearest-neighbour match pod tolerancí → (TP, FP, FN)."""
    gp = [(p["x"], p["y"]) for p in gt_pts]
    pp = [(p["x"], p["y"]) for p in pred_pts]
    pairs = []
    for gi, g in enumerate(gp):
        for pi, p in enumerate(pp):
            dist = math.hypot(g[0] - p[0], g[1] - p[1])
            if dist <= tol:
                pairs.append((dist, gi, pi))
    pairs.sort()
    used_g, used_p = set(), set()
    tp = 0
    for _, gi, pi in pairs:
        if gi in used_g or pi in used_p:
            continue
        used_g.add(gi)
        used_p.add(pi)
        tp += 1
    fp = len(pp) - tp
    fn = len(gp) - tp
    return tp, fp, fn


def f1(tp, fp, fn):
    if tp == 0:
        return 0.0
    prec = tp / (tp + fp)
    rec = tp / (tp + fn)
    return 0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec)


def score_points(gt_idx, pred_idx, gt_point_codes, pred_point_codes, tol, allow=None):
    """Macro-F1 přes UNII bodových kódů (halucinace i propady se trestají).

    `allow` (score_codes) omezí skórování na data-derivovatelné kódy — viz GT _caveats."""
    codes = gt_point_codes | pred_point_codes
    if allow is not None:
        codes &= allow
    if not codes:
        return None
    f1s = []
    for code in codes:
        gp = gt_idx.get(code, {}).get("points", [])
        pp = pred_idx.get(code, {}).get("points", [])
        f1s.append(f1(*match_points(gp, pp, tol)))
    return sum(f1s) / len(f1s)


def score_area_counts(gt_idx, pred_idx, gt_area_codes, allow=None):
    """Věrnost počtů přes GT plochy/linie: 1 - |Δ| / max(gt, pred, 1)."""
    if allow is not None:
        gt_area_codes = gt_area_codes & allow
    if not gt_area_codes:
        return None
    fids = []
    for code in gt_area_codes:
        gc = int(gt_idx[code].get("count", 0))
        pc = int(pred_idx.get(code, {}).get("count", 0))
        fids.append(1 - abs(gc - pc) / max(gc, pc, 1))
    return sum(fids) / len(fids)


def score_class_recall(gt_idx, pred_idx, allow=None):
    """Podíl GT kódů (libovolná geom), které model vůbec zachytil (count>0)."""
    codes = set(gt_idx) if allow is None else (set(gt_idx) & allow)
    if not codes:
        return None
    hit = sum(1 for c in codes if int(pred_idx.get(c, {}).get("count", 0)) > 0)
    return hit / len(codes)


def self_report(detections):
    n = {"point": 0, "line": 0, "area": 0}
    for d in detections:
        g = d.get("geom", "")
        if g in n:
            n[g] += 1
    return n["point"], n["line"], n["area"], len(detections)


def score_run(run_path, gt, tol):
    run = load_json(run_path)
    meta = run.get("meta", {})
    out = run.get("output", run)  # tolerantně: buď {meta,output}, nebo holý výstup
    dets = out.get("detections", [])

    n_point, n_line, n_area, n_codes = self_report(dets)
    pred_idx = index_by_code(dets)
    pred_pts, pred_al = split_geoms(dets)

    row = {f: meta.get(f, "") for f in CSV_FIELDS}
    row["run_id"] = meta.get("run_id") or os.path.splitext(os.path.basename(run_path))[0]
    row["benchmark_version"] = BENCHMARK_VERSION
    row["n_point"], row["n_line"], row["n_area"], row["n_codes"] = n_point, n_line, n_area, n_codes

    if not gt_is_filled(gt):
        print(f"  WARN: GT není vyplněná → scored metriky = NA ({row['run_id']})", file=sys.stderr)
        for m in ("point_F1", "area_count_fid", "class_recall", "headline_score"):
            row[m] = "NA"
        return row

    gt_idx = index_by_code(gt["detections"])
    gt_pts, gt_al = split_geoms(gt["detections"])
    allow = set(gt["score_codes"]) if gt.get("score_codes") else None

    pf1 = score_points(gt_idx, pred_idx, gt_pts, pred_pts, tol, allow)
    acf = score_area_counts(gt_idx, pred_idx, gt_al, allow)
    cr = score_class_recall(gt_idx, pred_idx, allow)
    fmt = lambda v: "NA" if v is None else round(v, 4)
    row["point_F1"], row["area_count_fid"], row["class_recall"] = fmt(pf1), fmt(acf), fmt(cr)
    row["headline_score"] = fmt(pf1)  # headline = point_F1 (anti-sprawl: jedno primární KPI)
    return row


def append_csv(rows, out_path):
    exists = os.path.exists(out_path)
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", help="run JSON soubor(y)")
    ap.add_argument("--gt", default=os.path.join(os.path.dirname(__file__), "gt", "ground_truth.json"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results.csv"))
    ap.add_argument("--tol-px", type=int, default=DEFAULT_TOL_PX)
    args = ap.parse_args()

    gt = load_json(args.gt)
    rows = []
    for rp in args.runs:
        print(f"Skóruji {rp}")
        row = score_run(rp, gt, args.tol_px)
        rows.append(row)
        print(f"  headline={row['headline_score']} point_F1={row['point_F1']} "
              f"area_fid={row['area_count_fid']} class_recall={row['class_recall']}")
    append_csv(rows, args.out)
    print(f"Zapsáno {len(rows)} řádků → {args.out}")


if __name__ == "__main__":
    main()
