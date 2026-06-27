#!/usr/bin/env python3
r"""Classic-CV PoC pro bodové balvany 204/205/204.5 ze skenu (jedna třída "boulder").

ISOM 204 Boulder / 205 Large boulder / 204.5 (different size) jsou TÝŽ tvar — plný
černý kruh (disk), liší se jen VELIKOSTÍ. Classic-CV je detekuje jako JEDNU rodinu
"boulder" (emit kód 204); velikostní podtřídění 204 vs 205 je relativní (paměť
isom-point-discriminators-classic-cv) -> strop CV, necháno na ML rekonstruktor.
Skórujeme proti SJEDNOCENÉ ruční GT 204/205/204.5 (score_boulder.py).

Diskriminátor disku od černé srázové/liniové kresby (202 cliff) na skalnaté mapě
(hlavní FP zdroj — viz contact sheet Branžeže):
  - vysoký fill (plný disk ~0,5-0,8 vs tenká linie ~0,1-0,3),
  - nízká excentricita (kruh ~0 vs úsečka ->1),
  - malá kompaktní velikost (bod, ne souvislá kresba).

Sdílená mašinérie (font/resize/shape-match/komponenty/payload/vizualizace) žije
v `points_common` (jako manmade/terrain). Tady jen barevná maska + disk template + parametry.

Použití:
  python isom_scan/boulder_points_poc.py
  python isom_scan/boulder_points_poc.py --input isom_scan/task_isom_scan.png --out-dir temp/boulder_bransez
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from points_common import run_simple_detector

# Lokální mapové skeny mohou být obří PNG (stovky MPx), ale jsou to naše vstupy,
# ne nedůvěryhodný upload (izomorf manmade_points_poc).
Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent

DEFAULT_INPUT = HERE / "task_isom_scan.png"
DEFAULT_OUT = HERE / "boulder_points_poc"
# Rodina se emituje pod jedním kódem (reprezentant 204); GT 205/204.5 se sjednotí ve skórování.
TARGET_CODES = ("204",)


def _black_neutral_mask(arr: np.ndarray, dark_max: int, neutral_spread: int) -> np.ndarray:
    """Maska černé kresby: tmavé a barevně neutrální pixely.

    DRY pozn.: identická s manmade_points_poc._black_neutral_mask (2. konzument). Extrahovat
    do points_common až s 3. konzumentem (pravidlo „extrahovat až 3. konzument", audit D9)."""
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    return (mx < dark_max) & ((mx - mn) < neutral_spread)


def _render_disk_template() -> np.ndarray:
    """Plný kruh (ISOM 204/205 boulder) jako referenční tvar pro shape_f1.

    Velikost je libovolná — shape_f1 šablonu přeškáluje na bbox komponenty. Disk dává shape_f1
    ~1 pro plný balvan a nízko pro tenkou srázovou kresbu (komplementární k fill/ecc filtrům)."""
    size = 48
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((4, 4, size - 5, size - 5), fill=255)
    arr = np.asarray(mask) > 0
    ys, xs = np.where(arr)
    return arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-dim", type=int, default=0,
                        help="Volitelne zmenseni pro zpracovani; 0 = plne rozliseni.")
    parser.add_argument("--dark-max", type=int, default=130)
    parser.add_argument("--neutral-spread", type=int, default=18)
    parser.add_argument("--score-threshold", type=float, default=0.60)
    # Velikost disku na plnem rozliseni Branzeze (1655x1868): 204 ~6-10 px, 205 ~10-16 px.
    parser.add_argument("--min-size", type=int, default=4)
    parser.add_argument("--max-size", type=int, default=18)
    parser.add_argument("--min-area", type=int, default=12)
    parser.add_argument("--max-area", type=int, default=230)
    # Klic: plny disk => VYSOKY fill (oproti manmade tenkym glyfum s max_fill 0.48).
    parser.add_argument("--min-fill", type=float, default=0.45)
    parser.add_argument("--max-fill", type=float, default=0.95)
    parser.add_argument("--max-eccentricity", type=float, default=0.72,
                        help="Kruh ~0, usecka ->1; odfiltruje protahle srazove fragmenty.")
    parser.add_argument("--close-px", type=int, default=1)
    parser.add_argument("--open-px", type=int, default=0)
    parser.add_argument("--max-per-code", type=int, default=200)
    args = parser.parse_args(argv)

    if not args.input.exists():
        raise SystemExit(f"Chybi vstupni sken: {args.input}")

    templates = {"204": _render_disk_template()}
    return run_simple_detector(
        args,
        mask_fn=lambda arr: _black_neutral_mask(arr, args.dark_max, args.neutral_spread),
        mask_name="black_neutral_mask.png",
        mask_stat_prefix="black",
        templates=templates,
        target_codes=TARGET_CODES,
        code_names={"204": "Boulder (204/205/204.5 sjednoceno)"},
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
            "max_eccentricity": args.max_eccentricity,
            "close_px": args.close_px,
            "open_px": args.open_px,
            "max_per_code": args.max_per_code,
        },
        status="POC classic_cv 2026-06-27; needs visual/curated validation before generator use",
        doc="Detekce balvanu 204/205/204.5 (jedna trida) z neutral-black disku skenu; "
            "pseudo fallback generatoru se tim zatim nenahrazuje.",
        overlay_name="boulder_points_overlay.png",
        sheet_name="boulder_points_contact_sheet.png",
        overlay_colors={"204": (220, 20, 60)},
        sheet_kwargs={"limit": 60, "tile": 160, "label_h": 24, "font_size": 13,
                      "half_min": 35, "half_extra": 25},
        component_kwargs={
            "min_size": args.min_size, "max_size": args.max_size,
            "min_area": args.min_area, "max_area": args.max_area,
            "min_fill": args.min_fill, "max_fill": args.max_fill,
            "close_px": args.close_px, "open_px": args.open_px,
            "max_eccentricity": args.max_eccentricity,
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
