#!/usr/bin/env python3
r"""Classic-CV PoC pro modré vodní bodové symboly 311/312/313 ze skenu.

Použití:
  python isom_scan/water_points_poc.py --input "maps/Buschdörfl/bg_scan.png" --out-dir temp/water_points_buschdorfl

Výstup je kandidátní diagnostika, ne GT. Detektor hledá malé izolované modré
komponenty a porovnává je se zjednodušenými šablonami ISOM symbolů.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi


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


@dataclass(frozen=True)
class Candidate:
    """Jedna modrá komponenta klasifikovaná podle nejlepší vodní point šablony."""

    code: str
    score: float
    angle_deg: int
    x: float
    y: float
    bbox: tuple[float, float, float, float]
    area_px: int
    fill: float


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _resize_for_processing(img: Image.Image, max_dim: int) -> tuple[Image.Image, float]:
    """Vrátí pracovní obraz a měřítko proc_px/orig_px."""
    if max_dim <= 0 or max(img.size) <= max_dim:
        return img.copy(), 1.0
    scale = max_dim / max(img.size)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(size, Image.Resampling.BILINEAR), scale


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


def _resize_bool(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Nearest-neighbour resize binární šablony přes PIL, bez OpenCV závislosti."""
    h, w = shape
    im = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
    return np.asarray(im.resize((w, h), Image.Resampling.NEAREST)) > 0


def _shape_f1(component: np.ndarray, template: np.ndarray) -> float:
    """F1 překryvu komponenty se šablonou přetaženou na stejný bbox."""
    if not component.any():
        return 0.0
    tmpl = _resize_bool(template, component.shape)
    overlap = component & tmpl
    tp = int(overlap.sum())
    if tp == 0:
        return 0.0
    precision = tp / int(component.sum())
    recall = tp / int(tmpl.sum())
    return 2 * precision * recall / (precision + recall)


def _component_candidates(mask: np.ndarray, args: argparse.Namespace) -> list[tuple[int, slice, slice]]:
    """Vybere malé modré komponenty; dlouhé potoky, šrafy a vodní plochy nechá mimo."""
    label_mask = mask
    if args.close_px > 0:
        structure = np.ones((3, 3), dtype=bool)
        label_mask = ndi.binary_closing(mask, structure=structure, iterations=args.close_px)
    labels, _ = ndi.label(label_mask)
    objects = ndi.find_objects(labels)

    out: list[tuple[int, slice, slice]] = []
    for idx, obj in enumerate(objects, start=1):
        if obj is None:
            continue
        sy, sx = obj
        h = sy.stop - sy.start
        w = sx.stop - sx.start
        if h < args.min_size or w < args.min_size or h > args.max_size or w > args.max_size:
            continue
        component = labels[sy, sx] == idx
        area = int(component.sum())
        if area < args.min_area or area > args.max_area:
            continue
        fill = area / (w * h)
        if fill < args.min_fill or fill > args.max_fill:
            continue
        out.append((idx, sy, sx))
    return out


def _classify(mask: np.ndarray, scale: float, args: argparse.Namespace) -> tuple[list[Candidate], dict[str, object]]:
    templates = {
        code: [(angle, _render_template(code, angle)) for angle in range(0, 360, args.angle_step)]
        for code in TARGET_CODES
    }
    labels, _ = ndi.label(mask)
    raw_components = _component_candidates(mask, args)
    candidates: list[Candidate] = []

    for idx, sy, sx in raw_components:
        component = labels[sy, sx] == idx
        best_code = ""
        best_angle = 0
        best_score = 0.0
        for code, rotations in templates.items():
            for angle, template in rotations:
                score = _shape_f1(component, template)
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


