"""
tile.py — příprava tréninkových dlaždic reconstructor modelu Png2Line (Sez. 130).

TŘETÍ ze tří CV úloh dekompozice OOM podle geometrie (Sez. 80): Png2Area (plochy, Sez. 88) | Png2Point
(body, Sez. 105) | **Png2Line (linie)**. Úloha: mapový sken → per-class segmentace liniových ISOM symbolů
(aktuálně watercourse 304/305 + 306 + 309 + 508*). Vektorizace maska→polyline je ODLOŽENÝ
sdílený downstream krok (skeletonizace+RDP), NE součást modelu — viz IDEAS „Png2Line — segmentace + odložená
vektorizace".

Izomorfní s model/png2area/tile.py (reuse tiling/split/resample), s JEDINÝM rozdílem:
  - Png2Area čte HOTOVÉ area_labels.png (omap_raster.main ho napekl do páru).
  - Png2Line počítá liniové Y **on-the-fly** z .omap+meta (omap_raster.rasterize_lines_map_dir) — line scope
    nesahá na pairs.py build pipeline. Pár tedy potřebuje jen
    rgb.png + <*.omap> + meta.json (ne předpočítaný label).

GT je NAFOUKLÁ linie (omap_raster.GT_LINE_WIDTH_PX) — tenká linie by se v U-Netu rozpustila (lekce
Png2Area: budovy 521 tenké → IoU 0,00). Skeletonizace zpět na 1px až při inferenci/vektorizaci.

Split (train/val/test) dědíme z connectors/split.py (geografický, bez leaku, Sez. 76) — STEJNÝ zdroj jako
Png2Area; dlaždice jedné mapy jdou CELÉ do splitu té mapy. Korpus jen na mrkla (copyright) → na ntbhej
smoke přes dev mapy z maps/ (build_tiles_dev).

DRY dluh (Sez. 130): tohle je 3. konzument tiling helperů (_positions/_crop/resample) = dokumentovaný
spouštěč extrakce sdíleného modulu (TODO). Zatím kopie vzoru Png2Area (nižší riziko k prvnímu výsledku).

Výstup:
  resources/line_tiles/<split>/<cid>/<r>_<c>_x.png   = X (sken RGB 512×512)
  resources/line_tiles/<split>/<cid>/<r>_<c>_y.png   = Y (line label 0..N_LINE-1, mode L)
  resources/line_tiles/_tiles.json                   = počty + class distribuce + median-freq váhy
  resources/line_tiles/_preview.png                  = vizuální verify (mozaika X|Y vzorků)

Sys.path skript (fáze B, ne balík). Spouštět z kořene repa:
  python model/png2line/tile.py             # korpus přes split (mrkla, po nočním build_pairs)
  python model/png2line/tile.py dev "Soví vrch"   # smoke na dev mapě z maps/ (ntbhej)
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[2]   # model/png2line/ → o dvě úrovně hloub
_TILES_DIR = _REPO_ROOT / "resources" / "line_tiles"
_CORPUS = _REPO_ROOT / "resources" / "livelox"
_MAPS = _REPO_ROOT / "maps"

# connectors (split) + generator (omap_raster: SSoT line tříd) + model (mpp: kanonické MPP) na path
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))
sys.path.insert(0, str(_REPO_ROOT / "model"))
import split                                                # noqa: E402
from omap_raster import (                                   # noqa: E402
    N_LINE, LINE_LABEL_NAME, colorize_lines, rasterize_lines_map_dir)
from mpp import CANONICAL_MPP, resample_to_mpp, read_src_mpp   # noqa: E402  (Sez. 126: páry na kanonické měřítko)

Image.MAX_IMAGE_PIXELS = None                  # páry jsou velké, vypnout PIL decompression bomb guard

TILE = 512          # strana dlaždice (px) — vstup U-Netu (shodně s png2area/png2point)
STRIDE = 256        # posun okna (px) → 50% překryv
# N_LINE se importuje z omap_raster (SSoT line schématu).


def _positions(length: int) -> list[int]:
    """Počáteční souřadnice okna TILE podél osy `length`, stride STRIDE. Poslední okno zarovnáno k okraji.

    Identické s png2area/tile.py (DRY dluh: extrakce až by vznikl sdílený tiling modul — teď 3. konzument)."""
    if length <= TILE:
        return [0]
    pos = list(range(0, length - TILE + 1, STRIDE))
    if pos[-1] != length - TILE:
        pos.append(length - TILE)
    return pos


def _crop(arr: np.ndarray, y0: int, x0: int) -> np.ndarray:
    """Vyřízne TILE×TILE z `arr` od (y0,x0). Když mapa < TILE, dopaduje 0 (= pozadí pro Y, černá pro X)."""
    H, W = arr.shape[:2]
    h = min(TILE, H - y0)
    w = min(TILE, W - x0)
    if h == TILE and w == TILE:
        return arr[y0:y0 + TILE, x0:x0 + TILE]
    shape = (TILE, TILE) + arr.shape[2:]
    out = np.zeros(shape, dtype=arr.dtype)
    out[:h, :w] = arr[y0:y0 + h, x0:x0 + w]
    return out


def _resolve_pair_dir(name: str) -> Path | None:
    """název (cid / lokalita) → adresář s rgb.png + <*.omap> + meta.json, nebo None.

    Na rozdíl od Png2Area NEvyžaduje předpočítaný label (line Y se počítá on-the-fly z .omap).
    Korpus (mrkla): resources/livelox/<cid>/gen/. Dev (ntbhej smoke): maps/<lokalita>/."""
    for cand in (_CORPUS / name / "gen", _MAPS / name):
        has_omap = (cand / f"{cand.name}.omap").exists() or bool(list(cand.glob("*.omap")))
        if (cand / "rgb.png").exists() and (cand / "meta.json").exists() and has_omap:
            return cand
    return None


def tile_one(pair_dir: Path, split_name: str, cid: str) -> Counter:
    """Nakrájí jeden pár (pair_dir) → PNG dlaždice do resources/line_tiles/<split>/<cid>/.

    Y (liniový label) se počítá on-the-fly z .omap+meta (rasterize_lines_map_dir), bez duplicitních masek
    z pairs.py. Vrací Counter line labelů přes VŠECHNY dlaždice téhle mapy (pro statistiku/váhy)."""
    x = np.asarray(Image.open(pair_dir / "rgb.png").convert("RGB"), dtype=np.uint8)
    y = rasterize_lines_map_dir(pair_dir)                   # (H,W) uint8, 0..N_LINE-1
    if y.shape != x.shape[:2]:
        raise RuntimeError(f"line label {y.shape} != scan {x.shape[:2]} v {pair_dir}")

    # Resample X+Y na kanonické měřítko dlaždice (Sez. 126) PŘED tilingem — stejný faktor pro oba.
    src_mpp = read_src_mpp(pair_dir)
    x = resample_to_mpp(x, src_mpp)                 # RGB → bilineár
    y = resample_to_mpp(y, src_mpp, label=True)     # label → nearest (bez míchání tříd)

    H, W = y.shape
    out_dir = _TILES_DIR / split_name / cid
    out_dir.mkdir(parents=True, exist_ok=True)

    counts: Counter = Counter()
    for r, y0 in enumerate(_positions(H)):
        for c, x0 in enumerate(_positions(W)):
            tx = _crop(x, y0, x0)
            ty = _crop(y, y0, x0)
            Image.fromarray(tx).save(out_dir / f"{r}_{c}_x.png")
            Image.fromarray(ty, mode="L").save(out_dir / f"{r}_{c}_y.png")
            v, n = np.unique(ty, return_counts=True)
            counts.update(dict(zip(v.tolist(), n.tolist())))
    return counts


def _median_freq_weights(counts: Counter) -> list[float]:
    """Median-frequency balancing (Eigen & Fergus 2015): w_c = median(freq) / freq_c.

    Linie jsou EXTRÉMNĚ vzácné (watercourse << 1 % px i s nafouklou GT) → bez vážení by model
    predikoval samé pozadí. Vrací list[N_LINE] (pořadí 0..N_LINE-1) přímo do CrossEntropyLoss(weight=)."""
    total = sum(counts.get(c, 0) for c in range(N_LINE))
    if not total:
        return [0.0] * N_LINE
    freqs = [counts.get(c, 0) / total for c in range(N_LINE)]
    med = float(np.median([f for f in freqs if f > 0]))   # medián jen z přítomných tříd
    return [round(med / f, 4) if f > 0 else 0.0 for f in freqs]


def _dist(counts: Counter) -> dict:
    """Class distribuce v % (pozadí včetně) — pro souhrn v _tiles.json."""
    total = sum(counts.get(c, 0) for c in range(N_LINE))
    return {LINE_LABEL_NAME[c]: round(100 * counts.get(c, 0) / total, 3)
            for c in range(N_LINE)} if total else {}


def _write_tiles_json(per_split: dict, source: str) -> dict:
    """Sestaví + zapíše resources/line_tiles/_tiles.json (váhy z TRAIN dlaždic). Vrací dict."""
    weights = _median_freq_weights(per_split["train"]["counts"])
    out = {
        "_meta": {
            "generated": "model/png2line/tile.py (Sez. 130, Png2Line)",
            "source": source, "tile": TILE, "stride": STRIDE, "n_line": N_LINE,
            "target_mpp": CANONICAL_MPP,   # měřítko dlaždice [m/px] — páry resamplované sem (Sez. 126)
        },
        "class_weights_train": {LINE_LABEL_NAME[c]: weights[c] for c in range(N_LINE)},
        "class_weights_list": weights,    # pořadí 0..N_LINE-1 pro CrossEntropyLoss(weight=)
        "splits": {
            s: {"n_maps": v["n_maps"], "n_tiles": v["n_tiles"], "class_pct": _dist(v["counts"])}
            for s, v in per_split.items()
        },
    }
    _TILES_DIR.mkdir(parents=True, exist_ok=True)
    (_TILES_DIR / "_tiles.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def build_tiles(allow_missing: bool = False) -> dict:
    """Korpus (mrkla): projde split train/val/test, nakrájí všechny páry → _tiles.json.

    No silent fallback (Sez. 110): prázdný split → selži; chybějící páry → selži se seznamem CID,
    ledaže allow_missing=True (vědomý resume proti rozjetému build_pairs)."""
    import logging
    log = logging.getLogger("line_tile")

    if not split.load_split():
        raise RuntimeError(
            "build_tiles: split je prázdný — chybí nebo je prázdný resources/livelox/_split.json. "
            "Spusť `python connectors/split.py` PŘED tiling. (no silent fallback, Sez. 110)")

    per_split = {}
    missing_all: list[str] = []
    for s in ("train", "val", "test"):
        cids = [d.name for d in split.dirs_for(s)]
        resolved = [(cid, _resolve_pair_dir(cid)) for cid in cids]
        missing = [cid for cid, pd in resolved if pd is None]
        missing_all += [f"{s}:{cid}" for cid in missing]
        pairs = [(cid, pd) for cid, pd in resolved if pd is not None]
        if missing:
            log.warning("[%s] %d/%d map bez páru (rgb/omap/meta chybí): %s", s, len(missing), len(cids),
                        ", ".join(missing))
        agg: Counter = Counter()
        n_tiles = 0
        for i, (cid, pd) in enumerate(sorted(pairs), 1):
            c = tile_one(pd, s, cid)
            n = len(list((_TILES_DIR / s / cid).glob("*_y.png")))
            n_tiles += n
            agg.update(c)
            log.info("[%s %d/%d] %s -> %d dlaždic", s, i, len(pairs), cid, n)
        per_split[s] = {"counts": agg, "n_tiles": n_tiles, "n_maps": len(pairs)}
    if missing_all and not allow_missing:
        raise RuntimeError(
            f"build_tiles: {len(missing_all)} map ve splitu nemá pár (rgb/omap/meta) — "
            f"dokonči build_pairs, nebo spusť s allow_missing=True. Chybí: {', '.join(missing_all)} "
            f"(no silent fallback, Sez. 110)")
    return _write_tiles_json(per_split, source="corpus (split.py)")


def build_tiles_dev(names: list[str], split_name: str = "train") -> dict:
    """Dev smoke (ntbhej): nakrájí dané dev mapy z maps/ → line_tiles/<split>/ + _tiles.json."""
    import logging
    log = logging.getLogger("line_tile")
    agg: Counter = Counter()
    n_tiles = 0
    used = 0
    for name in names:
        pd = _resolve_pair_dir(name)
        if pd is None:
            log.warning("dev mapa %r nemá rgb.png + .omap + meta.json — přeskakuji", name)
            continue
        c = tile_one(pd, split_name, name)
        n = len(list((_TILES_DIR / split_name / name).glob("*_y.png")))
        n_tiles += n
        used += 1
        agg.update(c)
        log.info("[dev] %s -> %d dlaždic", name, n)
    if not used:
        raise RuntimeError(f"žádná z dev map {names} nemá pár (rgb.png + .omap + meta.json)")
    per_split = {split_name: {"counts": agg, "n_tiles": n_tiles, "n_maps": used}}
    for s in ("train", "val", "test"):
        per_split.setdefault(s, {"counts": Counter(), "n_tiles": 0, "n_maps": 0})
    return _write_tiles_json(per_split, source=f"dev maps/ {names}")


def make_preview(n: int = 6) -> Path:
    """Vizuální verify: mozaika n train dlaždic s NEJVÍC liniemi, X (sken) nad Y (barevný line label)."""
    train_dir = _TILES_DIR / "train"
    ypaths = sorted(train_dir.glob("*/*_y.png"))
    if not ypaths:
        raise RuntimeError("žádné train dlaždice — spusť nejdřív build_tiles()/build_tiles_dev()")

    scored = []
    for p in ypaths:
        ty = np.asarray(Image.open(p))
        scored.append(((ty > 0).mean(), p))        # podíl linie (vybrat dlaždice, kde linie reálně je)
    scored.sort(reverse=True)
    picks = [p for _, p in scored[:n]]

    cell = TILE
    canvas = Image.new("RGB", (cell * len(picks), cell * 2), (40, 40, 40))
    for i, yp in enumerate(picks):
        xp = yp.with_name(yp.name.replace("_y.png", "_x.png"))
        canvas.paste(Image.open(xp).convert("RGB"), (i * cell, 0))
        ty = np.asarray(Image.open(yp))
        canvas.paste(colorize_lines(ty), (i * cell, cell))
    canvas = canvas.resize((cell * len(picks) // 2, cell), Image.NEAREST)
    out = _TILES_DIR / "_preview.png"
    canvas.save(out)
    return out


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        sys.stdout.reconfigure(encoding="utf-8")     # Windows cp1250 vs Unicode (Sez. 74)
    except Exception:
        pass

    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        names = sys.argv[2:] or ["Soví vrch"]
        res = build_tiles_dev(names)
    else:
        # --allow-missing = vědomý resume proti neúplnému build_pairs (mapy bez páru se zalogují a přeskočí)
        res = build_tiles(allow_missing="--allow-missing" in sys.argv[1:])

    print("\n=== line dlaždice hotové ===")
    for s, v in res["splits"].items():
        print(f"{s:<6} {v['n_maps']:>3} map  {v['n_tiles']:>6} dlaždic   class%: {v['class_pct']}")
    print("\nmedian-freq váhy (train, pořadí 0..N_LINE-1):")
    for name, w in res["class_weights_train"].items():
        print(f"  {name:<12} {w}")
    p = make_preview()
    print(f"\nnáhled: {p}")
