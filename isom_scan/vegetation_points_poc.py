#!/usr/bin/env python3
r"""Classic-CV PoC pro zelené vegetation-point symboly 417/418 ze skenu.

Použití:
  python isom_scan/vegetation_points_poc.py --input "maps/Buschdörfl/bg_scan.png" --out-dir temp/vegetation_points_buschdorfl

Výstup je kandidátní diagnostika, ne GT. Detektor hledá malé izolované zelené
komponenty podobné 417 Prominent large tree a 418 Prominent bush or tree.

Sdílená mašinérie (font/resize/shape-match/komponenty/payload/vizualizace) žije v `points_common`
(C1 dedup, Sez. 165); tady zůstává jen barevná maska + template renderer + parametry.
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from points_common import run_simple_detector


Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "task_isom_scan.png"
DEFAULT_OUT = HERE / "vegetation_points_poc"
TARGET_CODES = ("417", "418", "419")
CODE_NAMES = {
    "417": "Prominent large tree",
    "418": "Prominent bush or tree",
    "419": "Prominent vegetation feature: x",
}


def _green_mask(arr: np.ndarray, green_min: int, red_max: int, blue_max: int,
                green_red_diff: int, green_blue_diff: int) -> np.ndarray:
    """Maska tmavší zelené symbolové kresby; světlé plošné výplně se snaží nebrat."""
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    return (
        (g >= green_min)
        & (r <= red_max)
        & (b <= blue_max)
        & ((g - r) >= green_red_diff)
        & ((g - b) >= green_blue_diff)
    )


def _ellipse_template(size: int, bbox: list[int], *, fill: bool, width: int = 4) -> np.ndarray:
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    if fill:
        draw.ellipse(bbox, fill=255)
    else:
        for offset in range(width):
            draw.ellipse(
                [bbox[0] + offset, bbox[1] + offset, bbox[2] - offset, bbox[3] - offset],
                outline=255,
            )
    return np.asarray(img) > 0


def _cross_template(size: int, margin: int, width: int) -> np.ndarray:
    """Diagonální X (419 Prominent vegetation feature) — dvě úhlopříčky daného marginu/tloušťky."""
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    draw.line([margin, margin, size - margin, size - margin], fill=255, width=width)
    draw.line([margin, size - margin, size - margin, margin], fill=255, width=width)
    return np.asarray(img) > 0


def _render_template(code: str) -> np.ndarray:
    """Vyrenderuje jednoduchý shape template pro 417/418/419 a ořízne neprázdný bbox."""
    size = 64
    if code == "417":
        mask = _ellipse_template(size, [16, 16, 48, 48], fill=False, width=5)
    elif code == "418":
        mask = _ellipse_template(size, [20, 20, 44, 44], fill=True)
    elif code == "419":
        mask = _cross_template(size, margin=14, width=5)   # zelený X (mirror gen render, Sez. 136)
    else:
        raise RuntimeError(f"Nepodporovany vegetation-point symbol {code}")

    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise RuntimeError(f"Symbol {code} se nepodarilo vyrenderovat")
    x0, x1 = max(0, xs.min() - 1), min(mask.shape[1], xs.max() + 2)
    y0, y1 = max(0, ys.min() - 1), min(mask.shape[0], ys.max() + 2)
    return mask[y0:y1, x0:x1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-dim", type=int, default=3000,
                        help="Volitelne zmenseni pro zpracovani; 0 = plne rozliseni.")
    parser.add_argument("--green-min", type=int, default=90)
    parser.add_argument("--red-max", type=int, default=125)
    parser.add_argument("--blue-max", type=int, default=145)
    parser.add_argument("--green-red-diff", type=int, default=35)
    parser.add_argument("--green-blue-diff", type=int, default=10)
    parser.add_argument("--score-threshold", type=float, default=0.55)
    parser.add_argument("--min-size", type=int, default=5)
    parser.add_argument("--max-size", type=int, default=60)
    parser.add_argument("--min-area", type=int, default=10)
    parser.add_argument("--max-area", type=int, default=1400)
    parser.add_argument("--min-fill", type=float, default=0.10)
    parser.add_argument("--max-fill", type=float, default=0.85)
    parser.add_argument("--max-aspect", type=float, default=1.8)
    parser.add_argument("--close-px", type=int, default=1)
    parser.add_argument("--max-per-code", type=int, default=300)
    args = parser.parse_args(argv)

    if not args.input.exists():
        raise SystemExit(f"Chybi vstupni sken: {args.input}")

    templates = {code: _render_template(code) for code in TARGET_CODES}
    return run_simple_detector(
        args,
        mask_fn=lambda arr: _green_mask(arr, args.green_min, args.red_max, args.blue_max,
                                        args.green_red_diff, args.green_blue_diff),
        mask_name="green_mask.png",
        mask_stat_prefix="green",
        templates=templates,
        target_codes=TARGET_CODES,
        code_names=CODE_NAMES,
        parameters={
            "green_min": args.green_min,
            "red_max": args.red_max,
            "blue_max": args.blue_max,
            "green_red_diff": args.green_red_diff,
            "green_blue_diff": args.green_blue_diff,
            "score_threshold": args.score_threshold,
            "min_size": args.min_size,
            "max_size": args.max_size,
            "min_area": args.min_area,
            "max_area": args.max_area,
            "min_fill": args.min_fill,
            "max_fill": args.max_fill,
            "max_aspect": args.max_aspect,
            "close_px": args.close_px,
            "max_per_code": args.max_per_code,
        },
        status="POC classic_cv 2026-06-20; needs visual/curated validation before generator use",
        doc="Detekce 417/418 ze zelene kresby skenu; vystup je review kandidat, ne GT.",
        overlay_name="vegetation_points_overlay.png",
        sheet_name="vegetation_points_contact_sheet.png",
        overlay_colors={"417": (255, 0, 255), "418": (0, 120, 255), "419": (255, 140, 0)},
        sheet_kwargs={"limit": 72, "tile": 150, "label_h": 24, "font_size": 12,
                      "half_min": 40, "half_extra": 28},
        component_kwargs={
            "min_size": args.min_size, "max_size": args.max_size,
            "min_area": args.min_area, "max_area": args.max_area,
            "min_fill": args.min_fill, "max_fill": args.max_fill,
            "close_px": args.close_px, "max_aspect": args.max_aspect,
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
