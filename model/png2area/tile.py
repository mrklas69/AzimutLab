"""
tile.py — příprava tréninkových dlaždic reconstructor modelu Png2Area (Sez. 88).

Role v pipeline (reframe Sez. 79/80): reconstructor() se učí z páru [scan.png, area_labels.png]
(X = degradovaný render, Sez. 86; Y = label rastr plošných ISOM symbolů, omap_raster Sez. 87).
Tohle je první ze tří CV úloh dekompozice podle OOM geometrie: Png2Area (plochy) | Png2Point | Png2Line.
Páry vyrábí generator/pairs.py build_pair (korpus → resources/livelox/<cid>/gen/, dev → maps/<lokalita>/).

Páry jsou různě velké (~800–4000 px korpus, ~4500 px dev) a U-Net jede na fixní dlaždici. Tenhle skript
nakrájí každý pár na 512×512 dlaždice s 50% překryvem (stride 256) a uloží je jako PNG dvojice do
resources/area_tiles/<split>/. Izomorfní s archivovaným model/runnability/tile.py (runnability směr) —
liší se: X=scan místo ortho, Y=area_labels místo gt_grid, 16 area tříd místo 5, BEZ rejection (níže).

Proč BEZ rejection dlaždic (na rozdíl od archivu): scan.png je plný obdélníkový render — žádné IGNORE,
žádné prázdné rohy quadu. Pozadí (label 0) je LEGITIMNÍ třída „tady žádná plocha" (bílý les), kterou se
model MUSÍ naučit — zahodit lesní dlaždice by ukrojilo právě tenhle signál. Nevyváženost (pozadí 60–90 %)
řeší median-freq váhy, ne rejection (volba Sez. 88).

Split (train/val/test) dědíme z connectors/split.py (geografický, bez leaku, Sez. 76) — STEJNÝ zdroj jako
archiv; dlaždice jedné mapy jdou CELÉ do splitu té mapy. Korpus je jen na mrkla (copyright) → na ntbhej se
smoke-testuje přes dev mapy z maps/ (build_tiles_dev), které korpus nepotřebují.

Výstup:
  resources/area_tiles/<split>/<cid>/<r>_<c>_x.png   = X (sken RGB 512×512)
  resources/area_tiles/<split>/<cid>/<r>_<c>_y.png   = Y (area label 0..15, mode L)
  resources/area_tiles/_tiles.json                   = počty + class distribuce + median-freq váhy
  resources/area_tiles/_preview.png                  = vizuální verify (mozaika X|Y vzorků)

Sys.path skript (fáze B, ne balík). Spouštět z kořene repa:
  python model/png2area/tile.py             # korpus přes split (mrkla, po nočním build_pairs)
  python model/png2area/tile.py dev "Soví vrch"   # smoke na dev mapě z maps/ (ntbhej)
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[2]   # model/png2area/ → o dvě úrovně hloub
_TILES_DIR = _REPO_ROOT / "resources" / "area_tiles"
_CORPUS = _REPO_ROOT / "resources" / "livelox"
_MAPS = _REPO_ROOT / "maps"

# connectors (split) + generator (omap_raster: SSoT area tříd) na path
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))
import split                                                # noqa: E402
from omap_raster import N_AREA, LABEL_NAME, LABEL_VIS, colorize   # noqa: E402

Image.MAX_IMAGE_PIXELS = None                  # páry jsou velké, vypnout PIL decompression bomb guard

TILE = 512          # strana dlaždice (px) — vstup U-Netu
STRIDE = 256        # posun okna (px) → 50% překryv (volba Sez. 77, sdíleno s archivem)
# N_AREA (= 16: pozadí + 15 area kódů) se importuje z omap_raster (SSoT label schématu, Sez. 87).
# BEZ MIN_VALID rejection (viz hlavička) — všechny dlaždice plného renderu jsou validní.


def _positions(length: int) -> list[int]:
    """Počáteční souřadnice okna TILE podél osy `length`, stride STRIDE.

    Poslední okno se ZAROVNÁ k okraji (length-TILE), ať se okrajový pruh neztratí. Mapa menší
    než TILE → jediná pozice 0 (dlaždice se dopaduje). Identické s archivem (DRY dluh: extrakce
    sdíleného tiling helperu až by vznikl 3. konzument — princip generalizuj-jen-s-důkazem)."""
    if length <= TILE:
        return [0]
    pos = list(range(0, length - TILE + 1, STRIDE))
    if pos[-1] != length - TILE:
        pos.append(length - TILE)
    return pos


def _crop(arr: np.ndarray, y0: int, x0: int) -> np.ndarray:
    """Vyřízne TILE×TILE z `arr` od (y0,x0). Když mapa < TILE, dopaduje 0 doprava/dolů.

    arr je (H,W) label nebo (H,W,3) RGB. Fill = 0 pro OBA (pro Y = pozadí, pro X = černá) —
    na rozdíl od archivu (Y fill IGNORE) tu IGNORE není; paddingové pixely = legitimní pozadí."""
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
    """název (cid / lokalita) → adresář s párem scan.png + area_labels.png, nebo None.

    Korpus (mrkla): resources/livelox/<cid>/gen/. Dev (ntbhej smoke): maps/<lokalita>/.
    Vrací první existující; None když pár chybí (build_pair ještě neproběhl / není scan)."""
    for cand in (_CORPUS / name / "gen", _MAPS / name):
        if (cand / "area_labels.png").exists() and (cand / "scan.png").exists():
            return cand
    return None


def tile_one(pair_dir: Path, split_name: str, cid: str) -> Counter:
    """Nakrájí jeden pár (pair_dir) → PNG dlaždice do resources/area_tiles/<split>/<cid>/.

    Vrací Counter area labelů přes VŠECHNY dlaždice téhle mapy (pro statistiku/váhy)."""
    x = np.asarray(Image.open(pair_dir / "scan.png").convert("RGB"), dtype=np.uint8)
    y = np.asarray(Image.open(pair_dir / "area_labels.png"), dtype=np.uint8)
    if y.shape != x.shape[:2]:
        raise RuntimeError(f"area_labels {y.shape} != scan {x.shape[:2]} v {pair_dir}")

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

    freq_c = px třídy c / celkem px. Vzácné plochy (mokřad/balvany) dostanou velkou váhu, časté
    (pozadí) malou. Vrací list[N_AREA] v pořadí 0..N_AREA-1 (přímo do CrossEntropyLoss(weight=))."""
    total = sum(counts.get(c, 0) for c in range(N_AREA))
    if not total:
        return [0.0] * N_AREA
    freqs = [counts.get(c, 0) / total for c in range(N_AREA)]
    med = float(np.median([f for f in freqs if f > 0]))   # medián jen z přítomných tříd
    return [round(med / f, 4) if f > 0 else 0.0 for f in freqs]


