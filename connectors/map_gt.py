"""
map_gt.py — GT segmentace runnability z reálné ISOM rastrové mapy (UC5 ground-truth).

Účel (UC5 runnability korpus, Sez. 68): UC5 model predikuje běhatelnost (zelená škála +
žlutá open) z dat (ortofoto/DMR/věk). Je supervised → potřebuje GT = co kartograf nakreslil.
Tento modul vytáhne GT z reálné mapy klasifikací pixelů na ISOM barevné třídy.

Obecné (jakákoli ISOM rastrová mapa → GT), oddělené od stahování (livelox.py stahuje,
map_gt segmentuje — SLAP). Zatím jediný zdroj map = Livelox korpus resources/livelox/.

Metoda (ověřeno probe Sez. 68 na 4 mapách):
  1) nearest-color klasifikace na ISOM referenční barvy
  2) majority (medián) filtr → potlačí tenké linie uvnitř ploch (vrstevnice/cesty/symboly);
     plošná runnability chce DOMINANTNÍ barvu okolí, ne per-pixel šum
  3) tři zelené úrovně → tři runnability stupně, žlutá → open, zbytek → průchodné/bílá

Omezení (doložené probe): olivová 520 (oplocené areály) NENÍ v refs → klasifikuje se jako
brown/green; pro runnability GT nevadí (520 = out-of-bounds, ne běhatelnost). Voda/budovy/
skály se z runnability masky vyřazují (label 0 = podklad).

Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CORPUS_DIR = _REPO_ROOT / "resources" / "livelox"

# ISOM referenční barvy (RGB) pro klasifikaci pixelů nejbližší barvou.
# SSoT = generator/compare_real_vs_gen.py ISOM_REF (Sez. 64). KOPIE (ne import) — connectors
# nemají záviset na generator/. DRY dluh: až bude 3. konzument, vytáhnout do sdíleného modulu
# (princip „generalizuj jen s důkazem"). TODO zaznamenán.
ISOM_REF = {
    "white": (255, 255, 255), "yellow": (252, 221, 118), "road": (240, 170, 120),
    "brown": (191, 105, 37), "blue": (50, 162, 222), "black": (30, 30, 30),
    "green_l": (200, 232, 200), "green_m": (120, 200, 140), "green_d": (40, 160, 90),
}

# runnability label: 0 = průchodný/podklad (bílá, voda, vrstevnice, symboly), 1-3 = zelená
# škála (406 slow / 408 walk / 410 fight), 4 = open land (žlutá). Mapuje ISOM třídu → label.
_LABEL = {
    "white": 0, "brown": 0, "black": 0, "blue": 0,
    "green_l": 1, "green_m": 2, "green_d": 3,
    "yellow": 4, "road": 4,   # road (oranžová silnic) splývá s open žlutou (jako compare GROUP)
}
# barva pro vizualizaci labelu (ISOM-like)
_LABEL_VIS = {
    0: (255, 255, 255),       # průchodný/podklad
    1: (200, 232, 200),       # 406 slow
    2: (120, 200, 140),       # 408 walk
    3: (40, 160, 90),         # 410 fight
    4: (252, 221, 118),       # open
}
# popis labelů (pro report)
LABEL_NAME = {0: "průchodný", 1: "406 slow", 2: "408 walk", 3: "410 fight", 4: "open"}

# velikost okna majority filtru (px). Na ~1,33 m/px je 7 px ≈ 9 m — potlačí vrstevnici/cestu
# uvnitř plochy, zachová plošný tvar. Laděno probe Sez. 68.
_MEDIAN_SIZE = 7


def _classify(rgb: np.ndarray) -> np.ndarray:
    """Každý pixel → label (0-4) přes nejbližší ISOM barvu. Vrací (H,W) uint8."""
    keys = list(ISOM_REF)
    refs = np.array([ISOM_REF[k] for k in keys], dtype=np.int32)
    flat = rgb.reshape(-1, 3).astype(np.int32)   # int32: 255²·3 přeteče int16
    d = ((flat[:, None, :] - refs[None, :, :]) ** 2).sum(2)
    color_idx = d.argmin(1)
    # mapuj index barvy → runnability label
    idx_to_label = np.array([_LABEL[k] for k in keys], dtype=np.uint8)
    return idx_to_label[color_idx].reshape(rgb.shape[:2])


def segment_gt(map_png: str | Path, out_dir: str | Path | None = None) -> dict:
    """Z map.png vytvoří GT: gt_labels.png (index) + gt_vis.png (barevná). Vrací rozpad %.

    out_dir default = adresář vstupní mapy (vedle map.png/meta.json v korpusu).
    """
    map_png = Path(map_png)
    out_dir = Path(out_dir) if out_dir else map_png.parent
    rgb = np.asarray(Image.open(map_png).convert("RGB"))

    labels = _classify(rgb)
    # majority filtr potlačí tenké ne-plošné linie uvnitř ploch
    labels = ndimage.median_filter(labels, size=_MEDIAN_SIZE)

    # ulož index mapu (trénink) + barevnou vizualizaci (verify)
    Image.fromarray(labels, mode="L").save(out_dir / "gt_labels.png")
    vis = np.zeros((*labels.shape, 3), np.uint8)
    for lab, col in _LABEL_VIS.items():
        vis[labels == lab] = col
    Image.fromarray(vis).save(out_dir / "gt_vis.png")

    tot = labels.size
    breakdown = {LABEL_NAME[lab]: float(round(100 * (labels == lab).sum() / tot, 1))
                 for lab in sorted(_LABEL_VIS)}
    return breakdown


def segment_corpus() -> None:
    """Projde celý korpus resources/livelox/* a vytvoří GT u každé mapy s map.png."""
    for d in sorted(_CORPUS_DIR.iterdir()):
        mp = d / "map.png"
        if mp.exists():
            bd = segment_gt(mp)
            print(f"{d.name}: {bd}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # jeden classId
        bd = segment_gt(_CORPUS_DIR / sys.argv[1] / "map.png")
        print(f"{sys.argv[1]}: {bd}")
    else:
        segment_corpus()
