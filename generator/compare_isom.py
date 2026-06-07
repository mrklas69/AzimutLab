"""compare_isom.py — pokrytí ISOM symbolů: naše gen `.omap` vs reálná OB mapa (Sez. 91).

DoD nástroj generátoru: fáze výroby `generator()` je hotová až při ≥ 90 % pokrytí ISOM mapových
symbolů 5 vzorových map v `resources/` (Bedřichovka/Blatná/Slovanka2016/Soví vrch/Velbloud). Co
generátor nenakreslí do `.omap`, to se `reconstructor()` nikdy nenaučí → pokrytí = strop tréninku.

Měří jen POUŽITÉ symboly (≥1 objekt, ne celá template knihovna) a jen MAPOVÉ kódy 100-599
(vyloučí layout 6xxx, loga 5002/5006, control/overprint 7xx — ten se v map_gt stejně ignoruje).
Match integer prefixem (415.0 → 415; .0/.1 jsou template variace).

CROSSWALK (Sez. 94, oprava metodiky): reálné OB mapy jsou většinou v ISOM 2000, generátor v
ISOM 2017-2. Číslování se mezi verzemi RECYKLUJE s jiným významem (526 Building 2000 → 521 2017,
509 Narrow ride 2000 → 508 2017, …; KB `isom-issprom.md` Sez. 37-40) → naivní kód-na-kód dává
false negativy i pozitivy. `coverage()` proto detekuje verzi reálné mapy (526/521 budova) a
2000 kódy přemapuje přes `docs/kb/ISOM2000-ISOM2017-2.crt` (Kai Pastor, OOM) na 2017-2 PŘED
porovnáním. Custom ne-ISOM kódy (mimo crosswalk) se vyřadí z jmenovatele (volba uživatele Sez. 94).

  python generator/compare_isom.py <reálná.omap> <naše_gen.omap>
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_REPO = Path(__file__).resolve().parents[1]   # generator/ je 1 pod kořenem (Sez. 39)
_CRT = _REPO / "docs" / "kb" / "ISOM2000-ISOM2017-2.crt"   # autoritativní crosswalk (KB Sez. 37-40)
_TEMPLATE = Path(__file__).resolve().parent / "template_classic.omap"   # plná ISOM 2017-2 knihovna

# OOM `<symbol type=N>` → geometrie (doloženo distribucí v template, Sez. 95):
# 1=Point, 2=Line, 4=Area, 8=Text, 16=Combined. Geometrie určuje, který reconstructor kód umí.
_TYPE_GEOM = {1: "point", 2: "line", 4: "area", 8: "text", 16: "combined"}


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


def used_geometry(path: str) -> dict:
    """Mapuje ISOM integer kód → geometrie REÁLNĚ POUŽITÉHO symbolu v dané mapě (z OOM `type`).

    Geometrii čte přímo z mapy podle symbolu, který objekty SKUTEČNĚ nesou (ne z template podle
    primárního kódu) — ground truth kartografovy reprezentace. Klíčové pro
    analytický cut (Sez. 96): 210 má v template primary 'area' ('Stony ground, slow running'),
    ale VŠECHNY reálné mapy kreslí variantu 210.0/210.1 = 'point' ('individual dot') → strop plošné
    fáze ho nesmí počítat jako plochu (jinak nadhodnocení). Stejná past u dalších kódů s point/area
    variantou (104 Earth bank line + 104.1 point, …). Měř geometrii z reálné mapy, ne z template.

    Kolize variant (210 area + 210.1 point → oba ci=210): vyhrává geometrie varianty s NEJVÍCE
    objekty (majoritní reprezentace v mapě), počítáno přes počet objektů."""
    root = ET.parse(path).getroot()
    id2geom, id2code = {}, {}
    for el in root.iter():
        if _local(el.tag) == "symbol":
            id2geom[el.get("id")] = _TYPE_GEOM.get(int(el.get("type", "0")), "?")
            id2code[el.get("id")] = el.get("code", "")
    tally: dict[int, Counter] = {}        # ci → Counter(geom → počet objektů) pro majoritní volbu
    for el in root.iter():
        if _local(el.tag) != "object":
            continue
        sid = el.get("symbol")
        if sid is None:
            continue
        try:
            ci = int(float(id2code.get(sid, "")))
        except ValueError:
            continue
        if ci < 100 or ci >= 600:
            continue
        tally.setdefault(ci, Counter())[id2geom.get(sid, "?")] += 1
    return {ci: c.most_common(1)[0][0] for ci, c in tally.items()}


def _load_crosswalk() -> tuple[dict, set, set]:
    """Načte ISOM 2000→2017-2 crosswalk z `.crt` (Kai Pastor, OOM, GPL). Formát: `<2017-2>  <2000>`.

    Pracuje na integer prefixu (415.0 → 415, jako isom_usage). Vrací:
      cw:      {int 2000 → set(int 2017-2)}  — 1 kód 2000 může mít víc 2017 cílů a naopak,
      v2000:   set(int) všech 2000 kódů v tabulce (= co JE ISOM 2000; mimo = custom → vyřadit),
      v2017:   set(int) všech 2017-2 kódů (pro reálné mapy, co už jsou 2017-2 — identita).
    """
    cw: dict[int, set] = {}
    v2000: set = set()
    v2017: set = set()
    for line in _CRT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):       # přeskoč komentáře/prázdné
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            c2017, c2000 = int(float(parts[0])), int(float(parts[1]))   # integer prefix obou
        except ValueError:
            continue
        if not (100 <= c2000 < 600):                # jen mapové symboly (jako isom_usage)
            continue
        cw.setdefault(c2000, set()).add(c2017)
        v2000.add(c2000)
        v2017.add(c2017)
    return cw, v2000, v2017


def _resolve_targets(c: int, ver: str, cw: dict, v2000: set, v2017: set) -> set | None:
    """ISOM kód reálné mapy → set 2017-2 cílů (crosswalk), nebo None pro custom (mimo ISOM).

    2000: kód musí být v tabulce (jinak custom → None), pak jeho crosswalk cíle. 2017-2: identita
    {c} (kód musí být známý 2017 cíl, jinak custom). Sdílí coverage() i measure_dod.run_table()
    — single source of truth crosswalk-resolve logiky (DRY)."""
    if ver == "2000":
        if c not in v2000:
            return None
        return cw.get(c, set())
    if c not in v2017:
        return None
    return {c}


_BUILDING_KW = ("building", "budov", "dům", "dum", "house")   # CZ i EN (Soví vrch má „Budova")


def detect_version(path: str) -> str:
    """Vrať '2000' nebo '2017-2' podle kódu BUDOVY (tvrdý diskriminátor, KB Sez. 37-40).

    526 = Building/Budova v ISOM 2000 (v 2017-2 kód neexistuje), 521 = Building v 2017-2 (ve 2000
    je 521 High stone wall). Budova je v každé OB mapě → robustní. Fallback (mapa bez budov):
    průsek 509 (2000) / 508 (2017-2); jinak default 2017-2 (= generátorova verze)."""
    root = ET.parse(path).getroot()
    id2 = {s.get("id"): (s.get("code", ""), (s.get("name") or "").lower())
           for s in root.iter() if _local(s.tag) == "symbol"}
    used = {o.get("symbol") for o in root.iter() if _local(o.tag) == "object"}
    for sid in used:                                # primární diskriminátor: budova
        code, name = id2.get(sid, ("", ""))
        if any(k in name for k in _BUILDING_KW):
            try:
                ci = int(float(code))
            except ValueError:
                continue
            if ci == 526:
                return "2000"
            if ci == 521:
                return "2017-2"
    for sid in used:                                # fallback: průsek/ride
        code, name = id2.get(sid, ("", ""))
        if "průsek" in name or "prusek" in name or "ride" in name:
            try:
                ci = int(float(code))
            except ValueError:
                continue
            if ci == 509:
                return "2000"
            if ci == 508:
                return "2017-2"
    return "2017-2"


def coverage(real_path: str, gen_path: str) -> dict:
    """Crosswalk-aware pokrytí ISOM: reálná mapa (2000 i 2017) vs generátor (2017-2).

    1. detekuj verzi reálné mapy, 2. 2000 → přemapuj kódy přes crosswalk na 2017-2 (1→set cílů),
    3. custom ne-ISOM kódy (mimo tabulku) VYŘAĎ z jmenovatele, 4. kód POKRYT, pokud generátor
    kreslí aspoň jeden z jeho 2017-2 cílů. Vrací dict (version/covered/missing/custom/denom/pct
    + freq/names + per-missing 2017 cíle pro prioritizaci).
    """
    cw, v2000, v2017 = _load_crosswalk()
    ver = detect_version(real_path)
    real, rnames = isom_usage(real_path)
    gen, _ = isom_usage(gen_path)
    gen_set = set(gen)
    covered: list = []          # int real kód (pokrytý) — main/run_proxy počítají len/set
    missing: list = []          # (real kód, tuple 2017 cílů, freq, jméno)
    custom: list = []           # int real kód mimo ISOM crosswalk (vyřazen z jmenovatele)
    for c in real:
        targets = _resolve_targets(c, ver, cw, v2000, v2017)
        if targets is None:                          # custom ne-ISOM kód → vyřaď z jmenovatele
            custom.append(c)
            continue
        if targets & gen_set:
            covered.append(c)
        else:
            missing.append((c, tuple(sorted(targets)), real[c], rnames.get(c, "")))
    denom = len(covered) + len(missing)
    pct = 100 * len(covered) / denom if denom else 0
    return {"version": ver, "covered": covered, "missing": missing,
            "custom": custom, "denom": denom, "pct": pct,
            "used_geom": used_geometry(real_path)}   # geom reálně použitých symbolů (Sez. 96 cut)


def main() -> None:
    if len(sys.argv) != 3:
        print("použití: python generator/compare_isom.py <reálná.omap> <naše_gen.omap>")
        sys.exit(1)
    r = coverage(sys.argv[1], sys.argv[2])
    print(f"REÁLNÁ {sys.argv[1]}: verze ISOM {r['version']}, "
          f"{r['denom']} ISOM kódů v jmenovateli (+{len(r['custom'])} custom vyřazeno)")
    print(f">>> POKRYTÍ: {len(r['covered'])}/{r['denom']} = {r['pct']:.0f}%  (DoD = ≥ 90 %)\n")

    print(f"CHYBÍ v generátoru ({len(r['missing'])}, dle četnosti; → 2017-2 cíl, který má kreslit):")
    for c, targets, freq, name in sorted(r["missing"], key=lambda m: -m[2]):
        tgt = "/".join(str(t) for t in targets) if targets else "—"
        print(f"  2000:{c:<4} {freq:>4}×  → 2017:{tgt:<10} {name[:38]}")
    if r["custom"]:
        print(f"\nCUSTOM (ne-ISOM, vyřazeno z DoD): " + " ".join(str(c) for c in sorted(r["custom"])))
    print(f"\nPOKRÝVÁ ({len(r['covered'])}): " + " ".join(str(c) for c in sorted(r["covered"])))


if __name__ == "__main__":
    main()
