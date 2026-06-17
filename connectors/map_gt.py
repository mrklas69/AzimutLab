"""
map_gt.py — runnability + sémantická GT segmentace reálné ISOM rastrové mapy.

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

Kompatibilní `gt_labels.png` je nadále runnability maska: olivová 520 i voda v ní padají
na label 0. `gt_semantic_labels.png` však informaci zachovává jako 5=voda a 6=520;
vizualizace a `bg_gt.png` proto tyto plochy neztrácejí. Budovy/skály/vrstevnice zůstávají
podklad 0, protože samotná barva bez kontextu jejich přesný plošný symbol neurčí.

Fialový přetisk tratí (purpurová: kroužky kontrol, spojnice, start, čísla) NENÍ ISOM
runnability barva → label IGNORE (255), od Sez. 72. Trénink ho přeskočí (ignore_index v loss),
ne hádá co je pod ním. 31 % keep map ho nese (měření Sez. 72). Dvě purpurové reference
DOLOŽENÉ z reálných rastrů (magenta tratě 178/24/148 + fialovější 176/8/230). Maska se
dilatuje (antialiasovaný okraj čar) a aplikuje AŽ po median filtru (255 by zkreslil okno).

Layout mimo mapové území (legenda, control-description tabulka, titulek, tiráž, logo,
bílý papír kolem mapy) NENÍ běhatelný terén → taky label IGNORE (255), od Sez. 73 (část B).
Detekce z barevnosti (ne geometrie — ta byla křehká): mapa má sytou ISOM paletu
(zeleň/modř/hněď/žluť), mimo-mapové bloky jsou černobílé (mřížka/text) nebo bílý papír.
Dlaždicová mřížka → největší souvislá komponenta barevných dlaždic + fill holes = mapa
(vnitřní bílý les se vyplní), zbytek ignore. Konzervativní: barevné titulky/loga (žluté
pozadí) občas proklouznou jako mapa — radši drobná kontaminace label 0 než false-crop terénu.

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
# Základ = generator/compare_real_vs_gen.py ISOM_REF (Sez. 64), KOPIE (ne import) — connectors
# nemají záviset na generator/. DRY dluh: až bude 3. konzument, vytáhnout do sdíleného modulu
# (princip „generalizuj jen s důkazem"). TODO zaznamenán.
# ROZDÍL od compare (Sez. 71): map_gt přidává OLIVOVOU 520 (out-of-bounds), compare ji nemá —
# je runnability-specifická (compare Soví vrch žádnou olivovou neobsahuje). Dvě olivové reference
# = dva odstíny DOLOŽENÉ na korpusu (sprint vs lesní OCAD profil: 152/184/24 vs 168/168/56);
# bez nich padaly na green_m → falešná zelená runnability na městských mapách (Turnov, Sez. 70).
ISOM_REF = {
    "white": (255, 255, 255), "yellow": (252, 221, 118), "road": (240, 170, 120),
    "brown": (191, 105, 37), "blue": (50, 162, 222), "black": (30, 30, 30),
    "green_l": (200, 232, 200), "green_m": (120, 200, 140), "green_d": (40, 160, 90),
    "olive_a": (152, 184, 24), "olive_b": (168, 168, 56),   # 520 out-of-bounds (Sez. 71)
    "purple_a": (178, 24, 148), "purple_b": (176, 8, 230),  # přetisk tratě → ignore (Sez. 72)
}

# label pro pixely vyřazené z GT (trénink je přeskočí přes ignore_index v loss). 255 se vejde
# do uint8 a nekoliduje s runnability labely 0-4. Dva zdroje: purpurový přetisk tratí (Sez. 72)
# + layout mimo mapové území (legenda/tabulka/titulek/papír, Sez. 73).
IGNORE = 255

# klíče ISOM_REF, které tvoří MAPOVOU plochu (sytá paleta). white/black/purple = NE mapová
# plocha → slouží k detekci mapového území vs okraj (legenda/tabulka/titulek/papír). Sez. 73.
_MAP_COLOR_KEYS = {"yellow", "road", "brown", "blue",
                   "green_l", "green_m", "green_d", "olive_a", "olive_b"}

# runnability label: 0 = průchodný/podklad (bílá, voda, vrstevnice, symboly), 1-3 = zelená
# škála (406 slow / 408 walk / 410 fight), 4 = open land (žlutá). Mapuje ISOM třídu → label.
_LABEL = {
    "white": 0, "brown": 0, "black": 0, "blue": 0,
    "olive_a": 0, "olive_b": 0,   # 520 zákaz vstupu = podklad, NE běhatelnost (Sez. 71)
    "green_l": 1, "green_m": 2, "green_d": 3,
    "yellow": 4, "road": 4,   # road (oranžová silnic) splývá s open žlutou (jako compare GROUP)
    "purple_a": IGNORE, "purple_b": IGNORE,   # přetisk tratě = vyřadit z GT (Sez. 72)
}
# barva pro vizualizaci labelu (ISOM-like)
_LABEL_VIS = {
    0: (255, 255, 255),       # průchodný/podklad
    1: (200, 232, 200),       # 406 slow
    2: (120, 200, 140),       # 408 walk
    3: (40, 160, 90),         # 410 fight
    4: (252, 221, 118),       # open
    IGNORE: (255, 0, 255),    # přetisk + layout okraj (verify: magenta = co se vyřadilo)
}
# popis labelů (pro report)
LABEL_NAME = {0: "průchodný", 1: "406 slow", 2: "408 walk", 3: "410 fight", 4: "open",
              IGNORE: "ignore (přetisk+layout)"}
# počet runnability tříd 0..4 (IGNORE=255 je mimo). SSoT pro celý UC5 model — model/tile.py
# i model/train.py importují odtud, ať se „5" nedrží na dvou místech (DRY, nález audit Sez. 81).
N_CLASS = 5

# Sémantická plošná maska zachovává vedle runnability i třídy, které starý GT záměrně
# sléval do nuly. Čísla 0-4 jsou kompatibilní s runnability maskou; 5-6 jsou nové.
SEMANTIC_WATER = 5
SEMANTIC_OOB = 6
SEMANTIC_LABEL = {
    "white": 0, "brown": 0, "black": 0,
    "green_l": 1, "green_m": 2, "green_d": 3,
    "yellow": 4, "road": 4,
    "blue": SEMANTIC_WATER,
    "olive_a": SEMANTIC_OOB, "olive_b": SEMANTIC_OOB,
    "purple_a": IGNORE, "purple_b": IGNORE,
}
SEMANTIC_LABEL_VIS = {
    0: (255, 255, 255),
    1: (200, 232, 200),
    2: (120, 200, 140),
    3: (40, 160, 90),
    4: (252, 221, 118),
    SEMANTIC_WATER: (50, 162, 222),
    SEMANTIC_OOB: (168, 168, 56),
    IGNORE: (255, 0, 255),
}
SEMANTIC_LABEL_NAME = {
    0: "průchodný/podklad", 1: "406 slow", 2: "408 walk", 3: "410 fight",
    4: "open", SEMANTIC_WATER: "voda", SEMANTIC_OOB: "520 out-of-bounds",
    IGNORE: "ignore (přetisk+layout)",
}

# velikost okna majority filtru (px). Na ~1,33 m/px je 7 px ≈ 9 m — potlačí vrstevnici/cestu
# uvnitř plochy, zachová plošný tvar. Laděno probe Sez. 68.
_MEDIAN_SIZE = 7
# pixelový rozpočet jednoho chunku v _classify (Sez. 111). Nearest-color staví dočasné pole
# (N_chunk, 13, 3) int32 (~156 B/px), s temp od `(a-b)**2` peak ~2× → 4 Mpx ≈ 1,2 GB transient.
# Řez po řádcích drží peak konstantní bez ohledu na velikost mapy → segment_gt zvládne i 97 Mpx
# obří mapy (RAM strop ntbhej ~30 Mpx na celorázové alokaci, Sez. 110); výstup byte-identický.
_CLASSIFY_CHUNK_PX = 4_000_000
# dilatace přetisk-masky (px iterací 3×3): pokryje antialiasovaný okraj purpurových čar/kroužků,
# který nearest-color klasifikuje jako sousední barvu. 2 px ≈ 2,7 m na 1,33 m/px. Sez. 72.
_OVERPRINT_DILATE = 2

# layout detekce mapového území (Sez. 73): velikost dlaždice = 1/_TILE_DIV delší strany;
# dlaždice je "mapová" když podíl mapově-barevných pixelů > _MAP_TILE_FRAC; dilatace
# (v dlaždicích) scelí mapu přes řídké/bílé mezery před výběrem největší komponenty.
# Hodnoty laděné probe Sez. 73 na 12 mapách (4 s tabulkou/titulkem + 8 organických).
_TILE_DIV = 120
_MAP_TILE_FRAC = 0.04
_MAP_MERGE_DIL = 3
# Layout text MAPOVOU barvou (zelená „kategorie"/legenda) tvoří malý izolovaný ostrov dlaždic;
# scelovací dilatace ho jinak přilepí k mapě → falešný porost v separaci (Sez. 140, Borný).
# Před dilatací zahodíme ostrovy menší než tento zlomek největší komponenty (mapa je vždy
# největší). Černý text padá už dřív (černá není mapová barva); tohle řeší jen barevný layout.
_MAP_ISLAND_FRAC = 0.10


def _classify(rgb: np.ndarray) -> np.ndarray:
    """Každý pixel → index nejbližší ISOM barvy (do list(ISOM_REF)). Vrací (H,W) uint8.

    Vrací index barvy (ne rovnou label) — volající z něj odvodí jak runnability label
    (přes _LABEL), tak mapovou plochu (přes _MAP_COLOR_KEYS) jediným argmin (Sez. 73).

    Řez po řádcích (chunk ~_CLASSIFY_CHUNK_PX, Sez. 111): dočasné pole (N,13,3) int32 by na
    celé mapě přeteklo RAM (~5,5 GiB @ 35 Mpx → strop ntbhej ~30 Mpx). Per-pixel argmin je
    nezávislý → chunking je byte-identický s celorázovou klasifikací, jen drží peak konstantní.
    """
    refs = np.array([ISOM_REF[k] for k in ISOM_REF], dtype=np.int32)
    H, W = rgb.shape[:2]
    out = np.empty((H, W), dtype=np.uint8)       # 13 < 256 referencí → uint8 (index, ne label)
    rows = max(1, _CLASSIFY_CHUNK_PX // max(W, 1))
    for y0 in range(0, H, rows):
        y1 = min(y0 + rows, H)
        flat = rgb[y0:y1].reshape(-1, 3).astype(np.int32)   # int32: 255²·3 přeteče int16
        d = ((flat[:, None, :] - refs[None, :, :]) ** 2).sum(2)
        out[y0:y1] = d.argmin(1).reshape(y1 - y0, W)
    return out


def _detect_map_area(mappix: np.ndarray) -> np.ndarray:
    """Z masky mapově-barevných pixelů → bool maska mapového území (Sez. 73).

    True = mapa, False = okraj (legenda/tabulka/titulek/tiráž/logo/papír) → ignore.
    Dlaždicová mřížka potlačí šum; dilatace scelí mapu přes řídké/bílé oblasti;
    největší souvislá komponenta + fill_holes = mapa (vnitřní bílý les se vyplní).
    """
    H, W = mappix.shape
    T = max(max(H, W) // _TILE_DIV, 8)           # velikost dlaždice v px
    th, tw = H // T, W // T
    if th == 0 or tw == 0:
        return np.ones((H, W), bool)             # příliš malý obraz → neřeš
    # podíl mapově-barevných pixelů v každé dlaždici (ořež na násobek T, reshape, průměr)
    frac = mappix[:th * T, :tw * T].reshape(th, T, tw, T).mean((1, 3))
    maptile = frac > _MAP_TILE_FRAC
    # zahoď malé izolované ostrovy mapových dlaždic PŘED scelovací dilatací (barevný layout text
    # — zelená „kategorie" — by se jinak přilepil k mapě, Sez. 140). Mapa = vždy největší ostrov.
    lab0, n0 = ndimage.label(maptile)
    if n0 > 1:
        sizes0 = ndimage.sum(np.ones_like(lab0), lab0, range(1, n0 + 1))
        keep0 = np.flatnonzero(sizes0 >= _MAP_ISLAND_FRAC * sizes0.max()) + 1
        maptile = np.isin(lab0, keep0)
    # dilatace přimkne řídké okrajové oblasti mapy, pak největší komponenta + fill holes
    dil = ndimage.binary_dilation(maptile, iterations=_MAP_MERGE_DIL)
    lab, n = ndimage.label(dil)
    if n == 0:
        return np.ones((H, W), bool)             # žádná mapová barva → nech celé
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    biggest = int(np.argmax(sizes)) + 1
    m = ndimage.binary_fill_holes(lab == biggest)
    m = ndimage.binary_fill_holes(ndimage.binary_erosion(m, iterations=_MAP_MERGE_DIL))
    # dlaždicová maska → pixely (nearest resize pokryje celý obraz vč. ořezaného okraje)
    return np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize((W, H), Image.NEAREST)) > 0


def _categorical_majority(labels: np.ndarray, classes: tuple[int, ...],
                          size: int = _MEDIAN_SIZE) -> np.ndarray:
    """Kategoriální majority filtr bez předpokladu číselného pořadí labelů.

    `median_filter` je vhodný pro uspořádanou škálu runnability 0-4, ale pro nezávislé
    třídy voda/520 by výsledek závisel na libovolně přiděleném čísle. Počty sousedů
    počítáme po třídách; držíme jen aktuální maximum, takže paměť neroste s počtem tříd.
    """
    kernel = np.ones((size, size), dtype=np.uint8)
    best_count = np.zeros(labels.shape, dtype=np.uint16)
    result = np.zeros(labels.shape, dtype=np.uint8)
    for lab in classes:
        count = ndimage.convolve(
            (labels == lab).astype(np.uint8), kernel, mode="nearest", output=np.uint16
        )
        better = count > best_count
        result[better] = lab
        best_count[better] = count[better]
    return result


def colorize(labels: np.ndarray, palette: dict[int, tuple[int, int, int]]) -> np.ndarray:
    """Indexovou masku převede na RGB; neznámý label je tvrdá chyba."""
    unknown = set(np.unique(labels).tolist()) - set(palette)
    if unknown:
        raise ValueError(f"Maska obsahuje neznámé labely: {sorted(unknown)}")
    vis = np.zeros((*labels.shape, 3), np.uint8)
    for lab, col in palette.items():
        vis[labels == lab] = col
    return vis


def segment_gt(map_png: str | Path, out_dir: str | Path | None = None) -> dict:
    """Z map.png vytvoří runnability i sémantický GT. Vrací rozpad runnability v %.

    out_dir default = adresář vstupní mapy (vedle map.png/meta.json v korpusu).
    """
    map_png = Path(map_png)
    out_dir = Path(out_dir) if out_dir else map_png.parent
    rgb = np.asarray(Image.open(map_png).convert("RGB"))

    keys = list(ISOM_REF)
    color_idx = _classify(rgb)                   # index nejbližší ISOM barvy per pixel
    idx_to_label = np.array([_LABEL[k] for k in keys], dtype=np.uint8)
    labels = idx_to_label[color_idx]             # index barvy → runnability label
    idx_to_semantic = np.array([SEMANTIC_LABEL[k] for k in keys], dtype=np.uint8)
    semantic = idx_to_semantic[color_idx]        # voda a 520 zůstávají samostatné

    # přetisk tratě (purpurová) → IGNORE. Oddělit PŘED median: hodnota 255 v okně by zkreslila
    # medián sousedů. Ignore pixely dočasně na 0 (neutrální), medianuj runnability, pak vrať masku
    # dilatovanou (pokryje antialiasovaný okraj čar, který padl na sousední barvu).
    ignore = labels == IGNORE
    labels[ignore] = 0
    semantic[ignore] = 0
    # majority filtr potlačí tenké ne-plošné linie uvnitř ploch
    labels = ndimage.median_filter(labels, size=_MEDIAN_SIZE)
    semantic_majority = _categorical_majority(
        semantic, tuple(lab for lab in SEMANTIC_LABEL_VIS if lab != IGNORE)
    )
    # Základ 0-4 drží přesně původní runnability filtr. Kategoriální majority rozhoduje
    # jen o nových nezávislých třídách, aby přidání vody/520 neposunulo hranice zeleně.
    semantic = labels.copy()
    semantic[semantic_majority == SEMANTIC_WATER] = SEMANTIC_WATER
    semantic[semantic_majority == SEMANTIC_OOB] = SEMANTIC_OOB
    if ignore.any():
        ignore = ndimage.binary_dilation(ignore, iterations=_OVERPRINT_DILATE)
        labels[ignore] = IGNORE
        semantic[ignore] = IGNORE

    # layout mimo mapové území → IGNORE (Sez. 73). Spočítá se z mapově-barevných pixelů
    # (stejný color_idx) a aplikuje AŽ NAKONEC: vše mimo mapu (legenda/tabulka/titulek/papír)
    # přepíše na 255 bez ohledu na runnability/přetisk uvnitř toho okraje.
    is_map_color = np.array([k in _MAP_COLOR_KEYS for k in keys])
    map_area = _detect_map_area(is_map_color[color_idx])
    labels[~map_area] = IGNORE
    semantic[~map_area] = IGNORE

    # Kompatibilní runnability výstup.
    Image.fromarray(labels, mode="L").save(out_dir / "gt_labels.png")
    Image.fromarray(colorize(labels, _LABEL_VIS)).save(out_dir / "gt_vis.png")

    # Bezeztrátovější sémantický výstup pro vizuální GT a další plošné úlohy.
    Image.fromarray(semantic, mode="L").save(out_dir / "gt_semantic_labels.png")
    Image.fromarray(colorize(semantic, SEMANTIC_LABEL_VIS)).save(
        out_dir / "gt_semantic_vis.png"
    )

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
