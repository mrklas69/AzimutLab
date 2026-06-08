"""stats.py — agreguje meta.json všech DEV_LOCATIONS do tabulky STATISTICS.md.

Pro každou lokalitu (maps/<dirname>/) přečte:
- meta.json: počty symbolů ze sekcí (paths/rides/water/paved/buildings/powerlines/railways/rocks/
  bridges/surfaces/landmarks/linefeatures/marsh/treerows/veg_area/barriers + point_symbols) — každá items má
  `symbol: int` (např. 503, 304, 5122=512.2),
- contours.geojson: vrstevnice 101/102/103 (každý feature má properties.symbol),
- mtime meta.json: čas poslední regenerace.

Vypíše Markdown tabulku ISOM symbol × lokalita s počtem objektů + sekci „Poslední
aktualizace". Spouštět po regen kanonika; commit STATISTICS.md s změnou kódu/lokalit.
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent          # generator/ — sem se píše STATISTICS.md (verzováno)
MAPS_DIR = ROOT.parent / "maps"       # maps/<lokalita>/ — odsud čteme výstupy (Sez. 39)

# DEV_LOCATIONS (kód → název složky). Musí sedět s názvem výstupní složky (maps/<jméno>).
LOCATIONS = [
    ("SV", "Soví vrch",   "Soví vrch / Lužické hory"),
    ("NL", "Nová Louka",  "Nová Louka / Jizerské hory"),
    ("LS", "Lidové sady", "Lidové sady / Liberec"),
    ("HS", "Hrubá Skála", "Hruboskalsko / Český ráj"),
    ("NV", "Novina",      "Novina / Lužické hory"),
]

# ISOM symboly + popis (v pořadí kategorií: terén → skály → voda → komunikace → stavby
# → mosty/lávky). Sloupec „Symbol" má kód s tečkou tam, kde ISOM dělí sub-symboly.
SYMBOLS = [
    # Terén (§4.5, §4.10)
    ("101",   "Contour"),
    ("102",   "Index contour"),
    ("103",   "Form line"),
    ("109",   "Small knoll"),
    ("110",   "Small elongated knoll"),
    ("111",   "Small depression"),
    # Skály a balvany (§4.11)
    ("204",   "Boulder"),
    ("206",   "Gigantic boulder"),
    ("207",   "Boulder cluster"),
    ("208",   "Boulder field"),
    # Voda (§4.6)
    ("301",   "Uncrossable body of water"),
    ("304",   "Crossable watercourse"),
    ("305",   "Small crossable watercourse"),
    ("306",   "Minor seasonal water channel"),
    ("308",   "Marsh"),
    ("310",   "Indistinct marsh"),
    ("311",   "Well, fountain or water tank"),
    ("312",   "Spring"),
    # Skalní bodové (§4.11, Sez. 44)
    ("203.2", "Cave or rocky pit"),
    # Plošný pokryv / vegetace (§4.8, Sez. 41 + 45 + 47 + 53)
    ("401",   "Open land"),
    ("402",   "Open land with scattered trees"),
    ("402.1", "Open land with scattered bushes"),
    ("406",   "Vegetation: slow running"),
    ("408",   "Vegetation: walk"),       # věk porostu PROXY (Sez. 62, --forest-age)
    ("410",   "Vegetation: fight"),      # věk porostu PROXY (Sez. 62, --forest-age)
    ("412",   "Cultivated land"),
    ("520",   "Area that shall not be entered"),
    # Komunikace (§4.9)
    ("501",   "Paved area"),
    ("501.1", "Paved area (no bounding line)"),
    ("502",   "Wide road"),
    ("503",   "Road"),
    ("504",   "Vehicle track"),
    ("505",   "Footpath"),
    ("506",   "Small footpath"),
    ("508",   "Narrow ride"),
    ("509",   "Railway"),
    ("510",   "Power line, cableway or skilift"),
    # Stavby (§4.12)
    ("521",   "Building"),
    ("523",   "Ruin"),
    # Mosty / tunely / lávky (§4.12, Sez. 32 spec-driven)
    ("512",   "Bridge/tunnel"),
    ("512.2", "Footbridge"),
    # Bodové orientační prvky (§4.12, Sez. 43)
    ("524",   "High tower"),
    ("526",   "Cairn"),
    ("530",   "Prominent man-made feature"),
    ("417",   "Prominent large tree"),
    # Liniové orientační prvky (Sez. 43 + 58)
    ("104",   "Earth bank"),
    ("107",   "Erosion gully"),
    ("513",   "Wall"),
    ("516",   "Fence"),     # plot po obvodu RÚIAN-privát bloků (pseudo fáze 2, Sez. 98)
    # Prostupy (Sez. 52): zábrana na zdi → Crossing point
    ("519",   "Crossing point"),
]


def _normalize_code(sym) -> str:
    """Sjednotí kód na string s tečkou: int 5122 → „512.2", int 304 → „304"."""
    if sym is None:
        return ""
    if sym == 5122:               # ISOM_FOOTBRIDGE alias (= ISOM 512.2)
        return "512.2"
    return str(sym)


def _count_contours(geojson_path: Path) -> Counter:
    """Vrátí počty per ISOM kód z contours.geojson (101/102/103). Soubor obsahuje
    všechny vrstevnice (vč. form lines 103) jako liniové features s `properties.symbol`
    (int 101/102/103) — pozor, ne `code`."""
    if not geojson_path.exists():
        return Counter()
    d = json.loads(geojson_path.read_text(encoding="utf-8"))
    return Counter(str(f.get("properties", {}).get("symbol", ""))
                   for f in d.get("features", []))


def _gather_symbol_counts(folder: Path) -> tuple[Counter, datetime] | tuple[None, None]:
    """Načte meta.json + contours.geojson, vrátí (Counter[kód → počet], mtime meta)."""
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        return None, None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    mtime = datetime.fromtimestamp(meta_path.stat().st_mtime)
    counts: Counter = Counter()
    # 1) vrstevnice 101/102/103 z contours.geojson (meta agreguje jen total)
    counts.update(_count_contours(folder / "contours.geojson"))
    # 2) items z 15 sekcí (každá má seznam s {"symbol": <int>})
    for section in ("paths", "rides", "water", "paved", "buildings", "powerlines",
                    "railways", "rocks", "bridges", "surfaces", "landmarks", "linefeatures",
                    "marsh", "treerows", "veg_area", "barriers"):
        items = meta.get(section, {}).get("items", [])
        for it in items:
            counts[_normalize_code(it.get("symbol"))] += 1
    # 3) bodové symboly extrémů (109/110/111) — vlastní top-level list
    for ps in meta.get("point_symbols", []):
        counts[_normalize_code(ps.get("symbol"))] += 1
    counts.pop("", None)
    return counts, mtime


def main() -> None:
    rows = []
    for code, dirname, label in LOCATIONS:
        folder = MAPS_DIR / dirname
        counts, mtime = _gather_symbol_counts(folder)
        rows.append((code, dirname, label, counts, mtime))

    # --- Markdown tabulka ----------------------------------------------------------
    out: list[str] = [
        "# STATISTICS — testovací mapy AzimutLab",
        "",
        "Počty objektů per ISOM symbol napříč 5 DEV_LOCATIONS (`generator.py --location KÓD`).",
        "Regeneruj skriptem `stats.py` po každém regen kanonika nebo po změně rendereru.",
        "",
        "**Kanonické lokality** (různé formáty výseku pro test ořezu DMR/ZABAGED/ortofoto):",
        "",
    ]
    for code, dirname, label, _, mtime in rows:
        out.append(f"- **{code}** — {label}  (`{dirname}/`)")
    out += ["", "## Symboly × lokality", ""]
    # header row
    header = "| Symbol | Název ISOM 2017-2 | " + " | ".join(c for c, _, _, _, _ in rows) + " |"
    sep = "|--------|-------------------|" + "|".join(["---:" for _ in rows]) + "|"
    out += [header, sep]
    # rows
    used_symbols: set[str] = set()
    for code, name in SYMBOLS:
        cells = []
        for _, _, _, counts, _ in rows:
            if counts is None:
                cells.append("—")
            else:
                n = counts.get(code, 0)
                if n > 0:
                    used_symbols.add(code)
                cells.append(str(n) if n > 0 else "·")
        out.append(f"| **{code}** | {name} | " + " | ".join(cells) + " |")
    # souhrn
    total_per_loc = []
    for code, dirname, label, counts, _ in rows:
        if counts is None:
            total_per_loc.append("—")
        else:
            total_per_loc.append(str(sum(counts.values())))
    out.append(f"| **Σ** | Celkem objektů | " + " | ".join(total_per_loc) + " |")
    out += [
        "",
        f"Z {len(SYMBOLS)} sledovaných ISOM symbolů reálně používáme **{len(used_symbols)}** "
        "(zbytek = · znamená, že vrstva v dané lokalitě nemá žádný prvek; — znamená,"
        " že lokalita ještě nebyla regenerována). Legenda: · = 0 prvků, — = chybí výstup.",
        "",
        "## Poslední aktualizace",
        "",
    ]
    for code, dirname, _, _, mtime in rows:
        if mtime is None:
            out.append(f"- **{code}** (`{dirname}/`): *nevygenerováno*")
        else:
            out.append(f"- **{code}** (`{dirname}/`): "
                       f"{mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    # patička: kdy se tabulka generovala
    now = datetime.now()
    out += [
        "",
        f"---",
        f"*Tabulka regenerována `{Path(__file__).name}` v {now.strftime('%Y-%m-%d %H:%M:%S')}.*",
        "",
    ]
    (ROOT / "STATISTICS.md").write_text("\n".join(out), encoding="utf-8")
    print(f"saved {ROOT / 'STATISTICS.md'}")


if __name__ == "__main__":
    main()
