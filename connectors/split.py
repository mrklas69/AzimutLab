"""
split.py — geografický train/val/test split Livelox korpusu pro UC5 (Sez. 76).

Náhodný per-mapa split LEAKUJE: překrývající se mapy = stejný les v train i val.
Páry (gt_grid) pokrývají mapový quad v S-JTSK → překryv quadů = sdílené pozemní pixely
v train i val → falešně optimistický eval. Proto: mapy, jejichž S-JTSK bboxy se protínají,
MUSÍ do téhož splitu. Souvislé komponenty grafu překryvu = geografické clustery; celý
cluster jde do jednoho splitu (train/val/test).

Vstup: ČR keep-classic mapy = curate.kept_dirs('classic') ∩ ČR filtr. ČR/DE filtr =
near_white podíl ortofota (ČÚZK mimo ČR vrací jednolitou bílou 253) uložený durably v
_cz_filter.json; modul je díky tomu BEZ SÍTĚ (probe jen když soubor chybí).

Výstup: _split.json {cid: "train"|"val"|"test"}. Regenerovatelný, untracked (jako
_curation.json) — zdroj pravdy je tenhle deterministický skript, ne ten soubor.

Sys.path skript (fáze B, ne balík). Spouštět z kořene repa: `python connectors/split.py`.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CORPUS_DIR = _REPO_ROOT / "resources" / "livelox"
_CZ_FILTER = _CORPUS_DIR / "_cz_filter.json"
_SPLIT = _CORPUS_DIR / "_split.json"

# práh ČR/DE filtru: mapa je cizí (prázdné ČÚZK ortofoto), když near_white >= EMPTY.
# Separace je v datech široká (roh quadu ~0,12 vs většina-prázdná ~0,62) → 0,5 doprostřed.
EMPTY = 0.50
# cílový poměr train/val/test (volba uživatele Sez. 76)
RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}


def _near_white_map() -> dict:
    """Načte near_white per cid z _cz_filter.json. Když chybí, dopočítá probem (síť).

    Probe: malý ortofoto náhled v S-JTSK bboxu mapy → podíl skoro-bílých px. Lazy importy
    (livelox/ortofoto), ať čtení splitu na síti nezávisí. Re-build jen výjimečně.
    """
    if _CZ_FILTER.exists():
        return json.loads(_CZ_FILTER.read_text(encoding="utf-8"))["near_white"]

    # fallback: dopočítej probem (vyžaduje connectors na path + síť na ČÚZK)
    sys.path.insert(0, str(_REPO_ROOT / "connectors"))
    import numpy as np
    import livelox
    from ortofoto import _export_tile
    import curate

    nw = {}
    for d in sorted(curate.kept_dirs("classic")):
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        g = livelox._georef_grid(meta)
        aspect = (g["xmax"] - g["xmin"]) / (g["ymax"] - g["ymin"])
        w, h = (128, max(1, int(128 / aspect))) if aspect >= 1 else (max(1, int(128 * aspect)), 128)
        arr = _export_tile(g["xmin"], g["ymin"], g["xmax"], g["ymax"], w, h)
        lum = arr.astype(np.float32).mean(axis=2)
        nw[d.name] = round(float((lum > 245).mean()), 4)
    _CZ_FILTER.write_text(json.dumps(
        {"_meta": {"generated": "connectors/split.py probe", "count": len(nw)},
         "near_white": nw}, ensure_ascii=False, indent=2), encoding="utf-8")
    return nw


def cz_dirs() -> list[Path]:
    """Adresáře ČR keep-classic map (keep-classic ∩ near_white < EMPTY). Tréninkový pool."""
    sys.path.insert(0, str(_REPO_ROOT / "connectors"))
    import curate
    nw = _near_white_map()
    return [d for d in sorted(curate.kept_dirs("classic")) if nw.get(d.name, 1.0) < EMPTY]


def _bbox(meta: dict):
    """S-JTSK obalový obdélník mapy (reuse livelox._georef_grid: reprojekce quadu → obal)."""
    sys.path.insert(0, str(_REPO_ROOT / "connectors"))
    import livelox
    g = livelox._georef_grid(meta)
    return g["xmin"], g["ymin"], g["xmax"], g["ymax"]


def _overlap(a, b) -> bool:
    """Protínají se dva axis-aligned bboxy (xmin,ymin,xmax,ymax)? (konzervativní vůči quadu)."""
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _clusters(dirs: list[Path]) -> list[list[int]]:
    """Souvislé komponenty grafu překryvu bboxů. Vrací seznam clusterů (indexy do dirs)."""
    n = len(dirs)
    boxes = [_bbox(json.loads((d / "meta.json").read_text(encoding="utf-8"))) for d in dirs]
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if _overlap(boxes[i], boxes[j]):
                parent[find(i)] = find(j)

    comp = defaultdict(list)
    for i in range(n):
        comp[find(i)].append(i)
    # největší cluster první (greedy bin-packing potřebuje sestupně)
    return sorted(comp.values(), key=len, reverse=True)


def build_split(ratios: dict = RATIOS) -> dict:
    """Postaví geografický split a zapíše _split.json. Vrací {cid: split}.

    Greedy bin-packing: clustery sestupně podle velikosti, každý do splitu s největším
    zbývajícím deficitem (cíl − dosud). Deterministické (žádný RNG) → reprodukovatelné.
    """
    dirs = cz_dirs()
    n = len(dirs)
    clusters = _clusters(dirs)
    targets = {s: r * n for s, r in ratios.items()}
    counts = {s: 0 for s in ratios}

    assign = {}                                  # cid -> split
    for cl in clusters:
        # split s největším absolutním deficitem dostane tenhle cluster
        best = max(ratios, key=lambda s: targets[s] - counts[s])
        counts[best] += len(cl)
        for i in cl:
            assign[dirs[i].name] = best

    out = {"_meta": {
        "generated": "connectors/split.py (geografický split dle překryvu bboxů, Sez. 76)",
        "n_maps": n, "n_clusters": len(clusters), "ratios": ratios,
        "counts": counts,
    }}
    out.update(assign)
    _SPLIT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return assign


def load_split() -> dict:
    """Načte _split.json (bez _meta). {} když neexistuje."""
    if not _SPLIT.exists():
        return {}
    data = json.loads(_SPLIT.read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return data


def split_of(cid: str) -> str | None:
    """Split dané mapy ('train'/'val'/'test') nebo None (mimo split = cizí/non-keep)."""
    return load_split().get(cid)


def dirs_for(split: str) -> list[Path]:
    """Adresáře map v daném splitu (kontrakt pro UC5 tréninkový loader)."""
    return [_CORPUS_DIR / cid for cid, s in load_split().items() if s == split]


if __name__ == "__main__":
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(_REPO_ROOT / "connectors"))
    from map_gt import IGNORE, LABEL_NAME
    Image.MAX_IMAGE_PIXELS = None

    assign = build_split()
    by_split = defaultdict(list)
    for cid, s in assign.items():
        by_split[s].append(cid)

    print(f"split: {len(assign)} ČR map -> "
          + ", ".join(f"{s} {len(by_split[s])}" for s in RATIOS))
    print(f"\n{'split':<7}{'#map':>6}{'labeled px':>16}   per-class % (0/406/408/410/open)")
    for s in RATIOS:
        from collections import Counter
        tot = Counter()
        for cid in by_split[s]:
            lab = np.asarray(Image.open(_CORPUS_DIR / cid / "gt_labels.png"))
            v, c = np.unique(lab, return_counts=True)
            for vv, cc in zip(v.tolist(), c.tolist()):
                tot[vv] += cc
        labeled = sum(c for v, c in tot.items() if v != IGNORE)
        pcts = " / ".join(f"{100*tot.get(v,0)/labeled:4.1f}" for v in [0, 1, 2, 3, 4])
        print(f"{s:<7}{len(by_split[s]):>6}{labeled:>16,}   {pcts}")
