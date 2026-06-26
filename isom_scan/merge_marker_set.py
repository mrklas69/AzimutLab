#!/usr/bin/env python3
"""Spojí jeden marker SET z mark_isoms do master GT (bransez_gt.json) — Sez. 171.

GT factory workflow (paměť `mark-isoms-gt-factory-workflow`, Sez. 169): uživatel kliká po
SKUPINÁCH do čistých set souborů (per-set čistá plocha, ať Save nepřepíše master filtrovanou
paletou). Tenhle skript je durable článek SET → MASTER, který Sez. 169 dělal ad-hoc:
přidá markery setu do master.markers, ohlídá dedup a sanity blízkých různých kódů,
přepočítá `codes`+`summary`, zazálohuje master.

Bezpečnost (anti-ztráta ruční práce):
- master se NEMĚNÍ při --dry-run (default jen report);
- před zápisem se master zálohuje do `<master>.pre_merge.bak`;
- rozbitý/chybějící JSON selže NAHLAS (no-silent-fallback), nikdy tichý default.

Spouštět z kořene přes .venv:
  python isom_scan/merge_marker_set.py isom_scan/markers/bransez_green.json --dry-run
  python isom_scan/merge_marker_set.py isom_scan/markers/bransez_green.json --apply
"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MASTER = HERE / "markers" / "bransez_gt.json"
DEDUP_PX = 3.0        # stejný kód blíž než tohle = táž instance klikrutá 2× → tiše sloučit
SANITY_TOL_PX = 20.0  # RŮZNÉ kódy blíž než tohle = red flag (izomorf gt_from_markers/score)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def _load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Soubor neexistuje: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Rozbity JSON {path}: {exc}") from exc


def _markers(man: dict, path: Path) -> list[dict]:
    m = man.get("markers", [])
    if not isinstance(m, list):
        raise SystemExit(f"Manifest nema seznam `markers`: {path}")
    return m


def merge(master: dict, addition: list[dict], note: str) -> dict:
    """Vrátí report dict; master.markers se mutuje in-place (přidané body)."""
    markers = _markers(master, Path("master"))
    existing = [(str(m["code"]), float(m["x"]), float(m["y"])) for m in markers]
    added, dups, flags = [], [], []
    for m in addition:
        code, x, y = str(m["code"]), float(m["x"]), float(m["y"])
        # dedup: stejný kód v okolí DEDUP_PX = táž instance
        if any(c == code and math.hypot(x - ex, y - ey) <= DEDUP_PX for c, ex, ey in existing):
            dups.append((code, x, y))
            continue
        # sanity: jiný kód blízko = red flag (jeden objekt značený dvěma kódy)
        for c, ex, ey in existing:
            if c != code:
                d = math.hypot(x - ex, y - ey)
                if d < SANITY_TOL_PX:
                    flags.append((code, x, y, c, round(d, 1)))
        markers.append({"id": f"{code}_x{round(x)}_y{round(y)}", "code": code,
                        "x": round(x, 1), "y": round(y, 1), "note": note})
        existing.append((code, x, y))
        added.append((code, x, y))
    # přepočet codes + summary z aktuálních markerů
    codes = sorted({m["code"] for m in markers}, key=lambda c: [int(p) for p in c.split(".")] if c.replace(".", "").isdigit() else [9999])
    master["codes"] = codes
    master["summary"] = {"total": len(markers),
                         "by_code": {c: sum(1 for m in markers if m["code"] == c) for c in codes}}
    return {"added": added, "dups": dups, "flags": flags, "total": len(markers)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set_path", type=Path, help="marker SET JSON z mark_isoms")
    ap.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    ap.add_argument("--note", default=None, help="poznámka k přidaným bodům (default = jméno setu)")
    ap.add_argument("--apply", action="store_true", help="zapiš do master (default = jen report / dry-run)")
    args = ap.parse_args(argv)

    master = _load(args.master)
    addition = _markers(_load(args.set_path), args.set_path)
    note = args.note or f"merge {args.set_path.name}"

    rep = merge(master, addition, note)
    print(f"SET {args.set_path.name}: {len(addition)} bodů → přidáno {len(rep['added'])}, "
          f"dedup {len(rep['dups'])}, master celkem {rep['total']}")
    if rep["added"]:
        from collections import Counter
        print("  přidané kódy:", dict(Counter(c for c, _, _ in rep["added"])))
    if rep["dups"]:
        print(f"  ⚠ dedup (stejný kód ≤{DEDUP_PX}px):", rep["dups"][:5])
    if rep["flags"]:
        print(f"  ⚠ SANITY red flag (různé kódy <{SANITY_TOL_PX}px — jeden objekt 2 kódy?):")
        for code, x, y, c, d in rep["flags"]:
            print(f"      {code} @({x},{y}) je {d}px od {c}")

    if args.apply:
        bak = args.master.with_suffix(".pre_merge.bak")
        bak.write_text(json.dumps(_load(args.master), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.master.write_text(json.dumps(master, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ zapsáno do {args.master} (záloha {bak.name})")
    else:
        print("(dry-run — master NEZMĚNĚN; přidej --apply pro zápis)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