def _detections_payload(candidates: list[Candidate], image_path: Path, image_size: tuple[int, int],
                        scale: float, args: argparse.Namespace, stats: dict[str, object],
                        calibration: dict[str, Any] | None) -> dict[str, object]:
    detections = []
    for code in TARGET_CODES:
        pts = [
            {
                "x": round(c.x, 1),
                "y": round(c.y, 1),
                "score": round(c.score, 3),
                "angle_deg": c.angle_deg,
                "bbox": [round(v, 1) for v in c.bbox],
                "area_px_proc": c.area_px,
                "fill": round(c.fill, 3),
            }
            for c in candidates
            if c.code == code
        ]
        detections.append({
            "code": code,
            "name": CODE_NAMES[code],
            "geom": "point",
            "count": len(pts),
            "points": pts,
            "confidence": round(float(np.mean([p["score"] for p in pts])) if pts else 0.0, 3),
        })

    payload: dict[str, object] = {
        "_status": "POC classic_cv 2026-06-21; needs visual/curated validation before generator use",
        "_doc": "Detekce 311/312/313 z modre kresby skenu; vystup je review kandidat, ne GT.",
        "image": str(image_path),
        "image_size": {"w": image_size[0], "h": image_size[1]},
        "processing_scale": scale,
        "parameters": {
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
        "stats": stats,
        "detections": detections,
    }
    if calibration is not None:
        payload["calibration"] = calibration
    return payload


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


def _draw_overlay(img: Image.Image, candidates: list[Candidate], out_path: Path) -> None:
    colors = {"311": (0, 110, 255), "312": (255, 0, 180), "313": (120, 40, 220)}
    out = img.copy()
    draw = ImageDraw.Draw(out)
    font = _load_font(16)
    for c in candidates:
        color = colors.get(c.code, (255, 0, 0))
        x0, y0, x1, y1 = c.bbox
        pad = 5
        draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], outline=color, width=3)
        label = f"{c.code} {c.score:.2f} {c.angle_deg}°"
        box = draw.textbbox((x1 + 6, y0 - 2), label, font=font)
        draw.rectangle([box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2], fill=(255, 255, 255))
        draw.text((x1 + 6, y0 - 2), label, fill=color, font=font)
    out.save(out_path)


def _contact_sheet(img: Image.Image, candidates: list[Candidate], out_path: Path, limit: int = 72) -> None:
    if not candidates:
        Image.new("RGB", (420, 80), "white").save(out_path)
        return
    chosen = sorted(candidates, key=lambda c: -c.score)[:limit]
    tile = 170
    label_h = 28
    cols = min(6, len(chosen))
    rows = math.ceil(len(chosen) / cols)
    sheet = Image.new("RGB", (cols * tile, rows * (tile + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = _load_font(12)
    for i, c in enumerate(chosen):
        row, col = divmod(i, cols)
        x0, y0, x1, y1 = c.bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        half = max(55, (max(x1 - x0, y1 - y0) / 2) + 34)
        crop_box = (
            max(0, int(cx - half)),
            max(0, int(cy - half)),
            min(img.width, int(cx + half)),
            min(img.height, int(cy + half)),
        )
        crop = img.crop(crop_box).resize((tile, tile), Image.Resampling.BILINEAR)
        px = col * tile
        py = row * (tile + label_h)
        sheet.paste(crop, (px, py))
        draw.text((px + 4, py + tile + 4), f"{c.code} s={c.score:.2f} a={c.angle_deg}", fill=(0, 0, 0), font=font)
    sheet.save(out_path)


def _save_mask(mask: np.ndarray, out_path: Path) -> None:
    Image.fromarray(mask.astype(np.uint8) * 255, mode="L").save(out_path)


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
    proc, scale = _resize_for_processing(original, args.max_dim)
    arr = np.asarray(proc)
    blue = _blue_mask(arr, args.blue_min, args.green_min, args.red_max,
                      args.blue_red_diff, args.green_red_diff)
    candidates, stats = _classify(blue, scale, args)
    calibration = (
        _calibrate_with_markers(candidates, args.markers, args.match_tol_px)
        if args.markers is not None else None
    )
    payload = _detections_payload(candidates, args.input, original.size, scale, args, stats, calibration)

    (args.out_dir / "detections.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.out_dir / "stats.json").write_text(
        json.dumps({"blue_px_proc": int(blue.sum()), "blue_share_proc": float(blue.mean()), **stats},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _save_mask(blue, args.out_dir / "blue_mask.png")
    _draw_overlay(original, candidates, args.out_dir / "water_points_overlay.png")
    _contact_sheet(original, candidates, args.out_dir / "water_points_contact_sheet.png")

    print(json.dumps(payload["stats"], ensure_ascii=False, indent=2))
    if calibration is not None:
        print(json.dumps(calibration["marker_recall"], ensure_ascii=False, indent=2))
    print(f"Výstupy: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
