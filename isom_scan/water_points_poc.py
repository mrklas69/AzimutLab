#!/usr/bin/env python3
r"""Classic-CV PoC pro modré vodní bodové symboly 311/312/313 ze skenu.

Použití:
  python isom_scan/water_points_poc.py --input "maps/Buschdörfl/bg_scan.png" --out-dir temp/water_points_buschdorfl

Výstup je kandidátní diagnostika, ne GT. Detektor hledá malé izolované modré
komponenty a porovnává je se zjednodušenými šablonami ISOM symbolů.

Na rozdíl od ostatních *_points_poc je tu navíc ROTACE šablon (vodní symboly mají orientaci)
a volitelná MARKER KALIBRACE — proto má vlastní `main`/`_classify`. Sdílené helpery
(font/resize/shape-match/komponenty/payload/vizualizace) bere z `points_common` (C1 dedup, Sez. 165).
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

from points_common import (
    Candidate,
    component_candidates,
    contact_sheet,
    detections_payload,
    draw_overlay,
    resize_for_processing,
    save_mask,
    shape_f1,
)


Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "task_isom_scan.png"
DEFAULT_OUT = HERE / "water_points_poc"
TARGET_CODES = ("311", "312", "313")
CODE_NAMES = {
    "311": "Well, fountain or water tank",
    "312": "Spring",
    "313": "Prominent water feature",
}
CODE_ORDER = {code: i for i, code in enumerate(TARGET_CODES)}


def _blue_mask(arr: np.ndarray, blue_min: int, green_min: int, red_max: int,
               blue_red_diff: int, green_red_diff: int) -> np.ndarray:
    """Maska modré ISOM kresby; bere i tyrkysové antialias pixely ve skenu."""
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    return (
        (b >= blue_min)
        & (g >= green_min)
        & (r <= red_max)
        & ((b - r) >= blue_red_diff)
        & ((g - r) >= green_red_diff)
    )


def _crop_nonempty(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise RuntimeError("Sablona nema zadne pixely")
    return mask[
        max(0, ys.min() - 1): min(mask.shape[0], ys.max() + 2),
        max(0, xs.min() - 1): min(mask.shape[1], xs.max() + 2),
    ]


def _render_template(code: str, angle_deg: int) -> np.ndarray:
    """Vyrenderuje jednoduchou line šablonu a natočí ji po 15 stupních.

    Šablony nejsou exportní symboly. Jsou jen robustní tvarové otisky pro
    porovnání komponenty ve skenu, proto záměrně nepoužívají plnou OOM XML geometrii.
    """
    size = 72
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2

    if code == "311":
        half = 18
        draw.rectangle([cx - half, cy - half, cx + half, cy + half], outline=255, width=5)
    elif code == "312":
        radius = 22
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], 0, 180, fill=255, width=5)
    elif code == "313":
        radius = 22
        for base_angle in (-90, -18, 54, 126, 198):
            rad = math.radians(base_angle)
            draw.line(
                [cx, cy, cx + radius * math.cos(rad), cy + radius * math.sin(rad)],
                fill=255,
                width=5,
            )
    else:
        raise RuntimeError(f"Nepodporovany water-point symbol {code}")

    if angle_deg:
        img = img.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=False)
    return _crop_nonempty(np.asarray(img) > 20)


def _classify(mask: np.ndarray, scale: float, args: argparse.Namespace) -> tuple[list[Candidate], dict[str, object]]:
    """Rotující klasifikace: každou šablonu zkouší po `angle_step` stupních a bere nejlepší F1.

    POZN. (audit Sez. 165): `labels = ndi.label(mask)` re-labeluje RAW masku, idx ale přichází
    z `component_candidates` (label_mask). Při default `close_px=0` jsou obě labelingy shodné →
    chování beze změny; latentní rozjezd při `close_px>0` je známá vada, vědomě neopravená zde."""
    templates = {
        code: [(angle, _render_template(code, angle)) for angle in range(0, 360, args.angle_step)]
        for code in TARGET_CODES
    }
    labels, _ = ndi.label(mask)
    raw_components = component_candidates(
        mask, min_size=args.min_size, max_size=args.max_size, min_area=args.min_area,
        max_area=args.max_area, min_fill=args.min_fill, max_fill=args.max_fill,
        close_px=args.close_px, return_idx=True,
    )
    candidates: list[Candidate] = []

    for idx, sy, sx in raw_components:
        component = labels[sy, sx] == idx
        best_code = ""
        best_angle = 0
        best_score = 0.0
        for code, rotations in templates.items():
            for angle, template in rotations:
                score = shape_f1(component, template)
                if score > best_score or (score == best_score and CODE_ORDER[code] < CODE_ORDER.get(best_code, 99)):
                    best_code = code
                    best_angle = angle
                    best_score = score
        if best_score < args.score_threshold:
            continue

        ys, xs = np.where(component)
        x0 = (sx.start + float(xs.min())) / scale
        y0 = (sy.start + float(ys.min())) / scale
        x1 = (sx.start + float(xs.max()) + 1.0) / scale
        y1 = (sy.start + float(ys.max()) + 1.0) / scale
        area = int(component.sum())
        candidates.append(
            Candidate(
                code=best_code,
                score=float(best_score),
                angle_deg=int(best_angle),
                x=(x0 + x1) / 2.0,
                y=(y0 + y1) / 2.0,
                bbox=(x0, y0, x1, y1),
                area_px=area,
                fill=area / max(1, component.shape[0] * component.shape[1]),
            )
        )

    candidates.sort(key=lambda c: (c.code, -c.score, c.y, c.x))
    capped: list[Candidate] = []
    for code in TARGET_CODES:
        capped.extend([c for c in candidates if c.code == code][: args.max_per_code])

    stats = {
        "raw_components": len(raw_components),
        "kept_total": len(capped),
        "kept_by_code": {code: sum(1 for c in capped if c.code == code) for code in TARGET_CODES},
        "templates": {
            code: {
                "rotations": len(rotations),
                "max_w": max(int(t.shape[1]) for _, t in rotations),
                "max_h": max(int(t.shape[0]) for _, t in rotations),
            }
            for code, rotations in templates.items()
        },
    }
    return capped, stats


def _load_markers(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    markers = data.get("markers", [])
    if not isinstance(markers, list):
        raise SystemExit(f"Marker manifest nema seznam `markers`: {path}")
    return [marker for marker in markers if isinstance(marker, dict)]


def _nearest_candidate(marker: dict[str, Any], candidates: list[Candidate], tol_px: float) -> tuple[Candidate, float] | None:
    try:
        mx = float(marker["x"])
        my = float(marker["y"])
    except (KeyError, TypeError, ValueError):
        return None
    best: tuple[Candidate, float] | None = None
    for candidate in candidates:
        dist = math.hypot(candidate.x - mx, candidate.y - my)
        if dist <= tol_px and (best is None or dist < best[1]):
            best = (candidate, dist)
    return best


def _calibrate_with_markers(candidates: list[Candidate], marker_path: Path, tol_px: float) -> dict[str, Any]:
    """Porovná kandidáty s ručními markery a re-klasifikuje `unknown` podle nejbližšího detektoru."""
    markers = _load_markers(marker_path)
    raw_by_code = {code: 0 for code in (*TARGET_CODES, "unknown")}
    matched_by_code = {code: 0 for code in TARGET_CODES}
    expected_by_code = {code: 0 for code in TARGET_CODES}
    matches: list[dict[str, Any]] = []
    reclassified_unknown: list[dict[str, Any]] = []

    for marker in markers:
        raw_code = str(marker.get("code", ""))
        if raw_code in raw_by_code:
            raw_by_code[raw_code] += 1
        nearest = _nearest_candidate(marker, candidates, tol_px)
        if raw_code in TARGET_CODES:
            expected_by_code[raw_code] += 1
        elif raw_code == "unknown" and nearest is not None:
            expected_by_code[nearest[0].code] += 1

        if nearest is None:
            matches.append({
                "marker_id": marker.get("id"),
                "marker_code": raw_code,
                "matched": False,
            })
            continue

        candidate, dist = nearest
        if raw_code == candidate.code or raw_code == "unknown":
            matched_by_code[candidate.code] += 1
        match = {
            "marker_id": marker.get("id"),
            "marker_code": raw_code,
            "detected_code": candidate.code,
            "distance_px": round(dist, 2),
            "score": round(candidate.score, 3),
            "angle_deg": candidate.angle_deg,
        }
        matches.append(match)
        if raw_code == "unknown":
            reclassified_unknown.append(match)

    marker_recall = {}
    for code in TARGET_CODES:
        expected = expected_by_code[code]
        marker_recall[code] = None if expected == 0 else round(matched_by_code[code] / expected, 3)

    return {
        "markers": str(marker_path),
        "match_tol_px": tol_px,
        "raw_by_code": raw_by_code,
        "expected_by_code": expected_by_code,
        "matched_by_code": matched_by_code,
        "marker_recall": marker_recall,
        "matches": matches,
        "reclassified_unknown": reclassified_unknown,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markers", type=Path, default=None,
                        help="Volitelný ruční marker manifest pro měření recallu a re-klasifikaci unknown.")
    parser.add_argument("--match-tol-px", type=float, default=10.0)
    parser.add_argument("--max-dim", type=int, default=0,
                        help="Volitelne zmenseni pro zpracovani; 0 = plne rozliseni.")
    parser.add_argument("--blue-min", type=int, default=130)
    parser.add_argument("--green-min", type=int, default=90)
    parser.add_argument("--red-max", type=int, default=120)
    parser.add_argument("--blue-red-diff", type=int, default=45)
    parser.add_argument("--green-red-diff", type=int, default=25)
    parser.add_argument("--score-threshold", type=float, default=0.60)
    parser.add_argument("--min-size", type=int, default=16)
    parser.add_argument("--max-size", type=int, default=75)
    parser.add_argument("--min-area", type=int, default=120)
    parser.add_argument("--max-area", type=int, default=1500)
    parser.add_argument("--min-fill", type=float, default=0.08)
    parser.add_argument("--max-fill", type=float, default=0.75)
    parser.add_argument("--close-px", type=int, default=0)
    parser.add_argument("--angle-step", type=int, default=15)
    parser.add_argument("--max-per-code", type=int, default=120)
    args = parser.parse_args(argv)

    if args.angle_step <= 0 or 360 % args.angle_step != 0:
        raise SystemExit("--angle-step musi byt kladny delitel 360")
    if not args.input.exists():
        raise SystemExit(f"Chybi vstupni sken: {args.input}")
    if args.markers is not None and not args.markers.exists():
        raise SystemExit(f"Chybi marker manifest: {args.markers}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    original = Image.open(args.input).convert("RGB")
    proc, scale = resize_for_processing(original, args.max_dim)
    arr = np.asarray(proc)
    blue = _blue_mask(arr, args.blue_min, args.green_min, args.red_max,
                      args.blue_red_diff, args.green_red_diff)
    candidates, stats = _classify(blue, scale, args)
    calibration = (
        _calibrate_with_markers(candidates, args.markers, args.match_tol_px)
        if args.markers is not None else None
    )
    payload = detections_payload(
        candidates, args.input, original.size, scale, target_codes=TARGET_CODES,
        code_names=CODE_NAMES,
        parameters={
            "blue_min": args.blue_min,
            "green_min": args.green_min,
            "red_max": args.red_max,
            "blue_red_diff": args.blue_red_diff,
            "green_red_diff": args.green_red_diff,
            "score_threshold": args.score_threshold,
            "min_size": args.min_size,
            "max_size": args.max_size,
            "min_area": args.min_area,
            "max_area": args.max_area,
            "min_fill": args.min_fill,
            "max_fill": args.max_fill,
            "close_px": args.close_px,
            "angle_step": args.angle_step,
            "max_per_code": args.max_per_code,
        },
        status="POC classic_cv 2026-06-21; needs visual/curated validation before generator use",
        doc="Detekce 311/312/313 z modre kresby skenu; vystup je review kandidat, ne GT.",
        stats=stats,
        include_angle=True,
        calibration=calibration,
    )

    (args.out_dir / "detections.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.out_dir / "stats.json").write_text(
        json.dumps({"blue_px_proc": int(blue.sum()), "blue_share_proc": float(blue.mean()), **stats},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_mask(blue, args.out_dir / "blue_mask.png")
    draw_overlay(original, candidates, args.out_dir / "water_points_overlay.png",
                 colors={"311": (0, 110, 255), "312": (255, 0, 180), "313": (120, 40, 220)},
                 label_fn=lambda c: f"{c.code} {c.score:.2f} {c.angle_deg}°")
    contact_sheet(original, candidates, args.out_dir / "water_points_contact_sheet.png",
                  limit=72, tile=170, label_h=28, font_size=12, half_min=55, half_extra=34,
                  label_fn=lambda c: f"{c.code} s={c.score:.2f} a={c.angle_deg}")

    print(json.dumps(payload["stats"], ensure_ascii=False, indent=2))
    if calibration is not None:
        print(json.dumps(calibration["marker_recall"], ensure_ascii=False, indent=2))
    print(f"Výstupy: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
