"""compare_isom.py — pokrytí ISOM symbolů: naše gen `.omap` vs reálná OB mapa (Sez. 91).

DoD nástroj generátoru: fáze výroby `generator()` je hotová až při ≥ 90 % pokrytí ISOM mapových
symbolů 5 vzorových map v `resources/` (Bedřichovka/Blatná/Slovanka2016/Soví vrch/Velbloud). Co
generátor nenakreslí do `.omap`, to se `reconstructor()` nikdy nenaučí → pokrytí = strop tréninku.

Měří jen POUŽITÉ symboly (≥1 objekt, ne celá template knihovna) a jen MAPOVÉ kódy 100-599
(vyloučí layout 6xxx, loga 5002/5006, control/overprint 7xx — ten se v map_gt stejně ignoruje).
Match integer prefixem (415.0 → 415; .0/.1 jsou template variace, paměť `omap-area-code-suffix`).

  python generator/compare_isom.py <reálná.omap> <naše_gen.omap>

Příklad (Sez. 91): generate_map(Bedřichovka, všechny real) vs resources/Bedřichovka.omap → 27/71 = 38 %.
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _local(tag: str) -> str:
    """Lokální jméno XML tagu bez namespace ({...}symbol → symbol).

    OOM .omap má namespace `openorienteering.org/.../v2`; ET.iter("symbol") ani wildcard "{*}"
    spolehlivě nematchují → strip přes split je nejrobustnější."""
    return tag.split("}")[-1]


def isom_usage(path: str) -> tuple[Counter, dict]:
    """Vrátí (Counter ISOM_kód → počet objektů, dict ISOM_kód → jméno) pro mapové symboly 100-599."""
    root = ET.parse(path).getroot()
    id2code, id2name = {}, {}
    for el in root.iter():
        if _local(el.tag) == "symbol":
            id2code[el.get("id")] = el.get("code", "")
            id2name[el.get("id")] = el.get("name", "")
    used = Counter()
    for el in root.iter():
        if _local(el.tag) == "object":
            sid = el.get("symbol")
            if sid is not None:
                used[sid] += 1
    codes, names = Counter(), {}
    for sid, n in used.items():
        try:
            ci = int(float(id2code.get(sid, "")))   # integer prefix (415.0 → 415)
        except ValueError:
            continue
        if ci < 100 or ci >= 600:                    # jen mapové symboly (vyluč layout/control/overprint)
            continue
        codes[ci] += n
        names.setdefault(ci, id2name.get(sid, ""))
    return codes, names


def main() -> None:
    if len(sys.argv) != 3:
        print("použití: python generator/compare_isom.py <reálná.omap> <naše_gen.omap>")
        sys.exit(1)
    real, rnames = isom_usage(sys.argv[1])
    gen, _ = isom_usage(sys.argv[2])
    rs, gs = set(real), set(gen)
    covered, missing = rs & gs, rs - gs
    pct = 100 * len(covered) / len(rs) if rs else 0

    print(f"REÁLNÁ {sys.argv[1]}: {len(rs)} unikátních ISOM mapových kódů (100-599)")
    print(f"NAŠE   {sys.argv[2]}: {len(gs)} unikátních")
    print(f"\n>>> POKRYTÍ: {len(covered)}/{len(rs)} = {pct:.0f}%  (DoD = ≥ 90 %)\n")

    print(f"CHYBÍ v generátoru ({len(missing)}, dle četnosti v reálné mapě):")
    for c in sorted(missing, key=lambda c: -real[c]):
        print(f"  {c:>4}  {real[c]:>4}×  {rnames.get(c, '')[:45]}")
    print(f"\nPOKRÝVÁ ({len(covered)}): " + " ".join(str(c) for c in sorted(covered)))


if __name__ == "__main__":
    main()
