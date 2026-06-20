#!/usr/bin/env python3
r"""Classic-CV PoC pro hnědé terrain-point symboly ze skenu.

Použití:
  python isom_scan/terrain_points_poc.py --input "maps/Buschdörfl/bg_scan.png" --out-dir temp/terrain_points_buschdorfl --max-dim 3000

Výstup je kandidátní diagnostika, ne GT. Hnědá kresba obsahuje i vrstevnice, proto
skript pouze hledá malé izolované komponenty podobné vybraným bodovým symbolům.
Ruční review je nutné.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi


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


@dataclass(frozen=True)
class Candidate:
    """Jedna hnědá komponenta klasifikovaná podle nejlepšího terrain-point tvaru."""

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
    """Vybere malé hnědé komponenty; dlouhé vrstevnice a plošné šrafy nechá mimo."""
    label_mask = mask
    if args.close_px > 0:
        structure = np.ones((3, 3), dtype=bool)
        label_mask = ndi.binary_closing(mask, structure=structure, iterations=args.close_px)
    labels, _ = ndi.label(label_mask)
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


def _classify(mask: np.ndarray, scale: float, args: argparse.Namespace,
              target_codes: tuple[str, ...]) -> tuple[list[Candidate], dict[str, object]]:
    templates = {code: _render_template(code) for code in target_codes}
    code_order = {code: i for i, code in enumerate(target_codes)}
    candidates: list[Candidate] = []
    raw_components = _component_candidates(mask, args)

    for sy, sx in raw_components:
        component = mask[sy, sx]
        scores = {code: _shape_f1(component, tmpl) for code, tmpl in templates.items()}
        code, score = max(scores.items(), key=lambda item: (item[1], -code_order[item[0]]))
        if score < args.score_threshold:
            continue

        ys, xs = np.where(component)
        x0 = (sx.start + float(xs.min())) / scale
        y0 = (sy.start + float(ys.min())) / scale
        x1 = (sx.start + float(xs.max()) + 1.0) / scale
        y1 = (sy.start + float(ys.max()) + 1.0) / scale
        candidates.append(Candidate(
            code=code,
            score=float(score),
            x=(x0 + x1) / 2.0,
            y=(y0 + y1) / 2.0,
            bbox=(x0, y0, x1, y1),
            area_px=int(component.sum()),
            fill=int(component.sum()) / max(1, component.shape[0] * component.shape[1]),
        ))

    candidates.sort(key=lambda c: (c.code, -c.score, c.y, c.x))
    capped: list[Candidate] = []
    for code in target_codes:
        capped.extend([c for c in candidates if c.code == code][: args.max_per_code])

    stats = {
        "raw_components": len(raw_components),
        "kept_total": len(capped),
        "kept_by_code": {code: sum(1 for c in capped if c.code == code) for code in target_codes},
        "templates": {code: {"w": int(t.shape[1]), "h": int(t.shape[0]), "px": int(t.sum())}
                      for code, t in templates.items()},
    }
    return capped, stats


def _detections_payload(candidates: list[Candidate], image_path: Path, image_size: tuple[int, int],
                        scale: float, args: argparse.Namespace, stats: dict[str, object],
                        target_codes: tuple[str, ...]) -> dict[str, object]:
    detections = []
    for code in target_codes:
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
            "name": CODE_NAMES[code],
            "geom": "point",
            "count": len(pts),
            "points": pts,
            "confidence": round(float(np.mean([p["score"] for p in pts])) if pts else 0.0, 3),
        })

    return {
        "_status": "POC classic_cv 2026-06-20; needs visual/curated validation before generator use",
        "_doc": "Detekce hnedych terrain-point symbolu ze skenu; vystup je review kandidat, ne GT.",
        "image": str(image_path),
        "image_size": {"w": image_size[0], "h": image_size[1]},
        "processing_scale": scale,
        "parameters": {
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
        "stats": stats,
        "detections": detections,
    }


def _draw_overlay(img: Image.Image, candidates: list[Candidate], out_path: Path) -> None:
    colors = {"109": (255, 80, 0), "111": (255, 0, 255), "112": (0, 140, 255), "115": (120, 20, 220)}
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


def _contact_sheet(img: Image.Image, candidates: list[Candidate], out_path: Path, limit: int = 48) -> None:
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
        half = max(45, (max(x1 - x0, y1 - y0) / 2) + 30)
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

    args.out_dir.mkdir(parents=True, exist_ok=True)
    original = Image.open(args.input).convert("RGB")
    proc, scale = _resize_for_processing(original, args.max_dim)
    arr = np.asarray(proc)
    brown = _brown_mask(arr, args.brown_red_min, args.brown_red_green_diff,
                        args.brown_green_max, args.brown_blue_max)
    candidates, stats = _classify(brown, scale, args, target_codes)
    payload = _detections_payload(candidates, args.input, original.size, scale, args, stats, target_codes)

    (args.out_dir / "detections.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.out_dir / "stats.json").write_text(
        json.dumps({"brown_px_proc": int(brown.sum()), "brown_share_proc": float(brown.mean()), **stats},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _save_mask(brown, args.out_dir / "brown_mask.png")
    _draw_overlay(original, candidates, args.out_dir / "terrain_points_overlay.png")
    _contact_sheet(original, candidates, args.out_dir / "terrain_points_contact_sheet.png")

    print(json.dumps(payload["stats"], ensure_ascii=False, indent=2))
    print(f"Výstupy: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