def _dist(counts: Counter) -> dict:
    """Class distribuce v % (pozadí včetně) — pro souhrn v _tiles.json."""
    total = sum(counts.get(c, 0) for c in range(N_AREA))
    return {LABEL_NAME[c]: round(100 * counts.get(c, 0) / total, 2)
            for c in range(N_AREA)} if total else {}


def _write_tiles_json(per_split: dict, source: str) -> dict:
    """Sestaví + zapíše resources/area_tiles/_tiles.json (váhy z TRAIN dlaždic). Vrací dict."""
    weights = _median_freq_weights(per_split["train"]["counts"])
    out = {
        "_meta": {
            "generated": "model/png2area/tile.py (Sez. 88, Png2Area)",
            "source": source, "tile": TILE, "stride": STRIDE, "n_area": N_AREA,
        },
        "class_weights_train": {LABEL_NAME[c]: weights[c] for c in range(N_AREA)},
        "class_weights_list": weights,    # pořadí 0..N_AREA-1 pro CrossEntropyLoss(weight=)
        "splits": {
            s: {"n_maps": v["n_maps"], "n_tiles": v["n_tiles"], "class_pct": _dist(v["counts"])}
            for s, v in per_split.items()
        },
    }
    _TILES_DIR.mkdir(parents=True, exist_ok=True)
    (_TILES_DIR / "_tiles.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def build_tiles() -> dict:
    """Korpus (mrkla): projde split train/val/test, nakrájí všechny páry → _tiles.json.

    Zdroj = connectors/split.py (207 ČR keep, geo-split). Pár hledá v <cid>/gen/ (build_pairs).
    Mapy bez hotového páru (gen/ chybí) se přeskočí (resume-friendly proti rozjetému batchi)."""
    import logging
    log = logging.getLogger("area_tile")

    per_split = {}
    for s in ("train", "val", "test"):
        cids = [d.name for d in split.dirs_for(s)]
        pairs = [(cid, _resolve_pair_dir(cid)) for cid in cids]
        pairs = [(cid, pd) for cid, pd in pairs if pd is not None]
        agg: Counter = Counter()
        n_tiles = 0
        for i, (cid, pd) in enumerate(sorted(pairs), 1):
            c = tile_one(pd, s, cid)
            n = len(list((_TILES_DIR / s / cid).glob("*_y.png")))
            n_tiles += n
            agg.update(c)
            log.info("[%s %d/%d] %s -> %d dlaždic", s, i, len(pairs), cid, n)
        per_split[s] = {"counts": agg, "n_tiles": n_tiles, "n_maps": len(pairs)}
    return _write_tiles_json(per_split, source="corpus (split.py)")


def build_tiles_dev(names: list[str], split_name: str = "train") -> dict:
    """Dev smoke (ntbhej): nakrájí dané dev mapy z maps/ → area_tiles/<split>/ + _tiles.json.

    Korpus nepotřebuje (maps/ jsou veřejné dev rendery) → ověří celý tile→dataset řetězec na
    ntbhej, než noční batch na mrkla dodá korpusový set. Default split 'train' (dataset ho čte)."""
    import logging
    log = logging.getLogger("area_tile")
    agg: Counter = Counter()
    n_tiles = 0
    used = 0
    for name in names:
        pd = _resolve_pair_dir(name)
        if pd is None:
            log.warning("dev mapa %r nemá pár [scan.png, area_labels.png] — přeskakuji", name)
            continue
        c = tile_one(pd, split_name, name)
        n = len(list((_TILES_DIR / split_name / name).glob("*_y.png")))
        n_tiles += n
        used += 1
        agg.update(c)
        log.info("[dev] %s -> %d dlaždic", name, n)
    if not used:
        raise RuntimeError(f"žádná z dev map {names} nemá pár (scan.png + area_labels.png)")
    # smoke: jediný split nese statistiku i váhy (val/test prázdné placeholder)
    per_split = {split_name: {"counts": agg, "n_tiles": n_tiles, "n_maps": used}}
    for s in ("train", "val", "test"):
        per_split.setdefault(s, {"counts": Counter(), "n_tiles": 0, "n_maps": 0})
    return _write_tiles_json(per_split, source=f"dev maps/ {names}")


def make_preview(n: int = 6) -> Path:
    """Vizuální verify: mozaika n train dlaždic, X (sken) nad Y (barevný area label). → _preview.png.

    Vybírá dlaždice s nejvyšším podílem ne-pozadí (ať je na náhledu vidět plochy, ne bílý les).
    Y se barví reuse omap_raster.colorize/LABEL_VIS (DRY — stejná paleta jako Y-pipeline verify)."""
    train_dir = _TILES_DIR / "train"
    ypaths = sorted(train_dir.glob("*/*_y.png"))
    if not ypaths:
        raise RuntimeError("žádné train dlaždice — spusť nejdřív build_tiles()/build_tiles_dev()")

    scored = []
    for p in ypaths:
        ty = np.asarray(Image.open(p))
        scored.append(((ty > 0).mean(), p))        # podíl ne-pozadí (zajímavější než bílý les)
    scored.sort(reverse=True)
    picks = [p for _, p in scored[:n]]

    cell = TILE
    canvas = Image.new("RGB", (cell * len(picks), cell * 2), (40, 40, 40))
    for i, yp in enumerate(picks):
        xp = yp.with_name(yp.name.replace("_y.png", "_x.png"))
        canvas.paste(Image.open(xp).convert("RGB"), (i * cell, 0))
        ty = np.asarray(Image.open(yp))
        canvas.paste(colorize(ty), (i * cell, cell))
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
        res = build_tiles()

    print("\n=== area dlaždice hotové ===")
    for s, v in res["splits"].items():
        print(f"{s:<6} {v['n_maps']:>3} map  {v['n_tiles']:>6} dlaždic   class%: {v['class_pct']}")
    print("\nmedian-freq váhy (train, pořadí 0..N_AREA-1):")
    for name, w in res["class_weights_train"].items():
        print(f"  {name:<8} {w}")
    p = make_preview()
    print(f"\nnáhled: {p}")
