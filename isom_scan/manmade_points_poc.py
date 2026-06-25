#!/usr/bin/env python3
r"""Classic-CV PoC pro man-made bodové symboly 525/527/531 ze skenu.

Použití:
  python isom_scan/manmade_points_poc.py
  python isom_scan/manmade_points_poc.py --input "resources/Soví vrch.png" --out-dir temp/manmade_points_sovi --max-dim 1800

Výstup je diagnostika, ne finální mapper-scan pravda. Detektor hledá malé izolované
černé komponenty a porovnává jejich tvar s renderem stejných symbolů z generatoru.
Když chybí lokální sken, skript selže nahlas.

Sdílená mašinérie (font/resize/shape-match/komponenty/payload/vizualizace) žije v `points_common`
(C1 dedup, Sez. 165); tady zůstává jen barevná maska + template renderer + parametry.
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from points_common import run_simple_detector


# Lokální mapové skeny mohou být obří PNG (stovky MPx), ale jsou to naše vstupy,
# ne nedůvěryhodný upload. Bez toho PIL odmítne např. resources/Soví vrch.png.
Image.MAX_IMAGE_PIXELS = None

import sys

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

    templates = {code: _render_template(code) for code in TARGET_CODES}
    return run_simple_detector(
        args,
        mask_fn=lambda arr: _black_neutral_mask(arr, args.dark_max, args.neutral_spread),
        mask_name="black_neutral_mask.png",
        mask_stat_prefix="black",
        templates=templates,
        target_codes=TARGET_CODES,
        code_names={code: LANDMARK_NAME[int(code)] for code in TARGET_CODES},
        parameters={
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
        status="POC classic_cv 2026-06-19; needs visual/curated validation before generator use",
        doc="Detekce 525/527/531 z neutral-black komponent skenu; pseudo fallback generatoru se tim zatim nenahrazuje.",
        overlay_name="manmade_points_overlay.png",
        sheet_name="manmade_points_contact_sheet.png",
        overlay_colors={"525": (0, 120, 255), "527": (220, 20, 60), "531": (120, 40, 200)},
        sheet_kwargs={"limit": 36, "tile": 160, "label_h": 24, "font_size": 13,
                      "half_min": 35, "half_extra": 25},
        component_kwargs={
            "min_size": args.min_size, "max_size": args.max_size,
            "min_area": args.min_area, "max_area": args.max_area,
            "min_fill": args.min_fill, "max_fill": args.max_fill, "close_px": args.close_px,
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
