"""Vypis generatorovych ISOM capability zaznamu.

CLI je zamerne cteni-only: nic negeneruje ani neladi. Slouzi jako rychly
auditni pohled na "realne vs pseudo" a jako spojka mezi SVG katalogem a
generator/reconstructor rozhodovanim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from isom.capabilities import (  # noqa: E402
    CAPABILITIES,
    CONFLICT_POLICY,
    SymbolCapability,
    summarize_by_kind,
)
from isom.symbol_index import DEFAULT_RESOURCE_DIR, SymbolIndexError, build_symbol_index  # noqa: E402


def _local_svg_lookup(resource_dir: Path) -> dict[str, str]:
    """Vrati code -> relativni SVG cesta, kdyz lokalni katalog existuje.

    Chyby katalogu nejsou fatalni pro capability vypis: tabulka puvodu generatoru
    je pouzitelna i bez SVG dumpu. Pokud ale SVG existuje, ukazeme vazbu.
    """
    try:
        index = build_symbol_index(resource_dir)
    except (OSError, SymbolIndexError, ValueError):
        return {}
    return {record.code: record.files.get("svg", "") for record in index.records}


def _rows(records: tuple[SymbolCapability, ...],
          svg_lookup: dict[str, str]) -> list[dict[str, object]]:
    rows = []
    for record in records:
        row = record.to_json_dict()
        svg = svg_lookup.get(record.code)
        for variant in record.variants:
            if svg:
                break
            svg = svg_lookup.get(variant)
        row["local_svg"] = bool(svg)
        if svg:
            row["svg"] = svg
        rows.append(row)
    return rows


def _markdown(rows: list[dict[str, object]]) -> str:
    headers = ("code", "geom", "generator", "preferred", "scanner", "source", "svg")
    out = [
        f"Conflict policy: `{CONFLICT_POLICY}`",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append(
            "| {code} | {geom} | {kind} | {preferred} | {scanner} | {source} | {svg} |".format(
                code=row["code"],
                geom=row["geom"],
                kind=row["generator_kind"],
                preferred=row["preferred_kind"],
                scanner=row["scanner_status"],
                source=str(row["generator_source"]).replace("|", "/"),
                svg="yes" if row.get("local_svg") else "no",
            )
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List ISOM generator capabilities.")
    parser.add_argument("--resources", type=Path, default=DEFAULT_RESOURCE_DIR,
                        help="Adresar lokalniho SVG katalogu, default resources/isom.")
    parser.add_argument("--kind", choices=["all", "real", "mapper_scan", "mixed", "pseudo"],
                        default="all", help="Filtrovat podle typu zdroje generatoru.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="Vystupni format.")
    args = parser.parse_args(argv)

    records = CAPABILITIES
    if args.kind != "all":
        records = tuple(record for record in records if record.generator_kind == args.kind)

    rows = _rows(records, _local_svg_lookup(args.resources))
    payload = {
        "conflict_policy": CONFLICT_POLICY,
        "summary": summarize_by_kind(records),
        "symbols": rows,
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        summary = ", ".join(f"{key}={value}" for key, value in payload["summary"].items())
        print(f"Summary: {summary}")
        print(_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
