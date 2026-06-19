#!/usr/bin/env python3
r"""Classic-CV PoC pro man-made bodové symboly 525/527/531 ze skenu.

Použití:
  python isom_scan/manmade_points_poc.py
  python isom_scan/manmade_points_poc.py --input "resources/Soví vrch.png" --out-dir temp/manmade_points_sovi --max-dim 1800

Výstup je diagnostika, ne finální mapper-scan pravda. Detektor hledá malé izolované
černé komponenty a porovnává jejich tvar s renderem stejných symbolů z generatoru.
Když chybí lokální sken, skript selže nahlas.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi


# Lokální mapové skeny mohou být obří PNG (stovky MPx), ale jsou to naše vstupy,
# ne nedůvěryhodný upload. Bez toho PIL odmítne např. resources/Soví vrch.png.
Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
GENERATOR_DIR = REPO_ROOT / "generator"
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

from generator import (  # noqa: E402
    ISOM_FODDER,
    ISOM_PROM_X,
    ISOM_SMALL_TOWER,
    LANDMARK_NAME,
    _draw_landmark,
)


DEFAULT_INPUT = HERE / "task_isom_scan.png"
DEFAULT_OUT = HERE / "manmade_points_poc"
TARGET_CODES = (str(ISOM_SMALL_TOWER), str(ISOM_FODDER), str(ISOM_PROM_X))
CODE_ORDER = {code: i for i, code in enumerate(TARGET_CODES)}


@dataclass(frozen=True)
class Candidate:
    """Jedna izolovaná černá komponenta klasifikovaná podle nejlepšího symbolového tvaru."""

    code: str
    score: float
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


def _black_neutral_mask(arr: np.ndarray, dark_max: int, neutral_spread: int) -> np.ndarray:
    """Maska černé kresby: tmavé a barevně neutrální pixely."""
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    return (mx < dark_max) & ((mx - mn) < neutral_spread)


def _render_template(code: str) -> np.ndarray:
    """Vyrenderuje symbol stejnou funkcí jako generator a ořízne ho na neprázdný bbox."""
    size = 64
    rgb = Image.new("RGB", (size, size), "white")
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(rgb)
    mdraw = ImageDraw.Draw(mask)
    _draw_landmark(draw, mdraw, size // 2, size // 2, int(code))
    arr = np.asarray(mask) > 0
    ys, xs = np.where(arr)
    if len(xs) == 0:
        raise RuntimeError(f"Symbol {code} se nepodarilo vyrenderovat")
    x0, x1 = max(0, xs.min() - 1), min(size, xs.max() + 2)
    y0, y1 = max(0, ys.min() - 1), min(size, ys.max() + 2)
    return arr[y0:y1, x0:x1]


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


def _component_candidates(mask: np.ndarray, args: argparse.Namespace) -> list[tuple[slice, slice]]:
    """Najde rozumně malé komponenty; dlouhé linie/textové bloky nechá mimo hru."""
    label_mask = mask
    if args.close_px > 0:
        structure = np.ones((3, 3), dtype=bool)
        label_mask = ndi.binary_closing(mask, structure=structure, iterations=args.close_px)
    labels, n_labels = ndi.label(label_mask)
    objects = ndi.find_objects(labels)

    out: list[tuple[slice, slice]] = []
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
        out.append((sy, sx))
    return out


def _classify(mask: np.ndarray, scale: float, args: argparse.Namespace) -> tuple[list[Candidate], dict[str, object]]:
    templates = {code: _render_template(code) for code in TARGET_CODES}
    candidates: list[Candidate] = []
    raw_components = _component_candidates(mask, args)

    for sy, sx in raw_components:
        component = mask[sy, sx]
        scores = {code: _shape_f1(component, tmpl) for code, tmpl in templates.items()}
        code, score = max(scores.items(), key=lambda item: (item[1], -CODE_ORDER[item[0]]))
        if score < args.score_threshold:
            continue

        ys, xs = np.where(component)
        x0 = (sx.start + float(xs.min())) / scale
        y0 = (sy.start + float(ys.min())) / scale
        x1 = (sx.start + float(xs.max()) + 1.0) / scale
        y1 = (sy.start + float(ys.max()) + 1.0) / scale
        area = int(component.sum())
        candidates.append(
            Candidate(
                code=code,
                score=float(score),
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
        "templates": {code: {"w": int(t.shape[1]), "h": int(t.shape[0]), "px": int(t.sum())}
                      for code, t in templates.items()},
    }
    return capped, stats


def _detections_payload(candidates: list[Candidate], image_path: Path, image_size: tuple[int, int],
                        scale: float, args: argparse.Namespace, stats: dict[str, object]) -> dict[str, object]:
    detections = []
    for code in TARGET_CODES:
        pts = [
            {
                "x": round(c.x, 1),
                "y": round(c.y, 1),
                "score": round(c.score, 3),
                "bbox": [round(v, 1) for v in c.bbox],
                "area_px_proc": c.area_px,
                "fill": round(c.fill, 3),
            }
            for c in candidates
            if c.code == code
        ]
        detections.append({
            "code": code,
            "name": LANDMARK_NAME[int(code)],
            "geom": "point",
            "count": len(pts),
            "points": pts,
            "confidence": round(float(np.mean([p["score"] for p in pts])) if pts else 0.0, 3),
        })

    return {
        "_status": "POC classic_cv 2026-06-19; needs visual/curated validation before generator use",
        "_doc": "Detekce 525/527/531 z neutral-black komponent skenu; pseudo fallback generatoru se tim zatim nenahrazuje.",
        "image": str(image_path),
        "image_size": {"w": image_size[0], "h": image_size[1]},
        "processing_scale": scale,
        "parameters": {
            "dark_max": args.dark_max,
            "neutral_spread": args.neutral_spread,
            "score_threshold": args.score_threshold,
            "min_size": args.min_size,
            "max_size": args.max_size,
            "min_area": args.min_area,
            "max_area": args.max_area,
            "min_fill": args.min_fill,
            "max_fill": args.max_fill,
            "close_px": args.close_px,
            "max_per_code": args.max_per_code,
        },
        "stats": stats,
        "detections": detections,
    }


def _draw_overlay(img: Image.Image, candidates: list[Candidate], out_path: Path) -> None:
    colors = {"525": (0, 120, 255), "527": (220, 20, 60), "531": (120, 40, 200)}
    out = img.copy()
    draw = ImageDraw.Draw(out)
    font = _load_font(16)
    for c in candidates:
        color = colors.get(c.code, (255, 0, 0))
        x0, y0, x1, y1 = c.bbox
        pad = 5
        draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], outline=color, width=3)
        label = f"{c.code} {c.score:.2f}"
        box = draw.textbbox((x1 + 6, y0 - 2), label, font=font)
        draw.rectangle([box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2], fill=(255, 255, 255))
        draw.text((x1 + 6, y0 - 2), label, fill=color, font=font)
    out.save(out_path)


def _contact_sheet(img: Image.Image, candidates: list[Candidate], out_path: Path, limit: int = 36) -> None:
    if not candidates:
        Image.new("RGB", (420, 80), "white").save(out_path)
        return
    chosen = sorted(candidates, key=lambda c: -c.score)[:limit]
    tile = 160
    label_h = 24
    cols = min(6, len(chosen))
    rows = math.ceil(len(chosen) / cols)
    sheet = Image.new("RGB", (cols * tile, rows * (tile + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = _load_font(13)
    for i, c in enumerate(chosen):
        row, col = divmod(i, cols)
        x0, y0, x1, y1 = c.bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        half = max(35, (max(x1 - x0, y1 - y0) / 2) + 25)
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
        draw.text((px + 4, py + tile + 4), f"{c.code} score={c.score:.2f}", fill=(0, 0, 0), font=font)
    sheet.save(out_path)


def _save_mask(mask: np.ndarray, out_path: Path) -> None:
    Image.fromarray(mask.astype(np.uint8) * 255, mode="L").save(out_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-dim", type=int, default=0,
                        help="Volitelne zmenseni pro zpracovani; 0 = plne rozliseni.")
    parser.add_argument("--dark-max", type=int, default=130)
    parser.add_argument("--neutral-spread", type=int, default=18)
    parser.add_argument("--score-threshold", type=float, default=0.55)
    parser.add_argument("--min-size", type=int, default=4)
    parser.add_argument("--max-size", type=int, default=48)
    parser.add_argument("--min-area", type=int, default=8)
    parser.add_argument("--max-area", type=int, default=650)
    parser.add_argument("--min-fill", type=float, default=0.08)
    parser.add_argument("--max-fill", type=float, default=0.48)
    parser.add_argument("--close-px", type=int, default=1)
    parser.add_argument("--max-per-code", type=int, default=50)
    args = parser.parse_args(argv)

    if not args.input.exists():
        raise SystemExit(f"Chybi vstupni sken: {args.input}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    original = Image.open(args.input).convert("RGB")
    proc, scale = _resize_for_processing(original, args.max_dim)
    arr = np.asarray(proc)
    black = _black_neutral_mask(arr, args.dark_max, args.neutral_spread)
    candidates, stats = _classify(black, scale, args)
    payload = _detections_payload(candidates, args.input, original.size, scale, args, stats)

    (args.out_dir / "detections.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.out_dir / "stats.json").write_text(
        json.dumps({"black_px_proc": int(black.sum()), "black_share_proc": float(black.mean()), **stats},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _save_mask(black, args.out_dir / "black_neutral_mask.png")
    _draw_overlay(original, candidates, args.out_dir / "manmade_points_overlay.png")
    _contact_sheet(original, candidates, args.out_dir / "manmade_points_contact_sheet.png")

    print(json.dumps(payload["stats"], ensure_ascii=False, indent=2))
    print(f"Výstupy: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
