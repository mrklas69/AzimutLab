#!/usr/bin/env python3
r"""Exportuje scan-mining bodové kandidáty do pracovní `.omap` kopie.

Použití:
  python isom_scan/points_omap.py --detections temp/manmade_points_buschdorfl/detections.json --map "maps/Buschdörfl/Buschdörfl.omap" --out temp/manmade_points_buschdorfl/Buschdörfl_candidates.omap
  python isom_scan/points_omap.py --review temp/manmade_points_buschdorfl/review/review_manifest.json --include-unreviewed --map "maps/Buschdörfl/Buschdörfl.omap" --out temp/manmade_points_buschdorfl/Buschdörfl_candidates.omap

Skript nepřepisuje zdrojovou mapu. Přidá bodové objekty do kopie, aby šly kandidáty
zkontrolovat v OOM/OCAD nad stejným `bg_scan.png` podkladem.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from points_common import REVIEW_VALUES, candidate_id, load_json, resolve_existing_path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

# Skeny jsou lokální projektová data, ne upload od cizího uživatele.
Image.MAX_IMAGE_PIXELS = None


def _image_size_from_payload(payload: dict[str, Any], source_path: Path) -> tuple[int, int]:
    """Vezme velikost z detections.json, případně ji ověří přímo z image souboru."""
    raw_size = payload.get("image_size", {})
    if isinstance(raw_size, dict) and "w" in raw_size and "h" in raw_size:
        return int(raw_size["w"]), int(raw_size["h"])

    image_raw = payload.get("image")
    if not image_raw:
        raise SystemExit(f"Detekce nemaji image_size ani image: {source_path}")
    image_path = resolve_existing_path(str(image_raw), [source_path.parent, REPO_ROOT])
    with Image.open(image_path) as img:
        return img.size


def _candidates_from_detections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Zploští PoC detections.json na stejný tvar kandidáta jako review manifest."""
    candidates: list[dict[str, Any]] = []
    for detection in payload.get("detections", []):
        pred_code = str(detection.get("code", ""))
        pred_name = str(detection.get("name", ""))
        for point in detection.get("points", []):
            x = float(point["x"])
            y = float(point["y"])
            candidates.append({
                "id": candidate_id(pred_code, x, y),
                "pred_code": pred_code,
                "pred_name": pred_name,
                "score": float(point.get("score", 0.0)),
                "center": {"x": x, "y": y},
                "review": {"verdict": "unreviewed", "true_code": None, "note": ""},
            })
    return candidates


def _load_input(args: argparse.Namespace) -> tuple[Path, list[dict[str, Any]], tuple[int, int], str]:
    """Načte buď raw detekce, nebo ručně kurátorovaný review manifest."""
    if args.detections is not None:
        payload = load_json(args.detections)
        return (
            args.detections.resolve(),
            _candidates_from_detections(payload),
            _image_size_from_payload(payload, args.detections),
            "detections",
        )

    manifest = load_json(args.review)
    candidates = list(manifest.get("candidates", []))
    source_raw = manifest.get("source_detections")
    if source_raw:
        source_path = resolve_existing_path(str(source_raw), [args.review.parent, REPO_ROOT])
        image_size = _image_size_from_payload(load_json(source_path), source_path)
    else:
        image_raw = manifest.get("image")
        if not image_raw:
            raise SystemExit(f"Review manifest nema source_detections ani image: {args.review}")
        image_path = resolve_existing_path(str(image_raw), [args.review.parent, REPO_ROOT])
        with Image.open(image_path) as img:
            image_size = img.size
    return args.review.resolve(), candidates, image_size, "review"


def _attrs(fragment: str) -> dict[str, str]:
    """Malý atributový parser pro generovaný OMAP XML; nechceme kvůli tomu měnit strukturu mapy."""
    return {m.group(1): m.group(2) for m in re.finditer(r'([A-Za-z_][\w:.-]*)="([^"]*)"', fragment)}


def _parse_symbol_ids(doc: str, required_codes: set[str]) -> dict[str, int]:
    """Vrátí první symbol id pro cílové ISOM kódy; id nelze odvozovat z kódu."""
    ids: dict[str, int] = {}
    for match in re.finditer(r"<symbol\b(?P<attrs>[^>]*)>", doc):
        attrs = _attrs(match.group("attrs"))
        code = attrs.get("code")
        sym_id = attrs.get("id")
        if code in required_codes and sym_id is not None:
            ids.setdefault(code, int(sym_id))
    missing = sorted(code for code in required_codes if code not in ids)
    if missing:
        raise SystemExit(f"Mapa postrada cilove symboly {missing}")
    return ids


