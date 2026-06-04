"""
tile.py — příprava tréninkových dlaždic UC5 runnability modelu (Sez. 77, krok 4).

⟲ ARCHIVOVÁNO (Sez. 79) — směr `ortofoto → 4 runnability barvy` je DOLOŽENÁ slepá ulička
(val mIoU strop ~0,25, Sez. 78: podrost pod korunami z ortofota shora nevidět). Kód NEMAZÁN
(je to doložený nález „tudy ne"). Aktuální směr Laboratoře = `reconstructor()` (sken → `.omap`),
viz GLOSSARY `generator()`/`reconstructor()` + docs/TODO. Dlaždicová/split/GT pipeline ale
zůstává znovupoužitelná pro budoucí modely (Png2Polygon aj.).

Páry (X=ortho.png, Y=gt_grid.png) z Livelox korpusu jsou různě velké (~800–4000 px)
a U-Net jede na fixní dlaždici. Tenhle skript nakrájí každý pár na 512×512 dlaždice
s 50% překryvem (stride 256) a uloží je jako PNG dvojice do resources/tiles/<split>/.

Proč pre-tiling (a ne random-crop za běhu): deterministické (vizuálně zkontrolovatelné),
malé soubory = rychlé IO při tréninku, statistika/váhy se spočítají jednou. Augmentace
(flip/rot/jas) se přidá AŽ v loaderu za běhu — hustší překryv by jen kopíroval patche
(volba Sez. 77: stride 256, ne 128).

Split (train/val/test) dědíme z connectors/split.py — dlaždice jedné mapy jdou CELÉ do
splitu té mapy (žádný leak: split je geografický, Sez. 76).

Výstup:
  resources/tiles/<split>/<cid>/<r>_<c>_x.png   = X (RGB 512×512)
  resources/tiles/<split>/<cid>/<r>_<c>_y.png   = Y (label 0-4/255, mode L)
  resources/tiles/_tiles.json                   = počty + class distribuce + median-freq váhy
  resources/tiles/_preview.png                  = vizuální verify (mozaika X|Y vzorků)

Sys.path skript (fáze B, ne balík). Spouštět z kořene repa: `python model/runnability/tile.py`.
(Přesunuto do model/runnability/ v Sez. 88 — symetrie s model/png2area/ reconstructor modelem.)
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[2]   # model/runnability/ → o úroveň hloub (Sez. 88)
_TILES_DIR = _REPO_ROOT / "resources" / "tiles"

# connectors na path (split + map_gt konstanty)
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
import split                                   # noqa: E402
from map_gt import IGNORE, LABEL_NAME, N_CLASS, _LABEL_VIS   # noqa: E402

Image.MAX_IMAGE_PIXELS = None                  # páry jsou velké, vypnout PIL decompression bomb guard

TILE = 512          # strana dlaždice (px) — vstup U-Netu (@1,33 m/px ≈ 680 m kontext)
STRIDE = 256        # posun okna (px) → 50% překryv (volba Sez. 77)
MIN_VALID = 0.30    # dlaždice s méně než 30% validních (≠IGNORE) px zahodíme (rohy quadu, layout)
# N_CLASS (= 5, runnability třídy 0..4) se importuje z map_gt (SSoT, audit Sez. 81)


def _positions(length: int) -> list[int]:
    """Počáteční souřadnice okna TILE podél osy délky `length`, stride STRIDE.

    Poslední okno se ZAROVNÁ k okraji (length-TILE), ať se okrajový pruh neztratí.
    Když je mapa menší než TILE, vrátí jedinou pozici 0 (dlaždice se pak dopaduje).
    """
    if length <= TILE:
        return [0]
    pos = list(range(0, length - TILE + 1, STRIDE))
    # doplň poslední zarovnanou k okraji (pokud poslední krok nedošel až na konec)
    if pos[-1] != length - TILE:
        pos.append(length - TILE)
    return pos


def _crop(arr: np.ndarray, y0: int, x0: int, fill) -> np.ndarray:
    """Vyřízne TILE×TILE z `arr` od (y0,x0). Když mapa < TILE, dopaduje `fill` doprava/dolů.

    arr je (H,W) label nebo (H,W,3) RGB. fill = hodnota výplně (IGNORE pro Y, 0 pro X).
    """
    H, W = arr.shape[:2]
    h = min(TILE, H - y0)
    w = min(TILE, W - x0)
    if h == TILE and w == TILE:
        return arr[y0:y0 + TILE, x0:x0 + TILE]
    # menší kus → pad do plné dlaždice (fill); shape dopočítáme dle počtu kanálů
    shape = (TILE, TILE) + arr.shape[2:]
    out = np.full(shape, fill, dtype=arr.dtype)
    out[:h, :w] = arr[y0:y0 + h, x0:x0 + w]
    return out


def tile_one(cid_dir: Path, split_name: str) -> Counter:
    """Nakrájí jeden pár (cid_dir) → PNG dlaždice do resources/tiles/<split>/<cid>/.

    Vrací Counter labelů přes VŠECHNY uložené dlaždice téhle mapy (pro statistiku/váhy).
    Dlaždice pod prahem MIN_VALID se přeskočí (neuloží, nezapočítají).
    """
    x = np.asarray(Image.open(cid_dir / "ortho.png").convert("RGB"), dtype=np.uint8)
    y = np.asarray(Image.open(cid_dir / "gt_grid.png"), dtype=np.uint8)
    if y.shape != x.shape[:2]:
        raise RuntimeError(f"gt_grid {y.shape} != ortho {x.shape[:2]} v {cid_dir}")

    H, W = y.shape
    out_dir = _TILES_DIR / split_name / cid_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    counts = Counter()
    for r, y0 in enumerate(_positions(H)):
        for c, x0 in enumerate(_positions(W)):
            ty = _crop(y, y0, x0, IGNORE)
            valid = (ty != IGNORE).mean()      # podíl validních (běhatelnostních) px
            if valid < MIN_VALID:
                continue                       # skoro prázdná dlaždice → zahodit
            tx = _crop(x, y0, x0, 0)
            Image.fromarray(tx).save(out_dir / f"{r}_{c}_x.png")
            Image.fromarray(ty, mode="L").save(out_dir / f"{r}_{c}_y.png")
            v, n = np.unique(ty, return_counts=True)
            counts.update(dict(zip(v.tolist(), n.tolist())))
    return counts


def _median_freq_weights(counts: Counter) -> list[float]:
    """Median-frequency balancing (Eigen & Fergus 2015): w_c = median(freq) / freq_c.

    freq_c = počet px třídy c / celkem validních px. Vzácné třídy (410 fight) dostanou
    velkou váhu, časté (průchodný) malou. IGNORE se do výpočtu nepočítá. Vrací list[5].
    """
    total = sum(counts.get(c, 0) for c in range(N_CLASS))
    freqs = [counts.get(c, 0) / total for c in range(N_CLASS)]
    med = float(np.median([f for f in freqs if f > 0]))   # medián jen z přítomných tříd
    return [round(med / f, 4) if f > 0 else 0.0 for f in freqs]


def build_tiles() -> dict:
    """Projde train/val/test, nakrájí všechny páry, spočítá statistiku → zapíše _tiles.json.

    Vrací výsledný dict (i s váhami počítanými z TRAIN dlaždic po rejection).
    """
    import logging
    log = logging.getLogger("tile")

    per_split = {}                             # split -> {"counts": Counter, "n_tiles": int, "n_maps": int}
    for s in ("train", "val", "test"):
        dirs = [d for d in split.dirs_for(s) if (d / "ortho.png").exists()]
        agg = Counter()
        n_tiles = 0
        for i, d in enumerate(sorted(dirs), 1):
            c = tile_one(d, s)
            # počet dlaždic = počet uložených _y.png v adresáři mapy
            n = len(list((_TILES_DIR / s / d.name).glob("*_y.png")))
            n_tiles += n
            agg.update(c)
            log.info("[%s %d/%d] %s -> %d dlaždic", s, i, len(dirs), d.name, n)
        per_split[s] = {"counts": agg, "n_tiles": n_tiles, "n_maps": len(dirs)}

    weights = _median_freq_weights(per_split["train"]["counts"])

    def _dist(counts: Counter) -> dict:
        labeled = sum(counts.get(c, 0) for c in range(N_CLASS))
        return {LABEL_NAME[c]: round(100 * counts.get(c, 0) / labeled, 2)
                for c in range(N_CLASS)} if labeled else {}

    out = {
        "_meta": {
            "generated": "model/runnability/tile.py (Sez. 77, krok 4)",
            "tile": TILE, "stride": STRIDE, "min_valid": MIN_VALID,
            "n_class": N_CLASS,
        },
        "class_weights_train": {LABEL_NAME[c]: weights[c] for c in range(N_CLASS)},
        "class_weights_list": weights,    # pořadí 0..4 pro přímé dosazení do CrossEntropyLoss(weight=)
        "splits": {
            s: {"n_maps": v["n_maps"], "n_tiles": v["n_tiles"],
                "class_pct": _dist(v["counts"])}
            for s, v in per_split.items()
        },
    }
    _TILES_DIR.mkdir(parents=True, exist_ok=True)
    (_TILES_DIR / "_tiles.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def make_preview(n: int = 6) -> Path:
    """Vizuální verify: mozaika n train dlaždic, X (ortho) nad Y (barevný label). → _preview.png.

    Vybírá dlaždice s nejvyšším podílem vzácných tříd (410 fight), ať je na náhledu vidět
    runnability signál, ne jen bílý průchodný les.
    """
    train_dir = _TILES_DIR / "train"
    ypaths = sorted(train_dir.glob("*/*_y.png"))
    if not ypaths:
        raise RuntimeError("žádné train dlaždice — spusť nejdřív build_tiles()")

    # skóre dlaždice = podíl zelených tříd 1-3 (zajímavější než bílý les) → top n
    scored = []
    for p in ypaths:
        ty = np.asarray(Image.open(p))
        green = np.isin(ty, (1, 2, 3)).mean()
        scored.append((green, p))
    scored.sort(reverse=True)
    picks = [p for _, p in scored[:n]]

    cell = TILE
    canvas = Image.new("RGB", (cell * n, cell * 2), (40, 40, 40))
    for i, yp in enumerate(picks):
        xp = yp.with_name(yp.name.replace("_y.png", "_x.png"))
        canvas.paste(Image.open(xp).convert("RGB"), (i * cell, 0))
        ty = np.asarray(Image.open(yp))
        vis = np.zeros((*ty.shape, 3), np.uint8)
        for lab, col in _LABEL_VIS.items():
            vis[ty == lab] = col
        canvas.paste(Image.fromarray(vis), (i * cell, cell))
    # zmenši, ať náhled není obří
    canvas = canvas.resize((cell * n // 2, cell), Image.NEAREST)
    out = _TILES_DIR / "_preview.png"
    canvas.save(out)
    return out


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    res = build_tiles()
    print("\n=== dlaždice hotové ===")
    for s, v in res["splits"].items():
        print(f"{s:<6} {v['n_maps']:>3} map  {v['n_tiles']:>6} dlaždic   "
              f"class%: {v['class_pct']}")
    print("\nmedian-freq váhy (train, pořadí 0..4):")
    for name, w in res["class_weights_train"].items():
        print(f"  {name:<12} {w}")
    p = make_preview()
    print(f"\nnáhled: {p}")
