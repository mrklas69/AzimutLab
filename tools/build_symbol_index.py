"""CLI pro vytvoreni/prevereni `resources/isom/index.json`.

Pouziti:
  python tools/build_symbol_index.py --resources resources/isom
  python tools/build_symbol_index.py --resources resources/isom --write

Bez `--write` jde o dry-run: nacte existujici index nebo objevi SVG soubory a
vypise souhrn. Se `--write` zapise index a descriptor JSONy.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from isom.symbol_index import (  # noqa: E402
    DEFAULT_RESOURCE_DIR,
    SymbolIndexError,
    build_symbol_index,
    write_symbol_index,
)


def _summary(index) -> str:
    by_geom: dict[str, int] = {}
    unknown_license = 0
    for record in index.records:
        by_geom[record.geom] = by_geom.get(record.geom, 0) + 1
        if record.source.get("license", "unknown") == "unknown":
            unknown_license += 1
    geom = ", ".join(f"{key}={by_geom[key]}" for key in sorted(by_geom))
    return (
        f"symbols={len(index)}"
        + (f" ({geom})" if geom else "")
        + f", unknown_license={unknown_license}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build/validate ISOM SVG symbol index.")
    parser.add_argument("--resources", type=Path, default=DEFAULT_RESOURCE_DIR,
                        help="Adresar katalogu, default resources/isom.")
    parser.add_argument("--write", action="store_true",
                        help="Zapsat index.json a descriptors/*.json.")
    parser.add_argument("--strict", action="store_true",
                        help="Vyžadovat vyplnenou geometrii, licenci a ISOM verzi.")
    args = parser.parse_args(argv)

    try:
        index = build_symbol_index(args.resources, strict=args.strict)
        print(f"{args.resources}: {_summary(index)}")
        if args.write:
            out = write_symbol_index(index, args.resources)
            print(f"zapsano: {out}")
    except (OSError, SymbolIndexError, ValueError) as exc:
        print(f"CHYBA: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
