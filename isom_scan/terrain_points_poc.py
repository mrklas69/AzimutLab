#!/usr/bin/env python3
r"""Classic-CV PoC pro hnědé terrain-point symboly ze skenu.

Použití:
  python isom_scan/terrain_points_poc.py --input "maps/Buschdörfl/bg_scan.png" --out-dir temp/terrain_points_buschdorfl --max-dim 3000

Výstup je kandidátní diagnostika, ne GT. Hnědá kresba obsahuje i vrstevnice, proto
skript pouze hledá malé izolované komponenty podobné vybraným bodovým symbolům.
Ruční review je nutné.

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
DEFAULT_OUT = HERE / "terrain_points_poc"
DEFAULT_CODES = ("111", "112", "115")
CODE_NAMES = {
    "109": "Small knoll",
    "111": "Small depression",
    "112": "Pit",
    "115": "Prominent landform feature",
}


def _brown_mask(arr: np.ndarray, red_min: int, red_green_diff: int,
                green_max: int, blue_max: int) -> np.ndarray:
    """Maska hnědé kresby: oranžovo-hnědé pixely vrstevnic a terrain-point značek."""
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    return (r >= red_min) & ((r - g) >= red_green_diff) & (g <= green_max) & (b <= blue_max)


def _poly_mask(points: list[tuple[int, int]], size: int = 64) -> np.ndarray:
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    draw.polygon(points, fill=255)
    return np.asarray(img) > 0


def _line_mask(points: list[tuple[int, int]], width: int = 5, size: int = 64) -> np.ndarray:
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    draw.line(points, fill=255, width=width, joint="curve")
    return np.asarray(img) > 0


def _render_template(code: str) -> np.ndarray:
    """Vyrenderuje zjednodušený tvar podle OOM symbol definition a ořízne bbox."""
    if code == "109":
        mask = Image.new("L", (64, 64), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([22, 22, 42, 42], fill=255)
        mask = np.asarray(mask) > 0
    elif code == "111":
        # OOM coords tvoří spodní oblouk otevřený nahoru; polyline stačí pro shape-match.
        mask = _line_mask([(48, 17), (48, 28), (40, 40), (32, 40), (24, 40), (16, 28), (16, 17)])
    elif code == "112":
        # Pit je vyplněný hnědý klín; tvar odpovídá template coords 231/-453 ... 0/734 ...
        mask = _poly_mask([(38, 15), (50, 15), (32, 52), (14, 15), (26, 15), (32, 31)])
    elif code == "115":
        # Prominent landform feature je hnědý trojúhelník bez výplně.
        mask = _line_mask([(17, 42), (47, 42), (32, 15), (17, 42)], width=5)
    else:
        raise RuntimeError(f"Nepodporovany terrain-point symbol {code}")

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
    parser.add_argument("--codes", default=",".join(DEFAULT_CODES),
                        help="Čárkou oddělené ISOM kódy, např. 109 nebo 111,112,115.")
    parser.add_argument("--brown-red-min", type=int, default=110)
    parser.add_argument("--brown-red-green-diff", type=int, default=28)
    parser.add_argument("--brown-green-max", type=int, default=170)
    parser.add_argument("--brown-blue-max", type=int, default=140)
    parser.add_argument("--score-threshold", type=float, default=0.50)
    parser.add_argument("--min-size", type=int, default=3)
    parser.add_argument("--max-size", type=int, default=42)
    parser.add_argument("--min-area", type=int, default=6)
    parser.add_argument("--max-area", type=int, default=900)
    parser.add_argument("--min-fill", type=float, default=0.05)
    parser.add_argument("--max-fill", type=float, default=0.75)
    parser.add_argument("--close-px", type=int, default=0)
    parser.add_argument("--max-per-code", type=int, default=80)
    args = parser.parse_args(argv)
    target_codes = tuple(code.strip() for code in args.codes.split(",") if code.strip())
    unsupported = [code for code in target_codes if code not in CODE_NAMES]
    if unsupported:
        raise SystemExit(f"Nepodporovane terrain-point kody: {unsupported}")
    if not target_codes:
        raise SystemExit("Musis zadat aspon jeden kod pres --codes")

    if not args.input.exists():
        raise SystemExit(f"Chybi vstupni sken: {args.input}")

    templates = {code: _render_template(code) for code in target_codes}
    return run_simple_detector(
        args,
        mask_fn=lambda arr: _brown_mask(arr, args.brown_red_min, args.brown_red_green_diff,
                                        args.brown_green_max, args.brown_blue_max),
        mask_name="brown_mask.png",
        mask_stat_prefix="brown",
        templates=templates,
        target_codes=target_codes,
        code_names=CODE_NAMES,
        parameters={
            "brown_red_min": args.brown_red_min,
            "brown_red_green_diff": args.brown_red_green_diff,
            "brown_green_max": args.brown_green_max,
            "brown_blue_max": args.brown_blue_max,
            "codes": list(target_codes),
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
        status="POC classic_cv 2026-06-20; needs visual/curated validation before generator use",
        doc="Detekce hnedych terrain-point symbolu ze skenu; vystup je review kandidat, ne GT.",
        overlay_name="terrain_points_overlay.png",
        sheet_name="terrain_points_contact_sheet.png",
        overlay_colors={"109": (255, 80, 0), "111": (255, 0, 255), "112": (0, 140, 255), "115": (120, 20, 220)},
        sheet_kwargs={"limit": 48, "tile": 160, "label_h": 24, "font_size": 13,
                      "half_min": 45, "half_extra": 30},
        component_kwargs={
            "min_size": args.min_size, "max_size": args.max_size,
            "min_area": args.min_area, "max_area": args.max_area,
            "min_fill": args.min_fill, "max_fill": args.max_fill, "close_px": args.close_px,
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