def _scan_template_transform(doc: str, image_name: str) -> dict[str, float]:
    """Najde `bg_scan.png` template a vrátí px -> paper transformaci v OOM jednotkách."""
    template_re = re.compile(r"<template\b(?P<attrs>[^>]*)>.*?</template>", re.DOTALL)
    for match in template_re.finditer(doc):
        attrs = _attrs(match.group("attrs"))
        names = {attrs.get("name"), attrs.get("path"), attrs.get("relpath")}
        if attrs.get("type") != "TemplateImage" or image_name not in names:
            continue

        body = match.group(0)
        trans = re.search(r"<transformation\b(?P<attrs>[^>]*)/>", body)
        if trans is None:
            raise SystemExit(f"Template {image_name} nema aktivni transformation")
        trans_attrs = _attrs(trans.group("attrs"))
        if trans_attrs.get("role") != "active":
            raise SystemExit(f"Template {image_name} nema aktivni transformation jako prvni polozku")

        rotation = float(trans_attrs.get("rotation", "0"))
        if abs(rotation) > 1e-9:
            raise SystemExit(f"Template {image_name} ma rotaci {rotation}; export ji zatim nepodporuje")
        return {
            "x_mm": float(trans_attrs.get("x", "0")),
            "y_mm": float(trans_attrs.get("y", "0")),
            "scale_x_mm_per_px": float(trans_attrs["scale_x"]),
            "scale_y_mm_per_px": float(trans_attrs["scale_y"]),
        }
    raise SystemExit(f"Mapa neobsahuje TemplateImage {image_name}")


def _candidate_verdict(candidate: dict[str, Any]) -> str:
    return str(candidate.get("review", {}).get("verdict", "unreviewed"))


def _candidate_export_code(candidate: dict[str, Any]) -> str:
    review = candidate.get("review", {})
    true_code = review.get("true_code")
    if _candidate_verdict(candidate) == "tp" and true_code:
        return str(true_code)
    return str(candidate.get("pred_code", ""))


def _required_codes(candidates: list[dict[str, Any]]) -> set[str]:
    """Kódy, pro které musí mapa obsahovat symbol id."""
    codes: set[str] = set()
    for candidate in candidates:
        code = _candidate_export_code(candidate)
        if code:
            codes.add(code)
    if not codes:
        raise SystemExit("Vstup neobsahuje zadne kandidaty s kodem")
    return codes


def _selected_candidates(candidates: list[dict[str, Any]], source_kind: str,
                         args: argparse.Namespace) -> list[dict[str, Any]]:
    """Vybere kandidáty pro export; review manifest defaultně pouští jen TP."""
    selected: list[dict[str, Any]] = []
    for candidate in candidates:
        verdict = _candidate_verdict(candidate)
        if verdict == "tp":
            selected.append(candidate)
        elif verdict == "unreviewed" and (source_kind == "detections" or args.include_unreviewed):
            selected.append(candidate)
        elif verdict == "fp" and args.include_fp:
            selected.append(candidate)
        elif verdict == "ignore" and args.include_ignore:
            selected.append(candidate)
        elif verdict not in REVIEW_VALUES:
            raise SystemExit(f"Neznamy review.verdict u {candidate.get('id')}: {verdict}")
    return selected


def _pixel_to_paper_um(center: dict[str, Any], image_size: tuple[int, int],
                       transform: dict[str, float]) -> tuple[int, int]:
    """Převod px středu kandidáta na OOM paper µm podle centrovaného TemplateImage."""
    w, h = image_size
    x = float(center["x"])
    y = float(center["y"])
    paper_x = (transform["x_mm"] + (x - w / 2.0) * transform["scale_x_mm_per_px"]) * 1000.0
    paper_y = (transform["y_mm"] + (y - h / 2.0) * transform["scale_y_mm_per_px"]) * 1000.0
    return round(paper_x), round(paper_y)


def _candidate_objects(candidates: list[dict[str, Any]], image_size: tuple[int, int],
                       transform: dict[str, float], symbol_ids: dict[str, int]) -> tuple[list[str], dict[str, Any]]:
    objects: list[str] = []
    by_code: dict[str, int] = {}
    by_review: dict[str, int] = {}
    for candidate in candidates:
        code = _candidate_export_code(candidate)
        if code not in symbol_ids:
            raise SystemExit(f"Kandidat {candidate.get('id')} ma nepodporovany kod {code}")
        x, y = _pixel_to_paper_um(candidate["center"], image_size, transform)
        objects.append(f'<object type="0" symbol="{symbol_ids[code]}"><coords count="1">{x} {y};</coords></object>')
        by_code[code] = by_code.get(code, 0) + 1
        verdict = _candidate_verdict(candidate)
        by_review[verdict] = by_review.get(verdict, 0) + 1
    return objects, {"by_code": by_code, "by_review": by_review}


