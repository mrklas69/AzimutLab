#!/usr/bin/env python3
"""Validátor per-ISOM kalibračního manifestu pro scan-transfer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "calibration_manifest.json"

REQUIRED_ENTRY_KEYS = (
    "code",
    "name",
    "status",
    "source_map",
    "scan",
    "marker_source_omap",
    "marker_symbol",
    "positive_marker_count",
    "negative_examples",
    "detector",
    "parameters",
    "metrics",
    "review",
    "export",
)

REQUIRED_NESTED_KEYS = {
    "detector": ("family", "script", "source_detections", "review_manifest"),
    "metrics": ("candidate_count", "review_summary", "marker_recall", "false_positive_count"),
    "review": ("status", "sheet", "note"),
    "export": ("status", "omap"),
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Manifest nejde nacist jako JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Manifest musi byt JSON objekt: {path}")
    return data


def _has_key(obj: Any, key: str) -> bool:
    return isinstance(obj, dict) and key in obj


def validate_manifest(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Vrátí tvrdé chyby a měkká varování; bez výjimek kvůli snadnému použití v testech."""
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("schema_version") != 1:
        errors.append("schema_version musi byt 1")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries musi byt neprázdný seznam")
        return errors, warnings

    seen_codes: set[str] = set()
    for idx, entry in enumerate(entries):
        where = f"entries[{idx}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} musi byt objekt")
            continue

        code = str(entry.get("code", "")).strip()
        if not code:
            errors.append(f"{where}.code chybi nebo je prazdny")
        elif code in seen_codes:
            errors.append(f"duplicitni code {code}")
        else:
            seen_codes.add(code)

        for key in REQUIRED_ENTRY_KEYS:
            if key not in entry:
                errors.append(f"{where}.{key} chybi")

        for parent, keys in REQUIRED_NESTED_KEYS.items():
            nested = entry.get(parent)
            if not isinstance(nested, dict):
                errors.append(f"{where}.{parent} musi byt objekt")
                continue
            for key in keys:
                if not _has_key(nested, key):
                    errors.append(f"{where}.{parent}.{key} chybi")

        marker_count = entry.get("positive_marker_count")
        if marker_count is None:
            warnings.append(f"{code}: positive_marker_count je null")
        elif not isinstance(marker_count, int) or marker_count < 0:
            errors.append(f"{where}.positive_marker_count musi byt nezaporne cele cislo nebo null")
        elif marker_count == 0:
            warnings.append(f"{code}: nema pozitivni 602 markery")

        metrics = entry.get("metrics", {})
        if isinstance(metrics, dict):
            if metrics.get("marker_recall") is None:
                warnings.append(f"{code}: marker_recall neni doplneny")
            if metrics.get("false_positive_count") is None:
                warnings.append(f"{code}: false_positive_count neni doplneny")

    planned_next = data.get("planned_next", [])
    if not isinstance(planned_next, list):
        errors.append("planned_next musi byt seznam")
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--strict", action="store_true",
                        help="Varovani ber jako chyby; vhodne az po rucni kuraci.")
    args = parser.parse_args(argv)

    errors, warnings = validate_manifest(_load_json(args.manifest))
    for warning in warnings:
        print(f"WARN {warning}")
    for error in errors:
        print(f"ERROR {error}")

    if errors or (args.strict and warnings):
        return 1
    print(f"OK {args.manifest} ({len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
