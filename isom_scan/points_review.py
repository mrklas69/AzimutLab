#!/usr/bin/env python3
"""Vytvoří review manifest pro kuraci bodových scan-mining kandidátů.

Použití:
  python isom_scan/points_review.py --detections temp/manmade_points_bedrichovka/detections.json

Generický nástroj — funguje na `detections.json` z LIBOVOLNÉHO `*_points_poc` detektoru
(water/terrain/vegetation/manmade), ne jen man-made (dřív se jmenoval `manmade_points_review`,
audit Sez. 165 misnomer). Z PoC `detections.json` vyrobí:
  - `review_manifest.json` se stabilními kandidáty a review polem
  - `review_sheet.png` pro rychlou kontrolu očima
  - `crops/*.png` jednotlivé výřezy

Záměrně NErozhoduje TP/FP automaticky. Kurátor do manifestu doplní `review.verdict`
(`tp` / `fp` / `ignore`) a případně `review.true_code`. Při opakovaném spuštění
skript zachová existující review rozhodnutí podle stabilního `id`.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from points_common import REVIEW_VALUES, candidate_id, crop_box, load_font, resolve_existing_path, sha256


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_DETECTIONS = HERE / "manmade_points_poc" / "detections.json"

# Lokální mapové skeny mohou být velké. Jsou to naše vstupy, ne nedůvěryhodný upload.
Image.MAX_IMAGE_PIXELS = None


def _resolve_image_path(payload: dict[str, Any], override: Path | None) -> Path:
    """Najde sken z override nebo z `detections.json`; bez skenu selže nahlas."""
    raw = override if override is not None else Path(str(payload.get("image", "")))
    return resolve_existing_path(raw, [REPO_ROOT])


def _iter_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Zploští `detections[].points[]` na kandidáty se stabilním id."""
    out: list[dict[str, Any]] = []
    for det in payload.get("detections", []):
        pred_code = str(det.get("code", ""))
        pred_name = str(det.get("name", ""))
        for point in det.get("points", []):
            x = float(point["x"])
            y = float(point["y"])
            score = float(point.get("score", 0.0))
            out.append({
                "id": candidate_id(pred_code, x, y),
                "pred_code": pred_code,
                "pred_name": pred_name,
                "score": round(score, 3),
                "center": {"x": round(x, 1), "y": round(y, 1)},
                "bbox": [round(float(v), 1) for v in point.get("bbox", [])],
                "review": {
                    "verdict": "unreviewed",
                    "true_code": None,
                    "note": "",
                },
            })
    out.sort(key=lambda item: (item["pred_code"], -item["score"], item["center"]["y"], item["center"]["x"]))
    return out


def _load_existing_reviews(out_dir: Path) -> dict[str, dict[str, Any]]:
    """Načte ruční verdikty z předchozího manifestu, aby je rerun nesmazal."""
    manifest_path = out_dir / "review_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Existujici review manifest nejde nacist: {manifest_path}: {exc}") from exc

    reviews: dict[str, dict[str, Any]] = {}
    for candidate in payload.get("candidates", []):
        candidate_key = str(candidate.get("id", ""))
        review = candidate.get("review", {})
        if candidate_key and isinstance(review, dict):
            reviews[candidate_key] = review
    return reviews


def _preserve_existing_reviews(candidates: list[dict[str, Any]],
                               existing_reviews: dict[str, dict[str, Any]]) -> int:
    """Přenese staré review do nově sestavených kandidátů podle stabilního `id`."""
    kept = 0
    for candidate in candidates:
        old_review = existing_reviews.get(str(candidate["id"]))
        if old_review is None:
            continue
        # Necháme nové default klíče a přes ně vrátíme ruční hodnoty včetně případných poznámek.
        candidate["review"].update(old_review)
        kept += 1
    return kept