def _append_objects(doc: str, object_xml: list[str]) -> str:
    """Přidá objekty do jediné části mapy a aktualizuje `<objects count>`.

    Exportér je záměrně úzký pro naše generované `.omap`. Kdyby mapa měla víc částí,
    skript raději skončí, než aby kandidáty vložil do špatné vrstvy.
    """
    if not object_xml:
        return doc
    part_re = re.compile(
        r'(?P<head><part\b[^>]*>\s*<objects count=")(?P<count>\d+)(?P<after>">)'
        r"(?P<body>.*?)(?P<tail></objects></part>)",
        re.DOTALL,
    )
    matches = list(part_re.finditer(doc))
    if len(matches) != 1:
        raise SystemExit(f"Ocekavana je prave jedna <part><objects> cast, nalezeno: {len(matches)}")
    match = matches[0]
    new_count = int(match.group("count")) + len(object_xml)
    replacement = (
        f'{match.group("head")}{new_count}{match.group("after")}'
        f'{match.group("body")}{"".join(object_xml)}{match.group("tail")}'
    )
    return doc[:match.start()] + replacement + doc[match.end():]


def _remove_objects_by_symbol_ids(doc: str, symbol_ids: set[int]) -> tuple[str, int]:
    """Odstraní stávající objekty vybraných symbolů z jediné mapové části.

    Používá se pro scan-transfer update tam, kde generátor už kreslí pseudo objekty
    stejného kódu. Bez odstranění by kontrolní mapa míchala staré pseudo a nové scan
    kandidáty.
    """
    if not symbol_ids:
        return doc, 0
    part_re = re.compile(
        r'(?P<head><part\b[^>]*>\s*<objects count=")(?P<count>\d+)(?P<after>">)'
        r"(?P<body>.*?)(?P<tail></objects></part>)",
        re.DOTALL,
    )
    matches = list(part_re.finditer(doc))
    if len(matches) != 1:
        raise SystemExit(f"Ocekavana je prave jedna <part><objects> cast, nalezeno: {len(matches)}")
    match = matches[0]
    object_re = re.compile(r"<object\b.*?</object>", re.DOTALL)
    kept: list[str] = []
    removed = 0
    for obj in object_re.findall(match.group("body")):
        sym_match = re.search(r'\bsymbol="(\d+)"', obj)
        if sym_match is not None and int(sym_match.group(1)) in symbol_ids:
            removed += 1
        else:
            kept.append(obj)
    new_count = int(match.group("count")) - removed
    if new_count < 0:
        raise SystemExit("Po odstraneni objektu by byl zaporny <objects count>")
    replacement = f'{match.group("head")}{new_count}{match.group("after")}{"".join(kept)}{match.group("tail")}'
    return doc[:match.start()] + replacement + doc[match.end():], removed


def _write_summary(out_path: Path, payload: dict[str, Any]) -> Path:
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--detections", type=Path, help="PoC detections.json; exportuje všechny kandidáty.")
    source.add_argument("--review", type=Path, help="Kurátorský review_manifest.json; defaultně exportuje jen TP.")
    parser.add_argument("--map", dest="map_path", type=Path, required=True, help="Zdrojová .omap mapa.")
    parser.add_argument("--out", type=Path, required=True, help="Výstupní pracovní .omap kopie.")
    parser.add_argument("--image-name", default="bg_scan.png", help="TemplateImage jméno v .omap.")
    parser.add_argument("--include-unreviewed", action="store_true",
                        help="U review manifestu exportuje i nerozhodnuté kandidáty.")
    parser.add_argument("--include-fp", action="store_true", help="Debug: exportuje i označené false positive.")
    parser.add_argument("--include-ignore", action="store_true", help="Debug: exportuje i ignorované kandidáty.")
    parser.add_argument("--replace-existing-codes", action="store_true",
                        help="Před exportem odstraní stávající objekty stejných ISOM kódů.")
    args = parser.parse_args()

    if not args.map_path.exists():
        raise SystemExit(f"Chybi mapa: {args.map_path}")
    source_path, candidates, image_size, source_kind = _load_input(args)
    selected = _selected_candidates(candidates, source_kind, args)

    doc = args.map_path.read_text(encoding="utf-8")
    required_codes = _required_codes(selected)
    symbol_ids = _parse_symbol_ids(doc, required_codes)
    transform = _scan_template_transform(doc, args.image_name)
    objects, counts = _candidate_objects(selected, image_size, transform, symbol_ids)
    removed_existing = 0
    if args.replace_existing_codes:
        doc, removed_existing = _remove_objects_by_symbol_ids(doc, set(symbol_ids.values()))
    out_doc = _append_objects(doc, objects)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out_doc, encoding="utf-8")
    summary = {
        "source": str(source_path),
        "source_kind": source_kind,
        "map": str(args.map_path.resolve()),
        "out": str(args.out.resolve()),
        "image_name": args.image_name,
        "image_size": {"w": image_size[0], "h": image_size[1]},
        "template_transform": transform,
        "input_candidates": len(candidates),
        "removed_existing": removed_existing,
        "exported": len(selected),
        **counts,
    }
    summary_path = _write_summary(args.out, summary)
    print(json.dumps({**summary, "summary": str(summary_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
