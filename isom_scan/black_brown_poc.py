#!/usr/bin/env python3
"""Black-vs-brown PoC pro ISOM-scan benchmark.

Vytěží trik z běhu ChatGPT 5.5: neutrálně tmavé pixely
`max(rgb) < 130 && max(rgb)-min(rgb) < 18` oddělují černou kresbu od hnědých
vrstevnic. Skript ukládá diagnostické masky a contact sheet pro rychlý vizuální
verify; nevstupuje do tréninkové pipeline.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "task_isom_scan.png"
DEFAULT_OUT = HERE / "black_brown_poc"


def save_mask(mask: np.ndarray, path: Path) -> None:
    Image.fromarray((mask.astype(np.uint8) * 255), mode="L").save(path)


def colorize(base: np.ndarray, mask: np.ndarray, color: tuple[int, int, int]) -> Image.Image:
    out = base.copy()
    out[mask] = (0.35 * out[mask] + 0.65 * np.array(color)).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")


def crop_sheet(img: Image.Image, mask: np.ndarray, out_path: Path) -> None:
    """Contact sheet nejhustších výřezů; oko rychle řekne, jestli maska trefuje černou."""
    tile = 256
    step = 192
    arr = np.asarray(img.convert("RGB"))
    candidates = []
    h, w = mask.shape
    for y in range(0, max(1, h - tile + 1), step):
        for x in range(0, max(1, w - tile + 1), step):
            sub = mask[y : y + tile, x : x + tile]
            candidates.append((int(sub.sum()), x, y))
    candidates.sort(reverse=True)
    chosen = candidates[:12]

    cols = 4
    rows = (len(chosen) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * (tile + 24)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, (count, x, y) in enumerate(chosen):
        r, c = divmod(i, cols)
        crop = arr[y : y + tile, x : x + tile].copy()
        submask = mask[y : y + tile, x : x + tile]
        crop[submask] = (255, 0, 255)
        px = c * tile
        py = r * (tile + 24)
        sheet.paste(Image.fromarray(crop, mode="RGB"), (px, py))
        draw.text((px + 4, py + tile + 4), f"x{x} y{y} n={count}", fill=(0, 0, 0), font=font)
    sheet.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dark-max", type=int, default=130)
    ap.add_argument("--neutral-spread", type=int, default=18)
    ap.add_argument("--brown-red-min", type=int, default=120)
    ap.add_argument("--brown-red-green-diff", type=int, default=45)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(args.input).convert("RGB")
    arr = np.asarray(img)
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    spread = mx - mn

    black = (mx < args.dark_max) & (spread < args.neutral_spread)
    # Jednoduchá hnědá reference: tmavší oranžovo-hnědé vrstevnice mají vysoký R a R-G rozdíl.
    brown = (
        (arr[:, :, 0] >= args.brown_red_min)
        & ((arr[:, :, 0].astype(np.int16) - arr[:, :, 1].astype(np.int16)) >= args.brown_red_green_diff)
        & (arr[:, :, 1] < 140)
        & (arr[:, :, 2] < 100)
    )

    save_mask(black, args.out_dir / "black_neutral_mask.png")
    save_mask(brown, args.out_dir / "brown_reference_mask.png")
    colorize(arr, black, (255, 0, 255)).save(args.out_dir / "black_overlay.png")
    colorize(arr, brown, (0, 255, 255)).save(args.out_dir / "brown_overlay.png")
    both = arr.copy()
    both[brown] = (0.35 * both[brown] + 0.65 * np.array((0, 255, 255))).astype(np.uint8)
    both[black] = (0.35 * both[black] + 0.65 * np.array((255, 0, 255))).astype(np.uint8)
    Image.fromarray(both, mode="RGB").save(args.out_dir / "black_vs_brown_overlay.png")
    crop_sheet(img, black, args.out_dir / "black_dense_contact_sheet.png")

    stats = {
        "input": str(args.input),
        "size": {"w": img.width, "h": img.height},
        "dark_max": args.dark_max,
        "neutral_spread": args.neutral_spread,
        "black_px": int(black.sum()),
        "black_share": round(float(black.mean()), 6),
        "brown_px": int(brown.sum()),
        "brown_share": round(float(brown.mean()), 6),
        "overlap_px": int((black & brown).sum()),
    }
    (args.out_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"Výstupy: {args.out_dir}")


if __name__ == "__main__":
    main()