def _review_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Spočítá stav kurace; neznámé verdikty ukáže zvlášť místo tichého schování."""
    counts: dict[str, int] = {value: 0 for value in REVIEW_VALUES}
    unknown: dict[str, int] = {}
    for candidate in candidates:
        verdict = str(candidate.get("review", {}).get("verdict", "unreviewed"))
        if verdict in counts:
            counts[verdict] += 1
        else:
            unknown[verdict] = unknown.get(verdict, 0) + 1
    return {
        "total": len(candidates),
        **counts,
        "unknown": unknown,
    }


def _candidate_crop(img: Image.Image, candidate: dict[str, Any], crop_px: int) -> Image.Image:
    crop = img.crop(crop_box(candidate, img, crop_px)).convert("RGB")
    draw = ImageDraw.Draw(crop)
    # Středový kříž ukazuje kandidáta i v rušném mapovém okolí.
    cx, cy = crop.width // 2, crop.height // 2
    draw.line([(cx - 10, cy), (cx + 10, cy)], fill=(255, 0, 255), width=2)
    draw.line([(cx, cy - 10), (cx, cy + 10)], fill=(255, 0, 255), width=2)
    return crop


def _write_crops(img: Image.Image, candidates: list[dict[str, Any]], out_dir: Path, crop_px: int) -> None:
    crop_dir = out_dir / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        crop = _candidate_crop(img, candidate, crop_px)
        crop_path = crop_dir / f"{candidate['id']}.png"
        crop.save(crop_path)
        candidate["crop"] = str(crop_path.relative_to(out_dir))


def _write_sheet(img: Image.Image, candidates: list[dict[str, Any]], out_path: Path,
                 crop_px: int, max_items: int) -> None:
    chosen = candidates[:max_items]
    if not chosen:
        Image.new("RGB", (480, 80), "white").save(out_path)
        return
    tile = 180
    label_h = 38
    cols = min(5, len(chosen))
    rows = math.ceil(len(chosen) / cols)
    sheet = Image.new("RGB", (cols * tile, rows * (tile + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = load_font(12)
    for i, candidate in enumerate(chosen):
        row, col = divmod(i, cols)
        crop = _candidate_crop(img, candidate, crop_px).resize((tile, tile), Image.Resampling.BILINEAR)
        px = col * tile
        py = row * (tile + label_h)
        sheet.paste(crop, (px, py))
        label = f"{candidate['id']}  s={candidate['score']:.2f}"
        draw.text((px + 4, py + tile + 4), label, fill=(0, 0, 0), font=font)
    sheet.save(out_path)


def _manifest(payload: dict[str, Any], detections_path: Path, image_path: Path,
              candidates: list[dict[str, Any]]) -> dict[str, Any]:
    codes = [str(det.get("code", "")) for det in payload.get("detections", []) if det.get("code") is not None]
    return {
        "_status": "REVIEW_REQUIRED",
        "_doc": (
            "Rucni kurace point kandidatu. Vypln review.verdict jako "
            "tp/fp/ignore; true_code nech null, pokud pred_code sedi."
        ),
        "source_detections": str(detections_path),
        "source_status": payload.get("_status", ""),
        "image": str(image_path),
        "image_sha256": sha256(image_path),
        "codes": codes,
        "review_values": list(REVIEW_VALUES),
        "review_summary": _review_summary(candidates),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--detections", type=Path, default=DEFAULT_DETECTIONS)
    parser.add_argument("--image", type=Path, default=None,
                        help="Volitelne prepsani image cesty z detections.json.")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Default: adresar vedle detections.json / review.")
    parser.add_argument("--crop-px", type=int, default=180)
    parser.add_argument("--max-sheet-items", type=int, default=80)
    args = parser.parse_args()

    if not args.detections.exists():
        raise SystemExit(f"Chybi detections.json: {args.detections}")
    payload = json.loads(args.detections.read_text(encoding="utf-8"))
    image_path = _resolve_image_path(payload, args.image)
    out_dir = args.out_dir or (args.detections.parent / "review")
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(image_path).convert("RGB")
    candidates = _iter_candidates(payload)
    preserved = _preserve_existing_reviews(candidates, _load_existing_reviews(out_dir))
    _write_crops(img, candidates, out_dir, args.crop_px)
    _write_sheet(img, candidates, out_dir / "review_sheet.png", args.crop_px, args.max_sheet_items)
    manifest = _manifest(payload, args.detections.resolve(), image_path, candidates)
    (out_dir / "review_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "candidates": len(candidates),
        "preserved_reviews": preserved,
        "review_summary": manifest["review_summary"],
        "out_dir": str(out_dir),
        "manifest": str(out_dir / "review_manifest.json"),
        "sheet": str(out_dir / "review_sheet.png"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
